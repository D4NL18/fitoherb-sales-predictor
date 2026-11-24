"""T-7.2B.4: gates de nao chamada (P-188), gate de grounding (P-180.1), template e consultas sugeridas."""
import re

import pytest

from tests.trend_insights.helpers import canonical_evidence, make_evidence, mod

REGIONAL = [{"tipo": "REGIONAL", "status": "AVALIADO", "evidencia": {"ufConcentradora": "SP"}}]


def _mkt(classificacao):
    return {"classificacao": classificacao, "variacao_mercado_pct": -10.0, "efeito_mercado": -1.0, "efeito_participacao": -1.0}


def _gate(**over):
    return mod("domain.gates").evaluate_llm_gates(make_evidence(**over))


def test_gate_default_evidence_calls_llm():
    assert _gate() is None


@pytest.mark.parametrize("over,expected", [
    (dict(variacao_pct=-1.5), "GATE_VARIACAO"),
    (dict(cell_status="SEM_BASE", variacao_pct=None), "GATE_VARIACAO"),
    (dict(delta_receita=-999.99), "GATE_VALOR_BAIXO"),
    (dict(delta_receita=-1000.0), None),
    (dict(residual_share=0.19), "GATE_RESIDUO_BAIXO"),
    (dict(residual_share=0.20), None),
    (dict(residual_share=0.19, indicadores=REGIONAL), None),
    (dict(residual_share=0.19, diagnostico_mercado=_mkt("MERCADO_EM_QUEDA")), None),
    (dict(residual_share=0.19, diagnostico_mercado=_mkt("MERCADO_EM_ALTA")), None),
    (dict(variacao_pct=-1.0, delta_receita=-10.0, residual_share=0.0), "GATE_VARIACAO"),  # precedencia
])
def test_llm_gates(over, expected):
    assert _gate(**over) == expected


def test_value_gate_is_always_in_reais_even_for_quantity_metric():
    janela = {**canonical_evidence()["janela"], "metrica": "quantity"}
    ev = make_evidence(janela=janela, delta_observado=-5.0, delta_receita=-3000.0)
    assert mod("domain.gates").evaluate_llm_gates(ev) is None


def _ground(level="NORMAL", **over):
    return mod("domain.gates").grounding_enabled(make_evidence(**over), budget_level=level)


@pytest.mark.parametrize("over,level,expected", [
    (dict(residual_share=0.0, diagnostico_mercado=_mkt("MERCADO_EM_QUEDA")), "NORMAL", True),
    (dict(residual_share=0.0, diagnostico_mercado=_mkt("MERCADO_EM_ALTA")), "NORMAL", True),
    (dict(residual_share=0.30), "NORMAL", True),
    (dict(residual_share=0.29), "NORMAL", False),
    (dict(residual_share=0.15, indicadores=REGIONAL), "NORMAL", True),
    (dict(residual_share=0.14, indicadores=REGIONAL), "NORMAL", False),
    (dict(residual_share=0.30), "ALERTA", False),
    (dict(residual_share=0.50), "ALERTA", True),
])
def test_grounding_gate(over, level, expected):
    assert _ground(level, **over) is expected


def test_grounding_needs_a_search_term():
    ev = make_evidence(residual_share=0.9, produto={"funcao_primaria": None, "categoria_galeria": None})
    assert mod("domain.gates").grounding_enabled(ev, budget_level="NORMAL") is False


# --- Template
def test_template_is_label_digit_free_deterministic_and_never_external():
    tpl = mod("domain.template_summary")
    text = tpl.build_template_summary(make_evidence())
    assert text == tpl.build_template_summary(make_evidence())
    assert not re.search(r"\d", text)
    assert "sazonal" in text.lower()
    assert not any(w in text.lower() for w in ("clima", "regulat", "materia", "noticia", "notícia", "http"))
    assert tpl.TEMPLATE_LABEL == "Resumo automático (sem IA)"


def test_template_for_rise_and_qualitative_still_has_no_digits():
    tpl = mod("domain.template_summary")
    for ev in (make_evidence(direcao="ALTA", variacao_pct=25.0, delta_observado=2500.0),
               make_evidence(modo_diagnostico="QUALITATIVO", cascata=[])):
        assert not re.search(r"\d", tpl.build_template_summary(ev))


# --- Consultas sugeridas (LGPD-TIA-12)
def test_search_queries_limits_and_terms():
    fn = mod("llm.search_queries").build_search_queries
    queries = fn(make_evidence())
    assert 1 <= len(queries) <= 2
    joined = " ".join(queries).lower()
    assert "cha" in joined or "infus" in joined
    assert "hibisco 100g" not in joined
    assert len(fn(make_evidence(modo_diagnostico="QUALITATIVO"))) == 1
