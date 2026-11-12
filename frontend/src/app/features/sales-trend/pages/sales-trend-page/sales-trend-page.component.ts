/**
 * Página principal /tendencia-vendas (P-086, Design Plan §4 e §5).
 * Único componente inteligente da feature; compõe store, toolbar, tabela/cartões, skeleton, vazios e guia de leitura.
 */
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { SalesTrendStore } from '../../services/sales-trend.store';
import { ViewportService } from '../../services/viewport.service';
import { queryParamsToState } from '../../utils/trend-url';
import { formatIsoDate } from '../../utils/pt-br-format';
import { TrendToolbarComponent } from '../../components/trend-toolbar/trend-toolbar.component';
import { TrendErrorBannerComponent } from '../../components/trend-error-banner/trend-error-banner.component';
import { TrendEmptyStateComponent } from '../../components/trend-empty-state/trend-empty-state.component';
import { TrendTableSkeletonComponent } from '../../components/trend-table-skeleton/trend-table-skeleton.component';
import { TrendTableComponent } from '../../components/trend-table/trend-table.component';
import { TrendCardListComponent } from '../../components/trend-card-list/trend-card-list.component';
import { TrendPagerComponent } from '../../components/trend-pager/trend-pager.component';
import { PeriodLegendComponent } from '../../components/period-legend/period-legend.component';
import { ReadingGuideComponent } from '../../components/reading-guide/reading-guide.component';
import { InlineNoticeComponent } from '../../components/inline-notice/inline-notice.component';
import { getDisplayErrorMessage } from '../../utils/trend-error';

@Component({
  selector: 'app-sales-trend-page',
  standalone: true,
  imports: [
    CommonModule,
    TrendToolbarComponent,
    TrendErrorBannerComponent,
    TrendEmptyStateComponent,
    TrendTableSkeletonComponent,
    TrendTableComponent,
    TrendCardListComponent,
    TrendPagerComponent,
    PeriodLegendComponent,
    ReadingGuideComponent,
    InlineNoticeComponent,
  ],
  providers: [SalesTrendStore],
  template: `
    <main class="trend-page" role="main">
      <div class="trend-container">
        <!-- Hero da Feature -->
        <header class="feature-hero">
          <div class="hero-main">
            <h1 class="hero-title">Tendência de Vendas</h1>
            <p class="hero-subtitle">
              {{ subtitleText() }}
            </p>
            <span class="hero-scope-note">
              Mostra apenas produtos ativos do catálogo atual.
            </span>
          </div>

          <div class="hero-meta">
            @if (store.currentMeta?.ultimoDiaCoberto) {
              <div class="cache-badge" title="Data do último fechamento de vendas considerado">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <span>Vendas até {{ formatIsoDate(store.currentMeta!.ultimoDiaCoberto) }}</span>
              </div>
            }
          </div>
        </header>

        <!-- Barra de Controles e Filtros -->
        <app-trend-toolbar
          [query]="store.query()"
          [meta]="store.currentMeta"
          [loading]="store.status() === 'loading'"
          (groupByChange)="store.setGroupBy($event)"
          (metricChange)="store.setMetric($event)"
          (comparisonModeChange)="store.setComparisonMode($event)"
          (baseMonthChange)="store.setBaseMonth($event)"
          (searchChange)="store.setSearch($event)"
          (minVolumeChange)="store.setMinVolume($event)"
          (clearFilters)="onClearFilters()"
        />

        <!-- Aviso de carregamento lento / aquecimento de cache -->
        @if (store.isSlowLoading()) {
          <app-inline-notice
            tone="info"
            text="Carregando dados históricos agregados de vendas. Isso pode levar alguns segundos na primeira consulta."
          />
        }

        <!-- Alerta de Erro de Comunicação -->
        @if (store.status() === 'error') {
          <app-trend-error-banner
            [message]="errorMessage()"
            (retry)="store.retry()"
          />
        }

        <!-- Skeleton Loader de Carga -->
        @if (store.status() === 'loading' && !hasData()) {
          <app-trend-table-skeleton
            [variant]="viewport.isCompact() ? 'cards' : 'table'"
            [rows]="10"
          />
        }

        <!-- Estado Vazio -->
        @if (store.status() === 'empty') {
          <app-trend-empty-state
            title="Nenhum item encontrado"
            description="Não encontramos nenhum produto ou fornecedor ativo com movimentação para os filtros selecionados."
            actionLabel="Limpar filtros"
            (action)="onClearFilters()"
          />
        }

        <!-- Tabela Ledger (Desktop/Tablet >= 768px) -->
        @if (hasData() && !viewport.isCompact()) {
          <app-trend-table
            [columns]="columns()"
            [rows]="tableRows()"
            [groupBy]="store.query().groupBy || 'product'"
            [metric]="store.query().metric || 'revenue'"
            [comparisonMode]="store.query().comparisonMode || 'point'"
            [sortWindow]="store.query().sortWindow || 3"
            [sortDir]="store.query().sortDir || 'desc'"
            [params]="store.currentMeta?.parametros"
            [expandedKeys]="expandedKeysSet()"
            [details]="store.expandedSuppliers()"
            [totalRow]="store.currentMeta?.total || null"
            (sort)="store.setSort($event)"
            (toggleRow)="onToggleRow($event)"
            (detailSortChange)="onDetailSort($event)"
            (detailPageChange)="onDetailPage($event)"
            (detailRetry)="store.loadSupplierProducts($event)"
          />
        }

        <!-- Lista em Cartões (Mobile < 768px) -->
        @if (hasData() && viewport.isCompact()) {
          <app-trend-card-list
            [items]="tableRows()"
            [metric]="store.query().metric || 'revenue'"
            [sortWindow]="store.query().sortWindow || 3"
            [sortDir]="store.query().sortDir || 'desc'"
            [windowMetas]="columns()"
            [params]="store.currentMeta?.parametros"
            [expandedKeys]="expandedKeysSet()"
            (sortChange)="onMobileSort($event)"
            (toggleRow)="onToggleRow($event)"
          />
        }

        <!-- Paginação Principal -->
        @if (hasData() && (store.currentMeta?.totalPages || 0) > 1) {
          <app-trend-pager
            [page]="store.currentMeta!.page"
            [totalPages]="store.currentMeta!.totalPages"
            [totalItems]="store.currentMeta!.totalItems"
            [offset]="store.currentMeta!.offset"
            [limit]="store.currentMeta!.limit"
            [disabled]="store.status() === 'loading'"
            (pageChange)="store.setPage($event)"
          />
        }

        <!-- Legenda de Períodos e Guia de Leitura -->
        @if (hasData()) {
          <app-period-legend
            [windows]="columns()"
            [metric]="store.query().metric || 'revenue'"
            [comparisonMode]="store.query().comparisonMode || 'point'"
            [lastCoveredDay]="store.currentMeta?.ultimoDiaCoberto || null"
          />
        }

        <app-reading-guide />

        <!-- Região viva acessível para leitores de tela -->
        <div class="sr-only" aria-live="polite" aria-atomic="true">
          {{ liveRegionText() }}
        </div>
      </div>
    </main>
  `,
  styles: [`
    .trend-page {
      padding: var(--space-5, 20px) var(--space-4, 16px);
      background-color: var(--bg-canvas);
      min-height: calc(100vh - var(--navbar-height, 64px));
    }

    .trend-container {
      max-width: 1600px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: var(--space-5, 20px);
    }

    .feature-hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: var(--space-4, 16px);
      padding: var(--space-5, 20px) var(--space-6, 24px);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-default);
      border-top: 3px solid var(--brand-primary);
      border-radius: var(--radius-sm);
      box-shadow: var(--shadow-xs);
    }

    .hero-main {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .hero-title {
      font-size: 1.75rem;
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.01em;
      margin: 0;
    }

    .hero-subtitle {
      font-size: 0.9375rem;
      color: var(--text-secondary);
      margin: 0;
    }

    .hero-scope-note {
      font-size: 0.8125rem;
      color: var(--text-muted);
      margin-top: 2px;
    }

    .cache-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      background-color: var(--bg-subtle);
      border: 1px solid var(--border-default);
      border-radius: var(--radius-xs);
      font-family: var(--font-family-mono);
      font-size: 0.8125rem;
      color: var(--text-secondary);
      white-space: nowrap;
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      border: 0;
    }
  `],
})
export class SalesTrendPageComponent implements OnInit {
  readonly store = inject(SalesTrendStore);
  readonly viewport = inject(ViewportService);
  private readonly route = inject(ActivatedRoute);

  formatIsoDate = formatIsoDate;

  // Set local para controle de linhas de produto expandidas
  readonly expandedProductSkus = signal<Set<string | number>>(new Set());

  ngOnInit(): void {
    const params = queryParamsToState(this.route.snapshot.queryParams);
    this.store.init(params);
  }

  readonly subtitleText = computed(() => {
    return 'Identifique o que subiu e o que caiu nas vendas nas janelas de 1, 3, 6 e 12 meses.';
  });

  readonly columns = computed(() => this.store.currentMeta?.janelas || []);

  readonly tableRows = computed(() => {
    if (this.store.query().groupBy === 'supplier') {
      return this.store.supplierResponse()?.data || [];
    }
    return this.store.productResponse()?.data || [];
  });

  readonly hasData = computed(() => this.tableRows().length > 0);

  readonly errorMessage = computed(() => getDisplayErrorMessage(this.store.error()));

  readonly expandedKeysSet = computed(() => {
    if (this.store.query().groupBy === 'supplier') {
      return new Set(this.store.expandedSuppliers().keys());
    }
    return this.expandedProductSkus();
  });

  readonly liveRegionText = computed(() => {
    const s = this.store.status();
    if (s === 'loading') return 'Carregando dados da tendência...';
    if (s === 'error') return this.errorMessage();
    if (s === 'empty') return 'Nenhum item encontrado para os filtros informados.';
    if (s === 'success') {
      const total = this.store.currentMeta?.totalItems || 0;
      return `Carregados ${total} itens na tabela de tendência.`;
    }
    return '';
  });

  onToggleRow(key: string | number): void {
    if (this.store.query().groupBy === 'supplier') {
      this.store.toggleSupplier(key.toString());
    } else {
      const next = new Set(this.expandedProductSkus());
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      this.expandedProductSkus.set(next);
    }
  }

  onDetailSort(event: { supplierKey: string; sortBy: any }): void {
    this.store.setSupplierSort(event.supplierKey, event.sortBy);
  }

  onDetailPage(event: { supplierKey: string; page: number }): void {
    this.store.setSupplierPage(event.supplierKey, event.page);
  }

  onMobileSort(event: { window: any; dir: any }): void {
    this.store.setSort(event.window, event.dir);
  }

  onClearFilters(): void {
    this.store.setSearch(undefined);
    this.store.setMinVolume(0);
    this.store.setView('all');
  }
}
