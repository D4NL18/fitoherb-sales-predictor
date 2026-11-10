/**
 * Serviço Angular tipado para consumo da API REST de Tendência de Vendas (P-084, ADR-003 DA-08).
 * Isola chamadas HTTP e omite parâmetros iguais aos defaults do servidor.
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ProductTrendResponse,
  SalesTrendCacheResponse,
  SupplierDetailResponse,
  SupplierProductsQueryParams,
  SupplierTrendResponse,
  TrendQueryParams,
} from '../models/sales-trend.model';

@Injectable({
  providedIn: 'root',
})
export class SalesTrendService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/sales-trend';

  /**
   * Consulta a lista da tendência de vendas com suporte a overloads tipados por groupBy.
   */
  getTrend(params: TrendQueryParams & { groupBy: 'supplier' }): Observable<SupplierTrendResponse>;
  getTrend(params?: TrendQueryParams & { groupBy?: 'product' }): Observable<ProductTrendResponse>;
  getTrend(params?: TrendQueryParams): Observable<ProductTrendResponse | SupplierTrendResponse>;
  getTrend(params?: TrendQueryParams): Observable<ProductTrendResponse | SupplierTrendResponse> {
    const httpParams = this.buildTrendParams(params);
    return this.http.get<ProductTrendResponse | SupplierTrendResponse>(this.baseUrl, {
      params: httpParams,
    });
  }

  /**
   * Consulta detalhada dos produtos de um fornecedor (drill-down).
   */
  getSupplierProducts(params: SupplierProductsQueryParams): Observable<SupplierDetailResponse> {
    const httpParams = this.buildSupplierDetailParams(params);
    return this.http.get<SupplierDetailResponse>(`${this.baseUrl}/supplier-products`, {
      params: httpParams,
    });
  }

  /**
   * Consulta o estado atual do snapshot em memória sem disparar recarga.
   */
  getHealth(): Observable<SalesTrendCacheResponse> {
    return this.http.get<SalesTrendCacheResponse>(`${this.baseUrl}/health`);
  }

  /**
   * Solicita recarga síncrona manual do snapshot de tendência.
   */
  reloadCache(): Observable<SalesTrendCacheResponse> {
    return this.http.post<SalesTrendCacheResponse>(`${this.baseUrl}/reload`, {});
  }

  private buildTrendParams(params?: TrendQueryParams): HttpParams {
    let httpParams = new HttpParams();
    if (!params) {
      return httpParams;
    }

    if (params.baseMonth) {
      httpParams = httpParams.set('baseMonth', params.baseMonth);
    }
    if (params.metric && params.metric !== 'revenue') {
      httpParams = httpParams.set('metric', params.metric);
    }
    if (params.groupBy && params.groupBy !== 'product') {
      httpParams = httpParams.set('groupBy', params.groupBy);
    }
    if (params.sortWindow && params.sortWindow !== 3) {
      httpParams = httpParams.set('sortWindow', params.sortWindow.toString());
    }
    if (params.sortDir && params.sortDir !== 'desc') {
      httpParams = httpParams.set('sortDir', params.sortDir);
    }
    if (params.view && params.view !== 'all') {
      httpParams = httpParams.set('view', params.view);
    }
    if (params.q && params.q.trim().length > 0) {
      httpParams = httpParams.set('q', params.q.trim());
    }
    if (typeof params.minVolume === 'number' && params.minVolume > 0) {
      httpParams = httpParams.set('minVolume', params.minVolume.toString());
    }
    if (typeof params.limit === 'number' && params.limit !== 50) {
      httpParams = httpParams.set('limit', params.limit.toString());
    }
    if (typeof params.offset === 'number' && params.offset > 0) {
      httpParams = httpParams.set('offset', params.offset.toString());
    }

    return httpParams;
  }

  private buildSupplierDetailParams(params: SupplierProductsQueryParams): HttpParams {
    let httpParams = new HttpParams().set('supplierKey', params.supplierKey);

    if (params.baseMonth) {
      httpParams = httpParams.set('baseMonth', params.baseMonth);
    }
    if (params.metric && params.metric !== 'revenue') {
      httpParams = httpParams.set('metric', params.metric);
    }
    if (params.sortBy && params.sortBy !== 'contribution') {
      httpParams = httpParams.set('sortBy', params.sortBy);
    }
    if (params.sortWindow && params.sortWindow !== 3) {
      httpParams = httpParams.set('sortWindow', params.sortWindow.toString());
    }
    if (params.sortDir && params.sortDir !== 'desc') {
      httpParams = httpParams.set('sortDir', params.sortDir);
    }
    if (params.q && params.q.trim().length > 0) {
      httpParams = httpParams.set('q', params.q.trim());
    }
    if (typeof params.limit === 'number' && params.limit !== 20) {
      httpParams = httpParams.set('limit', params.limit.toString());
    }
    if (typeof params.offset === 'number' && params.offset > 0) {
      httpParams = httpParams.set('offset', params.offset.toString());
    }

    return httpParams;
  }
}
