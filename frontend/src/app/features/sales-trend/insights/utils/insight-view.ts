/**
 * Funções puras que montam as views do painel "Por que?" a partir do contrato (Design Plan §4.2, §6, §7).
 * Só formatação e mapeamento enum -> texto; parcelas, cortes, confiança e diagnóstico vêm da API.
 */
import { TrendMetric } from '../../models/sales-trend.model';
import { formatCurrency, formatDecimal, MINUS_SIGN } from '../../utils/pt-br-format';
import { formatPercentChange, formatPointsChange } from '../../utils/trend-format';
import {
  AffineItem,
  AiDiagnosis,
  CascadeParcel,
  ClientCount,
  Confidence,
  DiagnosisDirection,
  GenerateInsightResponse,
  InsightAiState,
  MigrationItem,
  PriceMechanism,
  ProductInsight,
  TemplateReason,
  ExternalDimension,
} from '../models/trend-insights.model';
import {
  AI_EMPTY_TEXT,
  ALREADY_SAVED_HELP,
  CONFIDENCE_LABELS,
  CONFIRM_REGENERATE_TEXT,
  NOT_EVALUATED_FALLBACK,
  NOT_EVALUATED_REASONS,
  ORIGIN_LABELS,
  PARCEL_LABELS_DROP,
  PARCEL_LABELS_RISE,
  RESIDUAL_LABEL,
  TEMPLATE_NOTES,
  TEMPLATE_NOTE_FALLBACK,
} from './insight-copy';
import { buildExternalFactorsView, buildRadarExternoView, ExternalFactorsView, RadarExternoView } from './external-factors-view';
import { InsightApiError, resolveInsightMessage } from './insight-error';

export const AI_SLOW_NOTICE_SECONDS = 30;

// ---------- utilitários ----------

export function formatClientCount(count: ClientCount): string {
  if (count === '<3') return 'menos de 3 clientes';
  return `${formatDecimal(count, 0)} ${count === 1 ? 'cliente' : 'clientes'}`;
}

export function sourceDomain(url: string, fallback: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return fallback.replace(/^www\./, '');
  }
}

/** Só devolve URLs https; qualquer outro esquema (inclusive http) vira `null` (sem link). */
export function safeHref(url: string): string | null {
  try {
    const u = new URL(url);
    return u.protocol === 'https:' ? u.href : null;
  } catch {
    return null;
  }
}

export function panelTitle(direcao: DiagnosisDirection | null, descricao: string): string {
  const verb = direcao === 'QUEDA' ? 'caiu' : direcao === 'ALTA' ? 'subiu' : 'mudou';
  return `Por que ${descricao} ${verb}?`;
}

/** Rótulo acessível do botão "Por que?" conforme o sentido da coluna ordenada. */
export function explainAriaLabel(descricao: string, variacaoPct: number | null, windowMonths: number): string {
  const verb = variacaoPct === null ? 'mudou' : variacaoPct < 0 ? 'caiu' : variacaoPct > 0 ? 'subiu' : 'mudou';
  return `Por que ${descricao} ${verb} em ${windowMonths} ${windowMonths === 1 ? 'mês' : 'meses'}? Abrir diagnóstico`;
}

export function formatIsoDateTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const p = (n: number): string => String(n).padStart(2, '0');
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} às ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function formatDayMonth(iso: string | null | undefined): string {
  const full = formatIsoDateTime(iso);
  return full ? full.slice(0, 5) : '';
}

export function formatSigned(value: number | null, metric: TrendMetric): string {
  if (value === null || !Number.isFinite(value)) return '—';
  const abs = Math.abs(value);
  const body = metric === 'revenue' ? formatCurrency(abs) : `${formatDecimal(abs, Number.isInteger(abs) ? 0 : 1)} un`;
  if (Math.round(abs * 100) === 0) return body;
  return `${value < 0 ? MINUS_SIGN : '+'}${body}`;
}

// ---------- cascata ----------

export interface MigrationItemView {
  sku: number;
  label: string;
  supplier: string | null;
  sameSupplier: boolean;
  similarityText: string;
  valueText: string;
  clientsText: string;
  mechanism: PriceMechanism | null;
}

export interface WaterfallRowView {
  key: string;
  label: string;
  note: string | null;
  status: 'AVALIADO' | 'SEM_EFEITO' | 'NAO_AVALIADO' | 'RESIDUO' | 'TOTAL';
  valueText: string;
  secondaryValueText: string | null;
  ppText: string;
  confidenceText: string | null;
  confidenceMarks: string | null;
  glyph: '▲' | '▼' | '';
  cut: boolean;
  bar: { x: number; width: number; kind: 'queda' | 'alta' | 'residuo' | 'total' } | null;
  expandable: boolean;
  items: MigrationItemView[];
  itemsTitle: string;
}

export interface WaterfallView {
  title: string;
  subtitle: string;
  caption: string;
  /** Posição do zero no eixo (0..100) para a linha de referência. */
  zeroX: number;
  rows: WaterfallRowView[];
}

function itemView(item: MigrationItem, rise: boolean, metric: TrendMetric): MigrationItemView {
  const rev = item.receitaMigrada;
  return {
    sku: item.sku,
    label: `${item.sku} · ${item.descricao}`,
    supplier: item.fornecedor,
    sameSupplier: item.sameSupplier,
    similarityText: `${Math.round(item.affinityScore * 100)}%`,
    valueText: rev === null ? '—' : formatSigned(rise ? rev : -rev, 'revenue'),
    clientsText: formatClientCount(item.clientesMigrados),
    mechanism: item.mecanismo,
  };
}

function detailNumber(detalhe: Record<string, unknown> | null, key: string): number | null {
  const v = detalhe?.[key];
  return typeof v === 'number' ? v : null;
}

function parcelNote(p: CascadeParcel, rise: boolean): string | null {
  if (p.status === 'NAO_AVALIADO') {
    return (p.motivoNaoAvaliado && NOT_EVALUATED_REASONS[p.motivoNaoAvaliado]) || NOT_EVALUATED_FALLBACK;
  }
  if (p.status === 'SEM_EFEITO') {
    return (p.motivoSemEfeito && NOT_EVALUATED_REASONS[p.motivoSemEfeito]) || null;
  }
  const parts: string[] = [];
  const noun = rise ? 'alta' : 'queda';
  switch (p.tipo) {
    case 'SAZONALIDADE': {
      const cur = detailNumber(p.detalhe, 'indiceAtual');
      const prev = detailNumber(p.detalhe, 'indiceAnterior');
      if (cur !== null && prev !== null) {
        parts.push(
          `Esta época costuma vender ${cur >= prev ? 'mais' : 'menos'}; ${p.explicativa === false ? 'compensa' : 'explica'} parte da ${noun}.`,
        );
      }
      break;
    }
    case 'PRECO': {
      const v = detailNumber(p.detalhe, 'variacaoValorPct');
      if (v !== null) {
        parts.push(`Preço médio praticado ${v >= 0 ? 'subiu' : 'caiu'} ${formatDecimal(Math.abs(v), 1)}%.`);
      }
      const obs = p.detalhe?.['observacoes'];
      if (Array.isArray(obs) && obs.includes('PRECO_INFLUENCIADO_POR_PROMOCAO')) {
        parts.push('Inclui descontos de promoção.');
      }
      break;
    }
    case 'CLIENTES_PERDIDOS': {
      const q = p.detalhe?.['clientesPerdidosQtd'];
      if (q === '<3' || typeof q === 'number') {
        parts.push(`${formatClientCount(q as ClientCount)} estão em risco ou inativos e não compraram semelhantes.`);
      }
      break;
    }
    default:
      if (p.itens.length > 0) {
        parts.push(
          rise
            ? `Clientes vieram de ${p.itens.length} ${p.itens.length === 1 ? 'produto semelhante' : 'produtos semelhantes'}.`
            : `${p.itens.length} ${p.itens.length === 1 ? 'produto semelhante ganhou' : 'produtos semelhantes ganharam'} clientes deste produto.`,
        );
      }
  }
  if (p.cortada) parts.push('Limitada ao total observado.');
  return parts.length ? parts.join(' ') : null;
}

export function buildWaterfallView(insight: ProductInsight, metric: TrendMetric): WaterfallView {
  const summary = insight.resumoNumerico;
  const rise = insight.direcao === 'ALTA';
  const noun = rise ? 'alta' : 'queda';
  const labels = rise ? PARCEL_LABELS_RISE : PARCEL_LABELS_DROP;
  const variation = formatPercentChange(insight.celula.variacaoPct);
  const unitLabel = metric === 'revenue' ? 'R$' : 'unidades';
  const base = {
    subtitle: `Valores em ${unitLabel} na escala do período atual. p.p. = pontos percentuais da variação de ${variation}.`,
    caption: `Decomposição da variação de ${variation} de ${insight.produto.descricao}, por causa`,
  };
  if (!summary) return { title: '', rows: [], zeroX: 0, ...base };

  const cover = summary.coberturaExplicacaoPct;
  const title =
    cover < 50
      ? `A maior parte da ${noun} (${formatDecimal(100 - cover, 1)}%) não tem causa nos dados internos`
      : `As causas medidas explicam ${formatDecimal(cover, 1)}% da ${noun}`;

  // Eixo: pontos acumulados da ponte (0 -> variação), ampliado pelas parcelas compensatórias.
  const spans: { from: number; to: number }[] = [];
  let cum = 0;
  const points: number[] = [0, summary.deltaObservado];
  const rows: WaterfallRowView[] = insight.cascata.map((p) => {
    let span: { from: number; to: number } | null = null;
    if (p.status === 'AVALIADO' && p.valor !== null) {
      span = { from: cum, to: cum + p.valor };
      cum += p.valor;
      points.push(cum);
    }
    spans.push(span ?? { from: 0, to: 0 });
    const conf = p.confianca ? CONFIDENCE_LABELS[p.confianca as Confidence] : null;
    const evaluated = p.status === 'AVALIADO' && p.valor !== null;
    return {
      key: p.tipo,
      label: labels[p.tipo],
      note: parcelNote(p, rise),
      status: p.status,
      valueText: evaluated
        ? formatSigned(p.valor, metric)
        : p.status === 'SEM_EFEITO'
          ? 'Sem efeito'
          : 'Não avaliado',
      secondaryValueText: evaluated && metric === 'quantity' && p.valorReceita !== null ? formatSigned(p.valorReceita, 'revenue') : null,
      ppText: evaluated ? formatPointsChange(p.pontosPercentuais) : '',
      confidenceText: evaluated && conf ? conf.text : null,
      confidenceMarks: evaluated && conf ? conf.marks : null,
      glyph: evaluated ? ((p.valor as number) < 0 ? '▼' : '▲') : '',
      cut: p.cortada,
      bar: null,
      expandable: p.itens.length > 0,
      items: p.itens.map((i) => itemView(i, rise, metric)),
      itemsTitle: rise ? 'De onde vieram os clientes' : p.tipo === 'CANIBALIZACAO_MESMO_FORNECEDOR'
        ? 'Para onde foram os clientes (mesmo fornecedor)'
        : 'Para onde foram os clientes',
    };
  });

  const residue = summary.residuo;
  const residueFrom = cum;
  points.push(cum + residue);
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const toBar = (a: number, b: number, kind: 'queda' | 'alta' | 'residuo' | 'total') => ({
    x: ((Math.min(a, b) - min) / range) * 100,
    width: (Math.abs(b - a) / range) * 100,
    kind,
  });

  rows.forEach((row, i) => {
    if (row.status === 'AVALIADO' && insight.cascata[i].valor !== null) {
      const s = spans[i];
      row.bar = toBar(s.from, s.to, s.to < s.from ? 'queda' : 'alta');
    }
  });

  const totalPp = formatPointsChange(insight.celula.variacaoPct);
  const residualPp = summary.baseAjustada ? (residue / summary.baseAjustada) * 100 : null;
  rows.push({
    key: 'RESIDUO', label: RESIDUAL_LABEL, note: null, status: 'RESIDUO',
    valueText: formatSigned(residue, metric), secondaryValueText: null,
    ppText: formatPointsChange(residualPp), confidenceText: null, confidenceMarks: null,
    glyph: residue < 0 ? '▼' : residue > 0 ? '▲' : '', cut: false,
    bar: toBar(residueFrom, residueFrom + residue, 'residuo'),
    expandable: false, items: [], itemsTitle: '',
  });
  rows.push({
    key: 'TOTAL', label: 'Variação total', note: null, status: 'TOTAL',
    valueText: formatSigned(summary.deltaObservado, metric), secondaryValueText: null,
    ppText: totalPp, confidenceText: null, confidenceMarks: null,
    glyph: summary.deltaObservado < 0 ? '▼' : summary.deltaObservado > 0 ? '▲' : '', cut: false,
    bar: toBar(0, summary.deltaObservado, 'total'),
    expandable: false, items: [], itemsTitle: '',
  });

  return { title, rows, zeroX: ((0 - min) / range) * 100, ...base };
}

// ---------- bloco de IA ----------

export interface AiGenerationState {
  phase: 'idle' | 'generating' | 'success' | 'error';
  response: GenerateInsightResponse | null;
  error: InsightApiError | null;
  confirming: boolean;
  startedAtSeconds?: number;
  failedAtSeconds?: number;
}

export type AiBlockStateName =
  | 'semVariacao'
  | 'vazio'
  | 'gerando'
  | 'sucesso'
  | 'salva'
  | 'confirmando'
  | 'template'
  | 'limite'
  | 'erro';

export interface AiButtonView {
  label: string;
  kind: 'generate' | 'regenerate';
  disabled: boolean;
  help: string | null;
}

export interface AiBlockView {
  state: AiBlockStateName;
  diagnosis: AiDiagnosis | null;
  originLabel: string | null;
  showFixedNotice: boolean;
  button: AiButtonView | null;
  elapsedSeconds: number;
  slow: boolean;
  templateText: string | null;
  templateNote: string | null;
  reusedNotice: string | null;
  notices: string[];
  confirmText: string | null;
  message: string | null;
  retryRemaining: number | null;
  showRetry: boolean;
  qualitativeNote: string | null;
  footerText: string | null;
  agedText: string | null;
  emptyText: string;
  /** 1.2.0: seção "Fatores externos" (com IA do produto). */
  external: ExternalFactorsView | null;
  /** 1.2.0: radar somente leitura (resumo automático). */
  radarOnly: RadarExternoView | null;
}

const NOTICE_TEXTS: Record<string, string> = {
  RADAR_DESATUALIZADO: '',
  SEM_RADAR_EXTERNO: '',
  IA_FALHOU: 'Não foi possível gerar a análise com IA agora; mostramos o resumo automático.',
  SEM_BUSCA_EXTERNA: 'Análise feita sem busca externa.',
};

function deriveAiBlockCore(
  insight: ProductInsight,
  getIa: InsightAiState,
  gen: AiGenerationState | undefined,
  clockSeconds: number,
): AiBlockView {
  const response = gen?.response ?? null;
  const ia = response?.meta.ia ?? getIa;
  const diagnosis = response?.data.diagnosticoIa ?? (response ? null : insight.diagnosticoIa);
  const hasSaved = diagnosis !== null;
  const origem = response?.meta.origem ?? null;

  const view: AiBlockView = {
    state: 'vazio', diagnosis, originLabel: null, showFixedNotice: false, button: null, elapsedSeconds: 0,
    slow: false, templateText: null, templateNote: null, reusedNotice: null, notices: [], confirmText: null,
    message: null, retryRemaining: null, showRetry: false, qualitativeNote: null, footerText: null,
    agedText: null, emptyText: AI_EMPTY_TEXT, external: null, radarOnly: null,
  };

  if (insight.modoDiagnostico === 'SEM_VARIACAO' && gen?.phase !== 'generating') {
    return { ...view, state: 'semVariacao' };
  }
  if (insight.modoDiagnostico === 'QUALITATIVO') {
    view.qualitativeNote = 'Com base pequena, a IA aponta sinais e notícias, sem estimar valores.';
  }

  // Limite 429: ativo enquanto o contador não zerar (pedidos) ou o dia inteiro (diário).
  let limited = false;
  if (gen?.phase === 'error' && gen.error?.kind === 'RATE_LIMIT') {
    if (gen.error.motivo === 'LIMITE_DIARIO') {
      limited = true;
    } else {
      const wait = gen.error.retryAfterSeconds ?? 60;
      const remaining = Math.max(0, Math.ceil(wait - (clockSeconds - (gen.failedAtSeconds ?? 0))));
      if (remaining > 0) {
        limited = true;
        view.retryRemaining = remaining;
      }
    }
  }

  const generating = gen?.phase === 'generating' || (!response && ia.geracaoEmAndamento);
  const locked = !ia.podeGerar || generating || limited;

  const saved = hasSaved || ia.diagnosticoSalvo;
  if (saved) {
    view.button = {
      label: ia.diagnosticoVencido ? 'Atualizar' : 'Gerar de novo',
      kind: 'regenerate',
      disabled: locked || !ia.podeForcar,
      help: !ia.podeForcar ? ALREADY_SAVED_HELP : null,
    };
  } else {
    const template = !ia.geraComIa;
    view.button = {
      label: template ? 'Gerar resumo automático' : 'Gerar análise com IA',
      kind: 'generate',
      disabled: locked,
      help: template && ia.motivoTemplate ? TEMPLATE_NOTES[ia.motivoTemplate] : null,
    };
  }

  if (ia.diagnosticoVencido && ia.diagnosticoSalvoEm) {
    const days = Math.max(1, Math.floor((Date.now() - new Date(ia.diagnosticoSalvoEm).getTime()) / 86_400_000));
    view.agedText = `Gerada há ${days} ${days === 1 ? 'dia' : 'dias'}`;
  }

  if (response) {
    view.notices = response.meta.avisos.map((a) => NOTICE_TEXTS[a.codigo]).filter((t): t is string => !!t);
  }

  if (generating) {
    const elapsed = Math.max(0, clockSeconds - (gen?.startedAtSeconds ?? 0));
    return {
      ...view,
      state: 'gerando',
      button: { label: 'Gerando…', kind: 'generate', disabled: true, help: null },
      elapsedSeconds: gen?.phase === 'generating' ? elapsed : 0,
      slow: elapsed >= AI_SLOW_NOTICE_SECONDS,
    };
  }

  if (gen?.phase === 'error' && gen.error) {
    const message = resolveInsightMessage(gen.error, 'post');
    if (limited) {
      view.showFixedNotice = hasSaved;
      return { ...view, state: 'limite', message, originLabel: hasSaved ? ORIGIN_LABELS.cache : null };
    }
    if (gen.error.kind !== 'RATE_LIMIT') {
      return {
        ...view, state: 'erro', message, button: null,
        showRetry: gen.error.kind !== 'NO_BASE' && gen.error.kind !== 'NOT_FOUND',
        showFixedNotice: hasSaved,
      };
    }
  }

  if (gen?.confirming && hasSaved) {
    return { ...view, state: 'confirmando', button: null, confirmText: CONFIRM_REGENERATE_TEXT, showFixedNotice: true,
      originLabel: ORIGIN_LABELS.cache, footerText: savedFooter(diagnosis, ia) };
  }

  if (response && origem === 'template') {
    const reason: TemplateReason | null = response.meta.motivoTemplate ?? ia.motivoTemplate;
    return {
      ...view, state: 'template', originLabel: ORIGIN_LABELS.template,
      templateText: response.data.resumoAutomatico ?? null,
      templateNote: reason ? TEMPLATE_NOTES[reason] : TEMPLATE_NOTE_FALLBACK,
    };
  }

  if (response && (origem === 'llm' || origem === 'fallback')) {
    return { ...view, state: 'sucesso', originLabel: ORIGIN_LABELS[origem], showFixedNotice: true, footerText: 'Gerada agora' };
  }

  if (diagnosis) {
    return {
      ...view,
      state: 'salva',
      originLabel: ORIGIN_LABELS.cache,
      showFixedNotice: true,
      reusedNotice:
        origem === 'cache'
          ? `Já havia uma análise salva para esta janela; mostramos a de ${formatDayMonth(diagnosis.geradoEm)}.`
          : null,
      footerText: savedFooter(diagnosis, ia),
    };
  }

  // Aviso fixo já no estado vazio (plano §7): o usuário sabe, antes de clicar, que o texto é gerado por IA.
  return { ...view, state: 'vazio', showFixedNotice: ia.geraComIa };
}

export function deriveAiBlock(
  insight: ProductInsight,
  getIa: InsightAiState,
  gen: AiGenerationState | undefined,
  clockSeconds: number,
): AiBlockView {
  const view = deriveAiBlockCore(insight, getIa, gen, clockSeconds);
  const response = gen?.response ?? null;
  const ia = response?.meta.ia ?? getIa;
  const codes = (response?.meta.avisos ?? []).map((a) => a.codigo);
  if (ia.radar?.estado === 'DESATUALIZADO' && !codes.includes('RADAR_DESATUALIZADO')) codes.push('RADAR_DESATUALIZADO');
  const data = response?.data ?? insight;
  const diagnosis = view.diagnosis;
  if (view.state !== 'gerando' && diagnosis) {
    const promoted = diagnosis.fatores.map((f) => f.dimensao).filter((d): d is ExternalDimension => !!d);
    view.external = buildExternalFactorsView(diagnosis.fatoresExternos, diagnosis.radar, codes, promoted);
  } else if (view.state === 'template' || (!diagnosis && view.state === 'vazio')) {
    view.radarOnly = buildRadarExternoView(data.radarExterno, codes);
  }
  return view;
}

function savedFooter(diagnosis: AiDiagnosis | null, ia: InsightAiState): string | null {
  const text = formatIsoDateTime(diagnosis?.geradoEm ?? ia.diagnosticoSalvoEm);
  return text ? `Gerada em ${text}` : null;
}

// ---------- resumo, selo de mercado e grupo afim ----------

export interface SummaryView {
  heroText: string;
  heroGlyph: '▲' | '▼' | '';
  heroTone: 'queda' | 'alta' | 'neutro';
  spanText: string;
  fromToText: string | null;
  deltaText: string | null;
  baseParcialNote: string | null;
  sentence: string;
}

function pct1(v: number | null): string {
  return v === null ? '—' : `${formatDecimal(v, 1)}%`;
}

export function buildMarketSentence(insight: ProductInsight, minExplainablePct?: number): string {
  const d = insight.diagnosticoMercado;
  const n = insight.grupoAfim.afins.length;
  const vMercado = formatPercentChange(d.variacaoMercadoPct);
  const sPre = pct1(d.participacaoAnteriorPct);
  const sCur = pct1(d.participacaoAtualPct);
  const pp = formatPointsChange(d.variacaoParticipacaoPp);
  const stable =
    d.variacaoMercadoPct !== null && minExplainablePct !== undefined && Math.abs(d.variacaoMercadoPct) < minExplainablePct;
  switch (d.classificacao) {
    case 'MERCADO_EM_QUEDA':
      return `Os ${n} produtos semelhantes caíram ${vMercado} no mesmo período. A causa provável é de mercado (época, clima, economia, regras).`;
    case 'MERCADO_EM_ALTA':
      return `Os ${n} produtos semelhantes subiram ${vMercado}. O produto acompanhou o mercado.`;
    case 'PERDA_DE_PARTICIPACAO': {
      const verb = stable ? 'ficaram estáveis' : (d.variacaoMercadoPct ?? 0) >= 0 ? 'cresceram' : 'caíram';
      return `Os ${n} produtos semelhantes ${verb} (${vMercado}); a fatia deste produto no grupo caiu de ${sPre} para ${sCur} (${pp}).`;
    }
    case 'GANHO_DE_PARTICIPACAO':
      return `A fatia deste produto no grupo subiu de ${sPre} para ${sCur} (${pp}), acima do que os semelhantes variaram (${vMercado}).`;
    case 'MISTO':
      return `O mercado variou ${vMercado} e a fatia do produto mudou ${pp}: as duas coisas pesaram.`;
    case 'SEM_GRUPO_AFIM':
      return 'Não há produtos semelhantes o bastante para comparar com o mercado.';
    default:
      return 'Comparação com o mercado não avaliada nesta consulta.';
  }
}

export function buildSummaryView(
  insight: ProductInsight,
  metric: TrendMetric,
  windowMonths: number,
  minExplainablePct?: number,
): SummaryView {
  const cell = insight.celula;
  const s = insight.resumoNumerico;
  const direction = insight.direcao;
  const plain = (v: number): string => formatSigned(v, metric).replace(/^\+/, '');
  return {
    heroText: formatPercentChange(cell.variacaoPct),
    heroGlyph: direction === 'QUEDA' ? '▼' : direction === 'ALTA' ? '▲' : '',
    heroTone: direction === 'QUEDA' ? 'queda' : direction === 'ALTA' ? 'alta' : 'neutro',
    spanText: `em ${windowMonths} ${windowMonths === 1 ? 'mês' : 'meses'}`,
    fromToText: s ? `de ${plain(s.baseAjustada)} para ${plain(cell.atual)}` : null,
    deltaText: s ? `(${formatSigned(s.deltaObservado, metric)})` : null,
    baseParcialNote: insight.periodo.baseParcial ? 'Período anterior ajustado para a mesma quantidade de dias.' : null,
    sentence: buildMarketSentence(insight, minExplainablePct),
  };
}

export function aiStatusLabel(view: AiBlockView | null): string {
  if (!view) return 'Análise com IA: indisponível';
  switch (view.state) {
    case 'vazio':
      return 'Análise com IA: ainda não gerada';
    case 'gerando':
      return 'Análise com IA: em andamento';
    case 'sucesso':
      return 'Análise com IA: gerada agora';
    case 'salva':
    case 'confirmando':
      return view.footerText
        ? `Análise com IA: ${view.footerText.charAt(0).toLowerCase()}${view.footerText.slice(1)}`
        : 'Análise com IA: salva';
    case 'template':
      return 'Resumo automático exibido';
    default:
      return 'Análise com IA: indisponível';
  }
}

export interface AffineRowView {
  sku: number;
  label: string;
  supplier: string | null;
  sameSupplier: boolean;
  similarityText: string;
  cell: AffineItem['celula'];
  gainedText: string;
  gained: boolean;
  lancamento: boolean;
}

export interface AffineGroupView {
  title: string;
  sameSupplierCount: number;
  otherSupplierCount: number;
  sameSupplierVariation: string;
  otherSupplierVariation: string;
  sameSupplierGlyph: '▲' | '▼' | '';
  otherSupplierGlyph: '▲' | '▼' | '';
  rows: AffineRowView[];
}

function glyphOf(v: number | null): '▲' | '▼' | '' {
  return v === null || Math.round(v * 10) === 0 ? '' : v > 0 ? '▲' : '▼';
}

export function buildAffineGroupView(insight: ProductInsight): AffineGroupView {
  const afins = insight.grupoAfim.afins;
  const rise = insight.direcao === 'ALTA';
  const migrated = new Map<number, MigrationItem>();
  for (const p of insight.cascata) for (const i of p.itens) migrated.set(i.sku, i);
  for (const i of insight.impactoEmOutrosProdutos?.itens ?? []) {
    if (!migrated.has(i.sku)) migrated.set(i.sku, { ...i, lancamento: false });
  }
  const gained = afins.filter((a) => a.ganhouClientesDoProduto).length;
  const same = afins.filter((a) => a.sameSupplier).length;
  const d = insight.diagnosticoMercado;
  const noun = afins.length === 1 ? 'produto semelhante' : 'produtos semelhantes';
  const tail = rise
    ? `${gained === 1 ? 'perdeu' : 'perderam'} clientes para este`
    : `${gained === 1 ? 'ganhou' : 'ganharam'} clientes deste`;
  return {
    title: `${afins.length} ${noun} · ${gained} ${tail}`,
    sameSupplierCount: same,
    otherSupplierCount: afins.length - same,
    sameSupplierVariation: formatPercentChange(d.variacaoAfinsMesmoFornecedorPct),
    otherSupplierVariation: formatPercentChange(d.variacaoAfinsOutroFornecedorPct),
    sameSupplierGlyph: glyphOf(d.variacaoAfinsMesmoFornecedorPct),
    otherSupplierGlyph: glyphOf(d.variacaoAfinsOutroFornecedorPct),
    rows: afins.map((a) => {
      const m = migrated.get(a.sku);
      const gainedText = a.ganhouClientesDoProduto
        ? [
            'Sim',
            m ? formatClientCount(m.clientesMigrados) : null,
            m && m.receitaMigrada !== null ? formatCurrency(m.receitaMigrada) : null,
          ]
            .filter((t): t is string => !!t)
            .join(' · ')
        : 'Não';
      return {
        sku: a.sku,
        label: `${a.sku} · ${a.descricao}`,
        supplier: a.fornecedor,
        sameSupplier: a.sameSupplier,
        similarityText: `${Math.round(a.affinityScore * 100)}%`,
        cell: a.celula,
        gainedText,
        gained: a.ganhouClientesDoProduto,
        lancamento: a.lancamento,
      };
    }),
  };
}
