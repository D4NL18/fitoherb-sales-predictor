"""Testes unitarios das correcoes de contrato (`celula`), fallback de indicadores, schema de serving, API key e store local."""
import re
from types import SimpleNamespace

import pytest

from tests.trend_insights.helpers import make_evidence, mod


def test_local_file_object_store_crud_and_conflict(tmp_path):
    store_mod = mod("object_storage.gcs_object_store")
    ports_mod = mod("domain.ports")
    store = store_mod.LocalFileObjectStore(tmp_path)

    assert store.read_json("insights/v1/missing.json") is None
    gen1 = store.write_json("insights/v1/item.json", {"ok": True, "n": 1}, if_generation_match=0)
    assert gen1 == 1

    loaded = store.read_json("insights/v1/item.json")
    assert loaded == ({"ok": True, "n": 1}, 1)

    with pytest.raises(ports_mod.ObjectConflict):
        store.write_json("insights/v1/item.json", {"ok": False}, if_generation_match=0)

    gen2 = store.write_json("insights/v1/item.json", {"ok": True, "n": 2}, if_generation_match=1)
    assert gen2 == 2
    assert store.paths("insights/v1") == ["insights/v1/item.json"]

    store.delete("insights/v1/item.json", if_generation_match=2)
    assert store.read_json("insights/v1/item.json") is None
    # Delete idempotente em caminho ausente nao lanca FileNotFoundError
    store.delete("insights/v1/item.json")


def test_gemini_client_supports_api_key_and_strips_serving_schema_constraints():
    cfg_mod = mod("config")
    gemini_mod = mod("llm.gemini_client")
    schema_mod = mod("llm.output_schema")

    settings = cfg_mod.TrendInsightsSettings.from_env({"GEMINI_API_KEY": "test-key"})
    assert settings.gemini_api_key == "test-key"

    client = gemini_mod.GeminiVertexClient(project=None, location="us-central1", api_key=settings.gemini_api_key)
    assert client.is_configured() is True

    empty_client = gemini_mod.GeminiVertexClient(project=None, location="us-central1", api_key=None)
    assert empty_client.is_configured() is False

    simplified = gemini_mod.GeminiVertexClient._serving_schema(schema_mod.LLM_OUTPUT_SCHEMA)
    dumped = repr(simplified)
    assert "maxItems" not in dumped
    assert "'format'" not in dumped
    assert "'pattern'" not in dumped
    assert "resumo" in simplified["properties"]


def test_template_summary_uses_evaluated_indicators_when_cascade_has_none():
    tpl = mod("domain.template_summary")
    ev = make_evidence(
        direcao="ALTA",
        modo_diagnostico="QUALITATIVO",
        cascata=[{"tipo": "SAZONALIDADE", "status": "SEM_EFEITO", "valor": None}],
        indicadores=[
            {"tipo": "PROMOCAO", "status": "AVALIADO"},
            {"tipo": "REGIONAL", "status": "AVALIADO"},
            {"tipo": "RUPTURA", "status": "SEM_EFEITO"},
        ],
    )
    text = tpl.build_template_summary(ev)
    assert "Sinais internos observados:" in text
    assert "promoção no período" in text
    assert "concentração regional das vendas" in text
    assert not re.search(r"\d", text)


def test_evidence_adapter_serializes_celula_for_product_and_affines():
    adapter_cls = mod("adapters.evidence_adapter").EvidenceBuilder
    cell = SimpleNamespace(
        status="VARIACAO",
        variacao_pct=15.5,
        atual=1155.0,
        anterior=1000.0,
        base_parcial=False,
        base_baixa=False,
        devolucao_liquida=False,
        atual_por_dia=38.5,
        anterior_por_dia=33.33,
    )
    serialized = adapter_cls._cell_dict(cell, 3)
    assert serialized == {
        "meses": 3,
        "atual": 1155.0,
        "anterior": 1000.0,
        "variacao_pct": 15.5,
        "status": "VARIACAO",
        "base_parcial": False,
        "base_baixa": False,
        "devolucao_liquida": False,
        "atual_por_dia": 38.5,
        "anterior_por_dia": 33.33,
    }
    affine = adapter_cls._affine_dict(
        {"sku": 999, "description": "AFIM", "supplier": "SUP", "sameSupplier": True, "affinityScore": 0.8},
        cell,
        window=6,
        lancamento=True,
    )
    assert affine["celula"]["meses"] == 6
    assert affine["celula"]["variacao_pct"] == 15.5
    assert affine["lancamento"] is True
