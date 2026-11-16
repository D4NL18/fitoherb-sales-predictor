/**
 * Visão mobile em cartões densos para telas < 768px (Design Plan §8).
 * Suporta grade 2x2 para produtos, total geral, detalhamento de valores e drill-down completo de fornecedores.
 */
import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendCell,
  TrendDetailRow,
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
import { TrendCellComponent } from '../trend-cell/trend-cell.component';
import { TrendRowValuesComponent } from '../trend-row-values/trend-row-values.component';
import { TrendPagerComponent } from '../trend-pager/trend-pager.component';
import { TrendErrorBannerComponent } from '../trend-error-banner/trend-error-banner.component';
import { TrendTableSkeletonComponent } from '../trend-table-skeleton/trend-table-skeleton.component';
import { formatWindowMonthSpan } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-card-list',
  standalone: true,
  imports: [
    CommonModule,
    TrendCellComponent,
    TrendRowValuesComponent,
    TrendPagerComponent,
    TrendErrorBannerComponent,
    TrendTableSkeletonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="trend-cards-container" [class.is-loading]="loading()" [attr.aria-busy]="loading()">
      <!-- Controles de ordenação mobile -->
      <div class="mobile-sort-bar">
        <label for="mobile-window-select" class="mobile-sort-label">Ordenar por:</label>
        <select
          id="mobile-window-select"
          class="mobile-select"
          [value]="sortWindow()"
          (change)="onWindowChange($event)"
        >
          <option [value]="1">1 mês</option>
          <option [value]="3">3 meses</option>
          <option [value]="6">6 meses</option>
          <option [value]="12">12 meses</option>
        </select>

        <button
          type="button"
          class="mobile-dir-btn"
          (click)="toggleSortDir()"
          aria-label="Alternar sentido da ordenação"
        >
          {{ sortDir() === 'desc' ? 'Maiores altas ↓' : 'Maiores quedas ↑' }}
        </button>
      </div>

      <!-- Cartão Resumo Geral -->
      @if (totalRow() && totalRow()!.janelas.length > 0) {
        <section class="trend-card total-summary-card" aria-label="Resumo geral de todos os produtos ativos">
          <header class="card-header">
            <div class="card-title-group">
              <span class="card-sku">RESUMO GERAL</span>
              <h3 class="card-title">Todos os produtos ativos</h3>
              <span class="card-subtitle">{{ totalRow()!.qtdProdutos }} produtos com movimento</span>
            </div>
          </header>

          <div class="card-windows-grid">
            @for (cell of totalRow()!.janelas; track cell.meses) {
              <div class="card-window-box" [class.is-sorted-box]="cell.meses === sortWindow()">
                <div class="box-header">
                  <span class="box-window-title">{{ cell.meses }} {{ cell.meses === 1 ? 'mês' : 'meses' }}</span>
                  <span class="box-span-sub">{{ getSpanLabel(cell.meses) }}</span>
                </div>
                <app-trend-cell
                  variant="card"
                  [cell]="cell"
                  [metric]="metric()"
                  [params]="params()"
                  [isSortedColumn]="cell.meses === sortWindow()"
                />
              </div>
            }
          </div>
        </section>
      }

      <!-- Lista de Cartões -->
      <ul class="card-list" aria-label="Lista de tendências">
        @for (item of items(); track getItemKey(item)) {
          <li class="card-list-item">
            <article class="trend-card" [class.is-expanded]="isExpanded(getItemKey(item))">
              <header class="card-header">
                <div class="card-title-group">
                  <span class="card-sku">{{ getSku(item) }}</span>
                  <h3 class="card-title">{{ getTitle(item) }}</h3>
                  @if (getSubtitle(item)) {
                    <span class="card-subtitle">{{ getSubtitle(item) }}</span>
                  }
                </div>

                <button
                  type="button"
                  class="card-expand-btn"
                  [class.is-expanded]="isExpanded(getItemKey(item))"
                  (click)="toggleRow.emit(getItemKey(item))"
                  [attr.aria-expanded]="isExpanded(getItemKey(item))"
                  [attr.aria-controls]="cardDetailId(getItemKey(item))"
                  [attr.aria-label]="(isExpanded(getItemKey(item)) ? 'Recolher detalhes de ' : 'Ver detalhes de ') + getTitle(item)"
                >
                  <span class="chevron-icon" aria-hidden="true">›</span>
                </button>
              </header>

              <!-- Grade 2x2 das 4 Janelas -->
              <div class="card-windows-grid">
                @for (cell of item.janelas; track cell.meses) {
                  <div
                    class="card-window-box"
                    [class.is-sorted-box]="cell.meses === sortWindow()"
                  >
                    <div class="box-header">
                      <span class="box-window-title">{{ cell.meses }} {{ cell.meses === 1 ? 'mês' : 'meses' }}</span>
                      <span class="box-span-sub">{{ getSpanLabel(cell.meses) }}</span>
                    </div>

                    <app-trend-cell
                      variant="card"
                      [cell]="cell"
                      [metric]="metric()"
                      [params]="params()"
                      [isSortedColumn]="cell.meses === sortWindow()"
                    />
                  </div>
                }
              </div>

              <!-- Área Expandida -->
              @if (isExpanded(getItemKey(item))) {
                <div [id]="cardDetailId(getItemKey(item))" class="card-expanded-region">
                  <app-trend-row-values
                    [janelas]="getExpandedJanelas(item)"
                    [metric]="metric()"
                    [windowMetas]="windowMetas()"
                  />

                  @if (groupBy() === 'supplier' && isSupplierRow(item)) {
                    <div class="mobile-supplier-detail">
                      <div class="mobile-detail-header">
                        <div class="mobile-detail-titles">
                          <strong class="mobile-detail-title">Produtos de {{ item.fornecedor }}</strong>
                          <span class="mobile-detail-sub">Contribuição sobre as vendas do fornecedor</span>
                        </div>

                        <div class="sort-pill-group">
                          <button
                            type="button"
                            class="sort-pill"
                            [class.active]="getSupplierDetail(item.fornecedorChave)?.sortBy === 'contribution'"
                            [attr.aria-pressed]="getSupplierDetail(item.fornecedorChave)?.sortBy === 'contribution'"
                            (click)="detailSortChange.emit({ supplierKey: item.fornecedorChave, sortBy: 'contribution' })"
                          >
                            <span>Contribuição</span>
                            @if (getSupplierDetail(item.fornecedorChave)?.sortBy === 'contribution') {
                              <span aria-hidden="true">{{ getSupplierDetail(item.fornecedorChave)?.sortDir === 'asc' ? '↑' : '↓' }}</span>
                            }
                          </button>
                          <button
                            type="button"
                            class="sort-pill"
                            [class.active]="getSupplierDetail(item.fornecedorChave)?.sortBy === 'variation'"
                            [attr.aria-pressed]="getSupplierDetail(item.fornecedorChave)?.sortBy === 'variation'"
                            (click)="detailSortChange.emit({ supplierKey: item.fornecedorChave, sortBy: 'variation' })"
                          >
                            <span>Variação %</span>
                            @if (getSupplierDetail(item.fornecedorChave)?.sortBy === 'variation') {
                              <span aria-hidden="true">{{ getSupplierDetail(item.fornecedorChave)?.sortDir === 'asc' ? '↑' : '↓' }}</span>
                            }
                          </button>
                        </div>
                      </div>

                      @if (getSupplierDetail(item.fornecedorChave)?.status === 'loading') {
                        <app-trend-table-skeleton [rows]="2" variant="cards" />
                      } @else if (getSupplierDetail(item.fornecedorChave)?.status === 'error') {
                        <app-trend-error-banner
                          [message]="getSupplierDetail(item.fornecedorChave)?.error?.message || 'Erro ao carregar produtos do fornecedor.'"
                          (retry)="detailRetry.emit(item.fornecedorChave)"
                        />
                      } @else if (getSupplierDetail(item.fornecedorChave)?.status === 'empty') {
                        <p class="mobile-detail-empty" role="status">
                          Nenhum produto ativo encontrado para este fornecedor no período.
                        </p>
                      } @else if (getSupplierDetail(item.fornecedorChave)?.data) {
                        <ul class="mobile-child-list">
                          @for (prod of getSupplierDetail(item.fornecedorChave)!.data!.data; track prod.codigo) {
                            <li class="mobile-child-card">
                              <div class="card-header">
                                <div class="card-title-group">
                                  <span class="card-sku">#{{ prod.codigo }}</span>
                                  <h4 class="mobile-child-title">{{ prod.descricao }}</h4>
                                </div>
                                <button
                                  type="button"
                                  class="card-expand-btn"
                                  [class.is-expanded]="isChildExpanded(item.fornecedorChave, prod.codigo)"
                                  (click)="toggleChild(item.fornecedorChave, prod.codigo)"
                                  [attr.aria-expanded]="isChildExpanded(item.fornecedorChave, prod.codigo)"
                                  [attr.aria-label]="'Ver valores detalhados de ' + prod.descricao"
                                >
                                  <span class="chevron-icon" aria-hidden="true">›</span>
                                </button>
                              </div>

                              <div class="card-windows-grid">
                                @for (c of prod.janelas; track c.meses) {
                                  <div class="card-window-box" [class.is-sorted-box]="c.meses === sortWindow()">
                                    <div class="box-header">
                                      <span class="box-window-title">{{ c.meses }} {{ c.meses === 1 ? 'mês' : 'meses' }}</span>
                                    </div>
                                    <app-trend-cell
                                      variant="card"
                                      [cell]="c"
                                      [metric]="metric()"
                                      [params]="params()"
                                      [isSortedColumn]="c.meses === sortWindow()"
                                    />
                                  </div>
                                }
                              </div>

                              @if (isChildExpanded(item.fornecedorChave, prod.codigo)) {
                                <app-trend-row-values
                                  [janelas]="prod.janelas"
                                  [metric]="metric()"
                                  [windowMetas]="windowMetas()"
                                />
                              }
                            </li>
                          }
                        </ul>

                        @if (getSupplierDetail(item.fornecedorChave)!.data!.meta.totalPages > 1) {
                          <app-trend-pager
                            [page]="getSupplierDetail(item.fornecedorChave)!.data!.meta.page"
                            [totalPages]="getSupplierDetail(item.fornecedorChave)!.data!.meta.totalPages"
                            [totalItems]="getSupplierDetail(item.fornecedorChave)!.data!.meta.totalItems"
                            [offset]="getSupplierDetail(item.fornecedorChave)!.data!.meta.offset"
                            [limit]="getSupplierDetail(item.fornecedorChave)!.data!.meta.limit"
                            [ariaLabel]="'Paginação de produtos de ' + item.fornecedor"
                            (pageChange)="detailPageChange.emit({ supplierKey: item.fornecedorChave, page: $event })"
                          />
                        }
                      }
                    </div>
                  }
                </div>
              }
            </article>
          </li>
        }
      </ul>
    </div>
  `,
  styles: [`
    .trend-cards-container {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      transition: opacity var(--transition-fast);

      &.is-loading {
        opacity: 0.65;
      }
    }

    .mobile-sort-bar {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
      padding: var(--space-2) var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
    }

    .mobile-sort-label {
      font-size: 0.8125rem;
      font-weight: 600;
      color: var(--text-secondary);
    }

    .mobile-select {
      min-height: 40px;
      padding: 0 var(--space-2);
      font-size: 0.8125rem;
      font-weight: 600;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      color: var(--text-primary);

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .mobile-dir-btn {
      margin-left: auto;
      min-height: 40px;
      padding: 0 var(--space-3);
      font-family: var(--font-family-body);
      font-size: 0.8125rem;
      font-weight: 600;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      color: var(--brand-primary);
      cursor: pointer;

      &:hover {
        background-color: var(--bg-subtle);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .card-list,
    .mobile-child-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .trend-card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      padding: var(--space-4);
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .total-summary-card {
      background-color: var(--bg-table-row-zebra);
      border-color: var(--border-strong);
    }

    .card-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-2);
    }

    .card-title-group {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }

    .card-sku {
      font-family: var(--font-family-mono);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
    }

    .card-title,
    .mobile-child-title {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
      overflow-wrap: anywhere;
    }

    .card-subtitle {
      font-size: 0.8125rem;
      color: var(--text-secondary);
      overflow-wrap: anywhere;
    }

    .card-expand-btn {
      width: 40px;
      height: 40px;
      flex-shrink: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      color: var(--text-secondary);
      font-size: 1.2rem;
      cursor: pointer;
      transition: transform var(--transition-fast), background-color var(--transition-fast);

      &.is-expanded {
        transform: rotate(90deg);
        color: var(--brand-primary);
        border-color: var(--brand-primary);
      }

      &:hover {
        background-color: var(--bg-muted);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .card-windows-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--space-2);
    }

    .card-window-box {
      padding: var(--space-2);
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      display: flex;
      flex-direction: column;
      gap: 4px;
      min-width: 0;

      &.is-sorted-box {
        background-color: var(--brand-primary-subtle);
        border-color: var(--brand-primary);
      }
    }

    .box-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 4px;
      font-size: 0.6875rem;
    }

    .box-window-title {
      font-weight: 700;
      text-transform: uppercase;
      color: var(--text-primary);
    }

    .box-span-sub {
      font-family: var(--font-family-mono);
      color: var(--text-secondary);
    }

    .card-expanded-region {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .mobile-supplier-detail {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      padding-top: var(--space-2);
      border-top: 1px solid var(--border-subtle);
    }

    .mobile-detail-header {
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }

    .mobile-detail-titles {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .mobile-detail-title {
      font-size: 0.8125rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: var(--text-primary);
    }

    .mobile-detail-sub {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }

    .sort-pill-group {
      display: inline-flex;
      align-self: flex-start;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      padding: 2px;
      gap: 2px;
    }

    .sort-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-height: 36px;
      padding: 0 var(--space-3);
      background: transparent;
      border: none;
      font-family: var(--font-family-body);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      border-radius: var(--radius-xs);

      &.active {
        background-color: var(--brand-primary);
        color: var(--text-on-brand);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }
    }

    .mobile-child-card {
      padding: var(--space-3);
      background-color: var(--bg-table-row-zebra);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }

    .mobile-detail-empty {
      margin: 0;
      padding: var(--space-3);
      text-align: center;
      font-size: 0.875rem;
      color: var(--text-secondary);
      background-color: var(--bg-table-row-zebra);
      border-radius: var(--radius-xs);
    }
  `],
})
export class TrendCardListComponent {
  readonly items = input.required<(TrendProductRow | TrendSupplierRow | TrendDetailRow)[]>();
  readonly groupBy = input<TrendGroupBy>('product');
  readonly metric = input.required<TrendMetric>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();
  readonly windowMetas = input<TrendWindowMeta[] | null>(null);
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly expandedKeys = input<Set<string | number>>(new Set());
  readonly details = input<Map<string, SupplierDetailState>>(new Map());
  readonly totalRow = input<TrendTotalRow | null>(null);
  readonly loading = input<boolean>(false);

  readonly sortChange = output<{ window: TrendSortWindow; dir: TrendSortDir }>();
  readonly toggleRow = output<string | number>();
  readonly detailSortChange = output<{ supplierKey: string; sortBy: TrendSortBy }>();
  readonly detailPageChange = output<{ supplierKey: string; page: number }>();
  readonly detailRetry = output<string>();

  private readonly expandedChildSkus = signal<Set<string>>(new Set());

  isSupplierRow(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): item is TrendSupplierRow {
    return 'fornecedorChave' in item;
  }

  getItemKey(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): string | number {
    return this.isSupplierRow(item) ? item.fornecedorChave : item.codigo;
  }

  cardDetailId(key: string | number): string {
    return `mobile-card-detail-${String(key).replace(/[^a-zA-Z0-9_-]/g, '-')}`;
  }

  getSku(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): string {
    if (this.isSupplierRow(item)) {
      return `${item.qtdProdutos} ${item.qtdProdutos === 1 ? 'produto ativo' : 'produtos ativos'}`;
    }
    return `#${item.codigo}`;
  }

  getTitle(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): string {
    return this.isSupplierRow(item) ? item.fornecedor : item.descricao;
  }

  getSubtitle(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): string | null {
    return this.isSupplierRow(item) ? null : item.fornecedor;
  }

  isExpanded(key: string | number): boolean {
    return this.expandedKeys().has(key);
  }

  getSupplierDetail(key: string): SupplierDetailState | null {
    return this.details().get(key) ?? null;
  }

  getExpandedJanelas(item: TrendProductRow | TrendSupplierRow | TrendDetailRow): TrendCell[] {
    if (this.isSupplierRow(item)) {
      const fromMeta = this.getSupplierDetail(item.fornecedorChave)?.data?.meta?.fornecedor?.janelas;
      if (fromMeta && fromMeta.length > 0) {
        return fromMeta;
      }
    }
    return item.janelas;
  }

  isChildExpanded(supplierKey: string, sku: number): boolean {
    return this.expandedChildSkus().has(`${supplierKey}:${sku}`);
  }

  toggleChild(supplierKey: string, sku: number): void {
    const compositeKey = `${supplierKey}:${sku}`;
    this.expandedChildSkus.update((curr) => {
      const next = new Set(curr);
      if (next.has(compositeKey)) {
        next.delete(compositeKey);
      } else {
        next.add(compositeKey);
      }
      return next;
    });
  }

  getSpanLabel(windowSize: number): string {
    const meta = this.windowMetas()?.find((w) => w.meses === windowSize);
    return meta ? formatWindowMonthSpan(meta.atual) : '';
  }

  onWindowChange(event: Event): void {
    const val = parseInt((event.target as HTMLSelectElement).value, 10) as TrendSortWindow;
    this.sortChange.emit({ window: val, dir: this.sortDir() });
  }

  toggleSortDir(): void {
    const newDir = this.sortDir() === 'desc' ? 'asc' : 'desc';
    this.sortChange.emit({ window: this.sortWindow(), dir: newDir });
  }
}
