"""
Testes unitários para o Motor de Otimização Prescritiva de Preços (US-05, P-008, P-009).
"""
import pytest

from src.price_optimizer import (
    OptimizationConfig,
    optimize_basket_pricing,
)


@pytest.fixture
def sample_pricing_problem():
    anchor_sku = 101
    compensators = [102, 103]
    
    # Preços de tabela atuais
    base_prices = {
        101: 100.0,
        102: 50.0,
        103: 40.0,
    }
    
    # Custos unitários (margem base = 40%)
    costs = {
        101: 60.0,
        102: 30.0,
        103: 24.0,
    }
    
    # Volumes médios de venda na cesta
    volumes = {
        101: 10.0,
        102: 15.0,
        103: 20.0,
    }
    
    # Elasticidades próprias
    own_elasticities = {
        101: -1.2,
        102: -0.8,
        103: -0.6,
    }
    
    return anchor_sku, compensators, base_prices, costs, volumes, own_elasticities


def test_price_optimizer_constraints(sample_pricing_problem):
    """Testa regras P-008 e P-009: Desconto âncora, reajuste compensador, piso de custo e trava de margem."""
    anchor_sku, compensators, base_prices, costs, volumes, own_elasticities = sample_pricing_problem
    
    config = OptimizationConfig(
        anchor_min_discount=-0.15,
        anchor_max_discount=-0.05,
        comp_min_increase=0.01,
        comp_max_increase=0.06,
        margin_floor_pct=0.05,
        k_basket_ratio=0.25,
    )
    
    result = optimize_basket_pricing(
        anchor_sku=anchor_sku,
        compensators=compensators,
        base_prices=base_prices,
        costs=costs,
        volumes=volumes,
        own_elasticities=own_elasticities,
        config=config,
    )
    
    assert result.success, f"Otimização falhou: {result.message}"
    
    new_prices = result.new_prices
    deltas_pct = result.deltas_pct
    
    # 1. Faixa de desconto no âncora: -15% a -5%
    x_ancora = deltas_pct[anchor_sku]
    assert -0.1501 <= x_ancora <= -0.0499, f"Desconto âncora fora da faixa: {x_ancora}"
    
    # 2. Piso de margem no âncora: P_novo >= Custo * 1.05
    assert new_prices[anchor_sku] >= costs[anchor_sku] * 1.05
    
    # 3. Faixa de reajuste nos compensadores: +1% a +6%
    for comp in compensators:
        x_comp = deltas_pct[comp]
        assert 0.0099 <= x_comp <= 0.0601, f"Reajuste compensador fora da faixa: {x_comp}"
    
    # 4. Neutralidade ou ganho de margem global: delta_margem_total >= 0
    assert result.delta_total_margin >= -1e-5, f"Perda de margem total: {result.delta_total_margin}"
