/**
 * Banner de alerta para erros de comunicação com a API (Design Plan §4.2).
 * Exibe role="alert" e botão de nova tentativa.
 */
import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-error-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="trend-error-banner" role="alert">
      <div class="banner-content">
        <svg class="alert-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span class="error-text">{{ message() }}</span>
      </div>

      <button type="button" class="retry-btn" (click)="retry.emit()">
        {{ retryLabel() }}
      </button>
    </div>
  `,
  styles: [`
    .trend-error-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-4, 16px);
      padding: var(--space-4, 16px);
      background-color: var(--bg-surface);
      border: 1px solid var(--feedback-critical-border, #661212);
      border-left: 4px solid var(--feedback-critical-bg, #8F1B1B);
      border-radius: var(--radius-sm, 5px);
      color: var(--text-primary);
    }

    .banner-content {
      display: flex;
      align-items: center;
      gap: var(--space-3, 12px);
    }

    .alert-icon {
      color: var(--feedback-critical-bg, #8F1B1B);
      flex-shrink: 0;
    }

    .error-text {
      font-weight: 500;
      font-size: 0.9375rem;
    }

    .retry-btn {
      min-height: 36px;
      padding: var(--space-1, 4px) var(--space-3, 12px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      font-weight: 600;
      font-size: 0.875rem;
      color: var(--text-primary);
      cursor: pointer;
      white-space: nowrap;

      &:hover {
        background-color: var(--bg-subtle);
        border-color: var(--border-strong);
      }
    }
  `],
})
export class TrendErrorBannerComponent {
  readonly message = input.required<string>();
  readonly retryLabel = input<string>('Tentar novamente');
  readonly retry = output<void>();
}
