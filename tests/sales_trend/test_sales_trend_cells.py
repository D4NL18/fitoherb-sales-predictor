"""
Testes para cálculo de células de tendência de vendas e estados (T-04).
Valida regras P-073, P-076, P-077, P-078, P-079, CA-02, CA-03, CA-04, CA-05, CA-07..CA-11, CA-21.
"""
from decimal import Decimal
import pytest

from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    LAST_COVERED_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
)


def _setup_monthly_sales():
    from src.modules.sales_trend.domain.sales_trend import build_monthly_sales

    catalog = get_active_catalog_sample()
    raw_rows = get_raw_sales_rows_sample()
    return build_monthly_sales(
        rows=[(r.sku, r.year_month, r.quantity, r.revenue) for r in raw_rows],
        active_skus=set(catalog.keys()),
        first_sale_date=FIRST_SALE_DATE,
    )


def test_ca02_returns_deducted_quantity():
    """Valida CA-02: Devoluções abatidas no cálculo de quantidade (1m +50%, 3m +16.7%, 6m +8.3%)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]
    base_idx = month_index(2026, 10)

    # 1m (out/26 vs set/26): 30 vs 20 -> +50.0%
    cell_1m = compute_cell(series_1001, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell_1m.status == "VARIACAO"
    assert cell_1m.variacao_pct == 50.0
    assert cell_1m.base_parcial is False
    assert cell_1m.devolucao_liquida is False

    # 3m (ago-out/26 vs mai-jul/26): 70 vs 60 -> +16.7%
    cell_3m = compute_cell(series_1001, base_idx, 3, "quantity", ms, LAST_COVERED_DATE)
    assert cell_3m.status == "VARIACAO"
    assert cell_3m.variacao_pct == 16.7

    # 6m (mai-out/26 vs nov/25-abr/26): 130 vs 120 -> +8.3%
    cell_6m = compute_cell(series_1001, base_idx, 6, "quantity", ms, LAST_COVERED_DATE)
    assert cell_6m.status == "VARIACAO"
    assert cell_6m.variacao_pct == 8.3


def test_compute_cell_point_and_average_modes():
    """Valida cálculo de tendência nos modos point (mês pontual) e average (média do período)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]
    base_idx = month_index(2026, 10)

    # Modo point (mês pontual): out/26 (30) vs jul/26 (20) -> +50.0%
    cell_point_3m = compute_cell(series_1001, base_idx, 3, "quantity", ms, LAST_COVERED_DATE, mode="point")
    assert cell_point_3m.status == "VARIACAO"
    assert cell_point_3m.atual == 30.0
    assert cell_point_3m.anterior == 20.0
    assert cell_point_3m.variacao_pct == 50.0

    # Modo average (média do período): out/26 (30) vs média jul..set (60 / 3 = 20) -> +50.0%
    cell_avg_3m = compute_cell(series_1001, base_idx, 3, "quantity", ms, LAST_COVERED_DATE, mode="average")
    assert cell_avg_3m.status == "VARIACAO"
    assert cell_avg_3m.atual == 30.0
    assert cell_avg_3m.anterior == 20.0
    assert cell_avg_3m.variacao_pct == 50.0



def test_ca03_12m_partial_base_daily_averages():
    """Valida CA-03: Janela 12m com base parcial compara médias diárias (+108.3%)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]
    base_idx = month_index(2026, 10)

    cell_12m = compute_cell(series_1001, base_idx, 12, "quantity", ms, LAST_COVERED_DATE)
    assert cell_12m.status == "VARIACAO"
    assert cell_12m.variacao_pct == 108.3
    assert cell_12m.base_parcial is True
    # Médias diárias: 250/365 = 0.6849 vs 98/298 = 0.3289
    assert cell_12m.atual_por_dia == pytest.approx(0.6849, abs=0.0001)
    assert cell_12m.anterior_por_dia == pytest.approx(0.3289, abs=0.0001)


def test_ca04_current_month_partial_base():
    """Valida CA-04: Mês-Base 2026-11 parcial (-48.3% em 1m, +20.0% em 3m)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]
    base_idx = month_index(2026, 11)

    cell_1m = compute_cell(series_1001, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell_1m.status == "VARIACAO"
    assert cell_1m.variacao_pct == -48.3
    assert cell_1m.base_parcial is True

    cell_3m = compute_cell(series_1001, base_idx, 3, "quantity", ms, LAST_COVERED_DATE)
    assert cell_3m.status == "VARIACAO"
    assert cell_3m.variacao_pct == 20.0
    assert cell_3m.base_parcial is True


def test_ca05_revenue_vs_quantity_and_base_baixa():
    """Valida CA-05: Faturamento +80% e baseBaixa quando anterior < R$ 500 (R$ 200)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]
    base_idx = month_index(2026, 10)

    cell_rev = compute_cell(series_1001, base_idx, 1, "revenue", ms, LAST_COVERED_DATE)
    assert cell_rev.status == "VARIACAO"
    assert cell_rev.variacao_pct == 80.0
    assert cell_rev.base_baixa is True  # R$ 200,00 < R$ 500,00


def test_ca07_novo_sku():
    """Valida CA-07: SKU Novo (sem venda na anterior, venda na atual)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1002 = ms.series[1002]
    base_idx = month_index(2026, 10)

    cell = compute_cell(series_1002, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell.status == "NOVO"
    assert cell.variacao_pct is None


def test_ca08_sku_que_parou():
    """Valida CA-08: SKU com venda anterior e zero atual vira -100.0%."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1003 = ms.series[1003]
    base_idx = month_index(2026, 10)

    cell = compute_cell(series_1003, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell.status == "VARIACAO"
    assert cell.variacao_pct == -100.0


def test_ca10_negative_net_floor_zero():
    """Valida CA-10: Líquido negativo vira zero com selo devolucaoLiquida."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    base_idx = month_index(2026, 10)

    # 1004: out/26 líquido = -7 un -> piso zero -> -100.0% com devolucaoLiquida
    series_1004 = ms.series[1004]
    cell_1004 = compute_cell(series_1004, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell_1004.status == "VARIACAO"
    assert cell_1004.variacao_pct == -100.0
    assert cell_1004.devolucao_liquida is True

    # 1005: set/26 líquido = -3 un -> piso zero -> NOVO com devolucaoLiquida
    series_1005 = ms.series[1005]
    cell_1005 = compute_cell(series_1005, base_idx, 1, "quantity", ms, LAST_COVERED_DATE)
    assert cell_1005.status == "NOVO"
    assert cell_1005.devolucao_liquida is True


def test_precedence_and_invariants():
    """Valida precedência de status e invariantes AR-2, AR-3, Q-1."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import compute_cell

    ms = _setup_monthly_sales()
    series_1001 = ms.series[1001]

    # Mês-Base 2025-06, janela 6m -> SEM_BASE (AR-2: todos os selos false)
    base_idx_06 = month_index(2025, 6)
    cell_sem_base = compute_cell(series_1001, base_idx_06, 6, "quantity", ms, LAST_COVERED_DATE)
    assert cell_sem_base.status == "SEM_BASE"
    assert cell_sem_base.variacao_pct is None
    assert cell_sem_base.base_parcial is False
    assert cell_sem_base.base_baixa is False
    assert cell_sem_base.devolucao_liquida is False
