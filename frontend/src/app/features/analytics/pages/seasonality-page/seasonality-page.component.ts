import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { SeasonalityService } from '../../services/seasonality.service';
import {
  MonthlySeasonalityPoint,
  SEASONALITY_ERROR_CODES,
  SeasonalityApiError,
  SeasonalityConfidence,
  SeasonalityData,
  SeasonalityErrorCode,
  SeasonalityReason,
  SeasonalityStrength,
} from '../../models/seasonality.model';
import { AnalyticsMeta } from '../../models/analytics.model';
import { CatalogProductItem } from '../../models/cross-sell.model';
import { ProductCatalogExplorerComponent } from '../../components/product-catalog-explorer/product-catalog-explorer.component';
import {
  BrlPipe,
  PtDatePipe,
  PtDecimalPipe,
  PtPercentPipe,
} from '../../pipes/pt-br-format.pipes';

interface ProductSelectionOptions {
  scrollAndFocus?: boolean;
  syncUrl?: boolean;
}

interface ParsedHttpError {
  code: SeasonalityErrorCode | null;
  message: string;
  isNotFound: boolean;
  retryable: boolean;
}

const POSITIVE_INT_REGEX = /^[1-9]\d*$/;

const SEASONALITY_ERROR_COPY: Record<
  SeasonalityErrorCode,
  { message: string; isNotFound: boolean; retryable: boolean }
> = {
  'SEA-001': {
    message: 'Produto não encontrado na base histórica de sazonalidade. Verifique o código SKU informado.',
    isNotFound: true,
    retryable: false,
  },
  'SEA-002': {
    message: 'Parâmetro inválido. Informe um código SKU numérico inteiro e positivo (ex.: 1042).',
    isNotFound: false,
    retryable: false,
  },
  'SEA-003': {
    message: 'Base de vendas insuficiente para calcular sazonalidade dos produtos.',
    isNotFound: false,
    retryable: false,
  },
  'ANL-001': {
    message: 'Os dados de sazonalidade ainda estão sendo preparados ou o serviço está temporariamente indisponível.',
    isNotFound: false,
    retryable: true,
  },
  'ANL-002': {
    message: 'Não foi possível concluir o cálculo de sazonalidade neste momento. Tente novamente em instantes.',
    isNotFound: false,
    retryable: true,
  },
};

@Component({
  selector: 'app-seasonality-page',
  standalone: true,
  imports: [ProductCatalogExplorerComponent, PtDecimalPipe, PtPercentPipe, BrlPipe, PtDatePipe],
  templateUrl: './seasonality-page.component.html',
  styleUrl: './seasonality-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SeasonalityPageComponent implements OnInit {
  private readonly seasonalityService = inject(SeasonalityService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly router = inject(Router, { optional: true });
  private readonly route = inject(ActivatedRoute, { optional: true });

  private readonly productHeading = viewChild<ElementRef<HTMLHeadingElement>>('productHeading');
  private readonly productPanel = viewChild<ElementRef<HTMLElement>>('productPanel');

  private readonly productRequest$ = new Subject<{
    sku: number;
    scrollAndFocus: boolean;
    syncUrl: boolean;
  }>();

  private pendingFocusTimer: ReturnType<typeof setTimeout> | null = null;

  protected readonly selectedSku = signal<number | null>(null);
  protected readonly productData = signal<SeasonalityData | null>(null);
  protected readonly productMeta = signal<AnalyticsMeta | null>(null);
  protected readonly isLoadingProduct = signal(false);
  protected readonly productError = signal<string | null>(null);
  protected readonly productErrorDetail = signal<ParsedHttpError | null>(null);
  protected readonly urlValidationError = signal<string | null>(null);

  protected readonly hoveredMonth = signal<number | null>(null);
  protected readonly focusedMonth = signal<number | null>(null);
  protected readonly selectedMonth = signal<number | null>(null);

  protected readonly chartMaxScale = computed(() => {
    const data = this.productData();
    if (!data || data.serieMensal.length === 0) {
      return 2.0;
    }
    const maxVal = Math.max(1.2, ...data.serieMensal.map((m) => m.indice));
    return Math.ceil(maxVal * 1.18 * 10) / 10;
  });

  protected readonly hasFlatSeries = computed(() => {
    const data = this.productData();
    if (!data || !data.elegivel) return false;
    return data.amplitude <= 0;
  });

  protected readonly hasLowConfidenceMonth = computed(() => {
    const data = this.productData();
    if (!data || !data.elegivel) return false;
    return data.serieMensal.some((m) => m.confianca === 'BAIXA');
  });

  protected readonly activeMonthPoint = computed<MonthlySeasonalityPoint | null>(() => {
    const data = this.productData();
    if (!data || data.serieMensal.length === 0) return null;
    const month = this.hoveredMonth() ?? this.focusedMonth() ?? this.selectedMonth();
    if (month === null) return null;
    return data.serieMensal.find((point) => point.mes === month) ?? null;
  });

  constructor() {
    this.destroyRef.onDestroy(() => {
      if (this.pendingFocusTimer !== null) {
        clearTimeout(this.pendingFocusTimer);
        this.pendingFocusTimer = null;
      }
    });

    this.productRequest$
      .pipe(
        switchMap((req) =>
          this.seasonalityService.getSeasonality(req.sku).pipe(
            tap((res) => {
              this.productData.set(res.data);
              this.productMeta.set(res.meta);
              this.productError.set(null);
              this.productErrorDetail.set(null);
              this.isLoadingProduct.set(false);
              if (req.scrollAndFocus) {
                this.focusProductPanelDeferred();
              }
            }),
            catchError((err: unknown) => {
              const parsed = this.parseHttpError(err);
              this.productData.set(null);
              this.productMeta.set(null);
              this.productError.set(parsed.message);
              this.productErrorDetail.set(parsed);
              this.isLoadingProduct.set(false);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();
  }

  ngOnInit(): void {
    this.route?.queryParamMap
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((params) => {
        const rawSku = params.get('sku')?.trim();
        if (!rawSku) {
          this.urlValidationError.set(null);
          if (this.selectedSku() !== null || this.productData() !== null || this.productError() !== null) {
            this.clearSelectedProductState();
          }
          return;
        }

        if (!POSITIVE_INT_REGEX.test(rawSku)) {
          this.clearSelectedProductState();
          this.urlValidationError.set(
            'O código SKU informado na URL é inválido. Utilize apenas números inteiros positivos.',
          );
          return;
        }

        const sku = Number(rawSku);
        this.urlValidationError.set(null);
        if (sku !== this.selectedSku()) {
          this.selectProductBySku(sku, { scrollAndFocus: false, syncUrl: false });
        }
      });
  }

  protected onCatalogProductSelect(item: CatalogProductItem): void {
    this.urlValidationError.set(null);
    this.selectProductBySku(item.codigo, { scrollAndFocus: true, syncUrl: true });
  }

  protected clearSelectedProduct(): void {
    this.clearSelectedProductState();
    this.urlValidationError.set(null);
    this.syncSkuQueryParam(null);
  }

  protected selectProductBySku(
    sku: number,
    options: ProductSelectionOptions = {},
  ): void {
    if (!Number.isInteger(sku) || sku <= 0) {
      this.urlValidationError.set(
        'Informe um código SKU numérico inteiro e positivo (ex.: 1042).',
      );
      return;
    }

    const scrollAndFocus = options.scrollAndFocus ?? false;
    const syncUrl = options.syncUrl ?? true;

    this.selectedSku.set(sku);
    this.isLoadingProduct.set(true);
    this.productError.set(null);
    this.productErrorDetail.set(null);
    this.urlValidationError.set(null);
    this.clearMonthInspection();

    if (syncUrl) {
      this.syncSkuQueryParam(sku);
    }

    this.productRequest$.next({ sku, scrollAndFocus, syncUrl });
  }

  protected retrySelectedProduct(): void {
    const sku = this.selectedSku();
    if (sku !== null) {
      this.selectProductBySku(sku, { scrollAndFocus: false, syncUrl: false });
    }
  }

  protected onBarHover(month: number | null): void {
    this.hoveredMonth.set(month);
  }

  protected onBarFocus(month: number | null): void {
    this.focusedMonth.set(month);
  }

  protected toggleMonthSelection(month: number): void {
    this.selectedMonth.update((current) => (current === month ? null : month));
  }

  protected clearMonthInspection(): void {
    this.hoveredMonth.set(null);
    this.focusedMonth.set(null);
    this.selectedMonth.set(null);
  }

  protected isMonthInspected(month: number): boolean {
    return this.activeMonthPoint()?.mes === month;
  }

  protected getBarHeightPercent(indice: number): number {
    if (indice <= 0) return 0;
    const maxScale = this.chartMaxScale();
    if (maxScale <= 0) return 0;
    return Math.min(100, Math.max(3, (indice / maxScale) * 100));
  }

  protected getBaselineBottomPercent(): number {
    const maxScale = this.chartMaxScale();
    if (maxScale <= 0) return 0;
    return Math.min(100, (1.0 / maxScale) * 100);
  }

  protected isMonthInPeriod(month: number, start: number, end: number): boolean {
    if (start <= end) {
      return month >= start && month <= end;
    }
    return month >= start || month <= end;
  }

  protected isPeakMonth(month: number): boolean {
    const data = this.productData();
    if (!data || !data.elegivel || data.amplitude <= 0) return false;
    return this.isMonthInPeriod(month, data.pico.mesInicio, data.pico.mesFim);
  }

  protected isValleyMonth(month: number): boolean {
    const data = this.productData();
    if (!data || !data.elegivel || data.amplitude <= 0) return false;
    if (this.isPeakMonth(month)) return false;
    return this.isMonthInPeriod(month, data.vale.mesInicio, data.vale.mesFim);
  }

  protected getBarStateLabel(pt: MonthlySeasonalityPoint): string {
    if (this.isPeakMonth(pt.mes)) return 'Mês de pico sazonal';
    if (this.isValleyMonth(pt.mes)) return 'Mês de vale sazonal';
    return 'Comportamento próximo à média';
  }

  protected getStrengthTagClass(strength: SeasonalityStrength): string {
    switch (strength) {
      case 'FORTE':
        return 'tag-positive';
      case 'MODERADA':
        return 'tag-info';
      case 'FRACA':
        return 'tag-warning';
      case 'INSUFICIENTE':
        return 'tag-critical';
    }
  }

  protected getStrengthLabel(strength: SeasonalityStrength): string {
    switch (strength) {
      case 'FORTE':
        return 'Sazonalidade Forte';
      case 'MODERADA':
        return 'Sazonalidade Moderada';
      case 'FRACA':
        return 'Sazonalidade Fraca';
      case 'INSUFICIENTE':
        return 'Histórico Insuficiente';
    }
  }

  protected getConfidenceTagClass(conf: SeasonalityConfidence): string {
    switch (conf) {
      case 'ALTA':
        return 'tag-positive';
      case 'MEDIA':
        return 'tag-warning';
      case 'BAIXA':
        return 'tag-neutral';
    }
  }

  protected getConfidenceLabel(conf: SeasonalityConfidence): string {
    switch (conf) {
      case 'ALTA':
        return 'Confiança Alta (2 anos)';
      case 'MEDIA':
        return 'Confiança Média';
      case 'BAIXA':
        return 'Confiança Baixa (1 ano)';
    }
  }

  protected getConfidenceShortLabel(conf: SeasonalityConfidence): string {
    switch (conf) {
      case 'ALTA':
        return '2 anos';
      case 'MEDIA':
        return 'Média';
      case 'BAIXA':
        return '1 ano';
    }
  }

  protected getReasonText(reason: SeasonalityReason): string {
    if (reason === 'HISTORICO_CURTO') {
      return 'Histórico inferior a 12 meses com vendas válidas';
    }
    if (reason === 'VENDA_ESPORADICA') {
      return 'Venda esporádica (inferior a 6 meses ativos no ano)';
    }
    return 'Sem restrições de mensuração';
  }

  protected getReasonDetailedGuidance(reason: SeasonalityReason): string {
    if (reason === 'HISTORICO_CURTO') {
      return 'Este produto ainda não acumulou ao menos 12 meses completos desde a primeira venda com faturamento líquido positivo. Assim que completar um ciclo anual completo, a curva sazonal será liberada automaticamente.';
    }
    if (reason === 'VENDA_ESPORADICA') {
      return 'O produto possui vendas em menos de 6 meses nos últimos 12 meses analisados. Com demanda muito concentrada ou esporádica, o índice mensal estatístico não representa um padrão confiável de reposição.';
    }
    return 'Este produto ainda não atingiu os critérios mínimos de consistência histórica para geração da curva sazonal.';
  }

  protected formatMonthAriaLabel(pt: MonthlySeasonalityPoint): string {
    const idxFormatted = pt.indice.toFixed(2).replace('.', ',');
    const state = this.getBarStateLabel(pt);
    const conf = this.getConfidenceLabel(pt.confianca);
    return `${pt.nomeMes}: índice ${idxFormatted}x, ${state}, ${conf}. Selecione para detalhar volume e faturamento.`;
  }

  private clearSelectedProductState(): void {
    this.selectedSku.set(null);
    this.productData.set(null);
    this.productMeta.set(null);
    this.isLoadingProduct.set(false);
    this.productError.set(null);
    this.productErrorDetail.set(null);
    this.clearMonthInspection();
  }

  private focusProductPanelDeferred(): void {
    if (this.pendingFocusTimer !== null) {
      clearTimeout(this.pendingFocusTimer);
    }
    this.pendingFocusTimer = setTimeout(() => {
      this.pendingFocusTimer = null;
      const panelEl = this.productPanel()?.nativeElement;
      const headingEl = this.productHeading()?.nativeElement;
      const prefersReduced =
        typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      panelEl?.scrollIntoView?.({
        behavior: prefersReduced ? 'auto' : 'smooth',
        block: 'start',
      });
      headingEl?.focus?.({ preventScroll: true });
    }, 0);
  }

  private syncSkuQueryParam(sku: number | null): void {
    if (!this.router) return;
    const currentSku = this.route?.snapshot.queryParamMap.get('sku');
    const nextSku = sku === null ? null : String(sku);
    if (currentSku === nextSku) return;

    void this.router.navigate([], {
      relativeTo: this.route ?? undefined,
      queryParams: { sku: nextSku },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  private parseHttpError(err: unknown): ParsedHttpError {
    if (err instanceof HttpErrorResponse) {
      const apiError = this.extractSeasonalityApiError(err.error);
      if (apiError) {
        const mapped = SEASONALITY_ERROR_COPY[apiError.code];
        return {
          code: apiError.code,
          message: mapped.message,
          isNotFound: mapped.isNotFound,
          retryable: mapped.retryable,
        };
      }
      if (err.status === 0) {
        return {
          code: null,
          message:
            'Não foi possível conectar ao servidor de análise. Verifique sua conexão e tente novamente.',
          isNotFound: false,
          retryable: true,
        };
      }
      if (err.status === 404) {
        return {
          code: 'SEA-001',
          message: SEASONALITY_ERROR_COPY['SEA-001'].message,
          isNotFound: true,
          retryable: false,
        };
      }
      if (err.status >= 500) {
        return {
          code: null,
          message:
            'O serviço de análise retornou uma instabilidade temporária. Tente novamente em instantes.',
          isNotFound: false,
          retryable: true,
        };
      }
    }
    return {
      code: null,
      message: 'Não foi possível carregar os dados de sazonalidade agora. Tente novamente.',
      isNotFound: false,
      retryable: true,
    };
  }

  private extractSeasonalityApiError(body: unknown): SeasonalityApiError | null {
    if (typeof body !== 'object' || body === null || !('error' in body)) {
      return null;
    }
    const rawError = (body as Record<string, unknown>)['error'];
    if (typeof rawError !== 'object' || rawError === null) {
      return null;
    }
    const record = rawError as Record<string, unknown>;
    const rawCode = record['code'];
    const rawMessage = record['message'];
    const rawFields = record['fields'];

    if (typeof rawCode !== 'string' || typeof rawMessage !== 'string') {
      return null;
    }

    const validCode = SEASONALITY_ERROR_CODES.find((c) => c === rawCode);
    if (!validCode) return null;

    const fields = Array.isArray(rawFields)
      ? rawFields.filter((f): f is string => typeof f === 'string')
      : [];

    return {
      code: validCode,
      message: rawMessage,
      fields,
    };
  }
}
