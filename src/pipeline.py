"""
Orquestrador do Pipeline Completo de Precificação Dinâmica Compensatória e Cestas B2B.
Integra ETL, Mineração de Cestas, Modelagem de Elasticidade, Otimização HiGHS e Backtesting.
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.backtest_simulation import (
    generate_consolidated_recommendation,
    simulate_2026_replay,
    stress_test_volume_drop,
)
from src.basket_mining import (
    build_basket_matrix,
    calculate_anchor_score,
    filter_orphan_baskets,
    mine_association_rules,
    select_anchors_and_compensators,
)
from src.config import DEFAULT_CONFIG, PipelineConfig
from src.core.database import fetch_sales_from_database
from src.elasticity_model import build_elasticity_matrix
from src.etl import load_catalog, load_catalog_from_database, run_etl_pipeline
from src.price_optimizer import (
    OptimizationConfig,
    optimize_basket_pricing,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


def resolve_file_path(primary: Optional[Path], fallback: Optional[Path] = None, template: Optional[Path] = None) -> Optional[Path]:
    """Resolve o arquivo existente caso fornecido."""
    if primary and primary.exists():
        return primary
    if fallback and fallback.exists():
        logger.info(f"Arquivo primário não encontrado; utilizando fallback: {fallback}")
        return fallback
    if template and template.exists():
        logger.info(f"Arquivo local não encontrado; utilizando template: {template}")
        return template
    return None


def run_full_pricing_pipeline(config: PipelineConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """
    Executa a esteira completa de ponta a ponta.
    """
    logger.info("=== INICIANDO PIPELINE DE PRECIFICAÇÃO DINÂMICA COMPENSATÓRIA (FITOHERB) ===")

    # 1. Ingestão do catálogo de produtos (prioridade: banco de dados SQL Server)
    if config.catalog_path and Path(config.catalog_path).exists():
        logger.info(f"1. Ingerindo catálogo mestre de arquivo: {config.catalog_path}")
        catalog_df = load_catalog(config.catalog_path, skiprows=config.catalog_skiprows, encoding="latin1")
    else:
        logger.info("1. Extraindo catálogo de produtos diretamente do SQL Server (Externo01.Produto)...")
        catalog_df = load_catalog_from_database()

    # 2. Ingestão da base de vendas (prioridade: banco de dados SQL Server)
    if config.sales_path and Path(config.sales_path).exists():
        logger.info(f"2. Ingerindo base de vendas de arquivo: {config.sales_path}")
        try:
            raw_sales = pd.read_csv(config.sales_path, encoding="latin1", low_memory=False)
        except UnicodeDecodeError:
            raw_sales = pd.read_csv(config.sales_path, encoding="utf-8", low_memory=False)
    else:
        logger.info("2. Extraindo vendas diretamente do SQL Server (Externo01.Vendas)...")
        raw_sales = fetch_sales_from_database()

    logger.info(f"Dados brutos carregados: {len(catalog_df)} produtos e {len(raw_sales)} vendas.")


    # 3. Funil de ETL e Higienização (P-001 a P-004 e LGPD)
    clean_sales = run_etl_pipeline(raw_sales, catalog_df, config=config)

    # 4. Market Basket Analysis (P-005)
    valid_baskets = filter_orphan_baskets(clean_sales, min_skus=config.min_basket_size)
    basket_matrix = build_basket_matrix(valid_baskets)
    rules_df = mine_association_rules(
        basket_matrix,
        min_support=config.min_support,
        min_confidence=config.min_confidence,
        min_lift=config.min_lift
    )

    # 5. Ranqueamento e Eleição de Âncoras (P-006)
    anchor_scores = calculate_anchor_score(
        clean_sales,
        rules_df,
        weights=(config.weight_giro, config.weight_penetracao, config.weight_lift)
    )
    
    top_anchors, anchor_compensators = select_anchors_and_compensators(
        anchor_scores,
        rules_df,
        top_n_anchors=config.top_n_anchors,
        max_comp_per_anchor=config.max_compensators_per_anchor
    )

    logger.info(f"Produtos Âncora eleitos ({len(top_anchors)}): {top_anchors}")

    # 6. Modelagem de Demanda e Elasticidades (P-007)
    catalog_price_dict = catalog_df.set_index("Código")["Preço"].to_dict()
    all_selected_skus = list(set(top_anchors + [c for comps in anchor_compensators.values() for c in comps]))
    
    elasticity_matrix = build_elasticity_matrix(
        skus=all_selected_skus,
        sales_df=clean_sales,
        catalog_prices=catalog_price_dict,
        half_life_days=config.temporal_half_life_days
    )

    # 7. Motor Prescritivo de Otimização de Preços (P-008 e P-009)
    opt_config = OptimizationConfig(
        anchor_min_discount=config.anchor_min_discount,
        anchor_max_discount=config.anchor_max_discount,
        comp_min_increase=config.comp_min_increase,
        comp_max_increase=config.comp_max_increase,
        margin_floor_pct=config.margin_floor_pct,
        k_basket_ratio=config.k_basket_ratio,
    )

    # Calcular volumes médios por SKU
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
            # Registrar recomendação do âncora
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
                "regra": f"Válido apenas quando o item representar até {int(config.k_basket_ratio*100)}% do valor total do pedido",
            }

            # Registrar compensadores
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
                        "regra": f"Item compensador de cesta (associado ao âncora {anchor})",
                    }

    # 8. Backtesting Replay e Stress Test (P-010)
    all_new_prices = {sku: info["novo_preco"] for sku, info in pricing_recommendations.items()}
    replay_metrics = simulate_2026_replay(
        orders_df=clean_sales,
        new_prices=all_new_prices,
        anchor_skus=set(top_anchors),
        k_ratio=config.k_basket_ratio
    )

    stress_metrics = stress_test_volume_drop(
        delta_margin_anchor=total_delta_margin_anchors,
        delta_margin_comp=total_delta_margin_comps,
        comp_volume_drop_pct=config.stress_volume_drop_pct
    )

    # 9. Geração dos Entregáveis (CSV e SQL)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    df_consolidated, sql_script = generate_consolidated_recommendation(
        catalog_df=catalog_df,
        pricing_results=pricing_recommendations
    )

    df_consolidated.to_csv(config.output_csv_path, index=False, encoding="utf-8-sig", sep=";")
    with open(config.output_sql_path, "w", encoding="utf-8") as f:
        f.write(sql_script)

    logger.info(f"Arquivos finais gerados com sucesso:\n- CSV: {config.output_csv_path}\n- SQL: {config.output_sql_path}")

    summary = {
        "total_skus_catalogo": len(catalog_df),
        "total_vendas_higienizadas": len(clean_sales),
        "total_regras_mineradas": len(rules_df),
        "ancoras_eleitos": len(top_anchors),
        "compensadores_eleitos": len([s for s, info in pricing_recommendations.items() if info["papel"] == "COMPENSADOR"]),
        "replay_2026": replay_metrics,
        "stress_test": stress_metrics,
        "output_csv": str(config.output_csv_path),
        "output_sql": str(config.output_sql_path),
    }

    return summary
