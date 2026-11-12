/**
 * Página principal da aba de Sazonalidade por Produto (F1; Design Plan §4; P-106 a P-116).
 * Sem `any`, com Signals reativos, suporte a teclado e acessibilidade WCAG AA.
 */
import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ListPagerComponent } from '../../components/list-pager/list-pager.component';
import { ErrorBannerComponent } from '../../components/error-banner/error-banner.component';
import { PageRequest } from '../../models/analytics.model';
import { ConsultedProduct } from '../../models/cross-sell.model';
import {
  MonthlySeasonalityPoint,
  SeasonalityData,
  SeasonalityOrder,
  SeasonalityRankingItem,
} from '../../models/seasonality.model';
import { BrlPipe, PtDecimalPipe } from '../../pipes/pt-br-format.pipes';
import { SeasonalityService } from '../../services/seasonality.service';

@Component({
  selector: 'app-seasonality-page',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ListPagerComponent,
    ErrorBannerComponent,
    PtDecimalPipe,
    BrlPipe,
  ],
  templateUrl: './seasonality-page.component.html',
  styleUrl: './seasonality-page.component.scss',
})
export class SeasonalityPageComponent implements OnInit {
  private readonly seasonalityService = inject(SeasonalityService);

  // Estados de busca
  protected readonly searchQuery = signal<string>('');
  protected readonly isSearching = signal<boolean>(false);
  protected readonly searchResults = signal<ConsultedProduct[]>([]);
  protected readonly showSuggestions = signal<boolean>(false);

  // Estados do produto selecionado
  protected readonly selectedSku = signal<number | null>(null);
  protected readonly isLoadingProduct = signal<boolean>(false);
  protected readonly productData = signal<SeasonalityData | null>(null);
  protected readonly productError = signal<string | null>(null);

  // Estados dos rankings
  protected readonly activeRankingOrder = signal<SeasonalityOrder>('most');
  protected readonly rankingItems = signal<SeasonalityRankingItem[]>([]);
  protected readonly isLoadingRanking = signal<boolean>(false);
  protected readonly rankingError = signal<string | null>(null);
  protected readonly rankingPage = signal<number>(1);
  protected readonly rankingLimit = signal<number>(20);
  protected readonly rankingTotalItems = signal<number>(0);
  protected readonly rankingTotalPages = signal<number>(0);

  // Computed properties
  protected readonly rankingOffset = computed(
    () => (this.rankingPage() - 1) * this.rankingLimit()
  );

  protected readonly maxChartValue = computed(() => {
    const data = this.productData();
    if (!data || !data.serieMensal.length) return 1.8;
    const maxVal = Math.max(...data.serieMensal.map((p) => p.indice));
    return Math.max(1.8, Math.ceil((maxVal + 0.2) * 10) / 10);
  });

  protected readonly hasLowConfidenceExtreme = computed(() => {
    const data = this.productData();
    if (!data) return false;
    return (
      data.pico.confianca === 'BAIXA' || data.vale.confianca === 'BAIXA'
    );
  });

  ngOnInit(): void {
    this.loadRankings();
  }

  // Ações de busca de produto
  protected onSearchInput(): void {
    const q = this.searchQuery().trim();
    if (q.length < 2) {
      this.searchResults.set([]);
      this.showSuggestions.set(false);
      return;
    }

    this.isSearching.set(true);
    this.seasonalityService.searchProducts(q, { limit: 10, offset: 0 }).subscribe({
      next: (resp) => {
        this.searchResults.set(resp.data);
        this.showSuggestions.set(resp.data.length > 0);
        this.isSearching.set(false);
      },
      error: () => {
        this.searchResults.set([]);
        this.showSuggestions.set(false);
        this.isSearching.set(false);
      },
    });
  }

  protected submitSearch(): void {
    const q = this.searchQuery().trim();
    if (!q) return;

    // Se for número puro, carrega direto por SKU
    const numericSku = Number(q);
    if (!Number.isNaN(numericSku) && numericSku > 0) {
      this.selectProductBySku(numericSku);
      this.showSuggestions.set(false);
      return;
    }

    // Se houver resultados na busca, seleciona o primeiro
    const results = this.searchResults();
    if (results.length > 0) {
      this.selectProduct(results[0]);
    }
  }

  protected selectProduct(product: ConsultedProduct): void {
    this.searchQuery.set(`${product.codigo} - ${product.descricao}`);
    this.showSuggestions.set(false);
    this.selectProductBySku(product.codigo);
  }

  protected selectProductBySku(sku: number): void {
    this.selectedSku.set(sku);
    this.isLoadingProduct.set(true);
    this.productError.set(null);

    this.seasonalityService.getSeasonality(sku).subscribe({
      next: (resp) => {
        this.productData.set(resp.data);
        this.isLoadingProduct.set(false);
      },
      error: (err) => {
        this.productData.set(null);
        this.productError.set(
          err.error?.error?.message ||
            'Não foi possível carregar os dados de sazonalidade deste produto.'
        );
        this.isLoadingProduct.set(false);
      },
    });
  }

  protected clearSearch(): void {
    this.searchQuery.set('');
    this.searchResults.set([]);
    this.showSuggestions.set(false);
  }

  // Ações de ranking
  protected setRankingOrder(order: SeasonalityOrder): void {
    if (this.activeRankingOrder() === order) return;
    this.activeRankingOrder.set(order);
    this.rankingPage.set(1);
    this.loadRankings();
  }

  protected onRankingPageChange(page: number): void {
    this.rankingPage.set(page);
    this.loadRankings();
  }

  protected loadRankings(): void {
    this.isLoadingRanking.set(true);
    this.rankingError.set(null);

    const pageReq: PageRequest = {
      limit: this.rankingLimit(),
      offset: this.rankingOffset(),
    };

    this.seasonalityService
      .getRanking(this.activeRankingOrder(), pageReq)
      .subscribe({
        next: (resp) => {
          this.rankingItems.set(resp.data);
          this.rankingTotalItems.set(resp.meta.totalItems);
          this.rankingTotalPages.set(resp.meta.totalPages);
          this.isLoadingRanking.set(false);
        },
        error: (err) => {
          this.rankingItems.set([]);
          this.rankingError.set(
            err.error?.error?.message ||
              'Falha ao carregar o ranking de sazonalidade.'
          );
          this.isLoadingRanking.set(false);
        },
      });
  }

  // Utilitários de renderização de gráfico
  protected getBarHeightPercent(indice: number): number {
    const maxVal = this.maxChartValue();
    return Math.min(100, Math.max(4, Math.round((indice / maxVal) * 100)));
  }

  protected getBaselineBottomPercent(): number {
    const maxVal = this.maxChartValue();
    return Math.round((1.0 / maxVal) * 100);
  }

  protected isPeakMonth(point: MonthlySeasonalityPoint): boolean {
    const data = this.productData();
    if (!data) return false;
    const { mesInicio, mesFim } = data.pico;
    if (mesInicio <= mesFim) {
      return point.mes >= mesInicio && point.mes <= mesFim;
    }
    // Caso de transição circular dez-jan
    return point.mes >= mesInicio || point.mes <= mesFim;
  }

  protected isValleyMonth(point: MonthlySeasonalityPoint): boolean {
    const data = this.productData();
    if (!data) return false;
    const { mesInicio, mesFim } = data.vale;
    if (mesInicio <= mesFim) {
      return point.mes >= mesInicio && point.mes <= mesFim;
    }
    return point.mes >= mesInicio || point.mes <= mesFim;
  }
}
