/**
 * Paginador de lista paginada no servidor (P-066; Design Plan §5.9, D-11).
 * Burro: mostra "{a}–{b} de {total}" e emite a página 1-based; oculto com uma página só.
 */
import { Component, computed, input, output } from '@angular/core';
import { PtDecimalPipe } from '../../pipes/pt-br-format.pipes';

@Component({
  selector: 'app-list-pager',
  standalone: true,
  imports: [PtDecimalPipe],
  templateUrl: './list-pager.component.html',
  styleUrl: './list-pager.component.scss',
})
export class ListPagerComponent {
  readonly page = input.required<number>();
  readonly totalPages = input.required<number>();
  readonly totalItems = input.required<number>();
  readonly offset = input.required<number>();
  readonly itemCount = input.required<number>();
  readonly disabled = input<boolean>(false);
  readonly pageChange = output<number>();

  protected readonly visible = computed(() => this.totalPages() > 1);
  protected readonly firstItem = computed(() => this.offset() + 1);
  protected readonly lastItem = computed(() => this.offset() + this.itemCount());
  protected readonly isFirst = computed(() => this.page() <= 1);
  protected readonly isLast = computed(() => this.page() >= this.totalPages());

  protected go(page: number): void {
    if (this.disabled() || page < 1 || page > this.totalPages()) return;
    this.pageChange.emit(page);
  }
}
