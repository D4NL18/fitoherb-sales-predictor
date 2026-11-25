"""D-7.1.16 / P-158..P-166 / P-173: o EvidenceBuilder de producao liga sazonalidade, preco, clientes perdidos,
ruptura e promocao; fonte ausente vira NAO_AVALIADO sem derrubar o diagnostico; chaves nao vazam precos (4.4)."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import FakeClock, collect_keys, mod

SKU, REFERENCE = 100, date(2026, 11, 10)
SCALE = 10_000
FIRST_MONTH = 2025 * 12  # jan/2025
MONTH_COUNT = 22  # ate out/2026
OCT_2026, JUL_2026 = 2026 * 12 + 9, 2026 * 12 + 6


def _series(overrides):
    qty, rev = [], []
    for offset in range(MONTH_COUNT):
        q, r = overrides.get(FIRST_MONTH + offset, (100, 15000))
        qty.append(q * SCALE)
        rev.append(r * SCALE)
    return qty, rev


def _snapshot():
    sales_mod = pytest.importorskip("src.modules.sales_trend.domain.sales_trend")
    mask = (1 << MONTH_COUNT) - 1
    qty, rev = _series({OCT_2026: (80, 12800)})
    flat_qty, flat_rev = _series({})
    series = {
        SKU: sales_mod.SkuSeries(quantity=tuple(qty), revenue=tuple(rev), movement_mask=mask),
        200: sales_mod.SkuSeries(quantity=tuple(flat_qty), revenue=tuple(flat_rev), movement_mask=mask),
    }
    monthly = sales_mod.MonthlySales(first_month=FIRST_MONTH, month_count=MONTH_COUNT, series=series,
                                     first_sale_date=date(2025, 1, 7))
    entry = lambda code, name, sup: sales_mod.TrendCatalogEntry(code, name, sup, name.lower())
    return SimpleNamespace(
        reference_date=REFERENCE, last_covered_day=date(2026, 11, 9), loaded_at=datetime.now(timezone.utc),
        monthly_sales=monthly, catalog={SKU: entry(SKU, "CREATINA A", "ALFA"), 200: entry(200, "CREATINA B", "BETA")},
        supplier_index={}, counts={})


class FakeSources:
    def __init__(self, **overrides):
        parcels = mod("domain.factor_parcels")
        adapter = mod("adapters.factor_adapter")
        self.seasonality_value = parcels.SeasonalityEvidence(
            True, "FORTE", None, {m: (1.0, "ALTA") for m in range(1, 13)} | {10: (0.9, "ALTA")})
        self.elasticity_value = adapter.ElasticityEvidence(-1.3, True, False, "ALTA")
        self.stock_value, self.promo_value, self.codes = 0.0, frozenset(), frozenset()
        self.__dict__.update(overrides)

    def seasonality(self, sku): return self.seasonality_value
    def elasticity(self, sku): return self.elasticity_value
    def current_stock(self, sku): return self.stock_value
    def lost_customer_codes(self): return self.codes
    def promotion_skus(self, start, end_exclusive): return self.promo_value


def _build(monkeypatch, sources, migration=None, window=3, metric="revenue"):
    st = mod("adapters.evidence_adapter")
    service = mod("service.insights_service")
    result = migration or mod("domain.ports").NotEvaluated("INDICE_AFINIDADE_INDISPONIVEL")
    cache = mod("service.migration_cache").MigrationCache(lambda key: result, FakeClock())
    aff = st.product_affinity_service
    neighbor = {"sku": "200", "description": "CREATINA B", "supplier": "BETA", "galleryCategory": "Suplementos",
                "currentPrice": 99.9, "affinityScore": 0.8, "sameSupplier": False}
    monkeypatch.setattr(aff, "get_product_affinities", lambda sku, top_k=20: {
        "category": "Cat", "galleryMatched": True, "meta": {}, "affinities": [neighbor]})
    monkeypatch.setattr(aff, "get_affinity_lookup_map", lambda *a, **k: {"100": {"200": 0.8}})
    monkeypatch.setattr(aff, "get_loaded_affinity_index", lambda *a, **k: {
        "meta": {"generatedAt": "g1"},
        "skus": {"100": {"primary_function": "creatina", "doc": "creatina ||| po puro monohidratada suplementos"}}})
    snapshot = _snapshot()
    builder = st.EvidenceBuilder(cache, sources, snapshot_provider=lambda: snapshot)
    query = service.InsightQuery(sku=SKU, metric=metric, window=window, base_month="2026-10", comparison_mode="point")
    return builder(query)


def _by_type(items):
    return {i["tipo"]: i for i in items}


def test_seasonal_and_price_parcels_are_evaluated(monkeypatch):
    cascade = _by_type(_build(monkeypatch, FakeSources()).data["cascata"])
    assert cascade["SAZONALIDADE"]["status"] == "AVALIADO" and cascade["SAZONALIDADE"]["detalhe"]["forca"] == "FORTE"
    price = cascade["PRECO"]
    assert price["status"] == "AVALIADO" and price["detalhe"]["variacao_valor_pct"] == pytest.approx(6.7)


def test_price_parcel_in_quantity_metric_uses_quantity_totals(monkeypatch):
    evidence = _build(monkeypatch, FakeSources(), metric="quantity")
    assert _by_type(evidence.data["cascata"])["PRECO"]["status"] == "AVALIADO"


def test_failed_sources_become_not_evaluated_without_breaking(monkeypatch):
    unavailable = mod("domain.ports").NotEvaluated("FONTE_INDISPONIVEL")
    sources = FakeSources(seasonality_value=unavailable, elasticity_value=unavailable, stock_value=unavailable,
                          promo_value=unavailable)
    evidence = _build(monkeypatch, sources)
    cascade, indicators = _by_type(evidence.data["cascata"]), _by_type(evidence.data["indicadores"])
    for tipo in ("SAZONALIDADE", "PRECO"):
        assert (cascade[tipo]["status"], cascade[tipo]["motivo_nao_avaliado"]) == ("NAO_AVALIADO", "FONTE_INDISPONIVEL")
    for tipo in ("RUPTURA", "PROMOCAO"):
        assert indicators[tipo]["status"] == "NAO_AVALIADO"


def test_stockout_and_promotion_indicators(monkeypatch):
    sources = FakeSources(stock_value=0.0, promo_value=frozenset({100}))
    indicators = _by_type(_build(monkeypatch, sources).data["indicadores"])
    assert indicators["RUPTURA"]["status"] == "AVALIADO" and indicators["RUPTURA"]["valor"] is None
    assert indicators["PROMOCAO"]["motivo_sem_efeito"] == "SEM_PROMOCAO"  # promocao nas duas janelas: nada mudou


def test_lost_customers_parcel_comes_from_migration_snapshot(monkeypatch):
    scaling = mod("domain.migration_scaling")
    snapshot_cls = mod("adapters.migration_adapter").TrendMigrationSnapshot
    migration = snapshot_cls(migration=SimpleNamespace(pair_flows={}),
                             lost_by_sku={"100": scaling.LostCustomersAggregate(count=4, revenue=500.0, quantity=5.0)})
    lost = _by_type(_build(monkeypatch, FakeSources(), migration=migration).data["cascata"])["CLIENTES_PERDIDOS"]
    assert lost["status"] == "AVALIADO" and lost["detalhe"]["clientes_perdidos_qtd"] == 4


def test_lost_customers_old_base_month_is_not_evaluated(monkeypatch):
    snapshot_cls = mod("adapters.migration_adapter").TrendMigrationSnapshot
    migration = snapshot_cls(migration=SimpleNamespace(pair_flows={}), lost_by_sku={},
                             lost_unavailable_reason="MES_BASE_ANTIGO")
    lost = _by_type(_build(monkeypatch, FakeSources(), migration=migration).data["cascata"])["CLIENTES_PERDIDOS"]
    assert (lost["status"], lost["motivo_nao_avaliado"]) == ("NAO_AVALIADO", "MES_BASE_ANTIGO")


def test_gallery_function_and_description_are_wired(monkeypatch):
    produto = _build(monkeypatch, FakeSources()).data["produto"]
    assert produto["funcao_primaria"] == "creatina"
    assert produto["descricao_galeria"] == "po puro monohidratada suplementos"


def test_no_price_named_keys_leak_in_public_data(monkeypatch):
    """Contrato 4.4: nenhuma chave com 'preco' em qualquer resposta (afins e detalhe do fator de preco)."""
    evidence = _build(monkeypatch, FakeSources())
    public = mod("service.insights_service").to_camel(
        {"afins": evidence.data["afins"], "cascata": evidence.data["cascata"]})
    assert evidence.data["afins"], "grupo afim deve existir no cenario"
    assert not [k for k in collect_keys(public) if "preco" in k.lower()]
    assert evidence.data["afins"][0]["valor_venda_atual"] == 99.9


def test_migration_builder_passes_lost_codes_only_for_recent_base_month(monkeypatch):
    st = mod("adapters.evidence_adapter")
    snapshot, captured = _snapshot(), {}
    monkeypatch.setattr(st, "build_migration_snapshot", lambda **kw: captured.update(kw) or "snap")
    build = st.make_migration_builder(lambda: snapshot, FakeSources(codes=frozenset({7})))
    build(("point", 3, "2026-10", REFERENCE.isoformat(), "g"))
    assert captured["lost_customer_codes"] == frozenset({7})
    build(("point", 3, "2026-08", REFERENCE.isoformat(), "g"))
    assert captured["lost_customer_codes"] == frozenset()
    assert captured["lost_unavailable_reason"] == "MES_BASE_ANTIGO"
