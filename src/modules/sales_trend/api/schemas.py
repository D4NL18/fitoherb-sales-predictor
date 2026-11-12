"""
Schemas Pydantic para validação e serialização da API de Tendência de Vendas (ADR-003 DA-11).
Utiliza camelCase via aliases para conformidade rigorosa com o Contrato de API 1.0.0.
"""
from typing import Any, Dict, List, Literal, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field


def _to_camel(string: str) -> str:
    """Converte snake_case para camelCase."""
    components = string.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


class CamelModel(BaseModel):
    """Modelo base com conversão automática de atributos para camelCase."""
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


class TrendCellSchema(CamelModel):
    """Célula de variação percentual de uma janela."""
    meses: int
    atual: float
    anterior: float
    variacao_pct: Optional[float] = None
    status: Literal["VARIACAO", "NOVO", "SEM_MOVIMENTO", "SEM_BASE"]
    base_parcial: bool
    base_baixa: bool
    devolucao_liquida: bool
    atual_por_dia: Optional[float] = None
    anterior_por_dia: Optional[float] = None


class TrendDetailCellSchema(TrendCellSchema):
    """Célula detalhada com contribuição para a linha do fornecedor."""
    contribuicao_pp: Optional[float] = None
    contribuicao_valor: Optional[float] = None


class ProductTrendItemSchema(CamelModel):
    """Linha da tabela de tendência por produto ativo."""
    codigo: int
    descricao: str
    fornecedor: Optional[str] = None
    janelas: List[TrendCellSchema]


class SupplierTrendItemSchema(CamelModel):
    """Linha da tabela de tendência por fornecedor."""
    fornecedor: str
    fornecedor_chave: str
    sem_fornecedor: bool = False
    qtd_produtos: int
    janelas: List[TrendCellSchema]


class SupplierProductItemSchema(CamelModel):
    """Item no detalhe de produtos de um fornecedor."""
    codigo: int
    descricao: str
    fornecedor: Optional[str] = None
    janelas: List[TrendDetailCellSchema]


class TrendTotalRowSchema(CamelModel):
    """Linha de total geral do catálogo ativo com movimento."""
    qtd_produtos: int
    janelas: List[TrendCellSchema]


class TrendWindowSpanSchema(CamelModel):
    """Período e quantidade de dias cobertos de uma janela."""
    inicio: str
    fim: str
    dias_janela: int
    dias_cobertos: int


class JanelaMeta(CamelModel):
    """Metadados de período e cobertura de uma janela."""
    meses: int
    atual: TrendWindowSpanSchema
    anterior: TrendWindowSpanSchema
    sem_base: bool
    base_parcial: bool


class TotaisPorVisaoSchema(CamelModel):
    """Contagem de SKUs/fornecedores nas diferentes visões."""
    todos: int
    maiores_altas: int
    maiores_quedas: int
    novos: int


class ParametrosMeta(CamelModel):
    """Hiperparâmetros e limiares de negócio da Tendência."""
    limite_base_baixa_quantidade: float = 10.0
    limite_base_baixa_faturamento: float = 500.0
    cobertura_minima_anterior: float = 0.5
    busca_min_caracteres: int = 2
    busca_min_caracteres_numerica: int = 1
    busca_max_caracteres: int = 60
    ttl_cache_horas: int = 6


class OrdenacaoMeta(CamelModel):
    """Metadados de ordenação aplicada na lista principal."""
    janela: int
    sentido: str


class DetailOrdenacaoMeta(CamelModel):
    """Metadados de ordenação aplicada no detalhe do fornecedor."""
    por: str
    janela: int
    sentido: str


class TrendMeta(CamelModel):
    """Metadados base de resposta da API."""
    timestamp: str
    version: str = "1.0.0"
    data_referencia: str
    ultimo_dia_coberto: str
    mes_base: str
    mes_base_padrao: str
    mes_base_minimo: str
    mes_base_maximo: str
    mes_base_parcial: bool
    metrica: str
    janelas: List[JanelaMeta]
    parametros: ParametrosMeta
    page: int
    limit: int
    offset: int
    total_items: int
    total_pages: int


class TrendListMeta(TrendMeta):
    """Metadados específicos da listagem principal."""
    agrupamento: str
    visao: str
    ordenacao: OrdenacaoMeta
    totais_por_visao: TotaisPorVisaoSchema
    total: TrendTotalRowSchema


class TrendDetailMeta(TrendMeta):
    """Metadados específicos do detalhe de produtos de fornecedor."""
    ordenacao: DetailOrdenacaoMeta
    fornecedor: SupplierTrendItemSchema


class ProductTrendResponse(CamelModel):
    """Envelope de resposta para listagem por produto."""
    data: List[ProductTrendItemSchema]
    meta: TrendListMeta


class SupplierTrendResponse(CamelModel):
    """Envelope de resposta para listagem por fornecedor."""
    data: List[SupplierTrendItemSchema]
    meta: TrendListMeta


class SupplierDetailResponse(CamelModel):
    """Envelope de resposta para detalhe de produtos de fornecedor."""
    data: List[SupplierProductItemSchema]
    meta: TrendDetailMeta


class ErrorDetail(CamelModel):
    """Detalhes de erro semântico TND-NNN."""
    code: str
    message: str
    fields: Sequence[str] = ()


class TrendErrorResponse(CamelModel):
    """Envelope padrão de erro do módulo sales_trend."""
    error: ErrorDetail
    meta: Dict[str, str]
