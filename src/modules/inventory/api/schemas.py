"""
Schemas Pydantic v2 para a API de Previsão de Estoque e Compras (Contrato 2.0.0).

Implementa o contrato REST `.agents/docs/api_contracts/inventory.md` sob o envelope
corporativo `{'data': ..., 'meta': ...}` e as regras P-053 a P-056 (ADR-001, DA-04 a DA-08).
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_core import PydanticCustomError

from src.modules.inventory.domain.replenishment_policy import (
    DEFAULT_LEAD_TIME_DAYS,
    DEFAULT_MAX_COVERAGE_DAYS,
    DEFAULT_MIN_COVERAGE_DAYS,
    check_lead_time_below_max_coverage,
    check_max_coverage_greater_than_min,
)

INVENTORY_CONTRACT_VERSION = "2.0.0"  # DA-07: marcador de versão do contrato Mín/Máx

API_HISTORY_WINDOW_DAYS_DEFAULT = 60  # P-041 / P-053.1: janela padrão de vendas
API_HISTORY_WINDOW_DAYS_LOWER = 15  # Limite inferior aceito pela API (A4 mantido)
API_HISTORY_WINDOW_DAYS_UPPER = 365  # Limite superior aceito pela API (A4 mantido)

API_MIN_COVERAGE_DAYS_DEFAULT = DEFAULT_MIN_COVERAGE_DAYS  # P-053.2: padrão 30 dias
API_MIN_COVERAGE_DAYS_LOWER = 1  # A1: piso de Dias Mínimo na API
API_MIN_COVERAGE_DAYS_UPPER = 180  # A1: teto de Dias Mínimo na API

API_MAX_COVERAGE_DAYS_DEFAULT = DEFAULT_MAX_COVERAGE_DAYS  # P-053.2: padrão 60 dias
API_MAX_COVERAGE_DAYS_LOWER = 2  # A1: piso de Dias Máximo na API (estritamente > 1)
API_MAX_COVERAGE_DAYS_UPPER = 365  # A1: teto de Dias Máximo na API

API_LEAD_TIME_DAYS_DEFAULT = DEFAULT_LEAD_TIME_DAYS  # P-055.3: padrão 15 dias
API_LEAD_TIME_DAYS_LOWER = 1  # A5: piso de Lead Time na API
API_LEAD_TIME_DAYS_UPPER = 90  # A5: teto de Lead Time na API

API_SUPPLIER_MAX_LENGTH = 120  # DA-11: tamanho máximo permitido para o filtro de fornecedor

InventoryStatusLiteral = Literal[
    "CRITICAL_STOCKOUT",
    "REORDER_NEEDED",
    "HEALTHY",
    "OVERSTOCK",
]
AbcCurveLiteral = Literal["A", "B", "C"]


class InventoryPredictRequest(BaseModel):
    """Parâmetros de entrada para cálculo da Política Mín/Máx (`/predict` e `/export-csv`).

    Regra: P-053.2, P-053.3, P-055.3, P-056.4, A1 e A2 (ADR-001, DA-05 e DA-06).
    ATENÇÃO À ORDEM DOS CAMPOS: O Pydantic v2 executa `@field_validator` na ordem de declaração
    e `info.data` contém apenas os campos anteriores que passaram pela validação de tipo/faixa.
    Portanto, `minCoverageDays` DEVE preceder `maxCoverageDays`, e `maxCoverageDays` DEVE
    preceder `leadTimeDays`. Não reordene estes atributos.
    """

    model_config = ConfigDict(
        extra="ignore",  # DA-06 / P-056.4: ignora parâmetros revogados sem alterar o cálculo
        json_schema_extra={
            "examples": [
                {
                    "historyWindowDays": 60,
                    "minCoverageDays": 30,
                    "maxCoverageDays": 60,
                    "leadTimeDays": 15,
                    "fornecedor": None,
                }
            ]
        },
    )

    historyWindowDays: int = Field(
        default=API_HISTORY_WINDOW_DAYS_DEFAULT,
        ge=API_HISTORY_WINDOW_DAYS_LOWER,
        le=API_HISTORY_WINDOW_DAYS_UPPER,
        description="Janela recente de vendas usada no cálculo da VMD, em dias (P-041, P-053.1).",
    )
    minCoverageDays: int = Field(
        default=API_MIN_COVERAGE_DAYS_DEFAULT,
        ge=API_MIN_COVERAGE_DAYS_LOWER,
        le=API_MIN_COVERAGE_DAYS_UPPER,
        description="Dias Mínimo de cobertura da política Mín/Máx (P-053.2).",
    )
    maxCoverageDays: int = Field(
        default=API_MAX_COVERAGE_DAYS_DEFAULT,
        ge=API_MAX_COVERAGE_DAYS_LOWER,
        le=API_MAX_COVERAGE_DAYS_UPPER,
        description="Dias Máximo de cobertura da política Mín/Máx; deve ser maior que minCoverageDays (P-053.3).",
    )
    leadTimeDays: int = Field(
        default=API_LEAD_TIME_DAYS_DEFAULT,
        ge=API_LEAD_TIME_DAYS_LOWER,
        le=API_LEAD_TIME_DAYS_UPPER,
        description="Prazo médio de entrega em dias; sinaliza Ruptura Iminente e deve ser menor que maxCoverageDays (P-055.3, A2).",
    )
    fornecedor: Optional[str] = Field(
        default=None,
        max_length=API_SUPPLIER_MAX_LENGTH,
        description="Filtro opcional por fornecedor/laboratório (P-047.1). None, vazio, TODOS ou ALL desativam o filtro.",
    )

    @field_validator("maxCoverageDays")
    @classmethod
    def validate_max_coverage_greater_than_min(
        cls,
        max_days: int,
        info: ValidationInfo,
    ) -> int:
        """Valida a regra cruzada P-053.3 (`maxCoverageDays > minCoverageDays`) com código INV-001."""
        min_days = info.data.get("minCoverageDays")
        if min_days is None:
            return max_days

        violation = check_max_coverage_greater_than_min(min_days, max_days)
        if violation is not None:
            raise PydanticCustomError(
                violation.code,
                violation.message,
                dict(violation.context),
            )
        return max_days

    @field_validator("leadTimeDays")
    @classmethod
    def validate_lead_time_below_max_coverage(
        cls,
        lead_time_days: int,
        info: ValidationInfo,
    ) -> int:
        """Valida a regra cruzada A2 (`leadTimeDays < maxCoverageDays`) com código INV-002."""
        max_days = info.data.get("maxCoverageDays")
        if max_days is None:
            return lead_time_days

        violation = check_lead_time_below_max_coverage(lead_time_days, max_days)
        if violation is not None:
            raise PydanticCustomError(
                violation.code,
                violation.message,
                dict(violation.context),
            )
        return lead_time_days


class InventoryPolicyEcho(BaseModel):
    """Eco dos parâmetros efetivamente aplicados no cálculo (ADR-001, DA-08)."""

    historyWindowDays: int = Field(description="Janela de vendas efetivamente usada, em dias.")
    leadTimeDays: int = Field(description="Lead time efetivamente usado na sinalização de ruptura, em dias.")
    minCoverageDays: int = Field(description="Dias Mínimo efetivamente usado no cálculo.")
    maxCoverageDays: int = Field(description="Dias Máximo efetivamente usado no cálculo.")


class CurvaADistribuicao(BaseModel):
    """Participação de SKUs de Curva A no conjunto analisado."""

    qtdItens: int = Field(description="Quantidade de SKUs classificados como Curva A no resultado.")
    percentualItens: float = Field(description="Percentual de SKUs Curva A sobre o total analisado (1 casa).")


class InventoryKPIs(BaseModel):
    """Indicadores agregados do cálculo da Política Mín/Máx (P-054.6, P-055.4, P-055.5)."""

    totalSkusAnalisados: int = Field(description="Total de SKUs no resultado após filtro de fornecedor.")
    skusEmRupturaCritica: int = Field(description="Contagem de SKUs em Ruptura Iminente (CRITICAL_STOCKOUT).")
    skusNecessitamReposicao: int = Field(description="Contagem de SKUs Abaixo do Mínimo (REORDER_NEEDED).")
    skusEstoqueSaudavel: int = Field(description="Contagem de SKUs com Estoque Saudável (HEALTHY).")
    skusEmOverstock: int = Field(description="Contagem de SKUs Acima do Máximo (OVERSTOCK).")
    investimentoTotalSugerido: float = Field(description="Soma integral de investimentoTotalItem em R$, sem teto (P-054.6).")
    capitalImobilizadoOverstock: float = Field(description="Soma do capital excedente ao Estoque Máximo nos itens OVERSTOCK em R$ (P-055.4).")
    curvaADistribuicao: CurvaADistribuicao = Field(description="Distribuição de itens de Curva A no resultado.")


class InventoryProductItem(BaseModel):
    """Item avaliado pela Política Mín/Máx (seção 5.2 do contrato 2.0.0)."""

    codigo: int = Field(description="Código interno do SKU no ERP.")
    descricao: str = Field(description="Descrição comercial do produto.")
    ean: str = Field(description="Código de barras EAN do produto.")
    fornecedor: str = Field(description="Nome do fornecedor/laboratório em maiúsculas.")
    tipo: str = Field(description="Tipo ou linha do produto.")
    estoqueAtual: float = Field(description="Estoque físico atual (1 casa decimal; negativo no ERP vira 0).")
    vmd: float = Field(description="Venda Média Diária arredondada a 2 casas apenas para exibição (P-053.6).")
    diasCobertura: float = Field(description="Autonomia do estoque atual em dias (1 casa; 999.0 representa '∞').")
    leadTime: int = Field(description="Lead time em dias aplicado na sinalização de Ruptura Iminente.")
    estoqueMinimo: int = Field(description="Estoque Mínimo em unidades inteiras: teto(VMD * minCoverageDays) (P-053.4).")
    estoqueMaximo: int = Field(description="Estoque Máximo em unidades inteiras: teto(VMD * maxCoverageDays) (P-053.5).")
    qtdSugeridaCompra: int = Field(description="Quantidade inteira sugerida de compra para voltar ao Estoque Máximo (P-054.2).")
    custoUnitario: float = Field(description="Último custo real ou fallback de 60% do preço de venda em R$ (P-054.5).")
    precoVenda: float = Field(description="Preço unitário de venda em R$.")
    investimentoTotalItem: float = Field(description="Valor total sugerido de compra do item em R$ (qtdSugeridaCompra * custoUnitario).")
    status: InventoryStatusLiteral = Field(description="Código do status operacional (P-055.2).")
    statusLabel: str = Field(description="Rótulo em português do status operacional (P-055.2).")
    curvaAbc: AbcCurveLiteral = Field(description="Classe da Curva ABC global por receita (A, B ou C).")


class InventoryPredictData(BaseModel):
    """Conteúdo do bloco `data` da resposta de `/predict`."""

    politica: InventoryPolicyEcho = Field(description="Parâmetros efetivos da Política Mín/Máx aplicada.")
    kpis: InventoryKPIs = Field(description="Indicadores consolidados do conjunto de SKUs.")
    produtos: List[InventoryProductItem] = Field(description="Lista de SKUs ordenados por prioridade operacional.")


class ResponseMeta(BaseModel):
    """Metadados padronizados do envelope de resposta da API de Estoque."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp ISO-8601 em UTC da geração da resposta.",
    )
    version: str = Field(
        default=INVENTORY_CONTRACT_VERSION,
        description="Versão do contrato REST do módulo de estoque.",
    )
    executionTimeMs: Optional[float] = Field(
        default=None,
        description="Tempo de execução do cálculo em milissegundos (preenchido em /predict).",
    )


class InventoryPredictResponse(BaseModel):
    """Envelope de resposta de `POST /api/v1/inventory/predict`."""

    data: InventoryPredictData = Field(description="Resultado da previsão de estoque e compras.")
    meta: ResponseMeta = Field(description="Metadados da execução.")


class SupplierItem(BaseModel):
    """Item de fornecedor e contagem de SKUs ativos."""

    fornecedor: str = Field(description="Identificador do fornecedor em maiúsculas (ou TODOS).")
    nome: str = Field(description="Nome de exibição do fornecedor.")
    totalSkus: int = Field(description="Total de SKUs ativos vinculados ao fornecedor.")


class SuppliersResponse(BaseModel):
    """Envelope de resposta de `GET /api/v1/inventory/suppliers`."""

    data: List[SupplierItem] = Field(description="Lista de fornecedores iniciada por TODOS.")
    meta: ResponseMeta = Field(description="Metadados da resposta.")


class RangeParameterConfig(BaseModel):
    """Configuração de faixa e passo de um controle deslizante da tela."""

    default: int = Field(description="Valor padrão do parâmetro.")
    min: int = Field(description="Valor mínimo selecionável no controle da tela.")
    max: int = Field(description="Valor máximo selecionável no controle da tela.")
    step: int = Field(description="Passo de incremento do controle deslizante.")


class InventoryConfigData(BaseModel):
    """Configuração dos 4 parâmetros da tela de Previsão de Estoque (seção 3.1 do contrato 2.0.0)."""

    historyWindowDays: RangeParameterConfig = Field(description="Faixa da Janela de Vendas Recentes na tela.")
    leadTimeDays: RangeParameterConfig = Field(description="Faixa do Lead Time de Ressuprimento na tela.")
    minCoverageDays: RangeParameterConfig = Field(description="Faixa de Dias Mínimo na tela.")
    maxCoverageDays: RangeParameterConfig = Field(description="Faixa de Dias Máximo na tela.")


class InventoryConfigResponse(BaseModel):
    """Envelope de resposta de `GET /api/v1/inventory/config`."""

    data: InventoryConfigData = Field(description="Faixas e padrões dos parâmetros da Política Mín/Máx.")
    meta: ResponseMeta = Field(description="Metadados da resposta.")
