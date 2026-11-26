"""T-7.2R.7/8/13 (C-28b revisado, C-29a revisado, C-36, C-43, C-45): ordem da 15.8, radar no prompt, cache, falhas, prazos."""
import re

import pytest

from tests.trend_insights.helpers import FLASH, HYDROGEN, make_evidence, make_llm_response, mod
from tests.trend_insights.radar_helpers import (
    COST_DIM, RoutedLlm, avaliacao, ledger_doc, make_radar_rig, make_radar_response, month_spent, plant_radar,
    radar_doc, request_text, seed_ledger, valid_diag_text,
)

TRANSIENT = lambda: mod("llm.client").LlmTransientError()  # noqa: E731


def _go(rig, evidence=None, force=False, caller="u1"):
    return rig.orch.generate(evidence or make_evidence(), caller_id=caller, force=force)


def _radar_block(request):
    match = re.search(r"<radar_externo_([0-9a-f]+)>(.*?)</radar_externo_\1>", request.user_prompt, re.S)
    assert match, "bloco do radar ausente do prompt do diagnostico"
    return match.group(2)


# --- C-36: todo diagnostico por LLM leva radar e devolve 8 dimensoes
def test_new_radar_then_diagnosis_in_order_with_eight_dimensions():
    rig = make_radar_rig()
    out = _go(rig)
    assert [c.request_tag == "radar" for c in rig.llm.calls] == [True, False]
    radar_req, diag_req = rig.llm.calls
    assert radar_req.use_search_grounding is True and radar_req.model_id == rig.settings.model_radar
    assert diag_req.use_search_grounding is False and diag_req.model_id == HYDROGEN
    assert out.origem == "llm" and len(out.diagnostico["fatoresExternos"]) == 8
    assert out.radar["origem"] == "GERADO_AGORA" and out.diagnostico["promptVersion"] == "tia-v3"
    doc = ledger_doc(rig)
    assert doc["radaresNovosMes"] == 1 and doc["consultasMes"] == 5 and doc["gastoRadarMes"] > 0


def test_prompt_order_system_radar_evidence_and_block_limits():
    rig = make_radar_rig()
    _go(rig)
    diag = rig.llm.diag_calls[0]
    text = diag.user_prompt
    assert text.index("<radar_externo_") < text.index("<evidencias_")
    block = _radar_block(diag)
    assert len(block) <= 2000 and "http" not in block and "5102" not in block and "cliente" not in block.lower()
    for name in ("CUSTO_MATERIA_PRIMA", "CLIMA_SAFRA", "EVENTOS_MERCADO"):
        assert name in block
    assert "dado" in diag.system_prompt.lower() and "radar" in diag.system_prompt.lower()


def test_gallery_description_never_reaches_radar_request():
    rig = make_radar_rig()
    _go(rig, make_evidence(produto={"descricao_galeria": "Texto secreto da galeria de hibisco."}))
    assert "secreto" not in request_text(rig.llm.radar_calls[0]).lower()


# --- C-28b (revisado): residuo 25% chama LLM com radar e sem busca do produto
def test_residual_25_competitive_calls_llm_with_radar_and_no_product_search():
    rig = make_radar_rig()
    _go(rig, make_evidence(residual_share=0.25, diagnostico_mercado={"classificacao": "PERDA_DE_PARTICIPACAO"}))
    assert len(rig.llm.radar_calls) == 1 and len(rig.llm.diag_calls) == 1
    assert rig.llm.diag_calls[0].use_search_grounding is False
    assert "Faca no maximo" not in rig.llm.diag_calls[0].user_prompt


def test_diagnosis_with_radar_never_searches_even_with_high_residual():
    rig = make_radar_rig()
    plant_radar(rig.objects, clock=rig.clock)
    _go(rig, make_evidence(residual_share=0.9))
    assert rig.llm.radar_calls == [] and rig.llm.diag_calls[0].use_search_grounding is False


@pytest.mark.parametrize("share,level_month,expected", [(0.30, 0.0, True), (0.29, 0.0, False), (0.9, 1.50, False)])
def test_product_search_only_when_radar_absent_and_rules_hold(share, level_month, expected):
    llm = RoutedLlm(radar=[mod("llm.client").LlmTransientError()] * 3)  # radar falha: SEM_RADAR
    rig = make_radar_rig(llm=llm)
    seed_ledger(rig, month=level_month, radares_dia=3)  # nao gera radar novo: SEM_RADAR
    _go(rig, make_evidence(residual_share=share))
    diag = rig.llm.diag_calls[0]
    assert diag.use_search_grounding is expected
    if expected:
        assert len(re.findall(r"^- ", diag.user_prompt, re.M)) == 1


# --- C-29a (revisado): a 80% a busca do produto desliga
def test_alert_level_disables_product_search_and_force():
    rig = make_radar_rig()
    _go(rig)
    seed_ledger(rig, month=1.50)
    rig.clock.advance(61)
    out = _go(rig, force=True)
    assert out.origem == "cache" and len(rig.llm.diag_calls) == 1


# --- C-45: cache independe do radar
def test_cache_key_does_not_depend_on_radar_and_stores_only_radar_ref():
    rig = make_radar_rig()
    first = _go(rig)
    rig.clock.advance(3600 * 24 * 40)  # radar vence; diagnostico (TTL logico 30 d) segue servindo do cache
    second = _go(rig)
    assert second.origem == "cache" and len(rig.llm.radar_calls) == 1 and len(rig.llm.diag_calls) == 1
    (path,) = rig.objects.paths("insights/")
    assert "radarRef" in rig.objects.objects[path] and "radar/" not in str(rig.objects.objects[path].get("diagnostico"))
    assert first.stored is not None


def test_force_reuses_current_radar():
    rig = make_radar_rig()
    _go(rig)
    rig.clock.advance(61)
    _go(rig, force=True)
    assert len(rig.llm.radar_calls) == 1 and len(rig.llm.diag_calls) == 2


def test_cache_hit_and_gate_never_call_radar():
    rig = make_radar_rig()
    _go(rig)
    calls = len(rig.llm.calls)
    _go(rig)
    _go(rig, make_evidence(variacao_pct=-1.0))
    assert len(rig.llm.calls) == calls


# --- C-43: orcamento esgotado / gate / kill-switch com radar existente
@pytest.mark.parametrize("age,desatualizado", [(10, False), (60, True)])
def test_budget_exhausted_returns_template_with_read_only_radar(age, desatualizado):
    rig = make_radar_rig()
    plant_radar(rig.objects, age_days=age, clock=rig.clock)
    seed_ledger(rig, month=1.80)
    out = _go(rig)
    assert (out.origem, out.motivo_template) == ("template", "ORCAMENTO_ESGOTADO") and rig.llm.calls == []
    view = out.radar_externo
    assert view and len(view["dimensoes"]) == 8 and view["desatualizado"] is desatualizado
    for dim in view["dimensoes"]:
        assert {"direcao", "relevanciaAoProduto", "confianca"}.isdisjoint(dim)
    assert not re.search(r"\d", out.resumo_automatico) and "radar" not in out.resumo_automatico.lower()


def test_template_without_radar_has_no_radar_block_and_gate_template_carries_existing_radar():
    rig = make_radar_rig()
    seed_ledger(rig, month=1.80)
    assert _go(rig).radar_externo is None
    rig2 = make_radar_rig()
    plant_radar(rig2.objects, clock=rig2.clock)
    out = _go(rig2, make_evidence(residual_share=0.1))
    assert out.motivo_template == "GATE_RESIDUO_BAIXO" and out.radar_externo is not None and rig2.llm.calls == []


def test_kill_switch_keeps_zero_calls_and_writes():
    rig = make_radar_rig(settings_env={"TREND_AI_ENABLED": "false"})
    out = _go(rig)
    assert out.motivo_template == "IA_DESLIGADA" and rig.llm.calls == [] and rig.objects.writes == 0


# --- falha do radar nao derruba o diagnostico
def test_radar_failure_continues_with_sem_radar_and_no_ia_falhou():
    rig = make_radar_rig(llm=RoutedLlm(radar=[TRANSIENT(), TRANSIENT(), TRANSIENT()]))
    out = _go(rig)
    assert out.origem == "llm" and "SEM_RADAR_EXTERNO" in out.avisos and "IA_FALHOU" not in out.avisos
    assert out.radar is None and rig.objects.paths("radar/") == []
    assert all(f["status"] == "NAO_AVALIADA" and f["motivoNaoAvaliado"] == "SEM_RADAR" for f in out.diagnostico["fatoresExternos"])
    assert not any("<radar_externo_" in c.user_prompt for c in rig.llm.diag_calls)


def test_radar_schema_failure_retries_once_then_gives_up():
    bad = make_radar_response("nao e json")
    rig = make_radar_rig(llm=RoutedLlm(radar=[bad, bad]))
    out = _go(rig)
    assert len(rig.llm.radar_calls) == 2 and "SEM_RADAR_EXTERNO" in out.avisos and rig.objects.paths("radar/") == []


def test_radar_falls_back_to_flash_on_infra_failure_with_grounding():
    rig = make_radar_rig(llm=RoutedLlm(radar=[TRANSIENT(), TRANSIENT(), make_radar_response(model=FLASH)]))
    out = _go(rig)
    flash = [c for c in rig.llm.radar_calls if c.model_id == FLASH]
    assert len(flash) == 1 and flash[0].use_search_grounding is True and out.radar["origem"] == "GERADO_AGORA"


def test_radar_model_is_configurable():
    rig = make_radar_rig(settings_env={"TREND_AI_MODEL_RADAR": FLASH})
    _go(rig)
    assert rig.llm.radar_calls[0].model_id == FLASH and rig.llm.diag_calls[0].model_id == HYDROGEN


def test_diagnosis_flash_fallback_uses_same_radar_without_tools():
    rig = make_radar_rig(llm=RoutedLlm(diagnosis=[TRANSIENT(), TRANSIENT(), make_llm_response(valid_diag_text(), model=FLASH)]))
    out = _go(rig)
    flash = rig.llm.diag_calls[-1]
    assert out.origem == "fallback" and flash.model_id == FLASH and flash.use_search_grounding is False
    assert _radar_block(flash) and len(rig.llm.radar_calls) == 1
    hydrogen_block = re.sub(r"[0-9a-f]{8}", "N", _radar_block(rig.llm.diag_calls[0]))
    assert re.sub(r"[0-9a-f]{8}", "N", _radar_block(flash)) == hydrogen_block
    assert "SEM_BUSCA_EXTERNA" not in out.avisos


def test_stale_radar_warns_and_lowers_confidence():
    rig = make_radar_rig()
    plant_radar(rig.objects, age_days=60, clock=rig.clock)
    seed_ledger(rig, radares_dia=3)
    out = _go(rig, make_evidence())
    assert "RADAR_DESATUALIZADO" in out.avisos and out.radar["desatualizado"] is True
    assert all(i["confianca"] == "BAIXA" for i in out.diagnostico["fatoresExternos"])


def test_no_term_gives_not_evaluated_sem_termo_busca_and_no_radar_call():
    rig = make_radar_rig()
    ev = make_evidence(produto={"funcao_primaria": None, "categoria_galeria": None, "descricao_galeria": None})
    out = _go(rig, ev)
    assert rig.llm.radar_calls == [] and out.origem == "llm"
    assert all(i["motivoNaoAvaliado"] == "SEM_TERMO_BUSCA" for i in out.diagnostico["fatoresExternos"])


# --- prazos (125 / 150 / 55 / 180)
def test_total_deadline_125_skips_flash_when_exhausted():
    err = TRANSIENT
    rig = make_radar_rig(llm=RoutedLlm(diagnosis=[err(), err(), make_llm_response(valid_diag_text(), model=FLASH)]),
                         seconds_per_call=55)
    out = _go(rig)
    assert FLASH not in [c.model_id for c in rig.llm.diag_calls] and out.origem == "template" and "IA_FALHOU" in out.avisos


def test_radar_plus_two_attempts_plus_flash_fit_in_125():
    err = TRANSIENT
    rig = make_radar_rig(llm=RoutedLlm(diagnosis=[err(), err(), make_llm_response(valid_diag_text(), model=FLASH)]),
                         seconds_per_call=30)
    assert _go(rig).origem == "fallback"


def test_radar_has_its_own_55s_deadline():
    rig = make_radar_rig(llm=RoutedLlm(radar=[TRANSIENT(), TRANSIENT(), make_radar_response(model=FLASH)]),
                         seconds_per_call=30)
    out = _go(rig)
    assert len(rig.llm.radar_calls) == 2 and FLASH not in [c.model_id for c in rig.llm.radar_calls]
    assert "SEM_RADAR_EXTERNO" in out.avisos


def test_reservation_ttl_covers_new_deadline():
    rig = make_radar_rig()
    res = rig.ledger.reserve(HYDROGEN, with_search=False)
    rig.clock.advance(170)
    rig.ledger.reserve(HYDROGEN, with_search=False)
    assert len(ledger_doc(rig)["reservado"]) == 2  # a primeira ainda vale aos 170 s (TTL 180)
    assert res.amount_usd > 0
