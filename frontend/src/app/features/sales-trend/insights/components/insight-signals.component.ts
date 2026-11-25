/**
 * Sinais sem valor (Design Plan §6.7). No modo qualitativo, substitui a tabela da cascata.
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { SignalView } from '../utils/insight-signals';

@Component({
  selector: 'app-insight-signals',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section aria-labelledby="signals-title">
      <h4 id="signals-title" class="sg-title">{{ title() }}</h4>
      @if (signals().length === 0) {
        <p class="sg-empty">Nenhum outro sinal encontrado (estoque, promoção, região).</p>
      } @else {
        <ul class="sg-list">
          @for (s of signals(); track s.key) {
            <li class="sg-item">
              <span class="sg-glyph" aria-hidden="true">{{ s.glyph }}</span>
              <span class="sr-only">{{ s.stateText }}: </span>
              <span>{{ s.text }}</span>
            </li>
          }
        </ul>
      }
    </section>
  `,
  styles: [`
    :host { display: block; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .sg-title { margin: 0 0 var(--space-2); font-size: 0.85rem; font-weight: 700; font-family: var(--font-family-headline); }
    .sg-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
    .sg-item { display: flex; gap: var(--space-2); font-size: 0.85rem; line-height: 1.4; overflow-wrap: anywhere; }
    .sg-glyph { color: var(--text-secondary); flex-shrink: 0; }
    .sg-empty { margin: 0; font-size: 0.85rem; color: var(--text-secondary); }
  `],
})
export class InsightSignalsComponent {
  readonly signals = input.required<SignalView[]>();
  readonly title = input<string>('Outros sinais no período');
}
