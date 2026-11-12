"""
Casos de uso do módulo Analytics Comercial (P-061 a P-069; ADR-002 DA-06, DA-07, DA-09).

Orquestra cache -> domínio -> curadoria (P-094) -> paginação -> mapper. Ordem de avaliação do contrato §3.3: a validação
(400) já aconteceu na rota; aqui vêm a carga do snapshot (503), a base suficiente (422), a existência
do SKU/cliente (404) e a lista (200). Sem `try/except`: erros sobem ao handler global. Sem log de
cliente, recomendação ou payload (LGPD-04).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Union

from src.modules.analytics.api import mappers
from src.modules.analytics.api.schemas import (
    AnalyticsHealthResponse,
    CustomerCrossSellResponse,
    ProductCrossSellResponse,
    ProductSearchResponse,
)
from src.modules.analytics.domain.cross_sell import ProductRecommendation, UsefulRule, recommend_for_product
from src.modules.analytics.domain.cross_sell_customer import CustomerRecommendation, recommend_for_customer
from src.modules.analytics.domain.exceptions import InsufficientBaseError
from src.modules.analytics.domain.pagination import PageRequest, paginate
from src.modules.analytics.domain.recommendation_curation import curate
from src.modules.analytics.domain.product_search import search_products as search_catalog
from src.modules.analytics.service import analytics_cache
from src.modules.analytics.service.analytics_cache import AnalyticsSnapshot


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
