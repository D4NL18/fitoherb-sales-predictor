/**
 * Controle segmentado "Por produto · Por cliente" com padrão ARIA de abas (Design Plan §5.3, D-5, §7.1).
 * Burro: roving tabindex, setas ←/→ alternam e ativam, Home/End vão aos extremos; emite o modo escolhido.
 */
import { Component, ElementRef, input, output, viewChildren } from '@angular/core';
import { CrossSellMode } from '../../services/cross-sell.store';

/** Segmento do controle, com os ids do tab e do painel controlado. */
export interface ModeOption {
  mode: CrossSellMode;
  label: string;
  tabId: string;
  panelId: string;
}

@Component({
  selector: 'app-mode-switch',
  standalone: true,
  templateUrl: './mode-switch.component.html',
  styleUrl: './mode-switch.component.scss',
})
export class ModeSwitchComponent {
  private readonly tabs = viewChildren<ElementRef<HTMLButtonElement>>('tab');

  readonly options = input.required<ModeOption[]>();
  readonly mode = input.required<CrossSellMode>();
  readonly modeChange = output<CrossSellMode>();

  protected onKeydown(event: KeyboardEvent, index: number): void {
    const target = this.targetIndex(event.key, index);
    if (target === null) return;
    event.preventDefault();
    this.select(target);
    this.tabs()[target]?.nativeElement.focus();
  }

  protected select(index: number): void {
    const option = this.options()[index];
    if (option && option.mode !== this.mode()) this.modeChange.emit(option.mode);
  }

  private targetIndex(key: string, index: number): number | null {
    const last = this.options().length - 1;
    const targets: Record<string, number> = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      Home: 0,
      End: last,
    };
    return key in targets ? targets[key] : null;
  }
}
