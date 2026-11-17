/**
 * Célula de variação percentual compartilhada entre a tabela ledger e a visão mobile em cartões (Design Plan §4.2, D-6).
 * Garante distinção por forma (▲/▼/▬/◆/⚠ + sinal + texto), tooltips acessíveis por teclado e contraste WCAG AA.
 */
import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  TrendCell,
  TrendDetailCell,
  TrendMetric,
  TrendParameters,
} from '../../models/sales-trend.model';
import { CellDisplayModel, getCellDisplayModel } from '../../utils/trend-view';
import { formatPointsChange, formatValueByMetric } from '../../utils/trend-format';

let nextTooltipUid = 0;

@Component({
  selector: 'app-trend-cell',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="trend-cell-container"
      [class.card-variant]="variant() === 'card'"
      [class.sorted-column]="isSortedColumn()"
    >
      <span class="sr-only">{{ model().ariaLabel }}</span>

      <!-- Variação Percentual Principal -->
      <div class="variation-row" [ngClass]="variationClass()" [attr.aria-hidden]="model().isNumeric || model().isNew">
        @if (model().isNumeric) {
          @if (model().direction === 'up') {
            <span class="direction-arrow" aria-hidden="true">▲</span>
          } @else if (model().direction === 'down') {
            <span class="direction-arrow" aria-hidden="true">▼</span>
          } @else if (model().direction === 'flat') {
            <span class="direction-arrow" aria-hidden="true">▬</span>
          }
          <span class="variation-value">{{ model().percentText }}</span>
        } @else if (model().isNew) {
          <span class="status-pill pill-new">
            <span aria-hidden="true">◆</span>
            <span>Novo</span>
          </span>
        } @else {
          <span
            class="dash-tooltip-anchor"
            tabindex="0"
            role="note"
            [attr.aria-label]="dashTooltipText()"
            [attr.aria-describedby]="dashTooltipOpen() ? dashTooltipId : null"
            (mouseenter)="dashTooltipOpen.set(true)"
            (mouseleave)="dashTooltipOpen.set(false)"
            (focus)="dashTooltipOpen.set(true)"
            (blur)="dashTooltipOpen.set(false)"
            (keydown.escape)="dashTooltipOpen.set(false)"
          >
            <span class="status-dash" aria-hidden="true">—</span>
            @if (dashTooltipOpen()) {
              <span class="cell-tooltip" [id]="dashTooltipId" role="tooltip">
                {{ dashTooltipText() }}
              </span>
            }
          </span>
        }
      </div>

      <!-- Contribuição (para produtos em detalhe de fornecedor) -->
      @if (detailCell()?.contribuicaoPp !== undefined && detailCell()?.contribuicaoPp !== null) {
        <div class="contribution-row">
          <span
            class="contrib-pp"
            [class.contrib-up]="(detailCell()!.contribuicaoPp ?? 0) > 0"
            [class.contrib-down]="(detailCell()!.contribuicaoPp ?? 0) < 0"
          >
            {{ formatPointsChange(detailCell()!.contribuicaoPp) }}
          </span>
          @if (detailCell()?.contribuicaoValor !== undefined && detailCell()?.contribuicaoValor !== null) {
            <span class="contrib-val">
              ({{ formatValueByMetric(detailCell()!.contribuicaoValor, metric()) }}{{ detailCell()!.baseParcial && detailCell()!.atualPorDia !== null ? '/dia' : '' }})
            </span>
          }
        </div>
      }

      <!-- Badges / Selos explicativos com tooltip acessível por teclado/mouse/toque -->
      @if (model().badges.length > 0) {
        <div class="badges-row">
          @for (b of model().badges; track b.text; let idx = $index) {
            <span class="badge-tooltip-anchor">
              <button
                type="button"
                class="cell-badge"
                [class.badge-warning]="b.variant === 'warning'"
                [class.badge-critical]="b.variant === 'critical'"
                [class.badge-info]="b.variant === 'info'"
                [attr.aria-expanded]="openBadgeKey() === b.text"
                [attr.aria-describedby]="openBadgeKey() === b.text ? badgeTooltipId(idx) : null"
                (click)="toggleBadge(b.text)"
                (mouseenter)="openBadgeKey.set(b.text)"
                (mouseleave)="openBadgeKey.set(null)"
                (focus)="openBadgeKey.set(b.text)"
                (blur)="openBadgeKey.set(null)"
                (keydown.escape)="openBadgeKey.set(null)"
              >
                @if (b.variant === 'critical' || b.variant === 'warning') {
                  <span aria-hidden="true">⚠ </span>
                }
                <span>{{ b.text }}</span>
              </button>
              @if (openBadgeKey() === b.text) {
                <span class="cell-tooltip" [id]="badgeTooltipId(idx)" role="tooltip">
                  {{ b.tooltip }}
                </span>
              }
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
      position: relative;
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
      gap: 4px;
      font-size: 0.9375rem;
      font-weight: 600;
    }

    .variation-row.is-up {
      color: var(--feedback-positive-bg);
    }

    .variation-row.is-down {
      color: var(--feedback-critical-bg);
    }

    .variation-row.is-flat {
      color: var(--text-secondary);
    }

    .direction-arrow {
      font-size: 0.625rem;
      line-height: 1;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      font-size: 0.6875rem;
      padding: 1px 6px;
      border-radius: var(--radius-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    .pill-new {
      background-color: var(--feedback-info-bg);
      color: var(--text-on-brand);
    }

    .dash-tooltip-anchor,
    .badge-tooltip-anchor {
      position: relative;
      display: inline-flex;
      align-items: center;
    }

    .dash-tooltip-anchor {
      border-radius: var(--radius-xs);
      padding: 0 2px;
      cursor: help;

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }
    }

    .status-dash {
      color: var(--text-secondary);
      font-weight: 700;
    }

    .contribution-row {
      font-size: 0.75rem;
      color: var(--text-secondary);
      display: inline-flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 4px;
    }

    .card-variant .contribution-row {
      justify-content: flex-start;
    }

    .contrib-pp {
      font-weight: 700;

      &.contrib-up {
        color: var(--feedback-positive-bg);
      }

      &.contrib-down {
        color: var(--feedback-critical-bg);
      }
    }

    .contrib-val {
      color: var(--text-secondary);
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
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-family: var(--font-family-body);
      font-size: 0.6875rem;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: var(--radius-xs);
      cursor: help;

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }
    }

    .badge-info {
      background-color: var(--brand-primary-subtle);
      color: var(--brand-primary);
      border: 1px solid var(--brand-primary);
    }

    .badge-warning {
      background-color: var(--feedback-warning-subtle);
      color: var(--feedback-warning-bg);
      border: 1px solid var(--feedback-warning-border);
    }

    .badge-critical {
      background-color: var(--feedback-critical-subtle);
      color: var(--feedback-critical-bg);
      border: 1px solid var(--feedback-critical-border);
    }

    .cell-tooltip {
      position: absolute;
      bottom: calc(100% + 6px);
      right: 0;
      z-index: 20;
      width: max-content;
      max-width: 240px;
      padding: var(--space-2) var(--space-3);
      background-color: var(--text-primary);
      color: var(--text-on-dark);
      border-radius: var(--radius-xs);
      box-shadow: var(--shadow-sm);
      font-family: var(--font-family-body);
      font-size: 0.75rem;
      font-weight: 500;
      line-height: 1.35;
      text-align: left;
      white-space: normal;
      pointer-events: none;
    }

    .card-variant .cell-tooltip {
      right: auto;
      left: 0;
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
export class TrendCellComponent {
  readonly cell = input.required<TrendCell | TrendDetailCell>();
  readonly metric = input.required<TrendMetric>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly variant = input<'table' | 'card'>('table');
  readonly isSortedColumn = input<boolean>(false);

  private readonly uid = ++nextTooltipUid;
  readonly dashTooltipId = `trend-cell-dash-tip-${this.uid}`;
  readonly dashTooltipOpen = signal(false);
  readonly openBadgeKey = signal<string | null>(null);

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

  readonly dashTooltipText = computed(() =>
    this.model().isNoBase
      ? 'Histórico insuficiente no período anterior (cobertura inferior a 50% dos dias).'
      : 'Sem movimentação de vendas no período atual nem no anterior.'
  );

  badgeTooltipId(idx: number): string {
    return `trend-cell-badge-tip-${this.uid}-${idx}`;
  }

  toggleBadge(key: string): void {
    this.openBadgeKey.update((curr) => (curr === key ? null : key));
  }

  formatPointsChange = formatPointsChange;
  formatValueByMetric = formatValueByMetric;
}
