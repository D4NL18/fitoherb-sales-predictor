import { InfoHelpContent } from '../components/info-help/info-help.component';
import { ProductElasticityMetrics } from '../models/elasticity.models';
import { formatPriceReactionHint, formatPriceReactionRangeHint } from './elasticity-view';
import { formatDecimal, formatPercent } from './pt-br-format';

/**
 * Copy didática dos guias contextuais `<app-info-help>` da Calculadora Unificada v3.
 * Textos 100% puros (sem HTML) para renderização segura via interpolação Angular.
 */
export const ELASTICITY_HELP_COPY = {
  elasticityOverview: {
    title: 'Como usar a Calculadora de Preço, Margem e Estoque',
    whatIs:
      'Esta ferramenta projeta como uma mudança de preço altera a margem unitária, o lucro bruto e a duração do estoque em um ciclo de 60 dias.',
    howToAnalyze:
      '1. Busque o produto por código ou nome. 2. Confira o custo unitário do catálogo (ou informe um custo manual para simular). 3. Ajuste o percentual de preço e compare os 4 cartões de decisão.',
    insight:
      'Nem todo aumento reduz o ganho financeiro: se o ganho por unidade superar a perda de volume, o lucro bruto dos 60 dias sobe e o estoque dura mais.',
  },
  classificationBadge: {
    title: 'Classificação de sensibilidade',
    whatIs:
      'Resume se os compradores reagem muito ou pouco quando o preço deste produto muda.',
    howToAnalyze:
      'Muito sensível a preço (abaixo de -1,00): o volume cai em proporção maior que o aumento de preço. Pouco sensível a preço (entre -1,00 e 0): os clientes continuam comprando quase a mesma quantidade após pequenos reajustes.',
    insight:
      'Produtos pouco sensíveis têm espaço para recompor margem; nos muito sensíveis, prefira ajustes graduais ou ações para girar estoque.',
    technicalNote:
      'Ponto de corte econômico em |Beta| = 1,00: valores menores que -1,00 são elásticos e valores entre -1,00 e 0 são inelásticos.',
  },
  technicalSummary: {
    title: 'Detalhes estatísticos do produto',
    whatIs:
      'Reúne o coeficiente de sensibilidade (Beta), a faixa provável de reação (IC 95%), o erro padrão, a aderência (R²) e a quantidade de meses válidos usados no cálculo.',
    howToAnalyze:
      'Beta negativo indica que aumentos reduzem o volume vendido; quanto maior o R² e mais meses válidos, maior a confiança na estimativa histórica.',
    insight:
      'Use o intervalo de confiança (IC 95%) para conferir se a decisão continua saudável mesmo no cenário mais conservador.',
    technicalNote:
      'Regressão linear log-log ponderada pelo tempo sobre vendas líquidas de devoluções, com fallback defensivo (-1,20) quando há poucos dados ou preço constante.',
  },
  unitCostInput: {
    title: 'Custo unitário (R$)',
    whatIs:
      'É o custo de reposição usado para calcular a margem unitária e o lucro bruto total da simulação.',
    howToAnalyze:
      'Por padrão, vem do último custo registrado no ERP ([Pc.Ultimo Custo]). Quando está zerado ou ausente no catálogo, estimamos 60% do preço atual. Você pode digitar outro valor para simular renegociação de compra ou reajuste de fornecedor.',
    insight:
      'Teste aqui o custo de uma nova tabela do fornecedor para descobrir qual preço de venda mantém sua margem saudável antes de comprar.',
    technicalNote:
      'Origem exibida no selo ao lado: Catálogo ERP, Estimado (60% do preço) ou Editado manualmente (com botão para restaurar o valor do catálogo).',
  },
  appliedElasticity: {
    title: 'Sensibilidade aplicada',
    whatIs:
      'É o índice exato (Beta) utilizado para projetar a variação de unidades vendidas neste produto.',
    howToAnalyze:
      'Cada 1% de mudança no preço multiplica esse índice para estimar a mudança percentual no volume do ciclo de 60 dias.',
    insight:
      'Valores mais negativos pedem cautela em aumentos bruscos e favorecem promoções quando há excesso de estoque.',
  },
  unitMarginCard: {
    title: 'Margem Unitária (R$/un. e p.p.)',
    whatIs:
      'Mostra quanto dinheiro sobra em cada unidade vendida após pagar o custo unitário, tanto em reais (R$/un.) quanto em percentual (%) sobre o preço.',
    howToAnalyze:
      'Compare o valor atual com o novo cenário. A diferença percentual aparece em pontos percentuais (p.p.), que medem a variação direta entre duas taxas (ex.: de 40,0% para 45,0% = +5,0 p.p.).',
    insight:
      'Fique atento ao alerta se a margem unitária ficar igual ou menor que zero: nesse ponto o desconto está vendendo abaixo ou no limite do custo.',
    technicalNote:
      'Margem unitária = Preço - Custo; Margem (%) = (Preço - Custo) / Preço × 100; Variação (p.p.) = Margem nova (%) - Margem atual (%).',
  },
  projectedMarginCard: {
    title: 'Lucro Bruto Estimado (60 dias)',
    whatIs:
      'Calcula a Margem de Contribuição total no ciclo de 60 dias: quanto sobra no caixa após pagar o custo das unidades previstas.',
    howToAnalyze:
      'Compare o Lucro Bruto Projetado com o cenário de Hoje (0%). O delta em reais e percentual mostra se a mudança de preço aumenta ou reduz o ganho total.',
    insight:
      'Este é o principal indicador financeiro da decisão: priorize cenários em que o lucro bruto em reais seja maior sem comprometer a saúde do estoque.',
    technicalNote:
      'Lucro bruto (60d) = (Preço projetado - Custo unitário) × Volume projetado (60d).',
  },
  projectedVolumeRevenueCard: {
    title: 'Unidades Vendidas & Faturamento (60 dias)',
    whatIs:
      'Projeta quantas unidades devem sair e qual será a receita bruta no ciclo de 60 dias, comparando com as vendas líquidas dos últimos 60 dias.',
    howToAnalyze:
      'Observe a quantidade prevista, a variação em unidades (un.) e o ritmo diário (un./dia), além do impacto no faturamento bruto (R$).',
    insight:
      'Atenção: faturar mais com desconto grande pode encolher o lucro bruto total se a margem unitária cair demais.',
    technicalNote:
      'Baseline = vendas líquidas de devoluções nos últimos 60 dias. Volume projetado = Volume 60d × max(0, 1 + Beta × ΔPreço% / 100).',
  },
  stockCoverage60d: {
    title: 'Cobertura de Estoque (Meta: 60 dias)',
    whatIs:
      'Estima por quantos dias o estoque atual dura no ritmo de vendas de Hoje (0%) versus o ritmo Após a mudança de preço, comparando com a meta de 60 dias.',
    howToAnalyze:
      'Dividimos o estoque atual pela venda diária (Vendas 60d ÷ 60). Coberturas até 15 dias sinalizam giro muito rápido (risco de ruptura); entre 16 e 60 dias ficam dentro da meta; acima de 60 dias indicam excesso de estoque.',
    insight:
      'Se o produto está acima de 60 dias (excesso), um desconto controlado pode acelerar o giro até a faixa saudável; se está com giro rápido (<= 15d), um aumento de preço protege o estoque e amplia o lucro.',
    technicalNote:
      'Cobertura (dias) = Estoque atual ÷ (Volume do ciclo 60d ÷ 60). Sem vendas líquidas nos últimos 60 dias, a cobertura permanece indisponível (—).',
  },
} satisfies Record<string, InfoHelpContent>;

/** Monta o guia "Ver detalhes estatísticos" interpolando os números reais do produto (sem HTML). */
export function buildTechnicalSummaryHelp(elasticity: ProductElasticityMetrics): InfoHelpContent {
  const betaStr = formatDecimal(elasticity.coefficient, 2);
  const icLow = formatDecimal(elasticity.confidenceInterval[0], 2);
  const icHigh = formatDecimal(elasticity.confidenceInterval[1], 2);
  const seStr = formatDecimal(elasticity.standardError, 2);
  const r2Str = formatPercent(elasticity.rSquared, 1);
  const obsStr = formatDecimal(elasticity.observationsCount);

  return {
    title: ELASTICITY_HELP_COPY.technicalSummary.title,
    whatIs: `Sensibilidade estimada (Beta): ${betaStr}. ${formatPriceReactionHint(elasticity.coefficient)}.`,
    howToAnalyze: `Faixa provável (IC 95%): de ${icLow} até ${icHigh} (${formatPriceReactionRangeHint(elasticity.confidenceInterval)}). Aderência (R²): ${r2Str} em ${obsStr} meses válidos líquidos de devoluções.`,
    insight: elasticity.insightMessage,
    technicalNote: `Beta = ${betaStr} · IC 95% = [${icLow}; ${icHigh}] · Erro padrão = ±${seStr} · R² = ${r2Str} · Meses válidos = ${obsStr}.`,
  };
}
