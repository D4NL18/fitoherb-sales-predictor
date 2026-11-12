# Regras de Negócio: Analytics Comercial — F6 Canibalização e Substituição de Produtos

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-canibalizacao.md`  
> **Responsável:** Analista (`business-rules-expert` / `analyst.md`)  
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`, `tasks/ia-analytics-vendas.md` (§2, §5, §8.1)

| Campo | Valor |
| :--- | :--- |
| **Feature** | Canibalização e Substituição de Produtos (Impacto de Promoções, Preços e Lançamentos) |
| **Módulo** | `analytics` (`src/modules/analytics/domain/cannibalization.py`) |
| **Branch** | `feature/analytics-canibalizacao` |
| **Faixa de Regras** | `P-128` a `P-138` |
| **Prefixo de Erro** | `CAN-XXX` (`CAN-001` a `CAN-005`) |
| **Origem** | Plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§5) e especificações comerciais Fitoherb |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado — Submetido ao Checkpoint da Etapa 2 |

---

## 1. Contexto e Objetivo

- **User Story Relacionada:** US-F6 — *Como gestor comercial ou comprador da Fitoherb, quero saber o impacto real de ações comerciais (descontos promocionais, reajustes de preço ou lançamentos de novos produtos), descobrindo quais outros produtos ganharam ou perderam vendas e se o efeito líquido em volume, receita e margem compensou a ação, para evitar promoções ilusórias que apenas canibalizam itens mais rentáveis.*
- **Objetivo da Feature:**
  1. **Identificar Substitutos Reais:** Encontrar automaticamente produtos concorrentes diretos no catálogo utilizando mesmo `Tipo` e similaridade de clientes compradores (Coeficiente de Jaccard).
  2. **Isolar o Efeito Causal (Diferença em Diferenças):** Medir a variação nas vendas dos substitutos comparando o período pré e pós evento contra um grupo de controle de produtos do mesmo `Tipo` não afetados, neutralizando a sazonalidade e tendências de mercado sem depender da Fase F1.
  3. **Classificar o Efeito:** Categorizar os produtos afetados em `CANIBALIZACAO`, `COMPLEMENTO` ou `SEM_EFEITO` com rigor estatístico (correção de Benjamini-Hochberg para múltiplos testes).
  4. **Calcular o Efeito Líquido:** Apurar o balanço consolidado de $\Delta$ unidades, $\Delta$ receita líquida e $\Delta$ margem em reais (R$), explicitando se a ação comercial destruiu ou agregou valor.
  5. **Planejar Integração com F5:** Prever interface de consumo do modelo de elasticidade de F5 para decompor a parcela explicada por elasticidade cruzada de preço.
- **Atores Envolvidos:** Gestor Comercial / Diretor de Vendas (avaliação de campanhas), Comprador / Precificador (simulação e análise pós-evento), Sistema ERP (SQL Server em modo somente leitura).
- **Fora do escopo:** Alteração automática de preços no ERP, geração automática de campanhas, alteração de regras de outros módulos, processamento de filiais (D3).

---

## 2. Tabela de Constantes e Parâmetros Numéricos

> [!IMPORTANT]
> Os parâmetros numéricos abaixo DEVEM existir como constantes declaradas no topo de `src/modules/analytics/domain/cannibalization.py`, sem números mágicos espalhados pelo código.

| Constante | Valor Padrão | Regra | Significado / Justificativa |
| :--- | :--- | :--- | :--- |
| `MIN_JACCARD_SIMILARITY` | `0.15` | P-128 | Coeficiente mínimo de compradores em comum para considerar substituto potencial |
| `MIN_COMMON_BUYERS` | `5` | P-128 | Número mínimo absoluto de clientes compradores compartilhados nos últimos 12 meses |
| `MAX_CANDIDATE_SUBSTITUTES` | `20` | P-128 | Limite superior de candidatos a substitutos submetidos ao teste DiD para evitar sobrecarga |
| `MIN_PRICE_CHANGE_PCT` | `0.05` (5%) | P-129 | Variação mínima relativa no preço médio de venda líquido para caracterizar evento de preço |
| `LAUNCH_CUTOFF_DATE` | `'2025-04-01'` | P-129 | Data mínima da 1ª venda para caracterizar um lançamento real no histórico (evita falso lançamento) |
| `MIN_LAUNCH_MONTHS` | `3` | P-129 | Meses mínimos de histórico pós-lançamento necessários para avaliar canibalização de lançamento |
| `DEFAULT_ANALYSIS_WINDOW_WEEKS` | `4` | P-130 | Janela simétrica pré/pós evento padrão (4 semanas antes vs 4 semanas depois) |
| `MIN_ANALYSIS_WINDOW_WEEKS` | `2` | P-130 | Limite mínimo configurável da janela de análise |
| `MAX_ANALYSIS_WINDOW_WEEKS` | `12` | P-130 | Limite máximo configurável da janela de análise |
| `MIN_CONTROL_GROUP_SIZE` | `5` | P-131 | Número mínimo de produtos no grupo de controle para cálculo da trajetória contrafactual |
| `CONTROL_MAX_PRICE_VARIATION` | `0.03` (3%) | P-131 | Variação máxima de preço permitida no período para um produto pertencer ao grupo de controle |
| `FDR_ALPHA` | `0.05` | P-133 | Taxa de Falsas Descobertas (FDR Benjamini-Hochberg) para controle de significância |
| `MIN_EFFECT_VOLUME_UNITS` | `5` | P-133 | Magnitude mínima absoluta de variação em unidades para ser classificado como efeito relevante |
| `COST_FALLBACK_RATIO` | `0.60` | P-135 | Margem padrão de custo (60% do preço de venda) caso `Pc.Ultimo Custo` seja nulo/inválido |
| `CACHE_TTL_HOURS` | `6` | P-137 | Tempo de vida do cache em memória com bloqueio concorrente |

---

## 3. Catálogo de Regras de Negócio (P-128 a P-138)

### `P-128`: Identificação de Produtos Candidatos a Substitutos

- **Declaração Mandatória:** O sistema DEVE mapear os produtos candidatos a substitutos do SKU alvo combinando pertencimento à mesma categoria (`Tipo`) e similaridade comportamental de compradores pelo índice de Jaccard.
- **Sub-regras:**
  - **P-128.1 (Elegibilidade Categorial):** Todo produto ativo no catálogo que compartilhe o mesmo atributo `Tipo` do SKU alvo e que não seja o próprio SKU alvo (`Codigo != Target_Codigo`) é um candidato primário.
  - **P-128.2 (Similaridade de Compradores - Jaccard):** Para cada candidato, calcula-se o Coeficiente de Jaccard sobre o conjunto de clientes (`Cod Cliente`) que compraram o produto nos últimos 365 dias:
    $$Jaccard(A, B) = \frac{|Clientes(A) \cap Clientes(B)|}{|Clientes(A) \cup Clientes(B)|}$$
  - **P-128.3 (Critério de Seleção):** Um produto é considerado candidato a substituto se:
    $$(Tipo_B = Tipo_A \text{ AND } Jaccard(A, B) \ge MIN\_JACCARD\_SIMILARITY) \text{ OU } (|Clientes(A) \cap Clientes(B)| \ge MIN\_COMMON\_BUYERS)$$
  - **P-128.4 (Ranqueamento e Poda):** Os candidatos são ordenados decrescentemente por $Jaccard(A, B)$ e limitados aos `MAX_CANDIDATE_SUBSTITUTES` (20 primeiros) para garantir tempo de resposta previsível e proteção contra sobrecarga de CPU no Cloud Run.
  - **P-128.5 (Isolamento de PII):** O conjunto `Clientes(A)` é manipulado exclusivamente como conjunto de inteiros/strings em memória volátil para contagem de interseção/união; nenhum identificador de cliente é retornado pela API ou persistido.
- **Condições de Ativação:** Requisição de análise de canibalização ou consulta direta de substitutos (`GET /analytics/substitution/{sku}`).
- **Resultado Esperado:** Lista de SKUs substitutos elegíveis com nome, tipo, Jaccard e compradores em comum.
- **Exceção / Mensagem de Erro:** Caso o SKU alvo não seja encontrado, disparar erro `CAN-001` (HTTP 404). Se não houver candidatos a substitutos suficientes, retornar lista vazia de substitutos com metadados informativos, sem interromper com 500.

---

### `P-129`: Detecção e Parametrização de Eventos Críticos

- **Declaração Mandatória:** O sistema DEVE permitir analisar a canibalização disparada por três tipos distintos de eventos comerciais associados a um SKU alvo: Promoção (`promo`), Alteração de Preço (`price`) ou Lançamento de Produto (`launch`).
- **Sub-regras:**
  - **P-129.1 (Evento Promoção `promo`):** Identificado através do agregado `promo_calendar` (`Cod Promocao` em `Externo01.Vendas`). A data de início do evento ($T_0$) corresponde ao primeiro dia da campanha promocional do SKU.
  - **P-129.2 (Evento Alteração de Preço `price`):** Identificado quando o preço médio de venda líquido semanal do SKU alvo sofre variação percentual relativa maior ou igual a `MIN_PRICE_CHANGE_PCT` (5%):
    $$|\Delta P\%| = \frac{|P_{pos} - P_{pre}|}{P_{pre}} \ge MIN\_PRICE\_CHANGE\_PCT$$
    O evento registra se a mudança foi de redução de preço (`PRICE_DROP`, típica de indução de canibalização) ou de aumento de preço (`PRICE_HIKE`, indutora de migração positiva para substitutos).
  - **P-129.3 (Evento Lançamento `launch`):** Conforme §8.1 do plano mestre, um lançamento real ocorre apenas para produtos cuja primeira venda registrada é $\ge LAUNCH\_CUTOFF\_DATE$ (`2025-04-01`). Produtos com primeira venda no primeiro trimestre de 2025 são classificados como maduros e rejeitados como eventos de lançamento.
  - **P-129.4 (Histórico Mínimo de Lançamento):** Para avaliar o efeito de um lançamento, o SKU alvo deve possuir no mínimo `MIN_LAUNCH_MONTHS` (3) meses completos de vendas desde sua introdução ($T_0$).
  - **P-129.5 (Detecção Automática ou Especificação Explícita):** A API aceita o parâmetro `eventType` (`promo`, `price`, `launch`) e opcionalmente a data do evento `eventDate` ($T_0$). Se omitida a data, o sistema seleciona o evento mais recente detectado no histórico para o tipo informado.
- **Condições de Ativação:** Chamada a `GET /analytics/cannibalization/{sku}?eventType=...`.
- **Resultado Esperado:** Objeto do evento parametrizado com tipo, data base $T_0$, magnitude do evento (ex: desconto de 15% ou introdução do SKU) e janelas pré e pós fixadas.
- **Exceção / Mensagem de Erro:** Se nenhum evento do tipo informado for detectado no histórico do produto, retornar `CAN-002` (HTTP 422: "Nenhum evento do tipo especificado encontrado para o produto no período analisável").

---

### `P-130`: Definição de Janelas Temporais de Análise e Expurgos de Dados

- **Declaração Mandatória:** A análise DEVE confrontar uma Janela Pré-Evento (período base) e uma Janela Pós-Evento (período de impacto) de extensões temporais idênticas e simétricas, expurgando dados parciais.
- **Sub-regras:**
  - **P-130.1 (Extensão Simétrica $W$):** A janela de análise é definida em semanas $W$, com valor padrão `DEFAULT_ANALYSIS_WINDOW_WEEKS = 4` semanas (28 dias pré vs 28 dias pós). O usuário pode parametrizar $W$ entre `MIN_ANALYSIS_WINDOW_WEEKS` (2) e `MAX_ANALYSIS_WINDOW_WEEKS` (12).
  - **P-130.2 (Limites Temporais):**
    - Janela Pré: $[T_0 - W \text{ dias}, T_0 - 1 \text{ dia}]$
    - Janela Pós: $[T_0, T_0 + W - 1 \text{ dias}]$
  - **P-130.3 (Caso Especial de Lançamento):** Para eventos de `launch`, a Janela Pré para os produtos substitutos é o período de $W$ semanas imediatamente anterior à primeira venda do SKU novo. O SKU novo possui venda zero por definição na janela pré.
  - **P-130.4 (Expurgo de Mês Corrente Incompleto):** Quando a análise opera no grão mensal, o mês calendário corrente incompleto DEVE ser rigorosamente expurgado para evitar distorções de volume.
  - **P-130.5 (Tratamento de Dias Sem Venda):** Dias sem vendas registrados dentro do intervalo do produto são preenchidos com quantidade zero, garantindo densidade temporal contínua na série.
- **Condições de Ativação:** Processamento do pipeline temporal no domínio.
- **Resultado Esperado:** Séries temporais alinhadas para o SKU alvo, candidatos substitutos e produtos do grupo de controle.
- **Exceção / Mensagem de Erro:** Caso a data do evento não permita construir a janela pré (evento muito próximo ao início da base) ou a janela pós (evento recente sem dados pós suficientes), lançar `CAN-003` (HTTP 422: "Histórico insuficiente para compor as janelas pré e pós do evento").

---

### `P-131`: Seleção e Validação do Grupo de Controle Categorial

- **Declaração Mandatória:** O sistema DEVE constituir um Grupo de Controle sintético composto por produtos da mesma categoria (`Tipo`) que não sofreram intervenções comerciais no período, servindo como baseline de neutralização macro e sazonal.
- **Sub-regras:**
  - **P-131.1 (Critérios de Inclusão no Controle):**
    1. Pertencer ao mesmo `Tipo` do SKU alvo.
    2. Não ser o SKU alvo e não estar na lista de candidatos a substitutos diretos com $Jaccard \ge MIN\_JACCARD\_SIMILARITY$.
    3. Não ter participado de campanhas de promoção (`Cod Promocao`) nas janelas pré ou pós.
    4. Não ter sofrido variação de preço médio maior que `CONTROL_MAX_PRICE_VARIATION` (3%) entre as janelas pré e pós.
  - **P-131.2 (Tamanho Mínimo do Grupo de Controle):** O grupo de controle DEVE conter pelo menos `MIN_CONTROL_GROUP_SIZE` (5) produtos elegíveis com vendas ativas em ambas as janelas.
  - **P-131.3 (Agregação do Baseline do Controle):** O índice de evolução do controle ($g_{ctrl}$) é calculado como a razão da soma dos volumes vendidos por todos os produtos do grupo de controle:
    $$g_{ctrl} = \frac{\sum_{k \in Controle} V_{k}^{Pos}}{\sum_{k \in Controle} V_{k}^{Pre}}$$
    Se $\sum V_{k}^{Pre} = 0$, o índice é unitário ($1.0$).
  - **P-131.4 (Fallback de Controle Categorial):** Se o `Tipo` não possuir 5 produtos elegíveis sem eventos, expandir o controle para produtos do mesmo `Fornecedor` estáveis ou, em último caso, para o portfólio global de produtos estáveis da empresa, registrando a tag `CONTROLE_EXPANDIDO` nos metadados.
- **Condições de Ativação:** Execução do motor de Diferença em Diferenças.
- **Resultado Esperado:** Fator de crescimento esperado $g_{ctrl}$ representativo da sazonalidade e tendência de categoria.
- **Exceção / Mensagem de Erro:** Se mesmo após o fallback for impossível reunir o tamanho mínimo de controle, retornar `CAN-003` (HTTP 422: "Impossível constituir grupo de controle válido para isolamento de sazonalidade").

---

### `P-132`: Modelo de Diferença em Diferenças (DiD) para Estimação do Efeito

- **Declaração Mandatória:** O efeito causal da ação sobre cada produto substituto DEVE ser estimado exclusivamente através da metodologia de Diferença em Diferenças (DiD) confrontando o volume observado com o volume contrafactual projetado pelo grupo de controle.
- **Sub-regras:**
  - **P-132.1 (Volume Esperado Contrafactual):** Para cada produto candidato a substituto $i$, o volume de vendas que teria ocorrido na ausência do evento é projetado multiplicando seu volume pré pelo índice do grupo de controle:
    $$\hat{V}_{i}^{Pos} = V_{i}^{Pre} \times g_{ctrl}$$
  - **P-132.2 (Efeito Estimado em Volume $\Delta V_i$):** A diferença entre o volume real observado e o contrafactual define o efeito causal líquido atribuído ao evento:
    $$\Delta V_i = V_{i}^{Pos} - \hat{V}_{i}^{Pos} = (V_{i}^{Pos} - V_{i}^{Pre}) - V_{i}^{Pre} \times (g_{ctrl} - 1)$$
  - **P-132.3 (Variação Percentual Causal):**
    $$\Delta\%_i = \begin{cases} \frac{V_{i}^{Pos} - \hat{V}_{i}^{Pos}}{\hat{V}_{i}^{Pos}} \times 100, & \text{se } \hat{V}_{i}^{Pos} > 0 \\ 0.0, & \text{se } \hat{V}_{i}^{Pos} = 0 \end{cases}$$
  - **P-132.4 (Interpretação do Sinal):**
    - Se $\Delta V_i < 0$: O produto substituto vendeu menos do que o esperado pela evolução natural da categoria (potencial canibalização).
    - Se $\Delta V_i > 0$: O produto vendeu mais do que o esperado pela categoria (potencial complemento ou efeito halo de tráfego).
- **Condições de Ativação:** Cálculo do efeito para cada candidato a substituto.
- **Resultado Esperado:** Vetor de efeitos brutos $\Delta V_i$ e percentuais $\Delta\%_i$ para todos os candidatos.

---

### `P-133`: Rigor Estatístico, Teste de Hipóteses e Controle de Descoberta Falsa (FDR)

- **Declaração Mandatória:** Nenhuma variação de volume deve ser reportada como conclusiva sem validação por teste de significância e correção de múltiplos testes de Benjamini-Hochberg (FDR $\le 0.05$).
- **Sub-regras:**
  - **P-133.1 (Método de Significância):** O sistema calcula o valor-p bicaudal para cada candidato através de teste estatístico (regressão DiD com erros robustos ou procedimento não-paramétrico de Bootstrap com $B = 1.000$ reamostragens sobre as vendas diárias/semanais dos produtos).
  - **P-133.2 (Correção de Benjamini-Hochberg):** Com $m$ candidatos testados simultaneamente:
    1. Ordenam-se os valores-p em ordem crescente: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$.
    2. Calcula-se o valor-p ajustado (q-value):
       $$q_{(k)} = \min \left( 1, \min_{j \ge k} \left\{ \frac{m}{j} p_{(j)} \right\} \right)$$
    3. Uma variação é estatisticamente significativa se $q_{(k)} \le FDR\_ALPHA$ ($0.05$).
  - **P-133.3 (Filtro de Relevância Prática):** Mesmo com significância estatística, se o volume absoluto do efeito for menor que `MIN_EFFECT_VOLUME_UNITS` ($|\Delta V_i| < 5$ unidades), o produto DEVE ser reclassificado como insignificante para evitar alarmismo com pequenas flutuações.
  - **P-133.4 (Intervalo de Confiança):** O sistema deve fornecer para cada efeito significativo o intervalo de confiança de 95% $[IC_{inf}, IC_{sup}]$ para $\Delta V_i$.
- **Condições de Ativação:** Avaliação de significância do conjunto de produtos impactados.
- **Resultado Esperado:** Lista de p-valores, q-valores corrigidos e flag booleano `isSignificant` por produto.

---

### `P-134`: Taxonomia de Classificação de Impacto

- **Declaração Mandatória:** Cada produto candidato avaliado DEVE receber uma e apenas uma classificação categorial dentre os tipos `CANIBALIZACAO`, `COMPLEMENTO` ou `SEM_EFEITO`.
- **Sub-regras:**
  - **P-134.1 (`CANIBALIZACAO`):**
    - O SKU alvo apresentou aumento de vendas ($\Delta V_{alvo} > 0$ no caso de promoção/lançamento/queda de preço).
    - O produto substituto apresentou queda estatisticamente significativa: $\Delta V_i < 0$, $q_i \le 0.05$ e $|\Delta V_i| \ge MIN\_EFFECT\_VOLUME\_UNITS$.
  - **P-134.2 (`COMPLEMENTO`):**
    - O SKU alvo aumentou vendas ($\Delta V_{alvo} > 0$).
    - O produto correlato apresentou aumento estatisticamente significativo: $\Delta V_i > 0$, $q_i \le 0.05$ e $|\Delta V_i| \ge MIN\_EFFECT\_VOLUME\_UNITS$. (Convergência com as regras de cross-sell de F4).
  - **P-134.3 (`SEM_EFEITO`):**
    - Quando o produto não atende ao critério de significância ($q_i > 0.05$) ou quando $|\Delta V_i| < MIN\_EFFECT\_VOLUME\_UNITS$.
  - **P-134.4 (Caso Inverso - Reajuste Positivo de Preço `PRICE_HIKE`):**
    - Quando o SKU alvo tem aumento de preço e queda de vendas ($\Delta V_{alvo} < 0$), o ganho significativo no substituto ($\Delta V_i > 0, q_i \le 0.05$) é classificado como `MIGRACAO_POSITIVA` (absorção de demanda pelo substituto).
- **Condições de Ativação:** Rotulagem final da análise.
- **Resultado Esperado:** Status semântico inequívoco para apresentação ao usuário final e resumo executivo.

---

### `P-135`: Cálculo do Efeito Líquido Global em Volume, Receita e Margem

- **Declaração Mandatória:** O sistema DEVE calcular o impacto financeiro global consolidado da ação comercial sobre toda a família de produtos impactados, reportando $\Delta$ unidades, $\Delta$ receita líquida e $\Delta$ margem de contribuição.
- **Sub-regras:**
  - **P-135.1 (Efeito Líquido em Volume $\Delta V_{liq}$):**
    $$\Delta V_{liq} = \Delta V_{alvo} + \sum_{i \in Afetados} \Delta V_i$$
  - **P-135.2 (Efeito Líquido em Receita $\Delta R_{liq}$):**
    $$\Delta R_{liq} = \Delta R_{alvo} + \sum_{i \in Afetados} (\Delta V_i \times \bar{P}_i^{Pos})$$
    onde $\Delta R_{alvo} = (V_{alvo}^{Pos} \times \bar{P}_{alvo}^{Pos}) - (V_{alvo}^{Pre} \times \bar{P}_{alvo}^{Pre})$.
  - **P-135.3 (Margem Unitária e Fallback de Custo):**
    - A margem unitária de cada produto é obtida por $M_u = Pc.Venda - Pc.Ultimo Custo$.
    - Se $Pc.Ultimo Custo$ for nulo, menor ou igual a zero ou inconsistente ($> Pc.Venda$), aplica-se o fallback padrão de P-054.5: $CustoEstimado = Pc.Venda \times COST\_FALLBACK\_RATIO$ ($0.60$), gerando margem de $40\%$.
  - **P-135.4 (Efeito Líquido em Margem $\Delta M_{liq}$):**
    $$\Delta M_{liq} = \Delta M_{alvo} + \sum_{i \in Afetados} (\Delta V_i \times M_{u, i})$$
  - **P-135.5 (Veredito Comercial da Ação):**
    - Se $\Delta M_{liq} > 0$: Classificado como `VALEU_A_PENA` (ganho líquido real de margem).
    - Se $\Delta M_{liq} \le 0$ e $\Delta V_{liq} > 0$: Classificado como `ILUSAO_DE_VOLUME` (aumento de giro, porém perda líquida de margem por canibalizar itens mais rentáveis).
    - Se $\Delta M_{liq} \le 0$ e $\Delta V_{liq} \le 0$: Classificado como `PREJUIZO_TOTAL` (perda tanto de volume quanto de margem).
- **Condições de Ativação:** Fechamento dos indicadores do painel de canibalização.
- **Resultado Esperado:** Card executivo contendo os 3 indicadores líquidos e o veredito comercial.

---

### `P-136`: Interface de Integração com Elasticidade-Preço Cruzada (Fase F5)

- **Declaração Mandatória:** A arquitetura DEVE definir formalmente o contrato de integração com o módulo de Elasticidade (F5), permitindo decompor a perda dos substitutos entre choque de preço e fatores exógenos de visibilidade.
- **Sub-regras:**
  - **P-136.1 (Elasticidade Cruzada Teórica):**
    $$\epsilon_{ji} = \frac{\% \Delta Q_j}{\% \Delta P_i}$$
    representa a sensibilidade da demanda do substituto $j$ à variação de preço do alvo $i$.
  - **P-136.2 (Decomposição do Efeito):** Quando o serviço de F5 estiver disponível, a queda esperada puramente por preço é:
    $$\Delta V_{j, preco} = V_j^{Pre} \times \left( \epsilon_{ji} \times \frac{\Delta P_i}{P_i^{Pre}} \right)$$
    O desvio residual é atribuído ao efeito de destaque promocional/layout:
    $$\Delta V_{j, residual} = \Delta V_j - \Delta V_{j, preco}$$
  - **P-136.3 (Degradação Graciosa):** Enquanto a Fase F5 não estiver implementada em produção, a feature F6 opera normalmente calculando o DiD integral e deixando os campos `crossElasticity` e `priceExplainedShare` como `null` e `statusElasticidade = "NAO_INTEGRADO"`, sem lançar erro ao usuário.
- **Condições de Ativação:** Invocação do analisador de canibalização para eventos de alteração de preço (`price`) ou promoção com desconto (`promo`).
- **Resultado Esperado:** Objeto de resposta compatível tanto no modo standalone quanto no modo enriquecido por F5.

---

### `P-137`: Agregação no Banco de Dados (SQL Server), Tratamento de Devoluções e Política de Cache

- **Declaração Mandatória:** Toda a recuperação de vendas no SQL Server DEVE ser feita em nível agregado por produto e período, respeitando o abatimento obrigatório de devoluções e validação de segurança de consulta.
- **Sub-regras:**
  - **P-137.1 (Segurança de Consulta e Somente Leitura):** Todas as consultas executadas no repositório DEVEM passar obrigatoriamente pela validação `is_readonly_query` de `src.core.database`. Nenhuma query pode conter comandos de DDL/DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`).
  - **P-137.2 (Abatimento de Devoluções - D4):** Linhas de `Externo01.Vendas` com `[Operação] LIKE 'DEVOLU%'` (constante `RETURN_OPERATION_PATTERN = 'DEVOLU%'`) DEVEM ser somadas algebricamente às linhas de `VENDA`. Quantidade líquida mensal/semanal $\le 0$ é ajustada para 0 para fins de séries temporais.
  - **P-137.3 (Sem Concatenações Inválidas no SQL):** É expressamente proibido o uso da função `CONCAT` nas queries do SQL Server legado (incompatibilidade com o driver/versão); utilizar operador `+` com conversões explícitas `CAST(... AS VARCHAR)`.
  - **P-137.4 (Agregação no SQL):** A extração de dados utiliza a query agregada `monthly_sales` e `promo_calendar` (§2.5). Proibido carregar linhas brutas de itens no Python para evitar estouro de memória no Cloud Run (limite 2Gi).
  - **P-137.5 (Cache em Memória):** Resultados de similaridade de substitutos e eventos minerados são preservados em cache de aplicação com lock thread-safe (`asyncio.Lock` ou `threading.Lock`) e TTL de `CACHE_TTL_HOURS = 6` horas.
- **Condições de Ativação:** Carga de dados no repositório e ciclo de vida do cache de serviço.
- **Resultado Esperado:** Dados consistentes, processamento leve em memória e imunidade a OOM.

---

### `P-138`: Padronização de Erros de Domínio (`CAN-001` a `CAN-005`), Envelopamento e Respostas HTTP

- **Declaração Mandatória:** Todas as respostas da API de Canibalização DEVEM ser envelopadas no padrão `{ "data": ..., "meta": ... }` com atributos em `camelCase`, e erros de negócio DEVEM utilizar o prefixo `CAN-XXX`.
- **Sub-regras:**
  - **P-138.1 (Matriz de Códigos de Erro):**
    - `CAN-001` (HTTP 404): SKU alvo inexistente ou inativo no catálogo.
    - `CAN-002` (HTTP 422): Evento especificado não localizado ou sem histórico transacional.
    - `CAN-003` (HTTP 422): Histórico insuficiente de vendas para janelas pré/pós ou impossibilidade de constituir grupo de controle.
    - `CAN-004` (HTTP 400): Parâmetros de requisição inválidos (datas incoerentes, tipo de evento inválido, janela fora dos limites permitidos).
    - `CAN-005` (HTTP 500): Falha de infraestrutura, timeout de conexão com banco de dados ou erro inesperado de processamento.
  - **P-138.2 (Envelope de Sucesso):**
    ```json
    {
      "data": { ... },
      "meta": {
        "timestamp": "2026-11-12T12:00:00Z",
        "sku": "100234",
        "eventType": "promo",
        "windowWeeks": 4
      }
    }
    ```
  - **P-138.3 (Envelope de Erro):**
    ```json
    {
      "error": {
        "code": "CAN-002",
        "message": "Nenhum evento promocional recente encontrado para o SKU especificado.",
        "details": null
      }
    }
    ```
  - **P-138.4 (Proibição de Stacktraces):** Em nenhuma circunstância o payload de erro HTTP deve expor rastros de pilha (stacktraces), estruturas internas de SQL ou detalhes do driver ODBC.
- **Condições de Ativação:** Toda e qualquer resposta HTTP emitida pelas rotas de canibalização.
- **Resultado Esperado:** Contrato resiliente, previsível e seguro.

---

## 4. Enquadramento LGPD & Privacidade (Art. 7º e 11 da LGPD)

| Dado / Atributo | Origem | Classificação LGPD | Base Legal Aplicada | Finalidade Específica e Proporcional |
| :--- | :--- | :--- | :--- | :--- |
| `Cod Cliente` | `Externo01.Vendas` | Dado Pessoal Pseudonimizado (quando PF/MEI) | Legítimo Interesse do Controlador (Art. 7º, IX) | Usado temporariamente e exclusivamente para cômputo agregado da similaridade de Jaccard entre produtos. Nunca exposto na API nem em logs. |
| `Codigo`, `Descricao`, `Tipo`, `Fornecedor`, `Preco`, `Custo` | `Externo01.Produto` | Dado Comercial Não Pessoal | Não aplicável (Fora do escopo LGPD) | Identificação cadastral de produtos, formação de categorias e cálculo de margem. |
| Volumes agregados de venda | `Externo01.Vendas` | Dado Estatístico Agregado | Não aplicável (Anonimizado por agregação) | Cálculo do modelo de Diferença em Diferenças e efeito líquido. |

> **Nota do Encarregado (DPO):** Como a feature F6 opera exclusivamente no grão de produto (SKU) e não expõe nenhum atributo individual de clientes em telas, relatórios ou payloads de API, confirma-se o **Bypass de RIPD Completo**, mantendo-se a exigência de minimização estrita e proibição de log de `Cod Cliente`.

---

## 5. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP | Código Interno |
| :--- | :--- | :--- | :--- | :--- |
| **C-01** | SKU válido, evento `promo` recente com 4 semanas pré/pós e controle estável | Calcula DiD, retorna afetados classificados e card de efeito líquido | `200 OK` | - |
| **C-02** | SKU inexistente na base (`/cannibalization/999999`) | Retorna mensagem amigável de produto não encontrado | `404 Not Found` | `CAN-001` |
| **C-03** | SKU com evento `launch`, primeira venda anterior a 2025-04-01 | Rejeita falso lançamento (produto antigo cadastrado no início da base) | `422 Unprocessable` | `CAN-002` |
| **C-04** | Evento recente sem histórico pós suficiente ($< 2$ semanas) | Notifica insuficiência de dados pós-evento para análise conclusiva | `422 Unprocessable` | `CAN-003` |
| **C-05** | Tipo de evento inválido (`?eventType=desconto_relampago`) | Rejeita requisição validando enum permitido (`promo`, `price`, `launch`) | `400 Bad Request` | `CAN-004` |
| **C-06** | Janela solicitada fora dos limites (`?windowWeeks=20`) | Rejeita informando limites permitidos (entre 2 e 12 semanas) | `400 Bad Request` | `CAN-004` |
| **C-07** | Nenhum produto substituto atinge significância ($q_i > 0.05$) | Retorna lista vazia ou itens com status `SEM_EFEITO`, sem erro | `200 OK` | - |
| **C-08** | Custo do produto nulo ou zero no banco | Aplica fallback de 60% de custo (margem de 40%) conforme P-135.3 | `200 OK` | - |
| **C-09** | Falha de rede ou timeout com SQL Server | Captura exceção e devolve erro sanitizado sem expor driver | `500 Internal Server` | `CAN-005` |

---

## 6. Critérios de Aceitação (DoD - Definition of Done da Especificação)

- [ ] Todas as regras `P-128` a `P-138` estão detalhadas com fórmulas matemáticas unívocas e sem parâmetros mágicos.
- [ ] O modelo estatístico de Diferença em Diferenças (DiD) e o controle de falsas descobertas (FDR Benjamini-Hochberg) estão formalizados.
- [ ] O mecanismo de expurgo de falso lançamento (`LAUNCH_CUTOFF_DATE = 2025-04-01`) e abatimento de devoluções (`LIKE 'DEVOLU%'`) estão garantidos.
- [ ] A interface de desacoplamento e integração futura com a Fase F5 (Elasticidade) está delineada.
- [ ] Códigos de erro semânticos `CAN-001` a `CAN-005` e envelope `data`/`meta` estão estipulados.
