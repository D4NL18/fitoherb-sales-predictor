import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
  viewChild,
} from '@angular/core';
import { InfoHelpCoordinatorService } from './info-help-coordinator.service';

export interface InfoHelpContent {
  title: string;
  whatIs: string;
  howToAnalyze: string;
  insight: string;
  technicalNote?: string;
}

const MOBILE_MEDIA_QUERY = '(max-width: 639.98px)';
const MOBILE_BREAKPOINT_PX = 640;
const DESKTOP_POPOVER_MAX_WIDTH = 340;
const MIN_POPOVER_WIDTH = 220;
const ESTIMATED_POPOVER_HEIGHT = 280;
const VIEWPORT_MARGIN_PX = 12;
const POPOVER_GAP_PX = 8;
const FALLBACK_VIEWPORT_WIDTH = 1024;
const FALLBACK_VIEWPORT_HEIGHT = 768;

let nextHelpInstanceId = 0;

@Component({
  selector: 'app-info-help',
  standalone: true,
  templateUrl: './info-help.component.html',
  styleUrl: './info-help.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InfoHelpComponent {
  private readonly coordinator = inject(InfoHelpCoordinatorService);
  private readonly hostRef = inject(ElementRef<HTMLElement>);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);

  private readonly triggerRef = viewChild<ElementRef<HTMLButtonElement>>('triggerBtn');
  private readonly popoverRef = viewChild<ElementRef<HTMLElement>>('popoverDialog');

  private readonly helpId = `info-help-${++nextHelpInstanceId}`;
  private listenersAttached = false;

  readonly topicLabel = input.required<string>();
  readonly content = input.required<InfoHelpContent>();
  readonly size = input<'sm' | 'md'>('sm');
  readonly preferredAlign = input<'start' | 'center' | 'end'>('center');

  protected readonly dialogId = `${this.helpId}-dialog`;
  protected readonly titleId = `${this.helpId}-title`;

  protected readonly isOpen = computed(() => this.coordinator.activeHelpId() === this.helpId);
  protected readonly isMobileViewport = signal<boolean>(false);
  protected readonly popoverTopPx = signal<number | null>(null);
  protected readonly popoverLeftPx = signal<number | null>(null);

  private readonly handleDocumentKeydown = (event: KeyboardEvent): void => {
    if (event.key !== 'Escape' || !this.isOpen()) return;
    event.preventDefault();
    event.stopPropagation();
    this.coordinator.close(this.helpId);
    this.triggerRef()?.nativeElement.focus();
  };

  private readonly handleDocumentPointerDown = (event: PointerEvent): void => {
    if (!this.isOpen()) return;
    const target = event.target as Node | null;
    if (target && !this.hostRef.nativeElement.contains(target)) {
      this.coordinator.close(this.helpId);
    }
  };

  private readonly handleDocumentClick = (event: MouseEvent): void => {
    if (!this.isOpen()) return;
    const target = event.target as Node | null;
    if (target && !this.hostRef.nativeElement.contains(target)) {
      this.coordinator.close(this.helpId);
    }
  };

  private readonly handleViewportChange = (): void => {
    if (!this.isOpen()) return;
    this.repositionPopover();
  };

  constructor() {
    effect(
      () => {
        const open = this.isOpen();
        const dialogEl = this.popoverRef()?.nativeElement;

        untracked(() => {
          if (open) {
            this.attachListeners();
            this.repositionPopover(dialogEl);
          } else {
            this.detachListeners();
          }
        });
      },
      { allowSignalWrites: true },
    );

    this.destroyRef.onDestroy(() => {
      this.detachListeners();
      this.coordinator.close(this.helpId);
    });
  }

  protected onToggle(event: MouseEvent): void {
    event.stopPropagation();
    this.coordinator.toggle(this.helpId);
  }

  protected closeAndRestoreFocus(): void {
    this.coordinator.close(this.helpId);
    this.triggerRef()?.nativeElement.focus();
  }

  protected closeFromBackdrop(): void {
    this.coordinator.close(this.helpId);
  }

  private attachListeners(): void {
    if (this.listenersAttached) return;
    this.listenersAttached = true;
    this.document.addEventListener('keydown', this.handleDocumentKeydown);
    this.document.addEventListener('pointerdown', this.handleDocumentPointerDown);
    this.document.addEventListener('click', this.handleDocumentClick);

    const win = this.document.defaultView;
    if (win) {
      win.addEventListener('resize', this.handleViewportChange, { passive: true });
      win.addEventListener('scroll', this.handleViewportChange, { passive: true, capture: true });
    }
  }

  private detachListeners(): void {
    if (!this.listenersAttached) return;
    this.listenersAttached = false;
    this.document.removeEventListener('keydown', this.handleDocumentKeydown);
    this.document.removeEventListener('pointerdown', this.handleDocumentPointerDown);
    this.document.removeEventListener('click', this.handleDocumentClick);

    const win = this.document.defaultView;
    if (win) {
      win.removeEventListener('resize', this.handleViewportChange);
      win.removeEventListener('scroll', this.handleViewportChange, true);
    }
  }

  private repositionPopover(dialogEl: HTMLElement | undefined = this.popoverRef()?.nativeElement): void {
    const win = this.document.defaultView;
    const triggerEl = this.triggerRef()?.nativeElement;
    if (!win || !triggerEl) return;

    const isMobile =
      typeof win.matchMedia === 'function'
        ? win.matchMedia(MOBILE_MEDIA_QUERY).matches
        : win.innerWidth < MOBILE_BREAKPOINT_PX;
    this.isMobileViewport.set(isMobile);

    if (isMobile) {
      this.popoverTopPx.set(null);
      this.popoverLeftPx.set(null);
      return;
    }

    const vw = win.innerWidth || FALLBACK_VIEWPORT_WIDTH;
    const vh = win.innerHeight || FALLBACK_VIEWPORT_HEIGHT;
    const triggerRect = triggerEl.getBoundingClientRect();
    const dialogRect = dialogEl?.getBoundingClientRect();

    const width =
      dialogRect && dialogRect.width > 0
        ? dialogRect.width
        : Math.min(DESKTOP_POPOVER_MAX_WIDTH, Math.max(MIN_POPOVER_WIDTH, vw - VIEWPORT_MARGIN_PX * 2));
    const height = dialogRect && dialogRect.height > 0 ? dialogRect.height : ESTIMATED_POPOVER_HEIGHT;

    let left: number;
    switch (this.preferredAlign()) {
      case 'start':
        left = triggerRect.left;
        break;
      case 'end':
        left = triggerRect.right - width;
        break;
      default:
        left = triggerRect.left + triggerRect.width / 2 - width / 2;
        break;
    }

    const maxLeft = Math.max(VIEWPORT_MARGIN_PX, vw - width - VIEWPORT_MARGIN_PX);
    left = Math.min(Math.max(VIEWPORT_MARGIN_PX, left), maxLeft);

    const spaceBelow = vh - triggerRect.bottom - VIEWPORT_MARGIN_PX - POPOVER_GAP_PX;
    const spaceAbove = triggerRect.top - VIEWPORT_MARGIN_PX - POPOVER_GAP_PX;
    const topCandidate =
      spaceBelow >= height || spaceBelow >= spaceAbove
        ? triggerRect.bottom + POPOVER_GAP_PX
        : triggerRect.top - height - POPOVER_GAP_PX;

    const maxTop = Math.max(VIEWPORT_MARGIN_PX, vh - height - VIEWPORT_MARGIN_PX);
    const top = Math.min(Math.max(VIEWPORT_MARGIN_PX, topCandidate), maxTop);

    this.popoverTopPx.set(Math.round(top));
    this.popoverLeftPx.set(Math.round(left));
  }
}
