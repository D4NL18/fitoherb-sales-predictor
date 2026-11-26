"""
Anonimizacao regional (P-167, P-167.1, P-167.2): UFs com menos de 3 clientes viram `OUTRAS`, o grupo
`OUTRAS` tem piso proprio (evita dedução por diferenca) e contagens pequenas saem como "<3".
"""
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from src.modules.trend_insights.domain.constants import (
    MIN_CLIENTS_PER_UF,
    REGIONAL_CONCENTRATION_SHARE,
    SMALL_COUNT_THRESHOLD,
)

OTHER_REGIONS = "OUTRAS"
SMALL_COUNT_LABEL = "<3"


@dataclass(frozen=True)
class RegionRow:
    uf: str
    pre_rev: float
    cur_rev: float
    clients: int


@dataclass(frozen=True)
class RegionGroup:
    """Grupo exibivel: nenhuma contagem de clientes e exposta."""

    uf: str
    delta: float


@dataclass(frozen=True)
class RegionGrouping:
    status: str
    groups: Sequence[RegionGroup]
    motivo: Optional[str] = None


@dataclass(frozen=True)
class RegionalIndicator:
    status: str
    uf_concentradora: Optional[str] = None
    participacao_pct: Optional[float] = None


def format_small_count(count: int) -> Union[int, str]:
    return SMALL_COUNT_LABEL if count < SMALL_COUNT_THRESHOLD else count


def _absorb_until_floor(displayed: List[RegionRow], hidden: List[RegionRow]) -> None:
    """P-167.1: a menor UF exibida e absorvida ate `OUTRAS` ter o piso de clientes."""
    while displayed and sum(r.clients for r in hidden) < MIN_CLIENTS_PER_UF:
        smallest = min(displayed, key=lambda r: (r.clients, abs(r.cur_rev - r.pre_rev)))
        displayed.remove(smallest)
        hidden.append(smallest)


def _delta(row: RegionRow, k: float) -> float:
    return row.cur_rev - row.pre_rev * k


def group_regions(rows: Sequence[RegionRow], k: float = 1) -> RegionGrouping:
    displayed = [r for r in rows if r.clients >= MIN_CLIENTS_PER_UF]
    hidden = [r for r in rows if r.clients < MIN_CLIENTS_PER_UF]
    if hidden:
        _absorb_until_floor(displayed, hidden)
    if hidden and sum(r.clients for r in hidden) < MIN_CLIENTS_PER_UF:
        return RegionGrouping(status="NAO_AVALIADO", groups=(), motivo="ANONIMIZACAO")
    groups = [RegionGroup(uf=r.uf, delta=_delta(r, k)) for r in displayed]
    if hidden:
        groups.append(RegionGroup(uf=OTHER_REGIONS, delta=sum(_delta(r, k) for r in hidden)))
    return RegionGrouping(status="AVALIADO", groups=tuple(groups))


def detect_regional(grouping: RegionGrouping, delta_observado: float) -> RegionalIndicator:
    """Uma UF concentra a variacao com >= 60% de delta no mesmo sentido; `OUTRAS` nunca e nomeada."""
    if grouping.status != "AVALIADO":
        return RegionalIndicator(status="NAO_AVALIADO")
    if delta_observado == 0:
        return RegionalIndicator(status="SEM_EFEITO")
    named = [g for g in grouping.groups if g.uf != OTHER_REGIONS]
    best = max(named, key=lambda g: g.delta * delta_observado, default=None)
    if best is None:
        return RegionalIndicator(status="SEM_EFEITO")
    share = best.delta / delta_observado
    if share < REGIONAL_CONCENTRATION_SHARE:
        return RegionalIndicator(status="SEM_EFEITO")
    return RegionalIndicator(status="AVALIADO", uf_concentradora=best.uf, participacao_pct=share * 100)
