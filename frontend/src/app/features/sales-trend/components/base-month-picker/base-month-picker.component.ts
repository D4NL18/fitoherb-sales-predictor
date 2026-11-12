/**
 * Seletor simples de Mês-Base com opções de mês atual e mês passado (Design Plan §5.3).
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

    .month-select {
      height: 38px;
      padding: 0 var(--space-3, 12px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      cursor: pointer;
      outline: none;
      transition: border-color var(--transition-fast), box-shadow var(--transition-fast);

      &:hover:not(:disabled) {
        border-color: var(--border-hover, var(--brand-primary));
      }

      &:focus-visible {
        border-color: var(--border-focus);
        box-shadow: 0 0 0 1px var(--border-focus);
      }

      &:disabled {
        opacity: 0.5;
        cursor: not-allowed;
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
    const max = this.maxMonth() || this.defaultMonth() || '2026-11';
    const def = this.defaultMonth() || '2026-10';
    const lastDayFormatted = formatIsoDate(this.lastCoveredDay());

    // Mês atual
    const [maxY, maxM] = max.split('-').map((s) => parseInt(s, 10));
    const maxMonthName = SHORT_MONTHS[maxM - 1];
    let maxLabel = `${maxMonthName}/${maxY} · mês atual`;
    if (this.lastCoveredDay()) {
      maxLabel += ` (parcial até ${lastDayFormatted.substring(0, 5)})`;
    }

    // Mês passado
    let prevVal = def;
    if (prevVal === max) {
      const curIdx = maxY * 12 + maxM - 2;
      const py = Math.floor(curIdx / 12);
      const pm = (curIdx % 12) + 1;
      prevVal = `${py}-${pm.toString().padStart(2, '0')}`;
    }

    const [prevY, prevM] = prevVal.split('-').map((s) => parseInt(s, 10));
    const prevMonthName = SHORT_MONTHS[prevM - 1];
    const prevLabel = `${prevMonthName}/${prevY} · mês passado`;

    return [
      { value: max, label: maxLabel },
      { value: prevVal, label: prevLabel },
    ];
  });

  onSelectChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    this.monthChange.emit(target.value);
  }
}
