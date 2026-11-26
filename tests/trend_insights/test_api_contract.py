"""T-7.1.17/18, T-7.2.9: contrato HTTP 1.2.0 (envelope, meta, TIA-001..007, 401, rate limit, campos que nao vazam)."""
import base64
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.trend_insights.helpers import (
    FORBIDDEN_COST_KEYS, FLASH, HYDROGEN, FakeLlm, collect_keys, make_evidence, make_llm_response, make_rig, mod,
)

BASE = "/api/v1/sales-trend/insights"
GEN = BASE + "/product/5102/generate"
BODY = {"metric": "revenue", "window": 3, "baseMonth": "2026-10", "comparisonMode": "point", "force": False}


def _app(rig, provider=None):
    router_mod = mod("api.router")
    service = mod("service.insights_service").InsightsService(
        evidence_provider=provider or (lambda query: make_evidence()),
        orchestrator=rig.orch, insight_store=rig.insight_store, ledger=rig.ledger, lease=rig.lease,
        settings=rig.settings, clock=rig.clock,
        index_status_provider=lambda: {"disponivel": True, "lastSyncAt": None, "totalActiveSkus": 3, "origem": "GCS"},
        migration_cache_status_provider=lambda: [],
    )
    app = FastAPI()
    app.include_router(router_mod.insights_router, prefix="/api/v1")
    app.dependency_overrides[router_mod.get_insights_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def _post(client, **over):
    return client.post(GEN, json={**BODY, **over})


def test_get_returns_envelope_and_never_calls_llm():
    rig = make_rig()
    client = _app(rig)
    r = client.get(BASE + "/product/5102?metric=revenue&window=3&baseMonth=2026-10&comparisonMode=point")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"data", "meta"} and body["meta"]["version"] == "1.2.0"  # revisado v3.1: contrato 1.2.0
    for key in ("dataReferencia", "modoComparacao", "promptVersion", "avisos", "indiceAfinidade", "ia"):
        assert key in body["meta"]
    ia = body["meta"]["ia"]
    for key in ("podeGerar", "geraComIa", "motivoTemplate", "diagnosticoSalvo", "diagnosticoVencido", "podeForcar",
                "geracaoEmAndamento", "orcamento"):
        assert key in ia
    assert set(ia["orcamento"]) == {"nivel"} and ia["orcamento"]["nivel"] == "NORMAL"
    assert body["data"]["diagnosticoIa"] is None
    for _ in range(3):
        client.get(BASE + "/product/5102")
    assert rig.llm.calls == []


@pytest.mark.parametrize("query", ["metric=profit", "window=2", "baseMonth=2026-13", "comparisonMode=range",
                                   "baseMonth=2099-01"])
def test_invalid_params_are_400_tia_001_without_echoing_values(query):
    r = _app(make_rig()).get(f"{BASE}/product/5102?{query}")
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "TIA-001" and err["fields"] and "meta" in r.json()
    assert query.split("=")[1] not in err["message"]


def test_invalid_sku_is_400():
    assert _app(make_rig()).get(BASE + "/product/abc").status_code == 400


@pytest.mark.parametrize("exc_name,status,code", [
    ("ProductNotFoundError", 404, "TIA-002"),
    ("InsufficientBaseError", 422, "TIA-003"),
])
def test_domain_errors_map_to_status_and_code(exc_name, status, code):
    exc = getattr(mod("domain.exceptions"), exc_name)

    def provider(query):
        raise exc()
    r = _app(make_rig(), provider).get(BASE + "/product/5102")
    assert r.status_code == status and r.json()["error"]["code"] == code
    assert "5102" not in r.json()["error"]["message"]


def test_source_unavailable_is_503_anl_001():
    def provider(query):
        raise mod("domain.ports").TrendSourceUnavailable()
    r = _app(make_rig(), provider).get(BASE + "/product/5102")
    assert r.status_code == 503 and r.json()["error"]["code"] == "ANL-001"


def test_unexpected_error_is_500_without_stacktrace():
    def provider(query):
        raise RuntimeError("segredo interno /etc/passwd")
    r = _app(make_rig(), provider).get(BASE + "/product/5102")
    assert r.status_code == 500
    assert "Traceback" not in r.text and "segredo" not in r.text and "passwd" not in r.text


# --- POST
def test_post_llm_then_cache_flow():
    rig = make_rig()
    client = _app(rig)
    r1 = _post(client)
    assert r1.status_code == 200
    m1 = r1.json()["meta"]
    assert m1["origem"] == "llm" and m1["modelo"] == HYDROGEN and m1["reutilizado"] is False
    assert m1["geradoEm"] and m1["motivoTemplate"] is None and m1["ia"]["diagnosticoSalvo"] is True
    d = r1.json()["data"]["diagnosticoIa"]
    assert d["resumo"] and d["origem"] == "llm" and d["modelo"] == HYDROGEN and d["promptVersion"] == "tia-v3"
    assert r1.json()["data"].get("resumoAutomatico") is None
    r2 = _post(client)
    assert r2.json()["meta"]["origem"] == "cache" and r2.json()["meta"]["reutilizado"] is True
    assert len(rig.llm.calls) == 1
    g = client.get(BASE + "/product/5102")
    assert g.json()["data"]["diagnosticoIa"]["resumo"] == d["resumo"]


def test_post_fallback_reports_flash():
    err = mod("llm.client").LlmTransientError
    rig = make_rig(llm=FakeLlm([err(), err(), make_llm_response(model=FLASH)]))
    m = _post(_app(rig)).json()["meta"]
    assert m["origem"] == "fallback" and m["modelo"] == FLASH


@pytest.mark.parametrize("env,provider_over,motivo", [
    ({"TREND_AI_ENABLED": "false"}, {}, "IA_DESLIGADA"),
    ({}, {"variacao_pct": -1.0}, "GATE_VARIACAO"),
    ({}, {"delta_receita": -10.0}, "GATE_VALOR_BAIXO"),
    ({}, {"residual_share": 0.05}, "GATE_RESIDUO_BAIXO"),
])
def test_post_template_is_200_with_resumo_automatico(env, provider_over, motivo):
    rig = make_rig(settings_env=env)
    r = _app(rig, lambda q: make_evidence(**provider_over)).post(GEN, json=BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["origem"] == "template" and body["meta"]["motivoTemplate"] == motivo
    assert body["data"]["diagnosticoIa"] is None and body["meta"]["modelo"] is None and body["meta"]["geradoEm"] is None
    text = body["data"]["resumoAutomatico"]
    assert text and len(text) <= 400 and not re.search(r"\d", text)
    assert rig.llm.calls == []


def test_post_budget_exhausted_is_template_not_503():
    from tests.trend_insights.helpers import seed_budget
    rig = make_rig()
    seed_budget(rig, month=1.80)
    r = _post(_app(rig))
    assert r.status_code == 200 and r.json()["meta"]["motivoTemplate"] == "ORCAMENTO_ESGOTADO"


def test_post_ia_failure_is_template_with_warning_and_no_503():
    bad = make_llm_response("lixo")
    r = _post(_app(make_rig(llm=FakeLlm([bad, bad]))))
    assert r.status_code == 200
    assert "IA_FALHOU" in [a["codigo"] for a in r.json()["meta"]["avisos"]]


def test_post_sem_variacao_is_422():
    r = _app(make_rig(), lambda q: make_evidence(modo_diagnostico="SEM_VARIACAO", variacao_pct=0.5)).post(GEN, json=BODY)
    assert r.status_code == 422 and r.json()["error"]["code"] == "TIA-003"
    assert r.json()["error"]["message"] == "Não há variação relevante para analisar."


def test_post_deep_field_is_ignored_and_invalid_body_is_400():
    rig = make_rig()
    client = _app(rig)
    assert client.post(GEN, json={**BODY, "deep": True}).status_code == 200
    assert set(rig.llm.models) == {HYDROGEN}
    assert client.post(GEN, json={**BODY, "force": "talvez"}).status_code == 400
    assert client.post(GEN, content="{nao json", headers={"Content-Type": "application/json"}).status_code == 400


def test_post_rate_limit_429_with_motivo_and_retry_after():
    rig = make_rig()
    # evidencia igual vira cache; cada pedido usa uma evidencia nova para forcar chamadas ao LLM
    evidences = iter([make_evidence(delta_observado=-3000.0 - i * 100, variacao_pct=-30.0 - i) for i in range(5)])
    client = _app(rig, lambda q: next(evidences))
    assert _post(client).status_code == 200 and _post(client).status_code == 200
    r = _post(client)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "TIA-004" and r.json()["error"]["motivo"] == "LIMITE_DE_PEDIDOS"
    assert int(r.headers["Retry-After"]) > 0


def test_no_response_leaks_cost_tokens_or_hash():
    rig = make_rig(llm=FakeLlm([make_llm_response(queries=2)]))
    client = _app(rig)
    bodies = [_post(client).json(), _post(client).json(), client.get(BASE + "/product/5102").json(),
              client.get(BASE + "/health").json()]
    stored_hash = mod("llm.evidence_payload").compute_evidence_hash(make_evidence())
    for body in bodies:
        keys = [k.lower() for k in collect_keys(body)]
        assert not [k for k in keys if any(bad in k for bad in FORBIDDEN_COST_KEYS)], keys
        assert stored_hash not in str(body) and "neon" not in str(body).lower()


def test_health_has_ia_state_and_budget_level_only():
    rig = make_rig()
    r = _app(rig).get(BASE + "/health")
    data = r.json()["data"]
    assert r.status_code == 200 and data["ia"]["ligada"] is True
    assert data["ia"]["modeloPadrao"] == HYDROGEN and data["ia"]["modeloFallback"] == FLASH
    assert data["orcamento"]["nivel"] == "NORMAL" and "credencial" not in str(data).lower()
    off = _app(make_rig(settings_env={"TREND_AI_ENABLED": "false"})).get(BASE + "/health")
    assert off.json()["data"]["ia"]["ligada"] is False


def test_get_meta_ia_reflects_kill_switch_and_exhausted_budget():
    off = _app(make_rig(settings_env={"TREND_AI_ENABLED": "false"})).get(BASE + "/product/5102").json()["meta"]["ia"]
    assert off["geraComIa"] is False and off["motivoTemplate"] == "IA_DESLIGADA" and off["podeGerar"] is True
    from tests.trend_insights.helpers import seed_budget
    rig = make_rig()
    seed_budget(rig, month=1.50)
    alert = _app(rig).get(BASE + "/product/5102").json()["meta"]["ia"]
    assert alert["orcamento"]["nivel"] == "ALERTA" and alert["podeForcar"] is False


def test_app_registers_routes_and_requires_basic_auth_in_production(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_USERNAME", "u")
    monkeypatch.setenv("AUTH_PASSWORD", "p")
    from src.api import app
    paths = set(app.openapi()["paths"])  # FastAPI >= 0.141 inclui routers de forma preguicosa: `app.routes` nao os expoe
    assert "/api/v1/sales-trend/insights/product/{sku}" in paths
    assert "/api/v1/sales-trend/insights/product/{sku}/generate" in paths
    assert "/api/v1/sales-trend/insights/health" in paths
    client = TestClient(app)
    assert client.get(BASE + "/product/5102").status_code == 401
    assert client.post(GEN, json=BODY).status_code == 401
    assert "WWW-Authenticate" in client.get(BASE + "/health").headers
