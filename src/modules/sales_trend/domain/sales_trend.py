"""
Domínio central da Tendência de Vendas (P-072 a P-079, ADR-003 DA-03 e DA-06).
Contém constantes de negócio no topo, tipos de dados imutáveis, montagem do agregado
e cálculo de célula com aritmética exata (Fraction/inteiros escalados).
"""
from dataclasses import dataclass
import datetime
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from src.modules.sales_trend.domain.month_windows import (
    covered_days,
    days_in_span,
    index_to_year_month,
    is_coverage_sufficient,
    window_pair,
)
from src.modules.sales_trend.domain.rounding import (
    round_fraction_half_up,
    round_scaled_half_up,
)

# Constantes de Negócio (P-072 a P-093)
SALE_OPERATION: str = "VENDA"
RETURN_OPERATION_PATTERN: str = "DEVOLU%"
ACTIVE_PRODUCT_MIN_PRICE: float = 0.0
WINDOW_SIZES_MONTHS: Tuple[int, ...] = (1, 3, 6, 12)
TREND_SPAN_MONTHS: int = 24
DEFAULT_METRIC: str = "revenue"
DEFAULT_SORT_WINDOW: int = 3
MIN_PREVIOUS_COVERAGE_RATIO: float = 0.5
PERCENT_DECIMALS: int = 1
LOW_BASE_MIN_QUANTITY: int = 10
LOW_BASE_MIN_REVENUE: float = 500.00
DEFAULT_MIN_VOLUME: float = 0.0
DEFAULT_PAGE_LIMIT: int = 50
MAX_PAGE_LIMIT: int = 200
MIN_SEARCH_LENGTH_DIGITS: int = 1
MIN_SEARCH_LENGTH_TEXT: int = 2
MAX_SEARCH_LENGTH: int = 60
CACHE_TTL_HOURS: int = 6
MIN_RELOAD_INTERVAL_MINUTES: int = 15
DEFAULT_GROUP_BY: str = "product"
NO_SUPPLIER_LABEL: str = "Sem fornecedor"
NO_SUPPLIER_KEY: str = "sem-fornecedor"
VALUE_SCALE: int = 10_000


@dataclass(frozen=True)
class TrendCatalogEntry:
    """Item do catálogo ativo da Fitoherb (Pc.Venda > 0)."""
    codigo: int
    descricao: str
    fornecedor: Optional[str]
    descricao_normalizada: str


@dataclass(frozen=True)
class SkuSeries:
    """Série mensal compacta com inteiros escalados e máscara de movimento."""
    quantity: Tuple[int, ...]
    revenue: Tuple[int, ...]
    movement_mask: int


@dataclass(frozen=True)
class MonthlySales:
    """Snapshot consolidado do histórico mensal de vendas por SKU ativo."""
    first_month: int
    month_count: int
    series: Mapping[int, SkuSeries]
    first_sale_date: Optional[datetime.date]


@dataclass(frozen=True)
class TrendCell:
    """Resultado do cálculo de uma célula de tendência de vendas para uma janela."""
    status: str  # VARIACAO, NOVO, SEM_MOVIMENTO, SEM_BASE
    variacao_pct: Optional[float]
    atual: float
    anterior: float
    atual_bruto_escalado: int
    anterior_bruto_escalado: int
    base_parcial: bool
    base_baixa: bool
    devolucao_liquida: bool
    atual_por_dia: Optional[float] = None
    anterior_por_dia: Optional[float] = None
    variacao_fracao: Optional[Fraction] = None


def _scale_decimal(val: Decimal) -> int:
    """Converte Decimal em inteiro escalado por VALUE_SCALE meio para cima."""
    scaled = (val * VALUE_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(scaled)


def build_monthly_sales(
    rows: Sequence[Tuple[int, int, Decimal, Decimal]],
    active_skus: Set[int],
    first_sale_date: Optional[datetime.date],
) -> MonthlySales:
    """
    Constrói a estrutura MonthlySales a partir das linhas do SQL.
    Descarta SKUs fora de active_skus durante a leitura (P-072.2).
    """
    if not rows or not active_skus:
        return MonthlySales(
            first_month=0,
            month_count=0,
            series={},
            first_sale_date=first_sale_date,
        )

    # Identifica o mês mínimo e máximo entre todas as linhas
    min_ym = min(r[1] for r in rows)
    max_ym = max(r[1] for r in rows)

    first_year, first_month_num = min_ym // 100, min_ym % 100
    last_year, last_month_num = max_ym // 100, max_ym % 100

    start_idx = first_year * 12 + first_month_num - 1
    end_idx = last_year * 12 + last_month_num - 1
    month_count = end_idx - start_idx + 1

    # Agrupa por SKU ativo
    sku_qty: Dict[int, List[int]] = {sku: [0] * month_count for sku in active_skus}
    sku_rev: Dict[int, List[int]] = {sku: [0] * month_count for sku in active_skus}
    sku_mask: Dict[int, int] = {sku: 0 for sku in active_skus}

    for sku, ym, qty, rev in rows:
        if sku not in active_skus:
            continue
        y, m = ym // 100, ym % 100
        idx = (y * 12 + m - 1) - start_idx
        if 0 <= idx < month_count:
            sku_qty[sku][idx] += _scale_decimal(qty)
            sku_rev[sku][idx] += _scale_decimal(rev)
            sku_mask[sku] |= 1 << idx

    series_map: Dict[int, SkuSeries] = {}
    for sku in active_skus:
        series_map[sku] = SkuSeries(
            quantity=tuple(sku_qty[sku]),
            revenue=tuple(sku_rev[sku]),
            movement_mask=sku_mask[sku],
        )

    return MonthlySales(
        first_month=start_idx,
        month_count=month_count,
        series=series_map,
        first_sale_date=first_sale_date,
    )


def compute_cell(
    series: SkuSeries,
    base_month_index: int,
    size: int,
    metric: str,
    monthly_sales: MonthlySales,
    last_covered_day: datetime.date,
    mode: str = "range",
) -> TrendCell:
    """
    Calcula uma célula de tendência de vendas para uma janela de 'size' meses.
    - mode='point': mês-base pontual vs mês de X meses atrás.
    - mode='average': mês-base pontual vs média mensal dos X meses anteriores.
    - mode='range': bloco de X meses vs bloco imediatamente anterior de X meses.
    Aplica piso zero, médias diárias se baseParcial, Fraction para exatidão e precedência.
    """
    curr_span, prev_span = window_pair(base_month_index, size, mode=mode)

    # 1. Cobertura da janela anterior
    days_prev = days_in_span(prev_span)
    cov_prev = covered_days(prev_span, monthly_sales.first_sale_date or datetime.date.min, last_covered_day)
    days_curr = days_in_span(curr_span)
    cov_curr = covered_days(curr_span, monthly_sales.first_sale_date or datetime.date.min, last_covered_day)

    # Menos de 50% de cobertura na anterior -> SEM_BASE (AR-2: todos selos false)
    if not is_coverage_sufficient(cov_prev, days_prev, MIN_PREVIOUS_COVERAGE_RATIO):
        return TrendCell(
            status="SEM_BASE",
            variacao_pct=None,
            atual=0.0,
            anterior=0.0,
            atual_bruto_escalado=0,
            anterior_bruto_escalado=0,
            base_parcial=False,
            base_baixa=False,
            devolucao_liquida=False,
        )

    # 2. Soma de valores escalados
    source_tuple = series.revenue if metric == "revenue" else series.quantity
    first_m = monthly_sales.first_month
    m_count = monthly_sales.month_count

    def sum_span(span: Sequence[int]) -> int:
        total = 0
        for m in span:
            idx = m - first_m
            if 0 <= idx < m_count:
                total += source_tuple[idx]
        return total

    curr_raw = sum_span(curr_span)
    prev_raw = sum_span(prev_span)

    # Piso zero (P-077)
    curr_effective = max(0, curr_raw)
    prev_effective = max(0, prev_raw)
    devolucao_liquida = (curr_raw < 0) or (prev_raw < 0)

    # 3. Base parcial e médias diárias (P-076)
    base_parcial = (cov_curr < days_curr) or (cov_prev < days_prev)
    atual_por_dia: Optional[float] = None
    anterior_por_dia: Optional[float] = None

    if base_parcial:
        curr_rate = Fraction(curr_effective, max(1, cov_curr) * VALUE_SCALE)
        prev_rate = Fraction(prev_effective, max(1, cov_prev) * VALUE_SCALE)
        atual_por_dia = float(curr_rate)
        anterior_por_dia = float(prev_rate)
    else:
        curr_rate = Fraction(curr_effective, VALUE_SCALE)
        if mode == "average" and size > 1:
            prev_rate = Fraction(prev_effective, size * VALUE_SCALE)
        else:
            prev_rate = Fraction(prev_effective, VALUE_SCALE)

    # 4. Status e Percentual de Variação
    variacao_pct: Optional[float] = None
    variacao_fracao: Optional[Fraction] = None

    if curr_effective == 0 and prev_effective == 0:
        status = "SEM_MOVIMENTO"
    elif prev_effective == 0 and curr_effective > 0:
        status = "NOVO"
    else:
        status = "VARIACAO"
        var_frac = ((curr_rate - prev_rate) / prev_rate) * 100
        # Piso de -100.0%
        if var_frac < -100:
            var_frac = Fraction(-100, 1)
        variacao_fracao = var_frac
        variacao_pct = round_fraction_half_up(var_frac, PERCENT_DECIMALS)

    # 5. Base baixa (P-079)
    base_baixa = False
    if status == "VARIACAO":
        threshold = LOW_BASE_MIN_REVENUE if metric == "revenue" else LOW_BASE_MIN_QUANTITY
        prev_nominal = (prev_effective / (size if mode == "average" else 1)) / VALUE_SCALE
        base_baixa = prev_nominal < threshold

    # Valores nominais para exibição
    places = 2 if metric == "revenue" else 3
    atual_float = round_scaled_half_up(curr_effective, places, VALUE_SCALE)
    if mode == "average" and size > 1:
        prev_scaled_display = prev_effective // size
        anterior_float = round_scaled_half_up(prev_scaled_display, places, VALUE_SCALE)
    else:
        anterior_float = round_scaled_half_up(prev_effective, places, VALUE_SCALE)

    return TrendCell(
        status=status,
        variacao_pct=variacao_pct,
        atual=atual_float,
        anterior=anterior_float,
        atual_bruto_escalado=curr_raw,
        anterior_bruto_escalado=prev_raw,
        base_parcial=base_parcial,
        base_baixa=base_baixa,
        devolucao_liquida=devolucao_liquida,
        atual_por_dia=atual_por_dia,
        anterior_por_dia=anterior_por_dia,
        variacao_fracao=variacao_fracao,
    )
