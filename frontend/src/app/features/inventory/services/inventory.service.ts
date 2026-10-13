import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  InventoryConfigResponse,
  InventoryParams,
  InventoryPredictResponse,
  SuppliersResponse,
} from '../models/inventory.model';

@Injectable({
  providedIn: 'root'
})
export class InventoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/inventory';

  getConfig(): Observable<InventoryConfigResponse> {
    return this.http.get<InventoryConfigResponse>(`${this.baseUrl}/config`);
  }

  getSuppliers(): Observable<SuppliersResponse> {
    return this.http.get<SuppliersResponse>(`${this.baseUrl}/suppliers`);
  }

  predict(params: InventoryParams): Observable<InventoryPredictResponse> {
    return this.http.post<InventoryPredictResponse>(`${this.baseUrl}/predict`, params);
  }

  exportCsv(params: InventoryParams): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export-csv`, params, {
      responseType: 'blob'
    });
  }
}
