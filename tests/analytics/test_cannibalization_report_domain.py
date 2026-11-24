"""
Testes Unitários de Domínio (TDD First — v2): Relatório de Canibalização por Migração
de Clientes e Equilíbrio de Preço (Fase F6 v2).

Regras cobertas: P-128 a P-137; ADR-007 (v2); LGPD-CAN-01..06.

Interface de Domínio v2 esperada em `src/modules/analytics/domain/cannibalization.py`:
- Constantes:
  ALLOWED_WINDOW_DAYS = (30, 60, 90)
  DEFAULT_WINDOW_DAYS = 90
  RETURN_OPERATION_PATTERN = "DEVOLU%"
  MIN_PRE_REVENUE = 500.0
  DEFAULT_MIN_DROP_PCT = 5.0
  DEFAULT_MIN_MIGRATED_CLIENTS = 3
  COST_FALLBACK_RATIO = 0.60
  PRICE_GAP_THRESHOLD_PCT = 3.0
  GAP_REDUCTION_TARGET = 0.40
  MIN_CONTRIBUTION_MARGIN_PCT = 0.20
  MAX_CANNIBAL_PRICE_HIKE_PCT = 0.12
  MAX_CANNIBALIZERS_PER_VICTIM = 10
  CACHE_TTL_HOURS = 6
- Funções puras:
  - `compute_directional_migration(customer_sku_rows, catalog) -> MigrationSnapshot`
  - `calculate_price_equilibrium(victim_price, victim_cost, cannibal_price, cannibal_cost, migrated_revenue, victim_stock=0) -> PriceEquilibriumResult`
  - `build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3, category=None, supplier=None, mechanism=None, search=None) -> CannibalizationReportResult`
  - `build_cannibalization_sku_detail(sku, snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3) -> CannibalizationDetailResult`
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from typing import Any, Dict, List

import pytest

from src.modules.analytics.domain import cannibalization as dom
from src.modules.analytics.domain.exceptions import CannibalizationProductNotFoundError


# ---------------------------------------------------------------------------
# Helpers determinísticos de massa sintética (sem I/O)
# ---------------------------------------------------------------------------

def _make_catalog() -> Dict[str, Dict[str, Any]]:
    return {
        "100235": {
            "sku": "100235",
            "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
            "category": "EXTRATOS",
            "supplier": "FITOHERB",
            "active": True,
            "current_stock": 185,
            "last_cost": 16.00,
            "current_price": 30.00,
        },
        "100234": {
            "sku": "100234",
            "description": "EXTRATO DE PROPOLIS VERDE 30ML",
            "category": "EXTRATOS",
            "supplier": "FITOHERB",
            "active": True,
            "current_stock": 340,
            "last_cost": 13.50,
            "current_price": 22.00,
        },
        "100290": {
            "sku": "100290",
            "description": "EXTRATO DE PROPOLIS COMPOSTO 30ML",
            "category": "EXTRATOS",
            "supplier": "HERBARIUM",
            "active": True,
            "current_stock": 95,
            "last_cost": None,  # Força fallback 60%
            "current_price": 24.00,
        },
        "200100": {
            "sku": "200100",
            "description": "CHA VERDE ORGANICO 60G",
            "category": "CHAS",
            "supplier": "NATUVIDA",
            "active": True,
            "current_stock": 200,
            "last_cost": 8.00,
            "current_price": 18.00,
        },
    }


def _row(
    customer_code: int,
    sku: str,
    pre_rev: float,
    cur_rev: float,
    pre_qty: float = 10.0,
    cur_qty: float = 10.0,
) -> Dict[str, Any]:
    return {
        "customer_code": customer_code,
        "sku": sku,
        "pre_qty": pre_qty,
        "pre_rev": pre_rev,
        "cur_qty": cur_qty,
        "cur_rev": cur_rev,
    }


def _serialize_no_pii_check(obj: Any) -> str:
    if is_dataclass(obj):
        return json.dumps(asdict(obj), default=str)
    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# 1. Constantes Canônicas (P-128..P-137)
# ---------------------------------------------------------------------------


def test_domain_constants_match_v2_specification():
    """T-CAN-DOM-01: Constantes de domínio v2 devem estar declaradas sem números mágicos."""
    # Arrange / Act / Assert
    assert dom.ALLOWED_WINDOW_DAYS == (30, 60, 90)
    assert dom.DEFAULT_WINDOW_DAYS == 90
    assert dom.RETURN_OPERATION_PATTERN == "DEVOLU%"
    assert dom.MIN_PRE_REVENUE == pytest.approx(500.0)
    assert dom.DEFAULT_MIN_DROP_PCT == pytest.approx(5.0)
    assert dom.DEFAULT_MIN_MIGRATED_CLIENTS == 3
    assert dom.COST_FALLBACK_RATIO == pytest.approx(0.60)
    assert dom.PRICE_GAP_THRESHOLD_PCT == pytest.approx(3.0)
    assert dom.GAP_REDUCTION_TARGET == pytest.approx(0.40)
    assert dom.MIN_CONTRIBUTION_MARGIN_PCT == pytest.approx(0.20)
    assert dom.MAX_CANNIBAL_PRICE_HIKE_PCT == pytest.approx(0.12)
    assert dom.MAX_CANNIBALIZERS_PER_VICTIM == 10
    assert dom.CACHE_TTL_HOURS == 6


# ---------------------------------------------------------------------------
# 2. Migração Direcional Líquida e Conservação de Fluxo (P-130, P-131)
# ---------------------------------------------------------------------------


def test_directional_migration_conservative_flow_no_double_counting():
    """
    T-CAN-DOM-02 (P-130.2): Cliente reduz 1 item A em R$ 100 e aumenta 2 itens B (+80) e C (+120)
    na mesma categoria. Fluxo total migrado de A deve ser conservado (<= L_{c,A} = 100),
    alocado proporcionalmente: 100 * (80/200) = 40 para B e 100 * (120/200) = 60 para C.
    """
    # Arrange
    catalog = _make_catalog()
    rows = [
        _row(customer_code=1, sku="100235", pre_rev=200.0, cur_rev=100.0),  # L_A = 100
        _row(customer_code=1, sku="100234", pre_rev=20.0, cur_rev=100.0),   # G_B = 80
        _row(customer_code=1, sku="100290", pre_rev=0.0, cur_rev=120.0),    # G_C = 120
    ]

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)

    # Assert
    flow_ab = snapshot.pair_flows[("100235", "100234")]
    flow_ac = snapshot.pair_flows[("100235", "100290")]
    assert flow_ab.gross_rev == pytest.approx(40.0, abs=1e-6)
    assert flow_ac.gross_rev == pytest.approx(60.0, abs=1e-6)
    assert flow_ab.gross_rev + flow_ac.gross_rev <= 100.0 + 1e-9
    assert flow_ab.net_rev == pytest.approx(40.0, abs=1e-6)
    assert flow_ac.net_rev == pytest.approx(60.0, abs=1e-6)
    assert flow_ab.net_clients == 1
    assert flow_ac.net_clients == 1


def test_directional_migration_discounts_symmetric_reverse_flow():
    """
    T-CAN-DOM-03 (P-131.1 / C-02): Fluxo bidirecional simétrico (4 clientes A->B e 4 clientes B->A
    com mesmo valor) resulta em net_clients = 0 e net_rev = 0 (ruído anulado).
    """
    # Arrange
    catalog = _make_catalog()
    rows: List[Dict[str, Any]] = []
    # 4 clientes migram A -> B (R$ 200 cada)
    for cid in range(1, 5):
        rows.append(_row(cid, "100235", pre_rev=300.0, cur_rev=100.0))
        rows.append(_row(cid, "100234", pre_rev=0.0, cur_rev=200.0))
    # 4 clientes migram B -> A (R$ 200 cada)
    for cid in range(5, 9):
        rows.append(_row(cid, "100234", pre_rev=300.0, cur_rev=100.0))
        rows.append(_row(cid, "100235", pre_rev=0.0, cur_rev=200.0))

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)
    report = dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3)

    # Assert
    flow_ab = snapshot.pair_flows.get(("100235", "100234"))
    if flow_ab is not None:
        assert flow_ab.net_clients == 0
        assert flow_ab.net_rev == pytest.approx(0.0)
    assert report.victims == []


def test_directional_migration_ignores_cross_category_and_truncates_negative_returns():
    """
    T-CAN-DOM-04 (P-128.2 / P-130):
    - Migração entre categorias distintas (EXTRATOS -> CHAS) não gera fluxo.
    - Saldos líquidos negativos (devoluções > vendas) são truncados em 0.0.
    """
    # Arrange
    catalog = _make_catalog()
    rows = [
        # Cliente 1 cai em EXTRATOS (100235) e sobe em CHAS (200100) -> categorias distintas
        _row(1, "100235", pre_rev=600.0, cur_rev=-50.0),  # cur_rev negativo truncado para 0.0
        _row(1, "200100", pre_rev=0.0, cur_rev=600.0),
    ]

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)

    # Assert
    assert ("100235", "200100") not in snapshot.pair_flows
    assert snapshot.sku_totals["100235"].cur_rev == pytest.approx(0.0)
    assert snapshot.sku_totals["100235"].pre_rev == pytest.approx(600.0)


def test_directional_migration_prunes_by_min_migrated_clients():
    """
    T-CAN-DOM-05 (P-131.2): Par com net_clients = 2 (3 diretos - 1 reverso) é podado
    quando min_migrated_clients = 3, mas aceito quando min_migrated_clients = 2.
    """
    # Arrange
    catalog = _make_catalog()
    rows: List[Dict[str, Any]] = []
    # 3 clientes A -> B (R$ 300 cada)
    for cid in range(1, 4):
        rows.append(_row(cid, "100235", pre_rev=400.0, cur_rev=100.0))
        rows.append(_row(cid, "100234", pre_rev=0.0, cur_rev=300.0))
    # 1 cliente B -> A (R$ 100)
    rows.append(_row(99, "100234", pre_rev=200.0, cur_rev=100.0))
    rows.append(_row(99, "100235", pre_rev=0.0, cur_rev=100.0))

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)
    report_strict = dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3)
    report_relaxed = dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=2)

    # Assert
    assert report_strict.victims == []
    assert len(report_relaxed.victims) == 1
    victim = report_relaxed.victims[0]
    assert victim.sku == "100235"
    assert victim.top_cannibal.sku == "100234"
    assert victim.top_cannibal.migrated_clients == 2


# ---------------------------------------------------------------------------
# 3. Elegibilidade da Vítima e Quantificação (P-129, P-132)
# ---------------------------------------------------------------------------


def test_victim_eligibility_enforces_min_pre_revenue_500_and_drop_pct():
    """
    T-CAN-DOM-06 (P-129.2, P-129.3): SKU com pre_revenue < 500 ou queda < min_drop_pct
    não é reportado como vítima mesmo com >= 3 clientes migrando.
    """
    # Arrange
    catalog = _make_catalog()
    # Caso A: pre_revenue = 450 (< 500), 4 clientes migrando
    rows_low_rev: List[Dict[str, Any]] = []
    for cid in range(1, 5):
        rows_low_rev.append(_row(cid, "100235", pre_rev=112.5, cur_rev=12.5))  # total pre = 450
        rows_low_rev.append(_row(cid, "100234", pre_rev=0.0, cur_rev=100.0))

    # Caso B: pre_revenue = 1000, queda de apenas 3% (< 5%)
    rows_low_drop: List[Dict[str, Any]] = []
    for cid in range(1, 5):
        rows_low_drop.append(_row(cid, "100235", pre_rev=250.0, cur_rev=242.5))  # drop = 30 (3%)
        rows_low_drop.append(_row(cid, "100234", pre_rev=0.0, cur_rev=7.5))

    # Act
    snap_low_rev = dom.compute_directional_migration(rows_low_rev, catalog)
    rep_low_rev = dom.build_cannibalization_report(snap_low_rev, catalog, min_drop_pct=5.0, min_migrated_clients=3)

    snap_low_drop = dom.compute_directional_migration(rows_low_drop, catalog)
    rep_low_drop = dom.build_cannibalization_report(snap_low_drop, catalog, min_drop_pct=5.0, min_migrated_clients=3)

    # Assert
    assert rep_low_rev.victims == []
    assert rep_low_drop.victims == []


def test_cannibalized_revenue_capped_at_revenue_drop_and_kpis_consolidated():
    """
    T-CAN-DOM-07 (P-132.1..4):
    - cannibalized_revenue = min(revenue_drop, sum(net_rev)).
    - Quando novos clientes entram em A parcialmente compensando a queda, sum(net_rev) pode
      superar revenue_drop líquido do SKU, e o cap em revenue_drop DEVE ser respeitado.
    - cannibalized_revenue_pct e drop_explained_pct calculados corretamente.
    """
    # Arrange
    catalog = _make_catalog()
    rows: List[Dict[str, Any]] = []
    # 4 clientes migram R$ 200 cada de 100235 -> 100234 (sum net_rev = 800)
    for cid in range(1, 5):
        rows.append(_row(cid, "100235", pre_rev=250.0, cur_rev=50.0))
        rows.append(_row(cid, "100234", pre_rev=0.0, cur_rev=200.0))
    # 1 cliente novo compra R$ 500 de 100235 em CUR -> pre_total=1000, cur_total=700, revenue_drop=300
    rows.append(_row(50, "100235", pre_rev=0.0, cur_rev=500.0))

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)
    report = dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3)

    # Assert
    assert len(report.victims) == 1
    victim = report.victims[0]
    assert victim.pre_revenue == pytest.approx(1000.0)
    assert victim.cur_revenue == pytest.approx(700.0)
    assert victim.revenue_drop == pytest.approx(300.0)
    assert victim.cannibalized_revenue == pytest.approx(300.0)  # min(300, 800)
    assert victim.cannibalized_revenue_pct == pytest.approx(30.0)  # 300 / 1000 * 100
    assert victim.drop_explained_pct == pytest.approx(100.0)
    assert report.kpis.total_victims == 1
    assert report.kpis.total_cannibalized_revenue == pytest.approx(300.0)
    assert report.kpis.avg_cannibalized_revenue_pct == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# 4. Motor de Equilíbrio de Preço e Mecanismos (P-133, P-134, P-135)
# ---------------------------------------------------------------------------


def test_price_equilibrium_destroys_margin_closes_gap_40_pct():
    """
    T-CAN-DOM-08 (P-133, P-134.1, P-135.2 / C-03):
    Vítima P_A=30, C_A=16 (M_u=14, m=46.67%, floor=20.00);
    Canibalizador P_B=22, C_B=13.50 (M_u=8.50, m=38.64%, cap=24.64).
    delta_P = 8.0, 40% = 3.20 -> -1.60 na vítima (28.40), +1.60 no canibalizador (23.60).
    """
    # Arrange / Act
    eq = dom.calculate_price_equilibrium(
        victim_price=30.00,
        victim_cost=16.00,
        cannibal_price=22.00,
        cannibal_cost=13.50,
        migrated_revenue=3180.50,
    )

    # Assert
    assert eq.victim_cost_fallback_used is False
    assert eq.cannibal_cost_fallback_used is False
    assert eq.price_gap_pct == pytest.approx((30.0 - 22.0) / 22.0 * 100.0, abs=0.05)
    assert eq.mechanism == "PRECO_MENOR_DESTROI_MARGEM"
    assert eq.net_margin_impact < 0.0
    assert eq.victim_margin_floor_price == pytest.approx(20.00, abs=0.01)
    assert eq.suggested_victim_price == pytest.approx(28.40, abs=0.01)
    assert eq.suggested_cannibal_price == pytest.approx(23.60, abs=0.01)
    assert eq.projected_price_gap_pct < eq.price_gap_pct
    assert len(eq.action_summary) > 10


def test_price_equilibrium_margin_preserved_mechanism():
    """
    T-CAN-DOM-09 (P-134.2, P-135.3):
    Vítima P_A=30, C_A=21 (M_u=9, m=30%); Canibalizador P_B=24, C_B=12 (M_u=12, m=50%).
    priceGapPct = 25% (> 3%), mas M_u_B >= M_u_A e m_B >= m_A -> PRECO_MENOR_MARGEM_PRESERVADA.
    """
    # Arrange / Act
    eq = dom.calculate_price_equilibrium(
        victim_price=30.00,
        victim_cost=21.00,
        cannibal_price=24.00,
        cannibal_cost=12.00,
        migrated_revenue=1000.00,
    )

    # Assert
    assert eq.mechanism == "PRECO_MENOR_MARGEM_PRESERVADA"
    assert eq.net_margin_impact >= 0.0
    # P_floor_A = 21 / 0.8 = 26.25; P_A - 0.25 * 6 = 28.50; P_B + 0.15 * 6 = 24.90
    assert eq.suggested_victim_price == pytest.approx(28.50, abs=0.01)
    assert eq.suggested_cannibal_price == pytest.approx(24.90, abs=0.01)


def test_price_equilibrium_value_migration_keeps_prices():
    """
    T-CAN-DOM-10 (P-134.3, P-135.4):
    Quando priceGapPct <= 3.0% (ex.: P_A=25, P_B=28, gap=-10.7%), classifica MIGRACAO_POR_VALOR
    e mantém P_A* = P_A e P_B* = P_B.
    """
    # Arrange / Act
    eq = dom.calculate_price_equilibrium(
        victim_price=25.00,
        victim_cost=14.00,
        cannibal_price=28.00,
        cannibal_cost=15.00,
        migrated_revenue=1500.00,
        victim_stock=0,
    )

    # Assert
    assert eq.price_gap_pct <= 3.0
    assert eq.mechanism == "MIGRACAO_POR_VALOR"
    assert eq.suggested_victim_price == pytest.approx(25.00, abs=0.01)
    assert eq.suggested_cannibal_price == pytest.approx(28.00, abs=0.01)
    assert eq.action_summary


def test_price_equilibrium_cost_fallback_60_pct():
    """
    T-CAN-DOM-11 (P-133.3 / C-04):
    Quando custo é None, <= 0 ou >= preço, aplica fallback de 60% do preço (margem 40%)
    e marca cost_fallback_used = True.
    """
    # Arrange / Act
    eq_none = dom.calculate_price_equilibrium(
        victim_price=50.00,
        victim_cost=None,
        cannibal_price=35.00,
        cannibal_cost=40.00,  # >= preço -> fallback
        migrated_revenue=1000.00,
    )

    # Assert
    assert eq_none.victim_cost_fallback_used is True
    assert eq_none.cannibal_cost_fallback_used is True
    assert eq_none.victim_unit_cost == pytest.approx(30.00, abs=0.01)
    assert eq_none.victim_margin_pct == pytest.approx(40.0, abs=0.05)
    assert eq_none.cannibal_unit_cost == pytest.approx(21.00, abs=0.01)
    assert eq_none.cannibal_margin_pct == pytest.approx(40.0, abs=0.05)


def test_price_equilibrium_respects_victim_margin_floor_20_and_cannibal_cap_12():
    """
    T-CAN-DOM-12 (P-135.1, P-135.2):
    Garante que o preço sugerido da vítima nunca fique abaixo do piso de margem 20%
    (C_ef / 0.80) e o canibalizador nunca suba mais que +12% (P_B * 1.12).
    """
    # Arrange: vítima já muito próxima do piso de 20% (P_A=100, C_A=79 -> floor=98.75)
    # e canibalizador muito barato (P_B=50, C_B=45 -> cap=56.00; delta_P=50, 40%=20)
    # Act
    eq = dom.calculate_price_equilibrium(
        victim_price=100.00,
        victim_cost=79.00,
        cannibal_price=50.00,
        cannibal_cost=45.00,
        migrated_revenue=2000.00,
    )

    # Assert
    assert eq.mechanism == "PRECO_MENOR_DESTROI_MARGEM"
    assert eq.victim_margin_floor_price == pytest.approx(98.75, abs=0.01)
    assert eq.suggested_victim_price == pytest.approx(98.75, abs=0.01)
    assert eq.suggested_cannibal_price == pytest.approx(56.00, abs=0.01)  # cap +12%


def test_price_equilibrium_handles_zero_prices_safely():
    """T-CAN-DOM-13 (Edge Case): Preço zero no canibalizador não causa ZeroDivisionError."""
    # Arrange / Act
    eq = dom.calculate_price_equilibrium(
        victim_price=30.00,
        victim_cost=15.00,
        cannibal_price=0.0,
        cannibal_cost=None,
        migrated_revenue=500.0,
    )

    # Assert
    assert eq.price_gap_pct == pytest.approx(0.0)
    assert eq.projected_price_gap_pct == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 5. Detalhe por SKU e Zero PII em Dataclasses (P-136.2, LGPD-CAN-02/04)
# ---------------------------------------------------------------------------


def test_sku_detail_not_found_raises_can_001_and_non_victim_returns_false():
    """
    T-CAN-DOM-14 (P-136.2 / C-06 / C-07):
    - SKU inexistente no catálogo ativo lança CannibalizationProductNotFoundError (CAN-001).
    - SKU ativo sem canibalização retorna is_cannibalized=False e cannibalizers=[].
    """
    # Arrange
    catalog = _make_catalog()
    rows = [_row(1, "200100", pre_rev=800.0, cur_rev=900.0)]
    snapshot = dom.compute_directional_migration(rows, catalog)

    # Act / Assert (404)
    with pytest.raises(CannibalizationProductNotFoundError):
        dom.build_cannibalization_sku_detail("999999", snapshot, catalog)

    # Act / Assert (200 não canibalizado)
    detail = dom.build_cannibalization_sku_detail("200100", snapshot, catalog)
    assert detail.is_cannibalized is False
    assert detail.victim.sku == "200100"
    assert detail.victim.cannibalized_revenue == pytest.approx(0.0)
    assert list(detail.cannibalizers) == []


def test_zero_customer_code_in_domain_snapshot_report_and_detail():
    """
    T-CAN-DOM-15 (LGPD-CAN-02 / LGPD-CAN-04 / LGPD-CAN-05):
    Nenhum identificador de cliente (`Cod Cliente` / `customer_code` / valor numérico do cliente)
    pode existir no snapshot cacheável, no relatório global ou no detalhe por SKU.
    """
    # Arrange
    catalog = _make_catalog()
    secret_customer_ids = [8877661, 8877662, 8877663, 8877664]
    rows: List[Dict[str, Any]] = []
    for cid in secret_customer_ids:
        rows.append(_row(cid, "100235", pre_rev=400.0, cur_rev=100.0))
        rows.append(_row(cid, "100234", pre_rev=0.0, cur_rev=300.0))

    # Act
    snapshot = dom.compute_directional_migration(rows, catalog)
    report = dom.build_cannibalization_report(snapshot, catalog)
    detail = dom.build_cannibalization_sku_detail("100235", snapshot, catalog)

    # Assert
    for artifact in (snapshot, report, detail):
        serialized = _serialize_no_pii_check(artifact).lower()
        assert "customer_code" not in serialized
        assert "cod cliente" not in serialized
        assert "customercode" not in serialized
        for cid in secret_customer_ids:
            assert str(cid) not in serialized


def test_cross_supplier_equal_weight_and_ignores_unrelated_same_supplier_products():
    """
    T-CAN-DOM-16 (P-130 Agnóstico de Fornecedor):
    - Produtos da mesma família (ex.: CREATINA 300G / 500G) de fornecedores e `Tipo`
      distintos (LINHA MAX TITANIUM vs LINHA INTEGRALMEDICA) competem com peso estritamente igual.
    - Produtos de famílias distintas do MESMO fornecedor (ex.: CREATINA vs WHEY da MAX TITANIUM)
      não geram fluxo falso de canibalização.
    """
    catalog = {
        "770019": {
            "sku": "770019",
            "description": "CREATINA 300G",
            "category": "LINHA MAX TITANIUM",
            "supplier": "MAX TITANIUM",
            "active": True,
            "current_stock": 100,
            "last_cost": 30.00,
            "current_price": 55.00,
        },
        "770145": {
            "sku": "770145",
            "description": "CREATINA POTE 500G",
            "category": "LINHA MAX TITANIUM",
            "supplier": "MAX TITANIUM",
            "active": True,
            "current_stock": 80,
            "last_cost": 40.00,
            "current_price": 62.00,
        },
        "111940": {
            "sku": "111940",
            "description": "CREATINA 300 GRS",
            "category": "LINHA INTEGRALMEDICA",
            "supplier": "INTEGRALMEDICA",
            "active": True,
            "current_stock": 120,
            "last_cost": 26.00,
            "current_price": 45.00,
        },
        "112246": {
            "sku": "112246",
            "description": "CREATINA HARDCORE 500G POTE",
            "category": "LINHA INTEGRALMEDICA",
            "supplier": "INTEGRALMEDICA",
            "active": True,
            "current_stock": 90,
            "last_cost": 35.00,
            "current_price": 58.00,
        },
        "770999": {
            "sku": "770999",
            "description": "WHEY 100% HD 900G CHOCOLATE REFIL",
            "category": "LINHA MAX TITANIUM",
            "supplier": "MAX TITANIUM",
            "active": True,
            "current_stock": 50,
            "last_cost": 60.00,
            "current_price": 110.00,
        },
    }

    rows: List[Dict[str, Any]] = []
    # 4 clientes caem R$ 300 na CREATINA 300G (Max Titanium) e sobem R$ 100 em cada uma das 3 outras creatinas
    # (1 da Max Titanium e 2 da Integralmedica) + R$ 500 em WHEY da Max Titanium (nao deve capturar fluxo).
    for cid in range(1, 5):
        rows.append(_row(cid, "770019", pre_rev=300.0, cur_rev=0.0))
        rows.append(_row(cid, "770145", pre_rev=0.0, cur_rev=100.0))
        rows.append(_row(cid, "111940", pre_rev=0.0, cur_rev=100.0))
        rows.append(_row(cid, "112246", pre_rev=0.0, cur_rev=100.0))
        rows.append(_row(cid, "770999", pre_rev=0.0, cur_rev=500.0))

    snapshot = dom.compute_directional_migration(rows, catalog)
    report = dom.build_cannibalization_report(snapshot, catalog, min_drop_pct=5.0, min_migrated_clients=3)

    assert ("770019", "770999") not in snapshot.pair_flows
    assert len(report.victims) == 1
    victim = report.victims[0]
    assert victim.sku == "770019"
    assert len(victim.cannibalizers) == 3

    by_sku = {c.sku: c for c in victim.cannibalizers}
    # Mesmo peso entre fornecedores: cada um dos 3 recebe exatamente R$ 400 (1/3 de R$ 1200)
    assert by_sku["770145"].migrated_revenue == pytest.approx(400.0, abs=1e-2)
    assert by_sku["111940"].migrated_revenue == pytest.approx(400.0, abs=1e-2)
    assert by_sku["112246"].migrated_revenue == pytest.approx(400.0, abs=1e-2)
    assert by_sku["111940"].supplier == "INTEGRALMEDICA"
    assert by_sku["112246"].supplier == "INTEGRALMEDICA"
