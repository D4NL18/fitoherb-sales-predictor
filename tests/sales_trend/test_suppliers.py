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
