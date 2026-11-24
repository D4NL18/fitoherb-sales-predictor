"""T-7.1.1 / T-7.1.2: janelas (4 datas, fator k) e modo do diagnostico. P-151, P-152, P-153.4, DA-03."""
from datetime import date
from fractions import Fraction

import pytest

from tests.trend_insights.helpers import mod

FIRST_SALE = date(2025, 1, 7)
LAST_COVERED = date(2026, 11, 8)  # dataReferencia = 2026-11-09


def _idx(year, month):
    return year * 12 + month - 1


def _spec(base, window, mode, first=FIRST_SALE, last=LAST_COVERED):
    return mod("domain.windows").build_window_spec(
        base_month_index=base, window=window, comparison_mode=mode,
        first_sale_date=first, last_covered_day=last,
    )


def test_point_window_3_is_not_contiguous_and_has_four_dates():
    spec = _spec(_idx(2026, 10), 3, "point")
    assert (spec.cur_start, spec.cur_end_exclusive) == (date(2026, 10, 1), date(2026, 11, 1))
    assert (spec.pre_start, spec.pre_end_exclusive) == (date(2026, 7, 1), date(2026, 8, 1))
    assert spec.is_contiguous is False and spec.scale_k == Fraction(1)


def test_point_window_1_is_contiguous():
    spec = _spec(_idx(2026, 10), 1, "point")
    assert spec.pre_end_exclusive == spec.cur_start and spec.is_contiguous is True


def test_average_window_3_covers_three_previous_months_and_k_is_one_third():
    spec = _spec(_idx(2026, 10), 3, "average")
    assert (spec.pre_start, spec.pre_end_exclusive) == (date(2026, 7, 1), date(2026, 10, 1))
    assert spec.is_contiguous is True and spec.scale_k == Fraction(1, 3)


def test_current_month_base_is_cut_at_reference_date_and_k_uses_covered_days():
    spec = _spec(_idx(2026, 11), 1, "point")
    assert spec.cur_end_exclusive == date(2026, 11, 9)
    assert spec.scale_k == Fraction(8, 31)


def test_pre_start_respects_first_sale_and_flags_incomplete_previous():
    spec = _spec(_idx(2026, 1), 12, "point")
    assert spec.pre_start == FIRST_SALE
    assert spec.is_previous_fully_covered is False
    assert _spec(_idx(2026, 10), 3, "point").is_previous_fully_covered is True


def _monthly_sales():
    from src.modules.sales_trend.domain.sales_trend import MonthlySales, SkuSeries, VALUE_SCALE

    first_month = _idx(2025, 1)
    count = 23
    revenue = tuple(int((1000 + 137 * i) * VALUE_SCALE) for i in range(count))
    quantity = tuple(int((10 + 3 * (i % 5)) * VALUE_SCALE) for i in range(count))
    series = SkuSeries(quantity=quantity, revenue=revenue, movement_mask=(1 << count) - 1)
    return MonthlySales(first_month=first_month, month_count=count, series={1: series}, first_sale_date=FIRST_SALE)


@pytest.mark.parametrize("mode", ["point", "average"])
@pytest.mark.parametrize("window", [1, 3, 6, 12])
@pytest.mark.parametrize("base", [(2026, 10), (2026, 11)])
@pytest.mark.parametrize("metric", ["revenue", "quantity"])
def test_delta_over_adjusted_base_reproduces_trend_variation(mode, window, base, metric):
    """P-151: delta obs / base ajustada * 100 == variacaoPct da celula (<= 0,05 pp)."""
    from src.modules.sales_trend.domain.sales_trend import VALUE_SCALE, compute_cell

    ms = _monthly_sales()
    base_idx = _idx(*base)
    cell = compute_cell(ms.series[1], base_idx, window, metric, ms, LAST_COVERED, mode=mode)
    if cell.status != "VARIACAO":
        pytest.skip("celula sem variacao")
    spec = _spec(base_idx, window, mode)
    cur = Fraction(cell.atual_bruto_escalado, VALUE_SCALE)
    pre = Fraction(cell.anterior_bruto_escalado, VALUE_SCALE)
    base_adjusted = pre * spec.scale_k
    observed = (cur - base_adjusted) / base_adjusted * 100
    assert abs(float(observed) - cell.variacao_pct) <= 0.05


@pytest.mark.parametrize(
    "status,var,low,expected",
    [
        ("VARIACAO", -30.0, False, "QUANTITATIVO"),
        ("VARIACAO", 2.0, False, "QUANTITATIVO"),
        ("VARIACAO", -1.99, False, "SEM_VARIACAO"),
        ("VARIACAO", -30.0, True, "QUALITATIVO"),
        ("SEM_BASE", None, False, "QUALITATIVO"),
        ("NOVO", None, False, "QUALITATIVO"),
        ("SEM_MOVIMENTO", None, False, "SEM_VARIACAO"),
    ],
)
def test_diagnosis_mode_from_cell_state(status, var, low, expected):
    fn = mod("domain.cell_mode").diagnosis_mode
    assert fn(status=status, variacao_pct=var, base_baixa=low) == expected
