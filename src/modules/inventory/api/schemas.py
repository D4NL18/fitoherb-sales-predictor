"""
Schemas Pydantic v2 para a API de Estoque e Compras (Inventory & Replenishment AI).
Segue o padrão de envelope corporativo {'data': ..., 'meta': ...} (P-012).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class InventoryPredictRequest(BaseModel):
    """Payload de parâmetros para a simulação de estoque e compras."""
    historyWindowDays: int = Field(default=60, ge=15, le=365, description="Janela de histórico de vendas em dias")
    leadTimeDays: int = Field(default=15, ge=1, le=90, description="Lead time médio de entrega do fornecedor em dias")
    targetCoverageDays: int = Field(default=30, ge=5, le=180, description="Dias de cobertura desejada no estoque ideal")
    serviceLevel: float = Field(default=0.95, ge=0.80, le=0.999, description="Nível de serviço probabilístico (z-score)")
    fornecedor: Optional[str] = Field(default=None, description="Filtro opcional por laboratório/fornecedor")
    budgetLimit: Optional[float] = Field(default=None, ge=0.0, description="Teto orçamentário opcional para compras")
    maxPurchaseVariationPct: Optional[float] = Field(
        default=100.0,
        ge=10.0,
        le=1000.0,
        description="Margem máxima percentual de variação pra mais da compra sobre a base física (ex: 100% permite até +100% sobre o estoque base)"
    )


class CurvaADistribuicao(BaseModel):
    qtdItens: int
    percentualItens: float


class InventoryKPIs(BaseModel):
    totalSkusAnalisados: int
    skusEmRupturaCritica: int
    skusNecessitamReposicao: int
    skusEstoqueSaudavel: int
    skusEmOverstock: int
    skusLimitadosPorEspaco: int = 0
    investimentoTotalSugerido: float
    capitalImobilizadoOverstock: float
    curvaADistribuicao: CurvaADistribuicao


class InventoryProductItem(BaseModel):
    codigo: int
    descricao: str
    ean: str
    fornecedor: str
    tipo: str
    estoqueAtual: float
    vmd: float
    desvioPadraoDemanda: float
    diasCobertura: float
    leadTime: int
    estoqueSeguranca: int
    rop: int
    estoqueIdeal: int
    estoqueIdealTeorico: Optional[int] = None
    qtdSugeridaCompra: int
    qtdSugeridaTeorica: int = 0
    limitadoPorEspaco: bool = False
    tetoCompraFisica: Optional[int] = None
    custoUnitario: float
    precoVenda: float
    investimentoTotalItem: float
    status: str
    statusLabel: str
    curvaAbc: str


class InventoryPredictData(BaseModel):
    kpis: InventoryKPIs
    produtos: List[InventoryProductItem]


class ResponseMeta(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    version: str = "1.0.0"
    executionTimeMs: Optional[float] = None


class InventoryPredictResponse(BaseModel):
    data: InventoryPredictData
    meta: ResponseMeta


class SupplierItem(BaseModel):
    fornecedor: str
    nome: str
    totalSkus: int


class SuppliersResponse(BaseModel):
    data: List[SupplierItem]
    meta: ResponseMeta


class InventoryConfigResponse(BaseModel):
    data: Dict[str, Any]
    meta: ResponseMeta
