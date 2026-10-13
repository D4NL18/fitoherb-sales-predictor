"""
Testes unitários para Modelagem de Elasticidade-Preço e Decaimento Temporal (US-04, P-007).
"""
import numpy as np
import pandas as pd
import pytest

from src.elasticity_model import (
    calculate_temporal_decay_weights,
    estimate_log_log_elasticity,
    build_elasticity_matrix,
)


def test_temporal_decay_weights():
    """Testa regra P-007: sample_weight = 2 ** (-dias_ate_presente / meia_vida)."""
    reference_date = pd.Timestamp("2026-09-28")
    dates = pd.Series([
        reference_date,                                      # dias = 0 -> peso = 1.0
        reference_date - pd.Timedelta(days=100),             # dias = 100 (meia-vida) -> peso = 0.5
        reference_date - pd.Timedelta(days=200),             # dias = 200 -> peso = 0.25
    ])
    
    weights = calculate_temporal_decay_weights(dates, half_life_days=100.0, reference_date=reference_date)
    
    assert np.isclose(weights[0], 1.0, atol=1e-3)
    assert np.isclose(weights[1], 0.5, atol=1e-3)
    assert np.isclose(weights[2], 0.25, atol=1e-3)


def test_log_log_elasticity_estimation():
    """Testa estimação econométrica Log-Log: ln(Q) = a + b * ln(P)."""
    # Gerar dados sintéticos com elasticidade real = -1.5
    np.random.seed(42)
    prices = np.linspace(20.0, 50.0, 50)
    # Q = exp(8) * P^(-1.5)
    log_q = 8.0 - 1.5 * np.log(prices) + np.random.normal(0, 0.05, 50)
    quantities = np.exp(log_q)
    
    df_product = pd.DataFrame({
        "preco_praticado": prices,
        "Qtd Venda": quantities,
        "sample_weight": np.ones(50)
    })
    
    own_elasticity = estimate_log_log_elasticity(df_product)
    assert own_elasticity < 0  # Elasticidade própria negativa
    assert np.isclose(own_elasticity, -1.5, atol=0.2)


def test_elasticity_matrix_generation():
    """Testa montagem da matriz de elasticidades para um conjunto de SKUs."""
    skus = [101, 102, 103]
    df_sales = pd.DataFrame({
        "Cod Produto": [101]*30 + [102]*30 + [103]*30,
        "Valor Venda": [100.0]*90,
        "Qtd Venda": [5.0]*90,
        "Data": [pd.Timestamp("2026-05-01")]*90,
    })
    catalog_prices = {101: 50.0, 102: 70.0, 103: 40.0}
    
    elast_matrix = build_elasticity_matrix(skus, df_sales, catalog_prices)
    for sku in skus:
        assert (sku, sku) in elast_matrix
        assert elast_matrix[(sku, sku)] < 0  # própria negativa
