"""
Mappers de conversão entre entidades do domínio e schemas de resposta da API (ADR-003 DA-11).
Garante conformidade estrita com o Contrato de API 1.0.0.
"""
from datetime import datetime, timezone, date
from typing import Dict, List, Optional

from src.modules.sales_trend.api.schemas import (
    DetailOrdenacaoMeta,
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
    TrendDetailCellSchema,
    TrendDetailMeta,
    TrendListMeta,
    TrendTotalRowSchema,
    TrendWindowSpanSchema,
)
from src.modules.sales_trend.domain.month_windows import (
    covered_days,
    days_in_month,
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
    NO_SUPPLIER_KEY,
    TREND_SPAN_MONTHS,
    WINDOW_SIZES_MONTHS,
    TrendCell,
    compute_cell,
)
from src.modules.sales_trend.domain.suppliers import (
    SupplierDetailResult,
    SupplierTrendRow,
    _build_supplier_aggregated_series,
)
from src.modules.sales_trend.service.sales_trend_cache import SalesTrendSnapshot
from src.modules.sales_trend.service.sales_trend_service import SalesTrendServiceResult


def _map_cell_to_schema(cell: TrendCell, window_months: int) -> TrendCellSchema:
    """Mapeia TrendCell do domínio para TrendCellSchema com campo meses."""
    return TrendCellSchema(
        meses=window_months,
        atual=cell.atual,
        anterior=cell.anterior,
        variacao_pct=cell.variacao_pct,
        status=cell.status,  # type: ignore
        base_parcial=cell.base_parcial,
        base_baixa=cell.base_baixa,
        devolucao_liquida=cell.devolucao_liquida,
        atual_por_dia=cell.atual_por_dia,
        anterior_por_dia=cell.anterior_por_dia,
    )


def _build_janelas_meta(base_month_idx: int, snapshot: SalesTrendSnapshot) -> List[JanelaMeta]:
    """Constrói metadados estruturados das 4 janelas (1, 3, 6, 12 meses)."""
    metas: List[JanelaMeta] = []
    first_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)

    for w in WINDOW_SIZES_MONTHS:
        curr_span, prev_span = window_pair(base_month_idx, w)

        dias_j_curr = days_in_span(curr_span)
        dias_cov_curr = covered_days(curr_span, first_date, snapshot.last_covered_day)
        curr_start_y, curr_start_m = index_to_year_month(curr_span[0])
        curr_end_y, curr_end_m = index_to_year_month(curr_span[-1])
        curr_span_schema = TrendWindowSpanSchema(
            inicio=f"{curr_start_y:04d}-{curr_start_m:02d}-01",
            fim=f"{curr_end_y:04d}-{curr_end_m:02d}-{days_in_month(curr_span[-1]):02d}",
            dias_janela=dias_j_curr,
            dias_cobertos=dias_cov_curr,
        )

        dias_j_prev = days_in_span(prev_span)
        dias_cov_prev = covered_days(prev_span, first_date, snapshot.last_covered_day)
        prev_start_y, prev_start_m = index_to_year_month(prev_span[0])
        prev_end_y, prev_end_m = index_to_year_month(prev_span[-1])
        prev_span_schema = TrendWindowSpanSchema(
            inicio=f"{prev_start_y:04d}-{prev_start_m:02d}-01",
            fim=f"{prev_end_y:04d}-{prev_end_m:02d}-{days_in_month(prev_span[-1]):02d}",
            dias_janela=dias_j_prev,
            dias_cobertos=dias_cov_prev,
        )

        sem_base = (dias_cov_prev / max(1, dias_j_prev) < 0.5)
        base_parcial = (dias_cov_curr < dias_j_curr) or (dias_cov_prev < dias_j_prev)

        metas.append(
            JanelaMeta(
                meses=w,
                atual=curr_span_schema,
                anterior=prev_span_schema,
                sem_base=sem_base,
                base_parcial=base_parcial,
            )
        )
    return metas


def _build_total_row(base_month_idx: int, metric: str, snapshot: SalesTrendSnapshot) -> TrendTotalRowSchema:
    """Calcula a linha de total geral somando todos os produtos ativos com movimento."""
    first_m = snapshot.monthly_sales.first_month
    m_count = snapshot.monthly_sales.month_count
    min_span_m = base_month_idx - TREND_SPAN_MONTHS + 1
    max_span_m = base_month_idx

    active_skus_with_movement: List[int] = []
    for sku in snapshot.catalog.keys():
        series = snapshot.monthly_sales.series.get(sku)
        if not series:
            continue
        has_movement = False
        for m in range(min_span_m, max_span_m + 1):
            idx = m - first_m
            if 0 <= idx < m_count:
                if (series.movement_mask & (1 << idx)) != 0:
                    has_movement = True
                    break
        if has_movement:
            active_skus_with_movement.append(sku)

    agg_series = _build_supplier_aggregated_series(active_skus_with_movement, snapshot.monthly_sales)
    if agg_series:
        cells = [
            _map_cell_to_schema(
                compute_cell(
                    series=agg_series,
                    base_month_index=base_month_idx,
                    size=w,
                    metric=metric,
                    monthly_sales=snapshot.monthly_sales,
                    last_covered_day=snapshot.last_covered_day,
                ),
                w,
            )
            for w in WINDOW_SIZES_MONTHS
        ]
    else:
        cells = []

    return TrendTotalRowSchema(
        qtd_produtos=len(active_skus_with_movement),
        janelas=cells,
    )


def _build_trend_meta(service_res: SalesTrendServiceResult) -> TrendListMeta:
    """Monta o objeto TrendListMeta consolidado."""
    snap = service_res.snapshot
    ref_y, ref_m = snap.reference_date.year, snap.reference_date.month
    curr_m_idx = month_index(ref_y, ref_m)
    first_date = snap.monthly_sales.first_sale_date or date(2025, 1, 1)

    return TrendListMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        data_referencia=snap.reference_date.isoformat(),
        ultimo_dia_coberto=snap.last_covered_day.isoformat(),
        mes_base=format_year_month(service_res.base_month_index),
        mes_base_padrao=format_year_month(previous_month(curr_m_idx)),
        mes_base_minimo=format_year_month(month_index(first_date.year, first_date.month)),
        mes_base_maximo=format_year_month(curr_m_idx),
        mes_base_parcial=service_res.mes_base_parcial,
        agrupamento=service_res.agrupamento,
        metrica=service_res.metrica,
        visao=service_res.view,
        total_items=service_res.total_items,
        total_pages=service_res.total_pages,
        page=service_res.page,
        limit=service_res.limit,
        offset=service_res.offset,
        totais_por_visao=TotaisPorVisaoSchema(
            todos=service_res.totais_por_visao.total,
            maiores_altas=service_res.totais_por_visao.rising,
            maiores_quedas=service_res.totais_por_visao.falling,
            novos=service_res.totais_por_visao.new,
        ),
        ordenacao=OrdenacaoMeta(
            janela=service_res.sort_window,
            sentido=service_res.sort_dir,
        ),
        total=_build_total_row(service_res.base_month_index, service_res.metrica, snap),
        janelas=_build_janelas_meta(service_res.base_month_index, snap),
        parametros=ParametrosMeta(
            limite_base_baixa_quantidade=LOW_BASE_MIN_QUANTITY,
            limite_base_baixa_faturamento=LOW_BASE_MIN_REVENUE,
            cobertura_minima_anterior=0.5,
            busca_min_caracteres=2,
            busca_min_caracteres_numerica=1,
            busca_max_caracteres=60,
            ttl_cache_horas=CACHE_TTL_HOURS,
        ),
    )


def map_products_response(service_res: SalesTrendServiceResult) -> ProductTrendResponse:
    """Mapeia lista de produtos do serviço para ProductTrendResponse."""
    data_items: List[ProductTrendItemSchema] = []
    for r in service_res.items:
        row: ProductTrendRow = r
        janelas_list = [_map_cell_to_schema(row.janelas[w], w) for w in WINDOW_SIZES_MONTHS]
        data_items.append(
            ProductTrendItemSchema(
                codigo=row.sku,
                descricao=row.descricao,
                fornecedor=row.fornecedor,
                janelas=janelas_list,
            )
        )

    meta = _build_trend_meta(service_res)
    return ProductTrendResponse(data=data_items, meta=meta)


def map_suppliers_response(service_res: SalesTrendServiceResult) -> SupplierTrendResponse:
    """Mapeia lista de fornecedores do serviço para SupplierTrendResponse."""
    data_items: List[SupplierTrendItemSchema] = []
    for r in service_res.items:
        row: SupplierTrendRow = r
        janelas_list = [_map_cell_to_schema(row.janelas[w], w) for w in WINDOW_SIZES_MONTHS]
        data_items.append(
            SupplierTrendItemSchema(
                fornecedor=row.fornecedor,
                fornecedor_chave=row.supplier_key,
                sem_fornecedor=(row.supplier_key == NO_SUPPLIER_KEY),
                qtd_produtos=row.total_skus,
                janelas=janelas_list,
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
        janelas_list: List[TrendDetailCellSchema] = []
        for w in WINDOW_SIZES_MONTHS:
            d_cell = it.janelas.get(w)
            if d_cell:
                c = d_cell.cell
                janelas_list.append(
                    TrendDetailCellSchema(
                        meses=w,
                        status=c.status,  # type: ignore
                        variacao_pct=c.variacao_pct,
                        atual=c.atual,
                        anterior=c.anterior,
                        base_parcial=c.base_parcial,
                        base_baixa=c.base_baixa,
                        devolucao_liquida=c.devolucao_liquida,
                        atual_por_dia=c.atual_por_dia,
                        anterior_por_dia=c.anterior_por_dia,
                        contribuicao_pp=d_cell.contribuicao_pp,
                        contribuicao_valor=d_cell.contribuicao_valor,
                    )
                )

        data_items.append(
            SupplierProductItemSchema(
                codigo=it.sku,
                descricao=it.descricao,
                fornecedor=it.fornecedor,
                janelas=janelas_list,
            )
        )

    ref_y, ref_m = snapshot.reference_date.year, snapshot.reference_date.month
    curr_m_idx = month_index(ref_y, ref_m)
    first_date = snapshot.monthly_sales.first_sale_date or date(2025, 1, 1)

    group = snapshot.supplier_index.get(detail_res.supplier_key)
    if group:
        agg_series = _build_supplier_aggregated_series(group.skus, snapshot.monthly_sales)
        if agg_series:
            supp_cells = [
                _map_cell_to_schema(
                    compute_cell(
                        series=agg_series,
                        base_month_index=base_month_idx,
                        size=w,
                        metric=metric,
                        monthly_sales=snapshot.monthly_sales,
                        last_covered_day=snapshot.last_covered_day,
                    ),
                    w,
                )
                for w in WINDOW_SIZES_MONTHS
            ]
        else:
            supp_cells = []
        supp_schema = SupplierTrendItemSchema(
            fornecedor=detail_res.fornecedor,
            fornecedor_chave=detail_res.supplier_key,
            sem_fornecedor=(detail_res.supplier_key == NO_SUPPLIER_KEY),
            qtd_produtos=len(group.skus),
            janelas=supp_cells,
        )
    else:
        supp_schema = SupplierTrendItemSchema(
            fornecedor=detail_res.fornecedor,
            fornecedor_chave=detail_res.supplier_key,
            sem_fornecedor=(detail_res.supplier_key == NO_SUPPLIER_KEY),
            qtd_produtos=detail_res.total_items,
            janelas=[],
        )

    meta = TrendDetailMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        data_referencia=snapshot.reference_date.isoformat(),
        ultimo_dia_coberto=snapshot.last_covered_day.isoformat(),
        mes_base=format_year_month(base_month_idx),
        mes_base_padrao=format_year_month(previous_month(curr_m_idx)),
        mes_base_minimo=format_year_month(month_index(first_date.year, first_date.month)),
        mes_base_maximo=format_year_month(curr_m_idx),
        mes_base_parcial=(base_month_idx == curr_m_idx),
        metrica=metric,
        total_items=detail_res.total_items,
        total_pages=detail_res.total_pages,
        page=detail_res.page,
        limit=limit,
        offset=offset,
        ordenacao=DetailOrdenacaoMeta(por=sort_by, janela=sort_window, sentido=sort_dir),
        janelas=_build_janelas_meta(base_month_idx, snapshot),
        parametros=ParametrosMeta(
            limite_base_baixa_quantidade=LOW_BASE_MIN_QUANTITY,
            limite_base_baixa_faturamento=LOW_BASE_MIN_REVENUE,
            cobertura_minima_anterior=0.5,
            busca_min_caracteres=2,
            busca_min_caracteres_numerica=1,
            busca_max_caracteres=60,
            ttl_cache_horas=CACHE_TTL_HOURS,
        ),
        fornecedor=supp_schema,
    )

    return SupplierDetailResponse(data=data_items, meta=meta)
