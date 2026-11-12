/**
 * T-13 — Type guard de erros do módulo Analytics (contrato §4, F-03).
 * `toAnalyticsApiError` aceita só corpos do contrato e devolve `null` (genérico) no resto: 500, rede (0),
 * código desconhecido, corpo malformado ou objeto que não é HttpErrorResponse.
 */
import { HttpErrorResponse } from '@angular/common/http';
import { ANALYTICS_ERROR_MESSAGES, toAnalyticsApiError } from './analytics-error';
import { AnalyticsErrorCode } from '../models/analytics.model';
import { contractError } from '../testing/cross-sell-test-data';

const ALL_CODES: AnalyticsErrorCode[] = ['XSL-001', 'XSL-002', 'XSL-003', 'XSL-004', 'ANL-001', 'ANL-002'];

function httpError(status: number, error: unknown): HttpErrorResponse {
  return new HttpErrorResponse({ status, statusText: 'Error', error });
}

describe('toAnalyticsApiError', () => {
  it('converte cada código do contrato', () => {
    for (const code of ALL_CODES) {
      const result = toAnalyticsApiError(contractError(code));
      expect(result?.code).withContext(code).toBe(code);
      expect(result?.fields).withContext(code).toEqual([]);
    }
  });

  it('preserva os campos inválidos do XSL-004', () => {
    const result = toAnalyticsApiError(contractError('XSL-004', ['limit', 'offset']));
    expect(result).toEqual({
      code: 'XSL-004',
      message: 'Parâmetros inválidos: sku.',
      fields: ['limit', 'offset'],
    });
  });

  it('cai no genérico (null) em 500 com corpo do Starlette', () => {
    expect(toAnalyticsApiError(httpError(500, 'Internal Server Error'))).toBeNull();
  });

  it('cai no genérico (null) em erro de rede (status 0)', () => {
    expect(toAnalyticsApiError(httpError(0, new ProgressEvent('error')))).toBeNull();
  });

  it('rejeita código fora do contrato', () => {
    const body = { error: { code: 'FOO-999', message: 'x', fields: [] } };
    expect(toAnalyticsApiError(httpError(404, body))).toBeNull();
  });

  it('rejeita corpo sem fields ou com fields inválido', () => {
    expect(toAnalyticsApiError(httpError(404, { error: { code: 'XSL-001', message: 'x' } }))).toBeNull();
    expect(toAnalyticsApiError(httpError(400, { error: { code: 'XSL-004', message: 'x', fields: [1] } }))).toBeNull();
    expect(toAnalyticsApiError(httpError(400, { error: { code: 'XSL-004', message: 1, fields: [] } }))).toBeNull();
  });

  it('rejeita o 422 padrão do FastAPI (detail) e valores que não são HttpErrorResponse', () => {
    expect(toAnalyticsApiError(httpError(422, { detail: [{ loc: ['body'], msg: 'x' }] }))).toBeNull();
    expect(toAnalyticsApiError(new Error('boom'))).toBeNull();
    expect(toAnalyticsApiError({ error: { code: 'XSL-001', message: 'x', fields: [] } })).toBeNull();
    expect(toAnalyticsApiError(null)).toBeNull();
    expect(toAnalyticsApiError(undefined)).toBeNull();
  });
});

describe('ANALYTICS_ERROR_MESSAGES', () => {
  it('tem mensagem de tela para todos os códigos', () => {
    for (const code of ALL_CODES) {
      expect(ANALYTICS_ERROR_MESSAGES[code]).withContext(code).toBeTruthy();
    }
  });

  it('usa as mensagens de campo do Design Plan (§6.4)', () => {
    expect(ANALYTICS_ERROR_MESSAGES['XSL-001']).toBe(
      'Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item.',
    );
    expect(ANALYTICS_ERROR_MESSAGES['XSL-002']).toBe('Cliente sem histórico de compras.');
    expect(ANALYTICS_ERROR_MESSAGES['XSL-003']).toContain('pedidos suficientes');
    expect(ANALYTICS_ERROR_MESSAGES['XSL-004']).toBe('Digite só números, sem pontos ou letras.');
  });
});
