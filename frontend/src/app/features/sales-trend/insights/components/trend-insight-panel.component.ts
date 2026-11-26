/**
 * Painel "Por que?" (Design Plan §6): diálogo lateral 720 px (tela cheia < 768 px) com resumo, cascata,
 * migração/impacto, grupo afim e bloco de IA. Componente burro: recebe views prontas e emite intenções.
 * Abrir o painel nunca aciona IA; só os botões do bloco de IA emitem `generate`.
 */
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { RouterLink } from '@angular/router';
import { inertOutside, lockBodyScroll, trapFocus } from '../../../../shared/a11y/dialog-focus';
import { InlineNoticeComponent } from '../../components/inline-notice/inline-notice.component';
import { SegmentedControlComponent, SegmentOption } from '../../components/segmented-control/segmented-control.component';
import { TrendEmptyStateComponent } from '../../components/trend-empty-state/trend-empty-state.component';
import { TrendErrorBannerComponent } from '../../components/trend-error-banner/trend-error-banner.component';
import { TrendMetric, TrendSortWindow } from '../../models/sales-trend.model';
import { formatWindowMonthSpan } from '../../utils/trend-format';
import { InsightMeta, ParcelType, ProductInsight } from '../models/trend-insights.model';
import { InsightContext } from '../services/trend-insights.store';
import { WINDOW_OPTIONS } from '../utils/insight-copy';
import { buildSignalViews } from '../utils/insight-signals';
import {
  AiBlockView,
  aiStatusLabel,
  buildAffineGroupView,
  buildSummaryView,
  buildWaterfallView,
  panelTitle,
} from '../utils/insight-view';
import { AffineGroupComponent } from './affine-group.component';
import { AiDiagnosisBlockComponent } from './ai-diagnosis-block.component';
import { AttributionWaterfallComponent } from './attribution-waterfall.component';
import { ImpactedProductsComponent } from './impacted-products.component';
import { InsightSignalsComponent } from './insight-signals.component';
import { InsightSummaryComponent } from './insight-summary.component';
import { TrendInsightSkeletonComponent } from './trend-insight-skeleton.component';

let nextPanelId = 0;

const MONTHS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

function formatMonthYear(ym: string): string {
  const [y, m] = ym.split('-');
  const idx = Number(m) - 1;
  return y && idx >= 0 && idx < 12 ? `${MONTHS[idx]}/${y}` : ym;
}

@Component({
  selector: 'app-trend-insight-panel',
  standalone: true,
  imports: [
    RouterLink,
    InlineNoticeComponent,
    SegmentedControlComponent,
    TrendEmptyStateComponent,
    TrendErrorBannerComponent,
    AffineGroupComponent,
    AiDiagnosisBlockComponent,
    AttributionWaterfallComponent,
    ImpactedProductsComponent,
    InsightSignalsComponent,
    InsightSummaryComponent,
    TrendInsightSkeletonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ip-backdrop" (click)="closePanel.emit()" aria-hidden="true"></div>
    <aside
      #panel
      class="ip-panel"
      role="dialog"
      aria-modal="true"
      [attr.aria-labelledby]="titleId"
      [attr.aria-describedby]="insight() ? summaryId : null"
    >
      <header class="ip-header">
        <div class="ip-header-top">
          <span class="ip-code">{{ context().sku }}@if (context().fornecedor) { · {{ context().fornecedor }}}</span>
          <button type="button" class="ip-close" aria-label="Fechar diagnóstico" (click)="closePanel.emit()">
            <span aria-hidden="true">×</span>
          </button>
        </div>
        <h2 #titleEl [id]="titleId" class="ip-title" tabindex="-1">{{ title() }}</h2>
        <p class="ip-context">{{ contextLine() }}</p>
        <div class="ip-window">
          <span class="ip-window-label">Janela</span>
          <app-segmented-control
            label="Janela do diagnóstico"
            [options]="windowOptions()"
            [value]="context().window"
            (valueChange)="windowChange.emit($event)"
          />
        </div>
      </header>

      <div #body class="ip-body" [class.is-reloading]="reloading()" [attr.aria-busy]="status() === 'loading'">
        @if (status() === 'error' && !insight()) {
          @if (canRetry()) {
            <app-trend-error-banner [message]="errorMessage() ?? ''" (retry)="retry.emit()" />
          } @else {
            <app-inline-notice tone="warning" [text]="errorMessage() ?? ''" actionLabel="Fechar" (action)="closePanel.emit()" />
          }
        }

        @if (status() === 'loading' && !insight()) {
          <app-trend-insight-skeleton part="panel" />
          @if (slowLoading()) {
            <p class="ip-slow" role="status">
              Calculando a migração de clientes desta janela; a primeira consulta pode levar alguns segundos.
            </p>
          }
        }

        @if (insight(); as data) {
          @if (ai(); as aiView) {
            <div class="ip-section ip-ai-featured">
              <app-ai-diagnosis-block
                #aiBlock
                [view]="aiView"
                [rise]="data.direcao === 'ALTA'"
                [metric]="metric()"
                [minVariationPct]="meta()?.parametros?.minExplainableVariationPct ?? null"
                (generate)="generate.emit()"
                (requestRegenerate)="requestRegenerate.emit()"
                (confirmed)="confirmRegenerate.emit()"
                (cancelled)="cancelConfirm.emit()"
                (retry)="generate.emit()"
                (focusParcel)="focusParcel($event)"
              />
            </div>
          }

          <div [id]="summaryId" class="ip-section first">
            @for (n of notices(); track n.key) {
              <app-inline-notice
                [tone]="n.tone"
                [text]="n.text"
                [actionLabel]="n.action ?? null"
                (action)="retry.emit()"
              />
            }

            @if (data.modoDiagnostico === 'SEM_VARIACAO') {
              <app-trend-empty-state
                [title]="'Sem variação relevante em ' + windowLabel()"
                [description]="'A venda mudou menos de ' + minVariationText() + ' entre os dois períodos; não há o que explicar.'"
                [actionLabel]="context().window !== 3 ? 'Ver 3 meses' : null"
                (action)="windowChange.emit(3)"
              />
            } @else {
              <app-insight-summary
                [view]="summary()!"
                [diagnosis]="data.diagnosticoMercado.classificacao"
                [aiStatus]="aiStatus()"
                (goToAi)="goToAi()"
              />
            }
          </div>

          @if (data.modoDiagnostico === 'QUANTITATIVO') {
            <div class="ip-section">
              @if (reloading()) {
                <!-- Recarregando: skeleton só no lugar da cascata (mesma altura de linhas), sem empurrar o conteúdo. -->
                <app-trend-insight-skeleton part="waterfall" />
              } @else {
                <app-attribution-waterfall #waterfallCmp [view]="waterfall()!" (navigate)="closePanel.emit()" />
              }
              <div class="ip-sub"><app-insight-signals [signals]="signals()" /></div>
            </div>
          } @else if (data.modoDiagnostico === 'QUALITATIVO') {
            <div class="ip-section">
              <app-insight-signals title="Sinais encontrados (sem estimar valores)" [signals]="signals()" />
            </div>
          }

          @if (data.impactoEmOutrosProdutos; as impact) {
            <div class="ip-section">
              <app-impacted-products [impact]="impact" [isNew]="data.celula?.status === 'NOVO'" />
            </div>
          }

          <div class="ip-section">
            <app-affine-group
              [view]="affine()"
              [status]="data.grupoAfim.status"
              [metric]="metric()"
              [sku]="data.produto.sku"
              [minScore]="meta()?.parametros?.affineGroupMinScore ?? null"
              (refresh)="retry.emit()"
              (navigate)="closePanel.emit()"
            />
          </div>
        }
      </div>

      <footer class="ip-footer">
        <a
          class="ip-footer-link"
          routerLink="/analytics/canibalizacao"
          [queryParams]="{ periodo: 90, busca: context().sku }"
          (click)="closePanel.emit()"
        >Ver no relatório de Canibalização</a>
        <button type="button" class="ip-footer-close" (click)="closePanel.emit()">Fechar</button>
      </footer>

      <div class="sr-only" aria-live="polite" aria-atomic="true" data-testid="panel-live">{{ liveMessage() }}</div>
    </aside>
  `,
  styles: [`
    :host { display: contents; }
    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    .ip-backdrop { position: fixed; inset: 0; background: var(--bg-overlay); z-index: 1040; }
    .ip-panel { position: fixed; top: 0; right: 0; bottom: 0; width: min(720px, 100vw); z-index: 1050; display: flex; flex-direction: column; background: var(--bg-surface); border-left: 1px solid var(--border-default); border-radius: var(--radius-md) 0 0 var(--radius-md); box-shadow: var(--shadow-md); animation: ipSlideIn var(--transition-fast) both; }
    @keyframes ipSlideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
    @media (prefers-reduced-motion: reduce) { .ip-panel { animation: none; } }
    @media (max-width: 1023.98px) { .ip-panel { width: min(640px, 100vw); } }
    @media (max-width: 767.98px) { .ip-panel { inset: 0; width: 100vw; border-left: 0; border-radius: 0; } .ip-backdrop { background: transparent; } }
    .ip-header { position: sticky; top: 0; padding: var(--space-4) var(--space-5) var(--space-3); border-bottom: 1px solid var(--border-subtle); background: var(--bg-surface); display: flex; flex-direction: column; gap: var(--space-2); flex-shrink: 0; }
    .ip-header-top { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
    .ip-code { font-family: var(--font-family-mono); font-size: 0.75rem; color: var(--text-secondary); overflow-wrap: anywhere; }
    .ip-close { width: 44px; height: 44px; margin: calc(var(--space-2) * -1); background: none; border: 0; border-radius: var(--radius-xs); font-size: 1.5rem; color: var(--text-secondary); cursor: pointer; }
    @media (hover: hover) { .ip-close:hover { background-color: var(--bg-subtle); } }
    .ip-close:focus-visible, .ip-title:focus-visible, .ip-footer-link:focus-visible, .ip-footer-close:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .ip-title { margin: 0; font-family: var(--font-family-headline); font-size: 1.25rem; font-weight: 700; color: var(--text-primary); overflow-wrap: anywhere; }
    .ip-context { margin: 0; font-size: 0.8rem; color: var(--text-secondary); }
    .ip-window { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
    .ip-window-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-secondary); }
    .ip-body { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: var(--space-4) var(--space-5); }
    .ip-body.is-reloading { opacity: 0.55; }
    .ip-section { padding-block: var(--space-5); border-top: 1px solid var(--border-subtle); }
    .ip-section.first { border-top: 0; padding-top: 0; display: flex; flex-direction: column; gap: var(--space-3); }
    .ip-ai-featured { padding: var(--space-4); margin-bottom: var(--space-4); background-color: var(--bg-canvas); border: 1px solid var(--border-default); border-left: 4px solid var(--brand-primary); border-radius: var(--radius-sm); }
    .ip-sub { margin-top: var(--space-4); }
    .ip-slow { margin: var(--space-3) 0 0; font-size: 0.85rem; color: var(--text-secondary); }
    .ip-footer { position: sticky; bottom: 0; display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); min-height: 56px; padding: 0 var(--space-5); border-top: 1px solid var(--border-subtle); background: var(--bg-surface); flex-shrink: 0; }
    .ip-footer-link { color: var(--brand-primary); font-size: 0.875rem; text-decoration: underline; text-underline-offset: 2px; }
    .ip-footer-close { min-height: 40px; padding: 0 var(--space-4); background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: var(--radius-xs); color: var(--brand-primary); font-weight: 600; cursor: pointer; }
    @media (hover: hover) { .ip-footer-close:hover { background-color: var(--bg-subtle); } }
    @media (max-width: 767.98px) { .ip-header, .ip-body, .ip-footer { padding-inline: var(--space-4); } .ip-footer-close, .ip-footer-link { min-height: 44px; display: inline-flex; align-items: center; } }
  `],
})
export class TrendInsightPanelComponent implements AfterViewInit {
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly context = input.required<InsightContext>();
  readonly insight = input<ProductInsight | null>(null);
  readonly meta = input<InsightMeta | null>(null);
  readonly status = input<'idle' | 'loading' | 'success' | 'error'>('idle');
  readonly reloading = input<boolean>(false);
  readonly slowLoading = input<boolean>(false);
  readonly errorMessage = input<string | null>(null);
  readonly canRetry = input<boolean>(true);
  readonly ai = input<AiBlockView | null>(null);
  readonly returnFocusTo = input<HTMLElement | null>(null);

  readonly closePanel = output<void>();
  readonly windowChange = output<TrendSortWindow>();
  readonly retry = output<void>();
  readonly generate = output<void>();
  readonly requestRegenerate = output<void>();
  readonly confirmRegenerate = output<void>();
  readonly cancelConfirm = output<void>();

  private readonly panelRef = viewChild<ElementRef<HTMLElement>>('panel');
  private readonly titleRef = viewChild<ElementRef<HTMLElement>>('titleEl');
  private readonly bodyRef = viewChild<ElementRef<HTMLElement>>('body');
  private readonly waterfallRef = viewChild<AttributionWaterfallComponent>('waterfallCmp');
  private readonly aiBlockRef = viewChild<AiDiagnosisBlockComponent>('aiBlock');

  private readonly uid = nextPanelId++;
  protected readonly titleId = `trend-insight-title-${this.uid}`;
  protected readonly summaryId = `trend-insight-summary-${this.uid}`;
  private unlockScroll: (() => void) | null = null;
  private previousAiState: AiBlockView['state'] | null = null;
  private previousWindow: number | null = null;
  private readonly windowAnnouncement = signal('');
  private announcementTimer: ReturnType<typeof setTimeout> | null = null;
  private restoreInert: (() => void) | null = null;

  protected readonly metric = computed<TrendMetric>(() => this.meta()?.metrica ?? this.context().metric);

  protected readonly windowOptions = computed<SegmentOption<TrendSortWindow>[]>(() =>
    WINDOW_OPTIONS.map((o) => ({ value: o.value, label: o.label, busy: this.status() === 'loading' })),
  );

  protected readonly windowLabel = computed(() => WINDOW_OPTIONS.find((o) => o.value === this.context().window)?.label ?? '');

  protected readonly title = computed(() => {
    const data = this.insight();
    return data
      ? panelTitle(data.direcao, data.produto.descricao)
      : `Diagnóstico de ${this.context().descricao}`;
  });

  protected readonly contextLine = computed(() => {
    const data = this.insight();
    const meta = this.meta();
    const metricLabel = this.metric() === 'revenue' ? 'Faturamento líquido' : 'Quantidade líquida';
    if (!data || !meta) return metricLabel;
    const cur = formatWindowMonthSpan(data.periodo.atual);
    const prev = formatWindowMonthSpan(data.periodo.anterior);
    const versus = meta.modoComparacao === 'average' ? `vs média de ${prev}` : `vs ${prev}`;
    return `${metricLabel} · Mês-base ${formatMonthYear(meta.mesBase)} · ${cur} ${versus}`;
  });

  protected readonly minVariationText = computed(() => {
    const v = this.meta()?.parametros?.minExplainableVariationPct;
    return v === undefined ? 'o limite mínimo' : `${String(v).replace('.', ',')}%`;
  });

  protected readonly summary = computed(() => {
    const data = this.insight();
    return data
      ? buildSummaryView(data, this.metric(), this.context().window, this.meta()?.parametros?.minExplainableVariationPct)
      : null;
  });

  protected readonly waterfall = computed(() => {
    const data = this.insight();
    return data ? buildWaterfallView(data, this.metric()) : null;
  });

  protected readonly signals = computed(() => {
    const data = this.insight();
    return data ? buildSignalViews(data) : [];
  });

  protected readonly affine = computed(() => buildAffineGroupView(this.insight()!));

  protected readonly aiStatus = computed(() => aiStatusLabel(this.ai()));

  protected readonly notices = computed(() => {
    const data = this.insight();
    const meta = this.meta();
    const list: { key: string; tone: 'info' | 'warning'; text: string; action?: string }[] = [];
    if (!data || !meta) return list;
    if (meta.avisos.some((a) => a.codigo === 'TIA-005')) {
      list.push({
        key: 'tia005',
        tone: 'warning',
        text: 'Índice de produtos afins em atualização: canibalização e grupo afim não avaliados.',
        action: 'Atualizar painel',
      });
    }
    if (meta.avisos.some((a) => a.codigo === 'FORNECEDOR_NAO_INFORMADO')) {
      list.push({
        key: 'sem-fornecedor',
        tone: 'info',
        text: 'Fornecedor do produto não informado: todos os semelhantes aparecem como "outro fornecedor".',
      });
    }
    if (data.modoDiagnostico === 'QUALITATIVO') {
      list.push({ key: 'qualitativo', tone: 'info', text: 'Base pequena: a análise mostra só os sinais, sem estimar valores.' });
    }
    if (data.celula?.status === 'NOVO') {
      list.push({ key: 'novo', tone: 'info', text: 'Produto novo ou retomado nesta janela: não há período anterior para comparar.' });
    }
    return list;
  });

  protected readonly liveMessage = computed(() => {
    const view = this.ai();
    switch (view?.state) {
      case 'gerando':
        return 'Análise com IA iniciada. Costuma levar de 10 a 30 segundos.';
      case 'sucesso':
        return 'Análise com IA pronta.';
      case 'salva':
        return view.footerText ? `Análise salva exibida. ${view.footerText}.` : 'Análise salva exibida.';
      case 'template':
        return 'Resumo automático exibido.';
      case 'erro':
      case 'limite':
        return view.message ?? '';
      default:
        return this.windowAnnouncement() || `Diagnóstico de ${this.context().descricao} aberto.`;
    }
  });

  constructor() {
    effect(() => {
      const state = this.ai()?.state ?? null;
      const prev = this.previousAiState;
      this.previousAiState = state;
      if (prev !== state) this.clearAnnouncement();
      if (prev === state || prev === null) return;
      queueMicrotask(() => {
        const block = this.aiBlockRef();
        if (!block) return;
        if (state === 'confirmando') block.focusConfirm();
        else if (prev === 'confirmando' && state !== 'gerando') block.focusMainButton();
        else if (state === 'erro') block.focusRetry();
        else if ((state === 'sucesso' || state === 'salva' || state === 'template') && prev === 'gerando') block.focusTitle();
      });
    });

    effect(() => {
      const w = this.context().window;
      if (this.previousWindow !== null && this.previousWindow !== w) {
        this.announceWindow(`Janela alterada para ${this.windowLabel()}.`);
        this.bodyRef()?.nativeElement.scrollTo?.({ top: 0 });
      }
      this.previousWindow = w;
    }, { allowSignalWrites: true });

    this.unlockScroll = lockBodyScroll(this.document);
    this.destroyRef.onDestroy(() => {
      this.unlockScroll?.();
      this.restoreInert?.();
      this.clearAnnouncement();
      const trigger = this.returnFocusTo();
      queueMicrotask(() => {
        if (trigger && trigger.isConnected) trigger.focus();
        else this.document.querySelector<HTMLElement>('h1')?.focus();
      });
    });
  }

  private announceWindow(message: string): void {
    this.windowAnnouncement.set(message);
    if (this.announcementTimer) clearTimeout(this.announcementTimer);
    this.announcementTimer = setTimeout(() => this.windowAnnouncement.set(''), 4000);
  }

  private clearAnnouncement(): void {
    if (this.announcementTimer) clearTimeout(this.announcementTimer);
    this.announcementTimer = null;
    if (this.windowAnnouncement()) this.windowAnnouncement.set('');
  }

  ngAfterViewInit(): void {
    // Navbar, `main` e a página ficam inert: o Tab não escapa do diálogo (aria-modal não basta em todos os leitores).
    this.restoreInert = inertOutside(this.host.nativeElement, this.document);
    // D-5: foco no título (conteúdo longo), não no botão Fechar.
    queueMicrotask(() => this.titleRef()?.nativeElement.focus());
  }

  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      if (this.ai()?.state === 'confirmando') this.cancelConfirm.emit();
      else this.closePanel.emit();
      return;
    }
    if (event.key === 'Tab') {
      const panel = this.panelRef()?.nativeElement;
      if (panel) trapFocus(event, panel, this.document);
    }
  }

  protected goToAi(): void {
    const block = this.aiBlockRef();
    block?.focusTitle();
    this.document.getElementById('analise-ia')?.scrollIntoView?.({ block: 'start' });
  }

  protected focusParcel(key: ParcelType): void {
    this.waterfallRef()?.focusRow(key);
  }
}
