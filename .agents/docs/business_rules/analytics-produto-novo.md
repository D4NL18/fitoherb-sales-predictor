# Regras de Negócio: Viabilidade de Produto Novo (`analytics-produto-novo`)

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-produto-novo.md`  
> **Responsável:** Analista de Requisitos (`analyst.md` / `business-rules-expert`)  
> **Faixa Exclusiva de Regras:** `P-139` a `P-149`  
> **Prefixo Exclusivo de Erros:** `NEW-XXX`  
> **Referências Normativas:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`, `.agents/docs/tasks/ia-analytics-vendas.md` (§8)

---

## 1. Contexto, Objetivo e Decisões Fundamentais

- **User Story:** US-NEW — *Como comprador ou gestor da Fitoherb, quero simular a viabilidade de introdução de um produto não cadastrado (através de seus atributos comerciais e descritivos), obtendo uma estimativa de vendas conservadora baseada em lançamentos reais semelhantes e uma análise financeira de margem, para decidir com segurança se vale a pena incluí-lo no portfólio.*
- **Decisão D2 (Produto não cadastrado):** A funcionalidade não opera sobre SKUs existentes. A entrada é composta exclusivamente por atributos hipotéticos (`tipo`, `fornecedor`, `descricao`, `precoVendaPrevisto`, `custoUnitario`, `margemMinimaDesejada`, `horizonMonths`).
- **Decisão D4 (Abatimento de Devoluções):** A curva de vendas dos produtos similares e dos produtos maduros utiliza faturamento e quantidades estritamente líquidos de devoluções (`[Operação] LIKE 'DEVOLU%'`, com valores e quantidades negativos somados aritmeticamente).
- **Atores:** Comprador / Gestor Comercial (entrada de dados e consulta interativa), Sistema ERP SQL Server (somente leitura de agregados).
- **Natureza Conservadora:** A previsão visa proteção de caixa e estoque contra excessos de compra. Por design, o produto novo inicia sua projeção abaixo da média de mercado dos similares ($P25 \times 0.70$), de modo que em pelo menos 80% dos casos reais o produto supere a previsão inicial.

---

## 2. Tabela de Parâmetros e Constantes do Domínio

> [!IMPORTANT]
> Todos os parâmetros abaixo DEVEM ser declarados como constantes imutáveis no topo do módulo de domínio `src/modules/analytics/domain/new_product.py` (sem números mágicos no código).

| Constante | Valor | Finalidade | Regra Associada |
| :--- | :--- | :--- | :--- |
| `SALE_OPERATION` | `'VENDA'` | Identificador de operação de venda no ERP | `P-139`, `P-144` |
| `RETURN_OPERATION_PATTERN` | `'DEVOLU%'` | Padrão SQL de filtro de devoluções (driver ODBC) | `P-139`, `P-144` |
| `LAUNCH_CUTOFF_DATE` | `'2025-04-01'` | Data de corte que separa produtos pré-existentes de lançamentos reais | `P-139` |
| `MIN_LAUNCH_MONTHS` | `3` | Meses mínimos de histórico desde a 1ª venda para elegibilidade da curva | `P-139`, `P-144` |
| `TOP_K_SIMILARS` | `10` | Quantidade máxima de produtos similares selecionados para o cálculo | `P-142`, `P-143` |
| `MIN_SIMILARS` | `3` | Quantidade mínima obrigatória de similares; abaixo disso aborta com `NEW-001` | `P-143` |
| `WEIGHT_SUPPLIER` | `0.25` | Peso da similaridade de fornecedor ($w_{\text{forn}}$) | `P-142` |
| `WEIGHT_PRICE` | `0.35` | Peso da proximidade de preço em escala logarítmica ($w_{\text{preco}}$) | `P-142` |
| `WEIGHT_TFIDF` | `0.40` | Peso da similaridade textual de descrição por TF-IDF ($w_{\text{tfidf}}$) | `P-142` |
| `NEW_PRODUCT_HAIRCUT` | `0.70` | Fator multiplicativo conservador aplicado sobre o P25 dos similares | `P-145` |
| `MIN_BACKTEST_SUCCESS_RATE` | `0.80` | Limiar do backtest (>= 80% dos lançamentos reais superam a previsão) | `P-145` |
| `DEFAULT_HORIZON_MONTHS` | `3` | Horizonte padrão de projeção mensal | `P-140`, `P-144` |
| `MAX_HORIZON_MONTHS` | `3` | Horizonte máximo permitido na FASE F2 | `P-140`, `P-144` |
| `SEASONALITY_MIN_FACTOR` | `0.90` | Piso de atenuação do multiplicador sazonal | `P-146` |
| `SEASONALITY_MAX_FACTOR` | `1.10` | Teto de atenuação do multiplicador sazonal | `P-146` |
| `CACHE_TTL_HOURS` | `6` | Tempo de vida do cache dos agregados de similares e catálogo | `P-149` |

---

## 3. Catálogo de Regras de Negócio (`P-139` a `P-149`)

### `P-139`: Definição de Lançamento Real e Elegibilidade da Curva Histórica
- **Declaração Mandatória:** O sistema DEVE distinguir rigorosamente lançamentos reais de produtos pré-existentes na base de dados, excluindo do conjunto de similares qualquer produto cuja primeira venda seja anterior a `2025-04-01`.
- **Sub-regras:**
  - **P-139.1 (Corte Temporal):** Como o histórico do ERP inicia em `2025-01-07`, os ~1.421 produtos com primeira venda registrada no 1º trimestre de 2025 (2025-T1) são considerados "produtos antigos/pré-existentes" e NÃO representam lançamentos reais.
  - **P-139.2 (Lançamento Real):** É classificado como lançamento real apenas o produto cuja data mínima de venda (`MIN([Data])` com `[Operação] = 'VENDA'`) for maior ou igual a `LAUNCH_CUTOFF_DATE` (`2025-04-01`).
  - **P-139.3 (Maturidade da Curva Inicial):** Para compor a curva de projeção dos primeiros meses, o lançamento real DEVE possuir pelo menos `MIN_LAUNCH_MONTHS = 3` meses completos decorridos entre o mês da primeira venda e o último mês fechado da base (excluído o mês corrente parcial).
  - **P-139.4 (Isolamento de Produtos Maduros):** Produtos com primeira venda anterior a `2025-04-01` são segregados e utilizados EXCLUSIVAMENTE para a determinação do "Teto Maduro de Referência" (`P-147`), sendo terminantemente proibida sua inclusão no cálculo de similares do produto novo.

---

### `P-140`: Entrada de Dados por Atributos Hipotéticos (Sem SKU)
- **Declaração Mandatória:** O sistema DEVE processar a análise de viabilidade a partir de um conjunto de atributos comerciais e técnicos informados pelo usuário, sem exigir ou permitir a amarração a um SKU pré-existente no ERP.
- **Sub-regras:**
  - **P-140.1 (Campos Obrigatórios):**
    - `tipo`: string não vazia, obrigatória, devendo existir na lista de tipos válidos do catálogo ativo (`P-141`).
    - `fornecedor`: string não vazia, obrigatória, devendo existir na lista de fornecedores válidos do catálogo ativo (`P-141`).
    - `descricao`: string contendo entre 3 e 120 caracteres, obrigatória, descrevendo o item em linguagem natural.
    - `precoVendaPrevisto`: numérico decimal, obrigatório, estritamente maior que zero (`precoVendaPrevisto > 0.00`).
  - **P-140.2 (Campos Opcionais de Viabilidade Financeira):**
    - `custoUnitario`: numérico decimal opcional. Se informado, deve ser estritamente maior que zero e menor ou igual a `precoVendaPrevisto` (`0.00 < custoUnitario <= precoVendaPrevisto`).
    - `margemMinimaDesejada`: percentual decimal opcional ($0.00 \le \text{margemMinimaDesejada} \le 1.00$, correspondendo a 0% a 100%).
    - `horizonMonths`: número inteiro opcional de meses para projeção, restrito a $\{1, 2, 3\}$, com padrão igual a `DEFAULT_HORIZON_MONTHS = 3`.
  - **P-140.3 (Exceções de Validação):**
    - Caso `precoVendaPrevisto <= 0`, retornar HTTP `400` com código `NEW-004` e mensagem: `"O preço de venda previsto deve ser estritamente positivo."`
    - Caso `custoUnitario` seja informado e `custoUnitario > precoVendaPrevisto`, retornar HTTP `400` com código `NEW-004` e mensagem: `"O custo unitário não pode ser superior ao preço de venda previsto."`
    - Caso `margemMinimaDesejada` seja informada fora do intervalo $[0.0, 1.0]$, retornar HTTP `400` com código `NEW-004` e mensagem: `"A margem mínima desejada deve estar entre 0% e 100%."`

---

### `P-141`: Catálogo de Opções de Tipo e Fornecedor
- **Declaração Mandatória:** O sistema DEVE fornecer um endpoint leve de consulta das opções disponíveis de `tipo` e `fornecedor` oriundas do catálogo ativo de produtos.
- **Sub-regras:**
  - **P-141.1 (Origem e Atividade):** As listas DEVEM ser extraídas da tabela `Externo01.Produto` considerando apenas produtos com `[Pc.Venda] > 0` e valores não nulos/não vazios.
  - **P-141.2 (Ordenação e Deduplicação):** As listas retornadas devem ser deduplicadas e ordenadas alfabeticamente (case-insensitive / pt-BR).
  - **P-141.3 (Cache de Catálogo):** As opções de catálogo devem ser mantidas em cache em memória com TTL de `CACHE_TTL_HOURS = 6`, atualizadas em conjunto com a carga base do módulo.

---

### `P-142`: Algoritmo de Similaridade Híbrido Multicritério
- **Declaração Mandatória:** A seleção dos produtos similares DEVE operar por filtragem estrita pelo `tipo` informado, seguida pela pontuação híbrida normalizada no intervalo $[0.0, 1.0]$ baseada em Fornecedor, Preço e Descrição Textual.
- **Sub-regras:**
  - **P-142.1 (Filtro Rígido de Categoria):** O universo candidato é composto EXCLUSIVAMENTE pelos lançamentos reais elegíveis (`P-139`) cujo campo `[Tipo]` seja idêntico ao `tipo` informado (comparação semântica insensível a maiúsculas e espaços excedentes). É PROIBIDO relaxar o filtro de categoria mesmo se a quantidade for reduzida.
  - **P-142.2 (Score de Fornecedor - $S_{\text{forn}}$):**
    $$S_{\text{forn}} = \begin{cases} 1.0 & \text{se } \text{Fornecedor}_{\text{candidato}} = \text{fornecedor}_{\text{informado}} \\ 0.0 & \text{caso contrário} \end{cases}$$
  - **P-142.3 (Score de Preço em Escala Logarítmica - $S_{\text{preco}}$):** Para evitar distorções de magnitude linear e tratar variações relativas uniformemente:
    $$\Delta_{\ln} = \left| \ln(\text{precoVendaPrevisto}) - \ln(P_{\text{candidato}}) \right|$$
    $$S_{\text{preco}} = \exp\left( - \Delta_{\ln} \right) = \frac{\min(\text{precoVendaPrevisto}, P_{\text{candidato}})}{\max(\text{precoVendaPrevisto}, P_{\text{candidato}})}$$
    O score atinge $1.0$ quando os preços são idênticos e decresce proporcionalmente à razão dos valores.
  - **P-142.4 (Score Textual TF-IDF - $S_{\text{tfidf}}$):**
    - A descrição informada e as descrições dos produtos candidatos são normalizadas: conversão para minúsculas, remoção de pontuação e acentos, e eliminação de stop words comuns em português e termos genéricos de embalagem (`un`, `cx`, `pct`, `frasco`, `500ml`, `1kg`).
    - Vetorização por TF-IDF com n-grams de palavras $(1, 2)$ e cálculo da similaridade por cosseno entre o vetor da descrição informada e o vetor de cada similar candidato:
      $$S_{\text{tfidf}} = \cos(\vec{v}_{\text{informado}}, \vec{v}_{\text{candidato}}) \in [0.0, 1.0]$$
  - **P-142.5 (Score Composto Final):**
    $$\text{Score} = (w_{\text{forn}} \cdot S_{\text{forn}}) + (w_{\text{preco}} \cdot S_{\text{preco}}) + (w_{\text{tfidf}} \cdot S_{\text{tfidf}})$$
    onde $w_{\text{forn}} = 0.25$, $w_{\text{preco}} = 0.35$ e $w_{\text{tfidf}} = 0.40$, com $\sum w = 1.00$.

---

### `P-143`: Seleção de Similares, Mínimo Obrigatório e Base Insuficiente
- **Declaração Mandatória:** O sistema DEVE ordenar os candidatos elegíveis em ordem decrescente do Score Composto e selecionar até `TOP_K_SIMILARS = 10` itens, exigindo um mínimo de `MIN_SIMILARS = 3` itens válidos.
- **Sub-regras:**
  - **P-143.1 (Ordenação e Desempate):** Em caso de empate no score composto, o desempate segue a maior similaridade de preço ($S_{\text{preco}}$) e, persistindo, a data de primeira venda mais recente.
  - **P-143.2 (Bloqueio por Base Insuficiente - `NEW-001`):** Se a quantidade de candidatos elegíveis no `tipo` informado for estritamente inferior a `MIN_SIMILARS` ($N < 3$), o sistema DEVE interromper imediatamente o cálculo e retornar código HTTP `422 Unprocessable Entity` com erro `NEW-001` e mensagem: `"Base de lançamentos similares insuficiente para o tipo selecionado (mínimo de 3 lançamentos necessários; encontrados: N)."`
  - **P-143.3 (Transparência dos Similares):** A resposta da API DEVE listar os similares utilizados contendo: código SKU, descrição, fornecedor, preço histórico de venda, data da primeira venda, pontuação de similaridade consolidada e scores parciais.

---

### `P-144`: Curva Histórica Inicial dos Similares (Líquida de Devoluções)
- **Declaração Mandatória:** Para cada produto similar selecionado, o sistema DEVE extrair a série temporal mensal de quantidades líquidas vendidas nos seus primeiros 3 meses de vida no mercado.
- **Sub-regras:**
  - **P-144.1 (Mês Relativo de Vida):** O Mês 1 ($M_1$) de um similar corresponde ao mês civil de sua primeira venda registrada. O Mês 2 ($M_2$) é o mês civil subsequente ($M_1 + 1$) e o Mês 3 ($M_3$) é o seguinte ($M_1 + 2$).
  - **P-144.2 (Abatimento Integral de Devoluções):** A quantidade de cada mês $m \in \{1, 2, 3\}$ é estritamente a soma algébrica das vendas e devoluções:
    $$Q_{\text{liq}}(m) = \sum \text{Qtd Venda (VENDA)} + \sum \text{Qtd Venda (DEVOLUÇÃO)}$$
    Se $Q_{\text{liq}}(m) < 0$ em decorrência de devoluções superiores a vendas no mês, o valor líquido adotado na série é delimitado em $0$.
  - **P-144.3 (Meses sem Movimentação):** Se um similar não apresentar vendas em $M_2$ ou $M_3$ dentro de seu período ativo, a quantidade líquida associada é imputada como $0$.

---

### `P-145`: Cálculo da Previsão Conservadora e Trava de Haircut
- **Declaração Mandatória:** A quantidade prevista para cada mês do horizonte DEVE ser calculada aplicando-se o fator redutor conservador `NEW_PRODUCT_HAIRCUT = 0.70` sobre o percentil 25 ($P25$) das quantidades líquidas dos similares naquele respectivo mês de vida.
- **Sub-regras:**
  - **P-145.1 (Percentil 25 dos Similares):** Para cada mês relativo $m \in \{1, \dots, \text{horizonMonths}\}$, calcula-se $P25_m$ como o percentil 25 (método linear ou nearest rank) da distribuição $\{Q_{\text{liq}, i}(m)\}_{i=1}^K$ dos $K$ similares selecionados.
  - **P-145.2 (Aplicação do Haircut):**
    $$Q_{\text{base}}(m) = P25_m \times \text{NEW\_PRODUCT\_HAIRCUT}$$
    com $\text{NEW\_PRODUCT\_HAIRCUT} = 0.70$.
  - **P-145.3 (Trava de Segurança Inviolável):** O código DEVE conter uma assertiva explícita garantindo que a quantidade prevista nunca ultrapasse o percentil 25 dos similares:
    $$Q_{\text{previsto}}(m) \le P25_m, \quad \forall m$$
    Em nenhuma hipótese de ajuste (incluindo sazonalidade) a estimativa poderá violar esse teto prudencial.
  - **P-145.4 (Arredondamento Operacional):** A quantidade prevista em unidades é arredondada para o número inteiro imediatamente inferior ou por meio de arredondamento padrão `round(Q, 0)`, respeitando o valor mínimo de zero unidades.
  - **P-145.5 (Critério de Calibração / Backtest):** O valor de $0.70$ foi homologado via simulação retroativa com os lançamentos reais históricos, satisfazendo o requisito de que pelo menos 80% dos lançamentos reais vendam em volume estritamente superior ao valor projetado pelo modelo conservador.

---

### `P-146`: Interface e Modulação de Sazonalidade (Integração com Fase 1 / F1)
- **Declaração Mandatória:** A previsão conservadora base DEVE poder ser ajustada pelo índice de sazonalidade mensal relativo à categoria `tipo`, respeitando travas estritas de amortecimento e fallback em casos de incerteza histórica.
- **Sub-regras:**
  - **P-146.1 (Consumo da Interface de Sazonalidade):** O serviço DEVE consultar a interface de domínio fornecida pela Fase F1 (`SeasonalityService` / `get_seasonal_index(tipo, mes_calendario)`).
  - **P-146.2 (Amortecimento Obrigatório):** O fator sazonal $F_{\text{sazonal}}$ aplicável à previsão é contido rigidamente no intervalo $[0.90, 1.10]$:
    $$F_{\text{ajustado}} = \max(0.90, \min(1.10, F_{\text{sazonal}}))$$
    Isso impede que ruídos em categorias com histórico de apenas 2 anos distorçam drasticamente a viabilidade de um lançamento.
  - **P-146.3 (Fallback de Confiança Baixa ou Inexistente):** Caso o índice da categoria retorne com nível de confiança `BAIXA` (menos de 2 ciclos concordantes) ou caso a Fase F1 ainda não esteja implementada no ambiente de execução, o sistema DEVE adotar neutralidade absoluta: $F_{\text{ajustado}} = 1.00$ (sem ajuste sazonal).
  - **P-146.4 (Preservação da Trava Conservadora):** Mesmo após a aplicação do fator sazonal amortecido, a regra `P-145.3` permanece ativa: $Q_{\text{final}}(m) = \min(Q_{\text{base}}(m) \times F_{\text{ajustado}}, P25_m)$.

---

### `P-147`: Faixas de Incerteza e Teto Maduro de Referência
- **Declaração Mandatória:** Para propiciar clareza de contexto e visão de cenário sem comprometer o perfil conservador, a resposta DEVE fornecer uma faixa de dispersão dos similares e o teto de vendas maduro do `tipo`.
- **Sub-regras:**
  - **P-147.1 (Faixas dos Similares por Mês):**
    - `p10`: Percentil 10 da distribuição dos similares no mês $m$ (cenário de estresse).
    - `conservador`: Valor calculado conforme `P-145` e `P-146` (recomendação oficial).
    - `p50_mediana`: Mediana ($P50$) dos similares no mês $m$ (desempenho típico observado).
  - **P-147.2 (Teto Maduro do Tipo):** Para balizar o potencial de longo prazo caso o produto atinja maturidade plena:
    - O sistema calcula a distribuição mensal dos produtos maduros do mesmo `tipo` (produtos com $1^{\text{a}}$ venda $< \text{LAUNCH\_CUTOFF\_DATE}$).
    - Extrai-se o percentil 75 ($P75$) das vendas mensais desses produtos como `tetoMaduroP75`.
  - **P-147.3 (Distinção Conceitual):** A interface e o contrato DEVEM explicitar claramente que o `tetoMaduroP75` constitui um referencial de mercado maduro, JAMAIS devendo ser compreendido como meta ou projeção para os meses inaugurais do lançamento.

---

### `P-148`: Projeção Financeira e Análise de Viabilidade Comercial
- **Declaração Mandatória:** O sistema DEVE calcular a receita projetada e, quando `custoUnitario` for fornecido, a margem bruta nominal, a margem percentual e o parecer de viabilidade frente à margem mínima desejada.
- **Sub-regras:**
  - **P-148.1 (Receita Prevista):**
    $$\text{Receita}(m) = Q_{\text{final}}(m) \times \text{precoVendaPrevisto}$$
  - **P-148.2 (Margem Bruta Nominal e Percentual):**
    $$\text{MargemBruta}(m) = Q_{\text{final}}(m) \times (\text{precoVendaPrevisto} - \text{custoUnitario})$$
    $$\text{MargemPct} = \frac{\text{precoVendaPrevisto} - \text{custoUnitario}}{\text{precoVendaPrevisto}}$$
  - **P-148.3 (Parecer Booleano de Viabilidade - `viavel`):**
    - Se `margemMinimaDesejada` for fornecida:
      $$\text{viavel} = \begin{cases} \text{true} & \text{se } \text{MargemPct} \ge \text{margemMinimaDesejada} \\ \text{false} & \text{se } \text{MargemPct} < \text{margemMinimaDesejada} \end{cases}$$
    - Se `margemMinimaDesejada` não for informada, o atributo `viavel` retorna `null` e a tela apresenta os valores de margem calculados sem julgamento automatizado.
  - **P-148.4 (Ponto de Equilíbrio / Volume de Cobertura):**
    - Se o usuário especificar um custo de investimento inicial ou meta mínima de faturamento de margem, o sistema calcula o volume mínimo mensal necessário. Caso contrário, reporta a quantidade mensal conservadora e a margem unitária gerada.

---

### `P-149`: Isolamento de Execução, Cache e Tratamento de Erros `NEW-XXX`
- **Declaração Mandatória:** Toda a execução do módulo DEVE respeitar limites rigorosos de memória (sem carregamento de vendas brutas), reuso de cache em memória e envelope de resposta padronizado com códigos de erro `NEW-XXX`.
- **Sub-regras:**
  - **P-149.1 (Agregação SQL Rígida):** É expressamente proibido transferir tabelas brutas de vendas para a aplicação. O repositório extrai unicamente agregados mensais sumarizados por produto via `is_readonly_query`.
  - **P-149.2 (Catálogo de Erros de Domínio):**
    - `NEW-001` (HTTP `422`): Base de similares insuficiente para o tipo selecionado ($< 3$ lançamentos).
    - `NEW-002` (HTTP `400`): Tipo informado inexistente no catálogo ativo.
    - `NEW-003` (HTTP `400`): Fornecedor informado inexistente no catálogo ativo.
    - `NEW-004` (HTTP `400`): Inconsistência nos parâmetros numéricos (preço $\le 0$, custo $>$ preço, margem fora de $[0, 1]$).
    - `NEW-005` (HTTP `503`): Indisponibilidade momentânea do banco de dados ou erro de timeout no repositório.
  - **P-149.3 (Envelope Padrão):** Todas as respostas bem-sucedidas (`200 OK`) DEVEM seguir a estrutura envelope `{ "data": { ... }, "meta": { "timestamp": "...", "version": "1.0.0" } }` em formato `camelCase`.
  - **P-149.4 (Sem PII):** Nenhum dado de cliente é lido, processado ou exposto nesta funcionalidade.

---

## 4. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP | Código Interno |
| :--- | :--- | :--- | :--- | :--- |
| **C-01** | Atributos válidos, tipo com 15 lançamentos, custo e margem informados (margem atingida) | Retorna previsão mensal, 10 similares, margem e `viavel = true` | `200 OK` | - |
| **C-02** | Atributos válidos, tipo com 8 lançamentos, custo informado mas margem abaixo da desejada | Retorna previsão mensal, similares, margem e `viavel = false` | `200 OK` | - |
| **C-03** | Atributos válidos sem `custoUnitario` nem `margemMinimaDesejada` | Retorna previsão de volume e receita; margens e `viavel` retornam `null` | `200 OK` | - |
| **C-04** | Tipo informado possui apenas 1 ou 2 lançamentos reais desde 2025-04-01 | Bloqueia operação; não relaxa o tipo; explica falta de base | `422 Unprocessable` | `NEW-001` |
| **C-05** | Tipo informado não consta no catálogo ativo | Rejeita requisição indicando tipo inválido | `400 Bad Request` | `NEW-002` |
| **C-06** | Fornecedor informado não consta no catálogo ativo | Rejeita requisição indicando fornecedor inválido | `400 Bad Request` | `NEW-003` |
| **C-07** | `precoVendaPrevisto <= 0` | Validação rejeita valor nulo ou negativo | `400 Bad Request` | `NEW-004` |
| **C-08** | `custoUnitario > precoVendaPrevisto` | Rejeita inconsistência de custo superior ao preço | `400 Bad Request` | `NEW-004` |
| **C-09** | `margemMinimaDesejada = 1.25` (125%) | Rejeita valor percentual superior a 100% | `400 Bad Request` | `NEW-004` |
| **C-10** | Similar teve devolução massiva em $M_2$ gerando líquido negativo | Quantidade líquida de $M_2$ é truncada em 0 e não gera erro numérico | `200 OK` | - |
| **C-11** | Produtos com 1ª venda em 2025-T1 existem no mesmo tipo | São ignorados na busca de similares; entram apenas no `tetoMaduroP75` | `200 OK` | - |
| **C-12** | Timeout na conexão com o banco de dados SQL Server | Captura falha sem expor stacktrace e retorna erro semântico | `503 Service Unavailable` | `NEW-005` |

---

## 5. Critérios de Aceitação da Especificação (DoD)

- [x] Regras delimitadas com identificadores unívocos na faixa `P-139` a `P-149`.
- [x] Respeito absoluto às decisões D2 (sem SKU) e D4 (abatimento de devoluções).
- [x] Definição objetiva de Lançamento Real (primeira venda $\ge 2025-04-01$ e $\ge 3$ meses de histórico).
- [x] Formulação matemática completa da similaridade híbrida (Tipo + Fornecedor + Log-Preço + TF-IDF) e do Haircut ($P25 \times 0.70$).
- [x] Interface de integração com a Fase F1 (Sazonalidade) definida com amortecimento $[0.9, 1.1]$ e fallback seguro.
- [x] Isenção formal de dados pessoais (LGPD / sem PII).
- [x] Documento salvo estritamente em `.agents/docs/business_rules/analytics-produto-novo.md`.
