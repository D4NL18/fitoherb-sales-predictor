/**
 * Casca de `/analytics` (F-05; Design Plan §5.2, D-3, D-4): cabeçalho da página, navegação de seções
 * por links (`aria-current`) e `<router-outlet>`. Cada nova análise acrescenta só uma entrada em
 * `ANALYTICS_SECTIONS` e uma rota filha; seções futuras não aparecem como "em breve".
 */
import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

/** Seção (aba) do módulo Analytics. */
export interface AnalyticsSection {
  label: string;
  path: string;
  description: string;
}

/** Seções disponíveis nesta fase, na ordem do roadmap. */
export const ANALYTICS_SECTIONS: readonly AnalyticsSection[] = [
  {
    label: 'Cross-sell',
    path: '/analytics/cross-sell',
    description: 'O que oferecer junto com um produto ou a um cliente',
  },
];

@Component({
  selector: 'app-analytics-shell',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  templateUrl: './analytics-shell.component.html',
  styleUrl: './analytics-shell.component.scss',
})
export class AnalyticsShellComponent {
  protected readonly sections = ANALYTICS_SECTIONS;
}
