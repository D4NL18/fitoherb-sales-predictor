/**
 * Grupo expansível de fornecedor (tbody compartilhado na tabela principal) com valores detalhados,
 * produtos filhos alinhados às colunas do pai, ordenação por contribuição/variação e paginação (Design Plan §5.6, P-090, P-092).
 */
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
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
import { TrendRowValuesComponent } from '../trend-row-values/trend-row-values.component';
import { TrendPagerComponent } from '../trend-pager/trend-pager.component';
import { TrendErrorBannerComponent } from '../trend-error-banner/trend-error-banner.component';

@Component({
  selector: 'tbody[appTrendSupplierGroup]',
  standalone: true,
  imports: [
    CommonModule,
    TrendCellComponent,
    TrendRowComponent,
    TrendRowValuesComponent,
    TrendPagerComponent,
    TrendErrorBannerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Linha Pai do Fornecedor (alinhada diretamente às colunas da tabela principal) -->
    <tr class="supplier-row" [class.is-expanded]="isExpanded()">
      <td class="col-expand">
        <button
          #expandBtn
          type="button"
          class="expand-chevron-btn"
          [class.is-expanded]="isExpanded()"
          (click)="toggle.emit()"
          [attr.aria-expanded]="isExpanded()"
          [attr.aria-controls]="detailRegionId()"
          [attr.aria-busy]="isExpanded() && detailState()?.status === 'loading'"
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

    <!-- Região Expansível: Valores do Fornecedor + Controles e Produtos Filhos Alinhados -->
    @if (isExpanded()) {
      <tr [id]="detailRegionId()" class="detail-header-row" (keydown.escape)="onCollapseKey($event)">
        <td colspan="6" class="detail-banner-td">
          <app-trend-row-values
            [janelas]="supplierValuesJanelas()"
            [metric]="metric()"
            [windowMetas]="windowMetas()"
          />

          <div class="detail-header">
            <div class="detail-header-info">
              <span class="detail-caption">Produtos de {{ supplier().fornecedor }}</span>
              <span class="detail-subcaption">
                Contribuição calculada sobre a soma de vendas do fornecedor
              </span>
            </div>

            <div class="detail-sort-controls">
              <span class="sort-caption">Ordenar filhos por:</span>
              <div class="sort-pill-group">
                <button
                  type="button"
                  class="sort-pill"
                  [class.active]="detailState()?.sortBy === 'contribution'"
                  [attr.aria-pressed]="detailState()?.sortBy === 'contribution'"
                  (click)="sortChange.emit('contribution')"
                >
                  <span>Contribuição</span>
                  @if (detailState()?.sortBy === 'contribution') {
                    <span class="sort-dir-glyph" aria-hidden="true">{{ detailState()?.sortDir === 'asc' ? '↑' : '↓' }}</span>
                  }
                </button>
                <button
                  type="button"
                  class="sort-pill"
                  [class.active]="detailState()?.sortBy === 'variation'"
                  [attr.aria-pressed]="detailState()?.sortBy === 'variation'"
                  (click)="sortChange.emit('variation')"
                >
                  <span>Variação %</span>
                  @if (detailState()?.sortBy === 'variation') {
                    <span class="sort-dir-glyph" aria-hidden="true">{{ detailState()?.sortDir === 'asc' ? '↑' : '↓' }}</span>
                  }
                </button>
              </div>
            </div>
          </div>
        </td>
      </tr>

      @if (detailState()?.status === 'loading') {
        @for (sk of skeletonRows; track sk) {
          <tr class="detail-skeleton-row" aria-hidden="true">
            <td class="col-expand"></td>
            <td class="col-entity">
              <div class="child-skeleton-entity">
                <span class="skeleton-line" style="width: 65%"></span>
                <span class="skeleton-line" style="width: 35%"></span>
              </div>
            </td>
            <td class="col-window"><span class="skeleton-box" style="width: 70px; height: 22px"></span></td>
            <td class="col-window"><span class="skeleton-box" style="width: 70px; height: 22px"></span></td>
            <td class="col-window"><span class="skeleton-box" style="width: 70px; height: 22px"></span></td>
            <td class="col-window"><span class="skeleton-box" style="width: 70px; height: 22px"></span></td>
          </tr>
        }
      } @else if (detailState()?.status === 'error') {
        <tr class="detail-state-row" (keydown.escape)="onCollapseKey($event)">
          <td colspan="6" class="detail-state-td">
            <app-trend-error-banner
              [message]="detailState()?.error?.message || 'Erro ao carregar produtos do fornecedor.'"
              (retry)="retry.emit()"
            />
          </td>
        </tr>
      } @else if (detailState()?.status === 'empty') {
        <tr class="detail-state-row" (keydown.escape)="onCollapseKey($event)">
          <td colspan="6" class="detail-state-td">
            <div class="detail-empty" role="status">
              Nenhum produto ativo encontrado para este fornecedor no período.
            </div>
          </td>
        </tr>
      } @else if (detailState()?.data) {
        @for (prod of detailState()!.data!.data; track prod.codigo) {
          <tr
            appTrendRow
            class="detail-child-row"
            level="child"
            [row]="prod"
            [metric]="metric()"
            [sortWindow]="sortWindow()"
            [params]="params()"
            [isExpanded]="isChildExpanded(prod.codigo)"
            [ariaControlsId]="childValuesId(prod.codigo)"
            (toggle)="toggleChild(prod.codigo)"
            (keydown.escape)="onCollapseKey($event)"
          ></tr>
          @if (isChildExpanded(prod.codigo)) {
            <tr
              [id]="childValuesId(prod.codigo)"
              class="child-values-row"
              (keydown.escape)="onCollapseChild($event, prod.codigo)"
            >
              <td colspan="6" class="child-values-td">
                <app-trend-row-values
                  [janelas]="prod.janelas"
                  [metric]="metric()"
                  [windowMetas]="windowMetas()"
                />
              </td>
            </tr>
          }
        }

        @if (detailState()!.data!.meta.totalPages > 1) {
          <tr class="detail-pager-row" (keydown.escape)="onCollapseKey($event)">
            <td colspan="6" class="detail-pager-td">
              <app-trend-pager
                [page]="detailState()!.data!.meta.page"
                [totalPages]="detailState()!.data!.meta.totalPages"
                [totalItems]="detailState()!.data!.meta.totalItems"
                [offset]="detailState()!.data!.meta.offset"
                [limit]="detailState()!.data!.meta.limit"
                [ariaLabel]="'Paginação de produtos de ' + supplier().fornecedor"
                (pageChange)="pageChange.emit($event)"
              />
            </td>
          </tr>
        }
      }
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

    .supplier-title-group {
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: var(--space-2);
      min-width: 0;
    }

    .supplier-name {
      font-size: 0.9375rem;
      color: var(--text-primary);
      overflow-wrap: anywhere;
    }

    .supplier-meta-pill {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-secondary);
    }

    .col-window {
      padding: var(--space-2) var(--space-3);
      text-align: right;
      vertical-align: middle;
    }

    .col-window.sorted-col {
      background-color: var(--bg-table-col-sorted);
    }

    .detail-header-row,
    .detail-state-row,
    .detail-pager-row {
      background-color: var(--bg-table-row-zebra);
    }

    .detail-banner-td,
    .child-values-td {
      padding: 0 !important;
    }

    .detail-state-td {
      padding: var(--space-3) var(--space-4) !important;
      border-bottom: 2px solid var(--border-default);
    }

    .detail-pager-td {
      padding: 0 var(--space-4) var(--space-2) !important;
      border-bottom: 2px solid var(--border-default);
    }

    .detail-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: var(--space-2);
      padding: var(--space-3) var(--space-4);
      background-color: var(--bg-table-row-zebra);
      border-bottom: 1px solid var(--border-subtle);
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
      color: var(--text-secondary);
    }

    .detail-sort-controls {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
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

      &:hover:not(.active) {
        background-color: var(--bg-subtle);
        color: var(--text-primary);
      }

      &.active {
        background-color: var(--brand-primary);
        color: var(--text-on-brand);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }
    }

    .sort-dir-glyph {
      font-size: 0.75rem;
      line-height: 1;
    }

    .detail-child-row {
      background-color: var(--bg-table-row-zebra);
    }

    .detail-skeleton-row {
      background-color: var(--bg-table-row-zebra);
      border-bottom: 1px solid var(--border-subtle);
    }

    .child-skeleton-entity {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding-left: var(--space-4);
    }

    .detail-empty {
      padding: var(--space-3);
      text-align: center;
      color: var(--text-secondary);
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

  private readonly expandBtn = viewChild<ElementRef<HTMLButtonElement>>('expandBtn');
  private readonly expandedChildSkus = signal<Set<number>>(new Set());
  readonly skeletonRows = [0, 1, 2];

  readonly detailRegionId = computed(() =>
    `supplier-detail-${this.supplier().fornecedorChave.replace(/[^a-zA-Z0-9_-]/g, '-')}`
  );

  readonly supplierValuesJanelas = computed(() => {
    const fromMeta = this.detailState()?.data?.meta?.fornecedor?.janelas;
    return fromMeta && fromMeta.length > 0 ? fromMeta : this.supplier().janelas;
  });

  readonly expandAriaLabel = computed(() => {
    const isExp = this.isExpanded();
    return `${isExp ? 'Recolher' : 'Expandir'} produtos do fornecedor ${this.supplier().fornecedor}`;
  });

  childValuesId(sku: number): string {
    return `${this.detailRegionId()}-child-${sku}`;
  }

  isChildExpanded(sku: number): boolean {
    return this.expandedChildSkus().has(sku);
  }

  toggleChild(sku: number): void {
    this.expandedChildSkus.update((curr) => {
      const next = new Set(curr);
      if (next.has(sku)) {
        next.delete(sku);
      } else {
        next.add(sku);
      }
      return next;
    });
  }

  onCollapseChild(event: Event, sku: number): void {
    event.stopPropagation();
    this.expandedChildSkus.update((curr) => {
      const next = new Set(curr);
      next.delete(sku);
      return next;
    });
  }

  onCollapseKey(event: Event): void {
    event.stopPropagation();
    if (this.isExpanded()) {
      this.toggle.emit();
      this.expandBtn()?.nativeElement.focus();
    }
  }
}
