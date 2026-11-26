"""T-7.2R.12 (C-38..C-41): 8 dimensoes sempre, causalidade temporal/direcional do backend, fonteIds, confianca. P-180.4/5, P-181.3."""
import json
from datetime import date

import pytest

from tests.trend_insights.helpers import mod
from tests.trend_insights.radar_helpers import (
    COST_DIM, COST_THEME, DIMENSIONS, SOURCE_TITLE, SOURCE_URL, avaliacao, radar_dimensions, valid_diag_text,
)

CAUSAL = ("CUSTO_MATERIA_PRIMA", "CLIMA_SAFRA", "POLITICA_REGULATORIO", "CONCORRENCIA", "CAMBIO_LOGISTICA_IMPORTACAO")


def _source(sid="F1", data="2026-09-20", origem="MODELO"):
    return {"id": sid, "url": SOURCE_URL, "dominio": "noticias.exemplo.com", "titulo": SOURCE_TITLE,
            "dataPublicacao": data, "origemData": origem if data else "SEM_DATA"}


def _external(*, dims=None, sources=None, variation=-30.0, stale=False, missing=None):
    return mod("llm.validation").ExternalContext(
        dimensions=tuple(dims if dims is not None else radar_dimensions()),
        sources={s["id"]: s for s in (sources if sources is not None else [_source()])},
        variation_pct=variation, current_start=date(2026, 10, 1), current_end=date(2026, 10, 31),
        previous_start=date(2026, 7, 1), radar_stale=stale, radar_missing_reason=missing,
    )


def _ctx(external=None, **over):
    base = dict(
        modo="QUANTITATIVO", package_skus=frozenset({5102, 5140}),
        evaluated_types=frozenset({"SAZONALIDADE", "CANIBALIZACAO_OUTRO_FORNECEDOR"}),
        parcel_values={"SAZONALIDADE": -1000.0, "CANIBALIZACAO_OUTRO_FORNECEDOR": -500.0},
        cited_urls=frozenset({SOURCE_URL}), lookback_start=date(2026, 4, 3), reference_date=date(2026, 11, 9),
        cited_titles={}, external=external,
    )
    base.update(over)
    return mod("llm.validation").ValidationContext(**base)


def _run(avaliacoes, *, drop=False, **external_kw):
    text = valid_diag_text(avaliacoes) if not isinstance(avaliacoes, str) else avaliacoes
    return mod("llm.validation").validate_llm_output(text, context=_ctx(_external(**external_kw)), drop_offending=drop)


def _by_dim(out):
    return {i["dimensao"]: i for i in out.diagnostico["fatoresExternos"]}


def _external_factors(out):
    return [f for f in out.diagnostico["fatores"] if f.get("dimensao")]


# --- 8 dimensoes sempre
def test_all_eight_returned_in_fixed_order_and_omitted_are_completed():
    out = _run([avaliacao(COST_DIM)])
    items = out.diagnostico["fatoresExternos"]
    assert out.ok and [i["dimensao"] for i in items] == list(DIMENSIONS)
    omitted = [i for i in items if i["dimensao"] != COST_DIM]
    assert all(i["status"] in ("SEM_EVIDENCIA", "NAO_AVALIADA") for i in omitted)
    assert any(i["status"] == "NAO_AVALIADA" and i["motivoNaoAvaliado"] == "DIMENSAO_OMITIDA_PELA_IA" for i in omitted)


def test_shuffled_model_order_is_normalized():
    out = _run([avaliacao("CONCORRENCIA", fonte_ids=()), avaliacao(COST_DIM)])
    assert [i["dimensao"] for i in out.diagnostico["fatoresExternos"]] == list(DIMENSIONS)


def test_avaliacoes_externas_is_internal_and_not_exposed():
    assert "avaliacoesExternas" not in _run([avaliacao()]).diagnostico


def test_without_radar_all_eight_are_not_evaluated_with_reason():
    for reason in ("SEM_RADAR", "SEM_TERMO_BUSCA"):
        out = _run([], dims=[], sources=[], missing=reason)
        items = out.diagnostico["fatoresExternos"]
        assert len(items) == 8 and all(i["status"] == "NAO_AVALIADA" and i["motivoNaoAvaliado"] == reason for i in items)
        assert all(i["direcao"] == "INDETERMINADA" and i["fontes"] == [] for i in items)
    legacy = mod("llm.validation").validate_llm_output(valid_diag_text([]), context=_ctx(None), drop_offending=False)
    assert len(legacy.diagnostico["fatoresExternos"]) == 8


def test_sem_evidencia_never_becomes_neutral_nor_did_not_happen():
    out = _run([avaliacao("CLIMA_SAFRA", direcao="NEUTRA", relevancia="ALTA", fonte_ids=())])
    item = _by_dim(out)["CLIMA_SAFRA"]
    assert item["status"] == "SEM_EVIDENCIA" and item["direcao"] == "INDETERMINADA"
    assert item["rotulo"] == "SEM_EVIDENCIA" and item["origemEvidencia"] == "NENHUMA" and item["relacaoTemporal"] is None
    assert "não houve" not in (item["notaRadar"] or "").lower() and "evid" in item["notaRadar"].lower()
    assert item["fontes"] == [] and item["nota"] is None


# --- causalidade temporal (C-39)
@pytest.mark.parametrize("data,relacao,rotulo", [
    ("2026-09-20", "ANTERIOR", "POSSIVEL"), ("2026-10-15", "CONTEMPORANEA", "POSSIVEL"),
    ("2026-11-05", "POSTERIOR", "CONTEXTO"), (None, "SEM_DATA", "SEM_DATA"), ("2026-03-01", "ANTIGA", "DESCARTADA"),
])
def test_temporal_relation_is_computed_by_backend_and_only_possible_is_promoted(data, relacao, rotulo):
    out = _run([avaliacao()], sources=[_source(data=data)])
    item = _by_dim(out)[COST_DIM]
    assert (item["relacaoTemporal"], item["rotulo"]) == (relacao, rotulo)
    promoted = [f["dimensao"] for f in _external_factors(out)]
    assert (COST_DIM in promoted) is (rotulo == "POSSIVEL")


def test_model_cannot_set_temporal_fields():
    out = _run([avaliacao(relacaoTemporal="ANTERIOR", rotulo="POSSIVEL")], sources=[_source(data="2026-11-05")])
    assert not out.ok or _by_dim(out)[COST_DIM]["relacaoTemporal"] == "POSTERIOR"


def test_posterior_and_sem_data_become_hypotheses_with_motive_never_factors():
    posterior = _run([avaliacao()], sources=[_source(data="2026-11-05")])
    assert COST_DIM not in [f["dimensao"] for f in _external_factors(posterior)]
    assert "POSTERIOR_AO_PERIODO" in [h["motivo"] for h in posterior.diagnostico["hipotesesNaoConfirmadas"]]
    no_date = _run([avaliacao()], sources=[_source(data=None)])
    assert "SEM_DATA" in [h["motivo"] for h in no_date.diagnostico["hipotesesNaoConfirmadas"]]
    assert all(h["tipo"] and not any(ch.isdigit() for ch in h["descricao"]) for h in posterior.diagnostico["hipotesesNaoConfirmadas"])


# --- coerencia direcional (C-40)
@pytest.mark.parametrize("direcao,variation,promoted", [
    ("PRESSAO_BAIXA", -30.0, True), ("PRESSAO_ALTA", 25.0, True),
    ("PRESSAO_BAIXA", 25.0, False), ("PRESSAO_ALTA", -30.0, False),
])
def test_directional_coherence_gates_promotion(direcao, variation, promoted):
    out = _run([avaliacao(direcao=direcao)], variation=variation)
    assert (COST_DIM in [f["dimensao"] for f in _external_factors(out)]) is promoted
    if not promoted:
        assert _by_dim(out)[COST_DIM]["rotulo"] == "CONTEXTO"
        assert "SEM_COERENCIA_DIRECIONAL" in [h["motivo"] for h in out.diagnostico["hipotesesNaoConfirmadas"]]


# --- promocao e limites (C-41)
def test_promoted_factor_shape():
    out = _run([avaliacao()])
    (factor,) = _external_factors(out)
    assert factor["tipo"] == "MATERIA_PRIMA" and factor["dimensao"] == COST_DIM and factor["rotulo"] == "POSSIVEL"
    assert factor["parcelaEstimada"] is None and factor["confianca"] in ("MEDIA", "BAIXA") and len(factor["fontes"]) <= 2
    assert all(f.get("dimensao") is None for f in out.diagnostico["fatores"] if f["tipo"] == "SAZONALIDADE")


def test_low_relevance_is_not_promoted_and_has_no_note():
    for relevancia in ("BAIXA", "NENHUMA"):
        out = _run([avaliacao(relevancia=relevancia)])
        assert _external_factors(out) == [] and _by_dim(out)[COST_DIM]["nota"] is None
        assert _by_dim(out)[COST_DIM]["status"] == "AVALIADA"


def test_at_most_three_external_factors_among_five():
    dims = radar_dimensions(**{d: {"status": "AVALIADA", "movimento": "SUBIU", "intensidade": "FORTE", "tema": "OUTRO",
                                   "fonteIds": ["F1"]} for d in CAUSAL})
    out = _run([avaliacao(d) for d in CAUSAL], dims=dims)
    assert len(_external_factors(out)) == 3 and len(out.diagnostico["fatores"]) <= 5


def test_confidence_never_high_and_stale_radar_is_low():
    out = _run([avaliacao(confianca="MEDIA")])
    assert all(i["confianca"] in ("MEDIA", "BAIXA") for i in out.diagnostico["fatoresExternos"])
    high = _run([avaliacao(confianca="ALTA")])
    assert not high.ok or all(i["confianca"] != "ALTA" for i in high.diagnostico["fatoresExternos"])
    assert all(f["confianca"] != "ALTA" for f in _external_factors(high))
    stale = _run([avaliacao()], stale=True)
    assert _by_dim(stale)[COST_DIM]["confianca"] == "BAIXA"


def test_external_parcel_from_model_is_ignored_or_rejected():
    out = _run([avaliacao(parcelaEstimada=999.0)])
    assert not out.ok or all(f["parcelaEstimada"] is None for f in _external_factors(out))


# --- fonteIds
@pytest.mark.parametrize("bad", ["f3", "F100", "F", "P1x", "http://x.com", "F3 ", "X1", "F-1"])
def test_source_id_grammar_is_enforced(bad):
    assert not _run([avaliacao(fonte_ids=(bad,))]).ok


def test_source_id_outside_radar_and_product_search_is_rejected():
    out = _run([avaliacao(fonte_ids=("F9",))])
    assert "FONTE_FORA_DO_RADAR" in out.violations
    item = _by_dim(out)[COST_DIM]
    assert item["fontes"] == [] and COST_DIM not in [f["dimensao"] for f in _external_factors(out)]


def test_product_search_source_id_is_accepted_and_labeled():
    out = _run([avaliacao(fonte_ids=("P1",))], sources=[_source("F1"), _source("P1")])
    item = _by_dim(out)[COST_DIM]
    assert item["fontes"] and item["fontes"][0]["id"] == "P1" and item["origemEvidencia"] == "BUSCA_PRODUTO"


def test_radar_sources_are_filled_by_backend_not_model():
    out = _run([avaliacao()])
    src = _by_dim(out)[COST_DIM]["fontes"][0]
    assert src == _source() and _by_dim(out)[COST_DIM]["origemEvidencia"] == "RADAR"
    assert _by_dim(out)[COST_DIM]["tema"] == COST_THEME


def test_at_most_two_source_ids():
    assert not _run([avaliacao(fonte_ids=("F1", "F2", "F3"))], sources=[_source("F1"), _source("F2"), _source("F3")]).ok


def test_source_ids_not_allowed_in_free_text():
    body = json.loads(valid_diag_text([avaliacao()]))
    body["resumo"] = "A causa foi a fonte F1 sobre o insumo."
    assert not _run(json.dumps(body)).ok


# --- nota
@pytest.mark.parametrize("nota,ok", [("Pode ter pressionado o valor.", True), ("Subiu 10 por cento.", False),
                                     ("a" * 100, True), ("a" * 101, False)])
def test_note_has_no_digits_and_is_at_most_100_chars(nota, ok):
    assert _run([avaliacao(nota=nota)]).ok is ok


def test_digit_in_note_reports_digit_violation():
    assert "DIGITO_NO_TEXTO" in _run([avaliacao(nota="Alta de 5 pontos.")]).violations


def test_external_schema_shape():
    schema = mod("llm.output_schema").LLM_OUTPUT_SCHEMA
    item = schema["properties"]["avaliacoesExternas"]["items"]
    assert item["additionalProperties"] is False and "parcelaEstimada" not in item["properties"]
    assert item["properties"]["confianca"]["enum"] == ["MEDIA", "BAIXA"]
    assert item["properties"]["dimensao"]["enum"] == list(DIMENSIONS)
    assert item["properties"]["fonteIds"]["items"]["pattern"] == r"^[FP][0-9]{1,2}$"
    assert item["properties"]["fonteIds"]["maxItems"] == 2
    assert set(item["properties"]["direcao"]["enum"]) == {"PRESSAO_ALTA", "PRESSAO_BAIXA", "NEUTRA", "INDETERMINADA"}
