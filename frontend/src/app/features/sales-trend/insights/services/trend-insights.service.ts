/**
 * Serviço HTTP do diagnóstico "Por que?" (contrato sales-trend-insights 1.1.0).
 * O GET nunca aciona IA; só o POST /generate, disparado por clique explícito (P-174).
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, timeout } from 'rxjs';
import {
  GenerateInsightResponse,
  GenerateOptions,
  InsightQueryParams,
  ProductInsightResponse,
} from '../models/trend-insights.model';

export const GENERATE_TIMEOUT_MS = 150_000;

@Injectable({ providedIn: 'root' })
export class TrendInsightsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/sales-trend/insights/product';

  getProductInsight(sku: number, params: InsightQueryParams): Observable<ProductInsightResponse> {
    let httpParams = new HttpParams();
    if (params.metric) httpParams = httpParams.set('metric', params.metric);
    if (params.window) httpParams = httpParams.set('window', String(params.window));
    if (params.baseMonth) httpParams = httpParams.set('baseMonth', params.baseMonth);
    if (params.comparisonMode) httpParams = httpParams.set('comparisonMode', params.comparisonMode);
    return this.http.get<ProductInsightResponse>(`${this.baseUrl}/${sku}`, { params: httpParams });
  }

  generateProductInsight(
    sku: number,
    params: InsightQueryParams,
    options: GenerateOptions = {},
  ): Observable<GenerateInsightResponse> {
    const body: Record<string, unknown> = { ...params, force: options.force === true };
    return this.http
      .post<GenerateInsightResponse>(`${this.baseUrl}/${sku}/generate`, body)
      .pipe(timeout(GENERATE_TIMEOUT_MS));
  }
}
