"""
Testes de Unidade do Domínio Puro de Elasticidade-Preço (TDD First)
Fase 2 (F5) - Regras P-095 a P-101.

Cenários cobertos:
1. Recuperação de elasticidade sintética (-2.0) dentro da tolerância (P-096).
2. Preço constante cai no padrão defensivo -1.2 com confiança BAIXA (P-096).
3. Rejeição de elasticidade positiva ou implausível com fallback para -1.2 (P-098).
4. Suavização hierárquica (shrinkage) monotônica por cliente (P-097).
5. Abatimento de devoluções no cálculo de volumes e preços médios (P-095).
6. Motor de simulação de variação de preço e impacto de receita/margem (P-101).
"""
import math
from datetime import date, timedelta
import numpy as np
import pandas as pd
import pytest

from src.modules.analytics.domain.elasticity import (
    DEFAULT_ELASTICITY,
    K_SHRINKAGE,
    calculate_decay_weights,
    estimate_customer_elasticity,
    estimate_product_elasticity,
    prepare_price_points,
    simulate_price_impact,
)
from src.modules.analytics.domain.exceptions import (
    CustomerWithoutHistoryError,
    InsufficientBaseError,
    InvalidParametersError,
)


def _generate_synthetic_sales_series(
    true_elasticity: float = -2.0,
    base_price: float = 20.0,
    base_qty: float = 100.0,
    n_points: int = 20,
    price_noise_std: float = 0.15,
) -> pd.DataFrame:
    """Gera série sintética onde Q = base_qty * (P / base_price) ** true_elasticity."""
    np.random.seed(42)
    rows = []
    ref_date = date(2026, 11, 1)

    for i in range(n_points):
        month_date = ref_date - timedelta(days=30 * (n_points - i))
        # Variação log-normal de preço
        price = base_price * math.exp(np.random.normal(0, price_noise_std))
        # Qtd esperada pela lei de demanda constante log-log
        expected_qty = base_qty * ((price / base_price) ** true_elasticity)
        qty = max(1.0, expected_qty * math.exp(np.random.normal(0, 0.05)))
        revenue = price * qty

        rows.append({
            "ano": month_date.year,
            "mes": month_date.month,
            "data": month_date,
            "preco_medio": price,
            "qtd_liquida": qty,
            "valor_liquido": revenue,
        })
    return pd.DataFrame(rows)


def test_estimate_product_elasticity_recovers_synthetic_value():
    """T-01: Recupera elasticidade sintética -2.0 dentro de tolerância aceitável."""
    df_series = _generate_synthetic_sales_series(true_elasticity=-2.0, n_points=22)
    result = estimate_product_elasticity(df_series)

    assert result.coefficient == pytest.approx(-2.0, abs=0.25)
    assert result.classification == "ELASTICO"
    assert result.r_squared >= 0.50
    assert result.confidence_level in ("ALTA", "MEDIA")
    assert result.is_reliable is True
    assert result.fallback_applied is False
    assert result.confidence_interval[0] < result.coefficient < result.confidence_interval[1]


def test_estimate_product_elasticity_constant_price_applies_fallback():
    """T-02: Preço constante não tem variação para regressão e aplica fallback canônico -1.2."""
    rows = []
    ref_date = date(2026, 11, 1)
    for i in range(12):
        month_date = ref_date - timedelta(days=30 * (12 - i))
        rows.append({
            "ano": month_date.year,
            "mes": month_date.month,
            "data": month_date,
            "preco_medio": 25.00,  # Preço idêntico em todos os meses
            "qtd_liquida": 100.0 + i * 5,
            "valor_liquido": 25.00 * (100.0 + i * 5),
        })
    df_constant = pd.DataFrame(rows)

    result = estimate_product_elasticity(df_constant)

    assert result.coefficient == DEFAULT_ELASTICITY  # -1.2
    assert result.fallback_applied is True
    assert result.confidence_level == "BAIXA"
    assert result.is_reliable is False


def test_estimate_product_elasticity_positive_value_is_rejected():
    """T-03: Relação positiva (P sobe e Q sobe) é rejeitada economicamente e substituída por -1.2."""
    rows = []
    ref_date = date(2026, 11, 1)
    for i in range(10):
        month_date = ref_date - timedelta(days=30 * (10 - i))
        p = 10.0 + i * 2.0  # Preço crescendo
        q = 50.0 + i * 15.0  # Quantidade crescendo junto (efeito espúrio/inflacionário)
        rows.append({
            "ano": month_date.year,
            "mes": month_date.month,
            "data": month_date,
            "preco_medio": p,
            "qtd_liquida": q,
            "valor_liquido": p * q,
        })
    df_positive = pd.DataFrame(rows)

    result = estimate_product_elasticity(df_positive)

    assert result.coefficient == DEFAULT_ELASTICITY
    assert result.fallback_applied is True
    assert result.confidence_level == "BAIXA"
    assert result.is_reliable is False


def test_estimate_product_elasticity_insufficient_points_fallback():
    """T-04: Menos de 5 observações mensais aplica fallback -1.2."""
    rows = [
        {"ano": 2026, "mes": 1, "data": date(2026, 1, 15), "preco_medio": 10.0, "qtd_liquida": 50.0, "valor_liquido": 500.0},
        {"ano": 2026, "mes": 2, "data": date(2026, 2, 15), "preco_medio": 12.0, "qtd_liquida": 40.0, "valor_liquido": 480.0},
        {"ano": 2026, "mes": 3, "data": date(2026, 3, 15), "preco_medio": 11.0, "qtd_liquida": 45.0, "valor_liquido": 495.0},
    ]
    df_short = pd.DataFrame(rows)

    result = estimate_product_elasticity(df_short)

    assert result.coefficient == DEFAULT_ELASTICITY
    assert result.fallback_applied is True
    assert result.is_reliable is False
    assert result.observations_count == 3


def test_estimate_customer_elasticity_shrinkage_monotonicity():
    """T-05: Shrinkage bayesiano aproxima do produto com poucos dados e do cliente com muitos dados."""
    product_elasticity = -1.50
    customer_empirical = -2.50

    # Cenário A: Cliente com apenas 1 pedido (n=1)
    # w = 1 / (1 + 10) = 1/11 ≈ 0.0909
    # beta ≈ 0.0909 * (-2.50) + 0.9091 * (-1.50) ≈ -1.59
    res_n1 = estimate_customer_elasticity(
        product_elasticity=product_elasticity,
        customer_empirical=customer_empirical,
        orders_count=1,
        k_shrinkage=K_SHRINKAGE,
    )
    assert math.isclose(res_n1.shrinkage_weight, 1.0 / 11.0, rel_tol=1e-3)
    assert abs(res_n1.shrinkage_elasticity - product_elasticity) < abs(res_n1.shrinkage_elasticity - customer_empirical)

    # Cenário B: Cliente com 10 pedidos (n=10)
    # w = 10 / (10 + 10) = 0.50
    # beta = 0.5 * (-2.50) + 0.5 * (-1.50) = -2.00
    res_n10 = estimate_customer_elasticity(
        product_elasticity=product_elasticity,
        customer_empirical=customer_empirical,
        orders_count=10,
        k_shrinkage=K_SHRINKAGE,
    )
    assert math.isclose(res_n10.shrinkage_weight, 0.50, rel_tol=1e-3)
    assert res_n10.shrinkage_elasticity == pytest.approx(-2.00, abs=1e-3)

    # Cenário C: Cliente frequente com 40 pedidos (n=40)
    # w = 40 / (40 + 10) = 0.80
    res_n40 = estimate_customer_elasticity(
        product_elasticity=product_elasticity,
        customer_empirical=customer_empirical,
        orders_count=40,
        k_shrinkage=K_SHRINKAGE,
    )
    assert math.isclose(res_n40.shrinkage_weight, 0.80, rel_tol=1e-3)
    assert abs(res_n40.shrinkage_elasticity - customer_empirical) < abs(res_n40.shrinkage_elasticity - product_elasticity)

    # Monotonicidade estrita: |res_n40 - customer_empirical| < |res_n10 - customer_empirical| < |res_n1 - customer_empirical|
    dist_1 = abs(res_n1.shrinkage_elasticity - customer_empirical)
    dist_10 = abs(res_n10.shrinkage_elasticity - customer_empirical)
    dist_40 = abs(res_n40.shrinkage_elasticity - customer_empirical)
    assert dist_40 < dist_10 < dist_1


def test_prepare_price_points_deducts_returns():
    """T-06: Prepara série agregando vendas e abatendo devoluções corretamente."""
    # Vendas e devoluções no mesmo mês
    raw_records = [
        {"ano": 2026, "mes": 1, "operacao": "VENDA", "qtd": 100.0, "valor": 2000.0},
        {"ano": 2026, "mes": 1, "operacao": "DEVOLUÇÃO DE VENDA", "qtd": -20.0, "valor": -400.0},
        # Mês 2: Devolução total (líquido zero) -> deve ser descartado
        {"ano": 2026, "mes": 2, "operacao": "VENDA", "qtd": 50.0, "valor": 1000.0},
        {"ano": 2026, "mes": 2, "operacao": "DEVOLUÇÃO", "qtd": -50.0, "valor": -1000.0},
        # Mês 3: Venda normal
        {"ano": 2026, "mes": 3, "operacao": "VENDA", "qtd": 80.0, "valor": 1760.0},
    ]
    df_raw = pd.DataFrame(raw_records)
    df_prepared = prepare_price_points(df_raw)

    # Mês 1 deve ter qtd_liquida = 80 e valor_liquido = 1600 -> preco_medio = 20.0
    row_m1 = df_prepared[df_prepared["mes"] == 1].iloc[0]
    assert row_m1["qtd_liquida"] == 80.0
    assert row_m1["valor_liquido"] == 1600.0
    assert row_m1["preco_medio"] == 20.0

    # Mês 2 foi descartado porque qtd_liquida <= 0
    assert 2 not in df_prepared["mes"].values

    # Mês 3 permanece
    assert 3 in df_prepared["mes"].values


def test_simulate_price_impact_elastic_and_inelastic():
    """T-07: Simulação calcula variações de volume, receita e margem monetária."""
    # Cenário A: Produto Inelástico (-0.50), reajuste de +10%
    # Q_atual = 100, P_atual = R$ 50, Custo = R$ 30
    # Receita atual = R$ 5000, Margem atual = (50 - 30) * 100 = R$ 2000
    # delta_volume_pct = -0.50 * 10% = -5% -> Q_novo = 95
    # P_novo = R$ 55 -> Receita nova = 55 * 95 = R$ 5225 (+225)
    # Margem nova = (55 - 30) * 95 = 25 * 95 = R$ 2375 (+375)
    sim_inelastic = simulate_price_impact(
        elasticity=-0.50,
        current_price=50.0,
        cost_price=30.0,
        current_volume=100.0,
        price_change_pct=10.0,
    )
    assert sim_inelastic.volume_change_pct == -5.0
    assert sim_inelastic.projected_volume == pytest.approx(95.0)
    assert sim_inelastic.projected_price == 55.0
    assert sim_inelastic.current_revenue == 5000.0
    assert sim_inelastic.projected_revenue == pytest.approx(5225.0)
    assert sim_inelastic.revenue_change_abs == pytest.approx(225.0)
    assert sim_inelastic.current_margin == 2000.0
    assert sim_inelastic.projected_margin == pytest.approx(2375.0)
    assert sim_inelastic.margin_change_abs == pytest.approx(375.0)

    # Cenário B: Produto Muito Elástico (-2.50), reajuste de +10%
    # delta_volume_pct = -2.50 * 10% = -25% -> Q_novo = 75
    # P_novo = R$ 55 -> Receita nova = 55 * 75 = R$ 4125 (-875)
    # Margem nova = (55 - 30) * 75 = 25 * 75 = R$ 1875 (-125)
    sim_elastic = simulate_price_impact(
        elasticity=-2.50,
        current_price=50.0,
        cost_price=30.0,
        current_volume=100.0,
        price_change_pct=10.0,
    )
    assert sim_elastic.volume_change_pct == -25.0
    assert sim_elastic.projected_revenue == pytest.approx(4125.0)
    assert sim_elastic.revenue_change_abs == pytest.approx(-875.0)
    assert sim_elastic.projected_margin == pytest.approx(1875.0)
    assert sim_elastic.margin_change_abs == pytest.approx(-125.0)
