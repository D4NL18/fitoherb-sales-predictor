"""T-7.1.5 / T-7.1.13: escala por k, clientes perdidos, adaptador de migracao, cache. P-153, P-164, LGPD-TIA-02."""
import threading
import time
from datetime import date
from fractions import Fraction
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import FakeClock, mod

CUSTOMER = 987654321


def test_scale_previous_multiplies_only_pre_columns():
    fn = mod("domain.migration_scaling").scale_previous
    rows = [(CUSTOMER, "100", 30.0, 300.0, 5.0, 50.0)]
    out = list(fn(rows, Fraction(1, 3)))
    assert out[0][:2] == (CUSTOMER, "100")
    assert out[0][2:] == (pytest.approx(10.0), pytest.approx(100.0), 5.0, 50.0)


def test_lost_customers_exclude_those_who_gained_an_affine():
    fn = mod("domain.migration_scaling").aggregate_lost_customers
    affinity = {"100": {"200": 0.8}}
    rows = [
        (1, "100", 10.0, 100.0, 0.0, 0.0),    # perdido, nao ganhou afim
        (2, "100", 10.0, 100.0, 0.0, 20.0),   # perdido parcial: pre*k - cur = 80
        (3, "100", 10.0, 100.0, 0.0, 0.0),    # ganhou afim 200 -> fora
        (3, "200", 0.0, 0.0, 5.0, 50.0),
        (4, "100", 10.0, 100.0, 0.0, 0.0),    # nao esta na lista de churn -> fora
    ]
    out = fn(rows, frozenset({1, 2, 3}), affinity)
    agg = out["100"]
    assert agg.count == 2 and agg.revenue == pytest.approx(180.0)


def _spec(mode="average", window=3):
    from tests.trend_insights.test_windows_and_modes import _spec as spec, _idx
    return spec(_idx(2026, 10), window, mode)


def _build(**over):
    adapter = mod("adapters.migration_adapter")
    kwargs = dict(
        spec=_spec(), affinity_map={"100": {"200": 0.8}}, catalog={}, lost_customer_codes=frozenset(),
        read_rows=lambda *dates: [(CUSTOMER, "100", 30.0, 300.0, 5.0, 50.0)],
        engine=lambda rows, catalog, affinity_map=None: SimpleNamespace(pairs=[], rows_seen=list(rows)),
    )
    kwargs.update(over)
    return adapter.build_migration_snapshot(**kwargs)


def test_incomplete_previous_window_does_not_read_database():
    calls = []
    import dataclasses
    spec = dataclasses.replace(_spec("point", 12), is_previous_fully_covered=False)
    res = _build(spec=spec, read_rows=lambda *a: calls.append(a) or [])
    assert isinstance(res, mod("domain.ports").NotEvaluated) and res.reason == "JANELA_ANTERIOR_INCOMPLETA"
    assert calls == []


def test_missing_affinity_index_skips_engine():
    engine_calls = []
    res = _build(affinity_map=None, engine=lambda *a, **k: engine_calls.append(1))
    assert res.reason == "INDICE_AFINIDADE_INDISPONIVEL" and engine_calls == []


def test_engine_gets_scaled_rows_and_snapshot_has_no_customer_code():
    seen = {}
    dates = {}

    def engine(rows, catalog, affinity_map=None):
        seen["rows"] = list(rows)
        return SimpleNamespace(pairs=[("100", "200", 10.0)])

    def reader(*args):
        dates["args"] = args
        return [(CUSTOMER, "100", 30.0, 300.0, 5.0, 50.0)]

    snap = _build(engine=engine, read_rows=reader, lost_customer_codes=frozenset({CUSTOMER}))
    assert len(dates["args"]) == 4  # 4 datas sempre
    assert seen["rows"][0][2] == pytest.approx(10.0) and seen["rows"][0][3] == pytest.approx(100.0)
    assert str(CUSTOMER) not in repr(snap)
    import dataclasses
    assert str(CUSTOMER) not in repr(dataclasses.asdict(snap) if dataclasses.is_dataclass(snap) else snap.__dict__)


# --- MigrationCache
def _cache(builder, clock=None, **kw):
    return mod("service.migration_cache").MigrationCache(builder=builder, clock=clock or FakeClock(), **kw)


def test_cache_hit_ttl_and_failure_not_cached():
    clock = FakeClock()
    calls = []
    cache = _cache(lambda key: calls.append(key) or {"key": key}, clock)
    key = ("point", 3, "2026-10", date(2026, 11, 9), "gen1")
    cache.get_or_build(key); cache.get_or_build(key)
    assert len(calls) == 1
    clock.advance(6 * 3600 + 1)
    cache.get_or_build(key)
    assert len(calls) == 2

    def boom(_k):
        raise RuntimeError("falha")
    failing = _cache(boom, clock)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            failing.get_or_build(key)


def test_cache_generation_in_key_and_lru_of_eight():
    calls = []
    cache = _cache(lambda key: calls.append(key) or key)
    for i in range(9):
        cache.get_or_build(("point", i, "m", None, "g"))
    cache.get_or_build(("point", 0, "m", None, "g"))  # evicted -> rebuild
    assert len(calls) == 10
    cache.get_or_build(("point", 8, "m", None, "g2"))  # outra geracao do indice
    assert len(calls) == 11


def test_cache_single_flight_and_build_concurrency_one():
    active = {"now": 0, "max": 0}
    lock = threading.Lock()
    calls = []

    def builder(key):
        with lock:
            active["now"] += 1; active["max"] = max(active["max"], active["now"])
        calls.append(key)
        time.sleep(0.1)
        with lock:
            active["now"] -= 1
        return key

    cache = _cache(builder)
    threads = [threading.Thread(target=cache.get_or_build, args=(("point", 1 if i < 2 else 2, "m", None, "g"),))
               for i in range(4)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sorted(calls) == [("point", 1, "m", None, "g"), ("point", 2, "m", None, "g")]  # voo unico por chave
    assert active["max"] == 1
