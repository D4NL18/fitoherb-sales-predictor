"""
Módulo de Extração, Transformação, Carga e Higienização de Dados (ETL).
Implementa regras P-001 a P-004 e conformidade LGPD de minimização de dados.
"""
import io
import logging
from pathlib import Path
from typing import Optional, Set, Union

import numpy as np
import pandas as pd

from src.config import DEFAULT_CONFIG, PipelineConfig

logger = logging.getLogger(__name__)


def normalize_products_dataframe(
    df: pd.DataFrame,
    default_cost_ratio: float = DEFAULT_CONFIG.default_cost_ratio
) -> pd.DataFrame:
    """
    Normaliza DataFrame de produtos vindo da view Externo01.Produto do SQL Server (P-022)
    ou de qualquer fonte tabular para o formato canônico exigido pelo pipeline.
    """
    df = df.copy()
    rename_map = {
        "Codigo": "Código",
        "Descricao": "Descrição",
        "Fornecedor": "Fornec/Marca",
        "Pc.Venda": "Preço",
    }
    df = df.rename(columns=rename_map)

    # Conversão rigorosa de tipos
    df["Código"] = pd.to_numeric(df["Código"], errors="coerce").fillna(0).astype(np.int64)
    df["Preço"] = pd.to_numeric(df["Preço"], errors="coerce").fillna(0.0).astype(np.float64)
    df = df[(df["Código"] > 0) & (df["Preço"] > 0)].copy()

    if "Descrição" in df.columns:
        df["Descrição"] = df["Descrição"].astype(str).str.strip()
    else:
        df["Descrição"] = ""

    if "Fornec/Marca" in df.columns:
        df["Fornec/Marca"] = df["Fornec/Marca"].astype(str).str.strip()
    elif "Fornecedor" in df.columns:
        df["Fornec/Marca"] = df["Fornecedor"].astype(str).str.strip()
    else:
        df["Fornec/Marca"] = ""

    # Custo: usa 'Pc.Ultimo Custo' real do banco se existir e for > 0; caso contrário, aplica default_cost_ratio
    if "Pc.Ultimo Custo" in df.columns:
        custo_real = pd.to_numeric(df["Pc.Ultimo Custo"], errors="coerce").fillna(0.0)
        df["Custo"] = np.where(custo_real > 0, custo_real, np.round(df["Preço"] * default_cost_ratio, 2))
    elif "Custo" in df.columns:
        custo_val = pd.to_numeric(df["Custo"], errors="coerce").fillna(0.0)
        df["Custo"] = np.where(custo_val > 0, custo_val, np.round(df["Preço"] * default_cost_ratio, 2))
    else:
        df["Custo"] = np.round(df["Preço"] * default_cost_ratio, 2)

    if "Sit" not in df.columns:
        df["Sit"] = "A"

    return df


def load_catalog_from_database(
    limit: Optional[int] = None,
    default_cost_ratio: float = DEFAULT_CONFIG.default_cost_ratio
) -> pd.DataFrame:
    """
    Carrega o catálogo oficial de produtos diretamente da View Externo01.Produto do SQL Server (P-022).
    Aplica normalização de colunas, validação de preço e custos reais.
    """
    from src.core.database import fetch_products_from_database
    raw_df = fetch_products_from_database(limit=limit)
    df_catalog = normalize_products_dataframe(raw_df, default_cost_ratio=default_cost_ratio)
    logger.info(f"Catálogo carregado do banco de dados SQL Server: {len(df_catalog)} SKUs ativos na whitelist.")
    return df_catalog


def load_catalog(
    source: Union[str, Path, io.StringIO, pd.DataFrame, None] = None,
    skiprows: int = 4,
    encoding: str = "latin1"
) -> pd.DataFrame:
    """
    Carrega o catálogo oficial de preços (P-001 / P-022).
    Se source for None, extrai diretamente da View Externo01.Produto do banco de dados SQL Server.
    Se source for DataFrame, aplica a normalização canônica.
    Se source for caminho ou StringIO, faz o parse de texto preservando compatibilidade.
    """
    if source is None:
        return load_catalog_from_database()

    if isinstance(source, pd.DataFrame):
        return normalize_products_dataframe(source)

    try:
        df = pd.read_csv(
            source,
            sep=";",
            skiprows=skiprows,
            encoding=encoding,
            dtype=str,
        )
    except UnicodeDecodeError:
        # Fallback de encoding caso necessário
        if hasattr(source, "seek"):
            source.seek(0)
        df = pd.read_csv(
            source,
            sep=";",
            skiprows=skiprows,
            encoding="cp1252",
            dtype=str,
        )

    # Remover colunas em branco provenientes de delimitador no final da linha
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed")]

    # Normalizar nomes de colunas
    col_mapping = {}
    for col in df.columns:
        norm = col.strip()
        if "C" in norm and "digo" in norm:
            col_mapping[col] = "Código"
        elif "Descri" in norm:
            col_mapping[col] = "Descrição"
        elif "Fornec" in norm:
            col_mapping[col] = "Fornec/Marca"
        elif "Pre" in norm:
            col_mapping[col] = "Preço"
        elif "Sit" in norm:
            col_mapping[col] = "Sit"
        elif "Und" in norm:
            col_mapping[col] = "Und"
        elif "Tipo" in norm:
            col_mapping[col] = "Tipo"
        else:
            col_mapping[col] = norm
    df = df.rename(columns=col_mapping)

    # Filtrar linhas de rodapé ou metadados finais que não contêm código numérico
    df = df.dropna(subset=["Código"])
    df = df[df["Código"].str.strip().str.isdigit()]

    # Conversão rigorosa de tipos
    df["Código"] = df["Código"].astype(np.int64)

    # Sanitização de Preço (padrão brasileiro com vírgula para float64)
    df["Preço"] = (
        df["Preço"]
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .astype(np.float64)
    )

    if "Fornec/Marca" in df.columns:
        df["Fornec/Marca"] = df["Fornec/Marca"].astype(str).str.strip()
    if "Sit" in df.columns:
        df["Sit"] = df["Sit"].astype(str).str.strip()
    if "Descrição" in df.columns:
        df["Descrição"] = df["Descrição"].astype(str).str.strip()

    # Adicionar custo estimado (60% do preço de tabela como baseline de margem de 40%)
    df["Custo"] = np.round(df["Preço"] * DEFAULT_CONFIG.default_cost_ratio, 2)

    logger.info(f"Catálogo carregado com sucesso: {len(df)} SKUs ativos na whitelist.")
    return df



def filter_whitelist(sales_df: pd.DataFrame, valid_skus: Set[int]) -> pd.DataFrame:
    """
    Expurga sumariamente qualquer venda de produto fora do catálogo oficial (P-001).
    """
    initial_count = len(sales_df)
    filtered = sales_df[sales_df["Cod Produto"].isin(valid_skus)].copy()
    dropped = initial_count - len(filtered)
    if dropped > 0:
        logger.info(f"Whitelist Estrita: {dropped} registros de SKUs fora do catálogo foram expurgados.")
    return filtered


def clean_sales_data(
    sales_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    min_price_ratio: float = 0.40
) -> pd.DataFrame:
    """
    Executa o funil de sanitização de vendas (P-001, P-002 e P-003):
    1. Operação == 'VENDA'
    2. Qtd Venda > 0 e Valor Venda > 0
    3. Whitelist do catálogo oficial
    4. Remoção de amostras/brindes onde Preço Praticado < min_price_ratio * Preço Tabela.
    """
    df = sales_df.copy()

    # Garantir tipagem básica (suporta tanto tipos numéricos nativos do banco quanto strings formatadas do CSV)
    if df["Qtd Venda"].dtype == object:
        df["Qtd Venda"] = df["Qtd Venda"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    if df["Valor Venda"].dtype == object:
        df["Valor Venda"] = df["Valor Venda"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)

    df["Cod Produto"] = pd.to_numeric(df["Cod Produto"], errors="coerce").fillna(0).astype(np.int64)
    df["Qtd Venda"] = pd.to_numeric(df["Qtd Venda"], errors="coerce").fillna(0.0)
    df["Valor Venda"] = pd.to_numeric(df["Valor Venda"], errors="coerce").fillna(0.0)

    # 1. Filtro estrito de operação (P-002)
    if "Operação" in df.columns:
        df = df[df["Operação"].astype(str).str.strip().str.upper() == "VENDA"]

    # 2. Integridade de valores positivos (P-002)
    df = df[(df["Qtd Venda"] > 0) & (df["Valor Venda"] > 0)]

    # 3. Whitelist de catálogo (P-001)
    valid_skus = set(catalog_df["Código"].unique())
    df = filter_whitelist(df, valid_skus)

    # 4. Eliminação de vendas simbólicas e brindes faturados a R$ 0,01 (P-003)
    catalog_price_map = catalog_df.set_index("Código")["Preço"].to_dict()
    df["Preco Tabela"] = df["Cod Produto"].map(catalog_price_map)

    df["Preco Praticado"] = df["Valor Venda"] / df["Qtd Venda"]
    min_threshold = df["Preco Tabela"] * min_price_ratio
    
    valid_prices_mask = df["Preco Praticado"] >= min_threshold
    dropped_gifts = (~valid_prices_mask).sum()
    if dropped_gifts > 0:
        logger.info(f"Expurgo de Brindes/Amostras (P-003): {dropped_gifts} linhas descartadas por preço < 40% da tabela.")

    df = df[valid_prices_mask].copy()
    return df


def deduplicate_orders(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deduplica ocorrências do mesmo SKU no mesmo pedido somando quantidades e valores (P-004).
    """
    group_cols = ["Pedido", "Cod Produto"]
    
    agg_rules = {
        "Qtd Venda": "sum",
        "Valor Venda": "sum",
    }
    
    # Preservar colunas contextuais caso existam
    optional_cols = ["Data", "Cod Cliente", "UF", "Cod Promocao", "Promoção", "Preco Tabela"]
    for col in optional_cols:
        if col in sales_df.columns:
            agg_rules[col] = "first"

    dedup = sales_df.groupby(group_cols, as_index=False).agg(agg_rules)
    dedup["Preco Praticado"] = dedup["Valor Venda"] / dedup["Qtd Venda"]
    return dedup


def remove_outliers(sales_df: pd.DataFrame, percentile: float = 99.5) -> pd.DataFrame:
    """
    Descarta compras atípicas/licitações institucionais acima do percentil indicado de quantidade (P-004).
    """
    order_quantities = sales_df.groupby("Pedido")["Qtd Venda"].sum()
    cutoff_value = np.percentile(order_quantities, percentile)
    
    valid_orders = order_quantities[order_quantities <= cutoff_value].index
    filtered = sales_df[sales_df["Pedido"].isin(valid_orders)].copy()
    
    outliers_count = len(order_quantities) - len(valid_orders)
    if outliers_count > 0:
        logger.info(f"Remoção de Outliers (P-004): {outliers_count} pedidos com volume > p{percentile} ({cutoff_value:.1f} un) descartados.")
    return filtered


def run_etl_pipeline(
    sales_df: pd.DataFrame,
    catalog_df: pd.DataFrame,
    config: PipelineConfig = DEFAULT_CONFIG
) -> pd.DataFrame:
    """
    Executa o pipeline completo de ETL e projeta memória expurgando PII (LGPD).
    """
    df_clean = clean_sales_data(sales_df, catalog_df, min_price_ratio=config.min_price_ratio)
    df_dedup = deduplicate_orders(df_clean)
    df_no_outliers = remove_outliers(df_dedup, percentile=config.outlier_percentile)

    # Conversão de Data para Datetime
    if "Data" in df_no_outliers.columns:
        df_no_outliers["Data"] = pd.to_datetime(df_no_outliers["Data"], errors="coerce")

    # Adicionar Custo
    cost_map = catalog_df.set_index("Código")["Custo"].to_dict()
    df_no_outliers["Custo Unitario"] = df_no_outliers["Cod Produto"].map(cost_map)

    # Projeção de colunas com eliminação mandatória de dados pessoais (LGPD)
    retained_cols = [
        col for col in [
            "Pedido", "Data", "Cod Produto", "Valor Venda", "Qtd Venda",
            "Cod Promocao", "Cod Cliente", "UF", "Preco Tabela", "Preco Praticado", "Custo Unitario"
        ] if col in df_no_outliers.columns
    ]

    df_final = df_no_outliers[retained_cols].copy()
    logger.info(f"ETL concluído com sucesso: {len(df_final)} registros analíticos preparados.")
    return df_final
