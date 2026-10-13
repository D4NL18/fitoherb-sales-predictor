"""
Testes unitários para Mineração de Cestas e Eleição de Âncoras (US-02, US-03, P-005, P-006).
"""
import pandas as pd
import pytest

from src.basket_mining import (
    calculate_anchor_natural_shares,
    calculate_anchor_score,
    compute_optimized_anchor_locks,
    filter_orphan_baskets,
    build_basket_matrix,
    mine_association_rules,
    select_anchors_and_compensators,
)


@pytest.fixture
def transactions_df():
    # 5 pedidos:
    # Pedido 1: [A, B, C]
    # Pedido 2: [A, B]
    # Pedido 3: [A, C]
    # Pedido 4: [A] -> Cesta órfã! (apenas 1 SKU)
    # Pedido 5: [B, C]
    data = [
        {"Pedido": 1, "Cod Produto": 101, "Qtd Venda": 10.0, "Valor Venda": 100.0, "Data": "2026-01-01"},
        {"Pedido": 1, "Cod Produto": 102, "Qtd Venda": 5.0,  "Valor Venda": 50.0,  "Data": "2026-01-01"},
        {"Pedido": 1, "Cod Produto": 103, "Qtd Venda": 2.0,  "Valor Venda": 20.0,  "Data": "2026-01-01"},
        
        {"Pedido": 2, "Cod Produto": 101, "Qtd Venda": 8.0,  "Valor Venda": 80.0,  "Data": "2026-01-02"},
        {"Pedido": 2, "Cod Produto": 102, "Qtd Venda": 4.0,  "Valor Venda": 40.0,  "Data": "2026-01-02"},
        
        {"Pedido": 3, "Cod Produto": 101, "Qtd Venda": 12.0, "Valor Venda": 120.0, "Data": "2026-01-03"},
        {"Pedido": 3, "Cod Produto": 103, "Qtd Venda": 3.0,  "Valor Venda": 30.0,  "Data": "2026-01-03"},
        
        {"Pedido": 4, "Cod Produto": 101, "Qtd Venda": 5.0,  "Valor Venda": 50.0,  "Data": "2026-01-04"},
        
        {"Pedido": 5, "Cod Produto": 102, "Qtd Venda": 6.0,  "Valor Venda": 60.0,  "Data": "2026-01-05"},
        {"Pedido": 5, "Cod Produto": 103, "Qtd Venda": 4.0,  "Valor Venda": 40.0,  "Data": "2026-01-05"},
    ]
    return pd.DataFrame(data)


def test_orphan_baskets_filter(transactions_df):
    """Testa regra P-005: Pedidos com menos de 2 SKUs válidos são descartados da mineração."""
    filtered_df = filter_orphan_baskets(transactions_df)
    # Pedido 4 deve ser removido
    assert 4 not in filtered_df["Pedido"].values
    assert set(filtered_df["Pedido"].unique()) == {1, 2, 3, 5}


def test_basket_matrix_and_rules(transactions_df):
    """Testa construção da matriz binária e mineração FP-Growth com métricas de associação."""
    filtered_df = filter_orphan_baskets(transactions_df)
    matrix = build_basket_matrix(filtered_df)
    
    assert matrix.shape[0] == 4  # 4 pedidos válidos
    assert matrix.shape[1] == 3  # SKUs 101, 102, 103
    
    rules = mine_association_rules(matrix, min_support=0.2, min_confidence=0.3)
    assert not rules.empty
    assert "antecedents" in rules.columns
    assert "consequents" in rules.columns
    assert "support" in rules.columns
    assert "confidence" in rules.columns
    assert "lift" in rules.columns


def test_anchor_scoring_and_election(transactions_df):
    """Testa regra P-006: Eleição de Âncoras pelo Score Composto Ponderado."""
    filtered_df = filter_orphan_baskets(transactions_df)
    matrix = build_basket_matrix(filtered_df)
    rules = mine_association_rules(matrix, min_support=0.2, min_confidence=0.3)
    
    scores = calculate_anchor_score(filtered_df, rules)
    assert not scores.empty
    assert "score_composto" in scores.columns
    
    # SKU 101 tem o maior volume de vendas e penetração nos pedidos
    top_sku = scores.sort_values(by="score_composto", ascending=False).iloc[0]["Cod Produto"]
    assert top_sku == 101
    
    anchors, compensators = select_anchors_and_compensators(scores, rules, top_n_anchors=1)
    assert 101 in anchors
    assert len(compensators[101]) > 0


def test_calculate_anchor_natural_shares(transactions_df):
    """Testa regra P-017: Cálculo do share natural empírico por SKU nos pedidos."""
    shares = calculate_anchor_natural_shares(transactions_df, quantile=0.75, min_share=0.08, max_share=0.45)
    assert isinstance(shares, dict)
    assert 101 in shares
    assert 102 in shares
    assert 103 in shares
    # Todos os valores devem estar nos limites [min_share, max_share]
    for sku, share in shares.items():
        assert 0.08 <= share <= 0.45


def test_compute_optimized_anchor_locks():
    """Testa regra P-017: Otimização de travas por âncora sob modo dinâmico e uniforme."""
    natural_shares = {101: 0.12, 102: 0.35, 103: 0.22}
    anchors = [101, 102, 103]

    # Modo variável (True): escala as travas individuais
    var_locks = compute_optimized_anchor_locks(anchors, natural_shares, base_k_ratio=0.25, variable_mode=True)
    assert var_locks[101] == 0.12
    assert var_locks[102] == 0.35
    assert var_locks[103] == 0.22

    # Modo uniforme (False): todos recebem a trava base fixa
    fixed_locks = compute_optimized_anchor_locks(anchors, natural_shares, base_k_ratio=0.25, variable_mode=False)
    assert fixed_locks[101] == 0.25
    assert fixed_locks[102] == 0.25
    assert fixed_locks[103] == 0.25
