/**
 * Testes dos componentes do painel "Por que?" (T-7.3.2): cascata, grupo afim, bloco de IA e diálogo.
 */
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AiDiagnosisBlockComponent } from './ai-diagnosis-block.component';
import { AffineGroupComponent } from './affine-group.component';
import { AttributionWaterfallComponent } from './attribution-waterfall.component';
import { TrendInsightPanelComponent } from './trend-insight-panel.component';
import { InsightContext } from '../services/trend-insights.store';
import { buildAffineGroupView, buildWaterfallView } from '../utils/insight-view';
import { buildSignalViews } from '../utils/insight-signals';
import { DIAGNOSIS, aiView, makeGenMeta, makeInsight, makeMeta, makeResponse } from '../testing/insight-fixtures';

function text(el: HTMLElement): string {
  return (el.textContent ?? '').replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
}

describe('AttributionWaterfallComponent', () => {
  let fixture: ComponentFixture<AttributionWaterfallComponent>;
  let el: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [AttributionWaterfallComponent], providers: [provideRouter([])] });
    fixture = TestBed.createComponent(AttributionWaterfallComponent);
    fixture.componentRef.setInput('view', buildWaterfallView(makeInsight(), 'revenue'));
    fixture.detectChanges();
    el = fixture.nativeElement;
  });

  it('é uma tabela com caption, causas na ordem e p.p. vindos da API', () => {
    expect(el.querySelector('table caption')).not.toBeNull();
    const rows = Array.from(el.querySelectorAll('tbody tr.wf-row'));
    expect(rows.length).toBe(6); // 4 parcelas + resíduo + total
    expect(text(rows[0] as HTMLElement)).toContain('Época do ano');
    expect(text(rows[0] as HTMLElement)).toContain('−6,0 p.p.');
    expect(text(rows[rows.length - 1] as HTMLElement)).toContain('Variação total');
  });

  it('não avaliado aparece com motivo e sem barra, nunca como zero', () => {
    const row = el.querySelector('tr[data-parcel="PRODUTO_NOVO"]') as HTMLElement;
    expect(text(row)).toContain('Não avaliado');
    expect(text(row)).toContain('Lista de produtos semelhantes em atualização.');
    expect(row.querySelector('svg')).toBeNull();
    expect(text(row)).not.toContain('R$ 0,00');
  });

  it('barras são aria-hidden e a lista de produtos migrados mostra "menos de 3 clientes"', () => {
    expect(el.querySelector('td.col-bar')?.getAttribute('aria-hidden')).toBe('true');
    const btn = el.querySelector('button.disclosure') as HTMLButtonElement;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    btn.click();
    fixture.detectChanges();
    expect(btn.getAttribute('aria-expanded')).toBe('true');
    expect(text(el.querySelector('.wf-items-row') as HTMLElement)).toContain('menos de 3 clientes');
    expect(text(el.querySelector('.wf-items-row') as HTMLElement)).toContain('Reajustar canibalizador');
  });

  it('focusRow foca o cabeçalho da parcela', () => {
    fixture.componentInstance.focusRow('PRECO');
    expect(document.activeElement?.closest('tr')?.getAttribute('data-parcel')).toBe('PRECO');
  });
});

describe('AffineGroupComponent', () => {
  function create(status: 'AVALIADO' | 'SEM_GRUPO_AFIM' | 'NAO_AVALIADO', rows = 1) {
    TestBed.configureTestingModule({ imports: [AffineGroupComponent], providers: [provideRouter([])] });
    const base = makeInsight();
    const afins = Array.from({ length: rows }, (_, i) => ({ ...base.grupoAfim.afins[0], sku: 4000 + i }));
    const insight = makeInsight({ grupoAfim: { status, afins } });
    const f = TestBed.createComponent(AffineGroupComponent);
    f.componentRef.setInput('view', buildAffineGroupView(insight));
    f.componentRef.setInput('status', status);
    f.componentRef.setInput('metric', 'revenue');
    f.componentRef.setInput('sku', 2045);
    f.detectChanges();
    return f;
  }

  it('usa o TrendCellComponent da Tendência em cada afim', () => {
    const f = create('AVALIADO');
    expect(f.nativeElement.querySelectorAll('app-trend-cell').length).toBe(1);
    expect(text(f.nativeElement)).toContain('15,0%');
  });

  it('mostra 8 linhas e "Mostrar todos os N"', () => {
    const f = create('AVALIADO', 12);
    expect(f.nativeElement.querySelectorAll('li.ag-row').length).toBe(8);
    const btn = Array.from(f.nativeElement.querySelectorAll('button')).find((b) => (b as HTMLElement).textContent?.includes('Mostrar todos os 12')) as HTMLButtonElement;
    btn.click();
    f.detectChanges();
    expect(f.nativeElement.querySelectorAll('li.ag-row').length).toBe(12);
  });

  it('aponta a nota de 90 dias e o link com abrir={sku}', () => {
    const f = create('AVALIADO');
    expect(text(f.nativeElement)).toContain('usa os últimos 90 dias');
    const link = f.nativeElement.querySelector('a.ag-link:not(.block)') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toContain('abrir=4000');
    expect(link.getAttribute('href')).toContain('periodo=90');
  });

  it('SEM_GRUPO_AFIM usa o estado vazio e NAO_AVALIADO oferece atualizar', () => {
    expect(text(create('SEM_GRUPO_AFIM', 0).nativeElement)).toContain('Sem produtos semelhantes para comparar');
    TestBed.resetTestingModule();
    const f = create('NAO_AVALIADO', 0);
    let refreshed = false;
    f.componentInstance.refresh.subscribe(() => (refreshed = true));
    (f.nativeElement.querySelector('button.ag-btn') as HTMLButtonElement).click();
    expect(refreshed).toBeTrue();
  });
});

describe('AiDiagnosisBlockComponent', () => {
  function create(view: ReturnType<typeof aiView>): ComponentFixture<AiDiagnosisBlockComponent> {
    TestBed.configureTestingModule({ imports: [AiDiagnosisBlockComponent] });
    const f = TestBed.createComponent(AiDiagnosisBlockComponent);
    f.componentRef.setInput('view', view);
    f.detectChanges();
    return f;
  }

  const base = makeInsight();

  it('vazio: só o botão aciona a geração, com aviso fixo e sem custo', () => {
    const f = create(aiView(base));
    const el = f.nativeElement as HTMLElement;
    expect(text(el)).toContain('Ainda não há análise com IA para esta janela');
    expect(text(el)).toContain('Diagnóstico gerado por IA a partir de dados internos e notícias públicas');
    expect(text(el)).not.toMatch(/US\$|dólar|orçamento|saldo|crédito|token/i);
    let generated = 0;
    f.componentInstance.generate.subscribe(() => generated++);
    expect(generated).toBe(0);
    (el.querySelector('button.btn-primary') as HTMLButtonElement).click();
    expect(generated).toBe(1);
  });

  it('geraComIa=false mostra "Gerar resumo automático" e a ajuda', () => {
    const f = create(aiView(base, undefined, { geraComIa: false, motivoTemplate: 'IA_DESLIGADA' }));
    const el = f.nativeElement as HTMLElement;
    expect(text(el.querySelector('button.btn') as HTMLElement)).toBe('Gerar resumo automático');
    expect(text(el)).toContain('A análise com IA não está disponível agora');
  });

  it('gerando: botão desabilitado, skeleton e texto de progresso sem percentual', () => {
    const f = create(aiView(base, { phase: 'generating', startedAtSeconds: 0 }, {}, 5));
    const el = f.nativeElement as HTMLElement;
    expect((el.querySelector('button.btn') as HTMLButtonElement).disabled).toBeTrue();
    expect(text(el.querySelector('button.btn') as HTMLElement)).toBe('Gerando…');
    expect(el.querySelector('[data-testid="skeleton-ai"]')).not.toBeNull();
    expect(text(el.querySelector('.progress-text') as HTMLElement)).toContain('Costuma levar de 10 a 30 segundos');
    expect(text(el)).not.toContain('%');
  });

  it('sucesso: rótulo "Gerada por IA", fatores, fontes com rel/target e domínio, hipóteses separadas', () => {
    const insight = makeInsight({ diagnosticoIa: DIAGNOSIS });
    const f = create(aiView(insight, { phase: 'success', response: makeResponse({ diagnosticoIa: DIAGNOSIS }, { origem: 'fallback' }) }));
    const el = f.nativeElement as HTMLElement;
    expect(text(el.querySelector('.origin-badge') as HTMLElement)).toBe('Gerada por IA');
    expect(text(el)).toContain('Possível');
    const a = el.querySelector('a[href^="https://www.exemplo-noticias"]') as HTMLAnchorElement;
    expect(a.getAttribute('rel')).toBe('noopener noreferrer');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(text(el)).toContain('exemplo-noticias.com.br');
    expect(text(el)).toContain('14/08/2026');
    const hyp = el.querySelector('[data-testid="ai-hipoteses"]') as HTMLElement;
    expect(text(hyp)).toContain('Hipóteses sem fonte confirmada (1)');
    expect(text(hyp)).toContain('Nenhuma fonte encontrada.');
    expect(text(el)).toContain('Gerar de novo');
    expect(text(el)).not.toContain('gemini'.toUpperCase());
  });

  it('texto da IA é texto puro: HTML do resumo não vira elemento', () => {
    const evil = { ...DIAGNOSIS, resumo: '<img src=x onerror="window.__xss=1"><b>negrito</b>' };
    const f = create(aiView(makeInsight({ diagnosticoIa: evil }), { phase: 'success', response: makeResponse({ diagnosticoIa: evil }, { origem: 'llm' }) }));
    const el = f.nativeElement as HTMLElement;
    expect(el.querySelector('.summary-text img')).toBeNull();
    expect(el.querySelector('.summary-text b')).toBeNull();
    expect(text(el.querySelector('.summary-text') as HTMLElement)).toContain('<img src=x');
  });

  it('link com esquema perigoso não vira <a>', () => {
    const bad = { ...DIAGNOSIS, fatores: [{ ...DIAGNOSIS.fatores[1], fontes: [{ ...DIAGNOSIS.fatores[1].fontes[0], url: 'javascript:alert(1)' }] }] };
    const f = create(aiView(makeInsight({ diagnosticoIa: bad }), { phase: 'success', response: makeResponse({ diagnosticoIa: bad }, { origem: 'llm' }) }));
    expect((f.nativeElement as HTMLElement).querySelector('a[href^="javascript"]')).toBeNull();
  });

  it('sugestões de busca: iframe sandbox sem scripts/same-origin, só quando vier HTML', () => {
    const without = create(aiView(makeInsight({ diagnosticoIa: DIAGNOSIS }), { phase: 'success', response: makeResponse({ diagnosticoIa: DIAGNOSIS }, { origem: 'llm' }) }));
    expect((without.nativeElement as HTMLElement).querySelector('iframe')).toBeNull();
    TestBed.resetTestingModule();

    const withHtml = { ...DIAGNOSIS, sugestoesBuscaHtml: '<div class="chip"><a href="https://www.google.com/search?q=x">x</a></div><script>window.__s=1</script>' };
    const f = create(aiView(makeInsight({ diagnosticoIa: withHtml }), { phase: 'success', response: makeResponse({ diagnosticoIa: withHtml }, { origem: 'llm' }) }));
    const frame = (f.nativeElement as HTMLElement).querySelector('iframe') as HTMLIFrameElement;
    expect(frame).not.toBeNull();
    const sandbox = frame.getAttribute('sandbox') ?? '';
    expect(sandbox).not.toContain('allow-scripts');
    expect(sandbox).not.toContain('allow-same-origin');
    expect(frame.getAttribute('srcdoc')).toContain('<script>window.__s=1</script>'); // entregue sem alteração
  });

  it('template: selo "Resumo automático (sem IA)", nota do motivo e sem aviso fixo de IA', () => {
    const f = create(
      aiView(base, {
        phase: 'success',
        response: makeResponse({ resumoAutomatico: 'Resumo gerado por regras.' }, { origem: 'template', motivoTemplate: 'GATE_RESIDUO_BAIXO', modelo: null, geradoEm: null }),
      }),
    );
    const el = f.nativeElement as HTMLElement;
    expect(text(el.querySelector('.origin-badge') as HTMLElement)).toBe('Resumo automático (sem IA)');
    expect(text(el)).toContain('Resumo gerado por regras.');
    expect(text(el)).toContain('Os dados internos já explicam quase tudo');
    expect(text(el)).not.toContain('Diagnóstico gerado por IA');
  });

  it('cache: rótulo "Análise salva" com data no rodapé', () => {
    const f = create(aiView(makeInsight({ diagnosticoIa: DIAGNOSIS }), undefined, { diagnosticoSalvo: true, diagnosticoSalvoEm: DIAGNOSIS.geradoEm }));
    const el = f.nativeElement as HTMLElement;
    expect(text(el.querySelector('.origin-badge') as HTMLElement)).toBe('Análise salva');
    expect(text(el.querySelector('.footer-meta') as HTMLElement)).toMatch(/^Gerada em \d{2}\/\d{2}\/\d{4} às \d{2}:\d{2}$/);
  });

  it('regenerar: o botão pede confirmação (nunca emite generate) e a confirmação emite confirmed/cancelled', () => {
    const insight = makeInsight({ diagnosticoIa: DIAGNOSIS });
    const f = create(aiView(insight, undefined, { diagnosticoSalvo: true }));
    const events: string[] = [];
    f.componentInstance.generate.subscribe(() => events.push('generate'));
    f.componentInstance.requestRegenerate.subscribe(() => events.push('request'));
    f.componentInstance.confirmed.subscribe(() => events.push('confirmed'));
    f.componentInstance.cancelled.subscribe(() => events.push('cancelled'));
    (f.nativeElement.querySelector('button.btn-secondary') as HTMLButtonElement).click();
    expect(events).toEqual(['request']);

    f.componentRef.setInput('view', aiView(insight, { confirming: true }, { diagnosticoSalvo: true }));
    f.detectChanges();
    const el = f.nativeElement as HTMLElement;
    expect(text(el.querySelector('[role="group"]') as HTMLElement)).toContain('Gerar de novo substitui a análise salva desta janela. Continuar?');
    expect(text(el)).not.toMatch(/crédito/i);
    const [cont, cancel] = Array.from(el.querySelectorAll('.confirm-actions button')) as HTMLButtonElement[];
    cont.click();
    cancel.click();
    expect(events).toEqual(['request', 'confirmed', 'cancelled']);
    expect(text(el)).not.toContain('Análise aprofundada');
  });

  it('podeForcar=false desabilita "Gerar de novo" com motivo neutro', () => {
    const f = create(aiView(makeInsight({ diagnosticoIa: DIAGNOSIS }), undefined, { diagnosticoSalvo: true, podeForcar: false }));
    const el = f.nativeElement as HTMLElement;
    expect((el.querySelector('button.btn-secondary') as HTMLButtonElement).disabled).toBeTrue();
    expect(text(el)).toContain('Já existe uma análise salva para esta janela.');
  });

  it('erro mostra "Tentar de novo" e limite diário desabilita sem contador', () => {
    const err = aiView(base, { phase: 'error', error: { kind: 'NETWORK', code: null, motivo: null, retryAfterSeconds: null, status: 0 } });
    const f = create(err);
    let retried = false;
    f.componentInstance.retry.subscribe(() => (retried = true));
    expect(text(f.nativeElement)).toContain('Não foi possível gerar a análise agora. A parte numérica está disponível.');
    (f.nativeElement.querySelector('.error-box button') as HTMLButtonElement).click();
    expect(retried).toBeTrue();
    TestBed.resetTestingModule();

    const lim = create(aiView(base, { phase: 'error', error: { kind: 'RATE_LIMIT', code: 'TIA-004', motivo: 'LIMITE_DIARIO', retryAfterSeconds: 99, status: 429 } }));
    expect(text(lim.nativeElement)).toContain('limite de análises por hoje');
    expect((lim.nativeElement.querySelector('button.btn') as HTMLButtonElement).disabled).toBeTrue();
  });

  it('SEM_VARIACAO não tem botão', () => {
    const f = create(aiView(makeInsight({ modoDiagnostico: 'SEM_VARIACAO' }), undefined, { podeGerar: false, motivoBloqueio: 'SEM_VARIACAO' }));
    expect(f.nativeElement.querySelector('button.btn')).toBeNull();
  });
});

describe('TrendInsightPanelComponent', () => {
  const ctx: InsightContext = { sku: 2045, descricao: 'CREATINA 300G', fornecedor: 'ALFA', window: 3, metric: 'revenue', baseMonth: '2026-10', comparisonMode: 'point' };
  let fixture: ComponentFixture<TrendInsightPanelComponent>;
  let el: HTMLElement;

  function setup(inputs: Record<string, unknown>): void {
    TestBed.configureTestingModule({ imports: [TrendInsightPanelComponent], providers: [provideRouter([])] });
    fixture = TestBed.createComponent(TrendInsightPanelComponent);
    fixture.componentRef.setInput('context', ctx);
    for (const [k, v] of Object.entries(inputs)) fixture.componentRef.setInput(k, v);
    fixture.detectChanges();
    el = fixture.nativeElement;
  }

  function loaded() {
    const insight = makeInsight();
    return { insight, meta: makeMeta(), status: 'success', ai: aiView(insight) };
  }

  afterEach(() => {
    document.body.style.overflow = '';
  });

  it('é um diálogo modal rotulado, trava a rolagem e foca o título (D-5)', async () => {
    setup(loaded());
    await Promise.resolve();
    const dialog = el.querySelector('aside[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const title = el.querySelector('h2') as HTMLElement;
    expect(dialog.getAttribute('aria-labelledby')).toBe(title.id);
    expect(text(title)).toBe('Por que CREATINA 300G caiu?');
    expect(document.activeElement).toBe(title);
    expect(document.body.style.overflow).toBe('hidden');
    expect(el.querySelector('button[aria-label="Fechar diagnóstico"]')).not.toBeNull();
  });

  it('abrir mostra a parte numérica e o bloco de IA vazio, sem disparar geração', () => {
    setup(loaded());
    let generated = 0;
    fixture.componentInstance.generate.subscribe(() => generated++);
    expect(text(el)).toContain('As causas medidas explicam 88,7% da queda');
    expect(text(el)).toContain('Perdeu participação');
    expect(text(el)).toContain('Ainda não há análise com IA para esta janela');
    expect(generated).toBe(0);
  });

  it('Esc fecha o painel; com confirmação aberta, Esc só cancela', () => {
    setup(loaded());
    let closed = 0;
    let cancelled = 0;
    fixture.componentInstance.closePanel.subscribe(() => closed++);
    fixture.componentInstance.cancelConfirm.subscribe(() => cancelled++);

    const insight = makeInsight({ diagnosticoIa: DIAGNOSIS });
    fixture.componentRef.setInput('insight', insight);
    fixture.componentRef.setInput('ai', aiView(insight, { confirming: true }, { diagnosticoSalvo: true }));
    fixture.detectChanges();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect([closed, cancelled]).toEqual([0, 1]);

    fixture.componentRef.setInput('ai', aiView(insight, undefined, { diagnosticoSalvo: true }));
    fixture.detectChanges();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(closed).toBe(1);
  });

  it('clique no backdrop e no botão Fechar emitem closePanel', () => {
    setup(loaded());
    let closed = 0;
    fixture.componentInstance.closePanel.subscribe(() => closed++);
    (el.querySelector('.ip-backdrop') as HTMLElement).click();
    (el.querySelector('button[aria-label="Fechar diagnóstico"]') as HTMLButtonElement).click();
    expect(closed).toBe(2);
  });

  it('Tab no último elemento volta ao primeiro (focus trap)', () => {
    setup(loaded());
    const focusables = Array.from(el.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'));
    focusables[focusables.length - 1].focus();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    document.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBeTrue();
    expect(document.activeElement).toBe(focusables[0]);
  });

  it('trocar a janela emite windowChange', () => {
    setup(loaded());
    let w: number | null = null;
    fixture.componentInstance.windowChange.subscribe((v) => (w = v));
    const radios = Array.from(el.querySelectorAll<HTMLButtonElement>('app-segmented-control button'));
    radios.find((b) => b.textContent?.includes('6 meses'))!.click();
    expect(w as number | null).toBe(6);
  });

  it('seletor de janela ocupado usa aria-disabled, mantém o foco e não emite windowChange', () => {
    setup({ ...loaded(), status: 'loading', reloading: true });
    let w: number | null = null;
    fixture.componentInstance.windowChange.subscribe((v) => (w = v));
    const radios = Array.from(el.querySelectorAll<HTMLButtonElement>('app-segmented-control button'));
    expect(radios.every((b) => !b.disabled && b.getAttribute('aria-disabled') === 'true')).toBeTrue();
    const target = radios.find((b) => b.textContent?.includes('6 meses'))!;
    target.focus();
    target.click();
    expect(w as number | null).toBeNull();
    expect(document.activeElement).toBe(target);
  });

  it('recarregar: skeleton só no lugar da cascata, sem skeleton do painel inteiro', () => {
    setup({ ...loaded(), status: 'loading', reloading: true });
    expect(el.querySelector('[data-testid="skeleton-waterfall"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="skeleton-panel"]')).toBeNull();
    expect(el.querySelector('.ip-body')!.getAttribute('aria-busy')).toBe('true');
  });

  it('aria-describedby só existe depois do GET', () => {
    setup({ status: 'loading', insight: null, meta: null, ai: null });
    expect(el.querySelector('aside')!.hasAttribute('aria-describedby')).toBeFalse();
  });

  it('deixa navbar e página inert enquanto aberto e restaura ao destruir', () => {
    const shell = document.createElement('div');
    shell.innerHTML = '<header id="nav"></header><main id="main"></main>';
    document.body.appendChild(shell);
    TestBed.configureTestingModule({ imports: [TrendInsightPanelComponent], providers: [provideRouter([])] });
    fixture = TestBed.createComponent(TrendInsightPanelComponent);
    shell.querySelector('#main')!.appendChild(fixture.nativeElement);
    fixture.componentRef.setInput('context', ctx);
    fixture.detectChanges();
    expect(shell.querySelector('#nav')!.hasAttribute('inert')).toBeTrue();
    fixture.destroy();
    expect(shell.querySelector('#nav')!.hasAttribute('inert')).toBeFalse();
    shell.remove();
  });

  it('Tab com o foco fora do painel (ex.: body) volta para dentro', () => {
    setup(loaded());
    (document.activeElement as HTMLElement | null)?.blur();
    const ev = new KeyboardEvent('keydown', { key: 'Tab', cancelable: true });
    document.dispatchEvent(ev);
    expect(ev.defaultPrevented).toBeTrue();
    expect(el.querySelector('aside')!.contains(document.activeElement)).toBeTrue();
  });

  it('anúncio de troca de janela vai à região viva e é limpo depois', fakeAsync(() => {
    setup({ ...loaded(), ai: null });
    fixture.componentRef.setInput('context', { ...ctx, window: 6 });
    fixture.detectChanges();
    expect(text(el.querySelector('[data-testid="panel-live"]') as HTMLElement)).toContain('Janela alterada para');
    tick(4100);
    fixture.detectChanges();
    expect(text(el.querySelector('[data-testid="panel-live"]') as HTMLElement)).not.toContain('Janela alterada para');
  }));

  it('carregando: skeleton com a geometria do painel e título provisório (sem spinner)', () => {
    setup({ status: 'loading', insight: null, meta: null, ai: null });
    expect(el.querySelector('[data-testid="skeleton-panel"]')).not.toBeNull();
    expect(text(el.querySelector('h2') as HTMLElement)).toBe('Diagnóstico de CREATINA 300G');
  });

  it('erro TIA-002 sem retry oferece Fechar', () => {
    setup({ status: 'error', insight: null, meta: null, ai: null, canRetry: false, errorMessage: 'Este produto não está mais no catálogo ativo.' });
    expect(text(el)).toContain('Este produto não está mais no catálogo ativo.');
    expect(text(el)).not.toContain('Tentar novamente');
  });

  it('TIA-005 mostra aviso com ação "Atualizar painel" que refaz o GET', () => {
    const l = loaded();
    setup({ ...l, meta: { ...l.meta, avisos: [{ codigo: 'TIA-005', mensagem: 'x' }] } });
    let retried = false;
    fixture.componentInstance.retry.subscribe(() => (retried = true));
    const btn = Array.from(el.querySelectorAll('app-inline-notice button')).find((b) => b.textContent?.includes('Atualizar painel')) as HTMLButtonElement;
    btn.click();
    expect(retried).toBeTrue();
  });

  it('SEM_VARIACAO mostra estado vazio com "Ver 3 meses" (janela diferente de 3)', () => {
    const insight = makeInsight({ modoDiagnostico: 'SEM_VARIACAO', direcao: null, resumoNumerico: null, cascata: [] });
    setup({ insight, meta: makeMeta({ podeGerar: false, motivoBloqueio: 'SEM_VARIACAO' }), status: 'success', ai: aiView(insight, undefined, { podeGerar: false, motivoBloqueio: 'SEM_VARIACAO' }) });
    fixture.componentRef.setInput('context', { ...ctx, window: 6 });
    fixture.detectChanges();
    expect(text(el)).toContain('Sem variação relevante em 6 meses');
    expect(text(el)).toContain('Ver 3 meses');
  });

  it('modo qualitativo troca a cascata pela lista de sinais', () => {
    const insight = makeInsight({ modoDiagnostico: 'QUALITATIVO', resumoNumerico: null, cascata: [] });
    setup({ insight, meta: makeMeta(), status: 'success', ai: aiView(insight) });
    expect(el.querySelector('app-attribution-waterfall')).toBeNull();
    expect(text(el)).toContain('Sinais encontrados (sem estimar valores)');
    expect(text(el)).toContain('Base pequena');
  });

  it('alta mostra o bloco "Esta alta está tirando vendas de…"', () => {
    const insight = makeInsight({
      direcao: 'ALTA',
      impactoEmOutrosProdutos: {
        totalInterno: 480, totalConcorrentes: 3400,
        itens: [{ sku: 2045, descricao: 'CONCORRENTE X', fornecedor: 'ALFA', sameSupplier: false, affinityScore: 0.8, tipoImpacto: 'GANHO_SOBRE_CONCORRENTE', receitaMigrada: 3400, clientesMigrados: 12, confianca: 'ALTA', mecanismo: 'PRECO_MENOR_DESTROI_MARGEM', netMarginImpact: -1, estoqueZerado: false }],
      },
    });
    setup({ insight, meta: makeMeta(), status: 'success', ai: aiView(insight) });
    expect(text(el)).toContain('Esta alta está tirando vendas de 1 produto');
    expect(text(el)).toContain('R$ 3.400,00');
  });

  it('nenhum texto da tela expõe dólar, token ou orçamento', () => {
    setup(loaded());
    expect(text(el)).not.toMatch(/US\$|dólar|dolar|token|orçamento|saldo/i);
    expect(JSON.stringify(makeGenMeta())).toBeTruthy();
  });

  it('devolve o foco ao botão que abriu ao destruir', async () => {
    const trigger = document.createElement('button');
    document.body.appendChild(trigger);
    setup({ ...loaded(), returnFocusTo: trigger });
    fixture.destroy();
    await Promise.resolve();
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});

describe('buildSignalViews', () => {
  it('ruptura presente e indicadores ausentes/não avaliados', () => {
    const insight = makeInsight({
      indicadores: [
        { tipo: 'RUPTURA', status: 'AVALIADO', sentido: 'NEGATIVO', confianca: 'MEDIA', valor: null, motivoSemEfeito: null, motivoNaoAvaliado: null, evidencia: { estoqueAtual: 0, statusEstoque: 'ZERADO', observacao: null } },
        { tipo: 'PROMOCAO', status: 'SEM_EFEITO', sentido: null, confianca: null, valor: null, motivoSemEfeito: 'SEM_PROMOCAO', motivoNaoAvaliado: null, evidencia: null },
        { tipo: 'REGIONAL', status: 'NAO_AVALIADO', sentido: null, confianca: null, valor: null, motivoSemEfeito: null, motivoNaoAvaliado: 'ANONIMIZACAO', evidencia: null },
      ],
    });
    const v = buildSignalViews(insight);
    expect(v[0].text).toContain('Estoque atual: 0 un.');
    expect(v[1].glyph).toBe('○');
    expect(v[2].stateText).toBe('não avaliado');
  });
});
