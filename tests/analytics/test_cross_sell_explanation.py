"""
T-11 — Explicação em linguagem simples (P-065, CA-14, contrato §3.5).

Interface esperada (B-13, `src/modules/analytics/domain/cross_sell_explanation.py`):
- `build_product_explanation(rule, antecedent_desc, consequent_desc)`
- `build_customer_explanation(rule, descriptions, days_since_last_purchase)`, com
  `descriptions = (antecedent_desc, consequent_desc)` e `days_since_last_purchase=None` para
  `NUNCA_COMPROU` (dias inteiros para `DORMENTE`)
Ambas devolvem um objeto com as chaves (mapping) ou atributos `frequencia`, `intensidade`,
`evidencia` e `motivo` (`None` no modo produto). Arredondamento meio para cima
(`Decimal.quantize(ROUND_HALF_UP)`), vírgula decimal e milhar com ponto, sem depender de `locale`.
"""
import locale
import re
from collections.abc import Mapping

import pytest

from src.modules.analytics.domain.cross_sell import UsefulRule
from src.modules.analytics.domain.cross_sell_explanation import (
    build_customer_explanation,
    build_product_explanation,
)

DESC_A = "CHA VERDE 100G"
DESC_B = "CAPSULA DE HIBISCO"
DESC_G = "GENGIBRE EM PO 100G"
KEYS = ("frequencia", "intensidade", "evidencia", "motivo")
FORBIDDEN_WORDS = re.compile(r"lift|suporte|confian[cç]a|pontua[cç][aã]o", re.IGNORECASE)


def make_rule(confidence=0.34, lift=4.25, pair_orders=170):
    return UsefulRule(antecedent=1001, consequent=2002, support=pair_orders / 10_000, confidence=confidence,
                      lift=lift, pair_orders=pair_orders, antecedent_orders=500)


def field(explanation, name):
    if isinstance(explanation, Mapping):
        return explanation[name]
    return getattr(explanation, name)


def phrases(explanation):
    return {name: field(explanation, name) for name in KEYS}


# ------------------------------------------------------------------ CA-14 (R1)

def test_ca14_r1_product_phrases():
    explanation = phrases(build_product_explanation(make_rule(), DESC_A, DESC_B))

    assert explanation == {
        "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
        "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
        "evidencia": "Baseado em 170 pedidos.",
        "motivo": None,
    }


def test_r5_lift_at_minimum():
    explanation = phrases(build_product_explanation(make_rule(confidence=0.12, lift=1.2, pair_orders=60),
                                                    DESC_A, "OLEO DE COCO 200ML"))

    assert explanation["frequencia"] == "Em 12% dos pedidos com CHA VERDE 100G também há OLEO DE COCO 200ML."
    assert explanation["intensidade"] == "OLEO DE COCO 200ML aparece 1,2 vezes mais nesses pedidos do que no geral."
    assert explanation["evidencia"] == "Baseado em 60 pedidos."


# ------------------------------------------------------------------ arredondamento meio para cima

@pytest.mark.parametrize(
    "confidence, expected_percent",
    [(0.345, "35"), (0.125, "13"), (0.3449, "34"), (0.10, "10"), (0.09999999999999999, "10"), (1.0, "100")],
)
def test_percentage_rounds_half_up(confidence, expected_percent):
    explanation = phrases(build_product_explanation(make_rule(confidence=confidence), DESC_A, DESC_B))
    assert explanation["frequencia"].startswith(f"Em {expected_percent}% dos pedidos")


@pytest.mark.parametrize(
    "lift, expected",
    [(1.25, "1,3"), (1.15, "1,2"), (4.25, "4,3"), (1.1999999999999997, "1,2"), (2.0, "2,0"), (12.0, "12,0")],
)
def test_lift_one_decimal_half_up_with_comma(lift, expected):
    explanation = phrases(build_product_explanation(make_rule(lift=lift), DESC_A, DESC_B))
    assert explanation["intensidade"] == f"{DESC_B} aparece {expected} vezes mais nesses pedidos do que no geral."


@pytest.mark.parametrize("orders, expected", [(10, "10"), (999, "999"), (1234, "1.234"), (1_234_567, "1.234.567")])
def test_evidence_uses_dot_as_thousands_separator(orders, expected):
    explanation = phrases(build_product_explanation(make_rule(pair_orders=orders), DESC_A, DESC_B))
    assert explanation["evidencia"] == f"Baseado em {expected} pedidos."


def test_formatting_does_not_depend_on_system_locale(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("a explicação não pode depender de locale")

    monkeypatch.setattr(locale, "setlocale", fail)
    monkeypatch.setattr(locale, "format_string", fail)
    monkeypatch.setattr(locale, "localeconv", fail)

    explanation = phrases(build_product_explanation(make_rule(pair_orders=1234), DESC_A, DESC_B))
    assert explanation["evidencia"] == "Baseado em 1.234 pedidos."


# ------------------------------------------------------------------ motivo por cliente (P-065.4)

def test_customer_never_bought_motive():
    rule = make_rule(confidence=0.20, lift=1.5, pair_orders=100)
    explanation = phrases(build_customer_explanation(rule, (DESC_A, DESC_G), None))

    assert explanation["motivo"] == (
        "Sugerido porque o cliente compra CHA VERDE 100G. O cliente nunca comprou GENGIBRE EM PO 100G."
    )
    assert explanation["frequencia"] == "Em 20% dos pedidos com CHA VERDE 100G também há GENGIBRE EM PO 100G."
    assert explanation["intensidade"] == "GENGIBRE EM PO 100G aparece 1,5 vezes mais nesses pedidos do que no geral."
    assert explanation["evidencia"] == "Baseado em 100 pedidos."


def test_customer_dormant_motive():
    explanation = phrases(build_customer_explanation(make_rule(), (DESC_A, DESC_B), 120))

    assert explanation["motivo"] == (
        "Sugerido porque o cliente compra CHA VERDE 100G. O cliente não compra CAPSULA DE HIBISCO há 120 dias."
    )


# ------------------------------------------------------------------ CA-14 sem jargão

@pytest.mark.parametrize("days", [None, 91, 1234])
def test_no_statistical_jargon_in_any_phrase(days):
    explanations = [
        phrases(build_product_explanation(make_rule(), DESC_A, DESC_B)),
        phrases(build_customer_explanation(make_rule(), (DESC_A, DESC_B), days)),
    ]
    for explanation in explanations:
        for name, text in explanation.items():
            if text is None:
                continue
            assert FORBIDDEN_WORDS.search(text) is None, f"{name}: {text}"


def test_phrases_are_separate_not_concatenated():
    explanation = phrases(build_product_explanation(make_rule(), DESC_A, DESC_B))

    assert "Baseado em" not in explanation["frequencia"]
    assert "Em 34%" not in explanation["evidencia"]
    assert explanation["frequencia"].endswith(".")
    assert explanation["intensidade"].endswith(".")
