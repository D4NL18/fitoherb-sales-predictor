/**
 * Conversão de erros HTTP do módulo Analytics (contrato §4, P-067; F-03; F5 P-102).
 * Só corpos `{ error: { code, message, fields[] } }` com código do contrato viram erro tipado;
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
  return parseContractError(err, ANALYTICS_ERROR_CODES);
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

/** Códigos de erro do subdomínio Elasticidade-Preço (contrato analytics-elasticidade §4, P-102). */
export const ELASTICITY_ERROR_CODES = ['ELA-001', 'ELA-002', 'ELA-003', 'ELA-004', 'ANL-001', 'ANL-002'] as const;

export type ElasticityErrorCode = (typeof ELASTICITY_ERROR_CODES)[number];

export interface ElasticityApiError {
  code: ElasticityErrorCode;
  message: string;
  fields: string[];
}

/** Mensagens fixas da tela de Elasticidade; nunca exibe `detail` cru nem stacktrace. */
export const ELASTICITY_ERROR_MESSAGES: Record<ElasticityErrorCode, string> = {
  'ELA-001': 'Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade.',
  'ELA-002': 'Nenhum histórico de compras registrado para este código de cliente neste produto.',
  'ELA-003': 'Histórico de vendas insuficiente para estimar elasticidade do produto.',
  'ELA-004': 'Parâmetros inválidos fornecidos para consulta ou simulação de elasticidade.',
  'ANL-001': 'Base de dados de vendas temporariamente indisponível. Tente novamente em instantes.',
  'ANL-002': 'A base foi recarregada recentemente. Tente novamente mais tarde.',
};

export const ELASTICITY_GENERIC_ERROR_MESSAGE =
  'Não foi possível consultar a elasticidade agora. Tente novamente em instantes.';

export const ELASTICITY_SIMULATION_GENERIC_ERROR_MESSAGE =
  'Não foi possível calcular a simulação agora. Tente novamente em instantes.';

/** Type guard do corpo de erro do contrato de elasticidade; `null` em 500, rede ou corpo malformado. */
export function toElasticityApiError(err: unknown): ElasticityApiError | null {
  return parseContractError(err, ELASTICITY_ERROR_CODES);
}

/** Mensagem amigável de tela para erros de elasticidade usando o mapa fixo do contrato. */
export function resolveElasticityErrorMessage(
  error: ElasticityApiError | null,
  fallbackMessage = ELASTICITY_GENERIC_ERROR_MESSAGE,
): string {
  return error ? ELASTICITY_ERROR_MESSAGES[error.code] : fallbackMessage;
}

/** Mensagem inline para o campo SKU quando o erro da API aponta produto ausente ou `sku` inválido. */
export function resolveElasticitySkuFieldError(error: ElasticityApiError | null): string | null {
  if (error === null) return null;
  if (error.code === 'ELA-001') return ELASTICITY_ERROR_MESSAGES['ELA-001'];
  if (error.code === 'ELA-004' && error.fields.includes('sku')) return ANALYTICS_ERROR_MESSAGES['XSL-004'];
  return null;
}

/** Códigos de erro do subdomínio Canibalização por Migração e Equilíbrio de Preço (contrato analytics-canibalizacao v1.1.0 §5). */
export const CANNIBALIZATION_ERROR_CODES = [
  'CAN-001',
  'CAN-003',
  'CAN-004',
  'CAN-005',
  'ANL-001',
] as const;

export type CannibalizationErrorCode = (typeof CANNIBALIZATION_ERROR_CODES)[number];

export type CannibalizationField =
  | 'sku'
  | 'windowDays'
  | 'minDropPct'
  | 'minMigratedClients'
  | 'category'
  | 'supplier'
  | 'mechanism'
  | 'search';

export interface CannibalizationApiError {
  code: CannibalizationErrorCode;
  message: string;
  fields: string[];
}

export const CANNIBALIZATION_ERROR_MESSAGES: Record<CannibalizationErrorCode, string> = {
  'CAN-001': 'Produto não encontrado no catálogo ativo.',
  'CAN-003':
    'Histórico transacional insuficiente para compor a análise de canibalização na janela selecionada.',
  'CAN-004': 'Parâmetro inválido informado na consulta do relatório de canibalização.',
  'CAN-005':
    'Não foi possível processar o relatório de canibalização no momento. Tente novamente mais tarde.',
  'ANL-001': 'Base de vendas indisponível no momento. Tente novamente em instantes.',
};

export const CANNIBALIZATION_GENERIC_ERROR_MESSAGE =
  'Não foi possível carregar o relatório de canibalização agora. Tente novamente em instantes.';

const CANNIBALIZATION_FIELD_ERROR_MESSAGES: Record<CannibalizationField, string> = {
  sku: 'Informe um código de produto válido (somente dígitos positivos).',
  windowDays: 'Escolha um período válido: 30, 60 ou 90 dias.',
  minDropPct: 'Informe uma queda percentual mínima entre 1% e 80%.',
  minMigratedClients: 'Informe um mínimo de clientes migrados entre 1 e 50.',
  category: 'Informe uma categoria válida.',
  supplier: 'Informe um fornecedor válido.',
  mechanism: 'Selecione um mecanismo de canibalização válido.',
  search: 'Informe até 80 caracteres na busca.',
};

/** Type guard do corpo de erro do contrato de canibalização; `null` em 500 texto, rede ou corpo malformado. */
export function toCannibalizationApiError(err: unknown): CannibalizationApiError | null {
  return parseContractError(err, CANNIBALIZATION_ERROR_CODES);
}

/** Mensagem amigável de tela para erros de canibalização usando o mapa fixo do contrato. */
export function resolveCannibalizationErrorMessage(
  error: CannibalizationApiError | null,
  fallbackMessage = CANNIBALIZATION_GENERIC_ERROR_MESSAGE,
): string {
  return error ? CANNIBALIZATION_ERROR_MESSAGES[error.code] : fallbackMessage;
}

/** Roteamento seguro de erros de validação (CAN-004) e não encontrado (CAN-001) para o campo afetado. */
export function resolveCannibalizationFieldError(
  error: CannibalizationApiError | null,
  field: CannibalizationField,
): string | null {
  if (error === null) return null;
  if (error.code === 'CAN-001' && field === 'sku') return CANNIBALIZATION_ERROR_MESSAGES['CAN-001'];
  if (error.code === 'CAN-004' && error.fields.includes(field)) {
    return CANNIBALIZATION_FIELD_ERROR_MESSAGES[field];
  }
  return null;
}

function parseContractError<TCode extends string>(
  err: unknown,
  allowedCodes: readonly TCode[],
): { code: TCode; message: string; fields: string[] } | null {
  if (!(err instanceof HttpErrorResponse)) return null;
  const body: unknown = err.error;
  if (!isRecord(body) || !isRecord(body['error'])) return null;

  const { code, message, fields } = body['error'];
  if (!isAllowedCode(code, allowedCodes) || typeof message !== 'string' || !isStringArray(fields)) return null;
  return { code, message, fields: [...fields] };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isAllowedCode<TCode extends string>(value: unknown, allowedCodes: readonly TCode[]): value is TCode {
  return typeof value === 'string' && (allowedCodes as readonly string[]).includes(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}
