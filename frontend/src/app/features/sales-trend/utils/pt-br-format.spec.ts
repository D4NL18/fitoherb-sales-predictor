/**
 * Testes unitários para utilitários de formatação pt-BR (T-16).
 */
import { formatCurrency, formatDecimal, formatIsoDate, MINUS_SIGN, roundHalfUp } from './pt-br-format';

describe('pt-br-format utils (T-16)', () => {
  it('arredonda meio para cima sobre a magnitude', () => {
    expect(roundHalfUp(12.25, 1)).toBe(12.3);
    expect(roundHalfUp(-12.25, 1)).toBe(-12.3);
    expect(roundHalfUp(12.24, 1)).toBe(12.2);
    expect(roundHalfUp(-0.04, 1)).toBe(-0.0);
  });

  it('formata números decimais com separador de milhar e decimal pt-BR', () => {
    expect(formatDecimal(1250.5, 1)).toBe('1.250,5');
    expect(formatDecimal(1000000, 0)).toBe('1.000.000');
    expect(formatDecimal(-7.25, 2)).toBe(`${MINUS_SIGN}7,25`);
    expect(formatDecimal(null)).toBe('—');
  });

  it('formata moeda em reais', () => {
    expect(formatCurrency(1250.5)).toBe('R$ 1.250,50');
    expect(formatCurrency(-7.0)).toBe(`${MINUS_SIGN}R$ 7,00`);
    expect(formatCurrency(0)).toBe('R$ 0,00');
    expect(formatCurrency(null)).toBe('—');
  });

  it('converte datas ISO em formato pt-BR DD/MM/AAAA', () => {
    expect(formatIsoDate('2026-11-09')).toBe('09/11/2026');
    expect(formatIsoDate('2025-01-01')).toBe('01/01/2025');
    expect(formatIsoDate(null)).toBe('—');
  });
});
