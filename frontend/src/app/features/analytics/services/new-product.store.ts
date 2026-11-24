/**
 * Store reativo da feature Viabilidade de Produto Novo (F2, P-139 a P-149).
 * Gerencia carregamento de `/options`, simulação de `/forecast` via `switchMap` + `takeUntilDestroyed`
 * (cancelamento automático contra race conditions e double-submit), estado stale e Drawer de similares.
 */
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { AnalyticsMeta } from '../models/analytics.model';
import {
  NewProductApiError,
  NewProductForecastData,
  NewProductForecastRequest,
  NewProductOptions,
  SimilarProductItem,
} from '../models/new-product.model';
import { toNewProductApiError } from '../utils/analytics-error';
import { AnalyticsService } from './analytics.service';

export type OptionsLoadState = 'loading' | 'error' | 'ready';
export type SimulationState = 'idle' | 'loading' | 'success' | 'insufficient' | 'error';

@Injectable()
export class NewProductStore {
  private readonly service = inject(AnalyticsService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly loadOptionsTrigger$ = new Subject<void>();
  private readonly simulateTrigger$ = new Subject<NewProductForecastRequest>();

  private readonly optionsStateSignal = signal<OptionsLoadState>('loading');
  private readonly optionsSignal = signal<NewProductOptions | null>(null);
  private readonly optionsErrorSignal = signal<NewProductApiError | null>(null);

  private readonly simulationStateSignal = signal<SimulationState>('idle');
  private readonly forecastDataSignal = signal<NewProductForecastData | null>(null);
  private readonly forecastMetaSignal = signal<AnalyticsMeta | null>(null);
  private readonly forecastErrorSignal = signal<NewProductApiError | null>(null);
  private readonly isDirtySinceLastResultSignal = signal<boolean>(false);
  private readonly selectedSimilarSignal = signal<SimilarProductItem | null>(null);
  private readonly lastRequestSignal = signal<NewProductForecastRequest | null>(null);

  readonly optionsState = this.optionsStateSignal.asReadonly();
  readonly options = this.optionsSignal.asReadonly();
  readonly optionsError = this.optionsErrorSignal.asReadonly();

  readonly hasEmptyCatalog = computed(() => {
    if (this.optionsStateSignal() !== 'ready') return false;
    const opts = this.optionsSignal();
    return !opts || opts.tipos.length === 0 || opts.fornecedores.length === 0;
  });

  readonly simulationState = this.simulationStateSignal.asReadonly();
  readonly forecastData = this.forecastDataSignal.asReadonly();
  readonly forecastMeta = this.forecastMetaSignal.asReadonly();
  readonly forecastError = this.forecastErrorSignal.asReadonly();
  readonly isDirtySinceLastResult = this.isDirtySinceLastResultSignal.asReadonly();
  readonly selectedSimilar = this.selectedSimilarSignal.asReadonly();
  readonly lastRequest = this.lastRequestSignal.asReadonly();

  constructor() {
    this.setupOptionsStream();
    this.setupSimulationStream();
  }

  loadOptions(): void {
    this.loadOptionsTrigger$.next();
  }

  simulate(request: NewProductForecastRequest): void {
    this.lastRequestSignal.set(request);
    this.simulateTrigger$.next(request);
  }

  retryForecast(): void {
    const req = this.lastRequestSignal();
    if (!req) return;
    this.simulateTrigger$.next(req);
  }

  markDirty(): void {
    if (this.simulationStateSignal() === 'success' && this.forecastDataSignal() !== null) {
      this.isDirtySinceLastResultSignal.set(true);
    }
    if (this.forecastErrorSignal() !== null) {
      this.forecastErrorSignal.set(null);
    }
  }

  reset(): void {
    this.simulationStateSignal.set('idle');
    this.forecastDataSignal.set(null);
    this.forecastMetaSignal.set(null);
    this.forecastErrorSignal.set(null);
    this.isDirtySinceLastResultSignal.set(false);
    this.selectedSimilarSignal.set(null);
    this.lastRequestSignal.set(null);
  }

  openSimilar(similar: SimilarProductItem): void {
    this.selectedSimilarSignal.set(similar);
  }

  closeSimilar(): void {
    this.selectedSimilarSignal.set(null);
  }

  private setupOptionsStream(): void {
    this.loadOptionsTrigger$
      .pipe(
        tap(() => {
          this.optionsStateSignal.set('loading');
          this.optionsErrorSignal.set(null);
        }),
        switchMap(() =>
          this.service.getNewProductOptions().pipe(
            catchError((err: unknown) => {
              this.optionsErrorSignal.set(toNewProductApiError(err));
              this.optionsStateSignal.set('error');
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((res) => {
        this.optionsSignal.set(res.data);
        this.optionsStateSignal.set('ready');
      });
  }

  private setupSimulationStream(): void {
    this.simulateTrigger$
      .pipe(
        tap(() => {
          this.simulationStateSignal.set('loading');
          this.forecastErrorSignal.set(null);
          this.isDirtySinceLastResultSignal.set(false);
          this.selectedSimilarSignal.set(null);
        }),
        switchMap((request) =>
          this.service.simulateNewProductForecast(request).pipe(
            catchError((err: unknown) => {
              const apiError = toNewProductApiError(err);
              this.forecastErrorSignal.set(apiError);

              if (apiError?.code === 'NEW-001') {
                this.forecastDataSignal.set(null);
                this.simulationStateSignal.set('insufficient');
              } else if (
                apiError &&
                (apiError.code === 'NEW-002' ||
                  apiError.code === 'NEW-003' ||
                  (apiError.code === 'NEW-004' && apiError.fields.length > 0))
              ) {
                this.simulationStateSignal.set(this.forecastDataSignal() ? 'success' : 'idle');
              } else {
                this.forecastDataSignal.set(null);
                this.simulationStateSignal.set('error');
              }
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((res) => {
        this.forecastDataSignal.set(res.data);
        this.forecastMetaSignal.set(res.meta);
        this.forecastErrorSignal.set(null);
        this.isDirtySinceLastResultSignal.set(false);
        this.simulationStateSignal.set('success');
      });
  }
}
