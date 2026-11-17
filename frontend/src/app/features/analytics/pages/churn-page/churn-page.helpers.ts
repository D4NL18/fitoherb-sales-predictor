/**
 * Funções puras auxiliares da página e drawer de Churn de Clientes (P-117 a P-127, LGPD-CHU-01..05).
 * Sem dependência de DOM ou HTTP: mapeamento de status, mensagens de erro seguras, formatação e CSV.
 */
import { HttpErrorResponse } from '@angular/common/http';
import {
  ChurnCustomerItem,
  ChurnStatus,
  ChurnStatusFilter,
  ChurnTableRow,
  InactiveCustomerItem,
  MonthlyHistoryItem,
} from '../../models/churn.model';
import { formatIsoDate } from '../../utils/pt-br-format';

export type ChurnStatusIcon = 'alert' | 'clock' | 'check' | 'pause';

export interface ChurnStatusDisplay {
  label: string;
  tagClass: string;
  icon: ChurnStatusIcon;
}

export const CHURN_STATUS_DISPLAY: Record<ChurnStatus, ChurnStatusDisplay> = {
  EM_RISCO: { label: 'Em risco', tagClass: 'tag-critical', icon: 'alert' },
  ALERTA: { label: 'Em alerta', tagClass: 'tag-warning', icon: 'clock' },
  SAUDAVEL: { label: 'Saudável', tagClass: 'tag-positive', icon: 'check' },
  INATIVO_RECUPERACAO: { label: 'Inativo antigo', tagClass: 'tag-neutral', icon: 'pause' },
};

const CHURN_ERROR_MESSAGES: Record<string, string> = {
  'CHU-001': 'Cliente não encontrado ou sem histórico de compras válidas.',
  'CHU-002': 'Base de vendas insuficiente para calcular os indicadores de churn.',
  'CHU-003': 'Parâmetros de filtro inválidos. Recarregue a consulta.',
  'ANL-001': 'Base de vendas indisponível no momento. Tente novamente em instantes.',
  'ANL-002': 'A base foi recarregada recentemente. Tente novamente em instantes.',
  'XSL-004': 'Parâmetros da consulta inválidos. Tente novamente.',
};

const FORMULA_INJECTION_PREFIX = /^[=+\-@\t\r]/;
const CSV_NEEDS_QUOTING = /[;"\r\n]/;
const YEAR_MONTH_PATTERN = /^(\d{4})-(\d{2})$/;
const MONEY_DECIMALS = 2;
const GAP_DECIMALS = 1;

export function getChurnStatusDisplay(status: ChurnStatus): ChurnStatusDisplay {
  return CHURN_STATUS_DISPLAY[status] ?? CHURN_STATUS_DISPLAY.INATIVO_RECUPERACAO;
}

export function mapActiveChurnRow(item: ChurnCustomerItem): ChurnTableRow {
  return {
    customerCode: item.customerCode,
    customerName: item.customerName ?? '',
    sellerName: item.sellerName ?? '',
    city: item.city ?? '',
    status: item.status,
    diasSemComprar: item.diasSemComprar,
    gapTipico: item.gapTipico,
    diasReferencia: item.diasReferencia,
    fatorTempo: item.fatorTempo,
    faturamentoMedioMensal: item.faturamentoMedioMensal,
    scorePrioridade: item.scorePrioridade,
    historicoCurto: item.historicoCurto,
    dataUltimoPedido: item.dataUltimoPedido ?? null,
  };
}

export function mapInactiveChurnRow(item: InactiveCustomerItem): ChurnTableRow {
  return {
    customerCode: item.customerCode,
    customerName: item.customerName ?? '',
    sellerName: item.sellerName ?? '',
    city: item.city ?? '',
    status: 'INATIVO_RECUPERACAO',
    diasSemComprar: item.diasSemComprar,
    gapTipico: null,
    diasReferencia: null,
    fatorTempo: null,
    faturamentoMedioMensal: item.faturamentoMedioMensal,
    scorePrioridade: null,
    historicoCurto: item.historicoCurto,
    dataUltimoPedido: item.dataUltimoPedido,
  };
}

/** Traduz HttpErrorResponse para mensagem segura do contrato, sem nunca expor `detail` ou stacktrace. */
export function resolveChurnErrorMessage(err: unknown, fallback: string): string {
  if (!(err instanceof HttpErrorResponse)) return fallback;
  const body: unknown = err.error;
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return fallback;
  const errorObj = (body as Record<string, unknown>)['error'];
  if (typeof errorObj !== 'object' || errorObj === null || Array.isArray(errorObj)) return fallback;
  const code = (errorObj as Record<string, unknown>)['code'];
  if (typeof code === 'string' && code in CHURN_ERROR_MESSAGES) {
    return CHURN_ERROR_MESSAGES[code];
  }
  return fallback;
}

/** Ordena histórico mensal cronologicamente (AAAA-MM crescente). */
export function sortMonthlyHistoryAsc(history: readonly MonthlyHistoryItem[]): MonthlyHistoryItem[] {
  return [...history].sort((a, b) => a.anoMes.localeCompare(b.anoMes));
}

/** Formata `AAAA-MM` para `MM/AAAA` em pt-BR. */
export function formatYearMonth(anoMes: string): string {
  const match = YEAR_MONTH_PATTERN.exec(anoMes);
  if (!match) return anoMes;
  const [, year, month] = match;
  return `${month}/${year}`;
}

/** Protege células CSV contra Formula Injection (=, +, -, @, tab, CR) e escapa aspas/delimitadores RFC 4180. */
export function sanitizeCsvCell(value: string | number | boolean | null | undefined): string {
  if (value === null || value === undefined) return '';
  const raw = String(value);
  const needsFormulaGuard = FORMULA_INJECTION_PREFIX.test(raw) || FORMULA_INJECTION_PREFIX.test(raw.trimStart());
  const guarded = needsFormulaGuard ? `'${raw}` : raw;
  if (needsFormulaGuard || CSV_NEEDS_QUOTING.test(guarded)) {
    return `"${guarded.replace(/"/g, '""')}"`;
  }
  return guarded;
}

/**
 * Gera conteúdo CSV UTF-8 com BOM (`\uFEFF`) para Excel pt-BR, usando `;` e vírgula decimal.
 * LGPD-CHU-05: contém apenas código do cliente, status, métricas operacionais e datas agregadas (zero PII).
 */
export function buildChurnCsvContent(items: readonly ChurnTableRow[], statusFilter: ChurnStatusFilter): string {
  const isInactive = statusFilter === 'INATIVO_RECUPERACAO';
  const isAll = statusFilter === 'TODOS_GERAL';
  const headers = isInactive
    ? [
        'Codigo Cliente',
        'Cliente',
        'Vendedor',
        'Cidade',
        'Status',
        'Dias Sem Comprar',
        'Ultimo Pedido',
        'Historico Curto',
        'Faturamento Medio Mensal (R$)',
      ]
    : [
        'Codigo Cliente',
        'Cliente',
        'Vendedor',
        'Cidade',
        'Status',
        'Dias Sem Comprar',
        ...(isAll ? ['Ultimo Pedido'] : []),
        'Cadencia Tipica (dias)',
        'Regua Referencia (dias)',
        'Historico Curto',
        'Faturamento Medio Mensal (R$)',
        'Score Prioridade (R$)',
      ];

  const rows = items.map((c) => {
    const statusLabel = getChurnStatusDisplay(c.status).label;
    const historicoLabel = c.historicoCurto ? 'Sim' : 'Nao';
    const faturamento = formatCsvDecimal(c.faturamentoMedioMensal, MONEY_DECIMALS);

    if (isInactive) {
      const lastOrder = c.dataUltimoPedido ? formatIsoDate(c.dataUltimoPedido) : '—';
      return [
        c.customerCode,
        c.customerName || '—',
        c.sellerName || '—',
        c.city || '—',
        statusLabel,
        c.diasSemComprar,
        lastOrder,
        historicoLabel,
        faturamento,
      ].map(sanitizeCsvCell);
    }

    const lastOrder = c.dataUltimoPedido ? formatIsoDate(c.dataUltimoPedido) : '—';
    const gap = c.gapTipico !== null ? formatCsvDecimal(c.gapTipico, GAP_DECIMALS) : '—';
    const regua = c.diasReferencia !== null ? c.diasReferencia : '—';
    const score = c.scorePrioridade !== null ? formatCsvDecimal(c.scorePrioridade, MONEY_DECIMALS) : '—';

    return [
      c.customerCode,
      c.customerName || '—',
      c.sellerName || '—',
      c.city || '—',
      statusLabel,
      c.diasSemComprar,
      ...(isAll ? [lastOrder] : []),
      gap,
      regua,
      historicoLabel,
      faturamento,
      score,
    ].map(sanitizeCsvCell);
  });

  const lines = [headers.map(sanitizeCsvCell).join(';'), ...rows.map((row) => row.join(';'))];
  return `\uFEFF${lines.join('\r\n')}`;
}

function formatCsvDecimal(value: number, decimals: number): string {
  return value.toFixed(decimals).replace('.', ',');
}
