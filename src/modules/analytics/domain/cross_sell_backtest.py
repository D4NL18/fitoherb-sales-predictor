"""
Backtest temporal de hit rate@5 e linha de base por popularidade — domínio puro (P-071, ADR-002 DA-12).

Protocolo: para o mês N, o treino usa só pedidos com `order_day` < 1º dia de N (nada de N vaza, CA-23);
a data de referência é o último dia de N-1. Clientes avaliados = perfil não vazio no corte, compra em N
e ao menos uma recomendação. Acerto = comprou em N algum dos `HIT_RATE_K` primeiros SKUs sugeridos.
O filtro de estoque fica desligado (sem estoque histórico, P-071.5); a margem usa preço e custo atuais.

Saída só com agregados (LGPD-11): nenhum `customerCode`, lista ou acerto por cliente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import islice
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from src.modules.analytics.domain.cross_sell import (
    HIT_RATE_K,
    ORDER_DAY_EPOCH,
    build_catalog_lookup,
    build_valid_baskets,
    calculate_unit_margin,
    count_valid_baskets,
    index_rules_by_antecedent,
    mine_one_to_one_rules,
    select_useful_rules,
)
from src.modules.analytics.domain.cross_sell_customer import (
    CustomerSnapshotView,
    build_customer_history,
    build_customer_profile,
    classify_candidate,
    recommend_for_customer,
)
from src.modules.analytics.domain.recommendation_curation import curate

EXCLUDED_NO_PROFILE = "SEM_PERFIL"                  # P-071.3: perfil vazio no corte
EXCLUDED_NO_PURCHASE_IN_MONTH = "SEM_COMPRA_NO_MES"  # P-071.3: sem pedido de VENDA em N
EXCLUDED_NO_RECOMMENDATION = "SEM_RECOMENDACAO"     # P-071.3: nenhuma recomendação gerada
EXCLUSION_REASONS = (EXCLUDED_NO_PROFILE, EXCLUDED_NO_PURCHASE_IN_MONTH, EXCLUDED_NO_RECOMMENDATION)

_MONTHS_PER_YEAR = 12
_NO_PREVIOUS_PURCHASE: Mapping[int, int] = {}


@dataclass(frozen=True)
class BacktestMonthResult:
    """Métricas agregadas de um mês N (P-071.4, P-071.6, P-071.7)."""

    month: str
    model_hit_rate: float
    popularity_hit_rate: float
    evaluated_customers: int
    excluded_by_reason: Dict[str, int]


@dataclass(frozen=True)
class BacktestSummary:
    """Média simples dos meses avaliados (P-071.1, meta A-12)."""

    model_hit_rate: float
    popularity_hit_rate: float
    evaluated_customers: int


@dataclass(frozen=True)
class _MonthContext:
    """Tudo o que a avaliação de um cliente precisa, calculado uma vez por mês."""

    view: CustomerSnapshotView
    popularity_ranking: Tuple[int, ...]
    purchases_in_month: Mapping[int, FrozenSet[int]]


# ------------------------------------------------------------------ janelas do mês (P-071.2)

def _to_order_day(day: date) -> int:
    """Data -> `order_day` (dias desde `ORDER_DAY_EPOCH`, DA-05)."""
    return (day - ORDER_DAY_EPOCH).days


def month_boundaries(month: str) -> Tuple[int, int]:
    """
    (`order_day` do 1º dia de N, `order_day` do 1º dia de N+1) para `month` no formato "YYYY-MM".
    """
    year, month_number = (int(part) for part in month.split("-"))
    first_day = date(year, month_number, 1)
    next_year, next_month = divmod(month_number, _MONTHS_PER_YEAR)
    next_first_day = date(year + next_year, next_month + 1, 1)
    return _to_order_day(first_day), _to_order_day(next_first_day)


def split_train_and_eval(order_baskets: pd.DataFrame, month: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Treino = pedidos antes do 1º dia de N; avaliação = pedidos dentro de N. Regra: P-071.2, CA-23.
    """
    month_start, next_month_start = month_boundaries(month)
    order_days = order_baskets["order_day"]
    train = order_baskets[order_days < month_start]
    evaluation = order_baskets[(order_days >= month_start) & (order_days < next_month_start)]
    return train, evaluation


# ------------------------------------------------------------------ modelo e popularidade no treino

def _build_training_view(train: pd.DataFrame, catalog: Mapping, reference_day: int) -> CustomerSnapshotView:
    """Mesma esteira da produção (B-10 a B-12), só com o treino."""
    valid_baskets = build_valid_baskets(train)
    useful_rules = select_useful_rules(mine_one_to_one_rules(valid_baskets), count_valid_baskets(valid_baskets))
    return CustomerSnapshotView(
        rules_by_antecedent=index_rules_by_antecedent(useful_rules), catalog=catalog,
        customer_history=build_customer_history(train), reference_day=reference_day,
    )


def build_popularity_ranking(train: pd.DataFrame, catalog: Mapping) -> Tuple[int, ...]:
    """
    SKUs do treino por número de Cestas Válidas (desc, código asc), só no catálogo e com margem > 0.
    Regra: P-071.6 (mesmos filtros de catálogo e margem do modelo; sem filtro de estoque).
    """
    valid_baskets = build_valid_baskets(train)
    basket_counts = valid_baskets.groupby("Cod Produto")["Pedido"].nunique()
    ranked = sorted(basket_counts.items(), key=lambda sku_count: (-sku_count[1], sku_count[0]))
    return tuple(
        int(sku) for sku, _ in ranked
        if int(sku) in catalog and calculate_unit_margin(catalog[int(sku)]) > 0
    )


def recommend_by_popularity(ranking: Sequence[int], days_since_purchase: Mapping[int, int]) -> List[int]:
    """
    Top `HIT_RATE_K` da popularidade sem os SKUs comprados pelo cliente nos últimos 90 dias. Regra: P-071.6.
    """
    eligible = (sku for sku in ranking if classify_candidate(days_since_purchase.get(sku)) is not None)
    return list(islice(eligible, HIT_RATE_K))


def _purchases_by_customer(evaluation: pd.DataFrame) -> Dict[int, FrozenSet[int]]:
    """Cliente -> SKUs comprados no mês N."""
    grouped = evaluation.groupby("customer_code")["sku"].unique()
    return {int(customer): frozenset(skus.tolist()) for customer, skus in grouped.items()}


# ------------------------------------------------------------------ avaliação por cliente (P-071.3, P-071.4)

def _days_since_purchase(context: _MonthContext, customer_code: int) -> Mapping[int, int]:
    """Dias desde a última compra no treino; vazio para cliente que só comprou em N."""
    last_days = context.view.customer_history.last_purchase_days(customer_code)
    if not last_days:
        return _NO_PREVIOUS_PURCHASE
    return {sku: context.view.reference_day - day for sku, day in last_days.items()}


def _evaluate_customer(context: _MonthContext, customer_code: int) -> Tuple[Optional[str], bool, bool]:
    """
    (motivo de exclusão ou `None`, acertou no modelo, acertou na popularidade).
    Precedência dos motivos: sem perfil > sem compra em N > sem recomendação.
    """
    days_since_purchase = _days_since_purchase(context, customer_code)
    if not build_customer_profile(days_since_purchase):
        return EXCLUDED_NO_PROFILE, False, False
    bought_in_month = context.purchases_in_month.get(customer_code, frozenset())
    if not bought_in_month:
        return EXCLUDED_NO_PURCHASE_IN_MONTH, False, False
    result = recommend_for_customer(context.view, customer_code, apply_stock_filter=False)
    # P-094.5: o backtest mede o top-K da lista curada, que é o que a tela mostra.
    curated = curate(result.items, context.view.catalog, rule_of=lambda item: item.rule)
    model_top_k = {item.rule.consequent for item in curated[:HIT_RATE_K]}
    if not model_top_k:
        return EXCLUDED_NO_RECOMMENDATION, False, False
    popularity_top_k = set(recommend_by_popularity(context.popularity_ranking, days_since_purchase))
    return None, bool(model_top_k & bought_in_month), bool(popularity_top_k & bought_in_month)


def _population(order_baskets: pd.DataFrame, next_month_start: int) -> List[int]:
    """Todo cliente com pedido de VENDA até o fim de N (decisão do Tester registrada em STATE_Tester)."""
    customers = order_baskets.loc[order_baskets["order_day"] < next_month_start, "customer_code"]
    return sorted(set(customers.tolist()))


def _hit_rate(hits: int, evaluated: int) -> float:
    """Taxa de acerto; 0,0 quando ninguém foi avaliado (sem divisão por zero)."""
    return hits / evaluated if evaluated else 0.0


def _build_month_context(order_baskets: pd.DataFrame, catalog_df: pd.DataFrame, month: str) -> _MonthContext:
    """Treino, popularidade e compras de N, calculados uma vez por mês."""
    month_start, _ = month_boundaries(month)
    train, evaluation = split_train_and_eval(order_baskets, month)
    catalog = build_catalog_lookup(catalog_df)
    return _MonthContext(
        view=_build_training_view(train, catalog, reference_day=month_start - 1),
        popularity_ranking=build_popularity_ranking(train, catalog),
        purchases_in_month=_purchases_by_customer(evaluation),
    )


def evaluate_month(order_baskets: pd.DataFrame, catalog_df: pd.DataFrame, month: str) -> BacktestMonthResult:
    """
    hit rate@5 do modelo e da popularidade para o mês N, com clientes avaliados e excluídos por motivo.

    Args:
        order_baskets: agregado completo (`int32`), com treino e mês N.
        catalog_df: catálogo atual (P-071.5).
        month: "YYYY-MM".

    Regra: P-071.2 a P-071.6; CA-23, CA-24.
    """
    context = _build_month_context(order_baskets, catalog_df, month)
    excluded: Dict[str, int] = dict.fromkeys(EXCLUSION_REASONS, 0)
    model_hits = popularity_hits = evaluated = 0
    for customer_code in _population(order_baskets, month_boundaries(month)[1]):
        exclusion, is_model_hit, is_popularity_hit = _evaluate_customer(context, customer_code)
        if exclusion is not None:
            excluded[exclusion] += 1
            continue
        evaluated += 1
        model_hits += is_model_hit
        popularity_hits += is_popularity_hit
    return BacktestMonthResult(month=month, model_hit_rate=_hit_rate(model_hits, evaluated),
                               popularity_hit_rate=_hit_rate(popularity_hits, evaluated),
                               evaluated_customers=evaluated, excluded_by_reason=excluded)


def summarize(results: Sequence[BacktestMonthResult]) -> BacktestSummary:
    """Média simples dos meses (P-071.1) e total de clientes avaliados; zeros sem meses."""
    if not results:
        return BacktestSummary(model_hit_rate=0.0, popularity_hit_rate=0.0, evaluated_customers=0)
    month_count = len(results)
    return BacktestSummary(
        model_hit_rate=sum(result.model_hit_rate for result in results) / month_count,
        popularity_hit_rate=sum(result.popularity_hit_rate for result in results) / month_count,
        evaluated_customers=sum(result.evaluated_customers for result in results),
    )
