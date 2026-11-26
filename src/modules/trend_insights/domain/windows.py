"""
Janelas do diagnostico (P-151): quatro datas e fator de ajuste `k`, identicos aos da Tendencia de Vendas.
Reusa `window_pair`, `covered_days` e `days_in_span` da Tendencia: a aritmetica de meses nao e reimplementada.
"""
import calendar
import datetime
from dataclasses import dataclass
from fractions import Fraction

from src.modules.sales_trend.domain.month_windows import (
    covered_days,
    days_in_span,
    index_to_year_month,
    window_pair,
)


@dataclass(frozen=True)
class WindowSpec:
    """Datas das janelas PRE e CUR (fim exclusivo) e fator `k` que leva PRE a escala de CUR."""

    pre_start: datetime.date
    pre_end_exclusive: datetime.date
    cur_start: datetime.date
    cur_end_exclusive: datetime.date
    scale_k: Fraction
    is_contiguous: bool
    is_previous_fully_covered: bool
    is_partial_base: bool
    cur_days: int
    cur_covered_days: int
    pre_days: int
    pre_covered_days: int
    pre_last_month_index: int
    cur_last_month_index: int


def _month_start(month_idx: int) -> datetime.date:
    year, month = index_to_year_month(month_idx)
    return datetime.date(year, month, 1)


def _month_end(month_idx: int) -> datetime.date:
    year, month = index_to_year_month(month_idx)
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


def _scale_factor(comparison_mode: str, window: int, is_partial: bool, cur_cov: int, pre_cov: int) -> Fraction:
    """P-151.3: mesmas tres situacoes de `compute_cell`."""
    if is_partial:
        return Fraction(cur_cov, max(1, pre_cov))
    if comparison_mode == "average" and window > 1:
        return Fraction(1, window)
    return Fraction(1)


def build_window_spec(
    base_month_index: int,
    window: int,
    comparison_mode: str,
    first_sale_date: datetime.date,
    last_covered_day: datetime.date,
) -> WindowSpec:
    """Monta as quatro datas e o fator `k` a partir do Mes-Base (P-151.1 a P-151.3)."""
    cur_span, pre_span = window_pair(base_month_index, window, mode=comparison_mode)
    pre_days = days_in_span(pre_span)
    cur_days = days_in_span(cur_span)
    pre_cov = covered_days(pre_span, first_sale_date, last_covered_day)
    cur_cov = covered_days(cur_span, first_sale_date, last_covered_day)
    is_partial = cur_cov < cur_days or pre_cov < pre_days

    cur_start = _month_start(cur_span[0])
    cur_end_inclusive = min(_month_end(cur_span[-1]), last_covered_day)
    pre_start = max(_month_start(pre_span[0]), first_sale_date)
    pre_end_exclusive = _month_end(pre_span[-1]) + datetime.timedelta(days=1)

    return WindowSpec(
        pre_start=pre_start,
        pre_end_exclusive=pre_end_exclusive,
        cur_start=cur_start,
        cur_end_exclusive=cur_end_inclusive + datetime.timedelta(days=1),
        scale_k=_scale_factor(comparison_mode, window, is_partial, cur_cov, pre_cov),
        is_contiguous=pre_end_exclusive == cur_start,
        is_previous_fully_covered=pre_cov == pre_days,
        is_partial_base=is_partial,
        cur_days=cur_days,
        cur_covered_days=cur_cov,
        pre_days=pre_days,
        pre_covered_days=pre_cov,
        pre_last_month_index=pre_span[-1],
        cur_last_month_index=cur_span[-1],
    )
