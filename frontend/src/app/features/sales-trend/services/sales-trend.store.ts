/**
 * Store reativo para o estado da página de Tendência de Vendas (P-084, P-086, ADR-003 DA-08).
 * Gerencia signals de consulta, requisições canceláveis via switchMap, paginação, expansão de fornecedores e sync com URL.
 * Não utiliza localStorage nem sessionStorage.
 */
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Observable, Subject, Subscription, catchError, map, of, switchMap } from 'rxjs';
import {
  ProductTrendResponse,
  SalesTrendCacheResponse,
  SupplierDetailResponse,
  SupplierProductsQueryParams,
  SupplierTrendResponse,
  TrendComparisonMode,
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

interface MainTrigger {
  query: TrendQueryParams;
  generation: number;
}

type MainResult =
  | { ok: true; res: ProductTrendResponse | SupplierTrendResponse; generation: number }
  | { ok: false; error: TrendErrorPayload | null; generation: number };

interface DetailTrigger {
  req: SupplierProductsQueryParams;
  generation: number;
}

type DetailResult =
  | { ok: true; res: SupplierDetailResponse; generation: number }
  | { ok: false; error: TrendErrorPayload | null; generation: number };

const DEFAULT_QUERY: TrendQueryParams = {
  metric: 'revenue',
  groupBy: 'product',
  comparisonMode: 'point',
  sortWindow: 3,
  sortDir: 'desc',
  view: 'all',
  minVolume: 0,
  limit: 50,
  offset: 0,
};

const MAX_MIN_VOLUME = 1_000_000_000;
const MAX_SEARCH_LENGTH = 60;

@Injectable()
export class SalesTrendStore {
  private readonly service = inject(SalesTrendService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  // Signals do estado principal
  readonly query = signal<TrendQueryParams>({ ...DEFAULT_QUERY });
  readonly status = signal<'idle' | 'loading' | 'success' | 'empty' | 'error'>('idle');
  readonly productResponse = signal<ProductTrendResponse | null>(null);
  readonly supplierResponse = signal<SupplierTrendResponse | null>(null);
  readonly error = signal<TrendErrorPayload | null>(null);
  readonly cacheStatus = signal<SalesTrendCacheResponse | null>(null);
  readonly isSlowLoading = signal<boolean>(false);
  readonly noticeMessage = signal<string | null>(null);

  // Expansões de fornecedor: Map imutável supplierKey -> SupplierDetailState
  readonly expandedSuppliers = signal<Map<string, SupplierDetailState>>(new Map());

  private mainGeneration = 0;
  private readonly mainRequestTrigger$ = new Subject<MainTrigger>();
  private healthSub: Subscription | null = null;
  private slowLoadingTimer: ReturnType<typeof setTimeout> | null = null;

  private readonly detailChannels = new Map<
    string,
    { trigger$: Subject<DetailTrigger>; sub: Subscription }
  >();
  private readonly detailGenerations = new Map<string, number>();

  constructor() {
    this.mainRequestTrigger$
      .pipe(
        switchMap(
          ({ query, generation }): Observable<MainResult> =>
            this.service.getTrend(query).pipe(
              map((res): MainResult => ({ ok: true, res, generation })),
              catchError((err): Observable<MainResult> => of({ ok: false, error: toTrendApiError(err), generation }))
            )
        ),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe((outcome) => {
        if (outcome.generation !== this.mainGeneration) {
          return;
        }
        this.clearSlowLoadingTimer();

        if (!outcome.ok) {
          this.status.set('error');
          this.error.set(outcome.error);
          return;
        }

        const res = outcome.res;
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
      });

    this.destroyRef.onDestroy(() => {
      this.clearSlowLoadingTimer();
      this.healthSub?.unsubscribe();
      this.healthSub = null;
      this.cancelAllSupplierRequests();
      this.mainRequestTrigger$.complete();
    });
  }

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
   * Dispara a requisição principal da lista com cancelamento via switchMap e proteção por geração.
   */
  loadTrend(): void {
    const generation = ++this.mainGeneration;
    this.clearExpandedSuppliers();
    this.status.set('loading');
    this.error.set(null);
    this.startSlowLoadingTimer();

    const q = this.query();
    this.syncUrl();
    this.mainRequestTrigger$.next({ query: q, generation });
  }

  setGroupBy(groupBy: TrendGroupBy): void {
    const curr = this.query();
    if (curr.groupBy === groupBy) {
      return;
    }

    const hadFilters = Boolean(curr.q || (curr.minVolume ?? 0) > 0 || (curr.view && curr.view !== 'all'));
    if (hadFilters) {
      this.noticeMessage.set('A busca e os filtros foram limpos ao alternar o agrupamento.');
    }

    this.query.update((c) => ({
      ...c,
      groupBy,
      view: 'all',
      minVolume: 0,
      q: undefined,
      offset: 0,
    }));
    this.loadTrend();
  }

  setMetric(metric: TrendMetric): void {
    const curr = this.query();
    if (curr.metric === metric) {
      return;
    }

    if ((curr.minVolume ?? 0) > 0) {
      this.noticeMessage.set('O corte mínimo foi zerado porque a métrica de análise mudou.');
    }

    this.query.update((c) => ({
      ...c,
      metric,
      minVolume: 0,
      offset: 0,
    }));
    this.loadTrend();
  }

  setComparisonMode(comparisonMode: TrendComparisonMode): void {
    if (this.query().comparisonMode === comparisonMode) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      comparisonMode,
      offset: 0,
    }));
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

    if (curr.sortWindow === window && curr.sortDir === newDir) {
      return;
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
    const normalized =
      q && q.trim().length > 0
        ? q.trim().replace(/\s+/g, ' ').slice(0, MAX_SEARCH_LENGTH).trim()
        : undefined;
    if (normalized && !/^\d+$/.test(normalized) && normalized.length < 2) {
      return;
    }
    if (this.query().q === normalized) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      q: normalized,
      offset: 0,
    }));
    this.loadTrend();
  }

  setMinVolume(minVolume: number): void {
    const valid = Number.isFinite(minVolume)
      ? Math.min(MAX_MIN_VOLUME, Math.max(0, minVolume))
      : 0;
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
    const newOffset = Math.max(0, (Math.max(1, page) - 1) * limit);
    if (this.query().offset === newOffset) {
      return;
    }
    this.query.update((curr) => ({
      ...curr,
      offset: newOffset,
    }));
    this.loadTrend();
  }

  clearFilters(): void {
    this.noticeMessage.set(null);
    this.query.update((curr) => ({
      ...curr,
      q: undefined,
      minVolume: 0,
      view: 'all',
      offset: 0,
    }));
    this.loadTrend();
  }

  resetToDefaultMonth(): void {
    const defaultMonth = this.currentMeta?.mesBasePadrao;
    this.noticeMessage.set(null);
    this.query.update((curr) => ({
      ...curr,
      baseMonth: defaultMonth,
      offset: 0,
    }));
    this.loadTrend();
  }

  dismissNotice(): void {
    this.noticeMessage.set(null);
  }

  toggleSupplier(supplierKey: string): void {
    const map = new Map(this.expandedSuppliers());
    if (map.has(supplierKey)) {
      this.disposeSupplierChannel(supplierKey);
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
    const nextSortBy = paramsOverride?.sortBy ?? curr.sortBy;
    const nextSortWindow = paramsOverride?.sortWindow ?? curr.sortWindow;
    const nextSortDir = paramsOverride?.sortDir ?? curr.sortDir;
    const nextQ = paramsOverride?.q !== undefined ? paramsOverride.q : curr.q;
    const nextLimit = paramsOverride?.limit ?? curr.limit;
    const nextOffset = paramsOverride?.offset ?? curr.offset;
    const nextPage = Math.floor(nextOffset / Math.max(1, nextLimit)) + 1;

    const req: SupplierProductsQueryParams = {
      supplierKey,
      baseMonth,
      metric,
      comparisonMode: this.query().comparisonMode,
      sortBy: nextSortBy,
      sortWindow: nextSortWindow,
      sortDir: nextSortDir,
      q: nextQ,
      limit: nextLimit,
      offset: nextOffset,
    };

    const nextGeneration = (this.detailGenerations.get(supplierKey) ?? 0) + 1;
    this.detailGenerations.set(supplierKey, nextGeneration);

    map.set(supplierKey, {
      ...curr,
      status: 'loading',
      error: null,
      sortBy: nextSortBy,
      sortWindow: nextSortWindow,
      sortDir: nextSortDir,
      q: nextQ,
      limit: nextLimit,
      offset: nextOffset,
      page: nextPage,
    });
    this.expandedSuppliers.set(map);

    const channel = this.getOrCreateDetailChannel(supplierKey);
    channel.trigger$.next({ req, generation: nextGeneration });
  }

  setSupplierPage(supplierKey: string, page: number): void {
    const item = this.expandedSuppliers().get(supplierKey);
    if (!item) {
      return;
    }
    const newOffset = Math.max(0, (Math.max(1, page) - 1) * item.limit);
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
    this.healthSub?.unsubscribe();
    this.healthSub = this.service
      .getHealth()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => this.cacheStatus.set(res),
        error: () => {},
      });
  }

  retry(): void {
    this.loadTrend();
  }

  private getOrCreateDetailChannel(supplierKey: string): {
    trigger$: Subject<DetailTrigger>;
    sub: Subscription;
  } {
    const existing = this.detailChannels.get(supplierKey);
    if (existing) {
      return existing;
    }

    const trigger$ = new Subject<DetailTrigger>();
    const sub = trigger$
      .pipe(
        switchMap(
          ({ req, generation }): Observable<DetailResult> =>
            this.service.getSupplierProducts(req).pipe(
              map((res): DetailResult => ({ ok: true, res, generation })),
              catchError((err): Observable<DetailResult> => of({ ok: false, error: toTrendApiError(err), generation }))
            )
        )
      )
      .subscribe((outcome) => {
        if (this.detailGenerations.get(supplierKey) !== outcome.generation) {
          return;
        }

        const nextMap = new Map(this.expandedSuppliers());
        const item = nextMap.get(supplierKey);
        if (!item) {
          return;
        }

        if (!outcome.ok) {
          nextMap.set(supplierKey, {
            ...item,
            status: 'error',
            error: outcome.error,
          });
          this.expandedSuppliers.set(nextMap);
          return;
        }

        const res = outcome.res;

        // C-50: se a data de referência divergir do snapshot da lista principal, recarrega tudo
        if (this.currentMeta && res.meta.dataReferencia !== this.currentMeta.dataReferencia) {
          this.noticeMessage.set(
            'Os dados foram atualizados em segundo plano e a listagem foi recarregada.'
          );
          this.loadTrend();
          return;
        }

        nextMap.set(supplierKey, {
          ...item,
          data: res,
          status: !res.data || res.data.length === 0 ? 'empty' : 'success',
          error: null,
          page: res.meta.page,
          offset: res.meta.offset,
          limit: res.meta.limit,
          sortBy: res.meta.ordenacao?.por ?? item.sortBy,
          sortWindow: res.meta.ordenacao?.janela ?? item.sortWindow,
          sortDir: res.meta.ordenacao?.sentido ?? item.sortDir,
        });
        this.expandedSuppliers.set(nextMap);
      });

    const channel = { trigger$, sub };
    this.detailChannels.set(supplierKey, channel);
    return channel;
  }

  private disposeSupplierChannel(supplierKey: string): void {
    this.detailGenerations.set(supplierKey, (this.detailGenerations.get(supplierKey) ?? 0) + 1);
    const channel = this.detailChannels.get(supplierKey);
    if (channel) {
      channel.sub.unsubscribe();
      channel.trigger$.complete();
      this.detailChannels.delete(supplierKey);
    }
  }

  private cancelAllSupplierRequests(): void {
    for (const key of Array.from(this.detailChannels.keys())) {
      this.disposeSupplierChannel(key);
    }
    this.detailGenerations.clear();
  }

  private clearExpandedSuppliers(): void {
    this.cancelAllSupplierRequests();
    if (this.expandedSuppliers().size > 0) {
      this.expandedSuppliers.set(new Map());
    }
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
