"""Gates de nao chamada do LLM (P-188), politica do radar (P-180.3) e busca do produto (P-180.1). Funcoes puras."""
from typing import Optional

from src.modules.trend_insights.domain.constants import (
    LLM_MIN_ABS_REVENUE_DELTA,
    LLM_MIN_RESIDUAL_SHARE,
    MIN_EXPLAINABLE_VARIATION_PCT,
    MODE_QUALITATIVE,
    PRODUCT_SEARCH_MIN_RESIDUAL_SHARE,
    RADAR_MAX_NEW_PER_DAY,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.radar_policy import STATE_ABSENT, STATE_FRESH, STATE_STALE

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


def radar_policy(radar_state: str, budget_level: str, daily_new: int, share_spent: bool, hard_cap: bool) -> str:
    """
    O que fazer com o radar do assunto (P-180.3, P-178.4, P-178.8): USE_FRESH, GENERATE, USE_STALE ou NONE.
    Gera so com orcamento (nao esgotado), abaixo do teto duro de consultas, do limite diario e da fatia do radar;
    a 80% (ALERTA) so gera se nao existe nenhum radar para o assunto. Sem poder gerar, usa o vencido se houver.
    """
    if radar_state == STATE_FRESH:
        return "USE_FRESH"
    may_generate = (
        not hard_cap and not share_spent and daily_new < RADAR_MAX_NEW_PER_DAY and budget_level != "ESGOTADO"
        and (budget_level == "NORMAL" or radar_state == STATE_ABSENT)
    )
    if may_generate:
        return "GENERATE"
    return "USE_STALE" if radar_state == STATE_STALE else "NONE"


def product_search_enabled(evidence: EvidencePackage, budget_level: str, radar_state: str, hard_cap: bool) -> bool:
    """
    Busca especifica do produto (P-180.1 v3.1): so SEM radar utilizavel, com termo, modo != QUALITATIVO, orcamento
    NORMAL, residuo >= 0,30 e abaixo do teto duro de consultas. Com radar o diagnostico nao busca por conta propria.
    """
    if hard_cap or budget_level != "NORMAL" or radar_state != STATE_ABSENT:
        return False
    if not evidence.search_term_available or evidence.mode == MODE_QUALITATIVE:
        return False
    return (evidence.residual_share or 0.0) >= PRODUCT_SEARCH_MIN_RESIDUAL_SHARE
