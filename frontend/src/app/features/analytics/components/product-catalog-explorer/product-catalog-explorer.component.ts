import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { CatalogProductItem } from '../../models/cross-sell.model';
import { SeasonalityReason, SeasonalityStrength } from '../../models/seasonality.model';
import { BrlPipe, PtDecimalPipe } from '../../pipes/pt-br-format.pipes';
import { AnalyticsService } from '../../services/analytics.service';
import {
  CatalogSortKey,
  CatalogStockFilter,
  SeasonalityStrengthFilter,
  extractSupplierOptions,
  filterAndSortCatalog,
  groupCatalogRows,
  normalizeSearchText,
  tokenizeSearchQuery,
} from '../../utils/smart-product-search';
import { ErrorBannerComponent } from '../error-banner/error-banner.component';
import { ListPagerComponent } from '../list-pager/list-pager.component';

const DEFAULT_CATALOG_PAGE_SIZE = 50;
type SortableColumn =
  | 'sku'
  | 'name'
  | 'supplier'
  | 'stock'
  | 'price'
  | 'strength'
  | 'amplitude'
  | 'revenue';

let nextCatalogId = 0;

@Component({
  selector: 'app-product-catalog-explorer',
  standalone: true,
  imports: [NgTemplateOutlet, BrlPipe, PtDecimalPipe, ErrorBannerComponent, ListPagerComponent],
  templateUrl: './product-catalog-explorer.component.html',
  styleUrl: './product-catalog-explorer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:click)': 'onDocumentClick($event)',
  },
})
export class ProductCatalogExplorerComponent implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly loadTrigger$ = new Subject<void>();
  private readonly supplierCombobox = viewChild<ElementRef<HTMLElement>>('supplierCombobox');
  private readonly supplierSearchInput = viewChild<ElementRef<HTMLInputElement>>('supplierSearchEl');
  private readonly supplierTrigger = viewChild<ElementRef<HTMLButtonElement>>('supplierTrigger');

  readonly title = input<string>('Catálogo de Produtos');
  readonly subtitle = input<string>(
    'Explore os produtos em ordem alfabética por fornecedor ou busque por nome, palavras soltas, fornecedor ou código SKU.',
  );
  readonly actionLabel = input<string>('Selecionar');
  readonly selectedSku = input<number | null>(null);
  readonly showSeasonality = input<boolean>(false);
  readonly productSelect = output<CatalogProductItem>();

  protected readonly ids = createCatalogIds();
  protected readonly skeletonRows = [1, 2, 3, 4, 5, 6];

  protected readonly catalog = signal<CatalogProductItem[]>([]);
  protected readonly isLoading = signal<boolean>(true);
  protected readonly loadError = signal<string | null>(null);

  protected readonly searchQuery = signal<string>('');
  protected readonly selectedSupplier = signal<string>('');
  protected readonly supplierDropdownOpen = signal<boolean>(false);
  protected readonly supplierSearchQuery = signal<string>('');
  protected readonly supplierActiveIndex = signal<number>(-1);
  protected readonly stockFilter = signal<CatalogStockFilter>('all');
  protected readonly strengthFilter = signal<SeasonalityStrengthFilter>('all');
  protected readonly sortBy = signal<CatalogSortKey>('supplier-asc');
  protected readonly userOverrodeSort = signal<boolean>(false);
  protected readonly currentPage = signal<number>(1);

  protected readonly totalCatalogCount = computed(() => this.catalog().length);
  protected readonly supplierOptions = computed(() => extractSupplierOptions(this.catalog()));
  protected readonly totalSuppliersCount = computed(() => this.supplierOptions().length);
  protected readonly filteredSupplierOptions = computed(() => {
    const tokens = tokenizeSearchQuery(this.supplierSearchQuery());
    const options = this.supplierOptions();
    if (tokens.length === 0) return options;
    return options.filter((opt) => {
      const normalizedName = normalizeSearchText(opt.name);
      return tokens.every((token) => normalizedName.includes(token));
    });
  });

  protected readonly filteredItems = computed(() =>
    filterAndSortCatalog(this.catalog(), {
      query: this.searchQuery(),
      supplier: this.selectedSupplier(),
      stockFilter: this.stockFilter(),
      strengthFilter: this.showSeasonality() ? this.strengthFilter() : 'all',
      sortBy: this.sortBy(),
    }),
  );

  protected readonly totalFilteredCount = computed(() => this.filteredItems().length);

  protected readonly totalPages = computed(() => {
    const total = this.totalFilteredCount();
    if (total === 0) return 0;
    return Math.ceil(total / DEFAULT_CATALOG_PAGE_SIZE);
  });

  protected readonly safePage = computed(() => {
    const tp = this.totalPages();
    if (tp === 0) return 1;
    return Math.min(Math.max(1, this.currentPage()), tp);
  });

  protected readonly pageOffset = computed(() => (this.safePage() - 1) * DEFAULT_CATALOG_PAGE_SIZE);

  protected readonly pagedItems = computed(() => {
    const items = this.filteredItems();
    const start = this.pageOffset();
    return items.slice(start, start + DEFAULT_CATALOG_PAGE_SIZE);
  });

  protected readonly groupedRows = computed(() => groupCatalogRows(this.pagedItems()));

  protected readonly hasActiveFilters = computed(
    () =>
      this.searchQuery().trim().length > 0 ||
      this.selectedSupplier() !== '' ||
      this.stockFilter() !== 'all' ||
      (this.showSeasonality() && this.strengthFilter() !== 'all'),
  );

  protected readonly rangeSummary = computed(() => {
    const total = this.totalFilteredCount();
    if (total === 0) return '0 produtos';
    const first = this.pageOffset() + 1;
    const last = this.pageOffset() + this.pagedItems().length;
    if (total === this.totalCatalogCount()) {
      return `Exibindo ${first}–${last} de ${total} produtos`;
    }
    return `Exibindo ${first}–${last} de ${total} encontrados (catálogo: ${this.totalCatalogCount()})`;
  });

  constructor() {
    this.loadTrigger$
      .pipe(
        tap(() => {
          this.isLoading.set(true);
          this.loadError.set(null);
        }),
        switchMap(() => {
          const request$ = this.showSeasonality()
            ? this.analyticsService.getCatalogProducts({ includeSeasonality: true })
            : this.analyticsService.getCatalogProducts();
          return request$.pipe(
            tap((response) => {
              this.catalog.set(response.data ?? []);
              this.isLoading.set(false);
              this.loadError.set(null);
            }),
            catchError(() => {
              this.loadError.set(
                'Não foi possível carregar o catálogo de produtos agora. Tente novamente.',
              );
              this.isLoading.set(false);
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();
  }

  ngOnInit(): void {
    this.loadCatalog();
  }

  protected loadCatalog(): void {
    this.loadTrigger$.next();
  }

  protected onSearchInput(value: string): void {
    this.searchQuery.set(value);
    this.currentPage.set(1);

    if (!this.userOverrodeSort()) {
      const hasTokens = tokenizeSearchQuery(value).length > 0;
      this.sortBy.set(hasTokens ? 'relevance' : 'supplier-asc');
    }
  }

  protected clearSearchInput(): void {
    this.onSearchInput('');
  }

  protected onSupplierChange(value: string): void {
    this.selectedSupplier.set(value);
    this.supplierDropdownOpen.set(false);
    this.supplierSearchQuery.set('');
    this.supplierActiveIndex.set(-1);
    this.currentPage.set(1);
  }

  protected clearSupplierFilter(event?: Event): void {
    event?.stopPropagation();
    this.onSupplierChange('');
  }

  protected toggleSupplierDropdown(): void {
    if (this.supplierDropdownOpen()) {
      this.closeSupplierDropdown(false);
      return;
    }
    this.openSupplierDropdown();
  }

  protected openSupplierDropdown(): void {
    this.supplierDropdownOpen.set(true);
    this.supplierSearchQuery.set('');
    this.supplierActiveIndex.set(-1);
    queueMicrotask(() => {
      this.supplierSearchInput()?.nativeElement.focus();
    });
  }

  protected closeSupplierDropdown(restoreTriggerFocus = false): void {
    if (!this.supplierDropdownOpen()) return;
    this.supplierDropdownOpen.set(false);
    this.supplierSearchQuery.set('');
    this.supplierActiveIndex.set(-1);
    if (restoreTriggerFocus) {
      this.supplierTrigger()?.nativeElement.focus();
    }
  }

  protected onSupplierSearchInput(value: string): void {
    this.supplierSearchQuery.set(value);
    const matches = this.filteredSupplierOptions();
    this.supplierActiveIndex.set(matches.length > 0 && value.trim().length > 0 ? 0 : -1);
  }

  protected onSupplierKeydown(event: KeyboardEvent): void {
    const matches = this.filteredSupplierOptions();
    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeSupplierDropdown(true);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!this.supplierDropdownOpen()) {
        this.openSupplierDropdown();
        return;
      }
      if (matches.length === 0) return;
      const next = this.supplierActiveIndex() < matches.length - 1 ? this.supplierActiveIndex() + 1 : 0;
      this.supplierActiveIndex.set(next);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (matches.length === 0) return;
      const prev = this.supplierActiveIndex() > 0 ? this.supplierActiveIndex() - 1 : matches.length - 1;
      this.supplierActiveIndex.set(prev);
      return;
    }
    if (event.key === 'Enter' && this.supplierDropdownOpen()) {
      event.preventDefault();
      const idx = this.supplierActiveIndex();
      if (idx >= 0 && idx < matches.length) {
        this.onSupplierChange(matches[idx].name);
      } else if (matches.length === 1) {
        this.onSupplierChange(matches[0].name);
      } else if (this.supplierSearchQuery().trim() === '') {
        this.onSupplierChange('');
      }
    }
  }

  protected onDocumentClick(event: MouseEvent): void {
    if (!this.supplierDropdownOpen()) return;
    const container = this.supplierCombobox()?.nativeElement;
    const target = event.target as Node | null;
    if (container && target && !container.contains(target)) {
      this.closeSupplierDropdown(false);
    }
  }

  protected onStockFilterChange(value: string): void {
    if (value === 'all' || value === 'in-stock' || value === 'out-of-stock') {
      this.stockFilter.set(value);
      this.currentPage.set(1);
    }
  }

  protected onStrengthFilterChange(value: string): void {
    if (
      value === 'all' ||
      value === 'measurable' ||
      value === 'FORTE' ||
      value === 'MODERADA' ||
      value === 'FRACA' ||
      value === 'INSUFICIENTE'
    ) {
      this.strengthFilter.set(value);
      this.currentPage.set(1);
    }
  }

  protected onSortChange(value: string): void {
    const nextSort = value as CatalogSortKey;
    this.userOverrodeSort.set(true);
    this.sortBy.set(nextSort);
    this.currentPage.set(1);
  }

  protected onPageChange(page: number): void {
    this.currentPage.set(page);
  }

  protected onColumnSort(column: SortableColumn): void {
    const current = this.sortBy();
    let next: CatalogSortKey;

    switch (column) {
      case 'sku':
        next = current === 'sku-asc' ? 'sku-desc' : 'sku-asc';
        break;
      case 'name':
        next = current === 'name-asc' ? 'name-desc' : 'name-asc';
        break;
      case 'supplier':
        next = current === 'supplier-asc' ? 'supplier-desc' : 'supplier-asc';
        break;
      case 'stock':
        next = current === 'stock-desc' ? 'stock-asc' : 'stock-desc';
        break;
      case 'price':
        next = current === 'price-desc' ? 'price-asc' : 'price-desc';
        break;
      case 'strength':
      case 'amplitude':
        next = current === 'amplitude-desc' ? 'amplitude-asc' : 'amplitude-desc';
        break;
      case 'revenue':
        next = 'revenue-desc';
        break;
    }

    this.userOverrodeSort.set(true);
    this.sortBy.set(next);
    this.currentPage.set(1);
  }

  protected getAriaSort(column: SortableColumn): 'ascending' | 'descending' | 'none' {
    const current = this.sortBy();
    switch (column) {
      case 'sku':
        return current === 'sku-asc' ? 'ascending' : current === 'sku-desc' ? 'descending' : 'none';
      case 'name':
        return current === 'name-asc' ? 'ascending' : current === 'name-desc' ? 'descending' : 'none';
      case 'supplier':
        return current === 'supplier-asc'
          ? 'ascending'
          : current === 'supplier-desc'
            ? 'descending'
            : 'none';
      case 'stock':
        return current === 'stock-asc'
          ? 'ascending'
          : current === 'stock-desc'
            ? 'descending'
            : 'none';
      case 'price':
        return current === 'price-asc'
          ? 'ascending'
          : current === 'price-desc'
            ? 'descending'
            : 'none';
      case 'strength':
      case 'amplitude':
        return current === 'amplitude-asc'
          ? 'ascending'
          : current === 'amplitude-desc'
            ? 'descending'
            : 'none';
      case 'revenue':
        return current === 'revenue-desc' ? 'descending' : 'none';
    }
  }

  protected clearAllFilters(): void {
    this.searchQuery.set('');
    this.selectedSupplier.set('');
    this.supplierDropdownOpen.set(false);
    this.supplierSearchQuery.set('');
    this.supplierActiveIndex.set(-1);
    this.stockFilter.set('all');
    this.strengthFilter.set('all');
    this.userOverrodeSort.set(false);
    this.sortBy.set('supplier-asc');
    this.currentPage.set(1);
  }

  protected selectProduct(item: CatalogProductItem): void {
    this.productSelect.emit(item);
  }

  protected getStrengthTagClass(strength: SeasonalityStrength | null | undefined): string {
    switch (strength) {
      case 'FORTE':
        return 'tag-positive';
      case 'MODERADA':
        return 'tag-info';
      case 'FRACA':
        return 'tag-warning';
      case 'INSUFICIENTE':
        return 'tag-critical';
      default:
        return 'tag-neutral';
    }
  }

  protected getStrengthShortLabel(strength: SeasonalityStrength | null | undefined): string {
    switch (strength) {
      case 'FORTE':
        return 'Forte';
      case 'MODERADA':
        return 'Moderada';
      case 'FRACA':
        return 'Fraca';
      case 'INSUFICIENTE':
        return 'Insuficiente';
      default:
        return 'Sem dados';
    }
  }

  protected getInsufficientReasonShort(reason: SeasonalityReason | undefined): string {
    if (reason === 'HISTORICO_CURTO') return 'Histórico < 12 meses';
    if (reason === 'VENDA_ESPORADICA') return 'Venda esporádica (< 6 meses)';
    return 'Histórico insuficiente';
  }
}

function createCatalogIds() {
  const prefix = `catalog-explorer-${nextCatalogId++}`;
  return {
    title: `${prefix}-title`,
    search: `${prefix}-search`,
    supplier: `${prefix}-supplier`,
    supplierSearch: `${prefix}-supplier-search`,
    supplierListbox: `${prefix}-supplier-listbox`,
    stock: `${prefix}-stock`,
    strength: `${prefix}-strength`,
    sort: `${prefix}-sort`,
  };
}
