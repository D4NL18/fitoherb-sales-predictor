/**
 * Tabela ledger de alta densidade para telas >= 768px (Design Plan §5.4).
 * Suporta cabeçalho sticky, largura proporcional sem rolagem horizontal e acessibilidade WCAG AA.
 */
import { Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
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
  template: `
    <div class="trend-table-wrapper">
      <table class="trend-table" role="table">
        <thead>
          <tr>
            <th class="th-expand" scope="col"><span class="sr-only">Expandir</span></th>
            <th class="th-entity" scope="col">
              {{ groupBy() === 'supplier' ? 'FORNECEDOR' : 'PRODUTO' }}
            </th>
            @for (col of columns(); track col.meses) {
              <th
                class="th-window"
                scope="col"
                [attr.aria-sort]="col.meses === sortWindow() ? (sortDir() === 'desc' ? 'descending' : 'ascending') : 'none'"
              >
                <app-trend-column-header
                  [windowMeta]="col"
                  [sortWindow]="sortWindow()"
                  [sortDir]="sortDir()"
                  (sort)="sort.emit($event)"
                />
              </th>
            }
          </tr>
        </thead>

        <tbody>
          <!-- Linha Total Geral (Q-4) -->
          @if (totalRow()) {
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
          }

          <!-- Linhas de Dados -->
          @for (item of rows(); track getItemKey(item)) {
            @if (groupBy() === 'product') {
              <tr
                appTrendRow
                [row]="asProductRow(item)"
                [metric]="metric()"
                [sortWindow]="sortWindow()"
                [params]="params()"
                [isExpanded]="isExpanded(getItemKey(item))"
                (toggle)="toggleRow.emit(getItemKey(item))"
              ></tr>
              @if (isExpanded(getItemKey(item))) {
                <tr class="expanded-detail-row">
                  <td colspan="6" style="padding: 0">
                    <app-trend-row-values
                      [janelas]="item.janelas"
                      [metric]="metric()"
                      [windowMetas]="columns()"
                    />
                  </td>
                </tr>
              }
            } @else {
              <!-- Grupo de Fornecedor -->
              <app-trend-supplier-group
                style="display: contents"
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
              />
            }
          }
        </tbody>
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
    }

    .trend-table {
      width: 100%;
      table-layout: fixed;
      border-collapse: collapse;

      th {
        background-color: var(--bg-table-header);
        border-bottom: 2px solid var(--border-default);
        vertical-align: bottom;
        padding: 0;
      }
    }

    .th-expand {
      width: 40px;
    }

    .th-entity {
      padding: var(--space-2, 8px) var(--space-3, 12px);
      text-align: left;
      font-family: var(--font-family-headline);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      color: var(--text-primary);
    }

    .th-window {
      width: 15%;
      min-width: 110px;
      max-width: 168px;
    }

    .total-row {
      background-color: var(--bg-table-row-zebra, #FAF8F4);
      border-bottom: 2px solid var(--border-default);

      td {
        padding: var(--space-3, 12px) var(--space-3, 12px);
      }
    }

    .total-entity-title {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 0.875rem;
    }

    .total-count {
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .col-expand {
      width: 40px;
      text-align: center;
    }

    .col-entity {
      padding: var(--space-2, 8px) var(--space-3, 12px);
    }

    .col-window {
      padding: var(--space-2, 8px) var(--space-3, 12px);
      text-align: right;
    }

    .col-window.sorted-col {
      background-color: rgba(29, 69, 40, 0.04);
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }
  `],
})
export class TrendTableComponent {
  readonly columns = input.required<TrendWindowMeta[]>();
  readonly rows = input.required<(TrendProductRow | TrendSupplierRow)[]>();
  readonly groupBy = input.required<TrendGroupBy>();
  readonly metric = input.required<TrendMetric>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly expandedKeys = input<Set<string | number>>(new Set());
  readonly details = input<Map<string, SupplierDetailState>>(new Map());
  readonly totalRow = input<TrendTotalRow | null>(null);

  readonly sort = output<TrendSortWindow>();
  readonly toggleRow = output<string | number>();
  readonly detailSortChange = output<{ supplierKey: string; sortBy: TrendSortBy }>();
  readonly detailPageChange = output<{ supplierKey: string; page: number }>();
  readonly detailRetry = output<string>();

  getItemKey(item: TrendProductRow | TrendSupplierRow): string | number {
    return (item as TrendSupplierRow).fornecedorChave ?? (item as TrendProductRow).codigo;
  }

  isExpanded(key: string | number): boolean {
    return this.expandedKeys().has(key);
  }

  getSupplierDetail(key: string): SupplierDetailState | null {
    return this.details().get(key) ?? null;
  }

  asProductRow(item: any): TrendProductRow {
    return item as TrendProductRow;
  }

  asSupplierRow(item: any): TrendSupplierRow {
    return item as TrendSupplierRow;
  }
}
