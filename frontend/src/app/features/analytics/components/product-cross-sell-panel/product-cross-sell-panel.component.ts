/**
 * Painel do modo "Por produto" (F-09, F-11, F-12; Design Plan §5.3 a §5.9, §6; P-061, P-065, P-066).
 * Lê o estado do `CrossSellStore` e despacha ações; estado de tela e copy vêm de `utils/cross-sell-view.ts`.
 * O formulário vira combobox de busca por código ou descrição (D-7 aprovado com DC-5).
 */
import { Component, Injector, afterNextRender, computed, effect, inject, input, output, viewChild } from '@angular/core';
import { CrossSellStore } from '../../services/cross-sell.store';
import { PRODUCT_INVALID_FORMAT_MESSAGE, resolveFieldError } from '../../utils/analytics-error';
import {
  ResultStateAction,
  buildProductState,
  currentPageOf,
  liveMessage,
  productResultTitle,
  resolveResultView,
} from '../../utils/cross-sell-view';
import { CodeSearchFormComponent } from '../code-search-form/code-search-form.component';
import { ErrorBannerComponent } from '../error-banner/error-banner.component';
import { ListPagerComponent } from '../list-pager/list-pager.component';
import { ProductRecommendationsListComponent } from '../product-recommendations-list/product-recommendations-list.component';
import { QueryContextHeaderComponent } from '../query-context-header/query-context-header.component';
import { RecommendationListSkeletonComponent } from '../recommendation-list-skeleton/recommendation-list-skeleton.component';
import { ResultStateComponent } from '../result-state/result-state.component';

@Component({
  selector: 'app-product-cross-sell-panel',
  standalone: true,
  imports: [
    CodeSearchFormComponent,
    ErrorBannerComponent,
    ListPagerComponent,
    ProductRecommendationsListComponent,
    QueryContextHeaderComponent,
    RecommendationListSkeletonComponent,
    ResultStateComponent,
  ],
  templateUrl: './product-cross-sell-panel.component.html',
  styleUrl: '../../styles/cross-sell-panel.scss',
})
export class ProductCrossSellPanelComponent {
  private readonly store = inject(CrossSellStore);
  private readonly injector = inject(Injector);
  private readonly form = viewChild.required(CodeSearchFormComponent);
  private readonly header = viewChild(QueryContextHeaderComponent);
  private focusHeadingOnResult = false;

  /** SKU vindo da URL compartilhada (D-6), só para preencher o campo. */
  readonly initialSku = input<string>('');
  /** Avisa a página para refletir o SKU na URL (D-6). */
  readonly productSearched = output<number>();

  protected readonly query = this.store.product;
  protected readonly invalidFormatMessage = PRODUCT_INVALID_FORMAT_MESSAGE;
  protected readonly kind = computed(() => {
    const response = this.query.response();
    return resolveResultView({
      status: this.query.status(),
      error: this.query.error(),
      field: 'sku',
      totalItems: response?.meta.totalItems ?? 0,
      emptyReason: null,
    });
  });
  protected readonly fieldError = computed(() => resolveFieldError(this.query.error(), 'sku'));
  protected readonly state = computed(() => {
    const response = this.query.response();
    return buildProductState({
      kind: this.kind(),
      productDescription: response?.data.produto.descricao ?? null,
      totalItems: response?.meta.totalItems ?? 0,
    });
  });
  protected readonly title = computed(() => {
    const response = this.query.response();
    return response ? productResultTitle(response.data.produto.descricao, response.meta.totalItems) : '';
  });
  protected readonly live = computed(() => {
    const response = this.query.response();
    return liveMessage(this.kind(), response?.meta.totalItems ?? 0, response?.data.produto.descricao ?? '', this.state());
  });

  constructor() {
    effect(() => {
      if (this.kind() !== 'results' || !this.focusHeadingOnResult) return;
      this.focusHeadingOnResult = false;
      afterNextRender(() => this.header()?.focusHeading(), { injector: this.injector });
    });
  }

  protected onSearch(sku: number): void {
    this.store.searchProduct(sku);
    this.productSearched.emit(sku);
  }

  protected onPageChange(page: number): void {
    this.focusHeadingOnResult = true;
    this.store.goToPage(page);
  }

  protected retry(): void {
    this.store.goToPage(currentPageOf(this.query.pageRequest()));
  }

  protected onStateAction(action: ResultStateAction): void {
    const handlers: Record<ResultStateAction, () => void> = {
      'focus-field': () => this.form().focus(),
      'new-search': () => this.form().clearAndFocus(),
      'first-page': () => this.onPageChange(1),
      retry: () => this.retry(),
    };
    handlers[action]();
  }
}
