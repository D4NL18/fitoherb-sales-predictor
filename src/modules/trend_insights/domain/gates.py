"""Gates de nao chamada do LLM (P-188) e de liga da busca externa (P-180.1). Funcoes puras."""
from typing import Optional

from src.modules.trend_insights.domain.constants import (
    GROUNDING_MIN_RESIDUAL_SHARE,
    GROUNDING_MIN_RESIDUAL_SHARE_ALERT,
    GROUNDING_REGIONAL_MIN_RESIDUAL_SHARE,
    LLM_MIN_ABS_REVENUE_DELTA,
    LLM_MIN_RESIDUAL_SHARE,
    MIN_EXPLAINABLE_VARIATION_PCT,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage

MARKET_MOVE_CLASSES = ("MERCADO_EM_QUEDA", "MERCADO_EM_ALTA")


def _fails_variation_gate(evidence: EvidencePackage) -> bool:
    if evidence.cell_status == "SEM_BASE":
        return True
    variation = evidence.variation_pct
    if variation is None:
        return evidence.cell_status == "VARIACAO"
    return abs(variation) < MIN_EXPLAINABLE_VARIATION_PCT


def _fails_residual_gate(evidence: EvidencePackage) -> bool:
    share = evidence.residual_share
    if share is None or share >= LLM_MIN_RESIDUAL_SHARE:
        return False
    if evidence.has_evaluated_indicator("REGIONAL"):
        return False
    return evidence.market_classification not in MARKET_MOVE_CLASSES


def evaluate_llm_gates(evidence: EvidencePackage) -> Optional[str]:
    """Devolve o motivo do template (GATE_*) ou `None` se o LLM pode ser chamado (P-188.1 a P-188.3)."""
    if _fails_variation_gate(evidence):
        return "GATE_VARIACAO"
    revenue_delta = evidence.revenue_delta
    if revenue_delta is not None and abs(revenue_delta) < LLM_MIN_ABS_REVENUE_DELTA:
        return "GATE_VALOR_BAIXO"
    if _fails_residual_gate(evidence):
        return "GATE_RESIDUO_BAIXO"
    return None


def grounding_enabled(evidence: EvidencePackage, budget_level: str) -> bool:
    """A busca so liga com termo de busca e pelo menos uma condicao (P-180.1); a 80% do teto o limiar sobe."""
    if not evidence.search_term_available:
        return False
    if evidence.market_classification in MARKET_MOVE_CLASSES:
        return True
    share = evidence.residual_share or 0.0
    threshold = GROUNDING_MIN_RESIDUAL_SHARE_ALERT if budget_level != "NORMAL" else GROUNDING_MIN_RESIDUAL_SHARE
    if share >= threshold:
        return True
    return evidence.has_evaluated_indicator("REGIONAL") and share >= GROUNDING_REGIONAL_MIN_RESIDUAL_SHARE
