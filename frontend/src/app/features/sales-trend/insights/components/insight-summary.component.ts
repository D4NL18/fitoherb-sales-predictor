/**
 * Resumo do painel (Design Plan §6.3 item 1) com o selo de diagnóstico de mercado (§6.5).
 * Número herói com sinal e glifo (nunca só cor); atalho para o bloco de IA.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { MarketDiagnosis } from '../models/trend-insights.model';
import { MARKET_SEALS } from '../utils/insight-copy';
import { SummaryView } from '../utils/insight-view';

@Component({
  selector: 'app-insight-summary',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="sm-wrap">
      <div class="sm-hero-row">
        <div class="sm-hero" [class]="'tone-' + view().heroTone">
          <span class="sm-hero-num">
            @if (view().heroGlyph) {
              <span aria-hidden="true">{{ view().heroGlyph }}</span>
            }
            {{ view().heroText }}
          </span>
          <span class="sm-span">{{ view().spanText }}</span>
        </div>
        @if (view().fromToText) {
          <div class="sm-fromto">
            <span class="mono">{{ view().fromToText }}</span>
            <span class="mono">{{ view().deltaText }}</span>
            @if (view().baseParcialNote) {
              <span class="sm-note">{{ view().baseParcialNote }}</span>
            }
          </div>
        }
      </div>

      <div class="sm-market">
        <span class="sm-seal" [class]="sealClass()" data-testid="market-seal">{{ seal().label }}</span>
        <p class="sm-sentence">{{ view().sentence }}</p>
      </div>

      <p class="sm-ai-line">
        {{ aiStatus() }} ·
        <button type="button" class="sm-link" (click)="goToAi.emit()">Ir para a análise ↓</button>
      </p>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .sm-wrap { padding: var(--space-4); background-color: var(--bg-subtle); border-radius: var(--radius-xs); display: flex; flex-direction: column; gap: var(--space-3); }
    .sm-hero-row { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-3); }
    .sm-hero { display: flex; flex-direction: column; }
    .sm-hero-num { font-family: var(--font-family-headline); font-size: 2rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
    .tone-queda .sm-hero-num { color: var(--feedback-critical-bg); }
    .tone-alta .sm-hero-num { color: var(--feedback-positive-bg); }
    .sm-span { font-size: 0.8rem; color: var(--text-secondary); }
    .sm-fromto { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; font-size: 0.85rem; }
    .mono { font-family: var(--font-family-mono); font-variant-numeric: tabular-nums; }
    .sm-note { font-size: 0.75rem; color: var(--text-secondary); max-width: 260px; text-align: right; }
    .sm-market { display: flex; flex-direction: column; gap: var(--space-2); align-items: flex-start; }
    .sm-seal { align-self: flex-start; }
    .sm-seal.is-outlined { display: inline-flex; padding: 3px 9px; border: 1px solid var(--border-default); border-radius: var(--radius-xs); color: var(--text-secondary); font-size: 0.75rem; font-weight: 600; }
    .sm-sentence { margin: 0; font-size: 0.875rem; line-height: 1.45; overflow-wrap: anywhere; }
    .sm-ai-line { margin: 0; font-size: 0.8125rem; color: var(--text-secondary); }
    .sm-link { padding: 0; background: none; border: 0; color: var(--brand-primary); text-decoration: underline; cursor: pointer; font-size: inherit; min-height: 24px; }
    .sm-link:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
  `],
})
export class InsightSummaryComponent {
  readonly view = input.required<SummaryView>();
  readonly diagnosis = input.required<MarketDiagnosis>();
  readonly aiStatus = input.required<string>();
  readonly goToAi = output<void>();

  protected readonly seal = computed(() => MARKET_SEALS[this.diagnosis()]);
  protected readonly sealClass = computed(() => {
    const s = this.seal();
    return s.outlined ? 'is-outlined' : `tag ${s.tagClass}`;
  });
}
