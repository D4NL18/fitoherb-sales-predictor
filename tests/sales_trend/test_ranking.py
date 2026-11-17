"""
Testes para ranking, filtros, visões e desempate de produtos (T-05).
Valida regras P-072, P-080, P-081, CA-12..CA-18, C-20, C-21, AR-1, AR-9.
"""
from decimal import Decimal
import pytest

from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    LAST_COVERED_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
)


def _setup_context():
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text

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
    return catalog_entries, monthly_sales


def test_ranking_universe_active_skus_only():
    """Valida que o universo de produtos contém apenas SKUs ativos com movimento em [M-23, M]."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.ranking import filter_and_rank_products

    catalog, ms = _setup_context()
    base_idx = month_index(2026, 10)

    # SKU 1010 tem venda só em nov/26 (depois de out/26). Não deve aparecer em out/26 (C-32).
    # SKUs 1008 e 1009 nunca entram.
    result = filter_and_rank_products(
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

    skus = [item.sku for item in result.items]
    assert 1008 not in skus
    assert 1009 not in skus
    assert 1010 not in skus, "SKU 1010 teve venda só depois de out/26 e não deve aparecer"
    assert set(skus) == {1001, 1002, 1003, 1004, 1005, 1006, 1007}


def test_views_and_totais_por_visao():
    """Valida contagem de totaisPorVisao e filtro por view (all, rising, falling, new)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.ranking import filter_and_rank_products

    catalog, ms = _setup_context()
    base_idx = month_index(2026, 10)

    # Em out/26, 1m (quantity):
    # 1001 (+50%), 1007 (+200%) -> rising (2)
    # 1003 (-100%), 1004 (-100%) -> falling (2)
    # 1002 (0 -> 40), 1005 (0 -> 10 com piso zero) -> new (2)
    # 1006 (0 -> 0) -> sem_movimento (1)
    # Total de itens = 7. rising=2, falling=2, new=2.
    res_all = filter_and_rank_products(
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
    assert res_all.totais_por_visao.total == 7
    assert res_all.totais_por_visao.rising == 2
    assert res_all.totais_por_visao.falling == 2
    assert res_all.totais_por_visao.new == 2

    res_rising = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="rising",
        q=None,
        min_volume=0.0,
        last_covered_day=LAST_COVERED_DATE,
    )
    assert len(res_rising.items) == 2
    assert {it.sku for it in res_rising.items} == {1001, 1007}

    res_falling = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="falling",
        q=None,
        min_volume=0.0,
        last_covered_day=LAST_COVERED_DATE,
    )
    assert len(res_falling.items) == 2
    assert {it.sku for it in res_falling.items} == {1003, 1004}


def test_sorting_order_and_tie_breaking():
    """Valida grupos de ordenação VARIACAO -> NOVO -> SEM_BASE -> SEM_MOVIMENTO e desempate por perda absoluta (C-20, C-21, AR-1)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.ranking import filter_and_rank_products

    catalog, ms = _setup_context()
    base_idx = month_index(2026, 10)

    # Ordenação desc em 1m:
    # 1007 (+200%), 1001 (+50%), 1003 (-100%, perda 50), 1004 (-100%, perda 20), NOVO (1002, 1005), SEM_MOVIMENTO (1006)
    res_desc = filter_and_rank_products(
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
    skus_desc = [it.sku for it in res_desc.items]
    assert skus_desc[:4] == [1007, 1001, 1003, 1004]  # 1003 perdeu 50 vs 1004 que perdeu 20
    assert set(skus_desc[4:6]) == {1002, 1005}
    assert skus_desc[6] == 1006


def test_search_query_filter():
    """Valida busca por texto ou código de produto (CA-17)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.ranking import filter_and_rank_products

    catalog, ms = _setup_context()
    base_idx = month_index(2026, 10)

    # "cha" casa com 1001 (CHÁ VERDE) e 1004 (CHÁ BRANCO)
    res_cha = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="all",
        q="cha",
        min_volume=0.0,
        last_covered_day=LAST_COVERED_DATE,
    )
    assert {it.sku for it in res_cha.items} == {1001, 1004}

    # "1003" casa com 1003 (GUARANÁ EM PÓ)
    res_code = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="all",
        q="1003",
        min_volume=0.0,
        last_covered_day=LAST_COVERED_DATE,
    )
    assert [it.sku for it in res_code.items] == [1003]


def test_min_volume_filter():
    """Valida filtro minVolume (remove apenas VARIACAO com volume anterior inferior)."""
    from src.modules.sales_trend.domain.month_windows import month_index
    from src.modules.sales_trend.domain.ranking import filter_and_rank_products

    catalog, ms = _setup_context()
    base_idx = month_index(2026, 10)

    # 1007 tinha 1 un na anterior. min_volume=10 deve filtrá-lo, mas manter 1001 (20 un)
    res_vol = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=base_idx,
        metric="quantity",
        sort_window=1,
        sort_dir="desc",
        view="all",
        q=None,
        min_volume=10.0,
        last_covered_day=LAST_COVERED_DATE,
    )
    skus = {it.sku for it in res_vol.items}
    assert 1001 in skus
    assert 1007 not in skus
