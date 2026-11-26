/**
 * "Esta alta está tirando vendas de…" (Design Plan §6.9). Dado do motor, disponível sem IA; só altas e `NOVO`.
 */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MECHANISM_VISUAL_META } from '../../../analytics/utils/cannibalization-mechanism';
import { ImpactBlock } from '../models/trend-insights.model';
import { formatClientCount, formatSigned } from '../utils/insight-view';
import { formatCurrency } from '../../utils/pt-br-format';
import { CONFIDENCE_LABELS } from '../utils/insight-copy';

@Component({
  selector: 'app-impacted-products',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section aria-labelledby="impact-title">
      <h3 id="impact-title" class="ip-title">{{ title() }}</h3>
      @if (impact().itens.length === 0) {
        <p class="ip-empty">Nenhum produto semelhante perdeu clientes para este no período.</p>
      } @else {
        <div class="ip-totals">
          <div><span class="ip-label">Do mesmo fornecedor (troca interna)</span> <span class="mono">{{ money(impact().totalInterno) }}</span></div>
          <div><span class="ip-label">De concorrentes</span> <span class="mono">{{ money(impact().totalConcorrentes) }}</span></div>
        </div>
        @if (marginAlert()) {
          <p class="ip-alert">
            <span class="tag tag-warning"><span aria-hidden="true">▲</span> Atenção à margem</span>
            Parte da alta vem de outro item do mesmo fornecedor com margem maior: o portfólio troca venda e perde margem.
          </p>
        }
        <ul class="ip-list">
          @for (item of impact().itens; track item.sku) {
            <li class="ip-item">
              <span class="ip-name">{{ item.sku }} · {{ item.descricao }}@if (item.fornecedor) { · {{ item.fornecedor }}}</span>
              <span class="ip-chip">{{ item.sameSupplier ? 'Mesmo fornecedor' : 'Outro fornecedor' }}</span>
              <span class="mono">{{ item.receitaMigrada !== null ? signed(-item.receitaMigrada) : '—' }}</span>
              <span class="ip-meta">{{ clients(item.clientesMigrados) }}</span>
              <span class="ip-meta">{{ conf(item.confianca) }}</span>
              @if (item.mecanismo; as m) {
                <span class="tag" [class]="mech(m).tagClass"><span aria-hidden="true">{{ mech(m).symbol }}</span> {{ mech(m).label }}</span>
              }
            </li>
          }
        </ul>
      }
    </section>
  `,
  styles: [`
    :host { display: block; }
    .ip-title { margin: 0 0 var(--space-3); font-family: var(--font-family-headline); font-size: 1rem; font-weight: 700; }
    .ip-empty { margin: 0; font-size: 0.875rem; color: var(--text-secondary); }
    .ip-totals { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-5); font-size: 0.8125rem; margin-bottom: var(--space-3); }
    .ip-label { color: var(--text-secondary); margin-right: var(--space-2); }
    .mono { font-family: var(--font-family-mono); font-variant-numeric: tabular-nums; font-weight: 600; }
    .ip-alert { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border-left: 3px solid var(--feedback-warning-bg); background-color: var(--bg-canvas); font-size: 0.8125rem; display: flex; gap: var(--space-2); align-items: flex-start; flex-wrap: wrap; }
    .ip-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
    .ip-item { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-1) var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-subtle); font-size: 0.8125rem; }
    .ip-name { flex: 1 1 100%; font-weight: 600; overflow-wrap: anywhere; }
    .ip-chip { border: 1px solid var(--border-default); border-radius: var(--radius-xs); padding: 0 var(--space-1); color: var(--text-secondary); font-size: 0.75rem; }
    .ip-meta { color: var(--text-secondary); }
  `],
})
export class ImpactedProductsComponent {
  readonly impact = input.required<ImpactBlock>();
  readonly isNew = input<boolean>(false);

  protected readonly title = computed(() => {
    const n = this.impact().itens.length;
    if (n === 0) return this.isNew() ? 'Este lançamento não está tirando vendas de outros produtos' : 'Esta alta não está tirando vendas de outros produtos';
    const noun = n === 1 ? 'produto' : 'produtos';
    return this.isNew() ? `Este lançamento está tirando vendas de ${n} ${noun}` : `Esta alta está tirando vendas de ${n} ${noun}`;
  });

  protected readonly marginAlert = computed(() =>
    this.impact().itens.some((i) => i.tipoImpacto === 'CANIBALIZACAO_INTERNA' && i.mecanismo === 'PRECO_MENOR_DESTROI_MARGEM'),
  );

  protected readonly clients = formatClientCount;
  protected readonly mech = (m: keyof typeof MECHANISM_VISUAL_META): (typeof MECHANISM_VISUAL_META)[keyof typeof MECHANISM_VISUAL_META] =>
    MECHANISM_VISUAL_META[m];
  protected money(v: number): string {
    return formatCurrency(v);
  }
  protected signed(v: number): string {
    return formatSigned(v, 'revenue');
  }
  protected conf(c: keyof typeof CONFIDENCE_LABELS): string {
    return CONFIDENCE_LABELS[c].text;
  }
}
