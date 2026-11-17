"""
Autoteste da fixture e validação da massa sintética de Tendência de Vendas (T-01).
Verifica a integridade dos dados sintéticos antes do uso pelas suítes de teste.
"""
from decimal import Decimal
import pytest

from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    LAST_COVERED_DATE,
    REFERENCE_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
    generate_large_supplier_sample,
)


def test_active_catalog_sample_integrity():
    """Valida que o catálogo sintético reflete estritamente os produtos ativos (P-072.2)."""
    catalog = get_active_catalog_sample()
    assert len(catalog) == 8
    assert 1008 not in catalog, "SKU 1008 descontinuado não deve estar no catálogo ativo"
    assert 1009 not in catalog, "SKU 1009 sem cadastro não deve estar no catálogo ativo"
    assert catalog[1001]["fornecedor"] == "LABORATÓRIO ALFA"
    assert catalog[1004]["fornecedor"] is None
    assert catalog[1006]["fornecedor"] == "   "


def test_raw_sales_rows_sample_integrity():
    """Valida as linhas brutas sintéticas com SKUs ativos, inativo 1008 e não cadastrado 1009."""
    rows = get_raw_sales_rows_sample()
    skus = {r.sku for r in rows}
    assert 1008 in skus, "SKU 1008 deve existir no agregado bruto para testar descarte"
    assert 1009 in skus, "SKU 1009 deve existir no agregado bruto para testar descarte"
    assert 1001 in skus

    # Verifica valores de 1001 em set/26 (202609) e out/26 (202610)
    row_sep_26 = next(r for r in rows if r.sku == 1001 and r.year_month == 202609)
    assert row_sep_26.quantity == Decimal("20.0")
    assert row_sep_26.revenue == Decimal("200.0")

    row_oct_26 = next(r for r in rows if r.sku == 1001 and r.year_month == 202610)
    assert row_oct_26.quantity == Decimal("30.0")
    assert row_oct_26.revenue == Decimal("360.0")


def test_large_supplier_sample_generation():
    """Valida gerador de fornecedor com 120 SKUs para testes de paginação (CA-39)."""
    catalog, rows = generate_large_supplier_sample("LABORATÓRIO GIGANTE", 120)
    assert len(catalog) == 120
    assert len(rows) == 240  # 120 SKUs x 2 meses (set/26 e out/26)
    assert all(cat["fornecedor"] == "LABORATÓRIO GIGANTE" for cat in catalog.values())


def test_build_monthly_sales_discards_inactive():
    """
    Testa se build_monthly_sales descarta SKUs 1008 e 1009 mantendo first_sale_date global (AR-12).
    Falha inicialmente se o módulo de domínio ainda não foi implementado (TDD Red).
    """
    from src.modules.sales_trend.domain.sales_trend import build_monthly_sales

    catalog = get_active_catalog_sample()
    raw_rows = get_raw_sales_rows_sample()

    monthly_sales = build_monthly_sales(
        rows=[(r.sku, r.year_month, r.quantity, r.revenue) for r in raw_rows],
        active_skus=set(catalog.keys()),
        first_sale_date=FIRST_SALE_DATE,
    )

    assert 1008 not in monthly_sales.series, "SKU 1008 deve ter sido descartado"
    assert 1009 not in monthly_sales.series, "SKU 1009 deve ter sido descartado"
    assert 1001 in monthly_sales.series
    assert monthly_sales.first_sale_date == FIRST_SALE_DATE
