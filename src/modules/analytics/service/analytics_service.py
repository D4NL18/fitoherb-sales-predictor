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


# ------------------------------------------------------------------ sazonalidade por produto (P-106..P-116; ADR-005)

from datetime import datetime, timezone
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
    get_seasonality_index,
)


def _get_monthly_sales_df() -> pd.DataFrame:
    """Obtém DataFrame de vendas mensais líquidas via cache."""
    return analytics_cache.get_monthly_sales()


def _get_catalog_dict() -> dict[int, dict[str, Any]]:
    """Obtém mapa do catálogo ativo em cache."""
    cat = analytics_cache.get_catalog()
    return {
        entry.sku: {
            "Codigo": entry.sku,
            "Descricao": entry.description,
            "Fornecedor": entry.supplier,
            "Estoque": entry.stock,
            "Pc.Ultimo Custo": entry.last_cost,
            "Pc.Venda": entry.sale_price,
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
