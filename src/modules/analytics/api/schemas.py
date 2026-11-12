"""
Schemas Pydantic da API do módulo Analytics Comercial (contrato `analytics-cross-sell` 1.1.0, ADR-002 DA-09).

Atributos em `snake_case`, JSON em `camelCase` (`alias_generator=to_camel`). Envelope `data`/`meta` em
toda resposta 2xx (P-066) e corpo único de erro (P-067, contrato §4). Os campos listados aqui são a
allowlist de LGPD-03: nenhum dado de cliente além do que o contrato permite (nem o `customerCode`).
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.modules.analytics.domain import cross_sell
from src.modules.analytics.service.analytics_cache import CACHE_TTL_HOURS

ANALYTICS_CONTRACT_VERSION = "1.1.0"

CacheStateLiteral = Literal["FRIO", "CARREGANDO", "QUENTE", "EXPIRADO"]
CandidateReasonLiteral = Literal["NUNCA_COMPROU", "DORMENTE"]
EmptyReasonLiteral = Literal["SEM_COMPRAS_RECENTES"]

_PARAMETERS_EXAMPLE = {
    "minLift": 1.2, "minConfidence": 0.10, "minPairOrders": 10, "trivialItemSupport": 0.15,
    "dormantDays": 90, "customerProfileDays": 365, "cacheTtlHours": 6,
}
_PAGED_META_EXAMPLE = {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 50, "offset": 0, "totalItems": 2, "totalPages": 1, "parametros": _PARAMETERS_EXAMPLE,
}


class CamelModel(BaseModel):
    """Base dos schemas: JSON em camelCase, construção aceita o nome Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ------------------------------------------------------------------ meta e envelope (P-066)

class ErrorMeta(CamelModel):
    """`meta` dos erros: só momento e versão (contrato §4)."""

    timestamp: str = Field(description="Momento da resposta (ISO-8601 UTC).")
    version: str = Field(default=ANALYTICS_CONTRACT_VERSION, description="Versão do contrato da API.")


class AnalyticsMeta(ErrorMeta):
    """`meta` base de toda resposta 2xx (contrato §2.1)."""

    data_referencia: Optional[str] = Field(
        default=None, description="Último dia incluído na base em cache (AAAA-MM-DD); nulo só com cache vazio.")


class PagedMeta(AnalyticsMeta):
    """`meta` de lista (P-066, contrato §2.2)."""

    page: int = Field(description="Página atual: floor(offset / limit) + 1.")
    limit: int = Field(description="Tamanho efetivo da página.")
    offset: int = Field(description="Deslocamento efetivo.")
    total_items: int = Field(description="Itens após os filtros de viabilidade, antes da paginação (P-063.5).")
    total_pages: int = Field(description="ceil(totalItems / limit); 0 sem itens.")


class CrossSellParameters(CamelModel):
    """Constantes efetivas do domínio, para a tela não fixar números na copy (Q-5)."""

    min_lift: float = Field(default=cross_sell.MIN_LIFT, description="Lift mínimo de uma Regra Útil.")
    min_confidence: float = Field(default=cross_sell.MIN_CONFIDENCE, description="Confiança mínima de uma Regra Útil.")
    min_pair_orders: int = Field(default=cross_sell.MIN_PAIR_ORDERS, description="Pedidos em comum mínimos.")
    trivial_item_support: float = Field(
        default=cross_sell.TRIVIAL_ITEM_SUPPORT, description="Fração de cestas acima da qual o item é trivial.")
    dormant_days: int = Field(default=cross_sell.DORMANT_DAYS, description="Dias sem compra para Produto Dormente.")
    customer_profile_days: int = Field(
        default=cross_sell.CUSTOMER_PROFILE_DAYS, description="Janela do perfil de compra, em dias.")
    cache_ttl_hours: int = Field(default=CACHE_TTL_HOURS, description="Validade do cache da base, em horas.")


class CrossSellPagedMeta(PagedMeta):
    """`meta` das rotas de cross-sell: paginação mais `parametros`."""

    parametros: CrossSellParameters = Field(default_factory=CrossSellParameters,
                                            description="Parâmetros efetivos do domínio.")


class CustomerPagedMeta(CrossSellPagedMeta):
    """`meta` da rota por cliente: sempre traz `motivoVazio` (P-062.7)."""

    motivo_vazio: Optional[EmptyReasonLiteral] = Field(
        description="SEM_COMPRAS_RECENTES quando o perfil está vazio; nulo nos demais casos.")


class ErrorDetail(CamelModel):
    """Erro com código interno; mensagem fixa, sem valor recebido (LGPD-05)."""

    code: str = Field(description="Código interno (XSL-001..004, ANL-001, ANL-002).")
    message: str = Field(description="Mensagem fixa em português.")
    fields: List[str] = Field(default_factory=list, description="Nomes dos parâmetros inválidos (só no 400).")


class AnalyticsErrorResponse(CamelModel):
    """Corpo único de erro do módulo (contrato §4)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "error": {"code": "XSL-004", "message": "Parâmetros inválidos: limit, offset.", "fields": ["limit", "offset"]},
        "meta": {"timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0"},
    }})

    error: ErrorDetail = Field(description="Detalhe do erro.")
    meta: ErrorMeta = Field(description="Momento e versão.")


# ------------------------------------------------------------------ health (P-069)

class AnalyticsHealthCounts(CamelModel):
    """Contagens agregadas da base em cache, sem dado de cliente."""

    cestas_validas: int = Field(description="Cestas Válidas na base.")
    regras_uteis: int = Field(description="Regras Úteis mineradas.")
    itens_triviais: int = Field(description="SKUs classificados como Item Trivial.")
    skus_com_cesta: int = Field(description="SKUs presentes em ao menos uma Cesta Válida.")


class AnalyticsHealthData(CamelModel):
    """Estado do cache sem acessar o banco (contrato §3.1)."""

    status: Literal["UP"] = Field(default="UP", description="Processo respondendo.")
    estado_cache: CacheStateLiteral = Field(description="FRIO, CARREGANDO, QUENTE ou EXPIRADO.")
    cache_carregado: bool = Field(description="Existe snapshot publicado.")
    base_suficiente: Optional[bool] = Field(default=None, description="Falso se a base gera XSL-003; nulo sem cache.")
    carregado_em: Optional[str] = Field(default=None, description="Momento da última carga concluída (ISO-8601).")
    expira_em: Optional[str] = Field(default=None, description="carregadoEm + cacheTtlHours (ISO-8601).")
    duracao_ultima_carga_ms: Optional[int] = Field(default=None, description="Duração da última carga, em ms.")
    contagens: Optional[AnalyticsHealthCounts] = Field(default=None, description="Contagens agregadas da base.")
    parametros: CrossSellParameters = Field(default_factory=CrossSellParameters,
                                            description="Parâmetros efetivos do domínio.")


class AnalyticsHealthResponse(CamelModel):
    """Resposta de `GET /health` e `POST /cache/reload`."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "data": {"status": "UP", "estadoCache": "QUENTE", "cacheCarregado": True, "baseSuficiente": True,
                 "carregadoEm": "2026-11-05T14:02:11.418Z", "expiraEm": "2026-11-05T20:02:11.418Z",
                 "duracaoUltimaCargaMs": 4120,
                 "contagens": {"cestasValidas": 61234, "regrasUteis": 4180, "itensTriviais": 3, "skusComCesta": 1712},
                 "parametros": _PARAMETERS_EXAMPLE},
        "meta": {"timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05"},
    }})

    data: AnalyticsHealthData = Field(description="Estado do cache.")
    meta: AnalyticsMeta = Field(description="Metadados da resposta.")


# ------------------------------------------------------------------ cross-sell (P-061, P-064, P-065)

class ProductRef(CamelModel):
    """Referência a produto (código e descrição)."""

    codigo: int = Field(description="Código do SKU.")
    descricao: str = Field(description="Descrição do produto.")


class ConsultedProduct(ProductRef):
    """Produto do catálogo com fornecedor (produto consultado e item da busca)."""

    fornecedor: str = Field(description="Fornecedor do produto.")


class Explanation(CamelModel):
    """Frases prontas de P-065, separadas (contrato §3.5)."""

    frequencia: str = Field(description="Em X% dos pedidos com A também há B.")
    intensidade: str = Field(description="B aparece L vezes mais nesses pedidos do que no geral.")
    evidencia: str = Field(description="Baseado em N pedidos.")
    motivo: Optional[str] = Field(default=None, description="Motivo da sugestão ao cliente; nulo no modo produto.")


class ProductRecommendationItem(CamelModel):
    """Consequente da Recomendação por Produto (P-061.2, P-061.4)."""

    codigo: int = Field(description="SKU consequente.")
    descricao: str = Field(description="Descrição do consequente.")
    fornecedor: str = Field(description="Fornecedor do consequente.")
    suporte: float = Field(description="Pedidos com A e B / Cestas Válidas (4 casas).")
    confianca: float = Field(description="Pedidos com A e B / pedidos com A (4 casas).")
    lift: float = Field(description="Confiança / frequência de B (2 casas).")
    pedidos_em_comum: int = Field(description="Cestas Válidas com A e B.")
    estoque_atual: float = Field(description="Estoque atual (1 casa).")
    sem_estoque: bool = Field(description="Estoque <= 0.")
    margem_nao_positiva: bool = Field(description="Margem Unitária <= 0.")
    explicacao: Explanation = Field(description="Frases de P-065.")


class ProductCrossSellData(CamelModel):
    """`data` do modo produto: produto consultado sempre presente (Q-2)."""

    produto: ConsultedProduct = Field(description="Produto antecedente consultado.")
    recomendacoes: List[ProductRecommendationItem] = Field(description="Página de consequentes (P-061.1).")


class ProductCrossSellResponse(CamelModel):
    """Resposta de `GET /cross-sell/product/{sku}`."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "data": {
            "produto": {"codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE"},
            "recomendacoes": [{
                "codigo": 2002, "descricao": "CAPSULA DE HIBISCO", "fornecedor": "HERBARIUM", "suporte": 0.0170,
                "confianca": 0.3400, "lift": 4.25, "pedidosEmComum": 170, "estoqueAtual": 84.0, "semEstoque": False,
                "margemNaoPositiva": False,
                "explicacao": {
                    "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
                    "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
                    "evidencia": "Baseado em 170 pedidos.", "motivo": None},
            }],
        },
        "meta": _PAGED_META_EXAMPLE,
    }})

    data: ProductCrossSellData = Field(description="Produto consultado e recomendações.")
    meta: CrossSellPagedMeta = Field(description="Paginação e parâmetros.")


class CustomerRecommendationItem(CamelModel):
    """Candidato da Recomendação por Cliente (P-064.4)."""

    codigo: int = Field(description="SKU candidato.")
    descricao: str = Field(description="Descrição do candidato.")
    fornecedor: str = Field(description="Fornecedor do candidato.")
    antecedente_principal: ProductRef = Field(description="SKU do perfil da regra de maior pontuação.")
    qtd_antecedentes_relacionados: int = Field(description="Quantos SKUs do perfil sugerem o candidato.")
    lift: float = Field(description="Lift da regra principal (2 casas).")
    confianca: float = Field(description="Confiança da regra principal (4 casas).")
    pedidos_em_comum: int = Field(description="Pedidos em comum da regra principal (métrica global da regra).")
    margem_unitaria: float = Field(description="Pc.Venda - custo (2 casas).")
    custo_estimado: bool = Field(description="Custo pelo fallback de 60% do preço.")
    pontuacao: float = Field(description="lift x confiança x margemUnitaria (2 casas).")
    motivo: CandidateReasonLiteral = Field(description="NUNCA_COMPROU ou DORMENTE.")
    dias_desde_ultima_compra: Optional[int] = Field(default=None, description="Só quando DORMENTE.")
    explicacao: Explanation = Field(description="Frases de P-065 com motivo.")


class CustomerCrossSellData(CamelModel):
    """`data` do modo cliente (sem eco do `customerCode`)."""

    recomendacoes: List[CustomerRecommendationItem] = Field(description="Página de candidatos (P-064.2).")


class CustomerCrossSellResponse(CamelModel):
    """Resposta de `GET /cross-sell/customer/{customerCode}`."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "data": {"recomendacoes": [{
            "codigo": 7007, "descricao": "GENGIBRE EM PO 100G", "fornecedor": "CATARINENSE",
            "antecedentePrincipal": {"codigo": 1001, "descricao": "CHA VERDE 100G"},
            "qtdAntecedentesRelacionados": 2, "lift": 1.50, "confianca": 0.2000, "pedidosEmComum": 100,
            "margemUnitaria": 30.00, "custoEstimado": False, "pontuacao": 9.00, "motivo": "NUNCA_COMPROU",
            "diasDesdeUltimaCompra": None,
            "explicacao": {
                "frequencia": "Em 20% dos pedidos com CHA VERDE 100G também há GENGIBRE EM PO 100G.",
                "intensidade": "GENGIBRE EM PO 100G aparece 1,5 vezes mais nesses pedidos do que no geral.",
                "evidencia": "Baseado em 100 pedidos.",
                "motivo": ("Sugerido porque o cliente compra CHA VERDE 100G. "
                           "O cliente nunca comprou GENGIBRE EM PO 100G.")},
        }]},
        "meta": {**_PAGED_META_EXAMPLE, "motivoVazio": None},
    }})

    data: CustomerCrossSellData = Field(description="Candidatos priorizados.")
    meta: CustomerPagedMeta = Field(description="Paginação, parâmetros e motivo do vazio.")


# ------------------------------------------------------------------ busca de produtos (contrato §3.6)

class ProductSearchResponse(CamelModel):
    """Resposta de `GET /products/search` (catálogo; sem dado pessoal)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "data": [{"codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE"}],
        "meta": {"timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
                 "page": 1, "limit": 20, "offset": 0, "totalItems": 1, "totalPages": 1},
    }})

    data: List[ConsultedProduct] = Field(description="Página de produtos encontrados.")
    meta: PagedMeta = Field(description="Paginação.")


ProductSearchItem = ConsultedProduct  # nome do contrato §3.6 / checklist B-20
