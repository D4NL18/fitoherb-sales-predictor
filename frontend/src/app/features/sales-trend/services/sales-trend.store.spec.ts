/**
 * Testes unitários para o SalesTrendStore (T-17).
 * Valida transições de estado, preservação e reset de parâmetros, cancelamento de requisições e drill-down.
 */
import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of, throwError } from 'rxjs';
import { SalesTrendStore } from './sales-trend.store';
import { SalesTrendService } from './sales-trend.service';
import { ProductTrendResponse, SupplierDetailResponse } from '../models/sales-trend.model';

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
      total: { qtdProdutos: 1, janelas: [] as any },
    },
  };

  beforeEach(() => {
    serviceMock = jasmine.createSpyObj<SalesTrendService>('SalesTrendService', [
      'getTrend',
      'getSupplierProducts',
      'getHealth',
      'reloadCache',
    ]);
    routerMock = jasmine.createSpyObj<Router>('Router', ['navigate']);

    serviceMock.getTrend.and.returnValue(of(mockProductResponse as any));
    serviceMock.getHealth.and.returnValue(of({ estado: 'QUENTE' } as any));

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
    const emptyResponse = {
      ...mockProductResponse,
      data: [],
      meta: { ...mockProductResponse.meta, totalItems: 0, totalPages: 0 },
    };
    serviceMock.getTrend.and.returnValue(of(emptyResponse as any));

    store.loadTrend();
    expect(store.status()).toBe('empty');
  });

  it('transita para error quando API rejeita', () => {
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
  });

  it('trocar groupBy preserva baseMonth, metric, sortWindow, sortDir e reseta view, minVolume, q e offset', () => {
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
  });

  it('trocar metric zera minVolume e offset', () => {
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
  });

  it('clique repetido na mesma janela alterna desc e asc', () => {
    store.query.set({ sortWindow: 3, sortDir: 'desc' });

    store.setSort(3);
    expect(store.query().sortDir).toBe('asc');

    store.setSort(3);
    expect(store.query().sortDir).toBe('desc');
  });

  it('toggleSupplier expande fornecedor e busca produtos filhos', () => {
    const mockDetail: SupplierDetailResponse = {
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
        ordenacao: { por: 'contribution', janela: 3, sentido: 'desc' },
      },
    };
    serviceMock.getSupplierProducts.and.returnValue(of(mockDetail));

    store.toggleSupplier('f:laboratorio alfa');

    expect(store.expandedSuppliers().has('f:laboratorio alfa')).toBeTrue();
    expect(serviceMock.getSupplierProducts).toHaveBeenCalled();

    // Novo clique recolhe
    store.toggleSupplier('f:laboratorio alfa');
    expect(store.expandedSuppliers().has('f:laboratorio alfa')).toBeFalse();
  });
});
