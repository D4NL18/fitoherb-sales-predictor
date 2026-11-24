import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';
import {
  CannibalizationDetailData,
  CannibalizationMechanism,
  CannibalizationVictimBase,
  CannibalizationVictimSummary,
  CannibalizationWindowDays,
  CannibalizerDetail,
  CannibalizerSummary,
} from '../../../../models/cannibalization.model';
import {
  BrlPipe,
  PtDecimalPipe,
  SignedBrlPipe,
  SignedDecimalPipe,
  SignedPercentPipe,
} from '../../../../pipes/pt-br-format.pipes';
import {
  MECHANISM_VISUAL_META,
  MechanismVisualMeta,
  getReductionSeverityTag,
} from '../../cannibalization.store';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

let nextDrawerId = 0;

@Component({
  selector: 'app-price-equilibrium-drawer',
  standalone: true,
  imports: [
    BrlPipe,
    PtDecimalPipe,
    SignedBrlPipe,
    SignedDecimalPipe,
    SignedPercentPipe,
  ],
  templateUrl: './price-equilibrium-drawer.component.html',
  styleUrl: './price-equilibrium-drawer.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PriceEquilibriumDrawerComponent {
  readonly victim = input<CannibalizationVictimSummary | null>(null);
  readonly detail = input<CannibalizationDetailData | null>(null);
  readonly loadingDetail = input<boolean>(false);
  readonly detailError = input<string | null>(null);
  readonly windowDays = input<CannibalizationWindowDays>(90);
  readonly returnFocusTo = input<HTMLElement | null>(null);

  readonly closeDrawer = output<void>();
  readonly retryDetail = output<void>();

  private readonly document = inject(DOCUMENT);
  private readonly drawerPanel = viewChild<ElementRef<HTMLElement>>('drawerPanel');
  private readonly closeButton = viewChild<ElementRef<HTMLButtonElement>>('closeButton');

  protected readonly titleId = `price-equilibrium-drawer-title-${nextDrawerId++}`;

  private wasOpen = false;
  private previousBodyOverflow: string | null = null;

  protected readonly isOpen = computed(() => this.victim() !== null);

  protected readonly activeVictim = computed<CannibalizationVictimBase | null>(
    () => this.detail()?.victim ?? this.victim(),
  );

  protected readonly activeCannibalizers = computed<readonly (CannibalizerDetail | CannibalizerSummary)[]>(
    () => {
      const detailed = this.detail();
      if (detailed) return detailed.cannibalizers;
      return this.victim()?.cannibalizers ?? [];
    },
  );

  constructor() {
    effect(() => {
      const open = this.isOpen();
      if (open && !this.wasOpen) {
        this.wasOpen = true;
        this.lockBodyScroll();
        queueMicrotask(() => this.closeButton()?.nativeElement.focus());
      } else if (!open && this.wasOpen) {
        this.wasOpen = false;
        this.unlockBodyScroll();
        const trigger = this.returnFocusTo();
        queueMicrotask(() => trigger?.focus());
      }
    });
  }

  @HostListener('document:keydown', ['$event'])
  onDocumentKeydown(event: KeyboardEvent): void {
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

  protected getSeverityClass(pct: number): string {
    return getReductionSeverityTag(pct);
  }

  protected getMechanismMeta(mechanism: CannibalizationMechanism): MechanismVisualMeta {
    return MECHANISM_VISUAL_META[mechanism];
  }

  protected calcPriceChangePct(currentPrice: number, suggestedPrice: number): number {
    if (currentPrice <= 0) return 0;
    return ((suggestedPrice - currentPrice) / currentPrice) * 100;
  }

  protected calcMarginDiffPp(victimMarginPct: number, cannibalMarginPct: number): number {
    return cannibalMarginPct - victimMarginPct;
  }

  protected isDetailedCannibalizer(
    item: CannibalizerDetail | CannibalizerSummary,
  ): item is CannibalizerDetail {
    return 'victimMarginFloorPrice' in item;
  }

  private trapFocus(event: KeyboardEvent): void {
    const panel = this.drawerPanel()?.nativeElement;
    if (!panel) return;
    const focusables = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    if (focusables.length === 0) return;

    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = this.document.activeElement;

    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  private lockBodyScroll(): void {
    this.previousBodyOverflow = this.document.body.style.overflow;
    this.document.body.style.overflow = 'hidden';
  }

  private unlockBodyScroll(): void {
    if (this.previousBodyOverflow !== null) {
      this.document.body.style.overflow = this.previousBodyOverflow;
      this.previousBodyOverflow = null;
    }
  }
}
