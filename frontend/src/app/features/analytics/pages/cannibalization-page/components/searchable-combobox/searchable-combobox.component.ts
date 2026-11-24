import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { FilterOptionCount } from '../../../../models/cannibalization.model';
import { PtDecimalPipe } from '../../../../pipes/pt-br-format.pipes';
import { normalizeFilterText } from '../../cannibalization.store';

let nextComboboxId = 0;

@Component({
  selector: 'app-searchable-combobox',
  standalone: true,
  imports: [PtDecimalPipe],
  templateUrl: './searchable-combobox.component.html',
  styleUrl: './searchable-combobox.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '(document:click)': 'onDocumentClick($event)',
  },
})
export class SearchableComboboxComponent {
  readonly label = input.required<string>();
  readonly allLabel = input.required<string>();
  readonly searchPlaceholder = input<string>('Buscar...');
  readonly emptySearchLabel = input<string>('Nenhuma opção encontrada');
  readonly clearAriaLabel = input<string>('Limpar filtro');
  readonly listboxAriaLabel = input<string>('Opções disponíveis');
  readonly options = input<FilterOptionCount[]>([]);
  readonly totalItemsCount = input<number>(0);
  readonly selectedValue = input<string>('');
  readonly disabled = input<boolean>(false);

  readonly valueChange = output<string>();

  private readonly hostContainer = viewChild<ElementRef<HTMLElement>>('comboboxContainer');
  private readonly triggerButton = viewChild<ElementRef<HTMLButtonElement>>('triggerEl');
  private readonly searchInput = viewChild<ElementRef<HTMLInputElement>>('searchEl');

  protected readonly ids = createIds();
  protected readonly isOpen = signal<boolean>(false);
  protected readonly internalQuery = signal<string>('');
  protected readonly activeIndex = signal<number>(-1);

  protected readonly filteredOptions = computed(() => {
    const query = normalizeFilterText(this.internalQuery());
    const opts = this.options();
    if (!query) return opts;
    const tokens = query.split(/\s+/).filter((t) => t.length > 0);
    return opts.filter((opt) => {
      const normalized = normalizeFilterText(opt.name);
      return tokens.every((token) => normalized.includes(token));
    });
  });

  protected toggleDropdown(): void {
    if (this.disabled()) return;
    if (this.isOpen()) {
      this.closeDropdown(false);
      return;
    }
    this.openDropdown();
  }

  protected openDropdown(): void {
    if (this.disabled()) return;
    this.isOpen.set(true);
    this.internalQuery.set('');
    this.activeIndex.set(-1);
    queueMicrotask(() => {
      this.searchInput()?.nativeElement.focus();
    });
  }

  protected closeDropdown(restoreFocus = false): void {
    if (!this.isOpen()) return;
    this.isOpen.set(false);
    this.internalQuery.set('');
    this.activeIndex.set(-1);
    if (restoreFocus) {
      this.triggerButton()?.nativeElement.focus();
    }
  }

  protected selectOption(value: string): void {
    this.valueChange.emit(value);
    this.closeDropdown(false);
  }

  protected clearSelection(event: Event): void {
    event.stopPropagation();
    if (this.disabled()) return;
    this.valueChange.emit('');
    this.closeDropdown(false);
  }

  protected onSearchInput(value: string): void {
    this.internalQuery.set(value);
    const matches = this.filteredOptions();
    this.activeIndex.set(matches.length > 0 && value.trim().length > 0 ? 0 : -1);
  }

  protected onKeydown(event: KeyboardEvent): void {
    const matches = this.filteredOptions();
    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeDropdown(true);
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (!this.isOpen()) {
        this.openDropdown();
        return;
      }
      if (matches.length === 0) return;
      const next = this.activeIndex() < matches.length - 1 ? this.activeIndex() + 1 : 0;
      this.activeIndex.set(next);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (matches.length === 0) return;
      const prev = this.activeIndex() > 0 ? this.activeIndex() - 1 : matches.length - 1;
      this.activeIndex.set(prev);
      return;
    }
    if (event.key === 'Enter' && this.isOpen()) {
      event.preventDefault();
      const idx = this.activeIndex();
      if (idx >= 0 && idx < matches.length) {
        this.selectOption(matches[idx].name);
      } else if (matches.length === 1) {
        this.selectOption(matches[0].name);
      } else if (this.internalQuery().trim() === '') {
        this.selectOption('');
      }
    }
  }

  protected onDocumentClick(event: MouseEvent): void {
    if (!this.isOpen()) return;
    const container = this.hostContainer()?.nativeElement;
    const target = event.target as Node | null;
    if (container && target && !container.contains(target)) {
      this.closeDropdown(false);
    }
  }
}

function createIds() {
  const prefix = `searchable-cb-${nextComboboxId++}`;
  return {
    trigger: `${prefix}-trigger`,
    search: `${prefix}-search`,
    listbox: `${prefix}-listbox`,
  };
}
