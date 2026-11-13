import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { ErrorBannerComponent } from '../../../../components/error-banner/error-banner.component';
import { ListPagerComponent } from '../../../../components/list-pager/list-pager.component';
import { ResultStateComponent } from '../../../../components/result-state/result-state.component';
import { CustomerElasticityItem } from '../../../../models/elasticity.models';
import { PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';
import {
  CustomerSortKey,
  SortDirection,
  buildElasticityEmptyCustomersState,
  filterAndSortCustomers,
  formatUnits,
  getClassificationMeta,
} from '../../../../utils/elasticity-view';

const POSITIVE_INT_PATTERN = /^[1-9]\d*$/;

@Component({
  selector: 'app-elasticity-customers-table',
  standalone: true,
  imports: [PtDecimalPipe, PtPercentPipe, ErrorBannerComponent, ListPagerComponent, ResultStateComponent],
  templateUrl: './elasticity-customers-table.component.html',
  styleUrl: './elasticity-customers-table.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticityCustomersTableComponent {
  readonly customers = input.required<readonly CustomerElasticityItem[]>();
  readonly totalClients = input.required<number>();
  readonly currentPage = input.required<number>();
  readonly totalPages = input.required<number>();
  readonly pageOffset = input.required<number>();
  readonly selectedCustomerCode = input<number | null>(null);
  readonly isBusy = input<boolean>(false);
  readonly customerLookupError = input<string | null>(null);
  readonly pageLoadError = input<string | null>(null);

  readonly selectCustomer = output<number>();
  readonly lookupCustomer = output<number>();
  readonly pageChange = output<number>();
  readonly retryPage = output<void>();
  readonly newSearch = output<void>();

  protected readonly filterQuery = signal<string>('');
  protected readonly sortKey = signal<CustomerSortKey | null>(null);
  protected readonly sortDir = signal<SortDirection>('desc');
  protected readonly localLookupError = signal<string | null>(null);

  protected readonly emptyCustomersState = buildElasticityEmptyCustomersState();

  protected readonly visibleCustomers = computed(() =>
    filterAndSortCustomers(this.customers(), this.filterQuery(), this.sortKey(), this.sortDir()),
  );

  protected readonly hasFilter = computed(() => this.filterQuery().trim().length > 0);
  protected readonly displayedLookupError = computed(
    () => this.localLookupError() ?? this.customerLookupError(),
  );

  protected onFilterInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    this.filterQuery.set(target.value);
    if (this.localLookupError() !== null) {
      this.localLookupError.set(null);
    }
  }

  protected onClearFilter(): void {
    this.filterQuery.set('');
    this.localLookupError.set(null);
  }

  protected onLookupSubmit(event: Event): void {
    event.preventDefault();
    const raw = this.filterQuery().trim();
    if (!POSITIVE_INT_PATTERN.test(raw)) {
      this.localLookupError.set('Digite só números inteiros positivos para consultar o cliente (ex.: 1042).');
      return;
    }

    const code = Number.parseInt(raw, 10);
    if (!Number.isSafeInteger(code) || code <= 0) {
      this.localLookupError.set('Código de cliente inválido.');
      return;
    }

    this.localLookupError.set(null);
    this.lookupCustomer.emit(code);
  }

  protected toggleSort(key: CustomerSortKey): void {
    if (this.sortKey() === key) {
      this.sortDir.update((dir) => (dir === 'asc' ? 'desc' : 'asc'));
      return;
    }

    this.sortKey.set(key);
    this.sortDir.set(key === 'customerCode' ? 'asc' : 'desc');
  }

  protected ariaSortFor(key: CustomerSortKey): 'ascending' | 'descending' | 'none' {
    if (this.sortKey() !== key) return 'none';
    return this.sortDir() === 'asc' ? 'ascending' : 'descending';
  }

  protected classificationMeta(classification: CustomerElasticityItem['classification']) {
    return getClassificationMeta(classification);
  }

  protected unitsLabel(units: number): string {
    return formatUnits(units);
  }

  protected onSelectRow(customerCode: number): void {
    this.selectCustomer.emit(customerCode);
  }
}
