"""
Casos de uso do módulo Analytics Comercial (P-061 a P-069; ADR-002 DA-06, DA-07, DA-09).

Orquestra cache -> domínio -> curadoria (P-094) -> paginação -> mapper. Ordem de avaliação do contrato §3.3: a validação
(400) já aconteceu na rota; aqui vêm a carga do snapshot (503), a base suficiente (422), a existência
do SKU/cliente (404) e a lista (200). Sem `try/except`: erros sobem ao handler global. Sem log de
cliente, recomendação ou payload (LGPD-04).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Tuple, Union

from src.modules.analytics.api import mappers
from src.modules.analytics.api.schemas import (
    AnalyticsHealthResponse,
    CustomerCrossSellResponse,
    ProductCrossSellResponse,
    ProductSearchResponse,
)
from src.modules.analytics.domain.cross_sell import (
    CatalogEntry,
    ProductRecommendation,
    UsefulRule,
    recommend_for_product,
)
from src.modules.analytics.domain.cross_sell_customer import CustomerRecommendation, recommend_for_customer
from src.modules.analytics.domain.exceptions import InsufficientBaseError
from src.modules.analytics.domain.pagination import PageRequest, paginate
from src.modules.analytics.domain.recommendation_curation import curate
from src.modules.analytics.domain.product_search import search_products as search_catalog
from src.modules.analytics.service import analytics_cache
from src.modules.analytics.service.analytics_cache import (
    CUTOFF_DAYS_AFTER_REFERENCE,
    AnalyticsSnapshot,
    CatalogSnapshot,
)
import math
from datetime import datetime, timedelta, timezone

from src.modules.analytics.api.schemas import (
    CustomerElasticityDetail,
    CustomerElasticityItem,
    CustomerElasticityResponse,
    ElasticitySimulationRequest,
    ElasticitySimulationResponse,
    ProductElasticityDetail,
    ProductElasticityResponse,
    ProductHeader,
    ResponseMeta,
)
from src.modules.analytics.domain.elasticity import (
    estimate_customer_elasticity,
    estimate_product_elasticity,
    prepare_price_points,
    simulate_price_impact,
)
from src.modules.analytics.domain.exceptions import (
    ElasticityCustomerWithoutHistoryError,
    ElasticityProductNotFoundError,
)
from src.modules.analytics.repository import sales_repository


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


# ------------------------------------------------------------------ Elasticidade (F5 / P-095..P-105)

def _resolve_catalog_product(sku: int) -> Tuple[CatalogSnapshot, CatalogEntry]:
    """Obtém o catálogo em cache e valida a existência do SKU (P-096, ELA-001)."""
    catalog = analytics_cache.get_catalog()
    product = catalog.entries.get(sku)
    if product is None:
        raise ElasticityProductNotFoundError()
    return catalog, product


def get_product_elasticity(sku: int, page_request: PageRequest) -> ProductElasticityResponse:
    """Calcula a elasticidade do produto e lista seus clientes paginados (P-096, P-103)."""
    catalog, product = _resolve_catalog_product(sku)
    cutoff = catalog.reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    raw_points = sales_repository.fetch_product_price_points(sku, cutoff)
    prepared_points = prepare_price_points(raw_points)
    elasticity = estimate_product_elasticity(prepared_points)

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

    header = ProductHeader(
        code=product.code,
        description=product.description,
        supplier=product.supplier,
        current_price=float(product.price),
        cost_price=float(product.unit_cost),
        stock=float(product.stock),
    )
    detail = ProductElasticityDetail(
        product=header,
        elasticity={
            "coefficient": elasticity.coefficient,
            "classification": elasticity.classification,
            "rSquared": elasticity.r_squared,
            "standardError": elasticity.standard_error,
            "confidenceInterval": list(elasticity.confidence_interval),
            "confidenceLevel": elasticity.confidence_level,
            "isReliable": elasticity.is_reliable,
            "observationsCount": elasticity.observations_count,
            "fallbackApplied": elasticity.fallback_applied,
            "insightMessage": elasticity.insight_message,
        },
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
    """Simula impacto de reajuste de preço em volume, receita e margem (P-101)."""
    catalog, product = _resolve_catalog_product(request.sku)
    cutoff = catalog.reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    if request.customer_code:
        c_resp = get_customer_elasticity(request.sku, request.customer_code)
        applied_elasticity = c_resp.data.customer_elasticity
        base_volume = c_resp.data.total_units if c_resp.data.total_units > 0 else 100.0
    else:
        raw_points = sales_repository.fetch_product_price_points(request.sku, cutoff)
        prepared_points = prepare_price_points(raw_points)
        prod_el = estimate_product_elasticity(prepared_points)
        applied_elasticity = prod_el.coefficient
        base_volume = float(prepared_points["qtd_liquida"].sum()) if not prepared_points.empty else 100.0

    current_price = float(product.price) if product.price > 0 else 10.0
    cost_price = float(product.unit_cost) if product.unit_cost > 0 else (current_price * 0.6)

    impact = simulate_price_impact(
        elasticity=applied_elasticity,
        current_price=current_price,
        cost_price=cost_price,
        current_volume=base_volume,
        price_change_pct=request.price_change_pct,
        sku=request.sku,
        customer_code=request.customer_code,
    )
    meta = ResponseMeta(
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="1.0.0",
    )
    return ElasticitySimulationResponse(
        data={
            "sku": impact.sku,
            "customerCode": impact.customer_code,
            "appliedElasticity": impact.applied_elasticity,
            "priceChangePct": impact.price_change_pct,
            "currentPrice": impact.current_price,
            "projectedPrice": impact.projected_price,
            "currentVolume": impact.current_volume,
            "projectedVolume": impact.projected_volume,
            "volumeChangePct": impact.volume_change_pct,
            "currentRevenue": impact.current_revenue,
            "projectedRevenue": impact.projected_revenue,
            "revenueChangePct": impact.revenue_change_pct,
            "revenueChangeAbs": impact.revenue_change_abs,
            "currentMargin": impact.current_margin,
            "projectedMargin": impact.projected_margin,
            "marginChangePct": impact.margin_change_pct,
            "marginChangeAbs": impact.margin_change_abs,
            "recommendation": impact.recommendation,
        },
        meta=meta,
    )
