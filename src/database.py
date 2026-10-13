"""
Módulo de Acesso ao Banco de Dados SQL Server da Fitoherb (P-022).
Re-export para manter retrocompatibilidade com a suíte de testes.
"""
import pyodbc
from src.core.database import (
    DatabaseSecurityError,
    is_readonly_query,
    get_db_connection_string,
    test_db_connection,
    fetch_sales_from_database,
    fetch_products_from_database,
)

__all__ = [
    "pyodbc",
    "DatabaseSecurityError",
    "is_readonly_query",
    "get_db_connection_string",
    "test_db_connection",
    "fetch_sales_from_database",
    "fetch_products_from_database",
]

