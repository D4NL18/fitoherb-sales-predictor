/**
 * Seletor simples de Mês-Base com opções de mês atual e mês passado (Design Plan §5.3).
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { formatIsoDate } from '../../utils/pt-br-format';

interface MonthOption {
  value: string;
  label: string;
}

const SHORT_MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

function formatShortMonthLabel(ym: string, suffix: string): string {
  const parts = ym.split('-');
  const year = parseInt(parts[0] ?? '', 10);
  const month = parseInt(parts[1] ?? '', 10);
  const monthName = Number.isInteger(month) && month >= 1 && month <= 12
    ? SHORT_MONTHS[month - 1]
    : ym;
  const base = Number.isInteger(year) && monthName !== ym ? `${monthName}/${year}` : ym;
  return suffix ? `${base} · ${suffix}` : base;
}

@Component({
  selector: 'app-base-month-picker',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="month-picker-container">
      <label class="picker-label" for="base-month-select">Mês-base:</label>

      <select
        id="base-month-select"
        class="month-select"
        [disabled]="disabled()"
        [attr.aria-busy]="disabled()"
        [value]="currentValue()"
        (change)="onSelectChange($event)"
      >
        @for (m of monthOptions(); track m.value) {
          <option [value]="m.value" [selected]="m.value === currentValue()">{{ m.label }}</option>
        }
      </select>
    </div>
  `,
  styles: [`
    .month-picker-container {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
      max-width: 100%;
    }

    .picker-label {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .month-select {
      min-height: 40px;
      max-width: 100%;
      padding: 0 var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      cursor: pointer;
      transition: border-color var(--transition-fast), box-shadow var(--transition-fast);

      &:hover:not(:disabled) {
        border-color: var(--border-strong);
      }

      &:focus-visible {
        border-color: var(--border-focus);
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }

      &:disabled {
        opacity: 0.55;
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
    const min = this.minMonth();
    const lastDayFormatted = formatIsoDate(this.lastCoveredDay());

    const [maxY, maxM] = max.split('-').map((s) => parseInt(s, 10));
    let maxLabel = formatShortMonthLabel(max, 'mês atual');
    if (this.lastCoveredDay() && lastDayFormatted && lastDayFormatted !== '—') {
      maxLabel += ` (parcial até ${lastDayFormatted.substring(0, 5)})`;
    }

    let prevVal = def;
    if (prevVal === max && Number.isInteger(maxY) && Number.isInteger(maxM)) {
      const curIdx = maxY * 12 + maxM - 2;
      const py = Math.floor(curIdx / 12);
      const pm = (curIdx % 12) + 1;
      prevVal = `${py}-${pm.toString().padStart(2, '0')}`;
    }

    const options: MonthOption[] = [];
    if (!min || max >= min) {
      options.push({ value: max, label: maxLabel });
    }
    if (prevVal !== max && (!min || prevVal >= min)) {
      options.push({ value: prevVal, label: formatShortMonthLabel(prevVal, 'mês passado') });
    }

    // Preserva na lista eventual mês vindo via URL fora das duas opções rápidas
    const active = this.value();
    if (active && /^\d{4}-(0[1-9]|1[0-2])$/.test(active) && !options.some((o) => o.value === active)) {
      options.push({ value: active, label: formatShortMonthLabel(active, 'selecionado') });
    }

    return options;
  });

  onSelectChange(event: Event): void {
    const target = event.target as HTMLSelectElement;
    if (target.value) {
      this.monthChange.emit(target.value);
    }
  }
}
