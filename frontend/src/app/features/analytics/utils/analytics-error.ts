/**
 * Conversão de erros HTTP do módulo Analytics (contrato §4, P-067; F-03; F5 P-102).
 * Só corpos `{ error: { code, message, fields[] } }` com código do contrato viram erro tipado;
 * todo o resto (500 do Starlette, rede, 422 padrão do FastAPI, corpo malformado) vira `null` = falha genérica.
 * A tela mapeia por código e nunca exibe `detail` cru nem stacktrace.
 */
import { HttpErrorResponse } from '@angular/common/http';
import { ANALYTICS_ERROR_CODES, AnalyticsApiError, AnalyticsErrorCode } from '../models/analytics.model';
import { NEW_PRODUCT_ERROR_CODES, NewProductApiError, NewProductErrorCode } from '../models/new-product.model';

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

/** Campos do formulário de Produto Novo mapeados em `error.fields[]`. */
export type NewProductFormField =
  | 'tipo'
  | 'fornecedor'
  | 'descricao'
  | 'precoVendaPrevisto'
  | 'custoUnitario'
  | 'margemMinimaDesejada'
  | 'horizonMonths';

/** Mensagens amigáveis de tela para códigos de erro da F2 (`NEW-001`..`NEW-005`). */
export const NEW_PRODUCT_ERROR_MESSAGES: Record<NewProductErrorCode, string> = {
  'NEW-001': 'Base de lançamentos similares insuficiente para o tipo selecionado (mínimo de 3 lançamentos necessários).',
  'NEW-002': 'O tipo de produto informado não foi encontrado no catálogo ativo.',
  'NEW-003': 'O fornecedor informado não foi encontrado no catálogo ativo.',
  'NEW-004': 'Verifique os parâmetros comerciais informados antes de simular.',
  'NEW-005': 'Serviço de análise de produtos temporariamente indisponível. Tente novamente em instantes.',
  'ANL-001': 'Base de dados de vendas temporariamente indisponível. Tente novamente em instantes.',
  'ANL-002': 'A base foi recarregada recentemente. Tente novamente mais tarde.',
};

export const NEW_PRODUCT_GENERIC_ERROR_MESSAGE =
  'Não foi possível concluir a simulação agora. Tente novamente em instantes.';

export const NEW_PRODUCT_OPTIONS_GENERIC_ERROR_MESSAGE =
  'Não foi possível carregar os tipos e fornecedores ativos agora. Tente novamente.';

/** Type guard do corpo de erro do contrato Produto Novo; `null` em 500, rede ou corpo malformado. */
export function toNewProductApiError(err: unknown): NewProductApiError | null {
  return parseContractError(err, NEW_PRODUCT_ERROR_CODES);
}

/** Mensagem amigável para banner/estado de erro da F2 (prefere mensagem do contrato quando presente). */
export function resolveNewProductErrorMessage(
  error: NewProductApiError | null,
  fallbackMessage = NEW_PRODUCT_GENERIC_ERROR_MESSAGE,
): string {
  if (!error) return fallbackMessage;
  if (error.code === 'NEW-001' || error.code === 'NEW-004') {
    return error.message.trim() || NEW_PRODUCT_ERROR_MESSAGES[error.code];
  }
  return NEW_PRODUCT_ERROR_MESSAGES[error.code];
}

/** Resolve erro inline de um campo específico do formulário Produto Novo a partir de `error.fields[]`. */
export function resolveNewProductFieldError(
  error: NewProductApiError | null,
  field: NewProductFormField,
): string | null {
  if (!error) return null;
  if (error.code === 'NEW-002' && (field === 'tipo' || error.fields.includes('tipo'))) {
    return NEW_PRODUCT_ERROR_MESSAGES['NEW-002'];
  }
  if (error.code === 'NEW-003' && (field === 'fornecedor' || error.fields.includes('fornecedor'))) {
    return NEW_PRODUCT_ERROR_MESSAGES['NEW-003'];
  }
  if (error.code === 'NEW-004' && error.fields.includes(field)) {
    return error.message.trim() || NEW_PRODUCT_ERROR_MESSAGES['NEW-004'];
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
