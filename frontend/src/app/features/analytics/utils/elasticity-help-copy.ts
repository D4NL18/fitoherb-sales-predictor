import { InfoHelpContent } from '../components/info-help/info-help.component';

/**
 * Copy didática dos guias contextuais `<app-info-help>` da página Elasticidade-Preço (Design Plan v2).
 * Textos 100% puros (sem HTML) para renderização segura via interpolação Angular.
 */
export const ELASTICITY_HELP_COPY = {
  elasticityOverview: {
    title: 'Como usar o Simulador de Preço',
    whatIs:
      'Esta tela mede o quanto os compradores aumentam ou reduzem os pedidos de um produto quando o preço muda, com base no histórico de vendas.',
    howToAnalyze:
      '1. Confira o diagnóstico do produto no topo. 2. Mova a barra do simulador para testar aumentos ou descontos e observe o Lucro bruto estimado. 3. Compare clientes na tabela para decidir onde reajustar primeiro.',
    insight:
      'Nem todo aumento de preço faz você vender menos lucro: se a queda de volume for menor do que o ganho por unidade, o lucro total sobe.',
  },
  classificationBadge: {
    title: 'Classificação de sensibilidade',
    whatIs:
      'Resume se os compradores reagem muito ou pouco quando o preço deste produto muda.',
    howToAnalyze:
      'Muito sensível a preço (abaixo de -1,00): o volume cai em proporção maior que o aumento de preço. Pouco sensível a preço (entre -1,00 e 0): os clientes continuam comprando quase a mesma quantidade após pequenos reajustes.',
    insight:
      'Produtos pouco sensíveis têm espaço para recompor margem; nos muito sensíveis, prefira ajustes graduais ou ações de desconto por volume.',
    technicalNote:
      'Ponto de corte econômico em |Beta| = 1,00: valores menores que -1,00 são elásticos e valores entre -1,00 e 0 são inelásticos.',
  },
  confidenceBadge: {
    title: 'Confiança da previsão',
    whatIs:
      'Indica o quanto o histórico passado do produto dá segurança para o cálculo da reação ao preço.',
    howToAnalyze:
      'Confiança alta significa muitos meses com vendas regulares e boa explicação pelo preço. Confiança média pede validação comercial. Confiança baixa (usar com cautela) indica poucos dados ou variações externas fora do preço.',
    insight:
      'Quanto maior a confiança, mais firme pode ser o uso da simulação na negociação; em confiança baixa, trate os números apenas como referência inicial.',
    technicalNote:
      'Combinamos a aderência R², o erro padrão do coeficiente e a quantidade de meses válidos líquidos de devoluções.',
  },
  priceSensitivity: {
    title: 'Sensibilidade ao preço',
    whatIs:
      'Mostra quantos porcento o volume vendido costuma mudar para cada 1% de alteração no preço.',
    howToAnalyze:
      'O número costuma ser negativo porque, quando o preço sobe, a quantidade vendida cai. Ex.: se for -1,50, um aumento de +10% no preço tende a reduzir as unidades vendidas em cerca de 15,0%.',
    insight:
      'Olhe para a tradução prática em +10% logo abaixo do número principal para decidir se a perda de unidades compensa o ganho de margem.',
    technicalNote:
      'Coeficiente Beta estimado por regressão linear log-log ponderada pelo tempo (meses mais recentes têm peso maior).',
  },
  confidenceInterval: {
    title: 'Faixa provável de reação',
    whatIs:
      'Mostra o intervalo realista onde a reação verdadeira dos compradores costuma ficar, considerando as oscilações normais das vendas.',
    howToAnalyze:
      'Faixas estreitas indicam comportamento previsível mês a mês. Faixas muito abertas mostram que o volume variou bastante mesmo em preços parecidos.',
    insight:
      'Antes de aprovar um reajuste maior, avalie se a decisão continua lucrativa mesmo no cenário mais conservador da faixa.',
    technicalNote:
      'Intervalo de Confiança de 95% (IC 95%) calculado a partir do Beta estimado e do erro padrão amostral.',
  },
  rSquaredAndHistory: {
    title: 'Qualidade do cálculo e histórico',
    whatIs:
      'Mede o percentual das mudanças de venda que realmente foi explicado pelo preço, junto ao total de meses válidos analisados.',
    howToAnalyze:
      'Valores mais altos (ex.: acima de 50%) mostram forte ligação entre preço e quantidade. Valores baixos indicam que sazonalidade, falta de estoque ou campanhas pesaram mais que o preço.',
    insight:
      'Se o percentual for baixo, combine esta simulação com o calendário comercial e o giro de estoque antes de mexer na tabela de preços.',
    technicalNote:
      'R² da regressão log-log sobre meses fechados com quantidade líquida positiva (vendas abatidas das devoluções).',
  },
  unitPriceCostMargin: {
    title: 'Preço, Custo e Lucro Unitário',
    whatIs:
      'Reúne o preço atual de venda, o custo de reposição do catálogo, quanto sobra de lucro em cada unidade vendida e o estoque disponível.',
    howToAnalyze:
      'Confira o Lucro por unidade em reais e em percentual sobre o preço atual antes de testar descontos ou aumentos no simulador.',
    insight:
      'Produtos com lucro unitário apertado exigem cuidado redobrado com descontos; já itens com margem folgada suportam promoções para girar estoque.',
    technicalNote:
      'Lucro unitário = Preço atual - Custo; Margem unitária (%) = (Preço atual - Custo) / Preço atual × 100.',
  },
  priceSimulator: {
    title: 'Simulador de Reajuste de Preço',
    whatIs:
      'Ferramenta interativa para testar cenários de aumento ou desconto entre -50% e +100% antes de alterar a tabela real.',
    howToAnalyze:
      'Use os atalhos rápidos (-10% a +20%) ou arraste a barra. Se você selecionar um cliente na tabela abaixo, a simulação passa a refletir o perfil daquele comprador.',
    insight:
      'Compare sempre os três cartões juntos: quantidade, faturamento e principalmente o Lucro bruto estimado.',
  },
  productBaselineElasticity: {
    title: 'Média geral do produto',
    whatIs:
      'É a reação média observada somando todos os compradores deste produto no histórico avaliado.',
    howToAnalyze:
      'Funciona como referência estável quando o cliente selecionado ainda tem poucos pedidos no produto.',
    insight:
      'Compare a reação própria do cliente com esta média para saber se ele aceita preço mais alto ou exige mais negociação que a carteira.',
    technicalNote:
      'Coeficiente Beta agregado do SKU (prior hierárquica utilizada no modelo de suavização bayesiana).',
  },
  customerEmpiricalElasticity: {
    title: 'Reação própria do cliente',
    whatIs:
      'Mede como apenas este cliente específico reagiu às mudanças de preço que encontrou ao longo das próprias compras.',
    howToAnalyze:
      'Se o cliente tiver poucos pedidos, esse número isolado pode parecer exagerado ou distorcido por compras esporádicas.',
    insight:
      'Observe este dado junto com o Peso do histórico: quanto mais pedidos o cliente tiver, mais fiel à realidade será a reação própria dele.',
    technicalNote:
      'Elasticidade empírica individual estimada sobre os meses de compra líquida do cliente no SKU.',
  },
  shrinkageElasticity: {
    title: 'Sensibilidade usada na simulação',
    whatIs:
      'É o número equilibrado que o simulador usa para projetar as vendas deste cliente, combinando o histórico próprio dele com a média geral do produto.',
    howToAnalyze:
      'Com poucos pedidos, ela fica próxima da média do produto para evitar chutes extremos; conforme o cliente compra mais vezes, o cálculo dá mais peso ao comportamento dele.',
    insight:
      'Garante previsões estáveis mesmo para compradores recentes, sem perder a personalização dos clientes recorrentes.',
    technicalNote:
      'Suavização Bayesiana (Shrinkage): Beta_ajustado = w × Beta_cliente + (1 - w) × Beta_produto, onde w = n / (n + 10).',
  },
  shrinkageWeight: {
    title: 'Peso do histórico do cliente',
    whatIs:
      'Mostra em percentual quanto o histórico próprio de pedidos deste cliente pesa na sensibilidade usada para ele.',
    howToAnalyze:
      'Ex.: com n = 3 pedidos o peso é cerca de 23%; com n = 10 pedidos chega a 50%; com n = 30 pedidos sobe para 75%.',
    insight:
      'Clientes com peso alto têm padrão próprio bem definido e merecem estratégia de preço personalizada na tabela.',
    technicalNote:
      'Fórmula de ponderação w = n / (n + 10), onde n é o total de pedidos válidos do cliente para o produto.',
  },
  appliedElasticity: {
    title: 'Sensibilidade aplicada',
    whatIs:
      'É o índice exato utilizado neste cálculo: a média do produto na visão geral ou a média ajustada do cliente quando um comprador está selecionado.',
    howToAnalyze:
      'Confira este número ao lado do preço projetado para ter certeza de qual referência está dirigindo os cartões de resultado.',
    insight:
      'Ao trocar entre visão geral e clientes específicos, note como esse índice altera o volume e o lucro previstos para o mesmo percentual de reajuste.',
  },
  projectedVolume: {
    title: 'Quantidade prevista',
    whatIs:
      'Estima quantas unidades serão vendidas no cenário simulado, comparando com a média mensal atual.',
    howToAnalyze:
      'Aumentos de preço tendem a reduzir a quantidade prevista; descontos tendem a aumentá-la proporcionalmente à sensibilidade do produto ou cliente.',
    insight:
      'Verifique se o estoque atual suporta um eventual salto de unidades quando simular descontos mais agressivos.',
    technicalNote:
      'Projeção de volume multiplicativo: Q_proj = Q_atual × (1 + ΔPreço)^Elasticidade_aplicada.',
  },
  projectedRevenue: {
    title: 'Faturamento previsto',
    whatIs:
      'É a receita bruta estimada (Preço projetado multiplicado pela Quantidade prevista).',
    howToAnalyze:
      'Observe se o faturamento sobe ou cai em reais e em percentual em relação ao cenário atual.',
    insight:
      'Atenção: faturar mais nem sempre significa lucrar mais. Um desconto pode elevar o faturamento e reduzir o lucro líquido da operação.',
    technicalNote:
      'Receita bruta projetada = Preço projetado × Volume projetado.',
  },
  projectedMargin: {
    title: 'Lucro bruto estimado',
    whatIs:
      'Calcula quanto sobra após pagar o custo do produto no volume previsto (Margem de Contribuição total).',
    howToAnalyze:
      'Este é o cartão principal de decisão: busque cenários onde o ganho em reais seja positivo e alinhado ao posicionamento comercial.',
    insight:
      'Muitas vezes um preço levemente maior com menos unidades vendidas gera mais lucro total no caixa e poupa estoque.',
    technicalNote:
      'Margem de Contribuição = (Preço projetado - Custo unitário) × Volume projetado.',
  },
  customerLookup: {
    title: 'Buscar cliente pelo código',
    whatIs:
      'Campo de duplo uso: filtra instantaneamente os clientes carregados na página atual ou consulta um código exato em toda a base.',
    howToAnalyze:
      'Digite parte do código para filtrar na tabela abaixo. Para buscar um comprador que está em outra página, digite o código completo e clique em "Consultar cliente".',
    insight:
      'Use a consulta direta antes de uma ligação ou visita comercial para abrir na hora o perfil de preço daquele cliente.',
  },
  tableShrinkageWeight: {
    title: 'Peso histórico',
    whatIs:
      'Indica quanto dos pedidos do próprio cliente influencia a sensibilidade calculada para ele nesta tabela.',
    howToAnalyze:
      'Percentuais baixos (ex.: abaixo de 30%) significam histórico curto, puxando o cálculo para a média do produto; percentuais altos mostram histórico robusto.',
    insight:
      'Dê mais prioridade às diferenças de sensibilidade dos clientes com peso histórico maior.',
    technicalNote:
      'Peso de suavização w = n / (n + 10) conforme o número de pedidos válidos do comprador.',
  },
  tableEmpiricalElasticity: {
    title: 'Reação própria',
    whatIs:
      'Mostra a reação observada apenas nos pedidos deste comprador antes do ajuste de estabilidade.',
    howToAnalyze:
      'Use como leitura complementar: em clientes com poucos pedidos, esse valor pode oscilar bastante.',
    insight:
      'Quando a reação própria e a sensibilidade usada estiverem próximas, o comportamento do comprador é consistente ao longo do tempo.',
    technicalNote:
      'Elasticidade empírica individual antes da aplicação do Shrinkage Bayesiano.',
  },
  tableAdjustedElasticity: {
    title: 'Sensibilidade usada',
    whatIs:
      'É o índice final e estabilizado que entra na simulação quando você clica em "Simular" na linha do cliente.',
    howToAnalyze:
      'Clique no cabeçalho para ordenar do mais sensível ao menos sensível (ou o inverso) e identificar oportunidades por perfil.',
    insight:
      'Clientes com valor entre -1,00 e 0 respondem bem a reajustes leves; valores muito negativos pedem defesa de preço ou contrapartida de volume.',
    technicalNote:
      'Estimativa ajustada via Shrinkage Bayesiano combinando a reação própria do cliente e o Beta do produto.',
  },
  tableProfile: {
    title: 'Perfil de sensibilidade',
    whatIs:
      'Classifica rapidamente o comprador em "Sensível" ou "Pouco sensível" ao preço para facilitar a leitura da carteira.',
    howToAnalyze:
      'Cruze o perfil com as colunas de Pedidos e Volume (un.) para priorizar os compradores mais relevantes do produto.',
    insight:
      'Comece protegendo margem nos clientes "Pouco sensível" de alto volume e reserve condições promocionais apenas para os "Sensível".',
  },
} satisfies Record<string, InfoHelpContent>;
