/**
 * Tabela ledger de alta densidade para telas >= 768px (Design Plan §5.4).
 * Suporta cabeçalho descritivo acessível, largura proporcional sem rolagem horizontal e contraste WCAG AA.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendComparisonMode,
  TrendGroupBy,
  TrendMetric,
  TrendParameters,
  TrendProductRow,
  TrendSortBy,
  TrendSortDir,
  TrendSortWindow,
  TrendSupplierRow,
  TrendTotalRow,
  TrendWindowMeta,
} from '../../models/sales-trend.model';
import { SupplierDetailState } from '../../services/sales-trend.store';
import { formatWindowMonthSpan } from '../../utils/trend-format';
import { TrendColumnHeaderComponent } from '../trend-column-header/trend-column-header.component';
import { TrendRowComponent } from '../trend-row/trend-row.component';
import { TrendCellComponent } from '../trend-cell/trend-cell.component';
import { TrendRowValuesComponent } from '../trend-row-values/trend-row-values.component';
import { TrendSupplierGroupComponent } from '../trend-supplier-group/trend-supplier-group.component';

@Component({
  selector: 'app-trend-table',
  standalone: true,
  imports: [
    CommonModule,
    TrendColumnHeaderComponent,
    TrendRowComponent,
    TrendCellComponent,
    TrendRowValuesComponent,
    TrendSupplierGroupComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="trend-table-wrapper" [class.is-loading]="loading()">
      <table class="trend-table" [attr.aria-busy]="loading()">
        <caption class="sr-only">
          Tendência de vendas agrupada por {{ groupBy() === 'supplier' ? 'fornecedor' : 'produto' }} em janelas de 1, 3, 6 e 12 meses.
        </caption>
        <thead>
          <tr>
            <th class="th-expand" scope="col"><span class="sr-only">Expandir</span></th>
            <th class="th-entity" scope="col">
              <div class="th-entity-content">
                <span class="th-entity-title">{{ groupBy() === 'supplier' ? 'FORNECEDOR' : 'PRODUTO' }}</span>
                @if (baseSpanLabel()) {
                  <span class="th-entity-sub">
                    Mês-base: <span class="th-entity-base">{{ baseSpanLabel() }}</span>
                  </span>
                }
              </div>
            </th>
            @for (col of columns(); track col.meses) {
              <th
                class="th-window"
                [class.is-sorted]="col.meses === sortWindow()"
                scope="col"
                [attr.aria-sort]="col.meses === sortWindow() ? (sortDir() === 'desc' ? 'descending' : 'ascending') : 'none'"
              >
                <app-trend-column-header
                  [windowMeta]="col"
                  [sortWindow]="sortWindow()"
                  [sortDir]="sortDir()"
                  [comparisonMode]="comparisonMode()"
                  (sort)="sort.emit($event)"
                />
              </th>
            }
          </tr>
        </thead>

        @if (totalRow() && totalRow()!.janelas.length > 0) {
          <tbody>
            <!-- Linha Total Geral (Q-4) -->
            <tr class="total-row">
              <td class="col-expand"></td>
              <td class="col-entity">
                <div class="total-entity-title">
                  <strong>Todos os produtos ativos</strong>
                  <span class="total-count">({{ totalRow()!.qtdProdutos }} produtos com movimento)</span>
                </div>
              </td>
              @for (cell of totalRow()!.janelas; track cell.meses) {
                <td class="col-window" [class.sorted-col]="cell.meses === sortWindow()">
                  <app-trend-cell
                    [cell]="cell"
                    [metric]="metric()"
                    [params]="params()"
                    [isSortedColumn]="cell.meses === sortWindow()"
                  />
                </td>
              }
            </tr>
          </tbody>
        }

        @if (groupBy() === 'product') {
          <tbody>
            @for (item of rows(); track getItemKey(item)) {
              <tr
                appTrendRow
                [row]="asProductRow(item)"
                [metric]="metric()"
                [sortWindow]="sortWindow()"
                [params]="params()"
                [isExpanded]="isExpanded(getItemKey(item))"
                [ariaControlsId]="rowValuesId(getItemKey(item))"
                (toggle)="toggleRow.emit(getItemKey(item))"
              ></tr>
              @if (isExpanded(getItemKey(item))) {
                <tr [id]="rowValuesId(getItemKey(item))" class="expanded-detail-row">
                  <td colspan="6" class="expanded-detail-td">
                    <app-trend-row-values
                      [janelas]="item.janelas"
                      [metric]="metric()"
                      [windowMetas]="columns()"
                    />
                  </td>
                </tr>
              }
            }
          </tbody>
        } @else {
          @for (item of rows(); track getItemKey(item)) {
            <tbody
              appTrendSupplierGroup
              [supplier]="asSupplierRow(item)"
              [detailState]="getSupplierDetail(asSupplierRow(item).fornecedorChave)"
              [metric]="metric()"
              [sortWindow]="sortWindow()"
              [sortDir]="sortDir()"
              [params]="params()"
              [windowMetas]="columns()"
              [isExpanded]="isExpanded(asSupplierRow(item).fornecedorChave)"
              (toggle)="toggleRow.emit(asSupplierRow(item).fornecedorChave)"
              (sortChange)="detailSortChange.emit({ supplierKey: asSupplierRow(item).fornecedorChave, sortBy: $event })"
              (pageChange)="detailPageChange.emit({ supplierKey: asSupplierRow(item).fornecedorChave, page: $event })"
              (retry)="detailRetry.emit(asSupplierRow(item).fornecedorChave)"
            ></tbody>
          }
        }
      </table>
    </div>
  `,
  styles: [`
    .trend-table-wrapper {
      width: 100%;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      box-shadow: var(--shadow-xs);
      overflow-x: auto;
      transition: opacity var(--transition-fast);

      &.is-loading {
        opacity: 0.65;
      }
    }

    .trend-table {
      width: 100%;
      min-width: 720px;
      table-layout: fixed;
      border-collapse: collapse;

      th {
        background-color: var(--bg-table-header);
        border-bottom: 2px solid var(--border-default);
        vertical-align: middle;
        height: 1px;
        padding: 0;
      }
    }

    .th-expand {
      width: 44px;
    }

    .th-entity {
      text-align: left;
      color: var(--text-primary);
    }

    .th-entity-content {
      display: flex;
      flex-direction: column;
      justify-content: center;
      min-height: 58px;
      gap: 4px;
      padding: 10px var(--space-3);
    }

    .th-entity-title {
      font-family: var(--font-family-headline);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      line-height: 18px;
      color: var(--text-primary);
    }

    .th-entity-sub {
      font-family: var(--font-family-body);
      font-size: 0.6875rem;
      font-weight: 500;
      line-height: 1.25;
      color: var(--text-secondary);
    }

    .th-entity-base {
      font-family: var(--font-family-mono);
      font-weight: 600;
      color: var(--text-primary);
    }

    .th-window {
      width: 15.5%;
      min-width: 116px;
      border-left: 1px solid var(--border-subtle);
      transition: background-color var(--transition-fast);

      &.is-sorted {
        background-color: var(--brand-primary-subtle);
      }
    }

    .total-row {
      background-color: var(--bg-table-row-zebra);
      border-bottom: 2px solid var(--border-default);

      td {
        padding: var(--space-3);
      }
    }

    .total-entity-title {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 0.875rem;
      color: var(--text-primary);
    }

    .total-count {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }

    .col-expand {
      width: 44px;
      text-align: center;
    }

    .col-entity {
      padding: var(--space-2) var(--space-3);
    }

    .col-window {
      padding: var(--space-2) var(--space-3);
      text-align: right;
    }

    .col-window.sorted-col {
      background-color: var(--bg-table-col-sorted);
    }

    .expanded-detail-td {
      padding: 0;
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
  `],
})
export class TrendTableComponent {
  readonly columns = input.required<TrendWindowMeta[]>();
  readonly rows = input.required<(TrendProductRow | TrendSupplierRow)[]>();
  readonly groupBy = input.required<TrendGroupBy>();
  readonly metric = input.required<TrendMetric>();
  readonly comparisonMode = input<TrendComparisonMode>('point');
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly expandedKeys = input<Set<string | number>>(new Set());
  readonly details = input<Map<string, SupplierDetailState>>(new Map());
  readonly totalRow = input<TrendTotalRow | null>(null);
  readonly loading = input<boolean>(false);

  readonly sort = output<TrendSortWindow>();
  readonly toggleRow = output<string | number>();
  readonly detailSortChange = output<{ supplierKey: string; sortBy: TrendSortBy }>();
  readonly detailPageChange = output<{ supplierKey: string; page: number }>();
  readonly detailRetry = output<string>();

  readonly baseSpanLabel = computed(() => {
    const cols = this.columns();
    if (!cols.length) return '';
    const first = cols[0].atual;
    const firstStart = first.inicio.slice(0, 7);
    const firstEnd = first.fim.slice(0, 7);
    const allSameSingleMonth = cols.every(
      (c) => c.atual.inicio.slice(0, 7) === firstStart && c.atual.fim.slice(0, 7) === firstEnd && firstStart === firstEnd,
    );
    return allSameSingleMonth ? formatWindowMonthSpan(first) : '';
  });

  getItemKey(item: TrendProductRow | TrendSupplierRow): string | number {
    return 'fornecedorChave' in item ? item.fornecedorChave : item.codigo;
  }

  rowValuesId(key: string | number): string {
    return `product-values-${String(key).replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  }

  isExpanded(key: string | number): boolean {
    return this.expandedKeys().has(key);
  }

  getSupplierDetail(key: string): SupplierDetailState | null {
    return this.details().get(key) ?? null;
  }

  asProductRow(item: TrendProductRow | TrendSupplierRow): TrendProductRow {
    return item as TrendProductRow;
  }

  asSupplierRow(item: TrendProductRow | TrendSupplierRow): TrendSupplierRow {
    return item as TrendSupplierRow;
  }
}
