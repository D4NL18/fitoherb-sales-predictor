/**
 * Testes unitários para utilitários de view-model (T-16).
 */
import { getCellDisplayModel, isAllSemBase } from './trend-view';
import { TrendCell } from '../models/sales-trend.model';

describe('trend-view utils (T-16)', () => {
  it('gera modelo para célula VARIACAO com alta e badges', () => {
    const cell: TrendCell = {
      meses: 1,
      atual: 1500,
      anterior: 1000,
      variacaoPct: 50.0,
      status: 'VARIACAO',
      baseParcial: true,
      baseBaixa: false,
      devolucaoLiquida: false,
      atualPorDia: 50.0,
      anteriorPorDia: 33.3333,
    };

    const model = getCellDisplayModel(cell, 'revenue');
    expect(model.isNumeric).toBeTrue();
    expect(model.direction).toBe('up');
    expect(model.percentText).toBe('+50,0%');
    expect(model.badges.length).toBe(1);
    expect(model.badges[0].text).toBe('Base parcial');
    expect(model.currentDailyText).toContain('/dia');
    expect(model.ariaLabel).toContain('alta de +50,0%');
  });

  it('gera modelo para célula com base baixa e interpola parâmetros', () => {
    const cell: TrendCell = {
      meses: 3,
      atual: 400,
      anterior: 200,
      variacaoPct: 100.0,
      status: 'VARIACAO',
      baseParcial: false,
      baseBaixa: true,
      devolucaoLiquida: false,
      atualPorDia: null,
      anteriorPorDia: null,
    };

    const params = {
      limiteBaseBaixaQuantidade: 10,
      limiteBaseBaixaFaturamento: 500,
      coberturaMinimaAnterior: 0.5,
      buscaMinCaracteres: 2,
      buscaMinCaracteresNumerica: 1,
      buscaMaxCaracteres: 60,
      ttlCacheHoras: 6,
    };

    const model = getCellDisplayModel(cell, 'revenue', params);
    expect(model.badges.some((b) => b.text === 'Base baixa')).toBeTrue();
    expect(model.badges.find((b) => b.text === 'Base baixa')?.tooltip).toContain('R$ 500,00');
  });

  it('gera modelo para célula NOVO', () => {
    const cell: TrendCell = {
      meses: 1,
      atual: 50,
      anterior: 0,
      variacaoPct: null,
      status: 'NOVO',
      baseParcial: false,
      baseBaixa: false,
      devolucaoLiquida: false,
      atualPorDia: null,
      anteriorPorDia: null,
    };

    const model = getCellDisplayModel(cell, 'quantity');
    expect(model.isNew).toBeTrue();
    expect(model.isNumeric).toBeFalse();
    expect(model.percentText).toBe('—');
    expect(model.ariaLabel).toContain('Produto novo');
  });

  it('verifica corretamente se todas as janelas têm semBase', () => {
    const allSemBase = [
      { meses: 1 as const, atual: {} as any, anterior: {} as any, semBase: true, baseParcial: false },
      { meses: 3 as const, atual: {} as any, anterior: {} as any, semBase: true, baseParcial: false },
    ];
    expect(isAllSemBase(allSemBase)).toBeTrue();

    const mixed = [
      { meses: 1 as const, atual: {} as any, anterior: {} as any, semBase: false, baseParcial: false },
      { meses: 3 as const, atual: {} as any, anterior: {} as any, semBase: true, baseParcial: false },
    ];
    expect(isAllSemBase(mixed)).toBeFalse();
  });
});
