"""
Módulo de Meta-Otimização Evolutiva (Algoritmo Genético) para Precificação Fitoherb.
Descobre os hiperparâmetros ótimos (Trava K%, Qtd Âncoras, Meia-Vida, Tetos de Preço).
"""
import copy
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.config import DEFAULT_CONFIG
from src.modules.pricing.domain.backtest_simulation import (
    generate_consolidated_recommendation,
    simulate_2026_replay,
    stress_test_volume_drop,
)
from src.modules.pricing.domain.basket_mining import (
    build_basket_matrix,
    build_rules_index,
    calculate_anchor_score,
    filter_orphan_baskets,
    mine_association_rules,
    select_anchors_and_compensators,
)
from src.modules.pricing.domain.elasticity_model import build_elasticity_matrix
from src.modules.pricing.domain.price_optimizer import OptimizationConfig, optimize_basket_pricing

# Limites rígidos de viabilidade comercial para cada gene (P-014)
GENE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "k_ratio": (0.15, 0.35),
    "top_anchors": (5.0, 30.0),
    "half_life_days": (30.0, 365.0),
    "anchor_discount": (-0.15, -0.05),
    "comp_max_increase": (0.01, 0.08),
    "stress_drop": (0.01, 0.10),
}

GENE_KEYS = list(GENE_BOUNDS.keys())


def decode_chromosome(chromosome: np.ndarray) -> Dict[str, Any]:
    """
    Decodifica o vetor numérico do cromossomo para dicionário de hiperparâmetros.
    """
    return {
        "k_ratio": round(float(chromosome[0]), 2),
        "top_anchors": int(round(float(chromosome[1]))),
        "half_life_days": round(float(chromosome[2]), 1),
        "anchor_discount": round(float(chromosome[3]), 2),
        "comp_max_increase": round(float(chromosome[4]), 2),
        "stress_drop": round(float(chromosome[5]), 2),
    }


def initialize_population(
    pop_size: int,
    random_state: Optional[int] = None
) -> np.ndarray:
    """
    Inicializa população uniforme respeitando os bounds de cada gene.
    """
    rng = np.random.default_rng(random_state)
    population = np.zeros((pop_size, len(GENE_KEYS)))

    for i, key in enumerate(GENE_KEYS):
        low, high = GENE_BOUNDS[key]
        population[:, i] = rng.uniform(low, high, size=pop_size)

    return population


def evaluate_fitness(
    chromosome: np.ndarray,
    catalog_df: pd.DataFrame,
    clean_sales: pd.DataFrame,
    strategy: str = "balanced",
    precomputed_rules: Optional[pd.DataFrame] = None,
    precomputed_scores: Optional[pd.DataFrame] = None,
    fitness_cache: Optional[Dict[tuple, Tuple[float, Dict[str, Any]]]] = None,
    precomputed_rules_index: Optional[Dict[int, List[int]]] = None,
    replay_sales: Optional[pd.DataFrame] = None,
) -> Tuple[float, Dict[str, Any]]:
    """
    Avalia a aptidão (fitness) de um indivíduo segundo a estratégia comercial (P-015).
    """
    params = decode_chromosome(chromosome)
    cache_key = tuple(params.values())

    if fitness_cache is not None and cache_key in fitness_cache:
        return fitness_cache[cache_key]

    try:
        # 1. Regras de associação e scores (usa pré-computados para máxima velocidade)
        if precomputed_rules is None or precomputed_scores is None:
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
        else:
            rules_df = precomputed_rules
            anchor_scores = precomputed_scores

        # 2. Eleição dos Âncoras do cromossomo (com indexação O(1) de regras)
        top_anchors, anchor_compensators = select_anchors_and_compensators(
            anchor_scores,
            rules_df,
            top_n_anchors=params["top_anchors"],
            max_comp_per_anchor=DEFAULT_CONFIG.max_compensators_per_anchor,
            precomputed_rules_index=precomputed_rules_index
        )

        # 3. Matriz de Elasticidade
        catalog_price_dict = catalog_df.set_index("Código")["Preço"].to_dict()
        all_selected_skus = list(set(top_anchors + [c for comps in anchor_compensators.values() for c in comps]))
        elasticity_matrix = build_elasticity_matrix(
            skus=all_selected_skus,
            sales_df=clean_sales,
            catalog_prices=catalog_price_dict,
            half_life_days=params["half_life_days"]
        )

        # 4. Otimização Prescritiva HiGHS
        opt_config = OptimizationConfig(
            anchor_min_discount=params["anchor_discount"] - 0.02,
            anchor_max_discount=params["anchor_discount"],
            comp_min_increase=DEFAULT_CONFIG.comp_min_increase,
            comp_max_increase=params["comp_max_increase"],
            margin_floor_pct=DEFAULT_CONFIG.margin_floor_pct,
            k_basket_ratio=params["k_ratio"],
        )

        volume_dict = clean_sales.groupby("Cod Produto")["Qtd Venda"].sum().to_dict()
        cost_dict = catalog_df.set_index("Código")["Custo"].to_dict()

        pricing_recommendations: Dict[int, dict] = {}
        total_delta_margin_anchors = 0.0
        total_delta_margin_comps = 0.0

        for anchor in top_anchors:
            comps = anchor_compensators.get(anchor, [])
            if not comps:
                continue

            res = optimize_basket_pricing(
                anchor_sku=anchor,
                compensators=comps,
                base_prices=catalog_price_dict,
                costs=cost_dict,
                volumes=volume_dict,
                own_elasticities={s: elasticity_matrix.get((s, s), -1.2) for s in [anchor] + comps},
                config=opt_config
            )

            if res.success:
                ancora_new_p = res.new_prices[anchor]
                p0_a = catalog_price_dict[anchor]
                delta_p_a = ancora_new_p - p0_a
                q0_a = volume_dict.get(anchor, 1.0)
                margin_imp_a = delta_p_a * q0_a
                total_delta_margin_anchors += margin_imp_a

                pricing_recommendations[anchor] = {
                    "papel": "PRODUTO ÂNCORA",
                    "novo_preco": ancora_new_p,
                    "impacto_margem": margin_imp_a,
                }

                for comp_sku in comps:
                    comp_new_p = res.new_prices[comp_sku]
                    p0_c = catalog_price_dict[comp_sku]
                    delta_p_c = comp_new_p - p0_c
                    q0_c = volume_dict.get(comp_sku, 1.0)
                    margin_imp_c = delta_p_c * q0_c
                    total_delta_margin_comps += margin_imp_c

                    if comp_sku not in pricing_recommendations:
                        pricing_recommendations[comp_sku] = {
                            "papel": "COMPENSADOR",
                            "novo_preco": comp_new_p,
                            "impacto_margem": margin_imp_c,
                        }

        # 5. Backtest Replay 2026 e Estresse
        all_new_prices = {sku: info["novo_preco"] for sku, info in pricing_recommendations.items()}
        replay_metrics = simulate_2026_replay(
            orders_df=replay_sales if replay_sales is not None else clean_sales,
            new_prices=all_new_prices,
            anchor_skus=set(top_anchors),
            k_ratio=params["k_ratio"]
        )

        stress_metrics = stress_test_volume_drop(
            delta_margin_anchor=total_delta_margin_anchors,
            delta_margin_comp=total_delta_margin_comps,
            comp_volume_drop_pct=params["stress_drop"]
        )

        net_profit = float(stress_metrics.get("lucro_liquido_estresse", 0.0))
        eligibility_pct = float(replay_metrics.get("pct_elegibilidade", 0.0))
        margin_protected = bool(stress_metrics.get("margem_protegida", False))

        # Normalização do Lucro (escala normalizada)
        norm_profit = net_profit / 5000.0
        norm_eligibility = eligibility_pct / 100.0

        # Ponderação pela estratégia (P-015)
        if strategy == "profit_focused":
            w_profit, w_elig = 0.75, 0.25
        elif strategy == "volume_focused":
            w_profit, w_elig = 0.20, 0.80
        else:  # balanced
            w_profit, w_elig = 0.50, 0.50

        fitness = (w_profit * norm_profit) + (w_elig * norm_eligibility)

        # Penalidade severa se a margem for comprometida no estresse
        if not margin_protected or net_profit < 0:
            fitness -= 3.0

        simulation_info = {
            "projected_revenue": float(replay_metrics.get("faturamento_projetado", 0.0)),
            "replay_2026_eligibility_pct": eligibility_pct,
            "stress_net_profit": net_profit,
            "margin_protected": margin_protected,
            "anchors_elected": len(top_anchors),
            "compensators_elected": len(pricing_recommendations) - len(top_anchors)
        }

    except Exception as e:
        import logging
        logging.getLogger("src.meta_tuner").warning(f"Erro em evaluate_fitness: {e}")
        fitness = -10.0
        simulation_info = {
            "projected_revenue": 0.0,
            "replay_2026_eligibility_pct": 0.0,
            "stress_net_profit": -9999.0,
            "margin_protected": False,
            "anchors_elected": 0,
            "compensators_elected": 0
        }

    if fitness_cache is not None:
        fitness_cache[cache_key] = (float(fitness), simulation_info)

    return float(fitness), simulation_info


def tournament_selection(
    population: np.ndarray,
    fitness_scores: np.ndarray,
    tournament_size: int = 3,
    rng: Optional[np.random.Generator] = None
) -> np.ndarray:
    """
    Seleção por Torneio: sorteia k indivíduos e seleciona o mais apto.
    """
    if rng is None:
        rng = np.random.default_rng()

    indices = rng.choice(len(population), size=min(tournament_size, len(population)), replace=False)
    best_idx = indices[np.argmax(fitness_scores[indices])]
    return population[best_idx].copy()


def crossover_arithmetic(
    parent1: np.ndarray,
    parent2: np.ndarray,
    crossover_rate: float = 0.85,
    rng: Optional[np.random.Generator] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Crossover Aritmético: combinação convexa entre dois pais.
    """
    if rng is None:
        rng = np.random.default_rng()

    if rng.random() > crossover_rate:
        return parent1.copy(), parent2.copy()

    alpha = rng.uniform(0.1, 0.9, size=len(parent1))
    child1 = alpha * parent1 + (1.0 - alpha) * parent2
    child2 = (1.0 - alpha) * parent1 + alpha * parent2

    # Clipping aos limites
    for i, key in enumerate(GENE_KEYS):
        low, high = GENE_BOUNDS[key]
        child1[i] = np.clip(child1[i], low, high)
        child2[i] = np.clip(child2[i], low, high)

    return child1, child2


def mutate_gaussian(
    chromosome: np.ndarray,
    mutation_rate: float = 0.25,
    scale: float = 0.10,
    rng: Optional[np.random.Generator] = None
) -> np.ndarray:
    """
    Mutação Gaussiana adaptativa truncada nos limites dos genes (P-016).
    """
    if rng is None:
        rng = np.random.default_rng()

    mutated = chromosome.copy()
    for i, key in enumerate(GENE_KEYS):
        if rng.random() < mutation_rate:
            low, high = GENE_BOUNDS[key]
            gene_range = high - low
            noise = rng.normal(0.0, scale * gene_range)
            mutated[i] = np.clip(mutated[i] + noise, low, high)

    return mutated


def run_genetic_algorithm(
    catalog_df: pd.DataFrame,
    clean_sales: pd.DataFrame,
    population_size: int = 12,
    generations: int = 6,
    strategy: str = "balanced",
    elitism_count: int = 2,
    random_state: Optional[int] = 42,
    precomputed_rules: Optional[pd.DataFrame] = None,
    precomputed_scores: Optional[pd.DataFrame] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    precomputed_rules_index: Optional[Dict[int, List[int]]] = None,
    replay_sales: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Executa o Algoritmo Genético completo para descobrir os hiperparâmetros ótimos.
    Permite progress_callback para streaming em tempo real do andamento das gerações.
    Otimizado para execução ultra-rápida via indexação de regras e pré-filtragem analítica.
    """
    rng = np.random.default_rng(random_state)

    if progress_callback is not None:
        progress_callback({
            "generation": 0,
            "total_generations": generations,
            "percent": 5,
            "current_best_fitness": 0.0,
            "message": "Inicializando população genética e limites comerciais..."
        })

    # Performance: Usa regras pré-computadas do cache ou minera sob demanda
    if precomputed_rules is not None and precomputed_scores is not None:
        rules_df = precomputed_rules
        anchor_scores = precomputed_scores
    else:
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

    # Índice de regras para lookups O(1) de compensadores
    if precomputed_rules_index is not None:
        rules_index = precomputed_rules_index
    elif rules_df is not None and not rules_df.empty:
        rules_index = build_rules_index(rules_df)
    else:
        rules_index = None

    # Base de replay de 2026 pré-isolada
    if replay_sales is not None:
        replay_df = replay_sales
    elif "Data" in clean_sales.columns and pd.api.types.is_datetime64_any_dtype(clean_sales["Data"]):
        df_2026 = clean_sales[clean_sales["Data"].dt.year >= 2026]
        replay_df = df_2026 if not df_2026.empty else clean_sales
    else:
        replay_df = clean_sales

    population = initialize_population(population_size, random_state=random_state)
    fitness_cache: Dict[tuple, Tuple[float, Dict[str, Any]]] = {}

    best_overall_chrom: Optional[np.ndarray] = None
    best_overall_fitness: float = -np.inf
    best_overall_sim: Dict[str, Any] = {}
    fitness_history: List[float] = []

    for gen in range(generations):
        fitness_scores = np.zeros(population_size)
        sim_results: List[Dict[str, Any]] = []

        # Avaliação de Fitness da População
        for idx in range(population_size):
            fit, sim_info = evaluate_fitness(
                population[idx], catalog_df, clean_sales,
                strategy=strategy,
                precomputed_rules=rules_df,
                precomputed_scores=anchor_scores,
                fitness_cache=fitness_cache,
                precomputed_rules_index=rules_index,
                replay_sales=replay_df
            )
            fitness_scores[idx] = fit
            sim_results.append(sim_info)

            if fit > best_overall_fitness:
                best_overall_fitness = fit
                best_overall_chrom = population[idx].copy()
                best_overall_sim = copy.deepcopy(sim_info)

        current_best = float(np.max(fitness_scores))
        fitness_history.append(current_best)

        if progress_callback is not None:
            pct = int(((gen + 1) / generations) * 100)
            progress_callback({
                "generation": gen + 1,
                "total_generations": generations,
                "percent": pct,
                "current_best_fitness": round(float(best_overall_fitness), 4),
                "message": f"Geração {gen + 1} de {generations}: Fitness {round(float(best_overall_fitness), 2)} | Otimizando genes..."
            })

        # Se for a última geração, encerra
        if gen == generations - 1:
            break

        # Construção da Próxima Geração com Elitismo
        sorted_indices = np.argsort(fitness_scores)[::-1]
        next_population = []

        # Elitismo: preserva os melhores indivíduos
        for e in range(min(elitism_count, population_size)):
            next_population.append(population[sorted_indices[e]].copy())

        # Reprodução (Seleção + Crossover + Mutação)
        while len(next_population) < population_size:
            p1 = tournament_selection(population, fitness_scores, rng=rng)
            p2 = tournament_selection(population, fitness_scores, rng=rng)

            c1, c2 = crossover_arithmetic(p1, p2, crossover_rate=0.85, rng=rng)

            # Reduz a escala da mutação ao longo das gerações (Decaimento Adaptativo)
            decay_scale = 0.12 * (1.0 - (gen / generations) * 0.5)
            c1 = mutate_gaussian(c1, mutation_rate=0.25, scale=decay_scale, rng=rng)
            c2 = mutate_gaussian(c2, mutation_rate=0.25, scale=decay_scale, rng=rng)

            next_population.append(c1)
            if len(next_population) < population_size:
                next_population.append(c2)

        population = np.array(next_population)

    decoded_best = decode_chromosome(best_overall_chrom)

    return {
        "best_chromosome": best_overall_chrom.tolist(),
        "best_fitness": round(float(best_overall_fitness), 4),
        "best_params": decoded_best,
        "best_simulation": best_overall_sim,
        "fitness_history": [round(f, 4) for f in fitness_history],
        "generations_run": generations,
        "strategy": strategy
    }
