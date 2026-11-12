/**
 * Massas de teste tipadas do módulo Analytics (contrato analytics-cross-sell 1.1.0).
 * Usadas só pelos specs (T-13 a T-15, T-18). Dados sintéticos, sem cliente real (LGPD-11).
 */
import { HttpErrorResponse } from '@angular/common/http';
import {
  AnalyticsErrorCode,
  AnalyticsHealthResponse,
  CrossSellParameters,
} from '../models/analytics.model';
import {
  CustomerCrossSellResponse,
  ProductCrossSellResponse,
  ProductSearchResponse,
} from '../models/cross-sell.model';

export const TEST_PARAMETERS: CrossSellParameters = {
  minLift: 1.2,
  minConfidence: 0.1,
  minPairOrders: 10,
  trivialItemSupport: 0.15,
  dormantDays: 90,
  customerProfileDays: 365,
  cacheTtlHours: 6,
};

const BASE_META = {
  timestamp: '2026-11-05T15:10:00.000Z',
  version: '1.1.0',
  dataReferencia: '2026-11-05',
};

/** Exemplo 200 do contrato §3.3 (R1 e R5). */
export function productResponse(overrides: Partial<ProductCrossSellResponse['meta']> = {}): ProductCrossSellResponse {
  return {
    data: {
      produto: { codigo: 1001, descricao: 'CHA VERDE 100G', fornecedor: 'CATARINENSE' },
      recomendacoes: [
        {
          codigo: 2002, descricao: 'CAPSULA DE HIBISCO', fornecedor: 'HERBARIUM',
          suporte: 0.017, confianca: 0.34, lift: 4.25, pedidosEmComum: 170,
          estoqueAtual: 84, semEstoque: false, margemNaoPositiva: false,
          explicacao: {
            frequencia: 'Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.',
            intensidade: 'CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.',
            evidencia: 'Baseado em 170 pedidos.',
            motivo: null,
          },
        },
        {
          codigo: 3003, descricao: 'OLEO DE COCO 200ML', fornecedor: 'COPRA',
          suporte: 0.006, confianca: 0.12, lift: 1.2, pedidosEmComum: 60,
          estoqueAtual: 0, semEstoque: true, margemNaoPositiva: true,
          explicacao: {
            frequencia: 'Em 12% dos pedidos com CHA VERDE 100G também há OLEO DE COCO 200ML.',
            intensidade: 'OLEO DE COCO 200ML aparece 1,2 vezes mais nesses pedidos do que no geral.',
            evidencia: 'Baseado em 60 pedidos.',
            motivo: null,
          },
        },
      ],
    },
    meta: {
      ...BASE_META,
      page: 1, limit: 50, offset: 0, totalItems: 2, totalPages: 1,
      parametros: TEST_PARAMETERS,
      ...overrides,
    },
  };
}

/** Modo produto sem Regras Úteis (C-02): produto consultado presente, lista vazia. */
export function emptyProductResponse(): ProductCrossSellResponse {
  const response = productResponse({ totalItems: 0, totalPages: 0 });
  return {
    data: { produto: { codigo: 4004, descricao: 'MEL DE ABELHA 500G', fornecedor: 'APIS FLORA' }, recomendacoes: [] },
    meta: response.meta,
  };
}

/** Exemplo 200 do contrato §3.4 (CA-13: G antes de B). */
export function customerResponse(overrides: Partial<CustomerCrossSellResponse['meta']> = {}): CustomerCrossSellResponse {
  return {
    data: {
      recomendacoes: [
        {
          codigo: 7007, descricao: 'GENGIBRE EM PO 100G', fornecedor: 'CATARINENSE',
          antecedentePrincipal: { codigo: 1001, descricao: 'CHA VERDE 100G' },
          qtdAntecedentesRelacionados: 2,
          lift: 1.5, confianca: 0.2, pedidosEmComum: 100,
          margemUnitaria: 30, custoEstimado: false, pontuacao: 9,
          motivo: 'NUNCA_COMPROU', diasDesdeUltimaCompra: null,
          explicacao: {
            frequencia: 'Em 20% dos pedidos com CHA VERDE 100G também há GENGIBRE EM PO 100G.',
            intensidade: 'GENGIBRE EM PO 100G aparece 1,5 vezes mais nesses pedidos do que no geral.',
            evidencia: 'Baseado em 100 pedidos.',
            motivo: 'Sugerido porque o cliente compra CHA VERDE 100G. O cliente nunca comprou GENGIBRE EM PO 100G.',
          },
        },
        {
          codigo: 2002, descricao: 'CAPSULA DE HIBISCO', fornecedor: 'HERBARIUM',
          antecedentePrincipal: { codigo: 1001, descricao: 'CHA VERDE 100G' },
          qtdAntecedentesRelacionados: 1,
          lift: 4.25, confianca: 0.34, pedidosEmComum: 170,
          margemUnitaria: 5, custoEstimado: true, pontuacao: 7.23,
          motivo: 'DORMENTE', diasDesdeUltimaCompra: 120,
          explicacao: {
            frequencia: 'Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.',
            intensidade: 'CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.',
            evidencia: 'Baseado em 170 pedidos.',
            motivo: 'Sugerido porque o cliente compra CHA VERDE 100G. O cliente não compra CAPSULA DE HIBISCO há 120 dias.',
          },
        },
      ],
    },
    meta: {
      ...BASE_META,
      page: 1, limit: 50, offset: 0, totalItems: 2, totalPages: 1,
      motivoVazio: null,
      parametros: TEST_PARAMETERS,
      ...overrides,
    },
  };
}

/** Cliente sem compras nos últimos 365 dias (C-07). */
export function inactiveCustomerResponse(): CustomerCrossSellResponse {
  return {
    data: { recomendacoes: [] },
    meta: customerResponse({ totalItems: 0, totalPages: 0, motivoVazio: 'SEM_COMPRAS_RECENTES' }).meta,
  };
}

/** Perfil não vazio sem candidatos viáveis (C-06). */
export function emptyCustomerResponse(): CustomerCrossSellResponse {
  return {
    data: { recomendacoes: [] },
    meta: customerResponse({ totalItems: 0, totalPages: 0, motivoVazio: null }).meta,
  };
}

export function healthResponse(estadoCache: AnalyticsHealthResponse['data']['estadoCache'] = 'FRIO'): AnalyticsHealthResponse {
  return {
    data: {
      status: 'UP',
      estadoCache,
      cacheCarregado: estadoCache !== 'FRIO',
      baseSuficiente: estadoCache === 'FRIO' ? null : true,
      carregadoEm: null,
      expiraEm: null,
      duracaoUltimaCargaMs: estadoCache === 'FRIO' ? null : 4120,
      contagens: null,
      parametros: TEST_PARAMETERS,
    },
    meta: { timestamp: BASE_META.timestamp, version: '1.1.0', dataReferencia: null },
  };
}

export function searchResponse(): ProductSearchResponse {
  return {
    data: [
      { codigo: 1001, descricao: 'CHA VERDE 100G', fornecedor: 'CATARINENSE' },
      { codigo: 1002, descricao: 'CHA VERDE COM LIMAO 50G', fornecedor: 'CATARINENSE' },
    ],
    meta: { ...BASE_META, page: 1, limit: 20, offset: 0, totalItems: 2, totalPages: 1 },
  };
}

export const CONTRACT_MESSAGES: Record<AnalyticsErrorCode, string> = {
  'XSL-001': 'Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item.',
  'XSL-002': 'Cliente sem histórico de compras.',
  'XSL-003': 'Não há pedidos suficientes para gerar recomendações confiáveis.',
  'XSL-004': 'Parâmetros inválidos: sku.',
  'ANL-001': 'Base de vendas indisponível no momento. Tente novamente em instantes.',
  'ANL-002': 'A base foi recarregada recentemente. Tente novamente mais tarde.',
};

const STATUS_BY_CODE: Record<AnalyticsErrorCode, number> = {
  'XSL-001': 404, 'XSL-002': 404, 'XSL-003': 422, 'XSL-004': 400, 'ANL-001': 503, 'ANL-002': 429,
};

/** Corpo de erro do contrato §4 embrulhado num `HttpErrorResponse`. */
export function contractError(code: AnalyticsErrorCode, fields: string[] = []): HttpErrorResponse {
  return new HttpErrorResponse({
    status: STATUS_BY_CODE[code],
    statusText: 'Error',
    url: '/api/v1/analytics/cross-sell/product/1001',
    error: {
      error: { code, message: CONTRACT_MESSAGES[code], fields },
      meta: { timestamp: BASE_META.timestamp, version: '1.1.0' },
    },
  });
}
