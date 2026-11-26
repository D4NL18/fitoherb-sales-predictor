"""T-7.1.3: diagnostico mercado x concorrencia (shift-share, DOMINANT_EFFECT_RATIO) e lancamento afim. P-155, P-156, P-160."""
import pytest

from tests.trend_insights.helpers import mod

LOW_BASE = 500.0


def _diag(a_cur, g_cur, a_pre_adj=1000.0, g_pre=2000.0, low=LOW_BASE):
    return mod("domain.affinity_group").compute_market_diagnosis(
        base_adjusted=a_pre_adj, a_current=a_cur, group_previous_scaled=g_pre,
        group_current=g_cur, min_group_base=low,
    )


def test_dominant_effect_ratio_constant():
    assert mod("domain.constants").DOMINANT_EFFECT_RATIO == 0.70


def test_pure_market_drop():
    d = _diag(a_cur=700.0, g_cur=1400.0)
    assert d.classificacao == "MERCADO_EM_QUEDA"
    assert d.variacao_mercado_pct == pytest.approx(-30.0)
    assert d.efeito_mercado == pytest.approx(-300.0)
    assert d.efeito_participacao == pytest.approx(0.0)
    assert d.variacao_participacao_pp == pytest.approx(0.0, abs=1e-6)


def test_pure_share_loss_with_flat_market():
    d = _diag(a_cur=700.0, g_cur=2000.0)
    assert d.classificacao == "PERDA_DE_PARTICIPACAO"
    assert d.efeito_participacao == pytest.approx(-300.0)
    assert d.participacao_anterior_pct == pytest.approx(33.33, abs=0.01)
    assert d.participacao_atual_pct == pytest.approx(25.93, abs=0.01)
    assert d.variacao_participacao_pp == pytest.approx(-7.4, abs=0.01)


def test_market_rise_and_share_gain():
    assert _diag(a_cur=1300.0, g_cur=2600.0).classificacao == "MERCADO_EM_ALTA"
    assert _diag(a_cur=1300.0, g_cur=2000.0).classificacao == "GANHO_DE_PARTICIPACAO"


@pytest.mark.parametrize(
    "g_cur,expected",
    [(1574.0, "MERCADO_EM_QUEDA"),   # m = 0,71
     (1586.0, "MISTO"),              # m = 0,69
     (1826.0, "PERDA_DE_PARTICIPACAO"),  # m = 0,29
     (1814.0, "MISTO")],             # m = 0,31
)
def test_dominance_thresholds(g_cur, expected):
    assert _diag(a_cur=700.0, g_cur=g_cur).classificacao == expected


def test_group_too_small_is_sem_grupo_afim():
    assert _diag(a_cur=700.0, g_cur=100.0, g_pre=400.0).classificacao == "SEM_GRUPO_AFIM"


# --- Lancamento afim (P-160): primeira venda em (fim PRE, fim CUR] e >= primeiraData + 90 dias
def _launch(first_sale, pre_last, cur_last):
    fn = mod("domain.affinity_group").is_launch_affine
    return fn(first_sale_month_index=first_sale, pre_last_month_index=pre_last,
              cur_last_month_index=cur_last, base_first_date=__import__("datetime").date(2025, 1, 7))


def _i(y, m):
    return y * 12 + m - 1


def test_launch_inside_gap_between_non_contiguous_windows():
    assert _launch(_i(2026, 9), _i(2026, 7), _i(2026, 10)) is True


def test_first_sale_before_or_at_end_of_pre_is_not_launch():
    assert _launch(_i(2026, 7), _i(2026, 7), _i(2026, 10)) is False


def test_first_sale_after_current_window_is_not_launch():
    assert _launch(_i(2026, 11), _i(2026, 7), _i(2026, 10)) is False


def test_old_sku_with_first_sale_in_base_start_is_not_launch():
    assert _launch(_i(2025, 2), _i(2025, 1), _i(2025, 3)) is False
    assert _launch(_i(2025, 4), _i(2025, 3), _i(2025, 5)) is True
