"""
Módulo de Backtesting, Simulação de Monte Carlo e Geração de Entregáveis (US-06, P-010).
Executa replay histórico de 2026, stress testing de volume e exportação em CSV e SQL.
"""
import logging
from typing import Dict, List, Set, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def simulate_2026_replay(
    orders_df: pd.DataFrame,
    new_prices: Dict[int, float],
    anchor_skus: Set[int],
    k_ratio: Union[float, Dict[int, float]] = 0.25
) -> Dict[str, float]:
    """
    Regra P-010 e P-017: Replay histórico dos pedidos aplicando os novos preços.
    Avalia a proporção de pedidos que cumprem a trava de cesta K% (global ou específica por âncora).
    """
    # Se houver campo Data, tentar filtrar 2026 antes de copiar a base inteira
    if "Data" in orders_df.columns and pd.api.types.is_datetime64_any_dtype(orders_df["Data"]):
        df_2026 = orders_df[orders_df["Data"].dt.year >= 2026]
        df = df_2026.copy() if not df_2026.empty else orders_df.copy()
    else:
        df = orders_df.copy()

    if "Preco Tabela" in df.columns:
        fallback_price = df["Preco Tabela"]
    elif "Valor Venda" in df.columns:
        fallback_price = df["Valor Venda"] / df["Qtd Venda"]
    else:
        fallback_price = 0.0

    df["preco_novo"] = df["Cod Produto"].map(new_prices).fillna(fallback_price)
    df["faturamento_novo"] = df["preco_novo"] * df["Qtd Venda"]
    df["is_ancora"] = df["Cod Produto"].isin(anchor_skus)
    df["ancora_rev_item"] = np.where(df["is_ancora"], df["faturamento_novo"], 0.0)

    # Identificar pedidos com âncora
    orders_with_anchor_set = set(df[df["is_ancora"]]["Pedido"].unique())
    total_with_anchor = len(orders_with_anchor_set)

    if total_with_anchor == 0:
        return {
            "total_pedidos_com_ancora": 0,
            "pedidos_elegiveis_trava": 0,
            "pct_elegibilidade": 0.0,
            "faturamento_projetado": float(df["faturamento_novo"].sum()),
        }

    if isinstance(k_ratio, dict):
        # Regra P-017: Validação por trava comercial individual de cada âncora
        order_totals = df.groupby("Pedido")["faturamento_novo"].transform("sum")
        df["order_total"] = order_totals

        anchor_rows = df[df["is_ancora"]].copy()
        anchor_rows["k_limit"] = anchor_rows["Cod Produto"].map(k_ratio).fillna(0.25)
        anchor_rows["violates"] = anchor_rows["faturamento_novo"] > (
            anchor_rows["k_limit"] * anchor_rows["order_total"] + 1e-4
        )
        orders_violating = set(anchor_rows[anchor_rows["violates"]]["Pedido"].unique())
        eligible_orders = total_with_anchor - len(orders_violating)
    else:
        # Trava escalar uniforme tradicional
        order_summary = df.groupby("Pedido", sort=False).agg(
            total_rev=("faturamento_novo", "sum"),
            ancora_rev=("ancora_rev_item", "sum"),
            has_anchor=("is_ancora", "any")
        )
        orders_with_anchor = order_summary[order_summary["has_anchor"]]
        anchor_ratios = orders_with_anchor["ancora_rev"] / np.maximum(orders_with_anchor["total_rev"], 1e-4)
        eligible_orders = int((anchor_ratios <= k_ratio).sum())

    pct_eligibility = (eligible_orders / total_with_anchor) * 100.0

    return {
        "total_pedidos_com_ancora": int(total_with_anchor),
        "pedidos_elegiveis_trava": int(eligible_orders),
        "pct_elegibilidade": round(float(pct_eligibility), 2),
        "faturamento_projetado": round(float(df["faturamento_novo"].sum()), 2),
    }


def stress_test_volume_drop(
    delta_margin_anchor: float,
    delta_margin_comp: float,
    comp_volume_drop_pct: float = 0.05
) -> Dict[str, float]:
    """
    Regra P-010: Teste de estresse com reação adversa do mercado (queda de 3% a 5% nos compensadores).
    Verifica se a margem global permanece protegida (lucro >= 0).
    """
    stressed_comp_margin = delta_margin_comp * (1.0 - comp_volume_drop_pct)
    net_stress_profit = delta_margin_anchor + stressed_comp_margin
    is_protected = net_stress_profit >= 0.0

    return {
        "queda_volume_compensadores_pct": round(comp_volume_drop_pct * 100.0, 1),
        "delta_margem_ancora": round(delta_margin_anchor, 2),
        "delta_margem_comp_estresse": round(stressed_comp_margin, 2),
        "lucro_liquido_estresse": round(net_stress_profit, 2),
        "margem_protegida": bool(is_protected),
    }


def generate_consolidated_recommendation(
    catalog_df: pd.DataFrame,
    pricing_results: Dict[int, dict]
) -> Tuple[pd.DataFrame, str]:
    """
    Gera a tabela final de precificação consolidada (CSV) e os comandos de atualização para ERP (SQL).
    """
    rows = []

    for _, row in catalog_df.iterrows():
        sku = int(row["Código"])
        desc = str(row["Descrição"])
        brand = str(row["Fornec/Marca"])
        base_price = float(row["Preço"])

        if sku in pricing_results:
            info = pricing_results[sku]
            papel = info["papel"]
            new_price = round(float(info["novo_preco"]), 2)
            rule = info.get("regra", "")
            margin_imp = round(float(info.get("impacto_margem", 0.0)), 2)
            trava_k = info.get("trava_k")
        else:
            papel = "NEUTRO"
            new_price = base_price
            rule = "Manter preço de tabela vigente"
            margin_imp = 0.0
            trava_k = None

        delta_reais = round(new_price - base_price, 2)
        delta_pct = round(((new_price - base_price) / max(base_price, 1e-4)) * 100.0, 2)

        trava_k_str = f"{int(round(trava_k * 100))}%" if (trava_k is not None and "ÂNCORA" in papel) else "-"

        rows.append({
            "Codigo": sku,
            "Descricao": desc,
            "Fornecedor_Marca": brand,
            "Papel_Estrategico": papel,
            "Preco_Atual_Tabela": base_price,
            "Novo_Preco_Sugerido": new_price,
            "Variacao_Reais": delta_reais,
            "Variacao_Percentual": delta_pct,
            "Trava_K_Percentual": trava_k_str,
            "Regra_Comercial_Pedido": rule,
            "Impacto_Margem_Projetada": margin_imp,
        })

    df_consolidated = pd.DataFrame(rows)
    df_consolidated = df_consolidated.sort_values(
        by=["Papel_Estrategico", "Impacto_Margem_Projetada"],
        ascending=[True, False]
    ).reset_index(drop=True)

    # Geração do script SQL compatível com ERP Atrio / Relacional
    sql_lines = [
        "-- ==========================================================================",
        "-- FITOHERB NORDESTE DISTRIBUIDORA LTDA",
        "-- Script SQL: Atualização de Precificação Dinâmica Compensatória",
        f"-- Data de Geração: 2026-09-29 | Total de SKUs: {len(df_consolidated)}",
        "-- ==========================================================================\n",
        "BEGIN TRANSACTION;\n"
    ]

    for _, r in df_consolidated[df_consolidated["Papel_Estrategico"] != "NEUTRO"].iterrows():
        sql_lines.append(
            f"UPDATE PRODUTOS SET PRECO_VENDA = {r['Novo_Preco_Sugerido']:.2f}, "
            f"OBSERVAÇÃO_COMERCIAL = '{r['Regra_Comercial_Pedido']}' "
            f"WHERE CODIGO = {r['Codigo']}; -- {r['Descricao']} ({r['Papel_Estrategico']})"
        )

    sql_lines.append("\nCOMMIT;")
    sql_content = "\n".join(sql_lines)

    return df_consolidated, sql_content
