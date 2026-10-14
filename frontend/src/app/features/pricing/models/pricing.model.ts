export interface PricingParams {
  kRatio: number;
  variableKRatio?: boolean;
  topAnchors: number;
  halfLifeDays: number;
  anchorMinDiscount: number;
  anchorMaxDiscount: number;
  compMaxIncrease: number;
  stressDrop: number;
  autonomousSkuPricing?: boolean;
}

export interface PricingSummary {
  totalSkus: number;
  totalOrdersAnalyzed: number;
  anchorsElected: number;
  compensatorsElected: number;
  projectedRevenue: number;
  replay2026EligibilityPct: number;
  stressNetProfit: number;
  marginProtected: boolean;
  variableKRatioApplied?: boolean;
  minKRatio?: number;
  maxKRatio?: number;
  autonomousSkuPricingApplied?: boolean;
  avgAnchorDiscountPct?: number;
  minAnchorDiscountPct?: number;
  maxAnchorDiscountPct?: number;
  avgCompIncreasePct?: number;
  avgStressDropPct?: number;
}

export interface ProductPreview {
  codigo: number;
  descricao: string;
  fornecedor: string;
  papelEstrategico: string;
  precoAtual: number;
  novoPreco: number;
  variacaoReais: number;
  variacaoPct: number;
  regraComercial: string;
  travaKPercentual?: number | null;
  elasticidade?: number | null;
  quedaVolumeEstressePct?: number | null;
}

export interface PredictResponse {
  data: {
    summary: PricingSummary;
    previewProducts: ProductPreview[];
  };
  meta: {
    timestamp: string;
  };
}

export interface ConfigResponse {
  data: Record<string, {
    default: number;
    min: number;
    max: number;
    step: number;
    label: string;
  }>;
  meta: {
    timestamp: string;
  };
}

export interface CachedPredictionState {
  summary: PricingSummary;
  previewProducts: ProductPreview[];
  params: PricingParams;
  strategy: 'balanced' | 'profit_focused' | 'volume_focused';
  savedAt: string;
}

export interface AutoTuneRequest {
  strategy?: 'balanced' | 'profit_focused' | 'volume_focused';
  populationSize?: number;
  generations?: number;
}

export interface AutoTuneData {
  strategy: string;
  generationsRun: number;
  bestFitness: number;
  optimalParams: {
    kRatio: number;
    topAnchors: number;
    halfLifeDays: number;
    anchorDiscount: number;
    compMaxIncrease: number;
    stressDrop: number;
  };
  projectedMetrics: PricingSummary;
}

export interface AutoTuneResponse {
  data: AutoTuneData;
  meta: {
    timestamp: string;
    version?: string;
  };
}

