import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Subject, catchError, defer, map, of, switchMap, timer } from 'rxjs';
import { ErrorBannerComponent } from '../../components/error-banner/error-banner.component';
import { InfoHelpComponent } from '../../components/info-help/info-help.component';
import { ProductCatalogExplorerComponent } from '../../components/product-catalog-explorer/product-catalog-explorer.component';
import { ResultStateComponent } from '../../components/result-state/result-state.component';
import { DEFAULT_PAGE_LIMIT } from '../../models/analytics.model';
import {
  ProductElasticityDetail,
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
import { ElasticitySimulatorPanelComponent } from './components/elasticity-simulator-panel/elasticity-simulator-panel.component';
import { ElasticitySkeletonComponent } from './components/elasticity-skeleton/elasticity-skeleton.component';

type ElasticityLoadState = 'initial' | 'loading' | 'loaded' | 'insufficient-data' | 'error';

interface SimulationTrigger {
  sku: number;
  priceChangePct: number;
  costPrice: number | null;
  currentPrice: number | null;
  immediate: boolean;
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
    ErrorBannerComponent,
    InfoHelpComponent,
    ProductCatalogExplorerComponent,
    ResultStateComponent,
    ElasticitySkeletonComponent,
    ElasticitySimulatorPanelComponent,
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

  private readonly productRequest$ = new Subject<number | null>();
  private readonly simulationRequest$ = new Subject<SimulationTrigger | null>();

  protected readonly activeSku = signal<number | null>(null);
  protected readonly productData = signal<ProductElasticityDetail | null>(null);

  protected readonly isLoadingProduct = signal<boolean>(false);
  protected readonly loadState = signal<ElasticityLoadState>('initial');
  protected readonly skuFieldError = signal<string | null>(null);
  protected readonly bannerError = signal<BannerErrorState | null>(null);

  protected readonly priceChangePct = signal<number>(PRICE_CHANGE_DEFAULT);
  protected readonly customCostPrice = signal<number | null>(null);
  protected readonly customCurrentPrice = signal<number | null>(null);

  protected readonly simulationResult = signal<SimulationImpactData | null>(null);
  protected readonly isSimulating = signal<boolean>(false);
  protected readonly simulationError = signal<string | null>(null);
  protected readonly liveAnnouncement = signal<string>('');

  protected readonly initialState = buildElasticityInitialState();
  protected readonly insufficientDataState = buildElasticityInsufficientDataState();
  protected readonly invalidSkuFormatMessage = PRODUCT_INVALID_FORMAT_MESSAGE;
  protected readonly helpCopy = ELASTICITY_HELP_COPY;

  constructor() {
    this.setupProductStream();
    this.setupSimulationStream();
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
          this.skuFieldError.set(PRODUCT_INVALID_FORMAT_MESSAGE);
          return;
        }

        const parsedSku = Number.parseInt(rawSku, 10);
        if (!Number.isSafeInteger(parsedSku) || parsedSku <= 0) {
          this.resetToInitialState();
          this.skuFieldError.set(PRODUCT_INVALID_FORMAT_MESSAGE);
          return;
        }

        if (parsedSku !== this.activeSku()) {
          this.triggerProductLoad(parsedSku);
        }
      });
  }

  protected onSearchSku(sku: number): void {
    if (this.route.snapshot.queryParamMap.get('sku') !== String(sku)) {
      // LGPD: sincroniza apenas `sku` na URL; nunca expõe dados de cliente em query params ou storage.
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { sku: String(sku) },
      });
    }
    this.triggerProductLoad(sku);
  }

  protected onRetryProduct(): void {
    const sku = this.activeSku();
    if (sku === null) return;
    this.triggerProductLoad(sku);
  }

  protected backToCatalog(): void {
    this.resetToInitialState();
    if (this.route.snapshot.queryParamMap.get('sku') !== null) {
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { sku: null },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });
    }
  }

  protected onStateAction(action: ResultStateAction): void {
    if (action === 'focus-field' || action === 'new-search') {
      this.backToCatalog();
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
      priceChangePct: pct,
      costPrice: this.customCostPrice(),
      currentPrice: this.customCurrentPrice(),
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
      priceChangePct: pct,
      costPrice: this.customCostPrice(),
      currentPrice: this.customCurrentPrice(),
      immediate: true,
    });
  }

  protected onCostChange(costPrice: number): void {
    const sku = this.activeSku();
    this.customCostPrice.set(costPrice);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      priceChangePct: this.priceChangePct(),
      costPrice,
      currentPrice: this.customCurrentPrice(),
      immediate: false,
    });
  }

  protected onResetCost(): void {
    const sku = this.activeSku();
    this.customCostPrice.set(null);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      priceChangePct: this.priceChangePct(),
      costPrice: null,
      currentPrice: this.customCurrentPrice(),
      immediate: true,
    });
  }

  protected onCurrentPriceChange(currentPrice: number): void {
    this.submitCurrentPriceSimulation(currentPrice, false);
  }

  protected onCurrentPriceCommit(currentPrice: number): void {
    this.submitCurrentPriceSimulation(currentPrice, true);
  }

  private submitCurrentPriceSimulation(currentPrice: number, immediate: boolean): void {
    const sku = this.activeSku();
    this.customCurrentPrice.set(currentPrice);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      priceChangePct: this.priceChangePct(),
      costPrice: this.customCostPrice(),
      currentPrice,
      immediate,
    });
  }

  protected onResetCurrentPrice(): void {
    const sku = this.activeSku();
    this.customCurrentPrice.set(null);
    this.simulationError.set(null);
    if (sku === null || this.loadState() !== 'loaded') return;

    this.simulationRequest$.next({
      sku,
      priceChangePct: this.priceChangePct(),
      costPrice: this.customCostPrice(),
      currentPrice: null,
      immediate: true,
    });
  }

  protected onRetrySimulation(): void {
    const sku = this.activeSku();
    if (sku === null) return;

    this.simulationRequest$.next({
      sku,
      priceChangePct: this.priceChangePct(),
      costPrice: this.customCostPrice(),
      currentPrice: this.customCurrentPrice(),
      immediate: true,
    });
  }

  private setupProductStream(): void {
    this.productRequest$
      .pipe(
        switchMap((sku) => {
          if (sku === null) return EMPTY;

          return this.analyticsService
            .getProductElasticity(sku, { limit: DEFAULT_PAGE_LIMIT, offset: 0 })
            .pipe(
              map((resp) => ({ sku, resp })),
              catchError((err: unknown) => {
                const apiErr = toElasticityApiError(err);
                this.isLoadingProduct.set(false);
                this.productData.set(null);

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
      .subscribe(({ sku, resp }) => {
        this.productData.set(resp.data);
        this.isLoadingProduct.set(false);
        this.loadState.set('loaded');

        this.liveAnnouncement.set(buildProductLiveAnnouncement(resp.data));
        this.simulationRequest$.next({
          sku,
          priceChangePct: this.priceChangePct(),
          costPrice: this.customCostPrice(),
          currentPrice: this.customCurrentPrice(),
          immediate: true,
        });
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

          if (req.costPrice !== null && (!Number.isFinite(req.costPrice) || req.costPrice < 0)) {
            this.isSimulating.set(false);
            return EMPTY;
          }

          if (req.currentPrice !== null && (!Number.isFinite(req.currentPrice) || req.currentPrice <= 0)) {
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
                  priceChangePct: activeReq.priceChangePct,
                  ...(activeReq.costPrice !== null && activeReq.costPrice !== undefined
                    ? { costPrice: activeReq.costPrice }
                    : {}),
                  ...(activeReq.currentPrice !== null && activeReq.currentPrice !== undefined
                    ? { currentPrice: activeReq.currentPrice }
                    : {}),
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

  private triggerProductLoad(sku: number): void {
    this.activeSku.set(sku);
    this.productData.set(null);
    this.simulationResult.set(null);
    this.simulationError.set(null);
    this.isSimulating.set(false);
    this.priceChangePct.set(PRICE_CHANGE_DEFAULT);
    this.customCostPrice.set(null);
    this.customCurrentPrice.set(null);
    this.skuFieldError.set(null);
    this.bannerError.set(null);
    this.isLoadingProduct.set(true);
    this.loadState.set('loading');

    // Aborta simulações vinculadas ao SKU anterior antes da nova chamada.
    this.simulationRequest$.next(null);
    this.productRequest$.next(sku);
  }

  private resetToInitialState(): void {
    this.productRequest$.next(null);
    this.simulationRequest$.next(null);

    this.activeSku.set(null);
    this.productData.set(null);
    this.isLoadingProduct.set(false);
    this.loadState.set('initial');
    this.skuFieldError.set(null);
    this.bannerError.set(null);
    this.priceChangePct.set(PRICE_CHANGE_DEFAULT);
    this.customCostPrice.set(null);
    this.customCurrentPrice.set(null);
    this.simulationResult.set(null);
    this.isSimulating.set(false);
    this.simulationError.set(null);
    this.liveAnnouncement.set('');
  }
}
