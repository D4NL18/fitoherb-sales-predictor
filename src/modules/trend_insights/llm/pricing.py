"""
Tabela de precos (vem de `TREND_AI_PRICING_JSON`, nunca do codigo) e calculo do custo de uma chamada (P-178.1).
Custo = tokens (saida inclui thinking) x preco do modelo na data + consultas de busca acima da cota gratis.
"""
import json
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from src.modules.trend_insights.domain.constants import GROUNDING_FREE_QUERIES_ASSUMED
from src.modules.trend_insights.domain.exceptions import SettingsError

TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class TokenPrice:
    valid_from: date
    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class PricingTable:
    search_per_query: float
    models: Dict[str, Tuple[TokenPrice, ...]]

    def model_ids(self) -> List[str]:
        return sorted(self.models)

    def price_for(self, model_id: str, on_date: Optional[date] = None) -> TokenPrice:
        """Faixa vigente na data (a de `from` mais recente <= data); sem data, a mais recente."""
        tiers = self.models.get(model_id)
        if not tiers:
            raise SettingsError("Modelo sem preco configurado.", field="TREND_AI_PRICING_JSON")
        if on_date is None:
            return tiers[-1]
        eligible = [tier for tier in tiers if tier.valid_from <= on_date]
        return eligible[-1] if eligible else tiers[0]


def _parse_tiers(raw_tiers: list) -> Tuple[TokenPrice, ...]:
    tiers = [
        TokenPrice(
            valid_from=date.fromisoformat(tier["from"]),
            input_per_million=float(tier["input_per_million"]),
            output_per_million=float(tier["output_per_million"]),
        )
        for tier in raw_tiers
    ]
    return tuple(sorted(tiers, key=lambda tier: tier.valid_from))


def parse_pricing(raw_json: str) -> PricingTable:
    """Converte o JSON da configuracao; qualquer formato invalido vira `SettingsError` sem ecoar o conteudo."""
    try:
        data = json.loads(raw_json)
        models = {name: _parse_tiers(tiers) for name, tiers in data["models"].items()}
        return PricingTable(search_per_query=float(data["search_per_query"]), models=models)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise SettingsError("TREND_AI_PRICING_JSON invalido.", field="TREND_AI_PRICING_JSON") from None


def _billable_queries(executed: int, month_before: int, free_queries: int) -> int:
    after = month_before + executed
    return max(0, after - free_queries) - max(0, month_before - free_queries)


def compute_cost(
    model_id: str,
    usage,
    pricing: PricingTable,
    on_date: date,
    executed_queries: int,
    month_queries_before: int,
    free_queries: int = GROUNDING_FREE_QUERIES_ASSUMED,
) -> float:
    """Custo real em US$ da chamada, com a faixa de preco vigente em `on_date`."""
    price = pricing.price_for(model_id, on_date)
    input_tokens = usage.input_tokens + usage.tool_tokens
    output_tokens = usage.output_tokens + usage.thinking_tokens
    token_cost = (input_tokens * price.input_per_million + output_tokens * price.output_per_million) / TOKENS_PER_MILLION
    search_cost = _billable_queries(executed_queries, month_queries_before, free_queries) * pricing.search_per_query
    return token_cost + search_cost
