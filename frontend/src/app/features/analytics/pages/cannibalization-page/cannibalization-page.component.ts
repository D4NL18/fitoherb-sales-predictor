import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { ErrorBannerComponent } from '../../components/error-banner/error-banner.component';
import { ResultStateComponent } from '../../components/result-state/result-state.component';
import {
  CANNIBALIZATION_WINDOW_OPTIONS,
  CannibalizationSortKey,
  CannibalizationWindowDays,
} from '../../models/cannibalization.model';
import { PtDatePipe } from '../../pipes/pt-br-format.pipes';
import { ResultStateAction, ResultStateView } from '../../utils/cross-sell-view';
import {
  CannibalizationStore,
  DEFAULT_SORT_KEY,
  DEFAULT_WINDOW_DAYS,
} from './cannibalization.store';
import { CannibalizationKpiStripComponent } from './components/cannibalization-kpi-strip/cannibalization-kpi-strip.component';
import {
  CannibalizationReportTableComponent,
  VictimSelectEvent,
} from './components/cannibalization-report-table/cannibalization-report-table.component';
import { CannibalizationSkeletonComponent } from './components/cannibalization-skeleton/cannibalization-skeleton.component';
import { PriceEquilibriumDrawerComponent } from './components/price-equilibrium-drawer/price-equilibrium-drawer.component';

const MAX_FILTER_PARAM_LEN = 80;

const VALID_SORT_KEYS: readonly CannibalizationSortKey[] = [
  'reduction-desc',
  'reduction-asc',
  'lost-desc',
  'lost-asc',
  'pre-rev-desc',
  'pre-rev-asc',
  'cur-rev-desc',
  'cur-rev-asc',
  'price-desc',
  'price-asc',
  'cannibals-desc',
  'cannibals-asc',
];

@Component({
  selector: 'app-cannibalization-page',
  standalone: true,
  imports: [
    PtDatePipe,
    ErrorBannerComponent,
    ResultStateComponent,
    CannibalizationKpiStripComponent,
    CannibalizationReportTableComponent,
    CannibalizationSkeletonComponent,
    PriceEquilibriumDrawerComponent,
  ],
  providers: [CannibalizationStore],
  templateUrl: './cannibalization-page.component.html',
  styleUrl: './cannibalization-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CannibalizationPageComponent implements OnInit {
  protected readonly store = inject(CannibalizationStore);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly periodOptions = CANNIBALIZATION_WINDOW_OPTIONS;
  protected readonly drawerTriggerEl = signal<HTMLElement | null>(null);

  protected readonly drawerOpen = computed(() => this.store.selectedVictim() !== null);

  protected readonly emptyPeriodView = computed<ResultStateView>(() => {
    const days = this.store.windowDays();
    const canExpand = days < 90;
    return {
      icon: 'check',
      title: `Nenhum produto canibalizado nos últimos ${days} dias`,
      text: canExpand
        ? `Não foi detectada queda de faturamento atribuída à migração de clientes nos últimos ${days} dias. Amplie para 90 dias para avaliar uma janela mais longa.`
        : 'Não foi detectada queda de faturamento atribuída à migração de clientes nos últimos 90 dias com os critérios mínimos de relevância.',
      actionLabel: canExpand ? 'Analisar últimos 90 dias' : 'Atualizar relatório',
      action: 'retry',
      tone: 'neutral',
    };
  });

  private pendingOpenSku: string | null = null;

  constructor() {
    // Q-D2 (F7): abre o drawer de equilíbrio da vítima indicada em ?abrir={sku}, uma única vez, após o relatório carregar.
    effect(() => {
      const victims = this.store.victims();
      if (this.pendingOpenSku === null || this.store.loading() || victims.length === 0) return;
      const target = victims.find((v) => v.sku === this.pendingOpenSku);
      this.pendingOpenSku = null;
      if (target) {
        untracked(() => {
          this.drawerTriggerEl.set(null);
          this.store.openDrawer(target);
        });
      }
    });
  }

  ngOnInit(): void {
    const params = this.route.snapshot.queryParamMap;
    const initialWindow = parseWindowDays(params.get('periodo'));
    const initialSearch = sanitizeTextParam(params.get('busca'));
    const initialSupplier = sanitizeTextParam(params.get('fornecedor'));
    const initialCategory = sanitizeTextParam(params.get('categoria'));
    const initialSort = parseSortKey(params.get('ordenar'));
    this.pendingOpenSku = parseSkuParam(params.get('abrir'));

    if (initialSearch) this.store.setSearchQuery(initialSearch);
    if (initialSupplier) this.store.setSupplier(initialSupplier);
    if (initialCategory) this.store.setCategory(initialCategory);
    if (initialSort !== DEFAULT_SORT_KEY) this.store.setSortBy(initialSort);

    this.store.loadReport(initialWindow);
  }

  protected onSelectPeriod(days: CannibalizationWindowDays): void {
    if (this.store.loading() || this.store.windowDays() === days) return;
    this.store.loadReport(days);
    this.syncUrlParams();
  }

  protected onSearchChange(value: string): void {
    this.store.setSearchQuery(value);
    this.syncUrlParams();
  }

  protected onSupplierChange(value: string): void {
    this.store.setSupplier(value);
    this.syncUrlParams();
  }

  protected onCategoryChange(value: string): void {
    this.store.setCategory(value);
    this.syncUrlParams();
  }

  protected onSortChange(sort: CannibalizationSortKey): void {
    this.store.setSortBy(sort);
    this.syncUrlParams();
  }

  protected onClearFilters(): void {
    this.store.clearFilters();
    this.syncUrlParams();
  }

  protected onPageChange(page: number): void {
    this.store.setPage(page);
  }

  protected onSelectVictim(event: VictimSelectEvent): void {
    this.drawerTriggerEl.set(event.triggerEl);
    this.store.openDrawer(event.victim);
  }

  protected onCloseDrawer(): void {
    this.store.closeDrawer();
  }

  protected onRetryDetail(): void {
    this.store.retryDrawerDetail();
  }

  protected onRetry(): void {
    this.store.loadReport(this.store.windowDays());
  }

  protected onEmptyPeriodAction(_action: ResultStateAction): void {
    if (this.store.windowDays() < 90) {
      this.store.loadReport(90);
      this.syncUrlParams();
      return;
    }
    this.store.loadReport(this.store.windowDays());
  }

  private syncUrlParams(): void {
    const queryParams: Params = {};
    const days = this.store.windowDays();
    const search = this.store.searchQuery().trim();
    const supplier = this.store.selectedSupplier().trim();
    const category = this.store.selectedCategory().trim();
    const sort = this.store.sortBy();

    if (days !== DEFAULT_WINDOW_DAYS) {
      queryParams['periodo'] = String(days);
    }
    if (search) {
      queryParams['busca'] = search.slice(0, MAX_FILTER_PARAM_LEN);
    }
    if (supplier) {
      queryParams['fornecedor'] = supplier.slice(0, MAX_FILTER_PARAM_LEN);
    }
    if (category) {
      queryParams['categoria'] = category.slice(0, MAX_FILTER_PARAM_LEN);
    }
    if (sort !== DEFAULT_SORT_KEY) {
      queryParams['ordenar'] = sort;
    }

    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }
}

function parseWindowDays(raw: string | null): CannibalizationWindowDays {
  if (raw === '30') return 30;
  if (raw === '60') return 60;
  if (raw === '90') return 90;
  return DEFAULT_WINDOW_DAYS;
}

function sanitizeTextParam(raw: string | null): string {
  if (!raw) return '';
  return raw.trim().slice(0, MAX_FILTER_PARAM_LEN);
}

function parseSortKey(raw: string | null): CannibalizationSortKey {
  if (raw && (VALID_SORT_KEYS as readonly string[]).includes(raw)) {
    return raw as CannibalizationSortKey;
  }
  return DEFAULT_SORT_KEY;
}

function parseSkuParam(raw: string | null): string | null {
  if (!raw) return null;
  return /^\d{1,20}$/.test(raw.trim()) ? raw.trim() : null;
}
