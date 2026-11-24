"""
Testes Unitários do Domínio Puro de Canibalização e Substituição (TDD First)
Fase F6 — Tarefas 2, 3, 4 e 5 — Regras P-129 a P-137.

Cenários cobertos:
1. Constantes nominais de domínio (sem números mágicos).
2. Detecção de eventos `promo`, `price` (PRICE_DROP / PRICE_HIKE) e `launch` (trava `2025-04-01` + 3 meses).
3. Janelas simétricas pré/pós com preenchimento zero-fill, expurgo de mês corrente e devoluções `LIKE 'DEVOLU%'`.
4. Seleção do grupo de controle categorial, fallback para fornecedor/global (`CONTROLE_EXPANDIDO`) e proteção div/0.
5. Motor DiD: neutralização de choque comum (+15% e +20%) e detecção precisa de queda real (-30%).
6. Rigor estatístico: FDR Benjamini-Hochberg com 50 itens aleatórios (0 falsos positivos) e corte prático `|ΔV| >= 5`.
7. Taxonomia de classificação (`CANIBALIZACAO`, `COMPLEMENTO`, `MIGRACAO_POSITIVA`, `SEM_EFEITO`).
8. Efeito líquido financeiro (`VALEU_A_PENA`, `ILUSAO_DE_VOLUME`, `PREJUIZO_TOTAL`) e fallback de custo 60%.
9. Interface `CrossElasticityProvider` / `NullCrossElasticityProvider` (`NAO_INTEGRADO` na ausência de F5).
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from src.modules.analytics.domain.cannibalization import (
    COST_FALLBACK_RATIO,
    DEFAULT_ANALYSIS_WINDOW_WEEKS,
    FDR_ALPHA,
    LAUNCH_CUTOFF_DATE,
    MAX_ANALYSIS_WINDOW_WEEKS,
    MIN_ANALYSIS_WINDOW_WEEKS,
    MIN_CONTROL_GROUP_SIZE,
    MIN_EFFECT_VOLUME_UNITS,
    MIN_LAUNCH_MONTHS,
    MIN_PRICE_CHANGE_PCT,
    RETURN_OPERATION_PATTERN,
    apply_returns_netting,
    build_pre_post_windows,
    calculate_net_impact,
    classify_impact,
    detect_product_events,
    estimate_difference_in_differences,
    resolve_unit_margin,
    select_control_group,
)
from src.modules.analytics.domain.elasticity_interface import (
    CrossElasticityProvider,
    NullCrossElasticityProvider,
    decompose_cross_elasticity,
)
from src.modules.analytics.domain.exceptions import (
    CannibalizationEventNotFoundError,
    CannibalizationInsufficientHistoryError,
)
from src.modules.analytics.domain.fdr_correction import benjamini_hochberg


def _daily_series(
    start: date,
    days: int,
    qty_per_day: float = 10.0,
    price: float = 25.0,
    sku: str = "1001",
) -> pd.DataFrame:
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        rows.append(
            {
                "sku": sku,
                "date": d,
                "qty": float(qty_per_day),
                "price": float(price),
                "revenue": float(qty_per_day * price),
                "operation": "VENDA",
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Constantes (P-128 a P-137)
# ---------------------------------------------------------------------------


def test_domain_constants_match_business_rules():
    """Garante que os parâmetros numéricos canônicos estão declarados no domínio."""
    assert MIN_PRICE_CHANGE_PCT == pytest.approx(0.05)
    assert LAUNCH_CUTOFF_DATE == date(2025, 4, 1)
    assert MIN_LAUNCH_MONTHS == 3
    assert DEFAULT_ANALYSIS_WINDOW_WEEKS == 4
    assert MIN_ANALYSIS_WINDOW_WEEKS == 2
    assert MAX_ANALYSIS_WINDOW_WEEKS == 12
    assert MIN_CONTROL_GROUP_SIZE == 5
    assert FDR_ALPHA == pytest.approx(0.05)
    assert MIN_EFFECT_VOLUME_UNITS == 5
    assert COST_FALLBACK_RATIO == pytest.approx(0.60)
    assert RETURN_OPERATION_PATTERN == "DEVOLU%"


# ---------------------------------------------------------------------------
# Tarefa 2: Detecção de Eventos, Janelas Simétricas e Devoluções (P-129, P-130, P-137.2)
# ---------------------------------------------------------------------------


def test_detect_promo_event_from_calendar():
    """P-129.1: Identifica o início T0 da campanha promocional mais recente no promo_calendar."""
    # Arrange
    sales = _daily_series(date(2026, 7, 1), 90, sku="1001")
    promo_calendar = pd.DataFrame(
        [
            {"sku": "1001", "cod_promocao": "PR01", "start_date": date(2026, 7, 15)},
            {"sku": "1001", "cod_promocao": "PR02", "start_date": date(2026, 9, 1)},
        ]
    )

    # Act
    event = detect_product_events(
        sku="1001",
        sales_series=sales,
        promo_calendar=promo_calendar,
        event_type="promo",
    )

    # Assert
    assert event.event_type == "promo"
    assert event.event_date == date(2026, 9, 1)


def test_detect_promo_event_raises_can_002_when_absent():
    """P-129 / C-03: Produto sem eventos promocionais falha com CAN-002."""
    # Arrange
    sales = _daily_series(date(2026, 7, 1), 60, sku="1001")
    empty_calendar = pd.DataFrame(columns=["sku", "cod_promocao", "start_date"])

    # Act & Assert
    with pytest.raises(CannibalizationEventNotFoundError) as exc_info:
        detect_product_events(
            sku="1001",
            sales_series=sales,
            promo_calendar=empty_calendar,
            event_type="promo",
        )
    assert exc_info.value.code == "CAN-002"


def test_detect_price_drop_and_price_hike_events():
    """P-129.2: Queda de 10% gera PRICE_DROP; alta de 12% gera PRICE_HIKE; 2% não é evento."""
    # Arrange: 4 semanas a R$ 20,00 seguidas de 4 semanas a R$ 18,00 (-10%)
    pre_df = _daily_series(date(2026, 8, 1), 28, price=20.0, sku="1001")
    post_drop = _daily_series(date(2026, 8, 29), 28, price=18.0, sku="1001")
    sales_drop = pd.concat([pre_df, post_drop], ignore_index=True)

    post_hike = _daily_series(date(2026, 8, 29), 28, price=22.4, sku="1001")
    sales_hike = pd.concat([pre_df, post_hike], ignore_index=True)

    post_flat = _daily_series(date(2026, 8, 29), 28, price=20.4, sku="1001")  # +2% < 5%
    sales_flat = pd.concat([pre_df, post_flat], ignore_index=True)

    empty_cal = pd.DataFrame(columns=["sku", "cod_promocao", "start_date"])

    # Act
    ev_drop = detect_product_events("1001", sales_drop, empty_cal, event_type="price")
    ev_hike = detect_product_events("1001", sales_hike, empty_cal, event_type="price")

    # Assert
    assert ev_drop.event_type == "price"
    assert ev_drop.price_direction == "PRICE_DROP"
    assert ev_drop.avg_price_change_pct == pytest.approx(-10.0, abs=0.5)

    assert ev_hike.price_direction == "PRICE_HIKE"
    assert ev_hike.avg_price_change_pct == pytest.approx(12.0, abs=0.5)

    with pytest.raises(CannibalizationEventNotFoundError) as exc_info:
        detect_product_events("1001", sales_flat, empty_cal, event_type="price")
    assert exc_info.value.code == "CAN-002"


def test_detect_launch_rejects_pre_cutoff_and_insufficient_months():
    """
    P-129.3 / P-129.4:
    - 1ª venda em fev/2025 (< 2025-04-01) -> rejeita como falso lançamento (CAN-002).
    - 1ª venda >= 2025-04-01 com < 3 meses completos -> rejeita (CAN-003).
    - 1ª venda >= 2025-04-01 com >= 3 meses -> aceita.
    """
    # Arrange
    empty_cal = pd.DataFrame(columns=["sku", "cod_promocao", "start_date"])
    mature_sales = _daily_series(date(2025, 2, 10), 180, sku="1001")
    too_new_sales = _daily_series(date(2026, 9, 15), 40, sku="1002")
    valid_launch_sales = _daily_series(date(2026, 6, 1), 120, sku="1003")

    # Act & Assert: Falso lançamento (antes de 2025-04-01)
    with pytest.raises(CannibalizationEventNotFoundError) as exc_mature:
        detect_product_events("1001", mature_sales, empty_cal, event_type="launch")
    assert exc_mature.value.code == "CAN-002"

    # Act & Assert: Menos de 3 meses de histórico
    with pytest.raises(CannibalizationInsufficientHistoryError) as exc_short:
        detect_product_events("1002", too_new_sales, empty_cal, event_type="launch")
    assert exc_short.value.code == "CAN-003"

    # Act & Assert: Lançamento válido
    valid_ev = detect_product_events("1003", valid_launch_sales, empty_cal, event_type="launch")
    assert valid_ev.event_type == "launch"
    assert valid_ev.event_date == date(2026, 6, 1)


def test_build_pre_post_windows_symmetric_zero_fill_and_insufficient_history():
    """P-130: Janelas simétricas [T0 - 28, T0 - 1] e [T0, T0 + 27] com zero-fill nos dias sem venda."""
    # Arrange: Apenas 2 dias com venda na pré e 2 dias na pós dentro de janela de 4 semanas
    event_date = date(2026, 9, 1)
    sparse_sales = pd.DataFrame(
        [
            {"sku": "1001", "date": date(2026, 8, 4), "qty": 10.0, "price": 20.0, "revenue": 200.0},
            {"sku": "1001", "date": date(2026, 8, 20), "qty": 15.0, "price": 20.0, "revenue": 300.0},
            {"sku": "1001", "date": date(2026, 9, 1), "qty": 30.0, "price": 18.0, "revenue": 540.0},
            {"sku": "1001", "date": date(2026, 9, 28), "qty": 20.0, "price": 18.0, "revenue": 360.0},
        ]
    )

    # Act
    windows = build_pre_post_windows(
        event_date=event_date,
        window_weeks=4,
        sales_series=sparse_sales,
        history_start=date(2026, 7, 1),
        history_end=date(2026, 10, 15),
    )

    # Assert
    assert len(windows.pre_daily) == 28
    assert len(windows.post_daily) == 28
    assert windows.pre_start == date(2026, 8, 4)
    assert windows.pre_end == date(2026, 8, 31)
    assert windows.post_start == date(2026, 9, 1)
    assert windows.post_end == date(2026, 9, 28)
    assert windows.pre_total_volume == pytest.approx(25.0)
    assert windows.post_total_volume == pytest.approx(50.0)
    assert (windows.pre_daily["qty"] == 0.0).sum() == 26

    # Edge case: Histórico pós insuficiente -> CAN-003
    with pytest.raises(CannibalizationInsufficientHistoryError) as exc_info:
        build_pre_post_windows(
            event_date=event_date,
            window_weeks=4,
            sales_series=sparse_sales,
            history_start=date(2026, 7, 1),
            history_end=date(2026, 9, 10),
        )
    assert exc_info.value.code == "CAN-003"


def test_apply_returns_netting_subtracts_devolu_and_clamps_negative():
    """P-137.2: Devoluções ([Operação] LIKE 'DEVOLU%') são abatidas; líquido <= 0 vira 0 na série."""
    # Arrange
    raw = pd.DataFrame(
        [
            {"sku": "1001", "date": date(2026, 9, 1), "operation": "VENDA", "qty": 50.0, "revenue": 1000.0},
            {"sku": "1001", "date": date(2026, 9, 1), "operation": "DEVOLUCAO DE VENDA", "qty": -12.0, "revenue": -240.0},
            {"sku": "1001", "date": date(2026, 9, 2), "operation": "VENDA", "qty": 5.0, "revenue": 100.0},
            {"sku": "1001", "date": date(2026, 9, 2), "operation": "DEVOLUÇÃO", "qty": -8.0, "revenue": -160.0},
        ]
    )

    # Act
    net = apply_returns_netting(raw)

    # Assert
    day1 = net.loc[net["date"] == date(2026, 9, 1), "qty"].iloc[0]
    day2 = net.loc[net["date"] == date(2026, 9, 2), "qty"].iloc[0]
    assert day1 == pytest.approx(38.0)
    assert day2 == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tarefa 3: Grupo de Controle e Motor DiD (P-131, P-132)
# ---------------------------------------------------------------------------


def test_select_control_group_filters_promos_and_price_changes_and_expands_fallback():
    """
    P-131:
    - Exclui alvo, substitutos diretos, itens com promoção ou variação de preço > 3%.
    - Se categoria tem < 5 estáveis, expande para fornecedor/global (`is_expanded_control=True`).
    - Se mesmo global < 5, lança CAN-003.
    """
    # Arrange: 3 itens estáveis na categoria + 2 estáveis no mesmo fornecedor
    products = [
        {"sku": "1001", "category": "EXTRATOS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.0, "pre_vol": 100, "post_vol": 150},
        {"sku": "1002", "category": "EXTRATOS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.01, "pre_vol": 50, "post_vol": 52},
        {"sku": "1003", "category": "EXTRATOS", "supplier": "FITO", "in_promo": False, "price_change_pct": -0.02, "pre_vol": 60, "post_vol": 61},
        {"sku": "1004", "category": "EXTRATOS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.0, "pre_vol": 70, "post_vol": 71},
        {"sku": "1005", "category": "EXTRATOS", "supplier": "FITO", "in_promo": True, "price_change_pct": 0.0, "pre_vol": 80, "post_vol": 120},   # promo -> fora
        {"sku": "1006", "category": "EXTRATOS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.08, "pre_vol": 90, "post_vol": 60},  # >3% -> fora
        {"sku": "2001", "category": "CAPSULAS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.01, "pre_vol": 40, "post_vol": 41},
        {"sku": "2002", "category": "CAPSULAS", "supplier": "FITO", "in_promo": False, "price_change_pct": 0.0, "pre_vol": 45, "post_vol": 46},
    ]

    # Act
    control = select_control_group(
        target_sku="1001",
        target_category="EXTRATOS",
        target_supplier="FITO",
        substitute_skus=set(),
        category_products=products,
    )

    # Assert: Expandido para atingir >= 5
    assert control.sample_size >= 5
    assert control.is_expanded_control is True
    assert control.control_strategy in ("FORNECEDOR", "GLOBAL")
    assert "1001" not in control.skus
    assert "1005" not in control.skus
    assert "1006" not in control.skus

    # Edge case: impossível formar >= 5 -> CAN-003
    with pytest.raises(CannibalizationInsufficientHistoryError) as exc_info:
        select_control_group(
            target_sku="1001",
            target_category="EXTRATOS",
            target_supplier="FITO",
            substitute_skus=set(),
            category_products=products[:3],
        )
    assert exc_info.value.code == "CAN-003"


def test_did_neutralizes_common_seasonal_shock_15_and_20_percent():
    """
    Tarefa 3 Audit Cenário 1 & Etapa 3.3:
    Choque comum (+15% ou +20% em todos os itens) gera counterfactual == post -> ΔV ≈ 0.
    """
    for shock in (1.15, 1.20):
        # Arrange
        control_pre = [100.0] * 5
        control_post = [100.0 * shock] * 5
        cand_pre = 200.0
        cand_post = 200.0 * shock

        # Act
        did = estimate_difference_in_differences(
            candidate_pre_volume=cand_pre,
            candidate_post_volume=cand_post,
            control_pre_volumes=control_pre,
            control_post_volumes=control_post,
        )

        # Assert
        assert did.growth_factor == pytest.approx(shock)
        assert did.counterfactual_volume == pytest.approx(cand_post)
        assert did.delta_volume == pytest.approx(0.0, abs=1e-6)
        assert did.delta_volume_pct == pytest.approx(0.0, abs=1e-6)


def test_did_detects_real_30_percent_drop_against_stable_control():
    """
    Tarefa 3 Audit Cenário 2:
    Controle estável (g_ctrl = 1.0) e substituto com queda real de 30% -> ΔV = -30% com precisão.
    """
    # Arrange
    control_pre = [100.0, 120.0, 80.0, 110.0, 90.0]
    control_post = [100.0, 120.0, 80.0, 110.0, 90.0]

    # Act
    did = estimate_difference_in_differences(
        candidate_pre_volume=100.0,
        candidate_post_volume=70.0,
        control_pre_volumes=control_pre,
        control_post_volumes=control_post,
    )

    # Assert
    assert did.growth_factor == pytest.approx(1.0)
    assert did.counterfactual_volume == pytest.approx(100.0)
    assert did.delta_volume == pytest.approx(-30.0)
    assert did.delta_volume_pct == pytest.approx(-30.0)


def test_did_handles_zero_control_pre_volume_without_zero_division():
    """P-131.3: Se soma pré do controle for 0, g_ctrl = 1.0 (sem ZeroDivisionError)."""
    # Arrange & Act
    did = estimate_difference_in_differences(
        candidate_pre_volume=50.0,
        candidate_post_volume=40.0,
        control_pre_volumes=[0.0, 0.0, 0.0, 0.0, 0.0],
        control_post_volumes=[0.0, 0.0, 0.0, 0.0, 0.0],
    )

    # Assert
    assert did.growth_factor == pytest.approx(1.0)
    assert did.delta_volume == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Tarefa 4: FDR Benjamini-Hochberg, Corte Prático e Classificação (P-133, P-134)
# ---------------------------------------------------------------------------


def test_fdr_benjamini_hochberg_no_false_positives_on_50_random_items():
    """
    Tarefa 4 Audit Cenário 1:
    50 produtos puramente aleatórios (sem efeito real) submetidos ao BH FDR (alpha=0.05)
    não devem gerar nenhum falso positivo significativo.
    """
    # Arrange: 50 séries pré/pós de ruído i.i.d. com seed determinística (mesma distribuição)
    rng = np.random.default_rng(seed=42)
    n_items = 50
    p_values = []
    for _ in range(n_items):
        # 28 dias pré vs 28 dias pós da mesma distribuição Normal(20, 4)
        pre = rng.normal(loc=20.0, scale=4.0, size=28)
        post = rng.normal(loc=20.0, scale=4.0, size=28)
        diff = post.mean() - pre.mean()
        se = np.sqrt(post.var(ddof=1) / 28.0 + pre.var(ddof=1) / 28.0)
        z = abs(diff) / max(se, 1e-9)
        # p-valor bicaudal via aproximação normal (erf)
        from math import erfc, sqrt
        p_val = erfc(z / sqrt(2.0))
        p_values.append(p_val)

    # Act
    result = benjamini_hochberg(p_values, alpha=FDR_ALPHA)

    # Assert
    assert len(result.q_values) == n_items
    assert len(result.significant_flags) == n_items
    assert sum(result.significant_flags) == 0


def test_fdr_benjamini_hochberg_computes_monotonic_q_values():
    """P-133.2: Verifica cálculo exato e monotonicidade dos q-valores ajustados."""
    # Arrange
    p_values = [0.001, 0.008, 0.039, 0.041, 0.250]

    # Act
    result = benjamini_hochberg(p_values, alpha=0.05)

    # Assert: m=5 -> q_raw = [0.005, 0.020, 0.065, 0.05125, 0.250] -> step-up min = [0.005, 0.020, 0.05125, 0.05125, 0.250]
    assert result.q_values[0] == pytest.approx(0.005)
    assert result.q_values[1] == pytest.approx(0.020)
    assert result.q_values[2] == pytest.approx(0.05125)
    assert result.q_values[3] == pytest.approx(0.05125)
    assert result.significant_flags == [True, True, False, False, False]


@pytest.mark.parametrize(
    "target_delta,cand_delta,q_value,expected_class",
    [
        (100.0, -30.0, 0.01, "CANIBALIZACAO"),
        (100.0, 25.0, 0.01, "COMPLEMENTO"),
        (-50.0, 20.0, 0.01, "MIGRACAO_POSITIVA"),
        (100.0, -2.0, 0.005, "SEM_EFEITO"),     # Tarefa 4 Cenário 2: |ΔV| < 5 mesmo com q < 0.01
        (100.0, -40.0, 0.12, "SEM_EFEITO"),     # q > 0.05 -> SEM_EFEITO
    ],
)
def test_classify_impact_taxonomy_and_practical_cutoff(target_delta, cand_delta, q_value, expected_class):
    """P-133.3 e P-134: Classificação e filtro de relevância prática |ΔV| >= 5."""
    # Arrange & Act
    classification = classify_impact(
        target_delta_volume=target_delta,
        candidate_delta_volume=cand_delta,
        q_value=q_value,
    )

    # Assert
    assert classification == expected_class


# ---------------------------------------------------------------------------
# Tarefa 5: Efeito Líquido Financeiro, Fallback Custo 60% e Elasticidade F5 (P-135, P-136)
# ---------------------------------------------------------------------------


def test_calculate_net_impact_ilusao_de_volume():
    """
    Tarefa 5 Audit Cenário 1:
    Alvo +500 un. (margem R$ 5 -> +R$ 2.500), substituto -400 un. (margem R$ 10 -> -R$ 4.000)
    -> ΔV_liq = +100, ΔM_liq = -R$ 1.500, veredito ILUSAO_DE_VOLUME.
    """
    # Arrange
    target_metrics = {
        "delta_volume": 500.0,
        "delta_revenue": 5000.0,
        "delta_margin": 2500.0,
    }
    affected_items = [
        {
            "delta_volume": -400.0,
            "unit_price": 25.0,
            "unit_margin": 10.0,
            "is_significant": True,
        }
    ]

    # Act
    net = calculate_net_impact(target_metrics=target_metrics, affected_items=affected_items)

    # Assert
    assert net.net_delta_volume == pytest.approx(100.0)
    assert net.net_delta_margin == pytest.approx(-1500.0)
    assert net.commercial_verdict == "ILUSAO_DE_VOLUME"


@pytest.mark.parametrize(
    "target_dv,target_dm,affected_dv,affected_dm,expected_verdict",
    [
        (300.0, 1800.0, -50.0, -300.0, "VALEU_A_PENA"),
        (-100.0, -500.0, -50.0, -200.0, "PREJUIZO_TOTAL"),
    ],
)
def test_calculate_net_impact_valeu_a_pena_and_prejuizo_total(
    target_dv, target_dm, affected_dv, affected_dm, expected_verdict
):
    """P-135.5: Vereditos VALEU_A_PENA (ΔM > 0) e PREJUIZO_TOTAL (ΔM <= 0 e ΔV <= 0)."""
    # Arrange
    target_metrics = {"delta_volume": target_dv, "delta_revenue": 0.0, "delta_margin": target_dm}
    affected_items = [
        {"delta_volume": affected_dv, "unit_price": 20.0, "unit_margin": affected_dm / affected_dv, "is_significant": True}
    ]

    # Act
    net = calculate_net_impact(target_metrics=target_metrics, affected_items=affected_items)

    # Assert
    assert net.commercial_verdict == expected_verdict


@pytest.mark.parametrize("bad_cost", [None, 0.0, -5.0, 120.0])
def test_resolve_unit_margin_applies_60_percent_cost_fallback(bad_cost):
    """P-135.3: Custo nulo, <= 0 ou > preço de venda aplica fallback de 60% (margem 40%)."""
    # Arrange
    selling_price = 100.0

    # Act
    unit_margin, fallback_used = resolve_unit_margin(selling_price=selling_price, last_cost=bad_cost)

    # Assert
    assert fallback_used is True
    assert unit_margin == pytest.approx(40.0)


def test_cross_elasticity_provider_graceful_degradation_and_integration():
    """
    P-136 / Tarefa 5 Cenário 2:
    - `NullCrossElasticityProvider` retorna None e mantém status `NAO_INTEGRADO`.
    - Provedor integrado decompõe ΔV_preco e ΔV_residual corretamente.
    """
    # Arrange
    null_provider = NullCrossElasticityProvider()

    # Act
    cross_eps = asyncio.run(null_provider.get_cross_elasticity("1001", "1002"))
    decomp_none = decompose_cross_elasticity(
        cross_elasticity=cross_eps,
        candidate_pre_volume=200.0,
        target_price_change_ratio=-0.20,
        total_delta_volume=-40.0,
    )

    # Assert (ausência de F5)
    assert isinstance(null_provider, CrossElasticityProvider)
    assert cross_eps is None
    assert decomp_none is None

    # Arrange (F5 presente com ε_ji = +0.5 -> queda de 20% no alvo explica -10% no substituto = -20 un.)
    decomp_ok = decompose_cross_elasticity(
        cross_elasticity=0.5,
        candidate_pre_volume=200.0,
        target_price_change_ratio=-0.20,
        total_delta_volume=-40.0,
    )

    # Assert
    assert decomp_ok is not None
    assert decomp_ok.price_explained_delta_volume == pytest.approx(-20.0)
    assert decomp_ok.residual_delta_volume == pytest.approx(-20.0)
    assert decomp_ok.price_explained_share == pytest.approx(0.5)
