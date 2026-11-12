"""
T-10 — Recomendação por Cliente (P-062, P-063, P-064, CA-08 a CA-13, C-06, C-07, C-08).

Domínio puro. Interface esperada (B-12, `src/modules/analytics/domain/cross_sell_customer.py`):
- `build_customer_history(order_baskets)` (último `order_day` por cliente x SKU; formato livre)
- `calculate_cross_sell_score(lift, confidence, unit_margin) -> float` (P-064)
- `recommend_for_customer(snapshot_view, customer_code, apply_stock_filter=True)
  -> CustomerRecommendationResult(items, empty_reason)`, onde `snapshot_view` expõe
  `rules_by_antecedent`, `catalog`, `customer_history` e `reference_day` (int, `order_day` da data de
  referência). Cada item (`CustomerRecommendation`) expõe `rule` (regra principal), `entry`
  (`CatalogEntry`), `reason` (`"NUNCA_COMPROU"` | `"DORMENTE"`), `days_since_last_purchase`
  (int | None), `related_antecedent_count`, `unit_margin` e `score` (sem arredondamento, P-064.3).
"""
from types import SimpleNamespace

import pytest

from src.modules.analytics.domain.cross_sell import UsefulRule, build_catalog_lookup, index_rules_by_antecedent
from src.modules.analytics.domain.cross_sell_customer import (
    build_customer_history,
    calculate_cross_sell_score,
    recommend_for_customer,
)
from src.modules.analytics.domain.exceptions import CustomerWithoutHistoryError
from tests.analytics.fixtures.synthetic_data import REFERENCE_DAY, BasketBuilder, SyntheticProduct, catalog_frame

CUSTOMER = 4321
OTHER_CUSTOMER = 8765
SKU_A, SKU_B, SKU_D, SKU_G, SKU_H, SKU_K, SKU_X = 1, 2, 4, 7, 8, 11, 99


def make_rule(antecedent, consequent, lift, confidence, pair_orders=100):
    return UsefulRule(antecedent=antecedent, consequent=consequent, support=pair_orders / 10_000,
                      confidence=confidence, lift=lift, pair_orders=pair_orders, antecedent_orders=500)


def product(sku, stock=10.0, cost=5.0, price=10.0):
    return SyntheticProduct(sku, f"PRODUTO {sku}", f"FORNECEDOR {sku}", stock, cost, price)


DEFAULT_PRODUCTS = [product(sku) for sku in (SKU_A, SKU_B, SKU_D, SKU_G, SKU_H, SKU_K)]


def make_view(rules, purchases, products=None, orders=None):
    """`purchases`: (cliente, sku, dias atrás) em pedidos de 1 item; `orders`: (cliente, [skus], dias atrás)."""
    builder = BasketBuilder()
    for customer, sku, days_ago in purchases:
        builder.add_order([sku], customer_code=customer, order_day=REFERENCE_DAY - days_ago)
    for customer, skus, days_ago in orders or []:
        builder.add_order(skus, customer_code=customer, order_day=REFERENCE_DAY - days_ago)
    return SimpleNamespace(
        rules_by_antecedent=index_rules_by_antecedent(rules),
        catalog=build_catalog_lookup(catalog_frame(products or DEFAULT_PRODUCTS)),
        customer_history=build_customer_history(builder.to_frame()),
        reference_day=REFERENCE_DAY,
    )


def skus(result):
    return [item.rule.consequent for item in result.items]


# ------------------------------------------------------------------ P-064 pontuação

def test_score_is_lift_times_confidence_times_margin():
    assert calculate_cross_sell_score(4.25, 0.34, 5.0) == pytest.approx(7.225)
    assert calculate_cross_sell_score(1.5, 0.2, 30.0) == pytest.approx(9.0)


# ------------------------------------------------------------------ CA-08 / CA-09 candidatos e dormência

def test_ca08_only_never_bought_or_dormant_are_candidates():
    view = make_view(
        [make_rule(SKU_A, SKU_B, 3.0, 0.3), make_rule(SKU_A, SKU_D, 2.0, 0.2)],
        [(CUSTOMER, SKU_A, 10), (CUSTOMER, SKU_B, 30), (CUSTOMER, SKU_D, 120)],
    )

    result = recommend_for_customer(view, CUSTOMER)

    assert skus(result) == [SKU_D]
    [item] = result.items
    assert item.reason == "DORMENTE"
    assert item.days_since_last_purchase == 120
    assert result.empty_reason is None


@pytest.mark.parametrize("days_ago, expected", [(90, []), (91, [SKU_D])])
def test_ca09_dormancy_boundary(days_ago, expected):
    view = make_view([make_rule(SKU_A, SKU_D, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_D, days_ago)])

    assert skus(recommend_for_customer(view, CUSTOMER)) == expected


def test_never_bought_candidate_has_no_days():
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5)])

    [item] = recommend_for_customer(view, CUSTOMER).items

    assert item.reason == "NUNCA_COMPROU"
    assert item.days_since_last_purchase is None


def test_other_customers_purchases_do_not_affect_candidate():
    view = make_view(
        [make_rule(SKU_A, SKU_G, 2.0, 0.2)],
        [(CUSTOMER, SKU_A, 5), (OTHER_CUSTOMER, SKU_G, 1), (OTHER_CUSTOMER, SKU_A, 1)],
    )

    [item] = recommend_for_customer(view, CUSTOMER).items
    assert item.reason == "NUNCA_COMPROU"


# ------------------------------------------------------------------ P-063 viabilidade (CA-10, CA-11, CA-12)

def test_ca10_out_of_stock_candidate_is_excluded():
    products = [product(SKU_A), product(SKU_G, stock=0.0)]
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5)], products)

    assert skus(recommend_for_customer(view, CUSTOMER)) == []


def test_stock_filter_can_be_disabled_for_backtest():
    """P-071.5: o backtest chama com apply_stock_filter=False."""
    products = [product(SKU_A), product(SKU_G, stock=0.0)]
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5)], products)

    assert skus(recommend_for_customer(view, CUSTOMER, apply_stock_filter=False)) == [SKU_G]


@pytest.mark.parametrize("cost, price", [(10.0, 10.0), (11.0, 10.0)])
def test_ca11_non_positive_margin_is_excluded(cost, price):
    products = [product(SKU_A), product(SKU_G, cost=cost, price=price)]
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5)], products)

    assert skus(recommend_for_customer(view, CUSTOMER)) == []
    assert skus(recommend_for_customer(view, CUSTOMER, apply_stock_filter=False)) == []


def test_ca12_cost_fallback_keeps_candidate_with_estimated_cost():
    products = [product(SKU_A), product(SKU_G, cost=0.0, price=25.0)]
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 5)], products)

    [item] = recommend_for_customer(view, CUSTOMER).items

    assert item.unit_margin == pytest.approx(10.0)
    assert item.entry.is_cost_estimated is True
    assert item.score == pytest.approx(2.0 * 0.2 * 10.0)


def test_candidate_outside_catalog_is_excluded():
    view = make_view([make_rule(SKU_A, SKU_X, 5.0, 0.5)], [(CUSTOMER, SKU_A, 5)])

    assert skus(recommend_for_customer(view, CUSTOMER)) == []


def test_p063_5_filters_apply_before_any_pagination():
    """O domínio devolve a lista completa só com itens recomendáveis; o total reflete os filtros."""
    products = [product(SKU_A), product(SKU_B, stock=0.0), product(SKU_D, cost=10.0, price=10.0), product(SKU_G)]
    rules = [make_rule(SKU_A, SKU_B, 3.0, 0.3), make_rule(SKU_A, SKU_D, 3.0, 0.3), make_rule(SKU_A, SKU_G, 2.0, 0.2)]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5)], products)

    result = recommend_for_customer(view, CUSTOMER)

    assert skus(result) == [SKU_G]
    assert len(result.items) == 1


# ------------------------------------------------------------------ CA-13 pontuação, máximo e ordenação

CA13_PRODUCTS = [
    product(SKU_A), product(SKU_H),
    product(SKU_B, cost=10.0, price=15.0),   # margem 5,00
    product(SKU_G, cost=20.0, price=50.0),   # margem 30,00
    product(SKU_K, cost=10.0, price=10.0),   # margem 0,00
]


def test_ca13_g_before_b_and_g_counted_once():
    rules = [
        make_rule(SKU_A, SKU_B, 4.25, 0.34, 170),
        make_rule(SKU_A, SKU_G, 1.50, 0.20, 100),
        make_rule(SKU_H, SKU_G, 2.00, 0.15, 80),
        make_rule(SKU_H, SKU_K, 3.00, 0.30, 90),
    ]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_H, 8)], CA13_PRODUCTS)

    result = recommend_for_customer(view, CUSTOMER)

    assert skus(result) == [SKU_G, SKU_B]
    first, second = result.items
    assert first.score == pytest.approx(9.0)
    assert first.related_antecedent_count == 2
    assert first.unit_margin == pytest.approx(30.0)
    assert second.score == pytest.approx(7.225)
    assert second.related_antecedent_count == 1
    assert second.rule.antecedent == SKU_A


def test_main_rule_is_the_one_with_highest_score_not_sum():
    rules = [make_rule(SKU_A, SKU_G, 1.5, 0.20, 100), make_rule(SKU_H, SKU_G, 3.0, 0.15, 80)]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_H, 8)], CA13_PRODUCTS)

    [item] = recommend_for_customer(view, CUSTOMER).items

    assert item.rule.antecedent == SKU_H
    assert item.rule.pair_orders == 80
    assert item.score == pytest.approx(3.0 * 0.15 * 30.0)
    assert item.related_antecedent_count == 2


def test_score_tie_breaks_by_lift_then_code():
    products = [product(SKU_A), product(SKU_D, cost=6.0, price=10.0), product(SKU_B, cost=6.0, price=10.0),
                product(SKU_G, cost=8.0, price=10.0)]
    rules = [
        make_rule(SKU_A, SKU_D, 2.0, 0.25),   # 2,0 x 0,25 x 4 = 2,0
        make_rule(SKU_A, SKU_B, 2.0, 0.25),   # 2,0 (empata com D; código menor primeiro)
        make_rule(SKU_A, SKU_G, 4.0, 0.25),   # 4,0 x 0,25 x 2 = 2,0 (lift maior primeiro)
    ]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5)], products)

    assert skus(recommend_for_customer(view, CUSTOMER)) == [SKU_G, SKU_B, SKU_D]


# ------------------------------------------------------------------ P-062.1 perfil

def test_p062_1_single_item_orders_count_for_profile():
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 200)])

    assert skus(recommend_for_customer(view, CUSTOMER)) == [SKU_G]


def test_multi_item_order_contributes_every_sku_to_profile():
    rules = [make_rule(SKU_A, SKU_G, 2.0, 0.2), make_rule(SKU_H, SKU_B, 2.0, 0.2)]
    view = make_view(rules, [], orders=[(CUSTOMER, [SKU_A, SKU_H], 20)])

    assert sorted(skus(recommend_for_customer(view, CUSTOMER))) == [SKU_B, SKU_G]


@pytest.mark.parametrize("days_ago, expected", [(365, [SKU_G]), (366, [])])
def test_profile_window_boundary_365_days(days_ago, expected):
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, days_ago)])

    assert skus(recommend_for_customer(view, CUSTOMER)) == expected


def test_last_purchase_is_used_for_dormancy():
    """P-062.2: vale a data do último pedido do SKU (uma compra antiga não torna o SKU dormente)."""
    view = make_view(
        [make_rule(SKU_A, SKU_D, 2.0, 0.2)],
        [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_D, 300), (CUSTOMER, SKU_D, 40)],
    )

    assert skus(recommend_for_customer(view, CUSTOMER)) == []


# ------------------------------------------------------------------ P-062.6, C-06, C-07, C-08

def test_p062_6_profile_sku_never_recommended_to_itself_c06_empty():
    rules = [make_rule(SKU_A, SKU_H, 2.0, 0.2), make_rule(SKU_H, SKU_A, 2.0, 0.2)]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_H, 6)])

    result = recommend_for_customer(view, CUSTOMER)

    assert list(result.items) == []
    assert result.empty_reason is None


def test_dormant_profile_sku_can_be_recommended_from_other_antecedent():
    """Um SKU do perfil comprado há > 90 dias é Produto Dormente e pode ser candidato (P-062.4b)."""
    rules = [make_rule(SKU_A, SKU_H, 2.0, 0.2)]
    view = make_view(rules, [(CUSTOMER, SKU_A, 5), (CUSTOMER, SKU_H, 200)])

    [item] = recommend_for_customer(view, CUSTOMER).items
    assert item.rule.consequent == SKU_H
    assert item.reason == "DORMENTE"
    assert item.days_since_last_purchase == 200


def test_c07_customer_without_recent_purchases():
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(CUSTOMER, SKU_A, 400)])

    result = recommend_for_customer(view, CUSTOMER)

    assert list(result.items) == []
    assert result.empty_reason == "SEM_COMPRAS_RECENTES"


def test_c08_customer_without_history_raises_xsl002():
    view = make_view([make_rule(SKU_A, SKU_G, 2.0, 0.2)], [(OTHER_CUSTOMER, SKU_A, 5)])

    with pytest.raises(CustomerWithoutHistoryError) as exc_info:
        recommend_for_customer(view, CUSTOMER)
    assert exc_info.value.code == "XSL-002"
    assert str(CUSTOMER) not in exc_info.value.message
