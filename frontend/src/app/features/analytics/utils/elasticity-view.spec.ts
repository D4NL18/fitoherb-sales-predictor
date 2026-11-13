import {
  buildProductLiveAnnouncement,
  buildSimulationLiveAnnouncement,
  deltaTone,
  filterAndSortCustomers,
  formatSignedCurrency,
  formatSignedPercentValue,
  formatUnits,
  sliderMarkLeftPct,
} from './elasticity-view';
import { CustomerElasticityItem, ProductElasticityDetail, SimulationImpactData } from '../models/elasticity.models';

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

  it('filtra e ordena clientes sem mutar a lista original', () => {
    const items: CustomerElasticityItem[] = [
      {
        customerCode: 4502,
        ordersCount: 5,
        totalUnits: 120,
        empiricalElasticity: -1.1,
        shrinkageElasticity: -1.15,
        classification: 'ELASTICO',
        shrinkageWeight: 0.33,
      },
      {
        customerCode: 4501,
        ordersCount: 18,
        totalUnits: 480,
        empiricalElasticity: -0.8,
        shrinkageElasticity: -0.9,
        classification: 'INELASTICO',
        shrinkageWeight: 0.64,
      },
    ];

    expect(filterAndSortCustomers(items, '501', null, 'desc').map((c) => c.customerCode)).toEqual([4501]);
    expect(filterAndSortCustomers(items, '', 'ordersCount', 'asc').map((c) => c.customerCode)).toEqual([4502, 4501]);
    expect(filterAndSortCustomers(items, '', 'ordersCount', 'desc').map((c) => c.customerCode)).toEqual([4501, 4502]);
    expect(items.map((c) => c.customerCode)).toEqual([4502, 4501]);
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

    expect(buildProductLiveAnnouncement(detail, 12)).toContain('-1,45');
    expect(buildSimulationLiveAnnouncement(sim)).toContain('cliente 4501');
    expect(buildSimulationLiveAnnouncement(sim)).toContain('+10,0%');
  });
});
