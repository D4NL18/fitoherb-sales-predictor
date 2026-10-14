export interface InventoryParams {
  historyWindowDays: number;
  leadTimeDays: number;
  targetCoverageDays: number;
  serviceLevel: number;
  fornecedor?: string | null;
  budgetLimit?: number | null;
  maxPurchaseVariationPct?: number | null;
}

export interface CurvaADistribuicao {
  qtdItens: number;
  percentualItens: number;
}

export interface InventoryKPIs {
  totalSkusAnalisados: number;
  skusEmRupturaCritica: number;
  skusNecessitamReposicao: number;
  skusEstoqueSaudavel: number;
  skusEmOverstock: number;
  skusLimitadosPorEspaco?: number;
  investimentoTotalSugerido: number;
  capitalImobilizadoOverstock: number;
  curvaADistribuicao: CurvaADistribuicao;
}

export type InventoryStatus = 'CRITICAL_STOCKOUT' | 'REORDER_NEEDED' | 'HEALTHY' | 'OVERSTOCK';

export interface InventoryProductItem {
  codigo: number;
  descricao: string;
  ean: string;
  fornecedor: string;
  tipo: string;
  estoqueAtual: number;
  vmd: number;
  desvioPadraoDemanda: number;
  diasCobertura: number;
  leadTime: number;
  estoqueSeguranca: number;
  rop: number;
  estoqueIdeal: number;
  estoqueIdealTeorico?: number;
  qtdSugeridaCompra: number;
  qtdSugeridaTeorica?: number;
  limitadoPorEspaco?: boolean;
  tetoCompraFisica?: number | null;
  custoUnitario: number;
  precoVenda: number;
  investimentoTotalItem: number;
  status: InventoryStatus;
  statusLabel: string;
  curvaAbc: 'A' | 'B' | 'C';
}

export interface InventoryPredictResponse {
  data: {
    kpis: InventoryKPIs;
    produtos: InventoryProductItem[];
  };
  meta: {
    timestamp: string;
    version?: string;
    executionTimeMs?: number;
  };
}

export interface SupplierItem {
  fornecedor: string;
  nome: string;
  totalSkus: number;
}

export interface SuppliersResponse {
  data: SupplierItem[];
  meta: {
    timestamp: string;
    version?: string;
  };
}

export interface InventoryConfigResponse {
  data: {
    historyWindowDays: { default: number; min: number; max: number; step: number };
    leadTimeDays: { default: number; min: number; max: number; step: number };
    targetCoverageDays: { default: number; min: number; max: number; step: number };
    serviceLevel: {
      default: number;
      options: Array<{ label: string; value: number; zScore: number }>;
    };
    budgetLimit: { default: number | null; min: number; max: number; step: number };
    maxPurchaseVariationPct?: { default: number; min: number; max: number; step: number };
  };
  meta: {
    timestamp: string;
    version?: string;
  };
}
