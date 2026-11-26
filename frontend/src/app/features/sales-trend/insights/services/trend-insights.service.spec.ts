import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { fakeAsync, tick } from '@angular/core/testing';
import { TrendInsightsService, GENERATE_TIMEOUT_MS } from './trend-insights.service';

describe('TrendInsightsService', () => {
  let service: TrendInsightsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(TrendInsightsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('GET envia metric, window, baseMonth e comparisonMode no path do SKU', () => {
    service
      .getProductInsight(1007, { metric: 'quantity', window: 6, baseMonth: '2026-10', comparisonMode: 'average' })
      .subscribe();
    const req = http.expectOne((r) => r.url === '/api/v1/sales-trend/insights/product/1007');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('metric')).toBe('quantity');
    expect(req.request.params.get('window')).toBe('6');
    expect(req.request.params.get('baseMonth')).toBe('2026-10');
    expect(req.request.params.get('comparisonMode')).toBe('average');
    req.flush({ data: {}, meta: {} });
  });

  it('GET retorna o envelope sem mexer nos dados', () => {
    let got: unknown;
    service.getProductInsight(1, {}).subscribe((r) => (got = r));
    http.expectOne((r) => r.url.endsWith('/product/1')).flush({ data: { a: 1 }, meta: { b: 2 } });
    expect(got).toEqual({ data: { a: 1 }, meta: { b: 2 } });
  });

  it('POST /generate usa corpo com force=false por padrão', () => {
    service.generateProductInsight(1007, { metric: 'revenue', window: 3, baseMonth: '2026-10' }).subscribe();
    const req = http.expectOne('/api/v1/sales-trend/insights/product/1007/generate');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ metric: 'revenue', window: 3, baseMonth: '2026-10', force: false });
    req.flush({ data: {}, meta: {} });
  });

  it('POST envia force=true somente quando pedido', () => {
    service.generateProductInsight(1, { window: 1 }, { force: true }).subscribe();
    const req = http.expectOne('/api/v1/sales-trend/insights/product/1/generate');
    expect(req.request.body.force).toBeTrue();
    expect(req.request.body.deep).toBeUndefined();
    req.flush({ data: {}, meta: {} });
  });

  it('POST expira em 150 s com TimeoutError', fakeAsync(() => {
    let err: unknown;
    service.generateProductInsight(1, {}).subscribe({ error: (e) => (err = e) });
    http.expectOne((r) => r.url.endsWith('/generate'));
    tick(GENERATE_TIMEOUT_MS);
    expect((err as Error).name).toBe('TimeoutError');
    expect(GENERATE_TIMEOUT_MS).toBe(150_000);
  }));
});
