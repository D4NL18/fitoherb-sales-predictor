"""
Adaptador de migracao (P-153, ADR-009 DA-04): unica ponte com o motor da F6 e com a leitura SQL por cliente.
Le SEMPRE com quatro datas, escala a Janela Anterior por `k`, chama o motor com o mapa de afinidade
(nunca o fallback por tokens, P-153.3) e devolve so agregados. O codigo do cliente vive apenas dentro desta
funcao e as linhas sao descartadas antes do retorno (LGPD-TIA-01/02).
"""
from dataclasses import dataclass
from typing import AbstractSet, Any, Callable, Iterable, Mapping, Optional, Union

from src.modules.analytics.domain.cannibalization_report import compute_directional_migration
from src.modules.analytics.repository import sales_repository
from src.modules.trend_insights.domain.constants import MIGRATION_MIN_PREVIOUS_COVERAGE_RATIO
from src.modules.trend_insights.domain.migration_scaling import (
    LostCustomersAggregate,
    aggregate_lost_customers,
    scale_previous,
)
from src.modules.trend_insights.domain.ports import NotEvaluated
from src.modules.trend_insights.domain.windows import WindowSpec


@dataclass(frozen=True)
class TrendMigrationSnapshot:
    """Pares agregados do motor + perda agregada por SKU. Zero identificador de cliente."""

    migration: Any
    lost_by_sku: Mapping[str, LostCustomersAggregate]


def _read_split_window_rows(*dates):
    """Leitura padrao: consulta de 4 datas (a funcao contigua da F6 nunca e usada pela F7)."""
    return sales_repository.fetch_customer_sku_split_window_sales(*dates)


def _previous_coverage_ok(spec: WindowSpec) -> bool:
    ratio = spec.pre_covered_days / spec.pre_days if spec.pre_days else 0.0
    return spec.is_previous_fully_covered and ratio >= MIGRATION_MIN_PREVIOUS_COVERAGE_RATIO


def build_migration_snapshot(
    spec: WindowSpec,
    affinity_map: Optional[Mapping[str, Mapping[str, float]]],
    catalog: Mapping[str, Mapping[str, Any]],
    lost_customer_codes: AbstractSet[int],
    read_rows: Callable[..., Iterable[tuple]] = _read_split_window_rows,
    engine: Callable[..., Any] = compute_directional_migration,
) -> Union[TrendMigrationSnapshot, NotEvaluated]:
    if not _previous_coverage_ok(spec):
        return NotEvaluated("JANELA_ANTERIOR_INCOMPLETA")
    if affinity_map is None:
        return NotEvaluated("INDICE_AFINIDADE_INDISPONIVEL")
    rows = read_rows(spec.pre_start, spec.pre_end_exclusive, spec.cur_start, spec.cur_end_exclusive)
    scaled = list(scale_previous(rows, spec.scale_k))
    del rows
    migration = engine(scaled, catalog, affinity_map=affinity_map)
    lost = aggregate_lost_customers(scaled, lost_customer_codes, affinity_map) if lost_customer_codes else {}
    del scaled
    return TrendMigrationSnapshot(migration=migration, lost_by_sku=lost)
