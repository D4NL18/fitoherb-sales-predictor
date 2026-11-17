"""
Testes de Repositório para o agregado de vendas mensais líquidas (P-106; ADR-005 DA-02).

Testa:
- fetch_monthly_sales(cutoff: date) -> pd.DataFrame
- Query passa em is_readonly_query
- Agrupamento no grão SKU x Ano x Mês
- Abatimento de devoluções (VENDA ou LIKE 'DEVOLU%')
- Parâmetro vinculado (cutoff)
- Tratamento de erro virando AnalyticsDataSourceError (ANL-001)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.core.database import is_readonly_query
from src.modules.analytics.repository import sales_repository as repo
from src.modules.analytics.repository.errors import AnalyticsDataSourceError


def test_fetch_monthly_sales_query_is_readonly():
    """A SQL de agregação mensal deve passar na validação estrita de somente leitura."""
    sql = repo._MONTHLY_SALES_SQL
    assert is_readonly_query(sql) is True
    assert "Externo01.Vendas" in sql
    assert "[Cod Produto]" in sql
    assert "YEAR(" in sql
    assert "MONTH(" in sql
    assert "DEVOLU%" in sql
    assert "< ?" in sql  # Bind parameter


def test_fetch_monthly_sales_mock_cursor():
    """Valida a execução de fetch_monthly_sales com cursor mockado."""
    cutoff = date(2026, 11, 1)
    fake_rows = [
        (1042, 2025, 1, 100, 2500.0),
        (1042, 2025, 2, 120, 3000.0),
    ]

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = fake_rows

    with patch.object(repo, "_execute_readonly") as mock_exec:
        mock_exec.return_value.__enter__.return_value = mock_cursor

        df = repo.fetch_monthly_sales(cutoff)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert list(df.columns) == ["sku", "sale_year", "sale_month", "net_quantity", "net_revenue"]
        assert df.iloc[0]["sku"] == 1042
        assert df.iloc[0]["sale_year"] == 2025
        assert df.iloc[0]["sale_month"] == 1
        assert df.iloc[0]["net_quantity"] == 100
        assert df.iloc[0]["net_revenue"] == 2500.0


def test_fetch_monthly_sales_error_translation():
    """Falha de driver na consulta mensal deve ser traduzida em AnalyticsDataSourceError (ANL-001)."""
    cutoff = date(2026, 11, 1)

    with patch.object(repo, "_execute_readonly", side_effect=AnalyticsDataSourceError()):
        with pytest.raises(AnalyticsDataSourceError) as exc_info:
            repo.fetch_monthly_sales(cutoff)
        assert exc_info.value.code == "ANL-001"
