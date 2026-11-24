import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { ListPagerComponent } from '../../../../components/list-pager/list-pager.component';
import {
  CannibalizationMechanism,
  CannibalizationSortKey,
  CannibalizationVictimSummary,
  FilterOptionCount,
} from '../../../../models/cannibalization.model';
import {
  BrlPipe,
  PtDecimalPipe,
  SignedBrlPipe,
  SignedPercentPipe,
} from '../../../../pipes/pt-br-format.pipes';
import {
  MECHANISM_VISUAL_META,
  MechanismVisualMeta,
  getReductionSeverityTag,
} from '../../cannibalization.store';
import { SearchableComboboxComponent } from '../searchable-combobox/searchable-combobox.component';

export type ReportSortableColumn =
  | 'price'
  | 'pre-rev'
  | 'cur-rev'
  | 'reduction'
  | 'lost'
  | 'cannibals';

export interface VictimSelectEvent {
  victim: CannibalizationVictimSummary;
  triggerEl: HTMLElement | null;
}

let nextTableId = 0;

@Component({
  selector: 'app-cannibalization-report-table',
  standalone: true,
  imports: [
    BrlPipe,
    PtDecimalPipe,
    SignedBrlPipe,
    SignedPercentPipe,
    ListPagerComponent,
    SearchableComboboxComponent,
  ],
  templateUrl: './cannibalization-report-table.component.html',
  styleUrl: './cannibalization-report-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CannibalizationReportTableComponent {
  readonly victims = input.required<CannibalizationVictimSummary[]>();
  readonly totalCatalogVictims = input.required<number>();
  readonly totalFilteredCount = input.required<number>();
  readonly page = input.required<number>();
  readonly totalPages = input.required<number>();
  readonly pageOffset = input.required<number>();
  readonly searchQuery = input<string>('');
  readonly selectedSupplier = input<string>('');
  readonly selectedCategory = input<string>('');
  readonly supplierOptions = input<FilterOptionCount[]>([]);
  readonly categoryOptions = input<FilterOptionCount[]>([]);
  readonly sortBy = input<CannibalizationSortKey>('reduction-desc');
  readonly hasActiveFilters = input<boolean>(false);
  readonly selectedSku = input<string | null>(null);

  readonly searchChange = output<string>();
  readonly supplierChange = output<string>();
  readonly categoryChange = output<string>();
  readonly sortChange = output<CannibalizationSortKey>();
  readonly pageChange = output<number>();
  readonly clearFilters = output<void>();
  readonly selectVictim = output<VictimSelectEvent>();

  protected readonly ids = createTableIds();

  protected readonly rangeSummary = computed(() => {
    const total = this.totalFilteredCount();
    if (total === 0) return '0 produtos canibalizados';
    const first = this.pageOffset() + 1;
    const last = this.pageOffset() + this.victims().length;
    const noun = total === 1 ? 'produto canibalizado' : 'produtos canibalizados';
    if (total === this.totalCatalogVictims()) {
      return `Mostrando ${first}–${last} de ${total} ${noun}`;
    }
    return `Mostrando ${first}–${last} de ${total} filtrados (total no período: ${this.totalCatalogVictims()})`;
  });

  protected onSearchInput(value: string): void {
    this.searchChange.emit(value);
  }

  protected onSortSelectChange(value: string): void {
    if (isSortKey(value)) {
      this.sortChange.emit(value);
    }
  }

  protected onColumnSort(column: ReportSortableColumn): void {
    const current = this.sortBy();
    let next: CannibalizationSortKey;

    switch (column) {
      case 'reduction':
        next = current === 'reduction-desc' ? 'reduction-asc' : 'reduction-desc';
        break;
      case 'lost':
        next = current === 'lost-desc' ? 'lost-asc' : 'lost-desc';
        break;
      case 'pre-rev':
        next = current === 'pre-rev-desc' ? 'pre-rev-asc' : 'pre-rev-desc';
        break;
      case 'cur-rev':
        next = current === 'cur-rev-desc' ? 'cur-rev-asc' : 'cur-rev-desc';
        break;
      case 'price':
        next = current === 'price-desc' ? 'price-asc' : 'price-desc';
        break;
      case 'cannibals':
        next = current === 'cannibals-desc' ? 'cannibals-asc' : 'cannibals-desc';
        break;
    }

    this.sortChange.emit(next);
  }

  protected getAriaSort(column: ReportSortableColumn): 'ascending' | 'descending' | 'none' {
    const current = this.sortBy();
    switch (column) {
      case 'reduction':
        return current === 'reduction-asc'
          ? 'ascending'
          : current === 'reduction-desc'
            ? 'descending'
            : 'none';
      case 'lost':
        return current === 'lost-asc'
          ? 'ascending'
          : current === 'lost-desc'
            ? 'descending'
            : 'none';
      case 'pre-rev':
        return current === 'pre-rev-asc'
          ? 'ascending'
          : current === 'pre-rev-desc'
            ? 'descending'
            : 'none';
      case 'cur-rev':
        return current === 'cur-rev-asc'
          ? 'ascending'
          : current === 'cur-rev-desc'
            ? 'descending'
            : 'none';
      case 'price':
        return current === 'price-asc'
          ? 'ascending'
          : current === 'price-desc'
            ? 'descending'
            : 'none';
      case 'cannibals':
        return current === 'cannibals-asc'
          ? 'ascending'
          : current === 'cannibals-desc'
            ? 'descending'
            : 'none';
    }
  }

  protected isColumnSorted(column: ReportSortableColumn): boolean {
    return this.getAriaSort(column) !== 'none';
  }

  protected isRevenueSorted(): boolean {
    return this.isColumnSorted('pre-rev') || this.isColumnSorted('cur-rev');
  }

  protected getSeverityClass(pct: number): string {
    return getReductionSeverityTag(pct);
  }

  protected getMechanismMeta(mechanism: CannibalizationMechanism): MechanismVisualMeta {
    return MECHANISM_VISUAL_META[mechanism];
  }

  protected onRowClick(victim: CannibalizationVictimSummary, event: MouseEvent): void {
    const target = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    this.selectVictim.emit({ victim, triggerEl: target });
  }

  protected onActionClick(victim: CannibalizationVictimSummary, event: MouseEvent): void {
    event.stopPropagation();
    const target = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    this.selectVictim.emit({ victim, triggerEl: target });
  }
}

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

function isSortKey(value: string): value is CannibalizationSortKey {
  return (VALID_SORT_KEYS as readonly string[]).includes(value);
}

function createTableIds() {
  const prefix = `cannib-table-${nextTableId++}`;
  return {
    search: `${prefix}-search`,
    sort: `${prefix}-sort`,
  };
}
