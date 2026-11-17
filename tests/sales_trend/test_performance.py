"""
Teste de estresse e desempenho de memória e latência (T-13).
Executado fora da esteira padrão via mark slow.
"""
from datetime import date
from decimal import Decimal
import time
import tracemalloc
import pytest

from src.modules.sales_trend.domain.sales_trend import (
    TrendCatalogEntry,
    build_monthly_sales,
)
from src.modules.sales_trend.domain.suppliers import build_supplier_index, get_suppliers_trend
from src.modules.sales_trend.domain.ranking import filter_and_rank_products
from src.modules.sales_trend.domain.search_text import normalize_text


@pytest.mark.slow
def test_performance_2500_skus_and_150_suppliers():
    """Valida que o cálculo para 2.500 SKUs em 24 meses responde em menos de 300ms e < 20MB."""
    catalog = {}
    rows = []

    # 150 fornecedores, ~17 SKUs cada = ~2.550 SKUs
    for s_id in range(1, 151):
        supp_name = f"FORNECEDOR {s_id:03d}"
        for p_id in range(1, 18):
            sku = s_id * 100 + p_id
            catalog[sku] = TrendCatalogEntry(
                codigo=sku,
                descricao=f"PRODUTO TESTE {sku}",
                fornecedor=supp_name,
                descricao_normalizada=f"produto teste {sku}",
            )
            # 24 meses de histórico
            for m in range(202411, 202413):
                rows.append((sku, m, Decimal("10.0"), Decimal("100.0")))
            for m in range(202501, 202513):
                rows.append((sku, m, Decimal("15.0"), Decimal("150.0")))
            for m in range(202601, 202611):
                rows.append((sku, m, Decimal("20.0"), Decimal("200.0")))

    tracemalloc.start()
    t0 = time.perf_counter()
    ms = build_monthly_sales(rows, set(catalog.keys()), date(2024, 11, 1))
    s_idx = build_supplier_index(catalog)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_mem / (1024 * 1024)
    assert peak_mb < 20.0, f"Pico de memória {peak_mb:.2f} MB excedeu 20 MB"

    # Latência de ranqueamento
    t1 = time.perf_counter()
    res_prod = filter_and_rank_products(
        catalog=catalog,
        monthly_sales=ms,
        base_month_index=2026 * 12 + 10 - 1,
        metric="revenue",
        sort_window=3,
        sort_dir="desc",
        view="all",
        q=None,
        min_volume=0.0,
        last_covered_day=date(2026, 11, 8),
    )
    duration_ms = (time.perf_counter() - t1) * 1000
    assert duration_ms < 300.0, f"Latência de {duration_ms:.2f} ms excedeu 300 ms"
    assert len(res_prod.items) == len(catalog)
