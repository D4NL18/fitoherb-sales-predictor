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

const CLASSIFICATION_META: Record<ElasticityClassification, ElasticityTagMeta> = {
  ELASTICO: {
    label: 'Demanda elástica',
    shortLabel: 'Elástico',
    tagClass: 'tag-warning',
    icon: 'elastic',
  },
  INELASTICO: {
    label: 'Demanda inelástica',
    shortLabel: 'Inelástico',
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
    label: 'Confiança baixa',
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

export function buildElasticityInitialState(): ResultStateView {
  return {
    icon: 'chart',
    title: 'Analise a sensibilidade de preço por produto',
    text: 'Digite o código ou parte da descrição de um produto para estimar a elasticidade da demanda, comparar clientes e simular cenários de reajuste.',
    actionLabel: 'Ir para o campo',
    action: 'focus-field',
    tone: 'neutral',
  };
}

export function buildElasticityInsufficientDataState(): ResultStateView {
  return {
    icon: 'chart',
    title: 'Histórico insuficiente para estimar elasticidade',
    text: 'Este produto ainda não reúne meses ou volume líquido positivo suficientes para calcular a sensibilidade de preço.',
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
  return `Elasticidade carregada para ${detail.product.description}: ${cls}, coeficiente ${coef}, ${formatDecimal(totalClients)} clientes na base.`;
}

export function buildSimulationLiveAnnouncement(sim: SimulationImpactData): string {
  const scope = sim.customerCode ? `para o cliente ${sim.customerCode}` : 'geral do produto';
  return `Simulação ${scope} com reajuste de ${formatSignedPercentValue(sim.priceChangePct, 1)}: preço ${formatCurrency(sim.projectedPrice)}, volume ${formatUnits(sim.projectedVolume)} unidades, faturamento ${formatCurrency(sim.projectedRevenue)} e margem ${formatCurrency(sim.projectedMargin)}.`;
}

function normalizeZero(value: number): number {
  return Object.is(value, -0) || value === 0 ? 0 : value;
}
