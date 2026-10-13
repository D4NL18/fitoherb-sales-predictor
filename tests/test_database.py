"""
Testes unitários para o módulo de banco de dados (src/database.py).
Valida regras de segurança (somente SELECT), conexão e extração de dados (P-022).
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from src.database import (
    is_readonly_query,
    get_db_connection_string,
    fetch_sales_from_database,
    fetch_products_from_database,
    DatabaseSecurityError,
)



def test_is_readonly_query_valid():
    """Valida que queries SELECT puras são autorizadas."""
    assert is_readonly_query("SELECT * FROM Externo01.Vendas") is True
    assert is_readonly_query("  select top 100 [Data], [Pedido] from Externo01.Vendas where [Operação] = 'VENDA'") is True
    assert is_readonly_query("SELECT COUNT(*) FROM Externo01.Vendas") is True


def test_is_readonly_query_rejects_modifications():
    """Valida rejeição de qualquer query de escrita ou modificação (Segurança P-022)."""
    assert is_readonly_query("UPDATE Externo01.Vendas SET Valor = 0") is False
    assert is_readonly_query("DELETE FROM Externo01.Vendas") is False
    assert is_readonly_query("INSERT INTO Externo01.Vendas VALUES (1)") is False
    assert is_readonly_query("DROP TABLE Externo01.Vendas") is False
    assert is_readonly_query("ALTER TABLE Externo01.Vendas ADD Col INT") is False
    assert is_readonly_query("TRUNCATE TABLE Externo01.Vendas") is False
    assert is_readonly_query("EXEC sp_executesql 'SELECT 1'") is False
    assert is_readonly_query("SELECT 1; DROP TABLE Teste;") is False


def test_fetch_sales_rejects_non_select():
    """Garante que tentativa de executar query que não seja SELECT levanta DatabaseSecurityError."""
    with pytest.raises(DatabaseSecurityError):
        fetch_sales_from_database(custom_query="DELETE FROM Externo01.Vendas")


def test_get_db_connection_string():
    """Verifica formatação da connection string ODBC."""
    conn_str = get_db_connection_string()
    assert "DRIVER=" in conn_str
    assert "SERVER=" in conn_str
    assert "DATABASE=" in conn_str


@patch("src.database.pyodbc.connect")
def test_fetch_sales_mocked_success(mock_connect):
    """Testa fluxo de extração de dados com mock."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Simula colunas e linhas
    mock_cursor.description = [
        ("Data",), ("Pedido",), ("Cod Cliente",), ("UF",),
        ("Operação",), ("Cod Produto",), ("Cod Promocao",),
        ("Valor Venda",), ("Qtd Venda",)
    ]
    mock_cursor.fetchall.return_value = [
        ("2026-09-29", 1001, 10, "BA", "VENDA", 50984, 0, 150.0, 10.0),
        ("2026-09-29", 1002, 20, "SE", "VENDA", 112250, 0, 99.9, 1.0),
    ]

    df = fetch_sales_from_database(limit=2)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Cod Produto" in df.columns
    assert "Pedido" in df.columns


def test_fetch_products_rejects_non_select():
    """Garante que tentativa de executar query que não seja SELECT em produtos levanta DatabaseSecurityError."""
    with pytest.raises(DatabaseSecurityError):
        fetch_products_from_database(custom_query="DROP TABLE Externo01.Produto")


@patch("src.database.pyodbc.connect")
def test_fetch_products_mocked_success(mock_connect):
    """Testa fluxo de extração de produtos do banco com mock."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_cursor.description = [
        ("Codigo",), ("Descricao",), ("EAN",), ("Fornecedor",),
        ("Tipo",), ("Estoque",), ("Pc.Ultimo Custo",), ("Pc.Venda",)
    ]
    mock_cursor.fetchall.return_value = [
        (50930, "EXTRATO DE PROPOLIS", "7896663301317", "APIS FLORA", "LINHA APIS", 100.0, 14.20, 24.75),
        (50932, "PROPOMAX CAPS", "7896663327270", "APIS FLORA", "LINHA APIS", 50.0, 21.28, 36.40),
    ]

    df = fetch_products_from_database(limit=2)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "Codigo" in df.columns
    assert "Pc.Venda" in df.columns
    assert "Pc.Ultimo Custo" in df.columns

