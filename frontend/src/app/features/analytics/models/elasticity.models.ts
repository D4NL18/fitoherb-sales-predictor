/**
 * Tipos e Interfaces da funcionalidade Elasticidade-Preço (F5 / P-095..P-105).
 * Alinhado estritamente com o contrato REST (api_contracts/analytics-elasticidade.md).
 */

export type ElasticityClassification = 'ELASTICO' | 'INELASTICO';
export type ElasticityConfidenceLevel = 'ALTA' | 'MEDIA' | 'BAIXA';

export interface ProductHeader {
  code: number;
  description: string;
  supplier: string;
  currentPrice: number;
  costPrice: number;
  stock: number;
  isCostEstimated?: boolean;
  recentVolume60d?: number;
  stockTargetDays?: number;
}

export interface ProductElasticityMetrics {
  coefficient: number;
  classification: ElasticityClassification;
  rSquared: number;
  standardError: number;
  confidenceInterval: [number, number];
  confidenceLevel: ElasticityConfidenceLevel;
  isReliable: boolean;
  observationsCount: number;
  fallbackApplied: boolean;
  insightMessage: string;
}

export interface CustomerElasticityItem {
  customerCode: number;
  ordersCount: number;
  totalUnits: number;
  empiricalElasticity: number;
  shrinkageElasticity: number;
  classification: ElasticityClassification;
  shrinkageWeight: number;
}

export interface ProductElasticityDetail {
  product: ProductHeader;
  elasticity: ProductElasticityMetrics;
  customers: CustomerElasticityItem[];
}

export interface ResponseMeta {
  timestamp: string;
  version: string;
  totalItems?: number;
  totalPages?: number;
  limit?: number;
  offset?: number;
}

export interface ProductElasticityResponse {
  data: ProductElasticityDetail;
  meta: ResponseMeta;
}

export interface CustomerElasticityDetail {
  sku: number;
  customerCode: number;
  productElasticity: number;
  customerEmpiricalElasticity: number;
  customerElasticity: number;
  classification: ElasticityClassification;
  shrinkageWeight: number;
  ordersCount: number;
  totalUnits: number;
  confidenceLevel: ElasticityConfidenceLevel;
  isReliable: boolean;
  insightMessage: string;
}

export interface CustomerElasticityResponse {
  data: CustomerElasticityDetail;
  meta: ResponseMeta;
}

export interface ElasticitySimulationRequest {
  sku: number;
  customerCode?: number | null;
  priceChangePct: number;
  costPrice?: number | null;
}

export interface SimulationImpactData {
  sku: number;
  customerCode?: number | null;
  appliedElasticity: number;
  priceChangePct: number;
  currentPrice: number;
  projectedPrice: number;
  currentVolume: number;
  projectedVolume: number;
  volumeChangePct: number;
  currentRevenue: number;
  projectedRevenue: number;
  revenueChangePct: number;
  revenueChangeAbs: number;
  currentMargin: number;
  projectedMargin: number;
  marginChangePct: number;
  marginChangeAbs: number;
  recommendation: string;
  costPrice?: number;
  isCostEstimated?: boolean;
  isCostOverride?: boolean;
  stock?: number;
  stockTargetDays?: number;
  currentUnitMargin?: number;
  projectedUnitMargin?: number;
  currentUnitMarginPct?: number;
  projectedUnitMarginPct?: number;
  unitMarginPctChangePp?: number;
  volumeChangeUnits?: number;
  currentDailyUnits?: number;
  projectedDailyUnits?: number;
  currentStockDays?: number | null;
  projectedStockDays?: number | null;
  stockDaysDelta?: number | null;
}

export interface ElasticitySimulationResponse {
  data: SimulationImpactData;
  meta: ResponseMeta;
}
