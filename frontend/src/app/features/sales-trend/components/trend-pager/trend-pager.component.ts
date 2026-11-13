/**
 * Componente reutilizável de paginação acessível (Design Plan §4.2, P-081.4).
 * Oculta automaticamente se houver 1 página ou menos e usa tokens oficiais de design.
 */
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-trend-pager',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (totalPages() > 1) {
      <nav class="trend-pager" [attr.aria-label]="ariaLabel()">
        <span class="pager-summary">
          {{ rangeText() }}
        </span>

        <div class="pager-controls">
          <button
            type="button"
            class="pager-btn"
            [disabled]="disabled() || page() <= 1"
            (click)="goTo(page() - 1)"
            aria-label="Página anterior"
          >
            ‹ Anterior
          </button>

          <span class="pager-current">
            Página {{ page() }} de {{ totalPages() }}
          </span>

          <button
            type="button"
            class="pager-btn"
            [disabled]="disabled() || page() >= totalPages()"
            (click)="goTo(page() + 1)"
            aria-label="Próxima página"
          >
            Próxima ›
          </button>
        </div>
      </nav>
    }
  `,
  styles: [`
    .trend-pager {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: var(--space-3);
      padding: var(--space-3) 0;
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      color: var(--text-secondary);
    }

    .pager-summary {
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;
      color: var(--text-secondary);
    }

    .pager-controls {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-2);
    }

    .pager-btn {
      min-height: 40px;
      padding: var(--space-1) var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      color: var(--text-primary);
      font-family: var(--font-family-body);
      font-weight: 600;
      cursor: pointer;
      transition: background-color var(--transition-fast);

      &:hover:not(:disabled) {
        background-color: var(--bg-subtle);
        border-color: var(--border-strong);
      }

      &:focus-visible {
        outline: 2px solid var(--border-focus);
        outline-offset: 2px;
      }

      &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
    }

    .pager-current {
      font-weight: 600;
      color: var(--text-primary);
      padding: 0 var(--space-2);
    }
  `],
})
export class TrendPagerComponent {
  readonly page = input.required<number>();
  readonly totalPages = input.required<number>();
  readonly totalItems = input.required<number>();
  readonly offset = input.required<number>();
  readonly limit = input.required<number>();
  readonly ariaLabel = input<string>('Navegação entre páginas');
  readonly disabled = input<boolean>(false);

  readonly pageChange = output<number>();

  readonly rangeText = computed(() => {
    const total = this.totalItems();
    if (total === 0) return '0 itens';
    const start = this.offset() + 1;
    const end = Math.min(this.offset() + this.limit(), total);
    return `${start}–${end} de ${total}`;
  });

  goTo(target: number): void {
    if (target >= 1 && target <= this.totalPages() && !this.disabled()) {
      this.pageChange.emit(target);
    }
  }
}
