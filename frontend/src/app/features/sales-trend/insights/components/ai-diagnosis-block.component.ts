/**
 * Bloco "Análise com IA" (Design Plan §7): 8 estados, botão único e conteúdo do diagnóstico.
 * - Todo texto vindo da IA é renderizado por interpolação (texto puro); nunca `innerHTML` (P-184.5).
 * - `sugestoesBuscaHtml` (termos do grounding) só entra em `<iframe sandbox>`, sem scripts nem same-origin, sem alteração.
 * - Nenhum valor de custo, saldo ou orçamento é exibido.
 */
import { ChangeDetectionStrategy, Component, computed, ElementRef, inject, input, output, viewChild } from '@angular/core';
import { AiDiagnosis, AiFactor, ExternalDimension, ParcelType } from '../models/trend-insights.model';
import { InlineNoticeComponent } from '../../components/inline-notice/inline-notice.component';
import { AI_NOTICE_TEXT, CONFIDENCE_LABELS, GENERATING_TEXT, HYPOTHESIS_REASONS, SLOW_AI_TEXT, factorLabel } from '../utils/insight-copy';
import { AiBlockView, formatSigned } from '../utils/insight-view';
import { ExternalFactorsSectionComponent } from './external-factors-section.component';
import { SourceLinkComponent } from './source-link.component';
import { TrendInsightSkeletonComponent } from './trend-insight-skeleton.component';

const PARCEL_KEYS: readonly string[] = [
  'SAZONALIDADE', 'PRECO', 'PRODUTO_NOVO', 'CANIBALIZACAO_MESMO_FORNECEDOR', 'CANIBALIZACAO_OUTRO_FORNECEDOR', 'CLIENTES_PERDIDOS',
];

@Component({
  selector: 'app-ai-diagnosis-block',
  standalone: true,
  imports: [InlineNoticeComponent, ExternalFactorsSectionComponent, SourceLinkComponent, TrendInsightSkeletonComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="ai-block" aria-labelledby="analise-ia">
      <header class="ai-head">
        <h3 id="analise-ia" #title class="ai-title" tabindex="-1">Análise com IA</h3>
        @if (view().originLabel) {
          <span class="origin-badge">{{ view().originLabel }}</span>
        }
      </header>

      @if (view().showFixedNotice) {
        <app-inline-notice tone="info" [text]="fixedNotice" [dismissible]="false" />
      }
      @for (n of view().notices; track n) {
        <app-inline-notice tone="info" [text]="n" />
      }
      @if (view().reusedNotice; as reused) {
        <app-inline-notice tone="info" [text]="reused" />
      }
      @if (view().agedText; as aged) {
        <p class="aged-note">{{ aged }}</p>
      }

      @switch (view().state) {
        @case ('semVariacao') {
          <p class="plain-text" data-testid="ai-sem-variacao">
            Não há variação relevante para analisar nesta janela (menos de {{ minVariationText() }}). Escolha outra janela acima.
          </p>
        }
        @case ('vazio') {
          <div class="empty-state" data-testid="ai-vazio">
            <span class="empty-icon" aria-hidden="true">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M6 3h9l4 4v14H6z"></path><path d="M9 12h7M9 16h7M9 8h3"></path>
              </svg>
            </span>
            <h4 class="empty-title">Ainda não há análise com IA para esta janela</h4>
            <p class="plain-text">{{ view().emptyText }}</p>
          </div>
        }
        @case ('gerando') {
          <div class="generating" data-testid="ai-gerando">
            <app-trend-insight-skeleton part="ai" />
            <p class="progress-text">
              {{ view().slow ? slowText : generatingText }}
              @if (view().elapsedSeconds > 0) {
                <span class="elapsed" aria-hidden="true">{{ view().elapsedSeconds }} s</span>
              }
            </p>
          </div>
        }
        @case ('template') {
          <div class="template-box" data-testid="ai-template">
            <p class="plain-text">{{ view().templateText }}</p>
            @if (view().templateNote) {
              <p class="note">{{ view().templateNote }}</p>
            }
          </div>
        }
        @case ('limite') {
          <div class="warn-box" data-testid="ai-limite">
            <p class="plain-text">{{ view().message }}</p>
            @if (view().retryRemaining !== null) {
              <span class="elapsed" aria-hidden="true">{{ view().retryRemaining }} s</span>
            }
          </div>
        }
        @case ('erro') {
          <div class="error-box" data-testid="ai-erro">
            <p class="plain-text">{{ view().message }}</p>
            @if (view().showRetry) {
              <button #retryBtn type="button" class="btn btn-secondary" (click)="retry.emit()">Tentar de novo</button>
            }
          </div>
        }
      }

      @if (view().button; as btn) {
        @if (btn.kind === 'generate') {
          <div class="action-row">
            <button
              #mainBtn
              type="button"
              class="btn btn-primary"
              [disabled]="btn.disabled"
              [attr.aria-describedby]="btn.help ? 'ai-help' : null"
              (click)="generate.emit()"
            >{{ btn.label }}</button>
            @if (btn.help) {
              <p id="ai-help" class="help-text">{{ btn.help }}</p>
            }
          </div>
        }
      }

      @if (view().radarOnly) {
        <app-external-factors-section [radar]="view().radarOnly" />
      }

      @if (view().qualitativeNote && view().state !== 'semVariacao') {
        <p class="note">{{ view().qualitativeNote }}</p>
      }

      @if (view().diagnosis; as d) {
@if (view().state !== 'gerando') {
      <div class="content" data-testid="ai-content">
          <h4 class="sub-title">O que a IA encontrou</h4>
          <p class="summary-text">{{ d.resumo }}</p>

          <h4 class="sub-title">Fatores com evidência ({{ d.fatores.length }})</h4>
          @if (d.fatores.length === 0) {
            <p class="plain-text">A IA não encontrou fator com fonte válida. Veja as hipóteses abaixo e a cascata acima.</p>
          } @else {
            <ul class="factor-list">
              @for (f of d.fatores; track $index) {
                <li class="factor" tabindex="-1" [attr.data-factor-dimension]="f.dimensao ?? null">
                  <div class="factor-line">
                    <span class="factor-glyph" aria-hidden="true">{{ f.sentido === 'POSITIVO' ? '▲' : f.sentido === 'NEGATIVO' ? '▼' : '' }}</span>
                    <strong>{{ label(f) }}</strong>
                    @if (f.rotulo === 'POSSIVEL') {
                      <span class="micro-badge">Possível</span>
                    }
                    <span class="factor-value">{{ f.parcelaEstimada !== null ? signed(f.parcelaEstimada) : '—' }}</span>
                    <span class="factor-conf">Confiança {{ confidence(f).toLowerCase() }}</span>
                  </div>
                  @if (f.explicacao) {
                    <p class="factor-explain">{{ f.explicacao }}</p>
                  }
                  @if (parcelKey(f); as key) {
                    <button type="button" class="link-btn" (click)="focusParcel.emit(key)">Dado interno · ver na cascata ↑</button>
                  }
                  @if (f.fontes.length > 0) {
                    <ul class="source-list">
                      @for (s of f.fontes; track s.url) {
                        <li><app-source-link [source]="s" /></li>
                      }
                    </ul>
                  }
                </li>
              }
            </ul>
          }

          <app-external-factors-section [view]="view().external" (focusFactors)="focusFactor($event)" />

          @if (d.hipotesesNaoConfirmadas.length > 0) {
            <div class="hypotheses" data-testid="ai-hipoteses">
              <h4 class="sub-title">Hipóteses sem fonte confirmada ({{ d.hipotesesNaoConfirmadas.length }})</h4>
              <p class="note">A IA levantou, mas não achou fonte válida para o período. Não trate como causa.</p>
              <ul class="hyp-list">
                @for (h of d.hipotesesNaoConfirmadas; track $index) {
                  <li>
                    <span>{{ hypLabel(h.tipo) }}: {{ h.descricao }}</span>
                    <span class="note block">{{ reason(h.motivo) }}</span>
                    @if (h.fontes.length > 0) {
                      <ul class="source-list">
                        @for (s of h.fontes; track s.url) {
                          <li><app-source-link [source]="s" /></li>
                        }
                      </ul>
                    }
                  </li>
                }
              </ul>
            </div>
          }

          @if (d.recomendacoes.length > 0) {
            <h4 class="sub-title">Próximos passos sugeridos</h4>
            <ol class="reco-list">
              @for (r of d.recomendacoes; track $index) {
                <li>{{ r }}</li>
              }
            </ol>
          }

          @if (d.sugestoesBuscaHtml; as html) {
            <iframe
              class="suggestions-frame"
              title="Sugestões de busca do Google"
              sandbox="allow-popups allow-popups-to-escape-sandbox"
              referrerpolicy="no-referrer"
              loading="lazy"
              height="80"
              [attr.srcdoc]="html"
            ></iframe>
          }

          <details class="tech-details">
            <summary>Detalhes técnicos</summary>
            <p class="note">Modelo: {{ d.modelo }} · Prompt {{ d.promptVersion }}</p>
          </details>
        </div>
        }
      }

      @if (view().state === 'confirmando') {
        <div class="confirm-box" role="group" aria-labelledby="confirm-text">
          <p id="confirm-text" #confirmText class="confirm-text" tabindex="-1">{{ view().confirmText }}</p>
          <div class="confirm-actions">
            <button type="button" class="btn btn-primary" (click)="confirmed.emit()">Continuar</button>
            <button type="button" class="btn btn-secondary" (click)="cancelled.emit()">Cancelar</button>
          </div>
        </div>
      }

      @if (view().footerText) {
        <p class="footer-meta">{{ view().footerText }}</p>
      }

      @if (view().button; as btn) {
        @if (btn.kind === 'regenerate') {
          <div class="action-row">
            <button
              #mainBtn
              type="button"
              class="btn btn-secondary"
              [disabled]="btn.disabled"
              [attr.aria-describedby]="btn.help ? 'ai-help' : null"
              (click)="requestRegenerate.emit()"
            >{{ btn.label }}</button>
            @if (btn.help) {
              <p id="ai-help" class="help-text">{{ btn.help }}</p>
            }
          </div>
        }
      }
    </section>
  `,
  styles: [`
    :host { display: block; }
    .ai-block { display: flex; flex-direction: column; gap: var(--space-3); }
    .ai-head { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
    .ai-title { margin: 0; font-family: var(--font-family-headline); font-size: 1rem; font-weight: 700; color: var(--text-primary); }
    .ai-title:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .origin-badge { font-size: 0.75rem; color: var(--text-secondary); border: 1px solid var(--border-default); border-radius: var(--radius-xs); padding: 1px var(--space-2); }
    .plain-text, .summary-text { margin: 0; font-size: 0.9rem; line-height: 1.5; color: var(--text-primary); overflow-wrap: anywhere; }
    .note { margin: 0; font-size: 0.75rem; color: var(--text-secondary); }
    .note.block { display: block; }
    .aged-note, .footer-meta, .help-text { margin: 0; font-size: 0.75rem; color: var(--text-secondary); }
    .empty-state { display: flex; flex-direction: column; gap: var(--space-2); color: var(--text-secondary); }
    .empty-icon { display: inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; background-color: var(--bg-muted); border-radius: var(--radius-xs); color: var(--text-secondary); }
    .empty-title { margin: 0; font-size: 0.95rem; color: var(--text-primary); font-family: var(--font-family-headline); }
    .progress-text { margin: 0; font-size: 0.85rem; color: var(--text-secondary); }
    .elapsed { font-family: var(--font-family-mono); margin-left: var(--space-2); font-variant-numeric: tabular-nums; }
    .template-box { padding: var(--space-3); border-left: 3px solid var(--feedback-neutral-bg); background-color: var(--bg-canvas); display: flex; flex-direction: column; gap: var(--space-2); }
    .warn-box, .error-box, .confirm-box { padding: var(--space-3); background-color: var(--bg-surface); border: 1px solid var(--border-default); display: flex; flex-direction: column; gap: var(--space-2); }
    .warn-box, .confirm-box { border-left: 3px solid var(--feedback-warning-bg); }
    .error-box { border-left: 3px solid var(--feedback-critical-bg); }
    .confirm-text { margin: 0; font-weight: 600; font-size: 0.9rem; }
    .confirm-text:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .confirm-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
    .content { display: flex; flex-direction: column; gap: var(--space-3); }
    .sub-title { margin: var(--space-2) 0 0; font-size: 0.85rem; font-weight: 700; color: var(--text-primary); font-family: var(--font-family-headline); }
    .factor-list, .source-list, .hyp-list, .reco-list { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: var(--space-2); }
    .reco-list { list-style: decimal; padding-left: var(--space-5); }
    .factor { display: flex; flex-direction: column; gap: var(--space-1); padding-bottom: var(--space-2); border-bottom: 1px solid var(--border-subtle); }
    .factor:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .factor-line { display: flex; align-items: baseline; gap: var(--space-2); flex-wrap: wrap; font-size: 0.875rem; }
    .factor-value { font-family: var(--font-family-mono); font-variant-numeric: tabular-nums; margin-left: auto; }
    .factor-conf { font-size: 0.75rem; color: var(--text-secondary); }
    .factor-explain { margin: 0; font-size: 0.85rem; overflow-wrap: anywhere; }
    .micro-badge { font-size: 0.7rem; font-weight: 600; color: var(--feedback-info-bg); border: 1px solid var(--feedback-info-bg); border-radius: var(--radius-xs); padding: 0 var(--space-1); }
    .link-btn { align-self: flex-start; padding: 0; background: none; border: 0; color: var(--brand-primary); font-size: 0.8125rem; text-decoration: underline; cursor: pointer; min-height: 24px; }
    @media (hover: hover) { .link-btn:hover { text-decoration-thickness: 2px; } }
    .link-btn:active { color: var(--brand-primary-active); }
    .link-btn:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    .hypotheses { border: 1px dashed var(--border-strong); background-color: var(--bg-canvas); padding: var(--space-3); display: flex; flex-direction: column; gap: var(--space-2); }
    .hypotheses .note { color: var(--text-muted); }
    .suggestions-frame { width: 100%; border: 0; background-color: var(--bg-surface); }
    .tech-details { font-size: 0.75rem; color: var(--text-secondary); }
    .action-row { display: flex; flex-direction: column; gap: var(--space-1); align-items: flex-start; }
    .btn { min-height: 40px; padding: 0 var(--space-4); font-family: var(--font-family-body); font-size: 0.875rem; font-weight: 600; border-radius: var(--radius-xs); cursor: pointer; transition: background-color var(--transition-fast), border-color var(--transition-fast); }
    .btn-primary { background-color: var(--brand-primary); color: var(--text-on-brand); border: 1px solid var(--brand-primary); }
    .btn-secondary { background-color: var(--bg-surface); color: var(--brand-primary); border: 1px solid var(--border-default); }
    @media (hover: hover) {
      .btn-primary:hover:not(:disabled) { background-color: var(--brand-primary-hover); }
      .btn-secondary:hover:not(:disabled) { background-color: var(--bg-subtle); }
    }
    .btn-primary:active:not(:disabled) { background-color: var(--brand-primary-active); }
    .btn-secondary:active:not(:disabled) { background-color: var(--bg-muted); }
    .btn:disabled { opacity: 0.55; cursor: not-allowed; }
    .btn:focus-visible { outline: 2px solid var(--border-focus); outline-offset: 2px; }
    @media (max-width: 767.98px) { .btn { min-height: 44px; } }
  `],
})
export class AiDiagnosisBlockComponent {
  readonly view = input.required<AiBlockView>();
  /** Alta (true) ou queda (false), para os rótulos dos fatores. */
  readonly rise = input<boolean>(false);
  readonly minVariationPct = input<number | null>(null);
  readonly metric = input<'revenue' | 'quantity'>('revenue');

  readonly generate = output<void>();
  readonly requestRegenerate = output<void>();
  readonly confirmed = output<void>();
  readonly cancelled = output<void>();
  readonly retry = output<void>();
  readonly focusParcel = output<ParcelType>();

  readonly titleRef = viewChild<ElementRef<HTMLElement>>('title');
  readonly confirmRef = viewChild<ElementRef<HTMLElement>>('confirmText');
  readonly mainBtnRef = viewChild<ElementRef<HTMLButtonElement>>('mainBtn');
  readonly retryRef = viewChild<ElementRef<HTMLButtonElement>>('retryBtn');

  private readonly host = inject(ElementRef<HTMLElement>);

  protected focusFactor(dimension: ExternalDimension): void {
    const target = (this.host.nativeElement as HTMLElement).querySelector<HTMLElement>(`li[data-factor-dimension="${dimension}"]`);
    target?.focus();
  }

  protected readonly fixedNotice = AI_NOTICE_TEXT;
  protected readonly generatingText = GENERATING_TEXT;
  protected readonly slowText = SLOW_AI_TEXT;

  protected readonly minVariationText = computed(() => {
    const v = this.minVariationPct();
    return v === null ? 'o limite mínimo' : `${String(v).replace('.', ',')}%`;
  });

  protected label(f: AiFactor): string {
    return factorLabel(f.tipo, this.rise());
  }

  protected hypLabel(tipo: AiDiagnosis['hipotesesNaoConfirmadas'][number]['tipo']): string {
    return factorLabel(tipo, this.rise());
  }

  protected confidence(f: AiFactor): string {
    return CONFIDENCE_LABELS[f.confianca].text;
  }

  protected reason(motivo: keyof typeof HYPOTHESIS_REASONS): string {
    return HYPOTHESIS_REASONS[motivo];
  }

  protected signed(v: number): string {
    return formatSigned(v, this.metric());
  }

  protected parcelKey(f: AiFactor): ParcelType | null {
    return f.evidenciaInterna && PARCEL_KEYS.includes(f.evidenciaInterna) ? (f.evidenciaInterna as ParcelType) : null;
  }

  focusTitle(): void {
    this.titleRef()?.nativeElement.focus();
  }

  focusConfirm(): void {
    this.confirmRef()?.nativeElement.focus();
  }

  focusMainButton(): void {
    this.mainBtnRef()?.nativeElement.focus();
  }

  focusRetry(): void {
    this.retryRef()?.nativeElement.focus();
  }
}
