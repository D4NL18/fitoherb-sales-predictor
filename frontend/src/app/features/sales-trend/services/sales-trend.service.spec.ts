/**
 * Testes unitários para SalesTrendService (T-14).
 * Valida URLs, HttpParams, omissão de valores default e ausência de activeOnly.
 */
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { SalesTrendService } from './sales-trend.service';

describe('SalesTrendService (T-14)', () => {
  let service: SalesTrendService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [SalesTrendService],
    });
    service = TestBed.inject(SalesTrendService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('omite parâmetros que coincidem com os defaults do servidor em getTrend', () => {
    service
      .getTrend({
        metric: 'revenue',
        groupBy: 'product',
        sortWindow: 3,
        sortDir: 'desc',
        view: 'all',
        minVolume: 0,
        limit: 50,
        offset: 0,
      })
      .subscribe();

    const req = httpMock.expectOne('/api/v1/sales-trend');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().length).toBe(0);
    expect(req.request.params.has('activeOnly')).toBeFalse();
    req.flush({ data: [], meta: {} });
  });

  it('envia parâmetros não-default e não inclui activeOnly', () => {
    service
      .getTrend({
        baseMonth: '2026-10',
        metric: 'quantity',
        comparisonMode: 'average',
        groupBy: 'supplier',
        sortWindow: 1,
        sortDir: 'asc',
        view: 'rising',
        q: 'alfa',
        minVolume: 15.5,
        limit: 100,
        offset: 50,
      })
      .subscribe();

    const req = httpMock.expectOne((r) => r.url === '/api/v1/sales-trend');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('baseMonth')).toBe('2026-10');
    expect(req.request.params.get('metric')).toBe('quantity');
    expect(req.request.params.get('comparisonMode')).toBe('average');
    expect(req.request.params.get('groupBy')).toBe('supplier');
    expect(req.request.params.get('sortWindow')).toBe('1');
    expect(req.request.params.get('sortDir')).toBe('asc');
    expect(req.request.params.get('view')).toBe('rising');
    expect(req.request.params.get('q')).toBe('alfa');
    expect(req.request.params.get('minVolume')).toBe('15.5');
    expect(req.request.params.get('limit')).toBe('100');
    expect(req.request.params.get('offset')).toBe('50');
    expect(req.request.params.has('activeOnly')).toBeFalse();
    req.flush({ data: [], meta: {} });
  });

  it('chama getSupplierProducts com supplierKey obrigatória e limit default 20', () => {
    service
      .getSupplierProducts({
        supplierKey: 'f:laboratorio alfa',
      })
      .subscribe();

    const req = httpMock.expectOne((r) => r.url === '/api/v1/sales-trend/supplier-products');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('supplierKey')).toBe('f:laboratorio alfa');
    expect(req.request.params.has('limit')).toBeFalse(); // 20 é default, omitido
    req.flush({ data: [], meta: {} });
  });

  it('chama getHealth sem parâmetros', () => {
    service.getHealth().subscribe();

    const req = httpMock.expectOne('/api/v1/sales-trend/health');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().length).toBe(0);
    req.flush({ estado: 'QUENTE' });
  });
});
