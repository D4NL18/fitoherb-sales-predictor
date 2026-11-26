import { MECHANISM_VISUAL_META } from './cannibalization-mechanism';

describe('MECHANISM_VISUAL_META', () => {
  it('cobre os três mecanismos com rótulo e símbolo', () => {
    expect(Object.keys(MECHANISM_VISUAL_META).sort()).toEqual([
      'MIGRACAO_POR_VALOR',
      'PRECO_MENOR_DESTROI_MARGEM',
      'PRECO_MENOR_MARGEM_PRESERVADA',
    ]);
    expect(MECHANISM_VISUAL_META.PRECO_MENOR_DESTROI_MARGEM.label).toBe('Reajustar canibalizador');
    expect(MECHANISM_VISUAL_META.MIGRACAO_POR_VALOR.symbol).toBe('↗');
  });
});
