import {
  AiDiagnosis,
  CascadeParcel,
  GenerateInsightResponse,
  GenerateMeta,
  InsightAiState,
  ProductInsight,
} from '../models/trend-insights.model';
import { InsightApiError } from './insight-error';
import {
  AiGenerationState,
  aiStatusLabel,
  buildAffineGroupView,
  buildSummaryView,
  buildWaterfallView,
  deriveAiBlock,
  formatClientCount,
  panelTitle,
  safeHref,
  sourceDomain,
} from './insight-view';

const CELL = {
  meses: 3 as const, atual: 26000, anterior: 40000, variacaoPct: -35, status: 'VARIACAO' as const,
  baseParcial: false, baseBaixa: false, devolucaoLiquida: false, atualPorDia: null, anteriorPorDia: null,
};

function parcel(over: Partial<CascadeParcel>): CascadeParcel {
  return {
    tipo: 'SAZONALIDADE', status: 'AVALIADO', valor: -2400, pontosPercentuais: -6, valorReceita: null,
    sentido: 'NEGATIVO', explicativa: true, cortada: false, confianca: 'MEDIA', motivoNaoAvaliado: null,
    motivoSemEfeito: null, detalhe: null, itens: [], ...over,
  };
}

function insight(over: Partial<ProductInsight> = {}): ProductInsight {
  return {
    produto: { sku: 2045, descricao: 'CREATINA 300G', fornecedor: 'ALFA', categoriaGaleria: null, funcaoPrimaria: null },
    periodo: {
      atual: { inicio: '2026-10-01', fim: '2026-10-31', diasJanela: 31, diasCobertos: 31 },
      anterior: { inicio: '2026-07-01', fim: '2026-07-31', diasJanela: 31, diasCobertos: 31 },
      fatorAjuste: 1, baseParcial: false, contigua: false,
    },
    celula: CELL,
    modoDiagnostico: 'QUANTITATIVO',
    direcao: 'QUEDA',
    resumoNumerico: { baseAjustada: 40000, deltaObservado: -14000, somaParcelas: -12411.6, residuo: -1588.4, coberturaExplicacaoPct: 88.7 },
    cascata: [
      parcel({}),
      parcel({ tipo: 'PRECO', valor: -1161.6, pontosPercentuais: -2.9 }),
      parcel({ tipo: 'PRODUTO_NOVO', status: 'SEM_EFEITO', valor: null, pontosPercentuais: null, confianca: null, motivoSemEfeito: 'NAO_SE_APLICA_A_ALTA' }),
      parcel({ tipo: 'CANIBALIZACAO_MESMO_FORNECEDOR', status: 'NAO_AVALIADO', valor: null, pontosPercentuais: null, confianca: null, motivoNaoAvaliado: 'MES_BASE_ANTIGO' }),
      parcel({ tipo: 'CANIBALIZACAO_OUTRO_FORNECEDOR', valor: -8850, pontosPercentuais: -22.1, cortada: true,
        itens: [{ sku: 3301, descricao: 'X', fornecedor: 'B', sameSupplier: false, affinityScore: 0.8, lancamento: false,
          receitaMigrada: 3400, clientesMigrados: '<3', confianca: 'ALTA', mecanismo: 'PRECO_MENOR_DESTROI_MARGEM', netMarginImpact: -1 }] }),
      parcel({ tipo: 'CLIENTES_PERDIDOS', status: 'SEM_EFEITO', valor: null, pontosPercentuais: null, confianca: null, motivoSemEfeito: 'SEM_CLIENTES_PERDIDOS' }),
    ],
    indicadores: [],
    diagnosticoMercado: {
      classificacao: 'PERDA_DE_PARTICIPACAO', variacaoMercadoPct: 21, efeitoMercado: 8400, efeitoParticipacao: -22400,
      participacaoAnteriorPct: 31, participacaoAtualPct: 25.7, variacaoParticipacaoPp: -5.3,
      variacaoAfinsMesmoFornecedorPct: null, variacaoAfinsOutroFornecedorPct: null,
    },
    grupoAfim: { status: 'AVALIADO', afins: [] },
    impactoEmOutrosProdutos: null,
    diagnosticoIa: null,
    ...over,
  };
}

const AI_STATE: InsightAiState = {
  podeGerar: true, motivoBloqueio: null, geraComIa: true, motivoTemplate: null, diagnosticoSalvo: false,
  diagnosticoSalvoEm: null, diagnosticoVencido: false, podeForcar: true, geracaoEmAndamento: false,
  orcamento: { nivel: 'NORMAL' },
};

const DIAG: AiDiagnosis = {
  direcao: 'QUEDA', diagnosticoMercado: 'PERDA_DE_PARTICIPACAO', resumo: 'Resumo <b>x</b>', fatores: [],
  hipotesesNaoConfirmadas: [], recomendacoes: [], sugestoesBuscaHtml: null, origem: 'llm',
  modelo: 'gemini-4-hydrogen', geradoEm: '2026-11-24T14:10:27.530Z', promptVersion: 'tia-v2',
};

function genMeta(over: Partial<GenerateMeta>): GenerateMeta {
  return {
    timestamp: '', version: '1.1.0', dataReferencia: '2026-11-24', ultimoDiaCoberto: '2026-11-23', mesBase: '2026-10',
    metrica: 'revenue', janela: 3, modoComparacao: 'point', promptVersion: 'tia-v2',
    indiceAfinidade: { disponivel: true, lastSyncAt: null }, avisos: [], ia: AI_STATE,
    origem: 'llm', motivoTemplate: null, reutilizado: false, modelo: 'gemini-4-hydrogen', geradoEm: DIAG.geradoEm, ...over,
  };
}

function gen(over: Partial<AiGenerationState>): AiGenerationState {
  return { phase: 'idle', response: null, error: null, confirming: false, ...over };
}

function post(data: Partial<ProductInsight>, meta: Partial<GenerateMeta>): GenerateInsightResponse {
  return { data: insight(data), meta: genMeta(meta) };
}

describe('insight-view', () => {
  describe('utilitários', () => {
    it('formatClientCount exibe "<3" como "menos de 3 clientes" sem converter em número', () => {
      expect(formatClientCount('<3')).toBe('menos de 3 clientes');
      expect(formatClientCount(9)).toBe('9 clientes');
    });

    it('sourceDomain tira www e cai para o domínio informado quando a URL é inválida', () => {
      expect(sourceDomain('https://www.agrolink.com.br/x', 'a.com')).toBe('agrolink.com.br');
      expect(sourceDomain('lixo', 'a.com')).toBe('a.com');
    });

    it('safeHref só aceita http(s)', () => {
      expect(safeHref('https://a.com/x')).toBe('https://a.com/x');
      expect(safeHref('javascript:alert(1)')).toBeNull();
    });

    it('panelTitle varia por direção', () => {
      expect(panelTitle('QUEDA', 'ABC')).toBe('Por que ABC caiu?');
      expect(panelTitle('ALTA', 'ABC')).toBe('Por que ABC subiu?');
      expect(panelTitle(null, 'ABC')).toBe('Por que ABC mudou?');
    });
  });

  describe('buildWaterfallView', () => {
    it('mantém as 6 parcelas na ordem, resíduo e total com p.p. da API', () => {
      const v = buildWaterfallView(insight(), 'revenue');
      expect(v.rows.map((r) => r.key)).toEqual([
        'SAZONALIDADE', 'PRECO', 'PRODUTO_NOVO', 'CANIBALIZACAO_MESMO_FORNECEDOR',
        'CANIBALIZACAO_OUTRO_FORNECEDOR', 'CLIENTES_PERDIDOS', 'RESIDUO', 'TOTAL',
      ]);
      expect(v.rows[0].ppText).toBe('−6,0 p.p.');
      expect(v.rows[0].valueText).toBe('−R$ 2.400,00');
      expect(v.rows[6].label).toBe('Sem explicação nos dados internos');
    });

    it('título muda abaixo de 50% de cobertura', () => {
      expect(buildWaterfallView(insight(), 'revenue').title).toBe('As causas medidas explicam 88,7% da queda');
      const low = insight({ resumoNumerico: { baseAjustada: 40000, deltaObservado: -14000, somaParcelas: -2800, residuo: -11200, coberturaExplicacaoPct: 20 } });
      expect(buildWaterfallView(low, 'revenue').title).toContain('A maior parte da queda (80,0%) não tem causa nos dados internos');
    });

    it('não avaliado e sem efeito não têm barra e nunca viram zero', () => {
      const v = buildWaterfallView(insight(), 'revenue');
      const sem = v.rows[2];
      const nao = v.rows[3];
      expect(sem.bar).toBeNull();
      expect(sem.valueText).toBe('Sem efeito');
      expect(sem.note).toBe('Não se aplica a altas.');
      expect(nao.bar).toBeNull();
      expect(nao.valueText).toBe('Não avaliado');
      expect(nao.note).toBe('Só dá para medir em meses recentes.');
    });

    it('parcela cortada recebe marcador e nota; itens usam contagem anonimizada', () => {
      const row = buildWaterfallView(insight(), 'revenue').rows[4];
      expect(row.cut).toBeTrue();
      expect(row.note).toContain('Limitada ao total observado.');
      expect(row.expandable).toBeTrue();
      expect(row.items[0].clientsText).toBe('menos de 3 clientes');
    });

    it('barras de queda vão para a esquerda e ficam dentro do eixo 0..100', () => {
      const v = buildWaterfallView(insight(), 'revenue');
      for (const r of v.rows) {
        if (r.bar) {
          expect(r.bar.x).toBeGreaterThanOrEqual(0);
          expect(r.bar.x + r.bar.width).toBeLessThanOrEqual(100.0001);
        }
      }
      expect(v.rows[0].bar?.kind).toBe('queda');
      expect(v.rows[6].bar?.kind).toBe('residuo');
      expect(v.rows[7].bar?.kind).toBe('total');
    });

    it('nota de preço usa variacaoValorPct (contrato 1.1.1)', () => {
      const i = insight({ cascata: [parcel({ tipo: 'PRECO', detalhe: { variacaoValorPct: 6, valorMedioAnterior: 150, valorMedioAtual: 159 } })] });
      expect(buildWaterfallView(i, 'revenue').rows[0].note).toBe('Preço médio praticado subiu 6,0%.');
    });

    it('na alta inverte os rótulos de migração', () => {
      const up = insight({ direcao: 'ALTA' });
      expect(buildWaterfallView(up, 'revenue').rows[3].label).toBe('Clientes vindos do mesmo fornecedor');
    });

    it('em quantity mostra unidades e R$ da receita na linha de baixo', () => {
      const i = insight({ cascata: [parcel({ tipo: 'CANIBALIZACAO_MESMO_FORNECEDOR', valor: -96, valorReceita: -1420, pontosPercentuais: -10 })] });
      const row = buildWaterfallView(i, 'quantity').rows[0];
      expect(row.valueText).toBe('−96 un');
      expect(row.secondaryValueText).toBe('−R$ 1.420,00');
    });
  });

  describe('deriveAiBlock', () => {
    it('SEM_VARIACAO oculta o botão', () => {
      const v = deriveAiBlock(insight({ modoDiagnostico: 'SEM_VARIACAO' }), { ...AI_STATE, podeGerar: false, motivoBloqueio: 'SEM_VARIACAO' }, undefined, 0);
      expect(v.state).toBe('semVariacao');
      expect(v.button).toBeNull();
    });

    it('vazio: botão "Gerar análise com IA" e nunca gera sozinho', () => {
      const v = deriveAiBlock(insight(), AI_STATE, undefined, 0);
      expect(v.state).toBe('vazio');
      expect(v.button?.label).toBe('Gerar análise com IA');
      expect(v.button?.kind).toBe('generate');
      expect(v.button?.disabled).toBeFalse();
    });

    it('vazio mostra o aviso fixo de IA só quando a geração usa IA', () => {
      expect(deriveAiBlock(insight(), AI_STATE, undefined, 0).showFixedNotice).toBeTrue();
      expect(deriveAiBlock(insight(), { ...AI_STATE, geraComIa: false, motivoTemplate: 'IA_DESLIGADA' }, undefined, 0).showFixedNotice).toBeFalse();
    });

    it('geraComIa=false troca para "Gerar resumo automático" com a ajuda do motivo e não desabilita', () => {
      const v = deriveAiBlock(insight(), { ...AI_STATE, geraComIa: false, motivoTemplate: 'GATE_RESIDUO_BAIXO' }, undefined, 0);
      expect(v.button?.label).toBe('Gerar resumo automático');
      expect(v.button?.disabled).toBeFalse();
      expect(v.button?.help).toBe('Os dados internos já explicam quase tudo; a IA não foi necessária.');
    });

    it('gerando: botão desabilitado com "Gerando…"', () => {
      const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'generating' }), 12);
      expect(v.state).toBe('gerando');
      expect(v.button?.label).toBe('Gerando…');
      expect(v.button?.disabled).toBeTrue();
      expect(v.elapsedSeconds).toBe(12);
      expect(v.slow).toBeFalse();
      expect(deriveAiBlock(insight(), AI_STATE, gen({ phase: 'generating' }), 31).slow).toBeTrue();
    });

    it('geracaoEmAndamento no GET também mostra gerando', () => {
      const v = deriveAiBlock(insight(), { ...AI_STATE, podeGerar: false, geracaoEmAndamento: true }, undefined, 0);
      expect(v.state).toBe('gerando');
    });

    it('origem llm/fallback = "Gerada por IA" (sem nome do modelo)', () => {
      for (const origem of ['llm', 'fallback'] as const) {
        const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'success', response: post({ diagnosticoIa: DIAG }, { origem }) }), 0);
        expect(v.state).toBe('sucesso');
        expect(v.originLabel).toBe('Gerada por IA');
        expect(v.showFixedNotice).toBeTrue();
        expect(v.button?.label).toBe('Gerar de novo');
        expect(v.button?.kind).toBe('regenerate');
      }
    });

    it('origem cache = "Análise salva" com aviso de reutilização', () => {
      const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'success', response: post({ diagnosticoIa: DIAG }, { origem: 'cache', reutilizado: true }) }), 0);
      expect(v.state).toBe('salva');
      expect(v.originLabel).toBe('Análise salva');
      expect(v.reusedNotice).toContain('Já havia uma análise salva');
    });

    it('origem template = "Resumo automático (sem IA)", sem aviso fixo, com nota do motivo', () => {
      const v = deriveAiBlock(
        insight(),
        AI_STATE,
        gen({ phase: 'success', response: post({ resumoAutomatico: 'Texto automático.' }, { origem: 'template', motivoTemplate: 'ORCAMENTO_ESGOTADO', modelo: null, geradoEm: null }) }),
        0,
      );
      expect(v.state).toBe('template');
      expect(v.originLabel).toBe('Resumo automático (sem IA)');
      expect(v.showFixedNotice).toBeFalse();
      expect(v.templateText).toBe('Texto automático.');
      expect(v.templateNote).toContain('não está disponível agora');
      expect(JSON.stringify(v)).not.toMatch(/US\$|orçamento|saldo|crédito|token/i);
    });

    it('salvo no GET: "Análise salva", "Atualizar" quando vencido, desabilita se podeForcar=false', () => {
      const salvo = insight({ diagnosticoIa: DIAG });
      const ia = { ...AI_STATE, diagnosticoSalvo: true, diagnosticoSalvoEm: DIAG.geradoEm };
      expect(deriveAiBlock(salvo, ia, undefined, 0).button?.label).toBe('Gerar de novo');
      expect(deriveAiBlock(salvo, { ...ia, diagnosticoVencido: true }, undefined, 0).button?.label).toBe('Atualizar');
      const blocked = deriveAiBlock(salvo, { ...ia, podeForcar: false }, undefined, 0);
      expect(blocked.button?.disabled).toBeTrue();
      expect(blocked.button?.help).toBe('Já existe uma análise salva para esta janela.');
      expect(blocked.state).toBe('salva');
    });

    it('confirmando: mantém o salvo visível e expõe a pergunta', () => {
      const v = deriveAiBlock(insight({ diagnosticoIa: DIAG }), { ...AI_STATE, diagnosticoSalvo: true }, gen({ confirming: true }), 0);
      expect(v.state).toBe('confirmando');
      expect(v.diagnosis).toBe(DIAG);
      expect(v.confirmText).toBe('Gerar de novo substitui a análise salva desta janela. Continuar?');
      expect(v.confirmText).not.toMatch(/crédito/i);
    });

    it('429 LIMITE_DE_PEDIDOS: aviso e botão reabilita após Retry-After', () => {
      const err: InsightApiError = { kind: 'RATE_LIMIT', code: 'TIA-004', motivo: 'LIMITE_DE_PEDIDOS', retryAfterSeconds: 30, status: 429 };
      const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'error', error: err, failedAtSeconds: 0 }), 10);
      expect(v.state).toBe('limite');
      expect(v.button?.disabled).toBeTrue();
      expect(v.retryRemaining).toBe(20);
      expect(deriveAiBlock(insight(), AI_STATE, gen({ phase: 'error', error: err, failedAtSeconds: 0 }), 31).button?.disabled).toBeFalse();
    });

    it('429 LIMITE_DIARIO desabilita sem contador', () => {
      const err: InsightApiError = { kind: 'RATE_LIMIT', code: 'TIA-004', motivo: 'LIMITE_DIARIO', retryAfterSeconds: 3600, status: 429 };
      const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'error', error: err, failedAtSeconds: 0 }), 99999);
      expect(v.button?.disabled).toBeTrue();
      expect(v.retryRemaining).toBeNull();
      expect(v.message).toContain('limite de análises por hoje');
    });

    it('erro genérico: caixa com "Tentar de novo" (sem force)', () => {
      const err: InsightApiError = { kind: 'NETWORK', code: null, motivo: null, retryAfterSeconds: null, status: 0 };
      const v = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'error', error: err }), 0);
      expect(v.state).toBe('erro');
      expect(v.message).toBe('Não foi possível gerar a análise agora. A parte numérica está disponível.');
      expect(v.showRetry).toBeTrue();
    });

    it('401 mostra a mensagem de sessão', () => {
      const err: InsightApiError = { kind: 'UNAUTHORIZED', code: null, motivo: null, retryAfterSeconds: null, status: 401 };
      expect(deriveAiBlock(insight(), AI_STATE, gen({ phase: 'error', error: err }), 0).message).toContain('sessão');
    });

    it('aviso IA_FALHOU em template e SEM_BUSCA_EXTERNA em llm', () => {
      const t = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'success', response: post({ resumoAutomatico: 'x' }, { origem: 'template', avisos: [{ codigo: 'IA_FALHOU', mensagem: 'm' }] }) }), 0);
      expect(t.notices).toContain('Não foi possível gerar a análise com IA agora; mostramos o resumo automático.');
      const l = deriveAiBlock(insight(), AI_STATE, gen({ phase: 'success', response: post({ diagnosticoIa: DIAG }, { origem: 'fallback', avisos: [{ codigo: 'SEM_BUSCA_EXTERNA', mensagem: 'm' }] }) }), 0);
      expect(l.notices).toContain('Esta análise não consultou notícias externas; os fatores abaixo vêm só dos dados internos.');
    });

    it('QUALITATIVO acrescenta a linha de base pequena', () => {
      const v = deriveAiBlock(insight({ modoDiagnostico: 'QUALITATIVO' }), AI_STATE, undefined, 0);
      expect(v.qualitativeNote).toBe('Com base pequena, a IA aponta sinais e notícias, sem estimar valores.');
    });
  });

  describe('resumo e grupo afim', () => {
    it('resumo: número herói com sinal, glifo e frase de participação interpolada da API', () => {
      const v = buildSummaryView(insight(), 'revenue', 3);
      expect(v.heroText).toBe('−35,0%');
      expect(v.heroGlyph).toBe('▼');
      expect(v.spanText).toBe('em 3 meses');
      expect(v.fromToText).toBe('de R$ 40.000,00 para R$ 26.000,00');
      expect(v.deltaText).toBe('(−R$ 14.000,00)');
      expect(v.sentence).toContain('a fatia deste produto no grupo caiu de 31,0% para 25,7% (−5,3 p.p.)');
    });

    it('frase usa "ficaram estáveis" abaixo do limiar vindo de meta.parametros', () => {
      const i = insight({ diagnosticoMercado: { ...insight().diagnosticoMercado, variacaoMercadoPct: 0.5 } });
      expect(buildSummaryView(i, 'revenue', 3, 2).sentence).toContain('ficaram estáveis');
    });

    it('nota de base parcial', () => {
      const i = insight();
      i.periodo.baseParcial = true;
      expect(buildSummaryView(i, 'revenue', 1).baseParcialNote).toContain('mesma quantidade de dias');
    });

    it('aiStatusLabel segue o estado do bloco', () => {
      expect(aiStatusLabel(deriveAiBlock(insight(), AI_STATE, undefined, 0))).toBe('Análise com IA: ainda não gerada');
      expect(aiStatusLabel(null)).toBe('Análise com IA: indisponível');
    });

    it('grupo afim: título, contagem por fornecedor e ganho de clientes anonimizado', () => {
      const i = insight({
        grupoAfim: {
          status: 'AVALIADO',
          afins: [
            { sku: 3301, descricao: 'A', fornecedor: 'B', sameSupplier: false, affinityScore: 0.804, categoriaGaleria: null, valorVendaAtual: 1, celula: CELL, ganhouClientesDoProduto: true, lancamento: false },
            { sku: 3305, descricao: 'C', fornecedor: 'ALFA', sameSupplier: true, affinityScore: 0.5, categoriaGaleria: null, valorVendaAtual: 1, celula: CELL, ganhouClientesDoProduto: false, lancamento: false },
          ],
        },
      });
      const v = buildAffineGroupView(i);
      expect(v.title).toBe('2 produtos semelhantes · 1 ganhou clientes deste');
      expect(v.sameSupplierCount).toBe(1);
      expect(v.rows[0].similarityText).toBe('80%');
      expect(v.rows[0].gainedText).toContain('menos de 3 clientes');
      expect(v.rows[1].gainedText).toBe('Não');
    });
  });
});
