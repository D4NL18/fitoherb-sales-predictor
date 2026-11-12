/**
 * Estado informativo da área de resultado: inicial, vazios e dados insuficientes (Design Plan §6.3, §6.4).
 * Burro: recebe o conteúdo pronto (`utils/cross-sell-view.ts`) e emite a ação; nunca é um erro técnico.
 */
import { Component, input, output } from '@angular/core';
import { ResultStateAction, ResultStateView } from '../../utils/cross-sell-view';

@Component({
  selector: 'app-result-state',
  standalone: true,
  templateUrl: './result-state.component.html',
  styleUrl: './result-state.component.scss',
})
export class ResultStateComponent {
  readonly view = input.required<ResultStateView>();
  readonly action = output<ResultStateAction>();
}
