import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  ViewChild,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

@Component({
  selector: 'app-searchable-select',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ss-wrapper" [class.ss-open]="isOpen()">
      <button
        type="button"
        class="ss-trigger"
        [attr.aria-label]="ariaLabel()"
        [attr.aria-expanded]="isOpen()"
        aria-haspopup="listbox"
        (click)="toggle()"
      >
        <span class="ss-trigger-label">{{ value() || allLabel() }}</span>
        <svg class="ss-chevron" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <path stroke-linecap="round" stroke-linejoin="round" d="m4 6 4 4 4-4" />
        </svg>
      </button>

      @if (isOpen()) {
        <div class="ss-panel" role="dialog" [attr.aria-label]="ariaLabel()">
          <div class="ss-search-box">
            <input
              #searchInput
              type="search"
              class="ss-search-input"
              [placeholder]="searchPlaceholder()"
              [value]="filterText()"
              (input)="filterText.set($any($event.target).value)"
              (keydown.escape)="close()"
            />
          </div>

          <ul class="ss-list" role="listbox">
            <li
              role="option"
              class="ss-option ss-option-all"
              [class.ss-selected]="value() === ''"
              [attr.aria-selected]="value() === ''"
              (click)="select('')"
            >
              {{ allLabel() }}
            </li>
            @for (opt of filteredOptions(); track opt) {
              <li
                role="option"
                class="ss-option"
                [class.ss-selected]="value() === opt"
                [attr.aria-selected]="value() === opt"
                (click)="select(opt)"
              >
                {{ opt }}
              </li>
            } @empty {
              <li class="ss-empty">Nenhum resultado</li>
            }
          </ul>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .ss-wrapper {
        position: relative;
        display: inline-block;
        min-width: 190px;
        max-width: 260px;
      }

      .ss-trigger {
        display: inline-flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--space-2, 0.5rem);
        width: 100%;
        min-height: 44px;
        padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
        font-family: var(--font-family-body);
        font-size: 0.88rem;
        color: var(--text-primary);
        background-color: var(--bg-surface);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-xs, 4px);
        cursor: pointer;
        text-align: left;

        &:focus-visible {
          outline: 2px solid var(--brand-primary);
          outline-offset: 1px;
        }
      }

      .ss-trigger-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .ss-chevron {
        flex-shrink: 0;
        color: var(--text-muted);
      }

      .ss-panel {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        z-index: 30;
        min-width: 240px;
        width: 100%;
        background-color: var(--bg-surface);
        border: 1px solid var(--border-strong, var(--border-default));
        border-radius: var(--radius-xs, 4px);
        box-shadow: 0 8px 24px rgba(15, 23, 18, 0.12);
        overflow: hidden;
      }

      .ss-search-box {
        padding: 0.5rem;
        border-bottom: 1px solid var(--border-default);
        background-color: var(--bg-subtle);
      }

      .ss-search-input {
        width: 100%;
        padding: 0.45rem 0.6rem;
        font-family: var(--font-family-body);
        font-size: 0.85rem;
        color: var(--text-primary);
        background-color: var(--bg-surface);
        border: 1px solid var(--border-default);
        border-radius: var(--radius-xs, 4px);

        &:focus {
          outline: 2px solid var(--brand-primary);
          outline-offset: 1px;
        }
      }

      .ss-list {
        list-style: none;
        margin: 0;
        padding: 0.25rem 0;
        max-height: 240px;
        overflow-y: auto;
      }

      .ss-option {
        padding: 0.45rem 0.75rem;
        font-size: 0.86rem;
        color: var(--text-primary);
        cursor: pointer;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;

        &:hover {
          background-color: var(--bg-subtle);
        }

        &.ss-selected {
          font-weight: 600;
          color: var(--brand-primary);
          background-color: color-mix(in srgb, var(--brand-primary) 10%, transparent);
        }
      }

      .ss-option-all {
        border-bottom: 1px solid var(--border-default);
      }

      .ss-empty {
        padding: 0.65rem 0.75rem;
        font-size: 0.84rem;
        color: var(--text-muted);
        text-align: center;
      }
    `,
  ],
})
export class SearchableSelectComponent {
  private readonly hostRef = inject(ElementRef<HTMLElement>);

  @ViewChild('searchInput') private searchInput?: ElementRef<HTMLInputElement>;

  readonly options = input<readonly string[]>([]);
  readonly value = input<string>('');
  readonly allLabel = input<string>('Todos');
  readonly searchPlaceholder = input<string>('Buscar...');
  readonly ariaLabel = input<string>('Selecionar opção');

  readonly valueChange = output<string>();

  readonly isOpen = signal(false);
  readonly filterText = signal('');

  readonly filteredOptions = computed(() => {
    const query = normalizeText(this.filterText().trim());
    const all = this.options();
    if (!query) return all;
    return all.filter((opt) => normalizeText(opt).includes(query));
  });

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.isOpen()) return;
    const target = event.target as Node | null;
    if (target && !this.hostRef.nativeElement.contains(target)) {
      this.close();
    }
  }

  toggle(): void {
    if (this.isOpen()) {
      this.close();
      return;
    }
    this.filterText.set('');
    this.isOpen.set(true);
    setTimeout(() => this.searchInput?.nativeElement.focus(), 0);
  }

  close(): void {
    this.isOpen.set(false);
  }

  select(option: string): void {
    this.valueChange.emit(option);
    this.close();
  }
}
