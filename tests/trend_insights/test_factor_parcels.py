"""D-7.1.16 / T-7.1.4: formulas puras de sazonalidade, preco, clientes perdidos, ruptura e promocao (P-158..P-166)."""
from datetime import date

import pytest

from tests.trend_insights.helpers import mod


def fp():
    return mod("domain.factor_parcels")


def _monthly(**overrides):
    base = {m: (1.0, "ALTA") for m in range(1, 13)}
    base.update(overrides)
    return base


def _seasonality(monthly, eligible=True, strength="FORTE", reason=None):
    return fp().SeasonalityEvidence(eligible=eligible, strength=strength, reason=reason, monthly=monthly)


def test_month_day_weights_counts_days_per_calendar_month():
    assert fp().month_day_weights(date(2026, 1, 30), date(2026, 2, 2)) == {1: 2, 2: 1}


def test_seasonal_parcel_uses_weighted_index_ratio():
    monthly = _monthly() | {10: (1.2, "ALTA"), 7: (0.8, "MEDIA")}
    parcel = fp().build_seasonal_parcel(_seasonality(monthly), 1000.0, {10: 31}, {7: 31})
    assert parcel.status == "AVALIADO" and parcel.valor == pytest.approx(500.0)
    assert parcel.confianca == "MEDIA" and parcel.detalhe["forca"] == "FORTE"


@pytest.mark.parametrize("eligible,strength,reason,expected", [
    (False, "INSUFICIENTE", "HISTORICO_CURTO", "HISTORICO_CURTO"),
    (False, "INSUFICIENTE", "VENDA_ESPORADICA", "VENDA_ESPORADICA"),
    (True, "FRACA", None, "FRACA"),
])
def test_seasonal_not_eligible_is_no_effect(eligible, strength, reason, expected):
    parcel = fp().build_seasonal_parcel(_seasonality(_monthly(), eligible, strength, reason), 100.0, {10: 31}, {7: 31})
    assert (parcel.status, parcel.valor, parcel.motivo) == ("SEM_EFEITO", None, expected)


def test_seasonal_same_months_is_neutral():
    parcel = fp().build_seasonal_parcel(_seasonality(_monthly()), 100.0, {10: 31}, {10: 31})
    assert (parcel.status, parcel.motivo) == ("SEM_EFEITO", "MESMOS_MESES")


def test_seasonal_low_confidence_month_is_not_evaluated():
    monthly = _monthly() | {10: (1.3, "BAIXA")}
    parcel = fp().build_seasonal_parcel(_seasonality(monthly), 100.0, {10: 31}, {7: 31})
    assert (parcel.status, parcel.motivo) == ("NAO_AVALIADO", "CONFIANCA_BAIXA_SAZONAL")


def test_seasonal_missing_month_is_unavailable():
    parcel = fp().build_seasonal_parcel(_seasonality({7: (1.0, "ALTA")}), 100.0, {10: 31}, {7: 31})
    assert (parcel.status, parcel.motivo) == ("NAO_AVALIADO", "FONTE_INDISPONIVEL")


def _price(**over):
    base = dict(metric="quantity", qty_pre=100.0, rev_pre=15000.0, qty_cur=90.0, rev_cur=14400.0, scale_k=1.0,
                elasticity=-1.3, is_reliable=True, is_fallback=False, confidence_level="ALTA")
    base.update(over)
    return fp().PriceEvidence(**base)


def test_price_quantity_formula_and_detail():
    parcel = fp().build_price_parcel(_price())  # 150 -> 160: dp = +6.667%
    variation = (160 - 150) / 150
    assert parcel.valor == pytest.approx(100 * (max(0, 1 - 1.3 * variation) - 1))
    assert parcel.confianca == "ALTA" and parcel.detalhe["variacao_valor_pct"] == pytest.approx(6.7)
    assert parcel.detalhe["observacoes"] == []


def test_price_revenue_formula_counts_price_twice():
    parcel = fp().build_price_parcel(_price(metric="revenue"))
    variation = 10 / 150
    assert parcel.valor == pytest.approx(15000 * ((1 + variation) * (1 - 1.3 * variation) - 1))


def test_price_small_change_is_no_effect():
    parcel = fp().build_price_parcel(_price(qty_cur=100.0, rev_cur=15100.0))
    assert (parcel.status, parcel.motivo) == ("SEM_EFEITO", "VARIACAO_PRECO_PEQUENA")


def test_price_without_quantity_is_not_evaluated():
    parcel = fp().build_price_parcel(_price(qty_cur=0.0))
    assert (parcel.status, parcel.motivo) == ("NAO_AVALIADO", "SEM_PRECO_MEDIO")


def test_price_truncates_variation_and_flags_fallback_and_promotion():
    parcel = fp().build_price_parcel(_price(rev_cur=90 * 600.0, is_fallback=True, is_promotion_involved=True))
    assert parcel.valor == pytest.approx(100 * (max(0, 1 - 1.3 * 1.0) - 1))  # dp truncado em +100%
    assert parcel.confianca == "BAIXA" and parcel.detalhe["observacoes"] == ["PRECO_INFLUENCIADO_POR_PROMOCAO"]


def test_lost_customers_parcel_by_metric_and_confidence():
    aggregate = mod("domain.migration_scaling").LostCustomersAggregate(count=4, revenue=800.0, quantity=20.0)
    revenue = fp().build_lost_customers_parcel(aggregate, "revenue")
    quantity = fp().build_lost_customers_parcel(aggregate, "quantity")
    assert (revenue.valor, quantity.valor, revenue.confianca) == (-800.0, -20.0, "MEDIA")
    few = mod("domain.migration_scaling").LostCustomersAggregate(count=2, revenue=1.0, quantity=1.0)
    assert fp().build_lost_customers_parcel(few, "revenue").confianca == "BAIXA"


def test_lost_customers_absent_is_no_effect():
    parcel = fp().build_lost_customers_parcel(None, "revenue")
    assert (parcel.status, parcel.motivo) == ("SEM_EFEITO", "SEM_CLIENTES_PERDIDOS")


def test_stockout_indicator():
    assert fp().build_stockout_indicator(5, False)["motivo_sem_efeito"] == "SEM_RUPTURA"
    found = fp().build_stockout_indicator(0, True)
    assert found["status"] == "AVALIADO" and found["valor"] is None and found["confianca"] == "BAIXA"
    assert found["evidencia"]["estoque_atual"] == 0 and found["evidencia"]["observacao"]
    assert fp().build_stockout_indicator(-2, False)["evidencia"]["observacao"] is None


def test_promotion_indicator_directions():
    build = fp().build_promotion_indicator
    assert build(True, False, frozenset(), frozenset())["sentido"] == "NEGATIVO"
    assert build(False, True, frozenset(), frozenset())["sentido"] == "POSITIVO"
    only_affines = build(False, False, frozenset({1}), frozenset({1, 2}))
    assert only_affines["evidencia"]["afins_em_promocao_so_na_atual"] == [2]
    assert build(True, True, frozenset(), frozenset())["motivo_sem_efeito"] == "SEM_PROMOCAO"


@pytest.mark.parametrize("base,reference,expected", [(10, 10, True), (9, 10, True), (8, 10, False), (11, 10, False)])
def test_recent_base_month(base, reference, expected):
    assert fp().is_recent_base_month(base, reference, 1) is expected
