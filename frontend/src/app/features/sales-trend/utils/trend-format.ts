/**
 * Utilitários de formatação textual e símbolos para células e cabeçalhos de Tendência.
 * Usa U+2212 para sinal de menos, U+2013 para traço de intervalo, e regras de P-077.
 */
import { TrendMetric, TrendWindowMeta, TrendWindowSpan } from '../models/sales-trend.model';
import { formatCurrency, formatDecimal, MINUS_SIGN, roundHalfUp } from './pt-br-format';

export const EN_DASH = '\u2013'; // Meia-risca U+2013

const SHORT_MONTH_NAMES = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
];

/**
 * Formata variação percentual com sinal explícito (+ ou U+2212) e 1 casa decimal.
 * Valores que arredondam para 0.0 perdem o sinal (P-077.5).
 */
export function formatPercentChange(pct: number | null | undefined): string {
  if (pct === null || pct === undefined || !Number.isFinite(pct)) {
    return '—';
  }

  const rounded = roundHalfUp(pct, 1);
  if (Math.abs(rounded) === 0) {
    return '0,0%';
  }

  const formattedAbs = formatDecimal(Math.abs(rounded), 1);
  if (rounded > 0) {
    return `+${formattedAbs}%`;
  }
  return `${MINUS_SIGN}${formattedAbs}%`;
}

/**
 * Formata contribuição em pontos percentuais (+14,3 p.p. / −5,0 p.p.).
 */
export function formatPointsChange(pp: number | null | undefined): string {
  if (pp === null || pp === undefined || !Number.isFinite(pp)) {
    return '—';
  }

  const rounded = roundHalfUp(pp, 1);
  if (Math.abs(rounded) === 0) {
    return '0,0 p.p.';
  }

  const formattedAbs = formatDecimal(Math.abs(rounded), 1);
  if (rounded > 0) {
    return `+${formattedAbs} p.p.`;
  }
  return `${MINUS_SIGN}${formattedAbs} p.p.`;
}

/**
 * Formata valores brutos na unidade da métrica escolhida.
 */
export function formatValueByMetric(
  val: number | null | undefined,
  metric: TrendMetric,
  decimals?: number
): string {
  if (val === null || val === undefined || !Number.isFinite(val)) {
    return '—';
  }

  if (metric === 'revenue') {
    return formatCurrency(val);
  }

  const d = typeof decimals === 'number' ? decimals : Number.isInteger(val) ? 0 : 1;
  return `${formatDecimal(val, d)} un`;
}

/**
 * Converte um TrendWindowSpan (datas ISO) em texto resumido de meses (ex: "ago–out/26" ou "out/26").
 */
export function formatWindowMonthSpan(span: TrendWindowSpan): string {
  if (!span || !span.inicio || !span.fim) {
    return '—';
  }

  const [y1, m1] = span.inicio.split('-').map((s) => parseInt(s, 10));
  const [y2, m2] = span.fim.split('-').map((s) => parseInt(s, 10));

  const name1 = SHORT_MONTH_NAMES[m1 - 1] || '';
  const name2 = SHORT_MONTH_NAMES[m2 - 1] || '';
  const year2Short = (y2 % 100).toString().padStart(2, '0');

  if (y1 === y2 && m1 === m2) {
    return `${name1}/${year2Short}`;
  }

  if (y1 === y2) {
    return `${name1}${EN_DASH}${name2}/${year2Short}`;
  }

  const year1Short = (y1 % 100).toString().padStart(2, '0');
  return `${name1}/${year1Short}${EN_DASH}${name2}/${year2Short}`;
}

/**
 * Monta o cabeçalho descritivo da janela de comparação (ex: "ago–out/26 vs mai–jul/26").
 */
export function formatComparisonHeader(windowMeta: TrendWindowMeta): string {
  if (!windowMeta || !windowMeta.atual || !windowMeta.anterior) {
    return `${windowMeta?.meses ?? ''} meses`;
  }
  const current = formatWindowMonthSpan(windowMeta.atual);
  const previous = formatWindowMonthSpan(windowMeta.anterior);
  return `${current} vs ${previous}`;
}
