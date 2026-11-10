/**
 * Testes unitários para SalesTrendPageComponent (T-18, F-12).
 */
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { signal } from '@angular/core';
import { SalesTrendPageComponent } from './sales-trend-page.component';
import { SalesTrendService } from '../../services/sales-trend.service';
import { ViewportService } from '../../services/viewport.service';
import { ProductTrendResponse } from '../../models/sales-trend.model';

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
      parametros: {} as any,
      page: 1,
      limit: 50,
      offset: 0,
      totalItems: 1,
      totalPages: 1,
      agrupamento: 'product',
      visao: 'all',
      ordenacao: { janela: 1, sentido: 'desc' },
      totaisPorVisao: { todos: 1, maioresAltas: 1, maioresQuedas: 0, novos: 0 },
      total: { qtdProdutos: 1, janelas: [] as any },
    },
  };

  beforeEach(async () => {
    serviceMock = jasmine.createSpyObj<SalesTrendService>('SalesTrendService', [
      'getTrend',
      'getSupplierProducts',
      'getHealth',
    ]);
    serviceMock.getTrend.and.returnValue(of(mockResponse as any));
    serviceMock.getHealth.and.returnValue(of({ estado: 'QUENTE' } as any));
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

  it('inicializa e renderiza o título da página e nota de catálogo ativo', () => {
    const el = fixture.nativeElement;
    expect(el.querySelector('.hero-title').textContent).toContain('Tendência de Vendas');
    expect(el.querySelector('.hero-scope-note').textContent).toContain('produtos ativos do catálogo atual');
  });

  it('exibe a tabela quando há dados carregados com sucesso', () => {
    const el = fixture.nativeElement;
    expect(el.querySelector('app-trend-table')).not.toBeNull();
  });
});
