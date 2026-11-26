"""T-7.2R.10 (C-43, C-44): reserva do radar, tetos (share, dia, 1.500 consultas), livro v3, capacidade, config. P-178.2..8."""
import json
from datetime import datetime, timezone

import pytest

from tests.trend_insights.helpers import FLASH, HYDROGEN, PRICING_JSON, make_settings, mod
from tests.trend_insights.radar_helpers import day_count, ledger_doc, make_radar_rig, seed_ledger


def _table():
    return mod("llm.pricing").parse_pricing(PRICING_JSON)


def _exc():
    return mod("domain.exceptions")


def test_radar_reservation_is_about_two_cents_and_never_prices_search():
    amount = mod("domain.budget").reservation_amount(HYDROGEN, _table(), with_search=True, month_queries=0, kind="RADAR")
    assert 0.015 <= amount <= 0.025
    # cota gratis esgotada: o radar nunca e pago de proposito, a reserva nao soma consultas
    at_cap = mod("domain.budget").reservation_amount(HYDROGEN, _table(), with_search=True, month_queries=1500, kind="RADAR")
    assert at_cap == pytest.approx(amount)


def test_reserve_and_settle_radar_updates_v3_ledger_fields():
    rig = make_radar_rig()
    res = rig.ledger.reserve(HYDROGEN, with_search=True, kind="RADAR")
    assert res.kind == "RADAR" and 0.015 <= res.amount_usd <= 0.025
    rig.ledger.settle(res, cost_usd=0.0125, executed_queries=5)
    doc = ledger_doc(rig)
    assert doc["gastoRadarMes"] == pytest.approx(0.0125) and doc["gastoMes"] == pytest.approx(0.0125)
    assert doc["radaresNovosMes"] == 1 and day_count(doc["radaresNovosDia"]) == 1 and doc["consultasMes"] == 5


def test_diagnosis_settle_does_not_touch_radar_counters_and_release_does_not_count():
    rig = make_radar_rig()
    rig.ledger.settle(rig.ledger.reserve(HYDROGEN, with_search=False), cost_usd=0.018, executed_queries=0)
    rig.ledger.release(rig.ledger.reserve(HYDROGEN, with_search=True, kind="RADAR"))
    doc = ledger_doc(rig)
    assert doc.get("gastoRadarMes", 0) == 0 and doc.get("radaresNovosMes", 0) == 0 and doc["gastoMes"] == pytest.approx(0.018)


@pytest.mark.parametrize("seed,denied", [
    (dict(radar_month=0.44), True),    # 0,44 + 0,02 > 0,25 * 1,80 = 0,45
    (dict(radar_month=0.42), False),
    (dict(radares_dia=3), True),       # RADAR_MAX_NEW_PER_DAY
    (dict(radares_dia=2), False),
    (dict(queries=1500), True),        # teto duro de consultas
    (dict(queries=1000), False),
])
def test_ledger_enforces_radar_share_daily_limit_and_hard_cap(seed, denied):
    rig = make_radar_rig()
    seed_ledger(rig, month=0.5, **seed)
    if denied:
        with pytest.raises(_exc().BudgetDenied):
            rig.ledger.reserve(HYDROGEN, with_search=True, kind="RADAR")
    else:
        rig.ledger.reserve(HYDROGEN, with_search=True, kind="RADAR")


def test_hard_cap_does_not_block_diagnosis_without_search():
    rig = make_radar_rig()
    seed_ledger(rig, queries=1500)
    rig.ledger.reserve(HYDROGEN, with_search=False)


def test_hard_cap_reader_and_settings():
    rig = make_radar_rig()
    seed_ledger(rig, queries=1500)
    assert rig.ledger.month_queries() == 1500
    s = make_settings()
    assert s.hard_cap_queries == 1500 and s.model_radar == HYDROGEN
    assert make_settings(GROUNDING_HARD_CAP_QUERIES=5).hard_cap_queries == 5
    assert make_settings(TREND_AI_MODEL_RADAR=FLASH).model_radar == FLASH
    for name, bad in (("GROUNDING_HARD_CAP_QUERIES", "-1"), ("GROUNDING_HARD_CAP_QUERIES", "x"),
                      ("TREND_AI_MODEL_RADAR", "gemini-4-neon")):
        with pytest.raises(_exc().SettingsError):
            make_settings(**{name: bad})


def test_orchestrator_hard_cap_no_new_radar_no_product_search_and_never_paid():
    rig = make_radar_rig()
    seed_ledger(rig, queries=1500)
    from tests.trend_insights.helpers import make_evidence
    out = rig.orch.generate(make_evidence(residual_share=0.9), caller_id="u1")
    assert rig.llm.radar_calls == [] and all(c.use_search_grounding is False for c in rig.llm.calls)
    assert "SEM_RADAR_EXTERNO" in out.avisos and ledger_doc(rig)["consultasMes"] == 1500
    assert ledger_doc(rig)["gastoMes"] == pytest.approx(0.01425, abs=0.01)  # so tokens do diagnostico


def test_orchestrator_hard_cap_uses_stale_radar():
    from tests.trend_insights.helpers import make_evidence
    from tests.trend_insights.radar_helpers import plant_radar
    rig = make_radar_rig()
    seed_ledger(rig, queries=1500)
    plant_radar(rig.objects, age_days=60, clock=rig.clock)
    out = rig.orch.generate(make_evidence(), caller_id="u1")
    assert rig.llm.radar_calls == [] and out.radar["desatualizado"] is True and "RADAR_DESATUALIZADO" in out.avisos


def test_orchestrator_alert_level_radar_only_if_none_exists():
    from tests.trend_insights.helpers import make_evidence
    from tests.trend_insights.radar_helpers import plant_radar
    rig = make_radar_rig()
    seed_ledger(rig, month=1.50)
    out = rig.orch.generate(make_evidence(), caller_id="u1")
    assert len(rig.llm.radar_calls) == 1 and out.radar["origem"] == "GERADO_AGORA"
    rig2 = make_radar_rig()
    seed_ledger(rig2, month=1.50)
    plant_radar(rig2.objects, age_days=60, clock=rig2.clock)
    out2 = rig2.orch.generate(make_evidence(), caller_id="u1")
    assert rig2.llm.radar_calls == [] and out2.radar["desatualizado"] is True
    assert all(c.use_search_grounding is False for c in rig2.llm.diag_calls)


def test_daily_new_radar_limit_in_orchestrator():
    from tests.trend_insights.helpers import make_evidence
    rig = make_radar_rig()
    seed_ledger(rig, radares_dia=3)
    out = rig.orch.generate(make_evidence(), caller_id="u1")
    assert rig.llm.radar_calls == [] and "SEM_RADAR_EXTERNO" in out.avisos and out.origem == "llm"


def test_failed_radar_cost_goes_to_ledger_even_without_storing():
    from tests.trend_insights.helpers import make_evidence, make_llm_response
    from tests.trend_insights.radar_helpers import RoutedLlm
    bad = make_llm_response("nao e json", queries=5)
    rig = make_radar_rig(llm=RoutedLlm(radar=[bad, bad]))
    rig.orch.generate(make_evidence(), caller_id="u1")
    assert rig.objects.paths("radar/") == [] and ledger_doc(rig)["gastoRadarMes"] > 0 and ledger_doc(rig)["consultasMes"] == 10


def test_capacity_simulation_15_radars_gives_about_83_diagnoses_and_respects_caps():
    rig = make_radar_rig()
    rig.clock.now_dt = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    exc = _exc()
    radars = diagnoses = 0
    for day in range(28):
        rig.clock.advance(24 * 3600)
        if day < 15:
            res = rig.ledger.reserve(HYDROGEN, with_search=True, kind="RADAR")
            rig.ledger.settle(res, cost_usd=0.0144, executed_queries=5)
            radars += 1
        while True:
            try:
                res = rig.ledger.reserve(HYDROGEN, with_search=False)
            except exc.BudgetDenied:
                break
            rig.ledger.settle(res, cost_usd=0.0191, executed_queries=0)
            diagnoses += 1
    doc = ledger_doc(rig)
    assert radars == 15 and 78 <= diagnoses <= 86
    assert doc["gastoMes"] <= 1.80 + 1e-9 and doc["gastoRadarMes"] <= 0.45 and doc["consultasMes"] == 75


def test_deadlines_and_lock_constants():
    c = mod("domain.constants")
    assert (c.LLM_TOTAL_DEADLINE_SECONDS, c.IN_FLIGHT_LOCK_TTL_SECONDS) == (125, 150)
    assert (c.RADAR_DEADLINE_SECONDS, c.RESERVATION_TTL_SECONDS) == (55, 180)
    assert c.PROMPT_VERSION == "tia-v3" and c.CONTRACT_VERSION == "1.2.0"
