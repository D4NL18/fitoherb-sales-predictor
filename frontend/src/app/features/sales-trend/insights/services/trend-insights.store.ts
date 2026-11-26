/**
 * Store (Signals) do painel "Por que?" (Design Plan §4.2, D-9). Provida na página da Tendência.
 * - O GET (parte numérica) nunca aciona IA; a IA só nasce de `generate()`/`confirmRegenerate()`, ligados a cliques.
 * - Gerações em voo vivem num mapa por chave: fechar o painel ou trocar de janela não cancela o POST.
 * - Nada é persistido no navegador (sem localStorage/sessionStorage) e nada é logado.
 */
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, Subscription, catchError, interval, map, of, switchMap, tap, timer } from 'rxjs';
import { TrendComparisonMode, TrendMetric, TrendSortWindow } from '../../models/sales-trend.model';
import { InsightMeta, InsightQueryParams, ProductInsight } from '../models/trend-insights.model';
import { InsightApiError, resolveInsightMessage, toInsightApiError } from '../utils/insight-error';
import { AiBlockView, AiGenerationState, deriveAiBlock } from '../utils/insight-view';
import { TrendInsightsService } from './trend-insights.service';

export const SLOW_LOAD_NOTICE_MS = 4000;
export const POLL_INTERVAL_MS = 5000;
export const MAX_POLLS = 30; // 150 s

export interface InsightContext {
  sku: number;
  descricao: string;
  fornecedor: string | null;
  window: TrendSortWindow;
  metric: TrendMetric;
  baseMonth?: string;
  comparisonMode: TrendComparisonMode;
}

export type InsightLoadStatus = 'idle' | 'loading' | 'success' | 'error';

interface LoadRequest {
  ctx: InsightContext | null;
  silent: boolean;
}

type LoadResult =
  | { ok: true; insight: ProductInsight; meta: InsightMeta }
  | { ok: false; error: InsightApiError };

function toParams(ctx: InsightContext): InsightQueryParams {
  return { metric: ctx.metric, window: ctx.window, baseMonth: ctx.baseMonth, comparisonMode: ctx.comparisonMode };
}

export function generationKey(ctx: InsightContext): string {
  return `${ctx.sku}|${ctx.metric}|${ctx.window}|${ctx.baseMonth ?? ''}|${ctx.comparisonMode}`;
}

@Injectable()
export class TrendInsightsStore {
  private readonly service = inject(TrendInsightsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly context = signal<InsightContext | null>(null);
  readonly status = signal<InsightLoadStatus>('idle');
  readonly insight = signal<ProductInsight | null>(null);
  readonly meta = signal<InsightMeta | null>(null);
  readonly error = signal<InsightApiError | null>(null);
  readonly slowLoading = signal(false);
  /** Segundos desde que o primeiro timer de geração ligou; base dos contadores da IA. */
  readonly clock = signal(0);

  private readonly generations = signal<ReadonlyMap<string, AiGenerationState>>(new Map());
  private readonly load$ = new Subject<LoadRequest>();
  private tickSub: Subscription | null = null;
  private pollSub: Subscription | null = null;
  private slowSub: Subscription | null = null;
  private pollCount = 0;

  readonly errorMessage = computed(() => {
    const e = this.error();
    return e ? resolveInsightMessage(e, 'get') : null;
  });

  readonly canRetry = computed(() => {
    const kind = this.error()?.kind;
    return !!kind && kind !== 'NOT_FOUND' && kind !== 'NO_BASE' && kind !== 'INVALID_PARAMS';
  });

  readonly reloading = computed(() => this.status() === 'loading' && this.insight() !== null);

  readonly aiBlock = computed<AiBlockView | null>(() => {
    const ctx = this.context();
    const insight = this.insight();
    const meta = this.meta();
    if (!ctx || !insight || !meta) return null;
    return deriveAiBlock(insight, meta.ia, this.generations().get(generationKey(ctx)), this.clock());
  });

  constructor() {
    this.load$
      .pipe(
        switchMap((req) => {
          if (!req.ctx) return EMPTY;
          return this.service.getProductInsight(req.ctx.sku, toParams(req.ctx)).pipe(
            map((res): LoadResult => ({ ok: true, insight: res.data, meta: res.meta })),
            catchError((err: unknown) => of<LoadResult>({ ok: false, error: toInsightApiError(err) })),
            tap((result) => this.applyLoad(result, req.silent)),
          );
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe();

    this.destroyRef.onDestroy(() => {
      this.tickSub?.unsubscribe();
      this.pollSub?.unsubscribe();
      this.slowSub?.unsubscribe();
    });
  }

  openPanel(ctx: InsightContext): void {
    this.insight.set(null);
    this.meta.set(null);
    this.context.set(ctx);
    this.startLoad(false);
  }

  setWindow(window: TrendSortWindow): void {
    const ctx = this.context();
    if (!ctx || ctx.window === window) return;
    this.context.set({ ...ctx, window });
    this.startLoad(false);
  }

  retry(): void {
    if (this.context()) this.startLoad(false);
  }

  close(): void {
    this.context.set(null);
    this.insight.set(null);
    this.meta.set(null);
    this.error.set(null);
    this.status.set('idle');
    this.slowLoading.set(false);
    this.pollSub?.unsubscribe();
    this.slowSub?.unsubscribe();
    this.load$.next({ ctx: null, silent: false });
  }

  /** Clique em "Gerar análise com IA", "Gerar resumo automático" ou "Tentar de novo": sempre `force=false`. */
  generate(): void {
    this.run(false);
  }

  /** Clique em "Gerar de novo"/"Atualizar": só abre a confirmação inline; nenhuma chamada. */
  requestRegenerate(): void {
    this.patchCurrent({ confirming: true });
  }

  cancelConfirm(): void {
    this.patchCurrent({ confirming: false });
  }

  /** Único caminho para `force=true`, depois da confirmação. */
  confirmRegenerate(): void {
    const state = this.currentGeneration();
    if (!state?.confirming) return;
    this.run(true);
  }

  private startLoad(silent: boolean): void {
    const ctx = this.context();
    if (!ctx) return;
    if (!silent) {
      this.pollCount = 0;
      this.pollSub?.unsubscribe();
      this.error.set(null);
      this.status.set('loading');
      this.slowLoading.set(false);
      this.slowSub?.unsubscribe();
      this.slowSub = timer(SLOW_LOAD_NOTICE_MS).subscribe(() => {
        if (this.status() === 'loading') this.slowLoading.set(true);
      });
    }
    this.load$.next({ ctx, silent });
  }

  private applyLoad(result: LoadResult, silent: boolean): void {
    this.slowSub?.unsubscribe();
    this.slowLoading.set(false);
    if (!result.ok) {
      if (silent) return; // polling: mantém o que já está na tela
      this.error.set(result.error);
      this.status.set('error');
      return;
    }
    this.insight.set(result.insight);
    this.meta.set(result.meta);
    this.error.set(null);
    this.status.set('success');
    this.schedulePoll(result.meta);
  }

  private schedulePoll(meta: InsightMeta): void {
    this.pollSub?.unsubscribe();
    if (!meta.ia.geracaoEmAndamento || this.pollCount >= MAX_POLLS) return;
    this.pollCount += 1;
    this.pollSub = timer(POLL_INTERVAL_MS).subscribe(() => this.startLoad(true));
  }

  private currentGeneration(): AiGenerationState | undefined {
    const ctx = this.context();
    return ctx ? this.generations().get(generationKey(ctx)) : undefined;
  }

  private setGeneration(key: string, state: AiGenerationState): void {
    const next = new Map(this.generations());
    next.set(key, state);
    this.generations.set(next);
  }

  private patchCurrent(patch: Partial<AiGenerationState>): void {
    const ctx = this.context();
    if (!ctx) return;
    const key = generationKey(ctx);
    const cur = this.generations().get(key) ?? { phase: 'idle', response: null, error: null, confirming: false };
    this.setGeneration(key, { ...cur, ...patch });
  }

  private run(force: boolean): void {
    const ctx = this.context();
    const meta = this.meta();
    if (!ctx || !meta) return;
    const key = generationKey(ctx);
    const cur = this.generations().get(key);
    if (cur?.phase === 'generating') return; // P-176.1: um pedido por vez
    if (!(cur?.response?.meta.ia ?? meta.ia).podeGerar) return;

    this.setGeneration(key, {
      phase: 'generating',
      response: cur?.response ?? null,
      error: null,
      confirming: false,
      startedAtSeconds: this.clock(),
    });
    this.ensureTicker();

    this.service
      .generateProductInsight(ctx.sku, toParams(ctx), { force })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) =>
          this.setGeneration(key, { phase: 'success', response: res, error: null, confirming: false }),
        error: (err: unknown) => {
          this.setGeneration(key, {
            phase: 'error',
            response: cur?.response ?? null,
            error: toInsightApiError(err),
            confirming: false,
            failedAtSeconds: this.clock(),
          });
          this.ensureTicker();
        },
      });
  }

  /** Liga o relógio de 1 s só enquanto há geração em voo ou contagem de Retry-After. */
  private ensureTicker(): void {
    if (this.tickSub) return;
    this.tickSub = interval(1000).subscribe(() => {
      this.clock.update((n) => n + 1);
      if (!this.needsTicker()) {
        this.tickSub?.unsubscribe();
        this.tickSub = null;
      }
    });
  }

  private needsTicker(): boolean {
    const now = this.clock();
    for (const g of this.generations().values()) {
      if (g.phase === 'generating') return true;
      if (g.phase === 'error' && g.error?.kind === 'RATE_LIMIT' && g.error.motivo === 'LIMITE_DE_PEDIDOS') {
        const wait = g.error.retryAfterSeconds ?? 60;
        if (now - (g.failedAtSeconds ?? 0) < wait) return true;
      }
    }
    return false;
  }
}
