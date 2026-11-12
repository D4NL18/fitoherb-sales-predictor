"""
T-16 — Backtest temporal de hit rate@5 (P-071, CA-23, CA-24, LGPD-11).

Domínio puro, massa sintética com resposta conhecida (ver `build_backtest_mass`).

Interface esperada (B-16, `src/modules/analytics/domain/cross_sell_backtest.py`):
- `split_train_and_eval(order_baskets, month) -> (train, evaluation)`; `month` no formato `"YYYY-MM"`;
  treino = `order_day` < 1º dia de N; avaliação = pedidos dentro de N
- `evaluate_month(order_baskets, catalog_df, month) -> BacktestMonthResult`
- `BacktestMonthResult` (dataclass) com `month`, `model_hit_rate`, `popularity_hit_rate`,
  `evaluated_customers` e `excluded_by_reason` (`{"SEM_PERFIL", "SEM_COMPRA_NO_MES", "SEM_RECOMENDACAO"}`)
- `summarize(results)` -> objeto com `model_hit_rate` e `popularity_hit_rate` médios
Precedência dos motivos de exclusão (decisão do Tester, P-071.3): sem perfil > sem compra em N >
sem recomendação. População = todo cliente com pedido de VENDA até o fim de N.
"""
import dataclasses

import pytest

from src.modules.analytics.domain.cross_sell import build_valid_baskets, mine_one_to_one_rules, select_useful_rules
from src.modules.analytics.domain.cross_sell_backtest import (
    BacktestMonthResult,
    evaluate_month,
    split_train_and_eval,
    summarize,
)
from tests.analytics.fixtures.synthetic_data import (
    BACKTEST_CUSTOMERS,
    BACKTEST_CUT_DAY,
    BACKTEST_MONTH,
    BACKTEST_NEXT_MONTH_DAY,
    SKU_CHA_VERDE,
    SKU_HIBISCO,
    SKU_LEAK_A,
    SKU_LEAK_B,
    build_backtest_mass,
)


@pytest.fixture(scope="module")
def backtest_mass():
    return build_backtest_mass()


@pytest.fixture(scope="module")
def month_result(backtest_mass):
    order_baskets, catalog = backtest_mass
    return evaluate_month(order_baskets, catalog, BACKTEST_MONTH)


# ------------------------------------------------------------------ CA-23 sem vazamento

def test_split_respects_month_boundaries(backtest_mass):
    order_baskets, _ = backtest_mass

    train, evaluation = split_train_and_eval(order_baskets, BACKTEST_MONTH)

    assert train["order_day"].max() < BACKTEST_CUT_DAY
    assert evaluation["order_day"].min() >= BACKTEST_CUT_DAY
    assert evaluation["order_day"].max() < BACKTEST_NEXT_MONTH_DAY
    assert len(train) + len(evaluation) < len(order_baskets), "pedidos de novembro ficam fora do treino e de N"


def test_ca23_pair_only_in_month_n_is_not_a_training_rule():
    order_baskets, _ = build_backtest_mass(with_leak_pair=True)

    train, evaluation = split_train_and_eval(order_baskets, BACKTEST_MONTH)
    valid = build_valid_baskets(train)
    useful = select_useful_rules(mine_one_to_one_rules(valid), int(valid["Pedido"].nunique()))
    pairs = {(r.antecedent, r.consequent) for r in useful}

    assert SKU_LEAK_A in set(evaluation["sku"])
    assert (SKU_LEAK_A, SKU_LEAK_B) not in pairs
    assert (SKU_LEAK_B, SKU_LEAK_A) not in pairs
    assert (SKU_CHA_VERDE, SKU_HIBISCO) in pairs


def test_ca23_leak_pair_does_not_change_month_result():
    """Se o par do mês N vazasse para o treino, as recomendações mudariam; o resultado deve ser idêntico."""
    clean = evaluate_month(*build_backtest_mass(), BACKTEST_MONTH)
    with_leak = evaluate_month(*build_backtest_mass(with_leak_pair=True), BACKTEST_MONTH)

    assert with_leak.model_hit_rate == clean.model_hit_rate
    assert with_leak.popularity_hit_rate == clean.popularity_hit_rate
    assert with_leak.evaluated_customers == clean.evaluated_customers


# ------------------------------------------------------------------ CA-24 resposta conhecida

def test_ca24_model_hit_rate_is_exact(month_result):
    """Modelo recomenda só B (estoque 0 não filtra, P-071.5): acertam HIT_1 e HIT_2 de 4 avaliados."""
    assert month_result.evaluated_customers == 4
    assert month_result.model_hit_rate == pytest.approx(0.5)


def test_ca24_popularity_hit_rate_is_exact(month_result):
    """
    Popularidade = 5 SKUs com mais cestas no treino, fora do catálogo e com margem <= 0 excluídos e sem os
    comprados pelo cliente nos últimos 90 dias: acertam HIT_1, HIT_2 e POP_ONLY; RECENT_G não (G excluído).
    """
    assert month_result.popularity_hit_rate == pytest.approx(0.75)


def test_p071_3_excluded_customers_counted_by_reason(month_result):
    assert dict(month_result.excluded_by_reason) == {
        "SEM_PERFIL": 2,
        "SEM_COMPRA_NO_MES": 1,
        "SEM_RECOMENDACAO": 1,
    }


def test_month_is_reported(month_result):
    assert str(month_result.month) == BACKTEST_MONTH


def test_summarize_averages_months(month_result):
    other = dataclasses.replace(month_result, month="2026-09", model_hit_rate=0.25, popularity_hit_rate=0.5)

    summary = summarize([month_result, other])

    assert summary.model_hit_rate == pytest.approx((0.5 + 0.25) / 2)
    assert summary.popularity_hit_rate == pytest.approx((0.75 + 0.5) / 2)


def test_month_without_evaluated_customers_does_not_divide_by_zero(backtest_mass):
    order_baskets, catalog = backtest_mass

    result = evaluate_month(order_baskets, catalog, "2026-07")

    assert result.evaluated_customers == 0
    assert result.model_hit_rate == 0.0
    assert result.popularity_hit_rate == 0.0


# ------------------------------------------------------------------ LGPD-11 só agregados

def test_lgpd11_result_has_no_customer_codes(month_result):
    assert isinstance(month_result, BacktestMonthResult)
    rendered = repr(dataclasses.asdict(month_result)) + repr(month_result)
    for code in BACKTEST_CUSTOMERS:
        assert str(code) not in rendered
    for value in dataclasses.asdict(month_result).values():
        assert not isinstance(value, (list, tuple, set, frozenset)), "nada de listas por cliente no resultado"
