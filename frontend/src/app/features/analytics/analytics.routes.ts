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
      {
        path: 'churn',
        loadComponent: () =>
          import('./pages/churn-page/churn-page.component').then((m) => m.ChurnPageComponent),
      },
      {
        path: 'sazonalidade',
        loadComponent: () =>
          import('./pages/seasonality-page/seasonality-page.component').then((m) => m.SeasonalityPageComponent),
      },
      {
        path: 'elasticity',
        loadComponent: () =>
          import('./pages/elasticity-page/elasticity-page.component').then((m) => m.ElasticityPageComponent),
      },
      {
        path: 'canibalizacao',
        loadComponent: () =>
          import('./pages/cannibalization-page/cannibalization-page.component').then(
            (m) => m.CannibalizationPageComponent,
          ),
      },
    ],
  },
];
