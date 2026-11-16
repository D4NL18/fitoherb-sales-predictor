/**
 * Sincronização pura bidirecional entre o estado da consulta e os query parameters da URL (Design Plan D-12).
 * Omite parâmetros quando seus valores são iguais aos padrões de negócio e sanitiza entradas.
 */
import { Params } from '@angular/router';
import {
  TrendComparisonMode,
  TrendGroupBy,
  TrendMetric,
  TrendQueryParams,
  TrendSortDir,
  TrendSortWindow,
  TrendView,
} from '../models/sales-trend.model';

const VALID_METRICS: readonly TrendMetric[] = ['revenue', 'quantity'];
const VALID_GROUP_BY: readonly TrendGroupBy[] = ['product', 'supplier'];
const VALID_WINDOWS: readonly TrendSortWindow[] = [1, 3, 6, 12];
const VALID_SORT_DIRS: readonly TrendSortDir[] = ['asc', 'desc'];
const VALID_VIEWS: readonly TrendView[] = ['all', 'rising', 'falling', 'new'];
const VALID_MODES: readonly TrendComparisonMode[] = ['point', 'average'];
const MAX_SEARCH_QUERY_LENGTH = 60;
const MAX_MIN_VOLUME = 1_000_000_000;

function readStrictString(value: unknown): string | null {
  return typeof value === 'string' ? value.trim() : null;
}

/**
 * Converte o estado da consulta para parâmetros de URL limpos (omite padrões).
 */
export function stateToQueryParams(state: TrendQueryParams): Params {
  const params: Record<string, string | number | undefined> = {};

  if (state.baseMonth) {
    params['baseMonth'] = state.baseMonth;
  }
  if (state.metric && state.metric !== 'revenue') {
    params['metric'] = state.metric;
  }
  if (state.groupBy && state.groupBy !== 'product') {
    params['groupBy'] = state.groupBy;
  }
  if (state.comparisonMode && state.comparisonMode !== 'point') {
    params['comparisonMode'] = state.comparisonMode;
  }
  if (state.sortWindow && state.sortWindow !== 3) {
    params['sortWindow'] = state.sortWindow;
  }
  if (state.sortDir && state.sortDir !== 'desc') {
    params['sortDir'] = state.sortDir;
  }
  if (state.view && state.view !== 'all') {
    params['view'] = state.view;
  }
  if (state.q && state.q.trim().length > 0) {
    params['q'] = state.q.trim();
  }
  if (typeof state.minVolume === 'number' && state.minVolume > 0) {
    params['minVolume'] = state.minVolume;
  }
  if (typeof state.limit === 'number' && state.limit !== 50) {
    params['limit'] = state.limit;
  }
  if (typeof state.offset === 'number' && state.offset > 0) {
    params['offset'] = state.offset;
  }

  return params;
}

/**
 * Converte os parâmetros da URL em um objeto TrendQueryParams validado e tipado.
 */
export function queryParamsToState(rawParams: Params): TrendQueryParams {
  const result: TrendQueryParams = {};

  const baseMonth = readStrictString(rawParams['baseMonth']);
  if (baseMonth && /^\d{4}-(0[1-9]|1[0-2])$/.test(baseMonth)) {
    result.baseMonth = baseMonth;
  }

  const metric = readStrictString(rawParams['metric']);
  if (metric && VALID_METRICS.includes(metric as TrendMetric)) {
    result.metric = metric as TrendMetric;
  }

  const groupBy = readStrictString(rawParams['groupBy']);
  if (groupBy && VALID_GROUP_BY.includes(groupBy as TrendGroupBy)) {
    result.groupBy = groupBy as TrendGroupBy;
  }

  const comparisonMode = readStrictString(rawParams['comparisonMode']);
  if (comparisonMode && VALID_MODES.includes(comparisonMode as TrendComparisonMode)) {
    result.comparisonMode = comparisonMode as TrendComparisonMode;
  }

  const sortWindowRaw = readStrictString(rawParams['sortWindow']);
  if (sortWindowRaw && /^\d+$/.test(sortWindowRaw)) {
    const w = parseInt(sortWindowRaw, 10);
    if (VALID_WINDOWS.includes(w as TrendSortWindow)) {
      result.sortWindow = w as TrendSortWindow;
    }
  }

  const sortDir = readStrictString(rawParams['sortDir']);
  if (sortDir && VALID_SORT_DIRS.includes(sortDir as TrendSortDir)) {
    result.sortDir = sortDir as TrendSortDir;
  }

  const view = readStrictString(rawParams['view']);
  if (view && VALID_VIEWS.includes(view as TrendView)) {
    result.view = view as TrendView;
  }

  const rawQ = readStrictString(rawParams['q']);
  if (rawQ) {
    const normalizedQ = rawQ.replace(/\s+/g, ' ').slice(0, MAX_SEARCH_QUERY_LENGTH).trim();
    if (normalizedQ.length > 0) {
      result.q = normalizedQ;
    }
  }

  const minVolumeRaw = readStrictString(rawParams['minVolume']);
  if (minVolumeRaw && /^\d+(\.\d+)?$/.test(minVolumeRaw)) {
    const v = parseFloat(minVolumeRaw);
    if (Number.isFinite(v) && v >= 0 && v <= MAX_MIN_VOLUME) {
      result.minVolume = v;
    }
  }

  const limitRaw = readStrictString(rawParams['limit']);
  if (limitRaw && /^\d+$/.test(limitRaw)) {
    const l = parseInt(limitRaw, 10);
    if (Number.isInteger(l) && l >= 1 && l <= 200) {
      result.limit = l;
    }
  }

  const offsetRaw = readStrictString(rawParams['offset']);
  if (offsetRaw && /^\d+$/.test(offsetRaw)) {
    const o = parseInt(offsetRaw, 10);
    if (Number.isInteger(o) && o >= 0) {
      result.offset = o;
    }
  }

  return result;
}
