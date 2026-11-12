"""
T-07 — Cestas Válidas, mineração 1 -> 1, Regra Útil e Item Trivial (P-058.3, P-059, P-060, P-067).

Domínio puro com DataFrames sintéticos, sem banco.

Interface esperada (B-10, `src/modules/analytics/domain/cross_sell.py`):
- constantes da tabela de P-058..P-071
- `UsefulRule` frozen dataclass: `antecedent, consequent, support, confidence, lift, pair_orders, antecedent_orders`
- `build_valid_baskets(order_baskets) -> DataFrame` com `Pedido`, `Cod Produto`, `Qtd Venda` (`int8`),
  já sem cestas de 1 item (reusa `filter_orphan_baskets`)
- `mine_one_to_one_rules(valid_baskets) -> DataFrame` (mesmo formato do mlxtend, por contagem direta de pares
  (DA-04 revisada))
- `select_useful_rules(rules, total_baskets) -> Sequence[UsefulRule]`
- `find_trivial_skus(valid_baskets) -> Set[int]`
- `index_rules_by_antecedent(useful_rules) -> Dict[int, Tuple[UsefulRule, ...]]` (ordem P-061.1)
- `assert_base_is_sufficient(valid_basket_count, useful_rule_count)` -> `InsufficientBaseError` (XSL-003)
"""
import dataclasses

import numpy as np
import pytest

from src.modules.analytics.domain import cross_sell
from src.modules.analytics.domain.cross_sell import (
    UsefulRule,
    assert_base_is_sufficient,
    build_valid_baskets,
    count_valid_baskets,
    find_trivial_skus,
    index_rules_by_antecedent,
    mine_one_to_one_rules,
    select_useful_rules,
)
from src.modules.analytics.domain.exceptions import InsufficientBaseError
from src.modules.pricing.domain.basket_mining import build_basket_matrix, mine_association_rules
from tests.analytics.fixtures.synthetic_data import (
    SKU_CHA_VERDE,
    SKU_FORA_CATALOGO,
    SKU_HIBISCO,
    SKU_OLEO_COCO_200,
    BasketBuilder,
    build_product_contract_mass,
    rules_frame,
)

N_EXAMPLE = 10_000  # base do exemplo numérico de P-060
SKU_A, SKU_B, SKU_C, SKU_D, SKU_E, SKU_F = 1, 2, 3, 4, 5, 6


def mine_useful_rules(order_baskets):
    """Pipeline B-10 completo: cestas válidas -> mineração 1 -> 1 -> Regras Úteis."""
    valid = build_valid_baskets(order_baskets)
    total_baskets = int(valid["Pedido"].nunique())
    rules = mine_one_to_one_rules(valid)
    return valid, rules, select_useful_rules(rules, total_baskets)


def make_rule(antecedent, consequent, confidence, lift, pair_orders, antecedent_orders=500):
    return UsefulRule(antecedent=antecedent, consequent=consequent, support=pair_orders / N_EXAMPLE,
                      confidence=confidence, lift=lift, pair_orders=pair_orders, antecedent_orders=antecedent_orders)


def find_rule(useful_rules, antecedent, consequent):
    matches = [r for r in useful_rules if r.antecedent == antecedent and r.consequent == consequent]
    assert len(matches) <= 1
    return matches[0] if matches else None


def rule_row(antecedents, consequents, pair, antecedent, consequent, total=N_EXAMPLE):
    """Linha no formato mlxtend calculada a partir de contagens absolutas."""
    support = pair / total
    confidence = pair / antecedent
    return {
        "antecedents": frozenset(antecedents),
        "consequents": frozenset(consequents),
        "antecedent support": antecedent / total,
        "consequent support": consequent / total,
        "support": support,
        "confidence": confidence,
        "lift": confidence / (consequent / total),
    }


@pytest.fixture(scope="module")
def product_mass_rules():
    order_baskets, _ = build_product_contract_mass()
    return mine_useful_rules(order_baskets)


# ------------------------------------------------------------------ constantes (seção 2 das regras)

def test_business_constants():
    assert cross_sell.SALE_OPERATION == "VENDA"
    assert cross_sell.MIN_SKUS_PER_BASKET == 2
    assert cross_sell.MIN_SUPPORT == pytest.approx(0.002)
    assert cross_sell.MIN_PAIR_ORDERS == 10
    assert cross_sell.MIN_LIFT == pytest.approx(1.2)
    assert cross_sell.MIN_CONFIDENCE == pytest.approx(0.10)
    assert cross_sell.TRIVIAL_ITEM_SUPPORT == pytest.approx(0.15)
    assert cross_sell.CUSTOMER_PROFILE_DAYS == 365
    assert cross_sell.DORMANT_DAYS == 90
    assert cross_sell.COST_FALLBACK_RATIO == pytest.approx(0.60)
    assert cross_sell.MIN_VALID_BASKETS == 1000
    assert cross_sell.HIT_RATE_K == 5


def test_useful_rule_is_frozen():
    rule = UsefulRule(antecedent=1, consequent=2, support=0.017, confidence=0.34, lift=4.25, pair_orders=170,
                      antecedent_orders=500)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rule.lift = 1.0  # type: ignore[misc]


# ------------------------------------------------------------------ CA-03 cestas de 1 item

def test_ca03_single_item_orders_are_discarded():
    builder = BasketBuilder()
    multi = builder.add_order([SKU_A, SKU_B])
    single = builder.add_order([SKU_A])
    triple = builder.add_order([SKU_C, SKU_D, SKU_E])

    valid = build_valid_baskets(builder.to_frame())

    assert set(valid["Pedido"].unique()) == {multi, triple}
    assert single not in set(valid["Pedido"])
    assert set(valid["Cod Produto"].unique()) == {SKU_A, SKU_B, SKU_C, SKU_D, SKU_E}
    assert valid["Qtd Venda"].dtype == np.int8
    assert (valid["Qtd Venda"] == 1).all()


# ------------------------------------------------------------------ CA-01 associação plantada

def test_ca01_planted_association_is_recovered(product_mass_rules):
    _, _, useful = product_mass_rules
    rule = find_rule(useful, SKU_CHA_VERDE, SKU_HIBISCO)

    assert rule is not None
    assert rule.confidence == pytest.approx(0.34)
    assert rule.lift == pytest.approx(4.25)
    assert rule.support == pytest.approx(0.017)
    assert rule.pair_orders == 170
    assert rule.antecedent_orders == 500
    assert isinstance(rule.pair_orders, int) and isinstance(rule.antecedent_orders, int)


def test_lift_exactly_at_minimum_survives_real_mining(product_mass_rules):
    """P-060.1 com aritmética real: A -> F tem lift 0,12 / 0,10 = 1,2 exato e deve ser aceito."""
    _, _, useful = product_mass_rules
    rule = find_rule(useful, SKU_CHA_VERDE, SKU_OLEO_COCO_200)

    assert rule is not None
    assert rule.lift == pytest.approx(1.2)
    assert rule.confidence == pytest.approx(0.12)
    assert rule.pair_orders == 60


def test_confidence_exactly_at_minimum_survives_real_mining(product_mass_rules):
    """P-060.1: A -> X tem confiança 50/500 = 0,10 exata (lift 3,33) e deve ser aceita."""
    _, _, useful = product_mass_rules
    rule = find_rule(useful, SKU_CHA_VERDE, SKU_FORA_CATALOGO)

    assert rule is not None
    assert rule.confidence == pytest.approx(0.10)


def test_mined_rules_are_only_one_to_one(product_mass_rules):
    _, rules, useful = product_mass_rules

    assert all(len(itemset) == 1 for itemset in rules["antecedents"])
    assert all(len(itemset) == 1 for itemset in rules["consequents"])
    assert all(isinstance(r.antecedent, int) and isinstance(r.consequent, int) for r in useful)


# ------------------------------------------------------------------ CA-04 limites de Regra Útil

def test_ca04_only_r1_and_r5_survive():
    rules = rules_frame([
        rule_row([SKU_A], [SKU_B], pair=170, antecedent=500, consequent=800),    # R1 útil
        rule_row([SKU_A], [SKU_C], pair=200, antecedent=500, consequent=3000),   # R2 trivial (30%)
        rule_row([SKU_A], [SKU_D], pair=30, antecedent=500, consequent=400),     # R3 confiança 0,06
        rule_row([SKU_A], [SKU_E], pair=110, antecedent=500, consequent=2000),   # R4 lift 1,1
        {**rule_row([SKU_A], [SKU_F], pair=60, antecedent=500, consequent=1000), "lift": 1.2},  # R5 limite
    ])

    useful = select_useful_rules(rules, N_EXAMPLE)

    assert sorted((r.antecedent, r.consequent) for r in useful) == [(SKU_A, SKU_B), (SKU_A, SKU_F)]
    r1 = find_rule(useful, SKU_A, SKU_B)
    assert r1.pair_orders == 170
    assert r1.antecedent_orders == 500


def test_confidence_limit_is_inclusive():
    rules = rules_frame([{**rule_row([SKU_A], [SKU_B], pair=50, antecedent=500, consequent=300), "confidence": 0.10}])
    assert len(select_useful_rules(rules, N_EXAMPLE)) == 1


def test_just_below_limits_is_rejected():
    rules = rules_frame([
        {**rule_row([SKU_A], [SKU_B], pair=50, antecedent=500, consequent=300), "confidence": 0.0999},
        {**rule_row([SKU_A], [SKU_C], pair=60, antecedent=500, consequent=1000), "lift": 1.199},
    ])
    assert list(select_useful_rules(rules, N_EXAMPLE)) == []


def test_p059_6_self_rule_and_multi_item_rules_are_never_valid():
    rules = rules_frame([
        rule_row([SKU_A], [SKU_A], pair=170, antecedent=500, consequent=800),
        rule_row([SKU_A, SKU_B], [SKU_C], pair=100, antecedent=200, consequent=800),
        rule_row([SKU_A], [SKU_B, SKU_C], pair=100, antecedent=500, consequent=300),
    ])
    assert list(select_useful_rules(rules, N_EXAMPLE)) == []


# ------------------------------------------------------------------ CA-05 Item Trivial

@pytest.fixture(scope="module")
def trivial_mass():
    """2.000 cestas: C em 30% (trivial); A -> C forte mas trivial; C -> D útil (C pode ser antecedente)."""
    builder = BasketBuilder(seed=5)
    builder.add_orders(100, [SKU_A, SKU_C])
    builder.add_orders(90, [SKU_C, SKU_D])
    builder.add_with_filler(410, [SKU_C])
    builder.add_with_filler(100, [SKU_A])
    builder.add_with_filler(10, [SKU_D])
    builder.add_filler_only(2000 - (600 + 100 + 10))
    return mine_useful_rules(builder.to_frame())


def test_ca05_trivial_item_is_never_consequent(trivial_mass):
    valid, rules, useful = trivial_mass

    itemset_pairs = zip(rules["antecedents"], rules["consequents"], strict=True)
    mined_pairs = {(next(iter(a)), next(iter(c))) for a, c in itemset_pairs}
    assert (SKU_A, SKU_C) in mined_pairs, "a regra existe na mineração; quem a remove é o filtro de Par Trivial"
    assert all(r.consequent != SKU_C for r in useful)
    assert SKU_C in find_trivial_skus(valid)


def test_ca05_trivial_item_can_be_antecedent(trivial_mass):
    _, _, useful = trivial_mass
    rule = find_rule(useful, SKU_C, SKU_D)

    assert rule is not None
    assert rule.confidence == pytest.approx(0.15)
    assert rule.pair_orders == 90


def test_trivial_threshold_is_strictly_greater_than_15_percent():
    builder = BasketBuilder(seed=9)
    builder.add_with_filler(300, [SKU_E])  # 300 / 2.000 = 15% exatos: não é trivial
    builder.add_with_filler(301, [SKU_F])  # 15,05%: trivial
    builder.add_filler_only(2000 - 601)

    trivial = find_trivial_skus(build_valid_baskets(builder.to_frame()))

    assert SKU_F in trivial
    assert SKU_E not in trivial


# ------------------------------------------------------------------ CA-06 mínimo de pedidos em comum

def test_ca06_min_pair_orders():
    builder = BasketBuilder(seed=13)
    builder.add_orders(9, [SKU_A, SKU_B])     # 9 em comum: descartada
    builder.add_with_filler(21, [SKU_A])
    builder.add_with_filler(6, [SKU_B])
    builder.add_orders(10, [SKU_C, SKU_D])    # 10 em comum: aceita
    builder.add_with_filler(20, [SKU_C])
    builder.add_with_filler(5, [SKU_D])
    builder.add_filler_only(2000 - 71)

    _, _, useful = mine_useful_rules(builder.to_frame())

    assert find_rule(useful, SKU_A, SKU_B) is None
    assert find_rule(useful, SKU_B, SKU_A) is None
    accepted = find_rule(useful, SKU_C, SKU_D)
    assert accepted is not None
    assert accepted.pair_orders == 10
    assert accepted.antecedent_orders == 30
    assert accepted.confidence == pytest.approx(10 / 30)


# ------------------------------------------------------------------ índice por antecedente

def test_index_rules_by_antecedent_groups_and_orders():
    rules = [
        make_rule(SKU_A, 20, confidence=0.2, lift=2.0, pair_orders=100),
        make_rule(SKU_A, 10, confidence=0.3, lift=2.0, pair_orders=150),
        make_rule(SKU_A, 30, confidence=0.2, lift=3.0, pair_orders=100),
        make_rule(SKU_B, 40, confidence=0.2, lift=1.5, pair_orders=100),
    ]

    index = index_rules_by_antecedent(rules)

    assert set(index) == {SKU_A, SKU_B}
    assert [r.consequent for r in index[SKU_A]] == [30, 10, 20]
    assert isinstance(index[SKU_A], tuple)


# ------------------------------------------------------------------ XSL-003 base insuficiente

@pytest.mark.parametrize("valid_baskets, useful_rules", [(999, 10), (0, 0), (1000, 0), (50_000, 0)])
def test_insufficient_base_raises_xsl003(valid_baskets, useful_rules):
    with pytest.raises(InsufficientBaseError) as exc_info:
        assert_base_is_sufficient(valid_baskets, useful_rules)
    assert exc_info.value.code == "XSL-003"


def test_base_at_minimum_is_sufficient():
    assert_base_is_sufficient(1000, 1)


# ------------------------------------------------------------------ DA-04 revisada: contagem direta == FP-Growth
#
# `mine_one_to_one_rules` trocou o FP-Growth do mlxtend por contagem direta de pares (Xᵀ·X esparso). A troca
# só é válida se o resultado for o mesmo das regras 1 -> 1 de `mine_association_rules` (FP-Growth do mlxtend)
# (ADR-002 DA-04, revisão).

EQUIVALENCE_SKUS = tuple(range(101, 131))  # 30 SKUs, em 6 famílias de 5 que tendem a sair juntas
EQUIVALENCE_FAMILY_SIZE = 5
EQUIVALENCE_ORDERS = 600
EQUIVALENCE_FAMILY_SHARE = 0.6  # parte dos pedidos montada dentro de uma família (gera lift > 1)
EQUIVALENCE_METRICS = ["antecedent support", "consequent support", "support", "confidence", "lift"]


def build_random_mass(seed: int):
    """
    Cestas de 2 a 4 SKUs: parte sorteada dentro de uma família (associação real) e parte ao acaso
    (pares sem associação), mais pedidos de 1 item (descartados por P-058.3). Determinística por `seed`.
    """
    rng = np.random.RandomState(seed)
    skus = np.array(EQUIVALENCE_SKUS)
    families = skus.reshape(-1, EQUIVALENCE_FAMILY_SIZE)
    builder = BasketBuilder(seed=seed)
    for _ in range(EQUIVALENCE_ORDERS):
        size = int(rng.randint(2, 5))
        is_family_order = rng.rand() < EQUIVALENCE_FAMILY_SHARE
        pool = families[rng.randint(len(families))] if is_family_order else skus
        builder.add_order(rng.choice(pool, size=size, replace=False).tolist())
    builder.add_orders(5, [EQUIVALENCE_SKUS[0]])
    return builder.to_frame()


def rules_by_pair(rules):
    """Indexa a tabela de regras por (antecedente, consequente), só com as colunas comparáveis."""
    itemset_pairs = zip(rules["antecedents"], rules["consequents"], strict=True)
    keyed = rules.assign(pair=[(int(next(iter(a))), int(next(iter(c)))) for a, c in itemset_pairs])
    return keyed.set_index("pair")[EQUIVALENCE_METRICS].sort_index()


def fp_growth_rules(valid_baskets, min_support, min_confidence, min_lift):
    """FP-Growth completo do `pricing` (sem limite de tamanho), reduzido às regras 1 -> 1 (P-059.1)."""
    rules = mine_association_rules(build_basket_matrix(valid_baskets), min_support=min_support,
                                   min_confidence=min_confidence, min_lift=min_lift)
    is_one_to_one = (rules["antecedents"].map(len) == 1) & (rules["consequents"].map(len) == 1)
    return rules[is_one_to_one]


def useful_rules_signature(useful_rules):
    """Parte exata das Regras Úteis: par e contagens inteiras, em ordem canônica."""
    return sorted((r.antecedent, r.consequent, r.pair_orders, r.antecedent_orders) for r in useful_rules)


def useful_rules_metrics(useful_rules):
    """Métricas em ponto flutuante das Regras Úteis, na mesma ordem canônica de `useful_rules_signature`."""
    ordered = sorted(useful_rules, key=lambda r: (r.antecedent, r.consequent))
    return np.array([[r.support, r.confidence, r.lift] for r in ordered])


def ranked_consequents(useful_rules):
    """Ordem de negócio P-061.1 por antecedente, como o índice usado pelo modo produto."""
    return {sku: [r.consequent for r in rules] for sku, rules in index_rules_by_antecedent(useful_rules).items()}


@pytest.mark.parametrize("seed", [3, 11, 29])
def test_direct_count_matches_fp_growth_on_every_cooccurring_pair(monkeypatch, seed):
    """Sem limites (todo par com 1+ pedido em comum), a contagem direta reproduz o FP-Growth par a par."""
    valid = build_valid_baskets(build_random_mass(seed))
    total = count_valid_baskets(valid)
    monkeypatch.setattr(cross_sell, "MIN_SUPPORT", 0.0)
    monkeypatch.setattr(cross_sell, "MIN_CONFIDENCE", 0.0)
    monkeypatch.setattr(cross_sell, "MIN_LIFT", 0.0)

    direct = rules_by_pair(mine_one_to_one_rules(valid))
    reference = rules_by_pair(fp_growth_rules(valid, min_support=0.5 / total, min_confidence=0.0, min_lift=0.0))

    assert len(direct) > 50  # massa densa o bastante para o teste ser significativo
    assert list(direct.index) == list(reference.index)
    np.testing.assert_allclose(direct.to_numpy(), reference.to_numpy(), rtol=0, atol=1e-12)


@pytest.mark.parametrize("seed", [3, 11, 29])
def test_direct_count_matches_fp_growth_with_production_limits(seed):
    """Com os limites de P-059.2/P-060, o conjunto de regras e as Regras Úteis são os mesmos do FP-Growth."""
    valid = build_valid_baskets(build_random_mass(seed))
    total = count_valid_baskets(valid)

    direct_rules = mine_one_to_one_rules(valid)
    reference_rules = fp_growth_rules(valid, cross_sell.MIN_SUPPORT, cross_sell.MIN_CONFIDENCE, cross_sell.MIN_LIFT)
    direct, reference = rules_by_pair(direct_rules), rules_by_pair(reference_rules)

    # A massa não tem métrica exatamente no limite, onde só a contagem direta aplica FLOAT_TOLERANCE.
    assert not np.isclose(direct["lift"], cross_sell.MIN_LIFT).any()
    assert not np.isclose(direct["confidence"], cross_sell.MIN_CONFIDENCE).any()
    assert 0 < len(direct) < len(EQUIVALENCE_SKUS) * (len(EQUIVALENCE_SKUS) - 1)  # o filtro corta parte dos pares
    assert list(direct.index) == list(reference.index)
    np.testing.assert_allclose(direct.to_numpy(), reference.to_numpy(), rtol=0, atol=1e-12)
    # A ordem de saída de `select_useful_rules` segue a das linhas; a ordem de negócio (P-061.1) é a do índice.
    direct_useful = select_useful_rules(direct_rules, total)
    reference_useful = select_useful_rules(reference_rules, total)
    assert len(direct_useful) > 0
    # Mesmas regras e mesmas contagens inteiras; métricas iguais até o último bit de ponto flutuante
    # (o mlxtend divide suportes, a contagem direta divide contagens: diferença de 1 ULP).
    assert useful_rules_signature(direct_useful) == useful_rules_signature(reference_useful)
    np.testing.assert_allclose(useful_rules_metrics(direct_useful), useful_rules_metrics(reference_useful),
                               rtol=1e-12, atol=0)
    assert ranked_consequents(direct_useful) == ranked_consequents(reference_useful)


def test_direct_count_on_empty_base_returns_empty_rule_table():
    """Sem Cestas Válidas não há regra; a tabela vazia mantém as colunas que `select_useful_rules` espera."""
    only_single_items = BasketBuilder()
    only_single_items.add_orders(3, [SKU_A])
    valid = build_valid_baskets(only_single_items.to_frame())

    rules = mine_one_to_one_rules(valid)

    assert valid.empty and rules.empty
    assert list(rules.columns) == ["antecedents", "consequents", *EQUIVALENCE_METRICS]
    assert select_useful_rules(rules, 0) == ()


def test_direct_count_keeps_boundary_rules_that_fp_growth_loses_to_float_error(product_mass_rules):
    """
    Única diferença admitida: regras exatamente no limite inclusivo (P-060.1). O mlxtend calcula 50/500 como
    0.0999…; a contagem direta tem tolerância e mantém A -> X e A -> F. Fora isso, o conjunto é o mesmo.
    """
    valid, direct_rules, _ = product_mass_rules
    reference_rules = fp_growth_rules(valid, cross_sell.MIN_SUPPORT, cross_sell.MIN_CONFIDENCE, cross_sell.MIN_LIFT)
    direct, reference = rules_by_pair(direct_rules), rules_by_pair(reference_rules)

    assert set(reference.index) <= set(direct.index)
    only_direct = direct.loc[sorted(set(direct.index) - set(reference.index))]
    at_boundary = (np.isclose(only_direct["confidence"], cross_sell.MIN_CONFIDENCE)
                   | np.isclose(only_direct["lift"], cross_sell.MIN_LIFT))
    assert at_boundary.all()
    common = sorted(reference.index)
    np.testing.assert_allclose(direct.loc[common].to_numpy(), reference.loc[common].to_numpy(), rtol=0, atol=1e-12)
