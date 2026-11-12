"""
T-03 — Cache por snapshot do módulo Analytics (P-068, P-069, CA-19, CA-20, DA-06, DA-07).

Interface esperada (B-06, `src/modules/analytics/service/analytics_cache.py`):
- `AnalyticsSnapshot` (frozen dataclass com os campos de DA-06)
- `get_snapshot(force_reload=False)`, `peek_snapshot()` (sem lock, sem carga)
- `get_cache_status()` -> objeto com `state` ("FRIO" | "CARREGANDO" | "QUENTE" | "EXPIRADO") e
  `load_duration_ms` (int | None), lido sem lock (base do `estadoCache` do health)
- `_utc_now()` (relógio substituível), `_build_snapshot()` (carga completa, chamada sob o lock),
  `_SNAPSHOT`, `_LOCK`, `_is_loading`, `reset_cache()`
- `CACHE_TTL_HOURS = 6`, `MIN_RELOAD_INTERVAL_MINUTES = 15`, `ReloadTooSoonError` (`ANL-002`)
"""
import dataclasses
import threading
import time
from datetime import date, timedelta

import pytest

from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from src.modules.analytics.service import analytics_cache as cache
from src.modules.analytics.service.analytics_cache import AnalyticsSnapshot, ReloadTooSoonError
from tests.analytics.fixtures.synthetic_data import FIXED_NOW_UTC

CONCURRENT_CALLERS = 10
SIMULATED_LOAD_SECONDS = 0.2
THREAD_TIMEOUT_SECONDS = 5

DA06_FIELDS = {
    "reference_date", "loaded_at", "valid_basket_count", "is_base_sufficient", "rules_by_antecedent",
    "trivial_skus", "skus_with_basket", "customer_history", "catalog", "counts",
}


class Clock:
    """Relógio controlado que substitui `_utc_now()`."""

    def __init__(self, start):
        self.current = start

    def now(self):
        return self.current

    def advance(self, **delta):
        self.current = self.current + timedelta(**delta)


def make_snapshot(**overrides):
    """Constrói um `AnalyticsSnapshot` preenchendo campos não informados com valores neutros."""
    defaults = {
        "reference_date": date(2026, 11, 5),
        "loaded_at": FIXED_NOW_UTC,
        "valid_basket_count": 10_000,
        "is_base_sufficient": True,
        "rules_by_antecedent": {},
        "trivial_skus": frozenset(),
        "skus_with_basket": frozenset(),
        "customer_history": None,
        "catalog": {},
        "counts": {},
    }
    defaults.update(overrides)
    kwargs = {field.name: defaults.get(field.name) for field in dataclasses.fields(AnalyticsSnapshot)}
    return AnalyticsSnapshot(**kwargs)


class FakeLoader:
    """Substitui `_build_snapshot`: conta chamadas, pode demorar, bloquear ou falhar."""

    def __init__(self, clock, delay=0.0, error=None, is_base_sufficient=True):
        self.clock = clock
        self.delay = delay
        self.error = error
        self.is_base_sufficient = is_base_sufficient
        self.calls = 0
        self.gate = None
        self.started = threading.Event()

    def __call__(self):
        self.calls += 1
        self.started.set()
        if self.gate is not None:
            self.gate.wait(THREAD_TIMEOUT_SECONDS)
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return make_snapshot(loaded_at=self.clock.now(), is_base_sufficient=self.is_base_sufficient)


@pytest.fixture
def clock(monkeypatch):
    controlled = Clock(FIXED_NOW_UTC)
    monkeypatch.setattr(cache, "_utc_now", controlled.now)
    return controlled


@pytest.fixture
def loader(monkeypatch, clock):
    fake = FakeLoader(clock)
    monkeypatch.setattr(cache, "_build_snapshot", fake)
    return fake


def _run_in_threads(target, count):
    results, errors = [], []

    def worker():
        try:
            results.append(target())
        except Exception as exc:  # noqa: BLE001 - o teste inspeciona o erro
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(THREAD_TIMEOUT_SECONDS)
    return results, errors


# ------------------------------------------------------------------ contrato do snapshot

def test_snapshot_is_frozen_dataclass_with_da06_fields():
    assert dataclasses.is_dataclass(AnalyticsSnapshot)
    assert AnalyticsSnapshot.__dataclass_params__.frozen
    assert DA06_FIELDS <= {field.name for field in dataclasses.fields(AnalyticsSnapshot)}


def test_cache_constants():
    assert cache.CACHE_TTL_HOURS == 6
    assert cache.MIN_RELOAD_INTERVAL_MINUTES == 15
    assert ReloadTooSoonError().code == "ANL-002"


# ------------------------------------------------------------------ estadoCache (Q-7, P-069)

def test_cold_cache_state_without_loading(loader):
    status = cache.get_cache_status()

    assert status.state == "FRIO"
    assert status.load_duration_ms is None
    assert cache.peek_snapshot() is None
    assert loader.calls == 0


def test_first_access_loads_and_becomes_hot(loader):
    loader.delay = 0.02
    snapshot = cache.get_snapshot()

    status = cache.get_cache_status()
    assert loader.calls == 1
    assert cache.peek_snapshot() is snapshot
    assert status.state == "QUENTE"
    assert isinstance(status.load_duration_ms, int)
    assert status.load_duration_ms >= 0


def test_state_is_loading_while_load_in_progress(loader):
    loader.gate = threading.Event()
    worker = threading.Thread(target=cache.get_snapshot)
    worker.start()
    try:
        assert loader.started.wait(THREAD_TIMEOUT_SECONDS)
        assert cache.get_cache_status().state == "CARREGANDO"
        assert cache.peek_snapshot() is None
    finally:
        loader.gate.set()
        worker.join(THREAD_TIMEOUT_SECONDS)

    assert cache.get_cache_status().state == "QUENTE"


# ------------------------------------------------------------------ CA-20 TTL de 6 h

def test_ca20_does_not_reload_before_ttl(loader, clock):
    first = cache.get_snapshot()
    clock.advance(hours=5, minutes=59)

    assert cache.get_cache_status().state == "QUENTE"
    assert cache.get_snapshot() is first
    assert loader.calls == 1


def test_ca20_reloads_at_ttl(loader, clock):
    first = cache.get_snapshot()
    clock.advance(hours=6)

    assert cache.get_cache_status().state == "EXPIRADO"
    second = cache.get_snapshot()
    assert second is not first
    assert loader.calls == 2
    assert cache.get_cache_status().state == "QUENTE"


# ------------------------------------------------------------------ CA-19 carga única

def test_ca19_concurrent_cold_requests_load_once(loader):
    loader.delay = SIMULATED_LOAD_SECONDS

    results, errors = _run_in_threads(cache.get_snapshot, CONCURRENT_CALLERS)

    assert errors == []
    assert loader.calls == 1
    assert len(results) == CONCURRENT_CALLERS
    assert all(result is results[0] for result in results)


def test_concurrent_requests_after_expiry_reload_once(loader, clock):
    cache.get_snapshot()
    clock.advance(hours=7)
    loader.delay = SIMULATED_LOAD_SECONDS

    results, errors = _run_in_threads(cache.get_snapshot, CONCURRENT_CALLERS)

    assert errors == []
    assert loader.calls == 2
    assert all(result is results[0] for result in results)


# ------------------------------------------------------------------ force_reload (P-068.3, DA-07)

def test_force_reload_on_cold_cache_loads(loader):
    cache.get_snapshot(force_reload=True)
    assert loader.calls == 1


def test_force_reload_before_15_minutes_is_rejected_without_loading(loader, clock):
    first = cache.get_snapshot()
    clock.advance(minutes=14, seconds=59)

    with pytest.raises(ReloadTooSoonError):
        cache.get_snapshot(force_reload=True)
    assert loader.calls == 1
    assert cache.peek_snapshot() is first


def test_force_reload_after_15_minutes_reloads(loader, clock):
    first = cache.get_snapshot()
    clock.advance(minutes=15)

    second = cache.get_snapshot(force_reload=True)

    assert loader.calls == 2
    assert second is not first
    assert cache.peek_snapshot() is second


def test_force_reload_respects_lock_and_reuses_concurrent_load(loader, clock):
    """Quem chega durante uma carga espera o lock e reaproveita o resultado (P-068.3, contrato §3.2)."""
    cache.get_snapshot()
    clock.advance(hours=7)
    loader.gate = threading.Event()
    results = {}

    regular = threading.Thread(target=lambda: results.setdefault("regular", cache.get_snapshot()))
    regular.start()
    assert loader.started.wait(THREAD_TIMEOUT_SECONDS)
    loader.started.clear()

    forced_errors = []

    def forced_call():
        try:
            results["forced"] = cache.get_snapshot(force_reload=True)
        except Exception as exc:  # noqa: BLE001
            forced_errors.append(exc)

    forced = threading.Thread(target=forced_call)
    forced.start()
    time.sleep(0.05)
    loader.gate.set()
    regular.join(THREAD_TIMEOUT_SECONDS)
    forced.join(THREAD_TIMEOUT_SECONDS)

    assert forced_errors == []
    assert loader.calls == 2
    assert results["forced"] is results["regular"]


# ------------------------------------------------------------------ falha na carga (P-068.4)

def test_failed_reload_keeps_previous_snapshot_and_propagates(loader, clock):
    first = cache.get_snapshot()
    clock.advance(hours=7)
    loader.error = AnalyticsDataSourceError()

    with pytest.raises(AnalyticsDataSourceError):
        cache.get_snapshot()

    assert cache.peek_snapshot() is first
    assert cache.get_cache_status().state == "EXPIRADO"

    loader.error = None
    assert cache.get_snapshot() is not first
    assert loader.calls == 3


def test_failed_cold_load_clears_loading_flag(loader):
    loader.error = AnalyticsDataSourceError()

    with pytest.raises(AnalyticsDataSourceError):
        cache.get_snapshot()

    assert cache._is_loading is False
    assert cache.get_cache_status().state == "FRIO"
    assert cache.peek_snapshot() is None


def test_unexpected_error_also_clears_loading_flag(loader):
    loader.error = RuntimeError("falha inesperada")

    with pytest.raises(RuntimeError):
        cache.get_snapshot()

    assert cache._is_loading is False


# ------------------------------------------------------------------ base insuficiente (DA-06)

def test_insufficient_base_is_cached_and_not_reloaded_each_call(loader):
    loader.is_base_sufficient = False

    first = cache.get_snapshot()
    second = cache.get_snapshot()

    assert first.is_base_sufficient is False
    assert second is first
    assert loader.calls == 1


# ------------------------------------------------------------------ health sem lock (P-069)

def test_peek_and_status_do_not_wait_for_lock(loader):
    finished = threading.Event()

    def read_without_lock():
        cache.peek_snapshot()
        cache.get_cache_status()
        finished.set()

    cache._LOCK.acquire()
    try:
        reader = threading.Thread(target=read_without_lock)
        reader.start()
        assert finished.wait(1.0), "peek_snapshot/get_cache_status não podem esperar o lock"
    finally:
        cache._LOCK.release()
    assert loader.calls == 0


def test_reset_cache_returns_to_cold(loader):
    cache.get_snapshot()
    cache.reset_cache()

    assert cache.peek_snapshot() is None
    assert cache.get_cache_status().state == "FRIO"
