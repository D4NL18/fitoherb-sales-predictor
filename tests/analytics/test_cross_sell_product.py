"""
T-09 — Recomendação por Produto (P-061, P-063.3, CA-07, CA-10, C-02, C-03, C-09, C-10).

Domínio puro. Interface esperada (B-11, `src/modules/analytics/domain/cross_sell.py`):
- `CatalogEntry` frozen dataclass (código, descrição, fornecedor, estoque, preço, custo unitário,
  `is_cost_estimated`)
- `build_catalog_lookup(catalog_df) -> Dict[int, CatalogEntry]` (custo com fallback de 60%, P-063.3)
- `calculate_unit_margin(entry) -> float`
- `recommend_for_product(snapshot_view, sku) -> List[ProductRecommendation]`, onde `snapshot_view` é
  qualquer objeto com `rules_by_antecedent`, `catalog` e `skus_with_basket` (o `AnalyticsSnapshot`
  atende). `ProductRecommendation` expõe `rule` (`UsefulRule`), `entry` (`CatalogEntry`),
  `is_out_of_stock` e `has_non_positive_margin`.
"""
import dataclasses
import math
from types import SimpleNamespace

import pytest

from src.modules.analytics.domain.cross_sell import (
    CatalogEntry,
    UsefulRule,
    build_catalog_lookup,
    calculate_unit_margin,
    index_rules_by_antecedent,
    recommend_for_product,
)
from src.modules.analytics.domain.exceptions import ProductNotFoundError
from tests.analytics.fixtures.synthetic_data import SyntheticProduct, catalog_frame

ANTECEDENT = 1
N_BASKETS = 10_000


def make_rule(consequent, lift, confidence, pair_orders, antecedent=ANTECEDENT):
    return UsefulRule(antecedent=antecedent, consequent=consequent, support=pair_orders / N_BASKETS,
                      confidence=confidence, lift=lift, pair_orders=pair_orders, antecedent_orders=500)


def product(sku, stock=10.0, cost=5.0, price=10.0):
    return SyntheticProduct(sku, f"PRODUTO {sku}", f"FORNECEDOR {sku}", stock, cost, price)


def make_view(rules, products, skus_with_basket=None):
    catalog = build_catalog_lookup(catalog_frame(products))
    if skus_with_basket is None:
        skus_with_basket = {ANTECEDENT} | {r.consequent for r in rules} | {r.antecedent for r in rules}
    return SimpleNamespace(
        rules_by_antecedent=index_rules_by_antecedent(rules),
        catalog=catalog,
        skus_with_basket=frozenset(skus_with_basket),
    )


def consequents(recommendations):
    return [rec.rule.consequent for rec in recommendations]


# ------------------------------------------------------------------ catálogo e margem (P-063.3)

def test_catalog_entry_is_frozen():
    entry = build_catalog_lookup(catalog_frame([product(ANTECEDENT)]))[ANTECEDENT]
    assert isinstance(entry, CatalogEntry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.is_cost_estimated = True  # type: ignore[misc]


def test_real_cost_is_used_when_positive():
    entry = build_catalog_lookup(catalog_frame([product(10, cost=15.0, price=25.0)]))[10]

    assert entry.is_cost_estimated is False
    assert calculate_unit_margin(entry) == pytest.approx(10.0)


@pytest.mark.parametrize("missing_cost", [0.0, -3.0, float("nan"), None])
def test_ca12_cost_fallback_is_60_percent_of_price(missing_cost):
    """CA-12: Pc.Venda 25,00 e custo 0 (ou ausente/negativo) -> margem 10,00 e custoEstimado."""
    entry = build_catalog_lookup(catalog_frame([product(10, cost=missing_cost, price=25.0)]))[10]

    assert entry.is_cost_estimated is True
    assert calculate_unit_margin(entry) == pytest.approx(10.0)


def test_catalog_lookup_keys_are_int_skus():
    lookup = build_catalog_lookup(catalog_frame([product(10), product(20)]))
    assert set(lookup) == {10, 20}
    assert all(isinstance(key, int) for key in lookup)


# ------------------------------------------------------------------ CA-07 ordenação (P-061.1)

def test_ca07_order_by_lift_confidence_pair_orders_and_code():
    rules = [
        make_rule(11, lift=2.0, confidence=0.2, pair_orders=100),
        make_rule(16, lift=2.0, confidence=0.2, pair_orders=50),
        make_rule(12, lift=2.0, confidence=0.3, pair_orders=100),
        make_rule(10, lift=2.0, confidence=0.2, pair_orders=50),
        make_rule(13, lift=3.0, confidence=0.2, pair_orders=100),
    ]
    view = make_view(rules, [product(sku) for sku in (ANTECEDENT, 10, 11, 12, 13, 16)])

    assert consequents(recommend_for_product(view, ANTECEDENT)) == [13, 12, 11, 10, 16]


def test_recommendation_carries_rule_metrics():
    rule = make_rule(10, lift=4.25, confidence=0.34, pair_orders=170)
    view = make_view([rule], [product(ANTECEDENT), product(10)])

    [recommendation] = recommend_for_product(view, ANTECEDENT)

    assert recommendation.rule == rule
    assert recommendation.entry.is_cost_estimated is False


# ------------------------------------------------------------------ P-061.3 fora do catálogo

def test_consequent_outside_catalog_is_excluded():
    rules = [make_rule(10, 3.0, 0.3, 100), make_rule(99, 5.0, 0.5, 100)]
    view = make_view(rules, [product(ANTECEDENT), product(10)])

    assert consequents(recommend_for_product(view, ANTECEDENT)) == [10]


# ------------------------------------------------------------------ P-061.4 sinalizações (CA-10, C-09, C-10)

@pytest.mark.parametrize("stock, expected", [(0.0, True), (-2.0, True), (0.5, False), (84.0, False)])
def test_ca10_out_of_stock_is_flagged_not_excluded(stock, expected):
    view = make_view([make_rule(10, 3.0, 0.3, 100)], [product(ANTECEDENT), product(10, stock=stock)])

    [recommendation] = recommend_for_product(view, ANTECEDENT)

    assert recommendation.is_out_of_stock is expected


@pytest.mark.parametrize(
    "cost, price, expected",
    [(10.0, 10.0, True), (12.0, 10.0, True), (9.99, 10.0, False), (0.0, 25.0, False)],
)
def test_c10_non_positive_margin_is_flagged_not_excluded(cost, price, expected):
    view = make_view([make_rule(10, 3.0, 0.3, 100)], [product(ANTECEDENT), product(10, cost=cost, price=price)])

    [recommendation] = recommend_for_product(view, ANTECEDENT)

    assert recommendation.has_non_positive_margin is expected


def test_flagged_items_keep_api_order():
    """D-8: sinalizados não são reordenados nem esmaecidos; a ordem continua a de P-061.1."""
    rules = [make_rule(10, 3.0, 0.3, 100), make_rule(20, 2.0, 0.3, 100)]
    view = make_view(rules, [product(ANTECEDENT), product(10, stock=0.0), product(20)])

    assert consequents(recommend_for_product(view, ANTECEDENT)) == [10, 20]


# ------------------------------------------------------------------ C-02 e C-03

def test_c02_sku_with_baskets_but_no_useful_rule_returns_empty_list():
    view = make_view([make_rule(10, 3.0, 0.3, 100, antecedent=50)], [product(ANTECEDENT), product(10), product(50)],
                     skus_with_basket={ANTECEDENT, 10, 50})

    assert list(recommend_for_product(view, ANTECEDENT)) == []


@pytest.mark.parametrize(
    "case, products, skus_with_basket",
    [
        ("fora do catálogo", [product(10)], {ANTECEDENT, 10}),
        ("sem Cesta Válida", [product(ANTECEDENT), product(10)], {10}),
        ("inexistente", [product(10)], {10}),
    ],
)
def test_c03_unknown_or_basketless_sku_raises_xsl001(case, products, skus_with_basket):
    view = make_view([make_rule(10, 3.0, 0.3, 100)], products, skus_with_basket=skus_with_basket)

    with pytest.raises(ProductNotFoundError) as exc_info:
        recommend_for_product(view, ANTECEDENT)
    assert exc_info.value.code == "XSL-001"


def test_margin_is_finite_for_all_entries():
    lookup = build_catalog_lookup(catalog_frame([product(10, cost=None, price=10.0), product(20, cost=7.0)]))
    assert all(math.isfinite(calculate_unit_margin(entry)) for entry in lookup.values())
