"""
Módulo de Acesso ao Banco de Dados SQL Server da Fitoherb (P-022).
Core Database Client com minimização de dados LGPD e travas estritas de segurança.
"""
import os
import re
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import pyodbc
from dotenv import load_dotenv

# Carrega .env da raiz do repositório
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseSecurityError(PermissionError):
    """Exceção levantada quando uma tentativa de query não-SELECT ou perigosa é detectada."""
    pass


# Expressão regular para vetar qualquer comando DML/DDL de modificação
_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|EXEC|EXECUTE|GRANT|REVOKE|MERGE)\b",
    re.IGNORECASE
)


def is_readonly_query(sql: str) -> bool:
    """
    Valida rigorosamente se uma query SQL é estritamente de leitura (SELECT).
    Bloqueia múltiplos comandos concatenados por ponto-e-vírgula e comandos de escrita (P-022).
    """
    clean_sql = sql.strip()
    
    # 1. Proibição de ponto-e-vírgula para impedir stacked queries (SQL Injection)
    # Permite apenas ponto e vírgula se for o caractere final isolado
    sql_without_trailing_semi = clean_sql.rstrip(";")
    if ";" in sql_without_trailing_semi:
        return False

    # 2. Deve iniciar obrigatoriamente com SELECT
    if not clean_sql.upper().startswith("SELECT"):
        return False

    # 3. Não pode conter nenhuma palavra-chave proibida de modificação
    if _FORBIDDEN_SQL_PATTERN.search(sql_without_trailing_semi):
        return False

    return True


def get_db_connection_string() -> str:
    """
    Retorna a string de conexão ODBC com os parâmetros definidos nas variáveis de ambiente.
    Lança ValueError caso as variáveis obrigatórias não estejam definidas.
    """
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "1433")
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    pwd = os.getenv("DB_PASSWORD")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

    missing = [var for var, val in [("DB_HOST", host), ("DB_NAME", dbname), ("DB_USER", user), ("DB_PASSWORD", pwd)] if not val]
    if missing:
        raise ValueError(f"Variáveis de ambiente do banco de dados não configuradas: {', '.join(missing)}")

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={dbname};"
        f"UID={user};"
        f"PWD={pwd};"
        f"Encrypt=no;"
        f"TrustServerCertificate=yes;"
    )


def test_db_connection() -> Dict[str, Any]:
    """
    Testa a conectividade com o banco de dados SQL Server executando um SELECT 1.
    """
    conn_str = get_db_connection_string()
    t0 = time.time()
    try:
        timeout_sec = int(os.getenv("DB_TIMEOUT", "3"))
        conn = pyodbc.connect(conn_str, timeout=timeout_sec)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        latency = round((time.time() - t0) * 1000, 2)
        conn.close()
        return {
            "connected": True,
            "latencyMs": latency,
            "message": "Conexão com SQL Server estabelecida com sucesso."
        }
    except Exception as e:
        return {
            "connected": False,
            "latencyMs": round((time.time() - t0) * 1000, 2),
            "message": f"Falha de conexão com SQL Server: {str(e)}"
        }


def fetch_sales_from_database(
    limit: Optional[int] = None,
    custom_query: Optional[str] = None
) -> pd.DataFrame:
    """
    Extrai as vendas da view Externo01.Vendas aplicando estrita minimização de dados LGPD (P-022).
    Apenas colunas analíticas e registros onde [Operação] = 'VENDA' são retornados.
    """
    if custom_query:
        if not is_readonly_query(custom_query):
            raise DatabaseSecurityError(
                "Acesso negado: Apenas queries SELECT estritas são autorizadas no banco de dados corporativo."
            )
        sql = custom_query
    else:
        top_clause = f"TOP {limit} " if limit else ""
        sql = f"""
        SELECT {top_clause}
            [Data],
            [Pedido],
            [Cod Cliente],
            [UF],
            [Operação],
            [Cod Produto],
            [Cod Promocao],
            [Valor Venda],
            [Qtd Venda]
        FROM Externo01.Vendas
        WHERE [Operação] = 'VENDA'
        """

    conn_str = get_db_connection_string()
    logger.info("Executando SELECT no banco de dados SQL Server...")
    t0 = time.time()

    conn = pyodbc.connect(conn_str, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        # Converte para DataFrame preservando tipos
        df = pd.DataFrame.from_records(rows, columns=cols)
        elapsed = time.time() - t0
        logger.info(f"Extração concluída: {len(df)} vendas recuperadas do SQL Server em {elapsed:.2f}s.")
        return df
    finally:
        conn.close()


def fetch_products_from_database(
    limit: Optional[int] = None,
    custom_query: Optional[str] = None
) -> pd.DataFrame:
    """
    Extrai a lista oficial de produtos da view Externo01.Produto do SQL Server (P-022).
    Apenas produtos com preço de venda válido ([Pc.Venda] > 0) são retornados.
    """
    if custom_query:
        if not is_readonly_query(custom_query):
            raise DatabaseSecurityError(
                "Acesso negado: Apenas queries SELECT estritas são autorizadas no banco de dados corporativo."
            )
        sql = custom_query
    else:
        top_clause = f"TOP {limit} " if limit else ""
        sql = f"""
        SELECT {top_clause}
            [Codigo],
            [Descricao],
            [EAN],
            [Fornecedor],
            [Tipo],
            [Estoque],
            [Pc.Ultimo Custo],
            [Pc.Venda]
        FROM Externo01.Produto
        WHERE [Pc.Venda] > 0
        """

    conn_str = get_db_connection_string()
    logger.info("Executando SELECT de produtos no banco de dados SQL Server...")
    t0 = time.time()

    conn = pyodbc.connect(conn_str, timeout=30)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        
        df = pd.DataFrame.from_records(rows, columns=cols)
        elapsed = time.time() - t0
        logger.info(f"Extração concluída: {len(df)} produtos recuperados do SQL Server em {elapsed:.2f}s.")
        return df
    finally:
        conn.close()

