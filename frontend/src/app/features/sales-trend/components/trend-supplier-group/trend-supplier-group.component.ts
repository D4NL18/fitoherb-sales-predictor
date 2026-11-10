/**
 * Grupo expansível de fornecedor com produtos filhos e cálculo de contribuição (Design Plan §5.6, P-090, P-092).
 * Inclui paginação independente de 20 itens, alternância de ordenação e tratamento de erros do detalhe.
 */
import { Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendMetric,
  TrendParameters,
  TrendSortBy,
  TrendSortDir,
  TrendSortWindow,
  TrendSupplierRow,
  TrendWindowMeta,
} from '../../models/sales-trend.model';
import { SupplierDetailState } from '../../services/sales-trend.store';
import { TrendCellComponent } from '../trend-cell/trend-cell.component';
import { TrendRowComponent } from '../trend-row/trend-row.component';
import { TrendPagerComponent } from '../trend-pager/trend-pager.component';
import { TrendErrorBannerComponent } from '../trend-error-banner/trend-error-banner.component';
import { TrendTableSkeletonComponent } from '../trend-table-skeleton/trend-table-skeleton.component';

@Component({
  selector: 'app-trend-supplier-group',
  standalone: true,
  imports: [
    CommonModule,
    TrendCellComponent,
    TrendRowComponent,
    TrendPagerComponent,
    TrendErrorBannerComponent,
    TrendTableSkeletonComponent,
  ],
  template: `
    <!-- Linha Pai do Fornecedor -->
    <tr class="supplier-row" [class.is-expanded]="isExpanded()">
      <td class="col-expand">
        <button
          type="button"
          class="expand-chevron-btn"
          [class.is-expanded]="isExpanded()"
          (click)="toggle.emit()"
          [attr.aria-expanded]="isExpanded()"
          [attr.aria-label]="expandAriaLabel()"
        >
          <span class="chevron-icon" aria-hidden="true">›</span>
        </button>
      </td>

      <td class="col-entity">
        <div class="supplier-title-group">
          <strong class="supplier-name">{{ supplier().fornecedor }}</strong>
          <span class="supplier-meta-pill">
            {{ supplier().qtdProdutos }} {{ supplier().qtdProdutos === 1 ? 'produto ativo' : 'produtos ativos' }}
          </span>
        </div>
      </td>

      @for (cell of supplier().janelas; track cell.meses) {
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

    <!-- Região Expansível com Produtos Filhos -->
    @if (isExpanded()) {
      <tr class="detail-container-row">
        <td colspan="6" class="detail-cell">
          <div class="supplier-detail-panel">
            <header class="detail-header">
              <div class="detail-header-info">
                <span class="detail-caption">Produtos de {{ supplier().fornecedor }}</span>
                <span class="detail-subcaption">
                  Contribuição calculada sobre a soma de vendas do fornecedor
                </span>
              </div>

              <!-- Alternador de ordenação dos filhos -->
              <div class="detail-sort-controls">
                <span class="sort-caption">Ordenar filhos por:</span>
                <div class="sort-pill-group">
                  <button
                    type="button"
                    class="sort-pill"
                    [class.active]="detailState()?.sortBy === 'contribution'"
                    (click)="sortChange.emit('contribution')"
                  >
                    Contribuição
                  </button>
                  <button
                    type="button"
                    class="sort-pill"
                    [class.active]="detailState()?.sortBy === 'variation'"
                    (click)="sortChange.emit('variation')"
                  >
                    Variação %
                  </button>
                </div>
              </div>
            </header>

            <!-- Estados do Detalhe: Loading, Error, Empty, Success -->
            @if (detailState()?.status === 'loading') {
              <div class="detail-loading">
                <app-trend-table-skeleton [rows]="3" variant="table" />
              </div>
            } @else if (detailState()?.status === 'error') {
              <div class="detail-error">
                <app-trend-error-banner
                  [message]="detailState()?.error?.message || 'Erro ao carregar produtos do fornecedor.'"
                  (retry)="retry.emit()"
                />
              </div>
            } @else if (detailState()?.status === 'empty') {
              <div class="detail-empty">
                <span>Nenhum produto ativo encontrado para este fornecedor no período.</span>
              </div>
            } @else if (detailState()?.data) {
              <table class="detail-table">
                <thead>
                  <tr>
                    <th style="width: 40px"></th>
                    <th style="text-align: left">PRODUTO</th>
                    <th style="text-align: right">1 MÊS</th>
                    <th style="text-align: right">3 MESES</th>
                    <th style="text-align: right">6 MESES</th>
                    <th style="text-align: right">12 MESES</th>
                  </tr>
                </thead>
                <tbody>
                  @for (prod of detailState()!.data!.data; track prod.codigo) {
                    <tr
                      appTrendRow
                      level="child"
                      [row]="prod"
                      [metric]="metric()"
                      [sortWindow]="sortWindow()"
                      [params]="params()"
                      [isExpanded]="isChildExpanded(prod.codigo)"
                      (toggle)="toggleChild(prod.codigo)"
                    ></tr>
                  }
                </tbody>
              </table>

              <!-- Paginador do detalhe (20 por página) -->
              @if (detailState()!.data!.meta.totalPages > 1) {
                <div class="detail-pager-wrapper">
                  <app-trend-pager
                    [page]="detailState()!.data!.meta.page"
                    [totalPages]="detailState()!.data!.meta.totalPages"
                    [totalItems]="detailState()!.data!.meta.totalItems"
                    [offset]="detailState()!.data!.meta.offset"
                    [limit]="detailState()!.data!.meta.limit"
                    [ariaLabel]="'Paginação de produtos de ' + supplier().fornecedor"
                    (pageChange)="pageChange.emit($event)"
                  />
                </div>
              }
            }
          </div>
        </td>
      </tr>
    }
  `,
  styles: [`
    .supplier-row {
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-subtle);
      transition: background-color var(--transition-fast);

      &:hover {
        background-color: var(--bg-table-row-hover);
      }

      &.is-expanded {
        background-color: var(--brand-primary-subtle);
        border-bottom-color: var(--border-default);
      }
    }

    .col-expand {
      width: 40px;
      text-align: center;
      padding: var(--space-2, 8px) 0;
    }

    .expand-chevron-btn {
      width: 36px;
      height: 36px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      cursor: pointer;
      color: var(--text-secondary);
      font-size: 1.25rem;
      border-radius: var(--radius-xs);
      transition: transform var(--transition-fast);

      &.is-expanded {
        transform: rotate(90deg);
        color: var(--brand-primary);
      }

      &:hover {
        background-color: var(--bg-subtle);
      }
    }

    .col-entity {
      padding: var(--space-2, 8px) var(--space-3, 12px);
      vertical-align: middle;
    }

    .supplier-title-group {
      display: flex;
      align-items: baseline;
      gap: var(--space-2, 8px);
    }

    .supplier-name {
      font-size: 0.9375rem;
      color: var(--text-primary);
    }

    .supplier-meta-pill {
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .col-window {
      padding: var(--space-2, 8px) var(--space-3, 12px);
      text-align: right;
      vertical-align: middle;
    }

    .col-window.sorted-col {
      background-color: rgba(29, 69, 40, 0.04);
    }

    .detail-container-row {
      background-color: var(--bg-table-row-zebra, #FAF8F4);
      border-bottom: 2px solid var(--border-default);
    }

    .detail-cell {
      padding: 0 !important;
    }

    .supplier-detail-panel {
      padding: var(--space-3, 12px) var(--space-4, 16px);
      display: flex;
      flex-direction: column;
      gap: var(--space-3, 12px);
    }

    .detail-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: var(--space-2, 8px);
      padding-bottom: var(--space-2, 8px);
      border-bottom: 1px dashed var(--border-subtle);
    }

    .detail-header-info {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .detail-caption {
      font-family: var(--font-family-headline);
      font-size: 0.8125rem;
      font-weight: 700;
      color: var(--text-primary);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .detail-subcaption {
      font-size: 0.75rem;
      color: var(--text-muted);
    }

    .detail-sort-controls {
      display: flex;
      align-items: center;
      gap: var(--space-2, 8px);
    }

    .sort-caption {
      font-size: 0.75rem;
      color: var(--text-secondary);
      font-weight: 600;
    }

    .sort-pill-group {
      display: inline-flex;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      padding: 1px;
    }

    .sort-pill {
      height: 28px;
      padding: 0 var(--space-2, 8px);
      background: transparent;
      border: none;
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      border-radius: var(--radius-xs);

      &.active {
        background-color: var(--brand-primary);
        color: var(--text-on-brand);
      }
    }

    .detail-table {
      width: 100%;
      border-collapse: collapse;

      th {
        font-family: var(--font-family-body);
        font-size: 0.6875rem;
        font-weight: 700;
        color: var(--text-muted);
        padding: 4px 12px;
        border-bottom: 1px solid var(--border-subtle);
      }
    }

    .detail-pager-wrapper {
      padding-top: var(--space-2, 8px);
      border-top: 1px solid var(--border-subtle);
    }

    .detail-empty {
      padding: var(--space-4, 16px);
      text-align: center;
      color: var(--text-muted);
      font-size: 0.875rem;
    }
  `],
})
export class TrendSupplierGroupComponent {
  readonly supplier = input.required<TrendSupplierRow>();
  readonly detailState = input<SupplierDetailState | null>(null);
  readonly metric = input.required<TrendMetric>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly windowMetas = input<TrendWindowMeta[] | null>(null);
  readonly isExpanded = input<boolean>(false);

  readonly toggle = output<void>();
  readonly sortChange = output<TrendSortBy>();
  readonly pageChange = output<number>();
  readonly retry = output<void>();

  private readonly expandedChildSkus = new Set<number>();

  readonly expandAriaLabel = computed(() => {
    const isExp = this.isExpanded();
    return `${isExp ? 'Recolher' : 'Expandir'} produtos do fornecedor ${this.supplier().fornecedor}`;
  });

  isChildExpanded(sku: number): boolean {
    return this.expandedChildSkus.has(sku);
  }

  toggleChild(sku: number): void {
    if (this.expandedChildSkus.has(sku)) {
      this.expandedChildSkus.delete(sku);
    } else {
      this.expandedChildSkus.add(sku);
    }
  }
}
