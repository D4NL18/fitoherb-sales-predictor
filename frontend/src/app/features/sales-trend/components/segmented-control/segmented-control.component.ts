/**
 * Controle segmentado acessível com teclado (radiogroup, roving tabindex, setas ←/→ e Home/End).
 * Suporta modos 'segmented' (agrupado) e 'chips' (botões soltos com contador).
 */
import { Component, ElementRef, input, output, viewChildren } from '@angular/core';
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
  template: `
    <div
      class="segment-group"
      [class.chips-mode]="appearance() === 'chips'"
      role="radiogroup"
      [attr.aria-label]="label()"
    >
      @for (opt of options(); track opt.value; let idx = $index) {
        <button
          #buttonRef
          type="button"
          class="segment-item"
          role="radio"
          [attr.aria-checked]="opt.value === value()"
          [attr.tabindex]="opt.value === value() ? 0 : -1"
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
      gap: var(--space-2, 8px);
      flex-wrap: wrap;

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
      min-height: 36px;
      padding: var(--space-1, 4px) var(--space-3, 12px);
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
        outline-offset: 1px;
      }

      &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
    }

    .segment-count {
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;
      opacity: 0.9;
    }
  `],
})
export class SegmentedControlComponent<T = any> {
  readonly label = input<string>('');
  readonly options = input.required<SegmentOption<T>[]>();
  readonly value = input.required<T>();
  readonly appearance = input<'segmented' | 'chips'>('segmented');

  readonly valueChange = output<T>();

  private readonly buttons = viewChildren<ElementRef<HTMLButtonElement>>('buttonRef');

  select(val: T): void {
    if (val !== this.value()) {
      this.valueChange.emit(val);
    }
  }

  onKeyDown(event: KeyboardEvent, currentIndex: number): void {
    const opts = this.options();
    let targetIndex = -1;

    if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
      event.preventDefault();
      targetIndex = (currentIndex + 1) % opts.length;
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
      event.preventDefault();
      targetIndex = (currentIndex - 1 + opts.length) % opts.length;
    } else if (event.key === 'Home') {
      event.preventDefault();
      targetIndex = 0;
    } else if (event.key === 'End') {
      event.preventDefault();
      targetIndex = opts.length - 1;
    }

    if (targetIndex >= 0 && !opts[targetIndex].disabled) {
      this.select(opts[targetIndex].value);
      const btnList = this.buttons();
      if (btnList && btnList[targetIndex]) {
        btnList[targetIndex].nativeElement.focus();
      }
    }
  }
}
