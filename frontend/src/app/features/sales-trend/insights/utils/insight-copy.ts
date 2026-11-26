/**
 * Textos pt-BR do painel "Por que?" (Design Plan §6.5, §7.2, §10). Mapeamento enum -> texto; nenhuma regra de negócio.
 */
import {
  Confidence,
  FactorType,
  GenerationOrigin,
  HypothesisReason,
  MarketDiagnosis,
  ParcelType,
  TemplateReason,
} from '../models/trend-insights.model';

export const PARCEL_LABELS_DROP: Record<ParcelType, string> = {
  SAZONALIDADE: 'Época do ano',
  PRECO: 'Mudança de preço',
  PRODUTO_NOVO: 'Lançamento semelhante',
  CANIBALIZACAO_MESMO_FORNECEDOR: 'Migração de clientes · mesmo fornecedor',
  CANIBALIZACAO_OUTRO_FORNECEDOR: 'Migração de clientes · outro fornecedor',
  CLIENTES_PERDIDOS: 'Clientes que pararam de comprar',
};

export const PARCEL_LABELS_RISE: Record<ParcelType, string> = {
  ...PARCEL_LABELS_DROP,
  CANIBALIZACAO_MESMO_FORNECEDOR: 'Clientes vindos do mesmo fornecedor',
  CANIBALIZACAO_OUTRO_FORNECEDOR: 'Clientes vindos de outro fornecedor',
};

export const RESIDUAL_LABEL = 'Sem explicação nos dados internos';

const FACTOR_LABELS: Record<string, string> = {
  PERDA_PARTICIPACAO_SEM_MIGRACAO: 'Semelhantes cresceram sem levar clientes',
  RUPTURA: 'Falta de estoque',
  PROMOCAO: 'Promoção',
  REGIONAL: 'Concentração em um estado',
  CLIMA: 'Clima',
  POLITICO_REGULATORIO: 'Regras e governo',
  MATERIA_PRIMA: 'Matéria-prima',
  CONCORRENCIA_MERCADO: 'Concorrência no mercado',
  OUTRO: 'Outro fator',
};

export function factorLabel(tipo: FactorType, rise: boolean): string {
  const parcels = rise ? PARCEL_LABELS_RISE : PARCEL_LABELS_DROP;
  return (parcels as Record<string, string>)[tipo] ?? FACTOR_LABELS[tipo] ?? 'Outro fator';
}

export const NOT_EVALUATED_REASONS: Record<string, string> = {
  JANELA_ANTERIOR_INCOMPLETA: 'O período anterior não está completo na base.',
  MES_BASE_ANTIGO: 'Só dá para medir em meses recentes.',
  SEM_PRECO_MEDIO: 'Sem preço médio para converter em unidades; valor em R$ como referência.',
  CONFIANCA_BAIXA_SAZONAL: 'Histórico curto para medir a época do ano.',
  HISTORICO_CURTO: 'Histórico curto para medir a época do ano.',
  VENDA_ESPORADICA: 'Vendas esporádicas demais para medir a época do ano.',
  FRACA: 'A época do ano tem efeito pequeno neste produto.',
  INDICE_AFINIDADE_INDISPONIVEL: 'Lista de produtos semelhantes em atualização.',
  FONTE_INDISPONIVEL: 'Dado indisponível nesta consulta.',
  NAO_SE_APLICA_A_ALTA: 'Não se aplica a altas.',
  SEM_PARES: 'Nenhum produto semelhante com clientes deste produto.',
  SEM_CLIENTES_PERDIDOS: 'Nenhum cliente em risco ou inativo sem compras de semelhantes.',
  MESMOS_MESES: 'Os dois períodos cobrem os mesmos meses do ano.',
  VARIACAO_PRECO_PEQUENA: 'O preço médio praticado quase não mudou.',
  MODO_QUALITATIVO: 'Base pequena: só os sinais são mostrados.',
  ANONIMIZACAO: 'Dado omitido para proteger a privacidade dos clientes.',
};
export const NOT_EVALUATED_FALLBACK = 'Não avaliado nesta consulta.';

export const MARKET_SEALS: Record<
  MarketDiagnosis,
  { tagClass: string; label: string; outlined: boolean }
> = {
  MERCADO_EM_QUEDA: { tagClass: 'tag-info', label: '▼ Mercado em queda', outlined: false },
  MERCADO_EM_ALTA: { tagClass: 'tag-info', label: '▲ Mercado em alta', outlined: false },
  PERDA_DE_PARTICIPACAO: { tagClass: 'tag-warning', label: '▼ Perdeu participação', outlined: false },
  GANHO_DE_PARTICIPACAO: { tagClass: 'tag-warning', label: '▲ Ganhou participação', outlined: false },
  MISTO: { tagClass: 'tag-neutral', label: '◆ Mercado e concorrência', outlined: false },
  SEM_GRUPO_AFIM: { tagClass: '', label: '— Sem comparação', outlined: true },
  NAO_AVALIADO: { tagClass: '', label: '— Não avaliado', outlined: true },
};

export const CONFIDENCE_LABELS: Record<Confidence, { text: string; marks: string }> = {
  ALTA: { text: 'Alta', marks: '●●●' },
  MEDIA: { text: 'Média', marks: '●●○' },
  BAIXA: { text: 'Baixa', marks: '●○○' },
};

export const HYPOTHESIS_REASONS: Record<HypothesisReason, string> = {
  SEM_FONTE: 'Nenhuma fonte encontrada.',
  FONTE_NAO_CITADA: 'A fonte não foi confirmada pela busca.',
  SEM_DATA: 'Fonte sem data de publicação.',
  FORA_DO_PERIODO: 'Notícia fora do período analisado.',
  SKU_FORA_DO_PACOTE: 'Citou um produto fora da análise; ignorado.',
  POSTERIOR_AO_PERIODO: 'Notícia posterior ao período analisado.',
  SEM_COERENCIA_DIRECIONAL: 'O sentido da notícia não combina com o sentido da variação.',
};

export const TEMPLATE_NOTES: Record<TemplateReason, string> = {
  GATE_VARIACAO: 'A variação é pequena demais para uma análise com IA; veja o resumo automático.',
  GATE_VALOR_BAIXO: 'A variação é pequena demais para uma análise com IA; veja o resumo automático.',
  GATE_RESIDUO_BAIXO: 'Os dados internos já explicam quase tudo; a IA não foi necessária.',
  ORCAMENTO_ESGOTADO:
    'A análise com IA não está disponível agora. Mostramos o resumo automático; a parte numérica está completa.',
  IA_DESLIGADA:
    'A análise com IA não está disponível agora. Mostramos o resumo automático; a parte numérica está completa.',
  IA_INDISPONIVEL:
    'A análise com IA não está disponível agora. Mostramos o resumo automático; a parte numérica está completa.',
};
export const TEMPLATE_NOTE_FALLBACK =
  'A análise com IA não está disponível agora. Mostramos o resumo automático; a parte numérica está completa.';

export const ORIGIN_LABELS: Record<GenerationOrigin, string> = {
  llm: 'Gerada por IA',
  fallback: 'Gerada por IA',
  cache: 'Análise salva',
  template: 'Resumo automático (sem IA)',
};

export const AI_NOTICE_TEXT =
  'Diagnóstico gerado por IA a partir de dados internos e notícias públicas; confira as fontes.';

export const CONFIRM_REGENERATE_TEXT =
  'Gerar de novo substitui a análise salva desta janela. Continuar?';

export const AI_EMPTY_TEXT =
  'A IA lê os números acima, pesquisa notícias do período (clima, preço de matéria-prima, regras, concorrência) e aponta o que pode explicar a parte sem explicação. O resultado fica salvo para esta janela.';

export const SLOW_AI_TEXT =
  'Está demorando mais que o normal. Pode fechar este painel: a análise continua enquanto a página estiver aberta.';
export const GENERATING_TEXT =
  'Lendo os números e pesquisando notícias do período. Costuma levar de 10 a 30 segundos.';
export const ALREADY_SAVED_HELP = 'Já existe uma análise salva para esta janela.';

export const WINDOW_OPTIONS = [
  { value: 1, label: '1 mês' },
  { value: 3, label: '3 meses' },
  { value: 6, label: '6 meses' },
  { value: 12, label: '12 meses' },
] as const;
