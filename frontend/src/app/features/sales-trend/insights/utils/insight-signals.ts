/**
 * Sinais fora da soma da cascata (Design Plan §6.7): ruptura, promoção, concentração regional,
 * perda de participação sem migração e lançamento sem migração comprovada.
 */
import { formatDecimal } from '../../utils/pt-br-format';
import { InsightIndicator, ProductInsight } from '../models/trend-insights.model';
import { NOT_EVALUATED_FALLBACK, NOT_EVALUATED_REASONS } from './insight-copy';
import { formatSigned } from './insight-view';

export interface SignalView {
  key: string;
  glyph: '●' | '○' | '–';
  stateText: 'presente' | 'ausente' | 'não avaliado';
  text: string;
}

function numberList(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((x): x is number => typeof x === 'number') : [];
}

function signalText(ind: InsightIndicator, rise: boolean): string {
  const ev = ind.evidencia;
  const noun = rise ? 'alta' : 'queda';
  switch (ind.tipo) {
    case 'RUPTURA': {
      const stock = typeof ev?.['estoqueAtual'] === 'number' ? (ev['estoqueAtual'] as number) : null;
      const base = stock !== null ? `Estoque atual: ${formatDecimal(stock, 0)} un. Pode ter faltado produto.` : 'Pode ter faltado produto.';
      return `${base} A migração pode ter sido forçada por falta de estoque.`;
    }
    case 'PROMOCAO': {
      const parts: string[] = [];
      if (ev?.['produtoEmPromocaoAnterior'] === true && ev['produtoEmPromocaoAtual'] === false) {
        parts.push('Teve promoção no período anterior e não teve agora.');
      } else if (ev?.['produtoEmPromocaoAtual'] === true) {
        parts.push('Está em promoção no período atual.');
      }
      const afins = numberList(ev?.['afinsEmPromocaoSoNaAtual']);
      if (afins.length > 0) parts.push(`Semelhantes em promoção no período: ${afins.join(', ')}.`);
      return parts.join(' ') || 'Houve promoção no período.';
    }
    case 'REGIONAL': {
      const uf = typeof ev?.['ufConcentradora'] === 'string' ? (ev['ufConcentradora'] as string) : null;
      const pct = typeof ev?.['participacaoPct'] === 'number' ? (ev['participacaoPct'] as number) : null;
      return uf && pct !== null
        ? `${formatDecimal(pct, 1)}% da ${noun} ficou em ${uf}. Mostra onde a variação aconteceu; não é uma causa à parte.`
        : 'A variação ficou concentrada em um estado.';
    }
    default: {
      const afins = numberList(ev?.['afinsQueCresceramSemClientesDoProduto']);
      const value = ind.valor !== null ? ` (cerca de ${formatSigned(Math.abs(ind.valor), 'revenue')})` : '';
      return `Semelhantes cresceram sem levar clientes deste produto${value}.${afins.length ? ` Produtos: ${afins.join(', ')}.` : ''}`;
    }
  }
}

const ABSENT_TEXT: Record<InsightIndicator['tipo'], string> = {
  RUPTURA: 'Sem falta de estoque no período.',
  PROMOCAO: 'Sem promoção relevante no período.',
  REGIONAL: 'Sem concentração em um estado.',
  PERDA_PARTICIPACAO_SEM_MIGRACAO: 'Sem perda de participação fora da migração.',
};

export function buildSignalViews(insight: ProductInsight): SignalView[] {
  const rise = insight.direcao === 'ALTA';
  const views: SignalView[] = insight.indicadores.map((ind) => {
    if (ind.status === 'NAO_AVALIADO') {
      return {
        key: ind.tipo,
        glyph: '–',
        stateText: 'não avaliado',
        text: (ind.motivoNaoAvaliado && NOT_EVALUATED_REASONS[ind.motivoNaoAvaliado]) || NOT_EVALUATED_FALLBACK,
      };
    }
    if (ind.status === 'SEM_EFEITO') {
      return { key: ind.tipo, glyph: '○', stateText: 'ausente', text: ABSENT_TEXT[ind.tipo] };
    }
    return { key: ind.tipo, glyph: '●', stateText: 'presente', text: signalText(ind, rise) };
  });

  const launch = insight.cascata.find((p) => p.tipo === 'PRODUTO_NOVO');
  const launchedAffine = insight.grupoAfim.afins.find((a) => a.lancamento);
  if (launchedAffine && launch && launch.itens.length === 0 && launch.status !== 'NAO_AVALIADO') {
    views.push({
      key: 'LANCAMENTO_SEM_MIGRACAO',
      glyph: '●',
      stateText: 'presente',
      text: `Houve lançamento semelhante (${launchedAffine.sku}), sem migração comprovada de clientes.`,
    });
  }
  return views;
}
