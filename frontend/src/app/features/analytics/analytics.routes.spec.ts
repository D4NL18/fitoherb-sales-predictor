/**
 * T-15 — Rota lazy `/analytics` (F-04, F-05; Design Plan §5.2, D-3).
 * `/analytics` carrega por `loadChildren` e redireciona para a seção `cross-sell`, com nav de links.
 */
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { routes } from '../../app.routes';
import { ANALYTICS_ROUTES } from './analytics.routes';
import { AnalyticsShellComponent } from './pages/analytics-shell/analytics-shell.component';

describe('Rotas do módulo Analytics', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('app.routes registra /analytics como lazy (loadChildren) antes do coringa', () => {
    const index = routes.findIndex((route) => route.path === 'analytics');
    const wildcard = routes.findIndex((route) => route.path === '**');

    expect(index).toBeGreaterThanOrEqual(0);
    expect(routes[index].loadChildren).toBeDefined();
    expect(routes[index].component).toBeUndefined();
    expect(index).toBeLessThan(wildcard);
  });

  it('ANALYTICS_ROUTES usa o shell com filho padrão cross-sell', () => {
    const shell = ANALYTICS_ROUTES.find((route) => route.component === AnalyticsShellComponent);
    expect(shell).toBeDefined();
    const children = shell?.children ?? [];
    expect(children.some((child) => child.path === 'cross-sell')).toBeTrue();
    expect(children.some((child) => child.path === '' && child.redirectTo === 'cross-sell')).toBeTrue();
  });

  it('navegar para /analytics carrega o módulo e redireciona para /analytics/cross-sell', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/analytics');

    expect(TestBed.inject(Router).url).toBe('/analytics/cross-sell');
    const nav = harness.routeNativeElement?.querySelector('nav[aria-label="Seções de análise"]');
    expect(nav).not.toBeNull();
    const active = nav?.querySelector('a[aria-current="page"]');
    expect(active?.textContent).toContain('Cross-sell');
    expect(active?.getAttribute('href')).toBe('/analytics/cross-sell');
  });

  it('o código do cliente nunca vai para a URL da SPA (D-6, LGPD-09)', async () => {
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/analytics/cross-sell?modo=cliente');

    expect(TestBed.inject(Router).url).not.toMatch(/customerCode|cliente=\d/);
  });
});
