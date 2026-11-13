"""
Testes para agrupamento por fornecedor, soma líquida e contribuição (T-06).
Valida regras P-088 a P-092, CA-28 a CA-39, C-35, C-36, C-37, C-44, C-47, AR-4, AR-10.
"""
from decimal import Decimal
import pytest

from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    LAST_COVERED_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
    generate_large_supplier_sample,
)


def _setup_suppliers():
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text
    from src.modules.sales_trend.domain.suppliers import build_supplier_index

    raw_cat = get_active_catalog_sample()
    catalog_entries = {
        sku: TrendCatalogEntry(
            codigo=sku,
            descricao=data["descricao"],
            fornecedor=data["fornecedor"],
            descricao_normalizada=normalize_text(data["descricao"]),
        )
        for sku, data in raw_cat.items()
    }
    raw_rows = get_raw_sales_rows_sample()
    monthly_sales = build_monthly_sales(
        rows=[(r.sku, r.year_month, r.quantity, r.revenue) for r in raw_rows],
        active_skus=set(catalog_entries.keys()),
        first_sale_date=FIRST_SALE_DATE,
    )
    supplier_index = build_supplier_index(catalog_entries)
    return catalog_entries, monthly_sales, supplier_index


def test_supplier_net_sum_variation_ca28_ca31():
    """Valida CA-28 a CA-31: % do fornecedor sobre a soma líquida e tratamento de 'Sem fornecedor'."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.suppliers import get_suppliers_trend

    catalog, ms, s_idx = _setup_suppliers()
    base_idx = month_index(2026, 10)

    res = get_suppliers_trend(
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="all",
        q=None,
        min_volume=0.0,
        last_covered_day=LAST_COVERED_DATE,
    )

    by_key = {s.supplier_key: s for s in res.items}

    # 1. LABORATÓRIO ALFA (1001: 20->30, 1003: 50->0):
    # Soma: anterior = 70, atual = 30 -> (30 - 70) / 70 = -57.1% (NÃO a média das %)
    key_alfa = next(k for k in by_key if "alfa" in k)
    cell_alfa = by_key[key_alfa].janelas[1]
    assert cell_alfa.status == "VARIACAO"
    assert cell_alfa.variacao_pct == -57.1

    # 2. LABORATÓRIO BETA (1007: 1->3; 1008 inativo é excluído P-072.2)
    # Soma: anterior = 1, atual = 3 -> +200.0% com baseBaixa=True
    key_beta = next(k for k in by_key if "beta" in k)
    cell_beta = by_key[key_beta].janelas[1]
    assert cell_beta.status == "VARIACAO"
    assert cell_beta.variacao_pct == 200.0
    assert cell_beta.base_baixa is True

    # 3. LABORATÓRIO GAMA (1002: 0->40, 1005: -3->10 -> piso zero 0->10):
    # Anterior total = 0, Atual total = 50 -> status NOVO com devolucaoLiquida=True
    key_gama = next(k for k in by_key if "gama" in k)
    cell_gama = by_key[key_gama].janelas[1]
    assert cell_gama.status == "NOVO"
    assert cell_gama.devolucao_liquida is True

    # 4. Sem fornecedor (1004: 20-> -7 -> piso 0; 1006: 0->0):
    # Anterior = 20, Atual = 0 -> -100.0% com devolucaoLiquida=True
    cell_sem = by_key["sem-fornecedor"].janelas[1]
    assert cell_sem.status == "VARIACAO"
    assert cell_sem.variacao_pct == -100.0
    assert cell_sem.devolucao_liquida is True


def test_contribution_exact_closure_ca34_ca35():
    """Valida fecho da conta: Σ contribuicaoPp = variação % do fornecedor e Σ contribuicaoValor = delta (CA-34, CA-35)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.suppliers import (
        get_supplier_detail,
        get_suppliers_trend,
    )

    catalog, ms, s_idx = _setup_suppliers()
    base_idx = month_index(2026, 10)

    # Detalhe do LABORATÓRIO ALFA em 1m (quantity)
    key_alfa = next(k for k in s_idx.keys() if "alfa" in k)
    detail_alfa = get_supplier_detail(
        supplier_key=key_alfa,
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_by="contribution",
        sort_dir="asc",
        q=None,
        limit=50,
        offset=0,
        last_covered_day=LAST_COVERED_DATE,
    )

    # ALFA tem 1001 e 1003 (1010 só tem venda em nov/26 e não aparece em out/26)
    # Anterior total = 70. 1001: 20->30 (+10 un); 1003: 50->0 (-50 un).
    # 1001 contribuicaoPp = +10 / 70 = +14.2857% -> +14.3 p.p.
    # 1003 contribuicaoPp = -50 / 70 = -71.4285% -> -71.4 p.p.
    # Soma das frações exatas = -40 / 70 = -57.1428% -> -57.1% (fecho perfeito)
    c_pp_sum = sum(p.contribuicao_fracao for p in detail_alfa.items)
    from src.modules.sales_trend.domain.rounding import round_fraction_half_up
    assert round_fraction_half_up(c_pp_sum, 1) == -57.1

    c_val_sum = sum(p.contribuicao_valor for p in detail_alfa.items)
    assert c_val_sum == pytest.approx(-40.0)


def test_supplier_not_found_tnd003():
    """Valida que chave de fornecedor inexistente levanta SupplierNotFoundError (TND-003)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.exceptions import SupplierNotFoundError
    from src.modules.sales_trend.domain.suppliers import get_supplier_detail

    catalog, ms, s_idx = _setup_suppliers()
    base_idx = month_index(2026, 10)

    with pytest.raises(SupplierNotFoundError) as exc_info:
        get_supplier_detail(
            supplier_key="f:fornecedor-fantasma",
            supplier_index=s_idx,
            catalog=catalog,
            monthly_sales=ms,
            base_month_index=base_idx,
            metric="quantity",
            sort_by="contribution",
            sort_dir="desc",
            q=None,
            limit=20,
            offset=0,
            last_covered_day=LAST_COVERED_DATE,
        )
    assert exc_info.value.code == "TND-003"
    assert "supplierKey" in exc_info.value.fields


def test_supplier_detail_average_mode_contribution_closure():
    """Garante fecho exato de contribuicao_pp no modo average para janelas > 1."""
    from datetime import date
    from fractions import Decimal
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.rounding import round_fraction_half_up
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text
    from src.modules.sales_trend.domain.suppliers import (
        build_supplier_index,
        get_supplier_detail,
        get_suppliers_trend,
    )

    catalog = {
        2001: TrendCatalogEntry(2001, "PROD A", "LAB TESTE", normalize_text("PROD A")),
        2002: TrendCatalogEntry(2002, "PROD B", "LAB TESTE", normalize_text("PROD B")),
        2003: TrendCatalogEntry(2003, "PROD NOVO", "LAB TESTE", normalize_text("PROD NOVO")),
    }
    rows = [
        # 2001: jul-set = 10+20+30 = 60 (media 20), out = 45 -> +25
        (2001, 202607, Decimal("1"), Decimal("10.00")),
        (2001, 202608, Decimal("2"), Decimal("20.00")),
        (2001, 202609, Decimal("3"), Decimal("30.00")),
        (2001, 202610, Decimal("4"), Decimal("45.00")),
        # 2002: jul-set = 30+30+60 = 120 (media 40), out = 30 -> -10
        (2002, 202607, Decimal("3"), Decimal("30.00")),
        (2002, 202608, Decimal("3"), Decimal("30.00")),
        (2002, 202609, Decimal("6"), Decimal("60.00")),
        (2002, 202610, Decimal("3"), Decimal("30.00")),
        # 2003: vendido apenas em out/26 (+15 NOVO) -> soma out/26 = 90 vs media ant = 60 -> +50.0%
        (2003, 202610, Decimal("1"), Decimal("15.00")),
    ]
    ms = build_monthly_sales(rows, set(catalog.keys()), first_sale_date=date(2025, 1, 1))
    s_idx = build_supplier_index(catalog)
    base_idx = month_index(2026, 10)
    last_day = date(2026, 10, 31)

    sup_list = get_suppliers_trend(
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="revenue",
        sort_window=3,
        sort_dir="desc",
        view="all",
        q=None,
        min_volume=0.0,
        comparison_mode="average",
        last_covered_day=last_day,
    )
    assert len(sup_list.items) == 1
    assert sup_list.items[0].janelas[3].variacao_pct == 50.0

    detail = get_supplier_detail(
        supplier_key=sup_list.items[0].supplier_key,
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="revenue",
        sort_by="contribution",
        sort_dir="desc",
        sort_window=3,
        q=None,
        limit=20,
        offset=0,
        comparison_mode="average",
        last_covered_day=last_day,
    )
    by_sku = {item.sku: item for item in detail.items}
    assert by_sku[2001].contribuicao_pp == 41.7   # +25 / 60
    assert by_sku[2003].contribuicao_pp == 25.0   # +15 / 60
    assert by_sku[2002].contribuicao_pp == -16.7  # -10 / 60
    assert round_fraction_half_up(sum(i.contribuicao_fracao for i in detail.items), 1) == 50.0
    assert sum(i.contribuicao_valor for i in detail.items) == pytest.approx(30.0)


def test_supplier_detail_sort_by_variation_keeps_status_groups():
    """Ordenacao por variation mantem VARIACAO antes de NOVO (sem injetar None como 0%)."""
    from datetime import date
    from decimal import Decimal
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text
    from src.modules.sales_trend.domain.suppliers import (
        build_supplier_index,
        get_supplier_detail,
    )

    catalog = {
        3001: TrendCatalogEntry(3001, "ALTA", "LAB ORDEM", normalize_text("ALTA")),
        3002: TrendCatalogEntry(3002, "QUEDA", "LAB ORDEM", normalize_text("QUEDA")),
        3003: TrendCatalogEntry(3003, "LANCAMENTO", "LAB ORDEM", normalize_text("LANCAMENTO")),
    }
    rows = [
        (3001, 202609, Decimal("10"), Decimal("100.00")),
        (3001, 202610, Decimal("15"), Decimal("150.00")),  # +50%
        (3002, 202609, Decimal("10"), Decimal("100.00")),
        (3002, 202610, Decimal("8"), Decimal("80.00")),    # -20%
        (3003, 202610, Decimal("5"), Decimal("50.00")),    # NOVO
    ]
    ms = build_monthly_sales(rows, set(catalog.keys()), first_sale_date=date(2025, 1, 1))
    s_idx = build_supplier_index(catalog)
    key = next(iter(s_idx.keys()))
    base_idx = month_index(2026, 10)
    last_day = date(2026, 10, 31)

    desc_res = get_supplier_detail(
        supplier_key=key,
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="revenue",
        sort_by="variation",
        sort_dir="desc",
        sort_window=1,
        q=None,
        limit=20,
        offset=0,
        last_covered_day=last_day,
    )
    assert [i.sku for i in desc_res.items] == [3001, 3002, 3003]

    asc_res = get_supplier_detail(
        supplier_key=key,
        supplier_index=s_idx,
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="revenue",
        sort_by="variation",
        sort_dir="asc",
        sort_window=1,
        q=None,
        limit=20,
        offset=0,
        last_covered_day=last_day,
    )
    assert [i.sku for i in asc_res.items] == [3002, 3001, 3003]
