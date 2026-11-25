/**
 * Fixtures dos testes de componentes do painel "Por que?" (valores ilustrativos do contrato 1.1.0).
 */
import { TrendCell } from '../../models/sales-trend.model';
import {
  AiDiagnosis,
  CascadeParcel,
  GenerateInsightResponse,
  GenerateMeta,
  InsightAiState,
  InsightMeta,
  ProductInsight,
} from '../models/trend-insights.model';
import { AiGenerationState, deriveAiBlock } from '../utils/insight-view';

export const CELL: TrendCell = {
  meses: 3, atual: 26000, anterior: 40000, variacaoPct: -35, status: 'VARIACAO',
  baseParcial: false, baseBaixa: false, devolucaoLiquida: false, atualPorDia: null, anteriorPorDia: null,
};

export const IA_STATE: InsightAiState = {
  podeGerar: true, motivoBloqueio: null, geraComIa: true, motivoTemplate: null, diagnosticoSalvo: false,
  diagnosticoSalvoEm: null, diagnosticoVencido: false, podeForcar: true, geracaoEmAndamento: false,
  orcamento: { nivel: 'NORMAL' },
};

export function parcel(over: Partial<CascadeParcel>): CascadeParcel {
  return {
    tipo: 'SAZONALIDADE', status: 'AVALIADO', valor: -2400, pontosPercentuais: -6, valorReceita: null,
    sentido: 'NEGATIVO', explicativa: true, cortada: false, confianca: 'MEDIA', motivoNaoAvaliado: null,
    motivoSemEfeito: null, detalhe: null, itens: [], ...over,
  };
}

export function makeInsight(over: Partial<ProductInsight> = {}): ProductInsight {
  return {
    produto: { sku: 2045, descricao: 'CREATINA 300G', fornecedor: 'ALFA', categoriaGaleria: null, funcaoPrimaria: null },
    periodo: {
      atual: { inicio: '2026-08-01', fim: '2026-10-31', diasJanela: 92, diasCobertos: 92 },
      anterior: { inicio: '2026-05-01', fim: '2026-07-31', diasJanela: 92, diasCobertos: 92 },
      fatorAjuste: 1, baseParcial: false, contigua: true,
    },
    celula: CELL,
    modoDiagnostico: 'QUANTITATIVO',
    direcao: 'QUEDA',
    resumoNumerico: { baseAjustada: 40000, deltaObservado: -14000, somaParcelas: -12411.6, residuo: -1588.4, coberturaExplicacaoPct: 88.7 },
    cascata: [
      parcel({}),
      parcel({ tipo: 'PRECO', valor: -1161.6, pontosPercentuais: -2.9, detalhe: { variacaoValorPct: 6 } }),
      parcel({ tipo: 'PRODUTO_NOVO', status: 'NAO_AVALIADO', valor: null, pontosPercentuais: null, confianca: null, motivoNaoAvaliado: 'INDICE_AFINIDADE_INDISPONIVEL' }),
      parcel({
        tipo: 'CANIBALIZACAO_OUTRO_FORNECEDOR', valor: -3400, pontosPercentuais: -8.5,
        itens: [{
          sku: 3301, descricao: 'CREATINA PURA 300G', fornecedor: 'VITA GAMA', sameSupplier: false, affinityScore: 0.804,
          lancamento: false, receitaMigrada: 3400, clientesMigrados: '<3', confianca: 'ALTA',
          mecanismo: 'PRECO_MENOR_DESTROI_MARGEM', netMarginImpact: -680,
        }],
      }),
    ],
    indicadores: [],
    diagnosticoMercado: {
      classificacao: 'PERDA_DE_PARTICIPACAO', variacaoMercadoPct: 21, efeitoMercado: 8400, efeitoParticipacao: -22400,
      participacaoAnteriorPct: 31, participacaoAtualPct: 25.7, variacaoParticipacaoPp: -5.3,
      variacaoAfinsMesmoFornecedorPct: 5, variacaoAfinsOutroFornecedorPct: -3,
    },
    grupoAfim: {
      status: 'AVALIADO',
      afins: [{
        sku: 3301, descricao: 'CREATINA PURA 300G', fornecedor: 'VITA GAMA', sameSupplier: false, affinityScore: 0.804,
        categoriaGaleria: null, valorVendaAtual: 144, celula: { ...CELL, variacaoPct: 15, atual: 13800, anterior: 12000 },
        ganhouClientesDoProduto: true, lancamento: false,
      }],
    },
    impactoEmOutrosProdutos: null,
    diagnosticoIa: null,
    ...over,
  };
}

export const DIAGNOSIS: AiDiagnosis = {
  direcao: 'QUEDA',
  diagnosticoMercado: 'PERDA_DE_PARTICIPACAO',
  resumo: 'A queda acompanha a chegada de um concorrente mais barato.',
  fatores: [
    {
      tipo: 'CANIBALIZACAO_OUTRO_FORNECEDOR', sentido: 'NEGATIVO', parcelaEstimada: -3400, confianca: 'ALTA', rotulo: 'EVIDENCIA',
      explicacao: 'Clientes passaram a comprar o concorrente.', evidenciaInterna: 'CANIBALIZACAO_OUTRO_FORNECEDOR', skusCitados: [3301], fontes: [],
    },
    {
      tipo: 'MATERIA_PRIMA', sentido: 'NEGATIVO', parcelaEstimada: null, confianca: 'MEDIA', rotulo: 'POSSIVEL',
      explicacao: 'Notícias relatam alta de custo.', evidenciaInterna: null, skusCitados: [],
      fontes: [{ url: 'https://www.exemplo-noticias.com.br/a', dominio: 'exemplo-noticias.com.br', titulo: 'Custo sobe', dataPublicacao: '2026-08-14', origemData: 'URL' }],
    },
  ],
  hipotesesNaoConfirmadas: [
    { tipo: 'CLIMA', descricao: 'Inverno mais quente pode ter reduzido a procura.', motivo: 'SEM_FONTE', fontes: [] },
  ],
  recomendacoes: ['Comparar o preço com o concorrente.'],
  sugestoesBuscaHtml: null,
  origem: 'llm',
  modelo: 'gemini-4-hydrogen',
  geradoEm: '2026-11-24T14:10:27.530Z',
  promptVersion: 'tia-v2',
};

export function makeMeta(ia: Partial<InsightAiState> = {}): InsightMeta {
  return {
    timestamp: '', version: '1.1.0', dataReferencia: '2026-11-24', ultimoDiaCoberto: '2026-11-23', mesBase: '2026-10',
    metrica: 'revenue', janela: 3, modoComparacao: 'point', promptVersion: 'tia-v2',
    indiceAfinidade: { disponivel: true, lastSyncAt: null }, avisos: [], ia: { ...IA_STATE, ...ia },
  };
}

export function makeGenMeta(over: Partial<GenerateMeta> = {}): GenerateMeta {
  return { ...makeMeta(), origem: 'llm', motivoTemplate: null, reutilizado: false, modelo: 'gemini-4-hydrogen', geradoEm: DIAGNOSIS.geradoEm, ...over };
}

export function makeResponse(data: Partial<ProductInsight>, meta: Partial<GenerateMeta>): GenerateInsightResponse {
  return { data: makeInsight(data), meta: makeGenMeta(meta) };
}

export function aiView(
  insight: ProductInsight,
  gen?: Partial<AiGenerationState>,
  ia: Partial<InsightAiState> = {},
  clock = 0,
) {
  const state: AiGenerationState | undefined = gen
    ? { phase: 'idle', response: null, error: null, confirming: false, ...gen }
    : undefined;
  return deriveAiBlock(insight, { ...IA_STATE, ...ia }, state, clock);
}
