/**
 * Campo de busca estilizado com botão de limpeza acessível, suporte a Escape e debounce (Design Plan §5.3).
 */
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { CommonModule } from '@angular/common';

const SEARCH_DEBOUNCE_MS = 250;
const MAX_SEARCH_LENGTH = 60;

@Component({
  selector: 'app-trend-search-field',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="search-field-wrap">
      <div class="search-field-box" [class.is-disabled]="disabled()">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>

        <input
          #searchInput
          type="search"
          class="search-input"
          [maxLength]="60"
          [placeholder]="placeholder()"
          [attr.aria-label]="label()"
          [attr.aria-invalid]="validationHint() ? 'true' : null"
          [attr.aria-describedby]="validationHint() ? 'search-validation-hint' : null"
          [value]="draftValue()"
          [disabled]="disabled()"
          (input)="onInput($event)"
          (keydown.enter)="onEnter($event)"
          (keydown.escape)="onEscape($event)"
        />

        @if (draftValue().trim().length > 0 && !disabled()) {
          <button
            type="button"
            class="clear-btn"
            (click)="clear()"
            aria-label="Limpar busca"
            title="Limpar busca (Esc)"
          >
            ×
          </button>
        }
      </div>
      @if (validationHint()) {
        <p id="search-validation-hint" class="search-hint" role="status">
          {{ validationHint() }}
        </p>
      }
    </div>
  `,
  styles: [`
    .search-field-wrap {
      display: flex;
      flex-direction: column;
      gap: 4px;
      width: 100%;
      min-width: 0;
    }

    .search-field-box {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      min-height: 40px;
      padding: 0 var(--space-2) 0 var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      transition: border-color var(--transition-fast), box-shadow var(--transition-fast);

      &:hover:not(.is-disabled) {
        border-color: var(--border-strong);
      }

      &:focus-within {
        border-color: var(--border-focus);
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }

      &.is-disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }
    }

    .search-icon {
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    .search-input {
      flex: 1;
      min-width: 0;
      width: 100%;
      height: 38px;
      background: transparent;
      border: none;
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      color: var(--text-primary);
      outline: none;

      &::placeholder {
        color: var(--text-muted);
      }

      &::-webkit-search-cancel-button {
        -webkit-appearance: none;
        appearance: none;
      }
    }

    .clear-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      flex-shrink: 0;
      background: var(--bg-subtle);
      border: 1px solid transparent;
      border-radius: var(--radius-xs);
      font-size: 1.05rem;
      line-height: 1;
      color: var(--text-secondary);
      cursor: pointer;

      &:hover {
        background-color: var(--bg-muted);
        color: var(--text-primary);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 1px;
      }
    }

    .search-hint {
      margin: 0;
      font-size: 0.75rem;
      color: var(--feedback-warning-bg);
      font-weight: 600;
    }
  `],
})
export class TrendSearchFieldComponent {
  private readonly destroyRef = inject(DestroyRef);
  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('searchInput');

  readonly label = input<string>('Buscar');
  readonly placeholder = input<string>('Código ou descrição do produto');
  readonly value = input<string | undefined>(undefined);
  readonly disabled = input<boolean>(false);

  readonly searchChange = output<string>();

  readonly draftValue = signal<string>('');
  readonly validationHint = signal<string | null>(null);

  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private lastEmittedNormalized: string | null = null;

  constructor() {
    effect(
      () => {
        const external = this.value() ?? '';
        const externalNormalized = external.trim();
        if (this.lastEmittedNormalized === null || externalNormalized !== this.lastEmittedNormalized) {
          this.draftValue.set(external);
          this.lastEmittedNormalized = externalNormalized;
          this.validationHint.set(null);
        }
      },
      { allowSignalWrites: true },
    );

    this.destroyRef.onDestroy(() => this.clearDebounceTimer());
  }

  onInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    const raw = target.value.slice(0, MAX_SEARCH_LENGTH);
    this.draftValue.set(raw);
    this.validationHint.set(null);
    this.clearDebounceTimer();

    const val = raw.trim();
    if (val && !/^\d+$/.test(val) && val.length < 2) {
      return;
    }

    this.debounceTimer = setTimeout(() => {
      this.debounceTimer = null;
      this.emitSearch(raw);
    }, SEARCH_DEBOUNCE_MS);
  }

  onEnter(event: Event): void {
    event.preventDefault();
    this.clearDebounceTimer();
    const target = event.target as HTMLInputElement;
    const raw = target.value.slice(0, MAX_SEARCH_LENGTH);
    this.draftValue.set(raw);

    const val = raw.trim();
    if (val && !/^\d+$/.test(val) && val.length < 2) {
      this.validationHint.set('Digite ao menos 2 letras ou 1 número para buscar.');
      return;
    }
    this.validationHint.set(null);
    this.emitSearch(raw);
  }

  onEscape(event: Event): void {
    if (this.draftValue().trim().length > 0) {
      event.preventDefault();
      this.clear();
    }
  }

  clear(): void {
    this.clearDebounceTimer();
    this.draftValue.set('');
    this.validationHint.set(null);
    this.emitSearch('');
    this.searchInput()?.nativeElement.focus();
  }

  private emitSearch(raw: string): void {
    this.lastEmittedNormalized = raw.trim();
    this.searchChange.emit(raw);
  }

  private clearDebounceTimer(): void {
    if (this.debounceTimer !== null) {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = null;
    }
  }
}
