"""
Schemas Pydantic para o Módulo de Precificação (Pricing Predictor).
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PricingRequest(BaseModel):
    k_ratio: float = Field(0.25, ge=0.10, le=0.50, alias="kRatio")
    variable_k_ratio: bool = Field(True, alias="variableKRatio")
    top_anchors: int = Field(15, ge=1, le=50, alias="topAnchors")
    half_life_days: float = Field(100.0, ge=10.0, le=730.0, alias="halfLifeDays")
    anchor_min_discount: float = Field(-0.15, ge=-0.30, le=-0.01, alias="anchorMinDiscount")
    anchor_max_discount: float = Field(-0.05, ge=-0.30, le=-0.01, alias="anchorMaxDiscount")
    comp_max_increase: float = Field(0.06, ge=0.005, le=0.20, alias="compMaxIncrease")
    stress_drop: float = Field(0.05, ge=0.01, le=0.20, alias="stressDrop")

    model_config = ConfigDict(populate_by_name=True)


class ProductPreview(BaseModel):
    codigo: int
    descricao: str
    fornecedor: str
    papelEstrategico: str
    precoAtual: float
    novoPreco: float
    variacaoReais: float
    variacaoPct: float
    regraComercial: str
    travaKPercentual: Optional[float] = None


class PricingSummary(BaseModel):
    totalSkus: int
    totalOrdersAnalyzed: int
    anchorsElected: int
    compensatorsElected: int
    projectedRevenue: float
    replay2026EligibilityPct: float
    stressNetProfit: float
    marginProtected: bool
    variableKRatioApplied: bool = True
    minKRatio: Optional[float] = None
    maxKRatio: Optional[float] = None


class AutoTuneRequest(BaseModel):
    strategy: str = Field("balanced", pattern="^(balanced|profit_focused|volume_focused)$")
    population_size: int = Field(12, ge=4, le=30, alias="populationSize")
    generations: int = Field(6, ge=2, le=20, alias="generations")

    model_config = ConfigDict(populate_by_name=True)


class OptimalParams(BaseModel):
    kRatio: float
    topAnchors: int
    halfLifeDays: float
    anchorDiscount: float
    compMaxIncrease: float
    stressDrop: float


class AutoTuneData(BaseModel):
    strategy: str
    generationsRun: int
    bestFitness: float
    optimalParams: OptimalParams
    projectedMetrics: Dict[str, Any]
    fitnessHistory: List[float]


class AutoTuneResponse(BaseModel):
    data: AutoTuneData
    meta: Dict[str, Any]


class LatestPredictionState(BaseModel):
    summary: PricingSummary
    previewProducts: List[ProductPreview]
    params: Dict[str, Any]
    strategy: Optional[str] = "balanced"
    savedAt: str

