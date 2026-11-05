/**
 * Funções puras de validação da Política de Estoque Mín/Máx e verificação de schema
 * do cache local v3 (F-02).
 *
 * Regras implementadas:
 * - P-053.3 (`INV-001`): Dias Máximo deve ser estritamente maior que Dias Mínimo, sem ajuste silencioso.
 * - A2 (`INV-002`): Lead Time deve ser estritamente menor que Dias Máximo.
 * - CA-12 / DA-09: Type guard que garante integridade do payload salvo em `localStorage`.
 */
import {
  InventoryKPIs,
  InventoryParams,
  InventoryPolicy,
  InventoryProductItem,
} from '../models/inventory.model';

/** Códigos internos de violação de política na camada de apresentação. */
export type InventoryPolicyIssueCode = 'INV-001' | 'INV-002';

/** Campos sujeitos a validação cruzada no modal de parâmetros. */
export type InventoryPolicyIssueField = 'maxCoverageDays' | 'leadTimeDays';

/** Representa uma inconsistência de regra cruzada nos parâmetros da política. */
export interface InventoryPolicyIssue {
  code: InventoryPolicyIssueCode;
  field: InventoryPolicyIssueField;
  message: string;
}

/** Estrutura persistida no cache local v3 do navegador (DA-09). */
export interface InventoryCachePayload {
  politica: InventoryPolicy;
  kpis: InventoryKPIs;
  produtos: InventoryProductItem[];
  savedAt: string;
}

/**
 * Valida de forma pura as invariantes cruzadas da Política Mín/Máx (P-053.3 e A2).
 * Nunca altera os valores de entrada informados pelo comprador.
 */
export function validateInventoryPolicy(
  params: Pick<InventoryParams, 'minCoverageDays' | 'maxCoverageDays' | 'leadTimeDays'>
): InventoryPolicyIssue | null {
  if (params.maxCoverageDays <= params.minCoverageDays) {
    return {
      code: 'INV-001',
      field: 'maxCoverageDays',
      message: `O máximo precisa ser maior que o mínimo (atual: mín. ${params.minCoverageDays}d · máx. ${params.maxCoverageDays}d). Ajuste um dos controles para continuar.`,
    };
  }

  if (params.leadTimeDays >= params.maxCoverageDays) {
    return {
      code: 'INV-002',
      field: 'leadTimeDays',
      message: `O Lead Time (${params.leadTimeDays}d) precisa ser menor que os Dias Máximo (${params.maxCoverageDays}d) para evitar alerta permanente de ruptura.`,
    };
  }

  return null;
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value);
}

function isValidPolicyBlock(value: unknown): value is InventoryPolicy {
  if (!isPlainRecord(value)) {
    return false;
  }
  return (
    isFiniteInteger(value['historyWindowDays']) &&
    isFiniteInteger(value['leadTimeDays']) &&
    isFiniteInteger(value['minCoverageDays']) &&
    isFiniteInteger(value['maxCoverageDays'])
  );
}

function hasValidProductListShape(produtos: unknown[]): boolean {
  if (produtos.length === 0) {
    return true;
  }
  const firstItem = produtos[0];
  if (!isPlainRecord(firstItem)) {
    return false;
  }
  return (
    typeof firstItem['estoqueMinimo'] === 'number' &&
    typeof firstItem['estoqueMaximo'] === 'number'
  );
}

/**
 * Type guard para validar se o conteúdo lido do `localStorage` corresponde ao contrato v3 (CA-12).
 * Rejeita estruturas antigas que não contenham `politica` ou os níveis `estoqueMinimo`/`estoqueMaximo`.
 */
export function isInventoryCachePayload(value: unknown): value is InventoryCachePayload {
  if (!isPlainRecord(value)) {
    return false;
  }
  if (!isValidPolicyBlock(value['politica'])) {
    return false;
  }
  if (!isPlainRecord(value['kpis'])) {
    return false;
  }
  if (typeof value['savedAt'] !== 'string') {
    return false;
  }
  const produtos = value['produtos'];
  if (!Array.isArray(produtos)) {
    return false;
  }
  return hasValidProductListShape(produtos);
}
