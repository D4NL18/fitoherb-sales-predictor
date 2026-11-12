"""
Rotas REST do módulo Analytics Comercial (contrato `analytics-cross-sell` 1.1.0, ADR-002 DA-01).

As rotas só recebem e validam a entrada (tipos e faixas, P-066.2/P-067: 400 `XSL-004` via handler
global), chamam o serviço pelo módulo (`analytics_service.<caso_de_uso>`) e devolvem o envelope.
Sem regra de negócio e sem `try/except` (o handler global traduz os erros). Rotas síncronas: a carga
usa pyodbc e mineração em CPU, então o FastAPI as executa no threadpool.
Autenticação: middleware HTTP Basic global em produção (P-033, LGPD-10).
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query
from pydantic import AfterValidator

from src.modules.analytics.api.schemas import (
    AnalyticsErrorResponse,
    AnalyticsHealthResponse,
    CustomerCrossSellResponse,
    ProductCrossSellResponse,
    ProductSearchResponse,
)
from src.modules.analytics.domain.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, PageRequest
from src.modules.analytics.domain.product_search import (
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    is_valid_search_query,
)
from src.modules.analytics.service import analytics_service

MAX_INT32 = 2_147_483_647  # contrato §3.3/§3.4: sku e customerCode de 1 a 2.147.483.647
MIN_PAGE_LIMIT = 1
MIN_OFFSET = 0


def _validate_search_query(query: str) -> str:
    """Regra de `q` do contrato §3.6; o `ValueError` vira 400 `XSL-004` com `fields: ["q"]`."""
    if not is_valid_search_query(query):
        raise ValueError("q fora da faixa permitida")
    return query


SkuPath = Annotated[int, Path(gt=0, le=MAX_INT32, description="Código (`Codigo`) do produto consultado.")]
CustomerCodePath = Annotated[int, Path(alias="customerCode", gt=0, le=MAX_INT32,
                                       description="Código do cliente (`Cod Cliente`).")]
LimitQuery = Annotated[int, Query(ge=MIN_PAGE_LIMIT, le=MAX_PAGE_LIMIT, description="Tamanho da página (1 a 200).")]
OffsetQuery = Annotated[int, Query(ge=MIN_OFFSET, description="Deslocamento (>= 0).")]
SearchQuery = Annotated[
    str, Query(description="Código ou trecho da descrição."), AfterValidator(_validate_search_query),
]
SearchLimitQuery = Annotated[
    int, Query(ge=MIN_PAGE_LIMIT, le=MAX_SEARCH_LIMIT, description="Máximo de resultados (1 a 20)."),
]

_ERROR = {"model": AnalyticsErrorResponse}
_CROSS_SELL_ERRORS = {
    400: {**_ERROR, "description": "XSL-004: parâmetros inválidos."},
    404: {**_ERROR, "description": "XSL-001 (produto) ou XSL-002 (cliente)."},
    422: {**_ERROR, "description": "XSL-003: base insuficiente."},
    503: {**_ERROR, "description": "ANL-001: base de vendas indisponível."},
}

analytics_router = APIRouter(prefix="/analytics", tags=["Analytics Comercial"])


@analytics_router.get("/health", response_model=AnalyticsHealthResponse, summary="Estado do cache do módulo",
                      description="Informa o estado do cache sem disparar carga nem acessar o banco (P-069).")
def get_health() -> AnalyticsHealthResponse:
    return analytics_service.get_health()


@analytics_router.post("/cache/reload", response_model=AnalyticsHealthResponse, summary="Recarga manual da base",
                       description="Recarrega a base respeitando o lock e o intervalo mínimo de 15 min (P-068.3).",
                       responses={429: {**_ERROR, "description": "ANL-002: recarga recente."},
                                  503: _CROSS_SELL_ERRORS[503]})
def reload_cache() -> AnalyticsHealthResponse:
    return analytics_service.reload_cache()


@analytics_router.get("/cross-sell/product/{sku}", response_model=ProductCrossSellResponse,
                      summary="Recomendação de cross-sell por produto", responses=_CROSS_SELL_ERRORS,
                      description="Quem compra o produto também leva o quê (P-061), com explicação (P-065).")
def get_product_cross_sell(sku: SkuPath, limit: LimitQuery = DEFAULT_PAGE_LIMIT,
                           offset: OffsetQuery = MIN_OFFSET) -> ProductCrossSellResponse:
    return analytics_service.get_product_cross_sell(sku, PageRequest(limit=limit, offset=offset))


@analytics_router.get("/cross-sell/customer/{customerCode}", response_model=CustomerCrossSellResponse,
                      summary="Recomendação de cross-sell por cliente", responses=_CROSS_SELL_ERRORS,
                      description="O que oferecer ao cliente (P-062 a P-064). O código não é ecoado (LGPD-03).")
def get_customer_cross_sell(customer_code: CustomerCodePath, limit: LimitQuery = DEFAULT_PAGE_LIMIT,
                            offset: OffsetQuery = MIN_OFFSET) -> CustomerCrossSellResponse:
    return analytics_service.get_customer_cross_sell(customer_code, PageRequest(limit=limit, offset=offset))


@analytics_router.get("/products/search", response_model=ProductSearchResponse,
                      summary="Busca de produto por código ou descrição",
                      description="Busca no catálogo em cache, sem carregar as cestas (contrato §3.6).",
                      responses={400: _CROSS_SELL_ERRORS[400], 503: _CROSS_SELL_ERRORS[503]})
def search_products(q: SearchQuery, limit: SearchLimitQuery = DEFAULT_SEARCH_LIMIT,
                    offset: OffsetQuery = MIN_OFFSET) -> ProductSearchResponse:
    return analytics_service.search_products(q, PageRequest(limit=limit, offset=offset))
