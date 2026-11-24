"""
Testes de Domínio para Viabilidade de Produto Novo (F2; P-139 a P-149; ADR-008).

Cobre todos os cenários da Matriz de Rastreabilidade (§3 de tasks/analytics-produto-novo.md):
- test_launch_cutoff_exclusion (P-139): produtos com 1ª venda < 2025-04-01 excluídos dos similares.
- test_min_launch_months (P-139): lançamento com < 3 meses completos desconsiderado para a curva inicial.
- test_similarity_score_weights (P-142): pesos exatos Fornecedor (0.25), Log-Preço (0.35), TF-IDF Cosseno (0.40);
  TOP_K_SIMILARS = 10; tipo estrito sem relaxamento.
- test_min_similars_threshold (P-143): < 3 similares elegíveis lança NewProductInsufficientSimilarsError (NEW-001).
- test_returns_deduction (P-144): devoluções abatidas; saldo líquido negativo truncado em 0.
- test_conservative_haircut (P-145): previsão = P25 * 0.70 e invariavelmente <= P25.
- test_seasonality_damping (P-146): índice externo 1.40 amortecido para 1.10; confiança BAIXA ou indisponível -> 1.00.
- test_mature_ceiling (P-147): tetoMaduroP75 calculado sobre produtos antigos (< 2025-04-01) do mesmo tipo.
- test_financial_margin_viability (P-148): viavel true/false conforme margemMinimaDesejada; None se não informada;
  borda custo == preco -> margem 0.00.
- test_backtest_calibration (P-145): backtest sintético leave-one-out comprovando taxa de sucesso >= 80%.
"""
from __future__ import annotations

from datetime import date
from typing import List

import numpy as np
import pandas as pd
import pytest

from src.modules.analytics.domain.exceptions import NewProductInsufficientSimilarsError
from src.modules.analytics.domain.new_product import (
    CACHE_TTL_HOURS,
    DEFAULT_HORIZON_MONTHS,
    LAUNCH_CUTOFF_DATE,
    MAX_HORIZON_MONTHS,
    MIN_BACKTEST_SUCCESS_RATE,
    MIN_LAUNCH_MONTHS,
    MIN_SIMILARS,
    NEW_PRODUCT_HAIRCUT,
    RETURN_OPERATION_PATTERN,
    SALE_OPERATION,
    SEASONALITY_MAX_FACTOR,
    SEASONALITY_MIN_FACTOR,
    TOP_K_SIMILARS,
    WEIGHT_PRICE,
    WEIGHT_SUPPLIER,
    WEIGHT_TFIDF,
    SeasonalityProvider,
    SeasonalityResult,
    apply_seasonality_and_clamp,
    compute_conservative_curve,
    compute_mature_ceiling,
    evaluate_financial_viability,
    filter_eligible_launches,
    find_similars,
    run_backtest_calibration,
)


class _StubSeasonalityProvider(SeasonalityProvider):
    """Stub determinístico para testes de integração desacoplada com F1 (P-146)."""

    def __init__(self, index: float = 1.0, confidence: str = "PADRAO") -> None:
        self._index = index
        self._confidence = confidence

    def get_category_seasonality(self, category: str, month: int) -> SeasonalityResult:
        return SeasonalityResult(index=self._index, confidence=self._confidence)


def _make_launch_df(
    sku: int,
    tipo: str,
    fornecedor: str,
    descricao: str,
    preco: float,
    first_sale: date,
    monthly_quantities: List[int],
) -> pd.DataFrame:
    """Constrói série mensal sintética de um produto para testes de domínio."""
    rows = []
    year = first_sale.year
    month = first_sale.month
    for idx, qty in enumerate(monthly_quantities):
        m = month + idx
        y = year + (m - 1) // 12
        m = ((m - 1) % 12) + 1
        rows.append(
            {
                "sku": sku,
                "tipo": tipo,
                "fornecedor": fornecedor,
                "descricao": descricao,
                "preco": preco,
                "first_sale_date": first_sale,
                "sale_year": y,
                "sale_month": m,
                "net_quantity": qty,
            }
        )
    return pd.DataFrame(rows)


def test_domain_constants_match_specification():
    """P-139..P-149: Constantes imutáveis do domínio devem corresponder exatamente à tabela §2."""
    assert SALE_OPERATION == "VENDA"
    assert RETURN_OPERATION_PATTERN == "DEVOLU%"
    assert str(LAUNCH_CUTOFF_DATE) == "2025-04-01"
    assert MIN_LAUNCH_MONTHS == 3
    assert TOP_K_SIMILARS == 10
    assert MIN_SIMILARS == 3
    assert WEIGHT_SUPPLIER == pytest.approx(0.10)
    assert WEIGHT_PRICE == pytest.approx(0.40)
    assert WEIGHT_TFIDF == pytest.approx(0.50)
    assert WEIGHT_SUPPLIER + WEIGHT_PRICE + WEIGHT_TFIDF == pytest.approx(1.00)
    assert NEW_PRODUCT_HAIRCUT == pytest.approx(0.70)
    assert MIN_BACKTEST_SUCCESS_RATE == pytest.approx(0.80)
    assert DEFAULT_HORIZON_MONTHS == 3
    assert MAX_HORIZON_MONTHS == 3
    assert SEASONALITY_MIN_FACTOR == pytest.approx(0.90)
    assert SEASONALITY_MAX_FACTOR == pytest.approx(1.10)
    assert CACHE_TTL_HOURS == 6


def test_launch_cutoff_exclusion():
    """P-139: Produtos com 1ª venda anterior a 2025-04-01 são excluídos dos candidatos a similares."""
    # Arrange
    old_product = _make_launch_df(
        sku=1001,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Camomila 50ml",
        preco=40.0,
        first_sale=date(2025, 1, 15),
        monthly_quantities=[200, 220, 250, 240],
    )
    cutoff_edge_product = _make_launch_df(
        sku=1002,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Melissa 50ml",
        preco=42.0,
        first_sale=date(2025, 4, 1),
        monthly_quantities=[40, 50, 60],
    )
    recent_product = _make_launch_df(
        sku=1003,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Valeriana 50ml",
        preco=44.0,
        first_sale=date(2025, 6, 10),
        monthly_quantities=[35, 45, 55],
    )
    df = pd.concat([old_product, cutoff_edge_product, recent_product], ignore_index=True)

    # Act
    eligible = filter_eligible_launches(df, reference_date=date(2026, 11, 1))

    # Assert
    eligible_skus = set(eligible["sku"].unique())
    assert 1001 not in eligible_skus
    assert 1002 in eligible_skus
    assert 1003 in eligible_skus


def test_min_launch_months():
    """P-139: Lançamento com menos de 3 meses completos é desconsiderado para a curva inicial."""
    # Arrange
    two_months_only = _make_launch_df(
        sku=2001,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Erva Cidreira 50ml",
        preco=38.0,
        first_sale=date(2026, 9, 5),  # Apenas Set/2026 e Out/2026 completos antes de 2026-11-01
        monthly_quantities=[80, 90],
    )
    three_months_ok = _make_launch_df(
        sku=2002,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Passiflora 50ml",
        preco=39.0,
        first_sale=date(2026, 8, 5),  # Ago, Set, Out completos
        monthly_quantities=[50, 60, 70],
    )
    df = pd.concat([two_months_only, three_months_ok], ignore_index=True)

    # Act
    eligible = filter_eligible_launches(df, reference_date=date(2026, 11, 1))

    # Assert
    eligible_skus = set(eligible["sku"].unique())
    assert 2001 not in eligible_skus
    assert 2002 in eligible_skus


def test_similarity_score_weights():
    """P-142: Pesos exatos Fornecedor (0.25), Log-Preço (0.35), TF-IDF Cosseno (0.40); TOP_K=10 e tipo estrito."""
    # Arrange
    target = {
        "tipo": "Tinturas",
        "fornecedor": "FITOHERB LABORATORIOS",
        "descricao": "Tintura Mae de Melissa Officinalis 50ml Frasco",
        "preco_venda_previsto": 40.0,
    }
    # Similar 1: idêntico em fornecedor, preço e descrição -> score 1.00
    s_identical = _make_launch_df(
        sku=3001,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura Mae de Melissa Officinalis 50ml Frasco",
        preco=40.0,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[50, 60, 70],
    )
    # Similar 2: fornecedor diferente (0.0), preço metade (20.0 -> exp(-|ln(40)-ln(20)|)=0.50), descrição igual (~1.0)
    s_half_price_diff_sup = _make_launch_df(
        sku=3002,
        tipo="Tinturas",
        fornecedor="OUTRO FORNECEDOR",
        descricao="Tintura Mae de Melissa Officinalis 50ml Frasco",
        preco=20.0,
        first_sale=date(2025, 5, 10),
        monthly_quantities=[40, 50, 60],
    )
    # Similar 3: mesmo fornecedor (1.0), mesmo preço (1.0), descrição totalmente diferente (~0.0)
    s_diff_desc = _make_launch_df(
        sku=3003,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Xarope Expectorante Eucalipto",
        preco=40.0,
        first_sale=date(2025, 6, 1),
        monthly_quantities=[30, 40, 50],
    )
    # Produto de outro tipo (Capsulas) com descrição idêntica -> DEVE ser ignorado (sem relaxamento de tipo)
    s_other_type = _make_launch_df(
        sku=3099,
        tipo="Capsulas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura Mae de Melissa Officinalis 50ml Frasco",
        preco=40.0,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[90, 95, 100],
    )
    df = pd.concat([s_identical, s_half_price_diff_sup, s_diff_desc, s_other_type], ignore_index=True)

    # Act
    similars = find_similars(
        candidates_df=df,
        tipo=target["tipo"],
        fornecedor=target["fornecedor"],
        descricao=target["descricao"],
        preco_venda_previsto=target["preco_venda_previsto"],
        affinity_scores={3001: 1.0, 3002: 1.0, 3003: 0.0},
    )

    # Assert
    skus = [s.sku for s in similars]
    assert 3099 not in skus
    assert skus[0] == 3001
    assert similars[0].score_fornecedor == pytest.approx(1.0)
    assert similars[0].score_preco == pytest.approx(1.0)
    assert similars[0].score_tfidf == pytest.approx(1.0, abs=1e-4)
    assert similars[0].score_final == pytest.approx(1.0, abs=1e-4)

    sim_3002 = next(s for s in similars if s.sku == 3002)
    assert sim_3002.score_fornecedor == pytest.approx(0.0)
    assert sim_3002.score_preco == pytest.approx(0.50, abs=1e-4)
    expected_3002 = (0.10 * 0.0) + (0.40 * 0.50) + (0.50 * sim_3002.score_tfidf)
    assert sim_3002.score_final == pytest.approx(expected_3002, abs=1e-4)

    sim_3003 = next(s for s in similars if s.sku == 3003)
    assert sim_3003.score_fornecedor == pytest.approx(1.0)
    assert sim_3003.score_preco == pytest.approx(1.0)
    assert sim_3003.score_tfidf == pytest.approx(0.0, abs=1e-4)
    assert sim_3003.score_final == pytest.approx(0.50, abs=1e-4)


def test_top_k_similars_limit_10():
    """P-143: Mesmo havendo > 10 candidatos elegíveis, retorna no máximo TOP_K_SIMILARS = 10."""
    # Arrange
    dfs = [
        _make_launch_df(
            sku=4000 + i,
            tipo="Capsulas",
            fornecedor="FORNECEDOR A",
            descricao=f"Capsula Fitoterapica {i}",
            preco=30.0 + i,
            first_sale=date(2025, 5, 1),
            monthly_quantities=[20, 25, 30],
        )
        for i in range(15)
    ]
    df = pd.concat(dfs, ignore_index=True)

    # Act
    similars = find_similars(
        candidates_df=df,
        tipo="Capsulas",
        fornecedor="FORNECEDOR A",
        descricao="Capsula Fitoterapica Nova",
        preco_venda_previsto=35.0,
    )

    # Assert
    assert len(similars) == TOP_K_SIMILARS == 10
    scores = [s.score_final for s in similars]
    assert scores == sorted(scores, reverse=True)


def test_min_similars_threshold():
    """P-143: Tipo com menos de 3 similares elegíveis lança NewProductInsufficientSimilarsError (NEW-001)."""
    # Arrange
    dfs = [
        _make_launch_df(
            sku=5001,
            tipo="Pomadas",
            fornecedor="FORNECEDOR A",
            descricao="Pomada de Arnica 30g",
            preco=25.0,
            first_sale=date(2025, 5, 1),
            monthly_quantities=[30, 35, 40],
        ),
        _make_launch_df(
            sku=5002,
            tipo="Pomadas",
            fornecedor="FORNECEDOR A",
            descricao="Pomada de Calendula 30g",
            preco=26.0,
            first_sale=date(2025, 6, 1),
            monthly_quantities=[28, 32, 36],
        ),
    ]
    df = pd.concat(dfs, ignore_index=True)

    # Act & Assert
    with pytest.raises(NewProductInsufficientSimilarsError) as exc_info:
        find_similars(
            candidates_df=df,
            tipo="Pomadas",
            fornecedor="FORNECEDOR A",
            descricao="Pomada de Confrei 30g",
            preco_venda_previsto=25.0,
        )

    assert exc_info.value.code == "NEW-001"
    assert exc_info.value.fields == ()


def test_returns_deduction():
    """P-144: Devoluções são abatidas das vendas; saldo líquido negativo no mês é truncado em 0."""
    # Arrange: 3 similares onde um teve devolução maior que venda no M2 (-15)
    s1 = _make_launch_df(
        sku=6001,
        tipo="Extratos",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Extrato Propolis Verde 30ml",
        preco=35.0,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[50, -15, 60],  # M2 líquido negativo
    )
    s2 = _make_launch_df(
        sku=6002,
        tipo="Extratos",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Extrato Propolis Vermelha 30ml",
        preco=36.0,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[60, 40, 70],
    )
    s3 = _make_launch_df(
        sku=6003,
        tipo="Extratos",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Extrato Propolis Misto 30ml",
        preco=34.0,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[70, 50, 80],
    )
    df = pd.concat([s1, s2, s3], ignore_index=True)

    # Act
    similars = find_similars(
        candidates_df=df,
        tipo="Extratos",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Extrato Propolis 30ml",
        preco_venda_previsto=35.0,
    )
    curve = compute_conservative_curve(similars=similars, horizon_months=3)

    # Assert
    sim_6001 = next(s for s in similars if s.sku == 6001)
    assert sim_6001.quantidades_primeiros_meses[1] == 0  # Truncado em 0, nunca negativo
    assert all(m.p10_quantity >= 0 for m in curve)
    assert all(m.conservative_quantity >= 0 for m in curve)


def test_conservative_haircut():
    """P-145: Previsão = round(P25 * 0.70) e invariavelmente <= P25 em todos os meses."""
    # Arrange: 4 similares com valores bem definidos para M1, M2, M3
    # M1: [40, 60, 80, 100] -> P25 = 55.0 -> 55.0 * 0.70 = 38.5 -> 38 ou 39 (<= 55)
    # M2: [80, 100, 120, 140] -> P25 = 95.0 -> 95.0 * 0.70 = 66.5 (<= 95)
    # M3: [100, 120, 140, 160] -> P25 = 115.0 -> 115.0 * 0.70 = 80.5 (<= 115)
    quantities_list = [
        [40, 80, 100],
        [60, 100, 120],
        [80, 120, 140],
        [100, 140, 160],
    ]
    dfs = [
        _make_launch_df(
            sku=7000 + i,
            tipo="Florais",
            fornecedor="FITOHERB LABORATORIOS",
            descricao=f"Floral Bach {i}",
            preco=30.0,
            first_sale=date(2025, 5, 1),
            monthly_quantities=q,
        )
        for i, q in enumerate(quantities_list)
    ]
    df = pd.concat(dfs, ignore_index=True)
    similars = find_similars(
        candidates_df=df,
        tipo="Florais",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Floral Bach Calmante",
        preco_venda_previsto=30.0,
    )

    # Act
    curve = compute_conservative_curve(similars=similars, horizon_months=3)

    # Assert
    assert len(curve) == 3
    for point in curve:
        assert point.conservative_quantity <= point.similar_p25_quantity
        expected_base = round(point.similar_p25_quantity * NEW_PRODUCT_HAIRCUT)
        assert point.conservative_quantity == pytest.approx(expected_base, abs=1)
        assert point.p10_quantity <= point.p50_quantity


def test_seasonality_damping():
    """P-146: Índice externo 1.40 é amortecido para 1.10; confiança BAIXA ou indisponível -> fator 1.00."""
    # Arrange
    base_qty = 40
    p25_qty = 50

    # Act 1: índice alto 1.40 com confiança ALTA -> amortecido para 1.10
    qty_high, factor_high, conf_high, status_high = apply_seasonality_and_clamp(
        base_quantity=base_qty,
        p25_quantity=p25_qty,
        category="Tinturas",
        calendar_month=3,
        provider=_StubSeasonalityProvider(index=1.40, confidence="ALTA"),
    )

    # Act 2: índice baixo 0.60 com confiança MEDIA -> amortecido para 0.90
    qty_low, factor_low, conf_low, status_low = apply_seasonality_and_clamp(
        base_quantity=base_qty,
        p25_quantity=p25_qty,
        category="Tinturas",
        calendar_month=9,
        provider=_StubSeasonalityProvider(index=0.60, confidence="MEDIA"),
    )

    # Act 3: confiança BAIXA -> fallback neutro 1.00
    qty_baixa, factor_baixa, conf_baixa, status_baixa = apply_seasonality_and_clamp(
        base_quantity=base_qty,
        p25_quantity=p25_qty,
        category="Tinturas",
        calendar_month=12,
        provider=_StubSeasonalityProvider(index=1.40, confidence="BAIXA"),
    )

    # Act 4: provider ausente (None) -> fallback neutro 1.00 (UNAVAILABLE)
    qty_none, factor_none, conf_none, status_none = apply_seasonality_and_clamp(
        base_quantity=base_qty,
        p25_quantity=p25_qty,
        category="Tinturas",
        calendar_month=1,
        provider=None,
    )

    # Assert
    assert factor_high == pytest.approx(1.10)
    assert qty_high == 44
    assert qty_high <= p25_qty
    assert conf_high == "ALTA"
    assert status_high == "APPLIED"

    assert factor_low == pytest.approx(0.90)
    assert qty_low == 36
    assert qty_low <= p25_qty
    assert status_low == "APPLIED"

    assert factor_baixa == pytest.approx(1.00)
    assert qty_baixa == base_qty
    assert conf_baixa == "BAIXA"
    assert status_baixa == "FALLBACK_NEUTRAL"

    assert factor_none == pytest.approx(1.00)
    assert qty_none == base_qty
    assert status_none in ("UNAVAILABLE", "FALLBACK_NEUTRAL")


def test_seasonality_never_exceeds_p25_clamp():
    """P-146.4 / P-145.3: Mesmo com fator 1.10, quantidade final nunca ultrapassa P25."""
    # Arrange: se base fosse próximo de P25 (ex: P25=10, base=10), 10 * 1.10 = 11 > 10 -> trava em 10
    qty, factor, _, _ = apply_seasonality_and_clamp(
        base_quantity=10,
        p25_quantity=10,
        category="Tinturas",
        calendar_month=3,
        provider=_StubSeasonalityProvider(index=1.40, confidence="ALTA"),
    )
    assert qty <= 10


def test_mature_ceiling():
    """P-147: tetoMaduroP75 reflete o P75 das vendas mensais dos produtos antigos (< 2025-04-01) do mesmo tipo."""
    # Arrange
    mature_rows = [
        {"sku": 8001, "tipo": "Tinturas", "first_sale_date": date(2025, 1, 10), "net_quantity": 100},
        {"sku": 8002, "tipo": "Tinturas", "first_sale_date": date(2025, 2, 1), "net_quantity": 150},
        {"sku": 8003, "tipo": "Tinturas", "first_sale_date": date(2025, 3, 15), "net_quantity": 200},
        {"sku": 8004, "tipo": "Tinturas", "first_sale_date": date(2025, 1, 20), "net_quantity": 300},
        # Produto novo (>= 2025-04-01) não deve entrar no teto maduro
        {"sku": 8099, "tipo": "Tinturas", "first_sale_date": date(2025, 5, 1), "net_quantity": 9999},
        # Produto maduro de outro tipo não deve entrar
        {"sku": 8098, "tipo": "Capsulas", "first_sale_date": date(2025, 1, 10), "net_quantity": 5000},
    ]
    df_mature = pd.DataFrame(mature_rows)

    # Act
    teto = compute_mature_ceiling(mature_df=df_mature, tipo="Tinturas")

    # Assert
    expected_p75 = int(round(float(np.percentile([100, 150, 200, 300], 75))))
    assert teto == expected_p75


def test_financial_margin_viability():
    """P-148: viavel true/false conforme margemMinimaDesejada; None se não informada; borda custo == preco."""
    # Arrange & Act 1: margem 55.06% >= 50.0% -> viavel = True
    res_ok = evaluate_financial_viability(
        preco_venda=42.50,
        custo_unitario=19.10,
        margem_minima_desejada=0.50,
    )
    # Act 2: margem 20.0% < 35.0% -> viavel = False
    res_fail = evaluate_financial_viability(
        preco_venda=50.00,
        custo_unitario=40.00,
        margem_minima_desejada=0.35,
    )
    # Act 3: sem margemMinimaDesejada -> viavel = None
    res_no_min = evaluate_financial_viability(
        preco_venda=50.00,
        custo_unitario=25.00,
        margem_minima_desejada=None,
    )
    # Act 4: borda custoUnitario == precoVendaPrevisto -> margem 0.00
    res_zero = evaluate_financial_viability(
        preco_venda=40.00,
        custo_unitario=40.00,
        margem_minima_desejada=0.10,
    )

    # Assert
    assert res_ok.viavel is True
    assert res_ok.margem_bruta_unitaria == pytest.approx(23.40, abs=1e-2)
    assert res_ok.margem_bruta_percentual == pytest.approx(23.40 / 42.50, abs=1e-4)

    assert res_fail.viavel is False
    assert res_fail.margem_bruta_percentual == pytest.approx(0.20, abs=1e-4)

    assert res_no_min.viavel is None
    assert res_no_min.margem_bruta_unitaria == pytest.approx(25.00, abs=1e-2)

    assert res_zero.margem_bruta_unitaria == pytest.approx(0.00, abs=1e-4)
    assert res_zero.margem_bruta_percentual == pytest.approx(0.00, abs=1e-4)
    assert res_zero.viavel is False


def test_backtest_calibration():
    """P-145.5: Backtest leave-one-out sobre lançamentos sintéticos comprova taxa de sucesso >= 80%."""
    # Arrange: 10 lançamentos reais sintéticos no mesmo tipo com dispersão realista
    volumes = [
        [25, 30, 35],
        [45, 55, 65],
        [50, 60, 70],
        [55, 65, 75],
        [60, 70, 80],
        [65, 75, 85],
        [70, 85, 95],
        [80, 95, 110],
        [90, 105, 120],
        [100, 120, 140],
    ]
    dfs = [
        _make_launch_df(
            sku=9000 + i,
            tipo="Tinturas",
            fornecedor="FITOHERB LABORATORIOS" if i % 2 == 0 else "HERBAL BRASIL",
            descricao=f"Tintura Fitoterapica Padrao {i} 50ml",
            preco=35.0 + i,
            first_sale=date(2025, 5, 1),
            monthly_quantities=q,
        )
        for i, q in enumerate(volumes)
    ]
    df = pd.concat(dfs, ignore_index=True)

    # Act
    report = run_backtest_calibration(df, reference_date=date(2026, 11, 1))

    # Assert
    assert report.total_evaluated >= 8
    assert report.success_rate >= MIN_BACKTEST_SUCCESS_RATE


def test_select_similars_from_affinities_and_risk_and_price_range():
    """Reutiliza matches do product_affinity_service para similares, faixa de preço e risco de canibalização."""
    from src.modules.analytics.domain.new_product import (
        compute_cannibalization_risk,
        compute_reference_price_range,
        select_similars_from_affinities,
    )

    affinity_matches = [
        {
            "sku": "112225",
            "description": "WHEY 100% PURE 900 GRS GELATO DI LATTE SACO",
            "supplier": "INTEGRALMEDICA",
            "category": "LINHA INTEGRALMEDICA",
            "currentPrice": 219.90,
            "affinityScore": 0.88,
        },
        {
            "sku": "770152",
            "description": "100% WHEY DOUBLE TASTY POTE 900G BAUNILHA",
            "supplier": "MAX TITANIUM",
            "category": "LINHA MAX TITANIUM",
            "currentPrice": 149.90,
            "affinityScore": 0.72,
        },
        {
            "sku": "840130",
            "description": "WHEY DOUBLE POTE 900G COOKIES",
            "supplier": "FITOWAY",
            "category": "LINHA FITOWAY",
            "currentPrice": 129.90,
            "affinityScore": 0.61,
        },
    ]

    launches = pd.concat(
        [
            _make_launch_df(112225, "LINHA INTEGRALMEDICA", "INTEGRALMEDICA", "WHEY 100% PURE 900 GRS GELATO DI LATTE SACO", 219.90, date(2025, 6, 1), [25, 30, 28]),
            _make_launch_df(770152, "LINHA MAX TITANIUM", "MAX TITANIUM", "100% WHEY DOUBLE TASTY POTE 900G BAUNILHA", 149.90, date(2025, 6, 2), [12, 12, 24]),
            _make_launch_df(840130, "LINHA FITOWAY", "FITOWAY", "WHEY DOUBLE POTE 900G COOKIES", 129.90, date(2025, 7, 1), [8, 10, 9]),
        ],
        ignore_index=True,
    )

    similars = select_similars_from_affinities(
        affinity_matches=affinity_matches,
        launches_df=launches,
        fornecedor="MAX TITANIUM",
        preco_venda_previsto=220.0,
    )
    assert len(similars) == 3
    # Produto de maior afinidade + preço quase idêntico (Integralmedica) vence em #1
    assert similars[0].sku == 112225
    assert similars[0].affinity_score == pytest.approx(0.88, abs=1e-4)

    curve = compute_conservative_curve(similars, horizon_months=3)
    assert all(p.conservative_quantity <= p.similar_p25_quantity for p in curve)

    price_range = compute_reference_price_range(affinity_matches, preco_venda_previsto=220.0)
    assert price_range is not None
    assert price_range.min_price == pytest.approx(129.90)
    assert price_range.max_price == pytest.approx(219.90)
    assert price_range.price_position == "NA_FAIXA"
    assert price_range.sample_size == 3

    risk = compute_cannibalization_risk(affinity_matches, target_fornecedor="MAX TITANIUM")
    assert risk.risk_level == "ALTO"
    assert risk.affected_sku_count == 3
    assert risk.same_supplier_affected_count == 1
    assert risk.cross_supplier_affected_count == 2
    assert len(risk.top_at_risk_products) == 3


def test_find_similar_for_new_product_applies_compatibility_guards(tmp_path):
    """product_affinity_service.find_similar_for_new_product bloqueia barra proteica e pré-treino ao buscar Whey em pó."""
    from src.modules.analytics.service import product_affinity_service as aff_svc

    fake_catalog = {
        "1001": {"description": "WHEY 100% PURE POTE 900G BAUNILHA", "supplier": "INTEGRALMEDICA", "category": "LINHA INTEGRALMEDICA", "current_price": 219.90, "active": True},
        "1002": {"description": "100% WHEY PROTEIN POTE 900G CHOCOLATE", "supplier": "MAX TITANIUM", "category": "LINHA MAX TITANIUM", "current_price": 179.90, "active": True},
        "1003": {"description": "WHEY BAR 12X45G COOKIES", "supplier": "BLACK SKULL", "category": "LINHA BLACK SKULL", "current_price": 89.90, "active": True},
        "1004": {"description": "HORUS PRE WORKOUT 150G CITRUS", "supplier": "MAX TITANIUM", "category": "LINHA MAX TITANIUM", "current_price": 79.90, "active": True},
    }
    index_file = tmp_path / "product_affinity_index.json"
    aff_svc.reset_product_affinity_memory_cache()
    aff_svc.sync_product_affinity_index(
        force=True,
        index_path=index_file,
        catalog_loader=lambda: fake_catalog,
        gallery_loader=lambda: [],
    )
    results = aff_svc.find_similar_for_new_product(
        name="WHEY 100% POTE 900G GELATO",
        description="WHEY 100% POTE 900G GELATO",
        top_k=10,
        index_path=index_file,
    )
    aff_svc.reset_product_affinity_memory_cache()

    returned_skus = {item["sku"] for item in results}
    assert "1001" in returned_skus or "1002" in returned_skus
    assert "1003" not in returned_skus  # barra proteica bloqueada pela trava estrutural
    assert "1004" not in returned_skus  # pré-treino bloqueado pela trava estrutural


def test_brand_sales_strength_impacts_actual_conservative_forecast_quantity():
    """Força comercial real da marca impacta diretamente a quantidade prevista (Integral > Max > Probiótica) respeitando Q <= P25."""
    from src.modules.analytics.domain.new_product import SimilarProductMatch

    similars = [
        SimilarProductMatch(1, "WHEY A", "INTEGRALMEDICA", date(2025, 6, 1), 220.0, 0.90, 0.0, 1.0, 0.9, (40, 45, 50), 0.95),
        SimilarProductMatch(2, "WHEY B", "MAX TITANIUM", date(2025, 6, 1), 180.0, 0.80, 0.0, 0.8, 0.8, (30, 35, 40), 0.85),
        SimilarProductMatch(3, "WHEY C", "PROBIOTICA", date(2025, 6, 1), 170.0, 0.75, 0.0, 0.8, 0.75, (20, 25, 30), 0.75),
    ]
    sup_avg = {
        "integralmedica": 2500.0,
        "max titanium": 900.0,
        "probiotica": 250.0,
    }

    curve_int = compute_conservative_curve(similars, horizon_months=3, supplier_avg_monthly=sup_avg, target_fornecedor="INTEGRALMEDICA")
    curve_max = compute_conservative_curve(similars, horizon_months=3, supplier_avg_monthly=sup_avg, target_fornecedor="MAX TITANIUM")
    curve_pro = compute_conservative_curve(similars, horizon_months=3, supplier_avg_monthly=sup_avg, target_fornecedor="PROBIOTICA")

    tot_int = sum(p.conservative_quantity for p in curve_int)
    tot_max = sum(p.conservative_quantity for p in curve_max)
    tot_pro = sum(p.conservative_quantity for p in curve_pro)

    assert tot_int > tot_max > tot_pro
    assert all(p.conservative_quantity <= p.similar_p25_quantity for p in curve_int + curve_max + curve_pro)
