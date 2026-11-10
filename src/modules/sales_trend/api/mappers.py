"""
Mappers de conversão entre entidades do domínio e schemas de resposta da API (ADR-003 DA-11).
"""
from datetime import datetime, timezone, date
from typing import Dict, List, Optional

from src.modules.sales_trend.api.schemas import (
    JanelaMeta,
    OrdenacaoMeta,
    ParametrosMeta,
    ProductTrendItemSchema,
    ProductTrendResponse,
    SupplierDetailResponse,
    SupplierProductItemSchema,
    SupplierTrendItemSchema,
    SupplierTrendResponse,
    TotaisPorVisaoSchema,
    TrendCellSchema,
    TrendMeta,
)
from src.modules.sales_trend.domain.month_windows import (
    covered_days,
    days_in_span,
    format_year_month,
    index_to_year_month,
    month_index,
    previous_month,
    window_pair,
)
from src.modules.sales_trend.domain.ranking import ProductTrendRow
from src.modules.sales_trend.domain.sales_trend import (
    CACHE_TTL_HOURS,
    LOW_BASE_MIN_QUANTITY,
    LOW_BASE_MIN_REVENUE,
    TREND_SPAN_MONTHS,
    WINDOW_SIZES_MONTHS,
    TrendCell,
)
from src.modules.sales_trend.domain.suppliers import (
    SupplierDetailResult,
    SupplierTrendRow,
)
from src.modules.sales_trend.service.sales_trend_cache import SalesTrendSnapshot
from src.modules.sales_trend.service.sales_trend_service import SalesTrendServiceResult

_MES_ABREV = [
    "", "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez"
]


def _format_span_label(span: List[int]) -> str:
    """Formata sequência de meses para rótulo legível (ex: 'out/26', 'ago–out/26', 'nov/25–out/26')."""
    if not span:
        return ""
    start_y, start_m = index_to_year_month(span[0])
    end_y, end_m = index_to_year_month(span[-1])

    s_str = f"{_MES_ABREV[start_m]}/{str(start_y)[2:]}"
    e_str = f"{_MES_ABREV[end_m]}/{str(end_y)[2:]}"

    if len(span) == 1:
        return s_str
    if start_y == end_y:
        return f"{_MES_ABREV[start_m]}–{e_str}"
    return f"{s_str}–{e_str}"


def _build_janelas_meta(base_month_idx: int, snapshot: SalesTrendSnapshot) -> List[JanelaMeta]:
    """Constrói metadados estruturados das 4 janelas (1, 3, 6, 12 meses)."""
    metas: List[JanelaMeta] = []
    first_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)

    for w in WINDOW_SIZES_MONTHS:
        curr_span, prev_span = window_pair(base_month_idx, w)
        dias_j = days_in_span(curr_span)
        dias_cov_curr = covered_days(curr_span, first_date, snapshot.last_covered_day)
        dias_cov_prev = covered_days(prev_span, first_date, snapshot.last_covered_day)
        base_parcial = (dias_cov_curr < dias_j) or (dias_cov_prev < days_in_span(prev_span))

        metas.append(
            JanelaMeta(
                tamanho_meses=w,
                rotulo_periodo_atual=_format_span_label(curr_span),
                rotulo_periodo_anterior=_format_span_label(prev_span),
                dias_janela=dias_j,
                dias_cobertos_atual=dias_cov_curr,
                dias_cobertos_anterior=dias_cov_prev,
                base_parcial=base_parcial,
            )
        )
    return metas


def _build_trend_meta(
    service_res: SalesTrendServiceResult,
    fornecedor: Optional[str] = None,
) -> TrendMeta:
    """Monta o objeto TrendMeta consolidado."""
    snap = service_res.snapshot
    ref_y, ref_m = snap.reference_date.year, snap.reference_date.month
    curr_m_idx = month_index(ref_y, ref_m)
    first_date = snap.monthly_sales.first_sale_date or date(2025, 1, 1)

    return TrendMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        versao_contrato="1.0.0",
        data_referencia=snap.reference_date.isoformat(),
        ultimo_dia_coberto=snap.last_covered_day.isoformat(),
        mes_base=format_year_month(service_res.base_month_index),
        mes_base_padrao=format_year_month(previous_month(curr_m_idx)),
        mes_base_minimo=format_year_month(month_index(first_date.year, first_date.month)),
        mes_base_maximo=format_year_month(curr_m_idx),
        mes_base_parcial=service_res.mes_base_parcial,
        agrupamento=service_res.agrupamento,
        metrica=service_res.metrica,
        total_items=service_res.total_items,
        total_pages=service_res.total_pages,
        page=service_res.page,
        limit=service_res.limit,
        offset=service_res.offset,
        totais_por_visao=TotaisPorVisaoSchema(
            total=service_res.totais_por_visao.total,
            rising=service_res.totais_por_visao.rising,
            falling=service_res.totais_por_visao.falling,
            new=service_res.totais_por_visao.new,
        ),
        ordenacao=OrdenacaoMeta(
            sort_window=service_res.sort_window,
            sort_dir=service_res.sort_dir,
        ),
        janelas=_build_janelas_meta(service_res.base_month_index, snap),
        parametros=ParametrosMeta(
            low_base_min_quantity=LOW_BASE_MIN_QUANTITY,
            low_base_min_revenue=LOW_BASE_MIN_REVENUE,
            cache_ttl_hours=CACHE_TTL_HOURS,
            trend_span_months=TREND_SPAN_MONTHS,
        ),
        fornecedor=fornecedor,
    )


def _map_cell_to_schema(cell: TrendCell) -> TrendCellSchema:
    """Mapeia TrendCell do domínio para TrendCellSchema."""
    return TrendCellSchema(
        status=cell.status,  # type: ignore
        variacao_pct=cell.variacao_pct,
        atual=cell.atual,
        anterior=cell.anterior,
        base_parcial=cell.base_parcial,
        base_baixa=cell.base_baixa,
        devolucao_liquida=cell.devolucao_liquida,
        atual_por_dia=cell.atual_por_dia,
        anterior_por_dia=cell.anterior_por_dia,
    )


def map_products_response(service_res: SalesTrendServiceResult) -> ProductTrendResponse:
    """Mapeia lista de produtos do serviço para ProductTrendResponse."""
    data_items: List[ProductTrendItemSchema] = []
    for r in service_res.items:
        row: ProductTrendRow = r
        janelas_dict = {f"{w}m": _map_cell_to_schema(c) for w, c in row.janelas.items()}
        data_items.append(
            ProductTrendItemSchema(
                sku=row.sku,
                descricao=row.descricao,
                fornecedor=row.fornecedor,
                janelas=janelas_dict,
            )
        )

    meta = _build_trend_meta(service_res)
    return ProductTrendResponse(data=data_items, meta=meta)


def map_suppliers_response(service_res: SalesTrendServiceResult) -> SupplierTrendResponse:
    """Mapeia lista de fornecedores do serviço para SupplierTrendResponse."""
    data_items: List[SupplierTrendItemSchema] = []
    for r in service_res.items:
        row: SupplierTrendRow = r
        janelas_dict = {f"{w}m": _map_cell_to_schema(c) for w, c in row.janelas.items()}
        data_items.append(
            SupplierTrendItemSchema(
                supplier_key=row.supplier_key,
                fornecedor=row.fornecedor,
                total_skus=row.total_skus,
                janelas=janelas_dict,
            )
        )

    meta = _build_trend_meta(service_res)
    return SupplierTrendResponse(data=data_items, meta=meta)


def map_supplier_detail_response(
    detail_res: SupplierDetailResult,
    snapshot: SalesTrendSnapshot,
    base_month_idx: int,
    metric: str,
    sort_by: str,
    sort_dir: str,
    limit: int,
    offset: int,
    sort_window: int = 1,
) -> SupplierDetailResponse:
    """Mapeia detalhe de fornecedor para SupplierDetailResponse."""
    data_items: List[SupplierProductItemSchema] = []
    for it in detail_res.items:
        data_items.append(
            SupplierProductItemSchema(
                sku=it.sku,
                descricao=it.descricao,
                variacao_pct=it.variacao_pct,
                status=it.status,  # type: ignore
                atual=it.atual,
                anterior=it.anterior,
                contribuicao_pp=it.contribuicao_pp,
                contribuicao_valor=it.contribuicao_valor,
                base_parcial=it.base_parcial,
                base_baixa=it.base_baixa,
                devolucao_liquida=it.devolucao_liquida,
            )
        )

    ref_y, ref_m = snapshot.reference_date.year, snapshot.reference_date.month
    curr_m_idx = month_index(ref_y, ref_m)
    first_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)

    meta = TrendMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        versao_contrato="1.0.0",
        data_referencia=snapshot.reference_date.isoformat(),
        ultimo_dia_coberto=snapshot.last_covered_day.isoformat(),
        mes_base=format_year_month(base_month_idx),
        mes_base_padrao=format_year_month(previous_month(curr_m_idx)),
        mes_base_minimo=format_year_month(month_index(first_date.year, first_date.month)),
        mes_base_maximo=format_year_month(curr_m_idx),
        mes_base_parcial=(base_month_idx == curr_m_idx),
        agrupamento="supplier_detail",
        metrica=metric,
        total_items=detail_res.total_items,
        total_pages=detail_res.total_pages,
        page=detail_res.page,
        limit=limit,
        offset=offset,
        totais_por_visao=TotaisPorVisaoSchema(total=detail_res.total_items, rising=0, falling=0, new=0),
        ordenacao=OrdenacaoMeta(sort_window=sort_window, sort_dir=sort_dir, sort_by=sort_by),
        janelas=_build_janelas_meta(base_month_idx, snapshot),
        parametros=ParametrosMeta(
            low_base_min_quantity=LOW_BASE_MIN_QUANTITY,
            low_base_min_revenue=LOW_BASE_MIN_REVENUE,
            cache_ttl_hours=CACHE_TTL_HOURS,
            trend_span_months=TREND_SPAN_MONTHS,
        ),
        fornecedor=detail_res.fornecedor,
    )

    return SupplierDetailResponse(data=data_items, meta=meta)
