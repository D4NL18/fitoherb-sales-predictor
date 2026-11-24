"""T-7.1.6: anonimizacao por UF e contagens pequenas. P-167, LGPD-TIA-05, LGPD-TIA-06."""
import dataclasses

import pytest

from tests.trend_insights.helpers import mod


def _rows(*items):
    row = mod("domain.privacy").RegionRow
    return [row(uf=u, pre_rev=pre, cur_rev=cur, clients=c) for u, pre, cur, c in items]


def _group(rows, k=1):
    return mod("domain.privacy").group_regions(rows, k=k)


def test_small_count_format():
    fmt = mod("domain.privacy").format_small_count
    assert [fmt(0), fmt(1), fmt(2)] == ["<3", "<3", "<3"]
    assert fmt(3) == 3 and fmt(40) == 40


def test_small_ufs_go_to_outras_when_outras_has_three_clients():
    res = _group(_rows(("SP", 100, 50, 10), ("RJ", 80, 60, 5), ("MG", 20, 10, 2), ("ES", 10, 5, 1)))
    ufs = {g.uf: g for g in res.groups}
    assert set(ufs) == {"SP", "RJ", "OUTRAS"}
    assert ufs["OUTRAS"].delta == pytest.approx((10 - 20) + (5 - 10))


def test_outras_below_floor_absorbs_smallest_displayed_uf():
    res = _group(_rows(("SP", 100, 50, 10), ("RJ", 80, 60, 5), ("MG", 20, 10, 2)))
    assert {g.uf for g in res.groups} == {"SP", "OUTRAS"}
    outras = next(g for g in res.groups if g.uf == "OUTRAS")
    assert outras.delta == pytest.approx((60 - 80) + (10 - 20))


def test_impossible_anonymization_is_not_evaluated():
    res = _group(_rows(("SP", 10, 5, 1), ("RJ", 10, 5, 1)))
    assert res.status == "NAO_AVALIADO" and res.motivo == "ANONIMIZACAO" and not res.groups


def test_groups_never_expose_client_counts():
    res = _group(_rows(("SP", 100, 50, 10), ("RJ", 80, 60, 5), ("MG", 20, 10, 3)))
    for g in res.groups:
        assert not any("client" in f.name for f in dataclasses.fields(g))


def test_previous_scaled_by_k():
    res = _group(_rows(("SP", 300, 100, 10), ("RJ", 90, 90, 10)), k=1 / 3)
    sp = next(g for g in res.groups if g.uf == "SP")
    assert sp.delta == pytest.approx(100 - 100.0)


def test_regional_indicator_needs_60_percent_and_never_names_outras():
    detect = mod("domain.privacy").detect_regional
    res = _group(_rows(("SP", 1000, 400, 10), ("RJ", 100, 90, 10), ("MG", 100, 100, 10)))
    ind = detect(res, delta_observado=-610.0)
    assert ind.status == "AVALIADO" and ind.uf_concentradora == "SP"
    spread = _group(_rows(("SP", 100, 60, 10), ("RJ", 100, 60, 10)))
    assert detect(spread, delta_observado=-80.0).status == "SEM_EFEITO"
    outras_big = _group(_rows(("SP", 100, 100, 10), ("MG", 500, 100, 2), ("ES", 500, 100, 2)))
    ind2 = detect(outras_big, delta_observado=-800.0)
    assert ind2.uf_concentradora != "OUTRAS"
