/**
 * Testes unitários para mapeamento bidirecional URL <-> Estado (T-16).
 */
import { queryParamsToState, stateToQueryParams } from './trend-url';

describe('trend-url utils (T-16)', () => {
  it('omite parâmetros padrões ao converter estado para URL', () => {
    const params = stateToQueryParams({
      metric: 'revenue',
      groupBy: 'product',
      sortWindow: 3,
      sortDir: 'desc',
      view: 'all',
      minVolume: 0,
      limit: 50,
      offset: 0,
    });

    expect(Object.keys(params).length).toBe(0);
    expect(params['activeOnly']).toBeUndefined();
  });

  it('serializa valores customizados e omite activeOnly', () => {
    const params = stateToQueryParams({
      baseMonth: '2026-10',
      metric: 'quantity',
      groupBy: 'supplier',
      sortWindow: 1,
      sortDir: 'asc',
      view: 'rising',
      q: 'camomila',
      minVolume: 100,
      limit: 20,
      offset: 40,
    });

    expect(params['baseMonth']).toBe('2026-10');
    expect(params['metric']).toBe('quantity');
    expect(params['groupBy']).toBe('supplier');
    expect(params['sortWindow']).toBe(1);
    expect(params['sortDir']).toBe('asc');
    expect(params['view']).toBe('rising');
    expect(params['q']).toBe('camomila');
    expect(params['minVolume']).toBe(100);
    expect(params['limit']).toBe(20);
    expect(params['offset']).toBe(40);
    expect(params['activeOnly']).toBeUndefined();
  });

  it('converte parâmetros de URL em estado validado e descarta desconhecidos', () => {
    const state = queryParamsToState({
      baseMonth: '2026-10',
      metric: 'quantity',
      groupBy: 'supplier',
      sortWindow: '6',
      sortDir: 'desc',
      view: 'falling',
      q: '  chá  ',
      minVolume: '50.5',
      limit: '100',
      offset: '20',
      activeOnly: 'true', // parâmetro desconhecido/antigo
      outro: 'ignorado',
    });

    expect(state.baseMonth).toBe('2026-10');
    expect(state.metric).toBe('quantity');
    expect(state.groupBy).toBe('supplier');
    expect(state.sortWindow).toBe(6);
    expect(state.sortDir).toBe('desc');
    expect(state.view).toBe('falling');
    expect(state.q).toBe('chá');
    expect(state.minVolume).toBe(50.5);
    expect(state.limit).toBe(100);
    expect(state.offset).toBe(20);
    expect((state as Record<string, unknown>)['activeOnly']).toBeUndefined();
  });
});
