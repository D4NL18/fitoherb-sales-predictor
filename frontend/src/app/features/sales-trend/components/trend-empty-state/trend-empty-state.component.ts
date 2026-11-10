/**
 * Estado vazio informativo com ícone e ação sugerida (Design Plan §4.2).
 */
import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-empty-state',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="trend-empty-state" role="status">
      <div class="empty-icon-box" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
      </div>

      <h3 class="empty-title">{{ title() }}</h3>
      <p class="empty-desc">{{ description() }}</p>

      @if (actionLabel()) {
        <button type="button" class="empty-action-btn" (click)="action.emit()">
          {{ actionLabel() }}
        </button>
      }
    </div>
  `,
  styles: [`
    .trend-empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: var(--space-8, 32px) var(--space-4, 16px);
      text-align: center;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
    }

    .empty-icon-box {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 56px;
      margin-bottom: var(--space-4, 16px);
      background-color: var(--bg-subtle);
      border-radius: var(--radius-xs);
      color: var(--text-secondary);
    }

    .empty-title {
      font-size: 1.125rem;
      margin-bottom: var(--space-2, 8px);
      color: var(--text-primary);
    }

    .empty-desc {
      max-width: 440px;
      margin-bottom: var(--space-4, 16px);
      font-size: 0.875rem;
      color: var(--text-secondary);
      line-height: 1.4;
    }

    .empty-action-btn {
      min-height: 38px;
      padding: var(--space-2, 8px) var(--space-4, 16px);
      background-color: var(--brand-primary);
      border: 1px solid var(--brand-primary-active);
      border-radius: var(--radius-xs);
      color: var(--text-on-brand);
      font-weight: 600;
      font-size: 0.875rem;
      cursor: pointer;

      &:hover {
        background-color: var(--brand-primary-hover);
      }
    }
  `],
})
export class TrendEmptyStateComponent {
  readonly title = input.required<string>();
  readonly description = input.required<string>();
  readonly actionLabel = input<string | null>(null);
  readonly action = output<void>();
}
