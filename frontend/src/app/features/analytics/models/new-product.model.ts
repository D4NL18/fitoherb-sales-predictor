/**
 * Tipos do subdomínio Viabilidade de Produto Novo (F2, P-139 a P-149).
 * Alinhados 1:1 ao contrato `.agents/docs/api_contracts/analytics-produto-novo.md` (zero `any`).
 */
import { AnalyticsMeta } from './analytics.model';

export type SeasonalityConfidence = 'ALTA' | 'MEDIA' | 'BAIXA' | 'INSUFICIENTE' | 'PADRAO';

export type SeasonalityStatus = 'APPLIED' | 'FALLBACK_NEUTRAL' | 'UNAVAILABLE';

export interface NewProductOptions {
  tipos: string[];
  fornecedores: string[];
}

export interface NewProductForecastRequest {
  tipo: string;
  fornecedor: string;
  descricao: string;
  precoVendaPrevisto: number;
  custoUnitario?: number | null;
  margemMinimaDesejada?: number | null;
  horizonMonths?: number;
}

export interface MonthlyForecastItem {
  month: number;
  calendarMonth?: number;
  quantity: number;
  revenue: number;
  grossMargin: number | null;
  p10Quantity: number;
  conservativeQuantity: number;
  p50Quantity: number;
  similarP25Quantity: number;
  seasonalityFactor: number;
  seasonalityConfidence?: SeasonalityConfidence;
}

export interface AggregatedTotals {
  totalQuantity: number;
  totalRevenue: number;
  totalGrossMargin: number | null;
  averageMonthlyQuantity: number;
  averageMonthlyRevenue: number;
}

export interface FinancialViability {
  precoVenda: number;
  custoUnitario: number | null;
  margemBrutaUnitaria: number | null;
  margemBrutaPercentual: number | null;
  margemMinimaDesejada: number | null;
  viavel: boolean | null;
  parecer: string | null;
}

export interface MarketCeiling {
  tetoMaduroP75: number;
  descricao: string;
}

export interface SimilarProductItem {
  sku: string;
  descricao: string;
  fornecedor: string;
  primeiraVenda: string;
  precoHistorico: number;
  scoreFinal: number;
  scoreFornecedor: number;
  scorePreco: number;
  scoreTfidf: number;
  quantidadesPrimeirosMeses: number[];
}

export interface NewProductForecastData {
  inputSummary: NewProductForecastRequest;
  monthlyForecast: MonthlyForecastItem[];
  seasonalityStatus?: SeasonalityStatus;
  aggregatedTotals: AggregatedTotals;
  financialViability: FinancialViability;
  marketCeiling: MarketCeiling;
  similarsUsed: SimilarProductItem[];
  methodologyNotice: string;
}

export interface NewProductOptionsResponse {
  data: NewProductOptions;
  meta: AnalyticsMeta;
}

export interface NewProductForecastResponse {
  data: NewProductForecastData;
  meta: AnalyticsMeta;
}

/** Códigos de erro do subdomínio Produto Novo (contrato §2). */
export const NEW_PRODUCT_ERROR_CODES = [
  'NEW-001',
  'NEW-002',
  'NEW-003',
  'NEW-004',
  'NEW-005',
  'ANL-001',
  'ANL-002',
] as const;

export type NewProductErrorCode = (typeof NEW_PRODUCT_ERROR_CODES)[number];

export interface NewProductApiError {
  code: NewProductErrorCode;
  message: string;
  fields: string[];
}
