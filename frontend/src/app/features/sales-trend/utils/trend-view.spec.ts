/**
 * Testes unitários para utilitários de view-model (T-16).
 */
import { getCellDisplayModel, isAllSemBase } from './trend-view';
import { TrendCell } from '../models/sales-trend.model';

describe('trend-view utils (T-16)', () => {
  it('gera modelo para célula VARIACAO com alta e formatação monetária', () => {
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
    expect(model.badges.length).toBe(0);
    expect(model.currentDailyText).toContain('/dia');
    expect(model.ariaLabel).toContain('alta de +50,0%');
  });

  it('gera badge para célula com devolução líquida', () => {
    const cell: TrendCell = {
      meses: 3,
      atual: 0,
      anterior: 200,
      variacaoPct: -100.0,
      status: 'VARIACAO',
      baseParcial: false,
      baseBaixa: false,
      devolucaoLiquida: true,
      atualPorDia: null,
      anteriorPorDia: null,
    };

    const model = getCellDisplayModel(cell, 'revenue');
    expect(model.badges.some((b) => b.text === 'Devoluções > vendas')).toBeTrue();
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
