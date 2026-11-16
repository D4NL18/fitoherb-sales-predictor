"""
Rotas REST do módulo Analytics Comercial (contrato `analytics-cross-sell` 1.1.0, `analytics-sazonalidade` 1.0.0, ADR-002 DA-01, ADR-005).

As rotas só recebem e validam a entrada (tipos e faixas, P-066.2/P-067: 400 `XSL-004`/`SEA-002` via handler
global), chamam o serviço pelo módulo (`analytics_service.<caso_de_uso>`) e devolvem o envelope.
Sem regra de negócio e sem `try/except` (o handler global traduz os erros). Rotas síncronas: a carga
usa pyodbc e mineração em CPU, então o FastAPI as executa no threadpool.
Autenticação: middleware HTTP Basic global em produção (P-033, LGPD-10).
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Path, Query
from pydantic import AfterValidator

from src.modules.analytics.api.schemas import (
    AnalyticsErrorResponse,
    AnalyticsHealthResponse,
    CatalogListResponse,
    CustomerCrossSellResponse,
    ProductCrossSellResponse,
    ProductSearchResponse,
    SeasonalityRankingResponse,
    SeasonalityResponse,
    CustomerElasticityResponse,
    ElasticitySimulationRequest,
    ElasticitySimulationResponse,
    ProductElasticityResponse,
)
from src.modules.analytics.domain.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, PageRequest
from src.modules.analytics.domain.product_search import (
    DEFAULT_CATALOG_LIMIT,
    DEFAULT_SEARCH_LIMIT,
    MAX_CATALOG_LIMIT,
    MAX_QUERY_LENGTH,
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


def _validate_ranking_order(order: str) -> str:
    """Validação de ordenação do ranking de sazonalidade (P-114)."""
    if order not in ("most", "least"):
        raise ValueError("order deve ser 'most' ou 'least'")
    return order


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
CatalogLimitQuery = Annotated[
    int, Query(ge=MIN_PAGE_LIMIT, le=MAX_CATALOG_LIMIT, description="Tamanho da página do catálogo (1 a 5000)."),
]
StockFilterLiteral = Literal["all", "in_stock", "out_of_stock"]
CatalogSortByLiteral = Literal["product", "sku", "stock", "price", "relevance", "supplier_product"]
SortDirLiteral = Literal["asc", "desc"]
RankingOrderQuery = Annotated[
    str, Query(description="Ordenação do ranking: 'most' ou 'least'."), AfterValidator(_validate_ranking_order),
]

_ERROR = {"model": AnalyticsErrorResponse}
_CROSS_SELL_ERRORS = {
    400: {**_ERROR, "description": "XSL-004: parâmetros inválidos."},
    404: {**_ERROR, "description": "XSL-001 (produto) ou XSL-002 (cliente)."},
    422: {**_ERROR, "description": "XSL-003: base insuficiente."},
    503: {**_ERROR, "description": "ANL-001: base de vendas indisponível."},
}
_SEASONALITY_ERRORS = {
    400: {**_ERROR, "description": "SEA-002: parâmetros inválidos."},
    404: {**_ERROR, "description": "SEA-001: produto não encontrado."},
    422: {**_ERROR, "description": "SEA-003: base insuficiente."},
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


@analytics_router.get(
    "/products",
    response_model=CatalogListResponse,
    summary="Listagem paginada do catálogo ativo",
    description="Lista o catálogo ativo em cache com filtros e ordenação, sem carregar as cestas (contrato §3.7).",
    responses={400: _CROSS_SELL_ERRORS[400], 503: _CROSS_SELL_ERRORS[503]},
)
def list_products(
    q: Optional[str] = Query(default=None, max_length=MAX_QUERY_LENGTH, description="Busca inteligente opcional."),
    supplier: Optional[str] = Query(default=None, max_length=120, description="Filtro por fornecedor."),
    stock_filter: StockFilterLiteral = Query(default="all", alias="stockFilter", description="Filtro de estoque."),
    sort_by: CatalogSortByLiteral = Query(
        default="supplier_product", alias="sortBy", description="Critério de ordenação."
    ),
    sort_dir: SortDirLiteral = Query(default="asc", alias="sortDir", description="Direção da ordenação."),
    limit: CatalogLimitQuery = DEFAULT_CATALOG_LIMIT,
    offset: OffsetQuery = MIN_OFFSET,
    include_seasonality: bool = Query(
        default=False,
        alias="includeSeasonality",
        description="Quando true, inclui métricas resumidas de sazonalidade por SKU.",
    ),
) -> CatalogListResponse:
    return analytics_service.list_catalog_products(
        PageRequest(limit=limit, offset=offset),
        query=q,
        supplier=supplier,
        stock_filter=stock_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        include_seasonality=include_seasonality,
    )


@analytics_router.get("/products/search", response_model=ProductSearchResponse,
                      summary="Busca de produto por código ou descrição",
                      description="Busca no catálogo em cache, sem carregar as cestas (contrato §3.6).",
                      responses={400: _CROSS_SELL_ERRORS[400], 503: _CROSS_SELL_ERRORS[503]})
def search_products(q: SearchQuery, limit: SearchLimitQuery = DEFAULT_SEARCH_LIMIT,
                    offset: OffsetQuery = MIN_OFFSET) -> ProductSearchResponse:
    return analytics_service.search_products(q, PageRequest(limit=limit, offset=offset))


# ---------------------------------------------------------------------------
# F3: Churn de Clientes (P-117 a P-127; ADR-006 DA-05)
# ---------------------------------------------------------------------------
from src.modules.analytics.api.schemas import (
    ChurnCustomersResponse,
    CustomerChurnDetailResponse,
    InactiveChurnResponse,
)

_CHURN_ERRORS = {
    400: {**_ERROR, "description": "CHU-003: parâmetros de churn inválidos."},
    404: {**_ERROR, "description": "CHU-001: cliente não encontrado ou sem compras de venda."},
    422: {**_ERROR, "description": "CHU-002: base insuficiente para apuração de churn."},
    503: {**_ERROR, "description": "ANL-001: base de vendas indisponível."},
}


@analytics_router.get("/churn/customers", response_model=ChurnCustomersResponse,
                      summary="Listagem priorizada de clientes por score de churn",
                      description="Clientes em risco ou alerta ordenados por scorePrioridade decrescente (P-123).",
                      responses=_CHURN_ERRORS)
def get_churn_customers(status: Optional[str] = Query(default="EM_RISCO", description="Filtro de status (EM_RISCO, ALERTA, SAUDAVEL, TODOS)."),
                        limit: LimitQuery = DEFAULT_PAGE_LIMIT,
                        offset: OffsetQuery = MIN_OFFSET) -> ChurnCustomersResponse:
    if status is not None and status not in ("EM_RISCO", "ALERTA", "SAUDAVEL", "TODOS"):
        from src.modules.analytics.domain.exceptions import ChurnInvalidParametersError
        raise ChurnInvalidParametersError(fields=["status"])
    return analytics_service.get_churn_customers(status, PageRequest(limit=limit, offset=offset))


@analytics_router.get("/churn/customers/{customerCode}", response_model=CustomerChurnDetailResponse,
                      summary="Detalhamento explicativo do cliente em churn",
                      description="Decomposição do score, tendência trimestral e produtos perdidos (P-126).",
                      responses=_CHURN_ERRORS)
def get_customer_churn_detail(customer_code: CustomerCodePath) -> CustomerChurnDetailResponse:
    return analytics_service.get_customer_churn_detail(customer_code)


@analytics_router.get("/churn/inactive", response_model=InactiveChurnResponse,
                      summary="Fila especializada de clientes inativos antigos (> 180 dias)",
                      description="Inativos antigos ordenados por faturamento histórico para reativação (P-125).",
                      responses=_CHURN_ERRORS)
def get_inactive_churn(limit: LimitQuery = DEFAULT_PAGE_LIMIT,
                       offset: OffsetQuery = MIN_OFFSET) -> InactiveChurnResponse:
    return analytics_service.get_inactive_churn(PageRequest(limit=limit, offset=offset))


# ------------------------------------------------------------------ sazonalidade por produto (P-106..P-116; ADR-005)
# NOTA: /seasonality/ranking DEVE vir antes de /seasonality/{sku} para evitar conflito de path matching

@analytics_router.get("/seasonality/ranking", response_model=SeasonalityRankingResponse,
                      summary="Rankings de sazonalidade", responses=_SEASONALITY_ERRORS,
                      description="Lista produtos mais sazonais ou menos mensuráveis paginados (P-114).")
def get_seasonality_ranking(order: RankingOrderQuery = "most", limit: LimitQuery = DEFAULT_PAGE_LIMIT,
                            offset: OffsetQuery = MIN_OFFSET) -> SeasonalityRankingResponse:
    return analytics_service.get_seasonality_ranking(order, PageRequest(limit=limit, offset=offset))


@analytics_router.get("/seasonality/{sku}", response_model=SeasonalityResponse,
                      summary="Detecção de sazonalidade por produto", responses=_SEASONALITY_ERRORS,
                      description="Retorna a curva mensal de sazonalidade, pico, vale, força e confiança (P-106 a P-113).")
def get_product_seasonality(sku: SkuPath) -> SeasonalityResponse:
    return analytics_service.get_product_seasonality(sku)


# ------------------------------------------------------------------ Elasticidade (F5 / P-095..P-105)

_ELASTICITY_ERRORS = {
    400: {**_ERROR, "description": "ELA-004: parâmetros inválidos."},
    404: {**_ERROR, "description": "ELA-001 (produto) ou ELA-002 (cliente)."},
    422: {**_ERROR, "description": "ELA-003: histórico de vendas insuficiente."},
    503: {**_ERROR, "description": "ANL-001: base de dados indisponível."},
}


@analytics_router.get(
    "/elasticity/product/{sku}",
    response_model=ProductElasticityResponse,
    summary="Elasticidade-preço do produto e clientes",
    responses=_ELASTICITY_ERRORS,
    description="Estimação econométrica log-log de elasticidade do produto e lista paginada de clientes (P-096, P-099, P-103).",
)
def get_product_elasticity(
    sku: SkuPath,
    limit: LimitQuery = DEFAULT_PAGE_LIMIT,
    offset: OffsetQuery = MIN_OFFSET,
) -> ProductElasticityResponse:
    return analytics_service.get_product_elasticity(sku, PageRequest(limit=limit, offset=offset))


@analytics_router.get(
    "/elasticity/product/{sku}/customer/{customerCode}",
    response_model=CustomerElasticityResponse,
    summary="Elasticidade individualizada do cliente no produto",
    responses=_ELASTICITY_ERRORS,
    description="Elasticidade calculada via suavização hierárquica (shrinkage bayesiano) para o par produto x cliente (P-097).",
)
def get_customer_elasticity(
    sku: SkuPath,
    customer_code: CustomerCodePath,
) -> CustomerElasticityResponse:
    return analytics_service.get_customer_elasticity(sku, customer_code)


@analytics_router.post(
    "/elasticity/simulate",
    response_model=ElasticitySimulationResponse,
    summary="Simulação de variação de preço",
    responses=_ELASTICITY_ERRORS,
    description="Simula o impacto em volume, receita e margem monetária para uma alteração de preço (P-101).",
)
def simulate_price_impact(
    request: ElasticitySimulationRequest,
) -> ElasticitySimulationResponse:
    return analytics_service.simulate_price_change(request)
