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
  customerResponse,
  healthResponse,
  productResponse,
  searchResponse,
} from '../testing/cross-sell-test-data';
import { AnalyticsHealthResponse } from '../models/analytics.model';
import {
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

  it('não grava nada em localStorage/sessionStorage nem loga respostas', () => {
    const setItem = spyOn(Storage.prototype, 'setItem');
    const log = spyOn(console, 'log');

    service.getCustomerCrossSell(48213, { limit: 50, offset: 0 }).subscribe();
    http.expectOne((req) => req.url.endsWith('/customer/48213')).flush(customerResponse());

    expect(setItem).not.toHaveBeenCalled();
    expect(log).not.toHaveBeenCalled();
  });
});
