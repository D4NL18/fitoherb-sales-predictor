"""Hardening do radar compartilhado (S-2, S-3, S-4 da auditoria; P-180.3) e folga mensal desde o 1o dia (P-178.9)."""
import copy

import pytest

from tests.trend_insights.helpers import HYDROGEN, mod
from tests.trend_insights.radar_helpers import (
    DEFAULT_SLUG, BASE_MONTH, SOURCE_URL, make_radar_rig, plant_radar, radar_doc, radar_path, seed_ledger,
)


def _store():
    return mod("store.radar_store")


def _source(doc):
    return doc["fontes"][0]


def _bad(mutator):
    doc = radar_doc()
    mutator(doc)
    return doc


def test_valid_doc_with_recomputed_hash_is_accepted():
    assert _store().StoredRadar.from_json(radar_doc()).slug == DEFAULT_SLUG


@pytest.mark.parametrize("mutator", [
    lambda d: _source(d).update(url="http://noticias.exemplo.com/a"),
    lambda d: _source(d).update(url="javascript:alert(1)", dominio="alert(1)"),
    lambda d: _source(d).update(url="https://10.0.0.1/x", dominio="10.0.0.1"),
    lambda d: _source(d).update(dominio="outro.exemplo.com"),
    lambda d: _source(d).update(titulo="x" * 201),
    lambda d: _source(d).update(dataPublicacao="ontem"),
    lambda d: _source(d).update(origemData="QUALQUER"),
    lambda d: d.update(mesBase="2026-13"),
    lambda d: d["assunto"].update(slug="../etc"),
    lambda d: d.update(radarHash="f" * 64),
], ids=["http", "js", "ip", "dominio", "titulo", "data", "origem", "mes", "slug", "hash"])
def test_from_json_rejects_tampered_object(mutator):
    with pytest.raises(_store().RadarObjectInvalid):
        _store().StoredRadar.from_json(_bad(mutator))


def test_store_ignores_object_whose_slug_or_month_differs_from_key():
    rig = make_radar_rig()
    doc = radar_doc(slug="outro-slug")
    path = radar_path(DEFAULT_SLUG, BASE_MONTH)
    rig.objects.objects[path] = copy.deepcopy(doc)
    rig.objects.generations[path] = 1
    store = _store().RadarStore(rig.objects, rig.clock)
    assert store.get(DEFAULT_SLUG, BASE_MONTH) is None


def test_search_suggestions_html_is_never_kept_from_stored_object():
    doc = radar_doc()
    doc["searchSuggestionsHtml"] = "<script>alert(1)</script>"
    radar = _store().StoredRadar.from_json(doc)
    assert radar.search_suggestions_html is None and radar.to_json()["searchSuggestionsHtml"] is None


def test_runner_persists_radar_without_search_suggestions_html():
    from tests.trend_insights.helpers import make_evidence
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="u1")
    paths = rig.objects.paths("radar/")
    assert paths and all(rig.objects.objects[p]["searchSuggestionsHtml"] is None for p in paths)


def test_monthly_reserve_applies_from_first_day_without_radar():
    exc = mod("domain.exceptions")
    rig = make_radar_rig()
    seed_ledger(rig, month=1.60)  # 1,60 + diagnostico (~0,02) + folga 0,22 > 1,80, sem radar no mes
    with pytest.raises(exc.BudgetDenied):
        rig.ledger.reserve(HYDROGEN, with_search=False)


def test_budget_caps_live_in_domain_budget():
    budget = mod("domain.budget")
    assert callable(budget.check_radar_caps) and callable(budget.radar_headroom)
