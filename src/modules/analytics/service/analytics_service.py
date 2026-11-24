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
    CannibalizationInsufficientHistoryError,
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
# F6: Canibalização e Substituição (P-128 a P-138; ADR-007)
# ---------------------------------------------------------------------------

import asyncio
import threading
import time
from datetime import date as _date

from src.modules.analytics.api.schemas import (
    AffectedProductDTO,
    CannibalizationDataDTO,
    CannibalizationMeta,
    CannibalizationResponse,
    ControlGroupDTO,
    ElasticityDecompositionDTO,
    ElasticityIntegrationDTO,
    NetImpactDTO,
    PeriodMetricsDTO,
    SubstituteCandidateDTO,
    SubstitutionDataDTO,
    SubstitutionMeta,
    SubstitutionResponse,
    TargetProductDTO,
    TimelinePointDTO,
)
from src.modules.analytics.domain.cannibalization import (
    CACHE_TTL_HOURS as _CAN_CACHE_TTL_HOURS,
    DEFAULT_ANALYSIS_WINDOW_WEEKS,
    MAX_CANDIDATE_SUBSTITUTES,
    MIN_JACCARD_SIMILARITY,
    apply_returns_netting,
    build_pre_post_windows,
    calculate_net_impact,
    classify_impact,
    compute_did_significance_and_ci,
    detect_product_events,
    estimate_difference_in_differences,
    find_candidate_substitutes,
    resolve_unit_margin,
    select_control_group,
)
from src.modules.analytics.domain.elasticity_interface import (
    CrossElasticityProvider,
    NullCrossElasticityProvider,
    decompose_cross_elasticity,
)
from src.modules.analytics.domain.exceptions import (
    AnalyticsDomainException,
    CannibalizationProcessingError,
    CannibalizationProductNotFoundError,
)
from src.modules.analytics.domain.fdr_correction import benjamini_hochberg
from src.modules.analytics.repository.errors import AnalyticsInfrastructureException

_CAN_CACHE_LOCK = threading.Lock()
_CAN_SUB_CACHE: dict = {}


def _get_cannibalization_catalog_cached() -> Tuple[dict, _date]:
    now_dt = datetime.now(timezone.utc).date()
    with _CAN_CACHE_LOCK:
        entry = _CAN_SUB_CACHE.get("catalog")
        if entry is not None:
            loaded_ts, catalog_data, ref_date = entry
            if (time.monotonic() - loaded_ts) < (_CAN_CACHE_TTL_HOURS * 3600):
                return catalog_data, ref_date

    catalog_data = sales_repository.fetch_cannibalization_catalog()
    with _CAN_CACHE_LOCK:
        _CAN_SUB_CACHE["catalog"] = (time.monotonic(), catalog_data, now_dt)
    return catalog_data, now_dt


def _get_cached_substitutes_for_sku(
    sku_str: str,
    catalog: dict,
    cutoff: _date,
    min_jaccard: float,
    limit: int,
) -> list:
    cache_key = ("subs", sku_str, round(min_jaccard, 4), limit)
    with _CAN_CACHE_LOCK:
        entry = _CAN_SUB_CACHE.get(cache_key)
        if entry is not None:
            loaded_ts, cached_list = entry
            if (time.monotonic() - loaded_ts) < (_CAN_CACHE_TTL_HOURS * 3600):
                return cached_list

    # LGPD-CAN-04 / LGPD-CAN-05: buyers_by_sku existe apenas em memória volátil e nunca entra em cache
    buyers_by_sku = sales_repository.fetch_buyers_by_sku(cutoff)
    candidates = find_candidate_substitutes(
        target_sku=sku_str,
        catalog=catalog,
        buyers_by_sku=buyers_by_sku,
        min_jaccard=min_jaccard,
        limit=limit,
    )
    del buyers_by_sku

    with _CAN_CACHE_LOCK:
        _CAN_SUB_CACHE[cache_key] = (time.monotonic(), candidates)
    return candidates


def get_substitution_candidates(
    sku: str,
    min_jaccard: float = MIN_JACCARD_SIMILARITY,
    limit: int = MAX_CANDIDATE_SUBSTITUTES,
) -> SubstitutionResponse:
    """Lista produtos substitutos por similaridade de categoria e Jaccard de compradores (P-128)."""
    started = time.perf_counter()
    sku_str = str(sku)
    try:
        catalog, ref_date = _get_cannibalization_catalog_cached()
        target = catalog.get(sku_str)
        if target is None or not target.get("active", True):
            raise CannibalizationProductNotFoundError()

        cutoff = ref_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)
        candidates = _get_cached_substitutes_for_sku(sku_str, catalog, cutoff, min_jaccard, limit)

        dtos = [
            SubstituteCandidateDTO(
                sku=c.sku,
                description=c.description,
                category=c.category,
                jaccard_similarity=round(c.jaccard_similarity, 4),
                common_buyers_count=c.common_buyers_count,
                current_price=round(c.current_price, 2),
                current_stock=c.current_stock,
            )
            for c in candidates
        ]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return SubstitutionResponse(
            data=SubstitutionDataDTO(
                target_sku=sku_str,
                target_description=target["description"],
                target_category=target["category"],
                target_current_price=round(float(target["current_price"]), 2),
                target_stock=int(target["current_stock"]),
                substitutes=dtos,
            ),
            meta=SubstitutionMeta(
                timestamp=mappers.utc_timestamp(),
                version=ANALYTICS_CONTRACT_VERSION,
                data_referencia=ref_date.isoformat(),
                target_sku=sku_str,
                total_found=len(dtos),
                execution_time_ms=elapsed_ms,
            ),
        )
    except (AnalyticsDomainException, AnalyticsInfrastructureException):
        raise
    except Exception:
        raise CannibalizationProcessingError() from None


def get_cannibalization_analysis(
    sku: str,
    event_type: str = "promo",
    event_date: Optional[_date] = None,
    window_weeks: int = DEFAULT_ANALYSIS_WINDOW_WEEKS,
    include_non_significant: bool = False,
    elasticity_provider: Optional[CrossElasticityProvider] = None,
) -> CannibalizationResponse:
    """Executa análise causal DiD + FDR Benjamini-Hochberg de canibalização para um SKU (P-128 a P-138)."""
    started = time.perf_counter()
    sku_str = str(sku)
    provider = elasticity_provider or NullCrossElasticityProvider()

    try:
        catalog, ref_date = _get_cannibalization_catalog_cached()
        target = catalog.get(sku_str)
        if target is None or not target.get("active", True):
            raise CannibalizationProductNotFoundError()

        cutoff = ref_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)
        history_start = ref_date - timedelta(days=730)

        raw_target_sales = sales_repository.fetch_daily_sales_for_skus(
            [int(sku_str)], history_start, ref_date
        )
        net_target_sales = apply_returns_netting(raw_target_sales)
        promo_calendar = sales_repository.fetch_promo_calendar(int(sku_str), cutoff)

        detected = detect_product_events(
            sku=sku_str,
            sales_series=net_target_sales,
            promo_calendar=promo_calendar,
            event_type=event_type,
            event_date=event_date,
            window_weeks=window_weeks,
            history_start=history_start,
            history_end=ref_date,
        )

        target_windows = build_pre_post_windows(
            event_date=detected.event_date,
            window_weeks=window_weeks,
            sales_series=net_target_sales,
            history_start=None if event_type == "launch" else history_start,
            history_end=ref_date,
            allow_empty_pre=(event_type == "launch"),
        )

        target_pre_price = target_windows.pre_avg_price or float(target["current_price"])
        target_post_price = target_windows.post_avg_price or float(target["current_price"])
        target_price_ratio = (
            ((target_post_price - target_pre_price) / target_pre_price)
            if target_pre_price > 0
            else 0.0
        )
        price_direction = detected.price_direction
        avg_price_change_pct = detected.avg_price_change_pct
        if abs(avg_price_change_pct) < 1e-9 and abs(target_price_ratio) > 1e-9:
            avg_price_change_pct = target_price_ratio * 100.0
        if price_direction == "NONE" and abs(target_price_ratio) >= 0.01:
            price_direction = "PRICE_DROP" if target_price_ratio < 0 else "PRICE_HIKE"

        target_unit_margin_pre, target_fb_pre = resolve_unit_margin(target_pre_price, target.get("last_cost"))
        target_unit_margin_post, target_fb_post = resolve_unit_margin(target_post_price, target.get("last_cost"))
        target_fb = target_fb_pre or target_fb_post

        target_pre_margin = target_windows.pre_total_volume * target_unit_margin_pre
        target_post_margin = target_windows.post_total_volume * target_unit_margin_post
        target_dv = target_windows.post_total_volume - target_windows.pre_total_volume
        target_dv_pct = (
            ((target_dv / target_windows.pre_total_volume) * 100.0)
            if target_windows.pre_total_volume > 0
            else 0.0
        )
        target_dr = target_windows.post_total_revenue - target_windows.pre_total_revenue
        target_dm = target_post_margin - target_pre_margin

        candidates = _get_cached_substitutes_for_sku(
            sku_str, catalog, cutoff, MIN_JACCARD_SIMILARITY, MAX_CANDIDATE_SUBSTITUTES
        )
        sub_skus = {c.sku for c in candidates}

        # Carrega vendas dos substitutos e candidatos a controle no mesmo intervalo
        pool_entries = [
            p for p in catalog.values()
            if p["sku"] != sku_str and (
                p["category"] == target["category"]
                or p["supplier"] == target["supplier"]
                or p["sku"] in sub_skus
            )
        ]
        if len(pool_entries) < 5:
            pool_entries = [p for p in catalog.values() if p["sku"] != sku_str][:100]

        skus_to_fetch = [int(p["sku"]) for p in pool_entries]
        raw_pool = sales_repository.fetch_daily_sales_for_skus(
            skus_to_fetch, target_windows.pre_start, target_windows.post_end
        )
        net_pool = apply_returns_netting(raw_pool)
        promo_skus = sales_repository.fetch_promo_skus_in_window(
            target_windows.pre_start, target_windows.post_end
        )

        windows_by_sku = {}
        control_inputs = []
        for p in pool_entries:
            p_sku = p["sku"]
            p_df = net_pool[net_pool["sku"] == p_sku] if not net_pool.empty else net_pool
            w = build_pre_post_windows(
                event_date=detected.event_date,
                window_weeks=window_weeks,
                sales_series=p_df,
                allow_empty_pre=True,
            )
            windows_by_sku[p_sku] = w
            p_change = (
                ((w.post_avg_price - w.pre_avg_price) / w.pre_avg_price)
                if w.pre_avg_price > 0
                else 0.0
            )
            control_inputs.append(
                {
                    "sku": p_sku,
                    "category": p["category"],
                    "supplier": p["supplier"],
                    "in_promo": p_sku in promo_skus,
                    "price_change_pct": p_change,
                    "pre_vol": w.pre_total_volume,
                    "post_vol": w.post_total_volume,
                }
            )

        try:
            control_group = select_control_group(
                target_sku=sku_str,
                target_category=target["category"],
                target_supplier=target["supplier"],
                substitute_skus=sub_skus,
                category_products=control_inputs,
            )
        except CannibalizationInsufficientHistoryError:
            fetched_skus = {p["sku"] for p in pool_entries} | {sku_str}
            global_entries = [
                p for p in catalog.values() if p["sku"] not in fetched_skus
            ][:100]
            if not global_entries:
                raise
            raw_global = sales_repository.fetch_daily_sales_for_skus(
                [int(p["sku"]) for p in global_entries],
                target_windows.pre_start,
                target_windows.post_end,
            )
            net_global = apply_returns_netting(raw_global)
            for p in global_entries:
                p_sku = p["sku"]
                p_df = net_global[net_global["sku"] == p_sku] if not net_global.empty else net_global
                w = build_pre_post_windows(
                    event_date=detected.event_date,
                    window_weeks=window_weeks,
                    sales_series=p_df,
                    allow_empty_pre=True,
                )
                windows_by_sku[p_sku] = w
                p_change = (
                    ((w.post_avg_price - w.pre_avg_price) / w.pre_avg_price)
                    if w.pre_avg_price > 0
                    else 0.0
                )
                control_inputs.append(
                    {
                        "sku": p_sku,
                        "category": p["category"],
                        "supplier": p["supplier"],
                        "in_promo": p_sku in promo_skus,
                        "price_change_pct": p_change,
                        "pre_vol": w.pre_total_volume,
                        "post_vol": w.post_total_volume,
                    }
                )
            control_group = select_control_group(
                target_sku=sku_str,
                target_category=target["category"],
                target_supplier=target["supplier"],
                substitute_skus=sub_skus,
                category_products=control_inputs,
            )

        # Estima DiD e p-valores para todos os substitutos candidatos
        did_rows = []
        raw_p_values = []
        for cand in candidates:
            cw = windows_by_sku[cand.sku]
            did = estimate_difference_in_differences(
                candidate_pre_volume=cw.pre_total_volume,
                candidate_post_volume=cw.post_total_volume,
                control_pre_volumes=control_group.pre_volumes,
                control_post_volumes=control_group.post_volumes,
            )
            p_val, ci = compute_did_significance_and_ci(
                cw.pre_daily["qty"].to_numpy(),
                cw.post_daily["qty"].to_numpy(),
                did.growth_factor,
            )
            did_rows.append((cand, cw, did, p_val, ci))
            raw_p_values.append(p_val)

        fdr_res = benjamini_hochberg(raw_p_values)
        growth_factor = (
            (sum(control_group.post_volumes) / sum(control_group.pre_volumes))
            if sum(control_group.pre_volumes) > 0
            else 1.0
        )

        affected_dtos: List[AffectedProductDTO] = []
        net_items_input = []
        integrated_count = 0

        for idx, (cand, cw, did, p_val, ci) in enumerate(did_rows):
            q_val = fdr_res.q_values[idx]
            classification = classify_impact(target_dv, did.delta_volume, q_val)
            is_sig = classification != "SEM_EFEITO"

            cand_entry = catalog[cand.sku]
            unit_price = cw.post_avg_price or float(cand_entry["current_price"])
            unit_margin, fb_used = resolve_unit_margin(unit_price, cand_entry.get("last_cost"))
            delta_rev = did.delta_volume * unit_price
            delta_mrg = did.delta_volume * unit_margin

            cross_eps = asyncio.run(provider.get_cross_elasticity(sku_str, cand.sku))
            decomp = decompose_cross_elasticity(
                cross_elasticity=cross_eps,
                candidate_pre_volume=cw.pre_total_volume,
                target_price_change_ratio=target_price_ratio,
                total_delta_volume=did.delta_volume,
            )
            decomp_dto = None
            if decomp is not None:
                integrated_count += 1
                decomp_dto = ElasticityDecompositionDTO(
                    cross_elasticity=round(decomp.cross_elasticity, 4),
                    price_explained_delta_volume=round(decomp.price_explained_delta_volume, 2),
                    residual_delta_volume=round(decomp.residual_delta_volume, 2),
                    price_explained_share=round(decomp.price_explained_share, 4),
                )

            net_items_input.append(
                {
                    "delta_volume": did.delta_volume,
                    "unit_price": unit_price,
                    "unit_margin": unit_margin,
                    "is_significant": is_sig,
                }
            )

            if is_sig or include_non_significant:
                affected_dtos.append(
                    AffectedProductDTO(
                        sku=cand.sku,
                        description=cand.description,
                        category=cand.category,
                        jaccard_similarity=round(cand.jaccard_similarity, 4),
                        common_buyers_count=cand.common_buyers_count,
                        pre_volume=round(cw.pre_total_volume, 2),
                        post_volume=round(cw.post_total_volume, 2),
                        counterfactual_volume=round(did.counterfactual_volume, 2),
                        delta_volume=round(did.delta_volume, 2),
                        delta_volume_pct=round(did.delta_volume_pct, 2),
                        unit_price=round(unit_price, 2),
                        unit_margin=round(unit_margin, 2),
                        cost_fallback_used=fb_used,
                        delta_revenue=round(delta_rev, 2),
                        delta_margin=round(delta_mrg, 2),
                        classification=classification,
                        p_value=round(p_val, 6),
                        q_value=round(q_val, 6),
                        is_significant=is_sig,
                        confidence_interval=[round(ci[0], 2), round(ci[1], 2)],
                        elasticity_decomposition=decomp_dto,
                    )
                )

        net_res = calculate_net_impact(
            target_metrics={
                "delta_volume": target_dv,
                "delta_revenue": target_dr,
                "delta_margin": target_dm,
            },
            affected_items=net_items_input,
        )

        # Constrói timeline semanal simétrica (-W..-1 e 1..W) com limite explícito (S6680)
        safe_weeks = max(2, min(int(window_weeks), 12))
        timeline: List[TimelinePointDTO] = []
        for w_idx in range(-safe_weeks, safe_weeks + 1):
            if w_idx == 0:
                continue
            if w_idx < 0:
                offset_days = (safe_weeks + w_idx) * 7
                w_start = target_windows.pre_start + timedelta(days=offset_days)
                w_end = w_start + timedelta(days=6)
                t_vol = float(
                    target_windows.pre_daily[
                        (target_windows.pre_daily["date"] >= w_start)
                        & (target_windows.pre_daily["date"] <= w_end)
                    ]["qty"].sum()
                )
                c_vol = sum(
                    float(
                        windows_by_sku[c_sku].pre_daily[
                            (windows_by_sku[c_sku].pre_daily["date"] >= w_start)
                            & (windows_by_sku[c_sku].pre_daily["date"] <= w_end)
                        ]["qty"].sum()
                    )
                    for c_sku in control_group.skus
                )
                period_label = "PRE"
            else:
                offset_days = (w_idx - 1) * 7
                w_start = target_windows.post_start + timedelta(days=offset_days)
                w_end = w_start + timedelta(days=6)
                t_vol = float(
                    target_windows.post_daily[
                        (target_windows.post_daily["date"] >= w_start)
                        & (target_windows.post_daily["date"] <= w_end)
                    ]["qty"].sum()
                )
                c_vol = sum(
                    float(
                        windows_by_sku[c_sku].post_daily[
                            (windows_by_sku[c_sku].post_daily["date"] >= w_start)
                            & (windows_by_sku[c_sku].post_daily["date"] <= w_end)
                        ]["qty"].sum()
                    )
                    for c_sku in control_group.skus
                )
                period_label = "POST"

            timeline.append(
                TimelinePointDTO(
                    week_offset=w_idx,
                    start_date=w_start.isoformat(),
                    end_date=w_end.isoformat(),
                    period=period_label,
                    target_volume=round(t_vol, 2),
                    control_total_volume=round(c_vol, 2),
                )
            )

        if integrated_count == 0:
            el_status = "NAO_INTEGRADO"
            el_msg = "Módulo de Elasticidade-Preço (Fase F5) ainda não acoplado. Decomposição de choque de preço operando em modo gracioso."
        elif integrated_count == len(did_rows):
            el_status = "INTEGRADO"
            el_msg = "Decomposição de choque de preço integrada ao módulo de Elasticidade (Fase F5)."
        else:
            el_status = "PARCIAL"
            el_msg = "Integração parcial com o módulo de Elasticidade (Fase F5)."

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        summary_msg = (
            f"Variação líquida de {net_res.net_delta_volume:+.2f} un., "
            f"receita de R$ {net_res.net_delta_revenue:+.2f} e margem de R$ {net_res.net_delta_margin:+.2f} "
            f"({net_res.commercial_verdict})."
        )

        return CannibalizationResponse(
            data=CannibalizationDataDTO(
                target_product=TargetProductDTO(
                    sku=sku_str,
                    description=target["description"],
                    category=target["category"],
                    event_type=detected.event_type,
                    event_date=detected.event_date.isoformat(),
                    price_direction=price_direction,
                    avg_price_change_pct=round(avg_price_change_pct, 2),
                    cost_fallback_used=target_fb,
                    pre_period=PeriodMetricsDTO(
                        start_date=target_windows.pre_start.isoformat(),
                        end_date=target_windows.pre_end.isoformat(),
                        volume=round(target_windows.pre_total_volume, 2),
                        avg_price=round(target_pre_price, 2),
                        revenue=round(target_windows.pre_total_revenue, 2),
                        estimated_margin=round(target_pre_margin, 2),
                    ),
                    post_period=PeriodMetricsDTO(
                        start_date=target_windows.post_start.isoformat(),
                        end_date=target_windows.post_end.isoformat(),
                        volume=round(target_windows.post_total_volume, 2),
                        avg_price=round(target_post_price, 2),
                        revenue=round(target_windows.post_total_revenue, 2),
                        estimated_margin=round(target_post_margin, 2),
                    ),
                    delta_volume=round(target_dv, 2),
                    delta_volume_pct=round(target_dv_pct, 2),
                    delta_revenue=round(target_dr, 2),
                    delta_margin=round(target_dm, 2),
                ),
                control_group=ControlGroupDTO(
                    category=target["category"],
                    sample_size=control_group.sample_size,
                    growth_factor=round(growth_factor, 4),
                    control_strategy=control_group.control_strategy,
                    is_expanded_control=control_group.is_expanded_control,
                    description=f"{control_group.sample_size} produtos estáveis ({control_group.control_strategy}) sem promoções ou alterações de preço no período.",
                ),
                timeline_series=timeline,
                affected_products=affected_dtos,
                net_impact=NetImpactDTO(
                    target_delta_volume=round(net_res.target_delta_volume, 2),
                    affected_delta_volume=round(net_res.affected_delta_volume, 2),
                    net_delta_volume=round(net_res.net_delta_volume, 2),
                    target_delta_revenue=round(net_res.target_delta_revenue, 2),
                    affected_delta_revenue=round(net_res.affected_delta_revenue, 2),
                    net_delta_revenue=round(net_res.net_delta_revenue, 2),
                    target_delta_margin=round(net_res.target_delta_margin, 2),
                    affected_delta_margin=round(net_res.affected_delta_margin, 2),
                    net_delta_margin=round(net_res.net_delta_margin, 2),
                    commercial_verdict=net_res.commercial_verdict,
                    summary_message=summary_msg,
                ),
                elasticity_integration=ElasticityIntegrationDTO(
                    status=el_status,
                    message=el_msg,
                ),
            ),
            meta=CannibalizationMeta(
                timestamp=mappers.utc_timestamp(),
                version=ANALYTICS_CONTRACT_VERSION,
                data_referencia=ref_date.isoformat(),
                sku=sku_str,
                event_type=detected.event_type,
                window_weeks=window_weeks,
                execution_time_ms=elapsed_ms,
            ),
        )
    except (AnalyticsDomainException, AnalyticsInfrastructureException):
        raise
    except Exception:
        raise CannibalizationProcessingError() from None


# ------------------------------------------------------------------ Canibalização v2 — Relatório Global e Equilíbrio de Preço (F6 v2)

from src.modules.analytics.api.schemas import (
    CannibalizationReportDataDTO,
    CannibalizationReportKpisDTO,
    CannibalizationReportMeta,
    CannibalizationReportResponse,
    CannibalizationVictimBaseDTO,
    CannibalizationVictimDetailDataDTO,
    CannibalizationVictimDetailMeta,
    CannibalizationVictimDetailResponse,
    CannibalizationVictimSummaryDTO,
    CannibalizerDetailDTO,
    CannibalizerSummaryDTO,
    PeriodRangeDTO,
)
from src.modules.analytics.domain.cannibalization_report import (
    CACHE_TTL_HOURS as _CAN_REPORT_CACHE_TTL_HOURS,
    DEFAULT_MIN_DROP_PCT,
    DEFAULT_MIN_MIGRATED_CLIENTS,
    DEFAULT_WINDOW_DAYS,
    CannibalizerEvaluation,
    MigrationSnapshot,
    VictimEvaluation,
    WindowBoundaries,
    build_cannibalization_report,
    build_cannibalization_victim_detail,
    build_migration_snapshot,
    compute_window_boundaries,
)

from src.modules.analytics.service import product_affinity_service

_CAN_REPORT_CACHE_LOCK = threading.Lock()
_CAN_REPORT_SNAPSHOT_CACHE: dict = {}


def reset_cannibalization_report_cache() -> None:
    """Limpa o cache em memória do relatório v2 de canibalização (apoio a testes)."""
    with _CAN_REPORT_CACHE_LOCK:
        _CAN_REPORT_SNAPSHOT_CACHE.clear()
    with _CAN_CACHE_LOCK:
        _CAN_SUB_CACHE.clear()


def _get_cannibalization_migration_snapshot_cached(
    window_days: int,
    ref_date: _date,
    catalog: dict,
) -> Tuple[MigrationSnapshot, WindowBoundaries]:
    """
    Obtém ou constrói o `MigrationSnapshot` agregado por `(window_days, ref_date)` com TTL de 6h (P-137.2).
    LGPD-CAN-04/05: `raw_rows` e `by_cli` são descartados antes de gravar no cache.
    """
    boundaries = compute_window_boundaries(ref_date, window_days)
    cache_key = ("cannibalization_v2", window_days, ref_date.isoformat())

    with _CAN_REPORT_CACHE_LOCK:
        entry = _CAN_REPORT_SNAPSHOT_CACHE.get(cache_key)
        if entry is not None:
            loaded_ts, cached_snapshot = entry
            if (time.monotonic() - loaded_ts) < (_CAN_REPORT_CACHE_TTL_HOURS * 3600):
                return cached_snapshot, boundaries

        raw_rows = sales_repository.fetch_customer_sku_window_sales(
            pre_start_date=boundaries.pre_start,
            mid_date=boundaries.mid_date,
            reference_date=boundaries.reference_date,
        )
        affinity_map = product_affinity_service.get_affinity_lookup_map()
        snapshot = build_migration_snapshot(raw_rows, catalog, affinity_map=affinity_map)
        del raw_rows
        _CAN_REPORT_SNAPSHOT_CACHE[cache_key] = (time.monotonic(), snapshot)
        return snapshot, boundaries


def _to_cannibalizer_summary_dto(item: CannibalizerEvaluation) -> CannibalizerSummaryDTO:
    return CannibalizerSummaryDTO(
        sku=item.sku,
        description=item.description,
        supplier=item.supplier,
        migrated_clients=item.migrated_clients,
        migrated_revenue=item.migrated_revenue,
        share_of_cannibalization_pct=item.share_of_cannibalization_pct,
        current_price=item.current_price,
        unit_margin=item.unit_margin,
        margin_pct=item.margin_pct,
        cost_fallback_used=item.cost_fallback_used,
        price_gap_pct=item.price_gap_pct,
        net_margin_impact=item.net_margin_impact,
        mechanism=item.mechanism,
        suggested_victim_price=item.suggested_victim_price,
        suggested_cannibal_price=item.suggested_cannibal_price,
        projected_price_gap_pct=item.projected_price_gap_pct,
        action_summary=item.action_summary,
    )


def _to_cannibalizer_detail_dto(item: CannibalizerEvaluation) -> CannibalizerDetailDTO:
    return CannibalizerDetailDTO(
        sku=item.sku,
        description=item.description,
        category=item.category,
        supplier=item.supplier,
        migrated_clients=item.migrated_clients,
        gross_clients_to_cannibal=item.gross_clients_to_cannibal,
        reverse_clients_to_victim=item.reverse_clients_to_victim,
        migrated_revenue=item.migrated_revenue,
        share_of_cannibalization_pct=item.share_of_cannibalization_pct,
        pre_revenue=item.pre_revenue,
        cur_revenue=item.cur_revenue,
        current_price=item.current_price,
        unit_cost=item.unit_cost,
        unit_margin=item.unit_margin,
        margin_pct=item.margin_pct,
        cost_fallback_used=item.cost_fallback_used,
        current_stock=item.current_stock,
        price_gap_pct=item.price_gap_pct,
        net_margin_impact=item.net_margin_impact,
        mechanism=item.mechanism,
        suggested_victim_price=item.suggested_victim_price,
        suggested_cannibal_price=item.suggested_cannibal_price,
        projected_price_gap_pct=item.projected_price_gap_pct,
        victim_margin_floor_price=item.victim_margin_floor_price,
        action_summary=item.action_summary,
    )


def _to_victim_base_dto(item: VictimEvaluation) -> CannibalizationVictimBaseDTO:
    return CannibalizationVictimBaseDTO(
        sku=item.sku,
        description=item.description,
        category=item.category,
        supplier=item.supplier,
        pre_revenue=item.pre_revenue,
        cur_revenue=item.cur_revenue,
        revenue_drop=item.revenue_drop,
        revenue_drop_pct=item.revenue_drop_pct,
        cannibalized_revenue=item.cannibalized_revenue,
        cannibalized_revenue_pct=item.cannibalized_revenue_pct,
        drop_explained_pct=item.drop_explained_pct,
        current_price=item.current_price,
        unit_cost=item.unit_cost,
        unit_margin=item.unit_margin,
        margin_pct=item.margin_pct,
        cost_fallback_used=item.cost_fallback_used,
        current_stock=item.current_stock,
        cannibalizer_count=item.cannibalizer_count,
        net_margin_impact=item.net_margin_impact,
    )


def _to_victim_summary_dto(item: VictimEvaluation) -> CannibalizationVictimSummaryDTO:
    assert item.top_cannibal is not None
    return CannibalizationVictimSummaryDTO(
        sku=item.sku,
        description=item.description,
        category=item.category,
        supplier=item.supplier,
        pre_revenue=item.pre_revenue,
        cur_revenue=item.cur_revenue,
        revenue_drop=item.revenue_drop,
        revenue_drop_pct=item.revenue_drop_pct,
        cannibalized_revenue=item.cannibalized_revenue,
        cannibalized_revenue_pct=item.cannibalized_revenue_pct,
        drop_explained_pct=item.drop_explained_pct,
        current_price=item.current_price,
        unit_cost=item.unit_cost,
        unit_margin=item.unit_margin,
        margin_pct=item.margin_pct,
        cost_fallback_used=item.cost_fallback_used,
        current_stock=item.current_stock,
        cannibalizer_count=item.cannibalizer_count,
        net_margin_impact=item.net_margin_impact,
        top_cannibal=_to_cannibalizer_summary_dto(item.top_cannibal),
        cannibalizers=[_to_cannibalizer_summary_dto(c) for c in item.cannibalizers],
    )


def get_cannibalization_report(
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_drop_pct: float = DEFAULT_MIN_DROP_PCT,
    min_migrated_clients: int = DEFAULT_MIN_MIGRATED_CLIENTS,
    category: Optional[str] = None,
    supplier: Optional[str] = None,
    mechanism: Optional[str] = None,
    search: Optional[str] = None,
) -> CannibalizationReportResponse:
    """
    Retorna o Relatório Global de Canibalização por Migração de Clientes e Equilíbrio de Preço (P-128..P-138).
    """
    started = time.perf_counter()
    try:
        catalog, ref_date = _get_cannibalization_catalog_cached()
        snapshot, boundaries = _get_cannibalization_migration_snapshot_cached(
            window_days=window_days,
            ref_date=ref_date,
            catalog=catalog,
        )
        report = build_cannibalization_report(
            snapshot=snapshot,
            catalog=catalog,
            min_drop_pct=min_drop_pct,
            min_migrated_clients=min_migrated_clients,
            category=category,
            supplier=supplier,
            mechanism=mechanism,
            search=search,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CannibalizationReportResponse(
            data=CannibalizationReportDataDTO(
                kpis=CannibalizationReportKpisDTO(
                    total_victims=report.kpis.total_victims,
                    total_cannibalized_revenue=report.kpis.total_cannibalized_revenue,
                    avg_cannibalized_revenue_pct=report.kpis.avg_cannibalized_revenue_pct,
                    total_net_margin_impact=report.kpis.total_net_margin_impact,
                    margin_destroying_pairs_count=report.kpis.margin_destroying_pairs_count,
                ),
                available_categories=list(report.available_categories),
                available_suppliers=list(report.available_suppliers),
                victims=[_to_victim_summary_dto(v) for v in report.victims],
            ),
            meta=CannibalizationReportMeta(
                timestamp=mappers.utc_timestamp(),
                version=ANALYTICS_CONTRACT_VERSION,
                data_referencia=ref_date.isoformat(),
                window_days=window_days,
                min_drop_pct=min_drop_pct,
                min_migrated_clients=min_migrated_clients,
                pre_period=PeriodRangeDTO(
                    start_date=boundaries.pre_period.start_date.isoformat(),
                    end_date=boundaries.pre_period.end_date.isoformat(),
                ),
                cur_period=PeriodRangeDTO(
                    start_date=boundaries.cur_period.start_date.isoformat(),
                    end_date=boundaries.cur_period.end_date.isoformat(),
                ),
                total_found=report.kpis.total_victims,
                execution_time_ms=elapsed_ms,
            ),
        )
    except (AnalyticsDomainException, AnalyticsInfrastructureException):
        raise
    except Exception:
        raise CannibalizationProcessingError() from None


def get_cannibalization_sku_detail(
    sku: str,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_drop_pct: float = DEFAULT_MIN_DROP_PCT,
    min_migrated_clients: int = DEFAULT_MIN_MIGRATED_CLIENTS,
) -> CannibalizationVictimDetailResponse:
    """
    Retorna o detalhe completo de uma vítima específica e seus canibalizadores (P-136.2).
    """
    started = time.perf_counter()
    sku_str = str(sku)
    try:
        catalog, ref_date = _get_cannibalization_catalog_cached()
        snapshot, boundaries = _get_cannibalization_migration_snapshot_cached(
            window_days=window_days,
            ref_date=ref_date,
            catalog=catalog,
        )
        detail = build_cannibalization_victim_detail(
            sku=sku_str,
            snapshot=snapshot,
            catalog=catalog,
            min_drop_pct=min_drop_pct,
            min_migrated_clients=min_migrated_clients,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CannibalizationVictimDetailResponse(
            data=CannibalizationVictimDetailDataDTO(
                is_cannibalized=detail.is_cannibalized,
                victim=_to_victim_base_dto(detail.victim),
                cannibalizers=[_to_cannibalizer_detail_dto(c) for c in detail.cannibalizers],
            ),
            meta=CannibalizationVictimDetailMeta(
                timestamp=mappers.utc_timestamp(),
                version=ANALYTICS_CONTRACT_VERSION,
                data_referencia=ref_date.isoformat(),
                sku=sku_str,
                window_days=window_days,
                pre_period=PeriodRangeDTO(
                    start_date=boundaries.pre_period.start_date.isoformat(),
                    end_date=boundaries.pre_period.end_date.isoformat(),
                ),
                cur_period=PeriodRangeDTO(
                    start_date=boundaries.cur_period.start_date.isoformat(),
                    end_date=boundaries.cur_period.end_date.isoformat(),
                ),
                execution_time_ms=elapsed_ms,
            ),
        )
    except (AnalyticsDomainException, AnalyticsInfrastructureException):
        raise
    except Exception:
        raise CannibalizationProcessingError() from None


# Alias de compatibilidade
get_cannibalization_victim_detail = get_cannibalization_sku_detail
