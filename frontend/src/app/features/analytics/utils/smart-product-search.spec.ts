import { CatalogProductItem } from '../models/cross-sell.model';
import {
  extractSupplierOptions,
  filterAndSortCatalog,
  groupCatalogRows,
  normalizeRelaxedText,
  normalizeSearchText,
  scoreProductMatch,
  tokenizeSearchQuery,
} from './smart-product-search';

const SAMPLE_CATALOG: CatalogProductItem[] = [
  {
    codigo: 5001,
    descricao: 'WHEY 100% PURE GELATO',
    fornecedor: 'INTEGRALMEDICA',
    estoque: 25,
    precoVenda: 159.9,
  },
  {
    codigo: 5002,
    descricao: 'WHEY CONCENTRADO BAUNILHA 900G',
    fornecedor: 'INTEGRALMEDICA',
    estoque: 10,
    precoVenda: 139.9,
  },
  {
    codigo: 1003,
    descricao: 'CAMOMILA P/ CHÁ 30G',
    fornecedor: 'CATARINENSE',
    estoque: 0,
    precoVenda: 12.9,
  },
  {
    codigo: 1001,
    descricao: 'CHÁ VERDE SOLÚVEL 100G',
    fornecedor: 'CATARINENSE',
    estoque: 42,
    precoVenda: 24.5,
  },
  {
    codigo: 1042,
    descricao: 'EXTRATO DE PRÓPOLIS 30ML',
    fornecedor: 'APIS FLORA',
    estoque: 120,
    precoVenda: 28.5,
  },
];

describe('smart-product-search', () => {
  it('normaliza acentos, caixa e espaçamento em normalizeSearchText e normalizeRelaxedText', () => {
    expect(normalizeSearchText('  Extrato de Própolis 30mL  ')).toBe('extrato de propolis 30ml');
    expect(normalizeSearchText('WHEY 100% PURE')).toBe('whey 100% pure');
    expect(normalizeRelaxedText('CAMOMILA P/ CHÁ')).toBe('camomila p cha');
    expect(normalizeRelaxedText('WHEY 100% PURE')).toBe('whey 100 pure');
  });

  it('tokeniza query sem pontuação e remove duplicatas preservando ordem', () => {
    expect(tokenizeSearchQuery('  whey 100% gelato whey  ')).toEqual(['whey', '100', 'gelato']);
    expect(tokenizeSearchQuery('   ')).toEqual([]);
  });

  it('encontra "WHEY 100% PURE GELATO" ao buscar "whey 100% gelato" ou ordem trocada', () => {
    const whey = SAMPLE_CATALOG[0];
    const otherWhey = SAMPLE_CATALOG[1];

    expect(scoreProductMatch(whey, 'whey 100% gelato')).toBeGreaterThan(0);
    expect(scoreProductMatch(whey, 'gelato whey 100%')).toBeGreaterThan(0);
    expect(scoreProductMatch(otherWhey, 'whey 100% gelato')).toBe(0);
  });

  it('encontra pontuação opcional ("p cha" -> "P/ CHÁ"), acentos ignorados e combinação com fornecedor ou SKU', () => {
    const camomila = SAMPLE_CATALOG[2];
    const propolis = SAMPLE_CATALOG[4];

    expect(scoreProductMatch(camomila, 'p cha')).toBeGreaterThan(0);
    expect(scoreProductMatch(propolis, 'propolis apis')).toBeGreaterThan(0);
    expect(scoreProductMatch(propolis, '1042')).toBeGreaterThan(scoreProductMatch(propolis, 'propolis'));
  });

  it('aplica tolerância leve a erro de digitação apenas em palavras >= 5 letras sem falso positivo para "xyzw"', () => {
    const whey = SAMPLE_CATALOG[0];
    const propolis = SAMPLE_CATALOG[4];

    // Transposição / omissão em palavra >= 5 letras
    expect(scoreProductMatch(whey, 'whey 100% geltao')).toBeGreaterThan(0);
    expect(scoreProductMatch(propolis, 'extrato prpolis')).toBeGreaterThan(0);

    // Query curta aleatória (< 5 chars) não deve gerar falso positivo
    for (const item of SAMPLE_CATALOG) {
      expect(scoreProductMatch(item, 'xyzw')).toBe(0);
    }
  });

  it('prioriza prefixo e substring exato acima de matches parciais', () => {
    const exactPrefix: CatalogProductItem = {
      codigo: 1,
      descricao: 'CHA VERDE 100G',
      fornecedor: 'A',
      estoque: 10,
      precoVenda: 20,
    };
    const middleSubstring: CatalogProductItem = {
      codigo: 2,
      descricao: 'CAPSULA DE CHA VERDE',
      fornecedor: 'A',
      estoque: 10,
      precoVenda: 20,
    };
    const splitWords: CatalogProductItem = {
      codigo: 3,
      descricao: 'CHA COM HORTELA E EXTRATO VERDE',
      fornecedor: 'A',
      estoque: 10,
      precoVenda: 20,
    };

    const scorePrefix = scoreProductMatch(exactPrefix, 'cha verde');
    const scoreSub = scoreProductMatch(middleSubstring, 'cha verde');
    const scoreSplit = scoreProductMatch(splitWords, 'cha verde');

    expect(scorePrefix).toBeGreaterThan(scoreSub);
    expect(scoreSub).toBeGreaterThan(scoreSplit);
  });

  it('ordena por padrão por fornecedor A→Z e produto A→Z, e agrupa corretamente', () => {
    const sorted = filterAndSortCatalog(SAMPLE_CATALOG);
    expect(sorted.map((p) => p.codigo)).toEqual([
      1042, // APIS FLORA
      1003, // CATARINENSE - CAMOMILA...
      1001, // CATARINENSE - CHÁ VERDE...
      5001, // INTEGRALMEDICA - WHEY 100%...
      5002, // INTEGRALMEDICA - WHEY CONCENTRADO...
    ]);

    const groups = groupCatalogRows(sorted);
    expect(groups.map((g) => g.supplier)).toEqual(['APIS FLORA', 'CATARINENSE', 'INTEGRALMEDICA']);
    expect(groups[1].items.map((i) => i.codigo)).toEqual([1003, 1001]);
  });

  it('aplica filtros de fornecedor, estoque e ordenações diversas', () => {
    const outOfStock = filterAndSortCatalog(SAMPLE_CATALOG, { stockFilter: 'out-of-stock' });
    expect(outOfStock.map((p) => p.codigo)).toEqual([1003]);

    const inStockCatarinense = filterAndSortCatalog(SAMPLE_CATALOG, {
      supplier: 'CATARINENSE',
      stockFilter: 'in-stock',
    });
    expect(inStockCatarinense.map((p) => p.codigo)).toEqual([1001]);

    const byPriceDesc = filterAndSortCatalog(SAMPLE_CATALOG, { sortBy: 'price-desc' });
    expect(byPriceDesc[0].codigo).toBe(5001);
    expect(byPriceDesc[byPriceDesc.length - 1].codigo).toBe(1003);

    const byNameDesc = filterAndSortCatalog(SAMPLE_CATALOG, { sortBy: 'name-desc' });
    expect(byNameDesc[0].codigo).toBe(5002);

    const bySkuAsc = filterAndSortCatalog(SAMPLE_CATALOG, { sortBy: 'sku-asc' });
    expect(bySkuAsc.map((p) => p.codigo)).toEqual([1001, 1003, 1042, 5001, 5002]);
  });

  it('extrai fornecedores em ordem alfabética pt-BR com contagem', () => {
    const options = extractSupplierOptions(SAMPLE_CATALOG);
    expect(options).toEqual([
      { name: 'APIS FLORA', count: 1 },
      { name: 'CATARINENSE', count: 2 },
      { name: 'INTEGRALMEDICA', count: 2 },
    ]);
  });

  describe('filtros e ordenações sazonais', () => {
    const SEASONAL_CATALOG: CatalogProductItem[] = [
      {
        codigo: 1042,
        descricao: 'EXTRATO DE PRÓPOLIS 30ML',
        fornecedor: 'APIS FLORA',
        estoque: 120,
        precoVenda: 28.5,
        forca: 'FORTE',
        amplitude: 0.77,
        mesPico: 'Mai–Jul',
        mesVale: 'Nov–Jan',
        faturamentoTotal: 145000,
        motivoInsuficiencia: null,
      },
      {
        codigo: 1001,
        descricao: 'CHÁ VERDE SOLÚVEL 100G',
        fornecedor: 'CATARINENSE',
        estoque: 42,
        precoVenda: 24.5,
        forca: 'MODERADA',
        amplitude: 0.35,
        mesPico: 'Jan–Mar',
        mesVale: 'Jul–Set',
        faturamentoTotal: 210000,
        motivoInsuficiencia: null,
      },
      {
        codigo: 2002,
        descricao: 'WHEY 100% PURE GELATO',
        fornecedor: 'INTEGRALMEDICA',
        estoque: 18,
        precoVenda: 159.9,
        forca: 'FRACA',
        amplitude: 0.12,
        mesPico: 'Out–Dez',
        mesVale: 'Abr–Jun',
        faturamentoTotal: 320000,
        motivoInsuficiencia: null,
      },
      {
        codigo: 1003,
        descricao: 'CAMOMILA P/ CHÁ 30G',
        fornecedor: 'CATARINENSE',
        estoque: 0,
        precoVenda: 12.9,
        forca: 'INSUFICIENTE',
        amplitude: 0,
        mesPico: null,
        mesVale: null,
        faturamentoTotal: 1500,
        motivoInsuficiencia: 'VENDA_ESPORADICA',
      },
    ];

    it('filtra por strengthFilter (measurable, FORTE, MODERADA, FRACA e INSUFICIENTE)', () => {
      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { strengthFilter: 'measurable' }).map((p) => p.codigo),
      ).toEqual([1042, 1001, 2002]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { strengthFilter: 'FORTE' }).map((p) => p.codigo),
      ).toEqual([1042]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { strengthFilter: 'MODERADA' }).map((p) => p.codigo),
      ).toEqual([1001]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { strengthFilter: 'FRACA' }).map((p) => p.codigo),
      ).toEqual([2002]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { strengthFilter: 'INSUFICIENTE' }).map((p) => p.codigo),
      ).toEqual([1003]);
    });

    it('ordena por amplitude-desc, amplitude-asc e revenue-desc mantendo INSUFICIENTE ao final na amplitude', () => {
      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { sortBy: 'amplitude-desc' }).map((p) => p.codigo),
      ).toEqual([1042, 1001, 2002, 1003]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { sortBy: 'amplitude-asc' }).map((p) => p.codigo),
      ).toEqual([2002, 1001, 1042, 1003]);

      expect(
        filterAndSortCatalog(SEASONAL_CATALOG, { sortBy: 'revenue-desc' }).map((p) => p.codigo),
      ).toEqual([2002, 1001, 1042, 1003]);
    });

    it('mantém ordenação padrão Fornecedor A→Z · Produto A→Z mesmo com campos sazonais', () => {
      expect(filterAndSortCatalog(SEASONAL_CATALOG).map((p) => p.codigo)).toEqual([
        1042, // APIS FLORA
        1003, // CATARINENSE - CAMOMILA...
        1001, // CATARINENSE - CHÁ VERDE...
        2002, // INTEGRALMEDICA
      ]);
    });
  });
});
