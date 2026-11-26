"""T-7.2B.5 / T-7.2B.8: rate limit em memoria (LGPD-TIA-11) e inexistencia do Neon. P-176, P-177."""
import re
from pathlib import Path

import pytest

from tests.trend_insights.helpers import (
    FLASH, HYDROGEN, PRICING_JSON, FakeClock, FakeLlm, make_evidence, make_llm_response, make_rig, make_settings,
    mod, seed_budget,
)

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "src" / "modules" / "trend_insights"


def _guard(clock=None):
    clock = clock or FakeClock()
    return clock, mod("service.generation_guard").GenerationGuard(settings=make_settings(), clock=clock)


def _refused():
    return mod("domain.exceptions").GenerationRefused


def test_two_per_minute_then_refused_with_retry_after_and_recovers():
    clock, guard = _guard()
    guard.check("alice"); guard.check("alice")
    with pytest.raises(_refused()) as exc:
        guard.check("alice")
    assert exc.value.motivo == "LIMITE_DE_PEDIDOS" and exc.value.retry_after_seconds > 0
    clock.advance(61)
    guard.check("alice")


def test_ten_per_day_and_users_are_independent():
    clock, guard = _guard()
    for _ in range(5):
        guard.check("alice"); guard.check("alice"); clock.advance(61)
    with pytest.raises(_refused()) as exc:
        guard.check("alice")
    assert exc.value.motivo == "LIMITE_DIARIO"
    guard.check("bob")


def test_force_limited_to_three_per_day():
    clock, guard = _guard()
    for _ in range(3):
        guard.check("alice", force=True); clock.advance(61)
    with pytest.raises(_refused()) as exc:
        guard.check("alice", force=True)
    assert exc.value.motivo == "LIMITE_DIARIO"


def test_guard_state_never_holds_identifier_in_clear():
    _, guard = _guard()
    guard.check("alice@empresa.com"); guard.check("10.0.0.1")
    dump = repr(vars(guard)) + repr([vars(v) if hasattr(v, "__dict__") else v for v in vars(guard).values()])
    assert "alice" not in dump and "10.0.0.1" not in dump


def test_templates_and_cache_do_not_consume_the_limit():
    rig = make_rig()
    for _ in range(5):
        assert rig.orch.generate(make_evidence(variacao_pct=-1.0), caller_id="u").origem == "template"
    assert rig.orch.generate(make_evidence(), caller_id="u").origem == "llm"


# --- Neon
def _scan_files():
    files = list(PKG_DIR.rglob("*.py")) if PKG_DIR.is_dir() else []
    files += [p for p in (ROOT / ".env.example", ROOT / "Dockerfile") if p.exists()]
    workflows = ROOT / ".github" / "workflows"
    if workflows.is_dir():
        files += list(workflows.glob("*.yml"))
    return files


def test_package_exists_for_static_scan():
    assert PKG_DIR.is_dir() and list(PKG_DIR.rglob("*.py"))


def test_no_neon_deep_or_escalation_anywhere_in_code_or_config():
    pattern = re.compile(r"neon|escalon|\bdeep\b|tipoAnalise", re.IGNORECASE)
    offenders = [str(p) for p in _scan_files() if pattern.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert offenders == []


def test_config_rejects_unlisted_models():
    with pytest.raises(ValueError):
        make_settings(TREND_AI_MODEL_DEFAULT="gemini-4-neon")
    with pytest.raises(ValueError):
        make_settings(TREND_AI_MODEL_FALLBACK="gemini-4-neon")


def test_pricing_json_with_extra_model_is_rejected():
    import json
    data = json.loads(PRICING_JSON)
    data["models"]["gemini-4-neon"] = [{"from": "2026-01-01", "input_per_million": 3.0, "output_per_million": 15.0}]
    with pytest.raises(ValueError):
        make_settings(TREND_AI_PRICING_JSON=json.dumps(data))


@pytest.mark.parametrize("scenario", ["normal", "force", "transient", "schema", "grounding", "alert"])
def test_every_llm_call_in_every_scenario_uses_only_allowed_models(scenario):
    client = mod("llm.client")
    script = None
    if scenario == "transient":
        script = [client.LlmTransientError()] * 3
    if scenario == "schema":
        script = [make_llm_response("lixo")] * 2
    rig = make_rig(llm=FakeLlm(script))
    ev = make_evidence(residual_share=0.9) if scenario == "grounding" else make_evidence()
    rig.orch.generate(ev, caller_id="u", force=(scenario == "force"))
    if scenario == "alert":
        seed_budget(rig, month=1.5)
        rig.clock.advance(61)
        rig.orch.generate(ev, caller_id="u", force=True)
    assert rig.llm.calls and set(rig.llm.models) <= {HYDROGEN, FLASH}
