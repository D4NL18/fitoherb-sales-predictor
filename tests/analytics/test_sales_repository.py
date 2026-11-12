"""
T-02 — Repositório somente leitura do módulo Analytics (P-058.4, P-058.5, LGPD-01, LGPD-02, LGPD-05).

Cursor `pyodbc` totalmente mockado: nenhum acesso ao banco real.

Interface esperada (B-05, `src/modules/analytics/repository/sales_repository.py`):
- `fetch_order_baskets(cutoff: date) -> pd.DataFrame` (agregado `order_baskets`, DA-02)
- `fetch_catalog() -> pd.DataFrame` (catálogo ativo, colunas de LGPD-01)
- constantes `SALE_OPERATION`, `RETURN_OPERATION_PATTERN`, `ORDER_DAY_EPOCH`, `FETCH_CHUNK_SIZE`
- conexão por `pyodbc.connect(get_db_connection_string(), timeout=30)`, fechada em `finally`
- `repository/errors.py`: `AnalyticsDataSourceError` com `code == "ANL-001"`
"""
import logging
import re
from datetime import date

import numpy as np
import pyodbc
import pytest

from src.core.database import DatabaseSecurityError, is_readonly_query
from src.modules.analytics.repository import sales_repository as repo
from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from tests.analytics.fixtures.synthetic_data import CATALOG_COLUMNS, ORDER_BASKET_COLUMNS

CUTOFF = date(2026, 11, 6)
DRIVER_SECRET = "sa_secret_user"
DRIVER_HOST = "10.9.8.7"
DRIVER_MESSAGE = f"[Microsoft][ODBC Driver 18 for SQL Server] Login failed for user '{DRIVER_SECRET}' at {DRIVER_HOST}"
MAX_ROWS_PER_DRIVER_CALL = 2  # o driver pode devolver menos linhas que o pedido: o loop deve continuar

ORDER_BASKET_ROWS = [
    (0, 1001, 48213, 9000),
    (0, 2002, 48213, 9000),
    (1, 1001, 51977, 9010),
    (1, 3003, 51977, 9010),
    (2, 2002, 63421, 9020),
]

CATALOG_DESCRIPTION = [(name, None, None, None, None, None, None) for name in CATALOG_COLUMNS]
CATALOG_ROWS = [
    (1001, "CHA VERDE 100G", "CATARINENSE", 50.0, 8.0, 15.0),
    (2002, "CAPSULA DE HIBISCO", "HERBARIUM", 84.0, 0.0, 12.5),
]


class FakeCursor:
    """Cursor que registra execute/fetchmany e proíbe fetchall no agregado."""

    def __init__(self, rows, description=None, execute_error=None, allow_fetchall=False):
        self._rows = list(rows)
        self.description = description
        self.execute_error = execute_error
        self.allow_fetchall = allow_fetchall
        self.executed = []
        self.fetchmany_sizes = []
        self.fetchall_calls = 0

    def execute(self, sql, *params):
        if len(params) == 1 and isinstance(params[0], (list, tuple)):
            params = tuple(params[0])
        self.executed.append((sql, tuple(params)))
        if self.execute_error is not None:
            raise self.execute_error
        return self

    def fetchmany(self, size=None):
        self.fetchmany_sizes.append(size)
        take = min(size or 1, MAX_ROWS_PER_DRIVER_CALL)
        chunk, self._rows = self._rows[:take], self._rows[take:]
        return chunk

    def fetchall(self):
        self.fetchall_calls += 1
        if not self.allow_fetchall:
            raise AssertionError("fetchall() é proibido no agregado order_baskets (DA-02)")
        rows, self._rows = self._rows, []
        return rows

    def close(self):
        pass


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def database_env(monkeypatch):
    """Variáveis fictícias para `get_db_connection_string` funcionar sem `.env` real."""
    monkeypatch.setenv("DB_HOST", "fake-host")
    monkeypatch.setenv("DB_NAME", "fake-db")
    monkeypatch.setenv("DB_USER", "fake-user")
    monkeypatch.setenv("DB_PASSWORD", "fake-pass")


@pytest.fixture
def connect_spy(monkeypatch):
    """Substitui `pyodbc.connect` e devolve o registro das chamadas."""
    state = {"calls": [], "connection": None, "error": None}

    def install(cursor=None, error=None):
        state["error"] = error
        state["connection"] = FakeConnection(cursor) if cursor is not None else None

        def fake_connect(*args, **kwargs):
            state["calls"].append((args, kwargs))
            if state["error"] is not None:
                raise state["error"]
            return state["connection"]

        monkeypatch.setattr(pyodbc, "connect", fake_connect)
        return state

    return install


def _normalized(sql: str) -> str:
    return " ".join(sql.split())


def _run_order_baskets(connect_spy, rows=ORDER_BASKET_ROWS):
    cursor = FakeCursor(rows)
    state = connect_spy(cursor)
    frame = repo.fetch_order_baskets(CUTOFF)
    return frame, cursor, state


# ------------------------------------------------------------------ constantes (P-058.5, DA-02)

def test_repository_constants():
    assert repo.RETURN_OPERATION_PATTERN == "DEVOLU%"
    assert repo.SALE_OPERATION == "VENDA"
    assert repo.FETCH_CHUNK_SIZE == 50_000
    assert str(repo.ORDER_DAY_EPOCH)[:10] == "2000-01-01"


def test_data_source_error_code():
    assert AnalyticsDataSourceError().code == "ANL-001"


# ------------------------------------------------------------------ SQL do agregado (P-058.4, LGPD-01)

def test_order_baskets_sql_is_readonly_and_aggregated(connect_spy):
    _, cursor, _ = _run_order_baskets(connect_spy)
    sql = _normalized(cursor.executed[0][0])

    assert is_readonly_query(sql)
    assert "[Operação] = 'VENDA'" in sql
    assert "HAVING SUM([Qtd Venda]) > 0" in sql
    assert "DENSE_RANK" in sql.upper()
    assert "DATEDIFF" in sql.upper()
    assert "GROUP BY [Pedido], [Cod Produto]" in sql


@pytest.mark.parametrize(
    "forbidden",
    [r"CONCAT", r"\bUF\b", r"Valor Venda", r"Cod Promocao", r"\bEAN\b", r"\bTipo\b", r"SELECT\s+\*", r"SELECT\s+TOP"],
)
def test_order_baskets_sql_has_no_forbidden_column_or_construct(connect_spy, forbidden):
    """LGPD-01: sem UF, Valor Venda, Cod Promocao, EAN, Tipo, SELECT *; sem CONCAT (SQL Server legado)."""
    _, cursor, _ = _run_order_baskets(connect_spy)
    sql = _normalized(cursor.executed[0][0])
    assert re.search(forbidden, sql, flags=re.IGNORECASE) is None


def test_order_baskets_sql_never_includes_returns(connect_spy):
    """P-058: devolução não entra nem como abatimento; só pode aparecer como exclusão explícita."""
    _, cursor, _ = _run_order_baskets(connect_spy)
    sql = _normalized(cursor.executed[0][0]).upper()
    assert "DEVOLU" not in sql or "NOT LIKE 'DEVOLU%'" in sql
    assert " OR " not in sql


def test_cutoff_goes_as_bind_parameter(connect_spy):
    """LGPD-02: a data de corte vai como parâmetro vinculado, nunca interpolada no texto."""
    _, cursor, _ = _run_order_baskets(connect_spy)
    sql, params = cursor.executed[0]

    assert params == (CUTOFF,)
    assert "?" in sql
    for rendered in ("2026-11-06", "20261106", "2026/11/06", "06/11/2026"):
        assert rendered not in sql
    assert len(cursor.executed) == 1


# ------------------------------------------------------------------ leitura em blocos e tipos (DA-02, DA-03)

def test_order_baskets_read_in_chunks_never_fetchall(connect_spy):
    frame, cursor, _ = _run_order_baskets(connect_spy)

    assert cursor.fetchall_calls == 0
    assert cursor.fetchmany_sizes, "a leitura deve usar fetchmany"
    assert all(size == repo.FETCH_CHUNK_SIZE for size in cursor.fetchmany_sizes)
    assert len(frame) == len(ORDER_BASKET_ROWS), "o loop deve continuar até o driver devolver bloco vazio"


def test_order_baskets_columns_and_int32_dtypes(connect_spy):
    frame, _, _ = _run_order_baskets(connect_spy)

    assert list(frame.columns) == ORDER_BASKET_COLUMNS
    for column in ORDER_BASKET_COLUMNS:
        assert frame[column].dtype == np.int32, column
    assert frame.values.tolist() == [list(row) for row in ORDER_BASKET_ROWS]


def test_order_baskets_empty_result_keeps_schema(connect_spy):
    frame, _, _ = _run_order_baskets(connect_spy, rows=[])

    assert frame.empty
    assert list(frame.columns) == ORDER_BASKET_COLUMNS
    assert all(frame[column].dtype == np.int32 for column in ORDER_BASKET_COLUMNS)


def test_connection_uses_core_string_timeout_and_is_closed(connect_spy):
    _, _, state = _run_order_baskets(connect_spy)

    args, kwargs = state["calls"][0]
    assert "fake-host" in args[0]
    assert kwargs.get("timeout") == 30
    assert state["connection"].closed


# ------------------------------------------------------------------ catálogo (LGPD-01, P-061.3)

def test_catalog_sql_selects_exact_minimal_columns(connect_spy):
    cursor = FakeCursor(CATALOG_ROWS, description=CATALOG_DESCRIPTION, allow_fetchall=True)
    connect_spy(cursor)

    frame = repo.fetch_catalog()
    sql = _normalized(cursor.executed[0][0])
    select_part = re.search(r"SELECT\s+(.*?)\s+FROM", sql, flags=re.IGNORECASE | re.DOTALL).group(1)
    selected = re.findall(r"\[([^\]]+)\]", select_part)

    assert is_readonly_query(sql)
    assert sorted(selected) == sorted(CATALOG_COLUMNS)
    assert "*" not in select_part
    assert "Externo01.Produto" in sql
    assert "[Pc.Venda] > 0" in sql
    assert re.search(r"\bEAN\b|\bTipo\b", sql) is None
    assert list(frame.columns) == CATALOG_COLUMNS
    assert len(frame) == len(CATALOG_ROWS)


# ------------------------------------------------------------------ somente leitura

def test_query_is_validated_with_is_readonly_query_before_execution(connect_spy, monkeypatch):
    cursor = FakeCursor(ORDER_BASKET_ROWS)
    connect_spy(cursor)
    import src.core.database as core_database

    monkeypatch.setattr(core_database, "is_readonly_query", lambda sql: False)
    monkeypatch.setattr(repo, "is_readonly_query", lambda sql: False, raising=False)

    with pytest.raises((DatabaseSecurityError, AnalyticsDataSourceError)):
        repo.fetch_order_baskets(CUTOFF)
    assert cursor.executed == []


# ------------------------------------------------------------------ erros sanitizados (LGPD-05)

def _assert_no_driver_leak(caplog, exc_info):
    assert exc_info.value.code == "ANL-001"
    assert DRIVER_SECRET not in str(exc_info.value)
    assert DRIVER_HOST not in str(exc_info.value)
    for record in caplog.records:
        message = record.getMessage()
        assert DRIVER_SECRET not in message
        assert DRIVER_HOST not in message
        assert record.exc_info is None or DRIVER_SECRET not in str(record.exc_info[1])


def test_connect_driver_error_becomes_data_source_error(connect_spy, caplog):
    connect_spy(error=pyodbc.Error("08001", DRIVER_MESSAGE))
    caplog.set_level(logging.DEBUG)

    with pytest.raises(AnalyticsDataSourceError) as exc_info:
        repo.fetch_order_baskets(CUTOFF)
    _assert_no_driver_leak(caplog, exc_info)


def test_execute_driver_error_becomes_data_source_error_and_closes_connection(connect_spy, caplog):
    cursor = FakeCursor([], execute_error=pyodbc.Error("42000", DRIVER_MESSAGE))
    state = connect_spy(cursor)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(AnalyticsDataSourceError) as exc_info:
        repo.fetch_order_baskets(CUTOFF)
    _assert_no_driver_leak(caplog, exc_info)
    assert state["connection"].closed


def test_connection_error_becomes_data_source_error(connect_spy, caplog):
    connect_spy(error=ConnectionError(DRIVER_MESSAGE))
    caplog.set_level(logging.DEBUG)

    with pytest.raises(AnalyticsDataSourceError) as exc_info:
        repo.fetch_catalog()
    _assert_no_driver_leak(caplog, exc_info)


def test_missing_configuration_becomes_data_source_error(connect_spy, monkeypatch):
    state = connect_spy(FakeCursor(ORDER_BASKET_ROWS))
    monkeypatch.delenv("DB_HOST", raising=False)

    with pytest.raises(AnalyticsDataSourceError) as exc_info:
        repo.fetch_order_baskets(CUTOFF)
    assert exc_info.value.code == "ANL-001"
    assert "DB_HOST" not in str(exc_info.value)
    assert state["calls"] == []
