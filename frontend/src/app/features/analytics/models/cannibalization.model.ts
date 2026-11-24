import { AnalyticsMeta } from './analytics.model';

export type CannibalizationWindowDays = 30 | 60 | 90;

export const CANNIBALIZATION_WINDOW_OPTIONS: readonly CannibalizationWindowDays[] = [30, 60, 90];

export type CannibalizationMechanism =
  | 'PRECO_MENOR_DESTROI_MARGEM'
  | 'PRECO_MENOR_MARGEM_PRESERVADA'
  | 'MIGRACAO_POR_VALOR';

export type CannibalizationSortKey =
  | 'reduction-desc'
  | 'reduction-asc'
  | 'lost-desc'
  | 'lost-asc'
  | 'pre-rev-desc'
  | 'pre-rev-asc'
  | 'cur-rev-desc'
  | 'cur-rev-asc'
  | 'price-desc'
  | 'price-asc'
  | 'cannibals-desc'
  | 'cannibals-asc';

export interface CannibalizationDateRange {
  startDate: string;
  endDate: string;
}

export interface CannibalizationKpis {
  totalVictims: number;
  totalCannibalizedRevenue: number;
  avgCannibalizedRevenuePct: number;
  totalNetMarginImpact: number;
  marginDestroyingPairsCount: number;
}

export interface CannibalizerSummary {
  sku: string;
  description: string;
  supplier?: string;
  migratedClients: number;
  migratedRevenue: number;
  shareOfCannibalizationPct: number;
  currentPrice: number;
  unitMargin: number;
  marginPct: number;
  costFallbackUsed: boolean;
  priceGapPct: number;
  netMarginImpact: number;
  mechanism: CannibalizationMechanism;
  suggestedVictimPrice: number | null;
  suggestedCannibalPrice: number | null;
  projectedPriceGapPct: number | null;
  actionSummary: string;
}

export interface CannibalizationVictimBase {
  sku: string;
  description: string;
  category: string;
  supplier: string;
  preRevenue: number;
  curRevenue: number;
  revenueDrop: number;
  revenueDropPct: number;
  cannibalizedRevenue: number;
  cannibalizedRevenuePct: number;
  dropExplainedPct: number;
  currentPrice: number;
  unitCost: number;
  unitMargin: number;
  marginPct: number;
  costFallbackUsed: boolean;
  currentStock: number;
  cannibalizerCount: number;
  netMarginImpact: number;
}

export interface CannibalizationVictimSummary extends CannibalizationVictimBase {
  topCannibal: CannibalizerSummary | null;
  cannibalizers: CannibalizerSummary[];
}

export interface CannibalizationReportData {
  kpis: CannibalizationKpis;
  availableCategories: string[];
  availableSuppliers: string[];
  victims: CannibalizationVictimSummary[];
}

export interface CannibalizationReportMeta extends AnalyticsMeta {
  windowDays: CannibalizationWindowDays;
  minDropPct: number;
  minMigratedClients: number;
  prePeriod: CannibalizationDateRange;
  curPeriod: CannibalizationDateRange;
  totalFound: number;
  executionTimeMs: number;
}

export interface CannibalizationReportResponse {
  data: CannibalizationReportData;
  meta: CannibalizationReportMeta;
}

export interface CannibalizerDetail extends CannibalizerSummary {
  category: string;
  supplier: string;
  grossClientsToCannibal: number;
  reverseClientsToVictim: number;
  preRevenue: number;
  curRevenue: number;
  unitCost: number;
  currentStock: number;
  victimMarginFloorPrice: number | null;
}

export interface CannibalizationDetailData {
  isCannibalized: boolean;
  victim: CannibalizationVictimBase;
  cannibalizers: CannibalizerDetail[];
}

export interface CannibalizationDetailMeta extends AnalyticsMeta {
  sku: string;
  windowDays: CannibalizationWindowDays;
  prePeriod: CannibalizationDateRange;
  curPeriod: CannibalizationDateRange;
  executionTimeMs: number;
}

export interface CannibalizationDetailResponse {
  data: CannibalizationDetailData;
  meta: CannibalizationDetailMeta;
}

export interface CannibalizationReportQueryOptions {
  windowDays?: CannibalizationWindowDays;
  minDropPct?: number;
  minMigratedClients?: number;
  category?: string | null;
  supplier?: string | null;
  mechanism?: CannibalizationMechanism | null;
  search?: string | null;
}

export interface CannibalizationDetailQueryOptions {
  windowDays?: CannibalizationWindowDays;
  minDropPct?: number;
  minMigratedClients?: number;
}

export interface FilterOptionCount {
  name: string;
  count: number;
}

export interface TopCategoryHighlight {
  name: string;
  skuCount: number;
  totalCannibalizedRevenue: number;
}
