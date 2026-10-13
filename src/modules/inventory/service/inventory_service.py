"""
Serviço de Negócio para o Módulo de Estoque e Compras (Inventory & Replenishment AI).
Orquestra cache de velocidade de vendas, execução prescritiva e exportação CSV.
Fitoherb Nordeste Distribuidora.
"""
import io
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.core.database import fetch_products_from_database, fetch_sales_from_database
from src.etl import load_catalog_from_database, run_etl_pipeline
from src.modules.inventory.api.schemas import InventoryPredictRequest
from src.modules.inventory.domain.inventory_engine import (
    calculate_inventory_replenishment,
    calculate_sales_velocity,
)

logger = logging.getLogger(__name__)

# Cache de velocidade de vendas e catálogo para alta performance
_INVENTORY_CACHE: Dict[str, Any] = {}
_VELOCITY_CACHE: Dict[int, pd.DataFrame] = {}


def get_base_inventory_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Recupera o catálogo oficial de produtos e as vendas limpas.
    Tenta primeiro reutilizar o cache unificado do sistema; caso indisponível, extrai do banco.
    """
    if "catalog_df" in _INVENTORY_CACHE and "clean_sales" in _INVENTORY_CACHE:
        return _INVENTORY_CACHE["catalog_df"], _INVENTORY_CACHE["clean_sales"]

    # Tentativa de reuso transparente do cache do pipeline principal
    try:
        from src.modules.pricing.service.pricing_service import _DATA_CACHE
        if "catalog_df" in _DATA_CACHE and "clean_sales" in _DATA_CACHE:
            _INVENTORY_CACHE["catalog_df"] = _DATA_CACHE["catalog_df"]
            _INVENTORY_CACHE["clean_sales"] = _DATA_CACHE["clean_sales"]
            return _INVENTORY_CACHE["catalog_df"], _INVENTORY_CACHE["clean_sales"]
    except Exception:
        pass

    logger.info("Carregando catálogo e vendas do banco SQL Server para o módulo de inventário...")
    catalog_df = load_catalog_from_database()
    raw_sales = fetch_sales_from_database()
    clean_sales = run_etl_pipeline(raw_sales, catalog_df)

    _INVENTORY_CACHE["catalog_df"] = catalog_df
    _INVENTORY_CACHE["clean_sales"] = clean_sales
    return catalog_df, clean_sales


def get_cached_velocity(window_days: int) -> pd.DataFrame:
    """
    Retorna a velocidade de vendas para a janela especificada, usando cache em memória.
    """
    if window_days in _VELOCITY_CACHE:
        return _VELOCITY_CACHE[window_days]

    _, clean_sales = get_base_inventory_data()
    logger.info(f"Calculando velocidade de vendas (VMD) para janela de {window_days} dias...")
    vel_df = calculate_sales_velocity(clean_sales, window_days=window_days)
    _VELOCITY_CACHE[window_days] = vel_df
    return vel_df


def get_inventory_suppliers() -> List[Dict[str, Any]]:
    """
    Retorna a lista de fornecedores com a contagem de SKUs ativos.
    """
    catalog_df, _ = get_base_inventory_data()
    fornec_col = "Fornec/Marca" if "Fornec/Marca" in catalog_df.columns else "Fornecedor"
    
    counts = catalog_df[fornec_col].value_counts()
    suppliers = [
        {"fornecedor": "TODOS", "nome": "Todos os Fornecedores", "totalSkus": int(len(catalog_df))}
    ]
    for sup, count in counts.items():
        if pd.isna(sup) or not str(sup).strip():
            continue
        s_name = str(sup).strip()
        suppliers.append({
            "fornecedor": s_name.upper(),
            "nome": s_name.title(),
            "totalSkus": int(count)
        })
    return suppliers


def execute_inventory_prediction(request: InventoryPredictRequest) -> Tuple[Dict[str, Any], float]:
    """
    Executa o cálculo analítico de reposição e estoque ideal.
    Retorna (resultado_dict, tempo_execucao_ms).
    """
    t0 = time.time()
    catalog_df, _ = get_base_inventory_data()
    velocity_df = get_cached_velocity(request.historyWindowDays)

    result = calculate_inventory_replenishment(
        products_df=catalog_df,
        velocity_df=velocity_df,
        lead_time_days=request.leadTimeDays,
        target_coverage_days=request.targetCoverageDays,
        service_level=request.serviceLevel,
        supplier_filter=request.fornecedor,
        budget_limit=request.budgetLimit
    )
    elapsed_ms = round((time.time() - t0) * 1000, 2)
    return result, elapsed_ms


def generate_inventory_csv(request: InventoryPredictRequest) -> str:
    """
    Gera o conteúdo em formato CSV com o plano de compras sugerido.
    """
    result, _ = execute_inventory_prediction(request)
    produtos = result["produtos"]

    output = io.StringIO()
    # Adicionar BOM UTF-8 para compatibilidade perfeita com Excel brasileiro
    output.write("\ufeff")
    writer = io.StringIO()

    df_export = pd.DataFrame(produtos)
    rename_cols = {
        "codigo": "Código",
        "descricao": "Descrição",
        "ean": "EAN",
        "fornecedor": "Fornecedor",
        "tipo": "Tipo/Linha",
        "estoqueAtual": "Estoque Físico Atual",
        "vmd": "Venda Média Diária (VMD)",
        "diasCobertura": "Dias de Cobertura",
        "leadTime": "Lead Time (Dias)",
        "estoqueSeguranca": "Estoque de Segurança",
        "rop": "Ponto de Reposição (ROP)",
        "estoqueIdeal": "Estoque Ideal",
        "qtdSugeridaCompra": "Qtd Sugerida de Compra",
        "custoUnitario": "Último Custo Real (R$)",
        "precoVenda": "Preço de Venda (R$)",
        "investimentoTotalItem": "Investimento Total Sugerido (R$)",
        "statusLabel": "Status Operacional",
        "curvaAbc": "Curva ABC",
    }
    cols_to_keep = [c for c in rename_cols.keys() if c in df_export.columns]
    df_export = df_export[cols_to_keep].rename(columns=rename_cols)

    df_export.to_csv(output, sep=";", index=False, decimal=",")
    return output.getvalue()
