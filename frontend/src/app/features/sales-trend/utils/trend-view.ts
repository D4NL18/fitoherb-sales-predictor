/**
 * Funções puras de transformação de dados da API em View-Models prontos para renderização (Design Plan §4).
 * Isola lógica de selos, acessibilidade, tooltips e estados visuais fora dos templates.
 */
import {
  TrendCell,
  TrendCellStatus,
  TrendMetric,
  TrendParameters,
  TrendWindowMeta,
} from '../models/sales-trend.model';
import { formatCurrency, formatDecimal } from './pt-br-format';
import { formatPercentChange } from './trend-format';

export interface BadgeModel {
  text: string;
  variant: 'info' | 'warning' | 'critical' | 'neutral';
  tooltip: string;
}

export interface CellDisplayModel {
  status: TrendCellStatus;
  percentText: string;
  isNumeric: boolean;
  isNew: boolean;
  isNoBase: boolean;
  isNoMovement: boolean;
  badges: BadgeModel[];
  currentValueText: string;
  previousValueText: string;
  currentDailyText: string | null;
  previousDailyText: string | null;
  direction: 'up' | 'down' | 'flat' | 'none';
  ariaLabel: string;
}

/**
 * Converte uma célula bruta da API em modelo completo de exibição.
 */
export function getCellDisplayModel(
  cell: TrendCell,
  metric: TrendMetric,
  params?: TrendParameters
): CellDisplayModel {
  const percentText = formatPercentChange(cell.variacaoPct);
  const isNumeric = cell.status === 'VARIACAO';
  const isNew = cell.status === 'NOVO';
  const isNoBase = cell.status === 'SEM_BASE';
  const isNoMovement = cell.status === 'SEM_MOVIMENTO';

  let direction: 'up' | 'down' | 'flat' | 'none' = 'none';
  if (isNumeric) {
    const val = cell.variacaoPct ?? 0;
    if (val > 0) {
      direction = 'up';
    } else if (val < 0) {
      direction = 'down';
    } else {
      direction = 'flat';
    }
  }

  // Montagem de badges conforme regras (devolução líquida)
  const badges: BadgeModel[] = [];

  if (cell.devolucaoLiquida) {
    badges.push({
      text: 'Devoluções > vendas',
      variant: 'critical',
      tooltip: 'As devoluções superaram as vendas no período; o valor líquido foi ajustado para zero.',
    });
  }

  const currentValueText =
    metric === 'revenue' ? formatCurrency(cell.atual) : `${formatDecimal(cell.atual, 0)} un`;
  const previousValueText =
    metric === 'revenue' ? formatCurrency(cell.anterior) : `${formatDecimal(cell.anterior, 0)} un`;

  let currentDailyText: string | null = null;
  let previousDailyText: string | null = null;

  if (cell.baseParcial) {
    if (cell.atualPorDia !== null) {
      currentDailyText =
        metric === 'revenue'
          ? `${formatCurrency(cell.atualPorDia)}/dia`
          : `${formatDecimal(cell.atualPorDia, 4)} un/dia`;
    }
    if (cell.anteriorPorDia !== null) {
      previousDailyText =
        metric === 'revenue'
          ? `${formatCurrency(cell.anteriorPorDia)}/dia`
          : `${formatDecimal(cell.anteriorPorDia, 4)} un/dia`;
    }
  }

  // Rótulo de acessibilidade para leitor de tela
  let ariaLabel = '';
  if (isNumeric) {
    const dirWord = direction === 'up' ? 'alta de' : direction === 'down' ? 'queda de' : 'estável em';
    ariaLabel = `${dirWord} ${percentText}`;
  } else if (isNew) {
    ariaLabel = 'Produto novo, sem venda no período anterior';
  } else if (isNoBase) {
    ariaLabel = 'Sem base histórica suficiente no período anterior';
  } else {
    ariaLabel = 'Sem vendas no período atual nem no anterior';
  }

  return {
    status: cell.status,
    percentText,
    isNumeric,
    isNew,
    isNoBase,
    isNoMovement,
    badges,
    currentValueText,
    previousValueText,
    currentDailyText,
    previousDailyText,
    direction,
    ariaLabel,
  };
}

/**
 * Verifica se todas as janelas configuradas possuem semBase = true (histórico anterior insuficiente).
 */
export function isAllSemBase(windows: TrendWindowMeta[]): boolean {
  if (!windows || windows.length === 0) {
    return false;
  }
  return windows.every((w) => w.semBase);
}
