/**
 * Testes unitários para utilitários de formatação de tendência (T-16).
 */
import {
  formatComparisonHeader,
  formatPercentChange,
  formatPointsChange,
  formatValueByMetric,
  formatWindowMonthSpan,
} from './trend-format';
import { MINUS_SIGN } from './pt-br-format';

describe('trend-format utils (T-16)', () => {
  it('formata variações percentuais com sinal correto e símbolo menos U+2212', () => {
    expect(formatPercentChange(50.0)).toBe('+50,0%');
    expect(formatPercentChange(-100.0)).toBe(`${MINUS_SIGN}100,0%`);
    expect(formatPercentChange(0.0)).toBe('0,0%');
    expect(formatPercentChange(-0.04)).toBe('0,0%');
    expect(formatPercentChange(1250.5)).toBe('+1.250,5%');
    expect(formatPercentChange(null)).toBe('—');
  });

  it('formata pontos percentuais com sinal e sufixo p.p.', () => {
    expect(formatPointsChange(14.3)).toBe('+14,3 p.p.');
    expect(formatPointsChange(-20.0)).toBe(`${MINUS_SIGN}20,0 p.p.`);
    expect(formatPointsChange(0.0)).toBe('0,0 p.p.');
    expect(formatPointsChange(null)).toBe('—');
  });

  it('formata valores pela métrica', () => {
    expect(formatValueByMetric(1500.5, 'revenue')).toBe('R$ 1.500,50');
    expect(formatValueByMetric(25, 'quantity')).toBe('25 un');
    expect(formatValueByMetric(null, 'revenue')).toBe('—');
  });

  it('formata intervalos de meses com en-dash e virada de ano', () => {
    expect(
      formatWindowMonthSpan({
        inicio: '2026-10-01',
        fim: '2026-10-31',
        diasJanela: 31,
        diasCobertos: 31,
      })
    ).toBe('out/26');

    expect(
      formatWindowMonthSpan({
        inicio: '2026-08-01',
        fim: '2026-10-31',
        diasJanela: 92,
        diasCobertos: 92,
      })
    ).toBe('ago–out/26');

    expect(
      formatWindowMonthSpan({
        inicio: '2025-11-01',
        fim: '2026-10-31',
        diasJanela: 365,
        diasCobertos: 365,
      })
    ).toBe('nov/25–out/26');
  });

  it('formata cabeçalho de comparação de janelas', () => {
    const header = formatComparisonHeader({
      meses: 3,
      atual: { inicio: '2026-08-01', fim: '2026-10-31', diasJanela: 92, diasCobertos: 92 },
      anterior: { inicio: '2026-05-01', fim: '2026-07-31', diasJanela: 92, diasCobertos: 92 },
      semBase: false,
      baseParcial: false,
    });
    expect(header).toBe('ago–out/26 vs mai–jul/26');
  });
});
