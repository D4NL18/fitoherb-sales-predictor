/**
 * Aviso contextual em linha para notificações não-bloqueantes (Design Plan §4.2).
 */
import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-inline-notice',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="inline-notice" [class.warning-tone]="tone() === 'warning'" role="note">
      <div class="notice-icon" aria-hidden="true">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      </div>

      <div class="notice-body">
        @if (title()) {
          <strong class="notice-title">{{ title() }}</strong>
        }
        <span class="notice-text">{{ text() }}</span>
      </div>

      @if (actionLabel()) {
        <button type="button" class="notice-action-btn" (click)="action.emit()">
          {{ actionLabel() }}
        </button>
      }

      @if (dismissible()) {
        <button type="button" class="notice-dismiss-btn" (click)="dismiss.emit()" aria-label="Fechar aviso">
          ×
        </button>
      }
    </div>
  `,
  styles: [`
    .inline-notice {
      display: flex;
      align-items: center;
      gap: var(--space-3, 12px);
      padding: var(--space-3, 12px) var(--space-4, 16px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-left: 4px solid var(--feedback-info-bg, #1B4B7A);
      border-radius: var(--radius-xs);
      font-size: 0.875rem;
      color: var(--text-primary);
    }

    .inline-notice.warning-tone {
      border-left-color: var(--feedback-warning-bg, #7A4607);
    }

    .notice-icon {
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    .notice-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .notice-title {
      font-weight: 600;
    }

    .notice-action-btn {
      background: none;
      border: none;
      padding: 0;
      color: var(--brand-primary);
      font-weight: 600;
      text-decoration: underline;
      cursor: pointer;
      white-space: nowrap;

      &:hover {
        color: var(--brand-primary-hover);
      }
    }

    .notice-dismiss-btn {
      background: none;
      border: none;
      font-size: 1.25rem;
      line-height: 1;
      color: var(--text-muted);
      cursor: pointer;
      padding: 0 var(--space-1);

      &:hover {
        color: var(--text-primary);
      }
    }
  `],
})
export class InlineNoticeComponent {
  readonly tone = input<'info' | 'warning'>('info');
  readonly title = input<string | null>(null);
  readonly text = input.required<string>();
  readonly actionLabel = input<string | null>(null);
  readonly dismissible = input<boolean>(false);

  readonly action = output<void>();
  readonly dismiss = output<void>();
}
