import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SeasonalityService } from './seasonality.service';
import {
  SeasonalityRankingResponse,
  SeasonalityResponse,
} from '../models/seasonality.model';
import { ProductSearchResponse } from '../models/cross-sell.model';

describe('SeasonalityService', () => {
  let service: SeasonalityService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SeasonalityService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('deve buscar o diagnóstico de sazonalidade de um SKU preservando correlacaoYoy', () => {
    const mockResponse: SeasonalityResponse = {
      data: {
        produto: {
          codigo: 1042,
          descricao: 'EXTRATO DE PROPOLIS 30ML',
          fornecedor: 'APIS FLORA',
          estoque: 120,
          precoVenda: 28.5,
        },
        elegivel: true,
        forca: 'FORTE',
        motivoInsuficiencia: null,
        amplitude: 0.58,
        correlacaoYoy: 0.78,
        pico: {
          mesInicio: 5,
          mesFim: 7,
          nomePeriodo: 'Mai–Jul',
          indice: 1.42,
          confianca: 'ALTA',
        },
        vale: {
          mesInicio: 11,
          mesFim: 1,
          nomePeriodo: 'Nov–Jan',
          indice: 0.84,
          confianca: 'MEDIA',
        },
        serieMensal: [
          {
            mes: 5,
            nomeMes: 'Maio',
            indice: 1.4,
            confianca: 'ALTA',
            observacoesDisponiveis: 2,
            razao2025: 1.38,
            razao2026: 1.42,
            volumeLiquidoHistorico: 790,
            receitaLiquidaHistorica: 22515.0,
          },
        ],
      },
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
      },
    };

    let received: SeasonalityResponse | undefined;
    service.getSeasonality(1042).subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne('/api/v1/analytics/seasonality/1042');
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);

    expect(received?.data.correlacaoYoy).toBe(0.78);
    expect(received?.data.produto.codigo).toBe(1042);
  });

  it('deve buscar o ranking ordenado por mais sazonais com paginação explícita', () => {
    const mockRanking: SeasonalityRankingResponse = {
      data: [
        {
          sku: 1042,
          descricao: 'EXTRATO DE PROPOLIS 30ML',
          fornecedor: 'APIS FLORA',
          forca: 'FORTE',
          amplitude: 0.58,
          mesPico: 'Mai–Jul',
          mesVale: 'Nov–Jan',
          faturamentoTotal: 145000,
          motivoInsuficiencia: null,
        },
      ],
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
        page: 1,
        limit: 15,
        offset: 0,
        totalItems: 1,
        totalPages: 1,
      },
    };

    let received: SeasonalityRankingResponse | undefined;
    service.getRanking('most', { limit: 15, offset: 0 }).subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/seasonality/ranking' &&
        r.params.get('order') === 'most' &&
        r.params.get('limit') === '15' &&
        r.params.get('offset') === '0',
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockRanking);

    expect(received?.data.length).toBe(1);
    expect(received?.data[0].sku).toBe(1042);
  });

  it('deve buscar o ranking ordenado por menos mensuráveis com offset e limit configurados', () => {
    const mockRanking: SeasonalityRankingResponse = {
      data: [],
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
        page: 3,
        limit: 15,
        offset: 30,
        totalItems: 30,
        totalPages: 2,
      },
    };

    let received: SeasonalityRankingResponse | undefined;
    service.getRanking('least', { limit: 15, offset: 30 }).subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/seasonality/ranking' &&
        r.params.get('order') === 'least' &&
        r.params.get('limit') === '15' &&
        r.params.get('offset') === '30',
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockRanking);

    expect(received?.meta.offset).toBe(30);
    expect(received?.meta.limit).toBe(15);
  });

  it('deve enviar a consulta de produtos com trim no termo q e paginação padrão', () => {
    const mockSearch: ProductSearchResponse = {
      data: [
        {
          codigo: 1042,
          descricao: 'EXTRATO DE PROPOLIS 30ML',
          fornecedor: 'APIS FLORA',
        },
      ],
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
        page: 1,
        limit: 20,
        offset: 0,
        totalItems: 1,
        totalPages: 1,
      },
    };

    let received: ProductSearchResponse | undefined;
    service.searchProducts('  propolis  ').subscribe((res) => {
      received = res;
    });

    const req = httpMock.expectOne(
      (r) =>
        r.url === '/api/v1/analytics/products/search' &&
        r.params.get('q') === 'propolis' &&
        r.params.get('limit') === '20' &&
        r.params.get('offset') === '0',
    );
    expect(req.request.method).toBe('GET');
    req.flush(mockSearch);

    expect(received?.data.length).toBe(1);
    expect(received?.data[0].codigo).toBe(1042);
  });

  it('deve repassar erro HTTP sem mascarar falhas de rede ou contrato', () => {
    let statusReceived: number | undefined;
    service.getSeasonality(999999).subscribe({
      error: (err: { status: number }) => {
        statusReceived = err.status;
      },
    });

    const req = httpMock.expectOne('/api/v1/analytics/seasonality/999999');
    req.flush(
      { error: { code: 'SEA-001', message: 'Produto não encontrado', fields: [] } },
      { status: 404, statusText: 'Not Found' },
    );

    expect(statusReceived).toBe(404);
  });
});
