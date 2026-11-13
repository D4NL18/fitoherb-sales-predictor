/**
 * Testes unitários para utilitários de erro da API de Tendência (T-15).
 * Valida type guard TND-001 a TND-005, extração de fields e mensagens amigáveis.
 */
import {
  isTrendErrorCode,
  toTrendApiError,
  getDisplayErrorMessage,
  TREND_ERROR_MESSAGES,
  GENERIC_ERROR_MESSAGE,
} from './trend-error';

describe('trend-error utils (T-15)', () => {
  it('identifica códigos válidos TND-001 a TND-005', () => {
    expect(isTrendErrorCode('TND-001')).toBeTrue();
    expect(isTrendErrorCode('TND-002')).toBeTrue();
    expect(isTrendErrorCode('TND-003')).toBeTrue();
    expect(isTrendErrorCode('TND-004')).toBeTrue();
    expect(isTrendErrorCode('TND-005')).toBeTrue();
    expect(isTrendErrorCode('XSL-001')).toBeFalse();
    expect(isTrendErrorCode('500')).toBeFalse();
    expect(isTrendErrorCode(null)).toBeFalse();
  });

  it('extrai TrendErrorPayload de resposta HttpErrorResponse formatada', () => {
    const rawHttpError = {
      status: 400,
      error: {
        error: {
          code: 'TND-001',
          message: 'Parâmetros inválidos.',
          fields: ['sortWindow', 'minVolume'],
        },
        meta: {
          timestamp: '2026-11-10T12:00:00Z',
          version: '1.0.0',
        },
      },
    };

    const parsed = toTrendApiError(rawHttpError);
    expect(parsed).not.toBeNull();
    expect(parsed?.code).toBe('TND-001');
    expect(parsed?.message).toBe('Parâmetros inválidos.');
    expect(parsed?.fields).toEqual(['sortWindow', 'minVolume']);
  });

  it('devolve null para erro 500 ou formato desconhecido', () => {
    expect(toTrendApiError(null)).toBeNull();
    expect(toTrendApiError({ status: 500, error: 'Internal Server Error' })).toBeNull();
    expect(toTrendApiError({ error: { code: 'UNKNOWN_CODE' } })).toBeNull();
  });

  it('retorna mensagem especializada para TND-002 com baseMonth em fields', () => {
    const errorWithBaseMonth = {
      code: 'TND-002' as const,
      message: 'Mês-Base sem vendas',
      fields: ['baseMonth'],
    };
    const msg = getDisplayErrorMessage(errorWithBaseMonth);
    expect(msg).toContain('mês-base escolhido não possui dados de venda');
  });

  it('retorna mensagem especializada para TND-002 sem fields', () => {
    const errorWithoutFields = {
      code: 'TND-002' as const,
      message: 'Base vazia',
      fields: [],
    };
    const msg = getDisplayErrorMessage(errorWithoutFields);
    expect(msg).toContain('Base de dados sem fechamento');
  });

  it('retorna mensagem genérica quando payload é nulo', () => {
    expect(getDisplayErrorMessage(null)).toBe(GENERIC_ERROR_MESSAGE);
  });
});
