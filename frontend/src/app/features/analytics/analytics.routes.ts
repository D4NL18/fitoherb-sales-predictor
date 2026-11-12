/**
 * Rotas filhas de `/analytics`, carregadas por `loadChildren` (F-04; Design Plan §5.2, D-3).
 * A casca fica fixa e cada seção é uma rota filha lazy; `/analytics` redireciona para a primeira seção.
 */
import { Routes } from '@angular/router';
import { AnalyticsShellComponent } from './pages/analytics-shell/analytics-shell.component';

export const ANALYTICS_ROUTES: Routes = [
  {
    path: '',
    component: AnalyticsShellComponent,
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'cross-sell' },
      {
        path: 'cross-sell',
        loadComponent: () =>
          import('./pages/cross-sell-page/cross-sell-page.component').then((m) => m.CrossSellPageComponent),
      },
    ],
  },
];
