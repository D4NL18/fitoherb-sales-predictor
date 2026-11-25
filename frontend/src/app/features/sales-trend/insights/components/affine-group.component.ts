/**
 * Grupo afim (Design Plan §6.8): variação de cada produto semelhante com o `TrendCellComponent` da Tendência,
 * resumo por fornecedor, ajuda da semelhança e links para a Canibalização (período fixo de 90 dias, nota honesta).
 */
import { ChangeDetectionStrategy, Component, computed, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { TrendMetric, TrendParameters } from '../../models/sales-trend.model';
import { TrendCellComponent } from '../../components/trend-cell/trend-cell.component';
import { TrendEmptyStateComponent } from '../../components/trend-empty-state/trend-empty-state.component';
import { AffineGroupView } from '../utils/insight-view';

export const AFFINE_INITIAL_ROWS = 8;

@Component({
  selector: 'app-affine-group',
  standalone: true,
  imports: [RouterLink, TrendCellComponent, TrendEmptyStateComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @switch (status()) {
      @case ('NAO_AVALIADO') {
        <section aria-labelledby="affine-title">
          <h3 id="affine-title" class="ag-title">Produtos semelhantes</h3>
          <p class="ag-text">Lista de produtos semelhantes em atualização. Tente de novo em alguns minutos.</p>
          <button type="button" class="ag-btn" (click)="refresh.emit()">Atualizar painel</button>
        </section>
      }
      @case ('SEM_GRUPO_AFIM') {
        <section aria-labelledby="affine-title">
          <h3 id="affine-title" class="ag-title">Produtos semelhantes</h3>
          <app-trend-empty-state
            title="Sem produtos semelhantes para comparar"
            [description]="emptyDescription()"
          />
        </section>
      }
      @default {
        <section aria-labelledby="affine-title">
          <h3 id="affine-title" class="ag-title">{{ view().title }}</h3>
          <div class="ag-summary">
            <div class="ag-sum-cell">
              <span class="ag-sum-label">Mesmo fornecedor ({{ view().sameSupplierCount }})</span>
              <span class="ag-sum-value">{{ view().sameSupplierGlyph }} {{ view().sameSupplierVariation }}</span>
            </div>
            <div class="ag-sum-cell">
              <span class="ag-sum-label">Outro fornecedor ({{ view().otherSupplierCount }})</span>
              <span class="ag-sum-value">{{ view().otherSupplierGlyph }} {{ view().otherSupplierVariation }}</span>
            </div>
          </div>

          <ul class="ag-list">
            @for (row of visibleRows(); track row.sku) {
              <li class="ag-row">
                <div class="ag-name">
                  <span class="ag-label">{{ row.label }}</span>
                  <span class="ag-supplier">
                    {{ row.supplier ?? 'Fornecedor não informado' }}
                    <span class="ag-chip" [class.is-same]="row.sameSupplier">{{ row.sameSupplier ? 'Mesmo fornecedor' : 'Outro fornecedor' }}</span>
                  </span>
                </div>
                <div class="ag-sim"><span class="ag-sim-label">Semelhança</span> <span class="mono">{{ row.similarityText }}</span></div>
                <div class="ag-cell">
                  <app-trend-cell variant="card" [cell]="row.cell" [metric]="metric()" [params]="params()" />
                </div>
                <div class="ag-gain">
                  <span class="ag-sim-label">Ganhou clientes deste?</span>
                  <span [class.is-muted]="!row.gained">{{ row.gainedText }}</span>
                  @if (row.gained) {
                    <a
                      class="ag-link"
                      routerLink="/analytics/canibalizacao"
                      [queryParams]="{ periodo: 90, busca: sku(), abrir: row.sku }"
                      (click)="navigate.emit()"
                    >Ver equilíbrio de preço</a>
                  }
                </div>
              </li>
            }
          </ul>

          @if (view().rows.length > initialRows) {
            <button
              type="button"
              class="ag-btn"
              [attr.aria-expanded]="showAll()"
              (click)="showAll.set(!showAll())"
            >{{ showAll() ? 'Mostrar menos' : 'Mostrar todos os ' + view().rows.length }}</button>
          }

          <details class="ag-help" #help>
            <summary>Como a semelhança é calculada</summary>
            <p>A semelhança compara nome, categoria e função do produto. Só entram produtos {{ minScoreText() }}.</p>
          </details>

          <a class="ag-link block" routerLink="/analytics/canibalizacao" [queryParams]="{ periodo: 90, busca: sku() }" (click)="navigate.emit()">
            Ver estes produtos no relatório de Canibalização →
          </a>
          <p class="ag-note">O relatório de Canibalização usa os últimos 90 dias; os números podem diferir desta janela.</p>
        </section>
      }
    }
  `,
  styles: [`
    :host { display: block; }
    .ag-title { margin: 0 0 var(--space-3); font-family: var(--font-family-headline); font-size: 1rem; font-weight: 700; }
    .ag-text { margin: 0 0 var(--space-2); font-size: 0.875rem; }
    .ag-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
    @media (max-width: 374.98px) { .ag-summary { grid-template-columns: 1fr; } }
    .ag-sum-cell { display: flex; flex-direction: column; gap: 2px; padding: var(--space-2) var(--space-3); border: 1px solid var(--border-subtle); border-radius: var(--radius-xs); }
    .ag-sum-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-secondary); }
    .ag-sum-value { font-family: var(--font-family-mono); font-weight: 700; font-variant-numeric: tabular-nums; }
    .ag-list { list-style: none; margin: 0; padding: 0; }
    .ag-row { display: grid; grid-template-columns: minmax(0, 2fr) auto minmax(0, 1.2fr) minmax(0, 1.4fr); gap: var(--space-3); align-items: start; padding: var(--space-3) 0; border-bottom: 1px solid var(--border-subtle); font-size: 0.8125rem; }
    @media (max-width: 767.98px) { .ag-row { grid-template-columns: 1fr 1fr; } .ag-name { grid-column: 1 / -1; } }
    .ag-name { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .ag-label { font-weight: 600; overflow-wrap: anywhere; }
    .ag-supplier { color: var(--text-secondary); font-size: 0.75rem; overflow-wrap: anywhere; }
    .ag-chip { display: inline-block; margin-left: var(--space-1); padding: 0 var(--space-1); border: 1px solid var(--border-default); border-radius: var(--radius-xs); color: var(--text-secondary); }
    .ag-chip.is-same { color: var(--brand-primary); border-color: var(--brand-primary); }
    .ag-sim-label { display: block; font-size: 0.7rem; color: var(--text-secondary); }
    .mono { font-family: var(--font-family-mono); font-variant-numeric: tabular-nums; }
    .ag-gain { display: flex; flex-direction: column; gap: 2px; }
    .is-muted { color: var(--text-secondary); }
    .ag-link { color: var(--brand-primary); text-decoration: underline; text-underline-offset: 2px; font-size: 0.8125rem; }
    .ag-link.block { display: inline-block; margin-top: var(--space-3); }
    .ag-link:focus-visible, .ag-btn:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .ag-btn { margin-top: var(--space-3); min-height: 40px; padding: 0 var(--space-3); background-color: var(--bg-surface); color: var(--brand-primary); border: 1px solid var(--border-default); border-radius: var(--radius-xs); font-weight: 600; cursor: pointer; }
    @media (hover: hover) { .ag-btn:hover { background-color: var(--bg-subtle); } }
    .ag-help { margin-top: var(--space-3); font-size: 0.75rem; color: var(--text-secondary); }
    .ag-note { margin: var(--space-1) 0 0; font-size: 0.75rem; color: var(--text-secondary); }
  `],
})
export class AffineGroupComponent {
  readonly view = input.required<AffineGroupView>();
  readonly status = input<'AVALIADO' | 'SEM_GRUPO_AFIM' | 'NAO_AVALIADO'>('AVALIADO');
  readonly metric = input.required<TrendMetric>();
  readonly params = input<TrendParameters | undefined>(undefined);
  readonly sku = input.required<number>();
  /** Limiar de semelhança (0..1) vindo de `meta.parametros.affineGroupMinScore`. */
  readonly minScore = input<number | null>(null);

  readonly refresh = output<void>();
  readonly navigate = output<void>();

  protected readonly initialRows = AFFINE_INITIAL_ROWS;
  protected readonly showAll = signal(false);

  protected readonly visibleRows = computed(() =>
    this.showAll() ? this.view().rows : this.view().rows.slice(0, AFFINE_INITIAL_ROWS),
  );

  protected readonly minScoreText = computed(() => {
    const m = this.minScore();
    return m === null ? 'com semelhança mínima definida pelo sistema' : `com ${Math.round(m * 100)}% ou mais`;
  });

  protected readonly emptyDescription = computed(() => {
    const m = this.minScore();
    const limiar = m === null ? 'o mínimo' : `${Math.round(m * 100)}%`;
    return `Nenhum produto ativo tem semelhança de ${limiar} ou mais com este. A comparação com o mercado não foi feita.`;
  });
}
