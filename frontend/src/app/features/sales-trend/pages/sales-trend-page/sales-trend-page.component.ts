/**
 * Página principal /tendencia-vendas (P-086, Design Plan §4 e §5).
 * Único componente inteligente da feature; compõe store, toolbar, tabela/cartões, skeleton, vazios e guia de leitura.
 */
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import {
  TrendSortBy,
  TrendSortDir,
  TrendSortWindow,
} from '../../models/sales-trend.model';
import { SalesTrendStore } from '../../services/sales-trend.store';
import { ViewportService } from '../../services/viewport.service';
import { queryParamsToState } from '../../utils/trend-url';
import { formatIsoDate } from '../../utils/pt-br-format';
import { isAllSemBase } from '../../utils/trend-view';
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
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="trend-page" aria-label="Tendência de Vendas">
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

        <!-- Aviso contextual de ajuste automático de filtros ou atualização -->
        @if (store.noticeMessage()) {
          <app-inline-notice
            tone="info"
            [text]="store.noticeMessage()!"
            [dismissible]="true"
            (dismiss)="store.dismissNotice()"
          />
        }

        <!-- Aviso de mês-base parcial em curso -->
        @if (store.status() !== 'error' && store.currentMeta?.mesBaseParcial && store.currentMeta?.ultimoDiaCoberto) {
          <app-inline-notice
            tone="info"
            [text]="'Mês-base em andamento: as variações utilizam média diária acumulada até ' + formatIsoDate(store.currentMeta!.ultimoDiaCoberto) + ' comparada a período equivalente.'"
          />
        }

        <!-- Aviso quando nenhuma janela atinge 50% de base histórica -->
        @if (store.status() === 'success' && allSemBase()) {
          <app-inline-notice
            tone="warning"
            title="Base comparativa insuficiente"
            text="Nenhuma janela atingiu cobertura histórica mínima de 50% no período anterior para o mês-base selecionado."
          />
        }

        <!-- Alerta de Erro de Comunicação -->
        @if (store.status() === 'error') {
          <app-trend-error-banner
            [message]="errorMessage()"
            [secondaryActionLabel]="canResetMonthOnError() ? 'Voltar para mês padrão' : null"
            (secondaryAction)="store.resetToDefaultMonth()"
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

        <!-- Estado Vazio Contextual -->
        @if (store.status() === 'empty') {
          <app-trend-empty-state
            [title]="emptyStateTitle()"
            [description]="emptyStateDescription()"
            [actionLabel]="emptyStateActionLabel()"
            (action)="onEmptyAction()"
          />
        }

        <!-- Paginação Superior -->
        @if (canDisplayResults() && (store.currentMeta?.totalPages || 0) > 1) {
          <app-trend-pager
            ariaLabel="Paginação superior"
            [page]="store.currentMeta!.page"
            [totalPages]="store.currentMeta!.totalPages"
            [totalItems]="store.currentMeta!.totalItems"
            [offset]="store.currentMeta!.offset"
            [limit]="store.currentMeta!.limit"
            [disabled]="store.status() === 'loading'"
            (pageChange)="store.setPage($event)"
          />
        }

        <!-- Tabela Ledger (Desktop/Tablet >= 768px) -->
        @if (canDisplayResults() && !viewport.isCompact()) {
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
            [loading]="store.status() === 'loading'"
            (sort)="store.setSort($event)"
            (toggleRow)="onToggleRow($event)"
            (detailSortChange)="onDetailSort($event)"
            (detailPageChange)="onDetailPage($event)"
            (detailRetry)="store.loadSupplierProducts($event)"
          />
        }

        <!-- Lista em Cartões (Mobile < 768px) -->
        @if (canDisplayResults() && viewport.isCompact()) {
          <app-trend-card-list
            [items]="tableRows()"
            [groupBy]="store.query().groupBy || 'product'"
            [metric]="store.query().metric || 'revenue'"
            [sortWindow]="store.query().sortWindow || 3"
            [sortDir]="store.query().sortDir || 'desc'"
            [windowMetas]="columns()"
            [params]="store.currentMeta?.parametros"
            [expandedKeys]="expandedKeysSet()"
            [details]="store.expandedSuppliers()"
            [totalRow]="store.currentMeta?.total || null"
            [loading]="store.status() === 'loading'"
            (sortChange)="onMobileSort($event)"
            (toggleRow)="onToggleRow($event)"
            (detailSortChange)="onDetailSort($event)"
            (detailPageChange)="onDetailPage($event)"
            (detailRetry)="store.loadSupplierProducts($event)"
          />
        }

        <!-- Paginação Inferior -->
        @if (canDisplayResults() && (store.currentMeta?.totalPages || 0) > 1) {
          <app-trend-pager
            ariaLabel="Paginação inferior"
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
        @if (canDisplayResults()) {
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
    </section>
  `,
  styles: [`
    .trend-page {
      padding: var(--space-5) var(--space-4);
      background-color: var(--bg-canvas);
      min-height: calc(100vh - var(--navbar-height, 64px));
    }

    .trend-container {
      max-width: 1600px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: var(--space-5);
    }

    .feature-hero {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: var(--space-4);
      padding: var(--space-5) var(--space-6);
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
      color: var(--text-secondary);
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
      white-space: nowrap;
      border: 0;
    }

    @media (max-width: 639.98px) {
      .trend-page {
        padding: var(--space-3);
      }

      .feature-hero {
        padding: var(--space-4);
      }

      .hero-title {
        font-size: 1.45rem;
      }
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

  readonly allSemBase = computed(() => isAllSemBase(this.columns()));

  readonly tableRows = computed(() => {
    if (this.store.query().groupBy === 'supplier') {
      return this.store.supplierResponse()?.data || [];
    }
    return this.store.productResponse()?.data || [];
  });

  readonly hasData = computed(() => this.tableRows().length > 0);

  readonly canDisplayResults = computed(() => this.store.status() !== 'error' && this.hasData());

  readonly errorMessage = computed(() => getDisplayErrorMessage(this.store.error()));

  readonly canResetMonthOnError = computed(() => {
    const err = this.store.error();
    return err?.code === 'TND-002' && Boolean(this.store.query().baseMonth);
  });

  readonly hasActiveFilters = computed(() => {
    const q = this.store.query();
    return Boolean(
      (q.q && q.q.trim().length > 0) ||
      (typeof q.minVolume === 'number' && q.minVolume > 0) ||
      (q.view && q.view !== 'all')
    );
  });

  readonly isPagePastEnd = computed(() => {
    const offset = this.store.query().offset ?? 0;
    const total = this.store.currentMeta?.totalItems ?? 0;
    return offset > 0 && total > 0;
  });

  readonly isNonDefaultMonth = computed(() => {
    const selected = this.store.query().baseMonth;
    const def = this.store.currentMeta?.mesBasePadrao;
    return Boolean(selected && def && selected !== def);
  });

  readonly emptyStateTitle = computed(() => {
    if (this.isPagePastEnd()) {
      return 'Página sem resultados';
    }
    if (this.hasActiveFilters()) {
      return 'Nenhum item encontrado';
    }
    return 'Sem movimentação no período';
  });

  readonly emptyStateDescription = computed(() => {
    if (this.isPagePastEnd()) {
      return 'A página informada na URL ultrapassou a quantidade disponível para os filtros atuais.';
    }
    if (this.hasActiveFilters()) {
      return 'Não encontramos nenhum produto ou fornecedor ativo com movimentação para os filtros selecionados.';
    }
    return 'Não há vendas registradas para produtos ativos do catálogo no mês-base selecionado.';
  });

  readonly emptyStateActionLabel = computed(() => {
    if (this.isPagePastEnd()) {
      return 'Voltar para a primeira página';
    }
    if (this.hasActiveFilters()) {
      return 'Limpar filtros';
    }
    if (this.isNonDefaultMonth()) {
      return 'Voltar para mês padrão';
    }
    return null;
  });

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
    if (s === 'empty') return this.emptyStateDescription();
    if (s === 'success') {
      const meta = this.store.currentMeta;
      const total = meta?.totalItems ?? 0;
      const page = meta?.page ?? 1;
      const totalPages = meta?.totalPages ?? 1;
      const groupLabel = this.store.query().groupBy === 'supplier' ? 'fornecedores' : 'produtos';
      const sortWindow = this.store.query().sortWindow || 3;
      const sortDir = this.store.query().sortDir === 'asc' ? 'crescente' : 'decrescente';
      return `Carregados ${total} ${groupLabel}, ordenados por ${sortWindow} ${sortWindow === 1 ? 'mês' : 'meses'} em ordem ${sortDir}. Página ${page} de ${Math.max(1, totalPages)}.`;
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

  onDetailSort(event: { supplierKey: string; sortBy: TrendSortBy }): void {
    this.store.setSupplierSort(event.supplierKey, event.sortBy);
  }

  onDetailPage(event: { supplierKey: string; page: number }): void {
    this.store.setSupplierPage(event.supplierKey, event.page);
  }

  onMobileSort(event: { window: TrendSortWindow; dir: TrendSortDir }): void {
    this.store.setSort(event.window, event.dir);
  }

  onClearFilters(): void {
    this.store.clearFilters();
  }

  onEmptyAction(): void {
    if (this.isPagePastEnd()) {
      this.store.setPage(1);
      return;
    }
    if (this.hasActiveFilters()) {
      this.onClearFilters();
      return;
    }
    if (this.isNonDefaultMonth()) {
      this.store.resetToDefaultMonth();
    }
  }
}
