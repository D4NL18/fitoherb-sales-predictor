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
from contextlib import contextmanager
from datetime import date
from typing import Iterator, List, Sequence

import numpy as np
import pandas as pd
import pyodbc

from src.core.database import DatabaseSecurityError, get_db_connection_string, is_readonly_query
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

_CATALOG_SQL = """
SELECT [Codigo], [Descricao], [Fornecedor], [Estoque], [Pc.Ultimo Custo], [Pc.Venda]
FROM Externo01.Produto
WHERE [Pc.Venda] > 0
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
