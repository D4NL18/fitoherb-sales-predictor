/**
 * Serviço de comunicação HTTP com a API de Previsão de Estoque e Compras (`/api/v1/inventory`).
 *
 * Responsável pelo envio dos parâmetros da Política Mín/Máx (P-053 a P-056) e pela
 * tradução padronizada de erros HTTP (422/500/rede) em mensagens amigáveis em PT-BR (F-03).
 */
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  ApiValidationErrorItem,
  InventoryConfigResponse,
  InventoryParams,
  InventoryPredictResponse,
  SupplierListResponse,
} from '../models/inventory.model';

const DOMAIN_ERROR_CODE_PREFIX = 'INV-';

const INVALID_PARAMETERS_FALLBACK_MESSAGE =
  'Os parâmetros informados estão fora da faixa permitida. Revise os valores e tente novamente.';

const GENERIC_INVENTORY_ERROR_MESSAGE =
  'Não foi possível concluir a operação no momento. Verifique a conexão com o servidor e tente novamente.';

function isValidationErrorItem(item: unknown): item is ApiValidationErrorItem {
  if (typeof item !== 'object' || item === null) {
    return false;
  }
  const candidate = item as Record<string, unknown>;
  return typeof candidate['type'] === 'string' && typeof candidate['msg'] === 'string';
}

function extractDetailFromErrorBody(errorBody: unknown): unknown {
  if (typeof errorBody !== 'object' || errorBody === null || errorBody instanceof Blob) {
    return undefined;
  }
  return (errorBody as Record<string, unknown>)['detail'];
}

/**
 * Extrai uma mensagem amigável em PT-BR a partir de um `HttpErrorResponse` da API de estoque.
 * Decide pelo código interno `type` (`INV-001`, `INV-002`) quando `detail` é uma lista 422 (P-053.3, A2).
 */
export function extractInventoryErrorMessage(error: HttpErrorResponse): string {
  const detail = extractDetailFromErrorBody(error?.error);

  if (Array.isArray(detail)) {
    const domainError = detail.find(
      (item): item is ApiValidationErrorItem =>
        isValidationErrorItem(item) && item.type.startsWith(DOMAIN_ERROR_CODE_PREFIX)
    );
    return domainError ? domainError.msg : INVALID_PARAMETERS_FALLBACK_MESSAGE;
  }

  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }

  return GENERIC_INVENTORY_ERROR_MESSAGE;
}

@Injectable({
  providedIn: 'root',
})
export class InventoryService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1/inventory';

  /** Consulta os padrões e as faixas dos controles deslizantes da política (seção 3 do contrato). */
  getConfig(): Observable<InventoryConfigResponse> {
    return this.http.get<InventoryConfigResponse>(`${this.baseUrl}/config`);
  }

  /** Lista os fornecedores/laboratórios e a contagem de SKUs por fabricante (P-047.1). */
  getSuppliers(): Observable<SupplierListResponse> {
    return this.http.get<SupplierListResponse>(`${this.baseUrl}/suppliers`);
  }

  /** Executa o cálculo da Política Mín/Máx por SKU e retorna os KPIs consolidados (P-053 a P-055). */
  predict(params: InventoryParams): Observable<InventoryPredictResponse> {
    return this.http.post<InventoryPredictResponse>(`${this.baseUrl}/predict`, params);
  }

  /** Exporta o plano de compras em formato CSV alinhado à política aplicada (P-056.5, P-056.6). */
  exportCsv(params: InventoryParams): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export-csv`, params, {
      responseType: 'blob',
    });
  }
}
