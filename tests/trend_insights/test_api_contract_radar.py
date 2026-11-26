"""T-7.2R.8/15: contrato 1.2.0 (fatoresExternos[8], radar, radarExterno, meta.ia.radar, health.radar), bloco do radar
fora do evidenceHash e varredura de custo estendida (contrato 4.4)."""
import json
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.trend_insights.helpers import FORBIDDEN_COST_KEYS, HYDROGEN, collect_keys, make_evidence, make_llm_response, mod
from tests.trend_insights.radar_helpers import (
    COST_DIM, DIMENSIONS, RoutedLlm, avaliacao, make_radar_rig, plant_radar, seed_ledger, valid_diag_text,
)

BASE = "/api/v1/sales-trend/insights"
GEN = BASE + "/product/5102/generate"
BODY = {"metric": "revenue", "window": 3, "baseMonth": "2026-10", "comparisonMode": "point", "force": False}
EXTENDED_FORBIDDEN = FORBIDDEN_COST_KEYS + ("radarhash", "radarref", "searchsuggestions")
EXTERNAL_KEYS = {"dimensao", "status", "direcao", "confianca", "relevanciaAoProduto", "relacaoTemporal", "rotulo",
                 "origemEvidencia", "motivoNaoAvaliado", "tema", "notaRadar", "nota", "fontes"}
RADAR_DIM_KEYS = {"dimensao", "status", "movimento", "intensidade", "tema", "notaRadar", "fontes"}


def _app(rig, provider=None):
    router_mod = mod("api.router")
    service = mod("service.insights_service").InsightsService(
        evidence_provider=provider or (lambda query: make_evidence()),
        orchestrator=rig.orch, insight_store=rig.insight_store, ledger=rig.ledger, lease=rig.lease,
        settings=rig.settings, clock=rig.clock, radar_service=rig.radar,
        index_status_provider=lambda: {"disponivel": True, "lastSyncAt": None, "totalActiveSkus": 3, "origem": "GCS"},
        migration_cache_status_provider=lambda: [],
    )
    app = FastAPI()
    app.include_router(router_mod.insights_router, prefix="/api/v1")
    app.dependency_overrides[router_mod.get_insights_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def _get(client):
    return client.get(BASE + "/product/5102?metric=revenue&window=3&baseMonth=2026-10&comparisonMode=point")


def test_versions():
    r = _get(_app(make_radar_rig()))
    assert r.json()["meta"]["version"] == "1.2.0" and r.json()["meta"]["promptVersion"] == "tia-v3"


def test_get_without_radar_reads_only_and_reports_absent():
    rig = make_radar_rig()
    body = _get(_app(rig)).json()
    assert body["meta"]["ia"]["radar"] == {"estado": "AUSENTE", "geradoEm": None}
    assert body["data"]["radarExterno"] is None and rig.llm.calls == [] and rig.objects.paths("radar/") == []


def test_get_with_existing_radar_shows_read_only_block_without_direction():
    rig = make_radar_rig()
    plant_radar(rig.objects, age_days=10, clock=rig.clock)
    body = _get(_app(rig)).json()
    view = body["data"]["radarExterno"]
    assert body["meta"]["ia"]["radar"]["estado"] == "FRESCO" and body["data"]["diagnosticoIa"] is None
    assert set(view) == {"assunto", "mesBase", "geradoEm", "diasDesdeGeracao", "desatualizado", "dimensoes"}
    assert set(view["assunto"]) == {"termo", "tipo"} and view["diasDesdeGeracao"] == 10 and view["desatualizado"] is False
    assert [d["dimensao"] for d in view["dimensoes"]] == list(DIMENSIONS)
    assert all(set(d) == RADAR_DIM_KEYS for d in view["dimensoes"]) and rig.llm.calls == []


def test_stale_radar_is_reported_as_desatualizado():
    rig = make_radar_rig()
    plant_radar(rig.objects, age_days=60, clock=rig.clock)
    body = _get(_app(rig)).json()
    assert body["meta"]["ia"]["radar"]["estado"] == "DESATUALIZADO" and body["data"]["radarExterno"]["desatualizado"] is True


def test_post_llm_returns_eight_external_factors_radar_ref_and_generated_state():
    rig = make_radar_rig()
    r = _app(rig).post(GEN, json=BODY)
    body = r.json()
    d = body["data"]["diagnosticoIa"]
    assert r.status_code == 200 and d["promptVersion"] == "tia-v3" and body["meta"]["ia"]["radar"]["estado"] == "GERADO_AGORA"
    items = d["fatoresExternos"]
    assert [i["dimensao"] for i in items] == list(DIMENSIONS) and all(set(i) == EXTERNAL_KEYS for i in items)
    for item in items:
        assert item["status"] in ("AVALIADA", "SEM_EVIDENCIA", "NAO_AVALIADA") and item["confianca"] in ("MEDIA", "BAIXA")
        assert item["direcao"] in ("PRESSAO_ALTA", "PRESSAO_BAIXA", "NEUTRA", "INDETERMINADA")
        for src in item["fontes"]:
            assert re.fullmatch(r"[FP][0-9]{1,2}", src["id"]) and set(src) == {"id", "url", "dominio", "titulo", "dataPublicacao", "origemData"}
    ref = d["radar"]
    assert set(ref) == {"assunto", "mesBase", "geradoEm", "diasDesdeGeracao", "desatualizado", "origem"}
    assert ref["origem"] == "GERADO_AGORA" and set(ref["assunto"]) == {"termo", "tipo"} and body["data"]["radarExterno"] is None
    assert "avaliacoesExternas" not in d and all(f["parcelaEstimada"] is None for f in d["fatores"] if f.get("dimensao"))


def test_second_post_uses_cached_diagnosis_and_get_reports_fresh_radar():
    rig = make_radar_rig()
    client = _app(rig)
    client.post(GEN, json=BODY)
    again = client.post(GEN, json=BODY).json()
    assert again["meta"]["origem"] == "cache" and len(rig.llm.radar_calls) == 1
    assert _get(client).json()["meta"]["ia"]["radar"]["estado"] == "FRESCO"


def test_second_product_gets_radar_from_cache_origin():
    rig = make_radar_rig()
    ev = iter([make_evidence(), make_evidence(produto={"sku": 5103}, delta_observado=-3500.0, variacao_pct=-35.0)])
    client = _app(rig, lambda q: next(ev))
    client.post(GEN, json=BODY)
    second = client.post(GEN, json=BODY).json()
    assert second["data"]["diagnosticoIa"]["radar"]["origem"] == "CACHE"


@pytest.mark.parametrize("setup,expect_view", [("budget", True), ("budget_no_radar", False), ("gate", True)])
def test_post_template_carries_read_only_radar_only_when_it_exists(setup, expect_view):
    rig = make_radar_rig()
    if setup != "budget_no_radar":
        plant_radar(rig.objects, clock=rig.clock)
    if setup.startswith("budget"):
        seed_ledger(rig, month=1.80)
    provider = (lambda q: make_evidence(residual_share=0.05)) if setup == "gate" else None
    body = _app(rig, provider).post(GEN, json=BODY).json()
    assert body["meta"]["origem"] == "template" and body["data"]["diagnosticoIa"] is None
    assert (body["data"]["radarExterno"] is not None) is expect_view and rig.llm.calls == []
    if expect_view:
        assert all(set(d) == RADAR_DIM_KEYS for d in body["data"]["radarExterno"]["dimensoes"])


def test_warnings_sem_radar_externo_and_radar_desatualizado_without_ia_falhou():
    none = make_radar_rig(llm=RoutedLlm(radar=[mod("llm.client").LlmTransientError()] * 3))
    codes = [a["codigo"] for a in _app(none).post(GEN, json=BODY).json()["meta"]["avisos"]]
    assert "SEM_RADAR_EXTERNO" in codes and "IA_FALHOU" not in codes
    stale = make_radar_rig()
    plant_radar(stale.objects, age_days=60, clock=stale.clock)
    seed_ledger(stale, radares_dia=3)
    body = _app(stale).post(GEN, json=BODY).json()
    assert "RADAR_DESATUALIZADO" in [a["codigo"] for a in body["meta"]["avisos"]]
    assert body["meta"]["ia"]["radar"]["estado"] == "DESATUALIZADO"


def test_hypothesis_motives_for_posterior_source_reach_the_api():
    rig = make_radar_rig()
    plant_radar(rig.objects, clock=rig.clock, source_date="2026-11-05")
    body = _app(rig).post(GEN, json=BODY).json()
    d = body["data"]["diagnosticoIa"]
    assert "POSTERIOR_AO_PERIODO" in [h["motivo"] for h in d["hipotesesNaoConfirmadas"]]
    assert COST_DIM not in [f.get("dimensao") for f in d["fatores"]]


def test_hard_cap_is_invisible_to_the_client():
    rig = make_radar_rig()
    seed_ledger(rig, queries=1500)
    resp = _app(rig).post(GEN, json=BODY)
    assert resp.status_code == 200 and "SEM_RADAR_EXTERNO" in resp.text
    # Revisado pelo developer: a varredura crua de "custo" e "1500" reprovava respostas validas, pois o nome
    # contratual da dimensao `CUSTO_MATERIA_PRIMA` (contrato 2.4) e o residuo do motor (-1500.0 em `somaParcelas`)
    # contem esses trechos. Agora: o enum da dimensao e descontado e "1500" so e proibido na `meta` (avisos, orcamento).
    text = resp.text.lower().replace("custo_materia_prima", "")
    for word in ("teto", "limite de", "cota", "custo", "consulta", "usd", "gasto"):
        assert word not in text
    assert "1500" not in json.dumps(resp.json()["meta"])


def test_health_has_radar_block_and_radar_model():
    rig = make_radar_rig()
    client = _app(rig)
    client.post(GEN, json=BODY)
    data = client.get(BASE + "/health").json()["data"]
    assert data["ia"]["modeloRadar"] == HYDROGEN and data["ia"]["promptVersion"] == "tia-v3"
    assert data["radar"] == {"radarVersion": "radar-v1", "radaresEmCache": 1, "radaresGeradosMes": 1}


def test_cost_and_internal_scan_extended_to_radar_in_every_response():
    rig = make_radar_rig()
    plant_radar(rig.objects, clock=rig.clock, age_days=5)
    client = _app(rig)
    bodies = [_get(client).json(), client.post(GEN, json=BODY).json(), client.post(GEN, json=BODY).json(),
              client.get(BASE + "/health").json()]
    seed_ledger(rig, month=1.80)
    rig.clock.advance(61)
    other = _app(rig, lambda q: make_evidence(delta_observado=-4000.0, variacao_pct=-40.0))
    bodies.append(other.post(GEN, json=BODY).json())
    radar_hash = rig.objects.objects[next(iter(rig.objects.paths("radar/")))]["radarHash"]
    for body in bodies:
        keys = [k.lower() for k in collect_keys(body)]
        assert not [k for k in keys if any(bad in k for bad in EXTENDED_FORBIDDEN)], keys
        text = json.dumps(body)
        assert "radar/" not in text and radar_hash not in text and "consultasExecutadas" not in text


# --- radar fora do evidenceHash e bloco do prompt (T-7.2R.8)
def test_radar_is_outside_evidence_hash_and_payload():
    payload = mod("llm.evidence_payload")
    ev = make_evidence()
    assert "radar" not in payload.build_llm_payload(ev).lower()
    first = payload.compute_evidence_hash(ev)
    rig = make_radar_rig()
    rig.orch.generate(ev, caller_id="u1")
    plant_radar(rig.objects, clock=rig.clock, age_days=1)
    assert payload.compute_evidence_hash(ev) == first


def test_radar_block_builder_respects_limit_with_worst_case_and_has_no_urls_titles_or_company_data():
    payload = mod("llm.evidence_payload")
    store = mod("store.radar_store")
    dims = [{"dimensao": d, "status": "AVALIADA", "movimento": "SUBIU", "intensidade": "FORTE", "tema": "OUTRO",
             "fonteIds": ["F1", "F2"]} for d in DIMENSIONS]
    doc = {**plant_doc(), "dimensoes": dims}
    block = payload.build_radar_block(store.StoredRadar.from_json(doc), "abcd1234")
    assert len(block) <= 2000 and "http" not in block and "noticias.exemplo" not in block
    assert block.count("dimensao") >= 8 and "<radar_externo_abcd1234>" in block


def plant_doc():
    from tests.trend_insights.radar_helpers import radar_doc
    return radar_doc()
