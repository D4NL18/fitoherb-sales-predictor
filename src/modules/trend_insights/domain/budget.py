"""Niveis do orcamento e valor da reserva (P-178). Funcoes puras sobre a tabela de precos."""
from datetime import date
from typing import Any, Dict, Optional

from src.modules.trend_insights.domain.constants import (
    BUDGET_ALERT_RATIO,
    GROUNDING_FREE_QUERIES_ASSUMED,
    RADAR_BUDGET_SHARE,
    RADAR_MAX_NEW_PER_DAY,
    RADAR_MAX_OUTPUT_TOKENS,
    RADAR_RESERVATION_INPUT_TOKENS,
    RADAR_RESERVED_MONTHLY_USD,
    RESERVATION_ASSUMED_INPUT_TOKENS,
    RESERVATION_ASSUMED_OUTPUT_TOKENS,
    RESERVATION_ASSUMED_SEARCH_QUERIES,
)
from src.modules.trend_insights.domain.exceptions import BudgetDenied

KIND_DIAGNOSIS = "DIAGNOSTICO"
KIND_RADAR = "RADAR"
TOKENS_PER_MILLION = 1_000_000
LEVEL_COMPARE_DECIMALS = 6
_EPSILON = 1e-9


def budget_level(month_spent: float, day_spent: float, monthly_cap: float, daily_cap: float) -> str:
    """NORMAL, ALERTA (>= 80% do teto mensal) ou ESGOTADO (teto mensal ou diario atingido)."""
    month = round(month_spent, LEVEL_COMPARE_DECIMALS)
    day = round(day_spent, LEVEL_COMPARE_DECIMALS)
    if month >= round(monthly_cap, LEVEL_COMPARE_DECIMALS) or day >= round(daily_cap, LEVEL_COMPARE_DECIMALS):
        return "ESGOTADO"
    if month >= round(monthly_cap * BUDGET_ALERT_RATIO, LEVEL_COMPARE_DECIMALS):
        return "ALERTA"
    return "NORMAL"


def reservation_amount(
    model_id: str,
    pricing,
    *,
    with_search: bool,
    month_queries: int,
    on_date: Optional[date] = None,
    free_queries: int = GROUNDING_FREE_QUERIES_ASSUMED,
    kind: str = KIND_DIAGNOSIS,
) -> float:
    """
    Custo maximo estimado de uma tentativa. Diagnostico: 8.000 tokens de entrada + 2.500 de saida (+ 3 consultas
    pagas se houver busca). Radar (P-178.2 v3.1): so tokens (~US$ 0,02): a busca do radar nunca e paga de proposito,
    pois o teto duro de consultas (P-178.8) impede o radar acima da cota.
    """
    price = pricing.price_for(model_id, on_date)
    if kind == KIND_RADAR:
        return (RADAR_RESERVATION_INPUT_TOKENS * price.input_per_million
                + RADAR_MAX_OUTPUT_TOKENS * price.output_per_million) / TOKENS_PER_MILLION
    amount = (
        RESERVATION_ASSUMED_INPUT_TOKENS * price.input_per_million
        + RESERVATION_ASSUMED_OUTPUT_TOKENS * price.output_per_million
    ) / TOKENS_PER_MILLION
    exceeds_free_quota = month_queries + RESERVATION_ASSUMED_SEARCH_QUERIES > free_queries
    if with_search and exceeds_free_quota:
        amount += RESERVATION_ASSUMED_SEARCH_QUERIES * pricing.search_per_query
    return amount


def check_radar_caps(
    document: Dict[str, Any], amount: float, reserved_radar: float, monthly_budget_usd: float, hard_cap_queries: int,
) -> None:
    """Travas do radar (P-178.8, P-180.3): teto duro de consultas, radares por dia e fatia do teto mensal."""
    share_cap = RADAR_BUDGET_SHARE * monthly_budget_usd
    is_over_cap = (
        document["consultasMes"] >= hard_cap_queries
        or document["radaresNovosDia"]["valor"] >= RADAR_MAX_NEW_PER_DAY
        or document["gastoRadarMes"] + reserved_radar + amount > share_cap + _EPSILON
    )
    if is_over_cap:
        raise BudgetDenied()


def radar_headroom(document: Dict[str, Any]) -> float:
    """
    Folga mensal protegida para os radares (P-178.9, ~15 radares = US$ 0,22), aplicada desde o 1o dia do mes: o
    diagnostico nunca esgota o teto antes de os radares serem gerados. Encolhe conforme o gasto real do radar.
    """
    return max(0.0, RADAR_RESERVED_MONTHLY_USD - document["gastoRadarMes"])
