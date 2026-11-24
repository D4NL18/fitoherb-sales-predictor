"""T-7.1.4: cascata, corte, residuo, migracao por fornecedor e lancamento. P-157..P-171."""
import random

import pytest

from tests.trend_insights.helpers import mod

ORDER = ["SAZONALIDADE", "PRECO", "PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR",
         "CANIBALIZACAO_OUTRO_FORNECEDOR", "CLIENTES_PERDIDOS"]


def _raw(tipo, valor, conf="MEDIA", status="AVALIADO"):
    return mod("domain.evidence").RawParcel(tipo=tipo, valor=valor, confianca=conf, status=status)


def _run(delta, base, raws, modo="QUANTITATIVO"):
    return mod("domain.decomposition").finalize_cascade(
        delta_observado=delta, base_ajustada=base, parcels=raws, modo=modo)


def _by(res, tipo):
    return next(p for p in res.parcels if p.tipo == tipo)


def _assert_consistent(res, delta):
    total = sum(p.valor or 0.0 for p in res.parcels) + res.residuo
    assert total == pytest.approx(delta, abs=0.01)


def test_cascade_has_six_parcels_in_priority_order():
    res = _run(-300.0, 1000.0, [_raw("PRECO", -50.0), _raw("SAZONALIDADE", -100.0)])
    assert [p.tipo for p in res.parcels] == ORDER


def test_no_cut_residual_and_coverage():
    res = _run(-300.0, 1000.0, [_raw("SAZONALIDADE", -100.0), _raw("PRECO", -50.0),
                                _raw("CANIBALIZACAO_OUTRO_FORNECEDOR", -80.0)])
    assert res.residuo == pytest.approx(-70.0)
    assert res.cobertura_explicacao_pct == pytest.approx(76.67, abs=0.01)
    assert not any(p.cortada for p in res.parcels)
    _assert_consistent(res, -300.0)


def test_cut_reduces_first_parcel_that_exceeds_and_zeroes_the_rest():
    res = _run(-100.0, 1000.0, [_raw("SAZONALIDADE", -60.0), _raw("PRECO", -70.0),
                                _raw("CANIBALIZACAO_MESMO_FORNECEDOR", -50.0)])
    assert _by(res, "SAZONALIDADE").valor == pytest.approx(-60.0)
    assert _by(res, "PRECO").valor == pytest.approx(-40.0) and _by(res, "PRECO").cortada
    canib = _by(res, "CANIBALIZACAO_MESMO_FORNECEDOR")
    assert canib.valor == pytest.approx(0.0) and canib.cortada
    assert res.residuo == pytest.approx(0.0)


def test_compensatory_parcel_enters_whole_and_enlarges_budget():
    res = _run(-100.0, 1000.0, [_raw("SAZONALIDADE", 30.0), _raw("PRECO", -90.0), _raw("CLIENTES_PERDIDOS", -60.0)])
    assert _by(res, "SAZONALIDADE").valor == pytest.approx(30.0)
    assert _by(res, "SAZONALIDADE").explicativa is False
    assert _by(res, "CLIENTES_PERDIDOS").valor == pytest.approx(-40.0)
    _assert_consistent(res, -100.0)


def test_rise_mirrors_the_logic():
    res = _run(200.0, 1000.0, [_raw("SAZONALIDADE", 100.0), _raw("PRECO", -40.0),
                               _raw("CANIBALIZACAO_MESMO_FORNECEDOR", 150.0)])
    assert _by(res, "CANIBALIZACAO_MESMO_FORNECEDOR").valor == pytest.approx(140.0)
    assert res.residuo == pytest.approx(0.0)


def test_per_parcel_cap_is_base_ratio():
    res = _run(-3000.0, 1000.0, [_raw("SAZONALIDADE", -5000.0)])
    assert _by(res, "SAZONALIDADE").valor == pytest.approx(-1000.0)


def test_not_evaluated_and_no_effect_parcels_have_no_value():
    res = _run(-300.0, 1000.0, [_raw("PRECO", None, status="NAO_AVALIADO"), _raw("SAZONALIDADE", None, status="SEM_EFEITO")])
    assert _by(res, "PRECO").valor is None and _by(res, "SAZONALIDADE").valor is None
    assert res.residuo == pytest.approx(-300.0)


def test_residual_never_has_opposite_sign_and_sum_is_exact_random():
    rnd = random.Random(7)
    for _ in range(300):
        delta = rnd.choice([-1, 1]) * rnd.uniform(50, 2000)
        base = rnd.uniform(500, 5000)
        raws = [_raw(t, rnd.uniform(-1500, 1500)) for t in ORDER if rnd.random() < 0.8]
        res = _run(delta, base, raws)
        assert res.residuo * delta >= -1e-6
        _assert_consistent(res, delta)


def test_qualitative_mode_has_no_values_cut_or_residual():
    res = _run(None, None, [_raw("SAZONALIDADE", None)], modo="QUALITATIVO")
    assert all(p.valor is None and not p.cortada for p in res.parcels)
    assert res.residuo is None


# --- Migracao: lancamento x canibalizacao, mesmo x outro fornecedor, confianca por netClients
def _pair(sku, same, rev, clients, score=0.7):
    return mod("domain.evidence").MigrationPair(sku=sku, same_supplier=same, net_rev=rev, net_clients=clients, affinity_score=score)


def test_migration_parcels_split_by_supplier_and_launch_has_priority():
    fn = mod("domain.decomposition").build_migration_parcels
    pairs = [_pair(1, True, 500.0, 12), _pair(2, False, 300.0, 4), _pair(3, False, 200.0, 2)]
    out = fn(pairs=pairs, launch_skus={3}, direction="QUEDA")
    assert out["CANIBALIZACAO_MESMO_FORNECEDOR"].valor == pytest.approx(-500.0)
    assert out["CANIBALIZACAO_MESMO_FORNECEDOR"].confianca == "ALTA"
    assert out["CANIBALIZACAO_OUTRO_FORNECEDOR"].valor == pytest.approx(-300.0)
    assert out["CANIBALIZACAO_OUTRO_FORNECEDOR"].confianca == "MEDIA"
    assert out["PRODUTO_NOVO"].valor == pytest.approx(-200.0)
    assert out["PRODUTO_NOVO"].confianca == "BAIXA"
    skus = [i.sku for p in out.values() for i in p.itens]
    assert sorted(skus) == [1, 2, 3]  # cada B em uma unica parcela


def test_launch_without_pair_generates_no_value():
    out = mod("domain.decomposition").build_migration_parcels(pairs=[], launch_skus={9}, direction="QUEDA")
    assert out["PRODUTO_NOVO"].valor in (None, 0.0) and out["PRODUTO_NOVO"].status != "AVALIADO"


def test_rise_uses_received_migration_with_positive_sign():
    out = mod("domain.decomposition").build_migration_parcels(
        pairs=[_pair(1, True, 400.0, 5)], launch_skus=set(), direction="ALTA")
    assert out["CANIBALIZACAO_MESMO_FORNECEDOR"].valor == pytest.approx(400.0)
    assert out["PRODUTO_NOVO"].status == "SEM_EFEITO"
    assert out["CLIENTES_PERDIDOS"].status == "SEM_EFEITO"


@pytest.mark.parametrize("clients,expected", [(10, "ALTA"), (9, "MEDIA"), (3, "MEDIA"), (2, "BAIXA"), (1, "BAIXA")])
def test_confidence_by_net_clients(clients, expected):
    assert mod("domain.decomposition").migration_confidence(net_clients=clients) == expected


def test_quantity_conversion_uses_average_price_of_both_windows():
    fn = mod("domain.decomposition").convert_revenue_to_quantity
    # p = (R_pre*k + R_cur) / (Q_pre*k + Q_cur) = (1000*1 + 500)/(100 + 50) = 10
    assert fn(revenue=-300.0, rev_pre=1000.0, rev_cur=500.0, qty_pre=100.0, qty_cur=50.0, k=1.0) == pytest.approx(-30.0)
    assert fn(revenue=-300.0, rev_pre=0.0, rev_cur=0.0, qty_pre=0.0, qty_cur=0.0, k=1.0) is None


def test_lost_customers_and_residual_indicator_for_share_loss_without_migration():
    fn = mod("domain.decomposition").share_loss_without_migration
    # semMigracao = efeitoParticipacao - (lanc + canib) ; >= 20% de |delta| e mesmo sinal
    ind = fn(efeito_participacao=-200.0, migration_total=-50.0, delta_observado=-300.0, residuo=-120.0)
    assert ind is not None and ind.valor == pytest.approx(-120.0)  # min(|-150|, |-120|)
    assert fn(efeito_participacao=-200.0, migration_total=-180.0, delta_observado=-300.0, residuo=-20.0) is None
