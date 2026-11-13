/**
 * Página principal de Churn de Clientes com Score de Prioridade (F3: P-117 a P-127, LGPD-CHU-01..06).
 * Usa OnPush, switchMap + takeUntilDestroyed para evitar race conditions em filtros/paginação/drawer,
 * e mantém códigos de clientes fora da URL e storage do navegador.
 */
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, map, of, switchMap, tap } from 'rxjs';
import { CustomerChurnDrawerComponent } from '../../components/customer-churn-drawer/customer-churn-drawer.component';
import { ListPagerComponent } from '../../components/list-pager/list-pager.component';
import { DEFAULT_PAGE_LIMIT, PageRequest } from '../../models/analytics.model';
import {
  ChurnCustomersResponse,
  ChurnStatusFilter,
  ChurnSummaryKpi,
  ChurnTableRow,
  CustomerChurnDetailData,
  InactiveChurnResponse,
} from '../../models/churn.model';
import { BrlPipe, PtDatePipe, PtDecimalPipe } from '../../pipes/pt-br-format.pipes';
import { AnalyticsService } from '../../services/analytics.service';
import {
  buildChurnCsvContent,
  getChurnStatusDisplay,
  mapActiveChurnRow,
  mapInactiveChurnRow,
  resolveChurnErrorMessage,
} from './churn-page.helpers';

interface ChurnListQuery {
  status: ChurnStatusFilter;
  offset: number;
}

type ChurnListPayload =
  | { kind: 'active'; res: ChurnCustomersResponse }
  | { kind: 'inactive'; res: InactiveChurnResponse };

@Component({
  selector: 'app-churn-page',
  standalone: true,
  imports: [
    CustomerChurnDrawerComponent,
    ListPagerComponent,
    BrlPipe,
    PtDecimalPipe,
    PtDatePipe,
  ],
  templateUrl: './churn-page.component.html',
  styleUrl: './churn-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChurnPageComponent implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly document = inject(DOCUMENT);

  private readonly listTrigger$ = new Subject<ChurnListQuery>();
  private readonly detailTrigger$ = new Subject<number | null>();

  readonly limit = DEFAULT_PAGE_LIMIT;

  readonly statusFilter = signal<ChurnStatusFilter>('EM_RISCO');
  readonly customers = signal<ChurnTableRow[]>([]);
  readonly resumo = signal<ChurnSummaryKpi | null>(null);
  readonly inactiveTotalCount = signal<number | null>(null);
  readonly dataReferencia = signal<string | null>(null);

  readonly loading = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  readonly page = signal<number>(1);
  readonly offset = signal<number>(0);
  readonly totalItems = signal<number>(0);
  readonly totalPages = signal<number>(1);

  readonly isDrawerOpen = signal<boolean>(false);
  readonly drawerLoading = signal<boolean>(false);
  readonly drawerError = signal<string | null>(null);
  readonly selectedCustomer = signal<CustomerChurnDetailData | null>(null);
  readonly selectedCustomerCode = signal<number | null>(null);
  readonly drawerTriggerElement = signal<HTMLElement | null>(null);

  readonly isExporting = signal<boolean>(false);

  protected readonly isInactiveView = computed(
    () => this.statusFilter() === 'INATIVO_RECUPERACAO',
  );

  protected readonly totalActiveCount = computed(() => {
    const kpi = this.resumo();
    if (!kpi) return null;
    return kpi.totalEmRisco + kpi.totalAlerta + kpi.totalSaudavel;
  });

  protected readonly badgeInativosCount = computed(
    () => this.resumo()?.totalInativos ?? this.inactiveTotalCount(),
  );

  protected readonly canExportCsv = computed(
    () => !this.isExporting() && !this.loading() && !this.error() && this.customers().length > 0,
  );

  protected readonly liveAnnouncement = computed(() => {
    if (this.loading()) {
      return 'Carregando lista de clientes em risco de churn...';
    }
    const errMsg = this.error();
    if (errMsg) {
      return `Erro ao carregar clientes: ${errMsg}`;
    }
    const count = this.totalItems();
    if (count === 0) {
      return 'Nenhum cliente encontrado para o filtro selecionado.';
    }
    return `Exibindo página ${this.page()} de ${this.totalPages()}, com ${this.customers().length} de ${count} clientes.`;
  });

  constructor() {
    this.listTrigger$
      .pipe(
        tap(({ status, offset }) => {
          this.statusFilter.set(status);
          this.offset.set(offset);
          this.loading.set(true);
          this.error.set(null);
        }),
        switchMap(({ status, offset }) => {
          const pageRequest: PageRequest = { limit: this.limit, offset };
          if (status === 'INATIVO_RECUPERACAO') {
            return this.analyticsService.getInactiveChurn(pageRequest).pipe(
              map((res): ChurnListPayload => ({ kind: 'inactive', res })),
              catchError((err: unknown) => {
                this.handleListError(
                  err,
                  'Não foi possível carregar os clientes inativos. Tente novamente.',
                );
                return EMPTY;
              }),
            );
          }
          return this.analyticsService.getChurnCustomers(status, pageRequest).pipe(
            map((res): ChurnListPayload => ({ kind: 'active', res })),
            catchError((err: unknown) => {
              this.handleListError(
                err,
                'Não foi possível carregar a lista de churn. Tente novamente.',
              );
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((payload) => {
        if (payload.kind === 'active') {
          this.resumo.set(payload.res.data.resumo);
          this.inactiveTotalCount.set(payload.res.data.resumo.totalInativos);
          this.customers.set(payload.res.data.items.map(mapActiveChurnRow));
          this.totalItems.set(payload.res.meta.totalItems);
          this.page.set(payload.res.meta.page);
          this.totalPages.set(payload.res.meta.totalPages);
          this.dataReferencia.set(payload.res.meta.dataReferencia);
        } else {
          this.inactiveTotalCount.set(payload.res.data.totalInativos);
          this.customers.set(payload.res.data.items.map(mapInactiveChurnRow));
          this.totalItems.set(payload.res.meta.totalItems);
          this.page.set(payload.res.meta.page);
          this.totalPages.set(payload.res.meta.totalPages);
          this.dataReferencia.set(payload.res.meta.dataReferencia);
        }
        this.loading.set(false);
      });

    this.detailTrigger$
      .pipe(
        switchMap((customerCode) => {
          if (customerCode === null) {
            return of(null);
          }
          return this.analyticsService.getCustomerChurnDetail(customerCode).pipe(
            catchError((err: unknown) => {
              this.drawerError.set(
                resolveChurnErrorMessage(
                  err,
                  'Não foi possível carregar os detalhes deste cliente. Tente novamente.',
                ),
              );
              this.drawerLoading.set(false);
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((res) => {
        if (res === null) return;
        this.selectedCustomer.set(res.data);
        this.drawerError.set(null);
        this.drawerLoading.set(false);
        if (!this.dataReferencia()) {
          this.dataReferencia.set(res.meta.dataReferencia);
        }
      });
  }

  ngOnInit(): void {
    this.fetchData();
  }

  fetchData(): void {
    this.listTrigger$.next({
      status: this.statusFilter(),
      offset: this.offset(),
    });
  }

  setFilter(status: ChurnStatusFilter): void {
    if (this.statusFilter() === status && !this.error() && !this.loading()) {
      return;
    }
    this.listTrigger$.next({ status, offset: 0 });
  }

  onPageChange(targetPage: number): void {
    const nextOffset = (targetPage - 1) * this.limit;
    this.listTrigger$.next({
      status: this.statusFilter(),
      offset: nextOffset,
    });
  }

  protected onRowClick(
    customer: ChurnTableRow,
    triggerButton: HTMLButtonElement,
    event: MouseEvent,
  ): void {
    const target = event.target as HTMLElement | null;
    if (target?.closest('button, a')) return;
    this.openCustomerDetail(customer, triggerButton);
  }

  openCustomerDetail(
    customer: ChurnTableRow,
    triggerElement: HTMLElement | null = null,
  ): void {
    const fallbackTrigger =
      triggerElement ?? (this.document.activeElement as HTMLElement | null);
    this.drawerTriggerElement.set(fallbackTrigger);
    this.selectedCustomerCode.set(customer.customerCode);
    this.selectedCustomer.set(null);
    this.drawerError.set(null);
    this.drawerLoading.set(true);
    this.isDrawerOpen.set(true);
    this.detailTrigger$.next(customer.customerCode);
  }

  retryCustomerDetail(): void {
    const code = this.selectedCustomerCode();
    if (code === null) return;
    this.drawerError.set(null);
    this.drawerLoading.set(true);
    this.detailTrigger$.next(code);
  }

  closeDrawer(): void {
    this.detailTrigger$.next(null);
    this.isDrawerOpen.set(false);
    this.drawerLoading.set(false);
    this.drawerError.set(null);
    this.selectedCustomer.set(null);
    this.selectedCustomerCode.set(null);
  }

  exportCsv(): void {
    if (!this.canExportCsv()) return;
    this.isExporting.set(true);

    const view = this.document.defaultView;
    let blobUrl: string | null = null;
    let link: HTMLAnchorElement | null = null;

    try {
      const csvContent = buildChurnCsvContent(this.customers(), this.statusFilter());
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      if (view?.URL && typeof view.URL.createObjectURL === 'function') {
        blobUrl = view.URL.createObjectURL(blob);
        link = this.document.createElement('a');
        link.href = blobUrl;
        link.download = `fitoherb-churn-${this.statusFilter().toLowerCase()}-p${this.page()}.csv`;
        link.style.display = 'none';
        this.document.body.appendChild(link);
        link.click();
      }
    } finally {
      if (link?.parentNode) {
        link.parentNode.removeChild(link);
      }
      if (blobUrl && view?.URL && typeof view.URL.revokeObjectURL === 'function') {
        view.URL.revokeObjectURL(blobUrl);
      }
      this.isExporting.set(false);
    }
  }

  protected getStatusDisplay(status: ChurnTableRow['status']) {
    return getChurnStatusDisplay(status);
  }

  private handleListError(err: unknown, fallback: string): void {
    this.error.set(resolveChurnErrorMessage(err, fallback));
    this.customers.set([]);
    this.totalItems.set(0);
    this.page.set(1);
    this.totalPages.set(1);
    this.loading.set(false);
  }
}
