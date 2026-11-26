"""T-7.0c.3: rota interna `POST /internal/v1/affinity-index/sync` (OIDC) e isencao minima no middleware Basic.
O verificador OIDC e o executor da sincronizacao sao injetados: nenhum teste usa rede, Google ou SQL."""
import base64
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.trend_insights.helpers import mod

PATH = "/internal/v1/affinity-index/sync"
AUDIENCE, INVOKER = "https://fitoherb.example/internal", "sa-affinity-scheduler@proj.iam.gserviceaccount.com"
SUMMARY = {
    "last_sync_at": "2026-11-24T03:00:41.512Z", "recomputed": True, "total_active_skus": 1339,
    "gallery_products_fetched": 1180, "gallery_matched_skus": 1021, "added_count": 3, "updated_count": 1,
    "removed_count": 2, "unchanged_count": 1335, "duration_ms": 38215,
}


class FakeVerifier:
    """Dublê do `google.oauth2.id_token`: valida o `aud` esperado e devolve as claims do token de teste."""

    def __init__(self):
        self.tokens = {}

    def verify(self, token, audience):
        claims = self.tokens.get(token)
        if claims is None or claims.get("aud") != audience:
            raise ValueError("token invalido")
        return claims


class FakeRunner:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def __call__(self, force):
        self.calls.append(force)
        if self.error:
            raise self.error
        return {**SUMMARY, "object_generation": "1764039641512000"}


@pytest.fixture
def rig(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("AUTH_USERNAME", "fito")
    monkeypatch.setenv("AUTH_PASSWORD", "segredo")
    monkeypatch.setenv("AFFINITY_SYNC_AUDIENCE", AUDIENCE)
    monkeypatch.setenv("AFFINITY_SYNC_INVOKER_SA", INVOKER)
    internal = mod("api.internal_router")
    app = FastAPI()
    app.include_router(internal.internal_router)
    app.include_router(mod("api.router").insights_router, prefix="/api/v1")
    verifier, runner = FakeVerifier(), FakeRunner()
    verifier.tokens["good"] = {"aud": AUDIENCE, "email": INVOKER, "email_verified": True}
    verifier.tokens["other-aud"] = {"aud": "outra", "email": INVOKER, "email_verified": True}
    verifier.tokens["other-sa"] = {"aud": AUDIENCE, "email": "intruso@x.com", "email_verified": True}
    verifier.tokens["unverified"] = {"aud": AUDIENCE, "email": INVOKER, "email_verified": False}
    app.dependency_overrides[internal.get_oidc_verifier] = lambda: verifier
    app.dependency_overrides[internal.get_affinity_sync_runner] = lambda: runner
    from src.core.auth import HTTPBasicAuthASGIMiddleware

    app.add_middleware(HTTPBasicAuthASGIMiddleware)
    return SimpleNamespace(client=TestClient(app, raise_server_exceptions=False), runner=runner, verifier=verifier,
                           app=app, internal=internal)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _basic():
    return {"Authorization": "Basic " + base64.b64encode(b"fito:segredo").decode()}


def _error_without_timestamp(response):
    body = response.json()
    body["meta"].pop("timestamp", None)
    return body


def test_missing_token_is_401_tia_006_not_a_basic_challenge(rig):
    r = rig.client.post(PATH)
    assert r.status_code == 401 and r.json()["error"]["code"] == "TIA-006"
    assert "basic" not in r.headers.get("www-authenticate", "").lower()
    assert rig.runner.calls == []


@pytest.mark.parametrize("token", ["lixo", "other-aud", "other-sa", "unverified"])
def test_invalid_audience_caller_or_unverified_email_all_look_the_same(rig, token):
    reference = _error_without_timestamp(rig.client.post(PATH))
    r = rig.client.post(PATH, headers=_bearer(token))
    assert r.status_code == 401 and _error_without_timestamp(r) == reference
    assert rig.runner.calls == []


def test_basic_credentials_alone_do_not_authorize_the_internal_route(rig):
    r = rig.client.post(PATH, headers=_basic())
    assert r.status_code == 401 and r.json()["error"]["code"] == "TIA-006"


def test_without_configured_audience_or_invoker_the_route_is_closed(rig, monkeypatch):
    monkeypatch.delenv("AFFINITY_SYNC_AUDIENCE")
    assert rig.client.post(PATH, headers=_bearer("good")).status_code == 401
    monkeypatch.setenv("AFFINITY_SYNC_AUDIENCE", AUDIENCE)
    monkeypatch.delenv("AFFINITY_SYNC_INVOKER_SA")
    assert rig.client.post(PATH, headers=_bearer("good")).status_code == 401


def test_valid_token_runs_sync_and_returns_contract_summary(rig):
    r = rig.client.post(PATH, headers=_bearer("good"))
    assert r.status_code == 200 and rig.runner.calls == [False]
    body = r.json()
    assert set(body) == {"data", "meta"} and body["meta"]["version"] == "1.2.0"
    assert body["data"] == {
        "lastSyncAt": "2026-11-24T03:00:41.512Z", "recomputed": True, "totalActiveSkus": 1339,
        "galleryProductsFetched": 1180, "galleryMatchedSkus": 1021, "addedCount": 3, "updatedCount": 1,
        "removedCount": 2, "unchangedCount": 1335, "durationMs": 38215, "geracaoObjeto": "1764039641512000",
    }


def test_force_query_is_passed_through(rig):
    rig.client.post(PATH + "?force=true", headers=_bearer("good"))
    assert rig.runner.calls == [True]


def test_busy_lease_is_409_tia_007(rig):
    rig.runner.error = mod("domain.exceptions").AffinitySyncBusy()
    r = rig.client.post(PATH, headers=_bearer("good"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "TIA-007"


def test_unavailable_source_is_503_anl_001_and_never_leaks_details(rig):
    rig.runner.error = mod("domain.ports").TrendSourceUnavailable()
    r = rig.client.post(PATH, headers=_bearer("good"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "ANL-001"


def test_other_internal_paths_and_methods_still_require_basic(rig):
    for method, path in (("get", PATH), ("post", "/internal/v1/outra-rota"), ("post", PATH + "/")):
        r = getattr(rig.client, method)(path, headers=_bearer("good"))
        assert r.status_code == 401 and r.headers["www-authenticate"].lower().startswith("basic"), (method, path)


def test_public_api_still_requires_basic(rig):
    r = rig.client.get("/api/v1/sales-trend/insights/health")
    assert r.status_code == 401 and r.headers["www-authenticate"].lower().startswith("basic")


def test_oidc_claims_rule_is_pure_domain():
    identity = mod("domain.scheduler_identity")
    ok = {"aud": AUDIENCE, "email": INVOKER.upper(), "email_verified": True}
    assert identity.is_authorized_invoker(ok, AUDIENCE, INVOKER) is True
    assert identity.is_authorized_invoker({**ok, "email_verified": "true"}, AUDIENCE, INVOKER) is False
    assert identity.is_authorized_invoker(ok, AUDIENCE, "") is False
    assert identity.is_authorized_invoker({**ok, "aud": ["x"]}, AUDIENCE, INVOKER) is False


def test_adapter_translates_service_failures(monkeypatch):
    adapter = mod("adapters.affinity_sync_adapter")
    aff = adapter.product_affinity_service
    domain = mod("domain.exceptions")
    ports = mod("domain.ports")

    def failing(error):
        def sync(force=False):
            raise error
        return sync

    monkeypatch.setattr(aff, "sync_product_affinity_index", failing(aff.AffinitySyncBusyError()))
    with pytest.raises(domain.AffinitySyncBusy):
        adapter.run_affinity_sync(False)
    monkeypatch.setattr(aff, "sync_product_affinity_index", failing(aff.AffinityIndexConflictError()))
    with pytest.raises(domain.AffinitySyncBusy):
        adapter.run_affinity_sync(False)
    monkeypatch.setattr(aff, "sync_product_affinity_index", failing(RuntimeError("segredo do ERP")))
    with pytest.raises(ports.TrendSourceUnavailable):
        adapter.run_affinity_sync(False)


def test_adapter_returns_summary_with_generation_and_resets_report_cache(monkeypatch):
    adapter = mod("adapters.affinity_sync_adapter")
    monkeypatch.setattr(adapter.product_affinity_service, "sync_product_affinity_index",
                        lambda force=False: dict(SUMMARY))
    monkeypatch.setattr(adapter.product_affinity_service, "get_loaded_generation", lambda: 77)
    resets = []
    monkeypatch.setattr(adapter.analytics_service, "reset_cannibalization_report_cache", lambda: resets.append(1))
    result = adapter.run_affinity_sync(True)
    assert result["object_generation"] == "77" and resets == [1]


def test_no_in_process_daily_cron_remains():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "src" / "api.py").read_text(encoding="utf-8")
    assert "_daily_affinity_cron" not in source
    assert "internal_router" in source
