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
    ChurnFilterOptionsData,
    ChurnFilterOptionsResponse,
    CustomerChurnDetailResponse,
    InactiveChurnResponse,
)
from src.modules.analytics.domain.exceptions import ChurnInvalidParametersError, CustomerChurnNotFoundError

_CHURN_SORT_KEYS = {
    "customerCode": lambda c: c.customer_code,
    "customerName": lambda c: c.customer_name.casefold(),
    "sellerName": lambda c: c.seller_name.casefold(),
    "city": lambda c: c.city.casefold(),
    "status": lambda c: c.status,
    "diasSemComprar": lambda c: c.dias_sem_comprar,
    "gapTipico": lambda c: c.gap_tipico,
    "faturamentoMedioMensal": lambda c: c.faturamento_medio_mensal,
    "scorePrioridade": lambda c: c.score_prioridade,
    "dataUltimoPedido": lambda c: c.data_ultimo_pedido.isoformat() if c.data_ultimo_pedido else None,
}


def _filter_and_sort_churn(
    items: list,
    q: Optional[str] = None,
    seller: Optional[str] = None,
    city: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
) -> list:
    filtered = items
    if q and q.strip():
        needle = q.strip().casefold()
        filtered = [
            c
            for c in filtered
            if needle in str(c.customer_code)
            or needle in c.customer_name.casefold()
            or needle in c.seller_name.casefold()
            or needle in c.city.casefold()
        ]
    if seller and seller.strip():
        s_needle = seller.strip().casefold()
        filtered = [c for c in filtered if c.seller_name.casefold() == s_needle]
    if city and city.strip():
        c_needle = city.strip().casefold()
        filtered = [c for c in filtered if c.city.casefold() == c_needle]

    if sort_by:
        key_fn = _CHURN_SORT_KEYS.get(sort_by)
        if key_fn is None:
            raise ChurnInvalidParametersError(fields=["sortBy"])
        non_null = [c for c in filtered if key_fn(c) is not None]
        nulls = [c for c in filtered if key_fn(c) is None]
        non_null.sort(key=key_fn, reverse=(sort_dir == "desc"))
        return non_null + nulls
    return filtered


def get_churn_customers(
    status: Optional[str],
    page_request: PageRequest,
    q: Optional[str] = None,
    seller: Optional[str] = None,
    city: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
) -> ChurnCustomersResponse:
    """Listagem paginada de clientes classificados por churn (P-123, P-124)."""
    customers = _filter_and_sort_churn(
        analytics_cache.get_churn_customers_list(status),
        q=q,
        seller=seller,
        city=city,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
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


def get_inactive_churn(
    page_request: PageRequest,
    q: Optional[str] = None,
    seller: Optional[str] = None,
    city: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
) -> InactiveChurnResponse:
    """Fila especializada de reativação de clientes inativos antigos (P-125)."""
    inactives = _filter_and_sort_churn(
        analytics_cache.get_inactive_churn_list(),
        q=q,
        seller=seller,
        city=city,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    page = paginate(inactives, page_request)
    now = analytics_cache._utc_now()
    ref_date = analytics_cache.business_date(now)
    context = mappers.PageContext(page_request, ref_date.isoformat())
    return mappers.to_inactive_churn_response(page, context)


def get_churn_filters() -> ChurnFilterOptionsResponse:
    """Opções distintas de vendedores e cidades para filtros da tela de churn."""
    sellers, cities = analytics_cache.get_churn_filter_options()
    now = analytics_cache._utc_now()
    ref_date = analytics_cache.business_date(now)
    return ChurnFilterOptionsResponse(
        data=ChurnFilterOptionsData(sellers=sellers, cities=cities),
        meta=mappers.AnalyticsMeta(
            timestamp=mappers.utc_timestamp(),
            version="1.0.0",
            data_referencia=ref_date.isoformat(),
        ),
    )


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


# ---------------------------------------------------------------------------
# F2: Viabilidade de Produto Novo (P-139 a P-149; ADR-008)
# ---------------------------------------------------------------------------
from src.modules.analytics.api.schemas import (
    AnalyticsMeta,
    MonthlyForecastItem,
    NewProductAggregatedTotals,
    NewProductFinancialViability,
    NewProductForecastData,
    NewProductForecastRequest,
    NewProductForecastResponse,
    NewProductMarketCeiling,
    NewProductOptionsData,
    NewProductOptionsResponse,
    SimilarProductItem,
)
from src.modules.analytics.domain.exceptions import (
    NewProductDatabaseUnavailableError,
    NewProductInvalidParametersError,
    NewProductInvalidSupplierError,
    NewProductInvalidTypeError,
)
from src.modules.analytics.domain.new_product import (
    SeasonalityProvider,
    SeasonalityResult as NewProductSeasonalityResult,
    apply_seasonality_and_clamp,
    compute_conservative_curve,
    compute_mature_ceiling,
    evaluate_financial_viability,
    filter_eligible_launches,
    find_similars,
)
from src.modules.analytics.domain.seasonality import get_seasonality_index
from src.modules.analytics.repository.errors import AnalyticsDataSourceError


def _get_new_product_options() -> dict:
    """Wrapper de cache para opções de catálogo (substituível em testes)."""
    return analytics_cache.get_new_product_options()


def _get_new_product_candidates_df(tipo: str):
    """Wrapper de cache para lançamentos reais do tipo (substituível em testes)."""
    return analytics_cache.get_new_product_candidates(tipo)


def _get_mature_product_distribution_df(tipo: str):
    """Wrapper de cache para distribuição de produtos maduros do tipo (substituível em testes)."""
    return analytics_cache.get_mature_product_distribution(tipo)


class _F1CategorySeasonalityProvider(SeasonalityProvider):
    """Adaptador desacoplado que consulta `get_seasonality_index` (F1) sobre os SKUs da categoria."""

    def __init__(self, similar_skus: list[int]) -> None:
        self._similar_skus = similar_skus
        self._loaded = False
        self._monthly_df = None
        self._catalog_dict: dict = {}

    def _ensure_f1_data(self) -> bool:
        if self._loaded:
            return self._monthly_df is not None and not self._monthly_df.empty
        self._loaded = True
        try:
            monthly_df = analytics_cache.get_monthly_sales()
            catalog_snap = analytics_cache.get_catalog()
            self._monthly_df = monthly_df
            self._catalog_dict = {
                sku: {
                    "codigo": entry.code,
                    "descricao": entry.description,
                    "fornecedor": entry.supplier,
                    "estoque": entry.stock,
                    "preco_venda": entry.price,
                }
                for sku, entry in catalog_snap.entries.items()
            }
            return not monthly_df.empty
        except Exception:
            self._monthly_df = None
            return False

    def get_category_seasonality(self, category: str, month: int) -> Optional[NewProductSeasonalityResult]:
        if not self._ensure_f1_data() or not self._similar_skus:
            return None

        valid_indices: list[float] = []
        confidences: list[str] = []
        for sku in self._similar_skus:
            try:
                res = get_seasonality_index(sku, self._monthly_df, self._catalog_dict)
            except Exception:
                continue
            if not res.elegivel:
                continue
            point = next((p for p in res.serie_mensal if p.mes == month), None)
            if point is not None and point.confianca in ("ALTA", "MEDIA"):
                valid_indices.append(float(point.indice))
                confidences.append(point.confianca)

        if not valid_indices:
            return NewProductSeasonalityResult(index=1.0, confidence="BAIXA")

        valid_indices.sort()
        mid = len(valid_indices) // 2
        median_idx = (
            valid_indices[mid]
            if len(valid_indices) % 2 == 1
            else (valid_indices[mid - 1] + valid_indices[mid]) / 2.0
        )
        best_conf = "ALTA" if "ALTA" in confidences else "MEDIA"
        return NewProductSeasonalityResult(index=median_idx, confidence=best_conf)


def get_new_product_options() -> NewProductOptionsResponse:
    """Retorna listas deduplicadas e ordenadas de tipos e fornecedores ativos (P-141)."""
    try:
        options = _get_new_product_options()
    except AnalyticsDataSourceError:
        raise NewProductDatabaseUnavailableError() from None

    ref_date = analytics_cache.business_date(analytics_cache._utc_now()).isoformat()
    return NewProductOptionsResponse(
        data=NewProductOptionsData(
            tipos=list(options.get("tipos", [])),
            fornecedores=list(options.get("fornecedores", [])),
        ),
        meta=AnalyticsMeta(
            timestamp=mappers.utc_timestamp(),
            version="1.0.0",
            data_referencia=ref_date,
        ),
    )


def _validate_new_product_request(request: NewProductForecastRequest) -> None:
    """Valida invariantes numéricas sem ecoar valores recebidos (P-140.3, LGPD-05)."""
    if request.preco_venda_previsto <= 0:
        raise NewProductInvalidParametersError(
            message="O preço de venda previsto deve ser estritamente positivo.",
            fields=("precoVendaPrevisto",),
        )
    if request.custo_unitario is not None:
        if request.custo_unitario <= 0:
            raise NewProductInvalidParametersError(
                message="O custo unitário deve ser estritamente positivo.",
                fields=("custoUnitario",),
            )
        if request.custo_unitario > request.preco_venda_previsto:
            raise NewProductInvalidParametersError(
                message="O custo unitário não pode ser superior ao preço de venda previsto.",
                fields=("custoUnitario",),
            )
    if request.margem_minima_desejada is not None and not (0.0 <= request.margem_minima_desejada <= 1.0):
        raise NewProductInvalidParametersError(
            message="A margem mínima desejada deve estar entre 0% e 100%.",
            fields=("margemMinimaDesejada",),
        )
    if request.horizon_months not in (1, 2, 3):
        raise NewProductInvalidParametersError(
            message="O horizonte de projeção deve estar entre 1 e 3 meses.",
            fields=("horizonMonths",),
        )


def forecast_new_product(request: NewProductForecastRequest) -> NewProductForecastResponse:
    """Orquestra validação, seleção de similares, curva conservadora, F1 e viabilidade (P-139..P-149)."""
    _validate_new_product_request(request)

    try:
        options = _get_new_product_options()
    except AnalyticsDataSourceError:
        raise NewProductDatabaseUnavailableError() from None

    tipos_map = {t.strip().casefold(): t for t in options.get("tipos", [])}
    forn_map = {f.strip().casefold(): f for f in options.get("fornecedores", [])}

    canonical_tipo = tipos_map.get(request.tipo.strip().casefold())
    if canonical_tipo is None:
        raise NewProductInvalidTypeError()

    canonical_fornecedor = forn_map.get(request.fornecedor.strip().casefold())
    if canonical_fornecedor is None:
        raise NewProductInvalidSupplierError()

    try:
        candidates_df = _get_new_product_candidates_df(canonical_tipo)
        mature_df = _get_mature_product_distribution_df(canonical_tipo)
    except AnalyticsDataSourceError:
        raise NewProductDatabaseUnavailableError() from None

    ref_date = analytics_cache.business_date(analytics_cache._utc_now())
    eligible_df = filter_eligible_launches(candidates_df, reference_date=ref_date)

    similars = find_similars(
        candidates_df=eligible_df,
        tipo=canonical_tipo,
        fornecedor=canonical_fornecedor,
        descricao=request.descricao,
        preco_venda_previsto=request.preco_venda_previsto,
    )
    base_curve = compute_conservative_curve(similars, horizon_months=request.horizon_months)

    seasonality_provider = _F1CategorySeasonalityProvider([s.sku for s in similars])
    monthly_items: list[MonthlyForecastItem] = []
    statuses: list[str] = []

    for point in base_curve:
        cal_month = ((ref_date.month - 1 + (point.month - 1)) % 12) + 1
        final_qty, factor, conf, status = apply_seasonality_and_clamp(
            base_quantity=point.conservative_quantity,
            p25_quantity=point.similar_p25_quantity,
            category=canonical_tipo,
            calendar_month=cal_month,
            provider=seasonality_provider,
        )
        statuses.append(status)
        revenue = round(final_qty * request.preco_venda_previsto, 2)
        gross_margin = (
            round(final_qty * (request.preco_venda_previsto - request.custo_unitario), 2)
            if request.custo_unitario is not None
            else None
        )
        monthly_items.append(
            MonthlyForecastItem(
                month=point.month,
                calendar_month=cal_month,
                quantity=final_qty,
                revenue=revenue,
                gross_margin=gross_margin,
                p10_quantity=point.p10_quantity,
                conservative_quantity=final_qty,
                p50_quantity=point.p50_quantity,
                similar_p25_quantity=point.similar_p25_quantity,
                seasonality_factor=round(factor, 2),
                seasonality_confidence=conf,
            )
        )

    if "APPLIED" in statuses:
        overall_seasonality_status = "APPLIED"
    elif "FALLBACK_NEUTRAL" in statuses:
        overall_seasonality_status = "FALLBACK_NEUTRAL"
    else:
        overall_seasonality_status = "UNAVAILABLE"

    total_qty = sum(item.quantity for item in monthly_items)
    total_rev = round(sum(item.revenue for item in monthly_items), 2)
    total_margin = (
        round(sum(item.gross_margin for item in monthly_items if item.gross_margin is not None), 2)
        if request.custo_unitario is not None
        else None
    )
    horizon_count = len(monthly_items)
    aggregated = NewProductAggregatedTotals(
        total_quantity=total_qty,
        total_revenue=total_rev,
        total_gross_margin=total_margin,
        average_monthly_quantity=int(round(total_qty / horizon_count)) if horizon_count else 0,
        average_monthly_revenue=round(total_rev / horizon_count, 2) if horizon_count else 0.0,
    )

    fin = evaluate_financial_viability(
        preco_venda=request.preco_venda_previsto,
        custo_unitario=request.custo_unitario,
        margem_minima_desejada=request.margem_minima_desejada,
    )
    financial_viability = NewProductFinancialViability(
        preco_venda=fin.preco_venda,
        custo_unitario=fin.custo_unitario,
        margem_bruta_unitaria=fin.margem_bruta_unitaria,
        margem_bruta_percentual=fin.margem_bruta_percentual,
        margem_minima_desejada=fin.margem_minima_desejada,
        viavel=fin.viavel,
        parecer=fin.parecer,
    )

    teto_p75 = compute_mature_ceiling(mature_df, canonical_tipo)
    market_ceiling = NewProductMarketCeiling(
        teto_maduro_p75=teto_p75,
        descricao=(
            f"Percentil 75 das vendas mensais de produtos maduros do tipo {canonical_tipo} "
            "(referencial de mercado pleno; não representa meta de lançamento)."
        ),
    )

    similars_items = [
        SimilarProductItem(
            sku=str(s.sku),
            descricao=s.descricao,
            fornecedor=s.fornecedor,
            primeira_venda=s.primeira_venda.isoformat(),
            preco_historico=s.preco_historico,
            score_final=round(s.score_final, 4),
            score_fornecedor=round(s.score_fornecedor, 4),
            score_preco=round(s.score_preco, 4),
            score_tfidf=round(s.score_tfidf, 4),
            quantidades_primeiros_meses=list(s.quantidades_primeiros_meses),
        )
        for s in similars
    ]

    data = NewProductForecastData(
        input_summary=request,
        monthly_forecast=monthly_items,
        seasonality_status=overall_seasonality_status,
        aggregated_totals=aggregated,
        financial_viability=financial_viability,
        market_ceiling=market_ceiling,
        similars_used=similars_items,
        methodology_notice=(
            "Estimativa calculada sob critério conservador (Percentil 25 dos similares com haircut de 0,70). "
            "Historicamente, mais de 80% dos lançamentos reais superam estes volumes."
        ),
    )

    return NewProductForecastResponse(
        data=data,
        meta=AnalyticsMeta(
            timestamp=mappers.utc_timestamp(),
            version="1.0.0",
            data_referencia=ref_date.isoformat(),
        ),
    )
