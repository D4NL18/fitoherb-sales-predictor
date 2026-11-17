/**
 * Gaveta lateral de diagnóstico explicativo de churn por cliente (P-122, P-126, LGPD-CHU-01..06).
 * Implementa dialog acessível WCAG 2.1 AA: focus trap, foco inicial, restauração de foco,
 * fechamento por Escape/backdrop, estado de erro com retry e bloqueio de scroll no body.
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
import { CustomerChurnDetailData } from '../../models/churn.model';
import {
  ChurnStatusDisplay,
  formatYearMonth,
  getChurnStatusDisplay,
  sortMonthlyHistoryAsc,
} from '../../pages/churn-page/churn-page.helpers';
import { BrlPipe, PtDatePipe, PtDecimalPipe } from '../../pipes/pt-br-format.pipes';

export interface QuarterlyTrendView {
  symbol: '▲' | '▼' | '▬';
  directionLabel: string;
  cssClass: 'trend-up' | 'trend-down' | 'trend-flat';
  absValue: number;
  signPrefix: string;
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

const MIN_BAR_PERCENT = 4;

@Component({
  selector: 'app-customer-churn-drawer',
  standalone: true,
  imports: [BrlPipe, PtDecimalPipe, PtDatePipe],
  templateUrl: './customer-churn-drawer.component.html',
  styleUrl: './customer-churn-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CustomerChurnDrawerComponent {
  readonly customer = input<CustomerChurnDetailData | null>(null);
  readonly customerCode = input<number | null>(null);
  readonly isOpen = input<boolean>(false);
  readonly loading = input<boolean>(false);
  readonly error = input<string | null>(null);
  readonly returnFocusTo = input<HTMLElement | null>(null);

  readonly closeDrawer = output<void>();
  readonly retry = output<void>();

  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);

  private readonly drawerPanel = viewChild<ElementRef<HTMLElement>>('drawerPanel');
  private readonly closeButton = viewChild<ElementRef<HTMLButtonElement>>('closeButton');

  private wasOpen = false;
  private previousBodyOverflow: string | null = null;

  protected readonly displayCustomerCode = computed(
    () => this.customer()?.customerCode ?? this.customerCode(),
  );

  protected readonly statusDisplay = computed<ChurnStatusDisplay | null>(() => {
    const detail = this.customer();
    return detail ? getChurnStatusDisplay(detail.status) : null;
  });

  protected readonly sortedHistory = computed(() =>
    sortMonthlyHistoryAsc(this.customer()?.historicoMensal ?? []),
  );

  protected readonly maxMonthlyRevenue = computed(() => {
    const history = this.sortedHistory();
    if (history.length === 0) return 0;
    return Math.max(...history.map((item) => item.faturamentoLiquido), 0);
  });

  protected readonly quarterlyTrend = computed<QuarterlyTrendView | null>(() => {
    const pct = this.customer()?.variacaoReceitaTrimestralPct;
    if (pct === null || pct === undefined) return null;
    if (pct > 0) {
      return {
        symbol: '▲',
        directionLabel: 'alta',
        cssClass: 'trend-up',
        absValue: pct,
        signPrefix: '+',
      };
    }
    if (pct < 0) {
      return {
        symbol: '▼',
        directionLabel: 'queda',
        cssClass: 'trend-down',
        absValue: Math.abs(pct),
        signPrefix: '-',
      };
    }
    return {
      symbol: '▬',
      directionLabel: 'estável',
      cssClass: 'trend-flat',
      absValue: 0,
      signPrefix: '',
    };
  });

  constructor() {
    effect(() => {
      const open = this.isOpen();
      if (open && !this.wasOpen) {
        this.wasOpen = true;
        this.lockBodyScroll();
        Promise.resolve().then(() => this.focusInitialElement());
      } else if (!open && this.wasOpen) {
        this.wasOpen = false;
        this.restoreBodyScroll();
        const target = this.returnFocusTo();
        Promise.resolve().then(() => this.restoreFocus(target));
      }
    });

    this.destroyRef.onDestroy(() => this.restoreBodyScroll());
  }

  @HostListener('document:keydown', ['$event'])
  onDocumentKeydown(event: KeyboardEvent): void {
    if (!this.isOpen()) return;

    if (event.key === 'Escape') {
      event.preventDefault();
      this.close();
      return;
    }

    if (event.key === 'Tab') {
      this.trapTabKey(event);
    }
  }

  protected close(): void {
    this.closeDrawer.emit();
  }

  protected onRetry(): void {
    this.retry.emit();
  }

  protected formatMonth(anoMes: string): string {
    return formatYearMonth(anoMes);
  }

  protected getMonthlyBarPct(revenue: number): number {
    const max = this.maxMonthlyRevenue();
    if (max <= 0 || revenue <= 0) return 0;
    return Math.max(MIN_BAR_PERCENT, Math.min(100, Math.round((revenue / max) * 100)));
  }

  private lockBodyScroll(): void {
    if (this.previousBodyOverflow === null) {
      this.previousBodyOverflow = this.document.body.style.overflow;
    }
    this.document.body.style.overflow = 'hidden';
  }

  private restoreBodyScroll(): void {
    if (this.previousBodyOverflow !== null) {
      this.document.body.style.overflow = this.previousBodyOverflow;
      this.previousBodyOverflow = null;
    }
  }

  private focusInitialElement(): void {
    if (!this.isOpen()) return;
    const closeBtn = this.closeButton()?.nativeElement;
    if (closeBtn) {
      closeBtn.focus();
      return;
    }
    this.drawerPanel()?.nativeElement.focus();
  }

  private restoreFocus(target: HTMLElement | null): void {
    if (this.isOpen() || !target || !target.isConnected) return;
    target.focus();
  }

  private trapTabKey(event: KeyboardEvent): void {
    const panel = this.drawerPanel()?.nativeElement;
    if (!panel) return;

    const focusables = this.getFocusableElements(panel);
    if (focusables.length === 0) {
      event.preventDefault();
      panel.focus();
      return;
    }

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = this.document.activeElement as HTMLElement | null;

    if (!active || !panel.contains(active)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
      return;
    }

    if (event.shiftKey && (active === first || active === panel)) {
      event.preventDefault();
      last.focus();
      return;
    }

    if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  private getFocusableElements(container: HTMLElement): HTMLElement[] {
    const candidates = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    const view = this.document.defaultView;
    return candidates.filter((el) => {
      if (el.getAttribute('aria-hidden') === 'true') return false;
      if (el.closest('[hidden], [inert]')) return false;
      if (!view) return true;
      const style = view.getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
  }
}
