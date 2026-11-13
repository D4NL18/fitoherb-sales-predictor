/**
 * Painel expansível "Valores por janela" exibindo números absolutos, spans de datas e médias diárias (Design Plan §5.6).
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendCell, TrendMetric, TrendWindowMeta } from '../../models/sales-trend.model';
import { formatCurrency, formatDecimal } from '../../utils/pt-br-format';
import { formatWindowMonthSpan } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-row-values',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="row-values-panel">
      <h4 class="values-title">Valores detalhados por janela</h4>

      <table class="values-table">
        <thead>
          <tr>
            <th scope="col">Janela</th>
            <th scope="col">Vendas no período atual</th>
            <th scope="col">Vendas no período anterior</th>
            <th scope="col">Média diária (atual / anterior)</th>
          </tr>
        </thead>
        <tbody>
          @for (cell of janelas(); track cell.meses) {
            <tr>
              <td class="cell-window" data-label="Janela">
                <span class="win-name">{{ cell.meses }} {{ cell.meses === 1 ? 'mês' : 'meses' }}</span>
                @if (windowSpanText(cell.meses)) {
                  <span class="win-span">{{ windowSpanText(cell.meses) }}</span>
                }
              </td>
              <td class="cell-val" data-label="Período atual">{{ formatVal(cell.atual) }}</td>
              <td class="cell-val" data-label="Período anterior">{{ formatVal(cell.anterior) }}</td>
              <td class="cell-daily" data-label="Média diária">
                @if (cell.baseParcial && cell.atualPorDia !== null) {
                  {{ formatDaily(cell.atualPorDia) }} / {{ formatDaily(cell.anteriorPorDia) }}
                } @else {
                  <span class="text-secondary-dash">—</span>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .row-values-panel {
      padding: var(--space-3) var(--space-4);
      background-color: var(--bg-table-row-zebra);
      border-top: 1px dashed var(--border-subtle);
      border-bottom: 1px solid var(--border-default);
      overflow-x: auto;
    }

    .values-title {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--text-secondary);
      margin: 0 0 var(--space-2) 0;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .values-table {
      width: 100%;
      max-width: 860px;
      border-collapse: collapse;
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;

      th {
        font-family: var(--font-family-body);
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-align: left;
        padding: 4px 12px;
        border-bottom: 1px solid var(--border-subtle);
      }

      td {
        padding: 6px 12px;
        border-bottom: 1px solid var(--border-subtle);
        vertical-align: top;
      }
    }

    .cell-window {
      display: flex;
      flex-direction: column;
      gap: 1px;
      font-family: var(--font-family-body);
      font-weight: 600;
      color: var(--text-primary);
    }

    .win-span {
      font-family: var(--font-family-mono);
      font-size: 0.6875rem;
      font-weight: 500;
      color: var(--text-secondary);
    }

    .cell-val {
      font-weight: 600;
      color: var(--text-primary);
    }

    .cell-daily {
      color: var(--text-secondary);
    }

    .text-secondary-dash {
      color: var(--text-secondary);
    }

    @media (max-width: 639.98px) {
      .row-values-panel {
        padding: var(--space-3);
      }

      .values-table thead {
        display: none;
      }

      .values-table,
      .values-table tbody {
        display: flex;
        flex-direction: column;
        gap: var(--space-2);
      }

      .values-table tr {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
        padding: var(--space-2);
        background-color: var(--bg-surface);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-xs);
      }

      .values-table td {
        padding: 0;
        border: none;
        display: flex;
        flex-direction: column;
        gap: 1px;

        &::before {
          content: attr(data-label);
          font-family: var(--font-family-body);
          font-size: 0.6875rem;
          font-weight: 600;
          color: var(--text-secondary);
        }
      }
    }
  `],
})
export class TrendRowValuesComponent {
  readonly janelas = input.required<[TrendCell, TrendCell, TrendCell, TrendCell] | TrendCell[]>();
  readonly metric = input.required<TrendMetric>();
  readonly windowMetas = input<TrendWindowMeta[] | null>(null);

  windowSpanText(meses: number): string | null {
    const meta = this.windowMetas()?.find((w) => w.meses === meses);
    if (!meta) {
      return null;
    }
    return `${formatWindowMonthSpan(meta.atual)} vs ${formatWindowMonthSpan(meta.anterior)}`;
  }

  formatVal(val: number): string {
    if (this.metric() === 'revenue') {
      return formatCurrency(val);
    }
    return `${formatDecimal(val, Number.isInteger(val) ? 0 : 1)} un`;
  }

  formatDaily(val: number | null): string {
    if (val === null) return '—';
    if (this.metric() === 'revenue') {
      return `${formatCurrency(val)}/dia`;
    }
    return `${formatDecimal(val, 4)} un/dia`;
  }
}
