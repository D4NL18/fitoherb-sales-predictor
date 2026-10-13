import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AutoTuneRequest, AutoTuneResponse, ConfigResponse, PredictResponse, PricingParams } from '../models/pricing.model';

@Injectable({
  providedIn: 'root'
})
export class PricingService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/pricing';

  getConfig(): Observable<ConfigResponse> {
    return this.http.get<ConfigResponse>(`${this.baseUrl}/config`);
  }

  getDbStatus(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/db-status`);
  }

  getLatestPrediction(): Observable<{ data: any; meta: any }> {
    return this.http.get<{ data: any; meta: any }>(`${this.baseUrl}/latest-prediction`);
  }

  predict(params: PricingParams): Observable<PredictResponse> {
    return this.http.post<PredictResponse>(`${this.baseUrl}/predict`, params);
  }


  exportCsv(params: PricingParams): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export`, params, {
      responseType: 'blob'
    });
  }

  autoTune(request: AutoTuneRequest = {}): Observable<AutoTuneResponse> {
    return this.http.post<AutoTuneResponse>(`${this.baseUrl}/auto-tune`, request);
  }

  autoTuneStream(strategy: string = 'balanced', generations: number = 6): Observable<{ type: 'progress' | 'complete'; data: any }> {
    return new Observable((observer) => {
      const url = `${this.baseUrl}/auto-tune-stream?strategy=${encodeURIComponent(strategy)}&generations=${generations}`;
      const eventSource = new EventSource(url);

      eventSource.addEventListener('progress', (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data);
          observer.next({ type: 'progress', data: parsed });
        } catch (e) {
          console.warn('Erro ao processar evento de progresso SSE:', e);
        }
      });

      eventSource.addEventListener('complete', (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data);
          observer.next({ type: 'complete', data: parsed });
          observer.complete();
        } catch (e) {
          observer.error(e);
        } finally {
          eventSource.close();
        }
      });

      eventSource.addEventListener('error', (err) => {
        eventSource.close();
        observer.error(err);
      });

      return () => {
        eventSource.close();
      };
    });
  }

  downloadBlob(blob: Blob, filename = 'precificacao_fitoherb.csv'): void {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(url);
  }
}
