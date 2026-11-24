"""
Motor estatístico de Viabilidade de Produto Novo (F2 / Cold Start; P-139 a P-149; ADR-008).

Cálculo puro em memória, sem I/O e sem dependência de HTTP:
- Consome os similares semânticos produzidos pelo motor compartilhado `product_affinity`
  (agnóstico de fornecedor e com travas estruturais de compatibilidade — sem duplicar NLP/TF-IDF).
- Curva inicial dos primeiros 3 meses líquida de devoluções (saldo negativo truncado em 0),
  ponderada por `affinityScore`.
- Previsão conservadora P25 * 0.70 com trava inviolável <= P25 e modulação sazonal [0.90, 1.10].
- Faixa de preço de referência, risco de canibalização no portfólio ativo (inclusive concorrentes),
  teto maduro P75 sobre produtos pré-existentes (< 2025-04-01) e avaliação financeira de margem.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.modules.analytics.domain.exceptions import NewProductInsufficientSimilarsError
from src.modules.analytics.domain.product_affinity import (
    DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD,
)

# ---------------------------------------------------------------------------
# Constantes Imutáveis do Domínio (P-139 a P-149)
# ---------------------------------------------------------------------------

SALE_OPERATION = "VENDA"
RETURN_OPERATION_PATTERN = "DEVOLU%"
LAUNCH_CUTOFF_DATE = date(2025, 4, 1)
MIN_LAUNCH_MONTHS = 3
TOP_K_SIMILARS = 10
MIN_SIMILARS = 3
WEIGHT_SUPPLIER = 0.10
WEIGHT_PRICE = 0.40
WEIGHT_AFFINITY = 0.50
WEIGHT_TFIDF = WEIGHT_AFFINITY  # alias retrocompatível para testes de contrato existentes
NEW_PRODUCT_HAIRCUT = 0.70
MIN_BACKTEST_SUCCESS_RATE = 0.80
DEFAULT_HORIZON_MONTHS = 3
MAX_HORIZON_MONTHS = 3
SEASONALITY_MIN_FACTOR = 0.90
SEASONALITY_MAX_FACTOR = 1.10
CACHE_TTL_HOURS = 6
HIGH_CANNIBALIZATION_AFFINITY = 0.75
MODERATE_CANNIBALIZATION_CLUSTER_SCORE = 0.60
HIGH_CANNIBALIZATION_CLUSTER_COUNT = 3
BRAND_IMPACT_MIN_FACTOR = 0.75
BRAND_IMPACT_MAX_FACTOR = 1.25
BRAND_IMPACT_EXPONENT = 0.35


# ---------------------------------------------------------------------------
# Contratos de Dados e Interfaces
# ---------------------------------------------------------------------------

class SeasonalityResult(NamedTuple):
    """Resultado desacoplado de sazonalidade de categoria (F1 -> F2)."""

    index: float
    confidence: str


class SeasonalityProvider(ABC):
    """Porta abstrata para consumo desacoplado do índice sazonal da Fase F1 (ADR-008 DA-06)."""

    @abstractmethod
    def get_category_seasonality(self, category: str, month: int) -> SeasonalityResult:
        """Retorna (index, confidence) para a categoria e mês civil (1..12)."""
        raise NotImplementedError


@dataclass(frozen=True)
class SimilarProductMatch:
    """Produto histórico selecionado como similar ao produto hipotético (P-142, P-143)."""

    sku: int
    descricao: str
    fornecedor: str
    primeira_venda: date
    preco_historico: float
    score_final: float
    score_fornecedor: float
    score_preco: float
    score_tfidf: float
    quantidades_primeiros_meses: Tuple[int, ...]
    affinity_score: float = 0.0


@dataclass(frozen=True)
class ConservativeCurvePoint:
    """Ponto mensal da curva conservadora e faixas de dispersão dos similares (P-145, P-147)."""

    month: int
    p10_quantity: int
    conservative_quantity: int
    p50_quantity: int
    similar_p25_quantity: int


@dataclass(frozen=True)
class FinancialViabilityResult:
    """Indicadores financeiros e parecer de viabilidade comercial (P-148)."""

    preco_venda: float
    custo_unitario: Optional[float]
    margem_bruta_unitaria: Optional[float]
    margem_bruta_percentual: Optional[float]
    margem_minima_desejada: Optional[float]
    viavel: Optional[bool]
    parecer: Optional[str]


@dataclass(frozen=True)
class ReferencePriceRangeResult:
    """Faixa de preço de referência dos produtos afins no catálogo ativo."""

    min_price: float
    weighted_avg_price: float
    median_price: float
    max_price: float
    price_position: str  # ABAIXO | NA_FAIXA | ACIMA
    sample_size: int


@dataclass(frozen=True)
class CannibalizationRiskProduct:
    """Item ativo do portfólio exposto a risco de canibalização pelo lançamento."""

    sku: str
    descricao: str
    fornecedor: str
    preco_atual: float
    affinity_score: float
    same_supplier: bool


@dataclass(frozen=True)
class CannibalizationRiskResult:
    """Avaliação preventiva de risco de canibalização no portfólio ativo (F6 -> F2)."""

    risk_level: str  # ALTO | MODERADO | BAIXO
    affected_sku_count: int
    same_supplier_affected_count: int
    cross_supplier_affected_count: int
    estimated_overlap_pct: float
    summary: str
    top_at_risk_products: Tuple[CannibalizationRiskProduct, ...]


@dataclass(frozen=True)
class BacktestReport:
    """Resultado do backtest temporal leave-one-out de calibração do haircut (P-145.5)."""

    total_evaluated: int
    success_count: int
    success_rate: float


# ---------------------------------------------------------------------------
# Utilitários Internos
# ---------------------------------------------------------------------------

def _to_date(value: object) -> date:
    """Converte Timestamp/datetime/str/date para `datetime.date`."""
    if isinstance(value, date) and not hasattr(value, "hour"):
        return value
    if hasattr(value, "date"):
        return value.date()
    return pd.to_datetime(value).date()


def _add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    """Soma `delta` meses a `(year, month)` retornando `(novo_ano, novo_mes)`."""
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def _last_closed_year_month(reference_date: date) -> Tuple[int, int]:
    """Retorna `(ano, mês)` do último mês civil fechado anterior a `reference_date`."""
    last_closed = reference_date.replace(day=1) - timedelta(days=1)
    return last_closed.year, last_closed.month


def _weighted_percentile(values: Sequence[float], weights: Sequence[float], q: float) -> float:
    """
    Calcula o percentil `q` (0..100) ponderado por `weights` (affinityScore).
    Quando todos os pesos são nulos ou há 1 valor, delega para `np.percentile`.
    """
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    if arr.size == 1:
        return float(arr[0])

    w = np.asarray(weights, dtype=float)
    if w.size != arr.size or float(np.sum(w)) <= 0.0:
        return float(np.percentile(arr, q))

    order = np.argsort(arr)
    sorted_vals = arr[order]
    sorted_w = w[order]
    cum_w = np.cumsum(sorted_w)
    total_w = float(cum_w[-1])
    # Centro de massa normalizado [0, 1] equivalente à interpolação linear de percentis
    cdf = (cum_w - 0.5 * sorted_w) / total_w
    target = max(0.0, min(1.0, float(q) / 100.0))
    return float(np.interp(target, cdf, sorted_vals))


def _price_similarity(target_price: float, candidate_price: float) -> float:
    """Proximidade log-preço em [0, 1]: exp(-|ln(p_alvo) - ln(p_cand)|)."""
    if target_price > 0 and candidate_price > 0:
        return math.exp(-abs(math.log(target_price) - math.log(candidate_price)))
    return 0.0


def _build_launch_curve_by_sku(df: pd.DataFrame) -> Dict[int, dict]:
    """Agrupa `df` de lançamentos por SKU extraindo curva líquida M1..M3."""
    if df.empty:
        return {}
    result: Dict[int, dict] = {}
    for sku_val, grp in df.groupby("sku", sort=False):
        first_row = grp.iloc[0]
        first_sale = _to_date(first_row["first_sale_date"])
        month_map: Dict[Tuple[int, int], float] = {}
        for row in grp.itertuples(index=False):
            key = (int(row.sale_year), int(row.sale_month))
            month_map[key] = month_map.get(key, 0.0) + float(row.net_quantity)

        curve_3m: List[int] = []
        for offset in range(MIN_LAUNCH_MONTHS):
            ym = _add_months(first_sale.year, first_sale.month, offset)
            raw_qty = month_map.get(ym, 0.0)
            curve_3m.append(max(0, int(round(raw_qty))))

        result[int(sku_val)] = {
            "sku": int(sku_val),
            "descricao": str(first_row["descricao"]),
            "fornecedor": str(first_row["fornecedor"]),
            "preco": float(first_row["preco"]),
            "first_sale": first_sale,
            "curve": tuple(curve_3m),
        }
    return result


def _build_monthly_curve_by_sku(
    monthly_df: Optional[pd.DataFrame],
    allowed_skus: Sequence[int],
) -> Dict[int, Tuple[date, Tuple[int, ...]]]:
    """
    Extrai curva de 3 meses para SKUs do portfólio ativo que possuem histórico em `monthly_df`,
    usado como apoio quando < MIN_SIMILARS dos produtos afins foram lançados após 2025-04-01.
    """
    if monthly_df is None or monthly_df.empty or not allowed_skus:
        return {}
    allowed_set = {int(s) for s in allowed_skus}
    sub = monthly_df[monthly_df["sku"].isin(allowed_set)]
    if sub.empty:
        return {}

    curves: Dict[int, Tuple[date, Tuple[int, ...]]] = {}
    for sku_val, grp in sub.groupby("sku", sort=False):
        ordered = grp.sort_values(["sale_year", "sale_month"])
        first_y = int(ordered.iloc[0]["sale_year"])
        first_m = int(ordered.iloc[0]["sale_month"])
        first_sale = date(first_y, first_m, 1)
        # Usa os 3 meses mais recentes fechados do produto maduro como referência conservadora de giro
        tail = ordered.tail(MIN_LAUNCH_MONTHS)
        qtys = [max(0, int(round(float(q)))) for q in tail["net_quantity"].tolist()]
        while len(qtys) < MIN_LAUNCH_MONTHS:
            qtys.append(qtys[-1] if qtys else 0)
        curves[int(sku_val)] = (first_sale, tuple(qtys[:MIN_LAUNCH_MONTHS]))
    return curves


# ---------------------------------------------------------------------------
# Funções de Domínio Exportadas
# ---------------------------------------------------------------------------

def filter_eligible_launches(
    df: pd.DataFrame,
    reference_date: Optional[date] = None,
) -> pd.DataFrame:
    """
    Filtra lançamentos reais elegíveis (P-139):
    - primeira venda >= LAUNCH_CUTOFF_DATE (2025-04-01);
    - pelo menos MIN_LAUNCH_MONTHS (3) meses civis completos até o último mês fechado.
    """
    if df.empty:
        return df.copy()

    ref = reference_date or date.today()
    last_y, last_m = _last_closed_year_month(ref)

    work = df.copy()
    work["_first_sale"] = work["first_sale_date"].map(_to_date)

    months_elapsed = work["_first_sale"].map(
        lambda d: (last_y - d.year) * 12 + (last_m - d.month) + 1
    )
    mask = (work["_first_sale"] >= LAUNCH_CUTOFF_DATE) & (months_elapsed >= MIN_LAUNCH_MONTHS)
    filtered = work.loc[mask].drop(columns=["_first_sale"]).copy()
    return filtered


def compute_sales_impact_maps(
    monthly_sales_df: Optional[pd.DataFrame],
    sku_to_supplier: Mapping[int, str],
) -> Tuple[Dict[int, float], Dict[str, float]]:
    """
    Calcula em memória dois mapas de impacto comercial a partir do histórico mensal:
    - `product_avg_monthly[sku]`: média mensal líquida de unidades vendidas do produto.
    - `supplier_avg_monthly[supplier_norm]`: média mensal líquida de unidades vendidas da marca
      (soma mensal média da marca na loja, refletindo o peso real de cada fornecedor:
      ex.: Integralmedica > Max Titanium > Probiotica > Pronabol).
    """
    if monthly_sales_df is None or monthly_sales_df.empty:
        return {}, {}

    work = monthly_sales_df[["sku", "sale_year", "sale_month", "net_quantity"]].copy()
    work["net_quantity"] = work["net_quantity"].astype(float).clip(lower=0.0)

    # Média mensal por SKU
    prod_avg_series = work.groupby("sku")["net_quantity"].mean()
    product_avg_monthly: Dict[int, float] = {
        int(sku): round(float(val), 2) for sku, val in prod_avg_series.items()
    }

    # Volume médio mensal total por fornecedor (soma dos SKUs por ano/mês -> média mensal da marca)
    work["_supplier"] = work["sku"].map(
        lambda s: str(sku_to_supplier.get(int(s), "")).strip().casefold()
    )
    work_sup = work[work["_supplier"] != ""]
    if work_sup.empty:
        return product_avg_monthly, {}

    sup_monthly = work_sup.groupby(["_supplier", "sale_year", "sale_month"])["net_quantity"].sum()
    sup_avg_series = sup_monthly.groupby(level=0).mean()
    supplier_avg_monthly: Dict[str, float] = {
        str(sup): round(float(val), 2) for sup, val in sup_avg_series.items()
    }
    return product_avg_monthly, supplier_avg_monthly


def select_similars_from_affinities(
    affinity_matches: Sequence[Mapping[str, Any]],
    launches_df: pd.DataFrame,
    fornecedor: str,
    preco_venda_previsto: float,
    monthly_sales_df: Optional[pd.DataFrame] = None,
    top_k: int = TOP_K_SIMILARS,
    product_avg_monthly: Optional[Mapping[int, float]] = None,
    supplier_avg_monthly: Optional[Mapping[str, float]] = None,
) -> List[SimilarProductMatch]:
    """
    Seleciona até `top_k` produtos de referência a partir das afinidades semânticas
    retornadas por `product_affinity_service.find_similar_for_new_product(...)`.

    Prioriza lançamentos reais elegíveis (>= 2025-04-01); se houver menos que `MIN_SIMILARS`
    lançamentos recentes entre os produtos afins, complementa com produtos ativos afins
    presentes em `monthly_sales_df` para manter o cold start aderente ao produto.
    Lança `NewProductInsufficientSimilarsError` (NEW-001) se houver < MIN_SIMILARS (3).
    """
    forn_norm = fornecedor.strip().casefold()
    launch_by_sku = _build_launch_curve_by_sku(launches_df)

    affinity_by_sku: Dict[int, Mapping[str, Any]] = {}
    for item in affinity_matches:
        try:
            sku_int = int(str(item["sku"]).strip())
        except (KeyError, ValueError, TypeError):
            continue
        affinity_by_sku[sku_int] = item

    # 1) Lançamentos recentes que estão no conjunto de afinidades compatíveis
    selected_entries: List[Tuple[dict, float]] = []
    used_skus: set[int] = set()
    for sku_int, aff_item in affinity_by_sku.items():
        if sku_int in launch_by_sku:
            selected_entries.append((launch_by_sku[sku_int], float(aff_item.get("affinityScore", 0.0))))
            used_skus.add(sku_int)

    # 2) Se menos que MIN_SIMILARS lançamentos recentes forem afins, complementa com SKUs afins maduros
    if len(selected_entries) < MIN_SIMILARS and monthly_sales_df is not None and not monthly_sales_df.empty:
        remaining_skus = [s for s in affinity_by_sku if s not in used_skus]
        monthly_curves = _build_monthly_curve_by_sku(monthly_sales_df, remaining_skus)
        for sku_int in remaining_skus:
            if sku_int not in monthly_curves:
                continue
            aff_item = affinity_by_sku[sku_int]
            first_sale, curve_3m = monthly_curves[sku_int]
            selected_entries.append(
                (
                    {
                        "sku": sku_int,
                        "descricao": str(aff_item.get("description") or ""),
                        "fornecedor": str(aff_item.get("supplier") or ""),
                        "preco": float(aff_item.get("currentPrice") or 0.0),
                        "first_sale": first_sale,
                        "curve": curve_3m,
                    },
                    float(aff_item.get("affinityScore", 0.0)),
                )
            )
            used_skus.add(sku_int)

    if len(selected_entries) < MIN_SIMILARS:
        raise NewProductInsufficientSimilarsError(count=len(selected_entries))

    matches: List[SimilarProductMatch] = []
    for item, aff_score in selected_entries:
        s_aff = max(0.0, min(1.0, float(aff_score)))
        s_forn = 1.0 if item["fornecedor"].strip().casefold() == forn_norm else 0.0
        cand_price = float(item["preco"])
        s_preco = _price_similarity(preco_venda_previsto, cand_price)
        s_final = (
            WEIGHT_SUPPLIER * s_forn
            + WEIGHT_PRICE * s_preco
            + WEIGHT_AFFINITY * s_aff
        )
        matches.append(
            SimilarProductMatch(
                sku=item["sku"],
                descricao=item["descricao"],
                fornecedor=item["fornecedor"],
                primeira_venda=item["first_sale"],
                preco_historico=round(cand_price, 2),
                score_final=round(s_final, 6),
                score_fornecedor=round(s_forn, 6),
                score_preco=round(s_preco, 6),
                score_tfidf=round(s_aff, 6),
                quantidades_primeiros_meses=item["curve"],
                affinity_score=round(s_aff, 4),
            )
        )

    prod_sales = product_avg_monthly or {}
    sup_sales = supplier_avg_monthly or {}

    def _impact_tiebreak(m: SimilarProductMatch) -> Tuple[float, float]:
        p_avg = float(prod_sales.get(m.sku, 0.0))
        if p_avg <= 0.0 and m.quantidades_primeiros_meses:
            p_avg = sum(m.quantidades_primeiros_meses) / len(m.quantidades_primeiros_meses)
        s_avg = float(sup_sales.get(m.fornecedor.strip().casefold(), 0.0))
        return (p_avg, s_avg)

    matches.sort(
        key=lambda m: (
            -round(m.score_final, 3),
            -round(m.affinity_score, 3),
            -_impact_tiebreak(m)[1],  # impacto médio mensal da marca (Integral > Max > Probiotica...)
            -_impact_tiebreak(m)[0],  # média mensal de vendas do produto
            -m.score_preco,
            -m.primeira_venda.toordinal(),
            m.sku,
        )
    )
    return matches[:top_k]


def find_similars(
    candidates_df: pd.DataFrame,
    tipo: Optional[str],
    fornecedor: str,
    descricao: str,
    preco_venda_previsto: float,
    top_k: int = TOP_K_SIMILARS,
    affinity_scores: Optional[Mapping[int, float]] = None,
) -> List[SimilarProductMatch]:
    """
    Seleciona até `top_k` lançamentos similares (P-142, P-143) sem duplicar NLP/TF-IDF:
    recebe opcionalmente `affinity_scores` calculados por `product_affinity_service`
    (ou usa score neutro 0.0 quando chamado em modo puramente tabular/offline).
    """
    if candidates_df.empty:
        raise NewProductInsufficientSimilarsError(count=0)

    tipo_norm = tipo.strip().casefold() if tipo and tipo.strip() else ""
    forn_norm = fornecedor.strip().casefold()

    if tipo_norm:
        pool_df = candidates_df[
            candidates_df["tipo"].astype(str).str.strip().str.casefold() == tipo_norm
        ]
    else:
        pool_df = candidates_df

    if pool_df.empty:
        raise NewProductInsufficientSimilarsError(count=0)

    launch_by_sku = _build_launch_curve_by_sku(pool_df)
    if len(launch_by_sku) < MIN_SIMILARS:
        raise NewProductInsufficientSimilarsError(count=len(launch_by_sku))

    matches: List[SimilarProductMatch] = []
    for sku_int, item in launch_by_sku.items():
        s_aff = max(0.0, min(1.0, float((affinity_scores or {}).get(sku_int, 0.0))))
        s_forn = 1.0 if item["fornecedor"].strip().casefold() == forn_norm else 0.0
        cand_price = float(item["preco"])
        s_preco = _price_similarity(preco_venda_previsto, cand_price)
        s_final = (
            WEIGHT_SUPPLIER * s_forn
            + WEIGHT_PRICE * s_preco
            + WEIGHT_AFFINITY * s_aff
        )
        matches.append(
            SimilarProductMatch(
                sku=sku_int,
                descricao=item["descricao"],
                fornecedor=item["fornecedor"],
                primeira_venda=item["first_sale"],
                preco_historico=round(cand_price, 2),
                score_final=round(s_final, 6),
                score_fornecedor=round(s_forn, 6),
                score_preco=round(s_preco, 6),
                score_tfidf=round(s_aff, 6),
                quantidades_primeiros_meses=item["curve"],
                affinity_score=round(s_aff, 4),
            )
        )

    matches.sort(
        key=lambda m: (
            -m.score_final,
            -m.score_preco,
            -m.primeira_venda.toordinal(),
            m.sku,
        )
    )
    return matches[:top_k]


def compute_brand_strength_factor(
    similars: Sequence[SimilarProductMatch],
    target_fornecedor: Optional[str],
    supplier_avg_monthly: Optional[Mapping[str, float]],
) -> float:
    """
    Calcula o fator de tração comercial da marca alvo frente às marcas dos produtos de referência:
    `(media_marca_alvo / media_ponderada_marcas_similares) ** 0.35`, limitado a `[0.75, 1.25]`.
    Assim, marcas com maior giro real (ex.: Integralmedica > Max Titanium > Probiótica > Pronabol)
    impactam diretamente a projeção real de unidades, preservando a trava conservadora `<= P25`.
    """
    if not target_fornecedor or not supplier_avg_monthly or not similars:
        return 1.0

    target_sales = float(supplier_avg_monthly.get(target_fornecedor.strip().casefold(), 0.0))
    if target_sales <= 0.0:
        return 1.0

    weighted_sum = 0.0
    weight_total = 0.0
    for s in similars:
        sup_sales = float(supplier_avg_monthly.get(s.fornecedor.strip().casefold(), 0.0))
        if sup_sales <= 0.0:
            continue
        w = max(0.01, float(s.affinity_score or s.score_tfidf or 1.0))
        weighted_sum += sup_sales * w
        weight_total += w

    if weight_total <= 0.0 or weighted_sum <= 0.0:
        return 1.0

    ref_avg_sales = weighted_sum / weight_total
    ratio = target_sales / ref_avg_sales
    factor = ratio ** BRAND_IMPACT_EXPONENT
    return round(max(BRAND_IMPACT_MIN_FACTOR, min(BRAND_IMPACT_MAX_FACTOR, factor)), 4)


def compute_conservative_curve(
    similars: Sequence[SimilarProductMatch],
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
    product_avg_monthly: Optional[Mapping[int, float]] = None,
    supplier_avg_monthly: Optional[Mapping[str, float]] = None,
    target_fornecedor: Optional[str] = None,
) -> List[ConservativeCurvePoint]:
    """
    Calcula P10, P25, P50 e previsão conservadora (`P25 * 0.70 * fator_marca`) para cada mês (P-145, P-147),
    ponderando pela afinidade semântica (`affinity_score`) e pelo giro médio mensal real dos produtos/marcas.
    Garante matematicamente a trava inviolável `conservative_quantity <= similar_p25_quantity`.
    """
    if not similars:
        raise NewProductInsufficientSimilarsError(count=0)

    horizon = max(1, min(MAX_HORIZON_MONTHS, int(horizon_months)))
    prod_sales = product_avg_monthly or {}
    raw_prod_vols = [
        float(prod_sales.get(s.sku, 0.0))
        or (sum(s.quantidades_primeiros_meses) / max(1, len(s.quantidades_primeiros_meses)))
        for s in similars
    ]
    max_vol = max(raw_prod_vols) if raw_prod_vols else 0.0

    weights: List[float] = []
    for idx, s in enumerate(similars):
        aff = max(0.0, float(s.affinity_score or s.score_tfidf))
        if aff <= 0.0:
            weights.append(0.0)
            continue
        vol_norm = (math.log1p(raw_prod_vols[idx]) / math.log1p(max_vol)) if max_vol > 0.0 else 0.5
        # 70% afinidade pura + 30% peso pelo giro real do produto
        weights.append(aff * (0.70 + 0.30 * vol_norm))

    use_weights = sum(weights) > 0.0
    brand_factor = compute_brand_strength_factor(
        similars=similars,
        target_fornecedor=target_fornecedor,
        supplier_avg_monthly=supplier_avg_monthly,
    )

    curve: List[ConservativeCurvePoint] = []
    for m_idx in range(horizon):
        values = [max(0, s.quantidades_primeiros_meses[m_idx]) for s in similars]
        if use_weights:
            p10 = max(0, int(round(_weighted_percentile(values, weights, 10))))
            p25_raw = _weighted_percentile(values, weights, 25)
            p50 = max(0, int(round(_weighted_percentile(values, weights, 50))))
        else:
            p10 = max(0, int(round(float(np.percentile(values, 10)))))
            p25_raw = float(np.percentile(values, 25))
            p50 = max(0, int(round(float(np.percentile(values, 50)))))

        p25 = max(0, int(round(p25_raw)))
        conservative = max(0, int(round(p25_raw * NEW_PRODUCT_HAIRCUT * brand_factor)))
        conservative = min(conservative, p25)
        assert conservative <= p25  # P-145.3: trava de segurança inviolável
        curve.append(
            ConservativeCurvePoint(
                month=m_idx + 1,
                p10_quantity=p10,
                conservative_quantity=conservative,
                p50_quantity=p50,
                similar_p25_quantity=p25,
            )
        )
    return curve


def compute_reference_price_range(
    affinity_matches: Sequence[Mapping[str, Any]],
    preco_venda_previsto: float,
) -> Optional[ReferencePriceRangeResult]:
    """
    Calcula a faixa de preço de referência dos produtos afins ativos, ponderada por `affinityScore`.
    """
    priced = [
        (float(item.get("currentPrice") or 0.0), max(0.01, float(item.get("affinityScore") or 0.0)))
        for item in affinity_matches
        if float(item.get("currentPrice") or 0.0) > 0.0
    ]
    if not priced:
        return None

    prices = [p for p, _ in priced]
    weights = [w for _, w in priced]
    min_p = round(min(prices), 2)
    max_p = round(max(prices), 2)
    median_p = round(float(np.median(prices)), 2)
    weighted_avg = round(sum(p * w for p, w in priced) / sum(weights), 2)

    if preco_venda_previsto < min_p * 0.95:
        position = "ABAIXO"
    elif preco_venda_previsto > max_p * 1.05:
        position = "ACIMA"
    else:
        position = "NA_FAIXA"

    return ReferencePriceRangeResult(
        min_price=min_p,
        weighted_avg_price=weighted_avg,
        median_price=median_p,
        max_price=max_p,
        price_position=position,
        sample_size=len(priced),
    )


def compute_cannibalization_risk(
    affinity_matches: Sequence[Mapping[str, Any]],
    target_fornecedor: str,
    threshold: float = DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD,
    product_avg_monthly: Optional[Mapping[int, float]] = None,
    supplier_avg_monthly: Optional[Mapping[str, float]] = None,
) -> CannibalizationRiskResult:
    """
    Avalia o risco preventivo de canibalização do novo lançamento sobre produtos ativos
    do portfólio (mesmo fornecedor e concorrentes de outros fornecedores), usando o mesmo
    limiar de afinidade semântica da F6 (`DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD = 0.50`).
    Desempata produtos de mesma afinidade pelo impacto real de vendas (média mensal da marca e do produto).
    """
    target_sup_norm = target_fornecedor.strip().casefold()
    prod_sales = product_avg_monthly or {}
    sup_sales = supplier_avg_monthly or {}
    at_risk: List[CannibalizationRiskProduct] = []

    for item in affinity_matches:
        score = float(item.get("affinityScore") or 0.0)
        if score < threshold:
            continue
        sup = str(item.get("supplier") or "").strip()
        at_risk.append(
            CannibalizationRiskProduct(
                sku=str(item.get("sku") or ""),
                descricao=str(item.get("description") or "").strip(),
                fornecedor=sup,
                preco_atual=round(float(item.get("currentPrice") or 0.0), 2),
                affinity_score=round(score, 4),
                same_supplier=bool(target_sup_norm and sup.casefold() == target_sup_norm),
            )
        )

    def _risk_sort_key(p: CannibalizationRiskProduct) -> Tuple[float, float, float, str]:
        sku_int = int(p.sku) if p.sku.isdigit() else -1
        p_avg = float(prod_sales.get(sku_int, 0.0))
        s_avg = float(sup_sales.get(p.fornecedor.strip().casefold(), 0.0))
        return (-round(p.affinity_score, 3), -s_avg, -p_avg, p.sku)

    at_risk.sort(key=_risk_sort_key)
    affected_count = len(at_risk)
    same_sup_count = sum(1 for p in at_risk if p.same_supplier)
    cross_sup_count = affected_count - same_sup_count

    if affected_count == 0:
        return CannibalizationRiskResult(
            risk_level="BAIXO",
            affected_sku_count=0,
            same_supplier_affected_count=0,
            cross_supplier_affected_count=0,
            estimated_overlap_pct=0.0,
            summary=(
                "Baixo risco de canibalização: nenhum produto ativo do portfólio apresenta "
                "afinidade semântica >= 50% com este lançamento."
            ),
            top_at_risk_products=(),
        )

    top_scores = [p.affinity_score for p in at_risk[:3]]
    base_overlap_pct = (sum(top_scores) / len(top_scores)) * 100.0

    # Pondera a pressão de canibalização pela força comercial relativa da marca lançadora
    brand_pressure = 1.0
    if sup_sales:
        target_sup_sales = float(sup_sales.get(target_sup_norm, 0.0))
        ref_sup_vals = [
            float(sup_sales.get(p.fornecedor.strip().casefold(), 0.0))
            for p in at_risk[:10]
            if float(sup_sales.get(p.fornecedor.strip().casefold(), 0.0)) > 0.0
        ]
        if target_sup_sales > 0.0 and ref_sup_vals:
            avg_ref_sup = sum(ref_sup_vals) / len(ref_sup_vals)
            brand_pressure = max(
                BRAND_IMPACT_MIN_FACTOR,
                min(BRAND_IMPACT_MAX_FACTOR, (target_sup_sales / avg_ref_sup) ** BRAND_IMPACT_EXPONENT),
            )

    estimated_overlap_pct = round(min(100.0, base_overlap_pct * brand_pressure), 1)
    high_cluster = sum(1 for p in at_risk if p.affinity_score >= MODERATE_CANNIBALIZATION_CLUSTER_SCORE)

    effective_top_score = min(1.0, at_risk[0].affinity_score * brand_pressure)
    if effective_top_score >= HIGH_CANNIBALIZATION_AFFINITY or high_cluster >= HIGH_CANNIBALIZATION_CLUSTER_COUNT:
        risk_level = "ALTO"
        level_label = "Alto risco de canibalização"
    else:
        risk_level = "MODERADO"
        level_label = "Risco moderado de canibalização"

    summary = (
        f"{level_label}: {affected_count} produto(s) ativo(s) no portfólio "
        f"({same_sup_count} do mesmo fornecedor e {cross_sup_count} de outros fornecedores) "
        "apresentam afinidade semântica >= 50% e podem sofrer migração de demanda."
    )

    return CannibalizationRiskResult(
        risk_level=risk_level,
        affected_sku_count=affected_count,
        same_supplier_affected_count=same_sup_count,
        cross_supplier_affected_count=cross_sup_count,
        estimated_overlap_pct=estimated_overlap_pct,
        summary=summary,
        top_at_risk_products=tuple(at_risk[:5]),
    )


def apply_seasonality_and_clamp(
    base_quantity: int,
    p25_quantity: int,
    category: str,
    calendar_month: int,
    provider: Optional[SeasonalityProvider],
) -> Tuple[int, float, str, str]:
    """
    Modula a previsão conservadora pelo índice sazonal de F1 amortecido em [0.90, 1.10] (P-146).
    Adota fator neutro 1.00 se provider ausente ou confiança BAIXA/INSUFICIENTE,
    preservando sempre a trava `<= p25_quantity`.
    """
    safe_base = min(max(0, int(base_quantity)), max(0, int(p25_quantity)))
    if provider is None:
        return safe_base, 1.00, "PADRAO", "UNAVAILABLE"

    result = provider.get_category_seasonality(category, calendar_month)
    if result is None:
        return safe_base, 1.00, "PADRAO", "UNAVAILABLE"

    confidence = str(result.confidence or "PADRAO").upper()
    if confidence in ("BAIXA", "INSUFICIENTE"):
        return safe_base, 1.00, confidence, "FALLBACK_NEUTRAL"

    factor = max(SEASONALITY_MIN_FACTOR, min(SEASONALITY_MAX_FACTOR, float(result.index)))
    modulated = max(0, int(round(safe_base * factor)))
    clamped = min(modulated, max(0, int(p25_quantity)))
    assert clamped <= max(0, int(p25_quantity))  # P-146.4
    return clamped, round(factor, 4), confidence, "APPLIED"


def compute_mature_ceiling(
    mature_df: pd.DataFrame,
    tipo: Optional[str] = None,
    fornecedor: Optional[str] = None,
    similar_skus: Optional[Sequence[int]] = None,
) -> int:
    """
    Calcula o Teto Maduro de Referência (`tetoMaduroP75`, P-147) sobre produtos com
    primeira venda anterior a LAUNCH_CUTOFF_DATE (2025-04-01).
    - Se `tipo` for informado, restringe ao mesmo `tipo`.
    - Se `similar_skus` (do índice de afinidade) forem informados, prioriza esses SKUs maduros.
    - Fallback para `fornecedor` quando disponível.
    """
    if mature_df.empty:
        return 0

    work = mature_df
    tipo_norm = tipo.strip().casefold() if tipo and tipo.strip() else ""
    if tipo_norm:
        work = work[work["tipo"].astype(str).str.strip().str.casefold() == tipo_norm]
        if work.empty:
            return 0

    if "first_sale_date" in work.columns:
        first_dates = work["first_sale_date"].map(_to_date)
        work = work.loc[first_dates < LAUNCH_CUTOFF_DATE]

    if work.empty:
        return 0

    if not tipo_norm:
        filtered_work = None
        if similar_skus and "sku" in work.columns:
            sku_set = {int(s) for s in similar_skus}
            matched = work[work["sku"].isin(sku_set)]
            if not matched.empty:
                filtered_work = matched

        if filtered_work is None and fornecedor and "fornecedor" in work.columns:
            forn_norm = fornecedor.strip().casefold()
            forn_work = work[work["fornecedor"].astype(str).str.strip().str.casefold() == forn_norm]
            if not forn_work.empty:
                filtered_work = forn_work

        if filtered_work is not None and not filtered_work.empty:
            work = filtered_work

    quantities = [max(0, float(q)) for q in work["net_quantity"].tolist()]
    return max(0, int(round(float(np.percentile(quantities, 75)))))


def evaluate_financial_viability(
    preco_venda: float,
    custo_unitario: Optional[float],
    margem_minima_desejada: Optional[float],
) -> FinancialViabilityResult:
    """Calcula margem bruta unitária, percentual e parecer de viabilidade (P-148)."""
    if custo_unitario is None:
        return FinancialViabilityResult(
            preco_venda=round(float(preco_venda), 2),
            custo_unitario=None,
            margem_bruta_unitaria=None,
            margem_bruta_percentual=None,
            margem_minima_desejada=margem_minima_desejada,
            viavel=None,
            parecer=None,
        )

    margem_unit = round(float(preco_venda) - float(custo_unitario), 2)
    margem_pct = (float(preco_venda) - float(custo_unitario)) / float(preco_venda) if preco_venda > 0 else 0.0
    margem_pct_rounded = round(margem_pct, 4)

    viavel: Optional[bool] = None
    parecer: Optional[str] = None
    if margem_minima_desejada is not None:
        viavel = margem_pct >= float(margem_minima_desejada) - 1e-9
        pct_fmt = f"{margem_pct * 100:.1f}".replace(".", ",")
        min_fmt = f"{float(margem_minima_desejada) * 100:.1f}".replace(".", ",")
        if viavel:
            parecer = (
                f"Produto viável: margem bruta projetada de {pct_fmt}% "
                f"supera ou iguala a margem mínima de {min_fmt}%."
            )
        else:
            parecer = (
                f"Produto inviável: margem bruta projetada de {pct_fmt}% "
                f"abaixo da margem mínima de {min_fmt}%."
            )

    return FinancialViabilityResult(
        preco_venda=round(float(preco_venda), 2),
        custo_unitario=round(float(custo_unitario), 2),
        margem_bruta_unitaria=margem_unit,
        margem_bruta_percentual=margem_pct_rounded,
        margem_minima_desejada=margem_minima_desejada,
        viavel=viavel,
        parecer=parecer,
    )


def run_backtest_calibration(
    df: pd.DataFrame,
    reference_date: Optional[date] = None,
) -> BacktestReport:
    """
    Backtest temporal leave-one-out sobre lançamentos reais elegíveis (P-145.5).
    Avalia a fração de lançamentos cuja venda real acumulada nos 3 primeiros meses
    superou a previsão conservadora calculada a partir dos demais similares.
    """
    eligible = filter_eligible_launches(df, reference_date=reference_date)
    if eligible.empty:
        return BacktestReport(total_evaluated=0, success_count=0, success_rate=0.0)

    total_evaluated = 0
    success_count = 0

    for tipo_val, tipo_df in eligible.groupby("tipo", sort=False):
        skus = list(tipo_df["sku"].unique())
        if len(skus) <= MIN_SIMILARS:
            continue

        for target_sku in skus:
            target_rows = tipo_df[tipo_df["sku"] == target_sku]
            train_df = tipo_df[tipo_df["sku"] != target_sku]
            first_row = target_rows.iloc[0]
            first_sale = _to_date(first_row["first_sale_date"])

            month_map: Dict[Tuple[int, int], float] = {}
            for row in target_rows.itertuples(index=False):
                ym = (int(row.sale_year), int(row.sale_month))
                month_map[ym] = month_map.get(ym, 0.0) + float(row.net_quantity)

            actual_total = sum(
                max(0, int(round(month_map.get(_add_months(first_sale.year, first_sale.month, i), 0.0))))
                for i in range(MIN_LAUNCH_MONTHS)
            )

            try:
                similars = find_similars(
                    candidates_df=train_df,
                    tipo=str(tipo_val),
                    fornecedor=str(first_row["fornecedor"]),
                    descricao=str(first_row["descricao"]),
                    preco_venda_previsto=float(first_row["preco"]),
                )
            except NewProductInsufficientSimilarsError:
                continue

            curve = compute_conservative_curve(similars, horizon_months=MIN_LAUNCH_MONTHS)
            predicted_total = sum(p.conservative_quantity for p in curve)

            total_evaluated += 1
            if actual_total > predicted_total:
                success_count += 1

    success_rate = (success_count / total_evaluated) if total_evaluated > 0 else 0.0
    return BacktestReport(
        total_evaluated=total_evaluated,
        success_count=success_count,
        success_rate=round(success_rate, 4),
    )
