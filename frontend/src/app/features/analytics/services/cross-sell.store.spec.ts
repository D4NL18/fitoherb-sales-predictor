/**
 * T-14 — CrossSellStore (F-07): estado por modo com signals.
 *
 * Interface esperada (decisão do Tester, ver STATE_Tester.md):
 * - `mode()` ('product' | 'customer') e `setMode(mode)`
 * - `product` e `customer`, cada um com os signals `status()` ('idle' | 'loading' | 'success' | 'empty' | 'error'),
 *   `response()`, `error()` (AnalyticsApiError | null; null = falha genérica) e `pageRequest()`
 * - `searchProduct(sku)`, `searchCustomer(customerCode)` e `goToPage(page)` (1-based, no modo ativo,
 *   reaproveitando o último termo)
 * Sem storage (LGPD-09): customerCode só em memória.
 */
import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { CrossSellStore } from './cross-sell.store';
import {
  contractError,
  customerResponse,
  emptyCustomerResponse,
  emptyProductResponse,
  inactiveCustomerResponse,
  productResponse,
} from '../testing/cross-sell-test-data';

const PRODUCT_URL = '/api/v1/analytics/cross-sell/product/1001';
const CUSTOMER_URL = '/api/v1/analytics/cross-sell/customer/48213';

describe('CrossSellStore', () => {
  let store: CrossSellStore;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), CrossSellStore],
    });
    store = TestBed.inject(CrossSellStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function flushError(url: string, error: HttpErrorResponse): void {
    http.expectOne((req) => req.url === url).flush(error.error, { status: error.status, statusText: 'Error' });
  }

  it('começa em idle nos dois modos, no modo produto, com a página padrão', () => {
    expect(store.mode()).toBe('product');
    expect(store.product.status()).toBe('idle');
    expect(store.customer.status()).toBe('idle');
    expect(store.product.pageRequest()).toEqual({ limit: 50, offset: 0 });
    expect(store.product.response()).toBeNull();
    expect(store.product.error()).toBeNull();
  });

  it('produto: idle -> loading -> success', () => {
    store.searchProduct(1001);
    expect(store.product.status()).toBe('loading');

    http.expectOne((req) => req.url === PRODUCT_URL).flush(productResponse());

    expect(store.product.status()).toBe('success');
    expect(store.product.response()?.data.recomendacoes.length).toBe(2);
    expect(store.customer.status()).toBe('idle');
  });

  it('produto sem regras: empty', () => {
    store.searchProduct(4004);
    http.expectOne((req) => req.url.endsWith('/product/4004')).flush(emptyProductResponse());

    expect(store.product.status()).toBe('empty');
    expect(store.product.response()?.data.produto.descricao).toBe('MEL DE ABELHA 500G');
  });

  it('cliente: vazio com SEM_COMPRAS_RECENTES é distinto do vazio comum', () => {
    store.searchCustomer(48213);
    http.expectOne((req) => req.url === CUSTOMER_URL).flush(inactiveCustomerResponse());
    expect(store.customer.status()).toBe('empty');
    expect(store.customer.response()?.meta.motivoVazio).toBe('SEM_COMPRAS_RECENTES');

    store.searchCustomer(48213);
    http.expectOne((req) => req.url === CUSTOMER_URL).flush(emptyCustomerResponse());
    expect(store.customer.status()).toBe('empty');
    expect(store.customer.response()?.meta.motivoVazio).toBeNull();
  });

  it('erro do contrato: status error com o código', () => {
    store.searchProduct(1001);
    flushError(PRODUCT_URL, contractError('XSL-001'));

    expect(store.product.status()).toBe('error');
    expect(store.product.error()?.code).toBe('XSL-001');
  });

  it('falha técnica (500): status error com erro genérico (null)', () => {
    store.searchCustomer(48213);
    http.expectOne((req) => req.url === CUSTOMER_URL)
      .flush('Internal Server Error', { status: 500, statusText: 'Internal Server Error' });

    expect(store.customer.status()).toBe('error');
    expect(store.customer.error()).toBeNull();
  });

  it('nova busca reinicia a página e limpa o erro anterior', () => {
    store.searchProduct(1001);
    flushError(PRODUCT_URL, contractError('XSL-001'));

    store.searchProduct(1001);
    const request = http.expectOne((req) => req.url === PRODUCT_URL);
    expect(request.request.params.get('offset')).toBe('0');
    expect(store.product.error()).toBeNull();
    request.flush(productResponse());
  });

  it('goToPage reaproveita o último termo do modo ativo e calcula o offset', () => {
    store.searchProduct(1001);
    http.expectOne((req) => req.url === PRODUCT_URL).flush(productResponse({ totalItems: 120, totalPages: 3 }));

    store.goToPage(3);

    const request = http.expectOne((req) => req.url === PRODUCT_URL);
    expect(request.request.params.get('limit')).toBe('50');
    expect(request.request.params.get('offset')).toBe('100');
    expect(store.product.pageRequest()).toEqual({ limit: 50, offset: 100 });
    request.flush(productResponse({ page: 3, offset: 100, totalItems: 120, totalPages: 3 }));
    expect(store.product.status()).toBe('success');
  });

  it('cada modo guarda o próprio estado; goToPage age só no modo ativo', () => {
    store.searchProduct(1001);
    http.expectOne((req) => req.url === PRODUCT_URL).flush(productResponse({ totalItems: 120, totalPages: 3 }));

    store.setMode('customer');
    store.searchCustomer(48213);
    http.expectOne((req) => req.url === CUSTOMER_URL).flush(customerResponse({ totalItems: 60, totalPages: 2 }));

    store.goToPage(2);
    const request = http.expectOne((req) => req.url === CUSTOMER_URL);
    expect(request.request.params.get('offset')).toBe('50');
    request.flush(customerResponse({ page: 2, offset: 50, totalItems: 60, totalPages: 2 }));

    expect(store.product.status()).toBe('success');
    expect(store.product.pageRequest().offset).toBe(0);
  });

  it('goToPage sem busca anterior não faz requisição', () => {
    store.goToPage(2);
    http.expectNone(() => true);
    expect(store.product.status()).toBe('idle');
  });

  it('nada vai para localStorage/sessionStorage (LGPD-09)', () => {
    const setItem = spyOn(Storage.prototype, 'setItem');

    store.setMode('customer');
    store.searchCustomer(48213);
    http.expectOne((req) => req.url === CUSTOMER_URL).flush(customerResponse());

    expect(setItem).not.toHaveBeenCalled();
    expect(JSON.stringify({ ...localStorage })).not.toContain('48213');
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('48213');
  });
});
