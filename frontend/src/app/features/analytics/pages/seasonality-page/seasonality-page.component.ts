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
import { EMPTY, Subject, catchError, of, switchMap, tap, timer } from 'rxjs';
import { SeasonalityService } from '../../services/seasonality.service';
import {
  MonthlySeasonalityPoint,
  SEASONALITY_ERROR_CODES,
  SeasonalityApiError,
  SeasonalityConfidence,
  SeasonalityData,
  SeasonalityErrorCode,
  SeasonalityOrder,
  SeasonalityRankingItem,
  SeasonalityReason,
  SeasonalityStrength,
} from '../../models/seasonality.model';
import { AnalyticsMeta, PagedMeta } from '../../models/analytics.model';
import { ConsultedProduct } from '../../models/cross-sell.model';
import { ListPagerComponent } from '../../components/list-pager/list-pager.component';
import {
  BrlPipe,
  PtDatePipe,
  PtDecimalPipe,
  PtPercentPipe,
} from '../../pipes/pt-br-format.pipes';

interface SearchRequest {
  query: string;
  immediate: boolean;
  autoSelectSingle: boolean;
}

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

const SEARCH_MIN_CHARS = 2;
const SEARCH_MAX_CHARS = 60;
const SEARCH_DEBOUNCE_MS = 300;
const RANKING_PAGE_SIZE = 15;
const POSITIVE_INT_REGEX = /^[1-9]\d*$/;
const SUGGESTION_LABEL_REGEX = /^([1-9]\d*)\s*-\s*.+$/;
const NUMERIC_INPUT_REGEX = /^-?\d+(?:[.,]\d+)?$/;

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
    message: 'Parâmetros de paginação ou ordenação inválidos para o ranking de sazonalidade.',
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
  imports: [ListPagerComponent, PtDecimalPipe, PtPercentPipe, BrlPipe, PtDatePipe],
  templateUrl: './seasonality-page.component.html',
  styleUrl: './seasonality-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:click)': 'onDocumentClick($event)',
  },
})
export class SeasonalityPageComponent implements OnInit {
  private readonly seasonalityService = inject(SeasonalityService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly router = inject(Router, { optional: true });
  private readonly route = inject(ActivatedRoute, { optional: true });

  private readonly searchContainer = viewChild<ElementRef<HTMLElement>>('searchContainer');
  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');
  private readonly productHeading = viewChild<ElementRef<HTMLHeadingElement>>('productHeading');
  private readonly productPanel = viewChild<ElementRef<HTMLElement>>('productPanel');

  private readonly searchTrigger$ = new Subject<SearchRequest>();
  private readonly productRequest$ = new Subject<{
    sku: number;
    scrollAndFocus: boolean;
    syncUrl: boolean;
  }>();
  private readonly rankingRequest$ = new Subject<{
    order: SeasonalityOrder;
    offset: number;
  }>();

  private pendingFocusTimer: ReturnType<typeof setTimeout> | null = null;

  protected readonly searchMinChars = SEARCH_MIN_CHARS;
  protected readonly searchMaxChars = SEARCH_MAX_CHARS;
  protected readonly rankingPageSize = RANKING_PAGE_SIZE;

  protected readonly searchQuery = signal('');
  protected readonly searchResults = signal<ConsultedProduct[]>([]);
  protected readonly isSearching = signal(false);
  protected readonly showSuggestions = signal(false);
  protected readonly hasSearchedDropdown = signal(false);
  protected readonly activeSuggestionIndex = signal(-1);
  protected readonly searchValidationError = signal<string | null>(null);
  protected readonly searchFeedbackMessage = signal('');

  protected readonly selectedSku = signal<number | null>(null);
  protected readonly productData = signal<SeasonalityData | null>(null);
  protected readonly productMeta = signal<AnalyticsMeta | null>(null);
  protected readonly isLoadingProduct = signal(false);
  protected readonly productError = signal<string | null>(null);
  protected readonly productErrorDetail = signal<ParsedHttpError | null>(null);

  protected readonly activeRankingOrder = signal<SeasonalityOrder>('most');
  protected readonly rankingItems = signal<SeasonalityRankingItem[]>([]);
  protected readonly rankingMeta = signal<PagedMeta | null>(null);
  protected readonly rankingOffset = signal(0);
  protected readonly isLoadingRanking = signal(false);
  protected readonly rankingError = signal<string | null>(null);

  protected readonly hoveredMonth = signal<number | null>(null);
  protected readonly focusedMonth = signal<number | null>(null);
  protected readonly selectedMonth = signal<number | null>(null);

  protected readonly hasDropdownPanel = computed(
    () =>
      this.showSuggestions() &&
      (this.searchResults().length > 0 || this.isSearching() || this.hasSearchedDropdown()),
  );

  protected readonly activeDescendantId = computed(() => {
    const idx = this.activeSuggestionIndex();
    if (!this.hasDropdownPanel() || idx < 0 || idx >= this.searchResults().length) {
      return null;
    }
    return `seasonality-option-${idx}`;
  });

  protected readonly searchDescribedBy = computed(() => {
    const ids = ['seasonality-search-hint'];
    if (this.searchValidationError()) {
      ids.unshift('seasonality-search-error');
    }
    return ids.join(' ');
  });

  protected readonly rankingColCount = computed(() =>
    this.activeRankingOrder() === 'most' ? 9 : 7,
  );

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

    this.searchTrigger$
      .pipe(
        switchMap((req) => {
          const trimmed = req.query.trim();
          if (trimmed.length < SEARCH_MIN_CHARS || trimmed.length > SEARCH_MAX_CHARS) {
            this.isSearching.set(false);
            this.searchResults.set([]);
            this.showSuggestions.set(false);
            this.hasSearchedDropdown.set(false);
            this.activeSuggestionIndex.set(-1);
            this.searchFeedbackMessage.set('');
            return EMPTY;
          }

          const wait$ = req.immediate ? of(0) : timer(SEARCH_DEBOUNCE_MS);
          return wait$.pipe(
            tap(() => {
              this.isSearching.set(true);
              this.hasSearchedDropdown.set(false);
              this.showSuggestions.set(true);
            }),
            switchMap(() =>
              this.seasonalityService.searchProducts(trimmed, { limit: 10, offset: 0 }).pipe(
                tap((res) => {
                  const items = res.data;
                  this.searchResults.set(items);
                  this.isSearching.set(false);
                  this.hasSearchedDropdown.set(true);
                  this.activeSuggestionIndex.set(-1);

                  if (req.autoSelectSingle && items.length === 1) {
                    this.selectSuggestion(items[0]);
                    return;
                  }

                  this.showSuggestions.set(true);
                  this.announceSearchResults(items.length, trimmed);
                }),
                catchError((err: unknown) => {
                  const parsed = this.parseHttpError(err);
                  this.isSearching.set(false);
                  this.searchResults.set([]);
                  this.hasSearchedDropdown.set(false);
                  this.showSuggestions.set(false);
                  this.activeSuggestionIndex.set(-1);
                  this.searchFeedbackMessage.set(parsed.message);
                  return EMPTY;
                }),
              ),
            ),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

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

    this.rankingRequest$
      .pipe(
        switchMap((req) =>
          this.seasonalityService
            .getRanking(req.order, { limit: this.rankingPageSize, offset: req.offset })
            .pipe(
              tap((res) => {
                this.rankingItems.set(res.data);
                this.rankingMeta.set(res.meta);
                this.rankingError.set(null);
                this.isLoadingRanking.set(false);
              }),
              catchError((err: unknown) => {
                const parsed = this.parseHttpError(err);
                this.rankingError.set(parsed.message);
                this.isLoadingRanking.set(false);
                return EMPTY;
              }),
            ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();
  }

  ngOnInit(): void {
    this.loadRankings();

    this.route?.queryParamMap
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((params) => {
        const rawSku = params.get('sku')?.trim();
        if (!rawSku) return;

        if (!POSITIVE_INT_REGEX.test(rawSku)) {
          this.searchValidationError.set(
            'O código SKU informado na URL é inválido. Utilize apenas números inteiros positivos.',
          );
          return;
        }

        const sku = Number(rawSku);
        if (sku !== this.selectedSku()) {
          this.searchQuery.set(rawSku);
          this.selectProductBySku(sku, { scrollAndFocus: false, syncUrl: false });
        }
      });
  }

  protected onDocumentClick(event: Event): void {
    const container = this.searchContainer()?.nativeElement;
    const target = event.target;
    if (container && target instanceof Node && !container.contains(target)) {
      this.closeSuggestions();
    }
  }

  protected onSearchFocusOut(event: FocusEvent): void {
    const container = this.searchContainer()?.nativeElement;
    const nextFocus = event.relatedTarget;
    if (container && (!(nextFocus instanceof Node) || !container.contains(nextFocus))) {
      this.closeSuggestions();
    }
  }

  protected onSearchInput(value: string): void {
    this.searchQuery.set(value);
    this.searchValidationError.set(null);
    this.activeSuggestionIndex.set(-1);

    const trimmed = value.trim();
    if (trimmed.length > SEARCH_MAX_CHARS) {
      this.searchValidationError.set(
        `A busca pode ter no máximo ${SEARCH_MAX_CHARS} caracteres.`,
      );
      this.cancelAutocomplete();
      return;
    }

    if (trimmed.length < SEARCH_MIN_CHARS) {
      this.cancelAutocomplete();
      return;
    }

    this.searchTrigger$.next({
      query: trimmed,
      immediate: false,
      autoSelectSingle: false,
    });
  }

  protected onSearchKeydown(event: KeyboardEvent): void {
    const results = this.searchResults();
    const isDropdownOpen = this.hasDropdownPanel();

    switch (event.key) {
      case 'ArrowDown': {
        if (results.length === 0) return;
        event.preventDefault();
        if (!isDropdownOpen) {
          this.showSuggestions.set(true);
          this.activeSuggestionIndex.set(0);
        } else {
          const next = (this.activeSuggestionIndex() + 1) % results.length;
          this.activeSuggestionIndex.set(next);
        }
        this.scrollActiveOptionIntoView();
        break;
      }
      case 'ArrowUp': {
        if (results.length === 0) return;
        event.preventDefault();
        if (!isDropdownOpen) {
          this.showSuggestions.set(true);
          this.activeSuggestionIndex.set(results.length - 1);
        } else {
          const curr = this.activeSuggestionIndex();
          const prev = curr <= 0 ? results.length - 1 : curr - 1;
          this.activeSuggestionIndex.set(prev);
        }
        this.scrollActiveOptionIntoView();
        break;
      }
      case 'Home': {
        if (isDropdownOpen && results.length > 0) {
          event.preventDefault();
          this.activeSuggestionIndex.set(0);
          this.scrollActiveOptionIntoView();
        }
        break;
      }
      case 'End': {
        if (isDropdownOpen && results.length > 0) {
          event.preventDefault();
          this.activeSuggestionIndex.set(results.length - 1);
          this.scrollActiveOptionIntoView();
        }
        break;
      }
      case 'Enter': {
        event.preventDefault();
        const activeIdx = this.activeSuggestionIndex();
        if (this.showSuggestions() && activeIdx >= 0 && activeIdx < results.length) {
          this.selectSuggestion(results[activeIdx]);
          return;
        }
        this.submitSearch();
        break;
      }
      case 'Escape': {
        if (this.showSuggestions()) {
          event.preventDefault();
          this.closeSuggestions();
        } else if (this.searchQuery().length > 0) {
          event.preventDefault();
          this.clearSearch();
        }
        break;
      }
    }
  }

  protected submitSearch(): void {
    const trimmed = this.searchQuery().trim();
    this.searchValidationError.set(null);

    if (!trimmed) {
      this.searchValidationError.set('Informe um código SKU ou nome do produto para analisar.');
      this.focusSearchInput();
      return;
    }

    if (trimmed.length > SEARCH_MAX_CHARS) {
      this.searchValidationError.set(
        `A busca pode ter no máximo ${SEARCH_MAX_CHARS} caracteres.`,
      );
      this.focusSearchInput();
      return;
    }

    if (POSITIVE_INT_REGEX.test(trimmed)) {
      this.cancelAutocomplete();
      this.selectProductBySku(Number(trimmed), { scrollAndFocus: false, syncUrl: true });
      return;
    }

    const labelMatch = SUGGESTION_LABEL_REGEX.exec(trimmed);
    if (labelMatch) {
      this.cancelAutocomplete();
      this.selectProductBySku(Number(labelMatch[1]), { scrollAndFocus: false, syncUrl: true });
      return;
    }

    if (NUMERIC_INPUT_REGEX.test(trimmed)) {
      this.searchValidationError.set(
        'Informe um código SKU numérico inteiro e positivo (ex.: 1042).',
      );
      this.cancelAutocomplete();
      this.focusSearchInput();
      return;
    }

    if (trimmed.length < SEARCH_MIN_CHARS) {
      this.searchValidationError.set(
        `Digite ao menos ${SEARCH_MIN_CHARS} caracteres para buscar por descrição ou informe um SKU numérico.`,
      );
      this.focusSearchInput();
      return;
    }

    const results = this.searchResults();
    const activeIdx = this.activeSuggestionIndex();
    if (activeIdx >= 0 && activeIdx < results.length) {
      this.selectSuggestion(results[activeIdx]);
      return;
    }
    if (results.length === 1 && this.hasSearchedDropdown()) {
      this.selectSuggestion(results[0]);
      return;
    }
    if (results.length > 1 && this.hasSearchedDropdown()) {
      this.showSuggestions.set(true);
      this.activeSuggestionIndex.set(0);
      this.announceSearchResults(results.length, trimmed);
      return;
    }

    this.searchTrigger$.next({
      query: trimmed,
      immediate: true,
      autoSelectSingle: true,
    });
  }

  protected selectSuggestion(item: ConsultedProduct): void {
    this.searchQuery.set(`${item.codigo} - ${item.descricao}`);
    this.searchValidationError.set(null);
    this.cancelAutocomplete();
    this.selectProductBySku(item.codigo, { scrollAndFocus: false, syncUrl: true });
  }

  protected clearSearch(): void {
    this.searchQuery.set('');
    this.searchValidationError.set(null);
    this.cancelAutocomplete();
    this.focusSearchInput();
  }

  protected resetSearchAndProduct(): void {
    this.searchQuery.set('');
    this.searchValidationError.set(null);
    this.selectedSku.set(null);
    this.productData.set(null);
    this.productMeta.set(null);
    this.productError.set(null);
    this.productErrorDetail.set(null);
    this.clearMonthInspection();
    this.cancelAutocomplete();
    this.syncSkuQueryParam(null);
    this.focusSearchInput();
  }

  protected focusSearchInput(): void {
    this.searchInput()?.nativeElement.focus();
  }

  protected selectFirstRankedProduct(): void {
    const first = this.rankingItems()[0];
    if (!first) return;
    this.searchQuery.set(`${first.sku} - ${first.descricao}`);
    this.selectProductBySku(first.sku, { scrollAndFocus: true, syncUrl: true });
  }

  protected selectProductBySku(
    sku: number,
    options: ProductSelectionOptions = {},
  ): void {
    if (!Number.isInteger(sku) || sku <= 0) {
      this.searchValidationError.set(
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
    this.searchValidationError.set(null);
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

  protected setRankingOrder(order: SeasonalityOrder): void {
    if (this.activeRankingOrder() === order) return;
    this.activeRankingOrder.set(order);
    this.rankingOffset.set(0);
    this.loadRankings();
  }

  protected onRankingPageChange(page: number): void {
    const offset = Math.max(0, (page - 1) * this.rankingPageSize);
    this.rankingOffset.set(offset);
    this.loadRankings();
  }

  protected loadRankings(): void {
    this.isLoadingRanking.set(true);
    this.rankingError.set(null);
    this.rankingRequest$.next({
      order: this.activeRankingOrder(),
      offset: this.rankingOffset(),
    });
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

  private closeSuggestions(): void {
    this.showSuggestions.set(false);
    this.activeSuggestionIndex.set(-1);
  }

  private cancelAutocomplete(): void {
    this.searchTrigger$.next({ query: '', immediate: true, autoSelectSingle: false });
    this.closeSuggestions();
    this.isSearching.set(false);
    this.hasSearchedDropdown.set(false);
  }

  private announceSearchResults(count: number, query: string): void {
    if (count === 0) {
      this.searchFeedbackMessage.set(`Nenhum produto encontrado para "${query}".`);
      return;
    }
    const plural = count === 1 ? 'produto encontrado' : 'produtos encontrados';
    this.searchFeedbackMessage.set(
      `${count} ${plural} para "${query}". Use as setas para navegar e Enter para selecionar.`,
    );
  }

  private scrollActiveOptionIntoView(): void {
    const id = this.activeDescendantId();
    if (!id || typeof document === 'undefined') return;
    const optionEl = document.getElementById(id);
    optionEl?.scrollIntoView?.({ block: 'nearest' });
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
