import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ActivatedRoute, ParamMap, Router, convertToParamMap } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';
import { DEFAULT_PAGE_LIMIT } from '../../models/analytics.model';
import { ProductSearchResponse } from '../../models/cross-sell.model';
import {
  ElasticitySimulationResponse,
  ProductElasticityResponse,
  SimulationImpactData,
} from '../../models/elasticity.models';
import { AnalyticsService } from '../../services/analytics.service';
import { catalogResponse } from '../../testing/cross-sell-test-data';
import { ElasticityPageComponent } from './elasticity-page.component';

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

function makeProductResponse(
  sku = 1001,
  overrides: Partial<ProductElasticityResponse['data']> = {},
  productOverrides: Partial<ProductElasticityResponse['data']['product']> = {},
): ProductElasticityResponse {
  return {
    data: {
      product: {
        code: sku,
        description: sku === 1001 ? 'Chá Verde 500mg' : `Produto ${sku}`,
        supplier: 'Fitoherb',
        currentPrice: 30.0,
        costPrice: 15.0,
        stock: 150,
        isCostEstimated: false,
        recentVolume60d: 180,
        stockTargetDays: 60,
        ...productOverrides,
      },
      elasticity: {
        coefficient: -1.5,
        classification: 'ELASTICO',
        rSquared: 0.84,
        standardError: 0.19,
        confidenceInterval: [-1.87, -1.13],
        confidenceLevel: 'ALTA',
        isReliable: true,
        observationsCount: 24,
        fallbackApplied: false,
        insightMessage: 'Demanda sensível a variações de preço.',
      },
      customers: [],
      ...overrides,
    },
    meta: {
      timestamp: '2026-11-16T12:00:00Z',
      version: '1.0.0',
      totalItems: 0,
      totalPages: 0,
      limit: DEFAULT_PAGE_LIMIT,
      offset: 0,
    },
  };
}

function makeSimulationResponse(
  sku = 1001,
  priceChangePct = 5,
  costPrice: number | null = null,
  overrides: Partial<SimulationImpactData> = {},
  currentPriceOverride: number | null = null,
): ElasticitySimulationResponse {
  const currentPrice = overrides.currentPrice ?? currentPriceOverride ?? 30.0;
  const isPriceOverride = overrides.isPriceOverride ?? currentPriceOverride !== null;
  const appliedCost = costPrice ?? 15.0;
  const isCostOverride = costPrice !== null;
  const stock = overrides.stock ?? 150;
  const currentVolume = overrides.currentVolume ?? 180;
  const appliedElasticity = overrides.appliedElasticity ?? -1.5;

  const projectedPrice = Number((currentPrice * (1 + priceChangePct / 100)).toFixed(2));
  const volumeChangePct = Number((appliedElasticity * priceChangePct).toFixed(2));
  const projectedVolume = Number(
    (currentVolume * Math.max(0, 1 + volumeChangePct / 100)).toFixed(2),
  );
  const volumeChangeUnits = Number((projectedVolume - currentVolume).toFixed(2));

  const currentUnitMargin = Number((currentPrice - appliedCost).toFixed(2));
  const projectedUnitMargin = Number((projectedPrice - appliedCost).toFixed(2));
  const currentUnitMarginPct = Number(((currentUnitMargin / currentPrice) * 100).toFixed(2));
  const projectedUnitMarginPct =
    projectedPrice > 0 ? Number(((projectedUnitMargin / projectedPrice) * 100).toFixed(2)) : 0;
  const unitMarginPctChangePp = Number((projectedUnitMarginPct - currentUnitMarginPct).toFixed(2));

  const currentRevenue = Number((currentPrice * currentVolume).toFixed(2));
  const projectedRevenue = Number((projectedPrice * projectedVolume).toFixed(2));
  const revenueChangeAbs = Number((projectedRevenue - currentRevenue).toFixed(2));
  const revenueChangePct =
    currentRevenue > 0 ? Number(((revenueChangeAbs / currentRevenue) * 100).toFixed(2)) : 0;

  const currentMargin = Number((currentUnitMargin * currentVolume).toFixed(2));
  const projectedMargin = Number((projectedUnitMargin * projectedVolume).toFixed(2));
  const marginChangeAbs = Number((projectedMargin - currentMargin).toFixed(2));
  const marginChangePct =
    Math.abs(currentMargin) > 0
      ? Number(((marginChangeAbs / Math.abs(currentMargin)) * 100).toFixed(2))
      : 0;

  const currentDailyUnits = Number((currentVolume / 60).toFixed(3));
  const projectedDailyUnits = Number((projectedVolume / 60).toFixed(3));
  const currentStockDays =
    currentDailyUnits > 0 ? Number((Math.max(0, stock) / currentDailyUnits).toFixed(1)) : null;
  const projectedStockDays =
    projectedDailyUnits > 0 ? Number((Math.max(0, stock) / projectedDailyUnits).toFixed(1)) : null;
  const stockDaysDelta =
    currentStockDays !== null && projectedStockDays !== null
      ? Number((projectedStockDays - currentStockDays).toFixed(1))
      : null;

  return {
    data: {
      sku,
      customerCode: null,
      appliedElasticity,
      priceChangePct,
      currentPrice,
      projectedPrice,
      currentVolume,
      projectedVolume,
      volumeChangePct,
      volumeChangeUnits,
      currentRevenue,
      projectedRevenue,
      revenueChangePct,
      revenueChangeAbs,
      currentMargin,
      projectedMargin,
      marginChangePct,
      marginChangeAbs,
      costPrice: appliedCost,
      isCostEstimated: false,
      isCostOverride,
      isPriceOverride,
      stock,
      stockTargetDays: 60,
      currentUnitMargin,
      projectedUnitMargin,
      currentUnitMarginPct,
      projectedUnitMarginPct,
      unitMarginPctChangePp,
      currentDailyUnits,
      projectedDailyUnits,
      currentStockDays,
      projectedStockDays,
      stockDaysDelta,
      recommendation:
        priceChangePct === 0
          ? 'Cenário neutro com estabilidade de margem financeira.'
          : marginChangeAbs > 0
            ? 'Reajuste viável com expansão de margem financeira líquida.'
            : 'Atenção: queda de volume estimada supera o ganho de preço, reduzindo a margem total.',
      ...overrides,
    },
    meta: {
      timestamp: '2026-11-16T12:00:00Z',
      version: '1.0.0',
    },
  };
}

function makeHttpError(status: number, body: unknown): HttpErrorResponse {
  return new HttpErrorResponse({
    status,
    statusText: 'Error',
    error: body,
  });
}

describe('ElasticityPageComponent (Calculadora Unificada v3)', () => {
  let fixture: ComponentFixture<ElasticityPageComponent>;
  let analyticsSpy: jasmine.SpyObj<AnalyticsService>;
  let queryParamMap$: BehaviorSubject<ParamMap>;
  let routerSpy: jasmine.SpyObj<Router>;

  function createComponent(initialParams: Record<string, string> = {}): void {
    queryParamMap$.next(convertToParamMap(initialParams));
    fixture = TestBed.createComponent(ElasticityPageComponent);
    fixture.detectChanges();
    fixture.detectChanges();
  }

  function query<T extends HTMLElement = HTMLElement>(selector: string): T | null {
    return fixture.nativeElement.querySelector(selector) as T | null;
  }

  function queryAll<T extends HTMLElement = HTMLElement>(selector: string): T[] {
    return Array.from(fixture.nativeElement.querySelectorAll(selector)) as T[];
  }

  function selectCatalogSku(sku: number): void {
    const searchInput = query<HTMLInputElement>('app-product-catalog-explorer input[type="search"]');
    expect(searchInput).not.toBeNull();
    searchInput!.value = String(sku);
    searchInput!.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const actionBtn = query<HTMLButtonElement>('app-product-catalog-explorer .btn-row-action');
    expect(actionBtn).not.toBeNull();
    actionBtn!.click();
    fixture.detectChanges();
  }

  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();

    queryParamMap$ = new BehaviorSubject<ParamMap>(convertToParamMap({}));
    routerSpy = jasmine.createSpyObj<Router>('Router', ['navigate']);
    routerSpy.navigate.and.returnValue(Promise.resolve(true));

    analyticsSpy = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', [
      'searchProducts',
      'getCatalogProducts',
      'getProductElasticity',
      'simulatePriceChange',
    ]);

    const emptySearch: ProductSearchResponse = {
      data: [],
      meta: {
        timestamp: '2026-11-16T12:00:00Z',
        version: '1.0.0',
        dataReferencia: null,
        page: 1,
        limit: 10,
        offset: 0,
        totalItems: 0,
        totalPages: 0,
      },
    };
    analyticsSpy.searchProducts.and.returnValue(of(emptySearch));
    analyticsSpy.getCatalogProducts.and.returnValue(of(catalogResponse()));
    analyticsSpy.getProductElasticity.and.callFake((sku: number) => of(makeProductResponse(sku)));
    analyticsSpy.simulatePriceChange.and.callFake((req) =>
      of(
        makeSimulationResponse(
          req.sku,
          req.priceChangePct,
          req.costPrice ?? null,
          {},
          req.currentPrice ?? null,
        ),
      ),
    );

    const routeStub = {
      get snapshot() {
        return { queryParamMap: queryParamMap$.value };
      },
      queryParamMap: queryParamMap$.asObservable(),
    };

    await TestBed.configureTestingModule({
      imports: [ElasticityPageComponent],
      providers: [
        { provide: AnalyticsService, useValue: analyticsSpy },
        { provide: ActivatedRoute, useValue: routeStub },
        { provide: Router, useValue: routerSpy },
      ],
    }).compileComponents();
  });

  describe('Estado inicial e hidratação via URL (LGPD)', () => {
    it('renderiza catálogo de produtos agrupado por fornecedor sem formulário duplicado nem chamadas de elasticidade/simulação', () => {
      // Arrange & Act
      createComponent();

      // Assert
      expect(analyticsSpy.getCatalogProducts).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      expect(query('app-code-search-form')).toBeNull();
      expect(query('app-product-catalog-explorer')).not.toBeNull();
      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Escolha um produto para simular preço');
      expect(text).toContain('WHEY 100% PURE GELATO 900G');
    });

    it('seleciona produto pela tabela do catálogo ao clicar em "Simular preço" e carrega calculadora', () => {
      // Arrange
      createComponent();
      const searchInput = query<HTMLInputElement>('app-product-catalog-explorer input[type="search"]')!;
      searchInput.value = 'whey 100% gelato';
      searchInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();

      const actionBtn = query<HTMLButtonElement>('app-product-catalog-explorer .btn-row-action');
      expect(actionBtn).not.toBeNull();
      expect(normalizeText(actionBtn!.textContent)).toBe('Simular preço');

      // Act
      actionBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(2002, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({ sku: 2002 }),
      );
      expect(routerSpy.navigate).toHaveBeenCalledWith([], {
        relativeTo: jasmine.anything(),
        queryParams: { sku: '2002' },
      });
    });

    it('volta para o catálogo ao clicar em "← Voltar para lista de produtos" nos estados loaded, insufficient-data e error', () => {
      // Arrange — estado loaded
      createComponent({ sku: '1001' });
      let backBtn = query<HTMLButtonElement>('.btn-back-catalog');
      expect(backBtn).not.toBeNull();
      expect(normalizeText(backBtn!.textContent)).toContain('← Voltar para lista de produtos');

      // Act
      backBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(query('app-product-catalog-explorer')).not.toBeNull();
      expect(routerSpy.navigate).toHaveBeenCalledWith([], {
        relativeTo: jasmine.anything(),
        queryParams: { sku: null },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });

      // Arrange — estado insufficient-data
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(422, {
            error: { code: 'ELA-003', message: 'insufficient', fields: [] },
          }),
        ),
      );
      selectCatalogSku(1001);
      backBtn = query<HTMLButtonElement>('.btn-back-catalog');
      expect(backBtn).not.toBeNull();

      // Act
      backBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(query('app-product-catalog-explorer')).not.toBeNull();

      // Arrange — estado error
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() => makeHttpError(500, { detail: 'Erro' })),
      );
      selectCatalogSku(1001);
      backBtn = query<HTMLButtonElement>('.btn-back-catalog');
      expect(backBtn).not.toBeNull();

      // Act
      backBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(query('app-product-catalog-explorer')).not.toBeNull();
    });

    it('hidrata e consulta automaticamente quando ?sku=1001 está presente na URL', () => {
      // Arrange & Act
      createComponent({ sku: '1001' });

      // Assert
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 5,
        }),
      );
      expect(query('app-elasticity-simulator-panel')).not.toBeNull();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain('SKU #1001');
    });

    it('rejeita ?sku= inválido na URL sem chamar a API e exibe validação inline', () => {
      // Arrange & Act
      createComponent({ sku: 'abc' });

      // Assert
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(query('.url-sku-error[role="alert"]')?.textContent).toContain('Escolha um produto da lista');
      expect(query('app-product-catalog-explorer')).not.toBeNull();
    });

    it('sincroniza somente ?sku= na URL após seleção na tabela e não grava nada em Storage', () => {
      // Arrange
      createComponent();

      // Act
      selectCatalogSku(1001);

      // Assert
      expect(routerSpy.navigate).toHaveBeenCalledWith([], {
        relativeTo: jasmine.anything(),
        queryParams: { sku: '1001' },
      });
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });

    it('reage à navegação browser back/forward pelo queryParamMap', () => {
      // Arrange
      createComponent({ sku: '1001' });
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });

      // Act & Assert
      queryParamMap$.next(convertToParamMap({ sku: '2002' }));
      fixture.detectChanges();
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(2002, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });

      queryParamMap$.next(convertToParamMap({}));
      fixture.detectChanges();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Escolha um produto para simular preço',
      );
    });
  });

  describe('Seleção via busca inteligente na tabela do catálogo', () => {
    it('rejeita ?sku= não positivo ou decimal na URL sem chamar a API', () => {
      for (const invalidSku of ['0', '-5', '1.5', 'cha-invalido']) {
        createComponent({ sku: invalidSku });
        expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
        expect(query('.url-sku-error[role="alert"]')).not.toBeNull();
      }
    });

    it('busca produtos por descrição no catálogo e carrega calculadora ao clicar em "Simular preço"', () => {
      // Arrange
      createComponent();
      const searchInput = query<HTMLInputElement>('app-product-catalog-explorer input[type="search"]')!;

      // Act
      searchInput.value = 'cha verde';
      searchInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();

      const actionBtn = query<HTMLButtonElement>('app-product-catalog-explorer .btn-row-action');
      expect(actionBtn).not.toBeNull();
      actionBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
      expect(query('app-elasticity-simulator-panel')).not.toBeNull();
    });
  });

  describe('Calculadora Unificada v3 (sem diagnóstico separado nem tabela de clientes)', () => {
    it('exibe skeleton com aria-busy="true" e ao carregar renderiza apenas a Calculadora Unificada', () => {
      // Arrange
      const pending$ = new Subject<ProductElasticityResponse>();
      analyticsSpy.getProductElasticity.and.returnValue(pending$.asObservable());

      createComponent();
      selectCatalogSku(1001);

      expect(query('app-elasticity-skeleton [aria-busy="true"]')).not.toBeNull();

      // Act
      pending$.next(makeProductResponse(1001));
      pending$.complete();
      fixture.detectChanges();

      // Assert: estrutura enxuta sem diagnóstico separado, sem tabela de clientes e sem bloco de comprador
      expect(query('app-elasticity-skeleton')).toBeNull();
      expect(query('app-elasticity-simulator-panel')).not.toBeNull();
      expect(query('app-elasticity-diagnostic-card')).toBeNull();
      expect(query('app-elasticity-customers-table')).toBeNull();
      expect(query('.customer-scope-card')).toBeNull();
    });

    it('exibe cabeçalho compacto do produto sem tags de sensibilidade/confiança, comparativo de margem unitária (% em destaque) e cobertura 60d', () => {
      // Arrange & Act: default +5% sobre preço 30,00, custo 15,00, estoque 150, vendas 60d 180 (beta -1,5)
      // Preço proj = 31,50 | Margem unit: 50,0% (R$ 15,00/un.) -> 52,4% (R$ 16,50/un.) (+2,4 p.p. (+R$ 1,50/un.))
      // Volume: 180 -> 166,5 (-7,5%) | Cobertura 60d: Hoje ~50 dias -> Proposto ~54 dias (+4 dias vs hoje)
      createComponent({ sku: '1001' });

      const simText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);

      // Assert — cabeçalho compacto sem .badge-elasticity/.badge-confidence e mantendo .stats-help-pill
      expect(simText).toContain('SKU #1001');
      expect(simText).toContain('Chá Verde 500mg');
      expect(simText).toContain('Fitoherb');
      expect(simText).toContain('150');
      expect(simText).toContain('180');
      expect(query('.badge-elasticity')).toBeNull();
      expect(query('.badge-confidence')).toBeNull();
      expect(simText).not.toContain('Muito sensível a preço');
      expect(simText).not.toContain('Pouco sensível a preço');
      expect(simText).not.toContain('Confiança alta');
      const statsPill = query('.stats-help-pill');
      expect(statsPill).not.toBeNull();
      expect(normalizeText(statsPill?.textContent)).toContain('Ver detalhes estatísticos');
      expect(simText).toContain('Catálogo ERP');

      // Assert — Card 1 (Margem unitária): % em .sim-main-val, R$ entre parênteses, p.p. primeiro no delta e baseline
      const unitMarginCard = query('.sim-card-unit-margin');
      expect(unitMarginCard).not.toBeNull();
      expect(normalizeText(unitMarginCard?.querySelector('.sim-main-val')?.textContent)).toBe(
        '52,4% (R$ 16,50/un.)',
      );
      expect(normalizeText(unitMarginCard?.querySelector('.sim-delta')?.textContent)).toBe(
        '+2,4 p.p. (+R$ 1,50/un.)',
      );
      expect(normalizeText(unitMarginCard?.querySelector('.sim-baseline')?.textContent)).toBe(
        'Atual: 50,0% (R$ 15,00/un.)',
      );

      // Assert — lucro bruto 60d
      expect(simText).toContain('Lucro bruto estimado');
      expect(simText).toContain('R$ 2.747,25');
      expect(simText).toContain('+R$ 47,25');

      // Assert — vendas & faturamento 60d
      expect(simText).toContain('166,5');
      expect(simText).toContain('R$ 5.244,75');

      // Assert — comparativo de cobertura de estoque (Hoje 0% vs Proposto contra meta 60d)
      expect(simText).toContain('Cobertura de estoque');
      expect(simText).toContain('Hoje (0%)');
      expect(simText).toContain('~50 dias');
      expect(simText).toContain('~54 dias');
      expect(simText).toContain('+4 dias vs hoje');
      expect(simText).toContain('Dentro da meta');
      expect(query('.stock-status-tag svg')).not.toBeNull();
    });

    it('formata Card 1 (Margem unitária) com % principal, R$/un. entre parênteses, delta p.p. primeiro e remove badges em produto inelástico', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        of(
          makeProductResponse(
            1001,
            {
              elasticity: {
                coefficient: -0.6,
                classification: 'INELASTICO',
                rSquared: 0.42,
                standardError: 0.14,
                confidenceInterval: [-0.88, -0.32],
                confidenceLevel: 'MEDIA',
                isReliable: true,
                observationsCount: 14,
                fallbackApplied: false,
                insightMessage: 'Demanda pouco sensível.',
              },
            },
            { currentPrice: 229.99, costPrice: 122.41 },
          ),
        ),
      );
      analyticsSpy.simulatePriceChange.and.returnValue(
        of(
          makeSimulationResponse(1001, 10, null, {
            currentPrice: 229.99,
            projectedPrice: 252.99,
            costPrice: 122.42,
            currentUnitMargin: 107.58,
            projectedUnitMargin: 130.57,
            currentUnitMarginPct: 46.78,
            projectedUnitMarginPct: 51.61,
            unitMarginPctChangePp: 4.83,
          }),
        ),
      );

      // Act
      createComponent({ sku: '1001' });

      // Assert — Card 1
      const unitMarginCard = query('.sim-card-unit-margin');
      expect(unitMarginCard).not.toBeNull();
      expect(normalizeText(unitMarginCard?.querySelector('.sim-main-val')?.textContent)).toBe(
        '51,6% (R$ 130,57/un.)',
      );
      expect(normalizeText(unitMarginCard?.querySelector('.sim-delta')?.textContent)).toBe(
        '+4,8 p.p. (+R$ 22,99/un.)',
      );
      expect(normalizeText(unitMarginCard?.querySelector('.sim-baseline')?.textContent)).toBe(
        'Atual: 46,8% (R$ 107,58/un.)',
      );

      // Assert — cabeçalho sem .badge-elasticity / .badge-confidence e com .stats-help-pill
      expect(query('.badge-elasticity')).toBeNull();
      expect(query('.badge-confidence')).toBeNull();
      const simText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(simText).not.toContain('Pouco sensível a preço');
      expect(simText).not.toContain('Confiança média');
      expect(normalizeText(query('.stats-help-pill')?.textContent)).toContain('Ver detalhes estatísticos');
    });

    it('exibe aviso role="note" quando fallbackApplied=true ou isReliable=false', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        of(
          makeProductResponse(1001, {
            elasticity: {
              coefficient: -1.2,
              classification: 'ELASTICO',
              rSquared: 0.12,
              standardError: 0.48,
              confidenceInterval: [-2.14, -0.26],
              confidenceLevel: 'BAIXA',
              isReliable: false,
              observationsCount: 6,
              fallbackApplied: true,
              insightMessage: 'Base restrita.',
            },
          }),
        ),
      );

      // Act
      createComponent({ sku: '1001' });

      // Assert
      const note = query('[role="note"]');
      expect(note).not.toBeNull();
      expect(normalizeText(note!.textContent)).toContain('Estimativa padrão de segurança (-1,20)');
      expect(query('.badge-elasticity')).toBeNull();
      expect(query('.badge-confidence')).toBeNull();
      expect(normalizeText(fixture.nativeElement.textContent)).not.toContain('Confiança baixa');
      expect(normalizeText(query('.stats-help-pill')?.textContent)).toContain('Ver detalhes estatísticos');
    });

    it('exibe aviso honesto e cobertura indisponível quando recentVolume60d <= 0 sem inventar giro', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        of(makeProductResponse(1001, {}, { recentVolume60d: 0, isCostEstimated: true, costPrice: 18 })),
      );
      analyticsSpy.simulatePriceChange.and.returnValue(
        of(
          makeSimulationResponse(1001, 5, null, {
            costPrice: 18,
            isCostEstimated: true,
            currentVolume: 0,
            projectedVolume: 0,
            volumeChangePct: 0,
            volumeChangeUnits: 0,
            currentRevenue: 0,
            projectedRevenue: 0,
            revenueChangeAbs: 0,
            revenueChangePct: 0,
            currentMargin: 0,
            projectedMargin: 0,
            marginChangeAbs: 0,
            marginChangePct: 0,
            currentUnitMargin: 12,
            projectedUnitMargin: 13.5,
            currentUnitMarginPct: 40,
            projectedUnitMarginPct: 42.86,
            unitMarginPctChangePp: 2.86,
            currentDailyUnits: 0,
            projectedDailyUnits: 0,
            currentStockDays: null,
            projectedStockDays: null,
            stockDaysDelta: null,
          }),
        ),
      );

      // Act
      createComponent({ sku: '1001' });

      // Assert
      const simText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(simText).toContain('Estimado (60% do preço)');
      expect(simText).toContain('Sem vendas nos últimos 60 dias');
      expect(simText).toContain('Sem giro');
      expect(simText).toContain('R$ 13,50');
      const notes = queryAll('[role="note"]').map((el) => normalizeText(el.textContent));
      expect(notes.some((n) => n.includes('60 dias'))).toBeTrue();
    });
  });

  describe('Custo unitário editável, origem, restauração e validação negativa', () => {
    it('edita custo unitário com debounce de 180ms, envia costPrice na simulação e sinaliza Editado manualmente', fakeAsync(() => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const costInput = query<HTMLInputElement>('#cost-price-input');
      expect(costInput).not.toBeNull();
      expect(costInput!.getAttribute('min')).toBe('0');
      expect(costInput!.getAttribute('step')).toBe('0.01');

      // Act: digita novo custo e aguarda 180ms
      costInput!.value = '18.5';
      costInput!.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(179);
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      tick(1);
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 5,
          costPrice: 18.5,
        }),
      );
      const simText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(simText).toContain('Editado manualmente');
      expect(simText).toContain('R$ 13,00');
    }));

    it('restaura custo original do catálogo ao clicar no botão de restauração', () => {
      // Arrange
      createComponent({ sku: '1001' });
      const costInput = query<HTMLInputElement>('#cost-price-input')!;
      costInput.value = '20';
      costInput.dispatchEvent(new Event('input'));
      costInput.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      const restoreBtn = queryAll<HTMLButtonElement>('app-elasticity-simulator-panel button').find((btn) =>
        normalizeText(btn.textContent).includes('Restaurar custo do catálogo'),
      );
      expect(restoreBtn).toBeDefined();
      analyticsSpy.simulatePriceChange.calls.reset();

      // Act
      restoreBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      const lastArg = analyticsSpy.simulatePriceChange.calls.mostRecent().args[0];
      expect(lastArg.sku).toBe(1001);
      expect(lastArg.costPrice ?? null).toBeNull();
      expect(normalizeText(query('app-elasticity-simulator-panel')?.textContent)).toContain('Catálogo ERP');
    });

    it('bloqueia custo unitário negativo com aria-invalid="true" e erro inline sem disparar HTTP', fakeAsync(() => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const costInput = query<HTMLInputElement>('#cost-price-input')!;

      // Act
      costInput.value = '-4.5';
      costInput.dispatchEvent(new Event('input'));
      costInput.dispatchEvent(new Event('change'));
      fixture.detectChanges();
      tick(250);

      // Assert
      expect(costInput.getAttribute('aria-invalid')).toBe('true');
      expect(costInput.getAttribute('aria-describedby')).toBe('cost-validation-error');
      expect(query('.cost-field-group.has-invalid')).not.toBeNull();
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      const alert = query('#cost-validation-error[role="alert"]');
      expect(alert).not.toBeNull();
      expect(normalizeText(alert!.textContent)).toContain('custo');

      // Alterar preset ou slider com custo inválido não dispara simulação com custo stale
      const zeroBtn = queryAll<HTMLButtonElement>('.btn-quick').find(
        (btn) => normalizeText(btn.textContent) === '0% (Atual)',
      )!;
      zeroBtn.click();
      fixture.detectChanges();
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      // Ao corrigir custo para valor válido, volta a simular normalmente
      costInput.value = '18.5';
      costInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(180);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({ sku: 1001, costPrice: 18.5 }),
      );
    }));
  });

  describe('Preço atual editável, origem, restauração e validação <= 0', () => {
    it('pré-preenche #current-price-input com product.currentPrice, exibe origem Catálogo ERP e envia currentPrice após debounce 180ms marcando Editado manualmente', fakeAsync(() => {
      // Arrange: custo estimado para isolar visualmente o selo "Catálogo ERP" do preço atual
      analyticsSpy.getProductElasticity.and.returnValue(
        of(makeProductResponse(1001, {}, { currentPrice: 30, costPrice: 18, isCostEstimated: true })),
      );
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const priceInput = query<HTMLInputElement>('#current-price-input');
      expect(priceInput).not.toBeNull();
      expect(Number(priceInput!.value)).toBe(30);
      expect(priceInput!.getAttribute('step')).toBe('0.01');

      const initialText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(initialText).toContain('Catálogo ERP');
      expect(initialText).not.toContain('Editado manualmente');

      // Act: edita preço atual e aguarda 180ms
      priceInput!.value = '250';
      priceInput!.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(179);
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      tick(1);
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 5,
          currentPrice: 250,
        }),
      );
      const updatedText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(updatedText).toContain('Editado manualmente');
      expect(updatedText).not.toContain('Catálogo ERP');
    }));

    it('envia currentPrice imediatamente ao pressionar Enter em #current-price-input', fakeAsync(() => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const priceInput = query<HTMLInputElement>('#current-price-input')!;

      // Act
      priceInput.value = '250';
      priceInput.dispatchEvent(new Event('input'));
      priceInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
      fixture.detectChanges();

      // Assert — disparou imediatamente sem aguardar 180ms
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 5,
          currentPrice: 250,
        }),
      );
      tick(180);
    }));

    it('restaura preço original do catálogo ao clicar em "Restaurar preço do catálogo" e limpa override', () => {
      // Arrange: custo estimado para garantir que o retorno de "Catálogo ERP" vem do preço atual
      analyticsSpy.getProductElasticity.and.returnValue(
        of(makeProductResponse(1001, {}, { currentPrice: 30, costPrice: 18, isCostEstimated: true })),
      );
      createComponent({ sku: '1001' });
      const priceInput = query<HTMLInputElement>('#current-price-input')!;
      priceInput.value = '250';
      priceInput.dispatchEvent(new Event('input'));
      priceInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
      fixture.detectChanges();

      const restoreBtn = queryAll<HTMLButtonElement>('app-elasticity-simulator-panel button').find((btn) =>
        normalizeText(btn.textContent).includes('Restaurar preço do catálogo'),
      );
      expect(restoreBtn).toBeDefined();
      analyticsSpy.simulatePriceChange.calls.reset();

      // Act
      restoreBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      const lastArg = analyticsSpy.simulatePriceChange.calls.mostRecent().args[0];
      expect(lastArg.sku).toBe(1001);
      expect(lastArg.currentPrice ?? null).toBeNull();
      expect(Number(priceInput.value)).toBe(30);

      const restoredText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);
      expect(restoredText).toContain('Catálogo ERP');
      expect(restoredText).not.toContain('Editado manualmente');
      expect(restoredText).not.toContain('Restaurar preço do catálogo');
    });

    it('valida preço atual <= 0 (0 e negativo) com aria-invalid="true", #current-price-validation-error e bloqueio cruzado de HTTP', fakeAsync(() => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const priceInput = query<HTMLInputElement>('#current-price-input')!;
      const slider = query<HTMLInputElement>('#price-slider')!;
      const costInput = query<HTMLInputElement>('#cost-price-input')!;

      for (const invalidValue of ['0', '-10']) {
        // Act — preço inválido
        priceInput.value = invalidValue;
        priceInput.dispatchEvent(new Event('input'));
        priceInput.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', bubbles: true }));
        fixture.detectChanges();
        tick(250);

        // Assert — marcado inválido e HTTP bloqueado
        expect(priceInput.getAttribute('aria-invalid')).toBe('true');
        expect(priceInput.getAttribute('aria-describedby')).toContain('current-price-validation-error');
        const alert = query('#current-price-validation-error[role="alert"]');
        expect(alert).not.toBeNull();
        expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      }

      // Assert — bloqueio cruzado ao clicar preset, mexer no slider ou editar custo
      const zeroBtn = queryAll<HTMLButtonElement>('.btn-quick').find(
        (btn) => normalizeText(btn.textContent) === '0% (Atual)',
      )!;
      zeroBtn.click();
      fixture.detectChanges();

      slider.value = '15';
      slider.dispatchEvent(new Event('input'));
      fixture.detectChanges();

      costInput.value = '18.5';
      costInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(250);

      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      // Act — ao corrigir preço atual para valor válido, volta a simular normalmente
      priceInput.value = '250';
      priceInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(180);

      // Assert
      expect(priceInput.getAttribute('aria-invalid')).toBeNull();
      expect(query('#current-price-validation-error')).toBeNull();
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({ sku: 1001, currentPrice: 250 }),
      );
    }));
  });

  describe('Tratamento de erros amigável e isolamento de detalhes técnicos', () => {
    it('exibe erro amigável no ELA-001 e permite retry', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(404, {
            error: { code: 'ELA-001', message: 'not found', fields: ['sku'] },
          }),
        ),
      );

      createComponent({ sku: '1001' });
      const banner = query('app-error-banner');
      expect(banner).not.toBeNull();
      expect(normalizeText(banner!.textContent)).toContain('ELA-001');
      expect(normalizeText(banner!.textContent)).toContain(
        'Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade.',
      );

      // Act
      analyticsSpy.getProductElasticity.and.returnValue(of(makeProductResponse(1001)));
      const retryBtn = banner!.querySelector('button')!;
      expect(normalizeText(retryBtn.textContent)).toBe('Tentar novamente');
      retryBtn.click();
      fixture.detectChanges();

      // Assert
      expect(query('app-elasticity-simulator-panel')).not.toBeNull();
    });

    it('exibe estado dedicado de dados insuficientes no ELA-003', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(422, {
            error: { code: 'ELA-003', message: 'insufficient', fields: [] },
          }),
        ),
      );

      // Act
      createComponent({ sku: '1001' });

      // Assert
      expect(query('app-error-banner')).toBeNull();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Ainda não há histórico suficiente para este produto',
      );
    });

    it('nunca expõe detail/stacktrace em erro 500 e não fabrica código ELA-001 falso', () => {
      // Arrange
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() => makeHttpError(500, { detail: 'Traceback Postgres secret stack' })),
      );

      // Act
      createComponent({ sku: '1001' });

      // Assert
      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Não foi possível consultar a elasticidade agora.');
      expect(text).not.toContain('Traceback');
      expect(text).not.toContain('ELA-001');
    });

    it('isola falha do simulador preservando cabeçalho/controles e permitindo retry', () => {
      // Arrange
      analyticsSpy.simulatePriceChange.and.returnValue(
        throwError(() => makeHttpError(500, { detail: 'Sim engine crashed' })),
      );

      createComponent({ sku: '1001' });
      expect(query('app-elasticity-simulator-panel')).not.toBeNull();

      const simAlert = query('app-elasticity-simulator-panel [role="alert"]');
      expect(simAlert).not.toBeNull();
      expect(normalizeText(simAlert!.textContent)).toContain('Não foi possível calcular a simulação agora.');
      expect(normalizeText(simAlert!.textContent)).not.toContain('Sim engine crashed');

      // Act
      analyticsSpy.simulatePriceChange.and.returnValue(of(makeSimulationResponse(1001, 5)));
      simAlert!.querySelector('button')!.click();
      fixture.detectChanges();

      // Assert
      expect(query('app-elasticity-simulator-panel [role="alert"]')).toBeNull();
      expect(normalizeText(query('app-elasticity-simulator-panel')?.textContent)).toContain('R$ 31,50');
    });
  });

  describe('Simulador, presets, debounce 180ms, switchMap e acessibilidade', () => {
    it('inclui preset 0% (Atual) e dispara simulação imediata ao clicar', () => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const zeroBtn = queryAll<HTMLButtonElement>('.btn-quick').find(
        (btn) => normalizeText(btn.textContent) === '0% (Atual)',
      );
      expect(zeroBtn).toBeDefined();

      // Act
      zeroBtn!.click();
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 0,
        }),
      );
    });

    it('aplica debounce de 180ms e switchMap ao arrastar o slider rapidamente, sem desabilitar o slider', fakeAsync(() => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const pendingSim$ = new Subject<ElasticitySimulationResponse>();
      analyticsSpy.simulatePriceChange.and.returnValue(pendingSim$.asObservable());

      const slider = query<HTMLInputElement>('#price-slider')!;

      // Act
      slider.value = '10';
      slider.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(60);

      slider.value = '25';
      slider.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      tick(179);
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      tick(1);
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 25,
        }),
      );
      expect(slider.disabled).toBeFalse();
      expect(query<HTMLButtonElement>('.btn-quick')!.disabled).toBeTrue();
      expect(query('.simulation-results-grid')?.getAttribute('aria-busy')).toBe('true');

      pendingSim$.next(makeSimulationResponse(1001, 25));
      pendingSim$.complete();
      fixture.detectChanges();
      expect(query<HTMLButtonElement>('.btn-quick')!.disabled).toBeFalse();
    }));

    it('valida limites [-50, 100] no input numérico e confirma alteração válida via change', () => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const numberInput = query<HTMLInputElement>('#price-percent-input')!;

      // Act — valor inválido
      numberInput.value = '150';
      numberInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();

      // Assert — bloqueado
      expect(numberInput.getAttribute('aria-invalid')).toBe('true');
      expect(normalizeText(query('app-elasticity-simulator-panel [role="alert"]')?.textContent)).toContain(
        'Informe um percentual entre -50% e +100%',
      );
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      // Act — valor válido
      numberInput.value = '15';
      numberInput.dispatchEvent(new Event('input'));
      numberInput.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      // Assert — liberado
      expect(numberInput.getAttribute('aria-invalid')).toBeNull();
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith(
        jasmine.objectContaining({
          sku: 1001,
          priceChangePct: 15,
        }),
      );
    });

    it('descarta resposta atrasada de SKU anterior via switchMap', () => {
      // Arrange
      createComponent({ sku: '1001' });

      const slow3003$ = new Subject<ProductElasticityResponse>();
      const fast4004$ = new Subject<ProductElasticityResponse>();
      analyticsSpy.getProductElasticity.and.callFake((sku: number) =>
        sku === 3003 ? slow3003$.asObservable() : fast4004$.asObservable(),
      );

      // Act
      queryParamMap$.next(convertToParamMap({ sku: '3003' }));
      fixture.detectChanges();
      queryParamMap$.next(convertToParamMap({ sku: '4004' }));
      fixture.detectChanges();

      fast4004$.next(makeProductResponse(4004));
      fast4004$.complete();
      fixture.detectChanges();

      slow3003$.next(makeProductResponse(3003));
      slow3003$.complete();
      fixture.detectChanges();

      // Assert
      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Produto 4004');
      expect(text).not.toContain('Produto 3003');
    });

    it('anuncia simulação via aria-live="polite" e expõe atributos ARIA no slider', () => {
      // Arrange & Act
      createComponent({ sku: '1001' });

      // Assert
      const liveRegion = query<HTMLElement>('p.sr-only[role="status"][aria-live="polite"]')!;
      expect(normalizeText(liveRegion.textContent)).toContain('+5,0%');

      const slider = query<HTMLInputElement>('#price-slider')!;
      expect(slider.getAttribute('aria-valuemin')).toBe('-50');
      expect(slider.getAttribute('aria-valuemax')).toBe('100');
      expect(slider.getAttribute('aria-valuenow')).toBe('5');
      expect(slider.getAttribute('aria-valuetext')).toContain('+5,0%');
      expect(query<HTMLLabelElement>('label[for="price-percent-input"]')).not.toBeNull();
      expect(query<HTMLLabelElement>('label[for="current-price-input"]')).not.toBeNull();
      expect(query<HTMLLabelElement>('label[for="cost-price-input"]')).not.toBeNull();
    });

    it('mantém botões <app-info-help> (incluindo dados técnicos Beta/IC 95%/R²) clicáveis sem disparar HTTP', () => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();
      analyticsSpy.getProductElasticity.calls.reset();

      const helpTriggers = queryAll<HTMLButtonElement>('app-info-help button[aria-label^="Ajuda sobre "]');
      expect(helpTriggers.length).toBeGreaterThanOrEqual(7);

      const techHelpTrigger = helpTriggers.find((btn) =>
        normalizeText(btn.getAttribute('aria-label')).toLowerCase().includes('estat') ||
        normalizeText(btn.getAttribute('aria-label')).toLowerCase().includes('técn') ||
        normalizeText(btn.getAttribute('aria-label')).toLowerCase().includes('confiança'),
      ) ?? helpTriggers[1];
      const otherHelpTrigger = helpTriggers.find((btn) => btn !== techHelpTrigger)!;

      // Act: abre popover com detalhes técnicos (Beta, IC 95%, R²)
      techHelpTrigger.click();
      fixture.detectChanges();

      // Assert
      const dialog = query('[role="dialog"]');
      expect(dialog).not.toBeNull();
      const dialogText = normalizeText(dialog!.textContent);
      expect(dialogText).toContain('-1,50');
      expect(dialogText).toContain('84,0%');
      expect(dialogText).toContain('-1,87');

      // Act: alterna para outro popover e fecha por Escape
      otherHelpTrigger.click();
      fixture.detectChanges();
      expect(queryAll('[role="dialog"]').length).toBe(1);
      expect(techHelpTrigger.getAttribute('aria-expanded')).toBe('false');
      expect(otherHelpTrigger.getAttribute('aria-expanded')).toBe('true');

      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      fixture.detectChanges();

      // Assert
      expect(queryAll('[role="dialog"]').length).toBe(0);
      expect(document.activeElement).toBe(otherHelpTrigger);
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
    });
  });
});
