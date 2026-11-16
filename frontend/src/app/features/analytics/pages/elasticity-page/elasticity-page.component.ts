import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Subject, catchError, defer, map, of, switchMap, timer } from 'rxjs';
import { CodeSearchFormComponent } from '../../components/code-search-form/code-search-form.component';
import { ErrorBannerComponent } from '../../components/error-banner/error-banner.component';
import { InfoHelpComponent } from '../../components/info-help/info-help.component';
import { ResultStateComponent } from '../../components/result-state/result-state.component';
import { DEFAULT_PAGE_LIMIT } from '../../models/analytics.model';
import {
  CustomerElasticityDetail,
  ProductElasticityDetail,
  ResponseMeta,
  SimulationImpactData,
} from '../../models/elasticity.models';
import { AnalyticsService } from '../../services/analytics.service';
import {
  ELASTICITY_SIMULATION_GENERIC_ERROR_MESSAGE,
  PRODUCT_INVALID_FORMAT_MESSAGE,
  resolveElasticityErrorMessage,
  resolveElasticitySkuFieldError,
  toElasticityApiError,
} from '../../utils/analytics-error';
import { ResultStateAction } from '../../utils/cross-sell-view';
import { ELASTICITY_HELP_COPY } from '../../utils/elasticity-help-copy';
import {
  PRICE_CHANGE_DEFAULT,
  PRICE_CHANGE_MAX,
  PRICE_CHANGE_MIN,
  buildElasticityInitialState,
  buildElasticityInsufficientDataState,
  buildProductLiveAnnouncement,
  buildSimulationLiveAnnouncement,
} from '../../utils/elasticity-view';
import { ElasticityCustomersTableComponent } from './components/elasticity-customers-table/elasticity-customers-table.component';
import { ElasticityDiagnosticCardComponent } from './components/elasticity-diagnostic-card/elasticity-diagnostic-card.component';
import { ElasticitySimulatorPanelComponent } from './components/elasticity-simulator-panel/elasticity-simulator-panel.component';
import { ElasticitySkeletonComponent } from './components/elasticity-skeleton/elasticity-skeleton.component';

type ElasticityLoadState = 'initial' | 'loading' | 'loaded' | 'insufficient-data' | 'error';

interface ProductLoadRequest {
  sku: number;
  page: number;
  mode: 'full' | 'page';
}

interface SimulationTrigger {
  sku: number;
  customerCode: number | null;
  priceChangePct: number;
  immediate: boolean;
}

interface CustomerDetailTrigger {
  sku: number;
  customerCode: number;
  isLookup: boolean;
}

interface BannerErrorState {
  message: string;
  code: string | null;
}

const SLIDER_DEBOUNCE_MS = 180;
const POSITIVE_INT_PATTERN = /^[1-9]\d*$/;

@Component({
  selector: 'app-elasticity-page',
  standalone: true,
  imports: [
    CodeSearchFormComponent,
    ErrorBannerComponent,
    InfoHelpComponent,
    ResultStateComponent,
    ElasticitySkeletonComponent,
    ElasticityDiagnosticCardComponent,
    ElasticitySimulatorPanelComponent,
    ElasticityCustomersTableComponent,
  ],
  templateUrl: './elasticity-page.component.html',
  styleUrl: './elasticity-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticityPageComponent implements OnInit {
  private readonly analyticsService = inject(AnalyticsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  private readonly searchForm = viewChild(CodeSearchFormComponent);
  private readonly simulatorPanel = viewChild(ElasticitySimulatorPanelComponent);

  private readonly productRequest$ = new Subject<ProductLoadRequest | null>();
  private readonly simulationRequest$ = new Subject<SimulationTrigger | null>();
  private readonly customerDetailRequest$ = new Subject<CustomerDetailTrigger | null>();

  protected readonly skuInput = signal<string>('');
  protected readonly activeSku = signal<number | null>(null);
  protected readonly productData = signal<ProductElasticityDetail | null>(null);
  protected readonly productMeta = signal<ResponseMeta | null>(null);
  protected readonly currentPage = signal<number>(1);
  protected readonly failedPage = signal<number | null>(null);

  protected readonly isLoadingProduct = signal<boolean>(false);
  protected readonly isLoadingPage = signal<boolean>(false);
  protected readonly loadState = signal<ElasticityLoadState>('initial');
  protected readonly skuFieldError = signal<string | null>(null);
  protected readonly bannerError = signal<BannerErrorState | null>(null);
  protected readonly pageLoadError = signal<string | null>(null);

  protected readonly priceChangePct = signal<number>(PRICE_CHANGE_DEFAULT);
  protected readonly selectedCustomerCode = signal<number | null>(null);
  protected readonly customerDetail = signal<CustomerElasticityDetail | null>(null);
  protected readonly isCustomerLoading = signal<boolean>(false);
  protected readonly customerError = signal<string | null>(null);
  protected readonly customerLookupError = signal<string | null>(null);

  protected readonly simulationResult = signal<SimulationImpactData | null>(null);
  protected readonly isSimulating = signal<boolean>(false);
  protected readonly simulationError = signal<string | null>(null);
  protected readonly liveAnnouncement = signal<string>('');

  protected readonly initialState = buildElasticityInitialState();
  protected readonly insufficientDataState = buildElasticityInsufficientDataState();
  protected readonly invalidSkuFormatMessage = PRODUCT_INVALID_FORMAT_MESSAGE;
  protected readonly helpCopy = ELASTICITY_HELP_COPY;

  protected readonly totalClients = computed(
    () => this.productMeta()?.totalItems ?? this.productData()?.customers.length ?? 0,
  );

  protected readonly totalPages = computed(() => {
    const meta = this.productMeta();
    if (meta?.totalPages !== undefined && meta.totalPages >= 1) {
      return meta.totalPages;
    }
    return Math.max(1, Math.ceil(this.totalClients() / DEFAULT_PAGE_LIMIT));
  });

  protected readonly pageOffset = computed(
    () => this.productMeta()?.offset ?? (this.currentPage() - 1) * DEFAULT_PAGE_LIMIT,
  );

  constructor() {
    this.setupProductStream();
    this.setupSimulationStream();
    this.setupCustomerDetailStream();
  }

  ngOnInit(): void {
    this.route.queryParamMap
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((params) => {
        const rawSku = params.get('sku')?.trim() ?? '';
        if (!rawSku) {
          if (this.activeSku() !== null || this.loadState() !== 'initial') {
            this.resetToInitialState();
          }
          return;
        }

        if (!POSITIVE_INT_PATTERN.test(rawSku)) {
          this.resetToInitialState();
          this.skuInput.set(rawSku);
          this.skuFieldError.set(PRODUCT_INVALID_FORMAT_MESSAGE);
          return;
        }

        const parsedSku = Number.parseInt(rawSku, 10);
        if (!Number.isSafeInteger(parsedSku) || parsedSku <= 0) {
          this.resetToInitialState();
          this.skuInput.set(rawSku);
          this.skuFieldError.set(PRODUCT_INVALID_FORMAT_MESSAGE);
          return;
        }

        this.skuInput.set(String(parsedSku));
        if (parsedSku !== this.activeSku()) {
          this.triggerProductLoad(parsedSku, 1, 'full');
        }
      });
  }

  protected onSearchSku(sku: number): void {
    this.skuInput.set(String(sku));
    if (this.route.snapshot.queryParamMap.get('sku') !== String(sku)) {
      // LGPD: sincroniza apenas `sku` na URL; nunca expõe `customerCode` em query params ou storage.
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { sku: String(sku) },
      });
    }
    this.triggerProductLoad(sku, 1, 'full');
  }

  protected onRetryProduct(): void {
    const sku = this.activeSku();
    if (sku === null) return;
    this.triggerProductLoad(sku, 1, 'full');
  }

  protected onStateAction(action: ResultStateAction): void {
    if (action === 'focus-field') {
      this.searchForm()?.focus();
      return;
    }
    if (action === 'new-search') {
      this.searchForm()?.clearAndFocus();
      return;
    }
    if (action === 'retry') {
      this.onRetryProduct();
    }
  }

  protected onPriceSliderInput(pct: number): void {
    const sku = this.activeSku();
    this.priceChangePct.set(pct);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      customerCode: this.selectedCustomerCode(),
      priceChangePct: pct,
      immediate: false,
    });
  }

  protected onPriceImmediateChange(pct: number): void {
    const sku = this.activeSku();
    this.priceChangePct.set(pct);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      customerCode: this.selectedCustomerCode(),
      priceChangePct: pct,
      immediate: true,
    });
  }

  protected onRetrySimulation(): void {
    const sku = this.activeSku();
    if (sku === null) return;

    this.simulationRequest$.next({
      sku,
      customerCode: this.selectedCustomerCode(),
      priceChangePct: this.priceChangePct(),
      immediate: true,
    });
  }

  protected onSelectCustomer(customerCode: number): void {
    const sku = this.activeSku();
    if (sku === null) return;

    this.customerLookupError.set(null);
    if (this.selectedCustomerCode() === customerCode) {
      this.onClearCustomer();
      return;
    }

    this.selectedCustomerCode.set(customerCode);
    this.customerDetail.set(null);
    this.customerError.set(null);
    this.isCustomerLoading.set(true);
    this.simulatorPanel()?.focusSimulatorContext();

    this.customerDetailRequest$.next({ sku, customerCode, isLookup: false });
    this.simulationRequest$.next({
      sku,
      customerCode,
      priceChangePct: this.priceChangePct(),
      immediate: true,
    });
  }

  protected onLookupCustomer(customerCode: number): void {
    const sku = this.activeSku();
    if (sku === null) return;

    this.customerLookupError.set(null);
    this.customerError.set(null);
    this.isCustomerLoading.set(true);
    this.customerDetailRequest$.next({ sku, customerCode, isLookup: true });
  }

  protected onClearCustomer(): void {
    const sku = this.activeSku();
    this.selectedCustomerCode.set(null);
    this.customerDetail.set(null);
    this.isCustomerLoading.set(false);
    this.customerError.set(null);
    this.customerDetailRequest$.next(null);

    if (sku !== null && this.loadState() === 'loaded') {
      this.simulationRequest$.next({
        sku,
        customerCode: null,
        priceChangePct: this.priceChangePct(),
        immediate: true,
      });
    }
  }

  protected onPageChange(page: number): void {
    const sku = this.activeSku();
    if (sku === null || page === this.currentPage() || this.isLoadingPage()) return;
    this.triggerProductLoad(sku, page, 'page');
  }

  protected onRetryPage(): void {
    const sku = this.activeSku();
    if (sku === null) return;
    this.triggerProductLoad(sku, this.failedPage() ?? this.currentPage(), 'page');
  }

  protected onStartNewSearch(): void {
    this.searchForm()?.clearAndFocus();
  }

  private setupProductStream(): void {
    this.productRequest$
      .pipe(
        switchMap((req) => {
          if (req === null) return EMPTY;

          const pageRequest = {
            limit: DEFAULT_PAGE_LIMIT,
            offset: (req.page - 1) * DEFAULT_PAGE_LIMIT,
          };

          return this.analyticsService.getProductElasticity(req.sku, pageRequest).pipe(
            map((resp) => ({ req, resp })),
            catchError((err: unknown) => {
              const apiErr = toElasticityApiError(err);
              if (req.mode === 'page') {
                this.isLoadingPage.set(false);
                this.failedPage.set(req.page);
                this.pageLoadError.set(resolveElasticityErrorMessage(apiErr));
                return EMPTY;
              }

              this.isLoadingProduct.set(false);
              this.productData.set(null);
              this.productMeta.set(null);

              if (apiErr?.code === 'ELA-003') {
                this.loadState.set('insufficient-data');
                this.skuFieldError.set(null);
                this.bannerError.set(null);
              } else {
                this.loadState.set('error');
                this.skuFieldError.set(resolveElasticitySkuFieldError(apiErr));
                this.bannerError.set({
                  message: resolveElasticityErrorMessage(apiErr),
                  code: apiErr?.code ?? null,
                });
              }
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ req, resp }) => {
        this.productData.set(resp.data);
        this.productMeta.set(resp.meta);
        this.currentPage.set(req.page);
        this.failedPage.set(null);
        this.pageLoadError.set(null);
        this.isLoadingProduct.set(false);
        this.isLoadingPage.set(false);
        this.loadState.set('loaded');

        if (req.mode === 'full') {
          const total = resp.meta.totalItems ?? resp.data.customers.length;
          this.liveAnnouncement.set(buildProductLiveAnnouncement(resp.data, total));
          this.simulationRequest$.next({
            sku: req.sku,
            customerCode: null,
            priceChangePct: this.priceChangePct(),
            immediate: true,
          });
        }
      });
  }

  private setupSimulationStream(): void {
    this.simulationRequest$
      .pipe(
        switchMap((req) => {
          if (req === null) {
            this.isSimulating.set(false);
            return EMPTY;
          }

          if (req.priceChangePct < PRICE_CHANGE_MIN || req.priceChangePct > PRICE_CHANGE_MAX) {
            this.isSimulating.set(false);
            return EMPTY;
          }

          const trigger$ = req.immediate ? of(req) : timer(SLIDER_DEBOUNCE_MS).pipe(map(() => req));
          return trigger$.pipe(
            switchMap((activeReq) =>
              defer(() => {
                this.isSimulating.set(true);
                this.simulationError.set(null);
                return this.analyticsService.simulatePriceChange({
                  sku: activeReq.sku,
                  customerCode: activeReq.customerCode,
                  priceChangePct: activeReq.priceChangePct,
                });
              }),
            ),
            catchError((err: unknown) => {
              const apiErr = toElasticityApiError(err);
              this.isSimulating.set(false);
              this.simulationError.set(
                resolveElasticityErrorMessage(apiErr, ELASTICITY_SIMULATION_GENERIC_ERROR_MESSAGE),
              );
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((resp) => {
        this.simulationResult.set(resp.data);
        this.isSimulating.set(false);
        this.simulationError.set(null);
        this.liveAnnouncement.set(buildSimulationLiveAnnouncement(resp.data));
      });
  }

  private setupCustomerDetailStream(): void {
    this.customerDetailRequest$
      .pipe(
        switchMap((req) => {
          if (req === null) {
            this.isCustomerLoading.set(false);
            return EMPTY;
          }

          return this.analyticsService.getCustomerElasticity(req.sku, req.customerCode).pipe(
            map((resp) => ({ req, resp })),
            catchError((err: unknown) => {
              const apiErr = toElasticityApiError(err);
              const friendlyMessage = resolveElasticityErrorMessage(apiErr);
              this.isCustomerLoading.set(false);

              if (req.isLookup) {
                this.customerLookupError.set(friendlyMessage);
              } else {
                this.customerError.set(friendlyMessage);
              }
              return EMPTY;
            }),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe(({ req, resp }) => {
        this.isCustomerLoading.set(false);
        this.customerError.set(null);
        this.customerLookupError.set(null);
        this.customerDetail.set(resp.data);

        if (req.isLookup) {
          this.selectedCustomerCode.set(req.customerCode);
          this.simulatorPanel()?.focusSimulatorContext();
          this.simulationRequest$.next({
            sku: req.sku,
            customerCode: req.customerCode,
            priceChangePct: this.priceChangePct(),
            immediate: true,
          });
        }
      });
  }

  private triggerProductLoad(sku: number, page: number, mode: 'full' | 'page'): void {
    if (mode === 'full') {
      this.activeSku.set(sku);
      this.currentPage.set(1);
      this.failedPage.set(null);
      this.productData.set(null);
      this.productMeta.set(null);
      this.selectedCustomerCode.set(null);
      this.customerDetail.set(null);
      this.isCustomerLoading.set(false);
      this.customerError.set(null);
      this.customerLookupError.set(null);
      this.simulationResult.set(null);
      this.simulationError.set(null);
      this.isSimulating.set(false);
      this.priceChangePct.set(PRICE_CHANGE_DEFAULT);
      this.skuFieldError.set(null);
      this.bannerError.set(null);
      this.pageLoadError.set(null);
      this.isLoadingProduct.set(true);
      this.isLoadingPage.set(false);
      this.loadState.set('loading');

      // Aborta streams filhos vinculados ao SKU anterior antes da nova chamada.
      this.simulationRequest$.next(null);
      this.customerDetailRequest$.next(null);
    } else {
      this.isLoadingPage.set(true);
      this.pageLoadError.set(null);
    }

    this.productRequest$.next({ sku, page, mode });
  }

  private resetToInitialState(): void {
    this.productRequest$.next(null);
    this.simulationRequest$.next(null);
    this.customerDetailRequest$.next(null);

    this.skuInput.set('');
    this.activeSku.set(null);
    this.productData.set(null);
    this.productMeta.set(null);
    this.currentPage.set(1);
    this.failedPage.set(null);
    this.isLoadingProduct.set(false);
    this.isLoadingPage.set(false);
    this.loadState.set('initial');
    this.skuFieldError.set(null);
    this.bannerError.set(null);
    this.pageLoadError.set(null);
    this.priceChangePct.set(PRICE_CHANGE_DEFAULT);
    this.selectedCustomerCode.set(null);
    this.customerDetail.set(null);
    this.isCustomerLoading.set(false);
    this.customerError.set(null);
    this.customerLookupError.set(null);
    this.simulationResult.set(null);
    this.isSimulating.set(false);
    this.simulationError.set(null);
    this.liveAnnouncement.set('');
  }
}
