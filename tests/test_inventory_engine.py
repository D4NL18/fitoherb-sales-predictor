"""
Suíte TDD (fase vermelha): Motor de Estoque pela Política Mín/Máx por dias de cobertura.

Regras cobertas: P-041 (VMD), P-053 (mínimo/máximo), P-054 (gatilho e quantidade, sem travas),
P-055 (status, cobertura, capital imobilizado, KPIs, ordenação), P-056 (revogação de ROP/ES/ideal,
trava física P-044.4 e teto orçamentário P-046.3), P-047.1 (filtro por fornecedor) e Curva ABC global.
Contrato: .agents/docs/api_contracts/inventory.md (2.0.0). Decisões: ADR-001 (DA-01, DA-02, DA-10).
"""
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytest

from src.modules.inventory.domain.inventory_engine import (
    STATUS_LABELS,
    InventoryStatus,
    build_sales_lookup,
    calculate_coverage_days,
    calculate_inventory_replenishment,
    calculate_sales_velocity,
    classify_abc_curve,
    prepare_product_catalog,
)
from src.modules.inventory.domain.replenishment_policy import (
    InvalidReplenishmentPolicyError,
    ReplenishmentPolicy,
)

WINDOW_DAYS = 60
DEFAULT_POLICY_ARGS = {"min_coverage_days": 30, "max_coverage_days": 60, "lead_time_days": 15}

REVOKED_ITEM_KEYS = {
    "estoqueSeguranca",
    "rop",
    "estoqueIdeal",
    "estoqueIdealTeorico",
    "qtdSugeridaTeorica",
    "limitadoPorEspaco",
    "tetoCompraFisica",
    "desvioPadraoDemanda",
}
EXPECTED_ITEM_KEYS = {
    "codigo", "descricao", "ean", "fornecedor", "tipo", "estoqueAtual", "vmd", "diasCobertura",
    "leadTime", "estoqueMinimo", "estoqueMaximo", "qtdSugeridaCompra", "custoUnitario", "precoVenda",
    "investimentoTotalItem", "status", "statusLabel", "curvaAbc",
}
EXPECTED_KPI_KEYS = {
    "totalSkusAnalisados", "skusEmRupturaCritica", "skusNecessitamReposicao", "skusEstoqueSaudavel",
    "skusEmOverstock", "investimentoTotalSugerido", "capitalImobilizadoOverstock", "curvaADistribuicao",
}
STATUS_DISPLAY_ORDER = {"CRITICAL_STOCKOUT": 0, "REORDER_NEEDED": 1, "HEALTHY": 2, "OVERSTOCK": 3}
ABC_DISPLAY_ORDER = {"A": 0, "B": 1, "C": 2}


# ---------------------------------------------------------------------------
# Helpers de massa de dados
# ---------------------------------------------------------------------------
def default_policy(**overrides) -> ReplenishmentPolicy:
    return ReplenishmentPolicy(**{**DEFAULT_POLICY_ARGS, **overrides})


def make_catalog_row(sku: int, stock: float, cost: float = 10.0, price: float = 20.0,
                     supplier: str = "APIS FLORA") -> Dict:
    """Linha de catálogo com os nomes de coluna crus do ERP (normalizados por prepare_product_catalog)."""
    return {
        "Codigo": sku,
        "Descricao": f"PRODUTO {sku}",
        "EAN": f"789{sku:010d}",
        "Fornecedor": supplier,
        "Tipo": "EXTRATOS",
        "Estoque": stock,
        "Pc.Ultimo Custo": cost,
        "Pc.Venda": price,
    }


def make_velocity(totals: Dict[int, Tuple[float, float]], window_days: int = WINDOW_DAYS) -> pd.DataFrame:
    """DataFrame de velocidade (interface do motor): sku -> (qtd vendida na janela, receita na janela).

    A VMD é a razão exata qtd/janela, como exige P-053.6 (sem arredondamento a 4 casas).
    """
    if not totals:
        return pd.DataFrame(columns=["vmd", "std_demand", "total_sold_qty", "total_revenue"])
    skus = list(totals.keys())
    qty = [float(totals[s][0]) for s in skus]
    revenue = [float(totals[s][1]) for s in skus]
    df = pd.DataFrame(
        {
            "vmd": [q / window_days for q in qty],
            "std_demand": [0.0] * len(skus),
            "total_sold_qty": qty,
            "total_revenue": revenue,
        },
        index=pd.Index(np.array(skus, dtype=np.int64), name="sku"),
    )
    return df


def run_engine(rows: Iterable[Dict], velocity_df: pd.DataFrame,
               policy: Optional[ReplenishmentPolicy] = None,
               supplier_filter: Optional[str] = None) -> Dict:
    catalog = prepare_product_catalog(pd.DataFrame(list(rows)), supplier_filter)
    return calculate_inventory_replenishment(catalog, velocity_df, policy or default_policy())


def run_single(stock: float, sold_in_window: float, cost: float = 10.0, price: float = 20.0,
               policy: Optional[ReplenishmentPolicy] = None) -> Tuple[Dict, Dict]:
    """Executa o motor para um único SKU (código 1) e devolve (item, kpis)."""
    totals = {1: (sold_in_window, sold_in_window * price)} if sold_in_window > 0 else {}
    result = run_engine([make_catalog_row(1, stock, cost, price)], make_velocity(totals), policy)
    assert len(result["produtos"]) == 1
    return result["produtos"][0], result["kpis"]


def by_code(result: Dict) -> Dict[int, Dict]:
    return {p["codigo"]: p for p in result["produtos"]}


# ---------------------------------------------------------------------------
# Fixtures (mantidas do baseline)
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_sales_data():
    """Massa de vendas sintética: 101 vende 2 un/dia; 102 vende 10 un a cada 5 dias; 103 sem venda."""
    dates = pd.date_range(end="2026-09-30", periods=60, freq="D")
    data = []
    for d in dates:
        data.append({"Data": d, "Cod Produto": 101, "Qtd Venda": 2.0, "Valor Venda": 50.0})
    for i, d in enumerate(dates):
        if i % 5 == 0:
            data.append({"Data": d, "Cod Produto": 102, "Qtd Venda": 10.0, "Valor Venda": 200.0})
    return pd.DataFrame(data)


@pytest.fixture
def sample_catalog_data():
    return pd.DataFrame([
        {"Codigo": 101, "Descricao": "EXTRATO PROPOLIS APISFLORA", "EAN": "7891234567890",
         "Fornecedor": "APIS FLORA", "Tipo": "EXTRATOS", "Estoque": 10.0,
         "Pc.Ultimo Custo": 15.0, "Pc.Venda": 25.0},
        {"Codigo": 102, "Descricao": "VITAMINA C HERBARIUM", "EAN": "7899876543210",
         "Fornecedor": "HERBARIUM", "Tipo": "VITAMINAS", "Estoque": 50.0,
         "Pc.Ultimo Custo": 10.0, "Pc.Venda": 20.0},
        {"Codigo": 103, "Descricao": "CHA VERDE CATARINENSE", "EAN": "7891112223334",
         "Fornecedor": "CATARINENSE", "Tipo": "CHAS", "Estoque": 300.0,
         "Pc.Ultimo Custo": 5.0, "Pc.Venda": 12.0},
    ])


# ---------------------------------------------------------------------------
# P-041 / P-053.6 — Velocidade de vendas
# ---------------------------------------------------------------------------
class TestSalesVelocity:
    def test_calculate_sales_velocity(self, sample_sales_data):
        velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
        assert 101 in velocity_df.index
        assert 102 in velocity_df.index
        assert velocity_df.loc[101, "vmd"] == pytest.approx(2.0, abs=1e-12)
        assert velocity_df.loc[101, "std_demand"] == pytest.approx(0.0, abs=0.01)
        assert velocity_df.loc[102, "vmd"] == pytest.approx(2.0, abs=1e-12)
        assert velocity_df.loc[102, "std_demand"] > 1.0

    def test_p053_6_vmd_kept_in_full_precision(self):
        """1 un em 60 dias -> VMD = 1/60 exata (sem o arredondamento antigo a 4 casas = 0.0167)."""
        sales = pd.DataFrame([{"Data": pd.Timestamp("2026-09-30"), "Cod Produto": 7,
                               "Qtd Venda": 1.0, "Valor Venda": 10.0}])
        velocity_df = calculate_sales_velocity(sales, window_days=60)
        assert velocity_df.loc[7, "vmd"] == pytest.approx(1 / 60, abs=1e-12)

    def test_p053_6_vmd_75_units_in_60_days(self):
        dates = pd.date_range(end="2026-09-30", periods=60, freq="D")
        sales = pd.DataFrame([{"Data": dates[0], "Cod Produto": 8, "Qtd Venda": 75.0, "Valor Venda": 750.0}])
        velocity_df = calculate_sales_velocity(sales, window_days=60)
        assert velocity_df.loc[8, "vmd"] == pytest.approx(1.25, abs=1e-12)


class TestSqlVelocityPrecision:
    """T-04: o caminho SQL também preserva a VMD em precisão integral (P-053.6, A3)."""

    def test_p053_6_sql_path_does_not_round_vmd(self, monkeypatch):
        import src.core.database as database

        class FakeCursor:
            def execute(self, sql):
                self.sql = sql

            def fetchall(self):
                return [(1, 1, 10.0, 1.0, 1)]

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                pass

        monkeypatch.setattr(database, "get_db_connection_string", lambda: "DRIVER=fake")
        monkeypatch.setattr(database.pyodbc, "connect", lambda *args, **kwargs: FakeConnection())

        velocity_df = database.fetch_sales_velocity_from_database(window_days=60)
        assert velocity_df.loc[1, "vmd"] == pytest.approx(1 / 60, abs=1e-12)

        result = calculate_inventory_replenishment(
            prepare_product_catalog(pd.DataFrame([make_catalog_row(1, stock=0.0)]), None),
            velocity_df,
            default_policy(),
        )
        assert result["produtos"][0]["estoqueMaximo"] == 1


# ---------------------------------------------------------------------------
# P-053 — Estoque Mínimo / Máximo pelo motor completo (E1–E6, CA-P053-01..08)
# ---------------------------------------------------------------------------
class TestMinMaxLevels:
    @pytest.mark.parametrize(
        "sold,min_days,max_days,expected_min,expected_max",
        [
            (120, 30, 60, 60, 120),
            (75, 30, 60, 38, 75),
            (30, 30, 60, 15, 30),
            (120, 20, 45, 40, 90),
            (1, 30, 60, 1, 1),
            (0, 30, 60, 0, 0),
        ],
        ids=["P-053-E1-CA01", "P-053-E2-CA02", "P-053-E3", "P-053-E4-CA03", "P-053-E5-CA08", "P-053-E6-CA06"],
    )
    def test_p053_examples(self, sold, min_days, max_days, expected_min, expected_max):
        policy = default_policy(min_coverage_days=min_days, max_coverage_days=max_days)
        item, _ = run_single(stock=10_000.0, sold_in_window=sold, policy=policy)
        assert item["estoqueMinimo"] == expected_min
        assert item["estoqueMaximo"] == expected_max
        assert isinstance(item["estoqueMinimo"], int)
        assert isinstance(item["estoqueMaximo"], int)

    def test_ca_p053_06_no_sales_means_zero_levels_and_no_purchase(self):
        item, _ = run_single(stock=0.0, sold_in_window=0)
        assert (item["estoqueMinimo"], item["estoqueMaximo"], item["qtdSugeridaCompra"]) == (0, 0, 0)

    def test_ca_p053_07_volatility_does_not_change_levels(self, sample_sales_data):
        """101 (2 un/dia) e 102 (10 un a cada 5 dias) têm a mesma VMD 2,0 -> mesmo mínimo/máximo."""
        velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
        rows = [make_catalog_row(101, 90.0), make_catalog_row(102, 90.0)]
        products = by_code(run_engine(rows, velocity_df))
        for sku in (101, 102):
            assert products[sku]["estoqueMinimo"] == 60
            assert products[sku]["estoqueMaximo"] == 120
            assert products[sku]["qtdSugeridaCompra"] == 0

    def test_ca_p053_08_low_turnover_precision_end_to_end(self):
        """1 un em 60 dias, a partir das vendas brutas: mínimo 1 e máximo 1 (não 2)."""
        sales = pd.DataFrame([{"Data": pd.Timestamp("2026-09-30"), "Cod Produto": 1,
                               "Qtd Venda": 1.0, "Valor Venda": 20.0}])
        velocity_df = calculate_sales_velocity(sales, window_days=60)
        result = run_engine([make_catalog_row(1, 0.0)], velocity_df)
        item = result["produtos"][0]
        assert item["estoqueMinimo"] == 1
        assert item["estoqueMaximo"] == 1
        assert item["vmd"] == pytest.approx(0.02, abs=1e-9)  # exibição a 2 casas

    def test_p053_7_lead_time_does_not_change_levels(self):
        short, _ = run_single(stock=90.0, sold_in_window=120, policy=default_policy(lead_time_days=1))
        long, _ = run_single(stock=90.0, sold_in_window=120, policy=default_policy(lead_time_days=59))
        assert (short["estoqueMinimo"], short["estoqueMaximo"]) == (60, 120)
        assert (long["estoqueMinimo"], long["estoqueMaximo"]) == (60, 120)

    def test_p053_9_negative_erp_stock_is_zero(self):
        item, _ = run_single(stock=-5.0, sold_in_window=120)
        assert item["estoqueAtual"] == 0.0
        assert item["qtdSugeridaCompra"] == 120
        assert item["status"] == "CRITICAL_STOCKOUT"


# ---------------------------------------------------------------------------
# P-054 — Gatilho e quantidade de compra (C1–C8, CA-P054-01..08)
# ---------------------------------------------------------------------------
class TestPurchaseSuggestion:
    @pytest.mark.parametrize(
        "stock,coverage,expected_qty,expected_investment",
        [
            (50.0, 25.0, 70, 700.0),
            (10.0, 5.0, 110, 1100.0),
            (0.0, 0.0, 120, 1200.0),
            (60.0, 30.0, 60, 600.0),
            (61.0, 30.5, 0, 0.0),
            (120.0, 60.0, 0, 0.0),
            (150.0, 75.0, 0, 0.0),
            (50.4, 25.2, 70, 700.0),
        ],
        ids=["P-054-C1-CA01", "P-054-C2-CA02", "P-054-C3", "P-054-C4-CA03-inclusivo",
             "P-054-C5-CA04", "P-054-C6", "P-054-C7", "P-054-C8-fracionario"],
    )
    def test_p054_purchase_table(self, stock, coverage, expected_qty, expected_investment):
        item, kpis = run_single(stock=stock, sold_in_window=120, cost=10.0)
        assert item["diasCobertura"] == pytest.approx(coverage)
        assert item["qtdSugeridaCompra"] == expected_qty
        assert isinstance(item["qtdSugeridaCompra"], int)
        assert item["investimentoTotalItem"] == pytest.approx(expected_investment, abs=0.005)
        assert kpis["investimentoTotalSugerido"] == pytest.approx(expected_investment, abs=0.005)

    def test_ca_p056_01_no_physical_cap_on_stockout(self):
        """Antes, a trava +100% limitaria a 20 un; agora compra até o máximo (110)."""
        item, _ = run_single(stock=10.0, sold_in_window=120)
        assert item["qtdSugeridaCompra"] == 110

    def test_ca_p054_05_zero_stock_buys_full_maximum(self):
        item, _ = run_single(stock=0.0, sold_in_window=300)  # VMD 5,0
        assert item["estoqueMaximo"] == 300
        assert item["qtdSugeridaCompra"] == 300
        assert item["status"] == "CRITICAL_STOCKOUT"

    def test_ca_p054_06_no_budget_ceiling(self):
        """5 SKUs de R$ 100.000,00 cada -> total R$ 500.000,00 sem nenhum corte."""
        rows = [make_catalog_row(sku, stock=200.0, cost=100.0) for sku in range(1, 6)]
        velocity_df = make_velocity({sku: (1200.0, 1200.0 * 20.0) for sku in range(1, 6)})  # VMD 20
        result = run_engine(rows, velocity_df)
        for item in result["produtos"]:
            assert item["estoqueMaximo"] == 1200
            assert item["qtdSugeridaCompra"] == 1000
            assert item["investimentoTotalItem"] == pytest.approx(100_000.0)
        assert result["kpis"]["investimentoTotalSugerido"] == pytest.approx(500_000.0)

    def test_ca_p054_07_cost_fallback_60pct_of_price(self):
        item, _ = run_single(stock=50.0, sold_in_window=120, cost=0.0, price=25.0)
        assert item["custoUnitario"] == pytest.approx(15.0)
        assert item["qtdSugeridaCompra"] == 70
        assert item["investimentoTotalItem"] == pytest.approx(1050.0)

    def test_p054_5_zero_cost_keeps_quantity(self):
        item, _ = run_single(stock=50.0, sold_in_window=120, cost=0.0, price=0.0)
        assert item["custoUnitario"] == 0.0
        assert item["qtdSugeridaCompra"] == 70
        assert item["investimentoTotalItem"] == 0.0

    def test_p054_1_min_equals_max_stock_zero_triggers_one_unit(self):
        item, _ = run_single(stock=0.0, sold_in_window=1)
        assert (item["estoqueMinimo"], item["estoqueMaximo"]) == (1, 1)
        assert item["qtdSugeridaCompra"] == 1
        assert item["status"] == "CRITICAL_STOCKOUT"


# ---------------------------------------------------------------------------
# P-055 — Status, cobertura e capital imobilizado (S1–S9, CA-P055-01..09)
# ---------------------------------------------------------------------------
class TestStatusClassification:
    @pytest.mark.parametrize(
        "stock,sold,coverage,status,label,qty,capital",
        [
            (10.0, 120, 5.0, "CRITICAL_STOCKOUT", "Ruptura Iminente", 110, 0.0),
            (30.0, 120, 15.0, "REORDER_NEEDED", "Abaixo do Mínimo", 90, 0.0),
            (50.0, 120, 25.0, "REORDER_NEEDED", "Abaixo do Mínimo", 70, 0.0),
            (60.0, 120, 30.0, "REORDER_NEEDED", "Abaixo do Mínimo", 60, 0.0),
            (90.0, 120, 45.0, "HEALTHY", "Estoque Saudável", 0, 0.0),
            (120.0, 120, 60.0, "HEALTHY", "Estoque Saudável", 0, 0.0),
            (150.0, 120, 75.0, "OVERSTOCK", "Acima do Máximo", 0, 450.0),
            (300.0, 0, 999.0, "OVERSTOCK", "Acima do Máximo", 0, 4500.0),
            (0.0, 0, 0.0, "HEALTHY", "Estoque Saudável", 0, 0.0),
        ],
        ids=["P-055-S1-CA01", "P-055-S2-CA03-fronteira-lead", "P-055-S3-CA02", "P-055-S4-inclusivo",
             "P-055-S5-CA04", "P-055-S6-inclusivo-max", "P-055-S7-CA05", "P-055-S8-sem-venda",
             "P-055-S9-CA07"],
    )
    def test_p055_status_table(self, stock, sold, coverage, status, label, qty, capital):
        item, kpis = run_single(stock=stock, sold_in_window=sold, cost=15.0, price=25.0)
        assert item["diasCobertura"] == pytest.approx(coverage)
        assert item["status"] == status
        assert item["statusLabel"] == label
        assert item["qtdSugeridaCompra"] == qty
        assert kpis["capitalImobilizadoOverstock"] == pytest.approx(capital, abs=0.005)

    def test_ca_p055_06_no_sales_with_stock_capital(self):
        item, kpis = run_single(stock=300.0, sold_in_window=0, cost=5.0, price=12.0)
        assert item["diasCobertura"] == 999.0
        assert item["status"] == "OVERSTOCK"
        assert item["statusLabel"] == "Acima do Máximo"
        assert kpis["capitalImobilizadoOverstock"] == pytest.approx(1500.0)

    def test_ca_p055_08_min_equals_max_with_stock_is_healthy(self):
        item, _ = run_single(stock=1.0, sold_in_window=1)
        assert (item["estoqueMinimo"], item["estoqueMaximo"]) == (1, 1)
        assert item["qtdSugeridaCompra"] == 0
        assert item["status"] == "HEALTHY"
        assert item["statusLabel"] == "Estoque Saudável"

    def test_p055_3_lead_time_only_flags_stockout(self):
        """Mesmo estoque (50, cobertura 25): lead 30 -> ruptura; lead 15 -> abaixo do mínimo. Compra igual."""
        rupture, _ = run_single(stock=50.0, sold_in_window=120, policy=default_policy(lead_time_days=30))
        reorder, _ = run_single(stock=50.0, sold_in_window=120, policy=default_policy(lead_time_days=15))
        assert rupture["status"] == "CRITICAL_STOCKOUT"
        assert reorder["status"] == "REORDER_NEEDED"
        assert rupture["qtdSugeridaCompra"] == reorder["qtdSugeridaCompra"] == 70
        assert rupture["leadTime"] == 30

    def test_status_enum_and_labels(self):
        assert {s.value for s in InventoryStatus} == set(STATUS_DISPLAY_ORDER)
        assert STATUS_LABELS[InventoryStatus.CRITICAL_STOCKOUT] == "Ruptura Iminente"
        assert STATUS_LABELS[InventoryStatus.REORDER_NEEDED] == "Abaixo do Mínimo"
        assert STATUS_LABELS[InventoryStatus.HEALTHY] == "Estoque Saudável"
        assert STATUS_LABELS[InventoryStatus.OVERSTOCK] == "Acima do Máximo"

    @pytest.mark.parametrize(
        "stock,vmd,expected",
        [(10.0, 2.0, 5.0), (50.4, 2.0, 25.2), (300.0, 0.0, 999.0), (0.0, 0.0, 0.0), (1.0, 1 / 60, 60.0)],
        ids=["P-055.1-normal", "P-055.1-fracao", "P-055.1-infinito", "P-055.1-zero", "P-055.1-giro-baixo"],
    )
    def test_p055_1_coverage_days(self, stock, vmd, expected):
        assert calculate_coverage_days(stock, vmd) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# P-055.5 / P-055.6 / P-054.6 / P-056 — KPIs, ordenação e chaves do contrato
# ---------------------------------------------------------------------------
@pytest.fixture
def mixed_scenario_result():
    """Um SKU por exemplo S1–S9 (custo R$ 15,00), política 30/60/15."""
    scenarios = {
        1: (10.0, 120), 2: (30.0, 120), 3: (50.0, 120), 4: (60.0, 120), 5: (90.0, 120),
        6: (120.0, 120), 7: (150.0, 120), 8: (300.0, 0), 9: (0.0, 0),
    }
    rows = [make_catalog_row(sku, stock, cost=15.0, price=25.0) for sku, (stock, _) in scenarios.items()]
    velocity_df = make_velocity({sku: (sold, sold * 25.0) for sku, (_, sold) in scenarios.items() if sold > 0})
    return run_engine(rows, velocity_df)


class TestKpisAndContract:
    def test_ca_p055_09_status_counts_sum_to_total(self, mixed_scenario_result):
        kpis = mixed_scenario_result["kpis"]
        assert kpis["totalSkusAnalisados"] == 9
        assert kpis["skusEmRupturaCritica"] == 1
        assert kpis["skusNecessitamReposicao"] == 3
        assert kpis["skusEstoqueSaudavel"] == 3
        assert kpis["skusEmOverstock"] == 2
        assert (kpis["skusEmRupturaCritica"] + kpis["skusNecessitamReposicao"]
                + kpis["skusEstoqueSaudavel"] + kpis["skusEmOverstock"]) == kpis["totalSkusAnalisados"]

    def test_ca_p054_08_total_investment_equals_sum_of_items(self, mixed_scenario_result):
        produtos = mixed_scenario_result["produtos"]
        kpis = mixed_scenario_result["kpis"]
        items_sum = sum(p["investimentoTotalItem"] for p in produtos)
        assert kpis["investimentoTotalSugerido"] == pytest.approx(items_sum, abs=0.01)
        assert kpis["investimentoTotalSugerido"] == pytest.approx((110 + 90 + 70 + 60) * 15.0, abs=0.01)

    def test_p055_4_overstock_capital_kpi(self, mixed_scenario_result):
        assert mixed_scenario_result["kpis"]["capitalImobilizadoOverstock"] == pytest.approx(450.0 + 4500.0)

    def test_p055_6_default_ordering(self, mixed_scenario_result):
        produtos = mixed_scenario_result["produtos"]
        keys = [(STATUS_DISPLAY_ORDER[p["status"]], ABC_DISPLAY_ORDER[p["curvaAbc"]], -p["vmd"]) for p in produtos]
        assert keys == sorted(keys)
        assert produtos[0]["status"] == "CRITICAL_STOCKOUT"
        assert produtos[-1]["status"] == "OVERSTOCK"

    def test_p056_items_have_only_contract_keys(self, mixed_scenario_result):
        for item in mixed_scenario_result["produtos"]:
            assert set(item.keys()) == EXPECTED_ITEM_KEYS
            assert not (REVOKED_ITEM_KEYS & set(item.keys()))
            assert "overstock_capital" not in item

    def test_p056_1_kpis_have_no_physical_lock_counter(self, mixed_scenario_result):
        kpis = mixed_scenario_result["kpis"]
        assert set(kpis.keys()) == EXPECTED_KPI_KEYS
        assert "skusLimitadosPorEspaco" not in kpis
        assert set(kpis["curvaADistribuicao"].keys()) == {"qtdItens", "percentualItens"}

    def test_display_rounding(self):
        item, _ = run_single(stock=50.44, sold_in_window=1)  # VMD 1/60
        assert item["vmd"] == 0.02
        assert item["estoqueAtual"] == 50.4

    def test_empty_catalog_returns_zeroed_kpis(self):
        result = run_engine([make_catalog_row(1, 10.0, supplier="X")], make_velocity({}), supplier_filter="NENHUM")
        assert result["produtos"] == []
        assert result["kpis"]["totalSkusAnalisados"] == 0
        assert result["kpis"]["investimentoTotalSugerido"] == 0.0


# ---------------------------------------------------------------------------
# P-047.1 + Curva ABC global (CA-10)
# ---------------------------------------------------------------------------
class TestSupplierFilterAndAbc:
    def test_abc_curve_thresholds(self):
        abc = classify_abc_curve({1: 800.0, 2: 150.0, 3: 50.0})
        assert abc == {1: "A", 2: "B", 3: "C"}

    def test_sales_lookup_defaults_for_unknown_sku(self):
        lookup = build_sales_lookup(make_velocity({1: (120.0, 3000.0)}))
        assert lookup.vmd_for(1) == pytest.approx(2.0)
        assert lookup.vmd_for(999) == 0.0
        assert lookup.abc_class_for(999) == "C"

    def test_ca_10_filter_keeps_global_abc(self):
        rows = [
            make_catalog_row(1, 50.0, supplier="APIS FLORA"),
            make_catalog_row(2, 50.0, supplier="HERBARIUM"),
            make_catalog_row(3, 50.0, supplier="HERBARIUM"),
        ]
        velocity_df = make_velocity({1: (120.0, 800.0), 2: (120.0, 150.0), 3: (120.0, 50.0)})
        unfiltered = by_code(run_engine(rows, velocity_df))
        filtered = run_engine(rows, velocity_df, supplier_filter="HERBARIUM")

        assert {p["codigo"] for p in filtered["produtos"]} == {2, 3}
        for item in filtered["produtos"]:
            assert item["curvaAbc"] == unfiltered[item["codigo"]]["curvaAbc"]
        assert unfiltered[2]["curvaAbc"] == "B"
        assert unfiltered[3]["curvaAbc"] == "C"
        assert filtered["kpis"]["totalSkusAnalisados"] == 2
        assert filtered["kpis"]["curvaADistribuicao"]["qtdItens"] == 0

    @pytest.mark.parametrize("token", [None, "", "TODOS", "ALL", "todos"], ids=lambda t: f"P-047.1-{t!r}")
    def test_p047_1_all_supplier_tokens_do_not_filter(self, token):
        rows = [make_catalog_row(1, 50.0, supplier="APIS FLORA"), make_catalog_row(2, 50.0, supplier="HERBARIUM")]
        result = run_engine(rows, make_velocity({1: (120.0, 100.0)}), supplier_filter=token)
        assert result["kpis"]["totalSkusAnalisados"] == 2

    def test_p047_1_filter_is_case_and_space_insensitive(self, sample_catalog_data, sample_sales_data):
        velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
        catalog = prepare_product_catalog(sample_catalog_data, "  apis flora ")
        result = calculate_inventory_replenishment(catalog, velocity_df, default_policy())
        assert len(result["produtos"]) == 1
        assert result["produtos"][0]["codigo"] == 101
        assert result["produtos"][0]["fornecedor"] == "APIS FLORA"


# ---------------------------------------------------------------------------
# Cenário de integração do contrato (seção 5.2) com vendas brutas
# ---------------------------------------------------------------------------
def test_contract_example_with_raw_sales(sample_catalog_data, sample_sales_data):
    velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
    catalog = prepare_product_catalog(sample_catalog_data, None)
    result = calculate_inventory_replenishment(catalog, velocity_df, default_policy())
    products = by_code(result)

    p101 = products[101]
    assert (p101["status"], p101["diasCobertura"]) == ("CRITICAL_STOCKOUT", 5.0)
    assert (p101["estoqueMinimo"], p101["estoqueMaximo"], p101["qtdSugeridaCompra"]) == (60, 120, 110)
    assert p101["investimentoTotalItem"] == pytest.approx(1650.0)

    p102 = products[102]
    assert (p102["status"], p102["statusLabel"]) == ("REORDER_NEEDED", "Abaixo do Mínimo")
    assert p102["qtdSugeridaCompra"] == 70

    p103 = products[103]
    assert (p103["status"], p103["diasCobertura"], p103["estoqueMaximo"]) == ("OVERSTOCK", 999.0, 0)
    assert result["kpis"]["capitalImobilizadoOverstock"] == pytest.approx(1500.0)
    assert result["kpis"]["investimentoTotalSugerido"] == pytest.approx(2350.0)


# ---------------------------------------------------------------------------
# Invariantes no domínio (DA-05) — chamadas diretas ao motor
# ---------------------------------------------------------------------------
class TestDomainPolicyValidation:
    @pytest.mark.parametrize(
        "kwargs,code",
        [
            ({"min_coverage_days": 60, "max_coverage_days": 60}, "INV-001"),
            ({"min_coverage_days": 50, "max_coverage_days": 45}, "INV-001"),
            ({"min_coverage_days": 20, "max_coverage_days": 40, "lead_time_days": 45}, "INV-002"),
        ],
        ids=["INV-001-igual", "INV-001-menor", "INV-002-lead-maior-que-max"],
    )
    def test_invalid_policy_never_reaches_engine(self, kwargs, code):
        with pytest.raises(InvalidReplenishmentPolicyError) as exc_info:
            default_policy(**kwargs)
        assert exc_info.value.code == code
