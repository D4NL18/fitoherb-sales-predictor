/**
 * Linha de produto da tabela (usada tanto no universo geral quanto nos filhos de fornecedor).
 * Suporta expansão de valores detalhados e acessibilidade ARIA (Design Plan §5.4).
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendDetailRow,
  TrendMetric,
  TrendParameters,
  TrendProductRow,
  TrendSortWindow,
} from '../../models/sales-trend.model';
import { TrendCellComponent } from '../trend-cell/trend-cell.component';
import { ExplainRequest } from '../../insights/models/trend-insights.model';
import { explainAriaLabel } from '../../insights/utils/insight-view';

@Component({
  selector: 'tr[appTrendRow]',
  standalone: true,
  imports: [CommonModule, TrendCellComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Coluna 1: Botão de expandir detalhes -->
    <td class="col-expand">
      <button
        type="button"
        class="expand-chevron-btn"
        [class.is-expanded]="isExpanded()"
        (click)="toggle.emit()"
        [attr.aria-expanded]="isExpanded()"
        [attr.aria-controls]="ariaControlsId()"
        [attr.aria-label]="expandAriaLabel()"
      >
        <span class="chevron-icon" aria-hidden="true">›</span>
      </button>
    </td>

    <!-- Coluna 2: Produto -->
    <td class="col-entity">
      <div class="entity-content" [class.child-indent]="level() === 'child'">
        <div class="entity-main">
          <span class="product-sku">{{ row().codigo }}</span>
          <span class="product-desc">{{ row().descricao }}</span>
        </div>
        <div class="entity-footer">
          @if (row().fornecedor && level() === 'parent') {
            <span class="product-supplier">{{ row().fornecedor }}</span>
          }
          @if (explainable()) {
            <button
              type="button"
              class="btn-explain"
              aria-haspopup="dialog"
              [attr.aria-label]="explainLabel()"
              (click)="onExplain($event)"
            >Por que?</button>
          }
        </div>
      </div>
    </td>

    <!-- Colunas 3 a 6: Células das 4 janelas (1, 3, 6, 12 meses) -->
    @for (cell of row().janelas; track cell.meses) {
      <td class="col-window" [class.sorted-col]="cell.meses === sortWindow()">
        <app-trend-cell
          [cell]="cell"
          [metric]="metric()"
          [params]="params()"
          [isSortedColumn]="cell.meses === sortWindow()"
        />
      </td>
    }
  `,
  host: { '[class.is-explaining]': 'explaining()' },
  styles: [`
    :host {
      border-bottom: 1px solid var(--border-subtle);
      transition: background-color var(--transition-fast);

      &:hover {
        background-color: var(--bg-table-row-hover);
      }
    }

    .col-expand {
      width: 44px;
      text-align: center;
      padding: var(--space-1) 0;
      vertical-align: middle;
    }

    .expand-chevron-btn {
      width: 40px;
      height: 40px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      cursor: pointer;
      color: var(--text-secondary);
      font-size: 1.25rem;
      border-radius: var(--radius-xs);
      transition: transform var(--transition-fast), background-color var(--transition-fast);

      &.is-expanded {
        transform: rotate(90deg);
        color: var(--brand-primary);
      }

      &:hover {
        background-color: var(--bg-subtle);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .col-entity {
      padding: var(--space-2) var(--space-3);
      vertical-align: middle;
      min-width: 0;
    }

    .entity-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }

    .entity-content.child-indent {
      margin-left: var(--space-3);
      padding-left: var(--space-3);
      border-left: 2px solid var(--border-default);
    }

    .entity-main {
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: var(--space-2);
      min-width: 0;
    }

    .product-sku {
      font-family: var(--font-family-mono);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    .product-desc {
      font-size: 0.875rem;
      font-weight: 600;
      color: var(--text-primary);
      overflow-wrap: anywhere;
    }

    .entity-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-2);
      flex-wrap: wrap;
    }

    .btn-explain {
      margin-left: auto;
      min-height: 32px;
      padding: 0 var(--space-2);
      font-family: var(--font-family-body);
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--brand-primary);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      cursor: pointer;
      transition: background-color var(--transition-fast), border-color var(--transition-fast);

      @media (hover: hover) {
        &:hover {
          border-color: var(--brand-primary);
          background-color: var(--brand-primary-subtle);
        }
      }

      &:active {
        background-color: var(--bg-muted);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    :host(.is-explaining) {
      background-color: var(--brand-primary-subtle);
      box-shadow: inset 3px 0 0 var(--brand-primary);
    }

    .product-supplier {
      font-size: 0.75rem;
      color: var(--text-secondary);
      overflow-wrap: anywhere;
    }

    .col-window {
      padding: var(--space-2) var(--space-3);
      vertical-align: middle;
      text-align: right;
    }

    .col-window.sorted-col {
      background-color: var(--bg-table-col-sorted);
    }
  `],
})
export class TrendRowComponent {
  readonly row = input.required<TrendProductRow | TrendDetailRow>();
  readonly metric = input.required<TrendMetric>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly level = input<'parent' | 'child'>('parent');
  readonly isExpanded = input<boolean>(false);
  readonly ariaControlsId = input<string | null>(null);

  /** Mostra o botão "Por que?" (linhas de produto; D-3). */
  readonly explainable = input<boolean>(true);
  readonly explaining = input<boolean>(false);

  readonly toggle = output<void>();
  readonly explain = output<ExplainRequest>();

  readonly explainLabel = computed(() => {
    const cell = this.row().janelas.find((j) => j.meses === this.sortWindow());
    return explainAriaLabel(this.row().descricao, cell?.variacaoPct ?? null, this.sortWindow());
  });

  onExplain(event: Event): void {
    this.explain.emit({
      sku: this.row().codigo,
      descricao: this.row().descricao,
      fornecedor: this.row().fornecedor,
      triggerEl: event.currentTarget as HTMLElement,
    });
  }

  readonly expandAriaLabel = computed(() => {
    const isExp = this.isExpanded();
    return `${isExp ? 'Recolher' : 'Expandir'} detalhes do produto ${this.row().descricao}`;
  });
}
