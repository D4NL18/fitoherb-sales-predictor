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
  return {
    mode: signal<'product' | 'customer'>('product'),
    product: modeState<ProductCrossSellResponse>(),
    customer: modeState<CustomerCrossSellResponse>(),
    setMode: jasmine.createSpy('setMode'),
    searchProduct: jasmine.createSpy('searchProduct'),
    searchCustomer: jasmine.createSpy('searchCustomer'),
    goToPage: jasmine.createSpy('goToPage'),
  };
}

export type FakeCrossSellStore = ReturnType<typeof createFakeCrossSellStore>;
