/**
 * Derivação pura de apresentação, formatação pt-BR e estados da aba Elasticidade-Preço (F5 / P-095..P-105).
 * Sem dependência de DOM ou serviços: facilita testes unitários rápidos e mantém componentes enxutos.
 */
import {
  CustomerElasticityItem,
  ElasticityClassification,
  ElasticityConfidenceLevel,
  ProductElasticityDetail,
  SimulationImpactData,
} from '../models/elasticity.models';
import { ResultStateView } from './cross-sell-view';
import { formatCurrency, formatDecimal, roundHalfUp } from './pt-br-format';

export const PRICE_CHANGE_MIN = -50;
export const PRICE_CHANGE_MAX = 100;
export const PRICE_CHANGE_DEFAULT = 5;
export const PRICE_PRESETS: readonly number[] = [-10, -5, 0, 5, 10, 20];

export type DeltaTone = 'positive' | 'negative' | 'neutral';
export type CustomerSortKey = 'customerCode' | 'ordersCount' | 'totalUnits' | 'shrinkageElasticity';
export type SortDirection = 'asc' | 'desc';

export interface ElasticityTagMeta {
  label: string;
  shortLabel: string;
  tagClass: string;
  icon: 'elastic' | 'inelastic' | 'high' | 'medium' | 'low';
}

export interface UnitMarginSummary {
  amount: number;
  marginPct: number;
}

const CLASSIFICATION_META: Record<ElasticityClassification, ElasticityTagMeta> = {
  ELASTICO: {
    label: 'Muito sensível a preço',
    shortLabel: 'Sensível',
    tagClass: 'tag-warning',
    icon: 'elastic',
  },
  INELASTICO: {
    label: 'Pouco sensível a preço',
    shortLabel: 'Pouco sensível',
    tagClass: 'tag-positive',
    icon: 'inelastic',
  },
};

const CONFIDENCE_META: Record<ElasticityConfidenceLevel, ElasticityTagMeta> = {
  ALTA: {
    label: 'Confiança alta',
    shortLabel: 'Alta',
    tagClass: 'tag-positive',
    icon: 'high',
  },
  MEDIA: {
    label: 'Confiança média',
    shortLabel: 'Média',
    tagClass: 'tag-info',
    icon: 'medium',
  },
  BAIXA: {
    label: 'Confiança baixa (usar com cautela)',
    shortLabel: 'Baixa',
    tagClass: 'tag-neutral',
    icon: 'low',
  },
};

export function getClassificationMeta(classification: ElasticityClassification): ElasticityTagMeta {
  return CLASSIFICATION_META[classification];
}

export function getConfidenceMeta(level: ElasticityConfidenceLevel): ElasticityTagMeta {
  return CONFIDENCE_META[level];
}

/** Formata valor monetário em BRL com sinal explícito (`+R$ 72,59`, `-R$ 232,21`, `R$ 0,00`). */
export function formatSignedCurrency(value: number): string {
  const rounded = normalizeZero(roundHalfUp(value, 2));
  if (rounded > 0) return `+${formatCurrency(rounded)}`;
  return formatCurrency(rounded);
}

/** Formata percentual já em escala 0..100 com sinal explícito (`+5,0%`, `-7,3%`, `0,0%`). */
export function formatSignedPercentValue(value: number, fractionDigits = 1): string {
  const rounded = normalizeZero(roundHalfUp(value, fractionDigits));
  const formatted = formatDecimal(rounded, fractionDigits);
  return rounded > 0 ? `+${formatted}%` : `${formatted}%`;
}

/** Formata unidades evitando `.0` desnecessário, mas preservando frações (`350`, `324,6`). */
export function formatUnits(value: number): string {
  const rounded = normalizeZero(roundHalfUp(value, 1));
  return Number.isInteger(rounded) ? formatDecimal(rounded, 0) : formatDecimal(rounded, 1);
}

export function deltaTone(value: number): DeltaTone {
  const rounded = normalizeZero(roundHalfUp(value, 2));
  if (rounded > 0) return 'positive';
  if (rounded < 0) return 'negative';
  return 'neutral';
}

/** Traduz o coeficiente de elasticidade para o impacto prático de +10% no preço. */
export function formatPriceReactionHint(coefficient: number): string {
  if (!Number.isFinite(coefficient)) {
    return 'Sem variação estimada no volume para ajustes de preço';
  }
  const deltaPct = normalizeZero(roundHalfUp(Math.abs(coefficient) * 10, 1));
  if (deltaPct === 0) {
    return 'Sem variação estimada no volume para ajustes de preço';
  }
  const direction = coefficient < 0 ? 'cair' : 'subir';
  return `A cada +10% no preço, as vendas tendem a ${direction} cerca de ${formatDecimal(deltaPct, 1)}%`;
}

/** Traduz o intervalo de confiança (IC 95%) para faixa de impacto prático com +10% no preço. */
export function formatPriceReactionRangeHint(interval: readonly [number, number]): string {
  if (!Number.isFinite(interval[0]) || !Number.isFinite(interval[1])) {
    return 'Sem variação estimada no volume para ajustes de preço';
  }
  const first = normalizeZero(roundHalfUp(Math.abs(interval[0]) * 10, 1));
  const second = normalizeZero(roundHalfUp(Math.abs(interval[1]) * 10, 1));
  const low = Math.min(first, second);
  const high = Math.max(first, second);
  if (low === 0 && high === 0) {
    return 'Sem variação estimada no volume para ajustes de preço';
  }
  if (interval[0] <= 0 && interval[1] <= 0) {
    return `Com +10% no preço, queda estimada entre ${formatDecimal(low, 1)}% e ${formatDecimal(high, 1)}%`;
  }
  return `Com +10% no preço, variação estimada entre ${formatDecimal(low, 1)}% e ${formatDecimal(high, 1)}%`;
}

/** Calcula lucro unitário em reais e percentual sobre o preço atual, com guarda para preço <= 0. */
export function computeUnitMargin(currentPrice: number, costPrice: number): UnitMarginSummary {
  const amount = normalizeZero(currentPrice - costPrice);
  if (!Number.isFinite(currentPrice) || currentPrice <= 0) {
    return { amount, marginPct: 0 };
  }
  const marginPct = normalizeZero((amount / currentPrice) * 100);
  return { amount, marginPct };
}

export function buildElasticityInitialState(): ResultStateView {
  return {
    icon: 'chart',
    title: 'Veja como o preço afeta as vendas antes de reajustar',
    text: '1. Veja a sensibilidade do produto · 2. Teste cenários de aumento ou desconto · 3. Compare como cada cliente reage ao preço.',
    actionLabel: 'Escolher um produto',
    action: 'focus-field',
    tone: 'neutral',
  };
}

export function buildElasticityInsufficientDataState(): ResultStateView {
  return {
    icon: 'chart',
    title: 'Ainda não há histórico suficiente para este produto',
    text: 'Para estimar com segurança como os compradores reagem ao preço, este produto precisa reunir mais meses com vendas regulares líquidas de devoluções.',
    actionLabel: 'Buscar outro produto',
    action: 'new-search',
    tone: 'warning',
  };
}

export function buildElasticityEmptyCustomersState(): ResultStateView {
  return {
    icon: 'box',
    title: 'Nenhum cliente com compras válidas no período',
    text: 'Este produto não tem clientes individuais listados no histórico avaliado. A simulação geral do produto continua disponível acima.',
    actionLabel: 'Buscar outro produto',
    action: 'new-search',
    tone: 'neutral',
  };
}

export function filterAndSortCustomers(
  customers: readonly CustomerElasticityItem[],
  filterQuery: string,
  sortKey: CustomerSortKey | null,
  sortDir: SortDirection,
): CustomerElasticityItem[] {
  const term = filterQuery.trim();
  const filtered = term
    ? customers.filter((c) => String(c.customerCode).includes(term))
    : [...customers];

  if (sortKey === null) return filtered;

  const multiplier = sortDir === 'asc' ? 1 : -1;
  return [...filtered].sort((a, b) => (a[sortKey] - b[sortKey]) * multiplier);
}

export function sliderMarkLeftPct(value: number): number {
  const clamped = Math.min(Math.max(value, PRICE_CHANGE_MIN), PRICE_CHANGE_MAX);
  return ((clamped - PRICE_CHANGE_MIN) / (PRICE_CHANGE_MAX - PRICE_CHANGE_MIN)) * 100;
}

export function buildProductLiveAnnouncement(detail: ProductElasticityDetail, totalClients: number): string {
  const cls = getClassificationMeta(detail.elasticity.classification).label;
  const coef = formatDecimal(detail.elasticity.coefficient, 2);
  return `Análise carregada para ${detail.product.description}: ${cls}, sensibilidade ${coef}, ${formatDecimal(totalClients)} clientes na base.`;
}

export function buildSimulationLiveAnnouncement(sim: SimulationImpactData): string {
  const scope = sim.customerCode ? `para o cliente ${sim.customerCode}` : 'geral do produto';
  return `Simulação ${scope} com reajuste de ${formatSignedPercentValue(sim.priceChangePct, 1)}: preço ${formatCurrency(sim.projectedPrice)}, volume ${formatUnits(sim.projectedVolume)} unidades, faturamento ${formatCurrency(sim.projectedRevenue)} e margem ${formatCurrency(sim.projectedMargin)}.`;
}

function normalizeZero(value: number): number {
  return Object.is(value, -0) || value === 0 ? 0 : value;
}
