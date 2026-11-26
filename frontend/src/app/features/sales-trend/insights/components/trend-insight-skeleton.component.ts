/**
 * Skeleton com a geometria real do painel (Design Plan §8) e do bloco de IA (estado "Gerando", §7).
 * Usa as classes globais `.skeleton-*` (pulso sólido, sem gradiente).
 */
import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-trend-insight-skeleton',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (part() === 'panel') {
      <div class="sk-wrap" aria-hidden="true" data-testid="skeleton-panel">
        <div class="sk-summary">
          <span class="skeleton-box sk-hero"></span>
          <span class="skeleton-line sk-line-lg"></span>
          <span class="skeleton-line sk-line-md"></span>
          <span class="skeleton-box sk-seal"></span>
        </div>
        @for (n of rows; track n) {
          <div class="sk-row">
            <span class="skeleton-line sk-label"></span>
            <span class="skeleton-line sk-bar"></span>
            <span class="skeleton-line sk-value"></span>
          </div>
        }
        @for (n of affineRows; track n) {
          <span class="skeleton-line sk-affine"></span>
        }
      </div>
    } @else if (part() === 'waterfall') {
      <div class="sk-wrap" aria-hidden="true" data-testid="skeleton-waterfall">
        @for (n of rows; track n) {
          <div class="sk-row">
            <span class="skeleton-line sk-label"></span>
            <span class="skeleton-line sk-bar"></span>
            <span class="skeleton-line sk-value"></span>
          </div>
        }
      </div>
    } @else {
      <div class="sk-wrap" aria-hidden="true" data-testid="skeleton-ai">
        <span class="skeleton-line sk-ai-title"></span>
        @for (n of aiLines; track n) {
          <span class="skeleton-line sk-ai-line"></span>
        }
        @for (n of aiFactors; track n) {
          <div class="sk-factor">
            <span class="skeleton-box sk-tag"></span>
            <span class="skeleton-line sk-ai-line"></span>
          </div>
        }
      </div>
    }
  `,
  styles: [`
    :host { display: block; }
    .sk-wrap { display: flex; flex-direction: column; gap: var(--space-3); }
    .sk-summary { display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-4); background-color: var(--bg-subtle); border-radius: var(--radius-xs); }
    .sk-hero { width: 96px; height: 36px; }
    .sk-line-lg { width: 70%; }
    .sk-line-md { width: 50%; }
    .sk-seal { width: 120px; height: 24px; }
    .sk-row { display: grid; grid-template-columns: 40% 30% 18%; gap: var(--space-3); }
    .sk-row .skeleton-line { width: 100%; }
    .sk-affine { width: 100%; height: 1.5em; }
    .sk-ai-title { width: 60%; }
    .sk-ai-line { width: 100%; }
    .sk-factor { display: flex; flex-direction: column; gap: var(--space-2); }
    .sk-tag { width: 90px; height: 20px; }
  `],
})
export class TrendInsightSkeletonComponent {
  readonly part = input<'panel' | 'waterfall' | 'ai'>('panel');
  protected readonly rows = [1, 2, 3, 4, 5, 6, 7];
  protected readonly affineRows = [1, 2, 3, 4];
  protected readonly aiLines = [1, 2, 3];
  protected readonly aiFactors = [1, 2, 3];
}
