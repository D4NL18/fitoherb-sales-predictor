/**
 * Célula de variação percentual compartilhada entre a tabela ledger e a visão mobile em cartões (Design Plan §4.2, D-6).
 * Garante distinção por forma (▲/▼ + sinal + texto) com alto contraste WCAG AA.
 */
import { Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendCell,
  TrendDetailCell,
  TrendMetric,
  TrendParameters,
} from '../../models/sales-trend.model';
import { CellDisplayModel, getCellDisplayModel } from '../../utils/trend-view';
import { formatPointsChange, formatValueByMetric } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-cell',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div
      class="trend-cell-container"
      [class.card-variant]="variant() === 'card'"
      [class.sorted-column]="isSortedColumn()"
      [attr.aria-label]="model().ariaLabel"
    >
      <!-- Variação Percentual Principal -->
      <div class="variation-row" [ngClass]="variationClass()">
        @if (model().isNumeric) {
          @if (model().direction === 'up') {
            <span class="direction-arrow" aria-hidden="true">▲</span>
          } @else if (model().direction === 'down') {
            <span class="direction-arrow" aria-hidden="true">▼</span>
          }
          <span class="variation-value">{{ model().percentText }}</span>
        } @else if (model().isNew) {
          <span class="status-pill pill-new">Novo</span>
        } @else if (model().isNoBase) {
          <span class="status-dash" title="Histórico insuficiente no período anterior">—</span>
        } @else {
          <span class="status-dash" title="Sem movimento no período atual nem no anterior">—</span>
        }
      </div>

      <!-- Contribuição (para produtos em detalhe de fornecedor) -->
      @if (detailCell()?.contribuicaoPp !== undefined && detailCell()?.contribuicaoPp !== null) {
        <div class="contribution-row">
          <span class="contrib-pp">
            {{ formatPointsChange(detailCell()!.contribuicaoPp) }}
          </span>
          @if (detailCell()?.contribuicaoValor !== null) {
            <span class="contrib-val">
              ({{ formatValueByMetric(detailCell()!.contribuicaoValor, metric()) }})
            </span>
          }
        </div>
      }

      <!-- Badges / Selos explicativos -->
      @if (model().badges.length > 0) {
        <div class="badges-row">
          @for (b of model().badges; track b.text) {
            <span
              class="cell-badge"
              [class.badge-warning]="b.variant === 'warning'"
              [class.badge-critical]="b.variant === 'critical'"
              [class.badge-info]="b.variant === 'info'"
              [title]="b.tooltip"
            >
              {{ b.text }}
            </span>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .trend-cell-container {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      text-align: right;
      gap: 2px;
      font-family: var(--font-family-mono);
    }

    .trend-cell-container.card-variant {
      align-items: flex-start;
      text-align: left;
    }

    .sorted-column .variation-value {
      font-weight: 700;
    }

    .variation-row {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-size: 0.9375rem;
      font-weight: 600;
    }

    .variation-row.is-up {
      color: var(--feedback-positive-bg, #185A2E);
    }

    .variation-row.is-down {
      color: var(--feedback-critical-bg, #8F1B1B);
    }

    .variation-row.is-flat {
      color: var(--text-secondary);
    }

    .direction-arrow {
      font-size: 0.625rem;
      line-height: 1;
    }

    .status-pill {
      font-size: 0.6875rem;
      padding: 1px 6px;
      border-radius: var(--radius-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .pill-new {
      background-color: var(--feedback-info-bg, #1B4B7A);
      color: var(--text-on-brand, #FFFFFF);
    }

    .status-dash {
      color: var(--text-muted);
      font-weight: bold;
    }

    .contribution-row {
      font-size: 0.75rem;
      color: var(--text-secondary);
      display: inline-flex;
      gap: 4px;
    }

    .contrib-pp {
      font-weight: 600;
    }

    .contrib-val {
      color: var(--text-muted);
    }

    .badges-row {
      display: flex;
      flex-wrap: wrap;
      gap: 3px;
      justify-content: flex-end;
    }

    .card-variant .badges-row {
      justify-content: flex-start;
    }

    .cell-badge {
      display: inline-block;
      font-size: 0.6875rem;
      font-weight: 600;
      padding: 1px 4px;
      border-radius: var(--radius-xs);
      cursor: help;
    }

    .badge-info {
      background-color: var(--brand-primary-subtle, #E5EFE7);
      color: var(--brand-primary, #1D4528);
    }

    .badge-warning {
      background-color: #FDF3E7;
      color: var(--feedback-warning-bg, #7A4607);
      border: 1px solid var(--feedback-warning-border, #573104);
    }

    .badge-critical {
      background-color: #FDE8E8;
      color: var(--feedback-critical-bg, #8F1B1B);
      border: 1px solid var(--feedback-critical-border, #661212);
    }
  `],
})
export class TrendCellComponent {
  readonly cell = input.required<TrendCell | TrendDetailCell>();
  readonly metric = input.required<TrendMetric>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly variant = input<'table' | 'card'>('table');
  readonly isSortedColumn = input<boolean>(false);

  readonly model = computed<CellDisplayModel>(() =>
    getCellDisplayModel(this.cell(), this.metric(), this.params())
  );

  readonly detailCell = computed<TrendDetailCell | null>(() => {
    const c = this.cell() as TrendDetailCell;
    return c && (c.contribuicaoPp !== undefined || c.contribuicaoValor !== undefined) ? c : null;
  });

  readonly variationClass = computed(() => {
    const dir = this.model().direction;
    if (dir === 'up') return 'is-up';
    if (dir === 'down') return 'is-down';
    if (dir === 'flat') return 'is-flat';
    return '';
  });

  formatPointsChange = formatPointsChange;
  formatValueByMetric = formatValueByMetric;
}
