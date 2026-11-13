/**
 * Legenda explicativa dos períodos comparados em cada janela (Design Plan §4.2).
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendComparisonMode, TrendMetric, TrendWindowMeta } from '../../models/sales-trend.model';
import { formatWindowMonthSpan } from '../../utils/trend-format';
import { formatIsoDate } from '../../utils/pt-br-format';

@Component({
  selector: 'app-period-legend',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="period-legend-panel">
      <h4 class="legend-title">Períodos comparados</h4>
      <div class="legend-grid">
        @for (w of windows(); track w.meses) {
          <div class="legend-item">
            <strong class="item-window">{{ w.meses }} {{ w.meses === 1 ? 'mês' : 'meses' }}:</strong>
            <span class="item-span">
              {{ formatWindowMonthSpan(w.atual) }}
              <span class="vs-text">vs</span>
              {{ previousSpan(w) }}
            </span>
            @if (w.baseParcial) {
              <span class="legend-badge">Média diária</span>
            } @else if (w.semBase) {
              <span class="legend-badge badge-neutral">Sem base</span>
            }
          </div>
        }
      </div>

      @if (lastCoveredDay()) {
        <p class="legend-footer">
          * Dados fechados até {{ formatIsoDate(lastCoveredDay()) }}. Devoluções abatidas. Apenas produtos ativos do catálogo.
        </p>
      }
    </div>
  `,
  styles: [`
    .period-legend-panel {
      padding: var(--space-3) var(--space-4);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      font-size: 0.8125rem;
      color: var(--text-secondary);
    }

    .legend-title {
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      margin: 0 0 var(--space-2) 0;
      color: var(--text-secondary);
    }

    .legend-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(220px, 100%), 1fr));
      gap: var(--space-2) var(--space-4);
    }

    .legend-item {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
      min-width: 0;
      font-family: var(--font-family-mono);
      font-size: 0.75rem;
    }

    .item-window {
      font-family: var(--font-family-body);
      color: var(--text-primary);
    }

    .vs-text {
      color: var(--text-secondary);
      margin: 0 2px;
    }

    .legend-badge {
      font-size: 0.6875rem;
      padding: 1px 6px;
      background-color: var(--brand-primary-subtle);
      color: var(--brand-primary);
      border-radius: var(--radius-xs);
      font-family: var(--font-family-body);
      font-weight: 600;
    }

    .badge-neutral {
      background-color: var(--bg-subtle);
      color: var(--text-secondary);
    }

    .legend-footer {
      margin: var(--space-2) 0 0 0;
      font-size: 0.75rem;
      color: var(--text-secondary);
    }
  `],
})
export class PeriodLegendComponent {
  readonly windows = input.required<TrendWindowMeta[]>();
  readonly metric = input.required<TrendMetric>();
  readonly comparisonMode = input<TrendComparisonMode>('point');
  readonly lastCoveredDay = input<string | null>(null);

  formatWindowMonthSpan = formatWindowMonthSpan;
  formatIsoDate = formatIsoDate;

  previousSpan(w: TrendWindowMeta): string {
    const span = formatWindowMonthSpan(w.anterior);
    return this.comparisonMode() === 'average' && w.meses > 1 ? `média ${span}` : span;
  }
}
