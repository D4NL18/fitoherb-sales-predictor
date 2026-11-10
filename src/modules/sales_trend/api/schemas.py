"""
Schemas Pydantic para validação e serialização da API de Tendência de Vendas (ADR-003 DA-11).
Utiliza camelCase via aliases para conformidade rigorosa com o Contrato de API 1.0.0.
"""
from datetime import datetime, timezone
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
    status: Literal["VARIACAO", "NOVO", "SEM_MOVIMENTO", "SEM_BASE"]
    variacao_pct: Optional[float] = None
    atual: float
    anterior: float
    base_parcial: bool
    base_baixa: bool
    devolucao_liquida: bool
    atual_por_dia: Optional[float] = None
    anterior_por_dia: Optional[float] = None


class ProductTrendItemSchema(CamelModel):
    """Linha da tabela de tendência por produto ativo."""
    sku: int
    descricao: str
    fornecedor: Optional[str] = None
    janelas: Dict[str, TrendCellSchema]


class SupplierTrendItemSchema(CamelModel):
    """Linha da tabela de tendência por fornecedor."""
    supplier_key: str
    fornecedor: str
    total_skus: int
    janelas: Dict[str, TrendCellSchema]


class SupplierProductItemSchema(CamelModel):
    """Item no detalhe de produtos de um fornecedor."""
    sku: int
    descricao: str
    variacao_pct: Optional[float] = None
    status: Literal["VARIACAO", "NOVO", "SEM_MOVIMENTO", "SEM_BASE"]
    atual: float
    anterior: float
    contribuicao_pp: Optional[float] = None
    contribuicao_valor: float
    base_parcial: bool
    base_baixa: bool
    devolucao_liquida: bool


class JanelaMeta(CamelModel):
    """Metadados de período e cobertura de uma janela."""
    tamanho_meses: int
    rotulo_periodo_atual: str
    rotulo_periodo_anterior: str
    dias_janela: int
    dias_cobertos_atual: int
    dias_cobertos_anterior: int
    base_parcial: bool


class TotaisPorVisaoSchema(CamelModel):
    """Contagem de SKUs/fornecedores nas diferentes visões."""
    total: int
    rising: int
    falling: int
    new: int


class ParametrosMeta(CamelModel):
    """Hiperparâmetros e limiares de negócio da Tendência."""
    low_base_min_quantity: int
    low_base_min_revenue: float
    cache_ttl_hours: int
    trend_span_months: int


class OrdenacaoMeta(CamelModel):
    """Metadados de ordenação aplicada."""
    sort_window: int
    sort_dir: str
    sort_by: Optional[str] = None


class TrendMeta(CamelModel):
    """Metadados completos de resposta da API."""
    timestamp: str
    versao_contrato: str = "1.0.0"
    data_referencia: str
    ultimo_dia_coberto: str
    mes_base: str
    mes_base_padrao: str
    mes_base_minimo: str
    mes_base_maximo: str
    mes_base_parcial: bool
    agrupamento: str
    metrica: str
    total_items: int
    total_pages: int
    page: int
    limit: int
    offset: int
    totais_por_visao: TotaisPorVisaoSchema
    ordenacao: OrdenacaoMeta
    janelas: List[JanelaMeta]
    parametros: ParametrosMeta
    fornecedor: Optional[str] = None


class ProductTrendResponse(CamelModel):
    """Envelope de resposta para listagem por produto."""
    data: List[ProductTrendItemSchema]
    meta: TrendMeta


class SupplierTrendResponse(CamelModel):
    """Envelope de resposta para listagem por fornecedor."""
    data: List[SupplierTrendItemSchema]
    meta: TrendMeta


class SupplierDetailResponse(CamelModel):
    """Envelope de resposta para detalhe de produtos de fornecedor."""
    data: List[SupplierProductItemSchema]
    meta: TrendMeta


class ErrorDetail(CamelModel):
    """Detalhes de erro semântico TND-NNN."""
    code: str
    message: str
    fields: Sequence[str] = ()


class TrendErrorResponse(CamelModel):
    """Envelope padrão de erro do módulo sales_trend."""
    error: ErrorDetail
    meta: Dict[str, str]
