import { HttpErrorResponse } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { Subject, of, throwError } from 'rxjs';
import {
  NewProductForecastRequest,
  NewProductForecastResponse,
  NewProductOptionsResponse,
} from '../models/new-product.model';
import { AnalyticsService } from './analytics.service';
import { NewProductStore } from './new-product.store';

const MOCK_OPTIONS: NewProductOptionsResponse = {
  data: {
    tipos: ['Capsulas', 'Tinturas'],
    fornecedores: ['FITOHERB LABORATORIOS', 'HERBAL BRASIL'],
  },
  meta: { timestamp: '2026-11-17T10:00:00Z', version: '1.0.0', dataReferencia: '2026-11-16' },
};

const MOCK_REQUEST: NewProductForecastRequest = {
  tipo: 'Tinturas',
  fornecedor: 'FITOHERB LABORATORIOS',
  descricao: 'Tintura de Melissa 50ml',
  precoVendaPrevisto: 42.5,
  custoUnitario: 19.1,
  margemMinimaDesejada: 0.5,
  horizonMonths: 3,
};

const MOCK_FORECAST: NewProductForecastResponse = {
  data: {
    inputSummary: MOCK_REQUEST,
    monthlyForecast: [
      {
        month: 1,
        calendarMonth: 11,
        quantity: 38,
        revenue: 1615,
        grossMargin: 889.2,
        p10Quantity: 22,
        conservativeQuantity: 38,
        p50Quantity: 64,
        similarP25Quantity: 54,
        seasonalityFactor: 1,
        seasonalityConfidence: 'BAIXA',
      },
    ],
    seasonalityStatus: 'FALLBACK_NEUTRAL',
    aggregatedTotals: {
      totalQuantity: 38,
      totalRevenue: 1615,
      totalGrossMargin: 889.2,
      averageMonthlyQuantity: 38,
      averageMonthlyRevenue: 1615,
    },
    financialViability: {
      precoVenda: 42.5,
      custoUnitario: 19.1,
      margemBrutaUnitaria: 23.4,
      margemBrutaPercentual: 0.5506,
      margemMinimaDesejada: 0.5,
      viavel: true,
      parecer: 'Produto viavel.',
    },
    marketCeiling: {
      tetoMaduroP75: 210,
      descricao: 'Percentil 75 maduro.',
    },
    similarsUsed: [
      {
        sku: '1042',
        descricao: 'Tintura Passiflora 50ml',
        fornecedor: 'FITOHERB LABORATORIOS',
        primeiraVenda: '2025-05-10',
        precoHistorico: 39.9,
        scoreFinal: 0.9125,
        scoreFornecedor: 1,
        scorePreco: 0.9388,
        scoreTfidf: 0.835,
        quantidadesPrimeirosMeses: [58, 65, 80],
      },
    ],
    methodologyNotice: 'Estimativa conservadora P25 x 0,70.',
  },
  meta: { timestamp: '2026-11-17T10:00:00Z', version: '1.0.0', dataReferencia: '2026-11-16' },
};

describe('NewProductStore', () => {
  let store: NewProductStore;
  let serviceSpy: jasmine.SpyObj<AnalyticsService>;

  beforeEach(() => {
    serviceSpy = jasmine.createSpyObj<AnalyticsService>('AnalyticsService', [
      'getNewProductOptions',
      'simulateNewProductForecast',
    ]);
    serviceSpy.getNewProductOptions.and.returnValue(of(MOCK_OPTIONS));
    serviceSpy.simulateNewProductForecast.and.returnValue(of(MOCK_FORECAST));

    TestBed.configureTestingModule({
      providers: [NewProductStore, { provide: AnalyticsService, useValue: serviceSpy }],
    });
    store = TestBed.inject(NewProductStore);
  });

  it('carrega /options com sucesso e detecta catálogo não vazio', () => {
    store.loadOptions();
    expect(store.optionsState()).toBe('ready');
    expect(store.options()?.tipos).toEqual(['Capsulas', 'Tinturas']);
    expect(store.hasEmptyCatalog()).toBeFalse();
  });

  it('mapeia falha de /options para optionsState = error', () => {
    serviceSpy.getNewProductOptions.and.returnValue(
      throwError(() => new HttpErrorResponse({ status: 503, error: { error: { code: 'NEW-005', message: 'Indisponivel', fields: [] } } })),
    );
    store.loadOptions();
    expect(store.optionsState()).toBe('error');
    expect(store.optionsError()?.code).toBe('NEW-005');
  });

  it('simula previsão com sucesso e marca dirty ao alterar parâmetros', () => {
    store.simulate(MOCK_REQUEST);
    expect(store.simulationState()).toBe('success');
    expect(store.forecastData()?.aggregatedTotals.totalQuantity).toBe(38);
    expect(store.isDirtySinceLastResult()).toBeFalse();

    store.markDirty();
    expect(store.isDirtySinceLastResult()).toBeTrue();
  });

  it('trata NEW-001 como estado insufficient (não erro fatal)', () => {
    serviceSpy.simulateNewProductForecast.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 422,
            error: { error: { code: 'NEW-001', message: 'Menos de 3 similares.', fields: [] } },
          }),
      ),
    );
    store.simulate(MOCK_REQUEST);
    expect(store.simulationState()).toBe('insufficient');
    expect(store.forecastError()?.code).toBe('NEW-001');
  });

  it('trata NEW-002/003/004 com fields sem mostrar banner fatal', () => {
    serviceSpy.simulateNewProductForecast.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 400,
            error: { error: { code: 'NEW-002', message: 'Tipo invalido.', fields: ['tipo'] } },
          }),
      ),
    );
    store.simulate(MOCK_REQUEST);
    expect(store.simulationState()).toBe('idle');
    expect(store.forecastError()?.code).toBe('NEW-002');
  });

  it('cancela requisição anterior em voo via switchMap (anti-double-submit)', () => {
    const first$ = new Subject<NewProductForecastResponse>();
    const second$ = new Subject<NewProductForecastResponse>();
    serviceSpy.simulateNewProductForecast.and.returnValues(first$.asObservable(), second$.asObservable());

    store.simulate(MOCK_REQUEST);
    expect(store.simulationState()).toBe('loading');

    store.simulate({ ...MOCK_REQUEST, precoVendaPrevisto: 55 });
    expect(first$.observed).toBeFalse();

    second$.next(MOCK_FORECAST);
    second$.complete();
    expect(store.simulationState()).toBe('success');
  });
});
