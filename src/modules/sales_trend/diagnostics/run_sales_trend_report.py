"""
CLI de diagnósticos, reconciliação financeira e medição de memória (P-087.3, ADR-003 DA-14).
Mede pico de memória tracemalloc, reconcilia vendas com o banco e calcula percentis de volume anterior.
Execução: python -m src.modules.sales_trend.diagnostics.run_sales_trend_report
"""
from datetime import date
import logging
import math
import sys
import tracemalloc
from typing import List, Optional

from src.modules.sales_trend.domain.month_windows import format_year_month, month_index, previous_month
from src.modules.sales_trend.domain.ranking import filter_and_rank_products
from src.modules.sales_trend.domain.sales_trend import VALUE_SCALE
from src.modules.sales_trend.service.sales_trend_cache import get_snapshot

logger = logging.getLogger(__name__)


def calculate_percentiles(values: List[float], percentiles: List[int] = [10, 25, 50, 75, 90]) -> dict:
    """Calcula percentis de uma lista de valores numéricos."""
    if not values:
        return {f"p{p}": 0.0 for p in percentiles}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    res = {}
    for p in percentiles:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            res[f"p{p}"] = float(sorted_vals[int(k)])
        else:
            d0 = sorted_vals[int(f)] * (c - k)
            d1 = sorted_vals[int(c)] * (k - f)
            res[f"p{p}"] = float(d0 + d1)
    return res


def run_report() -> str:
    """Executa a medição de memória, reconciliação e gera relatório textual."""
    tracemalloc.start()
    snapshot = get_snapshot(force_reload=True)
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_mem / (1024 * 1024)
    resident_mb = current_mem / (1024 * 1024)

    ref_date = snapshot.reference_date
    default_base_idx = previous_month(month_index(ref_date.year, ref_date.month))
    base_month_str = format_year_month(default_base_idx)

    # Reconciliação e contagens
    res_products = filter_and_rank_products(
        catalog=snapshot.catalog,
        monthly_sales=snapshot.monthly_sales,
        base_month_index=default_base_idx,
        metric="revenue",
        sort_window=1,
        sort_dir="desc",
        view="all",
        q=None,
        min_volume=0.0,
        last_covered_day=snapshot.last_covered_day,
    )

    total_revenue_curr = sum(it.janelas[1].atual for it in res_products.items)
    prev_volumes = [it.janelas[1].anterior for it in res_products.items if it.janelas[1].anterior > 0]
    percentiles_rev = calculate_percentiles(prev_volumes)

    max_skus_per_supp = 0
    if snapshot.supplier_index:
        max_skus_per_supp = max(len(g.skus) for g in snapshot.supplier_index.values())

    report_lines = [
        "===========================================================",
        "   RELATÓRIO DE TENDÊNCIA DE VENDAS - FITOHERB AI SUITE   ",
        "===========================================================",
        f"Data de Referência: {snapshot.reference_date.isoformat()}",
        f"Mês-Base Padrão: {base_month_str}",
        "",
        "--- [1] MÉTRICAS DE CONSUMO DE MEMÓRIA (FinOps / Cloud Run) ---",
        f"Pico de Memória na Carga (tracemalloc): {peak_mb:.2f} MB (Esperado < 30 MB)",
        f"Memória Residente do Snapshot: {resident_mb:.2f} MB (Esperado < 6 MB)",
        "",
        "--- [2] CONTAGENS E ESTRUTURA DO CATÁLOGO ---",
        f"SKUs Ativos Catalogados (Pc.Venda > 0): {len(snapshot.catalog)}",
        f"SKUs com Movimento Retidos: {len(res_products.items)}",
        f"Total de Fornecedores Ativos: {len(snapshot.supplier_index)}",
        f"SKUs do Maior Fornecedor: {max_skus_per_supp}",
        "",
        "--- [3] RECONCILIAÇÃO E CALIBRAÇÃO DE BASE BAIXA ---",
        f"Soma Faturamento Líquido Janela 1m (Atual): R$ {total_revenue_curr:,.2f}",
        f"Distribuição de Volume Anterior (Percentis):",
        f"  p10: R$ {percentiles_rev.get('p10', 0):.2f}",
        f"  p25: R$ {percentiles_rev.get('p25', 0):.2f}",
        f"  p50 (Mediana): R$ {percentiles_rev.get('p50', 0):.2f}",
        f"  p75: R$ {percentiles_rev.get('p75', 0):.2f}",
        f"  p90: R$ {percentiles_rev.get('p90', 0):.2f}",
        "===========================================================",
    ]
    report_text = "\n".join(report_lines)
    return report_text


if __name__ == "__main__":
    report = run_report()
    print(report)
