/**
 * T-13 — AnalyticsService (contrato analytics-cross-sell 1.1.0, §5).
 * URLs, HttpParams de paginação e tipos de resposta; o serviço devolve o envelope completo (`data` + `meta`).
 * Sem console.log e sem storage (LGPD-09).
 */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AnalyticsService } from './analytics.service';
import {
  catalogResponse,
  customerResponse,
  healthResponse,
  productResponse,
  searchResponse,
} from '../testing/cross-sell-test-data';
import { AnalyticsHealthResponse } from '../models/analytics.model';
import {
  CatalogListResponse,
  CustomerCrossSellResponse,
  ProductCrossSellResponse,
  ProductSearchResponse,
} from '../models/cross-sell.model';

describe('AnalyticsService', () => {
  let service: AnalyticsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AnalyticsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('getHealth faz GET em /api/v1/analytics/health', () => {
    let received: AnalyticsHealthResponse | undefined;
    service.getHealth().subscribe((response) => (received = response));

    const request = http.expectOne('/api/v1/analytics/health');
    expect(request.request.method).toBe('GET');
    request.flush(healthResponse('QUENTE'));

    expect(received?.data.estadoCache).toBe('QUENTE');
    expect(received?.data.parametros.dormantDays).toBe(90);
  });

  it('getProductCrossSell usa o SKU no path e limit/offset como HttpParams', () => {
    let received: ProductCrossSellResponse | undefined;
    service.getProductCrossSell(1001, { limit: 50, offset: 100 }).subscribe((response) => (received = response));

    const request = http.expectOne((req) => req.url === '/api/v1/analytics/cross-sell/product/1001');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('limit')).toBe('50');
    expect(request.request.params.get('offset')).toBe('100');
    expect(request.request.params.keys().sort()).toEqual(['limit', 'offset']);
    request.flush(productResponse());

    expect(received?.data.produto.codigo).toBe(1001);
    expect(received?.data.recomendacoes.length).toBe(2);
    expect(received?.meta.totalItems).toBe(2);
  });

  it('getCustomerCrossSell usa o código do cliente só no path (LGPD-07)', () => {
    let received: CustomerCrossSellResponse | undefined;
    service.getCustomerCrossSell(48213, { limit: 50, offset: 0 }).subscribe((response) => (received = response));

    const request = http.expectOne((req) => req.url === '/api/v1/analytics/cross-sell/customer/48213');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.keys().sort()).toEqual(['limit', 'offset']);
    expect(request.request.headers.keys().length).toBe(0);
    request.flush(customerResponse());

    expect(received?.data.recomendacoes[0].motivo).toBe('NUNCA_COMPROU');
    expect(received?.meta.motivoVazio).toBeNull();
  });

  it('searchProducts envia q, limit e offset (DC-5)', () => {
    let received: ProductSearchResponse | undefined;
    service.searchProducts('cha verde', { limit: 20, offset: 0 }).subscribe((response) => (received = response));

    const request = http.expectOne((req) => req.url === '/api/v1/analytics/products/search');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.get('q')).toBe('cha verde');
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('offset')).toBe('0');
    request.flush(searchResponse());

    expect(received?.data.map((item) => item.codigo)).toEqual([1001, 1002]);
  });

  it('getCatalogProducts faz GET em /api/v1/analytics/products e compartilha cache em memória', () => {
    let first: CatalogListResponse | undefined;
    let second: CatalogListResponse | undefined;

    service.getCatalogProducts().subscribe((res) => (first = res));
    service.getCatalogProducts().subscribe((res) => (second = res));

    const request = http.expectOne('/api/v1/analytics/products');
    expect(request.request.method).toBe('GET');
    expect(request.request.params.keys().length).toBe(0);
    request.flush(catalogResponse());

    expect(first?.data.length).toBe(4);
    expect(second?.data.length).toBe(4);
    expect(first).toEqual(second);

    // Nova subscrição posterior também reutiliza o cache sem disparar nova requisição
    let third: CatalogListResponse | undefined;
    service.getCatalogProducts().subscribe((res) => (third = res));
    http.expectNone('/api/v1/analytics/products');
    expect(third?.data.length).toBe(4);
  });

  it('getCatalogProducts invalida cache quando ocorre erro, permitindo retry', () => {
    let errorCount = 0;
    service.getCatalogProducts().subscribe({
      error: () => {
        errorCount += 1;
      },
    });

    http
      .expectOne('/api/v1/analytics/products')
      .flush({ detail: 'Erro temporário' }, { status: 503, statusText: 'Service Unavailable' });
    expect(errorCount).toBe(1);

    let recovered: CatalogListResponse | undefined;
    service.getCatalogProducts().subscribe((res) => (recovered = res));

    const retryReq = http.expectOne('/api/v1/analytics/products');
    retryReq.flush(catalogResponse());
    expect(recovered?.data.length).toBe(4);
  });

  it('getCatalogProducts({ includeSeasonality: true }) envia includeSeasonality=true, usa cache separado e invalida em erro', () => {
    let basicFirst: CatalogListResponse | undefined;
    let seasonalFirst: CatalogListResponse | undefined;
    let seasonalSecond: CatalogListResponse | undefined;

    service.getCatalogProducts().subscribe((res) => (basicFirst = res));
    http.expectOne('/api/v1/analytics/products').flush(catalogResponse());

    service.getCatalogProducts({ includeSeasonality: true }).subscribe((res) => (seasonalFirst = res));
    service.getCatalogProducts({ includeSeasonality: true }).subscribe((res) => (seasonalSecond = res));

    const seasonalReq = http.expectOne('/api/v1/analytics/products?includeSeasonality=true');
    expect(seasonalReq.request.method).toBe('GET');
    expect(seasonalReq.request.params.get('includeSeasonality')).toBe('true');
    seasonalReq.flush(
      catalogResponse([
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
      ]),
    );

    expect(basicFirst?.data.length).toBe(4);
    expect(seasonalFirst?.data.length).toBe(1);
    expect(seasonalFirst?.data[0].forca).toBe('FORTE');
    expect(seasonalSecond).toEqual(seasonalFirst);

    // Nova chamada básica continua usando cache básico sem nova requisição
    service.getCatalogProducts().subscribe();
    http.expectNone('/api/v1/analytics/products');
  });

  it('getCatalogProducts({ includeSeasonality: true }) invalida apenas o cache sazonal em erro para permitir retry', () => {
    service.getCatalogProducts().subscribe();
    http.expectOne('/api/v1/analytics/products').flush(catalogResponse());

    let errorCount = 0;
    service.getCatalogProducts({ includeSeasonality: true }).subscribe({
      error: () => {
        errorCount += 1;
      },
    });
    http
      .expectOne('/api/v1/analytics/products?includeSeasonality=true')
      .flush({ detail: 'Erro' }, { status: 503, statusText: 'Service Unavailable' });
    expect(errorCount).toBe(1);

    let recovered: CatalogListResponse | undefined;
    service.getCatalogProducts({ includeSeasonality: true }).subscribe((res) => (recovered = res));
    http
      .expectOne('/api/v1/analytics/products?includeSeasonality=true')
      .flush(catalogResponse());
    expect(recovered?.data.length).toBe(4);
  });

  it('não grava nada em localStorage/sessionStorage nem loga respostas', () => {
    const setItem = spyOn(Storage.prototype, 'setItem');
    const log = spyOn(console, 'log');

    service.getCustomerCrossSell(48213, { limit: 50, offset: 0 }).subscribe();
    http.expectOne((req) => req.url.endsWith('/customer/48213')).flush(customerResponse());

    expect(setItem).not.toHaveBeenCalled();
    expect(log).not.toHaveBeenCalled();
  });

  it('simulatePriceChange omite costPrice quando null/undefined e envia costPrice quando informado', () => {
    service.simulatePriceChange({ sku: 1001, priceChangePct: 5, costPrice: null }).subscribe();
    const reqWithoutCost = http.expectOne('/api/v1/analytics/elasticity/simulate');
    expect(reqWithoutCost.request.method).toBe('POST');
    expect(reqWithoutCost.request.body).toEqual({ sku: 1001, priceChangePct: 5 });
    reqWithoutCost.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });

    service.simulatePriceChange({ sku: 1001, priceChangePct: -10, costPrice: 13.5 }).subscribe();
    const reqWithCost = http.expectOne('/api/v1/analytics/elasticity/simulate');
    expect(reqWithCost.request.method).toBe('POST');
    expect(reqWithCost.request.body).toEqual({ sku: 1001, priceChangePct: -10, costPrice: 13.5 });
    reqWithCost.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });
  });

  it('simulatePriceChange omite currentPrice quando null/undefined e envia currentPrice quando informado', () => {
    // Arrange & Act — currentPrice null
    service.simulatePriceChange({ sku: 1001, priceChangePct: 5, currentPrice: null }).subscribe();
    const reqWithNull = http.expectOne('/api/v1/analytics/elasticity/simulate');

    // Assert — omite currentPrice
    expect(reqWithNull.request.method).toBe('POST');
    expect(reqWithNull.request.body).toEqual({ sku: 1001, priceChangePct: 5 });
    expect('currentPrice' in reqWithNull.request.body).toBeFalse();
    reqWithNull.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });

    // Arrange & Act — currentPrice undefined
    service.simulatePriceChange({ sku: 1001, priceChangePct: 5, currentPrice: undefined }).subscribe();
    const reqWithUndefined = http.expectOne('/api/v1/analytics/elasticity/simulate');

    // Assert — omite currentPrice
    expect(reqWithUndefined.request.body).toEqual({ sku: 1001, priceChangePct: 5 });
    expect('currentPrice' in reqWithUndefined.request.body).toBeFalse();
    reqWithUndefined.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });

    // Arrange & Act — currentPrice informado (com e sem costPrice)
    service.simulatePriceChange({ sku: 1001, priceChangePct: 10, currentPrice: 250 }).subscribe();
    const reqWithPrice = http.expectOne('/api/v1/analytics/elasticity/simulate');

    // Assert — envia currentPrice
    expect(reqWithPrice.request.method).toBe('POST');
    expect(reqWithPrice.request.body).toEqual({ sku: 1001, priceChangePct: 10, currentPrice: 250 });
    reqWithPrice.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });

    service
      .simulatePriceChange({ sku: 1001, priceChangePct: 10, currentPrice: 250, costPrice: 122.42 })
      .subscribe();
    const reqWithPriceAndCost = http.expectOne('/api/v1/analytics/elasticity/simulate');
    expect(reqWithPriceAndCost.request.body).toEqual({
      sku: 1001,
      priceChangePct: 10,
      currentPrice: 250,
      costPrice: 122.42,
    });
    reqWithPriceAndCost.flush({ data: {}, meta: { timestamp: '2026-11-16T12:00:00Z', version: '1.0.0' } });
  });
});
