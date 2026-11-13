/**
 * Painel completo de controles da Tendência de Vendas (Design Plan §5.3).
 * Organizado em 2 faixas estruturais: medição (agrupamento, métrica, modo e mês-base) e filtro (busca e volume mínimo).
 */
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendComparisonMode,
  TrendGroupBy,
  TrendListMeta,
  TrendMetric,
  TrendQueryParams,
} from '../../models/sales-trend.model';
import {
  SegmentedControlComponent,
  SegmentOption,
} from '../segmented-control/segmented-control.component';
import { BaseMonthPickerComponent } from '../base-month-picker/base-month-picker.component';
import { TrendSearchFieldComponent } from '../trend-search-field/trend-search-field.component';

const MAX_MIN_VOLUME = 1_000_000_000;

@Component({
  selector: 'app-trend-toolbar',
  standalone: true,
  imports: [
    CommonModule,
    SegmentedControlComponent,
    BaseMonthPickerComponent,
    TrendSearchFieldComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="trend-toolbar" aria-label="Controles e filtros da tendência">
      <!-- Faixa 1: O que medir -->
      <div class="toolbar-row row-measure">
        <div class="control-item">
          <span class="control-caption" id="caption-groupby">Ver:</span>
          <app-segmented-control
            label="Agrupamento"
            [options]="groupByOptions"
            [value]="query().groupBy || 'product'"
            (valueChange)="groupByChange.emit($event)"
          />
        </div>

        <div class="control-item">
          <span class="control-caption" id="caption-metric">Medir por:</span>
          <app-segmented-control
            label="Métrica de comparação"
            [options]="metricOptions"
            [value]="query().metric || 'revenue'"
            (valueChange)="metricChange.emit($event)"
          />
        </div>

        <div class="control-item">
          <span class="control-caption" id="caption-mode">Tendência:</span>
          <app-segmented-control
            label="Modo de tendência"
            [options]="comparisonModeOptions"
            [value]="query().comparisonMode || 'point'"
            (valueChange)="comparisonModeChange.emit($event)"
          />
        </div>

        <div class="control-item month-item">
          <app-base-month-picker
            [value]="query().baseMonth || null"
            [defaultMonth]="meta()?.mesBasePadrao || null"
            [minMonth]="meta()?.mesBaseMinimo || null"
            [maxMonth]="meta()?.mesBaseMaximo || null"
            [lastCoveredDay]="meta()?.ultimoDiaCoberto || null"
            [disabled]="loading()"
            (monthChange)="baseMonthChange.emit($event)"
          />
        </div>
      </div>

      <!-- Faixa 2: Filtros de itens -->
      <div class="toolbar-row row-filter">
        <div class="search-wrapper">
          <app-trend-search-field
            [label]="searchAriaLabel()"
            [placeholder]="searchPlaceholder()"
            [value]="query().q"
            (searchChange)="searchChange.emit($event)"
          />
        </div>

        <div class="volume-wrapper">
          <label class="volume-label" for="min-volume-input">{{ minFilterLabel() }}</label>
          <div class="volume-control-stack">
            <div class="volume-input-group" [class.has-error]="!!volumeError()">
              <input
                id="min-volume-input"
                type="number"
                min="0"
                [attr.max]="1000000000"
                [attr.step]="query().metric === 'quantity' ? '1' : '0.01'"
                inputmode="decimal"
                class="volume-input"
                [placeholder]="minFilterPlaceholder()"
                [attr.aria-label]="minFilterAriaLabel()"
                [attr.aria-invalid]="volumeError() ? 'true' : null"
                [attr.aria-describedby]="volumeError() ? 'min-volume-error' : null"
                [value]="query().minVolume || ''"
                [disabled]="loading()"
                (input)="onVolumeInput()"
                (change)="onVolumeChange($event)"
                (keydown.enter)="onVolumeChange($event)"
              />
              <span class="volume-unit">{{ metricUnit() }}</span>
            </div>
            @if (volumeError()) {
              <p id="min-volume-error" class="volume-error" role="status">{{ volumeError() }}</p>
            }
          </div>
        </div>

        @if (hasActiveFilters()) {
          <button
            type="button"
            class="clear-filters-btn"
            [disabled]="loading()"
            (click)="onClearAll()"
          >
            Limpar filtros
          </button>
        }
      </div>
    </section>
  `,
  styles: [`
    .trend-toolbar {
      display: flex;
      flex-direction: column;
      gap: var(--space-4);
      padding: var(--space-4) var(--space-5);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      box-shadow: var(--shadow-xs);
    }

    .toolbar-row {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-4);

      &:not(:last-child) {
        padding-bottom: var(--space-4);
        border-bottom: 1px solid var(--border-subtle);
      }
    }

    .control-item {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
      min-width: 0;
    }

    .control-caption {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .search-wrapper {
      flex: 1 1 260px;
      min-width: 0;
    }

    .volume-wrapper {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
      min-width: 0;
    }

    .volume-label {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .volume-control-stack {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .volume-input-group {
      display: flex;
      align-items: center;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      min-height: 40px;
      padding: 0 var(--space-2);
      transition: border-color var(--transition-fast);

      &:hover {
        border-color: var(--border-strong);
      }

      &:focus-within {
        border-color: var(--border-focus);
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }

      &.has-error {
        border-color: var(--feedback-critical-border);
      }
    }

    .volume-input {
      width: 100px;
      border: none;
      background: transparent;
      font-family: var(--font-family-mono);
      font-size: 0.875rem;
      color: var(--text-primary);
      outline: none;
    }

    .volume-unit {
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text-secondary);
      margin-left: 4px;
    }

    .volume-error {
      margin: 0;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--feedback-critical-bg);
    }

    .clear-filters-btn {
      display: inline-flex;
      align-items: center;
      min-height: 40px;
      padding: 0 var(--space-2);
      background: transparent;
      border: 1px solid transparent;
      border-radius: var(--radius-xs);
      color: var(--brand-primary);
      font-family: var(--font-family-body);
      font-weight: 600;
      font-size: 0.875rem;
      cursor: pointer;
      text-decoration: underline;
      white-space: nowrap;

      &:hover:not(:disabled) {
        color: var(--brand-primary-hover);
        background-color: var(--brand-primary-subtle);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    }

    @media (max-width: 767.98px) {
      .trend-toolbar {
        padding: var(--space-3) var(--space-4);
      }

      .toolbar-row {
        gap: var(--space-3);
      }

      .search-wrapper,
      .volume-wrapper,
      .control-item {
        width: 100%;
      }
    }
  `],
})
export class TrendToolbarComponent {
  readonly query = input.required<TrendQueryParams>();
  readonly meta = input<TrendListMeta | null>(null);
  readonly loading = input<boolean>(false);

  readonly groupByChange = output<TrendGroupBy>();
  readonly metricChange = output<TrendMetric>();
  readonly comparisonModeChange = output<TrendComparisonMode>();
  readonly baseMonthChange = output<string>();
  readonly searchChange = output<string>();
  readonly minVolumeChange = output<number>();
  readonly clearFilters = output<void>();

  readonly volumeError = signal<string | null>(null);

  readonly groupByOptions: SegmentOption<TrendGroupBy>[] = [
    { value: 'product', label: 'Por produto' },
    { value: 'supplier', label: 'Por fornecedor' },
  ];

  readonly comparisonModeOptions: SegmentOption<TrendComparisonMode>[] = [
    { value: 'point', label: 'Mês pontual' },
    { value: 'average', label: 'Média do período' },
  ];

  readonly metricOptions: SegmentOption<TrendMetric>[] = [
    { value: 'revenue', label: 'Faturamento (R$)' },
    { value: 'quantity', label: 'Quantidade (un)' },
  ];

  readonly metricUnit = computed(() => (this.query().metric === 'quantity' ? 'un' : 'R$'));

  readonly minFilterLabel = computed(() =>
    this.query().metric === 'quantity' ? 'Volume mínimo:' : 'Faturamento mínimo:'
  );

  readonly minFilterPlaceholder = computed(() =>
    this.query().metric === 'quantity' ? '0' : '0,00'
  );

  readonly minFilterAriaLabel = computed(() =>
    this.query().metric === 'quantity'
      ? 'Volume mínimo em unidades'
      : 'Faturamento mínimo em reais'
  );

  readonly searchPlaceholder = computed(() =>
    this.query().groupBy === 'supplier'
      ? 'Nome do fornecedor'
      : 'Código ou descrição do produto'
  );

  readonly searchAriaLabel = computed(() =>
    this.query().groupBy === 'supplier' ? 'Buscar fornecedor' : 'Buscar produto por código ou descrição'
  );

  readonly hasActiveFilters = computed(() => {
    const q = this.query();
    return Boolean(
      (q.q && q.q.trim().length > 0) ||
      (typeof q.minVolume === 'number' && q.minVolume > 0)
    );
  });

  onVolumeInput(): void {
    if (this.volumeError()) {
      this.volumeError.set(null);
    }
  }

  onVolumeChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    const raw = target.value.trim();

    if (!raw) {
      this.volumeError.set(null);
      this.minVolumeChange.emit(0);
      return;
    }

    const val = parseFloat(raw.replace(',', '.'));
    if (!Number.isFinite(val) || val < 0) {
      this.volumeError.set('Informe um valor igual ou maior que zero.');
      target.value = this.query().minVolume ? String(this.query().minVolume) : '';
      this.minVolumeChange.emit(0);
      return;
    }

    if (val > MAX_MIN_VOLUME) {
      this.volumeError.set('Valor acima do limite permitido.');
      const clamped = MAX_MIN_VOLUME;
      target.value = String(clamped);
      this.minVolumeChange.emit(clamped);
      return;
    }

    this.volumeError.set(null);
    this.minVolumeChange.emit(val);
  }

  onClearAll(): void {
    this.volumeError.set(null);
    this.clearFilters.emit();
  }
}
