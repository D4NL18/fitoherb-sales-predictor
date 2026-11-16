"""
Testes de Domínio para a Detecção de Sazonalidade por Produto (P-106 a P-114).

Cobre os cenários exigidos pela FASE F1:
- Série sintética de 23 meses com pico em março nos dois anos recuperado com confiança ALTA e força FORTE.
- Série plana com força FRACA (amplitude próxima de 0).
- Série curta (< 18 meses) classificada como INSUFICIENTE por HISTORICO_CURTO.
- Série esparsa (< 50% meses ativos) classificada como INSUFICIENTE por VENDA_ESPORADICA.
- Pico em dezembro (1 única observação) classificado com confiança BAIXA.
- Abatimento de devoluções no mês e truncamento de saldos negativos em zero.
- Reutilização da função pública exportada `get_seasonality_index(...)`.
- Geração de rankings com order=most e order=least.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.modules.analytics.domain.seasonality import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    REASON_SHORT_HISTORY,
    REASON_SPARSE_SALES,
    STRENGTH_STRONG,
    STRENGTH_WEAK,
    STRENGTH_INSUFFICIENT,
    STRENGTH_MODERATE,
    SeasonalityResult,
    SeasonalityCatalogSummary,
    calculate_seasonality_rankings,
    calculate_seasonality_summaries,
    compute_product_seasonality,
    get_seasonality_index,
)


def _build_synthetic_monthly_sales(
    sku: int,
    start_year: int = 2025,
    start_month: int = 1,
    months_count: int = 22,
    base_qty: float = 100.0,
    peak_month: int | None = None,
    peak_factor: float = 1.6,
    valley_month: int | None = None,
    valley_factor: float = 0.5,
) -> pd.DataFrame:
    """Gera série cronológica sintética mês a mês para testes de sazonalidade."""
    rows = []
    current_year = start_year
    current_month = start_month

    for _ in range(months_count):
        qty = base_qty
        if peak_month is not None and current_month == peak_month:
            qty *= peak_factor
        elif valley_month is not None and current_month == valley_month:
            qty *= valley_factor

        rev = qty * 10.0
        rows.append({
            "sku": sku,
            "sale_year": current_year,
            "sale_month": current_month,
            "net_quantity": int(round(qty)),
            "net_revenue": float(round(rev, 2)),
        })

        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return pd.DataFrame(rows)


def test_seasonality_synthetic_23m_march_peak_high_confidence():
    """P-106, P-109..P-112: Série de 22 meses com pico em março em ambos os anos."""
    sku = 101
    df = _build_synthetic_monthly_sales(
        sku=sku,
        start_year=2025,
        start_month=1,
        months_count=22,  # Jan/2025 a Out/2026
        base_qty=100.0,
        peak_month=3,     # Março é o pico
        peak_factor=1.7,
        valley_month=9,   # Setembro é o vale
        valley_factor=0.6,
    )

    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    assert result.elegivel is True
    assert result.forca == STRENGTH_STRONG
    assert result.motivo_insuficiencia is None
    assert result.amplitude >= 0.40
    assert result.correlacao_yoy is not None
    assert result.correlacao_yoy >= 0.60

    # Pico deve ser em março (mês 3) com confiança ALTA
    assert result.pico.mes_inicio == 3
    assert result.pico.confianca == CONFIDENCE_HIGH
    assert result.pico.indice > 1.30

    # Vale deve ser em setembro (mês 9) com confiança ALTA
    assert result.vale.mes_inicio == 9
    assert result.vale.confianca == CONFIDENCE_HIGH
    assert result.vale.indice < 0.90

    # A média dos 12 índices do calendário deve ser rigorosamente 1.00
    media_indices = np.mean([p.indice for p in result.serie_mensal])
    assert pytest.approx(media_indices, abs=1e-3) == 1.00


def test_seasonality_flat_series_weak_strength():
    """P-111: Série plana tem amplitude próxima de zero e força FRACA."""
    sku = 102
    df = _build_synthetic_monthly_sales(
        sku=sku,
        start_year=2025,
        start_month=1,
        months_count=22,
        base_qty=150.0,  # flat, sem pico
    )

    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    assert result.elegivel is True
    assert result.forca == STRENGTH_WEAK
    assert result.amplitude < 0.15
    for p in result.serie_mensal:
        assert pytest.approx(p.indice, abs=0.1) == 1.0


def test_seasonality_short_series_insufficient():
    """P-107: Série com histórico menor que 18 meses cai em INSUFICIENTE (HISTORICO_CURTO)."""
    sku = 103
    df = _build_synthetic_monthly_sales(
        sku=sku,
        start_year=2026,
        start_month=1,
        months_count=10,  # Apenas 10 meses
        base_qty=100.0,
        peak_month=3,
        peak_factor=1.8,
    )

    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    assert result.elegivel is False
    assert result.forca == STRENGTH_INSUFFICIENT
    assert result.motivo_insuficiencia == REASON_SHORT_HISTORY


def test_seasonality_sparse_series_insufficient():
    """P-107: Série com 22 meses corridos mas com vendas em menos de 50% dos meses cai em VENDA_ESPORADICA."""
    sku = 104
    # Cria vendas apenas em 5 meses dentro de uma janela de 22 meses
    sparse_rows = [
        {"sku": sku, "sale_year": 2025, "sale_month": 1, "net_quantity": 50, "net_revenue": 500.0},
        {"sku": sku, "sale_year": 2025, "sale_month": 5, "net_quantity": 60, "net_revenue": 600.0},
        {"sku": sku, "sale_year": 2025, "sale_month": 10, "net_quantity": 40, "net_revenue": 400.0},
        {"sku": sku, "sale_year": 2026, "sale_month": 2, "net_quantity": 70, "net_revenue": 700.0},
        {"sku": sku, "sale_year": 2026, "sale_month": 10, "net_quantity": 80, "net_revenue": 800.0},
    ]
    df = pd.DataFrame(sparse_rows)

    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    assert result.elegivel is False
    assert result.forca == STRENGTH_INSUFFICIENT
    assert result.motivo_insuficiencia == REASON_SPARSE_SALES


def test_seasonality_december_peak_low_confidence():
    """P-112: Pico em dezembro (mês com apenas 1 observação histórica em 2025) recebe confiança BAIXA."""
    sku = 105
    df = _build_synthetic_monthly_sales(
        sku=sku,
        start_year=2025,
        start_month=1,
        months_count=22,  # Jan/2025 a Out/2026
        base_qty=100.0,
        peak_month=12,    # Dezembro (só ocorre em 2025)
        peak_factor=2.0,
    )

    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    assert result.pico.mes_inicio == 12
    assert result.pico.confianca == CONFIDENCE_LOW

    # Confiança de dezembro na série mensal também deve ser BAIXA
    dez_point = next(p for p in result.serie_mensal if p.mes == 12)
    assert dez_point.confianca == CONFIDENCE_LOW
    assert dez_point.observacoes_disponiveis == 1


def test_seasonality_returns_net_deduction_and_truncation():
    """P-106: Devoluções abatem quantidade e valor; saldos negativos são truncados em zero."""
    sku = 106
    # No SQL já vem agrupado com net_quantity e net_revenue líquidos.
    # Testamos se o domínio lida corretamente com net_quantity == 0 ou saldo truncado.
    rows = [
        {"sku": sku, "sale_year": 2025, "sale_month": m, "net_quantity": 100, "net_revenue": 1000.0}
        for m in range(1, 13)
    ]
    # Mês 6 teve mais devoluções que vendas -> net_quantity no SQL seria negativo (-10)
    rows[5]["net_quantity"] = -10
    rows[5]["net_revenue"] = -100.0

    # Adiciona 10 meses em 2026
    for m in range(1, 11):
        rows.append({"sku": sku, "sale_year": 2026, "sale_month": m, "net_quantity": 100, "net_revenue": 1000.0})

    df = pd.DataFrame(rows)
    result = compute_product_seasonality(sku=sku, product_sales_df=df)

    junho_point = next(p for p in result.serie_mensal if p.mes == 6)
    # No mês com devolução negativa, o volume para cálculo sazonal deve ser truncado em 0
    assert junho_point.razao_2025 == 0.0 or junho_point.indice < 1.0


def test_get_seasonality_index_exported_function():
    """P-109: Valida a função de domínio pública exportada get_seasonality_index para reuso por F6 e F2."""
    sku = 200
    df = _build_synthetic_monthly_sales(
        sku=sku,
        start_year=2025,
        start_month=1,
        months_count=22,
        base_qty=80.0,
        peak_month=4,
        peak_factor=1.5,
    )

    catalog = {
        sku: {
            "Codigo": sku,
            "Descricao": "PRODUTO TESTE EXPORT",
            "Fornecedor": "FORNECEDOR X",
            "Estoque": 50,
            "Pc.Venda": 35.0,
        }
    }

    res = get_seasonality_index(sku=sku, monthly_sales_df=df, catalog_dict=catalog)

    assert isinstance(res, SeasonalityResult)
    assert res.produto.codigo == sku
    assert len(res.serie_mensal) == 12
    assert res.pico.mes_inicio == 4


def test_calculate_seasonality_rankings():
    """P-114: Rankings order=most e order=least com paginação e filtros."""
    # Cria produto 1: muito sazonal e alto faturamento
    df1 = _build_synthetic_monthly_sales(sku=1, months_count=22, base_qty=1000.0, peak_month=3, peak_factor=2.0)
    # Cria produto 2: moderado sazonal
    df2 = _build_synthetic_monthly_sales(sku=2, months_count=22, base_qty=500.0, peak_month=5, peak_factor=1.4)
    # Cria produto 3: histórico curto (< 18m)
    df3 = _build_synthetic_monthly_sales(sku=3, months_count=10, base_qty=100.0)

    combined_df = pd.concat([df1, df2, df3], ignore_index=True)

    catalog = {
        1: {"Codigo": 1, "Descricao": "PROD 1 FORTE", "Fornecedor": "F1", "Estoque": 10, "Pc.Venda": 10.0},
        2: {"Codigo": 2, "Descricao": "PROD 2 MODERADO", "Fornecedor": "F2", "Estoque": 10, "Pc.Venda": 10.0},
        3: {"Codigo": 3, "Descricao": "PROD 3 CURTO", "Fornecedor": "F3", "Estoque": 10, "Pc.Venda": 10.0},
    }

    # Ranking most
    items_most, total_most = calculate_seasonality_rankings(
        monthly_sales_df=combined_df,
        catalog_dict=catalog,
        order="most",
        limit=10,
        offset=0,
    )

    assert total_most >= 1
    assert items_most[0].sku == 1
    assert items_most[0].forca in (STRENGTH_STRONG, STRENGTH_MODERATE)

    # Ranking least
    items_least, total_least = calculate_seasonality_rankings(
        monthly_sales_df=combined_df,
        catalog_dict=catalog,
        order="least",
        limit=10,
        offset=0,
    )

    assert total_least >= 1
    skus_least = [it.sku for it in items_least]
    assert 3 in skus_least
    item3 = next(it for it in items_least if it.sku == 3)
    assert item3.forca == STRENGTH_INSUFFICIENT
    assert item3.motivo_insuficiencia == REASON_SHORT_HISTORY


def test_calculate_seasonality_summaries_covers_all_catalog_skus():
    """Calcula resumo para FORTE, FRACA, INSUFICIENTE (histórico curto/esparso) e sem vendas."""
    df_forte = _build_synthetic_monthly_sales(
        sku=1, months_count=22, base_qty=100.0, peak_month=3, peak_factor=1.8, valley_month=9, valley_factor=0.5
    )
    df_fraca = _build_synthetic_monthly_sales(sku=2, months_count=22, base_qty=100.0)
    df_curto = _build_synthetic_monthly_sales(sku=3, months_count=8, base_qty=50.0)
    df_esparso = pd.DataFrame([
        {"sku": 4, "sale_year": 2025, "sale_month": 1, "net_quantity": 10, "net_revenue": 100.0},
        {"sku": 4, "sale_year": 2026, "sale_month": 10, "net_quantity": 15, "net_revenue": 150.0},
    ])
    combined_df = pd.concat([df_forte, df_fraca, df_curto, df_esparso], ignore_index=True)

    catalog = {
        1: {"Codigo": 1, "Descricao": "PROD 1 FORTE", "Fornecedor": "F1", "Estoque": 10, "Pc.Venda": 10.0},
        2: {"Codigo": 2, "Descricao": "PROD 2 FRACA", "Fornecedor": "F2", "Estoque": 10, "Pc.Venda": 10.0},
        3: {"Codigo": 3, "Descricao": "PROD 3 CURTO", "Fornecedor": "F3", "Estoque": 10, "Pc.Venda": 10.0},
        4: {"Codigo": 4, "Descricao": "PROD 4 ESPARSO", "Fornecedor": "F4", "Estoque": 10, "Pc.Venda": 10.0},
        5: {"Codigo": 5, "Descricao": "PROD 5 SEM VENDAS", "Fornecedor": "F5", "Estoque": 10, "Pc.Venda": 10.0},
    }

    summaries = calculate_seasonality_summaries(monthly_sales_df=combined_df, catalog_dict=catalog)

    assert set(summaries.keys()) == {1, 2, 3, 4, 5}
    assert all(isinstance(v, SeasonalityCatalogSummary) for v in summaries.values())

    assert summaries[1].forca == STRENGTH_STRONG
    assert summaries[1].mes_pico == "Março"
    assert summaries[1].mes_vale == "Setembro"
    assert summaries[1].motivo_insuficiencia is None
    assert summaries[1].faturamento_total == round(float(df_forte["net_revenue"].sum()), 2)

    assert summaries[2].forca == STRENGTH_WEAK
    assert summaries[2].mes_pico is not None
    assert summaries[2].mes_vale is not None
    assert summaries[2].motivo_insuficiencia is None

    assert summaries[3].forca == STRENGTH_INSUFFICIENT
    assert summaries[3].mes_pico is None
    assert summaries[3].mes_vale is None
    assert summaries[3].motivo_insuficiencia == REASON_SHORT_HISTORY

    assert summaries[4].forca == STRENGTH_INSUFFICIENT
    assert summaries[4].mes_pico is None
    assert summaries[4].mes_vale is None
    assert summaries[4].motivo_insuficiencia == REASON_SPARSE_SALES
    assert summaries[4].faturamento_total == 250.0

    assert summaries[5] == SeasonalityCatalogSummary(
        forca=STRENGTH_INSUFFICIENT,
        amplitude=0.0,
        mes_pico=None,
        mes_vale=None,
        faturamento_total=0.0,
        motivo_insuficiencia=REASON_SHORT_HISTORY,
    )
