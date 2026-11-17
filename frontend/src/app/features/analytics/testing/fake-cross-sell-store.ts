/**
 * Store falso para specs de componente (T-15): mesma forma pública de `CrossSellStore`,
 * com signals graváveis e métodos espionados pelo Jasmine.
 */
import { signal } from '@angular/core';
import { AnalyticsApiError, PageRequest } from '../models/analytics.model';
import { CustomerCrossSellResponse, ProductCrossSellResponse } from '../models/cross-sell.model';

export type FakeStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

function modeState<TResponse>() {
  return {
    status: signal<FakeStatus>('idle'),
    response: signal<TResponse | null>(null),
    error: signal<AnalyticsApiError | null>(null),
    pageRequest: signal<PageRequest>({ limit: 50, offset: 0 }),
  };
}

export function createFakeCrossSellStore() {
  const product = modeState<ProductCrossSellResponse>();
  const customer = modeState<CustomerCrossSellResponse>();

  return {
    mode: signal<'product' | 'customer'>('product'),
    product,
    customer,
    setMode: jasmine.createSpy('setMode'),
    searchProduct: jasmine.createSpy('searchProduct'),
    clearProduct: jasmine.createSpy('clearProduct').and.callFake(() => {
      product.status.set('idle');
      product.response.set(null);
      product.error.set(null);
      product.pageRequest.set({ limit: 50, offset: 0 });
    }),
    searchCustomer: jasmine.createSpy('searchCustomer'),
    goToPage: jasmine.createSpy('goToPage'),
  };
}

export type FakeCrossSellStore = ReturnType<typeof createFakeCrossSellStore>;
