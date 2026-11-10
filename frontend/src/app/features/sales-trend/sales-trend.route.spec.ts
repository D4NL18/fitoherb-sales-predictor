/**
 * Testes unitários da configuração de rota da Tendência de Vendas (T-19).
 * Valida lazy-loading em /tendencia-vendas antes do curinga **.
 */
import { routes } from '../../app.routes';
import { SalesTrendPageComponent } from './pages/sales-trend-page/sales-trend-page.component';

describe('SalesTrend Route Configuration (T-19)', () => {
  it('contém rota tendencia-vendas com carregamento lazy antes do curinga **', async () => {
    const trendRouteIndex = routes.findIndex((r) => r.path === 'tendencia-vendas');
    const wildcardIndex = routes.findIndex((r) => r.path === '**');

    expect(trendRouteIndex).toBeGreaterThan(-1);
    expect(wildcardIndex).toBeGreaterThan(trendRouteIndex);

    const trendRoute = routes[trendRouteIndex];
    expect(typeof trendRoute.loadComponent).toBe('function');

    const loaded = await (trendRoute.loadComponent as () => Promise<any>)();
    expect(loaded).toBe(SalesTrendPageComponent);
  });
});
