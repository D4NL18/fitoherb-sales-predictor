import {
  StockCoverageStatus,
  buildProductLiveAnnouncement,
  buildSimulationLiveAnnouncement,
  computeUnitMargin,
  deltaTone,
  formatPriceReactionHint,
  formatPriceReactionRangeHint,
  formatSignedCurrency,
  formatSignedPercentValue,
  formatSignedPp,
  formatSignedStockDays,
  formatStockDays,
  formatUnits,
  getClassificationMeta,
  getStockCoverageStatus,
  sliderMarkLeftPct,
} from './elasticity-view';
import { ProductElasticityDetail, SimulationImpactData } from '../models/elasticity.models';

describe('elasticity-view', () => {
  it('formata moedas e percentuais com sinal em pt-BR sem gerar -0', () => {
    expect(formatSignedCurrency(72.59)).toMatch(/^\+R\$\s72,59$/);
    expect(formatSignedCurrency(-232.21)).toMatch(/^-R\$\s232,21$/);
    expect(formatSignedCurrency(-0.001)).toMatch(/^R\$\s0,00$/);

    expect(formatSignedPercentValue(5)).toBe('+5,0%');
    expect(formatSignedPercentValue(-7.26, 1)).toBe('-7,3%');
    expect(formatSignedPercentValue(-0.001, 1)).toBe('0,0%');

    expect(formatUnits(350)).toBe('350');
    expect(formatUnits(324.6)).toBe('324,6');
    expect(deltaTone(10)).toBe('positive');
    expect(deltaTone(-1)).toBe('negative');
    expect(deltaTone(0)).toBe('neutral');
  });

  it('posiciona corretamente o marco 0% na escala assimétrica [-50, +100]', () => {
    expect(sliderMarkLeftPct(-50)).toBe(0);
    expect(sliderMarkLeftPct(0)).toBeCloseTo(33.3333, 2);
    expect(sliderMarkLeftPct(50)).toBeCloseTo(66.6667, 2);
    expect(sliderMarkLeftPct(100)).toBe(100);
  });

  it('gera anúncios acessíveis para produto e simulação', () => {
    const detail: ProductElasticityDetail = {
      product: {
        code: 1001,
        description: 'PROPOLIS 30ML',
        supplier: 'FITOHERB',
        currentPrice: 25.5,
        costPrice: 12,
        stock: 100,
      },
      elasticity: {
        coefficient: -1.45,
        classification: 'ELASTICO',
        rSquared: 0.6,
        standardError: 0.1,
        confidenceInterval: [-1.65, -1.25],
        confidenceLevel: 'ALTA',
        isReliable: true,
        observationsCount: 14,
        fallbackApplied: false,
        insightMessage: 'Demanda elástica.',
      },
      customers: [],
    };
    const sim: SimulationImpactData = {
      sku: 1001,
      customerCode: 4501,
      appliedElasticity: -1.52,
      priceChangePct: 10,
      currentPrice: 25.5,
      projectedPrice: 28.05,
      currentVolume: 350,
      projectedVolume: 296.8,
      volumeChangePct: -15.2,
      currentRevenue: 8925,
      projectedRevenue: 8325.24,
      revenueChangePct: -6.72,
      revenueChangeAbs: -599.76,
      currentMargin: 4725,
      projectedMargin: 4763.64,
      marginChangePct: 0.82,
      marginChangeAbs: 38.64,
      recommendation: 'Viável.',
    };

    expect(buildProductLiveAnnouncement(detail)).toContain('-1,45');
    expect(buildSimulationLiveAnnouncement(sim)).toContain('cliente 4501');
    expect(buildSimulationLiveAnnouncement(sim)).toContain('+10,0%');
  });

  it('traduz coeficiente e faixa de confiança para impacto prático em +10% no preço', () => {
    // Arrange & Act & Assert
    expect(formatPriceReactionHint(-1.45)).toBe(
      'A cada +10% no preço, as vendas tendem a cair cerca de 14,5%',
    );
    expect(formatPriceReactionHint(-0.8)).toBe(
      'A cada +10% no preço, as vendas tendem a cair cerca de 8,0%',
    );
    expect(formatPriceReactionHint(0)).toBe(
      'Sem variação estimada no volume para ajustes de preço',
    );
    expect(formatPriceReactionHint(-0)).toBe(
      'Sem variação estimada no volume para ajustes de preço',
    );

    expect(formatPriceReactionRangeHint([-1.8, -1.1])).toBe(
      'Com +10% no preço, queda estimada entre 11,0% e 18,0%',
    );
    expect(formatPriceReactionRangeHint([-1.1, -1.8])).toBe(
      'Com +10% no preço, queda estimada entre 11,0% e 18,0%',
    );
    expect(formatPriceReactionRangeHint([-2.04, -0.16])).toBe(
      'Com +10% no preço, queda estimada entre 1,6% e 20,4%',
    );
    expect(formatPriceReactionRangeHint([Number.NaN, -1.2])).toBe(
      'Sem variação estimada no volume para ajustes de preço',
    );
    expect(formatPriceReactionRangeHint([-1.8, Number.POSITIVE_INFINITY])).toBe(
      'Sem variação estimada no volume para ajustes de preço',
    );
  });

  it('calcula margem unitária e trata preço atual zero ou custo superior ao preço', () => {
    // Arrange & Act
    const positive = computeUnitMargin(25.5, 12);
    const exact = computeUnitMargin(20, 12);
    const negative = computeUnitMargin(10, 15);
    const zeroPrice = computeUnitMargin(0, 12);

    // Assert
    expect(positive.amount).toBeCloseTo(13.5, 2);
    expect(positive.marginPct).toBeCloseTo(52.941, 2);

    expect(exact).toEqual({ amount: 8, marginPct: 40 });
    expect(negative).toEqual({ amount: -5, marginPct: -50 });

    expect(zeroPrice.amount).toBe(-12);
    expect(Number.isFinite(zeroPrice.marginPct)).toBeTrue();
    expect(zeroPrice.marginPct).toBe(0);
  });

  it('retorna rótulos em linguagem cotidiana para classificação', () => {
    // Arrange & Act
    const elastic = getClassificationMeta('ELASTICO');
    const inelastic = getClassificationMeta('INELASTICO');

    // Assert
    expect(elastic.label).toBe('Muito sensível a preço');
    expect(elastic.shortLabel).toBe('Sensível');

    expect(inelastic.label).toBe('Pouco sensível a preço');
    expect(inelastic.shortLabel).toBe('Pouco sensível');
  });

  it('classifica cobertura de estoque para meta de 60 dias e extremos sem estoque ou sem giro', () => {
    // Arrange
    const expectedStatuses: StockCoverageStatus[] = [
      'empty',
      'no-sales',
      'critical-fast',
      'healthy',
      'excess',
    ];

    // Act
    const empty = getStockCoverageStatus(0, 0, 2.5);
    const negativeStock = getStockCoverageStatus(null, -10, 1.5);
    const noSales = getStockCoverageStatus(null, 120, 0);
    const fast = getStockCoverageStatus(15, 30, 2);
    const healthy = getStockCoverageStatus(45, 90, 2);
    const atTarget = getStockCoverageStatus(60, 120, 2);
    const excess = getStockCoverageStatus(75, 150, 2);
    const customTargetExcess = getStockCoverageStatus(40, 80, 2, 30);

    // Assert
    expect([empty.status, noSales.status, fast.status, healthy.status, excess.status]).toEqual(
      expectedStatuses,
    );
    expect(negativeStock.status).toBe('empty');
    expect(empty.tagClass).toBe('tag-critical');
    expect(noSales.tagClass).toBe('tag-neutral');
    expect(fast.tagClass).toBe('tag-warning');
    expect(fast.label).toBe('Giro rápido ≤ 15d');
    expect(healthy.tagClass).toBe('tag-positive');
    expect(atTarget.status).toBe('healthy');
    expect(excess.tagClass).toBe('tag-info');
    expect(customTargetExcess.status).toBe('excess');
    expect(healthy.label.length).toBeGreaterThan(0);
  });

  it('formata variação em pontos percentuais (p.p.) com sinal em pt-BR sem gerar -0', () => {
    // Arrange & Act & Assert
    expect(formatSignedPp(4.8)).toBe('+4,8 p.p.');
    expect(formatSignedPp(-2.14)).toBe('-2,1 p.p.');
    expect(formatSignedPp(0)).toBe('0,0 p.p.');
    expect(formatSignedPp(-0.001)).toBe('0,0 p.p.');
  });

  it('formata dias de cobertura de estoque e variação comparativa vs hoje', () => {
    // Arrange & Act & Assert
    expect(formatStockDays(47.2)).toBe('~47 dias');
    expect(formatStockDays(1)).toBe('~1 dia');
    expect(formatStockDays(null)).toBe('Sem giro');

    expect(formatSignedStockDays(36)).toBe('+36 dias vs hoje');
    expect(formatSignedStockDays(-14)).toBe('-14 dias vs hoje');
    expect(formatSignedStockDays(0)).toMatch(/^0 dias? vs hoje$/);
    expect(['', '—']).toContain(formatSignedStockDays(null));
  });
});
