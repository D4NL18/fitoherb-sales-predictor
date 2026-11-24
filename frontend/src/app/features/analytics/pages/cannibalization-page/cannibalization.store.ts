import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, takeUntil, tap, timer } from 'rxjs';
import {
  CannibalizationDetailResponse,
  CannibalizationMechanism,
  CannibalizationReportResponse,
  CannibalizationSortKey,
  CannibalizationVictimSummary,
  CannibalizationWindowDays,
  FilterOptionCount,
  TopCategoryHighlight,
} from '../../models/cannibalization.model';
import { CannibalizationService } from '../../services/cannibalization.service';
import {
  CannibalizationApiError,
  resolveCannibalizationErrorMessage,
  toCannibalizationApiError,
} from '../../utils/analytics-error';

export const SLOW_QUERY_NOTICE_MS = 4000;
export const DEFAULT_PAGE_SIZE = 20;
export const DEFAULT_WINDOW_DAYS: CannibalizationWindowDays = 90;
export const DEFAULT_SORT_KEY: CannibalizationSortKey = 'reduction-desc';

export interface MechanismVisualMeta {
  tagClass: 'tag-warning' | 'tag-info' | 'tag-positive';
  borderToken: string;
  symbol: string;
  label: string;
}

export const MECHANISM_VISUAL_META: Record<CannibalizationMechanism, MechanismVisualMeta> = {
  PRECO_MENOR_DESTROI_MARGEM: {
    tagClass: 'tag-warning',
    borderToken: 'var(--feedback-warning-bg)',
    symbol: '▲',
    label: 'Reajustar canibalizador',
  },
  PRECO_MENOR_MARGEM_PRESERVADA: {
    tagClass: 'tag-info',
    borderToken: 'var(--feedback-info-bg)',
    symbol: '▼',
    label: 'Ajustar preço da vítima',
  },
  MIGRACAO_POR_VALOR: {
    tagClass: 'tag-positive',
    borderToken: 'var(--feedback-positive-bg)',
    symbol: '↗',
    label: 'Migração por valor',
  },
};

export function normalizeFilterText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();
}

export function getReductionSeverityTag(reductionPct: number): 'tag-critical' | 'tag-warning' | 'tag-neutral' {
  if (reductionPct >= 30) return 'tag-critical';
  if (reductionPct >= 15) return 'tag-warning';
  return 'tag-neutral';
}

interface DetailRequest {
  sku: string;
  windowDays: CannibalizationWindowDays;
}

@Injectable()
export class CannibalizationStore {
  private readonly service = inject(CannibalizationService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly reportTrigger$ = new Subject<CannibalizationWindowDays>();
  private readonly detailTrigger$ = new Subject<DetailRequest | null>();
  private readonly slowTimerStop$ = new Subject<void>();

  readonly windowDays = signal<CannibalizationWindowDays>(DEFAULT_WINDOW_DAYS);
  readonly loading = signal<boolean>(false);
  readonly slowQuery = signal<boolean>(false);
  readonly apiError = signal<CannibalizationApiError | null>(null);
  readonly genericError = signal<string | null>(null);
  readonly reportResponse = signal<CannibalizationReportResponse | null>(null);

  readonly searchQuery = signal<string>('');
  readonly selectedSupplier = signal<string>('');
  readonly selectedCategory = signal<string>('');
  readonly sortBy = signal<CannibalizationSortKey>(DEFAULT_SORT_KEY);
  readonly currentPage = signal<number>(1);

  readonly selectedVictim = signal<CannibalizationVictimSummary | null>(null);
  readonly detailLoading = signal<boolean>(false);
  readonly detailError = signal<string | null>(null);
  readonly detailResponse = signal<CannibalizationDetailResponse | null>(null);

  readonly victims = computed(() => this.reportResponse()?.data.victims ?? []);
  readonly kpis = computed(() => this.reportResponse()?.data.kpis ?? null);
  readonly meta = computed(() => this.reportResponse()?.meta ?? null);

  readonly errorMessage = computed<string | null>(() => {
    const err = this.apiError();
    if (err) return resolveCannibalizationErrorMessage(err);
    return this.genericError();
  });

  readonly errorCode = computed<string | null>(() => this.apiError()?.code ?? null);

  readonly isPeriodEmpty = computed(
    () =>
      !this.loading() &&
      this.errorMessage() === null &&
      this.reportResponse() !== null &&
      this.victims().length === 0,
  );

  readonly topCategoryHighlight = computed<TopCategoryHighlight | null>(() => {
    const items = this.victims();
    if (items.length === 0) return null;

    const byCategory = new Map<string, { skuCount: number; total: number }>();
    for (const item of items) {
      const key = item.category?.trim() || 'Sem categoria';
      const entry = byCategory.get(key) ?? { skuCount: 0, total: 0 };
      entry.skuCount += 1;
      entry.total += item.cannibalizedRevenue;
      byCategory.set(key, entry);
    }

    let best: TopCategoryHighlight | null = null;
    for (const [name, stats] of byCategory.entries()) {
      if (!best || stats.total > best.totalCannibalizedRevenue) {
        best = {
          name,
          skuCount: stats.skuCount,
          totalCannibalizedRevenue: stats.total,
        };
      }
    }
    return best;
  });

  readonly supplierOptions = computed<FilterOptionCount[]>(() => {
    const counts = new Map<string, number>();
    for (const item of this.victims()) {
      const supplier = item.supplier?.trim() || 'Não informado';
      counts.set(supplier, (counts.get(supplier) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
  });

  readonly categoryOptions = computed<FilterOptionCount[]>(() => {
    const counts = new Map<string, number>();
    for (const item of this.victims()) {
      const category = item.category?.trim() || 'Sem categoria';
      counts.set(category, (counts.get(category) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'));
  });

  readonly filteredVictims = computed<CannibalizationVictimSummary[]>(() => {
    const items = this.victims();
    if (items.length === 0) return [];

    const supplier = this.selectedSupplier();
    const category = this.selectedCategory();
    const tokens = normalizeFilterText(this.searchQuery())
      .split(/\s+/)
      .filter((token) => token.length > 0);

    const filtered = items.filter((item) => {
      if (supplier && (item.supplier?.trim() || 'Não informado') !== supplier) {
        return false;
      }
      if (category && (item.category?.trim() || 'Sem categoria') !== category) {
        return false;
      }
      if (tokens.length === 0) {
        return true;
      }
      const haystack = buildVictimSearchHaystack(item);
      return tokens.every((token) => haystack.includes(token));
    });

    return sortVictims(filtered, this.sortBy());
  });

  readonly totalFilteredCount = computed(() => this.filteredVictims().length);

  readonly totalPages = computed(() => {
    const total = this.totalFilteredCount();
    return total === 0 ? 0 : Math.ceil(total / DEFAULT_PAGE_SIZE);
  });

  readonly safePage = computed(() => {
    const tp = this.totalPages();
    if (tp === 0) return 1;
    return Math.min(Math.max(1, this.currentPage()), tp);
  });

  readonly pageOffset = computed(() => (this.safePage() - 1) * DEFAULT_PAGE_SIZE);

  readonly pagedVictims = computed(() => {
    const start = this.pageOffset();
    return this.filteredVictims().slice(start, start + DEFAULT_PAGE_SIZE);
  });

  readonly hasActiveFilters = computed(
    () =>
      this.searchQuery().trim().length > 0 ||
      this.selectedSupplier() !== '' ||
      this.selectedCategory() !== '',
  );

  constructor() {
    this.reportTrigger$
      .pipe(
        tap((days) => {
          this.windowDays.set(days);
          this.loading.set(true);
          this.slowQuery.set(false);
          this.apiError.set(null);
          this.genericError.set(null);
          this.closeDrawer();
          this.startSlowQueryNotice();
        }),
        switchMap((days) =>
          this.service.getReport({ windowDays: days }).pipe(
            tap((response) => {
              this.stopSlowQueryNotice();
              this.reportResponse.set(response);
              this.reconcileActiveFilters(response.data.victims);
              this.currentPage.set(1);
              this.loading.set(false);
            }),
            catchError((err: unknown) => {
              this.stopSlowQueryNotice();
              this.reportResponse.set(null);
              const parsed = toCannibalizationApiError(err);
              if (parsed) {
                this.apiError.set(parsed);
                this.genericError.set(null);
              } else {
                this.apiError.set(null);
                this.genericError.set(resolveCannibalizationErrorMessage(null));
              }
              this.loading.set(false);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.detailTrigger$
      .pipe(
        switchMap((req) => {
          if (!req) {
            this.detailLoading.set(false);
            this.detailError.set(null);
            this.detailResponse.set(null);
            return EMPTY;
          }
          this.detailLoading.set(true);
          this.detailError.set(null);
          this.detailResponse.set(null);

          return this.service
            .getVictimDetail(req.sku, { windowDays: req.windowDays })
            .pipe(
              tap((response) => {
                this.detailResponse.set(response);
                this.detailLoading.set(false);
              }),
              catchError((err: unknown) => {
                const parsed = toCannibalizationApiError(err);
                this.detailError.set(resolveCannibalizationErrorMessage(parsed));
                this.detailLoading.set(false);
                return EMPTY;
              }),
            );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.destroyRef.onDestroy(() => {
      this.slowTimerStop$.next();
      this.slowTimerStop$.complete();
    });
  }

  loadReport(days: CannibalizationWindowDays = this.windowDays()): void {
    this.reportTrigger$.next(days);
  }

  setSearchQuery(value: string): void {
    this.searchQuery.set(value);
    this.currentPage.set(1);
  }

  setSupplier(value: string): void {
    this.selectedSupplier.set(value);
    this.currentPage.set(1);
  }

  setCategory(value: string): void {
    this.selectedCategory.set(value);
    this.currentPage.set(1);
  }

  setSortBy(sort: CannibalizationSortKey): void {
    this.sortBy.set(sort);
    this.currentPage.set(1);
  }

  setPage(page: number): void {
    this.currentPage.set(page);
  }

  clearFilters(): void {
    this.searchQuery.set('');
    this.selectedSupplier.set('');
    this.selectedCategory.set('');
    this.currentPage.set(1);
  }

  openDrawer(victim: CannibalizationVictimSummary): void {
    this.selectedVictim.set(victim);
    this.detailTrigger$.next({
      sku: victim.sku,
      windowDays: this.windowDays(),
    });
  }

  retryDrawerDetail(): void {
    const current = this.selectedVictim();
    if (!current) return;
    this.detailTrigger$.next({
      sku: current.sku,
      windowDays: this.windowDays(),
    });
  }

  closeDrawer(): void {
    this.selectedVictim.set(null);
    this.detailTrigger$.next(null);
  }

  private reconcileActiveFilters(items: CannibalizationVictimSummary[]): void {
    const currentSupplier = this.selectedSupplier();
    if (
      currentSupplier &&
      !items.some((item) => (item.supplier?.trim() || 'Não informado') === currentSupplier)
    ) {
      this.selectedSupplier.set('');
    }
    const currentCategory = this.selectedCategory();
    if (
      currentCategory &&
      !items.some((item) => (item.category?.trim() || 'Sem categoria') === currentCategory)
    ) {
      this.selectedCategory.set('');
    }
  }

  private startSlowQueryNotice(): void {
    this.slowTimerStop$.next();
    timer(SLOW_QUERY_NOTICE_MS)
      .pipe(
        takeUntil(this.slowTimerStop$),
        tap(() => {
          if (this.loading()) {
            this.slowQuery.set(true);
          }
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();
  }

  private stopSlowQueryNotice(): void {
    this.slowTimerStop$.next();
    this.slowQuery.set(false);
  }
}

function buildVictimSearchHaystack(item: CannibalizationVictimSummary): string {
  const parts: string[] = [
    item.sku,
    item.description,
    item.category,
    item.supplier,
  ];
  if (item.topCannibal) {
    parts.push(item.topCannibal.sku, item.topCannibal.description);
  }
  for (const cannibal of item.cannibalizers) {
    parts.push(cannibal.sku, cannibal.description);
  }
  return normalizeFilterText(parts.join(' '));
}

function sortVictims(
  items: CannibalizationVictimSummary[],
  sortBy: CannibalizationSortKey,
): CannibalizationVictimSummary[] {
  const sorted = [...items];
  sorted.sort((a, b) => {
    switch (sortBy) {
      case 'reduction-desc':
        return (
          b.cannibalizedRevenuePct - a.cannibalizedRevenuePct ||
          b.cannibalizedRevenue - a.cannibalizedRevenue
        );
      case 'reduction-asc':
        return (
          a.cannibalizedRevenuePct - b.cannibalizedRevenuePct ||
          a.cannibalizedRevenue - b.cannibalizedRevenue
        );
      case 'lost-desc':
        return b.cannibalizedRevenue - a.cannibalizedRevenue;
      case 'lost-asc':
        return a.cannibalizedRevenue - b.cannibalizedRevenue;
      case 'pre-rev-desc':
        return b.preRevenue - a.preRevenue;
      case 'pre-rev-asc':
        return a.preRevenue - b.preRevenue;
      case 'cur-rev-desc':
        return b.curRevenue - a.curRevenue;
      case 'cur-rev-asc':
        return a.curRevenue - b.curRevenue;
      case 'price-desc':
        return b.currentPrice - a.currentPrice;
      case 'price-asc':
        return a.currentPrice - b.currentPrice;
      case 'cannibals-desc':
        return (
          b.cannibalizerCount - a.cannibalizerCount ||
          b.cannibalizedRevenue - a.cannibalizedRevenue
        );
      case 'cannibals-asc':
        return (
          a.cannibalizerCount - b.cannibalizerCount ||
          a.cannibalizedRevenue - b.cannibalizedRevenue
        );
    }
  });
  return sorted;
}
