"""T-7.2B.1/2, T-7.2.4: custo, niveis, reserva/acerto no livro de gastos, teto diario/mensal, falha fechada. P-178, DA-09."""
import json
from datetime import datetime, timezone

import pytest

from tests.trend_insights.helpers import (
    FLASH, HYDROGEN, PRICING_JSON, FakeClock, FakeObjectStore, budget_path, make_rig, make_settings, mod, seed_budget,
)


def _usage(i=4000, o=800, t=300):
    return mod("llm.client").LlmUsage(input_tokens=i, output_tokens=o, thinking_tokens=t, cached_input_tokens=0, tool_tokens=0)


def _pricing():
    return mod("llm.pricing")


def _table():
    return _pricing().parse_pricing(PRICING_JSON)


def test_cost_is_tokens_plus_billable_queries():
    p = _pricing()
    base = dict(model_id=HYDROGEN, usage=_usage(), pricing=_table(), on_date=datetime(2026, 11, 24).date(),
                free_queries=1500)
    # 4000*1,5/1e6 + (800+300)*7,5/1e6 = 0,006 + 0,00825
    assert p.compute_cost(executed_queries=0, month_queries_before=0, **base) == pytest.approx(0.01425)
    assert p.compute_cost(executed_queries=2, month_queries_before=0, **base) == pytest.approx(0.01425)  # cota gratis assumida
    assert p.compute_cost(executed_queries=2, month_queries_before=1499, **base) == pytest.approx(0.01425 + 0.014)
    assert p.compute_cost(executed_queries=2, month_queries_before=1500, **base) == pytest.approx(0.01425 + 0.028)


def test_flash_price_changes_on_2027_01_01():
    p, t = _pricing(), _table()
    kw = dict(model_id=FLASH, usage=_usage(), pricing=t, executed_queries=0, month_queries_before=0, free_queries=1500)
    before = p.compute_cost(on_date=datetime(2026, 12, 31).date(), **kw)
    after = p.compute_cost(on_date=datetime(2027, 1, 1).date(), **kw)
    assert before == pytest.approx(4000 * 0.75e-6 + 1100 * 3.75e-6)
    assert after == pytest.approx(4000 * 1.5e-6 + 1100 * 7.5e-6)


def test_pricing_only_knows_the_two_allowed_models():
    assert set(_table().model_ids()) == {HYDROGEN, FLASH}


def test_reservation_estimate_values():
    est = mod("domain.budget").reservation_amount
    t = _table()
    assert est(HYDROGEN, t, with_search=False, month_queries=0) == pytest.approx(0.03075, abs=1e-5)
    assert est(HYDROGEN, t, with_search=True, month_queries=0) == pytest.approx(0.03075, abs=1e-5)
    assert est(HYDROGEN, t, with_search=True, month_queries=1499) == pytest.approx(0.07275, abs=1e-5)


@pytest.mark.parametrize("month,day,level", [
    (0.0, 0.0, "NORMAL"), (1.43, 0.0, "NORMAL"), (1.44, 0.0, "ALERTA"), (1.79, 0.1, "ALERTA"),
    (1.80, 0.0, "ESGOTADO"), (0.1, 0.20, "ESGOTADO"), (0.1, 0.19, "NORMAL"),
])
def test_budget_levels(month, day, level):
    assert mod("domain.budget").budget_level(month_spent=month, day_spent=day, monthly_cap=1.80, daily_cap=0.20) == level


def _ledger(rig=None):
    rig = rig or make_rig()
    return rig, rig.ledger


def test_reserve_then_settle_accounts_real_cost_and_clears_reservation():
    rig, ledger = _ledger()
    res = ledger.reserve(HYDROGEN, with_search=False)
    doc = rig.objects.objects[budget_path(rig.clock)]
    assert len(doc["reservado"]) == 1
    ledger.settle(res, cost_usd=0.014, executed_queries=2)
    doc = rig.objects.objects[budget_path(rig.clock)]
    assert doc["gastoMes"] == pytest.approx(0.014) and doc["gastoDia"]["valor"] == pytest.approx(0.014)
    assert doc["reservado"] == [] and doc["consultasMes"] == 2


def test_release_returns_reservation_without_spending():
    rig, ledger = _ledger()
    ledger.release(ledger.reserve(HYDROGEN, with_search=False))
    doc = rig.objects.objects[budget_path(rig.clock)]
    assert doc["gastoMes"] == 0 and doc["reservado"] == []


def test_orphan_reservation_expires_after_180_seconds():
    rig, ledger = _ledger()
    ledger.reserve(HYDROGEN, with_search=False)
    seed = rig.objects.objects[budget_path(rig.clock)]
    assert mod("domain.constants").RESERVATION_TTL_SECONDS == 180  # DA-13 item 8
    rig.clock.advance(181)
    ledger.reserve(HYDROGEN, with_search=False)
    live = [r for r in rig.objects.objects[budget_path(rig.clock)]["reservado"]]
    assert len(live) == 1 and seed["reservado"][0] != live[0]


def test_simultaneous_reservations_add_up_and_never_exceed_cap():
    rig, ledger = _ledger()
    seed_budget(rig, month=1.70, day=0.0)
    granted = 0
    for _ in range(5):
        try:
            ledger.reserve(HYDROGEN, with_search=False)
            granted += 1
        except mod("domain.exceptions").BudgetDenied:
            pass
    assert granted == 3  # (1,80 - 1,70) / 0,03075 = 3,25 reservas


def test_daily_cap_denies_even_with_monthly_room():
    rig, ledger = _ledger()
    seed_budget(rig, month=0.5, day=0.18)
    with pytest.raises(mod("domain.exceptions").BudgetDenied):
        ledger.reserve(HYDROGEN, with_search=False)


def test_conflict_retries_up_to_five_times_then_fails_closed():
    rig, ledger = _ledger()
    rig.objects.conflicts_to_inject = 4
    ledger.reserve(HYDROGEN, with_search=False)  # 5a tentativa passa
    rig.objects.conflicts_to_inject = 6
    with pytest.raises(mod("domain.exceptions").BudgetUnavailable):
        ledger.reserve(HYDROGEN, with_search=False)


def test_unreadable_ledger_fails_closed():
    rig, ledger = _ledger()
    rig.objects.fail = True
    with pytest.raises(mod("domain.exceptions").BudgetUnavailable):
        ledger.reserve(HYDROGEN, with_search=False)


def test_month_and_day_roll_over_in_utc_minus_3():
    clock = FakeClock(datetime(2026, 12, 1, 2, 0, tzinfo=timezone.utc))  # 30/11 23:00 em UTC-3
    rig = make_rig()
    rig.clock.now_dt = clock.now_dt
    rig.ledger.reserve(HYDROGEN, with_search=False)
    assert "ai-budget/2026-11.json" in rig.objects.objects
    rig.clock.advance(3600)  # 03:00Z = 00:00 de 01/12
    rig.ledger.reserve(HYDROGEN, with_search=False)
    assert "ai-budget/2026-12.json" in rig.objects.objects


def test_ledger_object_has_no_user_ip_or_email():
    rig, ledger = _ledger()
    ledger.settle(ledger.reserve(HYDROGEN, with_search=False), cost_usd=0.01, executed_queries=0)
    text = json.dumps(rig.objects.objects[budget_path(rig.clock)]).lower()
    assert not any(w in text for w in ("user", "usuario", "ip", "email", "@"))


def test_level_reader_reflects_alert_and_exhausted():
    rig, ledger = _ledger()
    seed_budget(rig, month=1.50)
    assert ledger.level() == "ALERTA"
    rig.clock.advance(61)
    seed_budget(rig, month=1.80)
    assert ledger.level() == "ESGOTADO"


@pytest.mark.parametrize("cost,lo,hi", [(0.0173, 95, 104), (0.0325, 50, 56)])
def test_capacity_simulation_never_exceeds_monthly_cap(cost, lo, hi):
    rig, ledger = _ledger()
    rig.clock.now_dt = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
    exc = mod("domain.exceptions")
    done = 0
    for _ in range(28):
        rig.clock.advance(24 * 3600)
        while True:
            try:
                res = ledger.reserve(HYDROGEN, with_search=False)
            except exc.BudgetDenied:
                break
            ledger.settle(res, cost_usd=cost, executed_queries=0)
            done += 1
    spent = sum(json.loads(json.dumps(v)).get("gastoMes", 0) for k, v in rig.objects.objects.items() if k.startswith("ai-budget/"))
    assert lo <= done <= hi
    assert spent <= 1.80 + 1e-9


def test_settings_defaults_and_validation():
    s = make_settings()
    assert s.ai_enabled is True
    assert s.monthly_budget_usd == pytest.approx(1.80) and s.daily_budget_usd == pytest.approx(0.20)
    assert s.model_default == HYDROGEN and s.model_fallback == FLASH
    assert make_settings(TREND_AI_ENABLED="false").ai_enabled is False


def test_grounding_free_quota_is_configurable_and_validated():
    assert make_settings().free_queries == 1500
    assert make_settings(TREND_AI_GROUNDING_FREE_QUERIES=0).free_queries == 0
    assert make_settings(TREND_AI_GROUNDING_FREE_QUERIES=5000).free_queries == 5000
    for invalid in ("-1", "1.5", "muitas"):
        with pytest.raises(mod("domain.exceptions").SettingsError):
            make_settings(TREND_AI_GROUNDING_FREE_QUERIES=invalid)


def test_month_queries_reader_follows_the_ledger_and_fails_toward_paid_mode():
    rig, ledger = _ledger()
    assert ledger.month_queries() == 0
    rig.clock.advance(61)
    seed_budget(rig, month=0.5, queries=1500)
    assert ledger.month_queries() == 1500
    rig.clock.advance(61)
    rig.objects.fail = True
    assert ledger.month_queries() >= rig.settings.free_queries
