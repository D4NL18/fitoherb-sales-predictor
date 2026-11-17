/**
 * Drawer de explicabilidade de produto similar (F2, P-142, P-143, P-144).
 * Dialog acessível WCAG 2.1 AA: Focus Trap nativo, Escape, backdrop, bloqueio de scroll
 * e restauração de foco ao botão gatilho. Exibe os 3 scores sem fabricar termos TF-IDF.
 */
import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import { NewProductForecastRequest, SimilarProductItem } from '../../../../models/new-product.model';
import { BrlPipe, PtDatePipe, PtDecimalPipe, PtPercentPipe } from '../../../../pipes/pt-br-format.pipes';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

@Component({
  selector: 'app-new-product-similars-drawer',
  standalone: true,
  imports: [BrlPipe, PtDatePipe, PtDecimalPipe, PtPercentPipe],
  templateUrl: './new-product-similars-drawer.component.html',
  styleUrl: './new-product-similars-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NewProductSimilarsDrawerComponent {
  readonly similar = input<SimilarProductItem | null>(null);
  readonly inputSummary = input<NewProductForecastRequest | null>(null);
  readonly returnFocusTo = input<HTMLElement | null>(null);

  readonly closeDrawer = output<void>();

  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);

  private readonly drawerPanel = viewChild<ElementRef<HTMLElement>>('drawerPanel');
  private readonly closeButton = viewChild<ElementRef<HTMLButtonElement>>('closeButton');

  private wasOpen = false;
  private previousBodyOverflow: string | null = null;

  protected readonly isOpen = computed(() => this.similar() !== null);

  protected readonly maxLaunchQty = computed(() => {
    const item = this.similar();
    if (!item || item.quantidadesPrimeirosMeses.length === 0) return 1;
    return Math.max(...item.quantidadesPrimeirosMeses, 1);
  });

  constructor() {
    effect(() => {
      const open = this.isOpen();
      if (open && !this.wasOpen) {
        this.wasOpen = true;
        this.lockBodyScroll();
        queueMicrotask(() => {
          this.closeButton()?.nativeElement.focus();
        });
      } else if (!open && this.wasOpen) {
        this.wasOpen = false;
        this.unlockBodyScroll();
        const target = this.returnFocusTo();
        queueMicrotask(() => {
          target?.focus();
        });
      }
    });

    this.destroyRef.onDestroy(() => {
      if (this.wasOpen) {
        this.unlockBodyScroll();
      }
    });
  }

  @HostListener('document:keydown', ['$event'])
  protected onDocumentKeydown(event: KeyboardEvent): void {
    if (!this.isOpen()) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      this.closeDrawer.emit();
      return;
    }

    if (event.key === 'Tab') {
      this.trapFocus(event);
    }
  }

  protected onBackdropClick(): void {
    this.closeDrawer.emit();
  }

  protected barWidthPercent(qty: number): number {
    const max = this.maxLaunchQty();
    if (qty <= 0 || max <= 0) return 0;
    return Math.max(6, Math.round((qty / max) * 100));
  }

  private trapFocus(event: KeyboardEvent): void {
    const panel = this.drawerPanel()?.nativeElement;
    if (!panel) return;

    const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
      (el) => el.offsetParent !== null,
    );
    if (focusables.length === 0) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = this.document.activeElement;

    if (event.shiftKey && (active === first || !panel.contains(active))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || !panel.contains(active))) {
      event.preventDefault();
      first.focus();
    }
  }

  private lockBodyScroll(): void {
    if (this.previousBodyOverflow !== null) return;
    this.previousBodyOverflow = this.document.body.style.overflow;
    this.document.body.style.overflow = 'hidden';
  }

  private unlockBodyScroll(): void {
    if (this.previousBodyOverflow === null) return;
    this.document.body.style.overflow = this.previousBodyOverflow;
    this.previousBodyOverflow = null;
  }
}
