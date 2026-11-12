/**
 * Conversão de erros HTTP do módulo Analytics (contrato §4, P-067; F-03).
 * Só corpos `{ error: { code, message, fields[] } }` com código do contrato viram `AnalyticsApiError`;
 * todo o resto (500 do Starlette, rede, 422 padrão do FastAPI, corpo malformado) vira `null` = falha genérica.
 * A tela mapeia por código e nunca exibe `detail` cru nem stacktrace.
 */
import { HttpErrorResponse } from '@angular/common/http';
import { ANALYTICS_ERROR_CODES, AnalyticsApiError, AnalyticsErrorCode } from '../models/analytics.model';

/** Mensagens de tela por código (Design Plan §6.4; literais de P-067 nos erros de campo). */
export const ANALYTICS_ERROR_MESSAGES: Record<AnalyticsErrorCode, string> = {
  'XSL-001': 'Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item.',
  'XSL-002': 'Cliente sem histórico de compras.',
  'XSL-003': 'Não há pedidos suficientes para gerar recomendações confiáveis.',
  'XSL-004': 'Digite só números, sem pontos ou letras.',
  'ANL-001': 'Base de vendas indisponível no momento. Tente novamente em instantes.',
  'ANL-002': 'A base foi recarregada recentemente. Tente novamente mais tarde.',
};

/**
 * Validação local de formato no modo produto: o campo também aceita descrição, então a mensagem
 * orienta a escolher da lista em vez de mandar digitar só números (UX B-3). O XSL-004 da API segue igual.
 */
export const PRODUCT_INVALID_FORMAT_MESSAGE = 'Escolha um produto da lista ou digite o código (só números).';

/** Campo de consulta de cada modo, como o backend o nomeia em `fields` do `XSL-004`. */
export type SearchField = 'sku' | 'customerCode';

/** Código "não encontrado" de cada campo (P-067). */
const NOT_FOUND_CODE_BY_FIELD: Record<SearchField, AnalyticsErrorCode> = {
  sku: 'XSL-001',
  customerCode: 'XSL-002',
};

/** Type guard do corpo de erro do contrato; `null` quando não é um erro reconhecido. */
export function toAnalyticsApiError(err: unknown): AnalyticsApiError | null {
  if (!(err instanceof HttpErrorResponse)) return null;
  const body: unknown = err.error;
  if (!isRecord(body) || !isRecord(body['error'])) return null;

  const { code, message, fields } = body['error'];
  if (!isAnalyticsErrorCode(code) || typeof message !== 'string' || !isStringArray(fields)) return null;
  return { code, message, fields: [...fields] };
}

/**
 * Mensagem inline do campo de consulta, ou `null` se o erro não é do campo.
 * `XSL-004` só é erro de campo quando cita o próprio campo; `limit`/`offset` são bug do frontend (falha técnica).
 */
export function resolveFieldError(error: AnalyticsApiError | null, field: SearchField): string | null {
  if (error === null) return null;
  if (error.code === NOT_FOUND_CODE_BY_FIELD[field]) return ANALYTICS_ERROR_MESSAGES[error.code];
  if (error.code === 'XSL-004' && error.fields.includes(field)) return ANALYTICS_ERROR_MESSAGES['XSL-004'];
  return null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isAnalyticsErrorCode(value: unknown): value is AnalyticsErrorCode {
  return typeof value === 'string' && (ANALYTICS_ERROR_CODES as readonly string[]).includes(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}
