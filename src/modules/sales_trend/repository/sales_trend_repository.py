"""
Repositório SQL para a Tendência de Vendas (P-072.4, P-073.3, P-085, ADR-003 DA-02).
Implementa consultas somente leitura de agregado mensal e catálogo ativo via pyodbc,
com leitura em streaming (fetchmany) e proteção contra SQL Injection / vazamento de PII.
"""
from datetime import date
from decimal import Decimal
import logging
from typing import Dict, List, Optional, Set, Tuple

import pyodbc

from src.core.database import (
    DatabaseSecurityError,
    get_db_connection_string,
    is_readonly_query,
)
from src.modules.sales_trend.domain.sales_trend import (
    MonthlySales,
    TrendCatalogEntry,
    build_monthly_sales,
)
from src.modules.sales_trend.domain.search_text import normalize_text
from src.modules.sales_trend.repository.errors import TrendDataSourceError

logger = logging.getLogger(__name__)

FETCH_CHUNK_SIZE: int = 50_000

ACTIVE_CATALOG_SQL: str = """SELECT [Codigo], [Descricao], [Fornecedor]
FROM Externo01.Produto
WHERE [Pc.Venda] > 0"""

MONTHLY_NET_SALES_SQL: str = """SELECT
    [Cod Produto] AS sku,
    YEAR([Data]) * 100 + MONTH([Data]) AS year_month,
    SUM([Qtd Venda]) AS quantity,
    SUM([Valor Venda]) AS revenue,
    MIN(CASE WHEN [Operação] = 'VENDA' THEN [Data] END) AS first_sale_date
FROM Externo01.Vendas
WHERE ([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%')
  AND [Data] < ?
GROUP BY [Cod Produto], YEAR([Data]) * 100 + MONTH([Data])"""


def _get_connection() -> pyodbc.Connection:
    """Obtém conexão com o banco de dados SQL Server usando a connection string do core."""
    conn_str = get_db_connection_string()
    return pyodbc.connect(conn_str, timeout=15)


def fetch_active_catalog() -> Dict[int, TrendCatalogEntry]:
    """
    Carrega o catálogo de produtos ativos (Pc.Venda > 0) de Externo01.Produto.
    """
    if not is_readonly_query(ACTIVE_CATALOG_SQL):
        raise DatabaseSecurityError("Consulta de catálogo rejeitada por validação de segurança.")

    try:
        with _get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(ACTIVE_CATALOG_SQL)
                rows = cursor.fetchall()

        catalog: Dict[int, TrendCatalogEntry] = {}
        for row in rows:
            codigo = int(row[0])
            desc = str(row[1]) if row[1] else ""
            fornec = str(row[2]) if row[2] else None
            catalog[codigo] = TrendCatalogEntry(
                codigo=codigo,
                descricao=desc,
                fornecedor=fornec,
                descricao_normalizada=normalize_text(desc),
            )
        logger.info("[SALES_TREND_REPO] Catálogo ativo carregado: %d itens", len(catalog))
        return catalog
    except Exception as exc:
        logger.error("[SALES_TREND_REPO] Erro ao carregar catálogo ativo: %s", type(exc).__name__)
        raise TrendDataSourceError() from exc


def fetch_monthly_net_sales(
    cutoff_date: date,
    active_skus: Set[int],
) -> MonthlySales:
    """
    Carrega o agregado mensal de vendas líquidas de devolução em blocos (fetchmany),
    descartando SKUs fora de active_skus durante a leitura e mantendo o first_sale_date global.
    """
    if not is_readonly_query(MONTHLY_NET_SALES_SQL):
        raise DatabaseSecurityError("Consulta agregada rejeitada por validação de segurança.")

    try:
        retained_rows: List[Tuple[int, int, Decimal, Decimal]] = []
        global_min_sale_date: Optional[date] = None

        with _get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(MONTHLY_NET_SALES_SQL, cutoff_date)

                while True:
                    chunk = cursor.fetchmany(FETCH_CHUNK_SIZE)
                    if not chunk:
                        break

                    for row in chunk:
                        sku = int(row[0])
                        ym = int(row[1])
                        qty = Decimal(str(row[2])) if row[2] is not None else Decimal("0")
                        rev = Decimal(str(row[3])) if row[3] is not None else Decimal("0")
                        row_first_date = row[4]

                        # Atualiza first_sale_date global sobre TODAS as linhas lidas (AR-12)
                        if row_first_date:
                            if isinstance(row_first_date, date):
                                f_date = row_first_date
                            else:
                                f_date = row_first_date.date() if hasattr(row_first_date, "date") else None
                            if f_date:
                                if global_min_sale_date is None or f_date < global_min_sale_date:
                                    global_min_sale_date = f_date

                        # Descarta durante o streaming se SKU não for ativo
                        if sku in active_skus:
                            retained_rows.append((sku, ym, qty, rev))

        logger.info(
            "[SALES_TREND_REPO] Agregado carregado: %d linhas ativas retidas (primeira venda global: %s)",
            len(retained_rows),
            global_min_sale_date,
        )

        return build_monthly_sales(
            rows=retained_rows,
            active_skus=active_skus,
            first_sale_date=global_min_sale_date,
        )
    except Exception as exc:
        logger.error("[SALES_TREND_REPO] Erro ao carregar agregado de vendas: %s", type(exc).__name__)
        raise TrendDataSourceError() from exc
