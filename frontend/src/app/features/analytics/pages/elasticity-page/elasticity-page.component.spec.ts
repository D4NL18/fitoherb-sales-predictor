import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ElasticityPageComponent } from './elasticity-page.component';
import { AnalyticsService } from '../../services/analytics.service';
import {
  ElasticitySimulationResponse,
  ProductElasticityResponse,
} from '../../models/elasticity.models';

describe('ElasticityPageComponent', () => {
  let component: ElasticityPageComponent;
  let fixture: ComponentFixture<ElasticityPageComponent>;
  let mockAnalyticsService: jasmine.SpyObj<AnalyticsService>;

  const fakeProductResp: ProductElasticityResponse = {
    data: {
      product: {
        code: 1001,
        description: 'EXTRATO DE PROPOLIS VERDE 30ML',
        supplier: 'FITOHERB LAB',
        currentPrice: 25.5,
        costPrice: 12.0,
        stock: 420,
      },
      elasticity: {
        coefficient: -1.45,
        classification: 'ELASTICO',
        rSquared: 0.58,
        standardError: 0.18,
        confidenceInterval: [-1.8, -1.1],
        confidenceLevel: 'ALTA',
        isReliable: true,
        observationsCount: 18,
        fallbackApplied: false,
        insightMessage: 'Demanda elástica.',
      },
      customers: [
        {
          customerCode: 4501,
          ordersCount: 12,
          totalUnits: 350,
          empiricalElasticity: -1.6,
          shrinkageElasticity: -1.52,
          classification: 'ELASTICO',
          shrinkageWeight: 0.55,
        },
      ],
    },
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
      totalItems: 1,
      totalPages: 1,
      limit: 50,
      offset: 0,
    },
  };

  const fakeSimulationResp: ElasticitySimulationResponse = {
    data: {
      sku: 1001,
      customerCode: null,
      appliedElasticity: -1.45,
      priceChangePct: 5.0,
      currentPrice: 25.5,
      projectedPrice: 26.78,
      currentVolume: 350,
      projectedVolume: 324.6,
      volumeChangePct: -7.25,
      currentRevenue: 8925.0,
      projectedRevenue: 8692.79,
      revenueChangePct: -2.6,
      revenueChangeAbs: -232.21,
      currentMargin: 4725.0,
      projectedMargin: 4797.59,
      marginChangePct: 1.54,
      marginChangeAbs: 72.59,
      recommendation: 'Reajuste viável com aumento de margem monetária.',
    },
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
    },
  };

  beforeEach(async () => {
    mockAnalyticsService = jasmine.createSpyObj('AnalyticsService', [
      'getProductElasticity',
      'simulatePriceChange',
    ]);
    mockAnalyticsService.getProductElasticity.and.returnValue(of(fakeProductResp));
    mockAnalyticsService.simulatePriceChange.and.returnValue(of(fakeSimulationResp));

    await TestBed.configureTestingModule({
      imports: [ElasticityPageComponent],
      providers: [{ provide: AnalyticsService, useValue: mockAnalyticsService }],
    }).compileComponents();

    fixture = TestBed.createComponent(ElasticityPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('deve inicializar e carregar os dados de elasticidade do produto', () => {
    expect(component).toBeTruthy();
    expect(mockAnalyticsService.getProductElasticity).toHaveBeenCalledWith(1001, { limit: 50, offset: 0 });
    expect(component['productData']()?.product.code).toBe(1001);
    expect(component['status']()).toBe('success');
  });

  it('deve exibir as métricas de elasticidade e o badge de classificação', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.product-description')?.textContent).toContain('EXTRATO DE PROPOLIS VERDE');
    expect(compiled.querySelector('.badge-elasticity')?.textContent).toContain('Demanda Elástica');
    expect(compiled.querySelector('.badge-confidence')?.textContent).toContain('Confiança ALTA');
  });

  it('deve renderizar a tabela de clientes com customerCode sem expor PII', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const customerPill = compiled.querySelector('.customer-code-pill');
    expect(customerPill?.textContent).toContain('#4501');
  });

  it('deve executar a simulação e exibir os valores projetados de volume, receita e margem', () => {
    component.setPriceQuickAdjust(10);
    expect(mockAnalyticsService.simulatePriceChange).toHaveBeenCalled();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.simulation-recommendation-bar')?.textContent).toContain('Reajuste viável');
  });

  it('deve tratar erros de API e renderizar banner de erro com código', () => {
    mockAnalyticsService.getProductElasticity.and.returnValue(
      throwError(() => ({
        error: {
          error: { code: 'ELA-001', message: 'Produto não encontrado.' },
        },
      }))
    );

    component['searchSku'].set('999999');
    component.loadProductElasticity();
    fixture.detectChanges();

    expect(component['status']()).toBe('error');
    expect(component['errorCode']()).toBe('ELA-001');
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.error-banner')).toBeTruthy();
  });
});
