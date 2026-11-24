"""
Schemas Pydantic da API do módulo Analytics Comercial (contrato `analytics-cross-sell` 1.1.0, ADR-002 DA-09).

Atributos em `snake_case`, JSON em `camelCase` (`alias_generator=to_camel`). Envelope `data`/`meta` em
toda resposta 2xx (P-066) e corpo único de erro (P-067, contrato §4). Os campos listados aqui são a
allowlist de LGPD-03: nenhum dado de cliente além do que o contrato permite (nem o `customerCode`).
"""
from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from src.modules.analytics.domain import cross_sell, elasticity
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


# ---------------------------------------------------------------------------
# F3: Churn de Clientes (P-117 a P-127; ADR-006 DA-05)
# ---------------------------------------------------------------------------

ChurnStatusFilterLiteral = Literal["EM_RISCO", "ALERTA", "SAUDAVEL", "TODOS"]


class ChurnSummaryKpi(CamelModel):
    """Métricas consolidadas de impacto de churn da carteira."""
    total_em_risco: int = Field(description="Total de clientes em risco.")
    total_alerta: int = Field(description="Total de clientes em alerta.")
    total_saudavel: int = Field(description="Total de clientes saudáveis.")
    total_inativos: int = Field(description="Total de clientes inativos antigos (> 180 dias).")
    receita_mensal_em_risco: float = Field(description="Soma do faturamento médio mensal dos clientes em risco (R$).")


class ChurnCustomerItem(CamelModel):
    """Item resumido do cliente na tabela priorizada de churn."""
    customer_code: int = Field(description="Código do cliente no ERP.")
    customer_name: str = Field(default="", description="Nome do cliente no ERP.")
    seller_name: str = Field(default="", description="Nome do vendedor do último pedido.")
    city: str = Field(default="", description="Cidade/UF do cliente.")
    status: str = Field(description="Status operacional: EM_RISCO, ALERTA, SAUDAVEL.")
    dias_sem_comprar: int = Field(description="Dias corridos desde o último pedido de VENDA.")
    gap_tipico: Optional[float] = Field(default=None, description="Mediana dos intervalos entre compras (dias).")
    dias_referencia: int = Field(description="Régua de referência de compra do cliente (dias).")
    fator_tempo: float = Field(description="Urgência temporal adimensional (saturada em 2.0).")
    faturamento_medio_mensal: float = Field(description="Faturamento médio mensal líquido de devoluções (R$).")
    score_prioridade: float = Field(description="Score ponderado em R$: faturamentoMedioMensal x fatorTempo.")
    historico_curto: bool = Field(description="True se o cliente possui menos de 3 pedidos no histórico.")
    data_ultimo_pedido: Optional[str] = Field(default=None, description="Data do último pedido (AAAA-MM-DD).")


class ChurnCustomersData(CamelModel):
    """Corpo 'data' da listagem priorizada de churn."""
    resumo: ChurnSummaryKpi = Field(description="KPIs de impacto financeiro e contagens.")
    items: List[ChurnCustomerItem] = Field(description="Clientes ordenados por score de retenção decrescente.")


class ChurnCustomersResponse(CamelModel):
    """Resposta de GET /analytics/churn/customers."""
    data: ChurnCustomersData = Field(description="Dados de clientes e resumo.")
    meta: PagedMeta = Field(description="Metadados de paginação.")


class MonthlyHistoryItem(CamelModel):
    """Ponto de histórico mensal de compras do cliente."""
    ano_mes: str = Field(description="Ano e mês no formato AAAA-MM.")
    faturamento_liquido: float = Field(description="Faturamento líquido do mês em R$.")
    qtd_pedidos: int = Field(description="Quantidade de pedidos no mês.")


class LostProductItem(CamelModel):
    """Produto relevante adquirido no passado e ausente nos últimos 60 dias."""
    sku: int = Field(description="Código do produto.")
    descricao: str = Field(description="Descrição comercial.")
    fornecedor: str = Field(description="Laboratório / Fabricante.")
    faturamento_historico: float = Field(description="Total comprado nos últimos 12 meses (R$).")
    data_ultima_compra: str = Field(description="Data da última compra do produto (AAAA-MM-DD).")


class CustomerChurnDetailData(CamelModel):
    """Corpo 'data' do detalhamento do cliente."""
    customer_code: int = Field(description="Código do cliente.")
    customer_name: str = Field(default="", description="Nome do cliente no ERP.")
    seller_name: str = Field(default="", description="Nome do vendedor do último pedido.")
    city: str = Field(default="", description="Cidade/UF do cliente.")
    status: str = Field(description="Status: EM_RISCO, ALERTA, SAUDAVEL, INATIVO_RECUPERACAO.")
    dias_sem_comprar: int = Field(description="Dias desde a última compra.")
    data_ultimo_pedido: Optional[str] = Field(default=None, description="Data do último pedido (AAAA-MM-DD).")
    gap_tipico: Optional[float] = Field(default=None, description="Intervalo habitual entre compras.")
    dias_referencia: int = Field(description="Régua de expectativa de compra.")
    fator_tempo: float = Field(description="Fator de urgência temporal.")
    faturamento_medio_mensal: float = Field(description="Média mensal líquida de devoluções (R$).")
    score_prioridade: float = Field(description="Score de Prioridade de Retenção (R$).")
    historico_curto: bool = Field(description="Flag de histórico curto (< 3 pedidos).")
    variacao_receita_trimestral_pct: Optional[float] = Field(default=None, description="Variação % últimos 3m vs 3m anteriores.")
    historico_mensal: List[MonthlyHistoryItem] = Field(default_factory=list, description="Série mensal histórica.")
    produtos_perdidos: List[LostProductItem] = Field(default_factory=list, description="Top SKUs perdidos.")


class CustomerChurnDetailResponse(CamelModel):
    """Resposta de GET /analytics/churn/customers/{customerCode}."""
    data: CustomerChurnDetailData = Field(description="Detalhamento e diagnóstico do cliente.")
    meta: AnalyticsMeta = Field(description="Metadados de resposta.")


class InactiveCustomerItem(CamelModel):
    """Item resumido de cliente inativo de longa data (> 180 dias)."""
    customer_code: int = Field(description="Código do cliente.")
    customer_name: str = Field(default="", description="Nome do cliente no ERP.")
    seller_name: str = Field(default="", description="Nome do vendedor do último pedido.")
    city: str = Field(default="", description="Cidade/UF do cliente.")
    status: str = Field(default="INATIVO_RECUPERACAO", description="Status fixo.")
    dias_sem_comprar: int = Field(description="Dias sem comprar (> 180).")
    data_ultimo_pedido: Optional[str] = Field(default=None, description="Data da última compra.")
    faturamento_medio_mensal: float = Field(description="Faturamento histórico médio mensal (R$).")
    historico_curto: bool = Field(description="Flag de histórico curto.")


class InactiveChurnData(CamelModel):
    """Corpo 'data' da fila de clientes inativos antigos."""
    total_inativos: int = Field(description="Total de clientes na fila de inativos.")
    items: List[InactiveCustomerItem] = Field(description="Clientes inativos ordenados por faturamento decrescente.")


class InactiveChurnResponse(CamelModel):
    """Resposta de GET /analytics/churn/inactive."""
    data: InactiveChurnData = Field(description="Fila de inativos antigos.")
    meta: PagedMeta = Field(description="Metadados de paginação.")


class ChurnFilterOptionsData(CamelModel):
    """Opções disponíveis de filtros para a tabela de churn."""
    sellers: List[str] = Field(default_factory=list, description="Vendedores disponíveis.")
    cities: List[str] = Field(default_factory=list, description="Cidades/UF disponíveis.")


class ChurnFilterOptionsResponse(CamelModel):
    """Resposta de GET /analytics/churn/filters."""
    data: ChurnFilterOptionsData = Field(description="Listas de vendedores e cidades.")
    meta: AnalyticsMeta = Field(description="Metadados da resposta.")


class CatalogProductItem(CamelModel):
    """Item da listagem paginada do catálogo ativo (contrato §3.7, P-117; sem dado pessoal)."""

    codigo: int = Field(description="Código do SKU.")
    descricao: str = Field(description="Descrição do produto.")
    fornecedor: str = Field(description="Fornecedor do produto.")
    estoque: float = Field(description="Estoque atual (1 casa).")
    preco_venda: float = Field(description="Preço de venda praticado (2 casas).")
    forca: Optional[str] = Field(default=None, description="Grau de sazonalidade (quando includeSeasonality=true).")
    amplitude: Optional[float] = Field(default=None, description="Amplitude do índice sazonal (quando includeSeasonality=true).")
    mes_pico: Optional[str] = Field(default=None, description="Mês ou período de pico (quando includeSeasonality=true e elegível).")
    mes_vale: Optional[str] = Field(default=None, description="Mês ou período de vale (quando includeSeasonality=true e elegível).")
    faturamento_total: Optional[float] = Field(default=None, description="Faturamento líquido total no período (quando includeSeasonality=true).")
    motivo_insuficiencia: Optional[str] = Field(default=None, description="Motivo de insuficiência quando forca=INSUFICIENTE.")


class CatalogListResponse(CamelModel):
    """Resposta de `GET /products` (catálogo completo em cache; sem dado pessoal)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "data": [{
            "codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE",
            "estoque": 10.0, "precoVenda": 24.9,
        }],
        "meta": {"timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
                 "page": 1, "limit": 2000, "offset": 0, "totalItems": 1, "totalPages": 1},
    }})

    data: List[CatalogProductItem] = Field(description="Página de produtos do catálogo.")
    meta: PagedMeta = Field(description="Paginação.")


# ------------------------------------------------------------------ sazonalidade por produto (contrato 1.0.0; P-106..P-116)

class SeasonalityProduct(CamelModel):
    """Dados cadastrais básicos do produto consultado para sazonalidade."""

    codigo: int = Field(description="Código do produto.")
    descricao: str = Field(description="Descrição cadastral.")
    fornecedor: str = Field(description="Fornecedor.")
    estoque: float = Field(description="Estoque atual disponível.")
    preco_venda: float = Field(description="Preço de venda praticado.")


class SeasonalityPeakValleySchema(CamelModel):
    """Período de pico ou vale da sazonalidade."""

    mes_inicio: int = Field(description="Mês inicial do período (1 a 12).")
    mes_fim: int = Field(description="Mês final do período (1 a 12).")
    nome_periodo: str = Field(description="Nome formatado (ex: 'Março' ou 'Mai–Jul').")
    indice: float = Field(description="Índice sazonal do ponto extremo.")
    confianca: str = Field(description="Nível de confiança: ALTA, MEDIA ou BAIXA.")


class MonthlySeasonalityPointSchema(CamelModel):
    """Ponto de índice sazonal para um mês do calendário."""

    mes: int = Field(description="Mês do calendário (1 a 12).")
    nome_mes: str = Field(description="Nome do mês por extenso (ex: 'Janeiro').")
    indice: float = Field(description="Índice sazonal normalizado (1.0 = neutro).")
    confianca: str = Field(description="Nível de confiança: ALTA, MEDIA ou BAIXA.")
    observacoes_disponiveis: int = Field(description="Número de ocorrências observadas (1 ou 2).")
    razao_2025: Optional[float] = Field(default=None, description="Razão anual observada em 2025.")
    razao_2026: Optional[float] = Field(default=None, description="Razão anual observada em 2026.")
    volume_liquido_historico: int = Field(description="Soma de quantidades líquidas no histórico.")
    receita_liquida_historica: float = Field(description="Soma de receita líquida no histórico.")


class SeasonalityData(CamelModel):
    """Payload de dados do produto na consulta de sazonalidade."""

    produto: SeasonalityProduct = Field(description="Dados do produto.")
    elegivel: bool = Field(description="Se possui histórico suficiente para análise confiável.")
    forca: str = Field(description="Grau de sazonalidade: FORTE, MODERADA, FRACA ou INSUFICIENTE.")
    motivo_insuficiencia: Optional[str] = Field(default=None, description="HISTORICO_CURTO ou VENDA_ESPORADICA se inelegível.")
    amplitude: float = Field(description="Diferença entre o maior e o menor índice sazonal.")
    correlacao_yoy: Optional[float] = Field(default=None, description="Correlação ano a ano nos meses em comum.")
    pico: SeasonalityPeakValleySchema = Field(description="Período de pico de demanda.")
    vale: SeasonalityPeakValleySchema = Field(description="Período de menor demanda.")
    serie_mensal: List[MonthlySeasonalityPointSchema] = Field(description="Curva dos 12 meses do calendário.")


class SeasonalityResponse(CamelModel):
    """Resposta de GET /analytics/seasonality/{sku}."""

    data: SeasonalityData = Field(description="Diagnóstico completo de sazonalidade.")
    meta: AnalyticsMeta = Field(description="Metadados da resposta.")


class SeasonalityRankingItemSchema(CamelModel):
    """Item do ranking de sazonalidade."""

    sku: int = Field(description="Código do produto.")
    descricao: str = Field(description="Descrição do produto.")
    fornecedor: str = Field(description="Fornecedor.")
    forca: str = Field(description="FORTE, MODERADA, FRACA ou INSUFICIENTE.")
    amplitude: float = Field(description="Amplitude do índice sazonal.")
    mes_pico: str = Field(description="Mês ou período de pico.")
    mes_vale: str = Field(description="Mês ou período de vale.")
    faturamento_total: float = Field(description="Faturamento total líquido no período.")
    motivo_insuficiencia: Optional[str] = Field(default=None, description="Motivo se for pouco mensurável.")


class SeasonalityRankingResponse(CamelModel):
    """Resposta de GET /analytics/seasonality/ranking."""

    data: List[SeasonalityRankingItemSchema] = Field(description="Lista paginada de produtos.")
    meta: PagedMeta = Field(description="Metadados com paginação.")


# ------------------------------------------------------------------ Elasticidade-Preço (F5 / P-095..P-105)

class ResponseMeta(CamelModel):
    """Metadados de resposta para os endpoints de elasticidade e analytics."""
    timestamp: str = Field(description="Momento da resposta (ISO-8601).")
    version: str = Field(default="1.0.0", description="Versão do contrato.")
    data_referencia: Optional[str] = Field(default=None, description="Data de referência da base (AAAA-MM-DD).")
    total_items: Optional[int] = Field(default=None, description="Total de itens disponíveis.")
    total_pages: Optional[int] = Field(default=None, description="Total de páginas.")
    limit: Optional[int] = Field(default=None, description="Limite da página.")
    offset: Optional[int] = Field(default=None, description="Deslocamento da página.")


class ProductHeader(CamelModel):
    """Cabeçalho com informações comerciais do produto avaliado."""
    code: int = Field(description="Código do produto.")
    description: str = Field(description="Descrição do produto.")
    supplier: str = Field(description="Nome do fornecedor / fabricante.")
    current_price: float = Field(description="Preço de venda praticado atual.")
    cost_price: float = Field(description="Último preço de custo unitário.")
    stock: float = Field(description="Estoque disponível atual.")
    is_cost_estimated: bool = Field(
        default=False,
        description="Indica se o custo do catálogo veio do fallback de 60% ([Pc.Ultimo Custo] <= 0).",
    )
    recent_volume_60d: float = Field(
        default=0.0,
        alias="recentVolume60d",
        description="Volume líquido de vendas nos últimos 60 dias (VENDA - DEVOLU%, mínimo 0.0).",
    )
    stock_target_days: int = Field(
        default=elasticity.STOCK_TARGET_DAYS,
        description="Meta corporativa de cobertura de estoque em dias (60).",
    )


class CustomerElasticityItem(CamelModel):
    """Item da lista de clientes do produto com elasticidade individual e shrinkage."""
    customer_code: int = Field(description="Código pseudonimizado do cliente.")
    orders_count: int = Field(description="Total de pedidos do cliente com este produto.")
    total_units: float = Field(description="Volume total de unidades compradas pelo cliente.")
    empirical_elasticity: float = Field(description="Elasticidade calculada estritamente com dados do cliente.")
    shrinkage_elasticity: float = Field(description="Elasticidade final suavizada via encolhimento bayesiano.")
    classification: str = Field(description="Classificação econômica: ELASTICO ou INELASTICO.")
    shrinkage_weight: float = Field(description="Peso amostral do cliente no shrinkage: n / (n + 10).")


class ProductElasticityMetrics(CamelModel):
    """Parâmetros econométricos estimados de elasticidade do produto."""
    coefficient: float = Field(description="Coeficiente de elasticidade da demanda.")
    classification: str = Field(description="Classificação: ELASTICO ou INELASTICO.")
    r_squared: float = Field(description="R² da regressão.")
    standard_error: float = Field(description="Erro padrão do estimador beta.")
    confidence_interval: List[float] = Field(description="Intervalo de confiança de 95%.")
    confidence_level: str = Field(description="Nível de confiança: ALTA, MEDIA ou BAIXA.")
    is_reliable: bool = Field(description="Se a estimativa é confiável.")
    observations_count: int = Field(description="Número de observações válidas.")
    fallback_applied: bool = Field(description="Se o fallback padrão foi aplicado.")
    insight_message: str = Field(description="Mensagem descritiva de apoio comercial.")


class ProductElasticityDetail(CamelModel):
    """Dados agregados completos de elasticidade do produto."""
    product: ProductHeader = Field(description="Dados cadastrais e comerciais do produto.")
    elasticity: ProductElasticityMetrics = Field(description="Parâmetros econométricos estimados de elasticidade.")
    customers: List[CustomerElasticityItem] = Field(default_factory=list, description="Clientes com histórico no produto.")


class ProductElasticityResponse(CamelModel):
    """Envelope 200 OK para GET /analytics/elasticity/product/{sku}."""
    data: ProductElasticityDetail = Field(description="Detalhe do produto e elasticidade.")
    meta: ResponseMeta = Field(description="Metadados da requisição.")


class CustomerElasticityDetail(CamelModel):
    """Detalhes de elasticidade para o par produto x cliente."""
    sku: int = Field(description="Código do produto.")
    customer_code: int = Field(description="Código do cliente.")
    product_elasticity: float = Field(description="Elasticidade geral do produto.")
    customer_empirical_elasticity: float = Field(description="Elasticidade empírica do cliente.")
    customer_elasticity: float = Field(description="Elasticidade final resultante do shrinkage.")
    classification: str = Field(description="Classificação econômica: ELASTICO ou INELASTICO.")
    shrinkage_weight: float = Field(description="Peso do cliente no encolhimento bayesiano.")
    orders_count: int = Field(description="Total de pedidos do cliente no SKU.")
    total_units: float = Field(description="Total de unidades adquiridas.")
    confidence_level: str = Field(description="Nível de confiança estatística.")
    is_reliable: bool = Field(description="Confiabilidade da estimativa.")
    insight_message: str = Field(description="Mensagem de diagnóstico comercial.")


class CustomerElasticityResponse(CamelModel):
    """Envelope 200 OK para GET /analytics/elasticity/product/{sku}/customer/{customerCode}."""
    data: CustomerElasticityDetail = Field(description="Dados de elasticidade do par produto x cliente.")
    meta: ResponseMeta = Field(description="Metadados da requisição.")


class ElasticitySimulationRequest(CamelModel):
    """Corpo de requisição para POST /analytics/elasticity/simulate."""
    sku: int = Field(gt=0, description="Código do produto avaliado.")
    customer_code: Optional[int] = Field(default=None, gt=0, description="Código do cliente opcional.")
    price_change_pct: float = Field(ge=-50.0, le=100.0, description="Variação percentual de preço pretendida.")
    current_price: Optional[float] = Field(default=None, gt=0.0, description="Preço atual manual opcional informado na calculadora.")
    cost_price: Optional[float] = Field(default=None, ge=0.0, description="Custo unitário manual opcional em R$.")


class SimulationImpactData(CamelModel):
    """Resultado dos impactos calculados em volume, receita, margem e estoque."""
    sku: int = Field(description="Código do produto.")
    customer_code: Optional[int] = Field(default=None, description="Código do cliente se individualizado.")
    applied_elasticity: float = Field(description="Elasticidade aplicada na projeção.")
    price_change_pct: float = Field(description="Percentual de variação de preço informado.")
    current_price: float = Field(description="Preço de venda atual.")
    projected_price: float = Field(description="Preço de venda projetado.")
    current_volume: float = Field(description="Volume atual em unidades.")
    projected_volume: float = Field(description="Volume projetado em unidades.")
    volume_change_pct: float = Field(description="Variação percentual de volume.")
    current_revenue: float = Field(description="Faturamento atual em R$.")
    projected_revenue: float = Field(description="Faturamento projetado em R$.")
    revenue_change_pct: float = Field(description="Variação percentual de faturamento.")
    revenue_change_abs: float = Field(description="Variação monetária de faturamento em R$.")
    current_margin: float = Field(description="Margem financeira atual em R$.")
    projected_margin: float = Field(description="Margem financeira projetada em R$.")
    margin_change_pct: float = Field(description="Variação percentual de margem.")
    margin_change_abs: float = Field(description="Variação monetária de margem em R$.")
    recommendation: str = Field(description="Recomendação comercial do cenário.")
    cost_price: float = Field(default=0.0, description="Custo unitário efetivamente utilizado na simulação (R$).")
    is_cost_estimated: bool = Field(default=False, description="Indica se usou fallback de 60% sem override manual.")
    is_cost_override: bool = Field(default=False, description="Indica se o custo unitário foi editado manualmente.")
    stock: float = Field(default=0.0, description="Estoque disponível atual do SKU (un.).")
    stock_target_days: int = Field(
        default=elasticity.STOCK_TARGET_DAYS,
        description="Meta de cobertura de estoque em dias (60).",
    )
    current_unit_margin: float = Field(default=0.0, description="Margem unitária atual (R$/un.).")
    projected_unit_margin: float = Field(default=0.0, description="Margem unitária projetada (R$/un.).")
    current_unit_margin_pct: float = Field(default=0.0, description="Margem unitária percentual atual (%).")
    projected_unit_margin_pct: float = Field(default=0.0, description="Margem unitária percentual projetada (%).")
    unit_margin_pct_change_pp: float = Field(default=0.0, description="Variação da margem unitária em pontos percentuais (p.p.).")
    volume_change_units: float = Field(default=0.0, description="Variação absoluta de volume (un.).")
    current_daily_units: float = Field(default=0.0, description="Ritmo diário atual (un./dia).")
    projected_daily_units: float = Field(default=0.0, description="Ritmo diário projetado (un./dia).")
    current_stock_days: Optional[float] = Field(default=None, description="Duração estimada do estoque atual em dias.")
    projected_stock_days: Optional[float] = Field(default=None, description="Duração estimada do estoque projetado em dias.")
    stock_days_delta: Optional[float] = Field(default=None, description="Variação na duração do estoque em dias.")
    is_price_override: bool = Field(default=False, description="Indica se o preço atual foi editado manualmente na calculadora.")


class ElasticitySimulationResponse(CamelModel):
    """Envelope 200 OK para POST /analytics/elasticity/simulate."""
    data: SimulationImpactData = Field(description="Resultado dos impactos calculados em volume, receita e margem.")
    meta: ResponseMeta = Field(description="Metadados da requisição.")


# ------------------------------------------------------------------ Canibalização e Substituição (F6 / P-128..P-138)


class SubstituteCandidateDTO(CamelModel):
    """Candidato a produto substituto (sem PII de clientes, P-128.5)."""

    sku: str = Field(description="Código do produto substituto.")
    description: str = Field(description="Descrição do produto.")
    category: str = Field(description="Categoria (`Tipo`) do produto.")
    jaccard_similarity: float = Field(description="Coeficiente de similaridade de Jaccard.")
    common_buyers_count: int = Field(description="Quantidade de compradores em comum (sem identificadores).")
    current_price: float = Field(description="Preço atual de venda.")
    current_stock: int = Field(description="Estoque disponível atual.")


class SubstitutionDataDTO(CamelModel):
    """Dados do endpoint GET /analytics/substitution/{sku}."""

    target_sku: str = Field(description="SKU alvo consultado.")
    target_description: str = Field(description="Descrição do SKU alvo.")
    target_category: str = Field(description="Categoria (`Tipo`) do SKU alvo.")
    target_current_price: float = Field(description="Preço de venda atual do SKU alvo.")
    target_stock: int = Field(description="Estoque atual do SKU alvo.")
    substitutes: List[SubstituteCandidateDTO] = Field(default_factory=list, description="Lista de substitutos.")


class SubstitutionMeta(AnalyticsMeta):
    """Metadados de resposta de GET /analytics/substitution/{sku}."""

    version: str = Field(default="1.0.0", description="Versão do contrato.")
    target_sku: str = Field(description="SKU alvo consultado.")
    total_found: int = Field(description="Total de substitutos encontrados.")
    execution_time_ms: int = Field(default=0, description="Tempo de execução em ms.")


class SubstitutionResponse(CamelModel):
    """Envelope 200 OK para GET /analytics/substitution/{sku}."""

    data: SubstitutionDataDTO = Field(description="Mapa de substitutos do SKU alvo.")
    meta: Union[SubstitutionMeta, ResponseMeta] = Field(description="Metadados da requisição.")


class PeriodMetricsDTO(CamelModel):
    """Métricas agregadas do produto alvo na janela pré ou pós evento."""

    start_date: str = Field(description="Data inicial da janela (AAAA-MM-DD).")
    end_date: str = Field(description="Data final da janela (AAAA-MM-DD).")
    volume: float = Field(description="Volume líquido vendido na janela.")
    avg_price: float = Field(description="Preço médio de venda na janela.")
    revenue: float = Field(description="Receita líquida na janela.")
    estimated_margin: float = Field(description="Margem de contribuição estimada na janela.")


class TargetProductDTO(CamelModel):
    """Dados e desempenho do produto alvo da ação comercial."""

    sku: str = Field(description="SKU do produto alvo.")
    description: str = Field(description="Descrição do produto alvo.")
    category: str = Field(description="Categoria (`Tipo`) do produto alvo.")
    event_type: Literal["promo", "price", "launch"] = Field(description="Tipo de evento analisado.")
    event_date: str = Field(description="Data base do evento T0 (AAAA-MM-DD).")
    price_direction: Literal["PRICE_DROP", "PRICE_HIKE", "NONE"] = Field(description="Direção da variação de preço.")
    avg_price_change_pct: float = Field(description="Variação percentual do preço médio.")
    cost_fallback_used: bool = Field(description="Indica se aplicou fallback de custo de 60%.")
    pre_period: PeriodMetricsDTO = Field(description="Métricas da janela pré-evento.")
    post_period: PeriodMetricsDTO = Field(description="Métricas da janela pós-evento.")
    delta_volume: float = Field(description="Variação absoluta de volume do alvo.")
    delta_volume_pct: float = Field(description="Variação percentual de volume do alvo.")
    delta_revenue: float = Field(description="Variação absoluta de receita do alvo.")
    delta_margin: float = Field(description="Variação absoluta de margem do alvo.")


class ControlGroupDTO(CamelModel):
    """Resumo do grupo de controle selecionado para o DiD (P-131)."""

    category: str = Field(description="Categoria principal do grupo de controle.")
    sample_size: int = Field(description="Quantidade de produtos estáveis no controle.")
    growth_factor: float = Field(description="Fator de crescimento g_ctrl do grupo de controle.")
    control_strategy: Literal["CATEGORIAL", "FORNECEDOR", "GLOBAL"] = Field(description="Estratégia de seleção.")
    is_expanded_control: bool = Field(description="True se houve fallback para fornecedor ou portfólio global.")
    description: str = Field(description="Descrição resumida do grupo de controle.")


class TimelinePointDTO(CamelModel):
    """Ponto semanal da série temporal simétrica pré/pós evento (P-130)."""

    week_offset: int = Field(description="Deslocamento semanal em relação a T0 (-W..-1 ou 1..W).")
    start_date: str = Field(description="Início da semana (AAAA-MM-DD).")
    end_date: str = Field(description="Fim da semana (AAAA-MM-DD).")
    period: Literal["PRE", "POST"] = Field(description="Período relativo ao evento.")
    target_volume: float = Field(description="Volume do produto alvo na semana.")
    control_total_volume: float = Field(description="Volume total do grupo de controle na semana.")


class ElasticityDecompositionDTO(CamelModel):
    """Decomposição opcional de choque de preço via F5 (P-136.2)."""

    cross_elasticity: float = Field(description="Elasticidade cruzada epsilon_ji.")
    price_explained_delta_volume: float = Field(description="Parcela da variação explicada por preço.")
    residual_delta_volume: float = Field(description="Parcela residual (visibilidade/layout).")
    price_explained_share: float = Field(description="Proporção explicada por preço.")


class AffectedProductDTO(CamelModel):
    """Produto candidato avaliado pelo motor DiD + FDR (P-132 a P-134)."""

    sku: str = Field(description="SKU do produto afetado.")
    description: str = Field(description="Descrição do produto.")
    category: str = Field(description="Categoria (`Tipo`).")
    jaccard_similarity: float = Field(description="Similaridade de Jaccard com o alvo.")
    common_buyers_count: int = Field(description="Quantidade de compradores em comum.")
    pre_volume: float = Field(description="Volume na janela pré-evento.")
    post_volume: float = Field(description="Volume na janela pós-evento.")
    counterfactual_volume: float = Field(description="Volume contrafactual projetado pelo controle.")
    delta_volume: float = Field(description="Efeito causal líquido estimado em unidades.")
    delta_volume_pct: float = Field(description="Variação percentual causal.")
    unit_price: float = Field(description="Preço unitário médio no período pós.")
    unit_margin: float = Field(description="Margem unitária em R$.")
    cost_fallback_used: bool = Field(description="Indica se aplicou fallback de custo de 60%.")
    delta_revenue: float = Field(description="Impacto estimado em receita líquida.")
    delta_margin: float = Field(description="Impacto estimado em margem de contribuição.")
    classification: Literal["CANIBALIZACAO", "COMPLEMENTO", "MIGRACAO_POSITIVA", "SEM_EFEITO"] = Field(
        description="Classificação semântica do impacto."
    )
    p_value: float = Field(description="Valor-p bicaudal bruto.")
    q_value: float = Field(description="Valor-q ajustado por Benjamini-Hochberg.")
    is_significant: bool = Field(description="Significativo após FDR e corte prático.")
    confidence_interval: List[float] = Field(description="Intervalo de confiança de 95% [inf, sup].")
    elasticity_decomposition: Optional[ElasticityDecompositionDTO] = Field(
        default=None, description="Decomposição de elasticidade cruzada (F5) ou null."
    )


class NetImpactDTO(CamelModel):
    """Balanço líquido consolidado e veredito comercial da ação (P-135)."""

    target_delta_volume: float = Field(description="Delta de volume do produto alvo.")
    affected_delta_volume: float = Field(description="Soma do delta de volume dos produtos afetados.")
    net_delta_volume: float = Field(description="Efeito líquido global em unidades.")
    target_delta_revenue: float = Field(description="Delta de receita do produto alvo.")
    affected_delta_revenue: float = Field(description="Soma do delta de receita dos afetados.")
    net_delta_revenue: float = Field(description="Efeito líquido global em receita.")
    target_delta_margin: float = Field(description="Delta de margem do produto alvo.")
    affected_delta_margin: float = Field(description="Soma do delta de margem dos afetados.")
    net_delta_margin: float = Field(description="Efeito líquido global em margem.")
    commercial_verdict: Literal["VALEU_A_PENA", "ILUSAO_DE_VOLUME", "PREJUIZO_TOTAL"] = Field(
        description="Veredito executivo da ação."
    )
    summary_message: str = Field(description="Resumo executivo em português.")


class ElasticityIntegrationDTO(CamelModel):
    """Status de integração com o módulo de Elasticidade-Preço Cruzada (F5, P-136.3)."""

    status: Literal["NAO_INTEGRADO", "INTEGRADO", "PARCIAL"] = Field(description="Estado da integração com F5.")
    message: str = Field(description="Mensagem descritiva do estado de integração.")


class CannibalizationDataDTO(CamelModel):
    """Corpo de dados do endpoint GET /analytics/cannibalization/{sku}."""

    target_product: TargetProductDTO = Field(description="Dados e desempenho do produto alvo.")
    control_group: ControlGroupDTO = Field(description="Grupo de controle utilizado no DiD.")
    timeline_series: List[TimelinePointDTO] = Field(default_factory=list, description="Série semanal pré/pós.")
    affected_products: List[AffectedProductDTO] = Field(default_factory=list, description="Produtos afetados.")
    net_impact: NetImpactDTO = Field(description="Consolidação financeira e veredito comercial.")
    elasticity_integration: ElasticityIntegrationDTO = Field(description="Estado da integração com F5.")


class CannibalizationMeta(AnalyticsMeta):
    """Metadados de resposta de GET /analytics/cannibalization/{sku}."""

    version: str = Field(default="1.0.0", description="Versão do contrato.")
    sku: str = Field(description="SKU alvo analisado.")
    event_type: Literal["promo", "price", "launch"] = Field(description="Tipo de evento analisado.")
    window_weeks: int = Field(description="Tamanho da janela simétrica em semanas.")
    execution_time_ms: int = Field(default=0, description="Tempo de execução em ms.")


class CannibalizationResponse(CamelModel):
    """Envelope 200 OK para GET /analytics/cannibalization/{sku}."""

    data: CannibalizationDataDTO = Field(description="Análise completa de canibalização.")
    meta: CannibalizationMeta = Field(description="Metadados da requisição.")


# ------------------------------------------------------------------ Canibalização v2 — Relatório Global e Equilíbrio de Preço (F6 v2 / P-128..P-138)

CannibalizationMechanismLiteral = Literal[
    "PRECO_MENOR_DESTROI_MARGEM",
    "PRECO_MENOR_MARGEM_PRESERVADA",
    "MIGRACAO_POR_VALOR",
]


class PeriodRangeDTO(CamelModel):
    """Intervalo inclusivo de datas (AAAA-MM-DD) de uma janela comparativa."""

    start_date: str = Field(description="Data inicial inclusiva (AAAA-MM-DD).")
    end_date: str = Field(description="Data final inclusiva (AAAA-MM-DD).")


class CannibalizationReportKpisDTO(CamelModel):
    """KPIs globais consolidados do relatório de canibalização (P-132.4)."""

    total_victims: int = Field(description="Quantidade de SKUs vítimas encontrados.")
    total_cannibalized_revenue: float = Field(description="Soma do faturamento canibalizado em R$.")
    avg_cannibalized_revenue_pct: float = Field(description="Percentual médio ponderado de faturamento canibalizado.")
    total_net_margin_impact: float = Field(description="Impacto líquido total de margem em R$.")
    margin_destroying_pairs_count: int = Field(description="Contagem de pares classificados como PRECO_MENOR_DESTROI_MARGEM.")


class CannibalizerSummaryDTO(CamelModel):
    """Resumo de um produto canibalizador B no relatório global (zero PII, LGPD-CAN-02)."""

    sku: str = Field(description="SKU do produto canibalizador.")
    description: str = Field(description="Descrição do produto canibalizador.")
    migrated_clients: int = Field(description="Quantidade líquida de clientes migrados (A -> B).")
    migrated_revenue: float = Field(description="Faturamento líquido migrado em R$.")
    share_of_cannibalization_pct: float = Field(description="Participação percentual deste canibalizador na vítima.")
    current_price: float = Field(description="Preço de referência atual do canibalizador.")
    unit_margin: float = Field(description="Margem unitária em R$.")
    margin_pct: float = Field(description="Margem unitária percentual (%).")
    cost_fallback_used: bool = Field(description="Indica se aplicou fallback de custo de 60%.")
    price_gap_pct: float = Field(description="Gap percentual de preço ((P_A - P_B) / P_B * 100).")
    net_margin_impact: float = Field(description="Impacto líquido de margem do par em R$.")
    mechanism: CannibalizationMechanismLiteral = Field(description="Classificação do mecanismo de canibalização.")
    suggested_victim_price: float = Field(description="Preço sugerido de equilíbrio para a vítima.")
    suggested_cannibal_price: float = Field(description="Preço sugerido de equilíbrio para o canibalizador.")
    projected_price_gap_pct: float = Field(description="Gap percentual de preço projetado após equilíbrio.")
    action_summary: str = Field(description="Resumo acionável de precificação em português.")


class CannibalizerDetailDTO(CannibalizerSummaryDTO):
    """Detalhe completo de um produto canibalizador B no drill-down da vítima."""

    category: str = Field(description="Categoria (`Tipo`) do canibalizador.")
    supplier: str = Field(description="Fornecedor do canibalizador.")
    gross_clients_to_cannibal: int = Field(description="Clientes brutos migrando de A para B.")
    reverse_clients_to_victim: int = Field(description="Clientes no fluxo reverso de B para A.")
    pre_revenue: float = Field(description="Faturamento líquido do canibalizador no período PRE.")
    cur_revenue: float = Field(description="Faturamento líquido do canibalizador no período CUR.")
    unit_cost: float = Field(description="Custo unitário efetivo utilizado (R$).")
    current_stock: int = Field(description="Estoque atual disponível do canibalizador.")
    victim_margin_floor_price: float = Field(description="Preço piso da vítima para preservar 20% de margem.")


class CannibalizationVictimBaseDTO(CamelModel):
    """Métricas financeiras e comerciais da vítima A."""

    sku: str = Field(description="SKU do produto vítima.")
    description: str = Field(description="Descrição do produto vítima.")
    category: str = Field(description="Categoria (`Tipo`) do produto vítima.")
    supplier: str = Field(description="Fornecedor do produto vítima.")
    pre_revenue: float = Field(description="Faturamento líquido no período PRE.")
    cur_revenue: float = Field(description="Faturamento líquido no período CUR.")
    revenue_drop: float = Field(description="Queda absoluta de faturamento (PRE - CUR).")
    revenue_drop_pct: float = Field(description="Queda percentual de faturamento.")
    cannibalized_revenue: float = Field(description="Faturamento perdido atribuído à canibalização (R$).")
    cannibalized_revenue_pct: float = Field(description="Percentual do faturamento PRE canibalizado.")
    drop_explained_pct: float = Field(description="Parcela percentual da queda explicada por canibalização.")
    current_price: float = Field(description="Preço de referência atual da vítima.")
    unit_cost: float = Field(description="Custo unitário efetivo da vítima (R$).")
    unit_margin: float = Field(description="Margem unitária da vítima (R$).")
    margin_pct: float = Field(description="Margem percentual da vítima (%).")
    cost_fallback_used: bool = Field(description="Indica se aplicou fallback de custo de 60%.")
    current_stock: int = Field(description="Estoque disponível atual da vítima.")
    cannibalizer_count: int = Field(description="Quantidade de canibalizadores válidos identificados.")
    net_margin_impact: float = Field(description="Impacto líquido acumulado de margem em R$.")


class CannibalizationVictimSummaryDTO(CannibalizationVictimBaseDTO):
    """Item de vítima no Relatório Global de Canibalização."""

    top_cannibal: CannibalizerSummaryDTO = Field(description="Principal canibalizador (maior receita migrada).")
    cannibalizers: List[CannibalizerSummaryDTO] = Field(default_factory=list, description="Lista de canibalizadores.")


class CannibalizationReportDataDTO(CamelModel):
    """Corpo de dados de GET /api/v1/analytics/cannibalization/report."""

    kpis: CannibalizationReportKpisDTO = Field(description="KPIs consolidados do relatório.")
    available_categories: List[str] = Field(default_factory=list, description="Categorias disponíveis para filtro.")
    available_suppliers: List[str] = Field(default_factory=list, description="Fornecedores disponíveis para filtro.")
    victims: List[CannibalizationVictimSummaryDTO] = Field(default_factory=list, description="Lista de produtos vítimas.")


class CannibalizationReportMeta(AnalyticsMeta):
    """Metadados de resposta de GET /api/v1/analytics/cannibalization/report."""

    version: str = Field(default=ANALYTICS_CONTRACT_VERSION, description="Versão do contrato da API.")
    window_days: int = Field(description="Janela comparativa selecionada (30, 60 ou 90 dias).")
    min_drop_pct: float = Field(description="Queda percentual mínima aplicada.")
    min_migrated_clients: int = Field(description="Mínimo de clientes em migração líquida aplicado.")
    pre_period: PeriodRangeDTO = Field(description="Período anterior (PRE).")
    cur_period: PeriodRangeDTO = Field(description="Período atual (CUR).")
    total_found: int = Field(description="Quantidade total de vítimas após filtros.")
    execution_time_ms: int = Field(default=0, description="Tempo de execução em ms.")


class CannibalizationReportResponse(CamelModel):
    """Envelope 200 OK para GET /api/v1/analytics/cannibalization/report."""

    data: CannibalizationReportDataDTO = Field(description="Relatório global de canibalização.")
    meta: CannibalizationReportMeta = Field(description="Metadados da requisição.")


class CannibalizationVictimDetailDataDTO(CamelModel):
    """Corpo de dados de GET /api/v1/analytics/cannibalization/report/{sku}."""

    is_cannibalized: bool = Field(description="Indica se o SKU possui canibalização detectada na janela.")
    victim: CannibalizationVictimBaseDTO = Field(description="Métricas da vítima consultada.")
    cannibalizers: List[CannibalizerDetailDTO] = Field(default_factory=list, description="Canibalizadores detalhados.")


class CannibalizationVictimDetailMeta(AnalyticsMeta):
    """Metadados de resposta de GET /api/v1/analytics/cannibalization/report/{sku}."""

    version: str = Field(default=ANALYTICS_CONTRACT_VERSION, description="Versão do contrato da API.")
    sku: str = Field(description="SKU consultado.")
    window_days: int = Field(description="Janela comparativa selecionada (30, 60 ou 90 dias).")
    pre_period: PeriodRangeDTO = Field(description="Período anterior (PRE).")
    cur_period: PeriodRangeDTO = Field(description="Período atual (CUR).")
    execution_time_ms: int = Field(default=0, description="Tempo de execução em ms.")


class CannibalizationVictimDetailResponse(CamelModel):
    """Envelope 200 OK para GET /api/v1/analytics/cannibalization/report/{sku}."""

    data: CannibalizationVictimDetailDataDTO = Field(description="Diagnóstico detalhado da vítima.")
    meta: CannibalizationVictimDetailMeta = Field(description="Metadados da requisição.")
