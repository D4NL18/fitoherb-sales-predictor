"""
Módulo de Mineração de Cestas B2B e Eleição de Produtos Âncora (US-02, US-03, P-005, P-006).
Utiliza FP-Growth sobre matrizes esparsas e cálculo de Score Composto Ponderado.
"""
import logging
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth

logger = logging.getLogger(__name__)


def filter_orphan_baskets(sales_df: pd.DataFrame, min_skus: int = 2) -> pd.DataFrame:
    """
    Regra P-005: Elimina pedidos que contenham menos de `min_skus` válidos de catálogo.
    Pedidos com apenas 1 SKU não representam cestas para fins de mineração de regras.
    """
    sku_counts_per_order = sales_df.groupby("Pedido")["Cod Produto"].nunique()
    valid_orders = sku_counts_per_order[sku_counts_per_order >= min_skus].index
    
    orphan_count = len(sku_counts_per_order) - len(valid_orders)
    if orphan_count > 0:
        logger.info(f"Filtro de Cestas Órfãs (P-005): {orphan_count} pedidos com < {min_skus} SKUs foram descartados.")

    return sales_df[sales_df["Pedido"].isin(valid_orders)].copy()


def build_basket_matrix(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Constrói a matriz binária booleana (Pedido x SKU) de co-ocorrência.
    """
    basket = (
        sales_df.groupby(["Pedido", "Cod Produto"])["Qtd Venda"]
        .sum()
        .unstack(fill_value=0)
    )
    # Converter para formato booleano estrito exigido pelo mlxtend
    return basket > 0


def mine_association_rules(
    basket_matrix: pd.DataFrame,
    min_support: float = 0.002,
    min_confidence: float = 0.02,
    min_lift: float = 0.1
) -> pd.DataFrame:
    """
    Executa FP-Growth e extrai regras de associação com suporte, confiança e lift (US-02).
    """
    logger.info(f"Executando FP-Growth com min_support={min_support} sobre {basket_matrix.shape[0]} pedidos...")
    
    frequent_itemsets = fpgrowth(
        basket_matrix,
        min_support=min_support,
        use_colnames=True
    )
    
    if frequent_itemsets.empty:
        logger.warning("Nenhum itemset frequente encontrado com o suporte fornecido.")
        return pd.DataFrame(columns=["antecedents", "consequents", "support", "confidence", "lift"])

    rules = association_rules(
        frequent_itemsets,
        metric="lift",
        min_threshold=min_lift,
    )
    
    # Filtrar por confiança mínima
    rules = rules[rules["confidence"] >= min_confidence].copy()
    logger.info(f"FP-Growth concluído: {len(rules)} regras de associação extraídas.")
    return rules


def calculate_anchor_score(
    sales_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    weights: Tuple[float, float, float] = (0.40, 0.35, 0.25)
) -> pd.DataFrame:
    """
    Regra P-006: Ranqueamento por Score Composto Ponderado:
    Score = 0.40 * Giro_Normalizado + 0.35 * Penetracao_Pedidos + 0.25 * Centralidade_Lift
    """
    w_giro, w_pen, w_lift = weights
    total_orders = sales_df["Pedido"].nunique()

    # Se houver data, priorizar 2026 para o giro recente
    if "Data" in sales_df.columns and pd.api.types.is_datetime64_any_dtype(sales_df["Data"]):
        recent_sales = sales_df[sales_df["Data"].dt.year >= 2026]
        if recent_sales.empty:
            recent_sales = sales_df
    else:
        recent_sales = sales_df

    # 1. Giro Recente (Volume faturado de unidades)
    giro_series = recent_sales.groupby("Cod Produto")["Qtd Venda"].sum()
    
    # 2. Penetração em Pedidos (fração de pedidos contendo o SKU)
    order_penetration = sales_df.groupby("Cod Produto")["Pedido"].nunique() / max(total_orders, 1)

    # 3. Centralidade de Lift (Média de Lift quando o SKU aparece como antecedente)
    lift_dict: Dict[int, float] = {}
    if not rules_df.empty:
        for _, row in rules_df.iterrows():
            antecedents = list(row["antecedents"])
            lift_val = row["lift"]
            for sku in antecedents:
                lift_dict.setdefault(sku, []).append(lift_val)
        
    avg_lift_map = {sku: float(np.mean(lifts)) for sku, lifts in lift_dict.items()}

    all_skus = sales_df["Cod Produto"].unique()
    scores = []

    for sku in all_skus:
        giro_val = giro_series.get(sku, 0.0)
        pen_val = order_penetration.get(sku, 0.0)
        lift_val = avg_lift_map.get(sku, 1.0) # default lift neutro = 1.0
        scores.append({
            "Cod Produto": sku,
            "giro": giro_val,
            "penetracao": pen_val,
            "centralidade_lift": lift_val,
        })

    df_scores = pd.DataFrame(scores)

    # Normalização Min-Max [0, 1]
    def min_max_scale(series: pd.Series) -> pd.Series:
        min_v = series.min()
        max_v = series.max()
        if max_v > min_v:
            return (series - min_v) / (max_v - min_v)
        return pd.Series(np.ones(len(series)), index=series.index)

    df_scores["giro_norm"] = min_max_scale(df_scores["giro"])
    df_scores["penetracao_norm"] = min_max_scale(df_scores["penetracao"])
    df_scores["lift_norm"] = min_max_scale(df_scores["centralidade_lift"])

    df_scores["score_composto"] = (
        w_giro * df_scores["giro_norm"]
        + w_pen * df_scores["penetracao_norm"]
        + w_lift * df_scores["lift_norm"]
    )

    df_scores = df_scores.sort_values(by="score_composto", ascending=False).reset_index(drop=True)
    return df_scores


def build_rules_index(rules_df: pd.DataFrame, max_comps_stored: int = 15) -> Dict[int, List[int]]:
    """
    Constrói índice de consequentes por antecedente uma única vez (O(1) lookups).
    Elimina a iteração sobre 800.000 regras durante otimizações repetidas.
    """
    sku_to_comps: Dict[int, List[int]] = {}
    if rules_df.empty:
        return sku_to_comps

    for row in rules_df.itertuples(index=False):
        ants = row.antecedents
        cons = row.consequents
        for a in ants:
            comps = sku_to_comps.get(a)
            if comps is None:
                comps = []
                sku_to_comps[a] = comps
            if len(comps) < max_comps_stored:
                for c in cons:
                    if c != a and c not in comps:
                        comps.append(c)
                        if len(comps) >= max_comps_stored:
                            break
    return sku_to_comps


def select_anchors_and_compensators(
    scores_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    top_n_anchors: int = 10,
    max_comp_per_anchor: int = 8,
    precomputed_rules_index: Optional[Dict[int, List[int]]] = None
) -> Tuple[List[int], Dict[int, List[int]]]:
    """
    Elege os Top N produtos âncora e mapeia seus itens compensadores diretos.
    Otimizado com precomputed_rules_index para consultas instantâneas em O(1),
    e itertuples com parada antecipada no fallback.
    """
    top_anchors = scores_df.head(top_n_anchors)["Cod Produto"].tolist()
    anchor_compensators: Dict[int, List[int]] = {a: [] for a in top_anchors}

    if precomputed_rules_index is not None:
        for anchor in top_anchors:
            comps = precomputed_rules_index.get(anchor, [])
            anchor_compensators[anchor] = [c for c in comps if c != anchor][:max_comp_per_anchor]
    elif not rules_df.empty:
        anchors_set = set(top_anchors)
        for r in rules_df.itertuples(index=False):
            matching_anchors = anchors_set.intersection(r.antecedents)
            if matching_anchors:
                for anchor in matching_anchors:
                    comps = anchor_compensators[anchor]
                    if len(comps) < max_comp_per_anchor:
                        for c in r.consequents:
                            if c != anchor and c not in comps:
                                comps.append(c)
                                if len(comps) >= max_comp_per_anchor:
                                    break

            if all(len(comps) >= max_comp_per_anchor for comps in anchor_compensators.values()):
                break

    # Fallback caso algum âncora não tenha regras suficientes mineradas
    fallback_pool = [sku for sku in scores_df["Cod Produto"].head(max_comp_per_anchor + 25)]
    for anchor in top_anchors:
        comps = anchor_compensators[anchor]
        if not comps:
            anchor_compensators[anchor] = [sku for sku in fallback_pool if sku != anchor][:max_comp_per_anchor]

    return top_anchors, anchor_compensators


def calculate_anchor_natural_shares(
    sales_df: pd.DataFrame,
    quantile: float = 0.75,
    min_share: float = 0.08,
    max_share: float = 0.45
) -> Dict[int, float]:
    """
    Calcula a distribuição empírica natural do share de cada SKU nos pedidos em que compareceu (Regra P-017).
    Retorna o quantil especificado (default p75) limitado aos limites de segurança de trava.
    Executado de forma estritamente vetorizada sobre pedidos.
    """
    if sales_df.empty or "Pedido" not in sales_df.columns or "Valor Venda" not in sales_df.columns:
        return {}

    order_totals = sales_df.groupby("Pedido")["Valor Venda"].transform("sum")
    valid_mask = order_totals > 0
    if not valid_mask.any():
        return {}

    sub = sales_df[valid_mask].copy()
    sub["item_share"] = sub["Valor Venda"] / order_totals[valid_mask]
    sku_quantiles = sub.groupby("Cod Produto")["item_share"].quantile(quantile)

    clipped = np.clip(sku_quantiles.values, min_share, max_share)
    return {int(sku): round(float(val), 2) for sku, val in zip(sku_quantiles.index, clipped)}


def compute_optimized_anchor_locks(
    anchors: List[int],
    natural_shares: Dict[int, float],
    base_k_ratio: float = 0.25,
    variable_mode: bool = True
) -> Dict[int, float]:
    """
    Calcula a trava comercial específica para cada produto âncora (Regra P-017).
    Se variable_mode for True, ajusta o share natural p75 pela sensibilidade da trava base.
    Se variable_mode for False, aplica a trava uniforme base_k_ratio para todos os âncoras.
    """
    locks: Dict[int, float] = {}
    scale = base_k_ratio / 0.25 if 0.25 > 0 else 1.0

    for a in anchors:
        if variable_mode:
            nat_share = natural_shares.get(a, 0.20)
            k_opt = round(float(np.clip(nat_share * scale, 0.08, 0.45)), 2)
            locks[a] = k_opt
        else:
            locks[a] = round(float(base_k_ratio), 2)

    return locks
