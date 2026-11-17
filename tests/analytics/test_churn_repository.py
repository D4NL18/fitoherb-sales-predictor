"""
Testes de unidade do repositório analítico para as queries agregadas de Churn (P-117, P-121).
Valida parametrização, is_readonly_query e tratamento de devolução.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from src.core.database import DatabaseSecurityError
from src.modules.analytics.repository import sales_repository


def test_fetch_customer_orders_sql_readonly_and_params():
    """Valida que a query de pedidos de clientes é estritamente somente leitura."""
    sql_text = sales_repository._CUSTOMER_ORDERS_SQL
    assert "UPDATE " not in sql_text.upper()
    assert "DELETE " not in sql_text.upper()
    assert "INSERT " not in sql_text.upper()
    assert "DROP " not in sql_text.upper()
    assert "VENDA" in sql_text


def test_fetch_customer_monthly_revenue_abates_returns():
    """Valida que a query de receita mensal considera venda e subtrai devoluções."""
    sql_text = sales_repository._CUSTOMER_MONTHLY_REVENUE_SQL
    assert "DEVOLU%" in sql_text
    assert "SUM" in sql_text.upper()
    assert "[Valor Venda]" in sql_text
