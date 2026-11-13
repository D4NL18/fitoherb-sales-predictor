import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { SeasonalityPageComponent } from './seasonality-page.component';
import {
  MonthlySeasonalityPoint,
  SeasonalityRankingResponse,
  SeasonalityResponse,
} from '../../models/seasonality.model';
import { ProductSearchResponse } from '../../models/cross-sell.model';

function createMonthlySeries(
  overrides: Partial<Record<number, Partial<MonthlySeasonalityPoint>>> = {},
): MonthlySeasonalityPoint[] {
  const monthNames = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];

  return monthNames.map((nomeMes, index) => {
    const mes = index + 1;
    const base: MonthlySeasonalityPoint = {
      mes,
      nomeMes,
      indice: mes === 6 ? 1.42 : mes === 12 ? 0.65 : 1.0,
      confianca: mes === 11 || mes === 12 ? 'BAIXA' : 'ALTA',
      observacoesDisponiveis: mes === 11 || mes === 12 ? 1 : 2,
      razao2025: 1.02,
      razao2026: mes === 11 || mes === 12 ? null : 0.98,
      volumeLiquidoHistorico: 420,
      receitaLiquidaHistorica: 11970,
    };
    return { ...base, ...(overrides[mes] ?? {}) };
  });
}

function createSeasonalityResponse(
  sku = 1042,
  descricao = 'EXTRATO DE PROPOLIS 30ML',
  overrides: Partial<SeasonalityResponse['data']> = {},
): SeasonalityResponse {
  return {
    data: {
      produto: {
        codigo: sku,
        descricao,
        fornecedor: 'APIS FLORA',
        estoque: 120,
        precoVenda: 28.5,
      },
      elegivel: true,
      forca: 'FORTE',
      motivoInsuficiencia: null,
      amplitude: 0.77,
      correlacaoYoy: 0.78,
      pico: {
        mesInicio: 5,
        mesFim: 7,
        nomePeriodo: 'Mai–Jul',
        indice: 1.42,
        confianca: 'ALTA',
      },
      vale: {
        mesInicio: 11,
        mesFim: 1,
        nomePeriodo: 'Nov–Jan',
        indice: 0.65,
        confianca: 'MEDIA',
      },
      serieMensal: createMonthlySeries({
        5: {
          indice: 1.4,
          confianca: 'ALTA',
          observacoesDisponiveis: 2,
          razao2025: 1.38,
          razao2026: 1.42,
          volumeLiquidoHistorico: 790,
          receitaLiquidaHistorica: 22515.0,
        },
      }),
      ...overrides,
    },
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
      dataReferencia: '2026-10-31',
    },
  };
}

function createRankingResponse(
  items: SeasonalityRankingResponse['data'] = [
    {
      sku: 1042,
      descricao: 'EXTRATO DE PROPOLIS 30ML',
      fornecedor: 'APIS FLORA',
      forca: 'FORTE',
      amplitude: 0.77,
      mesPico: 'Mai–Jul',
      mesVale: 'Nov–Jan',
      faturamentoTotal: 145000,
      motivoInsuficiencia: null,
    },
  ],
): SeasonalityRankingResponse {
  return {
    data: items,
    meta: {
      timestamp: '2026-11-12T12:00:00Z',
      version: '1.0.0',
      dataReferencia: '2026-10-31',
      page: 1,
      limit: 15,
      offset: 0,
      totalItems: items.length,
      totalPages: items.length > 0 ? 1 : 0,
    },
  };
}

describe('SeasonalityPageComponent', () => {
  let fixture: ComponentFixture<SeasonalityPageComponent>;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SeasonalityPageComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();

    fixture = TestBed.createComponent(SeasonalityPageComponent);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function initAndFlushRanking(
    response: SeasonalityRankingResponse = createRankingResponse(),
  ): void {
    fixture.detectChanges();
    const req = httpMock.expectOne(
      '/api/v1/analytics/seasonality/ranking?order=most&limit=15&offset=0',
    );
    req.flush(response);
    fixture.detectChanges();
  }

  it('deve carregar o ranking inicial "most" e exibir empty state amigável antes da seleção de SKU', () => {
    initAndFlushRanking();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('EXTRATO DE PROPOLIS 30ML');
    expect(text).toContain('Selecione um produto para visualizar a curva sazonal');

    const mostBtn = fixture.nativeElement.querySelector(
      '.ranking-mode-switch button:first-child',
    ) as HTMLButtonElement;
    expect(mostBtn.getAttribute('aria-pressed')).toBe('true');
  });

  it('deve renderizar correlacaoYoy como 78% sem NaN%, data de referência e aviso de baixa confiança sem ano hardcoded', () => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    input.value = '1042';
    input.dispatchEvent(new Event('input'));
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    const req = httpMock.expectOne('/api/v1/analytics/seasonality/1042');
    req.flush(createSeasonalityResponse(1042));
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const text = el.textContent ?? '';
    expect(text).toContain('78%');
    expect(text).not.toContain('NaN%');
    expect(text).toContain('Base até 31/10/2026');
    expect(text).toContain('Confiança Baixa (1 ano)');
    expect(text).not.toContain('(2025)');
    expect(text).not.toContain('P-107');

    const activeRow = el.querySelector('tbody tr.is-selected');
    expect(activeRow).toBeTruthy();
    expect(activeRow?.textContent).toContain('Em análise');
  });

  it('deve permitir inspecionar mês no gráfico exibindo volume líquido, faturamento e desafixar mês', () => {
    initAndFlushRanking();

    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    input.value = '1042';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/1042')
      .flush(createSeasonalityResponse(1042));
    fixture.detectChanges();

    const barButtons = fixture.nativeElement.querySelectorAll(
      '.chart-bar-btn',
    ) as NodeListOf<HTMLButtonElement>;
    expect(barButtons.length).toBe(12);

    // Maio é o índice 4 (5º mês)
    barButtons[4].click();
    fixture.detectChanges();

    const inspector = fixture.nativeElement.querySelector('.month-inspector') as HTMLElement;
    expect(inspector.textContent).toContain('Maio');
    expect(inspector.textContent).toContain('790 un.');
    expect(inspector.textContent).toMatch(/R\$\s*22\.515,00/);
    expect(inspector.textContent).toContain('1,38x');
    expect(inspector.textContent).toContain('1,42x');

    const unpinBtn = inspector.querySelector('.btn-unpin-month') as HTMLButtonElement;
    expect(unpinBtn).toBeTruthy();
    unpinBtn.click();
    fixture.detectChanges();

    expect(inspector.textContent).toContain('Passe o cursor, navegue com Tab ou selecione uma barra');
  });

  it('não deve marcar picos ou vales em série plana (amplitude === 0) e deve manter altura 0% para índice zero', () => {
    initAndFlushRanking();

    const flatSeries = createMonthlySeries({
      1: { indice: 1.0 },
      5: { indice: 1.0 },
      6: { indice: 1.0 },
      12: { indice: 0.0 },
    }).map((m) => (m.mes === 12 ? { ...m, indice: 0 } : { ...m, indice: 1.0 }));

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    input.value = '3001';
    input.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    fixture.detectChanges();

    httpMock.expectOne('/api/v1/analytics/seasonality/3001').flush(
      createSeasonalityResponse(3001, 'PRODUTO ESTAVEL', {
        amplitude: 0,
        forca: 'FRACA',
        pico: { mesInicio: 1, mesFim: 12, nomePeriodo: 'Jan–Dez', indice: 1.0, confianca: 'ALTA' },
        vale: { mesInicio: 1, mesFim: 12, nomePeriodo: 'Jan–Dez', indice: 1.0, confianca: 'ALTA' },
        serieMensal: flatSeries,
      }),
    );
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelectorAll('.chart-bar-btn.is-peak').length).toBe(0);
    expect(fixture.nativeElement.querySelectorAll('.chart-bar-btn.is-valley').length).toBe(0);
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Demanda uniforme ao longo dos 12 meses');
    const zeroBars = fixture.nativeElement.querySelectorAll('.bar-fill.is-zero');
    expect(zeroBars.length).toBe(1);
    expect((zeroBars[0] as HTMLElement).style.height).toBe('0%');
  });

  it('deve exibir estado INSUFICIENTE com explicação humana e sem código interno (P-107)', () => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    input.value = '5010';
    input.dispatchEvent(new Event('input'));
    (fixture.nativeElement.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
    fixture.detectChanges();

    httpMock.expectOne('/api/v1/analytics/seasonality/5010').flush(
      createSeasonalityResponse(5010, 'CHA LANCAMENTO 50G', {
        elegivel: false,
        forca: 'INSUFICIENTE',
        motivoInsuficiencia: 'VENDA_ESPORADICA',
      }),
    );
    fixture.detectChanges();

    const banner = fixture.nativeElement.querySelector('.insufficient-banner') as HTMLElement;
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain('Venda esporádica');
    expect(banner.textContent).not.toContain('P-107');
  });

  it('deve cancelar requisição de produto anterior (switchMap) em seleções rápidas', () => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;

    input.value = '1042';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    const req1 = httpMock.expectOne('/api/v1/analytics/seasonality/1042');

    input.value = '2050';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    const req2 = httpMock.expectOne('/api/v1/analytics/seasonality/2050');

    expect(req1.cancelled).toBeTrue();
    req2.flush(createSeasonalityResponse(2050, 'CHA VERDE ORGANICO'));
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('CHA VERDE ORGANICO');
  });

  it('deve tratar erro SEA-001 (404) sem botão retry e tratar 503 com "Tentar novamente" funcional', () => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;

    input.value = '9999';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/9999')
      .flush(
        { error: { code: 'SEA-001', message: 'Not found', fields: ['sku'] } },
        { status: 404, statusText: 'Not Found' },
      );
    fixture.detectChanges();

    let banner = fixture.nativeElement.querySelector('.feedback-banner') as HTMLElement;
    expect(banner).toBeTruthy();
    expect(banner.textContent).toContain('Produto não encontrado');
    expect(banner.querySelector('.btn-retry')).toBeNull();

    // Agora dispara erro recuperável 503 e testa retry
    input.value = '1042';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/1042')
      .flush(
        { error: { code: 'ANL-001', message: 'Cache frio', fields: [] } },
        { status: 503, statusText: 'Service Unavailable' },
      );
    fixture.detectChanges();

    banner = fixture.nativeElement.querySelector('.feedback-banner') as HTMLElement;
    const retryBtn = banner.querySelector('.btn-retry') as HTMLButtonElement;
    expect(retryBtn).toBeTruthy();
    expect(retryBtn.textContent?.trim()).toBe('Tentar novamente');

    retryBtn.click();
    fixture.detectChanges();
    httpMock
      .expectOne('/api/v1/analytics/seasonality/1042')
      .flush(createSeasonalityResponse(1042));
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('EXTRATO DE PROPOLIS 30ML');
  });

  it('deve validar entrada numérica inválida (decimal/zero/negativo) inline sem disparar HTTP', () => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;

    for (const invalidValue of ['1.5', '0', '-12']) {
      input.value = invalidValue;
      input.dispatchEvent(new Event('input'));
      form.dispatchEvent(new Event('submit'));
      fixture.detectChanges();

      expect(input.getAttribute('aria-invalid')).toBe('true');
      const alert = fixture.nativeElement.querySelector('#seasonality-search-error');
      expect(alert?.textContent).toContain('SKU numérico inteiro e positivo');
      httpMock.expectNone('/api/v1/analytics/seasonality/' + invalidValue);
    }
  });

  it('deve aplicar debounce, cancelar busca em voo via switchMap e navegar o combobox por teclado', fakeAsync(() => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    expect(input.getAttribute('role')).toBe('combobox');
    expect(input.getAttribute('aria-autocomplete')).toBe('list');
    expect(input.getAttribute('aria-expanded')).toBe('false');

    // Menos que 2 chars não busca
    input.value = 'p';
    input.dispatchEvent(new Event('input'));
    tick(350);
    httpMock.expectNone((r) => r.url.includes('/products/search'));

    // Busca "pr" e dispara HTTP após 300ms
    input.value = 'pr';
    input.dispatchEvent(new Event('input'));
    tick(300);
    fixture.detectChanges();

    const reqPr = httpMock.expectOne(
      '/api/v1/analytics/products/search?q=pr&limit=10&offset=0',
    );

    // Usuário digita "pro" antes de "pr" responder -> após 300ms cancela "pr"
    input.value = 'pro';
    input.dispatchEvent(new Event('input'));
    tick(300);
    fixture.detectChanges();

    expect(reqPr.cancelled).toBeTrue();

    const reqPro = httpMock.expectOne(
      '/api/v1/analytics/products/search?q=pro&limit=10&offset=0',
    );
    const searchPayload: ProductSearchResponse = {
      data: [
        { codigo: 1042, descricao: 'EXTRATO DE PROPOLIS 30ML', fornecedor: 'APIS FLORA' },
        { codigo: 1088, descricao: 'SPRAY DE PROPOLIS MEL', fornecedor: 'APIS FLORA' },
      ],
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
        page: 1,
        limit: 10,
        offset: 0,
        totalItems: 2,
        totalPages: 1,
      },
    };
    reqPro.flush(searchPayload);
    fixture.detectChanges();

    expect(input.getAttribute('aria-expanded')).toBe('true');
    expect(fixture.nativeElement.textContent).toContain('2 produtos encontrados para "pro"');

    // Navegação por teclado: ArrowDown -> 0, End -> 1, ArrowUp -> 0, Enter -> seleciona 1042
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
    fixture.detectChanges();
    expect(input.getAttribute('aria-activedescendant')).toBe('seasonality-option-0');

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'End' }));
    fixture.detectChanges();
    expect(input.getAttribute('aria-activedescendant')).toBe('seasonality-option-1');

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
    fixture.detectChanges();
    expect(input.getAttribute('aria-activedescendant')).toBe('seasonality-option-0');

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    fixture.detectChanges();

    const reqProduct = httpMock.expectOne('/api/v1/analytics/seasonality/1042');
    reqProduct.flush(createSeasonalityResponse(1042));
    fixture.detectChanges();

    expect(input.value).toBe('1042 - EXTRATO DE PROPOLIS 30ML');
    expect(input.getAttribute('aria-expanded')).toBe('false');

    // Re-submeter "1042 - EXTRATO DE PROPOLIS 30ML" pelo botão Buscar extrai 1042
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    httpMock
      .expectOne('/api/v1/analytics/seasonality/1042')
      .flush(createSeasonalityResponse(1042));
    fixture.detectChanges();
  }));

  it('deve fechar sugestões com Escape e clique fora, e anunciar lista vazia no combobox', fakeAsync(() => {
    initAndFlushRanking();

    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;

    input.value = 'inexistente';
    input.dispatchEvent(new Event('input'));
    tick(300);
    fixture.detectChanges();

    const req = httpMock.expectOne(
      '/api/v1/analytics/products/search?q=inexistente&limit=10&offset=0',
    );
    req.flush({
      data: [],
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
        page: 1,
        limit: 10,
        offset: 0,
        totalItems: 0,
        totalPages: 0,
      },
    });
    fixture.detectChanges();

    expect(input.getAttribute('aria-expanded')).toBe('true');
    expect(fixture.nativeElement.textContent).toContain('Nenhum produto encontrado para "inexistente"');

    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    fixture.detectChanges();
    expect(input.getAttribute('aria-expanded')).toBe('false');

    // Clique no botão limpar zera a busca
    const clearBtn = fixture.nativeElement.querySelector('.btn-clear') as HTMLButtonElement;
    expect(clearBtn).toBeTruthy();
    clearBtn.click();
    fixture.detectChanges();
    expect(input.value).toBe('');
  }));

  it('deve alternar ordenação do ranking com aria-pressed e ajustar colspan da tabela vazia', () => {
    initAndFlushRanking(createRankingResponse([]));

    let emptyTd = fixture.nativeElement.querySelector('.table-empty-cell') as HTMLTableCellElement;
    expect(emptyTd.getAttribute('colspan')).toBe('9');

    const leastBtn = fixture.nativeElement.querySelector(
      '.ranking-mode-switch button:last-child',
    ) as HTMLButtonElement;
    leastBtn.click();
    fixture.detectChanges();

    expect(leastBtn.getAttribute('aria-pressed')).toBe('true');

    const req = httpMock.expectOne(
      '/api/v1/analytics/seasonality/ranking?order=least&limit=15&offset=0',
    );
    req.flush(createRankingResponse([]));
    fixture.detectChanges();

    emptyTd = fixture.nativeElement.querySelector('.table-empty-cell') as HTMLTableCellElement;
    expect(emptyTd.getAttribute('colspan')).toBe('7');
  });

  it('deve exibir banner de erro no ranking com retry funcional', () => {
    fixture.detectChanges();
    httpMock
      .expectOne('/api/v1/analytics/seasonality/ranking?order=most&limit=15&offset=0')
      .flush(
        { error: { code: 'ANL-001', message: 'Cold', fields: [] } },
        { status: 503, statusText: 'Service Unavailable' },
      );
    fixture.detectChanges();

    const retryBtn = fixture.nativeElement.querySelector(
      '.rankings-section .btn-retry',
    ) as HTMLButtonElement;
    expect(retryBtn).toBeTruthy();
    retryBtn.click();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/ranking?order=most&limit=15&offset=0')
      .flush(createRankingResponse());
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('EXTRATO DE PROPOLIS 30ML');
  });
});

describe('SeasonalityPageComponent com Router (?sku=)', () => {
  let fixture: ComponentFixture<SeasonalityPageComponent>;
  let httpMock: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SeasonalityPageComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();

    router = TestBed.inject(Router);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('deve carregar produto automaticamente quando ?sku= estiver presente na URL e sincronizar nova seleção', fakeAsync(() => {
    void router.navigateByUrl('/?sku=1042');
    tick();

    fixture = TestBed.createComponent(SeasonalityPageComponent);
    fixture.detectChanges();

    const rankingReq = httpMock.expectOne(
      '/api/v1/analytics/seasonality/ranking?order=most&limit=15&offset=0',
    );
    rankingReq.flush(createRankingResponse());

    const productReq = httpMock.expectOne('/api/v1/analytics/seasonality/1042');
    productReq.flush(createSeasonalityResponse(1042));
    tick();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('SKU 1042');

    // Nova busca via formulário atualiza a query string ?sku=2050
    const input = fixture.nativeElement.querySelector(
      '#seasonality-search-input',
    ) as HTMLInputElement;
    const form = fixture.nativeElement.querySelector('form') as HTMLFormElement;
    input.value = '2050';
    input.dispatchEvent(new Event('input'));
    form.dispatchEvent(new Event('submit'));
    tick();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/2050')
      .flush(createSeasonalityResponse(2050, 'CHA VERDE 2050'));
    tick();
    fixture.detectChanges();

    expect(router.url).toContain('sku=2050');
  }));
});
