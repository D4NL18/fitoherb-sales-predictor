/**
 * Campo de busca estilizado com botão de limpeza e ícone de lupa (Design Plan §5.3).
 */
import { Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-search-field',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="search-field-box">
      <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>

      <input
        type="search"
        class="search-input"
        [placeholder]="placeholder()"
        [attr.aria-label]="label()"
        [value]="value() || ''"
        [disabled]="disabled()"
        (input)="onInput($event)"
        (keydown.enter)="onEnter($event)"
      />

      @if (value() && value()!.trim().length > 0) {
        <button
          type="button"
          class="clear-btn"
          (click)="clear()"
          aria-label="Limpar busca"
        >
          ×
        </button>
      }
    </div>
  `,
  styles: [`
    .search-field-box {
      display: flex;
      align-items: center;
      gap: var(--space-2, 8px);
      min-height: 40px;
      padding: 0 var(--space-3, 12px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      transition: border-color var(--transition-fast);

      &:focus-within {
        border-color: var(--border-focus);
        box-shadow: 0 0 0 1px var(--border-focus);
      }
    }

    .search-icon {
      color: var(--text-secondary);
      flex-shrink: 0;
    }

    .search-input {
      flex: 1;
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
    }

    .clear-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      background: var(--bg-subtle);
      border: none;
      border-radius: var(--radius-xs);
      font-size: 1rem;
      line-height: 1;
      color: var(--text-secondary);
      cursor: pointer;

      &:hover {
        background-color: var(--bg-muted);
        color: var(--text-primary);
      }
    }
  `],
})
export class TrendSearchFieldComponent {
  readonly label = input<string>('Buscar');
  readonly placeholder = input<string>('Código ou descrição do produto');
  readonly value = input<string | undefined>(undefined);
  readonly disabled = input<boolean>(false);

  readonly searchChange = output<string>();

  onInput(event: Event): void {
    const target = event.target as HTMLInputElement;
    const val = target.value.trim();
    if (!val) {
      this.searchChange.emit('');
      return;
    }
    // Aguarda pelo menos 2 caracteres se for busca textual (P-081.1)
    if (!/^\d+$/.test(val) && val.length < 2) {
      return;
    }
    this.searchChange.emit(target.value);
  }

  onEnter(event: Event): void {
    event.preventDefault();
    const target = event.target as HTMLInputElement;
    const val = target.value.trim();
    if (!val) {
      this.searchChange.emit('');
      return;
    }
    if (!/^\d+$/.test(val) && val.length < 2) {
      return;
    }
    this.searchChange.emit(target.value);
  }

  clear(): void {
    this.searchChange.emit('');
  }
}
