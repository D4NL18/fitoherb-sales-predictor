"""
Mappers do módulo Analytics: objetos de domínio -> schemas de resposta (ADR-002 DA-09).

Sem regra de negócio: só tradução de campos, arredondamento de exibição (contrato §2.4, meio para
cima) e montagem de `meta`. As frases de P-065 vêm do domínio (`cross_sell_explanation`), chamadas
apenas para os itens da página. Nenhum campo de cliente é copiado (LGPD-03).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence

from src.modules.analytics.api.schemas import (
    AnalyticsHealthCounts,
    AnalyticsHealthData,
    AnalyticsHealthResponse,
    AnalyticsMeta,
    ConsultedProduct,
    CrossSellPagedMeta,
    CustomerCrossSellData,
    CustomerCrossSellResponse,
    CustomerPagedMeta,
    CustomerRecommendationItem,
    ErrorMeta,
    Explanation,
    PagedMeta,
    ProductCrossSellData,
    ProductCrossSellResponse,
    ProductRecommendationItem,
    ProductRef,
    ProductSearchResponse,
)
from src.modules.analytics.domain.cross_sell import CatalogEntry, ProductRecommendation
from src.modules.analytics.domain.cross_sell_customer import CustomerRecommendation, CustomerRecommendationResult
from src.modules.analytics.domain.cross_sell_explanation import (
    Explanation as DomainExplanation,
    build_customer_explanation,
    build_product_explanation,
)
from src.modules.analytics.domain.number_format import round_for_display
from src.modules.analytics.domain.pagination import PageRequest, PageResult
from src.modules.analytics.service.analytics_cache import AnalyticsSnapshot, CacheStatus

RATIO_DECIMALS = 4   # suporte, confiança (contrato §2.4)
LIFT_DECIMALS = 2    # lift
MONEY_DECIMALS = 2   # margemUnitaria, pontuacao
STOCK_DECIMALS = 1   # estoqueAtual


@dataclass(frozen=True)
class PageContext:
    """Dados da requisição e da base usados para montar `meta` e os itens de uma página."""

    page_request: PageRequest
    reference_date: str
    catalog: Mapping[int, CatalogEntry] = field(default_factory=dict)


def utc_timestamp(moment: Optional[datetime] = None) -> str:
    """ISO-8601 UTC com milissegundos e sufixo `Z` (ex.: 2026-11-05T15:10:00.000Z)."""
    current = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return current.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def to_error_meta() -> ErrorMeta:
    """`meta` dos corpos de erro (contrato §4)."""
    return ErrorMeta(timestamp=utc_timestamp())


def _paged_fields(page: PageResult, context: PageContext) -> dict:
    """Campos comuns de `PagedMeta` (P-066)."""
    return {
        "timestamp": utc_timestamp(), "data_referencia": context.reference_date, "page": page.page,
        "limit": context.page_request.limit, "offset": context.page_request.offset, "total_items": page.total_items,
        "total_pages": page.total_pages,
    }


def _to_explanation(explanation: DomainExplanation) -> Explanation:
    """Frases do domínio -> schema."""
    return Explanation(frequencia=explanation.frequencia, intensidade=explanation.intensidade,
                       evidencia=explanation.evidencia, motivo=explanation.motivo)


def to_consulted_product(entry: CatalogEntry) -> ConsultedProduct:
    """Produto do catálogo com código, descrição e fornecedor."""
    return ConsultedProduct(codigo=entry.code, descricao=entry.description, fornecedor=entry.supplier)


# ------------------------------------------------------------------ health

def _to_counts(snapshot: AnalyticsSnapshot) -> AnalyticsHealthCounts:
    """Contagens agregadas do snapshot."""
    counts = snapshot.counts
    return AnalyticsHealthCounts(cestas_validas=counts["valid_baskets"], regras_uteis=counts["useful_rules"],
                                 itens_triviais=counts["trivial_items"], skus_com_cesta=counts["skus_with_basket"])


def to_health_response(status: CacheStatus, snapshot: Optional[AnalyticsSnapshot]) -> AnalyticsHealthResponse:
    """Health a partir do estado do cache e do snapshot publicado (pode ser `None`). Regra: P-069."""
    meta = AnalyticsMeta(timestamp=utc_timestamp(),
                         data_referencia=snapshot.reference_date.isoformat() if snapshot else None)
    if snapshot is None:
        return AnalyticsHealthResponse(data=AnalyticsHealthData(estado_cache=status.state, cache_carregado=False,
                                                                duracao_ultima_carga_ms=status.load_duration_ms),
                                       meta=meta)
    data = AnalyticsHealthData(
        estado_cache=status.state, cache_carregado=True, base_suficiente=snapshot.is_base_sufficient,
        carregado_em=utc_timestamp(snapshot.loaded_at), expira_em=utc_timestamp(snapshot.expires_at),
        duracao_ultima_carga_ms=status.load_duration_ms, contagens=_to_counts(snapshot),
    )
    return AnalyticsHealthResponse(data=data, meta=meta)


# ------------------------------------------------------------------ modo produto (P-061)

def _to_product_item(recommendation: ProductRecommendation, antecedent: CatalogEntry) -> ProductRecommendationItem:
    """Consequente com métricas arredondadas e frases de P-065."""
    rule, entry = recommendation.rule, recommendation.entry
    return ProductRecommendationItem(
        codigo=entry.code, descricao=entry.description, fornecedor=entry.supplier,
        suporte=round_for_display(rule.support, RATIO_DECIMALS),
        confianca=round_for_display(rule.confidence, RATIO_DECIMALS),
        lift=round_for_display(rule.lift, LIFT_DECIMALS), pedidos_em_comum=rule.pair_orders,
        estoque_atual=round_for_display(entry.stock, STOCK_DECIMALS), sem_estoque=recommendation.is_out_of_stock,
        margem_nao_positiva=recommendation.has_non_positive_margin,
        explicacao=_to_explanation(build_product_explanation(rule, antecedent.description, entry.description)),
    )


def to_product_response(antecedent: CatalogEntry, page: PageResult, context: PageContext) -> ProductCrossSellResponse:
    """
    Resposta do modo produto.

    Args:
        antecedent: produto consultado (sempre presente, Q-2).
        page: página de `ProductRecommendation`.
        context: paginação pedida e data de referência.
    """
    items = [_to_product_item(recommendation, antecedent) for recommendation in page.items]
    return ProductCrossSellResponse(
        data=ProductCrossSellData(produto=to_consulted_product(antecedent), recomendacoes=items),
        meta=CrossSellPagedMeta(**_paged_fields(page, context)),
    )


# ------------------------------------------------------------------ modo cliente (P-064)

def _to_customer_item(item: CustomerRecommendation, catalog) -> CustomerRecommendationItem:
    """Candidato com regra principal, métricas arredondadas e frases com motivo."""
    rule, entry = item.rule, item.entry
    antecedent = catalog[rule.antecedent]
    explanation = build_customer_explanation(rule, (antecedent.description, entry.description),
                                             item.days_since_last_purchase)
    return CustomerRecommendationItem(
        codigo=entry.code, descricao=entry.description, fornecedor=entry.supplier,
        antecedente_principal=ProductRef(codigo=antecedent.code, descricao=antecedent.description),
        qtd_antecedentes_relacionados=item.related_antecedent_count,
        lift=round_for_display(rule.lift, LIFT_DECIMALS), confianca=round_for_display(rule.confidence, RATIO_DECIMALS),
        pedidos_em_comum=rule.pair_orders, margem_unitaria=round_for_display(item.unit_margin, MONEY_DECIMALS),
        custo_estimado=entry.is_cost_estimated, pontuacao=round_for_display(item.score, MONEY_DECIMALS),
        motivo=item.reason, dias_desde_ultima_compra=item.days_since_last_purchase,
        explicacao=_to_explanation(explanation),
    )


def to_customer_response(result: CustomerRecommendationResult, page: PageResult,
                         context: PageContext) -> CustomerCrossSellResponse:
    """
    Resposta do modo cliente (sem eco do `customerCode`, LGPD-03).

    Args:
        result: resultado completo do domínio (fonte do `motivoVazio`).
        page: página de `CustomerRecommendation`.
        context: paginação pedida, data de referência e catálogo do snapshot (descrição do antecedente).
    """
    items = [_to_customer_item(item, context.catalog) for item in page.items]
    meta = CustomerPagedMeta(**_paged_fields(page, context), motivo_vazio=result.empty_reason)
    return CustomerCrossSellResponse(data=CustomerCrossSellData(recomendacoes=items), meta=meta)


# ------------------------------------------------------------------ busca de produtos (contrato §3.6)

def to_search_response(page: PageResult, context: PageContext) -> ProductSearchResponse:
    """Página da busca com `PagedMeta` (sem `parametros`)."""
    items: Sequence[CatalogEntry] = page.items
    return ProductSearchResponse(data=[to_consulted_product(entry) for entry in items],
                                 meta=PagedMeta(**_paged_fields(page, context)))
