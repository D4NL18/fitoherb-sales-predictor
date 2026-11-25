"""T-7.1.14 / D-7.1.15 / D-7.1.16: adaptadores das demais fontes e `evidence_cache`, sempre com dubles (sem SQL)."""
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import FakeClock, mod


def adapter():
    return mod("adapters.factor_adapter")


def _cache(clock=None, **kw):
    return mod("service.evidence_cache").EvidenceCache(clock or FakeClock(), **kw)


# ----------------------------------------------------------------------------- evidence_cache
def test_evidence_cache_hits_until_ttl_and_defaults():
    clock, calls = FakeClock(), []
    cache = _cache(clock)
    assert (cache.max_entries, cache.ttl_hours) == (200, 6)
    build = lambda: calls.append(1) or "v"
    cache.get_or_build("k", build), cache.get_or_build("k", build)
    assert len(calls) == 1
    clock.advance(6 * 3600)
    cache.get_or_build("k", build)
    assert len(calls) == 2


def test_evidence_cache_is_lru_and_does_not_store_failures():
    cache = _cache(max_entries=2)
    for key in ("a", "b", "a", "c"):
        cache.get_or_build(key, lambda key=key: key)
    assert cache.keys() == ["a", "c"]

    def boom():
        raise RuntimeError()

    with pytest.raises(RuntimeError):
        cache.get_or_build("x", boom)
    assert "x" not in cache.keys()


# ----------------------------------------------------------------------------- get_cannibalization_catalog
def test_get_cannibalization_catalog_is_public_and_cached(monkeypatch):
    service = pytest.importorskip("src.modules.analytics.service.analytics_service")
    repo = pytest.importorskip("src.modules.analytics.repository.sales_repository")
    service.reset_cannibalization_report_cache()
    calls = []
    monkeypatch.setattr(repo, "fetch_cannibalization_catalog", lambda: calls.append(1) or {"5": {"current_stock": 3}})
    assert service.get_cannibalization_catalog() == {"5": {"current_stock": 3}}
    service.get_cannibalization_catalog()
    assert len(calls) == 1
    service.reset_cannibalization_report_cache()


# ----------------------------------------------------------------------------- traducao de falhas
def _failing(exc):
    def reader(*_args):
        raise exc
    return reader


def _errors():
    analytics = pytest.importorskip("src.modules.analytics.repository.errors")
    trend = pytest.importorskip("src.modules.sales_trend.repository.errors")
    return analytics.AnalyticsDataSourceError(), trend.TrendDataSourceError()


def test_every_source_failure_becomes_not_evaluated():
    NotEvaluated = mod("domain.ports").NotEvaluated
    for exc in _errors():
        sources = adapter().FactorSources(
            _cache(), seasonality_reader=_failing(exc), elasticity_reader=_failing(exc),
            churn_reader=_failing(exc), stock_reader=_failing(exc), promotion_reader=_failing(exc))
        assert sources.seasonality(5) == NotEvaluated("FONTE_INDISPONIVEL")
        assert sources.elasticity(5) == NotEvaluated("FONTE_INDISPONIVEL")
        assert sources.lost_customer_codes() == NotEvaluated("FONTE_INDISPONIVEL")
        assert sources.current_stock(5) == NotEvaluated("FONTE_INDISPONIVEL")
        assert sources.promotion_skus(date(2026, 1, 1), date(2026, 2, 1)) == NotEvaluated("FONTE_INDISPONIVEL")


# ----------------------------------------------------------------------------- leituras felizes
def test_seasonality_maps_response_to_evidence():
    response = SimpleNamespace(data=SimpleNamespace(
        elegivel=True, forca="FORTE", motivo_insuficiencia=None,
        serie_mensal=[SimpleNamespace(mes=7, indice=0.8, confianca="ALTA"),
                      SimpleNamespace(mes=10, indice=1.2, confianca="MEDIA")]))
    sources = adapter().FactorSources(_cache(), seasonality_reader=lambda sku: response)
    found = sources.seasonality(5)
    assert found.eligible and found.strength == "FORTE" and found.monthly == {7: (0.8, "ALTA"), 10: (1.2, "MEDIA")}


def test_elasticity_is_cached_per_sku():
    calls = []
    result = SimpleNamespace(coefficient=-1.3, is_reliable=True, fallback_applied=False, confidence_level="ALTA")
    sources = adapter().FactorSources(_cache(), elasticity_reader=lambda sku: calls.append(sku) or result)
    first, second = sources.elasticity(5), sources.elasticity(5)
    assert first == second and calls == [5] and first.elasticity == -1.3 and first.confidence_level == "ALTA"


def test_lost_customer_codes_filters_statuses_and_returns_frozenset():
    customers = [SimpleNamespace(customer_code=1, status="EM_RISCO"), SimpleNamespace(customer_code=2, status="ATIVO"),
                 SimpleNamespace(customer_code=3, status="INATIVO_RECUPERACAO")]
    sources = adapter().FactorSources(_cache(), churn_reader=lambda: customers)
    codes = sources.lost_customer_codes()
    assert codes == frozenset({1, 3}) and isinstance(codes, frozenset)


def test_current_stock_reads_catalog_by_sku_text():
    sources = adapter().FactorSources(_cache(), stock_reader=lambda: {"5": {"current_stock": 0}})
    assert sources.current_stock(5) == 0.0
    missing = adapter().FactorSources(_cache(), stock_reader=lambda: {}).current_stock(5)
    assert missing == mod("domain.ports").NotEvaluated("FONTE_INDISPONIVEL")


def test_promotion_skus_uses_inclusive_end_and_caches_by_window():
    calls = []
    sources = adapter().FactorSources(_cache(), promotion_reader=lambda a, b: calls.append((a, b)) or {"5", "7"})
    first = sources.promotion_skus(date(2026, 9, 1), date(2026, 10, 1))
    sources.promotion_skus(date(2026, 9, 1), date(2026, 10, 1))
    assert first == frozenset({5, 7}) and calls == [(date(2026, 9, 1), date(2026, 9, 30))]
