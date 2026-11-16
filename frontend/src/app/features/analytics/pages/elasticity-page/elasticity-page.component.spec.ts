import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ActivatedRoute, ParamMap, Router, convertToParamMap } from '@angular/router';
import { BehaviorSubject, Subject, of, throwError } from 'rxjs';
import { DEFAULT_PAGE_LIMIT } from '../../models/analytics.model';
import { ProductSearchResponse } from '../../models/cross-sell.model';
import {
  CustomerElasticityResponse,
  ElasticitySimulationResponse,
  ProductElasticityResponse,
} from '../../models/elasticity.models';
import { AnalyticsService } from '../../services/analytics.service';
import { ElasticityPageComponent } from './elasticity-page.component';

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

function makeProductResponse(
  sku = 1001,
  overrides: Partial<ProductElasticityResponse['data']> = {},
  metaOverrides: Partial<ProductElasticityResponse['meta']> = {},
): ProductElasticityResponse {
  return {
    data: {
      product: {
        code: sku,
        description: sku === 1001 ? 'Chá Verde 500mg' : `Produto ${sku}`,
        supplier: 'Fitoherb',
        currentPrice: 29.9,
        costPrice: 15.0,
        stock: 250,
      },
      elasticity: {
        coefficient: -1.42,
        classification: 'ELASTICO',
        rSquared: 0.84,
        standardError: 0.19,
        confidenceInterval: [-1.8, -1.04],
        confidenceLevel: 'ALTA',
        isReliable: true,
        observationsCount: 24,
        fallbackApplied: false,
        insightMessage: 'Demanda sensível a variações de preço.',
      },
      customers: [
        {
          customerCode: 42,
          ordersCount: 12,
          totalUnits: 120,
          empiricalElasticity: -1.65,
          shrinkageElasticity: -1.5,
          classification: 'ELASTICO',
          shrinkageWeight: 0.72,
        },
        {
          customerCode: 99,
          ordersCount: 5,
          totalUnits: 45,
          empiricalElasticity: -0.55,
          shrinkageElasticity: -0.78,
          classification: 'INELASTICO',
          shrinkageWeight: 0.4,
        },
      ],
      ...overrides,
    },
    meta: {
      timestamp: '2026-04-15T12:00:00Z',
      version: '1.0.0',
      totalItems: overrides.customers ? overrides.customers.length : 2,
      totalPages: 1,
      limit: DEFAULT_PAGE_LIMIT,
      offset: 0,
      ...metaOverrides,
    },
  };
}

function makeCustomerDetailResponse(sku = 1001, customerCode = 42): CustomerElasticityResponse {
  return {
    data: {
      sku,
      customerCode,
      productElasticity: -1.42,
      customerEmpiricalElasticity: -1.65,
      customerElasticity: -1.5,
      classification: 'ELASTICO',
      shrinkageWeight: 0.72,
      ordersCount: 12,
      totalUnits: 120,
      confidenceLevel: 'ALTA',
      isReliable: true,
      insightMessage: 'Cliente mais sensível que a média do produto.',
    },
    meta: {
      timestamp: '2026-04-15T12:00:00Z',
      version: '1.0.0',
    },
  };
}

function makeSimulationResponse(
  sku = 1001,
  priceChangePct = 5,
  customerCode: number | null = null,
): ElasticitySimulationResponse {
  const projectedPrice = Number((29.9 * (1 + priceChangePct / 100)).toFixed(2));
  const isDrop = priceChangePct > 0;
  return {
    data: {
      sku,
      customerCode,
      appliedElasticity: customerCode ? -1.5 : -1.42,
      priceChangePct,
      currentPrice: 29.9,
      projectedPrice,
      currentVolume: 350,
      projectedVolume: isDrop ? 324.6 : 350,
      volumeChangePct: isDrop ? -7.26 : 0,
      currentRevenue: 10465.0,
      projectedRevenue: isDrop ? 10232.79 : 10465.0,
      revenueChangePct: isDrop ? -2.22 : 0,
      revenueChangeAbs: isDrop ? -232.21 : 0,
      currentMargin: 5215.0,
      projectedMargin: isDrop ? 5337.9 : 5215.0,
      marginChangePct: isDrop ? 2.36 : 0,
      marginChangeAbs: isDrop ? 122.9 : 0,
      recommendation:
        priceChangePct === 0
          ? 'Cenário base mantido sem alteração de preço.'
          : 'Margem sobe com leve retração de volume.',
    },
    meta: {
      timestamp: '2026-04-15T12:00:00Z',
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

describe('ElasticityPageComponent', () => {
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
      'getCustomerElasticity',
      'simulatePriceChange',
    ]);

    const emptySearch: ProductSearchResponse = {
      data: [],
      meta: {
        timestamp: '2026-04-15T12:00:00Z',
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
    analyticsSpy.getCustomerElasticity.and.callFake((sku: number, customerCode: number) =>
      of(makeCustomerDetailResponse(sku, customerCode)),
    );
    analyticsSpy.simulatePriceChange.and.callFake((req) =>
      of(makeSimulationResponse(req.sku, req.priceChangePct, req.customerCode ?? null)),
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
      createComponent();

      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Veja como o preço afeta as vendas antes de reajustar',
      );
    });

    it('foca o campo de SKU ao clicar na ação do estado inicial', () => {
      createComponent();
      const actionBtn = query<HTMLButtonElement>('app-result-state button');
      expect(actionBtn).not.toBeNull();
      actionBtn!.click();

      const input = query<HTMLInputElement>('app-code-search-form input');
      expect(document.activeElement).toBe(input);
    });

    it('hidrata e consulta automaticamente quando ?sku=1001 está presente na URL', () => {
      createComponent({ sku: '1001' });

      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 5,
      });
      const input = query<HTMLInputElement>('app-code-search-form input');
      expect(input?.value).toBe('1001');
    });

    it('rejeita ?sku= inválido na URL sem chamar a API e exibe validação inline', () => {
      createComponent({ sku: 'abc' });

      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(query('app-code-search-form .field-error')?.textContent).toContain('Escolha um produto da lista');
    });

    it('sincroniza somente ?sku= na URL após busca e jamais vaza customerCode em URL ou Storage', () => {
      createComponent();
      submitSkuInput('1001');

      expect(routerSpy.navigate).toHaveBeenCalledWith([], {
        relativeTo: jasmine.anything(),
        queryParams: { sku: '1001' },
      });

      const selectBtn = query<HTMLButtonElement>('app-elasticity-customers-table tbody button');
      selectBtn!.click();
      fixture.detectChanges();

      expect(routerSpy.navigate).toHaveBeenCalledTimes(1);
      expect(localStorage.length).toBe(0);
      expect(sessionStorage.length).toBe(0);
    });

    it('reage à navegação browser back/forward pelo queryParamMap', () => {
      createComponent({ sku: '1001' });
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });

      queryParamMap$.next(convertToParamMap({ sku: '2002' }));
      fixture.detectChanges();
      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(2002, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });

      queryParamMap$.next(convertToParamMap({}));
      fixture.detectChanges();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Veja como o preço afeta as vendas antes de reajustar',
      );
    });
  });

  describe('Validação de SKU e autocomplete por descrição', () => {
    it('valida formato antes de consultar a API e bloqueia texto não numérico', () => {
      createComponent();
      submitSkuInput('cha-invalido');

      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Escolha um produto da lista ou digite o código',
      );
    });

    it('busca produtos por descrição e carrega elasticidade ao selecionar sugestão', fakeAsync(() => {
      analyticsSpy.searchProducts.and.returnValue(
        of({
          data: [{ codigo: 1001, descricao: 'Chá Verde 500mg', fornecedor: 'Fitoherb' }],
          meta: {
            timestamp: '2026-04-15T12:00:00Z',
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

      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: 0,
      });
    }));
  });

  describe('Skeleton, sucesso pt-BR, fallback de baixa confiança e empty state', () => {
    it('exibe skeleton loader com aria-busy="true" enquanto a consulta está pendente', () => {
      const pending$ = new Subject<ProductElasticityResponse>();
      analyticsSpy.getProductElasticity.and.returnValue(pending$.asObservable());

      createComponent();
      submitSkuInput('1001');

      const skeleton = query('app-elasticity-skeleton [aria-busy="true"]');
      expect(skeleton).not.toBeNull();

      pending$.next(makeProductResponse(1001));
      pending$.complete();
      fixture.detectChanges();

      expect(query('app-elasticity-skeleton')).toBeNull();
      expect(query('app-elasticity-diagnostic-card')).not.toBeNull();
    });

    it('formata valores em pt-BR, exibe linguagem cotidiana, tradução +10%, margem unitária e deltas com sinal', () => {
      createComponent({ sku: '1001' });

      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Chá Verde 500mg');
      expect(text).toContain('R$ 29,90');
      expect(text).toContain('R$ 15,00');
      expect(text).toContain('-1,42');
      expect(text).toContain('84,0%');
      expect(text).toContain('Sensibilidade ao preço');
      expect(text).toContain('A cada +10% no preço, as vendas tendem a cair cerca de 14,2%');
      expect(text).toContain('Lucro por un.');
      expect(text).toContain('R$ 14,90');
      expect(text).toContain('Muito sensível a preço');
      expect(text).toContain('Pouco sensível');
      expect(text).toContain('Confiança alta');
      expect(text).toContain('Lucro bruto estimado');
      expect(text).toContain('R$ 31,39');
      expect(text).toContain('-R$ 232,21');
      expect(text).toContain('+R$ 122,90');
      expect(text).toContain('324,6 un.');
      expect(text).toContain('72%');
    });

    it('exibe aviso role="note" quando fallbackApplied=true ou isReliable=false', () => {
      analyticsSpy.getProductElasticity.and.returnValue(
        of(
          makeProductResponse(1001, {
            elasticity: {
              coefficient: -1.1,
              classification: 'ELASTICO',
              rSquared: 0.12,
              standardError: 0.48,
              confidenceInterval: [-2.04, -0.16],
              confidenceLevel: 'BAIXA',
              isReliable: false,
              observationsCount: 6,
              fallbackApplied: true,
              insightMessage: 'Base restrita.',
            },
          }),
        ),
      );

      createComponent({ sku: '1001' });
      const note = query('[role="note"]');
      expect(note).not.toBeNull();
      expect(normalizeText(note!.textContent)).toContain('Estimativa padrão de segurança (-1,20)');
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Confiança baixa (usar com cautela)',
      );
    });

    it('exibe aviso de baixa confiabilidade estatística quando isReliable=false e fallbackApplied=false', () => {
      analyticsSpy.getProductElasticity.and.returnValue(
        of(
          makeProductResponse(1001, {
            elasticity: {
              coefficient: -0.95,
              classification: 'INELASTICO',
              rSquared: 0.18,
              standardError: 0.45,
              confidenceInterval: [-1.83, -0.07],
              confidenceLevel: 'BAIXA',
              isReliable: false,
              observationsCount: 8,
              fallbackApplied: false,
              insightMessage: 'Amostra heterogênea.',
            },
          }),
        ),
      );

      createComponent({ sku: '1001' });
      const note = query('[role="note"]');
      expect(note).not.toBeNull();
      expect(normalizeText(note!.textContent)).toContain('Previsão com baixa precisão');
      expect(normalizeText(fixture.nativeElement.textContent)).toContain('Pouco sensível a preço');
    });

    it('exibe empty state na tabela quando o produto não possui clientes no período', () => {
      analyticsSpy.getProductElasticity.and.returnValue(
        of(makeProductResponse(1001, { customers: [] }, { totalItems: 0, totalPages: 0 })),
      );

      createComponent({ sku: '1001' });
      expect(query('app-elasticity-diagnostic-card')).not.toBeNull();
      expect(normalizeText(query('app-elasticity-customers-table')?.textContent)).toContain(
        'Nenhum cliente com compras válidas no período',
      );
    });
  });

  describe('Tratamento de erros amigável e isolamento de detalhes técnicos', () => {
    it('exibe erro amigável e campo inválido no ELA-001 e permite retry', () => {
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

      analyticsSpy.getProductElasticity.and.returnValue(of(makeProductResponse(1001)));
      const retryBtn = banner!.querySelector('button')!;
      expect(normalizeText(retryBtn.textContent)).toBe('Tentar novamente');
      retryBtn.click();
      fixture.detectChanges();

      expect(query('app-elasticity-diagnostic-card')).not.toBeNull();
    });

    it('exibe estado dedicado de dados insuficientes no ELA-003', () => {
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(422, {
            error: { code: 'ELA-003', message: 'insufficient', fields: [] },
          }),
        ),
      );

      createComponent({ sku: '1001' });
      expect(query('app-error-banner')).toBeNull();
      expect(normalizeText(fixture.nativeElement.textContent)).toContain(
        'Ainda não há histórico suficiente para este produto',
      );
    });

    it('nunca expõe detail/stacktrace em erro 500 e não fabrica código ELA-001 falso', () => {
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(500, { detail: 'Traceback Postgres secret stack' }),
        ),
      );

      createComponent({ sku: '1001' });
      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Não foi possível consultar a elasticidade agora.');
      expect(text).not.toContain('Traceback');
      expect(text).not.toContain('ELA-001');
    });

    it('isola falha do simulador preservando diagnóstico e tabela, com retry funcional', () => {
      analyticsSpy.simulatePriceChange.and.returnValue(
        throwError(() => makeHttpError(500, { detail: 'Sim engine crashed' })),
      );

      createComponent({ sku: '1001' });
      expect(query('app-elasticity-diagnostic-card')).not.toBeNull();
      expect(query('app-elasticity-customers-table')).not.toBeNull();

      const simAlert = query('app-elasticity-simulator-panel [role="alert"]');
      expect(simAlert).not.toBeNull();
      expect(normalizeText(simAlert!.textContent)).toContain('Não foi possível calcular a simulação agora.');
      expect(normalizeText(simAlert!.textContent)).not.toContain('Sim engine crashed');

      analyticsSpy.simulatePriceChange.and.returnValue(of(makeSimulationResponse(1001, 5)));
      simAlert!.querySelector('button')!.click();
      fixture.detectChanges();

      expect(query('app-elasticity-simulator-panel [role="alert"]')).toBeNull();
      expect(normalizeText(query('app-elasticity-simulator-panel')?.textContent)).toContain('R$ 31,39');
    });
  });

  describe('Simulador, presets, debounce 180ms e validação de intervalo', () => {
    it('inclui preset 0% (Atual) e dispara simulação imediata ao clicar', () => {
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const presetButtons = queryAll<HTMLButtonElement>('.btn-quick');
      const zeroBtn = presetButtons.find((btn) => normalizeText(btn.textContent) === '0% (Atual)');
      expect(zeroBtn).toBeDefined();
      zeroBtn!.click();
      fixture.detectChanges();

      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 0,
      });
    });

    it('aplica debounce de 180ms e switchMap ao arrastar o slider rapidamente, sem desabilitar o slider', fakeAsync(() => {
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const pendingSim$ = new Subject<ElasticitySimulationResponse>();
      analyticsSpy.simulatePriceChange.and.returnValue(pendingSim$.asObservable());

      const slider = query<HTMLInputElement>('#price-slider')!;
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
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledTimes(1);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 25,
      });

      // Slider nunca perde captura de ponteiro durante a requisição; botões preset ficam travados.
      expect(slider.disabled).toBeFalse();
      const firstPreset = query<HTMLButtonElement>('.btn-quick')!;
      expect(firstPreset.disabled).toBeTrue();
      expect(query('.simulation-results-grid')?.getAttribute('aria-busy')).toBe('true');

      pendingSim$.next(makeSimulationResponse(1001, 25));
      pendingSim$.complete();
      fixture.detectChanges();
      expect(firstPreset.disabled).toBeFalse();
    }));

    it('valida limites [-50, 100] no input numérico e confirma alteração válida via change', () => {
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();

      const numberInput = query<HTMLInputElement>('#price-percent-input')!;
      numberInput.value = '150';
      numberInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();

      expect(numberInput.getAttribute('aria-invalid')).toBe('true');
      expect(normalizeText(query('app-elasticity-simulator-panel [role="alert"]')?.textContent)).toContain(
        'Informe um percentual entre -50% e +100%',
      );
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();

      numberInput.value = '15';
      numberInput.dispatchEvent(new Event('input'));
      numberInput.dispatchEvent(new Event('change'));
      fixture.detectChanges();

      expect(numberInput.getAttribute('aria-invalid')).toBeNull();
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 15,
      });
    });
  });

  describe('Concorrência (switchMap), clientes, filtro, ordenação e paginação server-side', () => {
    it('descarta resposta atrasada de SKU anterior via switchMap e limpa cliente selecionado', () => {
      createComponent({ sku: '1001' });
      const selectBtn = query<HTMLButtonElement>('app-elasticity-customers-table tbody button')!;
      selectBtn.click();
      fixture.detectChanges();
      expect(normalizeText(query('app-elasticity-simulator-panel')?.textContent)).toContain('Cliente #42');

      const slow1001$ = new Subject<ProductElasticityResponse>();
      const fast2002$ = new Subject<ProductElasticityResponse>();
      analyticsSpy.getProductElasticity.and.callFake((sku: number) =>
        sku === 3003 ? slow1001$.asObservable() : fast2002$.asObservable(),
      );

      submitSkuInput('3003');
      submitSkuInput('4004');

      fast2002$.next(makeProductResponse(4004));
      fast2002$.complete();
      fixture.detectChanges();

      slow1001$.next(makeProductResponse(3003));
      slow1001$.complete();
      fixture.detectChanges();

      const text = normalizeText(fixture.nativeElement.textContent);
      expect(text).toContain('Produto 4004');
      expect(text).not.toContain('Produto 3003');
      expect(text).not.toContain('Cliente #42');
    });

    it('carrega detalhe bayesiano do cliente (getCustomerElasticity) e alterna de volta para visão geral', () => {
      createComponent({ sku: '1001' });

      const firstBtn = query<HTMLButtonElement>('app-elasticity-customers-table tbody button')!;
      firstBtn.click();
      fixture.detectChanges();

      expect(analyticsSpy.getCustomerElasticity).toHaveBeenCalledWith(1001, 42);
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: 42,
        priceChangePct: 5,
      });
      expect(firstBtn.getAttribute('aria-pressed')).toBe('true');
      expect(normalizeText(query('.customer-scope-card')?.textContent)).toContain('72%');

      const clearBtn = query<HTMLButtonElement>('.btn-clear-customer')!;
      clearBtn.click();
      fixture.detectChanges();

      expect(firstBtn.getAttribute('aria-pressed')).toBe('false');
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 5,
      });
    });

    it('descarta detalhe atrasado quando o usuário alterna clientes rapidamente', () => {
      createComponent({ sku: '1001' });

      const slow42$ = new Subject<CustomerElasticityResponse>();
      const fast99$ = new Subject<CustomerElasticityResponse>();
      analyticsSpy.getCustomerElasticity.and.callFake((_sku: number, code: number) =>
        code === 42 ? slow42$.asObservable() : fast99$.asObservable(),
      );

      const rowButtons = queryAll<HTMLButtonElement>('app-elasticity-customers-table tbody button');
      rowButtons[0].click();
      rowButtons[1].click();
      fixture.detectChanges();

      fast99$.next(makeCustomerDetailResponse(1001, 99));
      fast99$.complete();
      fixture.detectChanges();

      slow42$.next(makeCustomerDetailResponse(1001, 42));
      slow42$.complete();
      fixture.detectChanges();

      expect(normalizeText(query('.customer-scope-card')?.textContent)).toContain('Cliente #99');
    });

    it('consulta código exato de cliente na base e preserva contexto se retornar ELA-002', () => {
      createComponent({ sku: '1001' });

      analyticsSpy.getCustomerElasticity.and.returnValue(
        throwError(() =>
          makeHttpError(404, { error: { code: 'ELA-002', message: 'not found', fields: [] } }),
        ),
      );

      const lookupInput = query<HTMLInputElement>('#customer-code-filter')!;
      const lookupForm = query<HTMLFormElement>('app-elasticity-customers-table form')!;
      lookupInput.value = '8888';
      lookupInput.dispatchEvent(new Event('input'));
      fixture.detectChanges();
      lookupForm.dispatchEvent(new Event('submit'));
      fixture.detectChanges();

      expect(analyticsSpy.getCustomerElasticity).toHaveBeenCalledWith(1001, 8888);
      expect(normalizeText(query('#customer-lookup-error')?.textContent)).toContain(
        'Nenhum histórico de compras registrado para este código de cliente neste produto.',
      );

      // Agora limpa filtro e confirma restauração dos 2 itens da página
      query<HTMLButtonElement>('.clear-filter-btn')!.click();
      fixture.detectChanges();
      expect(queryAll('app-elasticity-customers-table tbody tr').length).toBe(2);
    });

    it('filtra localmente e ordena colunas atualizando aria-sort', () => {
      createComponent({ sku: '1001' });

      const ordersSortBtn = queryAll<HTMLButtonElement>('.sort-btn')[1];
      ordersSortBtn.click();
      fixture.detectChanges();

      const ordersHeader = ordersSortBtn.closest('th')!;
      expect(ordersHeader.getAttribute('aria-sort')).toBe('descending');
      expect(normalizeText(queryAll('tbody tr td.code-cell')[0].textContent)).toBe('#42');

      ordersSortBtn.click();
      fixture.detectChanges();
      expect(ordersHeader.getAttribute('aria-sort')).toBe('ascending');
      expect(normalizeText(queryAll('tbody tr td.code-cell')[0].textContent)).toBe('#99');
    });

    it('pagina no servidor via offset e mantém página anterior se próxima página falhar', () => {
      analyticsSpy.getProductElasticity.and.callFake((sku: number, page) => {
        if (page.offset === DEFAULT_PAGE_LIMIT) {
          return of(
            makeProductResponse(
              sku,
              {
                customers: [
                  {
                    customerCode: 501,
                    ordersCount: 9,
                    totalUnits: 90,
                    empiricalElasticity: -1.1,
                    shrinkageElasticity: -1.2,
                    classification: 'ELASTICO',
                    shrinkageWeight: 0.65,
                  },
                ],
              },
              { totalItems: 120, totalPages: 3, limit: DEFAULT_PAGE_LIMIT, offset: 50 },
            ),
          );
        }
        return of(
          makeProductResponse(sku, {}, { totalItems: 120, totalPages: 3, limit: DEFAULT_PAGE_LIMIT, offset: 0 }),
        );
      });

      createComponent({ sku: '1001' });
      expect(normalizeText(query('app-list-pager')?.textContent)).toContain('Página 1 de 3');

      const nextBtn = query<HTMLButtonElement>('app-list-pager button[aria-label="Próxima página"]')!;
      nextBtn.click();
      fixture.detectChanges();

      expect(analyticsSpy.getProductElasticity).toHaveBeenCalledWith(1001, {
        limit: DEFAULT_PAGE_LIMIT,
        offset: DEFAULT_PAGE_LIMIT,
      });
      expect(normalizeText(query('app-list-pager')?.textContent)).toContain('Página 2 de 3');
      expect(normalizeText(query('tbody')?.textContent)).toContain('#501');

      // Erro ao tentar ir para página 3 preserva página 2 visível e exibe retry local
      analyticsSpy.getProductElasticity.and.returnValue(
        throwError(() => makeHttpError(500, { detail: 'Timeout' })),
      );
      query<HTMLButtonElement>('app-list-pager button[aria-label="Próxima página"]')!.click();
      fixture.detectChanges();

      expect(normalizeText(query('app-list-pager')?.textContent)).toContain('Página 2 de 3');
      expect(query('app-elasticity-customers-table app-error-banner')).not.toBeNull();
    });
  });

  describe('Acessibilidade (ARIA)', () => {
    it('anuncia carregamento e simulação via aria-live="polite" e expõe atributos no slider', () => {
      createComponent({ sku: '1001' });

      const liveRegion = query<HTMLElement>('p.sr-only[role="status"][aria-live="polite"]')!;
      expect(normalizeText(liveRegion.textContent)).toContain('Simulação geral do produto');

      const slider = query<HTMLInputElement>('#price-slider')!;
      expect(slider.getAttribute('aria-valuemin')).toBe('-50');
      expect(slider.getAttribute('aria-valuemax')).toBe('100');
      expect(slider.getAttribute('aria-valuenow')).toBe('5');
      expect(slider.getAttribute('aria-valuetext')).toContain('+5,0%');

      const numberLabel = query<HTMLLabelElement>('label[for="price-percent-input"]');
      expect(numberLabel).not.toBeNull();
    });
  });

  describe('Camada didática: guia comercial na tabela e popovers <app-info-help>', () => {
    it('exibe guia comercial e cabeçalhos em linguagem cotidiana na tabela de clientes', () => {
      // Arrange & Act
      createComponent({ sku: '1001' });
      const tableSection = query('app-elasticity-customers-table');

      // Assert
      expect(tableSection).not.toBeNull();
      const tableText = normalizeText(tableSection!.textContent);
      expect(tableText).toContain('Como cada cliente reage ao preço');
      expect(tableText).toContain('Pouco sensível');
      expect(tableText).toContain('Sensível');

      const headerTexts = queryAll('app-elasticity-customers-table thead th').map((th) =>
        normalizeText(th.textContent),
      );
      expect(headerTexts.some((h) => h.includes('Peso histórico'))).toBeTrue();
      expect(headerTexts.some((h) => h.includes('Reação própria'))).toBeTrue();
      expect(headerTexts.some((h) => h.includes('Sensibilidade usada'))).toBeTrue();
      expect(headerTexts.some((h) => h.includes('Perfil'))).toBeTrue();

      // Garante presença de orientação comercial acima da tabela
      const tableEl = query('app-elasticity-customers-table table.customers-table');
      expect(tableEl).not.toBeNull();
      const textBeforeTable = normalizeText(
        tableSection!.innerHTML.split('<table')[0].replace(/<[^>]+>/g, ' '),
      );
      expect(textBeforeTable).toContain('Pouco sensível');
      expect(textBeforeTable).toContain('Sensível');
    });

    it('mantém botões <app-info-help> presentes e clicáveis sem interferir na simulação ou disparar chamadas HTTP', () => {
      // Arrange
      createComponent({ sku: '1001' });
      analyticsSpy.simulatePriceChange.calls.reset();
      analyticsSpy.getProductElasticity.calls.reset();
      analyticsSpy.getCustomerElasticity.calls.reset();

      const helpTriggers = queryAll<HTMLButtonElement>('app-info-help button[aria-label^="Ajuda sobre "]');
      expect(helpTriggers.length).toBeGreaterThanOrEqual(8);

      const simHelpTrigger = query<HTMLButtonElement>(
        'app-elasticity-simulator-panel app-info-help button[aria-label^="Ajuda sobre "]',
      )!;
      const diagHelpTrigger = query<HTMLButtonElement>(
        'app-elasticity-diagnostic-card app-info-help button[aria-label^="Ajuda sobre "]',
      )!;
      expect(simHelpTrigger).not.toBeNull();
      expect(diagHelpTrigger).not.toBeNull();

      // Act: abrir ajuda do diagnóstico e depois alternar para ajuda do simulador
      diagHelpTrigger.click();
      fixture.detectChanges();
      expect(queryAll('[role="dialog"]').length).toBe(1);
      expect(diagHelpTrigger.getAttribute('aria-expanded')).toBe('true');

      simHelpTrigger.click();
      fixture.detectChanges();

      // Assert: apenas 1 popover aberto, nenhuma chamada HTTP disparada
      expect(queryAll('[role="dialog"]').length).toBe(1);
      expect(diagHelpTrigger.getAttribute('aria-expanded')).toBe('false');
      expect(simHelpTrigger.getAttribute('aria-expanded')).toBe('true');
      expect(analyticsSpy.simulatePriceChange).not.toHaveBeenCalled();
      expect(analyticsSpy.getProductElasticity).not.toHaveBeenCalled();
      expect(analyticsSpy.getCustomerElasticity).not.toHaveBeenCalled();

      // Act: fechar por Escape e usar preset de simulação normalmente
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      fixture.detectChanges();
      expect(queryAll('[role="dialog"]').length).toBe(0);
      expect(document.activeElement).toBe(simHelpTrigger);

      const zeroBtn = queryAll<HTMLButtonElement>('.btn-quick').find(
        (btn) => normalizeText(btn.textContent) === '0% (Atual)',
      )!;
      zeroBtn.click();
      fixture.detectChanges();
      expect(analyticsSpy.simulatePriceChange).toHaveBeenCalledWith({
        sku: 1001,
        customerCode: null,
        priceChangePct: 0,
      });
    });
  });
});
