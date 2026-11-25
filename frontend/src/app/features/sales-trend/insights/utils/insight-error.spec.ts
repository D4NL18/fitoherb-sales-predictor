import { HttpErrorResponse, HttpHeaders } from '@angular/common/http';
import { TimeoutError } from 'rxjs';
import { resolveInsightMessage, toInsightApiError } from './insight-error';

function http(status: number, code?: string, motivo: string | null = null, headers?: Record<string, string>): HttpErrorResponse {
  return new HttpErrorResponse({
    status,
    headers: headers ? new HttpHeaders(headers) : undefined,
    error: code ? { error: { code, message: 'texto do servidor', fields: [], motivo }, meta: {} } : null,
  });
}

describe('insight-error', () => {
  it('mapeia TIA-004 com motivo LIMITE_DE_PEDIDOS', () => {
    const e = toInsightApiError(http(429, 'TIA-004', 'LIMITE_DE_PEDIDOS'));
    expect(e.kind).toBe('RATE_LIMIT');
    expect(e.motivo).toBe('LIMITE_DE_PEDIDOS');
    expect(resolveInsightMessage(e, 'post')).toContain('Aguarde um minuto');
  });

  it('mapeia TIA-004 com motivo LIMITE_DIARIO sem falar em orçamento ou dólar', () => {
    const e = toInsightApiError(http(429, 'TIA-004', 'LIMITE_DIARIO'));
    const msg = resolveInsightMessage(e, 'post');
    expect(msg).toContain('limite de análises por hoje');
    expect(msg).not.toMatch(/US\$|dólar|orçamento|token/i);
  });

  it('lê Retry-After em segundos', () => {
    const e = toInsightApiError(http(429, 'TIA-004', 'LIMITE_DE_PEDIDOS', { 'Retry-After': '42' }));
    expect(e.retryAfterSeconds).toBe(42);
  });

  it('401 vira UNAUTHORIZED com mensagem própria', () => {
    const e = toInsightApiError(http(401));
    expect(e.kind).toBe('UNAUTHORIZED');
    expect(resolveInsightMessage(e, 'get')).toContain('sessão');
  });

  it('409 TIA-007 e demais desconhecidos caem na mensagem genérica sem eco do servidor', () => {
    const e = toInsightApiError(http(409, 'TIA-007'));
    expect(e.kind).toBe('SERVER');
    expect(resolveInsightMessage(e, 'get')).toBe(
      'Não foi possível carregar o diagnóstico. Verifique a conexão e tente de novo.',
    );
  });

  it('TIA-003 difere entre GET e POST', () => {
    const e = toInsightApiError(http(422, 'TIA-003'));
    expect(resolveInsightMessage(e, 'get')).toContain('Escolha outra janela');
    expect(resolveInsightMessage(e, 'post')).toBe('Não há variação relevante para analisar.');
  });

  it('TIA-002, TIA-001 e ANL-001 usam copy do plano', () => {
    expect(resolveInsightMessage(toInsightApiError(http(404, 'TIA-002')), 'get')).toBe(
      'Este produto não está mais no catálogo ativo.',
    );
    expect(resolveInsightMessage(toInsightApiError(http(400, 'TIA-001')), 'get')).toContain('Recarregue a página');
    expect(resolveInsightMessage(toInsightApiError(http(503, 'ANL-001')), 'get')).toContain('base de vendas');
  });

  it('status 0 vira NETWORK e TimeoutError vira TIMEOUT', () => {
    expect(toInsightApiError(http(0)).kind).toBe('NETWORK');
    expect(toInsightApiError(new TimeoutError()).kind).toBe('TIMEOUT');
  });

  it('nunca ecoa message do servidor', () => {
    const e = toInsightApiError(http(404, 'TIA-002'));
    expect(JSON.stringify(e)).not.toContain('texto do servidor');
  });
});
