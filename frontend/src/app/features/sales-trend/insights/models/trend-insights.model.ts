/**
 * Tipos do contrato `sales-trend-insights` 1.2.0 (GET e POST /generate de produto).
 * Sem `any`. Nenhum tipo carrega custo, tokens ou orçamento em dólar (contrato §4.4).
 */
import { TrendCell, TrendComparisonMode, TrendMetric, TrendSortWindow } from '../../models/sales-trend.model';

export type DiagnosisMode = 'QUANTITATIVO' | 'QUALITATIVO' | 'SEM_VARIACAO';
export type DiagnosisDirection = 'QUEDA' | 'ALTA';
export type ParcelType =
  | 'SAZONALIDADE'
  | 'PRECO'
  | 'PRODUTO_NOVO'
  | 'CANIBALIZACAO_MESMO_FORNECEDOR'
  | 'CANIBALIZACAO_OUTRO_FORNECEDOR'
  | 'CLIENTES_PERDIDOS';
export type IndicatorType = 'RUPTURA' | 'PROMOCAO' | 'REGIONAL' | 'PERDA_PARTICIPACAO_SEM_MIGRACAO';
export type ExternalFactorType =
  | 'CLIMA'
  | 'POLITICO_REGULATORIO'
  | 'MATERIA_PRIMA'
  | 'CONCORRENCIA_MERCADO'
  | 'OUTRO';
export type FactorType = ParcelType | IndicatorType | ExternalFactorType;
export type EvaluationStatus = 'AVALIADO' | 'SEM_EFEITO' | 'NAO_AVALIADO';
export type Confidence = 'ALTA' | 'MEDIA' | 'BAIXA';
export type MarketDiagnosis =
  | 'MERCADO_EM_QUEDA'
  | 'MERCADO_EM_ALTA'
  | 'PERDA_DE_PARTICIPACAO'
  | 'GANHO_DE_PARTICIPACAO'
  | 'MISTO'
  | 'SEM_GRUPO_AFIM'
  | 'NAO_AVALIADO';
export type PriceMechanism =
  | 'PRECO_MENOR_DESTROI_MARGEM'
  | 'PRECO_MENOR_MARGEM_PRESERVADA'
  | 'MIGRACAO_POR_VALOR';
export type TemplateReason =
  | 'GATE_VARIACAO'
  | 'GATE_RESIDUO_BAIXO'
  | 'GATE_VALOR_BAIXO'
  | 'ORCAMENTO_ESGOTADO'
  | 'IA_DESLIGADA'
  | 'IA_INDISPONIVEL';
export type GenerationOrigin = 'cache' | 'template' | 'llm' | 'fallback';
export type AiModel = 'gemini-4-hydrogen' | 'gemini-3.8-flash';
export type HypothesisReason =
  | 'SEM_FONTE'
  | 'FONTE_NAO_CITADA'
  | 'SEM_DATA'
  | 'FORA_DO_PERIODO'
  | 'SKU_FORA_DO_PACOTE'
  | 'POSTERIOR_AO_PERIODO'
  | 'SEM_COERENCIA_DIRECIONAL';
export type ExternalDimension =
  | 'POLITICA_REGULATORIO'
  | 'CLIMA_SAFRA'
  | 'CUSTO_MATERIA_PRIMA'
  | 'OFERTA_DEMANDA_MATERIA_PRIMA'
  | 'CAMBIO_LOGISTICA_IMPORTACAO'
  | 'CONSUMO_MIDIA_SAUDE'
  | 'CONCORRENCIA'
  | 'EVENTOS_MERCADO';
export type ExternalStatus = 'AVALIADA' | 'SEM_EVIDENCIA' | 'NAO_AVALIADA';
export type ExternalDirection = 'PRESSAO_BAIXA' | 'PRESSAO_ALTA' | 'NEUTRA' | 'INDETERMINADA';
export type ExternalRelevance = 'ALTA' | 'MEDIA' | 'BAIXA' | 'NENHUMA';
export type TemporalRelation = 'ANTERIOR' | 'CONTEMPORANEA' | 'POSTERIOR' | 'SEM_DATA' | 'ANTIGA';
export type ExternalNotEvaluatedReason = 'SEM_RADAR' | 'SEM_TERMO_BUSCA' | 'DIMENSAO_OMITIDA_PELA_IA';
export type RadarMovement = 'SUBIU' | 'CAIU' | 'ESTAVEL' | 'MUDOU' | 'INDEFINIDO';
export type RadarIntensity = 'FORTE' | 'MODERADA' | 'FRACA';
export type RadarOrigin = 'GERADO_AGORA' | 'CACHE';
export type RadarState = 'FRESCO' | 'DESATUALIZADO' | 'AUSENTE' | 'GERADO_AGORA';
export type ClientCount = number | '<3';
export type RateLimitReason = 'LIMITE_DE_PEDIDOS' | 'LIMITE_DIARIO';

export interface InsightSpan {
  inicio: string;
  fim: string;
  diasJanela: number;
  diasCobertos: number;
}

export interface MigrationItem {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  sameSupplier: boolean;
  affinityScore: number;
  lancamento: boolean;
  receitaMigrada: number | null;
  clientesMigrados: ClientCount;
  confianca: Confidence;
  mecanismo: PriceMechanism | null;
  netMarginImpact: number | null;
}

export interface CascadeParcel {
  tipo: ParcelType;
  status: EvaluationStatus;
  valor: number | null;
  pontosPercentuais: number | null;
  valorReceita: number | null;
  sentido: 'NEGATIVO' | 'POSITIVO' | null;
  explicativa: boolean | null;
  cortada: boolean;
  confianca: Confidence | null;
  motivoNaoAvaliado: string | null;
  motivoSemEfeito: string | null;
  detalhe: Record<string, unknown> | null;
  itens: MigrationItem[];
}

export interface InsightIndicator {
  tipo: IndicatorType;
  status: EvaluationStatus;
  sentido: 'NEGATIVO' | 'POSITIVO' | null;
  confianca: Confidence | null;
  valor: number | null;
  motivoSemEfeito: string | null;
  motivoNaoAvaliado: string | null;
  evidencia: Record<string, unknown> | null;
}

export interface MarketDiagnosisBlock {
  classificacao: MarketDiagnosis;
  variacaoMercadoPct: number | null;
  efeitoMercado: number | null;
  efeitoParticipacao: number | null;
  participacaoAnteriorPct: number | null;
  participacaoAtualPct: number | null;
  variacaoParticipacaoPp: number | null;
  variacaoAfinsMesmoFornecedorPct: number | null;
  variacaoAfinsOutroFornecedorPct: number | null;
}

export interface AffineItem {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  sameSupplier: boolean;
  affinityScore: number;
  categoriaGaleria: string | null;
  valorVendaAtual: number | null;
  celula: TrendCell;
  ganhouClientesDoProduto: boolean;
  lancamento: boolean;
}

export interface ImpactItem {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  sameSupplier: boolean;
  affinityScore: number;
  tipoImpacto: 'CANIBALIZACAO_INTERNA' | 'GANHO_SOBRE_CONCORRENTE';
  receitaMigrada: number | null;
  clientesMigrados: ClientCount;
  confianca: Confidence;
  mecanismo: PriceMechanism | null;
  netMarginImpact: number | null;
  estoqueZerado: boolean;
}

export interface ImpactBlock {
  totalInterno: number;
  totalConcorrentes: number;
  itens: ImpactItem[];
}

export interface SourceRef {
  url: string;
  dominio: string;
  titulo: string;
  dataPublicacao: string | null;
  origemData: 'MODELO' | 'URL' | 'SEM_DATA' | null;
  /** 1.2.0: `F1..F16` (radar) ou `P1` (busca do produto). */
  id?: string;
}

export interface ExternalFactor {
  dimensao: ExternalDimension;
  status: ExternalStatus;
  direcao: ExternalDirection;
  /** O contrato garante MEDIA|BAIXA; a tela trata ALTA como BAIXA. */
  confianca: Confidence;
  relevanciaAoProduto: ExternalRelevance;
  relacaoTemporal: TemporalRelation | null;
  rotulo: string;
  origemEvidencia: 'RADAR' | 'BUSCA_PRODUTO' | 'NENHUMA';
  motivoNaoAvaliado: ExternalNotEvaluatedReason | null;
  tema: string | null;
  notaRadar: string | null;
  nota: string | null;
  fontes: SourceRef[];
}

export interface RadarSubject {
  termo: string;
  tipo: 'MATERIA_PRIMA' | 'CATEGORIA';
}

export interface RadarRef {
  assunto: RadarSubject;
  mesBase: string;
  geradoEm: string;
  diasDesdeGeracao: number;
  desatualizado: boolean;
  origem: RadarOrigin;
}

export interface RadarDimension {
  dimensao: ExternalDimension;
  status: ExternalStatus;
  movimento: RadarMovement | null;
  intensidade: RadarIntensity | null;
  tema: string | null;
  notaRadar: string | null;
  fontes: SourceRef[];
}

/** `data.radarExterno`: leitura da pesquisa, sem direção sobre vendas, confiança nem relevância. */
export interface RadarExterno {
  assunto: RadarSubject;
  mesBase: string;
  geradoEm: string;
  diasDesdeGeracao: number;
  desatualizado: boolean;
  dimensoes: RadarDimension[];
}

export interface AiFactor {
  tipo: FactorType;
  sentido: 'NEGATIVO' | 'POSITIVO' | null;
  parcelaEstimada: number | null;
  confianca: Confidence;
  rotulo: 'POSSIVEL' | 'EVIDENCIA';
  /** 1.2.0: preenchido só em fator externo promovido. */
  dimensao?: ExternalDimension | null;
  explicacao: string;
  evidenciaInterna: string | null;
  skusCitados: number[];
  fontes: SourceRef[];
}

export interface AiHypothesis {
  tipo: FactorType;
  descricao: string;
  motivo: HypothesisReason;
  fontes: SourceRef[];
}

export interface AiDiagnosis {
  direcao: DiagnosisDirection | null;
  diagnosticoMercado: MarketDiagnosis | null;
  resumo: string;
  fatores: AiFactor[];
  /** 1.2.0: sempre 8 itens na ordem fixa (ausente em respostas 1.1.x). */
  fatoresExternos?: ExternalFactor[];
  radar?: RadarRef | null;
  hipotesesNaoConfirmadas: AiHypothesis[];
  recomendacoes: string[];
  sugestoesBuscaHtml: string | null;
  origem: 'llm' | 'fallback';
  modelo: AiModel;
  geradoEm: string;
  promptVersion: string;
}

export interface InsightProductRef {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  categoriaGaleria: string | null;
  funcaoPrimaria: string | null;
}

export interface InsightPeriod {
  atual: InsightSpan;
  anterior: InsightSpan;
  fatorAjuste: number;
  baseParcial: boolean;
  contigua: boolean;
}

export interface NumericSummary {
  baseAjustada: number;
  deltaObservado: number;
  somaParcelas: number;
  residuo: number;
  coberturaExplicacaoPct: number;
}

export interface ProductInsight {
  produto: InsightProductRef;
  periodo: InsightPeriod;
  celula: TrendCell;
  modoDiagnostico: DiagnosisMode;
  direcao: DiagnosisDirection | null;
  resumoNumerico: NumericSummary | null;
  cascata: CascadeParcel[];
  indicadores: InsightIndicator[];
  diagnosticoMercado: MarketDiagnosisBlock;
  grupoAfim: { status: 'AVALIADO' | 'SEM_GRUPO_AFIM' | 'NAO_AVALIADO'; afins: AffineItem[] };
  impactoEmOutrosProdutos: ImpactBlock | null;
  diagnosticoIa: AiDiagnosis | null;
  /** Só quando `meta.origem = 'template'`. */
  resumoAutomatico?: string | null;
  /** 1.2.0: radar somente leitura (sem IA do produto). */
  radarExterno?: RadarExterno | null;
}

export interface InsightWarning {
  codigo: string;
  mensagem: string;
}

export interface InsightAiState {
  podeGerar: boolean;
  motivoBloqueio: 'SEM_VARIACAO' | null;
  geraComIa: boolean;
  motivoTemplate: TemplateReason | null;
  diagnosticoSalvo: boolean;
  diagnosticoSalvoEm: string | null;
  diagnosticoVencido: boolean;
  podeForcar: boolean;
  geracaoEmAndamento: boolean;
  /** Nível apenas; a tela não o exibe (contrato §4.4). */
  orcamento: { nivel: 'NORMAL' | 'ALERTA' | 'ESGOTADO' };
  radar?: { estado: RadarState; geradoEm: string | null; diasDesdeGeracao?: number; desatualizado?: boolean } | null;
}

export interface InsightMeta {
  timestamp: string;
  version: string;
  dataReferencia: string;
  ultimoDiaCoberto: string;
  mesBase: string;
  metrica: TrendMetric;
  janela: TrendSortWindow;
  modoComparacao: TrendComparisonMode;
  promptVersion: string;
  indiceAfinidade: { disponivel: boolean; lastSyncAt: string | null };
  avisos: InsightWarning[];
  ia: InsightAiState;
  parametros?: { minExplainableVariationPct?: number; affineGroupMinScore?: number };
}

export interface GenerateMeta extends InsightMeta {
  origem: GenerationOrigin;
  motivoTemplate: TemplateReason | null;
  reutilizado: boolean;
  modelo: AiModel | null;
  geradoEm: string | null;
}

export interface ProductInsightResponse {
  data: ProductInsight;
  meta: InsightMeta;
}

export interface GenerateInsightResponse {
  data: ProductInsight;
  meta: GenerateMeta;
}

export interface InsightErrorBody {
  code: string;
  message: string;
  fields: string[];
  motivo: RateLimitReason | null;
}

export interface InsightQueryParams {
  metric?: TrendMetric;
  window?: TrendSortWindow;
  baseMonth?: string;
  comparisonMode?: TrendComparisonMode;
}

/** Pedido de abertura do painel emitido pelas linhas/cartões de produto. */
export interface ExplainRequest {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  triggerEl: HTMLElement;
}

export interface GenerateOptions {
  force?: boolean;
}
