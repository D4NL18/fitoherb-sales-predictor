/**
 * Painel expansível "Valores por janela" exibindo números absolutos e médias diárias (Design Plan §5.6).
 */
import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrendCell, TrendMetric, TrendWindowMeta } from '../../models/sales-trend.model';
import { formatCurrency, formatDecimal } from '../../utils/pt-br-format';

@Component({
  selector: 'app-trend-row-values',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="row-values-panel">
      <h4 class="values-title">Valores detalhados por janela</h4>

      <table class="values-table">
        <thead>
          <tr>
            <th>Janela</th>
            <th>Vendas no período atual</th>
            <th>Vendas no período anterior</th>
            <th>Média diária (atual / anterior)</th>
          </tr>
        </thead>
        <tbody>
          @for (cell of janelas(); track cell.meses) {
            <tr>
              <td class="cell-window">{{ cell.meses }} {{ cell.meses === 1 ? 'mês' : 'meses' }}</td>
              <td class="cell-val">{{ formatVal(cell.atual) }}</td>
              <td class="cell-val">{{ formatVal(cell.anterior) }}</td>
              <td class="cell-daily">
                @if (cell.baseParcial && cell.atualPorDia !== null) {
                  {{ formatDaily(cell.atualPorDia) }} / {{ formatDaily(cell.anteriorPorDia) }}
                } @else {
                  <span class="text-muted">—</span>
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
      padding: var(--space-3, 12px) var(--space-4, 16px);
      background-color: var(--bg-table-row-zebra, #FAF8F4);
      border-top: 1px dashed var(--border-subtle);
      border-bottom: 1px solid var(--border-default);
    }

    .values-title {
      font-size: 0.8125rem;
      font-weight: 700;
      color: var(--text-secondary);
      margin-bottom: var(--space-2, 8px);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .values-table {
      width: 100%;
      max-width: 800px;
      border-collapse: collapse;
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;

      th {
        font-family: var(--font-family-body);
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-muted);
        text-align: left;
        padding: 4px 12px;
        border-bottom: 1px solid var(--border-subtle);
      }

      td {
        padding: 6px 12px;
        border-bottom: 1px solid var(--border-subtle);
      }
    }

    .cell-window {
      font-family: var(--font-family-body);
      font-weight: 600;
      color: var(--text-primary);
    }

    .cell-val {
      font-weight: 500;
      color: var(--text-primary);
    }

    .cell-daily {
      color: var(--text-secondary);
    }

    .text-muted {
      color: var(--text-muted);
    }
  `],
})
export class TrendRowValuesComponent {
  readonly janelas = input.required<[TrendCell, TrendCell, TrendCell, TrendCell] | TrendCell[]>();
  readonly metric = input.required<TrendMetric>();
  readonly windowMetas = input<TrendWindowMeta[] | null>(null);

  formatVal(val: number): string {
    if (this.metric() === 'revenue') {
      return formatCurrency(val);
    }
    return `${formatDecimal(val, 0)} un`;
  }

  formatDaily(val: number | null): string {
    if (val === null) return '—';
    if (this.metric() === 'revenue') {
      return `R$ ${formatDecimal(val, 4)}/dia`;
    }
    return `${formatDecimal(val, 4)} un/dia`;
  }
}
