/**
 * Testes unitários de SeasonalityPageComponent (P-106 a P-116).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { SeasonalityPageComponent } from './seasonality-page.component';
import { SeasonalityService } from '../../services/seasonality.service';
import {
  SeasonalityRankingResponse,
  SeasonalityResponse,
} from '../../models/seasonality.model';

describe('SeasonalityPageComponent', () => {
  let component: SeasonalityPageComponent;
  let fixture: ComponentFixture<SeasonalityPageComponent>;
  let seasonalityServiceSpy: jasmine.SpyObj<SeasonalityService>;

  const mockSeasonalityResponse: SeasonalityResponse = {
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
      correlacaoYoY: 0.78,
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

  const mockRankingResponse: SeasonalityRankingResponse = {
    data: [
      {
        sku: 1042,
        descricao: 'EXTRATO DE PROPOLIS 30ML',
        fornecedor: 'APIS FLORA',
        forca: 'FORTE',
        amplitude: 0.58,
        mesPico: 'Mai–Jul',
        mesVale: 'Nov–Jan',
        faturamentoTotal: 185400.0,
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

  beforeEach(async () => {
    seasonalityServiceSpy = jasmine.createSpyObj('SeasonalityService', [
      'getSeasonality',
      'getRanking',
      'searchProducts',
    ]);

    seasonalityServiceSpy.getRanking.and.returnValue(of(mockRankingResponse));
    seasonalityServiceSpy.getSeasonality.and.returnValue(of(mockSeasonalityResponse));
    seasonalityServiceSpy.searchProducts.and.returnValue(
      of({
        data: [{ codigo: 1042, descricao: 'EXTRATO DE PROPOLIS 30ML', fornecedor: 'APIS FLORA' }],
        meta: {
          timestamp: '2026-11-12T12:00:00Z',
          version: '1.0.0',
          dataReferencia: '2026-10-31',
          page: 1,
          limit: 10,
          offset: 0,
          totalItems: 1,
          totalPages: 1,
        },
      })
    );

    await TestBed.configureTestingModule({
      imports: [SeasonalityPageComponent],
      providers: [
        { provide: SeasonalityService, useValue: seasonalityServiceSpy },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SeasonalityPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('deve criar o componente e carregar o ranking inicial na inicialização', () => {
    expect(component).toBeTruthy();
    expect(seasonalityServiceSpy.getRanking).toHaveBeenCalledWith('most', { limit: 20, offset: 0 });
  });

  it('deve carregar o produto selecionado por SKU', () => {
    component['selectProductBySku'](1042);
    expect(seasonalityServiceSpy.getSeasonality).toHaveBeenCalledWith(1042);
    expect(component['productData']()?.produto.descricao).toBe('EXTRATO DE PROPOLIS 30ML');
    expect(component['productData']()?.pico.nomePeriodo).toBe('Mai–Jul');
  });

  it('deve tratar erro no carregamento do produto', () => {
    seasonalityServiceSpy.getSeasonality.and.returnValue(
      throwError(() => ({ error: { error: { message: 'Produto não encontrado.' } } }))
    );
    component['selectProductBySku'](9999);
    expect(component['productData']()).toBeNull();
    expect(component['productError']()).toBe('Produto não encontrado.');
  });

  it('deve alternar a ordem do ranking para least e recarregar', () => {
    component['setRankingOrder']('least');
    expect(component['activeRankingOrder']()).toBe('least');
    expect(seasonalityServiceSpy.getRanking).toHaveBeenCalledWith('least', { limit: 20, offset: 0 });
  });
});
