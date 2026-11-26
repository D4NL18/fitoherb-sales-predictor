/**
 * Cascata de atribuição como tabela visível (Design Plan §6.6, D-6).
 * A barra é só reforço visual (`aria-hidden`); a tabela é a versão acessível. Alta = listrada, queda = lisa,
 * resíduo = tracejado. Parcelas "Sem efeito"/"Não avaliado" nunca viram zero e não têm barra.
 */
import { ChangeDetectionStrategy, Component, ElementRef, inject, input, output, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MECHANISM_VISUAL_META } from '../../../analytics/utils/cannibalization-mechanism';
import { WaterfallView } from '../utils/insight-view';

let nextWaterfallId = 0;

@Component({
  selector: 'app-attribution-waterfall',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section [attr.aria-labelledby]="uid + '-title'">
      <h3 class="wf-title" [id]="uid + '-title'">{{ view().title }}</h3>
      <p class="wf-sub">{{ view().subtitle }}</p>
      <svg width="0" height="0" aria-hidden="true" focusable="false" class="defs-svg">
        <defs>
          <pattern [id]="uid + '-stripe'" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="4" height="4" class="stripe-bg"></rect>
            <line x1="0" y1="0" x2="0" y2="4" class="stripe-line"></line>
          </pattern>
        </defs>
      </svg>
      <table class="wf-table">
        <caption class="sr-only">{{ view().caption }}</caption>
        <thead>
          <tr>
            <th scope="col" class="col-cause">Causa</th>
            <th scope="col" class="col-bar"><span class="sr-only">Barra</span></th>
            <th scope="col" class="col-value">Valor</th>
            <th scope="col" class="col-pp">p.p.</th>
            <th scope="col" class="col-conf">Confiança</th>
          </tr>
        </thead>
        <tbody>
          @for (row of view().rows; track row.key) {
            <tr class="wf-row" [class.is-total]="row.status === 'TOTAL'" [attr.data-parcel]="row.key">
              <th scope="row" class="col-cause" tabindex="-1">
                <span class="cause-label">{{ row.label }}</span>
                @if (row.note) {
                  <span class="cause-note">{{ row.note }}</span>
                }
              </th>
              <td class="col-bar" aria-hidden="true">
                @if (row.bar; as bar) {
                  <svg viewBox="0 0 100 14" preserveAspectRatio="none" class="bar-svg" focusable="false">
                    <line [attr.x1]="view().zeroX" [attr.x2]="view().zeroX" y1="0" y2="14" class="zero-line"></line>
                    <rect
                      [attr.x]="bar.x"
                      [attr.width]="bar.width"
                      y="2"
                      height="10"
                      [attr.class]="'bar-' + bar.kind"
                      [attr.fill]="bar.kind === 'alta' ? 'url(#' + uid + '-stripe)' : null"
                    ></rect>
                  </svg>
                } @else {
                  <span class="no-bar">—</span>
                }
              </td>
              <td class="col-value">
                <span [class.is-muted]="row.status === 'SEM_EFEITO' || row.status === 'NAO_AVALIADO'">
                  @if (row.glyph) {
                    <span aria-hidden="true" class="glyph">{{ row.glyph }}</span>
                  }
                  {{ row.valueText }}@if (row.cut) {<span aria-hidden="true">*</span>}
                </span>
                @if (row.secondaryValueText) {
                  <span class="secondary">{{ row.secondaryValueText }}</span>
                }
                @if (row.expandable) {
                  <button
                    type="button"
                    class="disclosure"
                    [class.is-open]="isOpen(row.key)"
                    [attr.aria-expanded]="isOpen(row.key)"
                    [attr.aria-label]="'Ver os ' + row.items.length + ' produtos relacionados a ' + row.label"
                    (click)="toggle(row.key)"
                  ><span aria-hidden="true">›</span></button>
                }
              </td>
              <td class="col-pp">{{ row.ppText }}</td>
              <td class="col-conf">
                @if (row.confidenceText) {
                  <span>{{ row.confidenceText }}</span>
                  <span class="marks" aria-hidden="true">{{ row.confidenceMarks }}</span>
                }
              </td>
            </tr>
            @if (row.expandable && isOpen(row.key)) {
              <tr class="wf-items-row">
                <td colspan="5">
                  <p class="items-title">{{ row.itemsTitle }}</p>
                  <ul class="items-list">
                    @for (item of row.items; track item.sku) {
                      <li class="item">
                        <span class="item-name">{{ item.label }}@if (item.supplier) { · {{ item.supplier }}}</span>
                        <span class="item-meta">semelhança {{ item.similarityText }}</span>
                        <span class="item-meta mono">{{ item.valueText }}</span>
                        <span class="item-meta">{{ item.clientsText }}</span>
                        @if (item.mechanism; as m) {
                          <span class="tag" [class]="mechanism(m).tagClass"><span aria-hidden="true">{{ mechanism(m).symbol }}</span> {{ mechanism(m).label }}</span>
                        }
                      </li>
                    }
                  </ul>
                  <a
                    class="inline-link"
                    routerLink="/analytics/canibalizacao"
                    [queryParams]="{ periodo: 90, busca: row.items[0].sku, abrir: row.items[0].sku }"
                    (click)="navigate.emit()"
                  >Ver equilíbrio de preço no relatório de Canibalização →</a>
                </td>
              </tr>
            }
          }
        </tbody>
      </table>
      <details class="conf-help">
        <summary>Como ler a confiança</summary>
        <p>Alta: medida com muitos clientes ou histórico firme. Média: sinal claro, base menor. Baixa: poucos casos; use como pista.</p>
      </details>
    </section>
  `,
  styles: [`
    :host { display: block; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .wf-title { margin: 0 0 var(--space-1); font-family: var(--font-family-headline); font-size: 1rem; font-weight: 700; }
    .defs-svg { position: absolute; }
    .wf-sub { margin: 0 0 var(--space-3); font-size: 0.75rem; color: var(--text-secondary); }
    .wf-table { width: 100%; border-collapse: collapse; font-size: 0.8125rem; }
    thead th { text-align: left; padding: var(--space-2); background-color: var(--bg-table-header); color: var(--text-secondary); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .col-value, .col-pp { text-align: right; }
    .wf-row > * { padding: var(--space-2); vertical-align: top; border-bottom: 1px solid var(--border-subtle); }
    .wf-row th { text-align: left; font-weight: 600; width: 34%; }
    .wf-row th:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .cause-label { display: block; color: var(--text-primary); }
    .cause-note { display: block; font-weight: 400; font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px; }
    .col-bar { width: auto; min-width: 80px; }
    .bar-svg { width: 100%; height: 14px; display: block; }
    .zero-line { stroke: var(--border-strong); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .bar-queda { fill: var(--feedback-critical-bg); }
    .bar-alta { stroke: var(--feedback-positive-bg); }
    .stripe-bg { fill: var(--feedback-positive-bg); }
    .stripe-line { stroke: var(--bg-surface); stroke-width: 1.5; }
    .bar-residuo { fill: var(--bg-muted); stroke: var(--border-strong); stroke-dasharray: 2 1; vector-effect: non-scaling-stroke; }
    .bar-total { fill: var(--text-secondary); stroke: var(--text-primary); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
    .no-bar { color: var(--text-muted); }
    .col-value, .col-pp, .mono { font-family: var(--font-family-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
    .col-value { width: 124px; }
    .col-pp { width: 72px; }
    .col-conf { width: 88px; font-size: 0.75rem; }
    .marks { display: block; letter-spacing: 2px; color: var(--text-secondary); }
    .secondary { display: block; font-size: 0.75rem; color: var(--text-secondary); }
    .is-muted { color: var(--text-secondary); }
    .is-total > * { font-weight: 700; border-top: 2px solid var(--border-strong); }
    .disclosure { width: 40px; height: 40px; background: none; border: 0; border-radius: var(--radius-xs); color: var(--text-secondary); font-size: 1.25rem; cursor: pointer; transition: transform var(--transition-fast), background-color var(--transition-fast); }
    .disclosure.is-open { transform: rotate(90deg); color: var(--brand-primary); }
    @media (hover: hover) { .disclosure:hover { background-color: var(--bg-subtle); } }
    .disclosure:focus-visible, .inline-link:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .wf-items-row td { padding: var(--space-2) var(--space-3) var(--space-3); background-color: var(--bg-canvas); }
    .items-title { margin: 0 0 var(--space-2); font-weight: 700; font-size: 0.8rem; }
    .items-list { list-style: none; margin: 0 0 var(--space-2); padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
    .item { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--space-2) var(--space-3); font-size: 0.8rem; }
    .item-name { font-weight: 600; overflow-wrap: anywhere; flex: 1 1 100%; }
    .item-meta { color: var(--text-secondary); }
    .inline-link { color: var(--brand-primary); font-size: 0.8125rem; text-decoration: underline; text-underline-offset: 2px; }
    .conf-help { margin-top: var(--space-2); font-size: 0.75rem; color: var(--text-secondary); }
    @media (max-width: 767.98px) {
      thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); }
      .wf-row { display: grid; grid-template-columns: 1fr auto; border-bottom: 1px solid var(--border-subtle); }
      .wf-row > * { border-bottom: 0; width: auto; }
      .wf-row .col-bar { grid-column: 1 / -1; grid-row: 2; }
      .wf-row .col-pp, .wf-row .col-conf { grid-row: 3; text-align: left; }
      .wf-items-row, .wf-items-row td { display: block; }
    }
  `],
})
export class AttributionWaterfallComponent {
  readonly view = input.required<WaterfallView>();
  readonly navigate = output<void>();

  protected readonly uid = `wf-${nextWaterfallId++}`;
  private readonly open = signal<ReadonlySet<string>>(new Set());
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  protected isOpen(key: string): boolean {
    return this.open().has(key);
  }

  protected toggle(key: string): void {
    const next = new Set(this.open());
    if (next.has(key)) next.delete(key);
    else next.add(key);
    this.open.set(next);
  }

  protected mechanism(m: keyof typeof MECHANISM_VISUAL_META): (typeof MECHANISM_VISUAL_META)[typeof m] {
    return MECHANISM_VISUAL_META[m];
  }

  /** Foca o cabeçalho de linha da parcela (atalho "ver na cascata" do bloco de IA). */
  focusRow(key: string): void {
    this.host.nativeElement.querySelector<HTMLElement>(`tr[data-parcel="${key}"] th`)?.focus();
  }

}
