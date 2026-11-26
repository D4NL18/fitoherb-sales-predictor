"""Testes do script de spike 7.2-S com fakes (sem rede)."""
import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

_path = Path(__file__).resolve().parents[2] / "scripts" / "trend_insights_spike.py"
_spec = importlib.util.spec_from_file_location("trend_insights_spike", _path)
spike = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spike)

TODAY = date(2026, 11, 26)
PRICING = {"search_per_query": 0.001, "models": {m: [{"from": "2026-01-01", "input_per_million": 1.0,
                                                       "output_per_million": 5.0}] for m in spike.MODELS}}
ENV = {"GOOGLE_CLOUD_PROJECT": "p", "TREND_AI_LOCATION": "us-central1", "TREND_AI_PRICING_JSON": json.dumps(PRICING)}


class FakeTypes:
    def __getattr__(self, name):
        return lambda **kw: NS(**kw)


def raw(tokens=1000, queries=2):
    meta = NS(web_search_queries=["a"] * queries, grounding_chunks=[1], search_entry_point=NS())
    usage = NS(prompt_token_count=tokens, candidates_token_count=100, thoughts_token_count=50,
               cached_content_token_count=0, tool_use_prompt_token_count=0)
    return NS(text="{}", usage_metadata=usage, candidates=[NS(grounding_metadata=meta)])


class FakeClient:
    def __init__(self, response=None, error=None):
        self.models = self
        self.calls = 0
        self._r, self._e = response, error

    def generate_content(self, **kw):
        self.calls += 1
        if self._e:
            raise self._e
        return self._r


def test_missing_env_and_global_rejected():
    with pytest.raises(spike.SpikeError):
        spike.check_environment({})
    with pytest.raises(spike.SpikeError):
        spike.check_environment({**ENV, "TREND_AI_LOCATION": "global"})


def test_main_without_confirm_makes_no_calls(capsys):
    assert spike.main([], env=ENV) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True


def test_main_missing_env_exit_code(capsys):
    assert spike.main(["--confirm-billing"], env={}) == 2
    assert "ausentes" in capsys.readouterr().err


def test_run_spike_report_and_fields():
    client = FakeClient(raw())
    report = spike.run_spike(client, FakeTypes(), PRICING, TODAY)
    assert client.calls == 4 and len(report["calls"]) == 4
    assert all(report["schema_plus_search"].values())
    assert report["calls"][0]["fields_present"]["thoughts_token_count"] is True
    assert report["estimated_total_usd"] > 0


def test_cost_formula():
    cost = spike.estimate_cost(PRICING, "gemini-4-hydrogen",
                               {"input": 1_000_000, "tool": 0, "output": 100_000, "thinking": 100_000}, 2, TODAY)
    assert cost == pytest.approx(1.0 + 1.0 + 0.002)


def test_aborts_when_over_limit():
    with pytest.raises(spike.SpikeError):
        spike.run_spike(FakeClient(raw(tokens=1_000_000)), FakeTypes(), PRICING, TODAY)


def test_abort_stops_after_first_expensive_call():
    client = FakeClient(raw())
    with pytest.raises(spike.SpikeError):
        spike.run_spike(client, FakeTypes(), {**PRICING, "search_per_query": 5.0}, TODAY)
    assert client.calls == 1


def test_sdk_error_recorded_without_message():
    report = spike.run_spike(FakeClient(error=RuntimeError("prompt secreto")), FakeTypes(), PRICING, TODAY)
    assert not any(report["schema_plus_search"].values())
    assert "secreto" not in json.dumps(report)
