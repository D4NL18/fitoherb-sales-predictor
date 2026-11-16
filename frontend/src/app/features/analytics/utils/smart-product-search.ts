import { CatalogProductItem } from '../models/cross-sell.model';

export type CatalogStockFilter = 'all' | 'in-stock' | 'out-of-stock';

export type SeasonalityStrengthFilter =
  | 'all'
  | 'measurable'
  | 'FORTE'
  | 'MODERADA'
  | 'FRACA'
  | 'INSUFICIENTE';

export type CatalogSortKey =
  | 'supplier-asc'
  | 'supplier-desc'
  | 'relevance'
  | 'name-asc'
  | 'name-desc'
  | 'price-desc'
  | 'price-asc'
  | 'stock-desc'
  | 'stock-asc'
  | 'sku-asc'
  | 'sku-desc'
  | 'amplitude-desc'
  | 'amplitude-asc'
  | 'revenue-desc';

export type CatalogSortOption = CatalogSortKey;

export interface CatalogFilterOptions {
  query?: string;
  supplier?: string;
  stockFilter?: CatalogStockFilter;
  strengthFilter?: SeasonalityStrengthFilter;
  sortBy?: CatalogSortKey;
}

export interface CatalogGroup {
  supplier: string;
  items: CatalogProductItem[];
}

export interface SupplierOption {
  name: string;
  count: number;
}

const PT_BR_COLLATOR = new Intl.Collator('pt-BR', { sensitivity: 'base', numeric: true });
const MIN_FUZZY_TOKEN_LENGTH = 5;
const MIN_FUZZY_WORD_LENGTH = 4;
const FALLBACK_SUPPLIER = 'Sem fornecedor';

/** Normaliza texto removendo diacríticos, convertendo para minúsculas e colapsando espaços. */
export function normalizeSearchText(value: string): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/** Normaliza texto substituindo pontuação/símbolos por espaço para busca flexível ("p cha" -> "p/ chá"). */
export function normalizeRelaxedText(value: string): string {
  return normalizeSearchText(value)
    .replace(/[^\p{L}\p{N}\s]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Quebra a query em tokens únicos normalizados sem pontuação. */
export function tokenizeSearchQuery(query: string): string[] {
  const relaxed = normalizeRelaxedText(query);
  if (!relaxed) return [];
  const unique: string[] = [];
  for (const part of relaxed.split(' ')) {
    if (part && !unique.includes(part)) {
      unique.push(part);
    }
  }
  return unique;
}

/** Calcula relevância (> 0 se compatível, 0 caso contrário) com AND entre tokens, prefixo e tolerância leve a erro. */
export function scoreProductMatch(product: CatalogProductItem, query: string): number {
  const rawNormQuery = normalizeSearchText(query);
  const relaxedQuery = normalizeRelaxedText(query);
  const tokens = tokenizeSearchQuery(query);
  if (tokens.length === 0) return 0;

  const skuStr = String(product.codigo);
  const descNorm = normalizeSearchText(product.descricao);
  const descRelaxed = normalizeRelaxedText(product.descricao);
  const descWords = descRelaxed ? descRelaxed.split(' ') : [];

  const suppNorm = normalizeSearchText(product.fornecedor);
  const suppRelaxed = normalizeRelaxedText(product.fornecedor);
  const suppWords = suppRelaxed ? suppRelaxed.split(' ') : [];

  let tokenScoreSum = 0;
  for (const token of tokens) {
    const score = scoreSingleToken(token, skuStr, descRelaxed, descWords, suppRelaxed, suppWords);
    if (score === 0) {
      return 0;
    }
    tokenScoreSum += score;
  }

  let total = tokenScoreSum;

  if (skuStr === rawNormQuery) {
    total += 1000;
  } else if (descNorm === rawNormQuery || descRelaxed === relaxedQuery) {
    total += 600;
  } else if (descNorm.startsWith(rawNormQuery) || descRelaxed.startsWith(relaxedQuery)) {
    total += 300;
  } else if (descNorm.includes(rawNormQuery) || descRelaxed.includes(relaxedQuery)) {
    total += 160;
  }

  if (tokens.length > 1 && areTokensInOrder(tokens, descRelaxed)) {
    total += 45;
  }
  if (rawNormQuery !== relaxedQuery && descNorm.includes(rawNormQuery)) {
    total += 25;
  }
  if (suppNorm.startsWith(rawNormQuery) || suppRelaxed.startsWith(relaxedQuery)) {
    total += 60;
  } else if (suppNorm.includes(rawNormQuery) || suppRelaxed.includes(relaxedQuery)) {
    total += 30;
  }

  return total;
}

/** Filtra por busca inteligente, fornecedor, estoque e força sazonal, aplicando a ordenação escolhida. */
export function filterAndSortCatalog(
  items: readonly CatalogProductItem[],
  options: CatalogFilterOptions = {},
): CatalogProductItem[] {
  const query = options.query?.trim() ?? '';
  const supplierFilter = options.supplier?.trim() ?? '';
  const stockFilter = options.stockFilter ?? 'all';
  const strengthFilter = options.strengthFilter ?? 'all';
  const sortBy = options.sortBy ?? 'supplier-asc';
  const hasQuery = tokenizeSearchQuery(query).length > 0;

  const matched: Array<{ item: CatalogProductItem; score: number }> = [];

  for (const item of items) {
    if (supplierFilter && normalizeSupplier(item.fornecedor) !== supplierFilter) {
      continue;
    }
    if (stockFilter === 'in-stock' && item.estoque <= 0) {
      continue;
    }
    if (stockFilter === 'out-of-stock' && item.estoque > 0) {
      continue;
    }
    if (!matchesStrengthFilter(item, strengthFilter)) {
      continue;
    }

    const score = hasQuery ? scoreProductMatch(item, query) : 0;
    if (hasQuery && score <= 0) {
      continue;
    }

    matched.push({ item, score });
  }

  matched.sort((a, b) => compareCatalogEntries(a, b, sortBy, hasQuery));
  return matched.map((entry) => entry.item);
}

function matchesStrengthFilter(
  item: CatalogProductItem,
  filter: SeasonalityStrengthFilter,
): boolean {
  if (filter === 'all') return true;
  if (filter === 'measurable') {
    return item.forca != null && item.forca !== 'INSUFICIENTE';
  }
  if (filter === 'INSUFICIENTE') {
    return item.forca == null || item.forca === 'INSUFICIENTE';
  }
  return item.forca === filter;
}

/** Agrupa linhas mantendo a ordem de aparição dos fornecedores já ordenados. */
export function groupCatalogRows(items: readonly CatalogProductItem[]): CatalogGroup[] {
  const groups = new Map<string, CatalogProductItem[]>();
  for (const item of items) {
    const supplier = normalizeSupplier(item.fornecedor);
    const bucket = groups.get(supplier);
    if (bucket) {
      bucket.push(item);
    } else {
      groups.set(supplier, [item]);
    }
  }
  return Array.from(groups.entries(), ([supplier, groupItems]) => ({
    supplier,
    items: groupItems,
  }));
}

/** Extrai lista de fornecedores ordenada em pt-BR com a contagem de itens no catálogo. */
export function extractSupplierOptions(items: readonly CatalogProductItem[]): SupplierOption[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const supplier = normalizeSupplier(item.fornecedor);
    counts.set(supplier, (counts.get(supplier) ?? 0) + 1);
  }
  return Array.from(counts.entries(), ([name, count]) => ({ name, count })).sort((a, b) =>
    PT_BR_COLLATOR.compare(a.name, b.name),
  );
}

function normalizeSupplier(fornecedor: string | null | undefined): string {
  const trimmed = (fornecedor ?? '').trim();
  return trimmed || FALLBACK_SUPPLIER;
}

function scoreSingleToken(
  token: string,
  skuStr: string,
  descRelaxed: string,
  descWords: readonly string[],
  suppRelaxed: string,
  suppWords: readonly string[],
): number {
  let best = 0;

  if (skuStr === token) {
    best = Math.max(best, 120);
  } else if (skuStr.startsWith(token)) {
    best = Math.max(best, 70);
  } else if (skuStr.includes(token)) {
    best = Math.max(best, 30);
  }

  for (const word of descWords) {
    if (word === token) {
      best = Math.max(best, 55);
      break;
    }
    if (word.startsWith(token)) {
      best = Math.max(best, 40);
    }
  }

  if (best < 24 && descRelaxed.includes(token)) {
    best = Math.max(best, 24);
  }

  for (const word of suppWords) {
    if (word === token) {
      best = Math.max(best, 28);
      break;
    }
    if (word.startsWith(token)) {
      best = Math.max(best, 20);
    }
  }

  if (best < 12 && suppRelaxed.includes(token)) {
    best = Math.max(best, 12);
  }

  if (best === 0 && token.length >= MIN_FUZZY_TOKEN_LENGTH) {
    if (descWords.some((w) => w.length >= MIN_FUZZY_WORD_LENGTH && isWithinOneEdit(token, w))) {
      best = 10;
    } else if (suppWords.some((w) => w.length >= MIN_FUZZY_WORD_LENGTH && isWithinOneEdit(token, w))) {
      best = 6;
    }
  }

  return best;
}

function areTokensInOrder(tokens: readonly string[], text: string): boolean {
  let cursor = 0;
  for (const token of tokens) {
    const idx = text.indexOf(token, cursor);
    if (idx === -1) return false;
    cursor = idx + token.length;
  }
  return true;
}

/** Verifica distância Damerau-Levenshtein <= 1 (substituição, inserção, remoção ou transposição adjacente). */
function isWithinOneEdit(a: string, b: string): boolean {
  const lenA = a.length;
  const lenB = b.length;
  if (Math.abs(lenA - lenB) > 1) return false;

  if (lenA === lenB) {
    const diffs: number[] = [];
    for (let i = 0; i < lenA; i++) {
      if (a[i] !== b[i]) {
        diffs.push(i);
        if (diffs.length > 2) return false;
      }
    }
    if (diffs.length <= 1) return true;
    const [first, second] = diffs;
    return second === first + 1 && a[first] === b[second] && a[second] === b[first];
  }

  const shorter = lenA < lenB ? a : b;
  const longer = lenA < lenB ? b : a;
  let i = 0;
  let j = 0;
  let skipped = false;

  while (i < shorter.length && j < longer.length) {
    if (shorter[i] === longer[j]) {
      i++;
      j++;
    } else if (skipped) {
      return false;
    } else {
      skipped = true;
      j++;
    }
  }
  return true;
}

function compareCatalogEntries(
  a: { item: CatalogProductItem; score: number },
  b: { item: CatalogProductItem; score: number },
  sortBy: CatalogSortKey,
  hasQuery: boolean,
): number {
  switch (sortBy) {
    case 'relevance': {
      if (hasQuery && a.score !== b.score) {
        return b.score - a.score;
      }
      return compareBySupplierAndName(a.item, b.item);
    }
    case 'supplier-asc':
      return compareBySupplierAndName(a.item, b.item);
    case 'supplier-desc': {
      const supCmp = PT_BR_COLLATOR.compare(
        normalizeSupplier(b.item.fornecedor),
        normalizeSupplier(a.item.fornecedor),
      );
      if (supCmp !== 0) return supCmp;
      return compareByNameAndSku(a.item, b.item);
    }
    case 'name-asc':
      return compareByNameAndSku(a.item, b.item);
    case 'name-desc': {
      const nameCmp = PT_BR_COLLATOR.compare(b.item.descricao, a.item.descricao);
      return nameCmp !== 0 ? nameCmp : a.item.codigo - b.item.codigo;
    }
    case 'price-desc':
      return b.item.precoVenda - a.item.precoVenda || compareByNameAndSku(a.item, b.item);
    case 'price-asc':
      return a.item.precoVenda - b.item.precoVenda || compareByNameAndSku(a.item, b.item);
    case 'stock-desc':
      return b.item.estoque - a.item.estoque || compareByNameAndSku(a.item, b.item);
    case 'stock-asc':
      return a.item.estoque - b.item.estoque || compareByNameAndSku(a.item, b.item);
    case 'sku-asc':
      return a.item.codigo - b.item.codigo;
    case 'sku-desc':
      return b.item.codigo - a.item.codigo;
    case 'amplitude-desc':
      return compareByAmplitude(a.item, b.item, 'desc');
    case 'amplitude-asc':
      return compareByAmplitude(a.item, b.item, 'asc');
    case 'revenue-desc':
      return compareByRevenueDesc(a.item, b.item);
  }
}

function compareByAmplitude(
  a: CatalogProductItem,
  b: CatalogProductItem,
  direction: 'asc' | 'desc',
): number {
  const aMeasurable = isMeasurableAmplitude(a);
  const bMeasurable = isMeasurableAmplitude(b);
  if (aMeasurable !== bMeasurable) {
    return aMeasurable ? -1 : 1;
  }
  if (!aMeasurable && !bMeasurable) {
    return compareByRevenueDesc(a, b);
  }
  const ampA = a.amplitude ?? 0;
  const ampB = b.amplitude ?? 0;
  const diff = direction === 'desc' ? ampB - ampA : ampA - ampB;
  if (diff !== 0) return diff;
  return direction === 'desc' ? compareByRevenueDesc(a, b) : compareByNameAndSku(a, b);
}

function isMeasurableAmplitude(item: CatalogProductItem): boolean {
  return (
    item.amplitude !== null &&
    item.amplitude !== undefined &&
    Number.isFinite(item.amplitude) &&
    item.forca !== 'INSUFICIENTE'
  );
}

function compareByRevenueDesc(a: CatalogProductItem, b: CatalogProductItem): number {
  const hasA = a.faturamentoTotal !== null && a.faturamentoTotal !== undefined && Number.isFinite(a.faturamentoTotal);
  const hasB = b.faturamentoTotal !== null && b.faturamentoTotal !== undefined && Number.isFinite(b.faturamentoTotal);
  if (hasA !== hasB) {
    return hasA ? -1 : 1;
  }
  const revDiff = (b.faturamentoTotal ?? 0) - (a.faturamentoTotal ?? 0);
  return revDiff !== 0 ? revDiff : compareByNameAndSku(a, b);
}

function compareBySupplierAndName(a: CatalogProductItem, b: CatalogProductItem): number {
  const supCmp = PT_BR_COLLATOR.compare(
    normalizeSupplier(a.fornecedor),
    normalizeSupplier(b.fornecedor),
  );
  if (supCmp !== 0) return supCmp;
  return compareByNameAndSku(a, b);
}

function compareByNameAndSku(a: CatalogProductItem, b: CatalogProductItem): number {
  const nameCmp = PT_BR_COLLATOR.compare(a.descricao, b.descricao);
  return nameCmp !== 0 ? nameCmp : a.codigo - b.codigo;
}
