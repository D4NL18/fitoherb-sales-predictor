/**
 * Tipos da aba Cross-sell (contrato analytics-cross-sell 1.1.0, §3.3 a §3.6).
 * Recomendação por produto (P-061), por cliente (P-062 a P-064), explicação (P-065) e busca de produto (DC-5).
 * O cliente aparece só pelo código e nunca é ecoado nas respostas (P-070, LGPD-03).
 */
import { CrossSellPagedMeta, PagedMeta } from './analytics.model';

/** Motivo de lista vazia no modo cliente (P-062.7). */
export type EmptyReason = 'SEM_COMPRAS_RECENTES';

export interface CustomerPagedMeta extends CrossSellPagedMeta {
  motivoVazio: EmptyReason | null;
}

export interface ProductRef {
  codigo: number;
  descricao: string;
}

/** Frases prontas de P-065, separadas (Q-3); `motivo` é `null` no modo produto. */
export interface Explanation {
  frequencia: string;
  intensidade: string;
  evidencia: string;
  motivo: string | null;
}

/** Produto consultado (antecedente), presente também com a lista vazia (Q-2). */
export interface ConsultedProduct extends ProductRef {
  fornecedor: string;
}

/** Item do modo produto (P-061): sinalizado, nunca escondido, sem estoque ou margem (A-8). */
export interface ProductRecommendationItem {
  codigo: number;
  descricao: string;
  fornecedor: string;
  suporte: number;
  confianca: number;
  lift: number;
  pedidosEmComum: number;
  estoqueAtual: number;
  semEstoque: boolean;
  margemNaoPositiva: boolean;
  explicacao: Explanation;
}

export interface ProductCrossSellData {
  produto: ConsultedProduct;
  recomendacoes: ProductRecommendationItem[];
}

export interface ProductCrossSellResponse {
  data: ProductCrossSellData;
  meta: CrossSellPagedMeta;
}

/** Busca de produto por código ou descrição (contrato §3.6, DC-5). */
export interface ProductSearchResponse {
  data: ConsultedProduct[];
  meta: PagedMeta;
}

/** Motivo do candidato no modo cliente (P-062.5). */
export type CandidateReason = 'NUNCA_COMPROU' | 'DORMENTE';

/** Item do modo cliente (P-062 a P-064), já na ordem de pontuação da API. */
export interface CustomerRecommendationItem {
  codigo: number;
  descricao: string;
  fornecedor: string;
  antecedentePrincipal: ProductRef;
  qtdAntecedentesRelacionados: number;
  lift: number;
  confianca: number;
  pedidosEmComum: number;
  margemUnitaria: number;
  custoEstimado: boolean;
  pontuacao: number;
  motivo: CandidateReason;
  diasDesdeUltimaCompra: number | null;
  explicacao: Explanation;
}

export interface CustomerCrossSellData {
  recomendacoes: CustomerRecommendationItem[];
}

export interface CustomerCrossSellResponse {
  data: CustomerCrossSellData;
  meta: CustomerPagedMeta;
}
