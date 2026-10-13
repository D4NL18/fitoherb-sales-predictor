"""
Motor Analítico de Estoque, Reposição e Previsão de Compras (Inventory Engine).
Implementa regras de negócio P-041 a P-047 (P-012).
Fitoherb Nordeste Distribuidora.
"""
import math
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd


def get_z_score(service_level: float) -> float:
    """
    Retorna o Z-score estatístico associado ao nível de serviço desejado (P-043.2).
    Suporta interpolação ou consulta rápida para níveis típicos.
    """
    try:
        from scipy.stats import norm
        return float(norm.ppf(service_level))
    except (ImportError, Exception):
        # Tabela de fallback para níveis clássicos de serviço
        if service_level <= 0.90:
            return 1.2816
        elif service_level <= 0.95:
            return 1.6449
        elif service_level <= 0.98:
            return 2.0537
        elif service_level <= 0.99:
            return 2.3263
        return 1.65


def calculate_sales_velocity(
    sales_df: pd.DataFrame,
    window_days: int = 60,
    reference_date: Optional[Union[pd.Timestamp, str]] = None
) -> pd.DataFrame:
    """
    Calcula a velocidade de vendas (VMD), volatilidade da demanda diária (std_demand),
    volume faturado e receita por SKU na janela temporal recente (P-041).
    """
    if sales_df.empty:
        return pd.DataFrame(columns=["vmd", "std_demand", "total_sold_qty", "total_revenue"])

    df = sales_df.copy()

    # Normalização de nomes de colunas
    sku_col = "Cod Produto" if "Cod Produto" in df.columns else ("Código" if "Código" in df.columns else "Codigo")
    date_col = "Data"
    qty_col = "Qtd Venda" if "Qtd Venda" in df.columns else "Quantidade"
    val_col = "Valor Venda" if "Valor Venda" in df.columns else "Valor"

    df[sku_col] = pd.to_numeric(df[sku_col], errors="coerce").fillna(0).astype(np.int64)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[qty_col] = pd.to_numeric(df[qty_col], errors="coerce").fillna(0.0)
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce").fillna(0.0)

    # Filtrar registros válidos
    df = df[(df[sku_col] > 0) & (df[date_col].notna()) & (df[qty_col] > 0)].copy()
    if df.empty:
        return pd.DataFrame(columns=["vmd", "std_demand", "total_sold_qty", "total_revenue"])

    # Janela temporal
    if reference_date is None:
        ref_dt = df[date_col].max()
    else:
        ref_dt = pd.to_datetime(reference_date)

    start_dt = ref_dt - pd.Timedelta(days=window_days)
    recent_df = df[df[date_col] >= start_dt].copy()

    if recent_df.empty:
        return pd.DataFrame(columns=["vmd", "std_demand", "total_sold_qty", "total_revenue"])

    # Agregação por (SKU, Data) para capturar a quantidade diária vendida
    recent_df["Data_Dia"] = recent_df[date_col].dt.date
    daily_grouped = (
        recent_df.groupby([sku_col, "Data_Dia"])[qty_col]
        .sum()
        .reset_index()
    )

    # Agregação de receita total na janela
    sku_rev = recent_df.groupby(sku_col)[val_col].sum()
    sku_qty = recent_df.groupby(sku_col)[qty_col].sum()

    # Cálculo vetorizado e exato de VMD e Desvio Padrão sobre a janela completa de window_days
    # Para cada SKU: soma das quantidades, soma dos quadrados e dias com venda
    stats = daily_grouped.groupby(sku_col)[qty_col].agg(
        sum_qty="sum",
        sum_sq=lambda s: np.sum(s**2),
        days_with_sales="count"
    )

    n_days = max(1, window_days)
    vmd_series = stats["sum_qty"] / n_days

    # Variância amostral sobre a série com zeros para os dias sem venda:
    # Var = (sum(x_i^2) - N * mu^2) / (N - 1)
    if n_days > 1:
        variance = (stats["sum_sq"] - (n_days * (vmd_series ** 2))) / (n_days - 1)
        variance = variance.clip(lower=0.0)  # Evita imprecisão numérica negativa
        std_series = np.sqrt(variance)
    else:
        std_series = pd.Series(0.0, index=stats.index)

    result_df = pd.DataFrame({
        "vmd": vmd_series.round(4),
        "std_demand": std_series.round(4),
        "total_sold_qty": sku_qty.round(2),
        "total_revenue": sku_rev.round(2),
    }, index=stats.index)

    result_df.index.name = "sku"
    return result_df


def calculate_inventory_replenishment(
    products_df: pd.DataFrame,
    velocity_df: pd.DataFrame,
    lead_time_days: int = 15,
    target_coverage_days: int = 30,
    service_level: float = 0.95,
    supplier_filter: Optional[str] = None,
    budget_limit: Optional[float] = None
) -> Dict[str, Any]:
    """
    Executa o motor prescritivo de estoque ideal e recomendação de compras (P-042 a P-047).
    """
    df_prod = products_df.copy()

    # Normalização de colunas de produto
    col_sku = "Codigo" if "Codigo" in df_prod.columns else "Código"
    col_desc = "Descricao" if "Descricao" in df_prod.columns else "Descrição"
    col_fornec = "Fornecedor" if "Fornecedor" in df_prod.columns else ("Fornec/Marca" if "Fornec/Marca" in df_prod.columns else "Marca")
    col_tipo = "Tipo" if "Tipo" in df_prod.columns else "Linha"
    col_ean = "EAN" if "EAN" in df_prod.columns else "ean"
    col_est = "Estoque" if "Estoque" in df_prod.columns else "estoque"
    col_custo = "Pc.Ultimo Custo" if "Pc.Ultimo Custo" in df_prod.columns else "Custo"
    col_preco = "Pc.Venda" if "Pc.Venda" in df_prod.columns else "Preço"

    df_prod[col_sku] = pd.to_numeric(df_prod[col_sku], errors="coerce").fillna(0).astype(np.int64)
    df_prod[col_est] = pd.to_numeric(df_prod.get(col_est, 0.0), errors="coerce").fillna(0.0).clip(lower=0.0)
    df_prod[col_preco] = pd.to_numeric(df_prod.get(col_preco, 0.0), errors="coerce").fillna(0.0)

    # Custo com fallback seguro de 60%
    if col_custo in df_prod.columns:
        custo_num = pd.to_numeric(df_prod[col_custo], errors="coerce").fillna(0.0)
        df_prod["Custo_Calc"] = np.where(custo_num > 0, custo_num, np.round(df_prod[col_preco] * 0.60, 2))
    else:
        df_prod["Custo_Calc"] = np.round(df_prod[col_preco] * 0.60, 2)

    if col_fornec not in df_prod.columns:
        df_prod[col_fornec] = "OUTROS"
    df_prod[col_fornec] = df_prod[col_fornec].astype(str).str.strip().str.upper()

    if col_tipo not in df_prod.columns:
        df_prod[col_tipo] = "GERAL"
    df_prod[col_tipo] = df_prod[col_tipo].astype(str).str.strip()

    if col_desc not in df_prod.columns:
        df_prod[col_desc] = ""
    df_prod[col_desc] = df_prod[col_desc].astype(str).str.strip()

    if col_ean not in df_prod.columns:
        df_prod[col_ean] = ""
    df_prod[col_ean] = df_prod[col_ean].astype(str).str.strip()

    # Filtro opcional por Fornecedor (P-047.1)
    if supplier_filter and supplier_filter.strip().upper() not in ["TODOS", "ALL", ""]:
        sup_clean = supplier_filter.strip().upper()
        df_prod = df_prod[df_prod[col_fornec] == sup_clean].copy()

    # Z-Score para nível de serviço
    z_val = get_z_score(service_level)
    lt_sqrt = math.sqrt(max(1, lead_time_days))

    # Mapeamento de métricas de velocidade
    vmd_map = velocity_df["vmd"].to_dict() if not velocity_df.empty else {}
    std_map = velocity_df["std_demand"].to_dict() if not velocity_df.empty else {}
    rev_map = velocity_df["total_revenue"].to_dict() if not velocity_df.empty else {}

    # Curva ABC global de receita
    total_rev_all = sum(rev_map.values()) or 1.0
    sorted_rev = sorted(rev_map.items(), key=lambda x: x[1], reverse=True)
    cum_rev = 0.0
    abc_map = {}
    for sku, rev in sorted_rev:
        cum_rev += rev
        pct = (cum_rev / total_rev_all) * 100
        if pct <= 80.0:
            abc_map[sku] = "A"
        elif pct <= 95.0:
            abc_map[sku] = "B"
        else:
            abc_map[sku] = "C"

    items: List[Dict[str, Any]] = []
    capital_overstock = 0.0

    for _, row in df_prod.iterrows():
        sku = int(row[col_sku])
        desc = row[col_desc]
        ean = row[col_ean]
        fornec = row[col_fornec]
        tipo = row[col_tipo]
        estoque_atual = float(row[col_est])
        custo = float(row["Custo_Calc"])
        preco = float(row[col_preco])

        vmd = float(vmd_map.get(sku, 0.0))
        std_d = float(std_map.get(sku, 0.0))
        curva_abc = abc_map.get(sku, "C")

        # Dias de cobertura
        if vmd > 0:
            dias_cobertura = round(estoque_atual / vmd, 1)
        else:
            dias_cobertura = 999.0 if estoque_atual > 0 else 0.0

        # Estoque de Segurança e ROP
        if vmd > 0:
            estoque_seguranca = int(math.ceil(z_val * std_d * lt_sqrt))
            rop = int(math.ceil((vmd * lead_time_days) + estoque_seguranca))
            estoque_ideal = int(math.ceil((vmd * (lead_time_days + target_coverage_days)) + estoque_seguranca))
        else:
            estoque_seguranca = 0
            rop = 0
            estoque_ideal = 0

        # Quantidade Sugerida de Compra
        if vmd > 0 and (estoque_atual <= rop or dias_cobertura <= (lead_time_days + 5)):
            qtd_sugerida = max(0, int(math.ceil(estoque_ideal - estoque_atual)))
        else:
            qtd_sugerida = 0

        # Status Operacional (P-045)
        if vmd > 0 and dias_cobertura < lead_time_days:
            status = "CRITICAL_STOCKOUT"
            status_label = "Ruptura Iminente"
        elif estoque_atual <= rop and qtd_sugerida > 0:
            status = "REORDER_NEEDED"
            status_label = "Reposição Necessária"
        elif dias_cobertura > ((target_coverage_days + lead_time_days) * 1.5) or dias_cobertura > 75.0:
            status = "OVERSTOCK"
            status_label = "Excesso / Overstock"
            # Capital parado excedente
            excesso_un = max(0.0, estoque_atual - estoque_ideal)
            capital_overstock += excesso_un * custo
        else:
            status = "HEALTHY"
            status_label = "Estoque Saudável"

        investimento_item = round(qtd_sugerida * custo, 2)

        items.append({
            "codigo": sku,
            "descricao": desc,
            "ean": ean,
            "fornecedor": fornec,
            "tipo": tipo,
            "estoqueAtual": round(estoque_atual, 1),
            "vmd": round(vmd, 2),
            "desvioPadraoDemanda": round(std_d, 2),
            "diasCobertura": dias_cobertura,
            "leadTime": lead_time_days,
            "estoqueSeguranca": estoque_seguranca,
            "rop": rop,
            "estoqueIdeal": estoque_ideal,
            "qtdSugeridaCompra": qtd_sugerida,
            "custoUnitario": round(custo, 2),
            "precoVenda": round(preco, 2),
            "investimentoTotalItem": investimento_item,
            "status": status,
            "statusLabel": status_label,
            "curvaAbc": curva_abc,
        })

    # Otimização por Teto Orçamentário (P-046.3)
    investimento_total = sum(item["investimentoTotalItem"] for item in items)
    if budget_limit is not None and budget_limit > 0 and investimento_total > budget_limit:
        # Priorização: 1. Ruptura A, 2. Ruptura B/C, 3. Reposição A, 4. Reposição B/C
        def sort_priority(item):
            status_rank = 0 if item["status"] == "CRITICAL_STOCKOUT" else (1 if item["status"] == "REORDER_NEEDED" else 2)
            abc_rank = 0 if item["curvaAbc"] == "A" else (1 if item["curvaAbc"] == "B" else 2)
            # Maior VMD primeiro
            return (status_rank, abc_rank, -item["vmd"])

        items.sort(key=sort_priority)
        current_budget = 0.0
        for item in items:
            item_cost = item["investimentoTotalItem"]
            if current_budget + item_cost <= budget_limit:
                current_budget += item_cost
            else:
                # Corta ou reduz para o orçamento restante
                rem_budget = max(0.0, budget_limit - current_budget)
                if item["custoUnitario"] > 0:
                    max_units = int(rem_budget // item["custoUnitario"])
                    item["qtdSugeridaCompra"] = max_units
                    item["investimentoTotalItem"] = round(max_units * item["custoUnitario"], 2)
                    current_budget += item["investimentoTotalItem"]
                else:
                    item["qtdSugeridaCompra"] = 0
                    item["investimentoTotalItem"] = 0.0

    # Ordenação padrão: Ruptura Iminente primeiro, depois Reposição, depois por Curva ABC
    def final_sort(x):
        st_order = {"CRITICAL_STOCKOUT": 0, "REORDER_NEEDED": 1, "HEALTHY": 2, "OVERSTOCK": 3}
        return (st_order.get(x["status"], 4), 0 if x["curvaAbc"] == "A" else (1 if x["curvaAbc"] == "B" else 2), -x["vmd"])

    items.sort(key=final_sort)

    # Cálculo dos KPIs Agregados
    total_skus = len(items)
    ruptura_cnt = sum(1 for x in items if x["status"] == "CRITICAL_STOCKOUT")
    reposicao_cnt = sum(1 for x in items if x["status"] == "REORDER_NEEDED")
    saudavel_cnt = sum(1 for x in items if x["status"] == "HEALTHY")
    overstock_cnt = sum(1 for x in items if x["status"] == "OVERSTOCK")
    invest_final = sum(x["investimentoTotalItem"] for x in items)

    curva_a_items = sum(1 for x in items if x["curvaAbc"] == "A")
    curva_a_pct = round((curva_a_items / max(1, total_skus)) * 100, 1)

    kpis = {
        "totalSkusAnalisados": total_skus,
        "skusEmRupturaCritica": ruptura_cnt,
        "skusNecessitamReposicao": reposicao_cnt,
        "skusEstoqueSaudavel": saudavel_cnt,
        "skusEmOverstock": overstock_cnt,
        "investimentoTotalSugerido": round(invest_final, 2),
        "capitalImobilizadoOverstock": round(capital_overstock, 2),
        "curvaADistribuicao": {
            "qtdItens": curva_a_items,
            "percentualItens": curva_a_pct
        }
    }

    return {
        "kpis": kpis,
        "produtos": items
    }
