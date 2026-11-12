"""
T-08 — Devolução não cria co-ocorrência (P-058, P-058.5, CA-02, C-12), no repositório e no domínio.

1. Repositório: o SQL do agregado só aceita `[Operação] = 'VENDA'` (asserção sobre a query capturada
   por um cursor `pyodbc` mockado) e a constante de venda é a mesma do domínio.
2. Domínio: linhas brutas sintéticas passam por um emulador do SQL do agregado (filtro de operação
   com `SALE_OPERATION`, `GROUP BY Pedido x SKU`, `HAVING SUM(Qtd) > 0`, `DENSE_RANK`). Um par que
   só existe por causa de devolução não aparece no agregado e não gera regra.
"""
from datetime import date

import numpy as np
import pandas as pd
import pyodbc

from src.modules.analytics.domain import cross_sell
from src.modules.analytics.domain.cross_sell import build_valid_baskets, mine_one_to_one_rules, select_useful_rules
from src.modules.analytics.repository import sales_repository as repo
from tests.analytics.fixtures.synthetic_data import FILLER_POOL_START, ORDER_BASKET_COLUMNS

RETURN_OPERATION = "DEVOLUÇÃO DE VENDA"
SKU_A, SKU_B = 1001, 2002


class _Cursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, *params):
        self.executed.append(sql)
        return self

    def fetchmany(self, size=None):
        return []

    def fetchall(self):
        return []

    def close(self):
        pass


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        pass


def emulate_order_baskets_sql(raw_sales: pd.DataFrame) -> pd.DataFrame:
    """Reproduz em pandas a semântica do SQL de DA-02 usando as constantes do repositório."""
    sales = raw_sales[raw_sales["Operação"] == repo.SALE_OPERATION]
    grouped = sales.groupby(["Pedido", "Cod Produto"]).agg(
        qty=("Qtd Venda", "sum"), customer_code=("Cod Cliente", "min"), order_day=("Data", "min")
    ).reset_index()
    grouped = grouped[grouped["qty"] > 0]
    grouped["order_idx"] = grouped["Pedido"].rank(method="dense").astype(int) - 1
    frame = grouped.rename(columns={"Cod Produto": "sku"})[ORDER_BASKET_COLUMNS]
    return frame.astype({column: np.int32 for column in ORDER_BASKET_COLUMNS})


def build_raw_sales(include_returns_as_sales: bool = False) -> pd.DataFrame:
    """
    1.850 pedidos de VENDA. Em 50 dos 200 pedidos com A há uma linha de devolução de B (Qtd positiva,
    para provar que o filtro é a operação e não o sinal da quantidade). B é vendido em outros 150 pedidos.
    """
    rows = []
    rng = np.random.RandomState(17)
    pool = list(range(FILLER_POOL_START, FILLER_POOL_START + 300))

    def add_order(order, skus, day=9000):
        for sku in skus:
            rows.append({"Pedido": order, "Cod Cliente": 7, "Cod Produto": sku, "Data": day,
                         "Operação": "VENDA", "Qtd Venda": 1})

    order = 0
    for index in range(200):
        add_order(order, [SKU_A, pool[rng.randint(300)]])
        if index < 50:
            operation = "VENDA" if include_returns_as_sales else RETURN_OPERATION
            rows.append({"Pedido": order, "Cod Cliente": 7, "Cod Produto": SKU_B, "Data": 9000,
                         "Operação": operation, "Qtd Venda": 1})
        order += 1
    for _ in range(150):
        add_order(order, [SKU_B, pool[rng.randint(300)]])
        order += 1
    for _ in range(1500):
        first, second = rng.choice(300, size=2, replace=False)
        add_order(order, [pool[first], pool[second]])
        order += 1
    return pd.DataFrame(rows)


def _useful_pairs(order_baskets):
    valid = build_valid_baskets(order_baskets)
    rules = mine_one_to_one_rules(valid)
    useful = select_useful_rules(rules, int(valid["Pedido"].nunique()))
    return {(r.antecedent, r.consequent) for r in useful}


# ------------------------------------------------------------------ repositório

def test_sale_operation_is_single_source_of_truth():
    """DA-02: o repositório usa a mesma constante de venda do domínio."""
    assert repo.SALE_OPERATION == cross_sell.SALE_OPERATION == "VENDA"
    assert repo.RETURN_OPERATION_PATTERN == "DEVOLU%"


def test_order_baskets_sql_only_accepts_sales(monkeypatch):
    for name in ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"):
        monkeypatch.setenv(name, "fake")
    cursor = _Cursor()
    monkeypatch.setattr(pyodbc, "connect", lambda *args, **kwargs: _Connection(cursor))

    repo.fetch_order_baskets(date(2026, 11, 6))

    sql = " ".join(cursor.executed[0].split())
    assert "WHERE [Operação] = 'VENDA'" in sql
    assert "IN (" not in sql.upper()
    assert "LIKE 'DEVOLU%'" not in sql.upper().replace("NOT LIKE 'DEVOLU%'", "")


# ------------------------------------------------------------------ domínio (CA-02, C-12)

def test_ca02_return_line_does_not_enter_the_aggregate():
    raw = build_raw_sales()
    order_baskets = emulate_order_baskets_sql(raw)

    orders_with_a = set(order_baskets.loc[order_baskets["sku"] == SKU_A, "order_idx"])
    orders_with_b = set(order_baskets.loc[order_baskets["sku"] == SKU_B, "order_idx"])
    assert orders_with_a.isdisjoint(orders_with_b)
    assert len(orders_with_b) == 150


def test_ca02_return_does_not_create_rule():
    order_baskets = emulate_order_baskets_sql(build_raw_sales())

    pairs = _useful_pairs(order_baskets)

    assert (SKU_A, SKU_B) not in pairs
    assert (SKU_B, SKU_A) not in pairs


def test_control_same_lines_as_sales_would_create_the_rule():
    """Controle da massa: se as 50 linhas fossem VENDA, A -> B seria Regra Útil (prova que o teste discrimina)."""
    order_baskets = emulate_order_baskets_sql(build_raw_sales(include_returns_as_sales=True))

    assert (SKU_A, SKU_B) in _useful_pairs(order_baskets)
