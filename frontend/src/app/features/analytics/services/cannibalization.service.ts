import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import {
  CannibalizationDetailQueryOptions,
  CannibalizationDetailResponse,
  CannibalizationReportQueryOptions,
  CannibalizationReportResponse,
  CannibalizationWindowDays,
} from '../models/cannibalization.model';

const ANALYTICS_BASE_URL = '/api/v1/analytics';
const DEFAULT_WINDOW_DAYS: CannibalizationWindowDays = 90;

@Injectable({ providedIn: 'root' })
export class CannibalizationService {
  private readonly http = inject(HttpClient);

  getReport(
    options: CannibalizationReportQueryOptions = {},
  ): Observable<CannibalizationReportResponse> {
    let params = new HttpParams().set(
      'windowDays',
      String(options.windowDays ?? DEFAULT_WINDOW_DAYS),
    );

    if (options.minDropPct !== undefined) {
      params = params.set('minDropPct', String(options.minDropPct));
    }
    if (options.minMigratedClients !== undefined) {
      params = params.set('minMigratedClients', String(options.minMigratedClients));
    }

    const cleanCategory = options.category?.trim();
    if (cleanCategory) {
      params = params.set('category', cleanCategory);
    }

    const cleanSupplier = options.supplier?.trim();
    if (cleanSupplier) {
      params = params.set('supplier', cleanSupplier);
    }

    if (options.mechanism) {
      params = params.set('mechanism', options.mechanism);
    }

    const cleanSearch = options.search?.trim();
    if (cleanSearch) {
      params = params.set('search', cleanSearch);
    }

    return this.http.get<CannibalizationReportResponse>(
      `${ANALYTICS_BASE_URL}/cannibalization/report`,
      { params },
    );
  }

  getVictimDetail(
    sku: string,
    options: CannibalizationDetailQueryOptions = {},
  ): Observable<CannibalizationDetailResponse> {
    const cleanSku = encodeURIComponent(sku.trim());
    let params = new HttpParams().set(
      'windowDays',
      String(options.windowDays ?? DEFAULT_WINDOW_DAYS),
    );

    if (options.minDropPct !== undefined) {
      params = params.set('minDropPct', String(options.minDropPct));
    }
    if (options.minMigratedClients !== undefined) {
      params = params.set('minMigratedClients', String(options.minMigratedClients));
    }

    return this.http.get<CannibalizationDetailResponse>(
      `${ANALYTICS_BASE_URL}/cannibalization/report/${cleanSku}`,
      { params },
    );
  }
}
