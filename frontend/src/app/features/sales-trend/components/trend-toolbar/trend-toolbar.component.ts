/**
 * Painel completo de controles da Tendência de Vendas (Design Plan §5.3).
 * Organizado em 2 faixas estruturais: medição (agrupamento, métrica e mês-base) e filtro (busca e volume mínimo).
 */
import { Component, computed, input, output } from '@angular/core';
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

@Component({
  selector: 'app-trend-toolbar',
  standalone: true,
  imports: [
    CommonModule,
    SegmentedControlComponent,
    BaseMonthPickerComponent,
    TrendSearchFieldComponent,
  ],
  template: `
    <section class="trend-toolbar" aria-label="Controles e filtros da tendência">
      <!-- Faixa 1: O que medir -->
      <div class="toolbar-row row-measure">
        <div class="control-item">
          <span class="control-caption">Ver:</span>
          <app-segmented-control
            [options]="groupByOptions"
            [value]="query().groupBy || 'product'"
            (valueChange)="groupByChange.emit($event)"
          />
        </div>

        <div class="control-item">
          <span class="control-caption">Medir por:</span>
          <app-segmented-control
            [options]="metricOptions"
            [value]="query().metric || 'revenue'"
            (valueChange)="metricChange.emit($event)"
          />
        </div>

        <div class="control-item">
          <span class="control-caption">Tendência:</span>
          <app-segmented-control
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
            [placeholder]="searchPlaceholder()"
            [value]="query().q"
            (searchChange)="searchChange.emit($event)"
          />
        </div>

        <div class="volume-wrapper">
          <label class="volume-label" for="min-volume-input">{{ minFilterLabel() }}</label>
          <div class="volume-input-group">
            <input
              id="min-volume-input"
              type="number"
              min="0"
              step="any"
              class="volume-input"
              [placeholder]="minFilterPlaceholder()"
              [attr.aria-label]="minFilterAriaLabel()"
              [value]="query().minVolume || ''"
              [disabled]="loading()"
              (change)="onVolumeChange($event)"
            />
            <span class="volume-unit">{{ metricUnit() }}</span>
          </div>
        </div>

        @if (hasActiveFilters()) {
          <button type="button" class="clear-filters-btn" (click)="clearFilters.emit()">
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
      gap: var(--space-4, 16px);
      padding: var(--space-4, 16px) var(--space-5, 20px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      box-shadow: var(--shadow-xs);
    }

    .toolbar-row {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-4, 16px);

      &:not(:last-child) {
        padding-bottom: var(--space-4, 16px);
        border-bottom: 1px solid var(--border-subtle);
      }
    }

    .control-item {
      display: flex;
      align-items: center;
      gap: var(--space-2, 8px);
    }

    .control-caption {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .search-wrapper {
      flex: 1;
      min-width: 260px;
    }

    .volume-wrapper {
      display: flex;
      align-items: center;
      gap: var(--space-2, 8px);
    }

    .volume-label {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .volume-input-group {
      display: flex;
      align-items: center;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      height: 40px;
      padding: 0 var(--space-2, 8px);

      &:focus-within {
        border-color: var(--border-focus);
      }
    }

    .volume-input {
      width: 90px;
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
      color: var(--text-muted);
      margin-left: 4px;
    }

    .clear-filters-btn {
      background: none;
      border: none;
      color: var(--brand-primary);
      font-weight: 600;
      font-size: 0.875rem;
      cursor: pointer;
      text-decoration: underline;
      white-space: nowrap;

      &:hover {
        color: var(--brand-primary-hover);
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

  readonly hasActiveFilters = computed(() => {
    const q = this.query();
    return Boolean(
      (q.q && q.q.trim().length > 0) ||
      (typeof q.minVolume === 'number' && q.minVolume > 0)
    );
  });

  onVolumeChange(event: Event): void {
    const target = event.target as HTMLInputElement;
    const val = parseFloat(target.value);
    this.minVolumeChange.emit(isNaN(val) ? 0 : val);
  }
}
