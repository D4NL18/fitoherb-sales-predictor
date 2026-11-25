/**
 * Fonte citada pela IA (Design Plan §7.1): link externo com `rel="noopener noreferrer"`, domínio visível e data.
 * O título vem da citação (texto puro, nunca innerHTML); URLs fora de http(s) não viram link.
 */
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { SourceRef } from '../models/trend-insights.model';
import { formatIsoDateTime, safeHref, sourceDomain } from '../utils/insight-view';

@Component({
  selector: 'app-source-link',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (href(); as link) {
      <a class="source-title" [href]="link" target="_blank" rel="noopener noreferrer">{{ source().titulo }}<span class="sr-only"> (abre em nova aba)</span></a>
      <span class="source-domain">{{ domain() }}</span>
    } @else {
      <span class="source-title no-link">{{ source().titulo }}</span>
      <span class="source-domain">{{ domain() }}</span>
    }
    <span class="source-date">· {{ dateText() }}</span>
    @if (href()) {
      <span class="source-out" aria-hidden="true">↗</span>
    }
  `,
  styles: [`
    :host { display: inline; font-size: 0.8125rem; overflow-wrap: anywhere; }
    .source-title { color: var(--brand-primary); text-decoration: underline; text-underline-offset: 2px; }
    .source-title.no-link { color: var(--text-primary); text-decoration: none; }
    @media (hover: hover) { .source-title:hover { text-decoration-thickness: 2px; } }
    .source-title:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .source-domain { font-family: var(--font-family-mono); font-size: 0.75rem; color: var(--text-secondary); margin-left: var(--space-1); }
    .source-date { font-size: 0.75rem; color: var(--text-secondary); margin-left: var(--space-1); }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
  `],
})
export class SourceLinkComponent {
  readonly source = input.required<SourceRef>();

  protected readonly href = computed(() => safeHref(this.source().url));
  protected readonly domain = computed(() => sourceDomain(this.source().url, this.source().dominio));
  protected readonly dateText = computed(() => {
    const d = this.source().dataPublicacao;
    if (!d) return 'sem data de publicação';
    const [y, m, day] = d.split('-');
    return y && m && day ? `${day}/${m}/${y}` : formatIsoDateTime(d).slice(0, 10) || 'sem data de publicação';
  });
}
