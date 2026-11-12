"""
Recomendação de Cross-sell por Cliente — domínio puro (P-062, P-063, P-064).

Fluxo: histórico do cliente (último `order_day` por SKU) -> perfil dos últimos 365 dias -> candidatos
(consequentes que o cliente nunca comprou ou que são Produto Dormente) -> viabilidade comercial
(catálogo, estoque, margem) -> Pontuação de Cross-sell (máximo por candidato, não soma) -> ordenação.

O cliente é identificado só pelo `Cod Cliente` inteiro (P-070); nada aqui registra log.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Literal, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.modules.analytics.domain.cross_sell import (
    CUSTOMER_PROFILE_DAYS,
    DORMANT_DAYS,
    CatalogEntry,
    UsefulRule,
    calculate_unit_margin,
    is_out_of_stock,
)
from src.modules.analytics.domain.exceptions import CustomerWithoutHistoryError

CandidateReason = Literal["NUNCA_COMPROU", "DORMENTE"]
NEVER_BOUGHT: CandidateReason = "NUNCA_COMPROU"          # P-062.4a
DORMANT: CandidateReason = "DORMENTE"                    # P-062.4b
EMPTY_REASON_NO_RECENT_PURCHASES = "SEM_COMPRAS_RECENTES"  # P-062.7 / C-07


@dataclass(frozen=True, eq=False)
class CustomerHistory:
    """
    Histórico cliente x SKU (P-062.2): último `order_day` de cada SKU comprado pelo cliente.

    Guardado em três vetores `int32` ordenados por cliente (~12 B por par, DA-03), consultados por
    busca binária. Evita um dicionário Python por cliente no cache residente.
    """

    customer_codes: np.ndarray
    skus: np.ndarray
    last_order_days: np.ndarray

    def last_purchase_days(self, customer_code: int) -> Dict[int, int]:
        """SKU -> último `order_day` do cliente; dicionário vazio se o cliente não tem histórico."""
        start = int(np.searchsorted(self.customer_codes, customer_code, side="left"))
        end = int(np.searchsorted(self.customer_codes, customer_code, side="right"))
        return dict(zip(self.skus[start:end].tolist(), self.last_order_days[start:end].tolist(), strict=True))

    def list_customers(self) -> List[int]:
        """Códigos de cliente distintos, em ordem crescente (uso do backtest)."""
        return np.unique(self.customer_codes).tolist()


@dataclass(frozen=True)
class CustomerSnapshotView:
    """Visão mínima que a recomendação por cliente consome (o `AnalyticsSnapshot` também atende)."""

    rules_by_antecedent: Mapping[int, Tuple[UsefulRule, ...]]
    catalog: Mapping[int, CatalogEntry]
    customer_history: CustomerHistory
    reference_day: int


@dataclass(frozen=True)
class CustomerRecommendation:
    """Item da Recomendação por Cliente (P-064.4). `score` sem arredondamento (P-064.3)."""

    rule: UsefulRule
    entry: CatalogEntry
    reason: CandidateReason
    days_since_last_purchase: Optional[int]
    related_antecedent_count: int
    unit_margin: float
    score: float


@dataclass(frozen=True)
class CustomerRecommendationResult:
    """Lista completa (antes da paginação) e `motivoVazio` (`SEM_COMPRAS_RECENTES` ou `None`)."""

    items: Tuple[CustomerRecommendation, ...]
    empty_reason: Optional[str] = None


@dataclass(frozen=True)
class _CandidateContext:
    """Dados do cliente e do catálogo usados para avaliar cada candidato (agrupa parâmetros)."""

    days_since_purchase: Mapping[int, int]
    catalog: Mapping[int, CatalogEntry]
    apply_stock_filter: bool


# ------------------------------------------------------------------ histórico e perfil (P-062.1, P-062.2)

def build_customer_history(order_baskets: pd.DataFrame) -> CustomerHistory:
    """
    Último `order_day` por cliente x SKU, a partir do agregado (pedidos de 1 SKU contam, P-062.1).
    Regra: P-062.2.
    """
    last_days = order_baskets.groupby(["customer_code", "sku"], sort=True)["order_day"].max()
    return CustomerHistory(
        customer_codes=last_days.index.get_level_values("customer_code").to_numpy(dtype=np.int32),
        skus=last_days.index.get_level_values("sku").to_numpy(dtype=np.int32),
        last_order_days=last_days.to_numpy(dtype=np.int32),
    )


def days_since_last_purchase(view, customer_code: int) -> Dict[int, int]:
    """
    SKU -> dias desde a última compra do cliente, contados da data de referência (DA-05).

    Raises:
        CustomerWithoutHistoryError: `XSL-002` se o cliente não tem nenhum pedido de VENDA (P-062.7).
    """
    last_days = view.customer_history.last_purchase_days(customer_code)
    if not last_days:
        raise CustomerWithoutHistoryError()
    return {sku: view.reference_day - last_day for sku, last_day in last_days.items()}


def build_customer_profile(days_since_purchase: Mapping[int, int]) -> FrozenSet[int]:
    """Perfil (antecedentes): SKUs comprados há no máximo `CUSTOMER_PROFILE_DAYS` dias. Regra: P-062.1."""
    return frozenset(sku for sku, days in days_since_purchase.items() if days <= CUSTOMER_PROFILE_DAYS)


def classify_candidate(days_since: Optional[int]) -> Optional[CandidateReason]:
    """
    Tipo do candidato: nunca comprado -> `NUNCA_COMPROU`; última compra há mais de 90 dias -> `DORMENTE`;
    comprado nos últimos 90 dias (inclusive) -> `None` (não é candidato). Regra: P-062.3, P-062.4.
    """
    if days_since is None:
        return NEVER_BOUGHT
    if days_since > DORMANT_DAYS:
        return DORMANT
    return None


# ------------------------------------------------------------------ viabilidade e pontuação (P-063, P-064)

def is_commercially_viable(entry: Optional[CatalogEntry], apply_stock_filter: bool) -> bool:
    """
    No catálogo ativo, com margem > 0 e (fora do backtest) estoque > 0.
    Regra: P-063.1, P-063.2, P-063.4; P-071.5 desliga o filtro de estoque.
    """
    if entry is None or calculate_unit_margin(entry) <= 0:
        return False
    return not (apply_stock_filter and is_out_of_stock(entry))


def calculate_cross_sell_score(lift: float, confidence: float, unit_margin: float) -> float:
    """Pontuação de Cross-sell = lift x confiança x Margem Unitária (R$). Regra: P-064."""
    return lift * confidence * unit_margin


def _collect_candidate_rules(view, profile: FrozenSet[int], days_since_purchase: Mapping[int, int]
                             ) -> Dict[int, List[UsefulRule]]:
    """
    Candidato -> regras do perfil que o sugerem. Antecedentes em ordem crescente (desempate
    determinístico); consequentes comprados nos últimos 90 dias são descartados (P-062.4, P-062.6).
    """
    candidate_rules: Dict[int, List[UsefulRule]] = {}
    for antecedent in sorted(profile):
        for rule in view.rules_by_antecedent.get(antecedent, ()):
            if classify_candidate(days_since_purchase.get(rule.consequent)) is None:
                continue
            candidate_rules.setdefault(rule.consequent, []).append(rule)
    return candidate_rules


def aggregate_best_rule_per_candidate(rules: Sequence[UsefulRule], unit_margin: float) -> Tuple[UsefulRule, float]:
    """
    Regra principal do candidato: a de maior pontuação (máximo, não soma). Empate exato fica com o
    menor código de antecedente (as regras chegam em ordem crescente de antecedente). Regra: P-064.1.
    """
    best_rule, best_score = rules[0], calculate_cross_sell_score(rules[0].lift, rules[0].confidence, unit_margin)
    for rule in rules[1:]:
        score = calculate_cross_sell_score(rule.lift, rule.confidence, unit_margin)
        if score > best_score:
            best_rule, best_score = rule, score
    return best_rule, best_score


def _build_candidate_item(context: _CandidateContext, candidate: int, rules: Sequence[UsefulRule]
                          ) -> Optional[CustomerRecommendation]:
    """Item do candidato viável, ou `None` se ele não passa na viabilidade comercial (P-063)."""
    entry = context.catalog.get(candidate)
    if not is_commercially_viable(entry, context.apply_stock_filter):
        return None
    unit_margin = calculate_unit_margin(entry)
    best_rule, score = aggregate_best_rule_per_candidate(rules, unit_margin)
    days_since = context.days_since_purchase.get(candidate)
    return CustomerRecommendation(
        rule=best_rule, entry=entry, reason=classify_candidate(days_since), days_since_last_purchase=days_since,
        related_antecedent_count=len(rules), unit_margin=unit_margin, score=score,
    )


def _customer_mode_order(item: CustomerRecommendation) -> Tuple[float, float, int]:
    """Chave de P-064.2: pontuação desc, lift desc, código asc (valor integral, P-064.3)."""
    return (-item.score, -item.rule.lift, item.rule.consequent)


def recommend_for_customer(view, customer_code: int, apply_stock_filter: bool = True
                           ) -> CustomerRecommendationResult:
    """
    "O que oferecer a este cliente?"

    Args:
        view: objeto com `rules_by_antecedent`, `catalog`, `customer_history` e `reference_day`.
        customer_code: `Cod Cliente`.
        apply_stock_filter: `False` só no backtest (P-071.5).

    Returns:
        Lista completa e ordenada (filtros antes da paginação, P-063.5) e `empty_reason`.

    Raises:
        CustomerWithoutHistoryError: `XSL-002` (P-062.7).
    """
    days_since_purchase = days_since_last_purchase(view, customer_code)
    profile = build_customer_profile(days_since_purchase)
    if not profile:
        return CustomerRecommendationResult(items=(), empty_reason=EMPTY_REASON_NO_RECENT_PURCHASES)
    context = _CandidateContext(days_since_purchase, view.catalog, apply_stock_filter)
    candidate_rules = _collect_candidate_rules(view, profile, days_since_purchase)
    items = (_build_candidate_item(context, candidate, rules) for candidate, rules in candidate_rules.items())
    return CustomerRecommendationResult(items=tuple(sorted((item for item in items if item), key=_customer_mode_order)))
