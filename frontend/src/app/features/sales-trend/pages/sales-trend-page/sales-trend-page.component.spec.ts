/**
 * Testes unitários para SalesTrendPageComponent (T-18, F-12).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of, throwError } from 'rxjs';
import { signal } from '@angular/core';
import { SalesTrendPageComponent } from './sales-trend-page.component';
import { SalesTrendService } from '../../services/sales-trend.service';
import { ViewportService } from '../../services/viewport.service';
import {
  ProductTrendResponse,
  SalesTrendCacheResponse,
  TrendCell,
} from '../../models/sales-trend.model';

function createZeroCell(meses: 1 | 3 | 6 | 12): TrendCell {
  return {
    meses,
    atual: 0,
    anterior: 0,
    variacaoPct: null,
    status: 'SEM_MOVIMENTO',
    baseParcial: false,
    baseBaixa: false,
    devolucaoLiquida: false,
    atualPorDia: null,
    anteriorPorDia: null,
  };
}

describe('SalesTrendPageComponent (F-12)', () => {
  let fixture: ComponentFixture<SalesTrendPageComponent>;
  let component: SalesTrendPageComponent;
  let serviceMock: jasmine.SpyObj<SalesTrendService>;
  const isCompactSignal = signal<boolean>(false);

  const mockResponse: ProductTrendResponse = {
    data: [
      {
        codigo: 1001,
        descricao: 'CHÁ VERDE 100G',
        fornecedor: 'LABORATÓRIO ALFA',
        janelas: [
          {
            meses: 1,
            atual: 30,
            anterior: 20,
            variacaoPct: 50.0,
            status: 'VARIACAO',
            baseParcial: false,
            baseBaixa: false,
            devolucaoLiquida: false,
            atualPorDia: null,
            anteriorPorDia: null,
          },
        ],
      },
    ],
    meta: {
      timestamp: '2026-11-10T12:00:00Z',
      version: '1.0.0',
      dataReferencia: '2026-11-09',
      ultimoDiaCoberto: '2026-11-08',
      mesBase: '2026-10',
      mesBasePadrao: '2026-10',
      mesBaseMinimo: '2025-01',
      mesBaseMaximo: '2026-11',
      mesBaseParcial: false,
      metrica: 'revenue',
      janelas: [
        {
          meses: 1,
          atual: { inicio: '2026-10-01', fim: '2026-10-31', diasJanela: 31, diasCobertos: 31 },
          anterior: { inicio: '2026-09-01', fim: '2026-09-30', diasJanela: 30, diasCobertos: 30 },
          semBase: false,
          baseParcial: false,
        },
      ],
      parametros: {
        limiteBaseBaixaQuantidade: 10,
        limiteBaseBaixaFaturamento: 500,
        coberturaMinimaAnterior: 0.5,
        buscaMinCaracteres: 2,
        buscaMinCaracteresNumerica: 1,
        buscaMaxCaracteres: 60,
        ttlCacheHoras: 6,
      },
      page: 1,
      limit: 50,
      offset: 0,
      totalItems: 1,
      totalPages: 1,
      agrupamento: 'product',
      visao: 'all',
      ordenacao: { janela: 1, sentido: 'desc' },
      totaisPorVisao: { todos: 1, maioresAltas: 1, maioresQuedas: 0, novos: 0 },
      total: {
        qtdProdutos: 1,
        janelas: [createZeroCell(1), createZeroCell(3), createZeroCell(6), createZeroCell(12)],
      },
    },
  };

  const mockHealthResponse: SalesTrendCacheResponse = {
    estado: 'QUENTE',
    dataReferencia: '2026-11-09',
    carregadoEm: '2026-11-10T06:00:00Z',
    idadeHoras: 4,
    expirado: false,
    duracaoUltimaCargaMs: 1200,
    carregando: false,
    contagens: null,
  };

  beforeEach(async () => {
    serviceMock = jasmine.createSpyObj<SalesTrendService>('SalesTrendService', [
      'getTrend',
      'getSupplierProducts',
      'getHealth',
    ]);
    serviceMock.getTrend.and.returnValue(of(mockResponse));
    serviceMock.getHealth.and.returnValue(of(mockHealthResponse));
    isCompactSignal.set(false);

    await TestBed.configureTestingModule({
      imports: [SalesTrendPageComponent],
      providers: [
        { provide: SalesTrendService, useValue: serviceMock },
        { provide: ViewportService, useValue: { isCompact: isCompactSignal } },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { queryParams: {} },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SalesTrendPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('inicializa sem landmark main aninhado e renderiza título e nota de catálogo ativo', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('main')).toBeNull();
    expect(el.querySelector('section.trend-page')).not.toBeNull();
    expect(el.querySelector('.hero-title')?.textContent).toContain('Tendência de Vendas');
    expect(el.querySelector('.hero-scope-note')?.textContent).toContain('produtos ativos do catálogo atual');
  });

  it('exibe a tabela no desktop e cartões no viewport compacto', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('app-trend-table')).not.toBeNull();
    expect(el.querySelector('app-trend-card-list')).toBeNull();

    isCompactSignal.set(true);
    fixture.detectChanges();
    expect(el.querySelector('app-trend-table')).toBeNull();
    expect(el.querySelector('app-trend-card-list')).not.toBeNull();
  });

  it('oculta tabela obsoleta e oferece recuperação de mês padrão em erro TND-002', () => {
    serviceMock.getTrend.and.returnValue(
      throwError(() => ({
        error: {
          error: { code: 'TND-002', message: 'Mês-base inválido' },
        },
      }))
    );

    component.store.setBaseMonth('2020-01');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('app-trend-table')).toBeNull();
    expect(el.querySelector('app-trend-error-banner')).not.toBeNull();
    expect(el.querySelector('.primary-recovery-btn')?.textContent?.trim()).toBe('Voltar para mês padrão');
  });

  it('adapta estado vazio quando offset ultrapassa totalItems vs sem movimentação', () => {
    const pastEndResponse: ProductTrendResponse = {
      ...mockResponse,
      data: [],
      meta: { ...mockResponse.meta, totalItems: 25, totalPages: 1, page: 3, offset: 100 },
    };
    serviceMock.getTrend.and.returnValue(of(pastEndResponse));

    component.store.setPage(3);
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.empty-title')?.textContent?.trim()).toBe('Página sem resultados');
    expect(el.querySelector('.empty-action-btn')?.textContent?.trim()).toBe('Voltar para a primeira página');

    const emptyNoFiltersResponse: ProductTrendResponse = {
      ...mockResponse,
      data: [],
      meta: { ...mockResponse.meta, totalItems: 0, totalPages: 0, page: 1, offset: 0 },
    };
    serviceMock.getTrend.and.returnValue(of(emptyNoFiltersResponse));

    component.store.setPage(1);
    fixture.detectChanges();
    expect(el.querySelector('.empty-title')?.textContent?.trim()).toBe('Sem movimentação no período');
    expect(el.querySelector('.empty-action-btn')).toBeNull();
  });
});
