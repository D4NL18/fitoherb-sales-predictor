/**
 * Cliente HTTP do subdomínio de Sazonalidade por Produto (contrato 1.0.0; P-106 a P-116).
 * Sem console.log nem armazenamento local.
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PageRequest } from '../models/analytics.model';
import { ProductSearchResponse } from '../models/cross-sell.model';
import {
  SeasonalityOrder,
  SeasonalityRankingResponse,
  SeasonalityResponse,
} from '../models/seasonality.model';

@Injectable({ providedIn: 'root' })
export class SeasonalityService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/analytics';

  /** Consulta diagnóstico completo de sazonalidade de um produto pelo SKU (P-106..P-113). */
  getSeasonality(sku: number): Observable<SeasonalityResponse> {
    return this.http.get<SeasonalityResponse>(`${this.baseUrl}/seasonality/${sku}`);
  }

  /** Consulta rankings de sazonalidade (most: mais sazonais; least: pouco mensuráveis) paginado (P-114). */
  getRanking(order: SeasonalityOrder, page: PageRequest): Observable<SeasonalityRankingResponse> {
    const params = new HttpParams()
      .set('order', order)
      .set('limit', page.limit)
      .set('offset', page.offset);
    return this.http.get<SeasonalityRankingResponse>(`${this.baseUrl}/seasonality/ranking`, { params });
  }

  /** Busca rápida de produto no catálogo ativo para autocomplete (P-115). */
  searchProducts(query: string, page: PageRequest = { limit: 20, offset: 0 }): Observable<ProductSearchResponse> {
    const params = new HttpParams()
      .set('q', query.trim())
      .set('limit', page.limit)
      .set('offset', page.offset);
    return this.http.get<ProductSearchResponse>(`${this.baseUrl}/products/search`, { params });
  }
}
