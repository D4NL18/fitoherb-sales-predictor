/**
 * Testes unitários para o SalesTrendStore (T-17).
 * Valida transições de estado, preservação e reset de parâmetros, cancelamento via switchMap e drill-down.
 */
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { Subject, of, throwError } from 'rxjs';
import { SalesTrendStore } from './sales-trend.store';
import { SalesTrendService } from './sales-trend.service';
import {
  ProductTrendResponse,
  SalesTrendCacheResponse,
  SupplierDetailResponse,
  TrendCell,
} from '../models/sales-trend.model';

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

describe('SalesTrendStore (T-17)', () => {
  let store: SalesTrendStore;
  let serviceMock: jasmine.SpyObj<SalesTrendService>;
  let routerMock: jasmine.SpyObj<Router>;

  const mockProductResponse: ProductTrendResponse = {
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
          {
            meses: 3,
            atual: 70,
            anterior: 60,
            variacaoPct: 16.7,
            status: 'VARIACAO',
            baseParcial: false,
            baseBaixa: false,
            devolucaoLiquida: false,
            atualPorDia: null,
            anteriorPorDia: null,
          },
          {
            meses: 6,
            atual: 130,
            anterior: 120,
            variacaoPct: 8.3,
            status: 'VARIACAO',
            baseParcial: false,
            baseBaixa: false,
            devolucaoLiquida: false,
            atualPorDia: null,
            anteriorPorDia: null,
          },
          {
            meses: 12,
            atual: 250,
            anterior: 98,
            variacaoPct: 108.3,
            status: 'VARIACAO',
            baseParcial: true,
            baseBaixa: false,
            devolucaoLiquida: false,
            atualPorDia: 0.6849,
            anteriorPorDia: 0.3289,
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
      janelas: [],
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
      ordenacao: { janela: 3, sentido: 'desc' },
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

  beforeEach(() => {
    serviceMock = jasmine.createSpyObj<SalesTrendService>('SalesTrendService', [
      'getTrend',
      'getSupplierProducts',
      'getHealth',
      'reloadCache',
    ]);
    routerMock = jasmine.createSpyObj<Router>('Router', ['navigate']);

    serviceMock.getTrend.and.returnValue(of(mockProductResponse));
    serviceMock.getHealth.and.returnValue(of(mockHealthResponse));

    TestBed.configureTestingModule({
      providers: [
        SalesTrendStore,
        { provide: SalesTrendService, useValue: serviceMock },
        { provide: Router, useValue: routerMock },
      ],
    });

    store = TestBed.inject(SalesTrendStore);
  });

  it('inicia no estado idle e carrega dados com transição para success', () => {
    expect(store.status()).toBe('idle');
    store.loadTrend();
    expect(store.status()).toBe('success');
    expect(store.productResponse()).toEqual(mockProductResponse);
    expect(routerMock.navigate).toHaveBeenCalled();
  });

  it('transita para empty quando data vem vazia', () => {
    const emptyResponse: ProductTrendResponse = {
      ...mockProductResponse,
      data: [],
      meta: { ...mockProductResponse.meta, totalItems: 0, totalPages: 0 },
    };
    serviceMock.getTrend.and.returnValue(of(emptyResponse));

    store.loadTrend();
    expect(store.status()).toBe('empty');
  });

  it('transita para error quando API rejeita e continua aceitando retry via switchMap', () => {
    serviceMock.getTrend.and.returnValue(
      throwError(() => ({
        error: {
          error: { code: 'TND-004', message: 'Indisponível' },
        },
      }))
    );

    store.loadTrend();
    expect(store.status()).toBe('error');
    expect(store.error()?.code).toBe('TND-004');

    serviceMock.getTrend.and.returnValue(of(mockProductResponse));
    store.retry();
    expect(store.status()).toBe('success');
    expect(store.error()).toBeNull();
  });

  it('cancela requisição principal anterior via switchMap quando uma nova chamada ocorre antes da resposta', () => {
    const first$ = new Subject<ProductTrendResponse>();
    const second$ = new Subject<ProductTrendResponse>();
    serviceMock.getTrend.and.returnValues(first$.asObservable(), second$.asObservable());

    store.setSearch('camomila');
    store.setSearch('erva doce');

    const newerResponse: ProductTrendResponse = {
      ...mockProductResponse,
      data: [{ ...mockProductResponse.data[0], codigo: 2002, descricao: 'ERVA DOCE 100G' }],
    };

    second$.next(newerResponse);
    first$.next(mockProductResponse);

    expect(store.status()).toBe('success');
    expect(store.productResponse()?.data[0].codigo).toBe(2002);
  });

  it('trocar groupBy preserva baseMonth, metric, sortWindow, sortDir, reseta filtros e emite aviso', () => {
    store.query.set({
      baseMonth: '2026-09',
      metric: 'quantity',
      groupBy: 'product',
      sortWindow: 1,
      sortDir: 'asc',
      view: 'rising',
      minVolume: 20,
      q: 'teste',
      limit: 50,
      offset: 100,
    });

    store.setGroupBy('supplier');

    const q = store.query();
    expect(q.groupBy).toBe('supplier');
    expect(q.baseMonth).toBe('2026-09');
    expect(q.metric).toBe('quantity');
    expect(q.sortWindow).toBe(1);
    expect(q.sortDir).toBe('asc');
    expect(q.view).toBe('all');
    expect(q.minVolume).toBe(0);
    expect(q.q).toBeUndefined();
    expect(q.offset).toBe(0);
    expect(store.noticeMessage()).toContain('filtros');
  });

  it('trocar metric zera minVolume, offset e emite aviso quando havia corte ativo', () => {
    store.query.set({
      metric: 'revenue',
      minVolume: 500,
      offset: 50,
    });

    store.setMetric('quantity');

    const q = store.query();
    expect(q.metric).toBe('quantity');
    expect(q.minVolume).toBe(0);
    expect(q.offset).toBe(0);
    expect(store.noticeMessage()).toContain('corte mínimo');
  });

  it('clearFilters reseta q, minVolume, view e offset em uma única chamada', () => {
    store.query.set({
      metric: 'revenue',
      groupBy: 'product',
      q: 'cha',
      minVolume: 150,
      view: 'rising',
      offset: 100,
    });
    serviceMock.getTrend.calls.reset();

    store.clearFilters();

    expect(serviceMock.getTrend).toHaveBeenCalledTimes(1);
    expect(store.query().q).toBeUndefined();
    expect(store.query().minVolume).toBe(0);
    expect(store.query().view).toBe('all');
    expect(store.query().offset).toBe(0);
  });

  it('clique repetido na mesma janela alterna desc e asc', () => {
    store.query.set({ sortWindow: 3, sortDir: 'desc' });

    store.setSort(3);
    expect(store.query().sortDir).toBe('asc');

    store.setSort(3);
    expect(store.query().sortDir).toBe('desc');
  });

  it('toggleSupplier expande fornecedor, busca produtos filhos e atualiza ordenação com switchMap', () => {
    const buildDetail = (
      por: 'contribution' | 'variation',
      sentido: 'asc' | 'desc'
    ): SupplierDetailResponse => ({
      data: [],
      meta: {
        ...mockProductResponse.meta,
        fornecedor: {
          fornecedor: 'LABORATÓRIO ALFA',
          fornecedorChave: 'f:laboratorio alfa',
          semFornecedor: false,
          qtdProdutos: 1,
          janelas: [],
        },
        ordenacao: { por, janela: 3, sentido },
      },
    });

    const firstDetail$ = new Subject<SupplierDetailResponse>();
    const secondDetail$ = new Subject<SupplierDetailResponse>();
    const thirdDetail$ = new Subject<SupplierDetailResponse>();

    serviceMock.getSupplierProducts.and.returnValues(
      of(buildDetail('contribution', 'desc')),
      firstDetail$.asObservable(),
      secondDetail$.asObservable(),
      thirdDetail$.asObservable()
    );

    store.toggleSupplier('f:laboratorio alfa');

    expect(store.expandedSuppliers().has('f:laboratorio alfa')).toBeTrue();
    expect(serviceMock.getSupplierProducts).toHaveBeenCalled();

    // Troca ordenação para variation e clica novamente antes da primeira resposta
    store.setSupplierSort('f:laboratorio alfa', 'variation');
    expect(store.expandedSuppliers().get('f:laboratorio alfa')?.sortBy).toBe('variation');
    expect(store.expandedSuppliers().get('f:laboratorio alfa')?.sortDir).toBe('desc');

    store.setSupplierSort('f:laboratorio alfa', 'variation');
    expect(store.expandedSuppliers().get('f:laboratorio alfa')?.sortDir).toBe('asc');

    secondDetail$.next(buildDetail('variation', 'asc'));
    firstDetail$.next(buildDetail('variation', 'desc'));

    expect(store.expandedSuppliers().get('f:laboratorio alfa')?.sortBy).toBe('variation');
    expect(store.expandedSuppliers().get('f:laboratorio alfa')?.sortDir).toBe('asc');

    // Novo clique recolhe e impede respostas tardias
    store.toggleSupplier('f:laboratorio alfa');
    thirdDetail$.next(buildDetail('variation', 'desc'));
    expect(store.expandedSuppliers().has('f:laboratorio alfa')).toBeFalse();
  });
});
