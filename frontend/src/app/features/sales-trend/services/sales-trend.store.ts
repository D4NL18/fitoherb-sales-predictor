/**
 * Store reativo para o estado da página de Tendência de Vendas (P-084, P-086, ADR-003 DA-08).
 * Gerencia signals de consulta, requisições canceláveis, paginação, expansão de fornecedores e sync com URL.
 * Não utiliza localStorage nem sessionStorage.
 */
import { Injectable, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Subject, Subscription } from 'rxjs';
import {
  ProductTrendResponse,
  SalesTrendCacheResponse,
  SupplierDetailResponse,
  SupplierProductsQueryParams,
  SupplierTrendResponse,
  TrendErrorCode,
  TrendErrorPayload,
  TrendGroupBy,
  TrendListMeta,
  TrendMetric,
  TrendQueryParams,
  TrendSortBy,
  TrendSortDir,
  TrendSortWindow,
  TrendView,
} from '../models/sales-trend.model';
import { SalesTrendService } from './sales-trend.service';
import { stateToQueryParams } from '../utils/trend-url';
import { toTrendApiError } from '../utils/trend-error';

export interface SupplierDetailState {
  supplierKey: string;
  status: 'loading' | 'success' | 'empty' | 'error';
  data: SupplierDetailResponse | null;
  error: TrendErrorPayload | null;
  page: number;
  limit: number;
  offset: number;
  sortBy: TrendSortBy;
  sortDir: TrendSortDir;
  sortWindow: TrendSortWindow;
  q?: string;
}

const DEFAULT_QUERY: TrendQueryParams = {
  metric: 'revenue',
  groupBy: 'product',
  sortWindow: 3,
  sortDir: 'desc',
  view: 'all',
  minVolume: 0,
  limit: 50,
  offset: 0,
};

@Injectable()
export class SalesTrendStore {
  private readonly service = inject(SalesTrendService);
  private readonly router = inject(Router);

  // Signals do estado principal
  readonly query = signal<TrendQueryParams>({ ...DEFAULT_QUERY });
  readonly status = signal<'idle' | 'loading' | 'success' | 'empty' | 'error'>('idle');
  readonly productResponse = signal<ProductTrendResponse | null>(null);
  readonly supplierResponse = signal<SupplierTrendResponse | null>(null);
  readonly error = signal<TrendErrorPayload | null>(null);
  readonly cacheStatus = signal<SalesTrendCacheResponse | null>(null);
  readonly isSlowLoading = signal<boolean>(false);

  // Expansões de fornecedor: Map imutável supplierKey -> SupplierDetailState
  readonly expandedSuppliers = signal<Map<string, SupplierDetailState>>(new Map());

  private mainRequestSub: Subscription | null = null;
  private slowLoadingTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly cancel$ = new Subject<void>();

  get currentMeta(): TrendListMeta | null {
    if (this.query().groupBy === 'supplier') {
      return this.supplierResponse()?.meta ?? null;
    }
    return this.productResponse()?.meta ?? null;
  }

  /**
   * Inicializa o estado da consulta com parâmetros vindos da URL e dispara a carga inicial.
   */
  init(paramsFromUrl: TrendQueryParams): void {
    const merged: TrendQueryParams = {
      ...DEFAULT_QUERY,
      ...paramsFromUrl,
    };
    this.query.set(merged);
    this.checkHealth();
    this.loadTrend();
  }

  /**
   * Dispara a requisição principal da lista com cancelamento de requisições em trânsito.
   */
  loadTrend(): void {
    if (this.mainRequestSub) {
      this.mainRequestSub.unsubscribe();
      this.mainRequestSub = null;
    }

    this.status.set('loading');
    this.error.set(null);
    this.startSlowLoadingTimer();

    const q = this.query();
    this.syncUrl();

    this.mainRequestSub = this.service.getTrend(q).subscribe({
      next: (res) => {
        this.clearSlowLoadingTimer();
        const isEmpty = !res.data || res.data.length === 0;
        this.status.set(isEmpty ? 'empty' : 'success');

        if (res.meta.agrupamento === 'supplier') {
          this.supplierResponse.set(res as SupplierTrendResponse);
          this.productResponse.set(null);
        } else {
          this.productResponse.set(res as ProductTrendResponse);
          this.supplierResponse.set(null);
        }

        // Se o mês base não estava fixado no estado, adota o mês base retornado no meta
        if (!this.query().baseMonth && res.meta.mesBase) {
          this.query.update((curr) => ({ ...curr, baseMonth: res.meta.mesBase }));
        }
      },
      error: (err) => {
        this.clearSlowLoadingTimer();
        this.status.set('error');
        const parsed = toTrendApiError(err);
        this.error.set(parsed);
      },
    });
  }

  setGroupBy(groupBy: TrendGroupBy): void {
    if (this.query().groupBy === groupBy) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      groupBy,
      view: 'all',
      minVolume: 0,
      q: undefined,
      offset: 0,
    }));
    this.expandedSuppliers.set(new Map());
    this.loadTrend();
  }

  setMetric(metric: TrendMetric): void {
    if (this.query().metric === metric) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      metric,
      minVolume: 0,
      offset: 0,
    }));
    this.expandedSuppliers.set(new Map());
    this.loadTrend();
  }

  setBaseMonth(baseMonth: string | undefined): void {
    if (this.query().baseMonth === baseMonth) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      baseMonth,
      offset: 0,
    }));
    this.expandedSuppliers.set(new Map());
    this.loadTrend();
  }

  setSort(window: TrendSortWindow, dir?: TrendSortDir): void {
    const curr = this.query();
    let newDir = dir;
    if (!newDir) {
      if (curr.sortWindow === window) {
        newDir = curr.sortDir === 'desc' ? 'asc' : 'desc';
      } else {
        newDir = curr.view === 'falling' ? 'asc' : 'desc';
      }
    }

    this.query.update((c) => ({
      ...c,
      sortWindow: window,
      sortDir: newDir,
      offset: 0,
    }));
    this.loadTrend();
  }

  setView(view: TrendView): void {
    if (this.query().view === view) {
      return;
    }
    const sortDir: TrendSortDir = view === 'falling' ? 'asc' : 'desc';
    this.query.update((curr) => ({
      ...curr,
      view,
      sortDir,
      offset: 0,
    }));
    this.loadTrend();
  }

  setSearch(q: string | undefined): void {
    const cleanQ = q && q.trim().length > 0 ? q.trim() : undefined;
    if (this.query().q === cleanQ) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      q: cleanQ,
      offset: 0,
    }));
    this.loadTrend();
  }

  setMinVolume(minVolume: number): void {
    const valid = Math.max(0, minVolume);
    if (this.query().minVolume === valid) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      minVolume: valid,
      offset: 0,
    }));
    this.loadTrend();
  }

  setPage(page: number): void {
    const limit = this.query().limit || 50;
    const newOffset = Math.max(0, (page - 1) * limit);
    if (this.query().offset === newOffset) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      offset: newOffset,
    }));
    this.loadTrend();
  }

  toggleSupplier(supplierKey: string): void {
    const map = new Map(this.expandedSuppliers());
    if (map.has(supplierKey)) {
      map.delete(supplierKey);
      this.expandedSuppliers.set(map);
      return;
    }

    const initial: SupplierDetailState = {
      supplierKey,
      status: 'loading',
      data: null,
      error: null,
      page: 1,
      limit: 20,
      offset: 0,
      sortBy: 'contribution',
      sortDir: 'desc',
      sortWindow: this.query().sortWindow || 3,
    };
    map.set(supplierKey, initial);
    this.expandedSuppliers.set(map);
    this.loadSupplierProducts(supplierKey);
  }

  loadSupplierProducts(supplierKey: string, paramsOverride?: Partial<SupplierProductsQueryParams>): void {
    const map = new Map(this.expandedSuppliers());
    const curr = map.get(supplierKey);
    if (!curr) {
      return;
    }

    const baseMonth = this.currentMeta?.mesBase || this.query().baseMonth;
    const metric = this.query().metric || 'revenue';

    const req: SupplierProductsQueryParams = {
      supplierKey,
      baseMonth,
      metric,
      sortBy: paramsOverride?.sortBy ?? curr.sortBy,
      sortWindow: paramsOverride?.sortWindow ?? curr.sortWindow,
      sortDir: paramsOverride?.sortDir ?? curr.sortDir,
      q: paramsOverride?.q ?? curr.q,
      limit: paramsOverride?.limit ?? curr.limit,
      offset: paramsOverride?.offset ?? curr.offset,
    };

    curr.status = 'loading';
    this.expandedSuppliers.set(new Map(map));

    this.service.getSupplierProducts(req).subscribe({
      next: (res) => {
        const nextMap = new Map(this.expandedSuppliers());
        const item = nextMap.get(supplierKey);
        if (!item) {
          return;
        }

        // C-50: se a data de referência divergir do snapshot da lista principal, recarrega tudo
        if (this.currentMeta && res.meta.dataReferencia !== this.currentMeta.dataReferencia) {
          this.loadTrend();
          return;
        }

        item.data = res;
        item.status = !res.data || res.data.length === 0 ? 'empty' : 'success';
        item.error = null;
        item.page = res.meta.page;
        item.offset = res.meta.offset;
        item.limit = res.meta.limit;
        nextMap.set(supplierKey, { ...item });
        this.expandedSuppliers.set(nextMap);
      },
      error: (err) => {
        const nextMap = new Map(this.expandedSuppliers());
        const item = nextMap.get(supplierKey);
        if (item) {
          item.status = 'error';
          item.error = toTrendApiError(err);
          nextMap.set(supplierKey, { ...item });
          this.expandedSuppliers.set(nextMap);
        }
      },
    });
  }

  setSupplierPage(supplierKey: string, page: number): void {
    const item = this.expandedSuppliers().get(supplierKey);
    if (!item) {
      return;
    }
    const newOffset = Math.max(0, (page - 1) * item.limit);
    this.loadSupplierProducts(supplierKey, { offset: newOffset });
  }

  setSupplierSort(supplierKey: string, sortBy: TrendSortBy): void {
    const item = this.expandedSuppliers().get(supplierKey);
    if (!item) {
      return;
    }
    let newDir: TrendSortDir = 'desc';
    if (item.sortBy === sortBy) {
      newDir = item.sortDir === 'desc' ? 'asc' : 'desc';
    }
    this.loadSupplierProducts(supplierKey, { sortBy, sortDir: newDir, offset: 0 });
  }

  checkHealth(): void {
    this.service.getHealth().subscribe({
      next: (res) => this.cacheStatus.set(res),
      error: () => {},
    });
  }

  retry(): void {
    this.loadTrend();
  }

  private syncUrl(): void {
    const queryParams = stateToQueryParams(this.query());
    this.router.navigate([], {
      queryParams,
      replaceUrl: true,
    });
  }

  private startSlowLoadingTimer(): void {
    this.clearSlowLoadingTimer();
    this.isSlowLoading.set(false);
    this.slowLoadingTimer = setTimeout(() => {
      if (this.status() === 'loading') {
        this.isSlowLoading.set(true);
      }
    }, 4000);
  }

  private clearSlowLoadingTimer(): void {
    if (this.slowLoadingTimer) {
      clearTimeout(this.slowLoadingTimer);
      this.slowLoadingTimer = null;
    }
    this.isSlowLoading.set(false);
  }
}
