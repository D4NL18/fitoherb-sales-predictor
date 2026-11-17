/**
 * Modelos TypeScript da Feature Churn de Clientes (Contrato analytics-churn v1.0.0; P-117 a P-127).
 */
import { AnalyticsMeta, PagedMeta } from './analytics.model';

export type ChurnStatus = 'EM_RISCO' | 'ALERTA' | 'SAUDAVEL' | 'INATIVO_RECUPERACAO';

export type ChurnApiStatusFilter = 'EM_RISCO' | 'ALERTA' | 'SAUDAVEL' | 'TODOS' | 'TODOS_GERAL';

export type ChurnStatusFilter = ChurnApiStatusFilter | 'INATIVO_RECUPERACAO';

export type ChurnSortField =
  | 'customerCode'
  | 'customerName'
  | 'sellerName'
  | 'city'
  | 'status'
  | 'diasSemComprar'
  | 'gapTipico'
  | 'dataUltimoPedido'
  | 'faturamentoMedioMensal'
  | 'scorePrioridade';

export type ChurnSortDirection = 'asc' | 'desc';

export interface ChurnQueryOptions {
  q?: string;
  seller?: string;
  city?: string;
  sortBy?: ChurnSortField | null;
  sortDir?: ChurnSortDirection;
}

export interface ChurnFilterOptionsResponse {
  data: {
    sellers: string[];
    cities: string[];
  };
  meta: AnalyticsMeta;
}

export interface ChurnSummaryKpi {
  totalEmRisco: number;
  totalAlerta: number;
  totalSaudavel: number;
  totalInativos: number;
  receitaMensalEmRisco: number;
}

export interface ChurnCustomerItem {
  customerCode: number;
  customerName?: string;
  sellerName?: string;
  city?: string;
  status: ChurnStatus;
  diasSemComprar: number;
  gapTipico: number | null;
  diasReferencia: number;
  fatorTempo: number;
  faturamentoMedioMensal: number;
  scorePrioridade: number;
  historicoCurto: boolean;
  dataUltimoPedido?: string | null;
}

/** Linha unificada da tabela (ativos têm score/régua; inativos antigos usam faturamento e data do último pedido). */
export interface ChurnTableRow {
  customerCode: number;
  customerName: string;
  sellerName: string;
  city: string;
  status: ChurnStatus;
  diasSemComprar: number;
  gapTipico: number | null;
  diasReferencia: number | null;
  fatorTempo: number | null;
  faturamentoMedioMensal: number;
  scorePrioridade: number | null;
  historicoCurto: boolean;
  dataUltimoPedido: string | null;
}

export interface ChurnCustomersData {
  resumo: ChurnSummaryKpi;
  items: ChurnCustomerItem[];
}

export interface ChurnCustomersResponse {
  data: ChurnCustomersData;
  meta: PagedMeta;
}

export interface MonthlyHistoryItem {
  anoMes: string;
  faturamentoLiquido: number;
  qtdPedidos: number;
}

export interface LostProductItem {
  sku: number;
  descricao: string;
  fornecedor: string;
  faturamentoHistorico: number;
  dataUltimaCompra: string;
}

export interface CustomerChurnDetailData {
  customerCode: number;
  customerName?: string;
  sellerName?: string;
  city?: string;
  status: ChurnStatus;
  diasSemComprar: number;
  dataUltimoPedido: string | null;
  gapTipico: number | null;
  diasReferencia: number;
  fatorTempo: number;
  faturamentoMedioMensal: number;
  scorePrioridade: number;
  historicoCurto: boolean;
  variacaoReceitaTrimestralPct: number | null;
  historicoMensal: MonthlyHistoryItem[];
  produtosPerdidos: LostProductItem[];
}

export interface CustomerChurnDetailResponse {
  data: CustomerChurnDetailData;
  meta: AnalyticsMeta;
}

export interface InactiveCustomerItem {
  customerCode: number;
  customerName?: string;
  sellerName?: string;
  city?: string;
  status: ChurnStatus;
  diasSemComprar: number;
  dataUltimoPedido: string | null;
  faturamentoMedioMensal: number;
  historicoCurto: boolean;
}

export interface InactiveChurnData {
  totalInativos: number;
  items: InactiveCustomerItem[];
}

export interface InactiveChurnResponse {
  data: InactiveChurnData;
  meta: PagedMeta;
}
