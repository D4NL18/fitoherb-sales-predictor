"""T-7.2R.3: 8 dimensoes, temas fechados, frases fixas, causalidade temporal e coerencia direcional. P-180.4/5, P-181.3."""
import re
from datetime import date

import pytest

from tests.trend_insights.helpers import mod
from tests.trend_insights.radar_helpers import COST_DIM, COST_THEME, DIMENSIONS

INI_PRE, INI_CUR, FIM_CUR = date(2026, 7, 1), date(2026, 10, 1), date(2026, 10, 31)


def _rel(d):
    return mod("domain.external_dimensions").temporal_relation(
        d, current_start=INI_CUR, current_end=FIM_CUR, previous_start=INI_PRE)


def test_eight_dimensions_in_fixed_order():
    assert tuple(mod("domain.external_dimensions").EXTERNAL_DIMENSIONS) == DIMENSIONS


def test_dimension_to_factor_type_mapping():
    m = mod("domain.external_dimensions").DIMENSION_FACTOR_TYPE
    assert m == {
        "POLITICA_REGULATORIO": "POLITICO_REGULATORIO", "CLIMA_SAFRA": "CLIMA",
        "CUSTO_MATERIA_PRIMA": "MATERIA_PRIMA", "OFERTA_DEMANDA_MATERIA_PRIMA": "MATERIA_PRIMA",
        "CAMBIO_LOGISTICA_IMPORTACAO": "MATERIA_PRIMA", "CONSUMO_MIDIA_SAUDE": "OUTRO",
        "CONCORRENCIA": "CONCORRENCIA_MERCADO", "EVENTOS_MERCADO": "OUTRO",
    }


@pytest.mark.parametrize("d,relacao,rotulo", [
    (date(2026, 4, 1), "ANTIGA", "DESCARTADA"),
    (date(2026, 4, 3), "ANTERIOR", "POSSIVEL"),
    (date(2026, 9, 30), "ANTERIOR", "POSSIVEL"),
    (date(2026, 10, 1), "CONTEMPORANEA", "POSSIVEL"),
    (date(2026, 10, 31), "CONTEMPORANEA", "POSSIVEL"),
    (date(2026, 11, 1), "POSTERIOR", "CONTEXTO"),
    (None, "SEM_DATA", "SEM_DATA"),
])
def test_temporal_relation_borders(d, relacao, rotulo):
    assert _rel(d) == (relacao, rotulo)


def test_lookback_limit_is_inclusive():
    # ini_pre - 90 dias = 2026-04-02: `ini_pre - 90 <= d` e ANTERIOR (P-180.5)
    assert _rel(date(2026, 4, 2))[0] == "ANTERIOR"
    assert _rel(date(2026, 4, 1))[0] == "ANTIGA"


def test_only_possible_label_can_be_a_cause():
    for d in (date(2026, 11, 1), None, date(2025, 1, 1)):
        assert _rel(d)[1] != "POSSIVEL"


@pytest.mark.parametrize("direcao,variation,ok", [
    ("PRESSAO_BAIXA", -30.0, True), ("PRESSAO_BAIXA", 25.0, False),
    ("PRESSAO_ALTA", 25.0, True), ("PRESSAO_ALTA", -30.0, False),
    ("NEUTRA", -30.0, False), ("INDETERMINADA", 25.0, False),
])
def test_directional_coherence(direcao, variation, ok):
    assert mod("domain.external_dimensions").directional_coherence(direcao, variation) is ok


# --- temas fechados e frases fixas
def test_every_dimension_has_a_closed_theme_list_with_outro():
    themes = mod("domain.radar_themes").RADAR_THEMES
    assert set(themes) == set(DIMENSIONS)
    for dim, values in themes.items():
        assert "OUTRO" in values and len(values) == len(set(values)) and all(re.fullmatch(r"[A-Z_]+", t) for t in values)
    assert COST_THEME in themes[COST_DIM]


def test_every_theme_has_a_fixed_digit_free_product_free_sentence():
    rt = mod("domain.radar_themes")
    for dim, values in rt.RADAR_THEMES.items():
        for theme in values:
            text = rt.RADAR_THEME_TEXTS[(dim, theme)]
            assert text and len(text) <= 140
            assert not re.search(r"\d", text) and "http" not in text.lower() and not re.search(r"[<>{}]", text)
            assert not re.search(r"sku|cliente|r\$|%", text, re.I)
    assert set(k[0] for k in rt.RADAR_THEME_TEXTS) <= set(DIMENSIONS)


def test_no_evidence_text_is_fixed_and_never_says_it_did_not_happen():
    text = mod("domain.radar_themes").NO_EVIDENCE_TEXT
    assert "evid" in text.lower() and "não houve" not in text.lower() and "nao houve" not in text.lower()
    assert "neutr" not in text.lower() and not re.search(r"\d", text)
