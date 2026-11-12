"""
CLI do backtest temporal de hit rate@5 do cross-sell (P-071, ADR-002 DA-12, B-17).

Uso:
    python -m src.modules.analytics.backtest.run_cross_sell_backtest --months 2026-08 2026-09 2026-10

Faz UMA carga do repositório com corte exclusivo no 1º dia após o último mês (cobre treino e avaliação)
e o catálogo atual, avalia cada mês com o domínio puro e imprime uma tabela markdown só com agregados
(LGPD-11: nenhum `customerCode`, recomendação ou acerto por cliente; nada é gravado em arquivo).
Mede o pico de memória da carga (`tracemalloc`; no Linux também o RSS máximo via `resource`) e o tempo.
Somente leitura no banco; precisa das variáveis `DB_*` do `.env`.
"""
from __future__ import annotations

import argparse
import importlib.util
import time
import tracemalloc
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence

import pandas as pd

from src.modules.analytics.domain.cross_sell import ORDER_DAY_EPOCH
from src.modules.analytics.domain.cross_sell_backtest import (
    EXCLUSION_REASONS,
    BacktestMonthResult,
    evaluate_month,
    month_boundaries,
    summarize,
)
from src.modules.analytics.repository import sales_repository

DEFAULT_MONTHS = ("2026-08", "2026-09", "2026-10")  # P-071.1
BYTES_PER_MEGABYTE = 1024 * 1024
KILOBYTES_PER_MEGABYTE = 1024                        # `ru_maxrss` do Linux vem em KB
PERCENT_FACTOR = 100
STOCK_LIMITATION_NOTE = (
    "Nota (P-071.5): o filtro de estoque não é aplicado no backtest, porque a base não tem estoque "
    "histórico; a margem usa preço e custo atuais do catálogo."
)


@dataclass(frozen=True)
class LoadMeasurement:
    """Agregado e catálogo carregados, com tempo e pico de memória da carga."""

    order_baskets: pd.DataFrame
    catalog: pd.DataFrame
    seconds: float
    traced_peak_mb: float
    max_rss_mb: Optional[float]


def _parse_arguments(argv: Optional[Sequence[str]]) -> List[str]:
    """Meses "YYYY-MM" pedidos na linha de comando (padrão: P-071.1)."""
    parser = argparse.ArgumentParser(description="Backtest de hit rate@5 do cross-sell (P-071).")
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS), help="Meses N no formato YYYY-MM.")
    return parser.parse_args(argv).months


def _exclusive_cutoff(months: Sequence[str]) -> date:
    """1º dia do mês seguinte ao último mês avaliado (uma carga cobre treino e avaliação, DA-02)."""
    _, next_month_start = month_boundaries(max(months))
    return date.fromordinal(ORDER_DAY_EPOCH.toordinal() + next_month_start)


def _max_rss_mb() -> Optional[float]:
    """RSS máximo do processo no Linux (Cloud Run); `None` onde o módulo `resource` não existe."""
    if importlib.util.find_spec("resource") is None:
        return None
    import resource  # noqa: PLC0415 - só existe em sistemas POSIX
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / KILOBYTES_PER_MEGABYTE


def load_sources(cutoff: date) -> LoadMeasurement:
    """Carga única do agregado e do catálogo, medindo tempo e pico de memória."""
    tracemalloc.start()
    started = time.perf_counter()
    order_baskets = sales_repository.fetch_order_baskets(cutoff)
    catalog = sales_repository.fetch_catalog()
    seconds = time.perf_counter() - started
    _, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return LoadMeasurement(order_baskets, catalog, seconds, traced_peak / BYTES_PER_MEGABYTE, _max_rss_mb())


def _percent(rate: float) -> str:
    """Taxa 0..1 em percentual com 1 casa."""
    return f"{rate * PERCENT_FACTOR:.1f}%"


def render_markdown(results: Sequence[BacktestMonthResult], load: LoadMeasurement) -> str:
    """Tabela markdown só com agregados (LGPD-11), média dos meses, nota de estoque e medições."""
    header = "| Mês | hit rate@5 modelo | hit rate@5 popularidade | Avaliados | " + " | ".join(
        f"Excluídos {reason}" for reason in EXCLUSION_REASONS) + " |"
    separator = "|" + " --- |" * (4 + len(EXCLUSION_REASONS))
    rows = [
        f"| {result.month} | {_percent(result.model_hit_rate)} | {_percent(result.popularity_hit_rate)} | "
        f"{result.evaluated_customers} | " + " | ".join(str(result.excluded_by_reason[reason])
                                                      for reason in EXCLUSION_REASONS) + " |"
        for result in results
    ]
    summary = summarize(results)
    rows.append(f"| **Média** | {_percent(summary.model_hit_rate)} | {_percent(summary.popularity_hit_rate)} | "
                f"{summary.evaluated_customers} |" + " |" * len(EXCLUSION_REASONS))
    meets_goal = "sim" if summary.model_hit_rate >= summary.popularity_hit_rate else "não"
    rss = f"{load.max_rss_mb:.0f} MB" if load.max_rss_mb is not None else "indisponível neste SO"
    footer = [
        "", f"Meta A-12 (modelo >= popularidade na média): {meets_goal}.", STOCK_LIMITATION_NOTE,
        f"Carga: {load.seconds:.1f} s; pico tracemalloc {load.traced_peak_mb:.0f} MB; RSS máximo {rss}.",
    ]
    return "\n".join([header, separator, *rows, *footer])


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Ponto de entrada do CLI."""
    months = sorted(_parse_arguments(argv))
    load = load_sources(_exclusive_cutoff(months))
    results = [evaluate_month(load.order_baskets, load.catalog, month) for month in months]
    print(render_markdown(results, load))


if __name__ == "__main__":
    main()
