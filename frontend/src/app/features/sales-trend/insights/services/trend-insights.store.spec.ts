import { TestBed, discardPeriodicTasks, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TrendInsightsStore } from './trend-insights.store';
import {
  AiDiagnosis,
  GenerateMeta,
  InsightAiState,
  InsightMeta,
  ProductInsight,
} from '../models/trend-insights.model';

const BASE = '/api/v1/sales-trend/insights/product/1007';

const IA: InsightAiState = {
  podeGerar: true, motivoBloqueio: null, geraComIa: true, motivoTemplate: null, diagnosticoSalvo: false,
  diagnosticoSalvoEm: null, diagnosticoVencido: false, podeForcar: true, geracaoEmAndamento: false,
  orcamento: { nivel: 'NORMAL' },
};

const DIAG: AiDiagnosis = {
  direcao: 'QUEDA', diagnosticoMercado: 'MISTO', resumo: 'ok', fatores: [], hipotesesNaoConfirmadas: [],
  recomendacoes: [], sugestoesBuscaHtml: null, origem: 'llm', modelo: 'gemini-4-hydrogen',
  geradoEm: '2026-11-24T14:10:27.530Z', promptVersion: 'tia-v2',
};

function insight(over: Partial<ProductInsight> = {}): ProductInsight {
  return {
    produto: { sku: 1007, descricao: 'ÓLEO DE COCO', fornecedor: 'BETA', categoriaGaleria: null, funcaoPrimaria: null },
    periodo: {
      atual: { inicio: '2026-08-01', fim: '2026-10-31', diasJanela: 92, diasCobertos: 92 },
      anterior: { inicio: '2026-05-01', fim: '2026-07-31', diasJanela: 92, diasCobertos: 92 },
      fatorAjuste: 1, baseParcial: false, contigua: true,
    },
    celula: { meses: 3, atual: 10, anterior: 20, variacaoPct: -50, status: 'VARIACAO', baseParcial: false, baseBaixa: false, devolucaoLiquida: false, atualPorDia: null, anteriorPorDia: null },
    modoDiagnostico: 'QUANTITATIVO', direcao: 'QUEDA',
    resumoNumerico: { baseAjustada: 20, deltaObservado: -10, somaParcelas: -8, residuo: -2, coberturaExplicacaoPct: 80 },
    cascata: [], indicadores: [],
    diagnosticoMercado: { classificacao: 'NAO_AVALIADO', variacaoMercadoPct: null, efeitoMercado: null, efeitoParticipacao: null, participacaoAnteriorPct: null, participacaoAtualPct: null, variacaoParticipacaoPp: null, variacaoAfinsMesmoFornecedorPct: null, variacaoAfinsOutroFornecedorPct: null },
    grupoAfim: { status: 'SEM_GRUPO_AFIM', afins: [] }, impactoEmOutrosProdutos: null, diagnosticoIa: null, ...over,
  };
}

function meta(ia: Partial<InsightAiState> = {}): InsightMeta {
  return {
    timestamp: '', version: '1.1.0', dataReferencia: '2026-11-24', ultimoDiaCoberto: '2026-11-23', mesBase: '2026-10',
    metrica: 'revenue', janela: 3, modoComparacao: 'point', promptVersion: 'tia-v2',
    indiceAfinidade: { disponivel: true, lastSyncAt: null }, avisos: [], ia: { ...IA, ...ia },
  };
}

function genMeta(over: Partial<GenerateMeta> = {}): GenerateMeta {
  return { ...meta(), origem: 'llm', motivoTemplate: null, reutilizado: false, modelo: 'gemini-4-hydrogen', geradoEm: DIAG.geradoEm, ...over };
}

describe('TrendInsightsStore', () => {
  let store: TrendInsightsStore;
  let http: HttpTestingController;
  const ctx = { sku: 1007, descricao: 'ÓLEO DE COCO', fornecedor: 'BETA', window: 3 as const, metric: 'revenue' as const, baseMonth: '2026-10', comparisonMode: 'point' as const };

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [TrendInsightsStore, provideHttpClient(), provideHttpClientTesting()] });
    store = TestBed.inject(TrendInsightsStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function openAndLoad(ia: Partial<InsightAiState> = {}, data: Partial<ProductInsight> = {}): void {
    store.openPanel(ctx);
    http.expectOne((r) => r.url === BASE).flush({ data: insight(data), meta: meta(ia) });
  }

  it('abrir o painel faz só GET com a janela da tabela e nunca chama o POST', () => {
    store.openPanel(ctx);
    expect(store.status()).toBe('loading');
    const req = http.expectOne((r) => r.url === BASE);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('window')).toBe('3');
    req.flush({ data: insight(), meta: meta() });
    expect(store.status()).toBe('success');
    expect(store.aiBlock()?.state).toBe('vazio');
    http.expectNone((r) => r.url.endsWith('/generate'));
  });

  it('erro TIA-002 no GET vira erro sem retry', () => {
    store.openPanel(ctx);
    http.expectOne((r) => r.url === BASE).flush(
      { error: { code: 'TIA-002', message: 'x', fields: [], motivo: null }, meta: {} },
      { status: 404, statusText: 'Not Found' },
    );
    expect(store.status()).toBe('error');
    expect(store.error()?.kind).toBe('NOT_FOUND');
    expect(store.canRetry()).toBeFalse();
  });

  it('trocar a janela cancela o GET anterior e dispara outro', () => {
    store.openPanel(ctx);
    const first = http.expectOne((r) => r.url === BASE);
    store.setWindow(6);
    expect(first.cancelled).toBeTrue();
    const second = http.expectOne((r) => r.url === BASE);
    expect(second.request.params.get('window')).toBe('6');
    second.flush({ data: insight(), meta: meta() });
    expect(store.context()?.window).toBe(6);
  });

  it('generate envia POST com force=false, bloqueia clique duplo e mostra sucesso por origem', () => {
    openAndLoad();
    store.generate();
    store.generate();
    const reqs = http.match((r) => r.url === `${BASE}/generate`);
    expect(reqs.length).toBe(1);
    expect(reqs[0].request.body.force).toBeFalse();
    expect(store.aiBlock()?.state).toBe('gerando');
    reqs[0].flush({ data: insight({ diagnosticoIa: DIAG }), meta: genMeta() });
    expect(store.aiBlock()?.state).toBe('sucesso');
    expect(store.aiBlock()?.originLabel).toBe('Gerada por IA');
  });

  it('IA indisponível (200 template) vira resumo automático, não erro', () => {
    openAndLoad();
    store.generate();
    http.expectOne((r) => r.url.endsWith('/generate')).flush({
      data: insight({ resumoAutomatico: 'Resumo.' }),
      meta: genMeta({ origem: 'template', motivoTemplate: 'IA_INDISPONIVEL', modelo: null, geradoEm: null }),
    });
    expect(store.aiBlock()?.state).toBe('template');
    expect(store.aiBlock()?.originLabel).toBe('Resumo automático (sem IA)');
  });

  it('429 LIMITE_DE_PEDIDOS desabilita o botão até o Retry-After (contador)', fakeAsync(() => {
    openAndLoad();
    store.generate();
    http.expectOne((r) => r.url.endsWith('/generate')).flush(
      { error: { code: 'TIA-004', message: 'x', fields: [], motivo: 'LIMITE_DE_PEDIDOS' }, meta: {} },
      { status: 429, statusText: 'Too Many', headers: { 'Retry-After': '3' } },
    );
    expect(store.aiBlock()?.state).toBe('limite');
    expect(store.aiBlock()?.button?.disabled).toBeTrue();
    tick(3000);
    expect(store.aiBlock()?.button?.disabled).toBeFalse();
    discardPeriodicTasks();
  }));

  it('401 e 500 no POST mostram erro com nova tentativa (sem force)', () => {
    openAndLoad();
    store.generate();
    http.expectOne((r) => r.url.endsWith('/generate')).flush(null, { status: 401, statusText: 'Unauthorized' });
    expect(store.aiBlock()?.state).toBe('erro');
    expect(store.aiBlock()?.message).toContain('sessão');
    store.generate();
    const retry = http.expectOne((r) => r.url.endsWith('/generate'));
    expect(retry.request.body.force).toBeFalse();
    retry.flush(null, { status: 500, statusText: 'Err' });
    expect(store.aiBlock()?.message).toBe('Não foi possível gerar a análise agora. A parte numérica está disponível.');
  });

  it('409 TIA-007 no POST cai em erro genérico sem expor texto do servidor', () => {
    openAndLoad();
    store.generate();
    http.expectOne((r) => r.url.endsWith('/generate')).flush(
      { error: { code: 'TIA-007', message: 'Sincronização já em andamento.', fields: [], motivo: null }, meta: {} },
      { status: 409, statusText: 'Conflict' },
    );
    expect(store.aiBlock()?.state).toBe('erro');
    expect(store.aiBlock()?.message).not.toContain('Sincronização');
  });

  it('regenerar: pede confirmação sem HTTP; confirmar envia force=true; cancelar não chama nada', () => {
    openAndLoad({ diagnosticoSalvo: true, diagnosticoSalvoEm: DIAG.geradoEm }, { diagnosticoIa: DIAG });
    expect(store.aiBlock()?.state).toBe('salva');
    store.requestRegenerate();
    expect(store.aiBlock()?.state).toBe('confirmando');
    store.cancelConfirm();
    expect(store.aiBlock()?.state).toBe('salva');
    http.expectNone((r) => r.url.endsWith('/generate'));

    store.requestRegenerate();
    store.confirmRegenerate();
    const req = http.expectOne((r) => r.url.endsWith('/generate'));
    expect(req.request.body.force).toBeTrue();
    req.flush({ data: insight({ diagnosticoIa: DIAG }), meta: genMeta() });
  });

  it('generate não aceita force direto (só via confirmação)', () => {
    openAndLoad({ diagnosticoSalvo: true }, { diagnosticoIa: DIAG });
    store.generate();
    const req = http.expectOne((r) => r.url.endsWith('/generate'));
    expect(req.request.body.force).toBeFalse();
    req.flush({ data: insight({ diagnosticoIa: DIAG }), meta: genMeta({ origem: 'cache', reutilizado: true }) });
    expect(store.aiBlock()?.state).toBe('salva');
  });

  it('fechar o painel ou trocar de janela não cancela a geração; reabrir mostra "Gerando…"', () => {
    openAndLoad();
    store.generate();
    const post = http.expectOne((r) => r.url.endsWith('/generate'));
    store.setWindow(6);
    http.expectOne((r) => r.url === BASE).flush({ data: insight(), meta: meta() });
    store.close();
    expect(post.cancelled).toBeFalse();
    store.openPanel(ctx);
    http.expectOne((r) => r.url === BASE).flush({ data: insight(), meta: meta() });
    expect(store.aiBlock()?.state).toBe('gerando');
    post.flush({ data: insight({ diagnosticoIa: DIAG }), meta: genMeta() });
    expect(store.aiBlock()?.state).toBe('sucesso');
  });

  it('geracaoEmAndamento no GET refaz o GET a cada 5 s e para quando termina', fakeAsync(() => {
    openAndLoad({ geracaoEmAndamento: true, podeGerar: false });
    expect(store.aiBlock()?.state).toBe('gerando');
    tick(5000);
    http.expectOne((r) => r.url === BASE).flush({ data: insight(), meta: meta({ geracaoEmAndamento: true, podeGerar: false }) });
    tick(5000);
    http.expectOne((r) => r.url === BASE).flush({ data: insight({ diagnosticoIa: DIAG }), meta: meta({ diagnosticoSalvo: true }) });
    expect(store.aiBlock()?.state).toBe('salva');
    tick(20000);
    http.expectNone((r) => r.url === BASE);
    discardPeriodicTasks();
  }));

  it('fechar limpa o painel', () => {
    openAndLoad();
    store.close();
    expect(store.context()).toBeNull();
    expect(store.aiBlock()).toBeNull();
  });
});
