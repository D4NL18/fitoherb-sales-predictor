/**
 * Seção "Cross-sell" de `/analytics` (F-08, F-11a; Design Plan §5.3, D-5, D-6; contrato §5).
 * Container da aba: provê o `CrossSellStore` (estado vive e morre com a página), alterna os modos sem
 * perder o estado de cada um e consulta o health ao abrir para avisar sobre o cache frio (Q-7).
 * URL (D-6): o modo produto reflete `?modo=produto&sku=`; o modo cliente só `?modo=cliente` (LGPD-09).
 */
import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AnalyticsHealthData } from '../../models/analytics.model';
import { AnalyticsService } from '../../services/analytics.service';
import { CrossSellMode, CrossSellStore } from '../../services/cross-sell.store';
import { coldCacheNotice } from '../../utils/cross-sell-view';
import { CustomerCrossSellPanelComponent } from '../../components/customer-cross-sell-panel/customer-cross-sell-panel.component';
import { ModeOption, ModeSwitchComponent } from '../../components/mode-switch/mode-switch.component';
import { ProductCrossSellPanelComponent } from '../../components/product-cross-sell-panel/product-cross-sell-panel.component';

/** Valores do query param `modo` (em português, como o resto da URL visível). */
const MODE_PARAM: Record<CrossSellMode, string> = { product: 'produto', customer: 'cliente' };
const POSITIVE_CODE_PATTERN = /^[1-9]\d*$/;
const SETTLED_STATUSES = new Set(['success', 'empty']);

@Component({
  selector: 'app-cross-sell-page',
  standalone: true,
  imports: [ModeSwitchComponent, ProductCrossSellPanelComponent, CustomerCrossSellPanelComponent],
  providers: [CrossSellStore],
  templateUrl: './cross-sell-page.component.html',
  styleUrl: './cross-sell-page.component.scss',
})
export class CrossSellPageComponent implements OnInit {
  private readonly store = inject(CrossSellStore);
  private readonly analyticsService = inject(AnalyticsService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly health = signal<AnalyticsHealthData | null>(null);
  private lastSku: number | null = null;

  protected readonly mode = this.store.mode;
  protected readonly initialSku = signal('');
  protected readonly modeOptions: ModeOption[] = [
    { mode: 'product', label: 'Por produto', tabId: 'xs-tab-product', panelId: 'xs-panel-product' },
    { mode: 'customer', label: 'Por cliente', tabId: 'xs-tab-customer', panelId: 'xs-panel-customer' },
  ];
  /**
   * Aviso de cache frio até a primeira resposta chegar em qualquer modo (F-11a). Some durante o
   * carregamento, quando o skeleton assume o mesmo aviso após 4 s (um aviso por vez, UX NB-2).
   */
  protected readonly cacheNotice = computed(() => {
    const statuses = [this.store.product.status(), this.store.customer.status()];
    const anySettled = statuses.some((status) => SETTLED_STATUSES.has(status));
    const anyLoading = statuses.includes('loading');
    return anySettled || anyLoading ? null : coldCacheNotice(this.health());
  });

  ngOnInit(): void {
    this.applyUrlState(this.route.snapshot.queryParams);
    this.loadHealth();
  }

  protected onModeChange(mode: CrossSellMode): void {
    this.store.setMode(mode);
    this.syncUrl();
  }

  protected onProductSearched(sku: number): void {
    this.lastSku = sku;
    this.syncUrl();
  }

  private applyUrlState(params: Params): void {
    if (params['modo'] === MODE_PARAM.customer) {
      this.store.setMode('customer');
      return;
    }
    const sku: unknown = params['sku'];
    if (typeof sku !== 'string' || !POSITIVE_CODE_PATTERN.test(sku)) return;
    this.lastSku = Number(sku);
    this.initialSku.set(sku);
    this.store.searchProduct(this.lastSku);
  }

  /** Reflete o modo (e só o SKU) na URL, sem novo item de histórico. O código do cliente nunca entra. */
  private syncUrl(): void {
    const isProduct = this.store.mode() === 'product';
    const queryParams: Params = { modo: MODE_PARAM[this.store.mode()] };
    if (isProduct && this.lastSku !== null) queryParams['sku'] = this.lastSku;
    void this.router.navigate([], { relativeTo: this.route, queryParams, replaceUrl: true });
  }

  private loadHealth(): void {
    this.analyticsService
      .getHealth()
      .pipe(
        map((response) => response.data),
        catchError(() => of(null)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((health) => this.health.set(health));
  }
}
