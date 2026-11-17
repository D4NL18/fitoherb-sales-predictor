"""
Roteador FastAPI para os serviços da Tendência de Vendas (ADR-003 DA-08).
Rotas isoladas com TrendAPIRoute, sem dependência de handlers globais.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Union
from fastapi import APIRouter, Depends

from src.modules.sales_trend.api.mappers import (
    map_products_response,
    map_supplier_detail_response,
    map_suppliers_response,
)
from src.modules.sales_trend.api.query_params import TrendDetailQuery, TrendListQuery
from src.modules.sales_trend.api.route import TrendAPIRoute
from src.modules.sales_trend.api.schemas import (
    ProductTrendResponse,
    SupplierDetailResponse,
    SupplierTrendResponse,
    TrendErrorResponse,
)
from src.modules.sales_trend.service.sales_trend_service import (
    get_cache_state,
    get_sales_trend,
    get_supplier_products,
    reload_cache,
)

sales_trend_router = APIRouter(
    prefix="/sales-trend",
    tags=["Sales Trend"],
    route_class=TrendAPIRoute,
    responses={
        400: {"model": TrendErrorResponse, "description": "TND-001: Parâmetros inválidos"},
        404: {"model": TrendErrorResponse, "description": "TND-003: Fornecedor não encontrado"},
        422: {"model": TrendErrorResponse, "description": "TND-002: Mês-Base sem dados suficientes"},
        429: {"model": TrendErrorResponse, "description": "TND-005: Recarga recente em menos de 15 min"},
        503: {"model": TrendErrorResponse, "description": "TND-004: Base de dados indisponível"},
    },
)


@sales_trend_router.get(
    "",
    summary="Listagem da Tendência de Vendas (por Produto ou Fornecedor)",
    response_model=Union[ProductTrendResponse, SupplierTrendResponse],
)
def list_sales_trend(query: TrendListQuery = Depends()):
    """Lista a variação % de vendas em 1, 3, 6 e 12 meses para produtos ativos ou fornecedores."""
    service_res = get_sales_trend(
        base_month_str=query.base_month,
        metric=query.metric,
        group_by=query.group_by,
        sort_window=query.sort_window,
        sort_dir=query.sort_dir,
        view=query.view,
        q=query.q,
        min_volume=query.min_volume,
        limit=query.limit,
        offset=query.offset,
        comparison_mode=query.comparison_mode,
    )
    if query.group_by == "supplier":
        return map_suppliers_response(service_res)
    return map_products_response(service_res)


@sales_trend_router.get(
    "/supplier-products",
    summary="Detalhe de produtos de um fornecedor",
    response_model=SupplierDetailResponse,
)
def list_supplier_products(query: TrendDetailQuery = Depends()):
    """Retorna os produtos de um fornecedor com a contribuição em p.p. e em valor."""
    detail_res, snapshot, base_month_idx = get_supplier_products(
        supplier_key=query.supplier_key,
        base_month_str=query.base_month,
        metric=query.metric,
        sort_by=query.sort_by,
        sort_dir=query.sort_dir,
        q=query.q,
        limit=query.limit,
        offset=query.offset,
        sort_window=query.sort_window,
        comparison_mode=query.comparison_mode,
    )
    return map_supplier_detail_response(
        detail_res=detail_res,
        snapshot=snapshot,
        base_month_idx=base_month_idx,
        metric=query.metric,
        sort_by=query.sort_by,
        sort_dir=query.sort_dir,
        limit=query.limit,
        offset=query.offset,
        sort_window=query.sort_window,
        comparison_mode=query.comparison_mode,
    )


@sales_trend_router.get(
    "/health",
    summary="Health check do módulo e estado do snapshot",
)
def sales_trend_health() -> Dict[str, Any]:
    """Retorna o estado do cache e data de referência sem disparar leitura de banco."""
    cache_state = get_cache_state()
    return {
        "data": cache_state,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        },
    }


@sales_trend_router.post(
    "/reload",
    summary="Recarga manual forçada do snapshot",
)
def sales_trend_reload() -> Dict[str, Any]:
    """Dispara recarga forçada do snapshot em memória (rate-limit de 15 minutos)."""
    reload_state = reload_cache()
    return {
        "data": reload_state,
        "meta": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
        },
    }
