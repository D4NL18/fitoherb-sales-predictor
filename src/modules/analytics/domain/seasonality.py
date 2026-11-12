"""
Motor determinístico de Detecção de Sazonalidade por Produto (P-106 a P-114; ADR-005).

Cálculo puro em memória, sem I/O e sem dependências pesadas externas (sem statsmodels / sem prophet).
Exponibiliza `get_seasonality_index(...)` para consumo direto pelas fases F6 e F2.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.modules.analytics.domain.exceptions import SeasonalityProductNotFoundError

# Constantes de Negócio (P-106 a P-114)
MIN_MONTHS_FOR_SEASONALITY = 18
MIN_ACTIVE_MONTHS_RATIO = 0.50
MIN_YOY_CORRELATION = 0.60
MODERATE_YOY_CORRELATION = 0.35
STRONG_SEASONALITY_AMPLITUDE = 0.40
MODERATE_SEASONALITY_AMPLITUDE = 0.20
MAX_DIVERGENCE_RATIO = 0.35
PEAK_VALLEY_THRESHOLD_RATIO = 0.90
MIN_REVENUE_SHARE = 0.0005
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200
AUTOCOMPLETE_LIMIT = 20

# Enums / Níveis
STRENGTH_STRONG = "FORTE"
STRENGTH_MODERATE = "MODERADA"
STRENGTH_WEAK = "FRACA"
STRENGTH_INSUFFICIENT = "INSUFICIENTE"

CONFIDENCE_HIGH = "ALTA"
CONFIDENCE_MEDIUM = "MEDIA"
CONFIDENCE_LOW = "BAIXA"

REASON_SHORT_HISTORY = "HISTORICO_CURTO"
REASON_SPARSE_SALES = "VENDA_ESPORADICA"

MONTH_NAMES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]


@dataclass(frozen=True)
class SeasonalityProductInfo:
    codigo: int
    descricao: str
    fornecedor: str
    estoque: float
    preco_venda: float


@dataclass(frozen=True)
class SeasonalityPeakValley:
    mes_inicio: int
    mes_fim: int
    nome_periodo: str
    indice: float
    confianca: str


@dataclass(frozen=True)
class MonthlySeasonalityPoint:
    mes: int
    nome_mes: str
    indice: float
    confianca: str
    observacoes_disponiveis: int
    razao_2025: Optional[float]
    razao_2026: Optional[float]
    volume_liquido_historico: int
    receita_liquida_historica: float


@dataclass(frozen=True)
class SeasonalityResult:
    produto: SeasonalityProductInfo
    elegivel: bool
    forca: str
    motivo_insuficiencia: Optional[str]
    amplitude: float
    correlacao_yoy: Optional[float]
    pico: SeasonalityPeakValley
    vale: SeasonalityPeakValley
    serie_mensal: Tuple[MonthlySeasonalityPoint, ...]


@dataclass(frozen=True)
class SeasonalityRankingItem:
    sku: int
    descricao: str
    fornecedor: str
    forca: str
    amplitude: float
    mes_pico: str
    mes_vale: str
    faturamento_total: float
    motivo_insuficiencia: Optional[str]


def _format_period_name(start_m: int, end_m: int) -> str:
    """Formata período de meses (ex: 'Março' ou 'Mai–Jul' ou 'Nov–Jan')."""
    if start_m == end_m:
        return MONTH_NAMES_PT[start_m - 1]
    abbr = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    return f"{abbr[start_m - 1]}–{abbr[end_m - 1]}"


def _group_circular_adjacent_months(
    indices: List[float],
    center_month: int,
    threshold: float,
    is_upper: bool = True
) -> Tuple[int, int]:
    """
    Agrupa meses adjacentes circularmente (dez-jan) que satisfazem o limiar do pico ou vale.
    Retorna (mes_inicio, mes_fim).
    """
    n = 12
    # Transforma para 0-indexed
    c_idx = center_month - 1
    selected = {c_idx}

    # Expande para a esquerda
    curr = (c_idx - 1) % n
    while curr not in selected:
        val = indices[curr]
        condition = (val >= threshold) if is_upper else (val <= threshold)
        if condition:
            selected.add(curr)
            curr = (curr - 1) % n
        else:
            break

    # Expande para a direita
    curr = (c_idx + 1) % n
    while curr not in selected:
        val = indices[curr]
        condition = (val >= threshold) if is_upper else (val <= threshold)
        if condition:
            selected.add(curr)
            curr = (curr + 1) % n
        else:
            break

    sorted_indices = sorted(selected)
    # Se envolver a virada do ano (ex: 11, 0, 1 -> Nov a Fev)
    if 0 in selected and (n - 1) in selected:
        # Encontra o primeiro elemento que não está no bloco inicial
        # e o último elemento do bloco final
        left_block = []
        i = 0
        while i in selected:
            left_block.append(i)
            i += 1
        right_block = []
        j = n - 1
        while j in selected:
            right_block.append(j)
            j -= 1
        start_m = right_block[-1] + 1
        end_m = left_block[-1] + 1
        return start_m, end_m
    else:
        return sorted_indices[0] + 1, sorted_indices[-1] + 1


def _remove_linear_trend(y: np.ndarray) -> np.ndarray:
    """
    Remove tendência linear de longo prazo por regressão simples: y_detrend = y / y_hat.
    Regra P-108.
    """
    n = len(y)
    if n <= 1:
        return np.ones_like(y, dtype=float)

    t = np.arange(n, dtype=float)
    denom = np.sum((t - t.mean()) ** 2)
    if denom == 0:
        return np.ones_like(y, dtype=float)

    slope = np.sum((t - t.mean()) * (y - y.mean())) / denom
    intercept = y.mean() - slope * t.mean()
    y_hat = intercept + slope * t

    # Se a inclinação for negativa drástica que zera y_hat, usa piso seguro
    piso = max(1e-3, float(y.mean()) * 0.1)
    y_hat_safe = np.maximum(y_hat, piso)
    return y / y_hat_safe


def compute_product_seasonality(
    sku: int,
    product_sales_df: pd.DataFrame,
    catalog_info: Optional[Dict[str, Any]] = None,
) -> SeasonalityResult:
    """
    Computa o diagnóstico determinístico completo de sazonalidade de um produto.
    Regras P-106 a P-113.
    """
    if catalog_info is None:
        catalog_info = {
            "Codigo": sku,
            "Descricao": f"PRODUTO {sku}",
            "Fornecedor": "FORNECEDOR PADRAO",
            "Estoque": 0.0,
            "Pc.Venda": 0.0,
        }

    prod_info = SeasonalityProductInfo(
        codigo=int(catalog_info.get("Codigo", sku)),
        descricao=str(catalog_info.get("Descricao", f"PRODUTO {sku}")),
        fornecedor=str(catalog_info.get("Fornecedor", "")),
        estoque=float(catalog_info.get("Estoque", 0.0)),
        preco_venda=float(catalog_info.get("Pc.Venda", 0.0)),
    )

    if product_sales_df.empty:
        raise SeasonalityProductNotFoundError()

    # Filtra e ordena cronologicamente
    df = product_sales_df[product_sales_df["sku"] == sku].copy()
    if df.empty:
        raise SeasonalityProductNotFoundError()

    df = df.sort_values(by=["sale_year", "sale_month"]).reset_index(drop=True)

    # Identifica o primeiro e último mês com histórico
    first_year = int(df.iloc[0]["sale_year"])
    first_month = int(df.iloc[0]["sale_month"])
    last_year = int(df.iloc[-1]["sale_year"])
    last_month = int(df.iloc[-1]["sale_month"])

    # Monta a série temporal contínua preenchendo meses faltantes com 0 (P-106)
    continuous_records: List[Dict[str, Any]] = []
    cy, cm = first_year, first_month
    sales_map = {
        (int(r["sale_year"]), int(r["sale_month"])): (
            max(0, int(r["net_quantity"])),
            max(0.0, float(r["net_revenue"]))
        )
        for _, r in df.iterrows()
    }

    while (cy < last_year) or (cy == last_year and cm <= last_month):
        qty, rev = sales_map.get((cy, cm), (0, 0.0))
        continuous_records.append({
            "year": cy,
            "month": cm,
            "quantity": qty,
            "revenue": rev,
        })
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1

    total_months = len(continuous_records)
    active_months = sum(1 for r in continuous_records if r["quantity"] > 0)
    active_ratio = (active_months / total_months) if total_months > 0 else 0.0

    # Diagnóstico de Elegibilidade (P-107)
    elegivel = True
    motivo_insuficiencia: Optional[str] = None

    if total_months < MIN_MONTHS_FOR_SEASONALITY:
        elegivel = False
        motivo_insuficiencia = REASON_SHORT_HISTORY
    elif active_ratio < MIN_ACTIVE_MONTHS_RATIO:
        elegivel = False
        motivo_insuficiencia = REASON_SPARSE_SALES

    # Extrai quantidades líquidas
    raw_qty = np.array([r["quantity"] for r in continuous_records], dtype=float)

    # Remoção de tendência linear (P-108)
    if len(raw_qty) > 1 and raw_qty.sum() > 0:
        detrended_qty = _remove_linear_trend(raw_qty)
    else:
        detrended_qty = np.ones_like(raw_qty, dtype=float)

    for i, r in enumerate(continuous_records):
        r["detrended_qty"] = detrended_qty[i]

    # Agrupamento por ano para calcular razões anuais (P-109)
    records_by_year: Dict[int, List[Dict[str, Any]]] = {}
    for r in continuous_records:
        records_by_year.setdefault(r["year"], []).append(r)

    # Razões anuais: R_{a, m} = z_{a, m} / mean(z_a)
    yoy_ratios_by_month: Dict[int, Dict[int, float]] = {m: {} for m in range(1, 13)}
    historical_volume_by_month: Dict[int, int] = {m: 0 for m in range(1, 13)}
    historical_revenue_by_month: Dict[int, float] = {m: 0.0 for m in range(1, 13)}

    for year, y_records in records_by_year.items():
        y_detrended = np.array([item["detrended_qty"] for item in y_records], dtype=float)
        mean_y = float(y_detrended.mean()) if len(y_detrended) > 0 else 1.0
        if mean_y <= 1e-6:
            mean_y = 1.0

        for item in y_records:
            m = item["month"]
            ratio = item["detrended_qty"] / mean_y
            yoy_ratios_by_month[m][year] = ratio
            historical_volume_by_month[m] += item["quantity"]
            historical_revenue_by_month[m] += item["revenue"]

    # Calcula índice mensal bruto por média das razões disponíveis (1 ou 2)
    raw_indices: List[float] = []
    month_confidences: List[str] = []
    observations_count: List[int] = []
    ratios_2025: List[Optional[float]] = []
    ratios_2026: List[Optional[float]] = []

    for m in range(1, 13):
        year_dict = yoy_ratios_by_month[m]
        obs = len(year_dict)
        observations_count.append(obs)

        r25 = year_dict.get(2025)
        r26 = year_dict.get(2026)
        ratios_2025.append(round(r25, 4) if r25 is not None else None)
        ratios_2026.append(round(r26, 4) if r26 is not None else None)

        if obs == 0:
            raw_indices.append(1.0)
            month_confidences.append(CONFIDENCE_LOW)
        elif obs == 1:
            val = list(year_dict.values())[0]
            raw_indices.append(val)
            month_confidences.append(CONFIDENCE_LOW)  # P-112: 1 observação é BAIXA
        else:
            v1, v2 = list(year_dict.values())[:2]
            avg_val = (v1 + v2) / 2.0
            raw_indices.append(avg_val)
            max_v = max(v1, v2, 1e-6)
            rel_div = abs(v1 - v2) / max_v
            # P-112: divergência <= 0.35 -> ALTA, senão MEDIA
            conf = CONFIDENCE_HIGH if rel_div <= MAX_DIVERGENCE_RATIO else CONFIDENCE_MEDIUM
            month_confidences.append(conf)

    # Normalização final para média dos 12 meses ser exatamente 1.00 (P-109)
    mean_raw = float(np.mean(raw_indices))
    if mean_raw <= 1e-6:
        mean_raw = 1.0
    normalized_indices = [round(v / mean_raw, 4) for v in raw_indices]

    # Correlação YoY nos meses em comum (P-110)
    common_months = [m for m in range(1, 13) if 2025 in yoy_ratios_by_month[m] and 2026 in yoy_ratios_by_month[m]]
    correlacao_yoy: Optional[float] = None
    if len(common_months) >= 5:
        u = np.array([yoy_ratios_by_month[m][2025] for m in common_months], dtype=float)
        v = np.array([yoy_ratios_by_month[m][2026] for m in common_months], dtype=float)
        std_u, std_v = float(u.std()), float(v.std())
        if std_u > 1e-6 and std_v > 1e-6:
            r_val = float(np.corrcoef(u, v)[0, 1])
            correlacao_yoy = round(max(-1.0, min(1.0, r_val)), 4)
        else:
            correlacao_yoy = 0.0

    # Amplitude (P-111)
    max_idx = max(normalized_indices)
    min_idx = min(normalized_indices)
    amplitude = round(max_idx - min_idx, 4)

    # Classificação de Força (P-111)
    if not elegivel:
        forca = STRENGTH_INSUFFICIENT
    else:
        corr = correlacao_yoy if correlacao_yoy is not None else 0.0
        if corr >= MIN_YOY_CORRELATION and amplitude >= STRONG_SEASONALITY_AMPLITUDE:
            forca = STRENGTH_STRONG
        elif (corr >= MODERATE_YOY_CORRELATION and amplitude >= MODERATE_SEASONALITY_AMPLITUDE) or (amplitude >= STRONG_SEASONALITY_AMPLITUDE and corr >= 0.25):
            forca = STRENGTH_MODERATE
        else:
            forca = STRENGTH_WEAK

    # Identificação de Pico e Vale (P-113)
    pico_m = int(np.argmax(normalized_indices)) + 1
    pico_val = normalized_indices[pico_m - 1]
    pico_thresh = pico_val * PEAK_VALLEY_THRESHOLD_RATIO
    pico_start, pico_end = _group_circular_adjacent_months(normalized_indices, pico_m, pico_thresh, is_upper=True)
    pico_conf = month_confidences[pico_m - 1]

    pico_obj = SeasonalityPeakValley(
        mes_inicio=pico_start,
        mes_fim=pico_end,
        nome_periodo=_format_period_name(pico_start, pico_end),
        indice=pico_val,
        confianca=pico_conf,
    )

    vale_m = int(np.argmin(normalized_indices)) + 1
    vale_val = normalized_indices[vale_m - 1]
    # Vale limiar simétrico
    vale_thresh = vale_val + (1.0 - vale_val) * (1.0 - PEAK_VALLEY_THRESHOLD_RATIO)
    vale_start, vale_end = _group_circular_adjacent_months(normalized_indices, vale_m, vale_thresh, is_upper=False)
    vale_conf = month_confidences[vale_m - 1]

    vale_obj = SeasonalityPeakValley(
        mes_inicio=vale_start,
        mes_fim=vale_end,
        nome_periodo=_format_period_name(vale_start, vale_end),
        indice=vale_val,
        confianca=vale_conf,
    )

    # Monta lista dos 12 meses
    monthly_points: List[MonthlySeasonalityPoint] = []
    for m in range(1, 13):
        monthly_points.append(MonthlySeasonalityPoint(
            mes=m,
            nome_mes=MONTH_NAMES_PT[m - 1],
            indice=normalized_indices[m - 1],
            confianca=month_confidences[m - 1],
            observacoes_disponiveis=observations_count[m - 1],
            razao_2025=ratios_2025[m - 1],
            razao_2026=ratios_2026[m - 1],
            volume_liquido_historico=historical_volume_by_month[m],
            receita_liquida_historica=round(historical_revenue_by_month[m], 2),
        ))

    return SeasonalityResult(
        produto=prod_info,
        elegivel=elegivel,
        forca=forca,
        motivo_insuficiencia=motivo_insuficiencia,
        amplitude=amplitude,
        correlacao_yoy=correlacao_yoy,
        pico=pico_obj,
        vale=vale_obj,
        serie_mensal=tuple(monthly_points),
    )


def get_seasonality_index(
    sku: int,
    monthly_sales_df: pd.DataFrame,
    catalog_dict: Dict[int, Dict[str, Any]],
) -> SeasonalityResult:
    """
    Função pública de domínio EXPORTADA para consumo desacoplado por F6 e F2 (ADR-005 DA-05).
    """
    cat_item = catalog_dict.get(sku)
    if cat_item is None:
        raise SeasonalityProductNotFoundError()
    return compute_product_seasonality(sku=sku, product_sales_df=monthly_sales_df, catalog_info=cat_item)


def calculate_seasonality_rankings(
    monthly_sales_df: pd.DataFrame,
    catalog_dict: Dict[int, Dict[str, Any]],
    order: str = "most",
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
) -> Tuple[List[SeasonalityRankingItem], int]:
    """
    Gera lista de rankings (order='most' ou 'least') paginada (P-114).
    """
    if monthly_sales_df.empty:
        return [], 0

    total_revenue_company = float(monthly_sales_df["net_revenue"].sum())
    min_rev_threshold = total_revenue_company * MIN_REVENUE_SHARE

    # Calcula sazonalidade para cada SKU do catálogo
    items_most: List[SeasonalityRankingItem] = []
    items_least: List[SeasonalityRankingItem] = []

    # Agrupa vendas por SKU
    grouped = {sku: group for sku, group in monthly_sales_df.groupby("sku")}

    for sku, cat in catalog_dict.items():
        prod_sales = grouped.get(sku)
        if prod_sales is None or prod_sales.empty:
            # Sem vendas entra em least por histórico curto
            items_least.append(SeasonalityRankingItem(
                sku=sku,
                descricao=str(cat.get("Descricao", "")),
                fornecedor=str(cat.get("Fornecedor", "")),
                forca=STRENGTH_INSUFFICIENT,
                amplitude=0.0,
                mes_pico="-",
                mes_vale="-",
                faturamento_total=0.0,
                motivo_insuficiencia=REASON_SHORT_HISTORY,
            ))
            continue

        try:
            res = compute_product_seasonality(sku=sku, product_sales_df=prod_sales, catalog_info=cat)
        except SeasonalityProductNotFoundError:
            continue

        total_sku_revenue = float(prod_sales["net_revenue"].sum())

        if res.elegivel and res.forca in (STRENGTH_STRONG, STRENGTH_MODERATE):
            # Filtro de share mínimo de receita (P-114)
            if total_sku_revenue >= min_rev_threshold:
                items_most.append(SeasonalityRankingItem(
                    sku=sku,
                    descricao=res.produto.descricao,
                    fornecedor=res.produto.fornecedor,
                    forca=res.forca,
                    amplitude=res.amplitude,
                    mes_pico=res.pico.nome_periodo,
                    mes_vale=res.vale.nome_periodo,
                    faturamento_total=round(total_sku_revenue, 2),
                    motivo_insuficiencia=None,
                ))
        elif res.forca == STRENGTH_INSUFFICIENT:
            items_least.append(SeasonalityRankingItem(
                sku=sku,
                descricao=res.produto.descricao,
                fornecedor=res.produto.fornecedor,
                forca=res.forca,
                amplitude=res.amplitude,
                mes_pico="-",
                mes_vale="-",
                faturamento_total=round(total_sku_revenue, 2),
                motivo_insuficiencia=res.motivo_insuficiencia,
            ))

    if order == "most":
        # Ordena decrescente por amplitude e faturamento
        items_most.sort(key=lambda it: (it.amplitude, it.faturamento_total), reverse=True)
        total_items = len(items_most)
        paged = items_most[offset : offset + limit]
        return paged, total_items
    else:
        # order == "least": ordena decrescente por faturamento total
        items_least.sort(key=lambda it: it.faturamento_total, reverse=True)
        total_items = len(items_least)
        paged = items_least[offset : offset + limit]
        return paged, total_items
