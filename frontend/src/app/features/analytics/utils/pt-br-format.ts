/**
 * Formatação pt-BR do módulo Analytics (Design Plan §7.8; contrato §2.4).
 * Arredonda "meio para cima" sobre a representação decimal (1,15 -> 1,2; 0,345 -> 35%), igual ao backend (P-065),
 * para que chips e textos nunca divirjam das frases prontas. Sem depender do `LOCALE_ID` do Angular.
 */
const LOCALE = 'pt-BR';
const CURRENCY = 'BRL';
const CURRENCY_DIGITS = 2;
const PERCENT_SHIFT = 2;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})/;

/** Arredonda meio para cima deslocando o expoente em texto (evita o erro binário de `x * 10^n`). */
export function roundHalfUp(value: number, fractionDigits: number): number {
  const shifted = Number(`${value}e${fractionDigits}`);
  if (!Number.isFinite(shifted)) return value;
  return Number(`${Math.round(shifted)}e-${fractionDigits}`);
}

/** Número com vírgula decimal e ponto de milhar ("1.234", "4,25"). */
export function formatDecimal(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(roundHalfUp(value, fractionDigits));
}

/** Razão 0..1 como percentual ("34%", "1,7%"). */
export function formatPercent(ratio: number, fractionDigits = 0): string {
  const percent = Number(`${ratio}e${PERCENT_SHIFT}`);
  return `${formatDecimal(percent, fractionDigits)}%`;
}

/** Valor em reais ("R$ 30,00"). */
export function formatCurrency(value: number): string {
  return new Intl.NumberFormat(LOCALE, { style: 'currency', currency: CURRENCY }).format(
    roundHalfUp(value, CURRENCY_DIGITS),
  );
}

/** Data ISO (YYYY-MM-DD) como dd/MM/yyyy, sem conversão de fuso. */
export function formatIsoDate(isoDate: string): string {
  const match = ISO_DATE_PATTERN.exec(isoDate);
  if (!match) return isoDate;
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

const POSITION_MIN_DIGITS = 2;
const TYPOGRAPHIC_MINUS = '\u2212';

/** Posição na lista completa com dois dígitos ("01", "12", "150"), Design Plan §5.6. */
export function formatPosition(position: number): string {
  return String(position).padStart(POSITION_MIN_DIGITS, '0');
}

function resolveSignPrefix(value: number): string {
  if (value > 0) return '+';
  if (value < 0) return TYPOGRAPHIC_MINUS;
  return '';
}

/** Número decimal com sinal explícito (`+` ou `−` tipográfico). */
export function formatSignedDecimal(value: number, fractionDigits = 2): string {
  const rounded = roundHalfUp(value, fractionDigits);
  const sign = resolveSignPrefix(rounded);
  return `${sign}${formatDecimal(Math.abs(rounded), fractionDigits)}`;
}

/** Valor em reais com sinal explícito (`+R$ 3.235,63` ou `−R$ 1.381,05`). */
export function formatSignedCurrency(value: number): string {
  const rounded = roundHalfUp(value, CURRENCY_DIGITS);
  const sign = resolveSignPrefix(rounded);
  return `${sign}${formatCurrency(Math.abs(rounded))}`;
}

/**
 * Percentual com sinal explícito:
 * - `'points'`: valor já vem em pontos percentuais (ex.: `-49.31` -> `−49,31%`).
 * - `'ratio'`: valor vem como fração `0..1` (ex.: `0.42` -> `+42,00%`).
 */
export function formatSignedPercent(
  value: number,
  scale: 'points' | 'ratio' = 'points',
  fractionDigits = 2,
): string {
  const percentPoints = scale === 'ratio' ? Number(`${value}e${PERCENT_SHIFT}`) : value;
  return `${formatSignedDecimal(percentPoints, fractionDigits)}%`;
}
