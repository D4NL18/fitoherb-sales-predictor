/**
 * Tipos de base do módulo Analytics Comercial (contrato analytics-cross-sell 1.1.0, §2 e §5; ADR-002).
 * Envelope `data`/`meta`, paginação (P-066), health do cache (P-069) e erros do contrato (§4, P-067).
 * Sem `any`: toda entrada da rede passa por type guard em `utils/analytics-error.ts`.
 */

/** `meta` presente em toda resposta 2xx. */
export interface AnalyticsMeta {
  timestamp: string;
  version: string;
  /** Último dia de pedidos considerado (YYYY-MM-DD); `null` com o cache frio. */
  dataReferencia: string | null;
}

/** `meta` das rotas de lista (P-066). */
export interface PagedMeta extends AnalyticsMeta {
  page: number;
  limit: number;
  offset: number;
  totalItems: number;
  totalPages: number;
}

/** Constantes efetivas do domínio (Q-5), para a copy não fixar números. */
export interface CrossSellParameters {
  minLift: number;
  minConfidence: number;
  minPairOrders: number;
  trivialItemSupport: number;
  dormantDays: number;
  customerProfileDays: number;
  cacheTtlHours: number;
}

/** `meta` paginado das rotas de cross-sell, com os parâmetros usados. */
export interface CrossSellPagedMeta extends PagedMeta {
  parametros: CrossSellParameters;
}

/** Página pedida ao servidor (P-066): `limit` itens a partir de `offset`. */
export interface PageRequest {
  limit: number;
  offset: number;
}

/** Tamanho de página padrão da API (P-066, D-11: sem seletor de tamanho). */
export const DEFAULT_PAGE_LIMIT = 50;

/** Estado do cache em memória do backend (P-068, Q-7). */
export type CacheState = 'FRIO' | 'CARREGANDO' | 'QUENTE' | 'EXPIRADO';

/** Contagens agregadas da última carga (sem dado de cliente). */
export interface AnalyticsCacheCounts {
  cestasValidas: number;
  regrasUteis: number;
  itensTriviais: number;
  skusComCesta: number;
}

/** `data` de `GET /analytics/health` (P-069, CA-21). */
export interface AnalyticsHealthData {
  status: 'UP';
  estadoCache: CacheState;
  cacheCarregado: boolean;
  baseSuficiente: boolean | null;
  carregadoEm: string | null;
  expiraEm: string | null;
  duracaoUltimaCargaMs: number | null;
  contagens: AnalyticsCacheCounts | null;
  parametros: CrossSellParameters;
}

export interface AnalyticsHealthResponse {
  data: AnalyticsHealthData;
  meta: AnalyticsMeta;
}

/** Códigos de erro do contrato (§4, P-067). */
export const ANALYTICS_ERROR_CODES = ['XSL-001', 'XSL-002', 'XSL-003', 'XSL-004', 'ANL-001', 'ANL-002'] as const;

export type AnalyticsErrorCode = (typeof ANALYTICS_ERROR_CODES)[number];

/** Erro do contrato já validado; `null` nos consumidores significa falha técnica genérica. */
export interface AnalyticsApiError {
  code: AnalyticsErrorCode;
  message: string;
  fields: string[];
}
