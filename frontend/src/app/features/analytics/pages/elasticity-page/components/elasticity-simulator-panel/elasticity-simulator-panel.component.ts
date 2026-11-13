import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  effect,
  input,
  output,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { CustomerElasticityDetail, SimulationImpactData } from '../../../../models/elasticity.models';
import { BrlPipe, PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';
import {
  PRICE_CHANGE_MAX,
  PRICE_CHANGE_MIN,
  PRICE_PRESETS,
  deltaTone,
  formatSignedCurrency,
  formatSignedPercentValue,
  formatUnits,
  getClassificationMeta,
  getConfidenceMeta,
  sliderMarkLeftPct,
} from '../../../../utils/elasticity-view';

@Component({
  selector: 'app-elasticity-simulator-panel',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, PtPercentPipe],
  templateUrl: './elasticity-simulator-panel.component.html',
  styleUrl: './elasticity-simulator-panel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ElasticitySimulatorPanelComponent {
  private readonly hostRef = viewChild<ElementRef<HTMLElement>>('simulatorRoot');
  private readonly customerHeadingRef = viewChild<ElementRef<HTMLElement>>('customerFocusTarget');

  readonly priceChangePct = input.required<number>();
  readonly selectedCustomerCode = input<number | null>(null);
  readonly customerDetail = input<CustomerElasticityDetail | null>(null);
  readonly isCustomerLoading = input<boolean>(false);
  readonly customerError = input<string | null>(null);
  readonly simulationResult = input<SimulationImpactData | null>(null);
  readonly isSimulating = input<boolean>(false);
  readonly simulationError = input<string | null>(null);

  readonly priceSliderInput = output<number>();
  readonly pricePresetSelect = output<number>();
  readonly priceNumberCommit = output<number>();
  readonly clearCustomer = output<void>();
  readonly retrySimulation = output<void>();

  protected readonly minPct = PRICE_CHANGE_MIN;
  protected readonly maxPct = PRICE_CHANGE_MAX;
  protected readonly presets = PRICE_PRESETS;
  protected readonly scaleMarks = [
    { value: -50, label: '-50%', leftPct: sliderMarkLeftPct(-50), align: 'start' as const },
    { value: 0, label: '0%', leftPct: sliderMarkLeftPct(0), align: 'center' as const },
    { value: 50, label: '+50%', leftPct: sliderMarkLeftPct(50), align: 'center' as const },
    { value: 100, label: '+100%', leftPct: sliderMarkLeftPct(100), align: 'end' as const },
  ];

  protected readonly inputText = signal<string>('5');
  protected readonly localValidationError = signal<string | null>(null);

  protected readonly displayedError = computed(
    () => this.localValidationError() ?? this.simulationError(),
  );

  protected readonly sliderValueText = computed(() => {
    const val = this.priceChangePct();
    if (val === 0) return '0% (sem alteração de preço)';
    return `${formatSignedPercentValue(val, 1)} de variação no preço`;
  });

  protected readonly customerClassMeta = computed(() => {
    const detail = this.customerDetail();
    return detail ? getClassificationMeta(detail.classification) : null;
  });

  protected readonly customerConfidenceMeta = computed(() => {
    const detail = this.customerDetail();
    return detail ? getConfidenceMeta(detail.confidenceLevel) : null;
  });

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

  constructor() {
    effect(() => {
      const pct = this.priceChangePct();
      untracked(() => {
        this.inputText.set(String(pct));
        this.localValidationError.set(null);
      });
    }, { allowSignalWrites: true });
  }

  /** Desloca a viewport e o foco para o contexto do simulador ao selecionar um cliente na tabela. */
  focusSimulatorContext(): void {
    const root = this.hostRef()?.nativeElement;
    if (root && typeof root.scrollIntoView === 'function') {
      const reduced =
        typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      root.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'nearest' });
    }
    this.customerHeadingRef()?.nativeElement.focus({ preventScroll: true });
  }

  protected onSliderInput(event: Event): void {
    const value = Number((event.target as HTMLInputElement).value);
    if (!Number.isFinite(value)) return;
    this.inputText.set(String(value));
    this.localValidationError.set(null);
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
    this.priceSliderInput.emit(parsed);
  }

  protected onNumberCommit(): void {
    const parsed = this.parseValidPct(this.inputText());
    if (parsed === null) {
      this.localValidationError.set(`Informe um percentual entre ${PRICE_CHANGE_MIN}% e +${PRICE_CHANGE_MAX}%.`);
      return;
    }
    this.localValidationError.set(null);
    this.priceNumberCommit.emit(parsed);
  }

  protected selectPreset(preset: number): void {
    this.inputText.set(String(preset));
    this.localValidationError.set(null);
    this.pricePresetSelect.emit(preset);
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

  protected formatQty(value: number): string {
    return formatUnits(value);
  }

  private parseValidPct(raw: string): number | null {
    const normalized = raw.trim().replace(',', '.');
    if (normalized === '' || normalized === '-' || normalized === '+') return null;
    const num = Number(normalized);
    if (!Number.isFinite(num) || num < PRICE_CHANGE_MIN || num > PRICE_CHANGE_MAX) return null;
    return num;
  }
}
