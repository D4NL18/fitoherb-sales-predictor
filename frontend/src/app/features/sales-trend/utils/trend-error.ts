/**
 * Utilitários de tratamento e mensagens de erro da API de Tendência de Vendas (P-082, P-084).
 * Converte erros HTTP brutos nos tipos do contrato TND-001 a TND-005.
 */
import { TrendErrorCode, TrendErrorPayload, TrendErrorResponse } from '../models/sales-trend.model';

export const TREND_ERROR_CODES: readonly TrendErrorCode[] = [
  'TND-001',
  'TND-002',
  'TND-003',
  'TND-004',
  'TND-005',
];

export const TREND_ERROR_MESSAGES: Record<TrendErrorCode, string> = {
  'TND-001': 'Parâmetros de busca inválidos. Verifique os valores informados.',
  'TND-002': 'Mês-base sem dados de venda. Escolha outro período.',
  'TND-003': 'Fornecedor não encontrado no catálogo ativo.',
  'TND-004': 'Serviço de dados temporariamente indisponível. Tente novamente em instantes.',
  'TND-005': 'Recarga recente em andamento. Aguarde alguns minutos antes de tentar novamente.',
};

export const GENERIC_ERROR_MESSAGE = 'Não foi possível carregar os dados de tendência. Tente novamente.';

/**
 * Type guard que verifica se um código pertence aos erros TND-001..005.
 */
export function isTrendErrorCode(code: unknown): code is TrendErrorCode {
  return typeof code === 'string' && (TREND_ERROR_CODES as readonly string[]).includes(code);
}

/**
 * Converte um erro HTTP (HttpErrorResponse ou similar) em TrendErrorPayload tipado.
 */
export function toTrendApiError(err: unknown): TrendErrorPayload | null {
  if (!err || typeof err !== 'object') {
    return null;
  }

  const candidate = err as Record<string, unknown>;
  const payloadCandidate = (candidate['error'] ?? candidate) as Record<string, unknown>;

  // Padrão de envelope { error: { code, message, fields }, meta }
  const innerError = (payloadCandidate['error'] ?? payloadCandidate) as Record<string, unknown>;
  const code = innerError['code'];

  if (isTrendErrorCode(code)) {
    const fields = Array.isArray(innerError['fields'])
      ? (innerError['fields'] as string[]).filter((f) => typeof f === 'string')
      : [];
    const message =
      typeof innerError['message'] === 'string'
        ? innerError['message']
        : TREND_ERROR_MESSAGES[code];

    return {
      code,
      message,
      fields,
    };
  }

  return null;
}

/**
 * Retorna mensagem de tela amigável para o usuário de acordo com o código e campos (Q-7).
 */
export function getDisplayErrorMessage(err: TrendErrorPayload | null): string {
  if (!err) {
    return GENERIC_ERROR_MESSAGE;
  }

  if (err.code === 'TND-002') {
    if (err.fields && err.fields.includes('baseMonth')) {
      return 'O mês-base escolhido não possui dados de venda. Selecione outro mês na barra superior.';
    }
    return 'Base de dados sem fechamento para o período. Tente um mês anterior.';
  }

  return TREND_ERROR_MESSAGES[err.code] || GENERIC_ERROR_MESSAGE;
}
