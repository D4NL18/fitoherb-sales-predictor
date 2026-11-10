/**
 * Seletor de Mês-Base com navegação por setas ‹ / › e select acessível (Design Plan §5.3).
 * Gera opções decrescentes entre mesBaseMinimo e mesBaseMaximo.
 */
import { Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { formatIsoDate } from '../../utils/pt-br-format';

interface MonthOption {
  value: string;
  label: string;
}

const SHORT_MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

@Component({
  selector: 'app-base-month-picker',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="month-picker-container">
      <label class="picker-label" for="base-month-select">Mês-base:</label>

      <div class="picker-controls">
        <button
          type="button"
          class="step-btn"
          [disabled]="disabled() || !canPrev()"
          (click)="stepMonth(-1)"
          aria-label="Mês-base anterior"
        >
          ‹
        </button>

        <select
          id="base-month-select"
          class="month-select"
          [disabled]="disabled()"
          [value]="currentValue()"
          (change)="onSelectChange($event)"
        >
          @for (m of monthOptions(); track m.value) {
            <option [value]="m.value">{{ m.label }}</option>
          }
        </select>

        <button
          type="button"
          class="step-btn"
          [disabled]="disabled() || !canNext()"
          (click)="stepMonth(1)"
          aria-label="Próximo mês-base"
        >
          ›
        </button>
      </div>
    </div>
  `,
  styles: [`
    .month-picker-container {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2, 8px);
    }

    .picker-label {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .picker-controls {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      padding: 2px;
    }

    .step-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      border-radius: var(--radius-xs);
      color: var(--text-primary);
      font-size: 1.125rem;
      font-weight: bold;
      cursor: pointer;

      &:hover:not(:disabled) {
        background-color: var(--bg-subtle);
      }

      &:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
    }

    .month-select {
      height: 32px;
      padding: 0 var(--space-2, 8px);
      background: transparent;
      border: none;
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      cursor: pointer;
      outline: none;

      &:focus-visible {
        outline: 2px solid var(--border-focus);
      }
    }
  `],
})
export class BaseMonthPickerComponent {
  readonly value = input<string | null>(null);
  readonly defaultMonth = input<string | null>(null);
  readonly minMonth = input<string | null>(null);
  readonly maxMonth = input<string | null>(null);
  readonly lastCoveredDay = input<string | null>(null);
  readonly disabled = input<boolean>(false);

  readonly monthChange = output<string>();

  readonly currentValue = computed(() => this.value() || this.defaultMonth() || '');

  readonly monthOptions = computed<MonthOption[]>(() => {
    const min = this.minMonth() || '2025-01';
    const max = this.maxMonth() || this.defaultMonth() || '2026-11';
    const def = this.defaultMonth();
    const lastDayFormatted = formatIsoDate(this.lastCoveredDay());

    const [minY, minM] = min.split('-').map((s) => parseInt(s, 10));
    const [maxY, maxM] = max.split('-').map((s) => parseInt(s, 10));

    const options: MonthOption[] = [];
    let curIdx = maxY * 12 + maxM - 1;
    const minIdx = minY * 12 + minM - 1;

    while (curIdx >= minIdx) {
      const y = Math.floor(curIdx / 12);
      const m = (curIdx % 12) + 1;
      const strVal = `${y}-${m.toString().padStart(2, '0')}`;
      const monthName = SHORT_MONTHS[m - 1];

      let label = `${monthName}/${y}`;
      if (strVal === max && this.lastCoveredDay()) {
        label += ` · mês corrente, parcial até ${lastDayFormatted.substring(0, 5)}`;
      } else if (strVal === def) {
        label += ' · último mês completo';
      }

      options.push({ value: strVal, label });
      curIdx--;
    }

    return options;
  });

  readonly canPrev = computed(() => {
    const opts = this.monthOptions();
    const curr = this.currentValue();
    const idx = opts.findIndex((o) => o.value === curr);
    // As opções estão decrescentes, então mês anterior é índice seguinte (idx + 1)
    return idx >= 0 && idx < opts.length - 1;
  });

  readonly canNext = computed(() => {
    const opts = this.monthOptions();
    const curr = this.currentValue();
    const idx = opts.findIndex((o) => o.value === curr);
    return idx > 0;
  });

  onSelectChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.monthChange.emit(target.value);
  }

  stepMonth(delta: number): void {
    const opts = this.monthOptions();
    const curr = this.currentValue();
    const idx = opts.findIndex((o) => o.value === curr);
    if (idx < 0) return;

    // delta -1 = anterior cronológico = idx + 1 no array decrescente
    // delta +1 = próximo cronológico = idx - 1 no array decrescente
    const targetIdx = idx - delta;
    if (targetIdx >= 0 && targetIdx < opts.length) {
      this.monthChange.emit(opts[targetIdx].value);
    }
  }
}
