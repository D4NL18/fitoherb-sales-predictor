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
# SUPERADOS pela v3.1 (STATE_Testes): `grounding_enabled` e `build_search_queries` (2 consultas por diagnostico) deram
# lugar a `product_search_enabled` (coberto em `test_radar_store_policy.py`), `build_radar_queries` (5 consultas por
# tabela, so assunto + mes) e `build_product_query` (no maximo 1 consulta, so sem radar).
def test_radar_queries_use_only_subject_and_month_from_the_closed_table():
    raw = mod("domain.raw_material")
    queries = mod("llm.search_queries").build_radar_queries(raw.infer_radar_subject(make_evidence()), "2026-10")
    joined = " ".join(queries).lower()
    assert len(queries) == 5 and "ervas e plantas medicinais" in joined and "outubro de 2026" in joined
    for forbidden in ("5102", "hibisco", "queda", "ervas delta", "100g"):
        assert forbidden not in joined


@pytest.mark.parametrize("over,expected", [
    (dict(), "lancamento"),
    (dict(diagnostico_mercado=_mkt("PERDA_DE_PARTICIPACAO")), "ervas delta"),
    (dict(indicadores=REGIONAL, diagnostico_mercado=_mkt("MERCADO_EM_QUEDA")), "são paulo"),
])
def test_product_query_is_single_by_table_without_commercial_name(over, expected):
    query = mod("llm.search_queries").build_product_query(make_evidence(**over)).lower()
    assert expected in query.replace("lançamento", "lancamento")
    assert "hibisco" not in query and "queda" not in query.replace("mercado_em_queda", "")


def test_product_query_needs_a_subject():
    ev = make_evidence(produto={"funcao_primaria": None, "categoria_galeria": None, "descricao_galeria": None})
    assert mod("llm.search_queries").build_product_query(ev) is None
