"""T-7.1.12: consultas aditivas do repositorio (4 datas; UF sem codigo de cliente). P-153.1, P-167, LGPD-TIA-01."""
import re
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.core.database import is_readonly_query  # mesmo validador usado pelo modulo analytics

D = dict(pre_start=date(2026, 7, 1), pre_end=date(2026, 8, 1), cur_start=date(2026, 10, 1), cur_end=date(2026, 11, 1))


def _repo():
    from src.modules.analytics.repository import sales_repository
    return sales_repository


def _ctx(chunks):
    cursor = MagicMock()
    cursor.fetchmany.side_effect = chunks
    ctx = MagicMock()
    ctx.__enter__.return_value = cursor
    ctx.__exit__.return_value = False
    return ctx, cursor


def test_split_sql_is_readonly_select_without_with_concat_or_semicolon():
    sql = _repo()._CUSTOMER_SKU_SPLIT_WINDOW_SALES_SQL.strip()
    up = sql.upper()
    assert up.startswith("SELECT") and is_readonly_query(sql)
    assert not re.search(r"\bWITH\b", up) and "CONCAT" not in up and ";" not in sql
    assert sql.count("?") == 5
    for col in ("NOME", "CPF", "CNPJ", "EMAIL", "TELEFONE"):
        assert col not in up


def test_split_fetch_binds_five_params_in_order_and_uses_fetchmany():
    ctx, cursor = _ctx([[(101, 100235, 10.0, 300.0, 2.0, 60.0)], []])
    repo = _repo()
    with patch.object(repo, "_execute_readonly", return_value=ctx) as ex:
        rows = repo.fetch_customer_sku_split_window_sales(**D)
    assert ex.call_args[0][1] == (D["cur_start"], D["pre_start"], D["pre_end"], D["cur_start"], D["cur_end"])
    assert cursor.fetchmany.called and not cursor.fetchall.called
    assert rows == [(101, "100235", 10.0, 300.0, 2.0, 60.0)]


@pytest.mark.parametrize("bad", [
    dict(pre_end=date(2026, 6, 1)),            # pre_end <= pre_start
    dict(cur_start=date(2026, 7, 15)),         # cur_start < pre_end
    dict(cur_end=date(2026, 10, 1)),           # cur_end <= cur_start
])
def test_split_fetch_rejects_invalid_dates_before_executing(bad):
    repo = _repo()
    with patch.object(repo, "_execute_readonly") as ex:
        with pytest.raises(ValueError):
            repo.fetch_customer_sku_split_window_sales(**{**D, **bad})
    ex.assert_not_called()


def test_region_query_returns_only_uf_sums_and_distinct_count():
    repo = _repo()
    sql = repo._SKU_REGION_WINDOW_SALES_SQL.strip().upper()
    assert sql.startswith("SELECT") and "COUNT(DISTINCT" in sql and "GROUP BY" in sql
    select_list = sql.split("FROM")[0].replace("COUNT(DISTINCT [COD CLIENTE])", "")
    assert "COD CLIENTE" not in select_list
    ctx, _ = _ctx([[("SP", 10.0, 100.0, 5.0, 40.0, 7)], []])
    with patch.object(repo, "_execute_readonly", return_value=ctx):
        rows = repo.fetch_sku_region_window_sales(sku=5102, **D)
    assert rows == [("SP", 10.0, 100.0, 5.0, 40.0, 7)]


def test_f7_never_calls_contiguous_variant_in_migration_adapter(monkeypatch):
    """DA-04: 4 datas sempre, inclusive em `average` e janelas contiguas."""
    repo = _repo()
    spy = MagicMock(side_effect=AssertionError("F7 nao pode usar fetch_customer_sku_window_sales"))
    monkeypatch.setattr(repo, "fetch_customer_sku_window_sales", spy)
    from tests.trend_insights.helpers import mod
    source = mod("adapters.migration_adapter").__file__
    text = open(source, encoding="utf-8").read()
    assert "fetch_customer_sku_window_sales" not in text
    assert "fetch_customer_sku_split_window_sales" in text
