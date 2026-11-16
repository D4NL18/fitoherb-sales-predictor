import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { SeasonalityPageComponent } from './seasonality-page.component';
import {
  MonthlySeasonalityPoint,
  SeasonalityResponse,
} from '../../models/seasonality.model';
import { CatalogListResponse } from '../../models/cross-sell.model';
import { catalogResponse } from '../../testing/cross-sell-test-data';

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

function createSeasonalCatalogResponse(): CatalogListResponse {
  return catalogResponse([
    {
      codigo: 1042,
      descricao: 'EXTRATO DE PRÓPOLIS 30ML',
      fornecedor: 'APIS FLORA',
      estoque: 120,
      precoVenda: 28.5,
      forca: 'FORTE',
      amplitude: 0.77,
      mesPico: 'Mai–Jul',
      mesVale: 'Nov–Jan',
      faturamentoTotal: 145000,
      motivoInsuficiencia: null,
    },
    {
      codigo: 1001,
      descricao: 'CHA VERDE 100G',
      fornecedor: 'CATARINENSE',
      estoque: 42,
      precoVenda: 24.5,
      forca: 'MODERADA',
      amplitude: 0.34,
      mesPico: 'Jan–Mar',
      mesVale: 'Jul–Set',
      faturamentoTotal: 210000,
      motivoInsuficiencia: null,
    },
    {
      codigo: 1003,
      descricao: 'CAMOMILA P/ CHÁ 30G',
      fornecedor: 'CATARINENSE',
      estoque: 0,
      precoVenda: 12.9,
      forca: 'INSUFICIENTE',
      amplitude: 0,
      mesPico: null,
      mesVale: null,
      faturamentoTotal: 1800,
      motivoInsuficiencia: 'VENDA_ESPORADICA',
    },
    {
      codigo: 2002,
      descricao: 'WHEY 100% PURE GELATO 900G',
      fornecedor: 'INTEGRALMEDICA',
      estoque: 18,
      precoVenda: 159.9,
      forca: 'FRACA',
      amplitude: 0.14,
      mesPico: 'Out–Dez',
      mesVale: 'Abr–Jun',
      faturamentoTotal: 320000,
      motivoInsuficiencia: null,
    },
  ]);
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

  function initAndFlushCatalog(
    response: CatalogListResponse = createSeasonalCatalogResponse(),
  ): void {
    fixture.detectChanges();
    const catalogReq = httpMock.expectOne('/api/v1/analytics/products?includeSeasonality=true');
    catalogReq.flush(response);
    fixture.detectChanges();
  }

  it('renderiza apenas a tabela unificada do catálogo com colunas de sazonalidade (sem search-section nem rankings-section)', () => {
    initAndFlushCatalog();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.search-section')).toBeNull();
    expect(el.querySelector('.rankings-section')).toBeNull();
    expect(el.querySelector('app-product-catalog-explorer')).not.toBeNull();

    const text = el.textContent ?? '';
    expect(text).toContain('Catálogo e Sazonalidade de Produtos');
    expect(text).toContain('EXTRATO DE PRÓPOLIS 30ML');
    expect(text).toContain('WHEY 100% PURE GELATO 900G');
    expect(text).toContain('0,77x');
    expect(text).toContain('Mai–Jul');
    expect(text).toContain('Nov–Jan');
    expect(text).toContain('Venda esporádica (< 6 meses)');

    const groupNames = Array.from(
      el.querySelectorAll('app-product-catalog-explorer .supplier-group-name'),
    ).map((node) => (node.textContent ?? '').trim());
    expect(groupNames).toEqual(['APIS FLORA', 'CATARINENSE', 'INTEGRALMEDICA']);
  });

  it('filtra por força sazonal e busca inteligente na tabela e retorna ao catálogo via botão voltar', () => {
    initAndFlushCatalog();

    const el = fixture.nativeElement as HTMLElement;
    const strengthSelect = el.querySelector(
      'app-product-catalog-explorer select[id$="-strength"]',
    ) as HTMLSelectElement;
    expect(strengthSelect).not.toBeNull();

    strengthSelect.value = 'measurable';
    strengthSelect.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    expect(el.querySelectorAll('app-product-catalog-explorer tr.catalog-row').length).toBe(3);

    const searchInput = el.querySelector(
      'app-product-catalog-explorer input[type="search"]',
    ) as HTMLInputElement;
    searchInput.value = 'whey 100% gelato';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const actionBtn = el.querySelector(
      'app-product-catalog-explorer .btn-row-action',
    ) as HTMLButtonElement;
    expect(actionBtn).toBeTruthy();
    expect(actionBtn.textContent?.trim()).toBe('Ver sazonalidade');
    actionBtn.click();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/2002')
      .flush(createSeasonalityResponse(2002, 'WHEY 100% PURE GELATO 900G'));
    fixture.detectChanges();

    expect(el.textContent).toContain('WHEY 100% PURE GELATO 900G');
    const backBtn = el.querySelector('.product-header .btn-back-catalog') as HTMLButtonElement;
    expect(backBtn).toBeTruthy();
    expect(backBtn.textContent?.trim()).toBe('← Voltar para tabela de produtos');

    backBtn.click();
    fixture.detectChanges();

    // O catálogo vem do cache em memória do AnalyticsService sem nova chamada HTTP
    httpMock.expectNone('/api/v1/analytics/products?includeSeasonality=true');
    expect(el.querySelector('app-product-catalog-explorer')).toBeTruthy();
  });

  it('deve renderizar correlacaoYoy como 78% sem NaN%, data de referência e aviso de baixa confiança sem ano hardcoded', () => {
    initAndFlushCatalog();

    const el = fixture.nativeElement as HTMLElement;
    const firstRowBtn = el.querySelector(
      'app-product-catalog-explorer tr.catalog-row .btn-row-action',
    ) as HTMLButtonElement;
    firstRowBtn.click();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/1042')
      .flush(createSeasonalityResponse(1042));
    fixture.detectChanges();

    const text = el.textContent ?? '';
    expect(text).toContain('78%');
    expect(text).not.toContain('NaN%');
    expect(text).toContain('Base até 31/10/2026');
    expect(text).toContain('Confiança Baixa (1 ano)');
    expect(text).not.toContain('(2025)');
    expect(text).not.toContain('P-107');
  });

  it('deve permitir inspecionar mês no gráfico exibindo volume líquido, faturamento e desafixar mês', () => {
    initAndFlushCatalog();

    const firstRow = fixture.nativeElement.querySelector(
      'app-product-catalog-explorer tr.catalog-row',
    ) as HTMLTableRowElement;
    firstRow.click();
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
    initAndFlushCatalog();

    const flatSeries = createMonthlySeries({
      1: { indice: 1.0 },
      5: { indice: 1.0 },
      6: { indice: 1.0 },
      12: { indice: 0.0 },
    }).map((m) => (m.mes === 12 ? { ...m, indice: 0 } : { ...m, indice: 1.0 }));

    const firstRow = fixture.nativeElement.querySelector(
      'app-product-catalog-explorer tr.catalog-row',
    ) as HTMLTableRowElement;
    firstRow.click();
    fixture.detectChanges();

    httpMock.expectOne('/api/v1/analytics/seasonality/1042').flush(
      createSeasonalityResponse(1042, 'PRODUTO ESTAVEL', {
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
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Demanda uniforme ao longo dos 12 meses',
    );
    const zeroBars = fixture.nativeElement.querySelectorAll('.bar-fill.is-zero');
    expect(zeroBars.length).toBe(1);
    expect((zeroBars[0] as HTMLElement).style.height).toBe('0%');
  });

  it('deve exibir estado INSUFICIENTE com explicação humana e sem código interno (P-107)', () => {
    initAndFlushCatalog();

    const rows = fixture.nativeElement.querySelectorAll(
      'app-product-catalog-explorer tr.catalog-row',
    ) as NodeListOf<HTMLTableRowElement>;
    // Índice 1 é CAMOMILA P/ CHÁ 30G (SKU 1003, INSUFICIENTE)
    rows[1].click();
    fixture.detectChanges();

    httpMock.expectOne('/api/v1/analytics/seasonality/1003').flush(
      createSeasonalityResponse(1003, 'CAMOMILA P/ CHÁ 30G', {
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
    initAndFlushCatalog();

    const comp = fixture.componentInstance as unknown as {
      selectProductBySku: (sku: number) => void;
    };
    comp.selectProductBySku(1042);
    fixture.detectChanges();
    const req1 = httpMock.expectOne('/api/v1/analytics/seasonality/1042');

    comp.selectProductBySku(2002);
    fixture.detectChanges();
    const req2 = httpMock.expectOne('/api/v1/analytics/seasonality/2002');

    expect(req1.cancelled).toBeTrue();
    req2.flush(createSeasonalityResponse(2002, 'CHA VERDE ORGANICO'));
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('CHA VERDE ORGANICO');
  });

  it('deve tratar erro SEA-001 (404) sem botão retry e tratar 503 com "Tentar novamente" e botão voltar à tabela', () => {
    initAndFlushCatalog();

    const comp = fixture.componentInstance as unknown as {
      selectProductBySku: (sku: number) => void;
    };
    comp.selectProductBySku(9999);
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
    expect(banner.querySelector('.btn-back-catalog')?.textContent).toContain(
      '← Voltar para tabela de produtos',
    );

    // Volta à tabela e dispara novo SKU com erro recuperável 503
    (banner.querySelector('.btn-back-catalog') as HTMLButtonElement).click();
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-product-catalog-explorer')).not.toBeNull();

    comp.selectProductBySku(1042);
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

  it('deve carregar produto automaticamente quando ?sku= estiver presente e limpar URL ao voltar para a tabela', fakeAsync(() => {
    void router.navigateByUrl('/?sku=1042');
    tick();

    fixture = TestBed.createComponent(SeasonalityPageComponent);
    fixture.detectChanges();

    const productReq = httpMock.expectOne('/api/v1/analytics/seasonality/1042');
    productReq.flush(createSeasonalityResponse(1042));
    tick();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).textContent).toContain('SKU 1042');

    // Clicar em "← Voltar para tabela de produtos" limpa ?sku= da URL e exibe catálogo
    const backBtn = fixture.nativeElement.querySelector(
      '.product-header .btn-back-catalog',
    ) as HTMLButtonElement;
    backBtn.click();
    tick();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/products?includeSeasonality=true')
      .flush(createSeasonalCatalogResponse());
    fixture.detectChanges();

    expect(router.url).not.toContain('sku=');
    expect(fixture.nativeElement.querySelector('app-product-catalog-explorer')).not.toBeNull();

    // Selecionar outro produto na tabela atualiza a query string ?sku=2002
    const rows = fixture.nativeElement.querySelectorAll(
      'app-product-catalog-explorer tr.catalog-row',
    ) as NodeListOf<HTMLTableRowElement>;
    rows[3].click();
    tick();
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/seasonality/2002')
      .flush(createSeasonalityResponse(2002, 'WHEY 100% PURE GELATO 900G'));
    tick();
    fixture.detectChanges();

    expect(router.url).toContain('sku=2002');
  }));

  it('deve exibir aviso sem chamar API de sazonalidade quando ?sku= na URL for inválido', fakeAsync(() => {
    void router.navigateByUrl('/?sku=abc');
    tick();

    fixture = TestBed.createComponent(SeasonalityPageComponent);
    fixture.detectChanges();

    httpMock
      .expectOne('/api/v1/analytics/products?includeSeasonality=true')
      .flush(createSeasonalCatalogResponse());
    tick();
    fixture.detectChanges();

    httpMock.expectNone((req) => req.url.includes('/seasonality/'));
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'código SKU informado na URL é inválido',
    );
    expect(fixture.nativeElement.querySelector('app-product-catalog-explorer')).not.toBeNull();
  }));
});
