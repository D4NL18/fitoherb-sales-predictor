/**
 * Banner de alerta para erros de comunicação com a API (Design Plan §4.2).
 * Exibe role="alert" e botão de nova tentativa (com ação secundária opcional para recuperação contextual).
 */
import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-error-banner',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
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

      <div class="banner-actions">
        @if (secondaryActionLabel()) {
          <button type="button" class="retry-btn primary-recovery-btn" (click)="secondaryAction.emit()">
            {{ secondaryActionLabel() }}
          </button>
        }
        <button type="button" class="retry-btn" (click)="retry.emit()">
          {{ retryLabel() }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .trend-error-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: var(--space-3);
      padding: var(--space-4);
      background-color: var(--feedback-critical-subtle);
      border: 1px solid var(--feedback-critical-border);
      border-left: 4px solid var(--feedback-critical-bg);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
    }

    .banner-content {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      flex: 1 1 240px;
      min-width: 0;
    }

    .alert-icon {
      color: var(--feedback-critical-bg);
      flex-shrink: 0;
    }

    .error-text {
      font-weight: 500;
      font-size: 0.9375rem;
    }

    .banner-actions {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
    }

    .retry-btn {
      min-height: 40px;
      padding: var(--space-1) var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      font-family: var(--font-family-body);
      font-weight: 600;
      font-size: 0.875rem;
      color: var(--text-primary);
      cursor: pointer;
      white-space: nowrap;

      &:hover {
        background-color: var(--bg-subtle);
        border-color: var(--border-strong);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }

      &.primary-recovery-btn {
        background-color: var(--brand-primary);
        border-color: var(--brand-primary-active);
        color: var(--text-on-brand);

        &:hover {
          background-color: var(--brand-primary-hover);
        }
      }
    }
  `],
})
export class TrendErrorBannerComponent {
  readonly message = input.required<string>();
  readonly retryLabel = input<string>('Tentar novamente');
  readonly secondaryActionLabel = input<string | null>(null);
  readonly retry = output<void>();
  readonly secondaryAction = output<void>();
}
