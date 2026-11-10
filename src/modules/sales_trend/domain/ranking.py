"""
Ordenação determinística, visões e filtros por produto ativo (P-072, P-080, P-081, ADR-003 DA-06).
Aplica grupos de status, desempate por perda absoluta e código, e contagem de totaisPorVisao.
"""
from dataclasses import dataclass
import datetime
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence

from src.modules.sales_trend.domain.sales_trend import (
    MonthlySales,
    TrendCatalogEntry,
    TrendCell,
    WINDOW_SIZES_MONTHS,
    TREND_SPAN_MONTHS,
    compute_cell,
)
from src.modules.sales_trend.domain.search_text import matches_product


@dataclass(frozen=True)
class TotaisPorVisao:
    """Contagem de SKUs/grupos por visão na sortWindow (P-080.4)."""
    total: int
    rising: int
    falling: int
    new: int


@dataclass(frozen=True)
class ProductTrendRow:
    """Linha da tabela de tendência para um produto ativo."""
    sku: int
    descricao: str
    fornecedor: Optional[str]
    janelas: Dict[int, TrendCell]


@dataclass(frozen=True)
class RankingResult:
    """Resultado da filtragem e ordenação."""
    items: List[ProductTrendRow]
    totais_por_visao: TotaisPorVisao


def filter_and_rank_products(
    catalog: Mapping[int, TrendCatalogEntry],
    monthly_sales: MonthlySales,
    base_month_index: int,
    metric: str,
    sort_window: int,
    sort_dir: str,
    view: str,
    q: Optional[str],
    min_volume: float,
    last_covered_day: datetime.date,
) -> RankingResult:
    """
    Filtra o universo de produtos ativos com movimento em [M-23, M],
    calcula as células de variação nas 4 janelas, aplica filtros e ordena.
    """
    first_m = monthly_sales.first_month
    m_count = monthly_sales.month_count
    min_span_m = base_month_index - TREND_SPAN_MONTHS + 1
    max_span_m = base_month_index

    rows_universe: List[ProductTrendRow] = []

    # 1. Identifica SKUs ativos com movimento no intervalo de 24 meses
    for sku, entry in catalog.items():
        series = monthly_sales.series.get(sku)
        if not series:
            continue

        # Verifica se há movimento em [min_span_m, max_span_m]
        has_movement = False
        for m in range(min_span_m, max_span_m + 1):
            idx = m - first_m
            if 0 <= idx < m_count:
                if (series.movement_mask & (1 << idx)) != 0:
                    has_movement = True
                    break

        if not has_movement:
            continue

        # Calcula as 4 janelas
        cells: Dict[int, TrendCell] = {}
        for w in WINDOW_SIZES_MONTHS:
            cells[w] = compute_cell(
                series=series,
                base_month_index=base_month_index,
                size=w,
                metric=metric,
                monthly_sales=monthly_sales,
                last_covered_day=last_covered_day,
            )

        rows_universe.append(
            ProductTrendRow(
                sku=sku,
                descricao=entry.descricao,
                fornecedor=entry.fornecedor,
                janelas=cells,
            )
        )

    # 2. Contabiliza totaisPorVisao sobre todo o universo antes dos filtros de view/q/minVolume
    tot_total = len(rows_universe)
    tot_rising = 0
    tot_falling = 0
    tot_new = 0

    for r in rows_universe:
        cell_sw = r.janelas.get(sort_window)
        if cell_sw:
            if cell_sw.status == "VARIACAO":
                pct = cell_sw.variacao_pct or 0.0
                if pct > 0:
                    tot_rising += 1
                elif pct < 0:
                    tot_falling += 1
            elif cell_sw.status == "NOVO":
                tot_new += 1

    totais_visao = TotaisPorVisao(
        total=tot_total,
        rising=tot_rising,
        falling=tot_falling,
        new=tot_new,
    )

    # 3. Filtragem
    filtered: List[ProductTrendRow] = []
    for r in rows_universe:
        cell_sw = r.janelas[sort_window]

        # Filtro de Visão
        if view == "rising":
            if not (cell_sw.status == "VARIACAO" and (cell_sw.variacao_pct or 0.0) > 0):
                continue
        elif view == "falling":
            if not (cell_sw.status == "VARIACAO" and (cell_sw.variacao_pct or 0.0) < 0):
                continue
        elif view == "new":
            if cell_sw.status != "NOVO":
                continue

        # Filtro de Volume Mínimo (P-079: filtra só VARIACAO com anterior < min_volume)
        if min_volume > 0.0:
            if cell_sw.status == "VARIACAO" and cell_sw.anterior < min_volume:
                continue

        # Filtro de Busca q
        if q:
            entry = catalog.get(r.sku)
            desc_norm = entry.descricao_normalizada if entry else ""
            if not matches_product(q, r.sku, desc_norm):
                continue

        filtered.append(r)

    # 4. Ordenação Determinística (P-080, AR-1, AR-9)
    def sort_key(row: ProductTrendRow):
        cell = row.janelas[sort_window]

        if view == "new":
            # view=new ignora sortDir e ordena por maior valor atual, desempate código
            return (0, -cell.atual, row.sku)

        # Ordem de grupos: 0=VARIACAO, 1=NOVO, 2=SEM_BASE, 3=SEM_MOVIMENTO
        group = 0
        if cell.status == "NOVO":
            group = 1
        elif cell.status == "SEM_BASE":
            group = 2
        elif cell.status == "SEM_MOVIMENTO":
            group = 3

        if group == 0:
            var_f = cell.variacao_fracao or Fraction(0)
            # Perda absoluta = anterior - atual (maior perda desempata primeiro)
            perda_absoluta = cell.anterior - cell.atual
            if sort_dir == "desc":
                return (group, -var_f, -perda_absoluta, row.sku)
            else:
                return (group, var_f, -perda_absoluta, row.sku)
        elif group == 1:
            return (group, -cell.atual, row.sku)
        else:
            return (group, row.sku)

    filtered.sort(key=sort_key)

    return RankingResult(
        items=filtered,
        totais_por_visao=totais_visao,
    )
