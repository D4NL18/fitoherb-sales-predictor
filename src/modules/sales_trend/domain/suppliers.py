"""
Agrupamento por fornecedor, soma líquida e cálculo de contribuição de produtos (P-088 a P-092, ADR-003 DA-07).
Garante que a variação % do fornecedor seja calculada sobre a soma de vendas dos produtos ativos,
e calcula o fecho matemático da contribuição em p.p. e valor.
"""
from dataclasses import dataclass
import datetime
from fractions import Fraction
import re
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from src.modules.sales_trend.domain.exceptions import SupplierNotFoundError
from src.modules.sales_trend.domain.month_windows import (
    covered_days,
    days_in_span,
    is_coverage_sufficient,
    window_pair,
)
from src.modules.sales_trend.domain.pagination import paginate
from src.modules.sales_trend.domain.ranking import TotaisPorVisao
from src.modules.sales_trend.domain.rounding import round_fraction_half_up
from src.modules.sales_trend.domain.sales_trend import (
    MonthlySales,
    NO_SUPPLIER_KEY,
    NO_SUPPLIER_LABEL,
    SkuSeries,
    TREND_SPAN_MONTHS,
    TrendCatalogEntry,
    TrendCell,
    VALUE_SCALE,
    WINDOW_SIZES_MONTHS,
    compute_cell,
)
from src.modules.sales_trend.domain.search_text import matches_product, matches_supplier, normalize_text

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class SupplierGroup:
    """Metadados e SKUs associados a um fornecedor normalizado."""
    supplier_key: str
    display_name: str
    skus: Tuple[int, ...]


@dataclass(frozen=True)
class SupplierTrendRow:
    """Linha da visão por fornecedor."""
    supplier_key: str
    fornecedor: str
    total_skus: int
    janelas: Dict[int, TrendCell]


@dataclass(frozen=True)
class SuppliersRankingResult:
    """Resultado da listagem de fornecedores."""
    items: List[SupplierTrendRow]
    totais_por_visao: TotaisPorVisao


@dataclass(frozen=True)
class SupplierProductItem:
    """Produto no detalhe expandido de um fornecedor."""
    sku: int
    descricao: str
    variacao_pct: Optional[float]
    status: str
    atual: float
    anterior: float
    contribuicao_pp: Optional[float]
    contribuicao_valor: float
    base_parcial: bool
    base_baixa: bool
    devolucao_liquida: bool
    contribuicao_fracao: Fraction


@dataclass(frozen=True)
class SupplierDetailResult:
    """Resultado paginado do detalhe do fornecedor."""
    supplier_key: str
    fornecedor: str
    items: List[SupplierProductItem]
    total_items: int
    total_pages: int
    page: int


def build_supplier_index(catalog: Mapping[int, TrendCatalogEntry]) -> Dict[str, SupplierGroup]:
    """
    Agrupa produtos do catálogo ativo por fornecedor.
    Fornecedores sem nome viram 'sem-fornecedor' (P-089.2).
    Chaves formatadas como 'f:<slug>' para prevenir colisões (AR-4).
    """
    grouped_skus: Dict[str, List[int]] = {}
    display_names: Dict[str, str] = {}

    for sku, entry in catalog.items():
        raw_supp = (entry.fornecedor or "").strip()
        if not raw_supp:
            key = NO_SUPPLIER_KEY
            d_name = NO_SUPPLIER_LABEL
        else:
            norm = normalize_text(raw_supp)
            slug = _SLUG_CLEAN_RE.sub("-", norm).strip("-")
            key = f"f:{slug}"
            d_name = raw_supp

        if key not in grouped_skus:
            grouped_skus[key] = []
            display_names[key] = d_name
        else:
            # Prefere nome mais curto ou ordinal menor
            if len(d_name) < len(display_names[key]):
                display_names[key] = d_name

        grouped_skus[key].append(sku)

    index: Dict[str, SupplierGroup] = {}
    for key, skus in grouped_skus.items():
        index[key] = SupplierGroup(
            supplier_key=key,
            display_name=display_names[key],
            skus=tuple(skus),
        )
    return index


def _build_supplier_aggregated_series(
    skus: Sequence[int],
    monthly_sales: MonthlySales,
) -> Optional[SkuSeries]:
    """Soma as séries de quantidade e receita de todos os SKUs de um fornecedor."""
    m_count = monthly_sales.month_count
    if m_count == 0 or not skus:
        return None

    tot_qty = [0] * m_count
    tot_rev = [0] * m_count
    tot_mask = 0

    for sku in skus:
        series = monthly_sales.series.get(sku)
        if series:
            tot_mask |= series.movement_mask
            for i in range(m_count):
                tot_qty[i] += series.quantity[i]
                tot_rev[i] += series.revenue[i]

    return SkuSeries(
        quantity=tuple(tot_qty),
        revenue=tuple(tot_rev),
        movement_mask=tot_mask,
    )


def get_suppliers_trend(
    supplier_index: Mapping[str, SupplierGroup],
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
) -> SuppliersRankingResult:
    """
    Calcula a lista de fornecedores com a variação percentual sobre a soma líquida de vendas.
    """
    first_m = monthly_sales.first_month
    m_count = monthly_sales.month_count
    min_span_m = base_month_index - TREND_SPAN_MONTHS + 1
    max_span_m = base_month_index

    rows_universe: List[SupplierTrendRow] = []

    for key, group in supplier_index.items():
        agg_series = _build_supplier_aggregated_series(group.skus, monthly_sales)
        if not agg_series:
            continue

        # Verifica se há movimento no período de 24 meses
        has_movement = False
        for m in range(min_span_m, max_span_m + 1):
            idx = m - first_m
            if 0 <= idx < m_count:
                if (agg_series.movement_mask & (1 << idx)) != 0:
                    has_movement = True
                    break

        if not has_movement:
            continue

        # Calcula as 4 janelas do fornecedor
        cells: Dict[int, TrendCell] = {}
        for w in WINDOW_SIZES_MONTHS:
            cells[w] = compute_cell(
                series=agg_series,
                base_month_index=base_month_index,
                size=w,
                metric=metric,
                monthly_sales=monthly_sales,
                last_covered_day=last_covered_day,
            )

        rows_universe.append(
            SupplierTrendRow(
                supplier_key=key,
                fornecedor=group.display_name,
                total_skus=len(group.skus),
                janelas=cells,
            )
        )

    # Contabiliza totaisPorVisao
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

    # Filtragem
    filtered: List[SupplierTrendRow] = []
    for r in rows_universe:
        cell_sw = r.janelas[sort_window]

        if view == "rising":
            if not (cell_sw.status == "VARIACAO" and (cell_sw.variacao_pct or 0.0) > 0):
                continue
        elif view == "falling":
            if not (cell_sw.status == "VARIACAO" and (cell_sw.variacao_pct or 0.0) < 0):
                continue
        elif view == "new":
            if cell_sw.status != "NOVO":
                continue

        if min_volume > 0.0:
            if cell_sw.status == "VARIACAO" and cell_sw.anterior < min_volume:
                continue

        if q:
            norm_supp = normalize_text(r.fornecedor)
            if not matches_supplier(q, norm_supp):
                continue

        filtered.append(r)

    # Ordenação
    def sort_key(row: SupplierTrendRow):
        cell = row.janelas[sort_window]
        if view == "new":
            return (0, -cell.atual, row.fornecedor)

        group = 0
        if cell.status == "NOVO":
            group = 1
        elif cell.status == "SEM_BASE":
            group = 2
        elif cell.status == "SEM_MOVIMENTO":
            group = 3

        if group == 0:
            var_f = cell.variacao_fracao or Fraction(0)
            perda_absoluta = cell.anterior - cell.atual
            if sort_dir == "desc":
                return (group, -var_f, -perda_absoluta, row.fornecedor)
            else:
                return (group, var_f, -perda_absoluta, row.fornecedor)
        elif group == 1:
            return (group, -cell.atual, row.fornecedor)
        else:
            return (group, row.fornecedor)

    filtered.sort(key=sort_key)

    return SuppliersRankingResult(
        items=filtered,
        totais_por_visao=totais_visao,
    )


def get_supplier_detail(
    supplier_key: str,
    supplier_index: Mapping[str, SupplierGroup],
    catalog: Mapping[int, TrendCatalogEntry],
    monthly_sales: MonthlySales,
    base_month_index: int,
    metric: str,
    sort_by: str,  # contribution | variation
    sort_dir: str,  # asc | desc
    q: Optional[str],
    limit: int,
    offset: int,
    last_covered_day: datetime.date,
    sort_window: int = 1,
) -> SupplierDetailResult:
    """
    Retorna o detalhe de produtos de um fornecedor com a contribuição em p.p. e em valor.
    """
    group = supplier_index.get(supplier_key)
    if not group:
        raise SupplierNotFoundError(fields=("supplierKey",))

    # Calcula a célula do fornecedor na janela
    agg_series = _build_supplier_aggregated_series(group.skus, monthly_sales)
    if not agg_series:
        raise SupplierNotFoundError(fields=("supplierKey",))

    supplier_cell = compute_cell(
        series=agg_series,
        base_month_index=base_month_index,
        size=sort_window,
        metric=metric,
        monthly_sales=monthly_sales,
        last_covered_day=last_covered_day,
    )

    # Identifica dias e cobertura para cálculo de contribuição
    curr_span, prev_span = window_pair(base_month_index, sort_window)
    cov_prev = covered_days(prev_span, monthly_sales.first_sale_date or datetime.date.min, last_covered_day)
    cov_curr = covered_days(curr_span, monthly_sales.first_sale_date or datetime.date.min, last_covered_day)
    days_prev = days_in_span(prev_span)
    days_curr = days_in_span(curr_span)
    is_partial = (cov_curr < days_curr) or (cov_prev < days_prev)

    # Universo de SKUs do fornecedor com movimento no período
    first_m = monthly_sales.first_month
    m_count = monthly_sales.month_count
    min_span_m = base_month_index - TREND_SPAN_MONTHS + 1
    max_span_m = base_month_index

    product_items: List[SupplierProductItem] = []

    for sku in group.skus:
        series = monthly_sales.series.get(sku)
        if not series:
            continue

        has_movement = False
        for m in range(min_span_m, max_span_m + 1):
            idx = m - first_m
            if 0 <= idx < m_count:
                if (series.movement_mask & (1 << idx)) != 0:
                    has_movement = True
                    break

        if not has_movement:
            continue

        prod_cell = compute_cell(
            series=series,
            base_month_index=base_month_index,
            size=sort_window,
            metric=metric,
            monthly_sales=monthly_sales,
            last_covered_day=last_covered_day,
        )

        entry = catalog.get(sku)
        descricao = entry.descricao if entry else ""

        # Filtro de busca de produto dentro do fornecedor
        if q:
            desc_norm = entry.descricao_normalizada if entry else ""
            if not matches_product(q, sku, desc_norm):
                continue

        # Cálculo de contribuição:
        # Se fornecedor está SEM_BASE ou anterior efetivo <= 0 -> contribuição p.p. é null
        contribuicao_pp: Optional[float] = None
        contribuicao_fracao: Fraction = Fraction(0)

        # Contribuição em valor: delta simples ou por dia se baseParcial
        if is_partial:
            c_val = (prod_cell.atual_por_dia or 0.0) - (prod_cell.anterior_por_dia or 0.0)
        else:
            c_val = prod_cell.atual - prod_cell.anterior

        if supplier_cell.status != "SEM_BASE" and supplier_cell.anterior_bruto_escalado > 0:
            if is_partial:
                # Contribuição por taxas diárias
                p_curr_rate = Fraction(max(0, prod_cell.atual_bruto_escalado), max(1, cov_curr) * VALUE_SCALE)
                p_prev_rate = Fraction(max(0, prod_cell.anterior_bruto_escalado), max(1, cov_prev) * VALUE_SCALE)
                delta_rate = p_curr_rate - p_prev_rate
                s_prev_rate = Fraction(max(1, supplier_cell.anterior_bruto_escalado), max(1, cov_prev) * VALUE_SCALE)
                contribuicao_fracao = (delta_rate / s_prev_rate) * 100
            else:
                # delta nominal sobre anterior do fornecedor
                delta_escalado = max(0, prod_cell.atual_bruto_escalado) - max(0, prod_cell.anterior_bruto_escalado)
                contribuicao_fracao = Fraction(delta_escalado, supplier_cell.anterior_bruto_escalado) * 100

            contribuicao_pp = round_fraction_half_up(contribuicao_fracao, 1)

        product_items.append(
            SupplierProductItem(
                sku=sku,
                descricao=descricao,
                variacao_pct=prod_cell.variacao_pct,
                status=prod_cell.status,
                atual=prod_cell.atual,
                anterior=prod_cell.anterior,
                contribuicao_pp=contribuicao_pp,
                contribuicao_valor=c_val,
                base_parcial=prod_cell.base_parcial,
                base_baixa=prod_cell.base_baixa,
                devolucao_liquida=prod_cell.devolucao_liquida,
                contribuicao_fracao=contribuicao_fracao,
            )
        )

    # Ordenação do detalhe (sortBy: contribution | variation)
    def detail_sort_key(item: SupplierProductItem):
        if sort_by == "variation":
            var_f = Fraction(int((item.variacao_pct or 0.0) * 10), 10)
            if sort_dir == "desc":
                return (-var_f, item.sku)
            return (var_f, item.sku)
        else:  # contribution
            c_f = item.contribuicao_fracao
            if sort_dir == "desc":
                return (-c_f, item.sku)
            return (c_f, item.sku)

    product_items.sort(key=detail_sort_key)

    # Paginação do detalhe
    paginated = paginate(product_items, limit=limit, offset=offset)

    return SupplierDetailResult(
        supplier_key=supplier_key,
        fornecedor=group.display_name,
        items=list(paginated.items),
        total_items=paginated.total_items,
        total_pages=paginated.total_pages,
        page=paginated.page,
    )
