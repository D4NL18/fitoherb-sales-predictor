/**
 * Testes unitários de SeasonalityService (contrato 1.0.0; P-106 a P-116).
 */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SeasonalityService } from './seasonality.service';
import {
  SeasonalityRankingResponse,
  SeasonalityResponse,
} from '../models/seasonality.model';

describe('SeasonalityService', () => {
  let service: SeasonalityService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SeasonalityService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('getSeasonality faz GET em /api/v1/analytics/seasonality/{sku}', () => {
    let received: SeasonalityResponse | undefined;
    service.getSeasonality(1042).subscribe((res) => (received = res));

    const req = http.expectOne('/api/v1/analytics/seasonality/1042');
    expect(req.request.method).toBe('GET');

    const mockResponse: SeasonalityResponse = {
      data: {
        produto: {
          codigo: 1042,
          descricao: 'PRODUTO TESTE',
          fornecedor: 'FORNECEDOR TESTE',
          estoque: 100,
          precoVenda: 25.0,
        },
        elegivel: true,
        forca: 'FORTE',
        motivoInsuficiencia: null,
        amplitude: 0.5,
        correlacaoYoY: 0.8,
        pico: {
          mesInicio: 3,
          mesFim: 3,
          nomePeriodo: 'Março',
          indice: 1.5,
          confianca: 'ALTA',
        },
        vale: {
          mesInicio: 9,
          mesFim: 9,
          nomePeriodo: 'Setembro',
          indice: 0.7,
          confianca: 'ALTA',
        },
        serieMensal: [],
      },
      meta: {
        timestamp: '2026-11-12T12:00:00Z',
        version: '1.0.0',
        dataReferencia: '2026-10-31',
      },
    };

    req.flush(mockResponse);
    expect(received?.data.produto.codigo).toBe(1042);
    expect(received?.data.forca).toBe('FORTE');
  });

  it('getRanking envia order, limit e offset como HttpParams', () => {
    let received: SeasonalityRankingResponse | undefined;
    service.getRanking('most', { limit: 20, offset: 0 }).subscribe((res) => (received = res));

    const req = http.expectOne('/api/v1/analytics/seasonality/ranking?order=most&limit=20&offset=0');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('order')).toBe('most');
    expect(req.request.params.get('limit')).toBe('20');
    expect(req.request.params.get('offset')).toBe('0');

    const mockRankingResponse: SeasonalityRankingResponse = {
      data: [
        {
          sku: 1042,
          descricao: 'PRODUTO TESTE',
          fornecedor: 'FORNECEDOR',
          forca: 'FORTE',
          amplitude: 0.5,
          mesPico: 'Março',
          mesVale: 'Setembro',
          faturamentoTotal: 50000.0,
          motivoInsuficiencia: null,
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

    req.flush(mockRankingResponse);
    expect(received?.data.length).toBe(1);
    expect(received?.data[0].sku).toBe(1042);
  });
});
