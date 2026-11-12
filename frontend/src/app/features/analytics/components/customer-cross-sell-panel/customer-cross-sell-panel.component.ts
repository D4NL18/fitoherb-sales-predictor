/**
 * Painel do modo "Por cliente" (F-10, F-11, F-11a; Design Plan §5.3 a §5.9, §6; P-062 a P-066, P-070).
 * Lê o estado do `CrossSellStore` e despacha ações. LGPD-09: o código consultado fica só em memória
 * (sinal local, para a copy) e nunca vai para URL, storage ou log; a API não o ecoa na resposta.
 */
import { Component, Injector, afterNextRender, computed, effect, inject, signal, viewChild } from '@angular/core';
import { CrossSellStore } from '../../services/cross-sell.store';
import { resolveFieldError } from '../../utils/analytics-error';
import {
  ResultStateAction,
  buildCustomerState,
  currentPageOf,
  customerResultSubtitle,
  customerResultTitle,
  liveMessage,
  resolveResultView,
} from '../../utils/cross-sell-view';
import { CodeSearchFormComponent } from '../code-search-form/code-search-form.component';
import { CustomerRecommendationsListComponent } from '../customer-recommendations-list/customer-recommendations-list.component';
import { ErrorBannerComponent } from '../error-banner/error-banner.component';
import { ListPagerComponent } from '../list-pager/list-pager.component';
import { QueryContextHeaderComponent } from '../query-context-header/query-context-header.component';
import { RecommendationListSkeletonComponent } from '../recommendation-list-skeleton/recommendation-list-skeleton.component';
import { ResultStateComponent } from '../result-state/result-state.component';

@Component({
  selector: 'app-customer-cross-sell-panel',
  standalone: true,
  imports: [
    CodeSearchFormComponent,
    CustomerRecommendationsListComponent,
    ErrorBannerComponent,
    ListPagerComponent,
    QueryContextHeaderComponent,
    RecommendationListSkeletonComponent,
    ResultStateComponent,
  ],
  templateUrl: './customer-cross-sell-panel.component.html',
  styleUrl: '../../styles/cross-sell-panel.scss',
})
export class CustomerCrossSellPanelComponent {
  private readonly store = inject(CrossSellStore);
  private readonly injector = inject(Injector);
  private readonly form = viewChild.required(CodeSearchFormComponent);
  private readonly header = viewChild(QueryContextHeaderComponent);
  private focusHeadingOnResult = false;

  protected readonly query = this.store.customer;
  /** Último código enviado, só em memória (LGPD-09). */
  protected readonly customerCode = signal<number | null>(null);

  protected readonly kind = computed(() => {
    const response = this.query.response();
    return resolveResultView({
      status: this.query.status(),
      error: this.query.error(),
      field: 'customerCode',
      totalItems: response?.meta.totalItems ?? 0,
      emptyReason: response?.meta.motivoVazio ?? null,
    });
  });
  protected readonly fieldError = computed(() => resolveFieldError(this.query.error(), 'customerCode'));
  protected readonly state = computed(() => {
    const response = this.query.response();
    return buildCustomerState({
      kind: this.kind(),
      customerCode: this.customerCode(),
      totalItems: response?.meta.totalItems ?? 0,
      parameters: response?.meta.parametros ?? null,
    });
  });
  protected readonly title = computed(() =>
    customerResultTitle(this.customerCode(), this.query.response()?.meta.totalItems ?? 0),
  );
  protected readonly subtitle = computed(() => {
    const parameters = this.query.response()?.meta.parametros;
    return parameters ? customerResultSubtitle(parameters) : '';
  });
  protected readonly live = computed(() => {
    const code = this.customerCode();
    const target = code === null ? 'este cliente' : `o cliente ${code}`;
    return liveMessage(this.kind(), this.query.response()?.meta.totalItems ?? 0, target, this.state());
  });

  constructor() {
    effect(() => {
      if (this.kind() !== 'results' || !this.focusHeadingOnResult) return;
      this.focusHeadingOnResult = false;
      afterNextRender(() => this.header()?.focusHeading(), { injector: this.injector });
    });
  }

  protected onSearch(customerCode: number): void {
    this.customerCode.set(customerCode);
    this.store.searchCustomer(customerCode);
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
