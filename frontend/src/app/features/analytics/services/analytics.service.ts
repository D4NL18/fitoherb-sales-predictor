/**
 * Cliente HTTP do módulo Analytics Comercial (contrato analytics-cross-sell 1.1.0, §5).
 * Devolve o envelope completo (`data` + `meta`); a conversão de erro fica em `utils/analytics-error.ts`.
 * LGPD-07/09: o código do cliente vai só no path da API; nada de storage, URL da SPA ou `console.log`.
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, catchError, shareReplay, throwError } from 'rxjs';
import { AnalyticsHealthResponse, PageRequest } from '../models/analytics.model';
import {
  ChurnCustomersResponse,
  ChurnFilterOptionsResponse,
  ChurnQueryOptions,
  CustomerChurnDetailResponse,
  InactiveChurnResponse,
} from '../models/churn.model';
import {
  ElasticitySimulationRequest,
  ElasticitySimulationResponse,
  ProductElasticityResponse,
} from '../models/elasticity.models';
import {
  CatalogListResponse,
  CustomerCrossSellResponse,
  ProductCrossSellResponse,
  ProductSearchResponse,
} from '../models/cross-sell.model';
import {
  NewProductForecastRequest,
  NewProductForecastResponse,
  NewProductOptionsResponse,
} from '../models/new-product.model';

export interface CatalogProductsOptions {
  includeSeasonality?: boolean;
}

@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/analytics';
  private basicCatalogCache$: Observable<CatalogListResponse> | null = null;
  private seasonalCatalogCache$: Observable<CatalogListResponse> | null = null;

  /**
   * Catálogo completo em memória com `shareReplay(1)`; mantém caches separados para o catálogo
   * básico vs. enriquecido com sazonalidade, invalidando automaticamente em caso de erro.
   */
  getCatalogProducts(options?: CatalogProductsOptions): Observable<CatalogListResponse> {
    const includeSeasonality = options?.includeSeasonality === true;
    const cached$ = includeSeasonality ? this.seasonalCatalogCache$ : this.basicCatalogCache$;
    if (cached$) {
      return cached$;
    }

    const request$ = (
      includeSeasonality
        ? this.http.get<CatalogListResponse>(`${this.baseUrl}/products`, {
            params: new HttpParams().set('includeSeasonality', 'true'),
          })
        : this.http.get<CatalogListResponse>(`${this.baseUrl}/products`)
    ).pipe(
      catchError((err: unknown) => {
        if (includeSeasonality) {
          this.seasonalCatalogCache$ = null;
        } else {
          this.basicCatalogCache$ = null;
        }
        return throwError(() => err);
      }),
      shareReplay(1),
    );

    if (includeSeasonality) {
      this.seasonalCatalogCache$ = request$;
    } else {
      this.basicCatalogCache$ = request$;
    }
    return request$;
  }

  /** Estado do cache sem disparar carga (P-069, Q-7). */
  getHealth(): Observable<AnalyticsHealthResponse> {
    return this.http.get<AnalyticsHealthResponse>(`${this.baseUrl}/health`);
  }

  /** Recomendação por produto (P-061), paginada no servidor (P-066). */
  getProductCrossSell(sku: number, page: PageRequest): Observable<ProductCrossSellResponse> {
    return this.http.get<ProductCrossSellResponse>(`${this.baseUrl}/cross-sell/product/${sku}`, {
      params: toPageParams(page),
    });
  }

  /** Recomendação por cliente (P-062 a P-064); o código não vai em query nem header (LGPD-07). */
  getCustomerCrossSell(customerCode: number, page: PageRequest): Observable<CustomerCrossSellResponse> {
    return this.http.get<CustomerCrossSellResponse>(`${this.baseUrl}/cross-sell/customer/${customerCode}`, {
      params: toPageParams(page),
    });
  }

  /** Busca de produto por código ou descrição (contrato §3.6, DC-5). */
  searchProducts(query: string, page: PageRequest): Observable<ProductSearchResponse> {
    return this.http.get<ProductSearchResponse>(`${this.baseUrl}/products/search`, {
      params: toPageParams(page).set('q', query),
    });
  }

  /** Listagem priorizada de clientes por score de churn (P-123). */
  getChurnCustomers(
    status: string | null,
    page: PageRequest,
    options?: ChurnQueryOptions,
  ): Observable<ChurnCustomersResponse> {
    let params = toChurnParams(page, options);
    if (status) {
      params = params.set('status', status);
    }
    return this.http.get<ChurnCustomersResponse>(`${this.baseUrl}/churn/customers`, { params });
  }

  /** Opções de vendedores e cidades para filtros da tela de churn. */
  getChurnFilters(): Observable<ChurnFilterOptionsResponse> {
    return this.http.get<ChurnFilterOptionsResponse>(`${this.baseUrl}/churn/filters`);
  }

  /** Detalhe explicativo e diagnóstico do cliente em churn (P-126). */
  getCustomerChurnDetail(customerCode: number): Observable<CustomerChurnDetailResponse> {
    return this.http.get<CustomerChurnDetailResponse>(`${this.baseUrl}/churn/customers/${customerCode}`);
  }

  /** Fila especializada de clientes inativos antigos (P-125). */
  getInactiveChurn(page: PageRequest, options?: ChurnQueryOptions): Observable<InactiveChurnResponse> {
    return this.http.get<InactiveChurnResponse>(`${this.baseUrl}/churn/inactive`, {
      params: toChurnParams(page, options),
    });
  }

  /** Elasticidade do produto (P-096, P-103). */
  getProductElasticity(sku: number, page: PageRequest): Observable<ProductElasticityResponse> {
    return this.http.get<ProductElasticityResponse>(`${this.baseUrl}/elasticity/product/${sku}`, {
      params: toPageParams(page),
    });
  }

  /** Simulação de impacto de reajuste de preço, custo e preço atual opcionais (P-101). */
  simulatePriceChange(request: ElasticitySimulationRequest): Observable<ElasticitySimulationResponse> {
    const {
      sku,
      priceChangePct: pct,
      customerCode,
      costPrice: reqCostPrice,
      currentPrice: reqCurrentPrice,
    } = request;

    const payload: ElasticitySimulationRequest = {
      sku,
      priceChangePct: pct,
      ...(customerCode !== null && customerCode !== undefined ? { customerCode } : {}),
      ...(reqCostPrice !== null && reqCostPrice !== undefined ? { costPrice: reqCostPrice } : {}),
      ...(reqCurrentPrice !== null && reqCurrentPrice !== undefined
        ? { currentPrice: reqCurrentPrice }
        : {}),
    };
    return this.http.post<ElasticitySimulationResponse>(`${this.baseUrl}/elasticity/simulate`, payload);
  }

  /** Opções ativas de tipos e fornecedores para simulação de produto novo (P-141). */
  getNewProductOptions(): Observable<NewProductOptionsResponse> {
    return this.http.get<NewProductOptionsResponse>(`${this.baseUrl}/new-product/options`);
  }

  /** Simulação conservadora de viabilidade de produto novo sem SKU (P-140 a P-149). */
  simulateNewProductForecast(request: NewProductForecastRequest): Observable<NewProductForecastResponse> {
    const payload: NewProductForecastRequest = {
      tipo: request.tipo,
      fornecedor: request.fornecedor,
      descricao: request.descricao,
      precoVendaPrevisto: request.precoVendaPrevisto,
      ...(request.custoUnitario !== null && request.custoUnitario !== undefined
        ? { custoUnitario: request.custoUnitario }
        : {}),
      ...(request.margemMinimaDesejada !== null && request.margemMinimaDesejada !== undefined
        ? { margemMinimaDesejada: request.margemMinimaDesejada }
        : {}),
      ...(request.horizonMonths !== undefined ? { horizonMonths: request.horizonMonths } : {}),
    };
    return this.http.post<NewProductForecastResponse>(`${this.baseUrl}/new-product/forecast`, payload);
  }
}

function toPageParams(page: PageRequest): HttpParams {
  return new HttpParams().set('limit', page.limit).set('offset', page.offset);
}

function toChurnParams(page: PageRequest, options?: ChurnQueryOptions): HttpParams {
  let params = toPageParams(page);
  if (options?.q?.trim()) {
    params = params.set('q', options.q.trim());
  }
  if (options?.seller) {
    params = params.set('seller', options.seller);
  }
  if (options?.city) {
    params = params.set('city', options.city);
  }
  if (options?.sortBy) {
    params = params.set('sortBy', options.sortBy);
    params = params.set('sortDir', options.sortDir ?? 'desc');
  }
  return params;
}
