import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import {
  CannibalizationDetailResponse,
  CannibalizationReportResponse,
} from '../models/cannibalization.model';
import {
  CANNIBALIZATION_ERROR_CODES,
  CANNIBALIZATION_ERROR_MESSAGES,
  CannibalizationErrorCode,
  resolveCannibalizationErrorMessage,
  resolveCannibalizationFieldError,
  toCannibalizationApiError,
} from '../utils/analytics-error';
import { CannibalizationService } from './cannibalization.service';

function createReportMock(
  overrides: Partial<CannibalizationReportResponse['data']> = {},
): CannibalizationReportResponse {
  return {
    data: {
      kpis: {
        totalVictims: 2,
        totalCannibalizedRevenue: 6310.5,
        avgCannibalizedRevenuePct: 23.0,
        totalNetMarginImpact: -780.4,
        marginDestroyingPairsCount: 2,
      },
      availableCategories: ['EXTRATOS', 'CAPSULAS'],
      availableSuppliers: ['FITOHERB', 'HERBARIUM'],
      victims: [
        {
          sku: '100235',
          description: 'EXTRATO DE PROPOLIS AQUOSO 30ML',
          category: 'EXTRATOS',
          supplier: 'FITOHERB',
          preRevenue: 18400.0,
          curRevenue: 12100.0,
          revenueDrop: 6300.0,
          revenueDropPct: 34.24,
          cannibalizedRevenue: 4420.5,
          cannibalizedRevenuePct: 24.02,
          dropExplainedPct: 70.17,
          currentPrice: 30.0,
          unitCost: 16.0,
          unitMargin: 14.0,
          marginPct: 46.67,
          costFallbackUsed: false,
          currentStock: 185,
          cannibalizerCount: 2,
          netMarginImpact: -685.18,
          topCannibal: {
            sku: '100234',
            description: 'EXTRATO DE PROPOLIS VERDE 30ML',
            migratedClients: 11,
            migratedRevenue: 3180.5,
            shareOfCannibalizationPct: 71.95,
            currentPrice: 22.0,
            unitMargin: 8.5,
            marginPct: 38.64,
            costFallbackUsed: false,
            priceGapPct: 36.36,
            netMarginImpact: -255.39,
            mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
            suggestedVictimPrice: 28.4,
            suggestedCannibalPrice: 23.6,
            projectedPriceGapPct: 20.34,
            actionSummary:
              'Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%).',
          },
          cannibalizers: [
            {
              sku: '100234',
              description: 'EXTRATO DE PROPOLIS VERDE 30ML',
              migratedClients: 11,
              migratedRevenue: 3180.5,
              shareOfCannibalizationPct: 71.95,
              currentPrice: 22.0,
              unitMargin: 8.5,
              marginPct: 38.64,
              costFallbackUsed: false,
              priceGapPct: 36.36,
              netMarginImpact: -255.39,
              mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
              suggestedVictimPrice: 28.4,
              suggestedCannibalPrice: 23.6,
              projectedPriceGapPct: 20.34,
              actionSummary:
                'Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%).',
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
      windowDays: 90,
      minDropPct: 5.0,
      minMigratedClients: 3,
      prePeriod: { startDate: '2026-05-27', endDate: '2026-08-24' },
      curPeriod: { startDate: '2026-08-25', endDate: '2026-11-22' },
      totalFound: 1,
      executionTimeMs: 142,
    },
  };
}

function createDetailMock(sku = '100235'): CannibalizationDetailResponse {
  return {
    data: {
      isCannibalized: true,
      victim: {
        sku,
        description: 'EXTRATO DE PROPOLIS AQUOSO 30ML',
        category: 'EXTRATOS',
        supplier: 'FITOHERB',
        preRevenue: 18400.0,
        curRevenue: 12100.0,
        revenueDrop: 6300.0,
        revenueDropPct: 34.24,
        cannibalizedRevenue: 4420.5,
        cannibalizedRevenuePct: 24.02,
        dropExplainedPct: 70.17,
        currentPrice: 30.0,
        unitCost: 16.0,
        unitMargin: 14.0,
        marginPct: 46.67,
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
          supplier: 'FITOHERB',
          migratedClients: 11,
          grossClientsToCannibal: 13,
          reverseClientsToVictim: 2,
          migratedRevenue: 3180.5,
          shareOfCannibalizationPct: 71.95,
          preRevenue: 9200.0,
          curRevenue: 14800.0,
          currentPrice: 22.0,
          unitCost: 13.5,
          unitMargin: 8.5,
          marginPct: 38.64,
          costFallbackUsed: false,
          currentStock: 340,
          priceGapPct: 36.36,
          netMarginImpact: -255.39,
          mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
          suggestedVictimPrice: 28.4,
          suggestedCannibalPrice: 23.6,
          projectedPriceGapPct: 20.34,
          victimMarginFloorPrice: 20.0,
          actionSummary:
            'Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%).',
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

function httpError(status: number, error: unknown): HttpErrorResponse {
  return new HttpErrorResponse({ status, statusText: 'Error', error });
}

describe('CannibalizationService (v2)', () => {
  let service: CannibalizationService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(CannibalizationService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('deve consultar /api/v1/analytics/cannibalization/report com windowDays=90 padrão', () => {
    const mockResponse = createReportMock();
    let received: CannibalizationReportResponse | undefined;

    service.getReport().subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' &&
        r.params.get('windowDays') === '90' &&
        !r.params.has('category') &&
        !r.params.has('supplier'),
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);

    expect(received?.data.victims.length).toBe(1);
    expect(received?.meta.version).toBe('1.1.0');
  });

  it('deve enviar parâmetros opcionais sanitizados em getReport', () => {
    const mockResponse = createReportMock();

    service
      .getReport({
        windowDays: 60,
        minDropPct: 10,
        minMigratedClients: 5,
        category: ' EXTRATOS ',
        supplier: ' FITOHERB ',
        mechanism: 'PRECO_MENOR_DESTROI_MARGEM',
        search: ' propolis ',
      })
      .subscribe();

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report' &&
        r.params.get('windowDays') === '60' &&
        r.params.get('minDropPct') === '10' &&
        r.params.get('minMigratedClients') === '5' &&
        r.params.get('category') === 'EXTRATOS' &&
        r.params.get('supplier') === 'FITOHERB' &&
        r.params.get('mechanism') === 'PRECO_MENOR_DESTROI_MARGEM' &&
        r.params.get('search') === 'propolis',
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('deve consultar /api/v1/analytics/cannibalization/report/{sku} com windowDays', () => {
    const mockDetail = createDetailMock('100235');
    let received: CannibalizationDetailResponse | undefined;

    service.getVictimDetail(' 100235 ', { windowDays: 30 }).subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/cannibalization/report/100235' &&
        r.params.get('windowDays') === '30',
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockDetail);

    expect(received?.data.isCannibalized).toBeTrue();
    expect(received?.data.cannibalizers[0].victimMarginFloorPrice).toBe(20.0);
  });

  it('deve propagar erros HTTP (404 CAN-001, 503 ANL-001) sem mascarar falhas', () => {
    let capturedError: HttpErrorResponse | undefined;

    service.getVictimDetail('999999').subscribe({
      error: (err: HttpErrorResponse) => {
        capturedError = err;
      },
    });

    const req = httpMock.expectOne(
      (r) => r.url === '/api/v1/analytics/cannibalization/report/999999',
    );
    req.flush(
      {
        error: {
          code: 'CAN-001',
          message: 'Produto não encontrado no catálogo ativo.',
          fields: [],
          details: null,
        },
        meta: { timestamp: '2026-11-23T19:00:00Z', version: '1.1.0' },
      },
      { status: 404, statusText: 'Not Found' },
    );

    expect(capturedError?.status).toBe(404);
    expect(toCannibalizationApiError(capturedError)?.code).toBe('CAN-001');
  });
});

describe('Mapeamento de Erros de Canibalização v2 (CAN-001, CAN-003..005, ANL-001)', () => {
  const expectedCodes: CannibalizationErrorCode[] = [
    'CAN-001',
    'CAN-003',
    'CAN-004',
    'CAN-005',
    'ANL-001',
  ];

  it('deve converter todos os códigos do contrato v2 do envelope de erro', () => {
    for (const code of expectedCodes) {
      const err = httpError(400, {
        error: { code, message: 'Mensagem de contrato', fields: [] },
      });

      const parsed = toCannibalizationApiError(err);

      expect(CANNIBALIZATION_ERROR_CODES).toContain(code);
      expect(parsed?.code).withContext(code).toBe(code);
      expect(CANNIBALIZATION_ERROR_MESSAGES[code]).withContext(code).toBeTruthy();
      expect(resolveCannibalizationErrorMessage(parsed))
        .withContext(code)
        .toBe(CANNIBALIZATION_ERROR_MESSAGES[code]);
    }
  });

  it('deve retornar null para erro 500 texto puro, erro de rede (status 0), 422 FastAPI ou código desconhecido', () => {
    expect(toCannibalizationApiError(httpError(500, 'Internal Server Error'))).toBeNull();
    expect(toCannibalizationApiError(httpError(0, new ProgressEvent('error')))).toBeNull();
    expect(
      toCannibalizationApiError(
        httpError(422, { detail: [{ loc: ['query', 'windowDays'], msg: 'invalid' }] }),
      ),
    ).toBeNull();
    expect(
      toCannibalizationApiError(
        httpError(400, { error: { code: 'UNKNOWN-99', message: 'x', fields: [] } }),
      ),
    ).toBeNull();
    expect(resolveCannibalizationErrorMessage(null)).toBeTruthy();
  });

  it('deve rotear CAN-004 para windowDays e CAN-001 para sku sem ecoar input bruto', () => {
    const can004Window = toCannibalizationApiError(
      httpError(400, {
        error: { code: 'CAN-004', message: 'Parâmetros inválidos: windowDays.', fields: ['windowDays'] },
      }),
    );
    const can001 = toCannibalizationApiError(
      httpError(404, {
        error: { code: 'CAN-001', message: 'Produto não encontrado no catálogo ativo.', fields: [] },
      }),
    );

    expect(resolveCannibalizationFieldError(can004Window, 'windowDays')).toBeTruthy();
    expect(resolveCannibalizationFieldError(can004Window, 'sku')).toBeNull();
    expect(resolveCannibalizationFieldError(can001, 'sku')).toBe(
      CANNIBALIZATION_ERROR_MESSAGES['CAN-001'],
    );
  });
});
