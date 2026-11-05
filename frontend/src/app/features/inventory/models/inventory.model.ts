/**
 * Modelos e contratos de dados do módulo de Previsão de Estoque e Compras (v2.0.0).
 *
 * Implementa a tipagem estrita da Política Mín/Máx por dias de cobertura (P-053 a P-056),
 * alinhada à seção 8 de `.agents/docs/api_contracts/inventory.md`.
 */

/** Códigos de status operacional de estoque (P-055.2). */
export type InventoryStatusCode =
  | 'CRITICAL_STOCKOUT'
  | 'REORDER_NEEDED'
  | 'HEALTHY'
  | 'OVERSTOCK';

/** Alias semântico de status operacional de estoque (P-055.2). */
export type InventoryStatus = InventoryStatusCode;

/** Classificação global na Curva ABC por participação na receita da janela. */
export type CurvaAbc = 'A' | 'B' | 'C';

/** Parâmetros enviados a POST /predict e POST /export-csv (contrato 2.0.0, P-053.2). */
export interface InventoryParams {
  historyWindowDays: number;
  minCoverageDays: number;
  maxCoverageDays: number;
  leadTimeDays: number;
  fornecedor?: string | null;
}

/** Eco dos parâmetros efetivamente aplicados no cálculo (data.politica, ADR-001 DA-08). */
export interface InventoryPolicy {
  historyWindowDays: number;
  leadTimeDays: number;
  minCoverageDays: number;
  maxCoverageDays: number;
}

/** Distribuição de itens de Curva A no conjunto analisado. */
export interface CurvaADistribuicao {
  qtdItens: number;
  percentualItens: number;
}

/** Indicadores consolidados (KPIs) da previsão de estoque e compras (P-055.5, P-054.6). */
export interface InventoryKPIs {
  totalSkusAnalisados: number;
  skusEmRupturaCritica: number;
  skusNecessitamReposicao: number;
  skusEstoqueSaudavel: number;
  skusEmOverstock: number;
  investimentoTotalSugerido: number;
  capitalImobilizadoOverstock: number;
  curvaADistribuicao: CurvaADistribuicao;
}

/** Avaliação individual por SKU sob a Política Mín/Máx (P-053 a P-055). */
export interface InventoryProductItem {
  codigo: number;
  descricao: string;
  ean: string;
  fornecedor: string;
  tipo: string;
  estoqueAtual: number;
  vmd: number;
  diasCobertura: number;
  leadTime: number;
  estoqueMinimo: number;
  estoqueMaximo: number;
  qtdSugeridaCompra: number;
  custoUnitario: number;
  precoVenda: number;
  investimentoTotalItem: number;
  status: InventoryStatusCode;
  statusLabel: string;
  curvaAbc: CurvaAbc;
}

/** Carga principal de dados de POST /predict (contrato 2.0.0). */
export interface InventoryPredictData {
  politica: InventoryPolicy;
  kpis: InventoryKPIs;
  produtos: InventoryProductItem[];
}

/** Metadados padrão de resposta do módulo de estoque. */
export interface InventoryResponseMeta {
  timestamp: string;
  version?: string;
  executionTimeMs?: number | null;
}

/** Envelope de resposta de POST /api/v1/inventory/predict. */
export interface InventoryPredictResponse {
  data: InventoryPredictData;
  meta: InventoryResponseMeta;
}

/** Item de fornecedor/laboratório retornado por GET /suppliers (P-047.1). */
export interface SupplierItem {
  fornecedor: string;
  nome: string;
  totalSkus: number;
}

/** Envelope de resposta de GET /api/v1/inventory/suppliers. */
export interface SupplierListResponse {
  data: SupplierItem[];
  meta: InventoryResponseMeta;
}

/** Alias compatível para resposta de fornecedores. */
export type SuppliersResponse = SupplierListResponse;

/** Configuração de faixa e valor padrão de um controle deslizante na tela (A1). */
export interface RangeParameterConfig {
  default: number;
  min: number;
  max: number;
  step: number;
}

/** Dados de configuração dos controles deslizantes em GET /config (seção 3.1 do contrato). */
export interface InventoryConfigData {
  historyWindowDays: RangeParameterConfig;
  leadTimeDays: RangeParameterConfig;
  minCoverageDays: RangeParameterConfig;
  maxCoverageDays: RangeParameterConfig;
}

/** Envelope de resposta de GET /api/v1/inventory/config. */
export interface InventoryConfigResponse {
  data: InventoryConfigData;
  meta: InventoryResponseMeta;
}

/**
 * Item de erro de validação HTTP 422 do FastAPI.
 * O campo `type` carrega o código interno de regra (`INV-001`, `INV-002`)
 * ou o identificador nativo do Pydantic.
 */
export interface ApiValidationErrorItem {
  type: string;
  loc: Array<string | number>;
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
