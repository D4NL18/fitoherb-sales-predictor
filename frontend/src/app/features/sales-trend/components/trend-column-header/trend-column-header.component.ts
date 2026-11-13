/**
 * Cabeçalho de coluna interativo para as janelas de 1, 3, 6 e 12 meses (Design Plan §5.4).
 * Suporta períodos comparados em 2 linhas, contraste WCAG AA e indicador visual de direção.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendComparisonMode, TrendSortDir, TrendSortWindow, TrendWindowMeta } from '../../models/sales-trend.model';
import { formatWindowMonthSpan } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-column-header',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      type="button"
      class="header-btn"
      [class.is-sorted]="isSorted()"
      (click)="sort.emit(windowMeta().meses)"
      [attr.aria-label]="ariaLabel()"
      [attr.title]="tooltipText()"
    >
      <div class="header-title-row">
        <span class="window-title">{{ windowMeta().meses }} {{ windowMeta().meses === 1 ? 'MÊS' : 'MESES' }}</span>
        <span class="sort-chip" [class.is-active]="isSorted()" aria-hidden="true">
          @if (isSorted()) {
            @if (sortDir() === 'desc') {
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <path d="M6 2.25V9.75M6 9.75L2.75 6.5M6 9.75L9.25 6.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            } @else {
              <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
                <path d="M6 9.75V2.25M6 2.25L2.75 5.5M6 2.25L9.25 5.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            }
          } @else {
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
              <path d="M4 4.25L6 2.25L8 4.25M4 7.75L6 9.75L8 7.75" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          }
        </span>
      </div>

      <div class="header-period-row">
        @if (showCurrentSpan()) {
          <span class="period-line period-current">{{ currentSpanText() }}</span>
        }
        <span class="period-line vs-line">
          <span class="vs-prefix">vs</span>
          <span class="prev-target">{{ previousSpanDisplay() }}</span>
        </span>
      </div>

      @if (windowMeta().semBase) {
        <span class="window-badge badge-nobase">Sem base</span>
      }
    </button>
  `,
  styles: [`
    :host {
      display: block;
      width: 100%;
      height: 100%;
    }

    .header-btn {
      width: 100%;
      height: 100%;
      min-height: 58px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: flex-end;
      gap: 4px;
      padding: 10px 12px;
      background: transparent;
      border: none;
      cursor: pointer;
      text-align: right;
      font-family: var(--font-family-body);
      color: var(--text-primary);
      position: relative;
      transition: background-color var(--transition-fast), box-shadow var(--transition-fast);

      &:hover {
        background-color: var(--bg-subtle);

        .window-title {
          color: var(--brand-primary);
        }

        .sort-chip:not(.is-active) {
          color: var(--brand-primary);
          border-color: var(--border-default);
        }
      }

      &.is-sorted {
        background-color: var(--brand-primary-subtle);
        box-shadow: inset 0 3px 0 var(--brand-primary);

        .window-title {
          color: var(--brand-primary);
        }

        .vs-prefix {
          color: var(--text-secondary);
        }
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: -2px;
      }
    }

    .header-title-row {
      display: inline-flex;
      align-items: center;
      justify-content: flex-end;
      gap: 6px;
      font-family: var(--font-family-headline);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      line-height: 1.1;
      color: var(--text-primary);
    }

    .window-title {
      transition: color var(--transition-fast);
    }

    .sort-chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      border-radius: var(--radius-xs);
      color: var(--text-secondary);
      border: 1px solid transparent;
      flex-shrink: 0;
      transition: background-color var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);

      &.is-active {
        background-color: var(--brand-primary);
        color: var(--text-on-brand);
        border-color: var(--brand-primary);
      }
    }

    .header-period-row {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 1px;
      font-family: var(--font-family-mono);
      font-size: 0.6875rem;
      letter-spacing: -0.02em;
      color: var(--text-secondary);
      line-height: 1.25;
      white-space: nowrap;

      @media (max-width: 1080px) {
        white-space: normal;
      }
    }

    .period-current {
      color: var(--text-secondary);
      font-weight: 500;
    }

    .vs-line {
      display: inline-flex;
      align-items: baseline;
      gap: 3px;
    }

    .vs-prefix {
      color: var(--text-secondary);
      font-family: var(--font-family-body);
      font-size: 0.6875rem;
      letter-spacing: 0;
    }

    .prev-target {
      color: var(--text-secondary);
      font-weight: 500;
    }

    .window-badge {
      display: inline-block;
      margin-top: 2px;
      padding: 1px 5px;
      font-size: 0.6875rem;
      font-weight: 600;
      border-radius: var(--radius-xs);
    }

    .badge-nobase {
      background-color: var(--feedback-neutral-bg);
      color: var(--text-on-brand);
    }
  `],
})
export class TrendColumnHeaderComponent {
  readonly windowMeta = input.required<TrendWindowMeta>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();

  readonly sort = output<TrendSortWindow>();

  readonly isSorted = computed(() => this.windowMeta().meses === this.sortWindow());

  readonly currentSpanText = computed(() => formatWindowMonthSpan(this.windowMeta().atual));
  readonly previousSpanText = computed(() => formatWindowMonthSpan(this.windowMeta().anterior));
  readonly comparisonMode = input<TrendComparisonMode>('point');

  readonly showCurrentSpan = computed(() => {
    const atual = this.windowMeta().atual;
    return atual.inicio.slice(0, 7) !== atual.fim.slice(0, 7);
  });

  readonly previousSpanDisplay = computed(() => {
    const prev = this.previousSpanText();
    if (this.comparisonMode() === 'average' && this.windowMeta().meses > 1) {
      return `média ${prev}`;
    }
    return prev;
  });

  readonly tooltipText = computed(() => `${this.currentSpanText()} vs ${this.previousSpanDisplay()}`);

  readonly ariaLabel = computed(() => {
    const months = this.windowMeta().meses;
    const sorted = this.isSorted();
    const dir = this.sortDir() === 'desc' ? 'decrescente' : 'crescente';
    return `Coluna de ${months} ${months === 1 ? 'mês' : 'meses'}, ${sorted ? `ordenada ${dir}` : 'não ordenada'}. Clique para ordenar.`;
  });
}
