/**
 * Tipos e interfaces TypeScript da API de Sazonalidade por Produto (contrato 1.0.0; P-106 a P-116).
 * Sem uso de `any`.
 */
import { AnalyticsMeta, PagedMeta } from './analytics.model';

export type SeasonalityStrength = 'FORTE' | 'MODERADA' | 'FRACA' | 'INSUFICIENTE';
export type SeasonalityConfidence = 'ALTA' | 'MEDIA' | 'BAIXA';
export type SeasonalityOrder = 'most' | 'least';
export type SeasonalityReason = 'HISTORICO_CURTO' | 'VENDA_ESPORADICA' | null;

export interface SeasonalityProduct {
  codigo: number;
  descricao: string;
  fornecedor: string;
  estoque: number;
  precoVenda: number;
}

export interface SeasonalityPeakValley {
  mesInicio: number;
  mesFim: number;
  nomePeriodo: string;
  indice: number;
  confianca: SeasonalityConfidence;
}

export interface MonthlySeasonalityPoint {
  mes: number;
  nomeMes: string;
  indice: number;
  confianca: SeasonalityConfidence;
  observacoesDisponiveis: number;
  razao2025: number | null;
  razao2026: number | null;
  volumeLiquidoHistorico: number;
  receitaLiquidaHistorica: number;
}

export interface SeasonalityData {
  produto: SeasonalityProduct;
  elegivel: boolean;
  forca: SeasonalityStrength;
  motivoInsuficiencia: SeasonalityReason;
  amplitude: number;
  correlacaoYoy: number | null;
  pico: SeasonalityPeakValley;
  vale: SeasonalityPeakValley;
  serieMensal: MonthlySeasonalityPoint[];
}

export interface SeasonalityResponse {
  data: SeasonalityData;
  meta: AnalyticsMeta;
}

export interface SeasonalityRankingItem {
  sku: number;
  descricao: string;
  fornecedor: string;
  forca: SeasonalityStrength;
  amplitude: number;
  mesPico: string;
  mesVale: string;
  faturamentoTotal: number;
  motivoInsuficiencia: SeasonalityReason;
}

export interface SeasonalityRankingResponse {
  data: SeasonalityRankingItem[];
  meta: PagedMeta;
}

/** Códigos de erro do contrato de sazonalidade (P-116) e infraestrutura do módulo Analytics. */
export const SEASONALITY_ERROR_CODES = ['SEA-001', 'SEA-002', 'SEA-003', 'ANL-001', 'ANL-002'] as const;
export type SeasonalityErrorCode = (typeof SEASONALITY_ERROR_CODES)[number];

export interface SeasonalityApiError {
  code: SeasonalityErrorCode;
  message: string;
  fields: string[];
}
