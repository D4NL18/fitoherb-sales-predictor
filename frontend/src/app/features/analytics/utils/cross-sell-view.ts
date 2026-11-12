/**
 * Derivação pura do que a área de resultado mostra e da copy da aba Cross-sell
 * (Design Plan §5.5, §6.1, §6.3, §6.4, §9; F-11, F-11a).
 * Os painéis só leem estas funções: nenhum componente decide estado ou monta texto sozinho.
 * Textos com prazos interpolam `meta.parametros` (Q-5) em vez de fixar 90 dias / 12 meses.
 */
import { AnalyticsApiError, AnalyticsHealthData, CrossSellParameters } from '../models/analytics.model';
import { EmptyReason } from '../models/cross-sell.model';
import { QueryStatus } from '../services/cross-sell.store';
import { SearchField, resolveFieldError } from './analytics-error';
import { formatDecimal } from './pt-br-format';

/** O que a área de resultado de um modo exibe (§6.1). */
export type ResultViewKind =
  | 'intro'
  | 'loading'
  | 'results'
  | 'empty'
  | 'empty-inactive'
  | 'empty-page'
  | 'insufficient-data'
  | 'technical-error';

/** Ação do estado: focar o campo, limpar e focar, voltar à página 1 ou refazer a consulta. */
export type ResultStateAction = 'focus-field' | 'new-search' | 'first-page' | 'retry';

/** Ícone desenhado pelo `ResultStateComponent` (§6.3). */
export type ResultStateIcon = 'pair' | 'person' | 'box' | 'check' | 'clock' | 'list' | 'chart';

/** Conteúdo de um estado informativo (inicial, vazio ou dados insuficientes). */
export interface ResultStateView {
  icon: ResultStateIcon;
  title: string;
  text: string;
  actionLabel: string;
  action: ResultStateAction;
  /** `warning` = filete de aviso (XSL-003), não é erro. */
  tone: 'neutral' | 'warning';
}

export interface ResultViewInput {
  status: QueryStatus;
  error: AnalyticsApiError | null;
  field: SearchField;
  totalItems: number;
  emptyReason: EmptyReason | null;
}

const DAYS_PER_YEAR = 365;
const MONTHS_PER_YEAR = 12;
const FIRST_PRIORITY_ITEM = 1;

/** Estado da área de resultado (§6.1). Erro de campo não muda a área: ela fica no estado inicial. */
export function resolveResultView(input: ResultViewInput): ResultViewKind {
  if (input.status === 'loading') return 'loading';
  if (input.status === 'success') return 'results';
  if (input.status === 'empty') return resolveEmptyView(input);
  if (input.status === 'error') return resolveErrorView(input);
  return 'intro';
}

function resolveEmptyView(input: ResultViewInput): ResultViewKind {
  if (input.totalItems > 0) return 'empty-page';
  return input.emptyReason === 'SEM_COMPRAS_RECENTES' ? 'empty-inactive' : 'empty';
}

function resolveErrorView(input: ResultViewInput): ResultViewKind {
  if (resolveFieldError(input.error, input.field) !== null) return 'intro';
  return input.error?.code === 'XSL-003' ? 'insufficient-data' : 'technical-error';
}

/** "12 meses" quando o prazo é múltiplo de um ano; senão "N dias". */
export function formatDayWindow(days: number): string {
  if (days % DAYS_PER_YEAR !== 0) return `${days} dias`;
  return `${(days / DAYS_PER_YEAR) * MONTHS_PER_YEAR} meses`;
}

function plural(count: number, singular: string, pluralForm: string): string {
  return count === 1 ? singular : pluralForm;
}

const INSUFFICIENT_DATA: ResultStateView = {
  icon: 'chart',
  title: 'Ainda não dá para recomendar com segurança',
  text: 'Não há pedidos suficientes para gerar recomendações confiáveis. Isso vale para todos os produtos e clientes, não só para este código.',
  actionLabel: 'Tentar de novo',
  action: 'retry',
  tone: 'warning',
};

function emptyPageState(totalItems: number): ResultStateView {
  return {
    icon: 'list',
    title: 'Esta página não tem itens',
    text: `A lista tem ${formatDecimal(totalItems)} ${plural(totalItems, 'sugestão', 'sugestões')}; volte para o começo.`,
    actionLabel: 'Ir para a primeira página',
    action: 'first-page',
    tone: 'neutral',
  };
}

/** Contexto do modo produto para a copy. */
export interface ProductCopyContext {
  kind: ResultViewKind;
  productDescription: string | null;
  totalItems: number;
}

/** Estado informativo do modo produto, ou `null` quando a área mostra lista, skeleton ou banner. */
export function buildProductState(context: ProductCopyContext): ResultStateView | null {
  switch (context.kind) {
    case 'intro':
      return {
        icon: 'pair', title: 'Escolha um produto', tone: 'neutral',
        text: 'Digite o código ou parte da descrição de um produto para ver o que os clientes costumam levar no mesmo pedido.',
        actionLabel: 'Ir para o campo', action: 'focus-field',
      };
    case 'empty':
    case 'empty-inactive':
      return {
        icon: 'box', title: `Nenhuma combinação forte para ${context.productDescription ?? 'este produto'}`, tone: 'neutral',
        text: 'Não achamos produtos que saiam junto com este com frequência suficiente para virar sugestão. Variações dele mesmo (outro sabor, cor ou tamanho) não entram na lista.',
        actionLabel: 'Buscar outro produto', action: 'new-search',
      };
    case 'empty-page':
      return emptyPageState(context.totalItems);
    case 'insufficient-data':
      return INSUFFICIENT_DATA;
    default:
      return null;
  }
}

/** Contexto do modo cliente para a copy (o código vem do formulário, nunca da resposta). */
export interface CustomerCopyContext {
  kind: ResultViewKind;
  customerCode: number | null;
  totalItems: number;
  parameters: CrossSellParameters | null;
}

/** Estado informativo do modo cliente, ou `null` quando a área mostra lista, skeleton ou banner. */
export function buildCustomerState(context: CustomerCopyContext): ResultStateView | null {
  switch (context.kind) {
    case 'intro':
      return {
        icon: 'person', title: 'Escolha um cliente', tone: 'neutral',
        text: 'Digite o código do cliente para ver produtos que ele ainda não compra, ou parou de comprar, e que combinam com o que ele já leva.',
        actionLabel: 'Ir para o campo', action: 'focus-field',
      };
    case 'empty':
      return customerEmptyState(context);
    case 'empty-inactive':
      return customerInactiveState(context);
    case 'empty-page':
      return emptyPageState(context.totalItems);
    case 'insufficient-data':
      return INSUFFICIENT_DATA;
    default:
      return null;
  }
}

function customerEmptyState(context: CustomerCopyContext): ResultStateView {
  const target = context.customerCode === null ? 'a este cliente' : `ao cliente ${context.customerCode}`;
  const dormantDays = context.parameters ? `${context.parameters.dormantDays} dias` : 'meses recentes';
  return {
    icon: 'check', title: `Nada novo para oferecer ${target} agora`, tone: 'neutral',
    text: `Ele já comprou nos últimos ${dormantDays} os produtos que costumam acompanhar o que leva, ou as sugestões estão sem estoque ou sem margem.`,
    actionLabel: 'Consultar outro cliente', action: 'new-search',
  };
}

function customerInactiveState(context: CustomerCopyContext): ResultStateView {
  const subject = context.customerCode === null ? 'Este cliente' : `O cliente ${context.customerCode}`;
  const window = context.parameters ? formatDayWindow(context.parameters.customerProfileDays) : '12 meses';
  return {
    icon: 'clock', title: `${subject} não compra há mais de ${window}`, tone: 'neutral',
    text: `As sugestões partem do que o cliente comprou nos últimos ${window}, então não há base para recomendar.`,
    actionLabel: 'Consultar outro cliente', action: 'new-search',
  };
}

/** Título do cabeçalho do modo produto (§5.5). A lista é curada (P-094): mostra as principais, não o total. */
export function productResultTitle(description: string, totalItems: number): string {
  const subject = plural(totalItems, 'Principal produto que sai', 'Principais produtos que saem');
  return `${subject} junto com ${description}`;
}

/** Título do cabeçalho do modo cliente (§5.5). A lista é curada (P-094): mostra as principais, não o total. */
export function customerResultTitle(customerCode: number | null, totalItems: number): string {
  const target = customerCode === null ? 'a este cliente' : `ao cliente ${customerCode}`;
  return `${plural(totalItems, 'Principal produto', 'Principais produtos')} para oferecer ${target}`;
}

/** Linha de contexto do modo cliente (§5.5), com a janela do perfil vinda de `meta.parametros`. */
export function customerResultSubtitle(parameters: CrossSellParameters): string {
  return `Baseado nas compras dos últimos ${formatDayWindow(parameters.customerProfileDays)}. Só entram produtos com estoque e margem.`;
}

/** Linha "+ n outro(s) produto(s)..." do modo cliente (§5.7), ou `null` com um antecedente só. */
export function relatedAntecedentsNote(relatedCount: number): string | null {
  const others = relatedCount - FIRST_PRIORITY_ITEM;
  if (others < 1) return null;
  return others === 1
    ? '+ 1 outro produto que o cliente compra também leva a esta sugestão.'
    : `+ ${others} outros produtos que o cliente compra também levam a esta sugestão.`;
}

/** Mensagem da região viva do modo (§7.2). */
export function liveMessage(kind: ResultViewKind, totalItems: number, target: string, state: ResultStateView | null): string {
  if (kind === 'loading') return 'Buscando sugestões…';
  if (kind === 'results') return `${formatDecimal(totalItems)} ${plural(totalItems, 'sugestão', 'sugestões')} para ${target}.`;
  if (kind === 'intro') return '';
  return state?.title ?? '';
}

/**
 * Aviso único de primeira consulta lenta (cache frio, P-068; UX NB-2). Usado antes da busca, na página,
 * e durante um carregamento longo, no skeleton; nunca os dois ao mesmo tempo.
 */
export const COLD_CACHE_NOTICE =
  'A primeira consulta após um período sem uso monta a base de pedidos e pode levar até meio minuto.';

/** Aviso de cache frio antes da primeira busca (F-11a, Q-7); `null` com o cache quente ou sem health. */
export function coldCacheNotice(health: AnalyticsHealthData | null): string | null {
  if (health === null || health.estadoCache === 'QUENTE') return null;
  return COLD_CACHE_NOTICE;
}

/** Página 1-based atual a partir do `limit/offset` pedido (para "Tentar de novo" na mesma página). */
export function currentPageOf(pageRequest: { limit: number; offset: number }): number {
  return Math.floor(pageRequest.offset / pageRequest.limit) + 1;
}
