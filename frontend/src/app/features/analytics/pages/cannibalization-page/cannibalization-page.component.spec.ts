import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import {
  CannibalizationDetailResponse,
  CannibalizationReportResponse,
  CannibalizationWindowDays,
} from '../../models/cannibalization.model';
import { CannibalizationPageComponent } from './cannibalization-page.component';

function normalizeText(value: string | null | undefined): string {
  return (value ?? '').replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
}

function createReportResponse(
  windowDays: CannibalizationWindowDays = 90,
  overrides: Partial<CannibalizationReportResponse['data']> = {},
): CannibalizationReportResponse {
  return {
    data: {
      kpis: {
        totalVictims: 2,
        totalCannibalizedRevenue: 6310.5,
        avgCannibalizedRevenuePct: 26.4,
        totalNetMarginImpact: -780.4,
        marginDestroyingPairsCount: 2,
      },
      availableCategories: ['EXTRATOS', 'CAPSULAS'],
      availableSuppliers: ['APIS BRASIL', 'BIONAT'],
      victims: [
        {
          sku: '100235',
          description: 'EXTRATO DE PRÓPOLIS AQUOSO 30ML',
          category: 'EXTRATOS',
          supplier: 'APIS BRASIL',
          preRevenue: 18400.0,
          curRevenue: 12100.0,
          revenueDrop: 6300.0,
          revenueDropPct: 34.24,
          cannibalizedRevenue: 4420.5,
          cannibalizedRevenuePct: 33.9,
          dropExplainedPct: 70.17,
          currentPrice: 22.0,
          unitCost: 12.5,
          unitMargin: 9.5,
          marginPct: 43.18,
          costFallbackUsed: false,
          currentStock: 185,
          cannibalizerCount: 2,
          netMarginImpact: -685.18,
          topCannibal: {
            sku: '100234',
            description: 'EXTRATO DE PROPOLIS VERDE 30ML',
            migratedClients: 14,
            migratedRevenue: 3180.5,
            shareOfCannibalizationPct: 71.95,
            currentPrice: 18.9,
            unitMargin: 5.0,
            marginPct: 26.46,
            costFallbackUsed: false,
            priceGapPct: 16.4,
            netMarginImpact: -255.39,
            mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
            suggestedVictimPrice: 20.2,
            suggestedCannibalPrice: 20.9,
            projectedPriceGapPct: 3.4,
            actionSummary:
              'O canibalizador está abaixo da vítima com margem menor; reajustá-lo preserva rentabilidade.',
          },
          cannibalizers: [
            {
              sku: '100234',
              description: 'EXTRATO DE PROPOLIS VERDE 30ML',
              migratedClients: 14,
              migratedRevenue: 3180.5,
              shareOfCannibalizationPct: 71.95,
              currentPrice: 18.9,
              unitMargin: 5.0,
              marginPct: 26.46,
              costFallbackUsed: false,
              priceGapPct: 16.4,
              netMarginImpact: -255.39,
              mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
              suggestedVictimPrice: 20.2,
              suggestedCannibalPrice: 20.9,
              projectedPriceGapPct: 3.4,
              actionSummary:
                'O canibalizador está abaixo da vítima com margem menor; reajustá-lo preserva rentabilidade.',
            },
          ],
        },
        {
          sku: '200410',
          description: 'CÁPSULAS DE EQUINÁCEA 60UN',
          category: 'CAPSULAS',
          supplier: 'BIONAT',
          preRevenue: 8640.0,
          curRevenue: 6750.0,
          revenueDrop: 1890.0,
          revenueDropPct: 21.88,
          cannibalizedRevenue: 1890.0,
          cannibalizedRevenuePct: 18.9,
          dropExplainedPct: 100.0,
          currentPrice: 28.0,
          unitCost: 16.8,
          unitMargin: 11.2,
          marginPct: 40.0,
          costFallbackUsed: true,
          currentStock: 92,
          cannibalizerCount: 1,
          netMarginImpact: -95.22,
          topCannibal: {
            sku: '200411',
            description: 'CÁPSULAS IMUNIDADE PREMIUM 60UN',
            migratedClients: 8,
            migratedRevenue: 1890.0,
            shareOfCannibalizationPct: 100.0,
            currentPrice: 35.0,
            unitMargin: 16.8,
            marginPct: 48.0,
            costFallbackUsed: false,
            priceGapPct: -20.0,
            netMarginImpact: 120.0,
            mechanism: 'MIGRACAO_POR_VALOR',
            suggestedVictimPrice: null,
            suggestedCannibalPrice: null,
            projectedPriceGapPct: null,
            actionSummary: 'Manter preços atuais; migração favorável para item de maior margem.',
          },
          cannibalizers: [
            {
              sku: '200411',
              description: 'CÁPSULAS IMUNIDADE PREMIUM 60UN',
              migratedClients: 8,
              migratedRevenue: 1890.0,
              shareOfCannibalizationPct: 100.0,
              currentPrice: 35.0,
              unitMargin: 16.8,
              marginPct: 48.0,
              costFallbackUsed: false,
              priceGapPct: -20.0,
              netMarginImpact: 120.0,
              mechanism: 'MIGRACAO_POR_VALOR',
              suggestedVictimPrice: null,
              suggestedCannibalPrice: null,
              projectedPriceGapPct: null,
              actionSummary: 'Manter preços atuais; migração favorável para item de maior margem.',
            },
          ],
        },
      ],
      ...overrides,
    },
    meta: {
      timestamp: '2026-11-23T19:00:00Z',
      version: '1.1.0',
      dataReferencia: '2026-11-23',
      windowDays,
      minDropPct: 5.0,
      minMigratedClients: 3,
      prePeriod: { startDate: '2026-05-27', endDate: '2026-08-24' },
      curPeriod: { startDate: '2026-08-25', endDate: '2026-11-22' },
      totalFound: overrides.victims ? overrides.victims.length : 2,
      executionTimeMs: 142,
    },
  };
}

function createDetailResponse(sku = '100235'): CannibalizationDetailResponse {
  return {
    data: {
      isCannibalized: true,
      victim: {
        sku,
        description: 'EXTRATO DE PRÓPOLIS AQUOSO 30ML',
        category: 'EXTRATOS',
        supplier: 'APIS BRASIL',
        preRevenue: 18400.0,
        curRevenue: 12100.0,
        revenueDrop: 6300.0,
        revenueDropPct: 34.24,
        cannibalizedRevenue: 4420.5,
        cannibalizedRevenuePct: 33.9,
        dropExplainedPct: 70.17,
        currentPrice: 22.0,
        unitCost: 12.5,
        unitMargin: 9.5,
        marginPct: 43.18,
        costFallbackUsed: false,
        currentStock: 185,
        cannibalizerCount: 1,
        netMarginImpact: -685.18,
      },
      cannibalizers: [
        {
          sku: '100234',
          description: 'EXTRATO DE PROPOLIS VERDE 30ML',
          category: 'EXTRATOS',
          supplier: 'APIS BRASIL',
          migratedClients: 14,
          grossClientsToCannibal: 16,
          reverseClientsToVictim: 2,
          migratedRevenue: 3180.5,
          shareOfCannibalizationPct: 71.95,
          preRevenue: 9200.0,
          curRevenue: 14800.0,
          currentPrice: 18.9,
          unitCost: 13.9,
          unitMargin: 5.0,
          marginPct: 26.46,
          costFallbackUsed: false,
          currentStock: 340,
          priceGapPct: 16.4,
          netMarginImpact: -255.39,
          mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
          suggestedVictimPrice: 20.2,
          suggestedCannibalPrice: 20.9,
          projectedPriceGapPct: 3.4,
          victimMarginFloorPrice: 15.63,
          actionSummary:
            'O canibalizador está abaixo da vítima com margem menor; reajustá-lo preserva rentabilidade.',
        },
      ],
    },
    meta: {
      timestamp: '2026-11-23T19:00:00Z',
      version: '1.1.0',
      dataReferencia: '2026-11-23',
      sku,
      windowDays: 90,
      prePeriod: { startDate: '2026-05-27', endDate: '2026-08-24' },
      curPeriod: { startDate: '2026-08-25', endDate: '2026-11-22' },
      executionTimeMs: 12,
    },
  };
}

describe('CannibalizationPageComponent (v2)', () => {
  let fixture: ComponentFixture<CannibalizationPageComponent>;
  let httpMock: HttpTestingController;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CannibalizationPageComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([
          { path: 'analytics/canibalizacao', component: CannibalizationPageComponent },
          { path: '**', component: CannibalizationPageComponent },
        ]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CannibalizationPageComponent);
    httpMock = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    httpMock.verify();
  });

  function initAndFlushReport(
    windowDays: CannibalizationWindowDays = 90,
    response: CannibalizationReportResponse = createReportResponse(windowDays),
  ): void {
    fixture.detectChanges();
    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' &&
        r.params.get('windowDays') === String(windowDays),
    );
    req.flush(response);
    fixture.detectChanges();
  }

  it('renderiza hierarquia h2 (sem h1 e sem ModeSwitch v1), carrega janela 90d padrão e exibe 4 KPIs e tabela', () => {
    initAndFlushReport(90);
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('h1')).toBeNull();
    expect(el.querySelector('app-mode-switch')).toBeNull();
    expect(el.querySelector('h2')?.textContent).toContain(
      'Relatório de Canibalização e Equilíbrio de Preço',
    );

    const kpiCards = el.querySelectorAll('app-cannibalization-kpi-strip .kpi-card');
    expect(kpiCards.length).toBe(4);
    const kpiText = normalizeText(el.querySelector('app-cannibalization-kpi-strip')?.textContent);
    expect(kpiText).toContain('−R$ 6.310,50');
    expect(kpiText).toContain('EXTRATOS');

    const rows = el.querySelectorAll('table.cannibalization-table tbody tr');
    expect(rows.length).toBe(2);
    expect(normalizeText(rows[0].textContent)).toContain('EXTRATO DE PRÓPOLIS AQUOSO 30ML');
  });

  it('alterna período (30/60/90 dias) e cancela requisição anterior via switchMap', () => {
    initAndFlushReport(90);
    const el = fixture.nativeElement as HTMLElement;
    const buttons = Array.from(
      el.querySelectorAll<HTMLButtonElement>('.period-segmented button'),
    );
    expect(buttons.map((b) => normalizeText(b.textContent))).toEqual([
      '30 dias',
      '60 dias',
      '90 dias',
    ]);

    // Clica em 30 dias -> dispara req1
    buttons[0].click();
    fixture.detectChanges();
    const req30 = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' && r.params.get('windowDays') === '30',
    );

    // Simula disparo concorrente na store via loadReport(60)
    (fixture.componentInstance as unknown as { store: { loadReport: (d: 30 | 60 | 90) => void } })
      .store.loadReport(60);
    fixture.detectChanges();
    const req60 = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' && r.params.get('windowDays') === '60',
    );

    expect(req30.cancelled).toBeTrue();
    req60.flush(createReportResponse(60));
    fixture.detectChanges();

    expect(buttons[1].getAttribute('aria-pressed')).toBe('true');
  });

  it('exibe skeleton solid-pulse durante loading e aviso de consulta lenta após 4000ms', fakeAsync(() => {
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.querySelector('app-cannibalization-skeleton')).not.toBeNull();
    expect(el.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(el.querySelector('.slow-query-notice')).toBeNull();

    tick(4000);
    fixture.detectChanges();

    const statusText = normalizeText(el.querySelector('[role="status"]')?.textContent);
    expect(statusText).toContain('primeira consulta pode levar alguns segundos');

    const req = httpMock.expectOne(
      (r) => r.url === '/api/v1/analytics/cannibalization/report',
    );
    req.flush(createReportResponse(90));
    fixture.detectChanges();

    expect(el.querySelector('app-cannibalization-skeleton')).toBeNull();
  }));

  it('filtra client-side por busca textual (sem acentos), comboboxes Fornecedor e Categoria, e limpa filtros', () => {
    initAndFlushReport(90);
    const el = fixture.nativeElement as HTMLElement;

    // Busca textual NFD ("propolis" encontra "PRÓPOLIS")
    const searchInput = el.querySelector<HTMLInputElement>('input[type="search"]')!;
    searchInput.value = 'propolis';
    searchInput.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(el.querySelectorAll('table.cannibalization-table tbody tr').length).toBe(1);
    expect(normalizeText(el.querySelector('table.cannibalization-table tbody')?.textContent)).toContain(
      '100235',
    );

    // Limpar filtros via botão
    const clearBtn = el.querySelector<HTMLButtonElement>('.btn-clear-filters')!;
    clearBtn.click();
    fixture.detectChanges();
    expect(el.querySelectorAll('table.cannibalization-table tbody tr').length).toBe(2);

    // Combobox de Fornecedor: abrir, buscar internamente e selecionar BIONAT
    const comboboxTriggers = el.querySelectorAll<HTMLButtonElement>(
      'app-searchable-combobox .combobox-trigger',
    );
    expect(comboboxTriggers.length).toBe(2);
    comboboxTriggers[0].click();
    fixture.detectChanges();

    const internalSearch = el.querySelector<HTMLInputElement>('.combobox-search-input')!;
    internalSearch.value = 'bio';
    internalSearch.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const options = el.querySelectorAll<HTMLLIElement>('.combobox-option');
    expect(options.length).toBe(1);
    expect(normalizeText(options[0].textContent)).toContain('BIONAT');
    options[0].click();
    fixture.detectChanges();

    expect(el.querySelectorAll('table.cannibalization-table tbody tr').length).toBe(1);
    expect(normalizeText(el.querySelector('table.cannibalization-table tbody')?.textContent)).toContain(
      '200410',
    );

    // Combobox de Categoria com valor incompatível -> empty state de filtros
    comboboxTriggers[1].click();
    fixture.detectChanges();
    const catOption = Array.from(el.querySelectorAll<HTMLLIElement>('.combobox-option')).find((li) =>
      normalizeText(li.textContent).includes('EXTRATOS'),
    )!;
    catOption.click();
    fixture.detectChanges();

    expect(el.querySelector('.filters-empty-state')).not.toBeNull();
  });

  it('ordena colunas sincronizando aria-sort e select de ordenação', () => {
    initAndFlushReport(90);
    const el = fixture.nativeElement as HTMLElement;

    const priceHeaderBtn = Array.from(
      el.querySelectorAll<HTMLButtonElement>('thead .sort-header-btn'),
    ).find((b) => normalizeText(b.textContent).includes('Preço atual'))!;
    priceHeaderBtn.click();
    fixture.detectChanges();

    const firstRowText = normalizeText(
      el.querySelector('table.cannibalization-table tbody tr')?.textContent,
    );
    expect(firstRowText).toContain('200410'); // R$ 28,00 > R$ 22,00
    expect(priceHeaderBtn.closest('th')?.getAttribute('aria-sort')).toBe('descending');

    priceHeaderBtn.click();
    fixture.detectChanges();
    expect(priceHeaderBtn.closest('th')?.getAttribute('aria-sort')).toBe('ascending');
    expect(
      normalizeText(el.querySelector('table.cannibalization-table tbody tr')?.textContent),
    ).toContain('100235');
  });

  it('abre PriceEquilibriumDrawer, aplica inert no fundo, consulta /report/{sku}, fecha com Esc e restaura foco', fakeAsync(() => {
    initAndFlushReport(90);
    const el = fixture.nativeElement as HTMLElement;

    const actionBtn = el.querySelector<HTMLButtonElement>('table.cannibalization-table .btn-row-action')!;
    actionBtn.focus();
    actionBtn.click();
    fixture.detectChanges();
    tick();

    // Verifica aria-modal e inert no container principal
    const dialog = el.querySelector<HTMLElement>('app-price-equilibrium-drawer [role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
    expect(el.querySelector('.cannibalization-page')?.hasAttribute('inert')).toBeTrue();

    // Flush da consulta /cannibalization/report/100235
    const detailReq = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report/100235' &&
        r.params.get('windowDays') === '90',
    );
    detailReq.flush(createDetailResponse('100235'));
    fixture.detectChanges();

    const drawerText = normalizeText(dialog?.textContent);
    expect(drawerText).toContain('EXTRATO DE PROPOLIS VERDE 30ML');
    expect(drawerText).toContain('Reajustar canibalizador');
    expect(drawerText).toContain('R$ 20,90');
    expect(drawerText).toContain('R$ 20,20');

    // Fecha com Escape e restaura foco
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    tick();

    expect(el.querySelector('app-price-equilibrium-drawer [role="dialog"]')).toBeNull();
    expect(el.querySelector('.cannibalization-page')?.hasAttribute('inert')).toBeFalse();
    expect(document.activeElement).toBe(actionBtn);
  }));

  it('exibe ResultStateComponent quando período não possui vítimas e ErrorBanner com retry em 503 ANL-001', () => {
    // 1. Empty state de período
    initAndFlushReport(
      90,
      createReportResponse(90, {
        kpis: {
          totalVictims: 0,
          totalCannibalizedRevenue: 0,
          avgCannibalizedRevenuePct: 0,
          totalNetMarginImpact: 0,
          marginDestroyingPairsCount: 0,
        },
        victims: [],
      }),
    );
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('app-result-state')).not.toBeNull();

    // 2. Troca para 30 dias e simula 503 ANL-001
    const btn30 = el.querySelectorAll<HTMLButtonElement>('.period-segmented button')[0];
    btn30.click();
    fixture.detectChanges();

    httpMock
      .expectOne(
        (r) =>
          r.url === '/api/v1/analytics/cannibalization/report' && r.params.get('windowDays') === '30',
      )
      .flush(
        { error: { code: 'ANL-001', message: 'Base indisponível.', fields: [], details: null } },
        { status: 503, statusText: 'Service Unavailable' },
      );
    fixture.detectChanges();

    const banner = el.querySelector<HTMLElement>('app-error-banner');
    expect(banner).not.toBeNull();
    expect(normalizeText(banner?.textContent)).toContain('Base de vendas indisponível');

    // 3. Retry no ErrorBanner
    const retryBtn = banner!.querySelector<HTMLButtonElement>('button')!;
    retryBtn.click();
    fixture.detectChanges();

    httpMock
      .expectOne(
        (r) =>
          r.url === '/api/v1/analytics/cannibalization/report' && r.params.get('windowDays') === '30',
      )
      .flush(createReportResponse(30));
    fixture.detectChanges();

    expect(el.querySelector('app-cannibalization-kpi-strip')).not.toBeNull();
  });

  it('sanitiza query params inválidos da URL fazendo fallback para 90 dias', fakeAsync(() => {
    void router.navigateByUrl('/analytics/canibalizacao?periodo=999&ordenar=invalido');
    tick();

    const fixtureWithUrl = TestBed.createComponent(CannibalizationPageComponent);
    fixtureWithUrl.detectChanges();

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' && r.params.get('windowDays') === '90',
    );
    req.flush(createReportResponse(90));
    fixtureWithUrl.detectChanges();

    const activeBtn = fixtureWithUrl.nativeElement.querySelector(
      '.period-btn.is-active',
    ) as HTMLButtonElement;
    expect(normalizeText(activeBtn.textContent)).toBe('90 dias');
  }));
});
