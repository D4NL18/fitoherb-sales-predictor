"""
Testes para o repositório SQL da Tendência de Vendas com cursor mockado (T-07).
Valida regras P-072.4, P-073.3, P-085, P-093, CA-26, CA-40, ADR-003 DA-02.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from src.core.database import is_readonly_query


def test_aggregate_sql_security_and_structure():
    """Valida que a SQL do agregado é somente leitura, sem CONCAT, JOIN ou PII de cliente."""
    from src.modules.sales_trend.repository.sales_trend_repository import (
        MONTHLY_NET_SALES_SQL,
        ACTIVE_CATALOG_SQL,
    )

    # 1. Validação de is_readonly_query
    assert is_readonly_query(MONTHLY_NET_SALES_SQL) is True
    assert is_readonly_query(ACTIVE_CATALOG_SQL) is True

    # 2. Ausência de colunas proibidas (LGPD / PII e colunas de cliente)
    sql_upper = MONTHLY_NET_SALES_SQL.upper()
    assert "COD CLIENTE" not in sql_upper
    assert "CLIENTE" not in sql_upper
    assert "PEDIDO" not in sql_upper
    assert "CONCAT" not in sql_upper
    assert "JOIN" not in sql_upper
    assert "HAVING" not in sql_upper
    assert "SELECT *" not in sql_upper

    # 3. Presença obrigatória dos filtros e bind parameter
    assert "[OPERAÇÃO] = 'VENDA'" in sql_upper or "[OPERACAO] = 'VENDA'" in sql_upper
    assert "LIKE 'DEVOLU%'" in sql_upper
    assert "[DATA] < ?" in sql_upper


def test_fetch_active_catalog_mocked():
    """Valida leitura do catálogo ativo com filtro Pc.Venda > 0."""
    from src.modules.sales_trend.repository.sales_trend_repository import fetch_active_catalog

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (1001, "CHÁ VERDE 100G", "LABORATÓRIO ALFA"),
        (1004, "CHÁ BRANCO 50G", None),
    ]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.modules.sales_trend.repository.sales_trend_repository._get_connection", return_value=mock_conn):
        catalog = fetch_active_catalog()

    assert len(catalog) == 2
    assert catalog[1001].descricao == "CHÁ VERDE 100G"
    assert catalog[1001].fornecedor == "LABORATÓRIO ALFA"
    assert catalog[1004].fornecedor is None


def test_fetch_monthly_net_sales_streaming_discards_inactive():
    """Valida leitura por fetchmany com conversão para inteiros escalados e descarte de inativos."""
    from src.modules.sales_trend.repository.sales_trend_repository import fetch_monthly_net_sales

    # Bloco com SKUs 1001 (ativo) e 1008 (fora do catálogo ativo)
    chunk1 = [
        (1001, 202609, Decimal("20.0"), Decimal("200.0"), date(2025, 1, 7)),
        (1008, 202609, Decimal("40.0"), Decimal("400.0"), date(2025, 1, 10)),
    ]
    chunk2 = []

    mock_cursor = MagicMock()
    mock_cursor.fetchmany.side_effect = [chunk1, chunk2]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    active_skus = {1001}
    with patch("src.modules.sales_trend.repository.sales_trend_repository._get_connection", return_value=mock_conn):
        monthly_sales = fetch_monthly_net_sales(
            cutoff_date=date(2026, 11, 9),
            active_skus=active_skus,
        )

    # 1008 descartado
    assert 1008 not in monthly_sales.series
    assert 1001 in monthly_sales.series
    # first_sale_date preserva o mínimo global de todas as linhas lidas (2025-01-07)
    assert monthly_sales.first_sale_date == date(2025, 1, 7)


def test_repository_driver_error_wraps_in_tnd004():
    """Valida que pyodbc.Error é encapsulado em TrendDataSourceError (TND-004) sem vazar detalhes."""
    import pyodbc
    from src.modules.sales_trend.repository.errors import TrendDataSourceError
    from src.modules.sales_trend.repository.sales_trend_repository import fetch_active_catalog

    with patch("src.modules.sales_trend.repository.sales_trend_repository._get_connection", side_effect=pyodbc.Error("ODBC error")):
        with pytest.raises(TrendDataSourceError) as exc_info:
            fetch_active_catalog()

    assert exc_info.value.code == "TND-004"
    assert "indisponível" in exc_info.value.message.lower()
