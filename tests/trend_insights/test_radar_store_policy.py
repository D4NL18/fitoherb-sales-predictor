"""T-7.2R.6/7 (C-36, C-37): radar no GCS (chave, TTL, stale, single-flight, force) e politica de radar/busca. P-180.1/3."""
import json
import threading
from datetime import datetime, timezone

import pytest

from tests.trend_insights.helpers import FakeClock, FakeObjectStore, make_evidence, make_llm_response, mod
from tests.trend_insights.radar_helpers import (
    BASE_MONTH, DEFAULT_SLUG, RADAR_VERSION, RoutedLlm, TtlLease, avaliacao, make_radar_rig, plant_radar, radar_doc,
    radar_path, valid_diag_text,
)

NOW = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)


def _fresh(generated_at, base_month):
    return mod("domain.radar_policy").radar_freshness(generated_at=generated_at, base_month=base_month, now=NOW)


def _age(days):
    from datetime import timedelta
    return NOW - timedelta(days=days)


# --- TTL logico (30 corrente/anterior; 180 meses antigos; stale ate 120 d desde a geracao)
@pytest.mark.parametrize("base,age,state", [
    ("2026-11", 0, "FRESCO"), ("2026-10", 30, "FRESCO"), ("2026-10", 31, "DESATUALIZADO"),
    ("2026-11", 120, "DESATUALIZADO"), ("2026-10", 121, "AUSENTE"),
    ("2026-08", 180, "FRESCO"), ("2026-08", 181, "AUSENTE"), ("2026-08", 31, "FRESCO"),
])
def test_radar_freshness_ttl_and_stale_window(base, age, state):
    assert _fresh(_age(age), base) == state


def test_radar_constants():
    c = mod("domain.constants")
    assert (c.RADAR_PROMPT_VERSION, c.RADAR_TTL_DAYS, c.RADAR_TTL_PAST_DAYS, c.RADAR_STALE_MAX_DAYS) == ("radar-v1", 30, 180, 120)
    assert (c.RADAR_LOOKBACK_MONTHS, c.RADAR_SOURCE_LOOKBACK_DAYS) == (6, 270)
    assert (c.RADAR_MAX_SEARCH_QUERIES_SUGGESTED, c.RADAR_RESERVATION_QUERIES) == (5, 6)
    assert (c.RADAR_BUDGET_SHARE, c.RADAR_MAX_NEW_PER_DAY) == (0.25, 3)
    assert (c.RADAR_DEADLINE_SECONDS, c.RADAR_MAX_OUTPUT_TOKENS, c.GROUNDING_HARD_CAP_QUERIES) == (55, 1500, 1500)
    assert c.MAX_RADAR_CONTEXT_CHARS == 2000 and c.MAX_EXTERNAL_FACTORS_IN_FACTORS == 3
    assert c.PRODUCT_SEARCH_MIN_RESIDUAL_SHARE == 0.30 and c.PRODUCT_SEARCH_MAX_QUERIES == 1


def test_physical_retention_of_radar_prefix_is_210_days():
    import pathlib
    rules = json.loads(pathlib.Path("infra/trend-insights/lifecycle.json").read_text(encoding="utf-8"))["rule"]
    radar = [r for r in rules if "radar/" in r["condition"].get("matchesPrefix", [])]
    assert len(radar) == 1 and radar[0]["action"]["type"] == "Delete" and radar[0]["condition"]["age"] == 210


def test_env_script_forwards_radar_variables():
    import pathlib
    text = pathlib.Path("infra/trend-insights/env.sh").read_text(encoding="utf-8")
    for name in ("TREND_AI_MODEL_RADAR", "GROUNDING_HARD_CAP_QUERIES", "LLM_TOTAL_DEADLINE_SECONDS",
                 "IN_FLIGHT_LOCK_TTL_SECONDS", "RESERVATION_TTL_SECONDS"):
        assert name in text


# --- politica pura (C-36, C-43, C-44)
def _policy(**over):
    args = dict(radar_state="AUSENTE", budget_level="NORMAL", daily_new=0, share_spent=False, hard_cap=False)
    args.update(over)
    return mod("domain.gates").radar_policy(**args)


@pytest.mark.parametrize("over,expected", [
    (dict(radar_state="FRESCO"), "USE_FRESH"),
    (dict(radar_state="FRESCO", hard_cap=True, budget_level="ESGOTADO"), "USE_FRESH"),
    (dict(radar_state="AUSENTE"), "GENERATE"),
    (dict(radar_state="DESATUALIZADO"), "GENERATE"),
    (dict(radar_state="DESATUALIZADO", hard_cap=True), "USE_STALE"),
    (dict(radar_state="AUSENTE", hard_cap=True), "NONE"),
    (dict(radar_state="AUSENTE", daily_new=3), "NONE"),
    (dict(radar_state="DESATUALIZADO", daily_new=3), "USE_STALE"),
    (dict(radar_state="AUSENTE", share_spent=True), "NONE"),
    (dict(radar_state="DESATUALIZADO", share_spent=True), "USE_STALE"),
    (dict(radar_state="AUSENTE", budget_level="ALERTA"), "GENERATE"),        # a 80%: so se nao existe nenhum
    (dict(radar_state="DESATUALIZADO", budget_level="ALERTA"), "USE_STALE"),
    (dict(radar_state="AUSENTE", budget_level="ESGOTADO"), "NONE"),
    (dict(radar_state="DESATUALIZADO", budget_level="ESGOTADO"), "USE_STALE"),
    (dict(radar_state="AUSENTE", daily_new=2), "GENERATE"),
])
def test_radar_policy(over, expected):
    assert _policy(**over) == expected


def _search(level="NORMAL", radar_state="AUSENTE", hard_cap=False, **over):
    ev = make_evidence(**over)
    return mod("domain.gates").product_search_enabled(ev, budget_level=level, radar_state=radar_state, hard_cap=hard_cap)


@pytest.mark.parametrize("kw,expected", [
    (dict(residual_share=0.30), True), (dict(residual_share=0.29), False),
    (dict(residual_share=0.9, radar_state="FRESCO"), False), (dict(residual_share=0.9, radar_state="DESATUALIZADO"), False),
    (dict(residual_share=0.9, level="ALERTA"), False), (dict(residual_share=0.9, hard_cap=True), False),
    (dict(residual_share=0.9, modo_diagnostico="QUALITATIVO"), False),
    (dict(residual_share=0.9, diagnostico_mercado={"classificacao": "MERCADO_EM_QUEDA"}, radar_state="FRESCO"), False),
])
def test_product_search_only_without_radar(kw, expected):
    assert _search(**kw) is expected


def test_product_search_needs_a_term():
    assert _search(residual_share=0.9, produto={"funcao_primaria": None, "categoria_galeria": None}) is False


def test_gates_unchanged_and_old_grounding_gate_removed():
    gates, c = mod("domain.gates"), mod("domain.constants")
    assert gates.evaluate_llm_gates(make_evidence()) is None
    assert gates.evaluate_llm_gates(make_evidence(residual_share=0.19)) == "GATE_RESIDUO_BAIXO"
    assert not hasattr(c, "GROUNDING_MIN_RESIDUAL_SHARE_ALERT") and not hasattr(c, "MAX_SEARCH_QUERIES_QUALITATIVE")
    assert not hasattr(gates, "grounding_enabled")


# --- store: chave e conteudo
def test_object_key_has_no_sku_or_user_and_follows_pattern():
    store = mod("store.radar_store")
    assert store.radar_path(RADAR_VERSION, DEFAULT_SLUG, BASE_MONTH) == radar_path()
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="usuario-1")
    (path,) = rig.objects.paths("radar/")
    assert path == radar_path() and "5102" not in path and "usuario" not in path


def test_stored_object_has_only_company_free_content():
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="usuario-1")
    doc = rig.objects.objects[radar_path()]
    assert {"geradoEm", "modelo", "assunto", "mesBase", "dimensoes", "fontes", "consultasExecutadas", "radarHash"} <= set(doc)
    assert set(doc["assunto"]) == {"slug", "termo", "tipo"} and len(doc["dimensoes"]) == 8
    text = json.dumps(doc, default=str).lower()
    for forbidden in ("5102", "cha de hibisco", "ervas delta", "usuario", "-30", "3000", "queda", "hibisco"):
        assert forbidden not in text
    for dim in doc["dimensoes"]:
        assert set(dim) == {"dimensao", "status", "movimento", "intensidade", "tema", "fonteIds"}


def test_radar_request_carries_no_company_data():
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="usuario-1")
    (req,) = rig.llm.radar_calls
    text = (req.system_prompt + req.user_prompt).lower()
    for forbidden in ("5102", "cha de hibisco", "ervas delta", "hibisco seco", "-30", "3000", "10000", "usuario"):
        assert forbidden not in text
    assert "ervas e plantas medicinais" in text and req.use_search_grounding is True
    assert req.max_output_tokens == 1500 and req.timeout_seconds <= 55 and req.request_tag == "radar"


# --- cache compartilhado, force, single-flight
def test_second_product_same_subject_and_month_reuses_radar():
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="u1")
    other = make_evidence(produto={"sku": 5103, "descricao": "CHA DE CAMOMILA 50G"}, delta_observado=-3500.0, variacao_pct=-35.0)
    out = rig.orch.generate(other, caller_id="u2")
    assert len(rig.llm.radar_calls) == 1 and out.radar["origem"] == "CACHE"
    assert len(rig.llm.diag_calls) == 2 and rig.objects.writes >= 2


def test_force_does_not_renew_a_fresh_radar():
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="u1")
    rig.clock.advance(61)
    out = rig.orch.generate(make_evidence(), caller_id="u1", force=True)
    assert len(rig.llm.radar_calls) == 1 and len(rig.llm.diag_calls) == 2 and out.radar["origem"] == "CACHE"


def test_expired_radar_is_renewed_with_generation_precondition():
    rig = make_radar_rig()
    path = plant_radar(rig.objects, age_days=40, clock=rig.clock)
    assert rig.objects.generations[path] == 1
    out = rig.orch.generate(make_evidence(), caller_id="u1")
    assert len(rig.llm.radar_calls) == 1 and rig.objects.generations[path] == 2
    assert out.radar["origem"] == "GERADO_AGORA" and out.radar["desatualizado"] is False


def test_two_users_concurrent_share_one_radar_generation():
    entered, release = threading.Event(), threading.Event()
    llm = RoutedLlm(on_radar_call=lambda r: (entered.set(), release.wait(5)))
    rig = make_radar_rig(llm=llm)
    results = []
    ev_a = make_evidence()
    ev_b = make_evidence(produto={"sku": 5103}, delta_observado=-3500.0, variacao_pct=-35.0)
    t1 = threading.Thread(target=lambda: results.append(rig.orch.generate(ev_a, caller_id="a")))
    t1.start(); entered.wait(5)
    t2 = threading.Thread(target=lambda: results.append(rig.orch.generate(ev_b, caller_id="b")))
    t2.start()
    release.set(); t1.join(); t2.join()
    assert len(llm.radar_calls) == 1
    assert sorted(r.radar["origem"] for r in results) == ["CACHE", "GERADO_AGORA"]


def test_cross_instance_lease_follower_polls_and_uses_shared_radar():
    shared_objects, shared_lease, clock = FakeObjectStore(), TtlLease(), FakeClock()
    holder = {}
    a = make_radar_rig(objects=shared_objects, lease=shared_lease, clock=clock, sleep=lambda s: holder["fn"](s))
    b = make_radar_rig(objects=shared_objects, lease=shared_lease, clock=clock)
    key = None

    def other_instance_finishes(seconds):
        clock.advance(seconds)
        if shared_lease.hold_all:
            shared_lease.hold_all = False
            b.orch.generate(make_evidence(), caller_id="b")

    holder["fn"] = other_instance_finishes
    shared_lease.hold_all = True
    out = a.orch.generate(make_evidence(), caller_id="a")
    assert len(a.llm.radar_calls) == 0 and len(b.llm.radar_calls) == 1
    assert out.origem in ("cache", "llm") and (out.radar is None or out.radar["origem"] == "CACHE")


def test_lease_ttls_radar_90_diagnosis_150_and_keys_without_sku():
    rig = make_radar_rig()
    rig.orch.generate(make_evidence(), caller_id="u1")
    assert sorted(rig.lease.ttls.values()) == [90, 150]
    assert all("5102" not in key for key, ttl in rig.lease.ttls.items() if ttl == 90)
    assert rig.lease.held == set()


def test_store_get_returns_none_for_missing_and_stale_beyond_window():
    rig = make_radar_rig()
    assert rig.radar_store.get(DEFAULT_SLUG, BASE_MONTH) is None
    plant_radar(rig.objects, age_days=200, clock=rig.clock)
    view = rig.radar.peek(mod("domain.raw_material").infer_radar_subject(make_evidence()), BASE_MONTH)
    assert view is None  # alem de 120 dias: nao serve nem como stale
