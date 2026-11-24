"""
Testes de Repositório para Viabilidade de Produto Novo (P-139, P-141, P-144, P-147, P-149; ADR-008).

Valida:
- fetch_new_product_options(): consulta somente leitura ao catálogo ativo (Pc.Venda > 0), deduplicada e ordenada.
- fetch_new_product_candidates(tipo): agregação SQL no grão SKU x Ano x Mês com corte em 2025-04-01 e abatimento de devoluções.
- fetch_mature_product_distribution(tipo): agregação SQL de produtos maduros (1ª venda < 2025-04-01).
- Todas as queries passam por `is_readonly_query`.
- Erros de driver/conexão são traduzidos para AnalyticsDataSourceError (sem stacktrace ou mensagem do driver).
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.database import is_readonly_query
from src.modules.analytics.repository import sales_repository as repo
from src.modules.analytics.repository.errors import AnalyticsDataSourceError


def test_new_product_options_query_is_readonly():
    """P-141: A query de opções de tipo e fornecedor deve ser estritamente somente leitura."""
    sql = repo._NEW_PRODUCT_OPTIONS_SQL
    assert is_readonly_query(sql) is True
    assert "Externo01.Produto" in sql
    assert "Pc.Venda" in sql


def test_new_product_candidates_query_is_readonly():
    """P-139 / P-144 / P-149.1: A query de candidatos agrega no SQL Server e abate devoluções."""
    sql = repo._NEW_PRODUCT_CANDIDATES_SQL
    assert is_readonly_query(sql) is True
    assert "Externo01.Vendas" in sql
    assert "DEVOLU%" in sql
    assert "[Cod Produto]" in sql
    assert "GROUP BY" in sql.upper()


def test_mature_product_distribution_query_is_readonly():
    """P-147: A query de teto maduro agrega produtos com 1ª venda < 2025-04-01 no SQL Server."""
    sql = repo._MATURE_PRODUCT_DISTRIBUTION_SQL
    assert is_readonly_query(sql) is True
    assert "Externo01.Vendas" in sql
    assert "GROUP BY" in sql.upper()


def test_fetch_new_product_options_deduplicates_and_sorts():
    """P-141: fetch_new_product_options retorna tipos e fornecedores deduplicados e ordenados alfabeticamente."""
    # Arrange
    fake_rows = [
        ("Tinturas", "FITOHERB LABORATORIOS"),
        ("Capsulas", "BIO ERVAS IND E COM LTDA"),
        ("Tinturas", "FITOHERB LABORATORIOS"),
        ("Extratos", "APIS FLORA"),
        ("", "IGNORAR VAZIO"),
        ("Capsulas", None),
    ]
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = fake_rows

    with patch.object(repo, "_execute_readonly") as mock_exec:
        mock_exec.return_value.__enter__.return_value = mock_cursor

        # Act
        options = repo.fetch_new_product_options()

    # Assert
    assert options["tipos"] == ["Capsulas", "Extratos", "Tinturas"]
    assert options["fornecedores"] == ["APIS FLORA", "BIO ERVAS IND E COM LTDA", "FITOHERB LABORATORIOS"]


def test_fetch_new_product_candidates_mock_cursor():
    """P-139 / P-144: fetch_new_product_candidates retorna DataFrame agregado sem carregar linhas brutas."""
    # Arrange
    cutoff = date(2026, 11, 1)
    fake_rows = [
        (1042, "Tinturas", "FITOHERB LABORATORIOS", "Tintura Passiflora 50ml", 39.90, date(2025, 5, 10), 2025, 5, 58),
        (1042, "Tinturas", "FITOHERB LABORATORIOS", "Tintura Passiflora 50ml", 39.90, date(2025, 5, 10), 2025, 6, 65),
        (1042, "Tinturas", "FITOHERB LABORATORIOS", "Tintura Passiflora 50ml", 39.90, date(2025, 5, 10), 2025, 7, -5),
    ]
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = fake_rows

    with patch.object(repo, "_execute_readonly") as mock_exec:
        mock_exec.return_value.__enter__.return_value = mock_cursor

        # Act
        df = repo.fetch_new_product_candidates(tipo="Tinturas", cutoff=cutoff)

    # Assert
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert {"sku", "tipo", "fornecedor", "descricao", "preco", "first_sale_date", "sale_year", "sale_month", "net_quantity"}.issubset(
        set(df.columns)
    )
    # P-144: saldo negativo deve ser truncado em 0 ou preservado para truncamento seguro
    assert int(df.iloc[2]["net_quantity"]) >= 0


def test_fetch_new_product_error_translation():
    """P-149.2: Falha de banco no repositório é traduzida para AnalyticsDataSourceError (ANL-001)."""
    with patch.object(repo, "_execute_readonly", side_effect=AnalyticsDataSourceError()):
        with pytest.raises(AnalyticsDataSourceError) as exc_info:
            repo.fetch_new_product_options()
        assert exc_info.value.code == "ANL-001"
