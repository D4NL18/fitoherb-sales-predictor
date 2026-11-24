"""T-7.2B.3 / T-7.2.8: evidenceHash deterministico, chave/caminho do GCS, TTL logico, L1. P-175, DA-07."""
import copy
import json
from datetime import date

import pytest

from tests.trend_insights.helpers import FakeClock, FakeObjectStore, canonical_evidence, make_evidence, mod


def _hash(**kw):
    return mod("domain.evidence").compute_evidence_hash(make_evidence(**kw))


def test_hash_is_sha256_hex_and_deterministic():
    h = _hash()
    assert len(h) == 64 and int(h, 16) >= 0 and h == _hash()


def test_hash_ignores_list_order_rounding_and_reference_date():
    base = canonical_evidence()
    afins2 = base["afins"] + [{**base["afins"][0], "sku": 5200}]
    a = mod("domain.evidence").EvidencePackage.from_mapping({**base, "afins": afins2}, data_referencia=date(2026, 11, 9))
    b = mod("domain.evidence").EvidencePackage.from_mapping({**base, "afins": list(reversed(afins2))}, data_referencia=date(2026, 11, 20))
    ev = mod("domain.evidence").compute_evidence_hash
    assert ev(a) == ev(b)
    assert _hash(delta_observado=-3000.001, variacao_pct=-30.0001) == _hash()


def test_hash_changes_when_evidence_changes():
    assert _hash(delta_observado=-3500.0, variacao_pct=-35.0) != _hash()


def test_key_object_path_follows_adr():
    key = mod("store.insight_store").InsightKey(
        escopo="product", id=5102, metric="revenue", window=3, base_month="2026-10",
        comparison_mode="point", prompt_version="tia-v2", evidence_hash="abc")
    assert key.object_path() == "insights/v1/product/5102/revenue/point/w3/2026-10/tia-v2/abc.json"


def _stored(**over):
    cls = mod("store.insight_store").StoredInsight
    data = dict(diagnostico={"resumo": "x"}, modelo="gemini-4-hydrogen", origem="llm",
                gerado_em="2026-11-24T15:00:00+00:00", prompt_version="tia-v2", evidence_hash="abc",
                has_external_factor=True, cost_usd=0.014, input_tokens=4000, output_tokens=1100, queries=2,
                sugestoes_busca_html=None)
    data.update(over)
    return cls(**data)


def _key(h="abc"):
    return mod("store.insight_store").InsightKey(
        escopo="product", id=5102, metric="revenue", window=3, base_month="2026-10",
        comparison_mode="point", prompt_version="tia-v2", evidence_hash=h)


def test_put_get_roundtrip_and_stored_json_has_no_person_data():
    objects, clock = FakeObjectStore(), FakeClock()
    store = mod("store.insight_store").InsightStore(store=objects, clock=clock)
    store.put(_key(), _stored())
    assert store.get(_key()).modelo == "gemini-4-hydrogen"
    text = json.dumps(objects.objects[_key().object_path()]).lower()
    assert not any(w in text for w in ("usuario", "user", "email", "ip\"", "cod cliente", "customer"))


def test_l1_cache_5_minutes_and_invalidated_by_put():
    objects, clock = FakeObjectStore(), FakeClock()
    store = mod("store.insight_store").InsightStore(store=objects, clock=clock)
    store.put(_key(), _stored())
    objects.reads = 0
    store.get(_key()); store.get(_key())
    assert objects.reads <= 1
    clock.advance(301)
    store.get(_key())
    assert objects.reads >= 1
    reads_before = objects.reads
    store.put(_key(), _stored(diagnostico={"resumo": "novo"}), overwrite=True)
    assert store.get(_key()).diagnostico["resumo"] == "novo" and objects.reads >= reads_before


def test_missing_object_returns_none():
    store = mod("store.insight_store").InsightStore(store=FakeObjectStore(), clock=FakeClock())
    assert store.get(_key("nao-existe")) is None


@pytest.mark.parametrize("days,external,expired", [(29, True, False), (31, True, True), (400, False, False)])
def test_soft_ttl_30_days_only_for_external_factors(days, external, expired):
    stored = _stored(has_external_factor=external)
    clock = FakeClock()
    clock.advance(days * 86400)
    assert stored.is_expired(now=clock(), ttl_days=30) is expired
