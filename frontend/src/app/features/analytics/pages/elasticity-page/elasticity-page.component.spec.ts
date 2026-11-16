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
): ElasticitySimulationResponse {
  const currentPrice = 30.0;
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

  function submitSkuInput(value: string): void {
    const input = query<HTMLInputElement>('app-code-search-form input');
    const form = query<HTMLFormElement>('app-code-search-form form');
    expect(input).not.toBeNull();
    expect(form).not.toBeNull();

    input!.value = value;
    input!.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    form!.dispatchEvent(new Event('submit'));
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
    analyticsSpy.getProductElasticity.and.callFake((sku: number) => of(makeProductResponse(sku)));
    analyticsSpy.simulatePriceChange.and.callFake((req) =>
      of(makeSimulationResponse(req.sku, req.priceChangePct, req.costPrice ?? null)),
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
    it('renderiza estado inicial sem chamar API automaticamente quando não há ?sku=', () => {
      // Arrange & Act
      createComponent();

      // Assert
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Veja como o preço afeta vendas, lucro e estoque antes de reajustar',
      );
    });

    it('foca o campo de SKU ao clicar na ação do estado inicial', () => {
      // Arrange
      createComponent();
      const actionBtn = query<HTMLButtonElement>('app-result-state button');
      expect(actionBtn).not.toBeNull();

      // Act
      actionBtn!.click();

      // Assert
      const input = query<HTMLInputElement>('app-code-search-form input');
      expect(document.activeElement).toBe(input);
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
      const input = query<HTMLInputElement>('app-code-search-form input');
      expect(input?.value).toBe('1001');
    });

    it('rejeita ?sku= inválido na URL sem chamar a API e exibe validação inline', () => {
      // Arrange & Act
      createComponent({ sku: 'abc' });

      // Assert
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(query('app-code-search-form .field-error')?.textContent).toContain('Escolha um produto da lista');
    });

    it('sincroniza somente ?sku= na URL após busca e não grava nada em Storage', () => {
      // Arrange
      createComponent();

      // Act
      submitSkuInput('1001');

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
        'Veja como o preço afeta vendas, lucro e estoque antes de reajustar',
      );
    });
  });

  describe('Validação de SKU e autocomplete por descrição', () => {
    it('valida formato antes de consultar a API e bloqueia texto não numérico', () => {
      // Arrange
      createComponent();

      // Act
      submitSkuInput('cha-invalido');

      // Assert
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Escolha um produto da lista ou digite o código',
      );
    });

    it('busca produtos por descrição e carrega calculadora ao selecionar sugestão', fakeAsync(() => {
      // Arrange
      analyticsSpy.searchProducts.and.returnValue(
        of({
          data: [{ codigo: 1001, descricao: 'Chá Verde 500mg', fornecedor: 'Fitoherb' }],
          meta: {
            timestamp: '2026-11-16T12:00:00Z',
            version: '1.0.0',
            dataReferencia: null,
            page: 1,
            limit: 10,
            offset: 0,
            totalItems: 1,
            totalPages: 1,
          },
        }),
      );

      createComponent();
      const input = query<HTMLInputElement>('app-code-search-form input')!;
      const form = query<HTMLFormElement>('app-code-search-form form')!;

      // Act
      input.focus();
      input.value = 'Chá';
      input.dispatchEvent(new Event('input'));
      tick(350);
      fixture.detectChanges();

      expect(analyticsSpy.searchProducts).toHaveBeenCalledWith('Chá', { limit: 20, offset: 0 });
      const option = query<HTMLElement>('[role="option"]');
      expect(option).not.toBeNull();
      option!.click();
      fixture.detectChanges();

      expect(input.value).toBe('1001');
      form.dispatchEvent(new Event('submit'));
      fixture.detectChanges();

      // Assert
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
    }));
  });

  describe('Calculadora Unificada v3 (sem diagnóstico separado nem tabela de clientes)', () => {
    it('exibe skeleton com aria-busy="true" e ao carregar renderiza apenas a Calculadora Unificada', () => {
      // Arrange
      const pending$ = new Subject<ProductElasticityResponse>();
      analyticsSpy.getProductElasticity.and.returnValue(pending$.asObservable());

      createComponent();
      submitSkuInput('1001');

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

    it('exibe cabeçalho compacto do produto, comparativo de margem unitária/total e cobertura de estoque 60d Hoje vs Proposto', () => {
      // Arrange & Act: default +5% sobre preço 30,00, custo 15,00, estoque 150, vendas 60d 180 (beta -1,5)
      // Preço proj = 31,50 | Margem unit: 15,00 (50,0%) -> 16,50 (52,4%) (+2,4 p.p.)
      // Volume: 180 -> 166,5 (-7,5%) | Cobertura 60d: Hoje ~50 dias -> Proposto ~54 dias (+4 dias vs hoje)
      createComponent({ sku: '1001' });

      const simText = normalizeText(query('app-elasticity-simulator-panel')?.textContent);

      // Assert — cabeçalho compacto
      expect(simText).toContain('SKU #1001');
      expect(simText).toContain('Chá Verde 500mg');
      expect(simText).toContain('Fitoherb');
      expect(simText).toContain('150');
      expect(simText).toContain('180');
      expect(simText).toContain('Muito sensível a preço');
      expect(simText).toContain('Confiança alta');
      expect(simText).toContain('Catálogo ERP');

      // Assert — margem unitária (R$/un., % e delta p.p.) e lucro bruto 60d
      expect(simText).toContain('Margem unitária');
      expect(simText).toContain('R$ 16,50');
      expect(simText).toContain('52,4%');
      expect(simText).toContain('+2,4 p.p.');
      expect(simText).toContain('R$ 15,00');
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
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Confiança baixa (usar com cautela)',
      );
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
      submitSkuInput('3003');
      submitSkuInput('4004');

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
