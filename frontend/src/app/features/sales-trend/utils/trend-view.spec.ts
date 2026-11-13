/**
 * Testes unitários para utilitários de view-model (T-16).
 */
import { getCellDisplayModel, isAllSemBase } from './trend-view';
import { TrendCell, TrendWindowSpan } from '../models/sales-trend.model';

function createSpan(inicio: string, fim: string): TrendWindowSpan {
  return {
    inicio,
    fim,
    diasJanela: 30,
    diasCobertos: 30,
  };
}

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
    expect(model.currentDailyText).toBe('R$ 50,00/dia');
    expect(model.previousDailyText).toBe('R$ 33,33/dia');
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

  it('trata variação que arredonda para 0,0% (-0,04) como direção flat sem seta negativa', () => {
    const cell: TrendCell = {
      meses: 1,
      atual: 99.96,
      anterior: 100,
      variacaoPct: -0.04,
      status: 'VARIACAO',
      baseParcial: false,
      baseBaixa: false,
      devolucaoLiquida: false,
      atualPorDia: null,
      anteriorPorDia: null,
    };

    const model = getCellDisplayModel(cell, 'revenue');
    expect(model.percentText).toBe('0,0%');
    expect(model.direction).toBe('flat');
    expect(model.ariaLabel).toBe('estável em 0,0%');
  });

  it('verifica corretamente se todas as janelas têm semBase', () => {
    const allSemBase = [
      {
        meses: 1 as const,
        atual: createSpan('2026-10-01', '2026-10-31'),
        anterior: createSpan('2026-09-01', '2026-09-30'),
        semBase: true,
        baseParcial: false,
      },
      {
        meses: 3 as const,
        atual: createSpan('2026-08-01', '2026-10-31'),
        anterior: createSpan('2026-05-01', '2026-07-31'),
        semBase: true,
        baseParcial: false,
      },
    ];
    expect(isAllSemBase(allSemBase)).toBeTrue();

    const mixed = [
      {
        meses: 1 as const,
        atual: createSpan('2026-10-01', '2026-10-31'),
        anterior: createSpan('2026-09-01', '2026-09-30'),
        semBase: false,
        baseParcial: false,
      },
      {
        meses: 3 as const,
        atual: createSpan('2026-08-01', '2026-10-31'),
        anterior: createSpan('2026-05-01', '2026-07-31'),
        semBase: true,
        baseParcial: false,
      },
    ];
    expect(isAllSemBase(mixed)).toBeFalse();
  });
});
