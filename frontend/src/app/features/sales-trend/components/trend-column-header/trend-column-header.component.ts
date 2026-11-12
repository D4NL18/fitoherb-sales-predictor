/**
 * Cabeçalho de coluna interativo para as janelas de 1, 3, 6 e 12 meses (Design Plan §5.4).
 * Suporta indicação aria-sort, períodos comparados em 2 linhas e badges de base.
 */
import { Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendSortDir, TrendSortWindow, TrendWindowMeta } from '../../models/sales-trend.model';
import { formatWindowMonthSpan } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-column-header',
  standalone: true,
  imports: [CommonModule],
  template: `
    <button
      type="button"
      class="header-btn"
      [class.is-sorted]="isSorted()"
      (click)="sort.emit(windowMeta().meses)"
      [attr.aria-label]="ariaLabel()"
    >
      <div class="header-title-row">
        <span class="window-title">{{ windowMeta().meses }} {{ windowMeta().meses === 1 ? 'MÊS' : 'MESES' }}</span>
        <span class="sort-indicator" aria-hidden="true">
          @if (isSorted()) {
            {{ sortDir() === 'desc' ? '↓' : '↑' }}
          } @else {
            <span class="unsorted-indicator">↕</span>
          }
        </span>
      </div>

      <div class="header-period-row">
        <span class="period-line">{{ currentSpanText() }}</span>
        <span class="period-line vs-line">vs {{ previousSpanText() }}</span>
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
    }

    .header-btn {
      width: 100%;
      height: 100%;
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      padding: var(--space-2, 8px) var(--space-3, 12px);
      background: transparent;
      border: none;
      cursor: pointer;
      text-align: right;
      font-family: var(--font-family-body);
      color: var(--text-primary);
      position: relative;
      border-bottom: 3px solid transparent;
      transition: background-color var(--transition-fast);

      &:hover {
        background-color: var(--bg-table-row-hover);
      }

      &.is-sorted {
        border-bottom-color: var(--brand-primary);
        background-color: var(--brand-primary-subtle);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
      }
    }

    .header-title-row {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-family: var(--font-family-headline);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
    }

    .sort-indicator {
      font-weight: bold;
    }

    .unsorted-indicator {
      color: var(--text-muted);
      font-size: 0.75rem;
    }

    .header-period-row {
      display: flex;
      flex-direction: column;
      margin-top: 2px;
      font-family: var(--font-family-mono);
      font-size: 0.72rem;
      color: var(--text-secondary);
      line-height: 1.2;
    }

    .vs-line {
      color: var(--text-muted);
    }

    .window-badge {
      display: inline-block;
      margin-top: 4px;
      padding: 1px 5px;
      font-size: 0.6875rem;
      font-weight: 600;
      border-radius: var(--radius-xs);
    }

    .badge-partial {
      background-color: var(--feedback-info-bg);
      color: var(--text-on-brand);
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

  readonly ariaLabel = computed(() => {
    const months = this.windowMeta().meses;
    const sorted = this.isSorted();
    const dir = this.sortDir() === 'desc' ? 'decrescente' : 'crescente';
    return `Coluna de ${months} meses, ${sorted ? `ordenada ${dir}` : 'não ordenada'}. Clique para ordenar.`;
  });
}
