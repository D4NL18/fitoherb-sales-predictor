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
}

function toPageParams(page: PageRequest): HttpParams {
  return new HttpParams().set('limit', page.limit).set('offset', page.offset);
}
