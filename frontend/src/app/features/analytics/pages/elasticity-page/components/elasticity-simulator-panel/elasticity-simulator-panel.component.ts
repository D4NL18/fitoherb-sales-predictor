import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { InfoHelpComponent } from '../../../../components/info-help/info-help.component';
import {
  ProductElasticityMetrics,
  ProductHeader,
  SimulationImpactData,
} from '../../../../models/elasticity.models';
import { BrlPipe, PtDecimalPipe } from '../../../../pipes/pt-br-format.pipes';
import {
  ELASTICITY_HELP_COPY,
  buildTechnicalSummaryHelp,
} from '../../../../utils/elasticity-help-copy';
import {
  PRICE_CHANGE_MAX,
  PRICE_CHANGE_MIN,
  PRICE_PRESETS,
  STOCK_COVERAGE_BAR_MAX_DAYS,
  STOCK_TARGET_DAYS_DEFAULT,
  computeUnitMargin,
  deltaTone,
  formatSignedCurrency,
  formatSignedPercentValue,
  formatSignedPp,
  formatSignedStockDays,
  formatSignedUnits,
  formatStockDays,
  formatUnits,
  getStockCoverageStatus,
  sliderMarkLeftPct,
} from '../../../../utils/elasticity-view';
import { formatDecimal } from '../../../../utils/pt-br-format';

@Component({
  selector: 'app-elasticity-simulator-panel',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, InfoHelpComponent],
  templateUrl: './elasticity-simulator-panel.component.html',
  styleUrl: './elasticity-simulator-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticitySimulatorPanelComponent {
  readonly product = input.required<ProductHeader>();
  readonly elasticity = input.required<ProductElasticityMetrics>();
  readonly priceChangePct = input.required<number>();
  readonly customCostPrice = input<number | null>(null);
  readonly customCurrentPrice = input<number | null>(null);
  readonly simulationResult = input<SimulationImpactData | null>(null);
  readonly isSimulating = input<boolean>(false);
  readonly simulationError = input<string | null>(null);

  readonly priceSliderInput = output<number>();
  readonly pricePresetSelect = output<number>();
  readonly priceNumberCommit = output<number>();
  readonly costChange = output<number>();
  readonly resetCost = output<void>();
  readonly currentPriceChange = output<number>();
  readonly currentPriceCommit = output<number>();
  readonly resetCurrentPrice = output<void>();
  readonly retrySimulation = output<void>();

  protected readonly minPct = PRICE_CHANGE_MIN;
  protected readonly maxPct = PRICE_CHANGE_MAX;
  protected readonly presets = PRICE_PRESETS;
  protected readonly helpCopy = ELASTICITY_HELP_COPY;
  protected readonly scaleMarks = [
    { value: -50, label: '-50%', leftPct: sliderMarkLeftPct(-50), align: 'start' as const },
    { value: 0, label: '0%', leftPct: sliderMarkLeftPct(0), align: 'center' as const },
    { value: 50, label: '+50%', leftPct: sliderMarkLeftPct(50), align: 'center' as const },
    { value: 100, label: '+100%', leftPct: sliderMarkLeftPct(100), align: 'end' as const },
  ];

  protected readonly inputText = signal<string>('5');
  protected readonly localValidationError = signal<string | null>(null);
  protected readonly currentPriceInputText = signal<string>('0');
  protected readonly currentPriceValidationError = signal<string | null>(null);
  protected readonly costInputText = signal<string>('0');
  protected readonly costValidationError = signal<string | null>(null);

  protected readonly hasAnyLocalValidationError = computed(
    () =>
      this.localValidationError() !== null ||
      this.currentPriceValidationError() !== null ||
      this.costValidationError() !== null,
  );

  protected readonly pctOrApiError = computed(
    () => this.localValidationError() ?? this.simulationError(),
  );

  protected readonly hasInlineApiError = computed(
    () => this.simulationError() !== null && this.localValidationError() === null,
  );

  protected readonly technicalSummaryHelp = computed(() =>
    buildTechnicalSummaryHelp(this.elasticity()),
  );

  protected readonly formattedStock = computed(() => formatUnits(this.product().stock));
  protected readonly recentVolume60d = computed(() => this.product().recentVolume60d ?? 0);
  protected readonly formattedRecentVolume60d = computed(() =>
    formatUnits(this.recentVolume60d()),
  );

  protected readonly stockTargetDays = computed(
    () => this.simulationResult()?.stockTargetDays ?? this.product().stockTargetDays ?? STOCK_TARGET_DAYS_DEFAULT,
  );

  protected readonly isPriceOverrideActive = computed(() => {
    const custom = this.customCurrentPrice();
    return custom !== null && custom !== undefined;
  });

  protected readonly currentPriceOriginLabel = computed(() =>
    this.isPriceOverrideActive() ? 'Editado manualmente' : 'Catálogo ERP',
  );

  protected readonly currentPriceOriginTone = computed<'manual' | 'erp'>(() =>
    this.isPriceOverrideActive() ? 'manual' : 'erp',
  );

  protected readonly currentPriceSourceShortLabel = computed(() => {
    const sim = this.simulationResult();
    if (sim?.isPriceOverride || this.isPriceOverrideActive()) return 'Manual';
    return 'ERP';
  });

  protected readonly effectiveCurrentPrice = computed(
    () => this.simulationResult()?.currentPrice ?? this.customCurrentPrice() ?? this.product().currentPrice,
  );

  protected readonly isCostOverrideActive = computed(() => {
    const custom = this.customCostPrice();
    return custom !== null && custom !== undefined;
  });

  protected readonly isCatalogCostEstimated = computed(() => Boolean(this.product().isCostEstimated));

  protected readonly costOriginLabel = computed(() => {
    if (this.isCostOverrideActive()) return 'Editado manualmente';
    if (this.isCatalogCostEstimated()) return 'Estimado (60% do preço)';
    return 'Catálogo ERP';
  });

  protected readonly costOriginTone = computed<'manual' | 'estimated' | 'erp'>(() => {
    if (this.isCostOverrideActive()) return 'manual';
    if (this.isCatalogCostEstimated()) return 'estimated';
    return 'erp';
  });

  protected readonly costSourceShortLabel = computed(() => {
    const sim = this.simulationResult();
    if (sim?.isCostOverride || this.isCostOverrideActive()) return 'Manual';
    if (sim?.isCostEstimated ?? this.isCatalogCostEstimated()) return '60% est.';
    return 'ERP';
  });

  protected readonly effectiveCost = computed(
    () => this.simulationResult()?.costPrice ?? this.customCostPrice() ?? this.product().costPrice,
  );

  protected readonly sliderValueText = computed(() => {
    const val = this.priceChangePct();
    if (val === 0) return '0% (sem alteração de preço)';
    return `${formatSignedPercentValue(val, 1)} de variação no preço`;
  });

  protected readonly currentUnitMargin = computed(() => {
    const sim = this.simulationResult();
    if (sim?.currentUnitMargin !== undefined) return sim.currentUnitMargin;
    const price = sim?.currentPrice ?? this.effectiveCurrentPrice();
    return computeUnitMargin(price, this.effectiveCost()).amount;
  });

  protected readonly projectedUnitMargin = computed(() => {
    const sim = this.simulationResult();
    if (sim?.projectedUnitMargin !== undefined) return sim.projectedUnitMargin;
    const price = sim?.projectedPrice ?? this.effectiveCurrentPrice();
    return computeUnitMargin(price, this.effectiveCost()).amount;
  });

  protected readonly currentUnitMarginPct = computed(() => {
    const sim = this.simulationResult();
    if (sim?.currentUnitMarginPct !== undefined) return sim.currentUnitMarginPct;
    const price = sim?.currentPrice ?? this.effectiveCurrentPrice();
    return computeUnitMargin(price, this.effectiveCost()).marginPct;
  });

  protected readonly projectedUnitMarginPct = computed(() => {
    const sim = this.simulationResult();
    if (sim?.projectedUnitMarginPct !== undefined) return sim.projectedUnitMarginPct;
    const price = sim?.projectedPrice ?? this.effectiveCurrentPrice();
    return computeUnitMargin(price, this.effectiveCost()).marginPct;
  });

  protected readonly unitMarginDiff = computed(
    () => this.projectedUnitMargin() - this.currentUnitMargin(),
  );

  protected readonly unitMarginPctChangePp = computed(() => {
    const sim = this.simulationResult();
    if (sim?.unitMarginPctChangePp !== undefined) return sim.unitMarginPctChangePp;
    return this.projectedUnitMarginPct() - this.currentUnitMarginPct();
  });

  protected readonly formattedCurrentUnitMarginPct = computed(
    () => `${formatDecimal(this.currentUnitMarginPct(), 1)}%`,
  );

  protected readonly formattedProjectedUnitMarginPct = computed(
    () => `${formatDecimal(this.projectedUnitMarginPct(), 1)}%`,
  );

  protected readonly unitMarginTone = computed(() => deltaTone(this.unitMarginDiff()));

  protected readonly volumeChangeUnits = computed(() => {
    const sim = this.simulationResult();
    if (!sim) return 0;
    return sim.volumeChangeUnits ?? sim.projectedVolume - sim.currentVolume;
  });

  protected readonly currentDailyUnits = computed(() => {
    const sim = this.simulationResult();
    if (!sim) return 0;
    return sim.currentDailyUnits ?? sim.currentVolume / this.stockTargetDays();
  });

  protected readonly projectedDailyUnits = computed(() => {
    const sim = this.simulationResult();
    if (!sim) return 0;
    return sim.projectedDailyUnits ?? sim.projectedVolume / this.stockTargetDays();
  });

  protected readonly stockValue = computed(
    () => this.simulationResult()?.stock ?? this.product().stock,
  );

  protected readonly currentStockDays = computed<number | null>(() => {
    const sim = this.simulationResult();
    if (!sim) return null;
    if (sim.currentStockDays !== undefined) return sim.currentStockDays;
    const daily = this.currentDailyUnits();
    return daily > 0 ? Math.max(0, this.stockValue()) / daily : null;
  });

  protected readonly projectedStockDays = computed<number | null>(() => {
    const sim = this.simulationResult();
    if (!sim) return null;
    if (sim.projectedStockDays !== undefined) return sim.projectedStockDays;
    const daily = this.projectedDailyUnits();
    return daily > 0 ? Math.max(0, this.stockValue()) / daily : null;
  });

  protected readonly stockDaysDelta = computed<number | null>(() => {
    const sim = this.simulationResult();
    if (!sim) return null;
    if (sim.stockDaysDelta !== undefined) return sim.stockDaysDelta;
    const current = this.currentStockDays();
    const projected = this.projectedStockDays();
    if (current === null || projected === null) return null;
    return projected - current;
  });

  protected readonly currentStockDaysText = computed(() => formatStockDays(this.currentStockDays()));
  protected readonly projectedStockDaysText = computed(() => formatStockDays(this.projectedStockDays()));
  protected readonly stockDaysDeltaText = computed(() => formatSignedStockDays(this.stockDaysDelta()));

  protected readonly stockCoverageMeta = computed(() =>
    getStockCoverageStatus(
      this.projectedStockDays(),
      this.stockValue(),
      this.projectedDailyUnits(),
      this.stockTargetDays(),
    ),
  );

  protected readonly currentStockBarPct = computed(() =>
    this.toStockBarPct(this.currentStockDays()),
  );

  protected readonly projectedStockBarPct = computed(() =>
    this.toStockBarPct(this.projectedStockDays()),
  );

  protected readonly targetStockBarPct = computed(() =>
    this.toStockBarPct(this.stockTargetDays()),
  );

  protected readonly volumeTone = computed(() => {
    const sim = this.simulationResult();
    return sim ? deltaTone(sim.volumeChangePct) : 'neutral';
  });

  protected readonly revenueTone = computed(() => {
    const sim = this.simulationResult();
    return sim ? deltaTone(sim.revenueChangeAbs) : 'neutral';
  });

  protected readonly marginTone = computed(() => {
    const sim = this.simulationResult();
    return sim ? deltaTone(sim.marginChangeAbs) : 'neutral';
  });

  private lastSyncedCostSku: number | null = null;
  private lastSyncedPriceSku: number | null = null;

  constructor() {
    effect(() => {
      const pct = this.priceChangePct();
      untracked(() => {
        this.inputText.set(String(pct));
        this.localValidationError.set(null);
      });
    }, { allowSignalWrites: true });

    effect(() => {
      const prod = this.product();
      const customCost = this.customCostPrice();
      untracked(() => {
        const skuChanged = this.lastSyncedCostSku !== prod.code;
        this.lastSyncedCostSku = prod.code;

        if (customCost === null || customCost === undefined) {
          this.costInputText.set(this.formatMoneyInputValue(prod.costPrice));
          this.costValidationError.set(null);
          return;
        }

        const currentParsed = this.parseValidCost(this.costInputText());
        if (skuChanged || currentParsed !== customCost) {
          this.costInputText.set(this.formatMoneyInputValue(customCost));
          this.costValidationError.set(null);
        }
      });
    }, { allowSignalWrites: true });

    effect(() => {
      const prod = this.product();
      const customPrice = this.customCurrentPrice();
      untracked(() => {
        const skuChanged = this.lastSyncedPriceSku !== prod.code;
        this.lastSyncedPriceSku = prod.code;

        if (customPrice === null || customPrice === undefined) {
          this.currentPriceInputText.set(this.formatMoneyInputValue(prod.currentPrice));
          this.currentPriceValidationError.set(null);
          return;
        }

        const currentParsed = this.parseValidCurrentPrice(this.currentPriceInputText());
        if (skuChanged || currentParsed !== customPrice) {
          this.currentPriceInputText.set(this.formatMoneyInputValue(customPrice));
          this.currentPriceValidationError.set(null);
        }
      });
    }, { allowSignalWrites: true });
  }

  protected onSliderInput(event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    if (!Number.isFinite(value)) return;
    this.inputText.set(String(value));
    this.localValidationError.set(null);
    if (this.currentPriceValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('pct');
    this.priceSliderInput.emit(value);
  }

  protected onNumberInput(event: Event): void {
    const raw = (event.target as HTMLInputElement).value;
    this.inputText.set(raw);
    const parsed = this.parseValidPct(raw);
    if (parsed === null) {
      this.localValidationError.set(`Informe um percentual entre ${PRICE_CHANGE_MIN}% e +${PRICE_CHANGE_MAX}%.`);
      return;
    }
    this.localValidationError.set(null);
    if (this.currentPriceValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('pct');
    this.priceSliderInput.emit(parsed);
  }

  protected onNumberCommit(): void {
    const parsed = this.parseValidPct(this.inputText());
    if (parsed === null) {
      this.localValidationError.set(`Informe um percentual entre ${PRICE_CHANGE_MIN}% e +${PRICE_CHANGE_MAX}%.`);
      return;
    }
    this.localValidationError.set(null);
    if (this.currentPriceValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('pct');
    this.priceNumberCommit.emit(parsed);
  }

  protected onCurrentPriceInput(event: Event): void {
    const raw = (event.target as HTMLInputElement).value;
    this.currentPriceInputText.set(raw);
    const parsed = this.parseValidCurrentPrice(raw);
    if (parsed === null) {
      this.currentPriceValidationError.set('Informe um preço atual maior que R$ 0,00.');
      return;
    }
    this.currentPriceValidationError.set(null);
    if (this.localValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('currentPrice');
    this.currentPriceChange.emit(parsed);
  }

  protected onCurrentPriceCommit(): void {
    const parsed = this.parseValidCurrentPrice(this.currentPriceInputText());
    if (parsed === null) {
      this.currentPriceValidationError.set('Informe um preço atual maior que R$ 0,00.');
      return;
    }
    this.currentPriceValidationError.set(null);
    if (this.localValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('currentPrice');
    this.currentPriceCommit.emit(parsed);
  }

  protected onResetCurrentPriceClick(): void {
    this.currentPriceValidationError.set(null);
    this.currentPriceInputText.set(this.formatMoneyInputValue(this.product().currentPrice));
    if (this.localValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('currentPrice');
    this.resetCurrentPrice.emit();
  }

  protected onCostInput(event: Event): void {
    const raw = (event.target as HTMLInputElement).value;
    this.costInputText.set(raw);
    const parsed = this.parseValidCost(raw);
    if (parsed === null) {
      this.costValidationError.set('Informe um custo unitário igual ou maior que R$ 0,00.');
      return;
    }
    this.costValidationError.set(null);
    if (this.localValidationError() !== null || this.currentPriceValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('cost');
    this.costChange.emit(parsed);
  }

  protected onResetCostClick(): void {
    this.costValidationError.set(null);
    this.costInputText.set(this.formatMoneyInputValue(this.product().costPrice));
    if (this.localValidationError() !== null || this.currentPriceValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('cost');
    this.resetCost.emit();
  }

  protected selectPreset(preset: number): void {
    this.inputText.set(String(preset));
    this.localValidationError.set(null);
    if (this.currentPriceValidationError() !== null || this.costValidationError() !== null) return;
    this.syncPendingValidPremisesIfNeeded('pct');
    this.pricePresetSelect.emit(preset);
  }

  private syncPendingValidPremisesIfNeeded(exclude?: 'pct' | 'currentPrice' | 'cost'): void {
    if (exclude !== 'pct') {
      const parsedPct = this.parseValidPct(this.inputText());
      if (parsedPct !== null && parsedPct !== this.priceChangePct()) {
        this.priceSliderInput.emit(parsedPct);
      }
    }

    if (exclude !== 'currentPrice') {
      const parsedPrice = this.parseValidCurrentPrice(this.currentPriceInputText());
      const activePrice = this.customCurrentPrice() ?? this.product().currentPrice;
      if (parsedPrice !== null && parsedPrice !== activePrice) {
        this.currentPriceChange.emit(parsedPrice);
      }
    }

    if (exclude !== 'cost') {
      const parsedCost = this.parseValidCost(this.costInputText());
      const activeCost = this.customCostPrice() ?? this.product().costPrice;
      if (parsedCost !== null && parsedCost !== activeCost) {
        this.costChange.emit(parsedCost);
      }
    }
  }

  protected formatPresetLabel(preset: number): string {
    if (preset === 0) return '0% (Atual)';
    return preset > 0 ? `+${preset}%` : `${preset}%`;
  }

  protected formatSignedBrl(value: number): string {
    return formatSignedCurrency(value);
  }

  protected formatSignedPct(value: number): string {
    return formatSignedPercentValue(value, 1);
  }

  protected formatSignedPpValue(value: number): string {
    return formatSignedPp(value, 1);
  }

  protected formatQty(value: number): string {
    return formatUnits(value);
  }

  protected formatSignedQty(value: number): string {
    return formatSignedUnits(value);
  }

  protected formatDaily(value: number): string {
    return formatDecimal(value, 1);
  }

  private toStockBarPct(days: number | null): number {
    if (days === null || !Number.isFinite(days) || days <= 0) return 0;
    return Math.min(100, Math.max(0, (days / STOCK_COVERAGE_BAR_MAX_DAYS) * 100));
  }

  private formatMoneyInputValue(value: number): string {
    if (!Number.isFinite(value) || value < 0) return '0.00';
    return value.toFixed(2);
  }

  private parseValidPct(raw: string): number | null {
    const normalized = raw.trim().replace(',', '.');
    if (normalized === '' || normalized === '-' || normalized === '+') return null;
    const num = Number(normalized);
    if (!Number.isFinite(num) || num < PRICE_CHANGE_MIN || num > PRICE_CHANGE_MAX) return null;
    return num;
  }

  private parseValidCurrentPrice(raw: string): number | null {
    const normalized = raw.trim().replace(',', '.');
    if (normalized === '' || normalized === '-' || normalized === '+') return null;
    const num = Number(normalized);
    if (!Number.isFinite(num) || num <= 0) return null;
    return num;
  }

  private parseValidCost(raw: string): number | null {
    const normalized = raw.trim().replace(',', '.');
    if (normalized === '' || normalized === '-' || normalized === '+') return null;
    const num = Number(normalized);
    if (!Number.isFinite(num) || num < 0) return null;
    return num;
  }
}
