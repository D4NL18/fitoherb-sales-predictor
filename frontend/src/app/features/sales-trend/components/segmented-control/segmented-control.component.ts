/**
 * Controle segmentado acessível com teclado (radiogroup, roving tabindex, setas ←/→ e Home/End).
 * Suporta modos 'segmented' (agrupado) e 'chips' (botões soltos com contador).
 */
import { ChangeDetectionStrategy, Component, ElementRef, computed, input, output, viewChildren } from '@angular/core';
import { CommonModule } from '@angular/common';

export interface SegmentOption<T = string> {
  value: T;
  label: string;
  count?: number;
  disabled?: boolean;
}

@Component({
  selector: 'app-segmented-control',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="segment-group"
      [class.chips-mode]="appearance() === 'chips'"
      role="radiogroup"
      [attr.aria-label]="label() || 'Opções'"
    >
      @for (opt of options(); track opt.value; let idx = $index) {
        <button
          #buttonRef
          type="button"
          class="segment-item"
          role="radio"
          [attr.aria-checked]="opt.value === value()"
          [attr.tabindex]="idx === activeTabIndex() ? 0 : -1"
          [disabled]="opt.disabled"
          (click)="select(opt.value)"
          (keydown)="onKeyDown($event, idx)"
        >
          <span class="segment-label">{{ opt.label }}</span>
          @if (opt.count !== undefined) {
            <span class="segment-count">({{ opt.count }})</span>
          }
        </button>
      }
    </div>
  `,
  styles: [`
    .segment-group {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      max-width: 100%;
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      padding: 2px;
      gap: 2px;
    }

    .segment-group.chips-mode {
      background: transparent;
      border: none;
      padding: 0;
      gap: var(--space-2);

      .segment-item {
        border: 1px solid var(--border-default);
        border-radius: var(--radius-xs);
        background-color: var(--bg-surface);

        &[aria-checked="true"] {
          background-color: var(--brand-primary);
          border-color: var(--brand-primary-active);
          color: var(--text-on-brand);
        }
      }
    }

    .segment-item {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      min-height: 40px;
      padding: var(--space-1) var(--space-3);
      background-color: transparent;
      border: none;
      border-radius: var(--radius-xs);
      color: var(--text-secondary);
      font-family: var(--font-family-body);
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: background-color var(--transition-fast), color var(--transition-fast);

      &:hover:not([aria-checked="true"]):not(:disabled) {
        background-color: var(--bg-subtle);
        color: var(--text-primary);
      }

      &[aria-checked="true"] {
        background-color: var(--brand-primary);
        color: var(--text-on-brand);
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

    .segment-count {
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;
      opacity: 0.92;
    }

    @media (max-width: 639.98px) {
      .segment-group {
        display: flex;
        width: 100%;
      }

      .segment-item {
        flex: 1 1 auto;
        white-space: normal;
        text-align: center;
      }
    }
  `],
})
export class SegmentedControlComponent<T = string> {
  readonly label = input<string>('');
  readonly options = input.required<SegmentOption<T>[]>();
  readonly value = input.required<T>();
  readonly appearance = input<'segmented' | 'chips'>('segmented');

  readonly valueChange = output<T>();

  private readonly buttons = viewChildren<ElementRef<HTMLButtonElement>>('buttonRef');

  readonly activeTabIndex = computed(() => {
    const opts = this.options();
    if (!opts.length) {
      return -1;
    }
    const matched = opts.findIndex((o) => o.value === this.value() && !o.disabled);
    if (matched >= 0) {
      return matched;
    }
    return opts.findIndex((o) => !o.disabled);
  });

  select(val: T): void {
    if (val !== this.value()) {
      this.valueChange.emit(val);
    }
  }

  onKeyDown(event: KeyboardEvent, currentIndex: number): void {
    const opts = this.options();
    if (!opts.length) {
      return;
    }

    let step = 0;
    let targetIndex = -1;

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      step = 1;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      step = -1;
    } else if (event.key === 'Home') {
      event.preventDefault();
      targetIndex = opts.findIndex((o) => !o.disabled);
    } else if (event.key === 'End') {
      event.preventDefault();
      for (let i = opts.length - 1; i >= 0; i--) {
        if (!opts[i].disabled) {
          targetIndex = i;
          break;
        }
      }
    }

    if (step !== 0) {
      for (let offset = 1; offset <= opts.length; offset++) {
        const candidate = (currentIndex + step * offset + opts.length) % opts.length;
        if (!opts[candidate].disabled) {
          targetIndex = candidate;
          break;
        }
      }
    }

    if (targetIndex >= 0 && !opts[targetIndex].disabled) {
      this.select(opts[targetIndex].value);
      const btnList = this.buttons();
      btnList[targetIndex]?.nativeElement.focus();
    }
  }
}
