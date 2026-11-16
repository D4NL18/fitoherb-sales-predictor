"""
Casos de uso do módulo Analytics Comercial (P-061 a P-069; ADR-002 DA-06, DA-07, DA-09).

Orquestra cache -> domínio -> curadoria (P-094) -> paginação -> mapper. Ordem de avaliação do contrato §3.3: a validação
(400) já aconteceu na rota; aqui vêm a carga do snapshot (503), a base suficiente (422), a existência
do SKU/cliente (404) e a lista (200). Sem `try/except`: erros sobem ao handler global. Sem log de
cliente, recomendação ou payload (LGPD-04).
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple, Union

from src.modules.analytics.api import mappers
from src.modules.analytics.api.schemas import (
    AnalyticsHealthResponse,
    CatalogListResponse,
    CustomerCrossSellResponse,
    CustomerElasticityDetail,
    CustomerElasticityItem,
    CustomerElasticityResponse,
    ElasticitySimulationRequest,
    ElasticitySimulationResponse,
    ProductCrossSellResponse,
    ProductElasticityDetail,
    ProductElasticityMetrics,
    ProductElasticityResponse,
    ProductHeader,
    ProductSearchResponse,
    ResponseMeta,
    SimulationImpactData,
)
from src.modules.analytics.domain.cross_sell import (
    CatalogEntry,
    ProductRecommendation,
    UsefulRule,
    recommend_for_product,
)
from src.modules.analytics.domain.cross_sell_customer import CustomerRecommendation, recommend_for_customer
from src.modules.analytics.domain.elasticity import (
    COST_FALLBACK_RATIO,
    STOCK_TARGET_DAYS,
    estimate_customer_elasticity,
    estimate_product_elasticity,
    prepare_price_points,
    simulate_price_impact,
)
from src.modules.analytics.domain.exceptions import (
    ElasticityCustomerWithoutHistoryError,
    ElasticityProductNotFoundError,
    InsufficientBaseError,
)
from src.modules.analytics.domain.pagination import PageRequest, paginate
from src.modules.analytics.domain.product_search import (
    filter_and_sort_catalog,
    search_products as search_catalog,
)
from src.modules.analytics.domain.recommendation_curation import curate
from src.modules.analytics.repository import sales_repository
from src.modules.analytics.service import analytics_cache
from src.modules.analytics.service.analytics_cache import (
    CUTOFF_DAYS_AFTER_REFERENCE,
    AnalyticsSnapshot,
    CatalogSnapshot,
)


def _sufficient_snapshot() -> AnalyticsSnapshot:
    """
    Snapshot carregado e com base suficiente.

    Raises:
        AnalyticsDataSourceError: `ANL-001` (503) se a carga falhar.
        InsufficientBaseError: `XSL-003` (422), antes de qualquer 404 (contrato §3.3).
    """
    snapshot = analytics_cache.get_snapshot()
    if not snapshot.is_base_sufficient:
        raise InsufficientBaseError()
    return snapshot


def get_health() -> AnalyticsHealthResponse:
    """Estado do cache sem carga nem banco (P-069, CA-21)."""
    return mappers.to_health_response(analytics_cache.get_cache_status(), analytics_cache.peek_snapshot())


def reload_cache() -> AnalyticsHealthResponse:
    """Recarga manual respeitando o lock e o intervalo mínimo (P-068.3, DA-07)."""
    snapshot = analytics_cache.get_snapshot(force_reload=True)
    return mappers.to_health_response(analytics_cache.get_cache_status(), snapshot)


def _rule_of(item: Union[ProductRecommendation, CustomerRecommendation]) -> UsefulRule:
    """Regra principal do item, usada pela curadoria (P-094)."""
    return item.rule


def get_product_cross_sell(sku: int, page_request: PageRequest) -> ProductCrossSellResponse:
    """Recomendação por Produto paginada (P-061, P-066)."""
    snapshot = _sufficient_snapshot()
    recommendations = curate(recommend_for_product(snapshot, sku), snapshot.catalog, rule_of=_rule_of)  # P-094
    context = mappers.PageContext(page_request, snapshot.reference_date.isoformat())
    return mappers.to_product_response(snapshot.catalog[sku], paginate(recommendations, page_request), context)


def get_customer_cross_sell(customer_code: int, page_request: PageRequest) -> CustomerCrossSellResponse:
    """Recomendação por Cliente paginada, com filtros antes da paginação (P-062 a P-064, P-063.5)."""
    snapshot = _sufficient_snapshot()
    result = recommend_for_customer(snapshot, customer_code)
    result = replace(result, items=tuple(curate(result.items, snapshot.catalog, rule_of=_rule_of)))  # P-094
    context = mappers.PageContext(page_request, snapshot.reference_date.isoformat(), snapshot.catalog)
    return mappers.to_customer_response(result, paginate(result.items, page_request), context)


def search_products(query: str, page_request: PageRequest) -> ProductSearchResponse:
    """Busca por código ou descrição no catálogo em cache, sem carregar as cestas (contrato §3.6)."""
    catalog = analytics_cache.get_catalog()
    matches = search_catalog(catalog.search_index, query)
    context = mappers.PageContext(page_request, catalog.reference_date.isoformat())
    return mappers.to_search_response(paginate(matches, page_request), context)


# ---------------------------------------------------------------------------
# F3: Churn de Clientes — Casos de Uso (P-117 a P-127; ADR-006 DA-01)
# ---------------------------------------------------------------------------
from src.modules.analytics.api.schemas import (
    ChurnCustomersResponse,
    CustomerChurnDetailResponse,
    InactiveChurnResponse,
)
from src.modules.analytics.domain.exceptions import CustomerChurnNotFoundError


def get_churn_customers(status: Optional[str], page_request: PageRequest) -> ChurnCustomersResponse:
    """Listagem paginada de clientes classificados por churn (P-123, P-124)."""
    customers = analytics_cache.get_churn_customers_list(status)
    summary_kpi = analytics_cache.get_churn_summary_stats()
    page = paginate(customers, page_request)
    now = analytics_cache._utc_now()
    ref_date = analytics_cache.business_date(now)
    context = mappers.PageContext(page_request, ref_date.isoformat())
    return mappers.to_churn_customers_response(page, summary_kpi, context)


def get_customer_churn_detail(customer_code: int) -> CustomerChurnDetailResponse:
    """Detalhamento explicativo e diagnóstico do cliente (P-126)."""
    summary = analytics_cache.get_customer_churn_detail(customer_code)
    if summary is None:
        raise CustomerChurnNotFoundError()
    now = analytics_cache._utc_now()
    ref_date = analytics_cache.business_date(now)
    return mappers.to_customer_churn_detail_response(summary, ref_date.isoformat())


def get_inactive_churn(page_request: PageRequest) -> InactiveChurnResponse:
    """Fila especializada de reativação de clientes inativos antigos (P-125)."""
    inactives = analytics_cache.get_inactive_churn_list()
    page = paginate(inactives, page_request)
    now = analytics_cache._utc_now()
    ref_date = analytics_cache.business_date(now)
    context = mappers.PageContext(page_request, ref_date.isoformat())
    return mappers.to_inactive_churn_response(page, context)


def list_catalog_products(
    page_request: PageRequest,
    query: Optional[str] = None,
    supplier: Optional[str] = None,
    stock_filter: str = "all",
    sort_by: str = "supplier_product",
    sort_dir: str = "asc",
    include_seasonality: bool = False,
) -> CatalogListResponse:
    """Lista, filtra e ordena o catálogo ativo em cache sem carregar as cestas (contrato §3.7, P-117)."""
    catalog = analytics_cache.get_catalog()
    filtered = filter_and_sort_catalog(
        catalog.search_index,
        query=query,
        supplier=supplier,
        stock_filter=stock_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    seasonality_summaries = None
    if include_seasonality:
        sales_df = _get_monthly_sales_df()
        catalog_dict = _get_catalog_dict()
        seasonality_summaries = calculate_seasonality_summaries(sales_df, catalog_dict)
    context = mappers.PageContext(page_request, catalog.reference_date.isoformat())
    return mappers.to_catalog_response(
        paginate(filtered, page_request),
        context,
        seasonality_summaries=seasonality_summaries,
    )


# ------------------------------------------------------------------ sazonalidade por produto (P-106..P-116; ADR-005)

import pandas as pd
from src.modules.analytics.api.schemas import (
    ANALYTICS_CONTRACT_VERSION,
    AnalyticsMeta,
    MonthlySeasonalityPointSchema,
    PagedMeta,
    SeasonalityData,
    SeasonalityPeakValleySchema,
    SeasonalityProduct,
    SeasonalityRankingItemSchema,
    SeasonalityRankingResponse,
    SeasonalityResponse,
)
from src.modules.analytics.domain.seasonality import (
    calculate_seasonality_rankings,
    calculate_seasonality_summaries,
    get_seasonality_index,
)


def _get_monthly_sales_df() -> pd.DataFrame:
    """Obtém DataFrame de vendas mensais líquidas via cache."""
    return analytics_cache.get_monthly_sales()


def _get_catalog_dict() -> dict[int, dict[str, Any]]:
    """Obtém mapa do catálogo ativo em cache."""
    cat = analytics_cache.get_catalog()
    return {
        entry.code: {
            "Codigo": entry.code,
            "Descricao": entry.description,
            "Fornecedor": entry.supplier,
            "Estoque": entry.stock,
            "Pc.Ultimo Custo": entry.unit_cost,
            "Pc.Venda": entry.price,
        }
        for entry in cat.entries.values()
    }


def get_product_seasonality(sku: int) -> SeasonalityResponse:
    """Caso de uso: Detecção de sazonalidade por produto (P-106 a P-113)."""
    sales_df = _get_monthly_sales_df()
    catalog = _get_catalog_dict()
    res = get_seasonality_index(sku=sku, monthly_sales_df=sales_df, catalog_dict=catalog)

    now_iso = datetime.now(timezone.utc).isoformat()
    meta = AnalyticsMeta(timestamp=now_iso, version=ANALYTICS_CONTRACT_VERSION, data_referencia=None)

    data = SeasonalityData(
        produto=SeasonalityProduct(
            codigo=res.produto.codigo,
            descricao=res.produto.descricao,
            fornecedor=res.produto.fornecedor,
            estoque=res.produto.estoque,
            preco_venda=res.produto.preco_venda,
        ),
        elegivel=res.elegivel,
        forca=res.forca,
        motivo_insuficiencia=res.motivo_insuficiencia,
        amplitude=res.amplitude,
        correlacao_yoy=res.correlacao_yoy,
        pico=SeasonalityPeakValleySchema(
            mes_inicio=res.pico.mes_inicio,
            mes_fim=res.pico.mes_fim,
            nome_periodo=res.pico.nome_periodo,
            indice=res.pico.indice,
            confianca=res.pico.confianca,
        ),
        vale=SeasonalityPeakValleySchema(
            mes_inicio=res.vale.mes_inicio,
            mes_fim=res.vale.mes_fim,
            nome_periodo=res.vale.nome_periodo,
            indice=res.vale.indice,
            confianca=res.vale.confianca,
        ),
        serie_mensal=[
            MonthlySeasonalityPointSchema(
                mes=p.mes,
                nome_mes=p.nome_mes,
                indice=p.indice,
                confianca=p.confianca,
                observacoes_disponiveis=p.observacoes_disponiveis,
                razao_2025=p.razao_2025,
                razao_2026=p.razao_2026,
                volume_liquido_historico=p.volume_liquido_historico,
                receita_liquida_historica=p.receita_liquida_historica,
            )
            for p in res.serie_mensal
        ],
    )

    return SeasonalityResponse(data=data, meta=meta)


def get_seasonality_ranking(order: str, page_request: PageRequest) -> SeasonalityRankingResponse:
    """Caso de uso: Rankings de sazonalidade paginados (P-114)."""
    sales_df = _get_monthly_sales_df()
    catalog = _get_catalog_dict()
    items, total = calculate_seasonality_rankings(
        monthly_sales_df=sales_df,
        catalog_dict=catalog,
        order=order,
        limit=page_request.limit,
        offset=page_request.offset,
    )

    now_iso = datetime.now(timezone.utc).isoformat()
    total_pages = (total + page_request.limit - 1) // page_request.limit if total > 0 else 0
    current_page = (page_request.offset // page_request.limit) + 1 if page_request.limit > 0 else 1

    paged_meta = PagedMeta(
        timestamp=now_iso,
        version=ANALYTICS_CONTRACT_VERSION,
        data_referencia=None,
        page=current_page,
        limit=page_request.limit,
        offset=page_request.offset,
        total_items=total,
        total_pages=total_pages,
    )

    ranking_items = [
        SeasonalityRankingItemSchema(
            sku=it.sku,
            descricao=it.descricao,
            fornecedor=it.fornecedor,
            forca=it.forca,
            amplitude=it.amplitude,
            mes_pico=it.mes_pico,
            mes_vale=it.mes_vale,
            faturamento_total=it.faturamento_total,
            motivo_insuficiencia=it.motivo_insuficiencia,
        )
        for it in items
    ]

    return SeasonalityRankingResponse(data=ranking_items, meta=paged_meta)


# ------------------------------------------------------------------ Elasticidade (F5 / P-095..P-105)

def _resolve_catalog_product(sku: int) -> Tuple[CatalogSnapshot, CatalogEntry]:
    """Obtém o catálogo em cache e valida a existência do SKU (P-096, ELA-001)."""
    catalog = analytics_cache.get_catalog()
    product = catalog.entries.get(sku)
    if product is None:
        raise ElasticityProductNotFoundError()
    return catalog, product


def _resolve_catalog_cost(product: CatalogEntry, current_price: float) -> Tuple[float, bool]:
    """Resolve custo unitário do catálogo com fallback defensivo de 60% quando zerado/ausente (P-101)."""
    if product.unit_cost > 0:
        return round(float(product.unit_cost), 2), bool(product.is_cost_estimated)
    return round(current_price * COST_FALLBACK_RATIO, 2), True


def get_product_elasticity(sku: int, page_request: PageRequest) -> ProductElasticityResponse:
    """Calcula a elasticidade do produto e lista seus clientes paginados (P-096, P-103)."""
    catalog, product = _resolve_catalog_product(sku)
    cutoff = catalog.reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    raw_points = sales_repository.fetch_product_price_points(sku, cutoff)
    prepared_points = prepare_price_points(raw_points)
    elasticity = estimate_product_elasticity(prepared_points)
    recent_volume_60d = sales_repository.fetch_product_recent_volume_60d(sku, cutoff, STOCK_TARGET_DAYS)

    raw_customers = sales_repository.fetch_product_customers(sku, cutoff)
    customer_items = []
    if not raw_customers.empty:
        for _, row in raw_customers.iterrows():
            c_code = int(row["customer_code"])
            c_orders = int(row["orders_count"])
            c_units = float(row["total_units"])
            c_res = estimate_customer_elasticity(
                product_elasticity=elasticity.coefficient,
                customer_empirical=elasticity.coefficient,
                orders_count=c_orders,
                customer_code=c_code,
                total_units=c_units,
            )
            customer_items.append(CustomerElasticityItem(
                customer_code=c_code,
                orders_count=c_orders,
                total_units=c_units,
                empirical_elasticity=c_res.empirical_elasticity,
                shrinkage_elasticity=c_res.shrinkage_elasticity,
                classification=c_res.classification,
                shrinkage_weight=c_res.shrinkage_weight,
            ))

    paged_customers = customer_items[page_request.offset : page_request.offset + page_request.limit]
    total_items = len(customer_items)
    total_pages = math.ceil(total_items / page_request.limit) if total_items > 0 else 0

    current_price = float(product.price)
    resolved_cost, is_cost_estimated = _resolve_catalog_cost(product, current_price)

    header = ProductHeader(
        code=product.code,
        description=product.description,
        supplier=product.supplier,
        current_price=current_price,
        cost_price=resolved_cost,
        stock=float(product.stock),
        is_cost_estimated=is_cost_estimated,
        recent_volume_60d=round(float(recent_volume_60d), 2),
        stock_target_days=STOCK_TARGET_DAYS,
    )
    metrics = ProductElasticityMetrics(
        coefficient=elasticity.coefficient,
        classification=elasticity.classification,
        r_squared=elasticity.r_squared,
        standard_error=elasticity.standard_error,
        confidence_interval=list(elasticity.confidence_interval),
        confidence_level=elasticity.confidence_level,
        is_reliable=elasticity.is_reliable,
        observations_count=elasticity.observations_count,
        fallback_applied=elasticity.fallback_applied,
        insight_message=elasticity.insight_message,
    )
    detail = ProductElasticityDetail(
        product=header,
        elasticity=metrics,
        customers=paged_customers,
    )
    meta = ResponseMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
        total_items=total_items,
        total_pages=total_pages,
        limit=page_request.limit,
        offset=page_request.offset,
    )
    return ProductElasticityResponse(data=detail, meta=meta)


def get_customer_elasticity(sku: int, customer_code: int) -> CustomerElasticityResponse:
    """Calcula a elasticidade individual do cliente sobre o produto via shrinkage (P-097)."""
    catalog, _ = _resolve_catalog_product(sku)
    cutoff = catalog.reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    raw_points = sales_repository.fetch_product_price_points(sku, cutoff)
    prepared_points = prepare_price_points(raw_points)
    prod_elasticity = estimate_product_elasticity(prepared_points)

    c_raw = sales_repository.fetch_single_customer_points(sku, customer_code, cutoff)
    if c_raw.empty:
        raise ElasticityCustomerWithoutHistoryError()

    c_prepared = prepare_price_points(c_raw)
    c_orders = int(c_raw["qtd"].count())
    c_units = float(c_prepared["qtd_liquida"].sum()) if not c_prepared.empty else 0.0
    c_emp = estimate_product_elasticity(c_prepared)

    c_res = estimate_customer_elasticity(
        product_elasticity=prod_elasticity.coefficient,
        customer_empirical=c_emp.coefficient,
        orders_count=c_orders,
        customer_code=customer_code,
        total_units=c_units,
    )

    detail = CustomerElasticityDetail(
        sku=sku,
        customer_code=customer_code,
        product_elasticity=prod_elasticity.coefficient,
        customer_empirical_elasticity=c_res.empirical_elasticity,
        customer_elasticity=c_res.shrinkage_elasticity,
        classification=c_res.classification,
        shrinkage_weight=c_res.shrinkage_weight,
        orders_count=c_orders,
        total_units=c_units,
        confidence_level=c_emp.confidence_level if c_emp.is_reliable else prod_elasticity.confidence_level,
        is_reliable=c_emp.is_reliable or prod_elasticity.is_reliable,
        insight_message=f"Cliente com {c_orders} pedidos analisados; elasticidade refinada via shrinkage para {c_res.shrinkage_elasticity:.2f}.",
    )
    meta = ResponseMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )
    return CustomerElasticityResponse(data=detail, meta=meta)


def simulate_price_change(request: ElasticitySimulationRequest) -> ElasticitySimulationResponse:
    """Simula impacto de reajuste de preço em volume 60d, receita, margem unitária/total e estoque (P-101)."""
    catalog, product = _resolve_catalog_product(request.sku)
    cutoff = catalog.reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    if request.customer_code:
        c_resp = get_customer_elasticity(request.sku, request.customer_code)
        applied_elasticity = c_resp.data.customer_elasticity
        base_volume = max(0.0, float(c_resp.data.total_units))
    else:
        raw_points = sales_repository.fetch_product_price_points(request.sku, cutoff)
        prepared_points = prepare_price_points(raw_points)
        prod_el = estimate_product_elasticity(prepared_points)
        applied_elasticity = prod_el.coefficient
        base_volume = sales_repository.fetch_product_recent_volume_60d(
            request.sku, cutoff, STOCK_TARGET_DAYS
        )

    is_price_override = request.current_price is not None
    current_price = float(request.current_price) if is_price_override else max(0.0, float(product.price))
    if request.cost_price is not None:
        cost_price = float(request.cost_price)
        is_cost_override = True
        is_cost_estimated = False
    else:
        cost_price, is_cost_estimated = _resolve_catalog_cost(product, current_price)
        is_cost_override = False

    impact = simulate_price_impact(
        elasticity=applied_elasticity,
        current_price=current_price,
        cost_price=cost_price,
        current_volume=base_volume,
        price_change_pct=request.price_change_pct,
        sku=request.sku,
        customer_code=request.customer_code,
        stock=float(product.stock),
        window_days=STOCK_TARGET_DAYS,
        is_cost_estimated=is_cost_estimated,
        is_cost_override=is_cost_override,
        is_price_override=is_price_override,
    )
    meta = ResponseMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )
    data = SimulationImpactData(
        sku=impact.sku,
        customer_code=impact.customer_code,
        applied_elasticity=impact.applied_elasticity,
        price_change_pct=impact.price_change_pct,
        current_price=impact.current_price,
        projected_price=impact.projected_price,
        current_volume=impact.current_volume,
        projected_volume=impact.projected_volume,
        volume_change_pct=impact.volume_change_pct,
        current_revenue=impact.current_revenue,
        projected_revenue=impact.projected_revenue,
        revenue_change_pct=impact.revenue_change_pct,
        revenue_change_abs=impact.revenue_change_abs,
        current_margin=impact.current_margin,
        projected_margin=impact.projected_margin,
        margin_change_pct=impact.margin_change_pct,
        margin_change_abs=impact.margin_change_abs,
        recommendation=impact.recommendation,
        cost_price=impact.cost_price,
        is_cost_estimated=impact.is_cost_estimated,
        is_cost_override=impact.is_cost_override,
        stock=impact.stock,
        stock_target_days=impact.stock_target_days,
        current_unit_margin=impact.current_unit_margin,
        projected_unit_margin=impact.projected_unit_margin,
        current_unit_margin_pct=impact.current_unit_margin_pct,
        projected_unit_margin_pct=impact.projected_unit_margin_pct,
        unit_margin_pct_change_pp=impact.unit_margin_pct_change_pp,
        volume_change_units=impact.volume_change_units,
        current_daily_units=impact.current_daily_units,
        projected_daily_units=impact.projected_daily_units,
        current_stock_days=impact.current_stock_days,
        projected_stock_days=impact.projected_stock_days,
        stock_days_delta=impact.stock_days_delta,
        is_price_override=impact.is_price_override,
    )
    return ElasticitySimulationResponse(data=data, meta=meta)
