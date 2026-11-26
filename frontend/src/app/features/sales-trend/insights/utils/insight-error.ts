/**
 * Conversão de erros HTTP do diagnóstico em `InsightApiError` e mensagens de tela (Design Plan §10.4).
 * Decide sempre por `error.code`/`motivo` e status; nunca ecoa `message` do servidor nem dados da requisição.
 */
import { HttpErrorResponse } from '@angular/common/http';
import { TimeoutError } from 'rxjs';
import { RateLimitReason } from '../models/trend-insights.model';

export type InsightErrorKind =
  | 'INVALID_PARAMS'
  | 'NOT_FOUND'
  | 'NO_BASE'
  | 'RATE_LIMIT'
  | 'SALES_UNAVAILABLE'
  | 'UNAUTHORIZED'
  | 'NETWORK'
  | 'TIMEOUT'
  | 'SERVER';

export interface InsightApiError {
  kind: InsightErrorKind;
  code: string | null;
  motivo: RateLimitReason | null;
  retryAfterSeconds: number | null;
  status: number;
}

export const INSIGHT_GENERIC_MESSAGE =
  'Não foi possível carregar o diagnóstico. Verifique a conexão e tente de novo.';

const KIND_BY_CODE: Record<string, InsightErrorKind> = {
  'TIA-001': 'INVALID_PARAMS',
  'TIA-002': 'NOT_FOUND',
  'TIA-003': 'NO_BASE',
  'TIA-004': 'RATE_LIMIT',
  'ANL-001': 'SALES_UNAVAILABLE',
};

function readCode(body: unknown): { code: string | null; motivo: RateLimitReason | null } {
  if (!body || typeof body !== 'object') return { code: null, motivo: null };
  const inner = (body as Record<string, unknown>)['error'];
  if (!inner || typeof inner !== 'object') return { code: null, motivo: null };
  const rec = inner as Record<string, unknown>;
  const code = typeof rec['code'] === 'string' ? rec['code'] : null;
  const m = rec['motivo'];
  const motivo = m === 'LIMITE_DE_PEDIDOS' || m === 'LIMITE_DIARIO' ? m : null;
  return { code, motivo };
}

export function toInsightApiError(err: unknown): InsightApiError {
  if (err instanceof TimeoutError) {
    return { kind: 'TIMEOUT', code: null, motivo: null, retryAfterSeconds: null, status: 0 };
  }
  if (!(err instanceof HttpErrorResponse)) {
    return { kind: 'SERVER', code: null, motivo: null, retryAfterSeconds: null, status: 500 };
  }
  if (err.status === 0) {
    return { kind: 'NETWORK', code: null, motivo: null, retryAfterSeconds: null, status: 0 };
  }
  if (err.status === 401) {
    return { kind: 'UNAUTHORIZED', code: null, motivo: null, retryAfterSeconds: null, status: 401 };
  }
  const { code, motivo } = readCode(err.error);
  const kind = (code && KIND_BY_CODE[code]) || 'SERVER';
  const retryRaw = Number(err.headers?.get('Retry-After'));
  const retryAfterSeconds = kind === 'RATE_LIMIT' && Number.isFinite(retryRaw) && retryRaw > 0 ? retryRaw : null;
  return { kind, code: kind === 'SERVER' ? null : code, motivo, retryAfterSeconds, status: err.status };
}

/**
 * Mensagem amigável por tipo de erro. `channel` distingue GET (painel) de POST (bloco de IA).
 */
export function resolveInsightMessage(err: InsightApiError, channel: 'get' | 'post'): string {
  switch (err.kind) {
    case 'INVALID_PARAMS':
      return 'Não foi possível montar o diagnóstico com estes filtros. Recarregue a página.';
    case 'NOT_FOUND':
      return 'Este produto não está mais no catálogo ativo.';
    case 'NO_BASE':
      return channel === 'get'
        ? 'Não há base de vendas suficiente para diagnosticar esta janela. Escolha outra janela.'
        : 'Não há variação relevante para analisar.';
    case 'RATE_LIMIT':
      return err.motivo === 'LIMITE_DIARIO'
        ? 'Você chegou ao limite de análises por hoje. A parte numérica continua disponível e o limite renova amanhã.'
        : 'Muitos pedidos de análise em sequência. Aguarde um minuto e tente de novo.';
    case 'SALES_UNAVAILABLE':
      return 'A base de vendas está indisponível agora. Tente de novo em alguns minutos.';
    case 'UNAUTHORIZED':
      return 'Sua sessão expirou. Recarregue a página e entre de novo.';
    default:
      return channel === 'post'
        ? 'Não foi possível gerar a análise agora. A parte numérica está disponível.'
        : INSIGHT_GENERIC_MESSAGE;
  }
}
