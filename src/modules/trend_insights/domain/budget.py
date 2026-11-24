"""Niveis do orcamento e valor da reserva (P-178). Funcoes puras sobre a tabela de precos."""
from datetime import date
from typing import Optional

from src.modules.trend_insights.domain.constants import (
    BUDGET_ALERT_RATIO,
    GROUNDING_FREE_QUERIES_ASSUMED,
    RESERVATION_ASSUMED_INPUT_TOKENS,
    RESERVATION_ASSUMED_OUTPUT_TOKENS,
    RESERVATION_ASSUMED_SEARCH_QUERIES,
)

TOKENS_PER_MILLION = 1_000_000
LEVEL_COMPARE_DECIMALS = 6


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
) -> float:
    """Custo maximo estimado de uma tentativa: 8.000 tokens de entrada + 2.500 de saida (+ 3 consultas pagas)."""
    price = pricing.price_for(model_id, on_date)
    amount = (
        RESERVATION_ASSUMED_INPUT_TOKENS * price.input_per_million
        + RESERVATION_ASSUMED_OUTPUT_TOKENS * price.output_per_million
    ) / TOKENS_PER_MILLION
    exceeds_free_quota = month_queries + RESERVATION_ASSUMED_SEARCH_QUERIES > free_queries
    if with_search and exceeds_free_quota:
        amount += RESERVATION_ASSUMED_SEARCH_QUERIES * pricing.search_per_query
    return amount
