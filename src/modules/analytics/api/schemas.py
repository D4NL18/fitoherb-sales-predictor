"""
Schemas Pydantic da API do módulo Analytics Comercial (contrato `analytics-cross-sell` 1.1.0, ADR-002 DA-09).

Atributos em `snake_case`, JSON em `camelCase` (`alias_generator=to_camel`). Envelope `data`/`meta` em
toda resposta 2xx (P-066) e corpo único de erro (P-067, contrato §4). Os campos listados aqui são a
allowlist de LGPD-03: nenhum dado de cliente além do que o contrato permite (nem o `customerCode`).
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

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
    """Metadados de resposta para os endpoints de elasticidade."""
    timestamp: str = Field(description="Momento da resposta (ISO-8601).")
    version: str = Field(default="1.0.0", description="Versão do contrato.")
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


# ------------------------------------------------------------------ Viabilidade de Produto Novo (F2 / P-139..P-149)

NewProductSeasonalityConfidenceLiteral = Literal["ALTA", "MEDIA", "BAIXA", "INSUFICIENTE", "PADRAO"]
NewProductSeasonalityStatusLiteral = Literal["APPLIED", "FALLBACK_NEUTRAL", "UNAVAILABLE"]


class NewProductOptionsData(CamelModel):
    """Opções deduplicadas e ordenadas de fornecedores e linhas/tipos ativos (P-141)."""

    tipos: List[str] = Field(description="Lista ordenada de linhas/tipos de produto ativos.")
    fornecedores: List[str] = Field(description="Lista ordenada de fornecedores ativos.")
    tipos_por_fornecedor: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mapeamento de fornecedor ativo para suas linhas/tipos ativos.",
    )


class NewProductOptionsResponse(CamelModel):
    """Envelope 200 OK para GET /analytics/new-product/options."""

    data: NewProductOptionsData = Field(description="Opções do catálogo ativo.")
    meta: AnalyticsMeta = Field(description="Metadados da requisição.")


class NewProductForecastRequest(CamelModel):
    """Corpo de requisição para POST /analytics/new-product/forecast (P-140)."""

    tipo: Optional[str] = Field(
        default=None,
        description="Linha/categoria opcional do produto no catálogo ativo (quando omitida, busca similares em todo o catálogo priorizando descrição, preço e fornecedor).",
    )
    fornecedor: str = Field(min_length=1, description="Fornecedor pretendido no catálogo ativo.")
    descricao: str = Field(min_length=3, max_length=120, description="Descrição comercial do produto hipotético.")
    preco_venda_previsto: float = Field(description="Preço de venda previsto (R$).")
    custo_unitario: Optional[float] = Field(default=None, description="Custo unitário opcional (R$).")
    margem_minima_desejada: Optional[float] = Field(default=None, description="Margem mínima desejada [0.0..1.0].")
    horizon_months: int = Field(default=3, ge=1, le=3, description="Horizonte de projeção em meses (1 a 3).")


class MonthlyForecastItem(CamelModel):
    """Projeção mensal conservadora e faixas dos similares (P-145, P-146, P-147)."""

    month: int = Field(description="Mês relativo do lançamento (1, 2 ou 3).")
    calendar_month: int = Field(description="Mês civil correspondente (1..12).")
    quantity: int = Field(description="Quantidade final prevista após modulação sazonal e trava P25.")
    revenue: float = Field(description="Receita mensal projetada (R$).")
    gross_margin: Optional[float] = Field(default=None, description="Margem bruta mensal projetada (R$).")
    p10_quantity: int = Field(description="Percentil 10 dos similares no mês.")
    conservative_quantity: int = Field(description="Quantidade conservadora prevista.")
    p50_quantity: int = Field(description="Mediana (P50) dos similares no mês.")
    similar_p25_quantity: int = Field(description="Percentil 25 (P25) dos similares no mês.")
    seasonality_factor: float = Field(description="Fator sazonal amortecido aplicado [0.90, 1.10].")
    seasonality_confidence: NewProductSeasonalityConfidenceLiteral = Field(
        description="Nível de confiança do índice sazonal."
    )


class NewProductAggregatedTotals(CamelModel):
    """Totais e médias agregadas do horizonte projetado."""

    total_quantity: int = Field(description="Quantidade total projetada no horizonte.")
    total_revenue: float = Field(description="Receita total projetada no horizonte (R$).")
    total_gross_margin: Optional[float] = Field(default=None, description="Margem bruta total (R$).")
    average_monthly_quantity: int = Field(description="Média mensal de unidades.")
    average_monthly_revenue: float = Field(description="Receita média mensal (R$).")


class NewProductFinancialViability(CamelModel):
    """Indicadores financeiros e parecer de viabilidade (P-148)."""

    preco_venda: float = Field(description="Preço de venda previsto (R$).")
    custo_unitario: Optional[float] = Field(default=None, description="Custo unitário informado (R$).")
    margem_bruta_unitaria: Optional[float] = Field(default=None, description="Margem bruta unitária (R$).")
    margem_bruta_percentual: Optional[float] = Field(default=None, description="Margem bruta percentual [0..1].")
    margem_minima_desejada: Optional[float] = Field(default=None, description="Margem mínima desejada [0..1].")
    viavel: Optional[bool] = Field(default=None, description="Parecer booleano de viabilidade.")
    parecer: Optional[str] = Field(default=None, description="Parecer textual de viabilidade.")


class NewProductMarketCeiling(CamelModel):
    """Referencial de mercado maduro do tipo (P-147)."""

    teto_maduro_p75: int = Field(description="Percentil 75 das vendas mensais de produtos maduros do tipo.")
    descricao: str = Field(description="Aviso conceitual de que é referencial maduro, não meta de lançamento.")


class SimilarProductItem(CamelModel):
    """Produto histórico similar utilizado na composição da curva (P-142, P-143)."""

    sku: str = Field(description="Código SKU do produto similar.")
    descricao: str = Field(description="Descrição do produto similar.")
    fornecedor: str = Field(description="Fornecedor do produto similar.")
    primeira_venda: str = Field(description="Data da primeira venda (AAAA-MM-DD).")
    preco_historico: float = Field(description="Preço de venda histórico (R$).")
    score_final: float = Field(description="Score composto de similaridade [0..1].")
    score_fornecedor: float = Field(description="Score parcial de fornecedor [0..1].")
    score_preco: float = Field(description="Score parcial de proximidade log-preço [0..1].")
    score_tfidf: float = Field(description="Score parcial de similaridade textual TF-IDF [0..1].")
    quantidades_primeiros_meses: List[int] = Field(description="Quantidades líquidas nos primeiros 3 meses.")


class NewProductForecastData(CamelModel):
    """Payload principal da simulação de viabilidade de produto novo."""

    input_summary: NewProductForecastRequest = Field(description="Resumo dos parâmetros informados.")
    monthly_forecast: List[MonthlyForecastItem] = Field(description="Projeção mensal no horizonte.")
    seasonality_status: NewProductSeasonalityStatusLiteral = Field(
        description="Status de integração com o índice sazonal F1."
    )
    aggregated_totals: NewProductAggregatedTotals = Field(description="Totais agregados no horizonte.")
    financial_viability: NewProductFinancialViability = Field(description="Análise financeira de margem.")
    market_ceiling: NewProductMarketCeiling = Field(description="Teto maduro de referência (P75).")
    similars_used: List[SimilarProductItem] = Field(description="TOP-10 similares utilizados.")
    methodology_notice: str = Field(description="Aviso metodológico conservador.")


class NewProductForecastResponse(CamelModel):
    """Envelope 200 OK para POST /analytics/new-product/forecast."""

    data: NewProductForecastData = Field(description="Resultado da simulação de viabilidade.")
    meta: AnalyticsMeta = Field(description="Metadados da requisição com dataReferencia.")
