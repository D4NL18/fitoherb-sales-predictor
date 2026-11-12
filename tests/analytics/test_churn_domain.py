"""
Testes de unidade do motor de domínio de Churn de Clientes (P-117 a P-127).
FASE F3 — TDD First.
"""
from __future__ import annotations

from datetime import date, timedelta
import pytest

from src.modules.analytics.domain.churn import (
    CHURN_BASE_DAYS,
    DIAS_INATIVO_ANTIGO,
    FATOR_TEMPO_MAX,
    GAP_MULTIPLIER,
    MIN_ORDERS_FOR_CADENCE,
    ChurnCustomerSummary,
    CustomerOrderHistory,
    MonthlyRevenuePoint,
    calculate_churn_metrics,
    calculate_typical_gap,
    classify_churn_status,
    evaluate_lost_products,
    rank_churn_customers,
    run_churn_backtest,
)


def test_typical_gap_calculation_with_three_or_more_orders():
    """P-119: Calcula a mediana dos intervalos entre pedidos para >= 3 compras."""
    orders = [
        date(2026, 1, 10),
        date(2026, 1, 20),  # diff: 10
        date(2026, 2, 5),   # diff: 16
        date(2026, 2, 25),  # diff: 20
    ]
    # Intervalos: [10, 16, 20] -> mediana = 16.0
    gap = calculate_typical_gap(orders)
    assert gap == 16.0


def test_typical_gap_returns_none_for_few_orders():
    """P-119.3, P-122: Menos de 3 pedidos não geram gap típico."""
    assert calculate_typical_gap([date(2026, 1, 1)]) is None
    assert calculate_typical_gap([date(2026, 1, 1), date(2026, 1, 20)]) is None


def test_quarterly_buyer_not_marked_at_60_days():
    """
    P-119.4: Cliente trimestral (gap típico 60d) tem diasReferencia = 90d.
    Aos 70 dias parado, fatorTempo = 70/90 = 0.78 -> status ALERTA, não EM_RISCO.
    """
    reference_date = date(2026, 5, 10)
    # Pedidos a cada 60 dias: 2025-11-01, 2025-12-31, 2026-03-01 (último há 70 dias de 10/05/2026)
    order_dates = [date(2025, 11, 1), date(2025, 12, 31), date(2026, 3, 1)]
    revenue_history = [
        MonthlyRevenuePoint(year=2025, month=11, net_revenue=30000.0, order_count=1),
        MonthlyRevenuePoint(year=2025, month=12, net_revenue=30000.0, order_count=1),
        MonthlyRevenuePoint(year=2026, month=3, net_revenue=30000.0, order_count=1),
    ]
    summary = calculate_churn_metrics(
        customer_code=1001,
        order_dates=order_dates,
        revenue_history=revenue_history,
        reference_date=reference_date,
    )

    assert summary.dias_sem_comprar == 70
    assert summary.gap_tipico == 60.0
    assert summary.dias_referencia == 90  # max(60, 1.5 * 60)
    assert round(summary.fator_tempo, 2) == 0.78
    assert summary.status == "ALERTA"  # Proteção contra falso positivo!


def test_fator_tempo_caps_at_two():
    """P-120.2: fatorTempo satura estritamente no teto de 2.0."""
    reference_date = date(2026, 6, 1)
    # Último pedido há 150 dias, régua de 60d: 150/60 = 2.5 -> satura em 2.0
    order_dates = [date(2026, 1, 2)]
    revenue_history = [MonthlyRevenuePoint(year=2026, month=1, net_revenue=5000.0, order_count=1)]

    summary = calculate_churn_metrics(
        customer_code=2002,
        order_dates=order_dates,
        revenue_history=revenue_history,
        reference_date=reference_date,
    )
    assert summary.dias_sem_comprar == 150
    assert summary.dias_referencia == 60
    assert summary.fator_tempo == FATOR_TEMPO_MAX  # 2.0


def test_short_history_flag_and_damping_divisor():
    """
    P-122: Cliente com 1 pedido tem historicoCurto = True.
    Divisor de faturamento médio mensal é amortecido pelo mínimo de 3 meses.
    """
    reference_date = date(2026, 4, 1)
    # Compra única de R$ 30.000 em 2026-02-15
    order_dates = [date(2026, 2, 15)]
    revenue_history = [MonthlyRevenuePoint(year=2026, month=2, net_revenue=30000.0, order_count=1)]

    summary = calculate_churn_metrics(
        customer_code=3003,
        order_dates=order_dates,
        revenue_history=revenue_history,
        reference_date=reference_date,
    )
    assert summary.historico_curto is True
    assert summary.gap_tipico is None
    # 30.000 amortecido por 3 meses = 10.000/mês (e não 30.000)
    assert summary.faturamento_medio_mensal == 10000.0


def test_high_revenue_customer_70d_beats_low_revenue_customer_120d():
    """
    P-123.3: Prevalência de valor monetário:
    Cliente grande (50k/mês) parado 70d tem score superior a cliente pequeno (2k/mês) parado 120d.
    """
    ref = date(2026, 5, 1)
    # Cliente A: faturamento 50.000/mês, último pedido 70d atrás (ref=60d -> fator=70/60=1.1667)
    # Score A = 50.000 * 1.1667 = 58.333
    cust_a = calculate_churn_metrics(
        customer_code=1,
        order_dates=[ref - timedelta(days=70)],
        revenue_history=[
            MonthlyRevenuePoint(year=2026, month=1, net_revenue=50000.0, order_count=1),
            MonthlyRevenuePoint(year=2026, month=2, net_revenue=50000.0, order_count=1),
            MonthlyRevenuePoint(year=2026, month=3, net_revenue=50000.0, order_count=1),
        ],
        reference_date=ref,
    )

    # Cliente B: faturamento 2.000/mês, último pedido 120d atrás (ref=60d -> fator=2.0)
    # Score B = 2.000 * 2.0 = 4.000
    cust_b = calculate_churn_metrics(
        customer_code=2,
        order_dates=[ref - timedelta(days=120)],
        revenue_history=[
            MonthlyRevenuePoint(year=2025, month=11, net_revenue=2000.0, order_count=1),
            MonthlyRevenuePoint(year=2025, month=12, net_revenue=2000.0, order_count=1),
            MonthlyRevenuePoint(year=2026, month=1, net_revenue=2000.0, order_count=1),
        ],
        reference_date=ref,
    )

    assert cust_a.score_prioridade > cust_b.score_prioridade
    ranked = rank_churn_customers([cust_b, cust_a])
    assert ranked[0].customer_code == cust_a.customer_code


def test_inactive_customers_segregation_above_180d():
    """P-125: Clientes parados > 180 dias são classificados como INATIVO_RECUPERACAO."""
    ref = date(2026, 7, 1)
    summary = calculate_churn_metrics(
        customer_code=4004,
        order_dates=[ref - timedelta(days=190)],
        revenue_history=[MonthlyRevenuePoint(year=2025, month=12, net_revenue=15000.0, order_count=1)],
        reference_date=ref,
    )
    assert summary.dias_sem_comprar == 190
    assert summary.status == "INATIVO_RECUPERACAO"


def test_returns_abate_revenue_and_do_not_create_orders():
    """
    P-117.1, P-121: Devoluções abatem faturamento líquido.
    Se um mês teve VENDA de 10.000 e DEVOLUÇÃO de -2.000, o líquido do mês é 8.000.
    """
    net_point = MonthlyRevenuePoint(year=2026, month=3, net_revenue=8000.0, order_count=2)
    assert net_point.net_revenue == 8000.0


def test_lost_products_identification():
    """P-126.3: Identifica top produtos perdidos (comprados no passado, mas ausentes nos últimos 60d)."""
    ref = date(2026, 6, 1)
    past_purchases = [
        {"sku": 101, "descricao": "PROPOLIS", "fornecedor": "FORN A", "revenue": 15000.0, "last_date": date(2026, 2, 10)},
        {"sku": 102, "descricao": "MEL", "fornecedor": "FORN A", "revenue": 8000.0, "last_date": date(2026, 3, 1)},
        {"sku": 103, "descricao": "SPRAY", "fornecedor": "FORN B", "revenue": 5000.0, "last_date": date(2026, 5, 20)}, # Comprou recente (12 dias)
    ]
    lost = evaluate_lost_products(past_purchases, reference_date=ref, cutoff_days=60, limit=5)
    assert len(lost) == 2
    assert lost[0]["sku"] == 101  # Maior faturamento histórico
    assert lost[1]["sku"] == 102


def test_quantitative_acceptance_backtest():
    """
    P-127: Critério de aceite quantitativo:
    O ranking por score de prioridade DEVE capturar receita em risco nos top N maior ou igual à ordenação simples por dias.
    """
    ref = date(2026, 6, 1)
    customers = [
        # Grande parado 70 dias
        calculate_churn_metrics(
            customer_code=1,
            order_dates=[ref - timedelta(days=70)],
            revenue_history=[MonthlyRevenuePoint(year=2026, month=1, net_revenue=50000.0, order_count=1)],
            reference_date=ref,
        ),
        # Pequeno parado 150 dias
        calculate_churn_metrics(
            customer_code=2,
            order_dates=[ref - timedelta(days=150)],
            revenue_history=[MonthlyRevenuePoint(year=2026, month=1, net_revenue=1000.0, order_count=1)],
            reference_date=ref,
        ),
        # Médio parado 80 dias
        calculate_churn_metrics(
            customer_code=3,
            order_dates=[ref - timedelta(days=80)],
            revenue_history=[MonthlyRevenuePoint(year=2026, month=1, net_revenue=20000.0, order_count=1)],
            reference_date=ref,
        ),
    ]

    backtest_result = run_churn_backtest(customers, top_n=2)
    assert backtest_result.revenue_score_priority > backtest_result.revenue_simple_days
    assert backtest_result.is_superior is True
