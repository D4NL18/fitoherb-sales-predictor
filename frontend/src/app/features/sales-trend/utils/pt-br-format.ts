/**
 * Funções puras de formatação numérica e de data no padrão brasileiro pt-BR.
 * Não utiliza bibliotecas externas pesadas; garante arredondamento meio para cima exato.
 */

export const MINUS_SIGN = '\u2212'; // Símbolo matemático de menos U+2212

/**
 * Arredonda um número meio para cima sobre a magnitude (Half Up).
 */
export function roundHalfUp(val: number, decimals = 1): number {
  if (!Number.isFinite(val)) {
    return 0;
  }
  const factor = Math.pow(10, decimals);
  const sign = val < 0 ? -1 : 1;
  const abs = Math.abs(val);
  return (sign * Math.round(abs * factor * (1 + Number.EPSILON))) / factor;
}

/**
 * Formata um número decimal com separador de milhar '.' e decimal ','.
 */
export function formatDecimal(val: number | null | undefined, decimals = 0): string {
  if (val === null || val === undefined || !Number.isFinite(val)) {
    return '—';
  }

  const rounded = decimals > 0 ? roundHalfUp(val, decimals) : Math.round(val);
  const isNegative = rounded < 0;
  const absVal = Math.abs(rounded);

  const parts = absVal.toFixed(decimals).split('.');
  const intPart = Intl.NumberFormat('pt-BR', {
    useGrouping: true,
    maximumFractionDigits: 0,
  }).format(Number(parts[0]));
  const decPart = parts.length > 1 ? `,${parts[1]}` : '';

  const prefix = isNegative ? MINUS_SIGN : '';
  return `${prefix}${intPart}${decPart}`;
}

/**
 * Formata um valor monetário em Reais (R$ 1.250,00).
 */
export function formatCurrency(val: number | null | undefined): string {
  if (val === null || val === undefined || !Number.isFinite(val)) {
    return '—';
  }

  const rounded = roundHalfUp(val, 2);
  const isNegative = rounded < 0;
  const absVal = Math.abs(rounded);

  const formattedAbs = formatDecimal(absVal, 2);
  if (isNegative) {
    return `${MINUS_SIGN}R$ ${formattedAbs}`;
  }
  return `R$ ${formattedAbs}`;
}

/**
 * Converte data ISO AAAA-MM-DD para formato pt-BR DD/MM/AAAA.
 */
export function formatIsoDate(isoDate: string | null | undefined): string {
  if (!isoDate || typeof isoDate !== 'string') {
    return '—';
  }
  const parts = isoDate.split('-');
  if (parts.length !== 3) {
    return isoDate;
  }
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}
