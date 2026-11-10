"""
Testes para janelas de meses e calendário da Tendência de Vendas (T-02).
Valida regras P-074, P-075, P-076, CA-01, CA-03, CA-04, CA-06 e CA-20.
"""
import datetime
import pytest

from tests.sales_trend.trend_sample import FIRST_SALE_DATE, LAST_COVERED_DATE


def test_window_pairs_with_year_turnover():
    """Valida janelas atual e anterior com virada de ano para Mês-Base 2026-10 e 2026-11 (CA-01)."""
    from src.modules.sales_trend.domain.month_windows import (
        month_index,
        window_pair,
        index_to_year_month,
    )

    # Mês-Base 2026-10:
    base_idx = month_index(2026, 10)

    # 1m: out/26 vs set/26
    curr_1m, prev_1m = window_pair(base_idx, 1)
    assert [index_to_year_month(i) for i in curr_1m] == [(2026, 10)]
    assert [index_to_year_month(i) for i in prev_1m] == [(2026, 9)]

    # 3m: ago-out/26 vs mai-jul/26
    curr_3m, prev_3m = window_pair(base_idx, 3)
    assert [index_to_year_month(i) for i in curr_3m] == [(2026, 8), (2026, 9), (2026, 10)]
    assert [index_to_year_month(i) for i in prev_3m] == [(2026, 5), (2026, 6), (2026, 7)]

    # 6m: mai-out/26 vs nov/25-abr/26
    curr_6m, prev_6m = window_pair(base_idx, 6)
    assert index_to_year_month(curr_6m[0]) == (2026, 5)
    assert index_to_year_month(curr_6m[-1]) == (2026, 10)
    assert index_to_year_month(prev_6m[0]) == (2025, 11)
    assert index_to_year_month(prev_6m[-1]) == (2026, 4)

    # 12m: nov/25-out/26 vs nov/24-out/25
    curr_12m, prev_12m = window_pair(base_idx, 12)
    assert index_to_year_month(curr_12m[0]) == (2025, 11)
    assert index_to_year_month(curr_12m[-1]) == (2026, 10)
    assert index_to_year_month(prev_12m[0]) == (2024, 11)
    assert index_to_year_month(prev_12m[-1]) == (2025, 10)

    # Mês-Base 2026-11:
    base_idx_nov = month_index(2026, 11)
    curr_1m_nov, prev_1m_nov = window_pair(base_idx_nov, 1)
    assert [index_to_year_month(i) for i in curr_1m_nov] == [(2026, 11)]
    assert [index_to_year_month(i) for i in prev_1m_nov] == [(2026, 10)]


def test_days_in_span_leap_year():
    """Valida cálculo de dias em anos bissextos (fev/24 = 29 dias vs fev/25 = 28 dias)."""
    from src.modules.sales_trend.domain.month_windows import month_index, days_in_span

    # Fev/2024 (bissexto)
    idx_fev24 = month_index(2024, 2)
    assert days_in_span([idx_fev24]) == 29

    # Fev/2025 (não bissexto)
    idx_fev25 = month_index(2025, 2)
    assert days_in_span([idx_fev25]) == 28


def test_covered_days_12m_partial_base():
    """Valida CA-03: Janela anterior de 12m com base 2026-10 cobre 298 de 365 dias."""
    from src.modules.sales_trend.domain.month_windows import (
        month_index,
        window_pair,
        covered_days,
        days_in_span,
    )

    base_idx = month_index(2026, 10)
    curr_12m, prev_12m = window_pair(base_idx, 12)

    total_prev = days_in_span(prev_12m)
    assert total_prev == 365  # nov/24 a out/25

    # Base inicia em 2025-01-07. De 2025-01-07 a 2025-10-31 = 298 dias
    cov_prev = covered_days(prev_12m, FIRST_SALE_DATE, LAST_COVERED_DATE)
    assert cov_prev == 298
    ratio = cov_prev / total_prev
    assert ratio >= 0.5  # 81.6% >= 50% -> não é SEM_BASE, é baseParcial


def test_covered_days_current_month_partial():
    """Valida CA-04: Mês-Base 2026-11 tem 8 dias cobertos de 30 (até 2026-11-08)."""
    from src.modules.sales_trend.domain.month_windows import (
        month_index,
        window_pair,
        covered_days,
        days_in_span,
    )

    base_idx = month_index(2026, 11)
    curr_1m, prev_1m = window_pair(base_idx, 1)

    assert days_in_span(curr_1m) == 30
    cov_curr = covered_days(curr_1m, FIRST_SALE_DATE, LAST_COVERED_DATE)
    assert cov_curr == 8  # 01 a 08 de nov


def test_sem_base_when_coverage_under_50_percent():
    """Valida CA-06: Cobertura anterior < 50% vira SEM_BASE."""
    from src.modules.sales_trend.domain.month_windows import (
        month_index,
        window_pair,
        covered_days,
        days_in_span,
        is_coverage_sufficient,
    )

    # Mês-Base 2025-06, janela 6m: anterior jul/24 a dez/24 -> 0 dias cobertos
    base_idx_06 = month_index(2025, 6)
    _, prev_6m_06 = window_pair(base_idx_06, 6)
    cov_06 = covered_days(prev_6m_06, FIRST_SALE_DATE, LAST_COVERED_DATE)
    assert cov_06 == 0
    assert not is_coverage_sufficient(cov_06, days_in_span(prev_6m_06))

    # Mês-Base 2025-07, janela 6m: anterior ago/24 a jan/25 (184 dias) -> 25 dias cobertos (13.6%)
    base_idx_07 = month_index(2025, 7)
    _, prev_6m_07 = window_pair(base_idx_07, 6)
    total_days_07 = days_in_span(prev_6m_07)
    assert total_days_07 == 184
    cov_07 = covered_days(prev_6m_07, FIRST_SALE_DATE, LAST_COVERED_DATE)
    assert cov_07 == 25  # 07 a 31 de janeiro
    assert not is_coverage_sufficient(cov_07, total_days_07)

    # Exatos 50% de cobertura NÃO é SEM_BASE (é suficiente)
    assert is_coverage_sufficient(50, 100)
    assert not is_coverage_sufficient(49, 100)


def test_base_month_validation():
    """Valida validação pura do Mês-Base (futuro -> TND-001, anterior -> TND-002, 0000-01 sem crash)."""
    from src.modules.sales_trend.domain.month_windows import (
        month_index,
        parse_base_month,
        validate_base_month,
    )
    from src.modules.sales_trend.domain.exceptions import (
        InvalidTrendParametersError,
        BaseMonthWithoutSalesError,
    )

    # Formato inválido ou 0000-01 não deve levantar ValueError nativo
    parsed = parse_base_month("0000-01")
    assert parsed is None or isinstance(parsed, int)

    # Validação de limites
    min_month = month_index(2025, 1)
    max_month = month_index(2026, 11)

    # Futuro: 2026-12 > 2026-11 -> TND-001
    future_idx = month_index(2026, 12)
    with pytest.raises(InvalidTrendParametersError) as exc_info:
        validate_base_month(future_idx, min_month, max_month, last_covered_day=LAST_COVERED_DATE)
    assert exc_info.value.code == "TND-001"
    assert "baseMonth" in exc_info.value.fields

    # Anterior: 2024-12 < 2025-01 -> TND-002
    past_idx = month_index(2024, 12)
    with pytest.raises(BaseMonthWithoutSalesError) as exc_info:
        validate_base_month(past_idx, min_month, max_month, last_covered_day=LAST_COVERED_DATE)
    assert exc_info.value.code == "TND-002"
    assert "baseMonth" in exc_info.value.fields
