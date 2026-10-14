"""
Serviço de Negócio para o Módulo de Precificação (Pricing Predictor).
Gerencia cache em memória, execução de pipeline analítico e otimização HiGHS.
"""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.core.config import DEFAULT_CONFIG
from src.core.database import fetch_products_from_database, fetch_sales_from_database, test_db_connection
from src.etl import load_catalog, load_catalog_from_database, run_etl_pipeline
from src.modules.pricing.api.schemas import PricingRequest
from src.modules.pricing.domain.backtest_simulation import (
    generate_consolidated_recommendation,
    simulate_2026_replay,
    stress_test_volume_drop,
)
from src.modules.pricing.domain.basket_mining import (
    build_basket_matrix,
    build_rules_index,
    calculate_anchor_natural_shares,
    calculate_anchor_score,
    compute_optimized_anchor_locks,
    filter_orphan_baskets,
    mine_association_rules,
    select_anchors_and_compensators,
)
from src.modules.pricing.domain.elasticity_model import build_elasticity_matrix
from src.modules.pricing.domain.price_optimizer import OptimizationConfig, optimize_basket_pricing

logger = logging.getLogger(__name__)

# Cache em memória para evitar re-leitura do banco e re-mineração FP-Growth a cada requisição
_DATA_CACHE: Dict[str, Any] = {}


def get_cached_base_data(force_reload: bool = False) -> Dict[str, Any]:
    """
    Carrega e retém em memória o catálogo, vendas limpas, regras de associação FP-Growth
    e scores dos âncoras. Extrai os dados 100% diretamente do banco SQL Server (P-022).
    Garante respostas instantâneas (< 300ms) para simulações.
    """
    if force_reload or "rules_df" not in _DATA_CACHE:
        # Extração direta via Banco SQL Server da Fitoherb (P-022) com fallback seguro para templates em ambiente de CI/CD
        logger.info("Conectando ao SQL Server da Fitoherb para carregar catálogo e vendas atualizadas...")
        db_check = test_db_connection()
        if db_check.get("connected"):
            catalog_df = load_catalog_from_database()
            raw_sales = fetch_sales_from_database()
            data_source = "sql_server"
            logger.info(
                f"Dados carregados com sucesso diretamente do SQL Server: "
                f"{len(catalog_df)} produtos e {len(raw_sales)} vendas."
            )
        else:
            logger.warning(f"Banco SQL Server indisponível ({db_check.get('message')}). Utilizando templates sanitizados para simulação...")
            template_catalog = Path("templates/lista_precos_template.csv")
            template_sales = Path("templates/vendas_template.csv")
            if template_catalog.exists() and template_sales.exists():
                catalog_df = load_catalog(template_catalog, skiprows=4, encoding="utf-8")
                raw_sales = pd.read_csv(template_sales, encoding="utf-8")
                data_source = "templates"
            else:
                raise ConnectionError(db_check.get("message", "Banco SQL Server e templates indisponíveis"))

        clean_sales = run_etl_pipeline(raw_sales, catalog_df, config=DEFAULT_CONFIG)


        # Mineração de regras de cesta e cálculo de score executados uma única vez
        valid_baskets = filter_orphan_baskets(clean_sales, min_skus=DEFAULT_CONFIG.min_basket_size)
        basket_matrix = build_basket_matrix(valid_baskets)
        rules_df = mine_association_rules(
            basket_matrix,
            min_support=DEFAULT_CONFIG.min_support,
            min_confidence=DEFAULT_CONFIG.min_confidence,
            min_lift=DEFAULT_CONFIG.min_lift
        )
        anchor_scores = calculate_anchor_score(
            clean_sales,
            rules_df,
            weights=(DEFAULT_CONFIG.weight_giro, DEFAULT_CONFIG.weight_penetracao, DEFAULT_CONFIG.weight_lift)
        )

        catalog_price_dict = catalog_df.set_index("Código")["Preço"].to_dict()
        cost_dict = catalog_df.set_index("Código")["Custo"].to_dict()
        volume_dict = clean_sales.groupby("Cod Produto")["Qtd Venda"].sum().to_dict()
        rules_index = build_rules_index(rules_df)
        anchor_natural_shares = calculate_anchor_natural_shares(clean_sales)
        sales_2026 = (
            clean_sales[clean_sales["Data"].dt.year >= 2026].copy()
            if "Data" in clean_sales.columns and pd.api.types.is_datetime64_any_dtype(clean_sales["Data"])
            else clean_sales
        )

        _DATA_CACHE["catalog_df"] = catalog_df
        _DATA_CACHE["clean_sales"] = clean_sales
        _DATA_CACHE["rules_df"] = rules_df
        _DATA_CACHE["anchor_scores"] = anchor_scores
        _DATA_CACHE["catalog_price_dict"] = catalog_price_dict
        _DATA_CACHE["cost_dict"] = cost_dict
        _DATA_CACHE["volume_dict"] = volume_dict
        _DATA_CACHE["rules_index"] = rules_index
        _DATA_CACHE["sales_2026"] = sales_2026
        _DATA_CACHE["anchor_natural_shares"] = anchor_natural_shares
        _DATA_CACHE["data_source"] = data_source
        _DATA_CACHE["raw_sales_count"] = len(raw_sales)
        _DATA_CACHE["raw_products_count"] = len(catalog_df)
        _DATA_CACHE["loaded_at"] = datetime.now(timezone.utc).isoformat()

    return _DATA_CACHE


def get_cached_etl_data():
    """Compatibilidade retroativa: retorna (catalog_df, clean_sales)."""
    cache = get_cached_base_data()
    return cache["catalog_df"], cache["clean_sales"]


def execute_pricing_computation(req: PricingRequest) -> Tuple[pd.DataFrame, list, dict, dict, dict, dict]:
    """Executa o pipeline analítico com base nos parâmetros da requisição."""
    cache = get_cached_base_data()
    catalog_df = cache["catalog_df"]
    clean_sales = cache["clean_sales"]
    rules_df = cache["rules_df"]
    anchor_scores = cache["anchor_scores"]
    catalog_price_dict = cache["catalog_price_dict"]
    cost_dict = cache["cost_dict"]
    volume_dict = cache["volume_dict"]
    anchor_natural_shares = cache.get("anchor_natural_shares", {})

    # 1. Seleção de Âncoras: Se modo autônomo estiver ativo, determina quantidade dinâmica (P-048)
    if req.autonomous_sku_pricing and not anchor_scores.empty:
        # Corte estatístico: produtos com score composto elevado (Top percentil) limitado entre 8 e 32
        score_threshold = float(anchor_scores["score_composto"].quantile(0.85)) if len(anchor_scores) >= 10 else 0.5
        qualifying_anchors_count = int((anchor_scores["score_composto"] >= score_threshold).sum())
        effective_top_anchors = max(8, min(32, qualifying_anchors_count))
    else:
        effective_top_anchors = req.top_anchors

    top_anchors, anchor_compensators = select_anchors_and_compensators(
        anchor_scores,
        rules_df,
        top_n_anchors=effective_top_anchors,
        max_comp_per_anchor=DEFAULT_CONFIG.max_compensators_per_anchor
    )

    # 1.1 Otimização das Travas Comerciais por Âncora (Regra P-017)
    anchor_locks = compute_optimized_anchor_locks(
        anchors=top_anchors,
        natural_shares=anchor_natural_shares,
        base_k_ratio=req.k_ratio,
        variable_mode=req.variable_k_ratio
    )

    # 2. Matriz de Elasticidade para SKUs selecionados (< 50ms)
    all_selected_skus = list(set(top_anchors + [c for comps in anchor_compensators.values() for c in comps]))
    elasticity_matrix = build_elasticity_matrix(
        skus=all_selected_skus,
        sales_df=clean_sales,
        catalog_prices=catalog_price_dict,
        half_life_days=req.half_life_days
    )

    # 3. Otimização Prescritiva HiGHS com limites granulares por SKU (P-049 e P-050)
    opt_config = OptimizationConfig(
        anchor_min_discount=req.anchor_min_discount,
        anchor_max_discount=req.anchor_max_discount,
        comp_min_increase=DEFAULT_CONFIG.comp_min_increase,
        comp_max_increase=req.comp_max_increase,
        margin_floor_pct=DEFAULT_CONFIG.margin_floor_pct,
        k_basket_ratio=req.k_ratio,
    )

    pricing_recommendations: Dict[int, dict] = {}
    total_delta_margin_anchors = 0.0
    total_delta_margin_comps = 0.0

    for anchor in top_anchors:
        comps = anchor_compensators.get(anchor, [])
        if not comps:
            continue

        # No modo autônomo, personaliza os bounds individuais para este âncora específico (P-049)
        anchor_opt_config = opt_config
        if req.autonomous_sku_pricing:
            e_a = abs(elasticity_matrix.get((anchor, anchor), -1.2))
            # Ajuste proporcional: SKU mais elástico recebe desconto ligeiramente maior, até o limite seguro
            dyn_min_disc = max(req.anchor_min_discount, -0.05 - (0.07 * min(e_a / 1.5, 1.4)))
            dyn_max_disc = min(req.anchor_max_discount, dyn_min_disc + 0.03)
            anchor_opt_config = OptimizationConfig(
                anchor_min_discount=dyn_min_disc,
                anchor_max_discount=dyn_max_disc,
                comp_min_increase=opt_config.comp_min_increase,
                comp_max_increase=opt_config.comp_max_increase,
                margin_floor_pct=opt_config.margin_floor_pct,
                k_basket_ratio=req.k_ratio,
            )

        res = optimize_basket_pricing(
            anchor_sku=anchor,
            compensators=comps,
            base_prices=catalog_price_dict,
            costs=cost_dict,
            volumes=volume_dict,
            own_elasticities={s: elasticity_matrix.get((s, s), -1.2) for s in [anchor] + comps},
            config=anchor_opt_config
        )

        if res.success:
            ancora_new_p = res.new_prices[anchor]
            p0_a = catalog_price_dict[anchor]
            delta_p_a = ancora_new_p - p0_a
            q0_a = volume_dict.get(anchor, 1.0)
            margin_imp_a = delta_p_a * q0_a
            total_delta_margin_anchors += margin_imp_a

            anchor_k = anchor_locks.get(anchor, req.k_ratio)
            e_a_val = elasticity_matrix.get((anchor, anchor), -1.2)
            pricing_recommendations[anchor] = {
                "papel": "PRODUTO ÂNCORA",
                "novo_preco": ancora_new_p,
                "impacto_margem": margin_imp_a,
                "regra": f"Válido apenas quando o item representar até {int(round(anchor_k*100))}% do valor total do pedido",
                "trava_k": anchor_k,
                "elasticidade": round(float(e_a_val), 2),
                "queda_volume_estresse_pct": 0.0,
            }

            for comp_sku in comps:
                comp_new_p = res.new_prices[comp_sku]
                p0_c = catalog_price_dict[comp_sku]
                delta_p_c = comp_new_p - p0_c
                q0_c = volume_dict.get(comp_sku, 1.0)
                margin_imp_c = delta_p_c * q0_c
                total_delta_margin_comps += margin_imp_c

                if comp_sku not in pricing_recommendations:
                    e_c_val = elasticity_matrix.get((comp_sku, comp_sku), -1.0)
                    delta_pct_c = delta_p_c / p0_c if p0_c > 0 else 0.0
                    # P-051: Queda econométrica preditiva por produto
                    sku_stress_drop = min(0.15, max(0.01, abs(e_c_val) * delta_pct_c)) if req.autonomous_sku_pricing else req.stress_drop

                    pricing_recommendations[comp_sku] = {
                        "papel": "COMPENSADOR",
                        "novo_preco": comp_new_p,
                        "impacto_margem": margin_imp_c,
                        "regra": f"Item compensador de parâmetros (associado ao âncora {anchor})",
                        "elasticidade": round(float(e_c_val), 2),
                        "queda_volume_estresse_pct": round(float(sku_stress_drop), 4),
                    }

    # 5. Backtest Replay 2026 e Estresse
    all_new_prices = {sku: info["novo_preco"] for sku, info in pricing_recommendations.items()}
    replay_metrics = simulate_2026_replay(
        orders_df=clean_sales,
        new_prices=all_new_prices,
        anchor_skus=set(top_anchors),
        k_ratio=anchor_locks if req.variable_k_ratio else req.k_ratio
    )

    # P-051: Cálculo ponderado do estresse por SKU se modo autônomo
    comp_skus_list = [s for s, info in pricing_recommendations.items() if info["papel"] == "COMPENSADOR"]
    if req.autonomous_sku_pricing and comp_skus_list:
        total_comp_rev = sum(catalog_price_dict.get(s, 10.0) * volume_dict.get(s, 1.0) for s in comp_skus_list)
        if total_comp_rev > 0:
            weighted_stress_drop = sum(
                (catalog_price_dict.get(s, 10.0) * volume_dict.get(s, 1.0) / total_comp_rev) * pricing_recommendations[s].get("queda_volume_estresse_pct", req.stress_drop)
                for s in comp_skus_list
            )
        else:
            weighted_stress_drop = req.stress_drop
    else:
        weighted_stress_drop = req.stress_drop

    stress_metrics = stress_test_volume_drop(
        delta_margin_anchor=total_delta_margin_anchors,
        delta_margin_comp=total_delta_margin_comps,
        comp_volume_drop_pct=weighted_stress_drop
    )

    # 6. Tabela Consolidada
    df_consolidated, _ = generate_consolidated_recommendation(
        catalog_df=catalog_df,
        pricing_results=pricing_recommendations
    )

    return df_consolidated, top_anchors, pricing_recommendations, replay_metrics, stress_metrics, anchor_locks


_PREDICTION_FILE = (
    Path(__file__).resolve().parents[4] / "outputs" / "latest_shared_prediction.json"
    if len(Path(__file__).resolve().parents) >= 5
    else Path.cwd() / "outputs" / "latest_shared_prediction.json"
)


def save_shared_prediction(data: Dict[str, Any]) -> None:
    """Salva a previsão calculada para que seja compartilhada entre todos os usuários."""
    _DATA_CACHE["latest_shared_prediction"] = data
    try:
        _PREDICTION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_PREDICTION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Falha ao persistir previsão compartilhada em disco: {e}")


def get_shared_prediction() -> Optional[Dict[str, Any]]:
    """Recupera a última previsão compartilhada entre todos os usuários."""
    if "latest_shared_prediction" in _DATA_CACHE:
        return _DATA_CACHE["latest_shared_prediction"]
    
    if _PREDICTION_FILE.exists():
        try:
            with open(_PREDICTION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _DATA_CACHE["latest_shared_prediction"] = data
                return data
        except Exception as e:
            logger.warning(f"Falha ao ler previsão compartilhada do disco: {e}")
            
    return None

