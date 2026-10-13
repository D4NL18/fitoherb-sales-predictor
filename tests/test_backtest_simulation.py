"""
Testes unitários para Backtesting Histórico 2026 e Stress Testing (US-06, P-010).
"""
import pandas as pd
import pytest

from src.backtest_simulation import (
    simulate_2026_replay,
    stress_test_volume_drop,
    generate_consolidated_recommendation,
)


@pytest.fixture
def replay_orders_df():
    # 3 pedidos de 2026:
    # Pedido 1: Âncora 101 (1 un * 90 = 90), Comp 102 (4 un * 52 = 208). Total = 298. Âncora = 90/298 = 30.2% -> Trava 25% violada.
    # Pedido 2: Âncora 101 (1 un * 90 = 90), Comp 102 (8 un * 52 = 416). Total = 506. Âncora = 90/506 = 17.8% -> Trava 25% atendida!
    # Pedido 3: Âncora 101 (1 un * 90 = 90), Comp 103 (6 un * 42 = 252). Total = 342. Âncora = 90/342 = 26.3% -> Trava violada.
    data = [
        {"Pedido": 1, "Cod Produto": 101, "Qtd Venda": 1.0, "Data": "2026-02-01"},
        {"Pedido": 1, "Cod Produto": 102, "Qtd Venda": 4.0, "Data": "2026-02-01"},
        
        {"Pedido": 2, "Cod Produto": 101, "Qtd Venda": 1.0, "Data": "2026-02-02"},
        {"Pedido": 2, "Cod Produto": 102, "Qtd Venda": 8.0, "Data": "2026-02-02"},
        
        {"Pedido": 3, "Cod Produto": 101, "Qtd Venda": 1.0, "Data": "2026-02-03"},
        {"Pedido": 3, "Cod Produto": 103, "Qtd Venda": 6.0, "Data": "2026-02-03"},
    ]
    return pd.DataFrame(data)


def test_simulate_2026_replay(replay_orders_df):
    """Testa replay de pedidos de 2026 e cálculo da taxa de elegibilidade da trava K%."""
    new_prices = {101: 90.0, 102: 52.0, 103: 42.0}
    anchor_skus = {101}
    
    replay_metrics = simulate_2026_replay(
        orders_df=replay_orders_df,
        new_prices=new_prices,
        anchor_skus=anchor_skus,
        k_ratio=0.25,
    )
    
    assert "total_pedidos_com_ancora" in replay_metrics
    assert replay_metrics["total_pedidos_com_ancora"] == 3
    # Apenas o pedido 2 atendeu à trava <= 25%
    assert replay_metrics["pedidos_elegiveis_trava"] == 1
    assert np_isclose(replay_metrics["pct_elegibilidade"], 1 / 3 * 100, atol=0.1)


def test_stress_test_volume_drop():
    """Testa teste de estresse de queda de volume de 3% a 5% nos compensadores."""
    base_margin = 10000.0
    # Lucro projetado com novos preços
    simulated_delta_anchor = -1500.0
    simulated_delta_comp = +2000.0   # Ganho de 500
    
    stress_result = stress_test_volume_drop(
        delta_margin_anchor=simulated_delta_anchor,
        delta_margin_comp=simulated_delta_comp,
        comp_volume_drop_pct=0.05,  # Queda de 5%
    )
    
    assert "lucro_liquido_estresse" in stress_result
    assert "margem_protegida" in stress_result


def test_generate_consolidated_recommendation():
    """Testa geração da tabela de precificação consolidada e script SQL."""
    catalog_df = pd.DataFrame([
        {"Código": 101, "Descrição": "PRODUTO A", "Fornec/Marca": "MARCA A", "Preço": 100.0},
        {"Código": 102, "Descrição": "PRODUTO B", "Fornec/Marca": "MARCA B", "Preço": 50.0},
        {"Código": 103, "Descrição": "PRODUTO C", "Fornec/Marca": "MARCA C", "Preço": 40.0},
    ])
    
    pricing_results = {
        101: {"papel": "PRODUTO ÂNCORA", "novo_preco": 90.0, "impacto_margem": 500.0, "regra": "Trava K=25%"},
        102: {"papel": "COMPENSADOR", "novo_preco": 51.5, "impacto_margem": 300.0, "regra": "Compensador"},
        103: {"papel": "COMPENSADOR", "novo_preco": 41.2, "impacto_margem": 250.0, "regra": "Compensador"},
    }
    
    df_rec, sql_content = generate_consolidated_recommendation(catalog_df, pricing_results)
    
    assert len(df_rec) == 3
    assert "Codigo" in df_rec.columns
    assert "Novo_Preco_Sugerido" in df_rec.columns
    assert "Variacao_Reais" in df_rec.columns
    assert "Variacao_Percentual" in df_rec.columns
    assert "Trava_K_Percentual" in df_rec.columns
    assert "UPDATE" in sql_content


def test_simulate_2026_replay_with_variable_k_dict(replay_orders_df):
    """Testa regra P-017: Validação de pedidos com trava comercial variável individual."""
    new_prices = {101: 90.0, 102: 52.0, 103: 42.0}
    anchor_skus = {101}
    
    # Com trava uniforme de 25%, apenas o Pedido 2 atende (1 de 3)
    uniform_metrics = simulate_2026_replay(
        orders_df=replay_orders_df,
        new_prices=new_prices,
        anchor_skus=anchor_skus,
        k_ratio=0.25,
    )
    assert uniform_metrics["pedidos_elegiveis_trava"] == 1

    # Com trava individual otimizada de 35% para SKU 101, Pedido 1 (30.2%) e Pedido 3 (26.3%) também são elegíveis!
    variable_metrics = simulate_2026_replay(
        orders_df=replay_orders_df,
        new_prices=new_prices,
        anchor_skus=anchor_skus,
        k_ratio={101: 0.35},
    )
    assert variable_metrics["pedidos_elegiveis_trava"] == 3
    assert variable_metrics["pct_elegibilidade"] == 100.0


def np_isclose(a, b, atol=1e-3):
    return abs(a - b) <= atol
