/**
 * Estado da aba Cross-sell com signals, um bloco por modo (F-07; Design Plan §4, D-5).
 * Só orquestra chamadas: `idle -> loading -> success | empty | error`, paginação no servidor (P-066)
 * e "nova busca reinicia a página". Sem regra de negócio: ordem, filtros e pontuação vêm da API.
 * LGPD-09: o último código consultado fica só em memória (nada de storage, URL ou log).
 * Escopo: provido pela página `CrossSellPageComponent`, morre com ela.
 */
import { Injectable, OnDestroy, Signal, inject, signal } from '@angular/core';
import { Observable, Subscription } from 'rxjs';
import { AnalyticsApiError, DEFAULT_PAGE_LIMIT, PageRequest } from '../models/analytics.model';
import { CustomerCrossSellResponse, ProductCrossSellResponse } from '../models/cross-sell.model';
import { toAnalyticsApiError } from '../utils/analytics-error';
import { AnalyticsService } from './analytics.service';

export type CrossSellMode = 'product' | 'customer';

export type QueryStatus = 'idle' | 'loading' | 'success' | 'empty' | 'error';

/** Visão somente leitura do estado de um modo. `error() === null` com status `error` = falha técnica genérica. */
export interface ModeQueryState<TResponse> {
  status: Signal<QueryStatus>;
  response: Signal<TResponse | null>;
  error: Signal<AnalyticsApiError | null>;
  pageRequest: Signal<PageRequest>;
}

type Fetcher<TResponse> = (term: number, page: PageRequest) => Observable<TResponse>;

interface ListResponse {
  data: { recomendacoes: readonly unknown[] };
}

const FIRST_PAGE: PageRequest = { limit: DEFAULT_PAGE_LIMIT, offset: 0 };

/** Consulta paginada de um modo: guarda o último termo e cancela a requisição anterior ao disparar outra. */
class ModeQuery<TResponse extends ListResponse> {
  private readonly statusState = signal<QueryStatus>('idle');
  private readonly responseState = signal<TResponse | null>(null);
  private readonly errorState = signal<AnalyticsApiError | null>(null);
  private readonly pageRequestState = signal<PageRequest>(FIRST_PAGE);
  private term: number | null = null;
  private inFlight: Subscription | null = null;

  readonly state: ModeQueryState<TResponse> = {
    status: this.statusState.asReadonly(),
    response: this.responseState.asReadonly(),
    error: this.errorState.asReadonly(),
    pageRequest: this.pageRequestState.asReadonly(),
  };

  constructor(private readonly fetch: Fetcher<TResponse>) {}

  /** Nova busca: troca o termo, descarta o resultado anterior e volta à primeira página. */
  search(term: number): void {
    this.term = term;
    this.responseState.set(null);
    this.run(FIRST_PAGE);
  }

  /** Página 1-based sobre o último termo; sem busca anterior não faz nada. */
  goToPage(page: number): void {
    if (this.term === null || page < 1) return;
    const { limit } = this.pageRequestState();
    this.run({ limit, offset: (page - 1) * limit });
  }

  dispose(): void {
    this.inFlight?.unsubscribe();
  }

  private run(pageRequest: PageRequest): void {
    if (this.term === null) return;
    this.inFlight?.unsubscribe();
    this.pageRequestState.set(pageRequest);
    this.errorState.set(null);
    this.statusState.set('loading');
    this.inFlight = this.fetch(this.term, pageRequest).subscribe({
      next: (response) => this.handleSuccess(response),
      error: (err: unknown) => this.handleError(err),
    });
  }

  private handleSuccess(response: TResponse): void {
    this.responseState.set(response);
    this.statusState.set(response.data.recomendacoes.length === 0 ? 'empty' : 'success');
  }

  private handleError(err: unknown): void {
    this.errorState.set(toAnalyticsApiError(err));
    this.statusState.set('error');
  }
}

@Injectable()
export class CrossSellStore implements OnDestroy {
  private readonly service = inject(AnalyticsService);
  private readonly modeState = signal<CrossSellMode>('product');
  private readonly productQuery = new ModeQuery<ProductCrossSellResponse>((sku, page) =>
    this.service.getProductCrossSell(sku, page),
  );
  private readonly customerQuery = new ModeQuery<CustomerCrossSellResponse>((code, page) =>
    this.service.getCustomerCrossSell(code, page),
  );

  readonly mode = this.modeState.asReadonly();
  readonly product = this.productQuery.state;
  readonly customer = this.customerQuery.state;

  setMode(mode: CrossSellMode): void {
    this.modeState.set(mode);
  }

  searchProduct(sku: number): void {
    this.productQuery.search(sku);
  }

  searchCustomer(customerCode: number): void {
    this.customerQuery.search(customerCode);
  }

  /** Troca de página no modo ativo, reaproveitando o último termo dele. */
  goToPage(page: number): void {
    const query = this.modeState() === 'product' ? this.productQuery : this.customerQuery;
    query.goToPage(page);
  }

  ngOnDestroy(): void {
    this.productQuery.dispose();
    this.customerQuery.dispose();
  }
}
