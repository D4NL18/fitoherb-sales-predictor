/**
 * View-models da seção "Fatores externos" (Design Plan §7.4; contrato 1.2.0). Funções puras:
 * a tela só formata o que o contrato entrega. Nenhum valor monetário, token ou orçamento entra aqui.
 */
import { isDevMode } from '@angular/core';
import {
  Confidence,
  ExternalDimension,
  ExternalDirection,
  ExternalFactor,
  ExternalNotEvaluatedReason,
  ExternalRelevance,
  RadarDimension,
  RadarExterno,
  RadarIntensity,
  RadarMovement,
  RadarRef,
  SourceRef,
  TemporalRelation,
} from '../models/trend-insights.model';

export const EXTERNAL_DIMENSIONS: readonly ExternalDimension[] = [
  'POLITICA_REGULATORIO', 'CLIMA_SAFRA', 'CUSTO_MATERIA_PRIMA', 'OFERTA_DEMANDA_MATERIA_PRIMA',
  'CAMBIO_LOGISTICA_IMPORTACAO', 'CONSUMO_MIDIA_SAUDE', 'CONCORRENCIA', 'EVENTOS_MERCADO',
];

export const DIMENSION_LABELS: Record<ExternalDimension, string> = {
  POLITICA_REGULATORIO: 'Política e regulação',
  CLIMA_SAFRA: 'Clima e safra',
  CUSTO_MATERIA_PRIMA: 'Custo da matéria-prima',
  OFERTA_DEMANDA_MATERIA_PRIMA: 'Oferta e demanda da matéria-prima',
  CAMBIO_LOGISTICA_IMPORTACAO: 'Câmbio e logística',
  CONSUMO_MIDIA_SAUDE: 'Consumo e mídia',
  CONCORRENCIA: 'Concorrência',
  EVENTOS_MERCADO: 'Eventos de mercado',
};

const DIRECTIONS: Record<ExternalDirection, { glyph: string; text: string; tone: 'down' | 'up' | 'neutral' }> = {
  PRESSAO_BAIXA: { glyph: '▼', text: 'Pressão de baixa nas vendas', tone: 'down' },
  PRESSAO_ALTA: { glyph: '▲', text: 'Pressão de alta nas vendas', tone: 'up' },
  NEUTRA: { glyph: '●', text: 'Sem pressão clara', tone: 'neutral' },
  INDETERMINADA: { glyph: '○', text: 'direção não exibida', tone: 'neutral' },
};

const RELEVANCE: Record<ExternalRelevance, string> = { ALTA: 'alta', MEDIA: 'média', BAIXA: 'baixa', NENHUMA: 'nenhuma' };

const TEMPORAL_BADGES: Record<TemporalRelation, string | null> = {
  ANTERIOR: null,
  CONTEMPORANEA: null,
  POSTERIOR: 'Depois do período (só contexto)',
  SEM_DATA: 'Sem data (não vale como causa)',
  ANTIGA: 'Notícia antiga (descartada)',
};

export const EXTERNAL_NOT_EVALUATED: Record<ExternalNotEvaluatedReason, string> = {
  SEM_RADAR: 'Não havia pesquisa externa disponível.',
  SEM_TERMO_BUSCA: 'Não há matéria-prima ou categoria para pesquisar neste produto.',
  DIMENSAO_OMITIDA_PELA_IA: 'A análise não cobriu esta dimensão.',
};

const MOVEMENTS: Record<RadarMovement, string> = {
  SUBIU: 'Subiu', CAIU: 'Caiu', ESTAVEL: 'Estável', MUDOU: 'Mudou', INDEFINIDO: 'Indefinido',
};
const INTENSITIES: Record<RadarIntensity, string> = { FORTE: 'forte', MODERADA: 'moderada', FRACA: 'fraca' };

export const EXTERNAL_INTRO = 'Pesquisa pública sobre o assunto do produto. São hipóteses, não dados do sistema.';
export const SEM_EVIDENCIA_TEXT = 'Sem evidência encontrada';
const MAX_SOURCES = 2;

export interface ExternalRowView {
  dimension: ExternalDimension;
  label: string;
  status: ExternalFactor['status'];
  statusText: string | null;
  reasonText: string | null;
  compact: boolean;
  direction: { glyph: string; text: string; tone: 'down' | 'up' | 'neutral' } | null;
  confidenceText: string | null;
  relevanceText: string | null;
  notaRadar: string | null;
  nota: string | null;
  sources: SourceRef[];
  temporalBadge: string | null;
  promoted: boolean;
  ariaLabel: string;
}

export interface ExternalFactorsView {
  title: string;
  intro: string;
  ageText: string | null;
  staleNotice: string | null;
  unavailable: { title: string; text: string } | null;
  rows: ExternalRowView[];
}

export interface RadarRowView {
  dimension: ExternalDimension;
  label: string;
  statusText: string | null;
  movementText: string | null;
  intensityText: string | null;
  notaRadar: string | null;
  sources: SourceRef[];
}

export interface RadarExternoView {
  title: string;
  subtitle: string;
  staleNotice: string | null;
  rows: RadarRowView[];
}

function plural(n: number): string {
  return `${n} ${n === 1 ? 'dia' : 'dias'}`;
}

function formatDay(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-');
  return y && m && d ? `${d}/${m}/${y}` : '';
}

function staleText(days: number | null): string {
  const feita = days === null ? 'Feita há algum tempo' : `Feita há ${plural(days)}`;
  return `Os fatores externos usam uma pesquisa desatualizada. ${feita}; confira as datas das fontes.`;
}

function confidenceOf(c: Confidence, stale: boolean): string {
  if (c === 'ALTA' && isDevMode()) {
    console.warn('[trend-insights] confiança ALTA em fator externo viola o contrato; exibindo baixa.');
  }
  return `Confiança ${stale || c !== 'MEDIA' ? 'baixa' : 'média'}`;
}

function ageLine(radar: RadarRef): string {
  const when = radar.diasDesdeGeracao === 0 ? 'hoje' : `há ${plural(radar.diasDesdeGeracao)}`;
  const origin = radar.origem === 'CACHE' ? ' · compartilhada com outros produtos' : ' · atualizada agora';
  return `Pesquisa sobre "${radar.assunto.termo}" · feita em ${formatDay(radar.geradoEm)} (${when})${origin}`;
}

function omitted(dimensao: ExternalDimension): ExternalFactor {
  return {
    dimensao, status: 'NAO_AVALIADA', direcao: 'INDETERMINADA', confianca: 'BAIXA', relevanciaAoProduto: 'NENHUMA',
    relacaoTemporal: null, rotulo: 'SEM_EVIDENCIA', origemEvidencia: 'NENHUMA', motivoNaoAvaliado: 'DIMENSAO_OMITIDA_PELA_IA',
    tema: null, notaRadar: null, nota: null, fontes: [],
  };
}

function buildRow(f: ExternalFactor, stale: boolean, promoted: boolean): ExternalRowView {
  const label = DIMENSION_LABELS[f.dimensao];
  const base = {
    dimension: f.dimensao, label, status: f.status, promoted, temporalBadge: null as string | null,
    direction: null as ExternalRowView['direction'], confidenceText: null as string | null,
    relevanceText: null as string | null, sources: [] as SourceRef[], nota: null as string | null,
    notaRadar: f.notaRadar, statusText: null as string | null, reasonText: null as string | null, compact: false,
  };
  let row: ExternalRowView;
  if (f.status === 'NAO_AVALIADA') {
    const reason = EXTERNAL_NOT_EVALUATED[f.motivoNaoAvaliado ?? 'DIMENSAO_OMITIDA_PELA_IA'] ?? EXTERNAL_NOT_EVALUATED.DIMENSAO_OMITIDA_PELA_IA;
    row = { ...base, statusText: 'Não avaliada', reasonText: reason, notaRadar: null, compact: true, ariaLabel: '' };
  } else if (f.status === 'SEM_EVIDENCIA') {
    row = { ...base, statusText: SEM_EVIDENCIA_TEXT, compact: true, ariaLabel: '' };
  } else if (f.relevanciaAoProduto === 'NENHUMA') {
    row = { ...base, statusText: 'Sem relação com este produto', compact: true, ariaLabel: '' };
  } else {
    row = {
      ...base,
      direction: DIRECTIONS[f.direcao],
      confidenceText: confidenceOf(f.confianca, stale),
      relevanceText: `Relevância para este produto: ${RELEVANCE[f.relevanciaAoProduto]}`,
      nota: f.nota,
      sources: f.fontes.slice(0, MAX_SOURCES),
      temporalBadge: f.relacaoTemporal ? TEMPORAL_BADGES[f.relacaoTemporal] : null,
      ariaLabel: '',
    };
  }
  row.ariaLabel = rowAria(row);
  return row;
}

function rowAria(r: ExternalRowView): string {
  const parts = [`${r.label}.`];
  if (r.compact) {
    parts.push(`${r.statusText ?? ''}.`);
    if (r.reasonText) parts.push(r.reasonText);
    if (r.notaRadar) parts.push(r.notaRadar);
    return parts.join(' ');
  }
  parts.push('Hipótese.');
  if (r.direction) parts.push(`${r.direction.text}.`);
  if (r.confidenceText) parts.push(`${r.confidenceText}.`);
  if (r.relevanceText) parts.push(`${r.relevanceText}.`);
  if (r.nota) parts.push(r.nota);
  const s = r.sources[0];
  if (s) parts.push(`Fonte ${s.titulo}, ${s.dominio}, ${s.dataPublicacao ? formatDay(s.dataPublicacao) : 'sem data de publicação'}.`);
  return parts.join(' ');
}

/**
 * `factors` undefined = resposta 1.1.x (seção ausente). Sempre 8 linhas na ordem fixa.
 */
export function buildExternalFactorsView(
  factors: ExternalFactor[] | undefined,
  radar: RadarRef | null | undefined,
  warningCodes: readonly string[],
  promotedDimensions: readonly ExternalDimension[] = [],
): ExternalFactorsView | null {
  if (factors === undefined) return null;
  const stale = !!radar?.desatualizado || warningCodes.includes('RADAR_DESATUALIZADO');
  const byDim = new Map(factors.map((f) => [f.dimensao, f]));
  const rows = EXTERNAL_DIMENSIONS.map((d) => buildRow(byDim.get(d) ?? omitted(d), stale, promotedDimensions.includes(d)));
  const evidence = rows.filter((r) => r.status === 'AVALIADA').length;
  const unavailable = warningCodes.includes('SEM_RADAR_EXTERNO') || (!radar && rows.every((r) => r.status === 'NAO_AVALIADA'));
  return {
    title: `Fatores externos (${evidence} de 8 com evidência)`,
    intro: EXTERNAL_INTRO,
    ageText: radar ? ageLine(radar) : null,
    staleNotice: stale ? staleText(radar?.diasDesdeGeracao ?? null) : null,
    unavailable: unavailable
      ? { title: 'Fatores externos não avaliados nesta análise.', text: 'A análise usa só os dados de vendas e dos produtos semelhantes.' }
      : null,
    rows,
  };
}

function radarRow(d: RadarDimension | undefined, dimension: ExternalDimension): RadarRowView {
  const label = DIMENSION_LABELS[dimension];
  if (!d || d.status !== 'AVALIADA') {
    return { dimension, label, statusText: d?.status === 'NAO_AVALIADA' ? 'Não avaliada' : SEM_EVIDENCIA_TEXT, movementText: null, intensityText: null, notaRadar: d?.notaRadar ?? null, sources: [] };
  }
  return {
    dimension, label, statusText: null,
    movementText: d.movimento ? MOVEMENTS[d.movimento] : null,
    intensityText: d.intensidade ? `Intensidade ${INTENSITIES[d.intensidade]}` : null,
    notaRadar: d.notaRadar, sources: d.fontes.slice(0, MAX_SOURCES),
  };
}

export function buildRadarExternoView(radar: RadarExterno | null | undefined, warningCodes: readonly string[]): RadarExternoView | null {
  if (!radar) return null;
  const byDim = new Map(radar.dimensoes.map((d) => [d.dimensao, d]));
  const stale = radar.desatualizado || warningCodes.includes('RADAR_DESATUALIZADO');
  return {
    title: `Radar externo de ${plural(radar.diasDesdeGeracao)} (sem análise de IA para este produto)`,
    subtitle: 'Pesquisa geral, não específica deste produto',
    staleNotice: stale ? staleText(radar.diasDesdeGeracao) : null,
    rows: EXTERNAL_DIMENSIONS.map((d) => radarRow(byDim.get(d), d)),
  };
}
