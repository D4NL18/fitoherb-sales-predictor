/**
 * Constantes nomeadas da Política de Estoque Mínimo/Máximo (P-053 a P-056).
 *
 * Centraliza os padrões 30/60 (P-053.2), as faixas dos controles deslizantes
 * espelhadas de `GET /api/v1/inventory/config` (seção 3.1 de `api_contracts/inventory.md`, A1)
 * e as chaves de versão do cache local no navegador (CA-12, ADR-001 DA-09).
 */

/** Janela padrão de vendas recentes para cálculo da VMD, em dias (P-041, P-053.1). */
export const DEFAULT_HISTORY_WINDOW_DAYS = 60;

/** Lead time padrão de ressuprimento para sinalização de Ruptura Iminente, em dias (P-055.3). */
export const DEFAULT_LEAD_TIME_DAYS = 15;

/** Dias Mínimo padrão da política de reposição (P-053.2). */
export const DEFAULT_MIN_COVERAGE_DAYS = 30;

/** Dias Máximo padrão da política de reposição (P-053.2). */
export const DEFAULT_MAX_COVERAGE_DAYS = 60;

/** Faixa do controle deslizante de Janela de Vendas Recentes na tela (seção 3.1 do contrato). */
export const HISTORY_WINDOW_DAYS_RANGE = {
  min: 15,
  max: 180,
  step: 15,
} as const;

/** Faixa do controle deslizante de Lead Time na tela (A5, seção 3.1 do contrato). */
export const LEAD_TIME_DAYS_RANGE = {
  min: 5,
  max: 60,
  step: 5,
} as const;

/** Faixa do controle deslizante de Dias Mínimo na tela (A1, seção 3.1 do contrato). */
export const MIN_COVERAGE_DAYS_RANGE = {
  min: 5,
  max: 120,
  step: 5,
} as const;

/** Faixa do controle deslizante de Dias Máximo na tela (A1, seção 3.1 do contrato). */
export const MAX_COVERAGE_DAYS_RANGE = {
  min: 10,
  max: 180,
  step: 5,
} as const;

/** Chave atual do cache local da previsão sob o contrato 2.0.0 (CA-12, DA-09). */
export const INVENTORY_CACHE_KEY = 'fitoherb_inventory_cache_v3';

/** Chaves legadas de cache que devem ser expurgadas na inicialização da tela (CA-12). */
export const LEGACY_INVENTORY_CACHE_KEYS = ['fitoherb_inventory_cache_v2'] as const;
