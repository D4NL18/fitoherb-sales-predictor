"""
Testes unitários para o Meta-Otimizador com Algoritmo Genético (US-09, P-014 a P-016).
"""
import numpy as np
import pytest

from src.api import get_cached_etl_data
from src.meta_tuner import (
    GENE_BOUNDS,
    crossover_arithmetic,
    decode_chromosome,
    evaluate_fitness,
    mutate_gaussian,
    run_genetic_algorithm,
    tournament_selection,
)


from src.config import DEFAULT_CONFIG
from src.basket_mining import (
    build_basket_matrix,
    calculate_anchor_score,
    filter_orphan_baskets,
    mine_association_rules,
)


@pytest.fixture(scope="module")
def prepared_data():
    """Carrega dados limpos e regras pré-computadas para testes ultrarrápidos."""
    catalog_df, clean_sales = get_cached_etl_data()
    dense_sales = filter_orphan_baskets(clean_sales, min_skus=DEFAULT_CONFIG.min_basket_size)
    basket_mat = build_basket_matrix(dense_sales)
    rules_df = mine_association_rules(
        basket_mat,
        min_support=DEFAULT_CONFIG.min_support,
        min_confidence=DEFAULT_CONFIG.min_confidence,
        min_lift=DEFAULT_CONFIG.min_lift
    )
    anchor_scores = calculate_anchor_score(
        clean_sales,
        rules_df,
        weights=(DEFAULT_CONFIG.weight_giro, DEFAULT_CONFIG.weight_penetracao, DEFAULT_CONFIG.weight_lift)
    )
    return catalog_df, clean_sales, rules_df, anchor_scores


def test_decode_chromosome():
    """Testa se o decodificador converte o cromossomo para tipos e nomes corretos."""
    chrom = np.array([0.25, 15.0, 100.0, -0.10, 0.05, 0.05])
    decoded = decode_chromosome(chrom)

    assert isinstance(decoded["top_anchors"], int)
    assert decoded["top_anchors"] == 15
    assert decoded["k_ratio"] == 0.25
    assert decoded["half_life_days"] == 100.0
    assert decoded["anchor_discount"] == -0.10
    assert decoded["comp_max_increase"] == 0.05
    assert decoded["stress_drop"] == 0.05


def test_chromosome_bounds_clipping():
    """Testa se mutação respeita os limites de viabilidade comercial (P-014)."""
    chrom = np.array([0.50, 50.0, 1000.0, 0.10, 0.50, 0.90])
    mutated = mutate_gaussian(chrom, mutation_rate=1.0, scale=0.5)

    assert GENE_BOUNDS["k_ratio"][0] <= mutated[0] <= GENE_BOUNDS["k_ratio"][1]
    assert GENE_BOUNDS["top_anchors"][0] <= mutated[1] <= GENE_BOUNDS["top_anchors"][1]
    assert GENE_BOUNDS["half_life_days"][0] <= mutated[2] <= GENE_BOUNDS["half_life_days"][1]
    assert GENE_BOUNDS["anchor_discount"][0] <= mutated[3] <= GENE_BOUNDS["anchor_discount"][1]
    assert GENE_BOUNDS["comp_max_increase"][0] <= mutated[4] <= GENE_BOUNDS["comp_max_increase"][1]
    assert GENE_BOUNDS["stress_drop"][0] <= mutated[5] <= GENE_BOUNDS["stress_drop"][1]


def test_crossover_arithmetic():
    """Testa se o crossover gera filhos válidos entre dois pais viáveis."""
    parent1 = np.array([0.20, 10.0, 60.0, -0.12, 0.04, 0.04])
    parent2 = np.array([0.30, 20.0, 120.0, -0.08, 0.06, 0.06])

    child1, child2 = crossover_arithmetic(parent1, parent2, crossover_rate=1.0)
    for gene_idx in range(len(parent1)):
        min_val = min(parent1[gene_idx], parent2[gene_idx])
        max_val = max(parent1[gene_idx], parent2[gene_idx])
        assert min_val <= child1[gene_idx] <= max_val
        assert min_val <= child2[gene_idx] <= max_val


def test_fitness_evaluation_strategies(prepared_data):
    """Testa o cálculo de fitness para as 3 estratégias comerciais (P-015)."""
    catalog_df, clean_sales, rules_df, anchor_scores = prepared_data
    chrom = np.array([0.25, 5.0, 90.0, -0.10, 0.05, 0.05])

    fitness_balanced, sim_b = evaluate_fitness(
        chrom, catalog_df, clean_sales, strategy="balanced",
        precomputed_rules=rules_df, precomputed_scores=anchor_scores
    )
    fitness_profit, _ = evaluate_fitness(
        chrom, catalog_df, clean_sales, strategy="profit_focused",
        precomputed_rules=rules_df, precomputed_scores=anchor_scores
    )
    fitness_volume, _ = evaluate_fitness(
        chrom, catalog_df, clean_sales, strategy="volume_focused",
        precomputed_rules=rules_df, precomputed_scores=anchor_scores
    )

    assert isinstance(fitness_balanced, float)
    assert isinstance(fitness_profit, float)
    assert isinstance(fitness_volume, float)
    assert "projected_revenue" in sim_b
    assert "margin_protected" in sim_b


def test_genetic_algorithm_run(prepared_data):
    """Testa execução completa do loop evolutivo com população compacta."""
    catalog_df, clean_sales, rules_df, anchor_scores = prepared_data

    result = run_genetic_algorithm(
        catalog_df=catalog_df,
        clean_sales=clean_sales,
        population_size=6,
        generations=3,
        strategy="balanced",
        random_state=42,
        precomputed_rules=rules_df,
        precomputed_scores=anchor_scores
    )

    assert "best_chromosome" in result
    assert "best_fitness" in result
    assert "best_params" in result
    assert "best_simulation" in result
    assert len(result["fitness_history"]) == 3

    # O melhor fitness deve ser razoável e os parâmetros decodificados viáveis
    params = result["best_params"]
    assert 0.15 <= params["k_ratio"] <= 0.35
    assert 5 <= params["top_anchors"] <= 30
