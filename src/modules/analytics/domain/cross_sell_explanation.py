"""
Explicação em linguagem simples das recomendações — domínio puro (P-065, contrato §3.5, ADR-002 DA-09).

As frases são montadas aqui (e não no Angular) para haver uma única implementação testável do
arredondamento meio para cima, da vírgula decimal e do ponto de milhar, reaproveitável pelo backtest.
Vêm separadas (`frequencia`, `intensidade`, `evidencia`, `motivo`) para a tela ordenar e destacar sem
concatenar. Nenhuma frase usa os termos "lift", "suporte", "confiança" ou "pontuação" (CA-14).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.modules.analytics.domain.cross_sell import UsefulRule
from src.modules.analytics.domain.number_format import (
    format_decimal_pt_br,
    format_integer_pt_br,
    format_percent_pt_br,
)

LIFT_DISPLAY_DECIMALS = 1  # P-065.2: "4,3 vezes"


@dataclass(frozen=True)
class Explanation:
    """Frases prontas de P-065; `motivo` é `None` no modo produto."""

    frequencia: str
    intensidade: str
    evidencia: str
    motivo: Optional[str] = None


def build_product_explanation(rule: UsefulRule, antecedent_desc: str, consequent_desc: str) -> Explanation:
    """
    Frases do modo produto.

    Args:
        rule: Regra Útil A -> B.
        antecedent_desc: descrição de A.
        consequent_desc: descrição de B.

    Regra: P-065.1 (confiança em % inteiro), P-065.2 (lift com 1 casa), P-065.3 (pedidos em comum).
    """
    percent = format_percent_pt_br(rule.confidence)
    times = format_decimal_pt_br(rule.lift, LIFT_DISPLAY_DECIMALS)
    return Explanation(
        frequencia=f"Em {percent}% dos pedidos com {antecedent_desc} também há {consequent_desc}.",
        intensidade=f"{consequent_desc} aparece {times} vezes mais nesses pedidos do que no geral.",
        evidencia=f"Baseado em {format_integer_pt_br(rule.pair_orders)} pedidos.",
    )


def _customer_motive(descriptions: Tuple[str, str], days_since_last_purchase: Optional[int]) -> str:
    """Frase de motivo de P-065.4 (`NUNCA_COMPROU` quando `days_since_last_purchase` é `None`)."""
    antecedent_desc, consequent_desc = descriptions
    prefix = f"Sugerido porque o cliente compra {antecedent_desc}."
    if days_since_last_purchase is None:
        return f"{prefix} O cliente nunca comprou {consequent_desc}."
    days = format_integer_pt_br(days_since_last_purchase)
    return f"{prefix} O cliente não compra {consequent_desc} há {days} dias."


def build_customer_explanation(rule: UsefulRule, descriptions: Tuple[str, str],
                               days_since_last_purchase: Optional[int]) -> Explanation:
    """
    Frases do modo cliente: as três do modo produto mais o motivo.

    Args:
        rule: regra principal do candidato (P-064.1).
        descriptions: (descrição do antecedente principal, descrição do candidato).
        days_since_last_purchase: dias para `DORMENTE`; `None` para `NUNCA_COMPROU`.

    Regra: P-065.4.
    """
    base = build_product_explanation(rule, *descriptions)
    return Explanation(base.frequencia, base.intensidade, base.evidencia,
                       _customer_motive(descriptions, days_since_last_purchase))
