/**
 * Visão mobile em cartões densos para telas < 768px (Design Plan §8).
 * Apresenta grade 2x2 com as 4 janelas por item sem rolagem horizontal da página.
 */
import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendCell,
  TrendDetailRow,
  TrendMetric,
  TrendParameters,
  TrendProductRow,
  TrendSortDir,
  TrendSortWindow,
  TrendSupplierRow,
  TrendWindowMeta,
} from '../../models/sales-trend.model';
import { TrendCellComponent } from '../trend-cell/trend-cell.component';
import { TrendRowValuesComponent } from '../trend-row-values/trend-row-values.component';
import { formatWindowMonthSpan } from '../../utils/trend-format';

@Component({
  selector: 'app-trend-card-list',
  standalone: true,
  imports: [CommonModule, TrendCellComponent, TrendRowValuesComponent],
  template: `
    <div class="trend-cards-container" role="feed" aria-label="Lista de cartões de tendência">
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

      <!-- Lista de Cartões -->
      @for (item of items(); track getItemKey(item)) {
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
              (click)="toggleRow.emit(getItemKey(item))"
              [attr.aria-expanded]="isExpanded(getItemKey(item))"
              [attr.aria-label]="'Ver detalhes de ' + getTitle(item)"
            >
              {{ isExpanded(getItemKey(item)) ? '▲' : '▼' }}
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

          <!-- Valores detalhados expandidos -->
          @if (isExpanded(getItemKey(item))) {
            <app-trend-row-values
              [janelas]="item.janelas"
              [metric]="metric()"
              [windowMetas]="windowMetas()"
            />
          }
        </article>
      }
    </div>
  `,
  styles: [`
    .trend-cards-container {
      display: flex;
      flex-direction: column;
      gap: var(--space-3, 12px);
    }

    .mobile-sort-bar {
      display: flex;
      align-items: center;
      gap: var(--space-2, 8px);
      padding: var(--space-2, 8px) var(--space-3, 12px);
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
      height: 32px;
      padding: 0 var(--space-2);
      font-size: 0.8125rem;
      font-weight: 600;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      color: var(--text-primary);
    }

    .mobile-dir-btn {
      margin-left: auto;
      height: 32px;
      padding: 0 var(--space-3);
      font-size: 0.8125rem;
      font-weight: 600;
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      background-color: var(--bg-surface);
      color: var(--brand-primary);
      cursor: pointer;
    }

    .trend-card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-sm);
      padding: var(--space-4, 16px);
      display: flex;
      flex-direction: column;
      gap: var(--space-3, 12px);
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
    }

    .card-sku {
      font-family: var(--font-family-mono);
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--text-muted);
    }

    .card-title {
      font-size: 0.9375rem;
      font-weight: 600;
      color: var(--text-primary);
      margin: 0;
    }

    .card-subtitle {
      font-size: 0.8125rem;
      color: var(--text-secondary);
    }

    .card-expand-btn {
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--bg-subtle);
      border: none;
      border-radius: var(--radius-xs);
      color: var(--text-secondary);
      font-size: 0.875rem;
      cursor: pointer;
    }

    .card-windows-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: var(--space-2, 8px);
    }

    .card-window-box {
      padding: var(--space-2, 8px);
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-xs);
      display: flex;
      flex-direction: column;
      gap: 4px;

      &.is-sorted-box {
        background-color: var(--brand-primary-subtle);
        border-color: var(--brand-primary);
      }
    }

    .box-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 0.6875rem;
    }

    .box-window-title {
      font-weight: 700;
      text-transform: uppercase;
      color: var(--text-primary);
    }

    .box-span-sub {
      font-family: var(--font-family-mono);
      color: var(--text-muted);
    }
  `],
})
export class TrendCardListComponent {
  readonly items = input.required<(TrendProductRow | TrendSupplierRow | TrendDetailRow)[]>();
  readonly metric = input.required<TrendMetric>();
  readonly sortWindow = input.required<TrendSortWindow>();
  readonly sortDir = input.required<TrendSortDir>();
  readonly windowMetas = input<TrendWindowMeta[] | null>(null);
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly expandedKeys = input<Set<string | number>>(new Set());

  readonly sortChange = output<{ window: TrendSortWindow; dir: TrendSortDir }>();
  readonly toggleRow = output<string | number>();

  getItemKey(item: any): string | number {
    return item.fornecedorChave ?? item.codigo;
  }

  getSku(item: any): string {
    return item.codigo ? `#${item.codigo}` : `${item.qtdProdutos ?? 0} produtos`;
  }

  getTitle(item: any): string {
    return item.descricao ?? item.fornecedor;
  }

  getSubtitle(item: any): string | null {
    return item.codigo ? item.fornecedor : null;
  }

  isExpanded(key: string | number): boolean {
    return this.expandedKeys().has(key);
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
