/**
 * Tipos e interfaces TypeScript para a feature Tendência de Vendas (módulo sales_trend).
 * Mapeia 1:1 o Contrato de API REST 1.0.0 (P-072 a P-093).
 * Não utiliza 'any'.
 */

export type TrendErrorCode = 'TND-001' | 'TND-002' | 'TND-003' | 'TND-004' | 'TND-005';

export type TrendCellStatus = 'VARIACAO' | 'NOVO' | 'SEM_MOVIMENTO' | 'SEM_BASE';

export type TrendMetric = 'quantity' | 'revenue';

export type TrendGroupBy = 'product' | 'supplier';

export type TrendView = 'all' | 'rising' | 'falling' | 'new';

export type TrendSortDir = 'asc' | 'desc';

export type TrendSortBy = 'contribution' | 'variation';

export type TrendSortWindow = 1 | 3 | 6 | 12;

export interface TrendParameters {
  limiteBaseBaixaQuantidade: number;
  limiteBaseBaixaFaturamento: number;
  coberturaMinimaAnterior: number;
  buscaMinCaracteres: number;
  buscaMinCaracteresNumerica: number;
  buscaMaxCaracteres: number;
  ttlCacheHoras: number;
}

export interface TrendWindowSpan {
  inicio: string;
  fim: string;
  diasJanela: number;
  diasCobertos: number;
}

export interface TrendWindowMeta {
  meses: TrendSortWindow;
  atual: TrendWindowSpan;
  anterior: TrendWindowSpan;
  semBase: boolean;
  baseParcial: boolean;
}

export interface TrendTotaisPorVisao {
  todos: number;
  maioresAltas: number;
  maioresQuedas: number;
  novos: number;
}

export interface TrendCell {
  meses: TrendSortWindow;
  atual: number;
  anterior: number;
  variacaoPct: number | null;
  status: TrendCellStatus;
  baseParcial: boolean;
  baseBaixa: boolean;
  devolucaoLiquida: boolean;
  atualPorDia: number | null;
  anteriorPorDia: number | null;
}

export interface TrendDetailCell extends TrendCell {
  contribuicaoPp: number | null;
  contribuicaoValor: number | null;
}

export interface TrendProductRow {
  codigo: number;
  descricao: string;
  fornecedor: string | null;
  janelas: [TrendCell, TrendCell, TrendCell, TrendCell] | TrendCell[];
}

export interface TrendSupplierRow {
  fornecedor: string;
  fornecedorChave: string;
  semFornecedor: boolean;
  qtdProdutos: number;
  janelas: [TrendCell, TrendCell, TrendCell, TrendCell] | TrendCell[];
}

export interface TrendDetailRow {
  codigo: number;
  descricao: string;
  fornecedor: string | null;
  janelas: [TrendDetailCell, TrendDetailCell, TrendDetailCell, TrendDetailCell] | TrendDetailCell[];
}

export interface TrendTotalRow {
  qtdProdutos: number;
  janelas: [TrendCell, TrendCell, TrendCell, TrendCell] | TrendCell[];
}

export interface TrendMeta {
  timestamp: string;
  version: string;
  dataReferencia: string;
  ultimoDiaCoberto: string;
  mesBase: string;
  mesBasePadrao: string;
  mesBaseMinimo: string;
  mesBaseMaximo: string;
  mesBaseParcial: boolean;
  metrica: TrendMetric;
  janelas: [TrendWindowMeta, TrendWindowMeta, TrendWindowMeta, TrendWindowMeta] | TrendWindowMeta[];
  parametros: TrendParameters;
  page: number;
  limit: number;
  offset: number;
  totalItems: number;
  totalPages: number;
}

export interface TrendListMeta extends TrendMeta {
  agrupamento: TrendGroupBy;
  visao: TrendView;
  ordenacao: {
    janela: TrendSortWindow;
    sentido: TrendSortDir;
  };
  totaisPorVisao: TrendTotaisPorVisao;
  total: TrendTotalRow;
}

export interface TrendDetailMeta extends TrendMeta {
  ordenacao: {
    por: TrendSortBy;
    janela: TrendSortWindow;
    sentido: TrendSortDir;
  };
  fornecedor: TrendSupplierRow;
}

export interface ProductTrendResponse {
  data: TrendProductRow[];
  meta: TrendListMeta;
}

export interface SupplierTrendResponse {
  data: TrendSupplierRow[];
  meta: TrendListMeta;
}

export interface SupplierDetailResponse {
  data: TrendDetailRow[];
  meta: TrendDetailMeta;
}

export interface SalesTrendCacheResponse {
  estado: 'FRIO' | 'CARREGANDO' | 'QUENTE' | 'EXPIRADO';
  dataReferencia: string | null;
  carregadoEm: string | null;
  idadeHoras: number | null;
  expirado: boolean;
  duracaoUltimaCargaMs: number | null;
  carregando: boolean;
  contagens: {
    skusAtivos: number;
    skusComVenda: number;
    fornecedores: number;
    mesesHistorico: number;
    linhasAgregadas: number;
  } | null;
}

export interface TrendErrorPayload {
  code: TrendErrorCode;
  message: string;
  fields?: string[];
}

export interface TrendErrorResponse {
  error: TrendErrorPayload;
  meta: {
    timestamp: string;
    version: string;
  };
}

export interface TrendQueryParams {
  baseMonth?: string;
  metric?: TrendMetric;
  groupBy?: TrendGroupBy;
  sortWindow?: TrendSortWindow;
  sortDir?: TrendSortDir;
  view?: TrendView;
  q?: string;
  minVolume?: number;
  limit?: number;
  offset?: number;
}

export interface SupplierProductsQueryParams {
  supplierKey: string;
  baseMonth?: string;
  metric?: TrendMetric;
  sortBy?: TrendSortBy;
  sortWindow?: TrendSortWindow;
  sortDir?: TrendSortDir;
  q?: string;
  limit?: number;
  offset?: number;
}
