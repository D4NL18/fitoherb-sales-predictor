"""
Repositório somente leitura do módulo Analytics Comercial — única camada com SQL (ADR-002 DA-02).

- `fetch_order_baskets(cutoff)`: agregado `order_baskets` no grão Pedido x SKU, só VENDA, com
  `HAVING SUM([Qtd Venda]) > 0`, pedido como `DENSE_RANK` e data como `DATEDIFF` (tudo `int32`),
  lido em blocos com `fetchmany` (P-058.2, P-058.4, LGPD-01). A data de corte é exclusiva e vai como
  parâmetro vinculado, nunca interpolada (LGPD-02).
- `fetch_catalog()`: catálogo ativo com a projeção mínima de LGPD-01.

Toda SQL passa por `is_readonly_query` antes de executar. Falhas de driver, conexão ou configuração
viram `AnalyticsDataSourceError` (`ANL-001`); o log registra só o tipo da exceção, nunca a mensagem
do driver (LGPD-05). `RETURN_OPERATION_PATTERN` existe por P-058.5, mas devolução nunca entra no SQL.
"""
from __future__ import annotations

import logging
import math
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Iterator, List, Sequence

import numpy as np
import pandas as pd
import pyodbc

from src.core.database import (
    ACTIVE_CATALOG_FILTER_SQL,
    DatabaseSecurityError,
    get_db_connection_string,
    is_readonly_query,
)
from src.modules.analytics.domain.cross_sell import ORDER_DAY_EPOCH, SALE_OPERATION
from src.modules.analytics.repository.errors import AnalyticsDataSourceError

logger = logging.getLogger(__name__)

RETURN_OPERATION_PATTERN = "DEVOLU%"  # P-058.5: padrão das devoluções (o acento de [Operação] chega corrompido)
FETCH_CHUNK_SIZE = 50_000             # DA-02: linhas por bloco do cursor (~10 MB transitórios)
CONNECTION_TIMEOUT_SECONDS = 30       # mesmo timeout do core database

ORDER_BASKET_COLUMNS = ["order_idx", "sku", "customer_code", "order_day"]
CATALOG_COLUMNS = ["Codigo", "Descricao", "Fornecedor", "Estoque", "Pc.Ultimo Custo", "Pc.Venda"]

# Erros traduzidos em ANL-001: driver, rede e variáveis de ambiente ausentes (ValueError do core).
_DATA_SOURCE_ERRORS = (pyodbc.Error, ConnectionError, ValueError)

# Só constantes do módulo são interpoladas no texto (operação de venda e época do `order_day`);
# o único valor externo, a data de corte, vai como parâmetro `?`.
_ORDER_BASKETS_SQL = f"""
SELECT
    DENSE_RANK() OVER (ORDER BY b.[Pedido]) AS order_idx,
    b.[Cod Produto]                          AS sku,
    b.customer_code,
    b.order_day
FROM (
    SELECT
        [Pedido],
        [Cod Produto],
        MIN([Cod Cliente])                     AS customer_code,
        DATEDIFF(day, '{ORDER_DAY_EPOCH:%Y%m%d}', MIN([Data])) AS order_day
    FROM Externo01.Vendas
    WHERE [Operação] = '{SALE_OPERATION}'
      AND [Data] < ?
    GROUP BY [Pedido], [Cod Produto]
    HAVING SUM([Qtd Venda]) > 0
) AS b
""".strip()

_CATALOG_SQL = f"""
SELECT p.[Codigo], p.[Descricao], p.[Fornecedor], p.[Estoque], p.[Pc.Ultimo Custo], p.[Pc.Venda]
{ACTIVE_CATALOG_FILTER_SQL}
""".strip()


@contextmanager
def _execute_readonly(sql: str, params: Sequence[object] = ()) -> Iterator[pyodbc.Cursor]:
    """
    Valida a SQL, abre a conexão, executa com parâmetros vinculados e entrega o cursor.

    A conexão é sempre fechada. Erros de driver/conexão/configuração (inclusive durante a leitura
    feita pelo chamador) viram `AnalyticsDataSourceError` sem a mensagem original.

    Raises:
        DatabaseSecurityError: SQL que não é estritamente de leitura (nem chega a conectar).
        AnalyticsDataSourceError: `ANL-001`.
    """
    if not is_readonly_query(sql):
        raise DatabaseSecurityError("Consulta do módulo analytics rejeitada pelo validador de somente leitura.")
    connection = None
    try:
        connection = pyodbc.connect(get_db_connection_string(), timeout=CONNECTION_TIMEOUT_SECONDS)
        cursor = connection.cursor()
        cursor.execute(sql, *params)
        yield cursor
    except _DATA_SOURCE_ERRORS as exc:
        logger.error("Falha ao ler a base de vendas do analytics: %s", type(exc).__name__)
        raise AnalyticsDataSourceError() from None
    finally:
        if connection is not None:
            connection.close()


def _read_int32_chunks(cursor: pyodbc.Cursor) -> np.ndarray:
    """Lê o cursor em blocos de `FETCH_CHUNK_SIZE`, convertendo cada bloco para `int32` (nunca `fetchall`)."""
    blocks: List[np.ndarray] = []
    while True:
        rows = cursor.fetchmany(FETCH_CHUNK_SIZE)
        if not rows:
            break
        blocks.append(np.array([tuple(row) for row in rows], dtype=np.int32))
    if not blocks:
        return np.empty((0, len(ORDER_BASKET_COLUMNS)), dtype=np.int32)
    return np.concatenate(blocks)


def fetch_order_baskets(cutoff: date) -> pd.DataFrame:
    """
    Agregado `order_baskets` com pedidos de VENDA anteriores a `cutoff` (exclusivo).

    Args:
        cutoff: produção = data de referência + 1 dia; backtest = 1º dia após o último mês avaliado.

    Returns:
        DataFrame `order_idx, sku, customer_code, order_day`, todas `int32`.

    Regra: P-058, P-058.4; ADR-002 DA-02; LGPD-01, LGPD-02.
    """
    with _execute_readonly(_ORDER_BASKETS_SQL, (cutoff,)) as cursor:
        values = _read_int32_chunks(cursor)
    return pd.DataFrame(values, columns=ORDER_BASKET_COLUMNS).astype(np.int32)


def fetch_catalog() -> pd.DataFrame:
    """
    Catálogo ativo (`Pc.Venda > 0`) com `Codigo, Descricao, Fornecedor, Estoque, Pc.Ultimo Custo, Pc.Venda`.
    ~2 mil linhas, por isso lido de uma vez. Regra: P-061.3, P-063; LGPD-01.
    """
    with _execute_readonly(_CATALOG_SQL) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS)


# ---------------------------------------------------------------------------
# F3: Churn de Clientes (P-117 a P-127; ADR-006 DA-02)
# ---------------------------------------------------------------------------

_CUSTOMER_ORDERS_SQL = f"""
SELECT
    [Cod Cliente] AS customer_code,
    CAST([Data] AS date) AS order_date
FROM Externo01.Vendas
WHERE [Operação] = '{SALE_OPERATION}'
  AND [Data] < ?
GROUP BY [Cod Cliente], CAST([Data] AS date)
ORDER BY [Cod Cliente], order_date
""".strip()

_CUSTOMER_MONTHLY_REVENUE_SQL = f"""
SELECT
    [Cod Cliente] AS customer_code,
    YEAR([Data])  AS [year],
    MONTH([Data]) AS [month],
    SUM([Valor Venda]) AS net_revenue,
    COUNT(DISTINCT [Pedido]) AS order_count
FROM Externo01.Vendas
WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
  AND [Data] < ?
GROUP BY [Cod Cliente], YEAR([Data]), MONTH([Data])
""".strip()

_CUSTOMER_TOP_PRODUCTS_SQL = f"""
SELECT
    [Cod Cliente] AS customer_code,
    [Cod Produto] AS sku,
    MAX(CAST([Data] AS date)) AS last_date,
    SUM([Valor Venda]) AS revenue
FROM Externo01.Vendas
WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
  AND [Data] < ?
GROUP BY [Cod Cliente], [Cod Produto]
HAVING SUM([Valor Venda]) > 0
""".strip()


def fetch_customer_orders(cutoff: date) -> pd.DataFrame:
    """
    Agregado customer_orders: datas de pedidos de VENDA por cliente (P-117, P-118).
    """
    with _execute_readonly(_CUSTOMER_ORDERS_SQL, (cutoff,)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["customer_code", "order_date"])


def fetch_customer_monthly_revenue(cutoff: date) -> pd.DataFrame:
    """
    Agregado customer_monthly_revenue: faturamento líquido de devoluções agrupado por mês (P-121).
    """
    with _execute_readonly(_CUSTOMER_MONTHLY_REVENUE_SQL, (cutoff,)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["customer_code", "year", "month", "net_revenue", "order_count"])


_CUSTOMER_METADATA_SQL = f"""
SELECT customer_code, customer_name, seller_name, city, uf
FROM (
    SELECT
        [Cod Cliente] AS customer_code,
        [Cliente] AS customer_name,
        [Vendedor] AS seller_name,
        [Cidade] AS city,
        [UF] AS uf,
        ROW_NUMBER() OVER (PARTITION BY [Cod Cliente] ORDER BY [Data] DESC, [Pedido] DESC) AS rn
    FROM Externo01.Vendas
    WHERE [Operação] = '{SALE_OPERATION}'
      AND [Data] < ?
) AS LatestOrder
WHERE rn = 1
""".strip()


def fetch_customer_metadata(cutoff: date) -> pd.DataFrame:
    """
    Nome do cliente, vendedor e cidade/UF do pedido mais recente de VENDA por cliente.
    """
    with _execute_readonly(_CUSTOMER_METADATA_SQL, (cutoff,)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["customer_code", "customer_name", "seller_name", "city", "uf"])


def fetch_customer_top_products(cutoff: date) -> pd.DataFrame:
    """
    Agregado de produtos comprados por cliente para identificação de produtos perdidos (P-126.3).
    """
    with _execute_readonly(_CUSTOMER_TOP_PRODUCTS_SQL, (cutoff,)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["customer_code", "sku", "last_date", "revenue"])


MONTHLY_SALES_COLUMNS = ["sku", "sale_year", "sale_month", "net_quantity", "net_revenue"]

_MONTHLY_SALES_SQL = f"""
SELECT
    [Cod Produto]                                     AS sku,
    YEAR([Data])                                      AS sale_year,
    MONTH([Data])                                     AS sale_month,
    SUM([Qtd Venda])                                  AS net_quantity,
    SUM([Valor Venda])                                AS net_revenue
FROM Externo01.Vendas
WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
  AND [Data] < ?
GROUP BY [Cod Produto], YEAR([Data]), MONTH([Data])
""".strip()


def fetch_monthly_sales(cutoff: date) -> pd.DataFrame:
    """
    Agregado mensal líquido de vendas e devoluções por SKU (P-106; ADR-005 DA-02).

    Retorna DataFrame com colunas `sku, sale_year, sale_month, net_quantity, net_revenue`.
    """
    with _execute_readonly(_MONTHLY_SALES_SQL, (cutoff,)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    if not rows:
        return pd.DataFrame(columns=MONTHLY_SALES_COLUMNS)
    df = pd.DataFrame(rows, columns=MONTHLY_SALES_COLUMNS)
    df["sku"] = df["sku"].astype(np.int32)
    df["sale_year"] = df["sale_year"].astype(np.int32)
    df["sale_month"] = df["sale_month"].astype(np.int32)
    df["net_quantity"] = df["net_quantity"].astype(np.int64)
    df["net_revenue"] = df["net_revenue"].astype(float)
    return df


# ------------------------------------------------------------------ Elasticidade (F5 / P-095, P-097; ADR-004 DA-02)

_PRODUCT_PRICE_POINTS_SQL = f"""
SELECT
    YEAR([Data]) AS ano,
    MONTH([Data]) AS mes,
    [Operação] AS operacao,
    SUM([Qtd Venda]) AS qtd,
    SUM([Valor Venda]) AS valor
FROM Externo01.Vendas
WHERE [Cod Produto] = ?
  AND [Data] < ?
  AND ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
GROUP BY YEAR([Data]), MONTH([Data]), [Operação]
""".strip()

_PRODUCT_CUSTOMERS_SQL = f"""
SELECT
    [Cod Cliente] AS customer_code,
    COUNT(DISTINCT [Pedido]) AS orders_count,
    SUM([Qtd Venda]) AS total_units,
    SUM([Valor Venda]) AS total_revenue
FROM Externo01.Vendas
WHERE [Cod Produto] = ?
  AND [Data] < ?
  AND ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
GROUP BY [Cod Cliente]
HAVING SUM([Qtd Venda]) > 0
ORDER BY total_units DESC
""".strip()

_SINGLE_CUSTOMER_POINTS_SQL = f"""
SELECT
    YEAR([Data]) AS ano,
    MONTH([Data]) AS mes,
    [Operação] AS operacao,
    SUM([Qtd Venda]) AS qtd,
    SUM([Valor Venda]) AS valor
FROM Externo01.Vendas
WHERE [Cod Produto] = ?
  AND [Cod Cliente] = ?
  AND [Data] < ?
  AND ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
GROUP BY YEAR([Data]), MONTH([Data]), [Operação]
""".strip()

_PRODUCT_RECENT_VOLUME_SQL = f"""
SELECT SUM([Qtd Venda]) AS net_volume
FROM Externo01.Vendas
WHERE [Cod Produto] = ?
  AND [Data] >= ?
  AND [Data] < ?
  AND ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
""".strip()


def fetch_product_price_points(sku: int, cutoff: date) -> pd.DataFrame:
    """
    Agregado mensal de vendas e devoluções para estimação de elasticidade de produto (P-095).
    """
    with _execute_readonly(_PRODUCT_PRICE_POINTS_SQL, (sku, cutoff)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["ano", "mes", "operacao", "qtd", "valor"])


def fetch_product_customers(sku: int, cutoff: date) -> pd.DataFrame:
    """
    Agregado de clientes que compraram o produto com pedidos e unidades líquidas (P-097).
    """
    with _execute_readonly(_PRODUCT_CUSTOMERS_SQL, (sku, cutoff)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["customer_code", "orders_count", "total_units", "total_revenue"])


def fetch_single_customer_points(sku: int, customer_code: int, cutoff: date) -> pd.DataFrame:
    """
    Agregado mensal para o par produto x cliente específico (P-097).
    """
    with _execute_readonly(_SINGLE_CUSTOMER_POINTS_SQL, (sku, customer_code, cutoff)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    return pd.DataFrame(rows, columns=["ano", "mes", "operacao", "qtd", "valor"])


def fetch_product_recent_volume_60d(sku: int, cutoff: date, window_days: int = 60) -> float:
    """
    Volume líquido de vendas (VENDA - DEVOLU%) do produto nos últimos `window_days` dias até `cutoff` (P-101).
    """
    start_date = cutoff - timedelta(days=max(1, int(window_days)))
    with _execute_readonly(_PRODUCT_RECENT_VOLUME_SQL, (sku, start_date, cutoff)) as cursor:
        rows = cursor.fetchall()
    if not rows or rows[0][0] is None:
        return 0.0
    net_volume = float(rows[0][0])
    if math.isnan(net_volume):
        return 0.0
    return max(0.0, net_volume)


# ------------------------------------------------------------------ Canibalização e Substituição (F6 / P-128..P-137)

_CANNIBALIZATION_CATALOG_SQL = f"""
SELECT
    p.[Codigo],
    p.[Descricao],
    p.[Tipo],
    p.[Fornecedor],
    p.[Estoque],
    p.[Pc.Ultimo Custo],
    p.[Pc.Venda]
{ACTIVE_CATALOG_FILTER_SQL}
""".strip()

_BUYERS_BY_SKU_SQL = f"""
SELECT DISTINCT
    [Cod Produto] AS sku,
    [Cod Cliente] AS customer_code
FROM Externo01.Vendas
WHERE [Operação] = '{SALE_OPERATION}'
  AND [Data] >= ?
  AND [Data] < ?
""".strip()

_PROMO_CALENDAR_SQL = f"""
SELECT
    [Cod Produto] AS sku,
    [Cod Promocao] AS cod_promocao,
    MIN(CAST([Data] AS DATE)) AS start_date
FROM Externo01.Vendas
WHERE [Cod Produto] = ?
  AND [Data] < ?
  AND [Operação] = '{SALE_OPERATION}'
  AND [Cod Promocao] IS NOT NULL
  AND LTRIM(RTRIM(CAST([Cod Promocao] AS VARCHAR(50)))) NOT IN ('', '0')
GROUP BY [Cod Produto], [Cod Promocao]
""".strip()

_PROMO_SKUS_WINDOW_SQL = f"""
SELECT DISTINCT [Cod Produto] AS sku
FROM Externo01.Vendas
WHERE [Data] >= ?
  AND [Data] <= ?
  AND [Operação] = '{SALE_OPERATION}'
  AND [Cod Promocao] IS NOT NULL
  AND LTRIM(RTRIM(CAST([Cod Promocao] AS VARCHAR(50)))) NOT IN ('', '0')
""".strip()


def fetch_cannibalization_catalog() -> dict:
    """Catálogo ativo com `Tipo` e `Fornecedor` para canibalização e grupo de controle (P-128.1, P-131)."""
    with _execute_readonly(_CANNIBALIZATION_CATALOG_SQL) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    catalog = {}
    for row in rows:
        sku_str = str(int(row[0]))
        catalog[sku_str] = {
            "sku": sku_str,
            "description": str(row[1] or "").strip(),
            "category": str(row[2] or "").strip(),
            "supplier": str(row[3] or "").strip(),
            "active": True,
            "current_stock": int(float(row[4] or 0)),
            "last_cost": float(row[5]) if row[5] is not None else None,
            "current_price": float(row[6] or 0.0),
        }
    return catalog


def fetch_buyers_by_sku(cutoff: date, lookback_days: int = 365) -> dict:
    """
    Mapa volátil {sku: set(customer_code)} dos últimos 365 dias (LGPD-CAN-01 / LGPD-CAN-04).
    Seleciona estritamente [Cod Produto] e [Cod Cliente].
    """
    start_date = cutoff - timedelta(days=lookback_days)
    buyers_map: dict = {}
    with _execute_readonly(_BUYERS_BY_SKU_SQL, (start_date, cutoff)) as cursor:
        while True:
            rows = cursor.fetchmany(FETCH_CHUNK_SIZE)
            if not rows:
                break
            for sku_val, cust_val in rows:
                if sku_val is None or cust_val is None:
                    continue
                sku_str = str(int(sku_val))
                buyers_map.setdefault(sku_str, set()).add(int(cust_val))
    return buyers_map


def fetch_daily_sales_for_skus(
    skus: Sequence[int],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Agregado diário de vendas e devoluções para uma lista de SKUs (P-137.2)."""
    if not skus:
        return pd.DataFrame(columns=["sku", "date", "operation", "qty", "revenue"])
    placeholders = ", ".join("?" for _ in skus)
    sql = f"""
SELECT
    [Cod Produto] AS sku,
    CAST([Data] AS DATE) AS sale_date,
    [Operação] AS operation,
    SUM([Qtd Venda]) AS qty,
    SUM([Valor Venda]) AS revenue
FROM Externo01.Vendas
WHERE [Cod Produto] IN ({placeholders})
  AND [Data] >= ?
  AND [Data] <= ?
  AND ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
GROUP BY [Cod Produto], CAST([Data] AS DATE), [Operação]
""".strip()
    params = [*[int(s) for s in skus], start_date, end_date]
    with _execute_readonly(sql, params) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    if not rows:
        return pd.DataFrame(columns=["sku", "date", "operation", "qty", "revenue"])
    df = pd.DataFrame(rows, columns=["sku", "date", "operation", "qty", "revenue"])
    df["sku"] = df["sku"].astype(int).astype(str)
    return df


def fetch_promo_calendar(sku: int, cutoff: date) -> pd.DataFrame:
    """Datas de início de campanhas promocionais do SKU (P-129.1)."""
    with _execute_readonly(_PROMO_CALENDAR_SQL, (int(sku), cutoff)) as cursor:
        rows = [tuple(row) for row in cursor.fetchall()]
    if not rows:
        return pd.DataFrame(columns=["sku", "cod_promocao", "start_date"])
    df = pd.DataFrame(rows, columns=["sku", "cod_promocao", "start_date"])
    df["sku"] = df["sku"].astype(int).astype(str)
    return df


def fetch_promo_skus_in_window(start_date: date, end_date: date) -> set:
    """Retorna conjunto de SKUs que tiveram promoção no intervalo (P-131.1)."""
    with _execute_readonly(_PROMO_SKUS_WINDOW_SQL, (start_date, end_date)) as cursor:
        rows = cursor.fetchall()
    return {str(int(row[0])) for row in rows if row[0] is not None}


# ------------------------------------------------------------------ Canibalização v2 — Migração de Clientes (P-128, P-137; ADR-007 DA-03)

_CUSTOMER_SKU_WINDOW_SALES_SQL = f"""
SELECT
    base.customer_code,
    base.sku,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_qty ELSE 0 END) AS pre_qty,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) AS pre_rev,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_qty ELSE 0 END) AS cur_qty,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) AS cur_rev
FROM (
    SELECT
        [Cod Cliente] AS customer_code,
        [Cod Produto] AS sku,
        CASE WHEN [Data] >= ? THEN 1 ELSE 0 END AS period_flag,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Qtd Venda]) ELSE [Qtd Venda] END AS net_qty,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Valor Venda]) ELSE [Valor Venda] END AS net_rev
    FROM Externo01.Vendas
    WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
      AND [Data] >= ?
      AND [Data] < ?
      AND [Cod Cliente] IS NOT NULL
      AND [Cod Produto] IS NOT NULL
) AS base
GROUP BY base.customer_code, base.sku
HAVING SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) > 0
    OR SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) > 0
""".strip()


def fetch_customer_sku_window_sales(
    pre_start_date: date,
    mid_date: date,
    reference_date: date,
) -> List[dict]:
    """
    Lê faturamento e quantidade líquidos por `(Cod Cliente, Cod Produto)` nas janelas
    `PRE` [pre_start_date, mid_date) e `CUR` [mid_date, reference_date) (P-128, P-137.1, ADR-007 DA-03).

    - Subquery iniciando por `SELECT` (compatível com `is_readonly_query`, sem `WITH` e sem `CONCAT`).
    - Abate devoluções (`LIKE 'DEVOLU%'`) algebricamente.
    - Seleciona estritamente `[Cod Cliente]`, `[Cod Produto]`, `[Quantidade]`, `[Valor Venda]` (LGPD-CAN-01).
    - Leitura em blocos via `fetchmany(FETCH_CHUNK_SIZE)`.
    """
    result: List[dict] = []
    params = (mid_date, pre_start_date, reference_date)
    with _execute_readonly(_CUSTOMER_SKU_WINDOW_SALES_SQL, params) as cursor:
        while True:
            chunk = cursor.fetchmany(FETCH_CHUNK_SIZE)
            if not chunk:
                break
            for row in chunk:
                if row[0] is None or row[1] is None:
                    continue
                result.append(
                    {
                        "customer_code": int(row[0]),
                        "sku": str(int(row[1])),
                        "pre_qty": float(row[2] or 0.0),
                        "pre_rev": float(row[3] or 0.0),
                        "cur_qty": float(row[4] or 0.0),
                        "cur_rev": float(row[5] or 0.0),
                    }
                )
    return result


# ------------------------------------------------------------------ F7 — leituras aditivas com 4 datas (P-153.1, P-167; ADR-009 DA-04)

_CUSTOMER_SKU_SPLIT_WINDOW_SALES_SQL = f"""
SELECT
    base.customer_code,
    base.sku,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_qty ELSE 0 END) AS pre_qty,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) AS pre_rev,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_qty ELSE 0 END) AS cur_qty,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) AS cur_rev
FROM (
    SELECT
        [Cod Cliente] AS customer_code,
        [Cod Produto] AS sku,
        CASE WHEN [Data] >= ? THEN 1 ELSE 0 END AS period_flag,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Qtd Venda]) ELSE [Qtd Venda] END AS net_qty,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Valor Venda]) ELSE [Valor Venda] END AS net_rev
    FROM Externo01.Vendas
    WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
      AND (([Data] >= ? AND [Data] < ?) OR ([Data] >= ? AND [Data] < ?))
      AND [Cod Cliente] IS NOT NULL
      AND [Cod Produto] IS NOT NULL
) AS base
GROUP BY base.customer_code, base.sku
HAVING SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) > 0
    OR SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) > 0
""".strip()

_SKU_REGION_WINDOW_SALES_SQL = f"""
SELECT
    [UF] AS uf,
    SUM(CASE WHEN [Data] < ? THEN CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Qtd Venda]) ELSE [Qtd Venda] END ELSE 0 END) AS pre_qty,
    SUM(CASE WHEN [Data] < ? THEN CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Valor Venda]) ELSE [Valor Venda] END ELSE 0 END) AS pre_rev,
    SUM(CASE WHEN [Data] >= ? THEN CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Qtd Venda]) ELSE [Qtd Venda] END ELSE 0 END) AS cur_qty,
    SUM(CASE WHEN [Data] >= ? THEN CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Valor Venda]) ELSE [Valor Venda] END ELSE 0 END) AS cur_rev,
    COUNT(DISTINCT [Cod Cliente]) AS clients
FROM Externo01.Vendas
WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
  AND [Cod Produto] = ?
  AND (([Data] >= ? AND [Data] < ?) OR ([Data] >= ? AND [Data] < ?))
  AND [Cod Cliente] IS NOT NULL
  AND [UF] IS NOT NULL
GROUP BY [UF]
""".strip()


def _validate_four_dates(pre_start: date, pre_end: date, cur_start: date, cur_end: date) -> None:
    """Pré-condição das janelas: `PRE` e `CUR` não vazias, em ordem e sem sobreposição."""
    if not (pre_start < pre_end <= cur_start < cur_end):
        raise ValueError("Janelas inválidas: exige-se pre_start < pre_end <= cur_start < cur_end.")


def fetch_customer_sku_split_window_sales(
    pre_start: date,
    pre_end: date,
    cur_start: date,
    cur_end: date,
) -> List[tuple]:
    """
    Variante da leitura de migração com QUATRO datas (F7, P-153.1, ADR-009 DA-04): serve a janelas
    não contíguas (`point` com X > 1) e contíguas. `PRE` = [pre_start, pre_end), `CUR` = [cur_start, cur_end).

    Mesma blindagem e mesmas colunas da F6 (LGPD-CAN-01); a função da F6 permanece intacta.
    Devolve tuplas `(customer_code, sku_str, pre_qty, pre_rev, cur_qty, cur_rev)` lidas em blocos
    (`fetchmany`). O `customer_code` só existe na etapa volátil de quem chama (LGPD-TIA-01).

    Raises:
        ValueError: datas fora de ordem (antes de executar a consulta).
    """
    _validate_four_dates(pre_start, pre_end, cur_start, cur_end)
    params = (cur_start, pre_start, pre_end, cur_start, cur_end)
    result: List[tuple] = []
    with _execute_readonly(_CUSTOMER_SKU_SPLIT_WINDOW_SALES_SQL, params) as cursor:
        while True:
            chunk = cursor.fetchmany(FETCH_CHUNK_SIZE)
            if not chunk:
                break
            for row in chunk:
                if row[0] is None or row[1] is None:
                    continue
                result.append(
                    (
                        int(row[0]),
                        str(int(row[1])),
                        float(row[2] or 0.0),
                        float(row[3] or 0.0),
                        float(row[4] or 0.0),
                        float(row[5] or 0.0),
                    )
                )
    return result


def fetch_sku_region_window_sales(
    sku: int,
    pre_start: date,
    pre_end: date,
    cur_start: date,
    cur_end: date,
) -> List[tuple]:
    """
    Vendas líquidas de um SKU por UF nas janelas `PRE`/`CUR` (F7, P-167). Devolve só agregados
    `(uf, pre_qty, pre_rev, cur_qty, cur_rev, clientes_distintos)`; o código do cliente nunca sai do SQL.

    Raises:
        ValueError: datas fora de ordem (antes de executar a consulta).
    """
    _validate_four_dates(pre_start, pre_end, cur_start, cur_end)
    params = (pre_end, pre_end, cur_start, cur_start, int(sku), pre_start, pre_end, cur_start, cur_end)
    result: List[tuple] = []
    with _execute_readonly(_SKU_REGION_WINDOW_SALES_SQL, params) as cursor:
        while True:
            chunk = cursor.fetchmany(FETCH_CHUNK_SIZE)
            if not chunk:
                break
            for row in chunk:
                if row[0] is None:
                    continue
                result.append(
                    (
                        str(row[0]).strip().upper(),
                        float(row[1] or 0.0),
                        float(row[2] or 0.0),
                        float(row[3] or 0.0),
                        float(row[4] or 0.0),
                        int(row[5] or 0),
                    )
                )
    return result
