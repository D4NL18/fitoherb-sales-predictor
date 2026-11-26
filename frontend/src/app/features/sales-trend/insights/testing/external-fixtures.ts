/**
 * Fixtures do radar externo e dos fatores externos (contrato 1.2.0; valores ilustrativos).
 */
import { ExternalDimension, ExternalFactor } from '../models/trend-insights.model';

export function externalFactor(dimensao: ExternalDimension, over: Partial<ExternalFactor>): ExternalFactor {
  return {
    dimensao, status: 'AVALIADA', direcao: 'PRESSAO_BAIXA', confianca: 'MEDIA', relevanciaAoProduto: 'ALTA',
    relacaoTemporal: 'ANTERIOR', rotulo: 'POSSIVEL', origemEvidencia: 'RADAR', motivoNaoAvaliado: null,
    tema: 'INSUMO_MAIS_CARO', notaRadar: 'O insumo ficou mais caro na pesquisa do período.',
    nota: 'Pode ter pressionado o valor de venda do produto.',
    fontes: [{ id: 'F3', url: 'https://exemplo.gov.br/noticia', dominio: 'exemplo.gov.br', titulo: 'Cotação do insumo sobe', dataPublicacao: '2026-07-14', origemData: 'MODELO' }],
    ...over,
  };
}
