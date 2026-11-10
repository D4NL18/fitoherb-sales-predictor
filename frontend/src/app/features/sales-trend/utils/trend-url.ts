/**
 * Sincronização pura bidirecional entre o estado da consulta e os query parameters da URL (Design Plan D-12).
 * Omite parâmetros quando seus valores são iguais aos padrões de negócio e sanitiza entradas.
 */
import { Params } from '@angular/router';
import {
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

  if (typeof rawParams['baseMonth'] === 'string' && /^\d{4}-\d{2}$/.test(rawParams['baseMonth'])) {
    result.baseMonth = rawParams['baseMonth'];
  }

  if (typeof rawParams['metric'] === 'string' && VALID_METRICS.includes(rawParams['metric'] as TrendMetric)) {
    result.metric = rawParams['metric'] as TrendMetric;
  }

  if (typeof rawParams['groupBy'] === 'string' && VALID_GROUP_BY.includes(rawParams['groupBy'] as TrendGroupBy)) {
    result.groupBy = rawParams['groupBy'] as TrendGroupBy;
  }

  if (rawParams['sortWindow']) {
    const w = parseInt(rawParams['sortWindow'], 10);
    if (VALID_WINDOWS.includes(w as TrendSortWindow)) {
      result.sortWindow = w as TrendSortWindow;
    }
  }

  if (typeof rawParams['sortDir'] === 'string' && VALID_SORT_DIRS.includes(rawParams['sortDir'] as TrendSortDir)) {
    result.sortDir = rawParams['sortDir'] as TrendSortDir;
  }

  if (typeof rawParams['view'] === 'string' && VALID_VIEWS.includes(rawParams['view'] as TrendView)) {
    result.view = rawParams['view'] as TrendView;
  }

  if (typeof rawParams['q'] === 'string' && rawParams['q'].trim().length > 0) {
    result.q = rawParams['q'].trim();
  }

  if (rawParams['minVolume'] !== undefined) {
    const v = parseFloat(rawParams['minVolume']);
    if (Number.isFinite(v) && v >= 0) {
      result.minVolume = v;
    }
  }

  if (rawParams['limit'] !== undefined) {
    const l = parseInt(rawParams['limit'], 10);
    if (Number.isInteger(l) && l >= 1 && l <= 200) {
      result.limit = l;
    }
  }

  if (rawParams['offset'] !== undefined) {
    const o = parseInt(rawParams['offset'], 10);
    if (Number.isInteger(o) && o >= 0) {
      result.offset = o;
    }
  }

  return result;
}
