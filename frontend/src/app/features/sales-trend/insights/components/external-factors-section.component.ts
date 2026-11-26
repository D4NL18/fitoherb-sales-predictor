/**
 * Seção "Fatores externos" (Design Plan §7.4): 8 dimensões sempre visíveis, tratadas como hipóteses.
 * Texto sempre por interpolação (nunca innerHTML). Sem valores monetários, tokens ou orçamento.
 */
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { InlineNoticeComponent } from '../../components/inline-notice/inline-notice.component';
import { ExternalDimension } from '../models/trend-insights.model';
import { ExternalFactorsView, RadarExternoView } from '../utils/external-factors-view';
import { SourceLinkComponent } from './source-link.component';

@Component({
  selector: 'app-external-factors-section',
  standalone: true,
  imports: [InlineNoticeComponent, SourceLinkComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (view(); as v) {
      <section class="ext" data-testid="external-factors" aria-labelledby="ext-title">
        <h4 id="ext-title" class="ext-title">{{ v.title }}</h4>
        <p class="ext-intro">{{ v.intro }}</p>
        @if (v.ageText) {
          <p class="ext-age" data-testid="external-age">{{ v.ageText }}</p>
        }
        @if (v.staleNotice) {
          <div role="status" data-testid="external-stale">
            <app-inline-notice tone="info" [text]="v.staleNotice" [dismissible]="false" />
          </div>
        }
        @if (v.unavailable; as u) {
          <div class="ext-box" data-testid="external-unavailable">
            <p class="ext-strong">{{ u.title }}</p>
            <p class="ext-note">{{ u.text }}</p>
            <details class="ext-details">
              <summary>Ver as 8 dimensões</summary>
              <ul class="ext-list" aria-label="Fatores externos">
                @for (r of v.rows; track r.dimension) {
                  <li class="ext-row compact" [attr.aria-label]="r.ariaLabel">
                    <span class="ext-label">{{ r.label }}</span>
                    <span class="ext-muted">{{ r.statusText }}. {{ r.reasonText }}</span>
                  </li>
                }
              </ul>
            </details>
          </div>
        } @else {
          <div class="ext-box">
            <ul class="ext-list" aria-label="Fatores externos">
              @for (r of v.rows; track r.dimension) {
                <li class="ext-row" [class.compact]="r.compact" [attr.data-dimension]="r.dimension" [attr.aria-label]="r.ariaLabel">
                  <div class="ext-line">
                    <span class="ext-label">{{ r.label }}</span>
                    @if (!r.compact) {
                      <span class="ext-badge">hipótese</span>
                    }
                  </div>
                  @if (r.statusText) {
                    <p class="ext-muted">{{ r.statusText }}{{ r.reasonText ? '. ' + r.reasonText : '' }}</p>
                  }
                  @if (r.direction; as d) {
                    <p class="ext-dir" [class.down]="d.tone === 'down'" [class.up]="d.tone === 'up'">
                      <span aria-hidden="true">{{ d.glyph }}</span> {{ d.text }}
                    </p>
                  }
                  @if (r.confidenceText) {
                    <p class="ext-meta">{{ r.confidenceText }}</p>
                  }
                  @if (r.relevanceText) {
                    <p class="ext-meta">{{ r.relevanceText }}</p>
                  }
                  @if (r.notaRadar) {
                    <p class="ext-note">{{ r.notaRadar }}</p>
                  }
                  @if (r.nota) {
                    <p class="ext-note">{{ r.nota }}</p>
                  }
                  @for (s of r.sources; track $index) {
                    <p class="ext-source"><app-source-link [source]="s" /></p>
                  }
                  @if (r.temporalBadge) {
                    <span class="ext-temporal">{{ r.temporalBadge }}</span>
                  }
                  @if (r.promoted) {
                    <button type="button" class="ext-link" (click)="focusFactors.emit(r.dimension)">Também listado em Fatores com evidência ↑</button>
                  }
                </li>
              }
            </ul>
          </div>
        }
        <div class="sr-only" role="status" data-testid="external-live">Fatores externos atualizados</div>
      </section>
    }

    @if (radar(); as r) {
      <section class="ext" data-testid="radar-externo" aria-labelledby="radar-title">
        <h4 id="radar-title" class="ext-title">{{ r.title }}</h4>
        <p class="ext-intro">{{ r.subtitle }}</p>
        @if (r.staleNotice) {
          <div role="status" data-testid="radar-stale">
            <app-inline-notice tone="info" [text]="r.staleNotice" [dismissible]="false" />
          </div>
        }
        <div class="ext-box">
          <ul class="ext-list" aria-label="Radar externo">
            @for (row of r.rows; track row.dimension) {
              <li class="ext-row" [class.compact]="!!row.statusText">
                <div class="ext-line"><span class="ext-label">{{ row.label }}</span></div>
                @if (row.statusText) {
                  <p class="ext-muted">{{ row.statusText }}</p>
                }
                @if (row.movementText) {
                  <p class="ext-meta">{{ row.movementText }}{{ row.intensityText ? ' · ' + row.intensityText : '' }}</p>
                }
                @if (row.notaRadar) {
                  <p class="ext-note">{{ row.notaRadar }}</p>
                }
                @for (s of row.sources; track $index) {
                  <p class="ext-source"><app-source-link [source]="s" /></p>
                }
              </li>
            }
          </ul>
        </div>
      </section>
    }
  `,
  styles: [`
    :host { display: block; }
    .ext { display: flex; flex-direction: column; gap: var(--space-2); }
    .ext-title { margin: var(--space-2) 0 0; font-size: 0.85rem; font-weight: 700; color: var(--text-primary); font-family: var(--font-family-headline); }
    .ext-intro { margin: 0; font-size: 0.75rem; color: var(--text-muted); }
    .ext-age { margin: 0; font-size: 0.75rem; color: var(--text-secondary); }
    .ext-box { border: 1px dashed var(--border-strong); background-color: var(--bg-canvas); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-2); }
    .ext-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: var(--space-3); }
    .ext-row { display: flex; flex-direction: column; gap: var(--space-1); padding-bottom: var(--space-2); border-bottom: 1px solid var(--border-subtle); }
    .ext-row:last-child { border-bottom: 0; padding-bottom: 0; }
    .ext-line { display: flex; align-items: baseline; gap: var(--space-2); flex-wrap: wrap; }
    .ext-label { font-size: 0.875rem; font-weight: 600; color: var(--text-primary); }
    .ext-badge, .ext-temporal { font-size: 0.7rem; font-weight: 600; color: var(--text-secondary); border: 1px solid var(--border-strong); border-radius: var(--radius-xs); padding: 0 var(--space-1); align-self: flex-start; }
    .ext-dir { margin: 0; font-size: 0.8125rem; font-weight: 600; color: var(--text-primary); }
    .ext-meta, .ext-muted { margin: 0; font-size: 0.75rem; color: var(--text-secondary); }
    .ext-note { margin: 0; font-size: 0.85rem; color: var(--text-primary); overflow-wrap: anywhere; }
    .ext-strong { margin: 0; font-size: 0.9rem; font-weight: 600; color: var(--text-primary); }
    .ext-source { margin: 0; overflow-wrap: anywhere; }
    .ext-details { font-size: 0.8125rem; color: var(--text-secondary); }
    .ext-details summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; }
    .ext-details summary:focus-visible, .ext-link:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .ext-link { align-self: flex-start; padding: 0; background: none; border: 0; color: var(--brand-primary); font-size: 0.8125rem; text-decoration: underline; cursor: pointer; min-height: 24px; }
    @media (hover: hover) { .ext-link:hover { text-decoration-thickness: 2px; } }
    @media (max-width: 767.98px) { .ext-link { min-height: 44px; } .ext-age { display: flex; flex-direction: column; } }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
  `],
})
export class ExternalFactorsSectionComponent {
  readonly view = input<ExternalFactorsView | null>(null);
  readonly radar = input<RadarExternoView | null>(null);
  readonly focusFactors = output<ExternalDimension>();
}
