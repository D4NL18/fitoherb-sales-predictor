"""
Motor estatístico de Viabilidade de Produto Novo (F2; P-139 a P-149; ADR-008).

Cálculo puro em memória, sem I/O e sem dependência de HTTP:
- Filtro temporal de lançamentos reais (primeira venda >= 2025-04-01 e >= 3 meses completos).
- Similaridade híbrida multicritério (tipo estrito, fornecedor 0.25, log-preço 0.35, TF-IDF 0.40).
- Curva inicial dos primeiros 3 meses líquida de devoluções (saldo negativo truncado em 0).
- Previsão conservadora P25 * 0.70 com trava inviolável <= P25 e modulação sazonal [0.90, 1.10].
- Teto maduro P75 sobre produtos pré-existentes (< 2025-04-01) e avaliação financeira de margem.
"""
from __future__ import annotations

import math
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.modules.analytics.domain.exceptions import NewProductInsufficientSimilarsError

# ---------------------------------------------------------------------------
# Constantes Imutáveis do Domínio (P-139 a P-149)
# ---------------------------------------------------------------------------

SALE_OPERATION = "VENDA"
RETURN_OPERATION_PATTERN = "DEVOLU%"
LAUNCH_CUTOFF_DATE = date(2025, 4, 1)
MIN_LAUNCH_MONTHS = 3
TOP_K_SIMILARS = 10
MIN_SIMILARS = 3
WEIGHT_SUPPLIER = 0.25
WEIGHT_PRICE = 0.35
WEIGHT_TFIDF = 0.40
NEW_PRODUCT_HAIRCUT = 0.70
MIN_BACKTEST_SUCCESS_RATE = 0.80
DEFAULT_HORIZON_MONTHS = 3
MAX_HORIZON_MONTHS = 3
SEASONALITY_MIN_FACTOR = 0.90
SEASONALITY_MAX_FACTOR = 1.10
CACHE_TTL_HOURS = 6

_PT_BR_STOPWORDS = frozenset(
    {
        "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos",
        "e", "em", "na", "nas", "no", "nos", "o", "os", "ou", "para",
        "por", "que", "se", "sem", "um", "uma", "umas", "uns",
    }
)
_PACKAGING_TERMS = frozenset(
    {
        "un", "und", "unidade", "unidades", "cx", "caixa", "pct", "pacote",
        "frasco", "fr", "vidro", "pote", "bisnaga", "ampola",
        "ml", "mg", "g", "kg", "l", "lt",
    }
)
_MEASURE_UNIT_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:ml|mg|g|kg|l|lt|un|und|cx|pct)\b")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")


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


def _strip_accents(text: str) -> str:
    """Remove diacríticos Unicode mantendo caracteres ASCII base."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def preprocess_description(text: str) -> str:
    """Normaliza descrição em pt-BR removendo acentos, pontuação, stop words e embalagens (P-142.4)."""
    cleaned = _strip_accents(str(text or "").lower())
    cleaned = _MEASURE_UNIT_RE.sub(" ", cleaned)
    cleaned = _NON_ALNUM_RE.sub(" ", cleaned)
    tokens = [
        tok
        for tok in cleaned.split()
        if tok not in _PT_BR_STOPWORDS and tok not in _PACKAGING_TERMS
    ]
    return " ".join(tokens)


def _add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    """Soma `delta` meses a `(year, month)` retornando `(novo_ano, novo_mes)`."""
    total = (year * 12 + (month - 1)) + delta
    return total // 12, (total % 12) + 1


def _last_closed_year_month(reference_date: date) -> Tuple[int, int]:
    """Retorna `(ano, mês)` do último mês civil fechado anterior a `reference_date`."""
    last_closed = reference_date.replace(day=1) - timedelta(days=1)
    return last_closed.year, last_closed.month


def _compute_tfidf_scores(target_desc: str, candidate_descs: Sequence[str]) -> np.ndarray:
    """Calcula similaridade cosseno TF-IDF (n-grams 1..2) entre alvo e candidatos."""
    if not candidate_descs:
        return np.array([], dtype=float)
    processed_target = preprocess_description(target_desc)
    processed_candidates = [preprocess_description(d) for d in candidate_descs]
    if not processed_target.strip():
        return np.zeros(len(candidate_descs), dtype=float)

    corpus = [processed_target, *processed_candidates]
    if all(not doc.strip() for doc in corpus):
        return np.zeros(len(candidate_descs), dtype=float)

    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return np.zeros(len(candidate_descs), dtype=float)

    sims = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
    return np.clip(sims, 0.0, 1.0)


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


def find_similars(
    candidates_df: pd.DataFrame,
    tipo: str,
    fornecedor: str,
    descricao: str,
    preco_venda_previsto: float,
    top_k: int = TOP_K_SIMILARS,
) -> List[SimilarProductMatch]:
    """
    Seleciona até `top_k` lançamentos similares do mesmo `tipo` estrito (P-142, P-143).
    Lança `NewProductInsufficientSimilarsError` (NEW-001) se houver < MIN_SIMILARS (3).
    """
    if candidates_df.empty:
        raise NewProductInsufficientSimilarsError(count=0)

    tipo_norm = tipo.strip().casefold()
    forn_norm = fornecedor.strip().casefold()

    same_type = candidates_df[
        candidates_df["tipo"].astype(str).str.strip().str.casefold() == tipo_norm
    ]
    if same_type.empty:
        raise NewProductInsufficientSimilarsError(count=0)

    grouped_items: List[dict] = []
    for sku_val, grp in same_type.groupby("sku", sort=False):
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
            # P-144.2: saldo líquido negativo por devoluções é truncado em 0
            curve_3m.append(max(0, int(round(raw_qty))))

        grouped_items.append(
            {
                "sku": int(sku_val),
                "descricao": str(first_row["descricao"]),
                "fornecedor": str(first_row["fornecedor"]),
                "preco": float(first_row["preco"]),
                "first_sale": first_sale,
                "curve": tuple(curve_3m),
            }
        )

    if len(grouped_items) < MIN_SIMILARS:
        raise NewProductInsufficientSimilarsError(count=len(grouped_items))

    tfidf_scores = _compute_tfidf_scores(
        descricao, [item["descricao"] for item in grouped_items]
    )

    matches: List[SimilarProductMatch] = []
    for idx, item in enumerate(grouped_items):
        s_forn = 1.0 if item["fornecedor"].strip().casefold() == forn_norm else 0.0
        cand_price = item["preco"]
        if preco_venda_previsto > 0 and cand_price > 0:
            s_preco = math.exp(-abs(math.log(preco_venda_previsto) - math.log(cand_price)))
        else:
            s_preco = 0.0
        s_tfidf = float(tfidf_scores[idx])
        s_final = (
            WEIGHT_SUPPLIER * s_forn
            + WEIGHT_PRICE * s_preco
            + WEIGHT_TFIDF * s_tfidf
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
                score_tfidf=round(s_tfidf, 6),
                quantidades_primeiros_meses=item["curve"],
            )
        )

    # P-143.1: desempate por score_preco e primeira venda mais recente
    matches.sort(
        key=lambda m: (
            -m.score_final,
            -m.score_preco,
            -m.primeira_venda.toordinal(),
            m.sku,
        )
    )
    return matches[:top_k]


def compute_conservative_curve(
    similars: Sequence[SimilarProductMatch],
    horizon_months: int = DEFAULT_HORIZON_MONTHS,
) -> List[ConservativeCurvePoint]:
    """
    Calcula P10, P25, P50 e previsão conservadora (`P25 * 0.70`) para cada mês (P-145, P-147).
    Garante matematicamente a trava inviolável `conservative_quantity <= similar_p25_quantity`.
    """
    if not similars:
        raise NewProductInsufficientSimilarsError(count=0)

    horizon = max(1, min(MAX_HORIZON_MONTHS, int(horizon_months)))
    curve: List[ConservativeCurvePoint] = []
    for m_idx in range(horizon):
        values = [max(0, s.quantidades_primeiros_meses[m_idx]) for s in similars]
        p10 = max(0, int(round(float(np.percentile(values, 10)))))
        p25_raw = float(np.percentile(values, 25))
        p25 = max(0, int(round(p25_raw)))
        p50 = max(0, int(round(float(np.percentile(values, 50)))))
        conservative = max(0, int(round(p25_raw * NEW_PRODUCT_HAIRCUT)))
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


def compute_mature_ceiling(mature_df: pd.DataFrame, tipo: str) -> int:
    """
    Calcula o Teto Maduro de Referência (`tetoMaduroP75`, P-147) sobre produtos com
    primeira venda anterior a LAUNCH_CUTOFF_DATE (2025-04-01) do mesmo `tipo`.
    """
    if mature_df.empty:
        return 0

    tipo_norm = tipo.strip().casefold()
    work = mature_df[
        mature_df["tipo"].astype(str).str.strip().str.casefold() == tipo_norm
    ]
    if work.empty:
        return 0

    if "first_sale_date" in work.columns:
        first_dates = work["first_sale_date"].map(_to_date)
        work = work.loc[first_dates < LAUNCH_CUTOFF_DATE]

    if work.empty:
        return 0

    quantities = [max(0, float(q)) for q in work["net_quantity"].tolist()]
    return max(0, int(round(float(np.percentile(quantities, 75)))))


def evaluate_financial_viability(
    preco_venda: float,
    custo_unitario: Optional[float],
    margem_minima_desejada: Optional[float],
) -> FinancialViabilityResult:
    """
    Calcula margem bruta unitária, percentual e parecer de viabilidade (P-148).
    """
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
