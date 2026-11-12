# Regras de Negócio: Tendência de Vendas por Item (`analytics-sales-trend`)

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-sales-trend.md`
> **Responsável:** Analista (`business-rules-expert`)
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`

## Revisão 2026-11-09 (checkpoint)

Decisões do usuário no checkpoint, aplicadas a este documento. Nenhuma P-XXX foi renumerada; a sub-regra revogada (P-081.3) mantém o número com a nota de revogação.

| # | Mudança | Regras, CAs e premissas afetados |
| :-: | :--- | :--- |
| 1 | **Premissas A-1 a A-5 e A-17 a A-19 aceitas como estão** (usuário). | Seção 6 (A-1, A-2, A-3, A-5, A-17, A-18, A-19 marcadas como aceitas; A-4 reescrita, item 2) |
| 2 | **Produtos inativos NÃO existem na feature** (sem filtro e sem selo). Só entram na tabela e nas somas de fornecedor os produtos do catálogo **ativo** atual (`Externo01.Produto` com `Pc.Venda > 0`). Produto com venda no histórico mas fora do catálogo ativo (descontinuado ou sem cadastro) é excluído de tudo, inclusive da soma do fornecedor. **Consequência registrada:** os totais históricos de um fornecedor ignoram os produtos descontinuados e, por isso, não reconciliam com o faturamento total da base. | **P-072** (declaração, P-072.2 a P-072.5), P-081 (P-081.3 revogada, P-081.5), P-082, P-084 (P-084.1, P-084.2, P-084.6), P-085.1, P-086 (P-086.3, P-086.4, P-086.7), P-087.3, P-088.2, P-089 (P-089.2 a P-089.4), P-091 (P-091.1, P-091.6), P-092 (P-092.2, P-092.3), P-093; **constantes**; **C-18, C-19, C-36, C-40, C-47**; **CA-12 a CA-18, CA-30 a CA-35, CA-39**; massa sintética (SKUs 1008 e 1009 excluídos); **A-4 e A-22 reescritas como decisão fechada**, A-26 ajustada; glossário. O parâmetro `activeOnly` e o selo "Inativo" deixam de existir. |
| 3 | **Feature independente do cross-sell** (módulo próprio, branch a partir de `main`): nenhuma regra depende de `analytics-cross-sell.md`, de P-058 a P-071, de `XSL`/`ANL` nem de código do módulo `analytics`. (a) `ANL-001` (503) virou **`TND-004`** e `ANL-002` (429) virou **`TND-005`**. (b) **P-083** reescrita de forma autocontida (TTL 6 h, voo único, `force_reload` com intervalo mínimo de 15 min, mês corrente congelado até a recarga). (c) **P-081.1** e **P-081.4** descrevem a normalização, a validação da busca e a paginação por regra explícita. (d) Referências a outros módulos, a P-058..P-071 e a nomes de arquivos de outros módulos removidas; `Externo01.Vendas`, `Externo01.Produto` e a devolução (D4) ficam citadas só como fatos da base. | P-072.4, P-073.1, P-073.3, P-074, P-077.4, P-081.1, P-081.4, **P-082** (tabela e P-082.3), **P-083** (todas), P-084 (declaração), P-085.2, P-086.1, P-087.2, P-089.1, P-092.1, P-093; **C-28, C-52 (nova)**; **CA-23, CA-41 (novo)**; A-3, A-13, A-14; constantes; seção 1 |
| 4 | **Navegação:** a tela é uma **página própria** (`/tendencia-vendas`, item próprio na navbar), não uma aba do shell Analytics. Só as menções de "aba" foram ajustadas. | Metadados (campo Feature), seção 1 |

---

| Campo | Valor |
| :--- | :--- |
| **Feature** | Página própria "Tendência de Vendas" (rota `/tendencia-vendas`, item próprio na navbar): tabela de todos os SKUs ativos, ou fornecedores, com a variação % de vendas nas janelas de 1, 3, 6 e 12 meses |
| **Módulo** | Módulo próprio da feature (backend e frontend), **independente de qualquer outra feature** do projeto: tem o próprio repositório somente leitura, cache, exceções, handler e envelope. Nome e estrutura de pastas ficam com o Arquiteto |
| **Regras novas** | P-072 a P-093 (P-088 a P-093 acrescentadas em 2026-11-09 pelo requisito "ver por produto ou por fornecedor") |
| **Regras reaproveitadas** | Nenhuma. A feature não depende de regras, códigos de erro nem código de outra feature |
| **Origem** | Pedido do usuário (2026-11-09) e fatos da base: `Externo01.Vendas`, `Externo01.Produto` e devolução abatida (D4) |
| **Autor** | Analista (Etapa 1; revisão do checkpoint em 2026-11-09) |
| **Status** | Especificado e revisado no checkpoint; premissas A-1 a A-5 e A-17 a A-19 aceitas; demais aguardam confirmação (seção 6) |

---

## 1. Contexto e Objetivo

- **User Story Relacionada:** US-TND — *Como comprador/gestor da Fitoherb, quero ver todos os produtos com a variação percentual de vendas em 1, 3, 6 e 12 meses, ordenável, para identificar rapidamente o que mais cresce e o que mais cai.*
- **Pedido literal do usuário:** "Uma feature para fazer uma relação dos itens que tiveram maior crescimento de vendas e maior queda de vendas. Deve ser uma tabela com todos os itens com uma coluna da % de crescimento ou queda dos últimos 1, 3, 6 e 12 meses."
- **Objetivo da Feature:** responder "quais SKUs ativos (ou quais fornecedores, somando só os SKUs ativos) mais cresceram e quais mais caíram", em quantidade líquida **ou** faturamento líquido, na visão **por produto** (padrão) ou **por fornecedor** com os produtos do fornecedor agrupados e a contribuição de cada um (P-088 a P-093), comparando cada janela de X meses (que termina no Mês-Base) com a janela imediatamente anterior, de mesmo tamanho, de forma honesta quando a base não cobre o período inteiro (início da base em jan/2025, mês corrente parcial).
- **Atores Envolvidos:** Comprador / gestor / time comercial (consulta), Sistema (ERP SQL Server, somente leitura).
- **Independência:** a feature não depende de nenhuma outra feature do projeto. Tudo o que ela usa está definido neste documento; só `Externo01.Vendas`, `Externo01.Produto` e a devolução abatida (D4) são fatos da base.
- **Fora do escopo:** produtos fora do catálogo ativo (descontinuados ou sem cadastro; ficam fora de tudo, P-072.2); previsão de vendas futuras; análise de sazonalidade; causa da variação (preço, promoção, canibalização); correção inflacionária; exportação CSV; qualquer dado por cliente; agrupamento por categoria (`Tipo`) ou por outros eixos além de produto e fornecedor (podem virar evolução futura).
- **Vocabulário:** o usuário diz "item"; nas regras vale o termo do Glossário, **SKU** (rótulo de tela sugerido: "Produto"). O rótulo "Novo" na tabela significa "sem venda líquida na janela anterior" e **não** se confunde com "produto novo hipotético" (avaliação de viabilidade de um produto ainda não cadastrado, outra iniciativa).

---

## 2. Catálogo de Regras de Negócio (P-XXX)

> [!IMPORTANT]
> Os parâmetros abaixo DEVEM existir como constantes nomeadas no topo do módulo de domínio da feature (ex.: `sales_trend.py`; sem números mágicos). Valores marcados "Premissa A-n" estão na seção 6.

### Tabela de constantes

| Constante | Valor | Regra | Situação |
| :--- | :--- | :--- | :--- |
| `SALE_OPERATION` / `RETURN_OPERATION_PATTERN` | `'VENDA'` / `'DEVOLU%'` | P-073 | Fato da base (o acento de `[Operação]` chega corrompido no driver, por isso o padrão) |
| `ACTIVE_PRODUCT_MIN_PRICE` (exclusivo) | `0` (ativo = `Pc.Venda > 0`) | P-072.2 | Decidido (usuário, 2026-11-09) |
| `WINDOW_SIZES_MONTHS` | `(1, 3, 6, 12)` | P-075 | Decidido (usuário) |
| `TREND_SPAN_MONTHS` | `24` (2 × maior janela) | P-072, P-075 | Derivado |
| `DEFAULT_METRIC` | `'revenue'` | P-073 | Decidido (usuário) |
| `DEFAULT_SORT_WINDOW` | `3` | P-080 | Premissa A-12 |
| `MIN_PREVIOUS_COVERAGE_RATIO` | `0.5` | P-076 | Premissa A-2 |
| `PERCENT_DECIMALS` | `1` | P-077 | Premissa A-11 |
| `LOW_BASE_MIN_QUANTITY` | `10` (un) | P-079 | Premissa A-7 (calibrar com dados reais) |
| `LOW_BASE_MIN_REVENUE` | `500.00` (R$) | P-079 | Premissa A-7 (calibrar com dados reais) |
| `DEFAULT_MIN_VOLUME` | `0` (não filtra) | P-079 | Decidido (usuário: "padrão sem filtrar") |
| `DEFAULT_PAGE_LIMIT` / `MAX_PAGE_LIMIT` | `50` / `200` | P-081.4 | Decidido |
| `MIN_SEARCH_LENGTH_DIGITS` / `MIN_SEARCH_LENGTH_TEXT` / `MAX_SEARCH_LENGTH` | `1` / `2` / `60` | P-081.1 | Decidido |
| `CACHE_TTL_HOURS` | `6` | P-083.2 | Decidido |
| `MIN_RELOAD_INTERVAL_MINUTES` | `15` | P-083.2 | Decidido |
| `DEFAULT_GROUP_BY` | `'product'` | P-088 | Decidido (usuário) |
| `NO_SUPPLIER_LABEL` / `NO_SUPPLIER_KEY` | `'Sem fornecedor'` / chave reservada | P-089.2 | Decidido (usuário) |

---

### `P-072`: Quais SKUs entram na tabela

- **Declaração Mandatória:** O sistema DEVE listar **todo SKU ativo com movimento** (ao menos uma linha de VENDA ou de devolução) em qualquer mês do período de análise `[Mês-Base − 23 meses, Mês-Base]` (`TREND_SPAN_MONTHS = 24`, a união das oito janelas). SKU que não está no catálogo ativo NÃO existe para a feature (P-072.2). Não há "top N".
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-072.1** | **Movimento** é existência de linha em `Externo01.Vendas` com `[Operação] = 'VENDA'` ou `LIKE 'DEVOLU%'` no período, mesmo que o líquido seja 0 (ex.: venda e devolução do mesmo valor). SKU sem nenhuma linha no período não aparece (não há o que comparar). SKU cuja única venda ocorre **depois** do Mês-Base não entra (nada vaza do futuro do Mês-Base). |
| **P-072.2** | **Só SKUs ativos entram (decisão fechada do usuário, 2026-11-09).** SKU ativo = registro em `Externo01.Produto` com `Pc.Venda > 0` no catálogo atual. SKU com venda ou devolução no histórico que não é ativo (descontinuado, com `Pc.Venda ≤ 0`, ou sem registro em `Externo01.Produto`) é **excluído de tudo**: da tabela por produto, da soma e dos filhos de qualquer fornecedor e da busca. Não existe filtro, selo nem opção de incluí-los. **Consequência registrada:** os totais históricos de um fornecedor **ignoram os produtos descontinuados**; a soma dos fornecedores não reconcilia com o faturamento total da base, e uma queda causada só pela retirada de linha de um produto não aparece. O status é o do catálogo **atual**, aplicado a todo o histórico do SKU (produto reativado entra com todo o seu histórico; produto desativado sai com todo o seu histórico). |
| **P-072.3** | **Exemplo numérico (massa da seção 5, Mês-Base out/26, `quantity`, 1m):** o fornecedor LABORATÓRIO BETA vende o SKU 1007 (1 → 3 un) e o SKU 1008 (40 → 0 un, `Pc.Venda = 0`). O 1008 é excluído: Beta = só o 1007, anterior = 1, atual = 3, **+200,0%** com `baseBaixa`. Se o 1008 contasse, Beta seria (3 − 41) ÷ 41 = −92,7%. O SKU 1009 (15 → 25 un, sem registro em `Produto`) também fica fora de tudo. |
| **P-072.4** | O catálogo ativo é lido de `Externo01.Produto` com `WHERE [Pc.Venda] > 0` e projeção mínima `Codigo, Descricao, Fornecedor`. A exclusão dos não ativos é feita **no domínio**, pela interseção entre o agregado de vendas (`Cod Produto × mês`) e o catálogo ativo do mesmo snapshot; a consulta de vendas não filtra por ativo nem faz `JOIN` (P-093). `descricao` e `fornecedor` vêm do catálogo ativo; `fornecedor` pode ser nulo ou vazio (grupo "Sem fornecedor", P-089.2). |
| **P-072.5** | Um SKU aparece **uma única vez** na tabela, com as quatro janelas (1, 3, 6, 12) em colunas. O conjunto de linhas não muda com a coluna de ordenação (muda só com Mês-Base, `q`, `view`, `minVolume`). Na visão por fornecedor (`groupBy = supplier`), este conjunto de SKUs ativos é o **universo** que alimenta a soma dos fornecedores e seus filhos (P-088 a P-092). |

---

### `P-073`: Métrica, origem dos dados e líquido de devoluções

- **Declaração Mandatória:** O sistema DEVE calcular a tendência sobre a **quantidade líquida** (`metric = quantity`, soma de `[Qtd Venda]`) ou o **faturamento líquido** (`metric = revenue`, soma de `[Valor Venda]`), sempre **líquidos de devolução** (decisão D4): líquido = soma das linhas `VENDA` + soma das linhas `LIKE 'DEVOLU%'`. O padrão é `revenue`.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-073.1** | O abatimento é **aritmético**: devoluções já vêm com quantidade e valor negativos (fato da base: todas as devoluções têm quantidade negativa, verificado em 2026-11-05) e são somadas com o sinal original, sem `ABS` nem inversão. Uma devolução com sinal positivo na base não é tratada especialmente (a base é a fonte de verdade); há teste de regressão com devolução negativa. |
| **P-073.2** | Uma devolução é atribuída ao **mês da própria devolução** (campo `[Data]` da linha), não ao mês da venda original. Motivo: simplicidade e rastreabilidade; efeito pequeno (~0,4% do faturamento). |
| **P-073.3** | A agregação DEVE ocorrer no SQL Server no grão `Cod Produto × mês` (`YEAR([Data])*100+MONTH([Data])`), uma única consulta com `WHERE ([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%') AND [Data] < ?` (corte exclusivo = P-076.1), `GROUP BY [Cod Produto], mês`, sem `CONCAT`, validada pelo verificador de consulta somente leitura do núcleo do projeto (`is_readonly_query`), com parâmetros vinculados e leitura em blocos (`fetchmany`). Nenhuma linha bruta chega ao Python (o ambiente de execução já estourou memória com vendas brutas). A consulta NÃO filtra por produto ativo nem faz `JOIN` com `Externo01.Produto` (P-072.4). A consulta NÃO seleciona `Cod Cliente`, `Pedido` nem qualquer outra coluna além de `Cod Produto`, `Data`, `Qtd Venda`, `Valor Venda` e `Operação` (esta só no filtro). |
| **P-073.4** | O faturamento é **nominal** (R$ do dia da venda, sem correção inflacionária). Crescimento de faturamento mistura volume e preço; por isso a quantidade é oferecida como métrica alternativa. A tela DEVE rotular a métrica ativa ("Faturamento líquido (R$)" / "Quantidade líquida (un)"). (Premissa A-9.) |
| **P-073.5** | Trocar a métrica reaproveita os mesmos dados em cache (o agregado carrega quantidade e faturamento juntos); não dispara nova leitura do banco. |

---

### `P-074`: Mês-Base

- **Declaração Mandatória:** O sistema DEVE calcular tudo a partir de um **Mês-Base** (`baseMonth`, formato `AAAA-MM`) que termina todas as janelas atuais. O padrão é o **último mês completo**; o usuário PODE escolher qualquer mês entre o primeiro mês com dados e o mês corrente (inclusive, parcial).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-074.1** | **Mês-Base padrão** (`mesBasePadrao`) = mês anterior ao mês da `dataReferencia` do snapshot (P-083). Em 2026-11-09, o padrão é `2026-10`. |
| **P-074.2** | **Mês-Base máximo** (`mesBaseMaximo`) = mês da `dataReferencia` (o mês corrente, parcial). **Mês-Base mínimo** (`mesBaseMinimo`) = mês da primeira data de VENDA da base (hoje `2025-01`, lido do banco, nunca fixo no código). A API devolve os três valores em `meta` para a tela montar o seletor. |
| **P-074.3** | Escolher o mês corrente é permitido e produz **Base Parcial** (P-076): a janela atual cobre só os dias fechados do mês. A tela DEVE indicar no seletor e no cabeçalho "mês corrente, parcial: dados até DD/MM". |
| **P-074.4** | Mês-Base **posterior** ao mês da `dataReferencia` (futuro) → **400** `TND-001` (campo `baseMonth`). Mês-Base com formato inválido → **400** `TND-001`. |
| **P-074.5** | Mês-Base **anterior ao mês da primeira venda** → **422** `TND-002`. Mês-Base igual ao mês corrente quando ainda não há nenhum dia fechado nele (dia 1 do mês, P-076.1) → **422** `TND-002`. Mês-Base igual ao primeiro mês com dados é válido (janeiro/2025 já é parcial, pois a base começa em 07/01). |
| **P-074.6** | Sem `baseMonth` na requisição, vale `mesBasePadrao`. O Mês-Base escolhido é válido para as quatro colunas ao mesmo tempo. |

---

### `P-075`: Janelas de X meses (atual e anterior)

- **Declaração Mandatória:** Para cada `X ∈ {1, 3, 6, 12}`, o sistema DEVE definir a **Janela Atual** como os X meses civis consecutivos que terminam no Mês-Base e a **Janela Anterior** como os X meses civis imediatamente anteriores, de mesmo tamanho, **independentemente do ano**.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-075.1** | `atual(X) = [M − X + 1, M]` e `anterior(X) = [M − 2X + 1, M − X]`, em meses civis inteiros (do dia 1 ao último dia de cada mês), com M = Mês-Base. A aritmética atravessa a virada de ano. |
| **P-075.2** | As quatro janelas são independentes; a janela de 3 meses **não** é composta da de 1 mês. Elas se sobrepõem (a atual de 1 mês está dentro da atual de 3). |
| **P-075.3** | Cada janela tem `diasJanela` = número de dias corridos dos meses que a compõem (ex.: set/26 = 30). |

- **Exemplos (Mês-Base = out/2026, conforme o usuário):**

| X | Janela Atual | Janela Anterior |
| :-: | :--- | :--- |
| 1 | out/26 | set/26 |
| 3 | ago–out/26 | mai–jul/26 |
| 6 | mai–out/26 | nov/25–abr/26 |
| 12 | nov/25–out/26 | nov/24–out/25 |

- **Exemplos (Mês-Base = nov/2026, mês corrente, hoje = 2026-11-09):**

| X | Janela Atual | Janela Anterior |
| :-: | :--- | :--- |
| 1 | nov/26 (só 01 a 08/11) | out/26 |
| 3 | set–nov/26 | jun–ago/26 |
| 6 | jun–nov/26 | dez/25–mai/26 |
| 12 | dez/25–nov/26 | dez/24–nov/25 |

---

### `P-076`: Cobertura da base, base parcial e normalização

- **Declaração Mandatória:** O sistema DEVE medir quantos dias de cada janela a base realmente cobre. Quando as **duas** janelas estão 100% cobertas, compara **totais**; quando alguma está incompleta, compara a **média diária** sobre os dias cobertos e marca a célula como **Base Parcial**; quando a Janela Anterior tem cobertura insuficiente, a célula é **Sem Base**. Nunca devolve 0% nem erro por falta de histórico.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-076.1** | **Período coberto da base** = de `primeiraData` (primeira data de VENDA na base) até o **último dia fechado**, que é a `dataReferencia` do snapshot **menos 1 dia** (o dia corrente é parcial e fica fora; o corte do SQL é `[Data] < dataReferencia`). Em 2026-11-09, o último dia coberto é 2026-11-08. (Premissa A-3.) |
| **P-076.2** | **Dias cobertos** de uma janela = dias corridos da janela que caem dentro do período coberto. **Cobertura** = `diasCobertos ÷ diasJanela`. Dias sem venda dentro do período coberto contam como cobertos (venda zero é informação). |
| **P-076.3** | **Ambas as janelas com cobertura 100%:** `valor = total líquido da janela`; a variação compara totais. (Janelas de meses com número de dias diferente, ex.: fev vs jan, são comparadas pelo total: efeito de calendário aceito. Premissa A-1.) |
| **P-076.4** | **Alguma janela com cobertura < 100%** (e a Anterior com cobertura ≥ `MIN_PREVIOUS_COVERAGE_RATIO` = 50%): `valor = total líquido ÷ diasCobertos` (média diária) nas **duas** janelas; a variação compara as médias diárias; a célula recebe `baseParcial = true` (selo "Base parcial" com tooltip "janela anterior com X de Y dias" ou "mês-base parcial: X de Y dias"). Motivo: comparar total de 8 dias com total de 30 dias seria uma queda falsa de ~73%. |
| **P-076.5** | **Janela Atual:** basta ter **pelo menos 1 dia coberto** (garantido pelo P-074.5); não há mínimo de cobertura, pois o mês-base parcial é escolha explícita do usuário e vem sinalizado. Só o mês corrente deixa a Janela Atual incompleta (se a Anterior tem ≥ 50% de cobertura, a Atual já está inteira, exceto no mês corrente). |
| **P-076.6** | **Janela Anterior com cobertura < `MIN_PREVIOUS_COVERAGE_RATIO` (inclui 0%, totalmente fora da base):** a célula é **Sem Base** (`status = SEM_BASE`), exibida como "—" com selo "Sem base", `variacaoPct = null`. Motivo do corte de 50%: com poucos dias, a média diária da janela anterior é ruído (ex.: 1 dia de 365 daria variação sem sentido). (Premissa A-2.) |
| **P-076.7** | O cálculo de cobertura é **por janela**: a janela de 12 meses pode ser Base Parcial enquanto a de 1 mês é completa, e uma janela pode ser Sem Base enquanto as outras têm variação. |
| **P-076.8** | A média diária usa **dias corridos**, não dias úteis (não há calendário de feriados na base). Limitação conhecida: fins de semana desiguais entre os recortes distorcem levemente médias de janelas curtas e parciais (Premissa A-10). |

- **Exemplo numérico (SKU 1001 da massa da seção 5; hoje = 2026-11-09, primeira venda = 2025-01-07, Mês-Base = out/26, janela de 12 meses):**
  - Atual nov/25–out/26: 365 dias, 365 cobertos (100%), total líquido = **250 un**.
  - Anterior nov/24–out/25: 365 dias; cobertos = 25 (07–31/jan/25) + 273 (fev a out/25) = **298** (81,6% ≥ 50%); total líquido = 8 + 9×10 = **98 un**.
  - Anterior incompleta → média diária: atual 250 ÷ 365 = 0,6849; anterior 98 ÷ 298 = 0,3289; variação = **+108,3%**, `baseParcial = true`. (Comparar totais daria +155,1%, inflado só porque a base começa em 07/01.)
- **Exemplo (Mês-Base = nov/26, janela de 1 mês):** atual nov/26: 4 un em 8 dias cobertos de 30 → 0,5/dia; anterior out/26: 30 un ÷ 31 dias = 0,9677/dia → variação **−48,3%**, `baseParcial = true` (selo "mês-base parcial: 8 de 30 dias"). Sem a normalização, o total (4 vs 30) mostraria −86,7%.

---

### `P-077`: Cálculo do % de variação

- **Declaração Mandatória:** O sistema DEVE calcular a variação como `(atual − anterior) ÷ |anterior| × 100`, onde `atual` e `anterior` são os valores da métrica escolhida (totais ou médias diárias, conforme P-076), **após o piso zero** do líquido negativo.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-077.1** | **Piso zero:** se o líquido de uma janela for negativo (devoluções superam as vendas daquele recorte), o valor usado no cálculo é **0** e a célula recebe `devolucaoLiquida = true` (selo "Devoluções superam vendas"). O valor líquido bruto (negativo) continua exposto em `atual`/`anterior` para o tooltip. Motivo: evitar percentuais abaixo de −100% ou com sinal enganoso. (Premissa A-5.) |
| **P-077.2** | A fórmula só é aplicada quando `anterior > 0` (após o piso). Com `anterior ≤ 0` valem P-078. Como `|anterior| = anterior` nesse caso, o módulo é registrado na fórmula apenas por clareza/robustez. |
| **P-077.3** | **Piso de −100%:** SKU com `atual = 0` e `anterior > 0` tem variação **exatamente −100,0%** ("parou de vender"). Não existe variação menor que −100%. O teto é ilimitado (+200%, +1.500% são válidos; o sinalizador de Base Baixa, P-079, trata o ruído). |
| **P-077.4** | **Arredondamento:** `PERCENT_DECIMALS = 1` casa decimal, **meio para cima sobre a magnitude** (arredondamento decimal `ROUND_HALF_UP` a partir do texto do número, descartando o ruído binário de ponto flutuante, sem `round()` binário). 12,25 vira 12,3; −12,25 vira −12,3. A ordenação (P-080) usa o valor **sem** arredondar; a API devolve o valor arredondado em `variacaoPct`. |
| **P-077.5** | Variação que arredonda para 0,0 é exibida "0,0%" sem sinal e permanece `status = VARIACAO` (não é "sem movimento"). |
| **P-077.6** | O cálculo roda **por janela e por SKU** a partir do agregado mensal; nenhuma regra de variação vive no router nem no componente Angular (domínio puro, sem I/O). |

---

### `P-078`: Estados de uma célula (casos de borda)

- **Declaração Mandatória:** Toda célula (SKU × janela) DEVE ter exatamente um `status`, avaliado nesta ordem de precedência; nenhum estado produz erro HTTP.

| Ordem | `status` | Condição | `variacaoPct` | Exibição |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `SEM_BASE` | Janela Anterior com cobertura < 50% (P-076.6) | `null` | "—" + selo "Sem base" |
| 2 | `VARIACAO` | `anterior > 0` (após piso zero) | número (P-077) | "+50,0%", "−100,0%" |
| 3 | `NOVO` | `anterior = 0` e `atual > 0` (após piso zero) | `null` | Rótulo "Novo" |
| 4 | `SEM_MOVIMENTO` | `anterior = 0` e `atual = 0` (após piso zero) | `null` | "—" (sem movimento) |

- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-078.1** | **Novo:** SKU sem venda líquida positiva na Janela Anterior e com venda líquida positiva na Atual (produto lançado, retomado após pausa, ou vendas anteriores só devolvidas). Variação indefinida (divisão por zero): **não** é +∞%, não é 100%. Fica **fora do cálculo de ordenação por %** (P-080.2) mas **presente** na tabela. Tooltip: "Sem venda líquida na janela anterior (produto novo ou retomado)". Exemplo: SKU 1002 com 0 un em set/26 e 40 un em out/26. |
| **P-078.2** | **Parou:** `anterior > 0` e `atual = 0` é `VARIACAO` = −100,0% (P-077.3). Exemplo: SKU 1003 com 50 un em set/26 e 0 em out/26. |
| **P-078.3** | **Sem movimento:** as duas janelas com líquido 0 (inclui SKU cujo único movimento está em outra janela, ex.: venda só em mar/25 e janela 1 mês). Permanece na tabela (P-072.1) com "—". Exemplo: SKU 1006. |
| **P-078.4** | **Devolução supera venda na Atual:** `atual < 0` vira 0 (piso) e, com `anterior > 0`, a variação é −100,0% com `devolucaoLiquida = true`. Exemplo: SKU 1004, set/26 = 20 un e out/26 = VENDA 5 − DEVOLU 12 = −7 un: −100,0% com o selo. |
| **P-078.5** | **Líquido negativo na Anterior:** `anterior < 0` vira 0 (piso); se `atual > 0`, é `NOVO` com `devolucaoLiquida = true`; se `atual = 0`, é `SEM_MOVIMENTO` com `devolucaoLiquida = true`. Exemplo: SKU 1005, set/26 = VENDA 2 − DEVOLU 5 = −3 un e out/26 = 10 un: `NOVO` com selo. |
| **P-078.6** | O estado `SEM_BASE` (precedência 1) vale para **todos** os SKUs da janela, inclusive os que têm venda na Atual; a Atual continua exposta em `atual` para o tooltip. |
| **P-078.7** | Se as quatro janelas forem `SEM_BASE` (Mês-Base muito próximo do início da base, ex.: jan/2025), a resposta é **200** com a tabela completa de "—" e `meta.janelas[].semBase = true`; a tela explica "histórico anterior insuficiente para este mês-base". Não é erro. |

---

### `P-079`: Base Baixa e volume mínimo

- **Declaração Mandatória:** O sistema DEVE listar todos os SKUs mesmo com volume pequeno, mas DEVE sinalizar `baseBaixa = true` nas células `VARIACAO` cuja Janela Anterior tem volume pequeno e oferecer um filtro opcional de **volume mínimo** (padrão: não filtrar).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-079.1** | **Base Baixa:** célula `VARIACAO` com **valor líquido total** (não a média diária) da Janela Anterior **< `LOW_BASE_MIN_QUANTITY` (10 un)** quando `metric = quantity`, ou **< `LOW_BASE_MIN_REVENUE` (R$ 500,00)** quando `metric = revenue`. Selo "Base baixa" com tooltip "poucas vendas na janela anterior; o percentual pode exagerar". Exemplo: SKU 1007, 1 un em set/26 e 3 un em out/26 = +200,0% com `baseBaixa = true`. (Premissa A-7: valores a calibrar com a distribuição real antes do release.) |
| **P-079.2** | O sinalizador **não altera** o cálculo, a ordenação nem a presença do SKU; é informativo. `NOVO`, `SEM_MOVIMENTO` e `SEM_BASE` nunca recebem `baseBaixa`. |
| **P-079.3** | **Volume mínimo (`minVolume`)**: número ≥ 0, padrão `DEFAULT_MIN_VOLUME = 0` (não filtra). Na unidade da métrica ativa (un ou R$). Quando > 0, remove da lista os SKUs cuja célula **na janela de ordenação (`sortWindow`)** é `VARIACAO` e tem Janela Anterior (valor líquido total) **< `minVolume`**. Células `NOVO`, `SEM_MOVIMENTO` e `SEM_BASE` **não** são filtradas por `minVolume` (não têm percentual exagerado a conter). |
| **P-079.4** | O filtro é aplicado **antes** da paginação (P-081), e `totalItems` reflete a lista filtrada. `minVolume` negativo ou não numérico → **400** `TND-001`. |
| **P-079.5** | Trocar a métrica NÃO converte `minVolume` entre unidades e reais; a tela DEVE zerar/reaplicar o campo e exibir a unidade (un ou R$) ao lado dele. |

---

### `P-080`: Ordenação, visões e desempate

- **Declaração Mandatória:** A tabela DEVE ser ordenável por qualquer uma das quatro colunas de % (`sortWindow ∈ {1, 3, 6, 12}`), em ordem decrescente (maiores altas primeiro) ou crescente (maiores quedas primeiro), de forma estável e determinística.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-080.1** | Padrão: `sortWindow = DEFAULT_SORT_WINDOW (3)`, `sortDir = desc` (Premissa A-12). `sortDir ∈ {asc, desc}`. A ordenação em coluna de % usa a **variação sem arredondar** da coluna escolhida. |
| **P-080.2** | **Ordem de grupos (fixa, independe de `sortDir`):** primeiro as células `VARIACAO` (ordenadas por %), depois `NOVO`, depois `SEM_BASE`, por último `SEM_MOVIMENTO`. As células sem % **nunca** disputam posição com as que têm %, nem no sentido ascendente. Dentro de `NOVO`, `SEM_BASE` e `SEM_MOVIMENTO`: valor `atual` decrescente e código crescente. |
| **P-080.3** | **Desempate de % igual** (fixo, independe de `sortDir`): maior variação **absoluta** `|atual − anterior|` (na mesma base da comparação: total ou média diária) primeiro; persistindo, menor código crescente. Motivo: entre vários −100,0%, aparece primeiro o que perdeu mais venda. |
| **P-080.4** | **Visões (atalhos "maiores altas" / "maiores quedas")**, sempre relativas à `sortWindow`: `all` (padrão), `rising` (só `VARIACAO` com % > 0; sentido padrão `desc`), `falling` (só `VARIACAO` com % < 0; sentido padrão `asc`, a pior queda primeiro) e `new` (só `NOVO`; ordenados por `atual` decrescente). Quando `sortDir` é informado explicitamente, prevalece sobre o padrão da visão. A tela expõe as visões como controle segmentado "Todos / Maiores altas / Maiores quedas / Novos". `VARIACAO` com % = 0,0 aparece só em `all`. |
| **P-080.5** | Em `rising`/`falling`/`new` o filtro é aplicado antes da paginação (`totalItems` refletente). A mesma resposta contém sempre as quatro colunas, qualquer que seja a coluna de ordenação. |
| **P-080.6** | `sortWindow`, `sortDir` ou `view` fora dos valores permitidos → **400** `TND-001`. |

---

### `P-081`: Busca e paginação

- **Declaração Mandatória:** A lista DEVE ser paginada (`limit` padrão 50, máximo 200, e `offset`), filtrável por busca textual, com os filtros aplicados antes da paginação.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-081.1** | **Busca `q` (opcional), regra autocontida.** (a) **Normalização:** tanto o termo digitado quanto o texto pesquisado passam por decomposição Unicode (NFKD) com remoção das marcas de acento ("chá" = "cha", "açaí" = "acai"), conversão para minúsculas, remoção de espaços nas pontas e colapso de espaços repetidos em um só. (b) **Tamanho, após a normalização:** se `q` tem só dígitos, de `MIN_SEARCH_LENGTH_DIGITS` (1) a `MAX_SEARCH_LENGTH` (60) caracteres; nos demais casos, de `MIN_SEARCH_LENGTH_TEXT` (2) a 60. (c) **Casamento na visão por produto:** `q` só com dígitos casa quando o código do SKU é **igual** a `q` ou **começa com** `q`; caso contrário, casa quando a descrição normalizada **contém** `q`. (d) A busca só **filtra**; a ordem continua a de P-080, sem prioridade de "começa com" sobre "contém". Só SKUs ativos são pesquisados (P-072.2). |
| **P-081.2** | `q` inválido (vazio após trim não conta como inválido: equivale a sem filtro; curto demais ou > 60 caracteres é inválido) → **400** `TND-001` (campo `q`). |
| **P-081.3** | *(Revogada em 2026-11-09.)* O filtro "somente ativos" não existe: produtos fora do catálogo ativo não fazem parte da feature (P-072.2). O número é mantido para não renumerar o catálogo. |
| **P-081.4** | **Paginação (regra autocontida):** `limit` inteiro de 1 a `MAX_PAGE_LIMIT` (200), padrão `DEFAULT_PAGE_LIMIT` (50); `offset` inteiro ≥ 0, padrão 0; `page = floor(offset ÷ limit) + 1`; `totalPages = teto(totalItems ÷ limit)` (0 sem itens); `offset ≥ totalItems` devolve **200** com `data` vazio e os totais corretos. `limit`/`offset` inválidos → **400** `TND-001` (não há truncamento silencioso). |
| **P-081.5** | Ordem de aplicação: universo de SKUs ativos (P-072) → `q` → `view` → `minVolume` → ordenação (P-080) → paginação. |

---

### `P-082`: Validação de parâmetros e erros `TND`

- **Declaração Mandatória:** Toda entrada da rota DEVE ser validada antes de tocar na regra de negócio (o backend não confia no frontend); erros de regra são lançados como exceções de domínio próprias da feature, traduzidas por um handler global (sem `try/catch` por rota), com código interno `TND-NNN` e HTTP semântico, sem stacktrace e sem ecoar o valor recebido.

| Código | HTTP | Quando | Mensagem ao usuário |
| :--- | :--- | :--- | :--- |
| `TND-001` | 400 | `baseMonth` fora do formato `AAAA-MM` (mês 01 a 12) ou posterior ao mês da `dataReferencia`; `metric` fora de `quantity\|revenue`; `sortWindow` fora de `{1,3,6,12}`; `sortDir` fora de `asc\|desc`; `view` fora de `all\|rising\|falling\|new`; `q` inválido; `minVolume` negativo ou não numérico; `limit`/`offset` fora da faixa; `groupBy` fora de `product\|supplier`; `supplierKey` ausente na rota de detalhe; `sortBy` do detalhe fora de `contribution\|variation` (P-088, P-092). O corpo lista os campos inválidos | `"Parâmetros inválidos: {campos}."` |
| `TND-002` | 422 | Mês-Base anterior ao mês da primeira venda da base, ou mês corrente sem nenhum dia fechado (P-074.5), ou base de vendas vazia | `"O mês-base escolhido não possui dias com vendas registradas na base."` |
| `TND-003` | 404 | Rota de detalhe (P-092) com `supplierKey` que não corresponde a nenhum fornecedor do universo de SKUs ativos no Mês-Base informado (inclui fornecedor que sumiu ao trocar o Mês-Base) | `"Fornecedor não encontrado no período analisado."` |
| `TND-004` | 503 | Base de vendas indisponível (conexão, driver, configuração), sem detalhe do driver | `"Base de vendas indisponível no momento. Tente novamente em instantes."` |
| `TND-005` | 429 | Recarga manual (`force_reload`) pedida antes de `MIN_RELOAD_INTERVAL_MINUTES` (15 min) desde a última carga (P-083.2) | `"A base foi recarregada recentemente. Tente novamente mais tarde."` |

- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-082.1** | **Ordem de validação:** (1) formato e domínio dos parâmetros → `TND-001`; (2) obtenção do snapshot (P-083) → `TND-004` (ou `TND-005` em recarga manual antecipada); (3) Mês-Base vs `dataReferencia` e `primeiraData` → `TND-001` (futuro) ou `TND-002` (antes da base); (4) só na rota de detalhe, `supplierKey` inexistente no universo → `TND-003`. |
| **P-082.2** | Resultado vazio legítimo (nenhum SKU casa com os filtros, `offset` além do fim, visão sem itens) é **200** com `data` vazio, nunca 404/422. |
| **P-082.3** | **Nota ao Arquiteto:** os erros de validação, inclusive os detectados pelo próprio framework (tipo e faixa dos parâmetros), DEVEM sair como `TND-001` no corpo de erro padrão da feature, e não no 422 genérico do framework. O Arquiteto decide o mecanismo (validação no domínio/DTO da própria rota ou handler da feature) e registra no contrato. (Premissa A-13.) |
| **P-082.4** | A mensagem NÃO inclui o valor recebido de `q` nem de `baseMonth`, só o nome do campo (P-085.2). |

---

### `P-083`: Cache, concorrência e mês parcial

- **Declaração Mandatória:** O agregado mensal por SKU DEVE ficar em um **snapshot em memória** com TTL de **6 h**, voo único sob lock, troca atômica e recarga manual (`force_reload`) com intervalo mínimo de 15 minutos. A regra é autocontida (P-083.1 a P-083.7).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-083.1** | **Snapshot próprio e imutável da feature.** Conteúdo: agregado `Cod Produto × mês → (quantidade líquida, faturamento líquido)` (~1,9 mil SKUs × ~23 meses, ~44 mil linhas), catálogo ativo de P-072.4 (`Codigo, Descricao, Fornecedor`), `primeiraData`, `dataReferencia`, `ultimoDiaCoberto` e `loadedAt`. Agregado e catálogo são lidos na **mesma carga**. A estrutura de pastas e o módulo de cache ficam a critério do Arquiteto. |
| **P-083.2** | **Validade, voo único e recarga manual.** (a) **TTL** de `CACHE_TTL_HOURS` (6 h): com 6 h exatas desde `loadedAt` o snapshot já expirou. (b) **Voo único:** requisições simultâneas com cache vazio ou expirado disparam **uma única** carga; as demais aguardam o lock e reutilizam o resultado. (c) **Troca atômica:** o novo snapshot só substitui o anterior após carga bem-sucedida; se a carga falhar, o snapshot anterior (se houver) permanece e o erro `TND-004` é propagado. (d) **Recarga manual** (`force_reload`): respeita o lock; quem chega durante uma carga em andamento reaproveita o resultado; um pedido feito antes de `MIN_RELOAD_INTERVAL_MINUTES` (15 min) desde a última carga é recusado com **429** `TND-005` sem tocar no banco. |
| **P-083.3** | **Mês corrente (parcial):** o agregado é cortado em `[Data] < dataReferencia` (só dias fechados), e o total do mês corrente fica **congelado até o próximo recarregamento** (no máximo 6 h). `dataReferencia` e `ultimoDiaCoberto` pertencem ao **snapshot**, nunca ao relógio da requisição; toda cobertura (P-076) e o `mesBasePadrao` (P-074.1) são derivados dessas datas. Assim, resposta e rótulo "dados até DD/MM" são sempre coerentes entre si. A `dataReferencia` é a data de negócio em UTC-3 (fuso do negócio), calculada no instante da carga. |
| **P-083.4** | Uma requisição feita logo após a meia-noite com snapshot ainda válido continua usando a `dataReferencia` anterior (a tela mostra "dados até" a data correta); a recarga ocorre ao expirar o TTL ou por `force_reload`. Não há invalidação por virada de dia (Premissa A-14: recomendação, reavaliável). |
| **P-083.5** | **Nada de SQL por requisição:** janelas, percentuais, filtros, ordenação e paginação são calculados em memória a partir do snapshot. O resultado ordenado de `(baseMonth, metric, groupBy)` PODE ser memoizado dentro do snapshot e descartado com ele (opcional, decisão do Arquiteto). |
| **P-083.6** | Qualquer verificação de saúde ou consulta do estado do cache (opcional, decisão do Arquiteto) NÃO pode disparar carga do banco. |
| **P-083.7** | O mecanismo de recarga manual (`force_reload`) é exposto de forma a ser acionável por quem opera o sistema (forma e rota definidas pelo Arquiteto); os erros possíveis são `TND-004` (base indisponível) e `TND-005` (intervalo mínimo). A recarga não altera o conteúdo do contrato da lista. |

---

### `P-084`: Envelope de resposta e conteúdo mínimo

- **Declaração Mandatória:** Toda resposta 2xx DEVE seguir o envelope `{ "data": [...], "meta": {...} }` em `camelCase`. Os nomes abaixo são sugestões; o Arquiteto os confirma em `api_contracts/analytics-sales-trend.md` (sugestão de rota: `GET /api/v1/sales-trend`; prefixo e módulo definidos pelo Arquiteto).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-084.1** | **Parâmetros de entrada** (todos opcionais): `baseMonth`, `metric`, `sortWindow`, `sortDir`, `view`, `q`, `minVolume`, `limit`, `offset` (mais `groupBy`, P-084.6). |
| **P-084.2** | **Item de `data`** (um por SKU ativo): `codigo`, `descricao`, `fornecedor` e `janelas[]` com 4 objetos `{ meses (1\|3\|6\|12), atual, anterior, variacaoPct, status, baseParcial, baseBaixa, devolucaoLiquida }`. `atual`/`anterior` são os **totais líquidos** brutos da métrica (podem ser negativos), mesmo quando a variação usa a média diária. `variacaoPct` é número com 1 casa ou `null`. `status` ∈ `VARIACAO`, `NOVO`, `SEM_MOVIMENTO`, `SEM_BASE`. |
| **P-084.3** | **`meta`:** `timestamp`, `page`, `limit`, `offset`, `totalItems`, `totalPages`, `dataReferencia`, `ultimoDiaCoberto`, `mesBase`, `mesBasePadrao`, `mesBaseMinimo`, `mesBaseMaximo`, `metrica`, `mesBaseParcial` (boolean) e `janelas[]` com, para cada X: `meses`, `atual` e `anterior` (`inicio`, `fim`, `diasJanela`, `diasCobertos`) e `semBase`. A tela usa `meta.janelas` para montar os cabeçalhos "ago–out/26 vs mai–jul/26" e os selos. |
| **P-084.4** | A resposta NÃO contém dados de cliente (P-085), custos nem estoque. |
| **P-084.5** | O texto dos selos e tooltips é montado conforme P-086; onde (domínio ou frontend) é decisão do Arquiteto, mas os números vêm como campos estruturados. |
| **P-084.6** | **Visão por fornecedor** (`groupBy = supplier`): `data` traz uma linha por fornecedor com `fornecedor`, `fornecedorChave`, `qtdProdutos` e as mesmas `janelas[]` (sem `codigo`/`descricao`); `meta` mantém os campos de P-084.3. O detalhe do fornecedor tem rota própria (P-092). `groupBy` entra na lista de parâmetros de P-084.1. |

---

### `P-085`: Privacidade (LGPD) e logs

- **Declaração Mandatória:** Esta feature NÃO DEVE tratar dado de pessoa natural: a consulta e a resposta não contêm `Cod Cliente`, `Pedido`, nome, documento, endereço ou contato.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-085.1** | A consulta do repositório projeta apenas `Cod Produto`, `Data` (para derivar o mês), `Qtd Venda` e `Valor Venda` (e `Operação` no filtro); o catálogo, apenas `Codigo, Descricao, Fornecedor` (com `Pc.Venda` só no filtro `> 0`, P-072.4). |
| **P-085.2** | É proibido logar o DataFrame, a lista de SKUs, o conteúdo de `data` ou os parâmetros da requisição (`q` incluído). Logs só com contagens e duração (SKUs, meses, linhas do agregado, tempo de carga, `dataReferencia`) e o tipo (nunca a mensagem) da exceção de driver. |
| **P-085.3** | Não há persistência em disco nem em serviço externo (só cache em memória do processo). |
| **P-085.4** | Como não há dado pessoal, a feature dispensa RIPD e `privacy_officer` dedicado (bypass justificado); a checagem de P-085.1 e P-085.2 fica com o `reviewer`. |

---

### `P-086`: Apresentação (pt-BR) e estados de tela

- **Declaração Mandatória:** A tela DEVE apresentar os números em pt-BR sem depender de cor para transmitir direção, e DEVE tratar todos os estados interativos.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-086.1** | **Percentual:** 1 casa decimal, vírgula decimal, ponto de milhar, sinal explícito (`+` / `−`) exceto em 0,0%: `+50,0%`, `−100,0%`, `+1.250,5%`, `0,0%`. Rótulos: `Novo` e `—` conforme P-078. A direção também vem por ícone (▲ / ▼) e texto, além de cor (verde/vermelho), para acessibilidade. A formatação pt-BR fica em utilitário/pipe do próprio frontend da feature (o componente não formata). |
| **P-086.2** | **Valores no tooltip:** quantidade como inteiro pt-BR com `un` (até 2 casas se a base tiver fração); faturamento como `R$ 1.234,56`; sempre com o período ("ago–out/26: R$ 12.300,00 · mai–jul/26: R$ 10.500,00"). Quando a variação usou média diária, o tooltip mostra também "média por dia" e os dias cobertos. |
| **P-086.3** | **Selos** (cada um com texto, não só cor): "Base parcial", "Base baixa", "Sem base", "Devoluções superam vendas". Não existe selo para produto fora do catálogo ativo (esses produtos não aparecem, P-072.2). Uma mesma célula pode ter mais de um selo. |
| **P-086.4** | **Controles:** alternador de métrica (Faturamento líquido padrão / Quantidade líquida), seletor de Mês-Base (de `mesBaseMinimo` a `mesBaseMaximo`, padrão `mesBasePadrao`, mês corrente rotulado "parcial até DD/MM"), controle segmentado de visão (P-080.4), busca por código ou descrição (P-081.1), "Volume mínimo" com a unidade da métrica, cabeçalhos de coluna clicáveis (alternam desc/asc) e paginação. |
| **P-086.5** | **Estados:** carregando (skeleton), vazio (nenhum SKU casa com os filtros, com ação "limpar filtros"), erro (`TND-001` a `TND-005` com mensagem da API, nunca stacktrace), "histórico anterior insuficiente" (P-078.7). A tela mostra "Dados até DD/MM/AAAA" (`ultimoDiaCoberto`). |
| **P-086.7** | **Visão por fornecedor:** alternador "Por produto / Por fornecedor" (padrão por produto) ao lado do alternador de métrica; cada linha de fornecedor é expansível (acordeão/linha filha); ao expandir, a tela chama a rota de detalhe (P-092) e mostra os produtos com a própria % nas 4 janelas e a contribuição em **pontos percentuais** ("+14,3 p.p.") e em valor (un ou R$), com ícone ▲/▼ e texto, não só cor. A linha do fornecedor mostra `qtdProdutos`. O grupo "Sem fornecedor" é rotulado assim e não recebe tratamento visual de erro. Trocar `groupBy` mantém Mês-Base, métrica, `sortWindow` e `sortDir`; zera `view`, `minVolume` e `q` se não fizerem sentido no novo modo (a tela informa). Fornecedor expandido cujo detalhe devolve 404 `TND-003` é recolhido com aviso. |
| **P-086.6** | O componente só desenha; formatação, ordenação e filtros ficam em service/utilitário; o estado da consulta (Mês-Base, métrica, ordenação, visão, página) reflete em uma única chamada à API. Trocar a métrica NÃO exige nova leitura do banco (P-073.5). |

---

### `P-087`: Critério de aceite quantitativo (massa sintética conhecida e reconciliação)

- **Declaração Mandatória:** O sistema DEVE ser validado por testes automatizados sobre uma **massa sintética com resposta conhecida** (seção 5), que inclui devolução na série, janela de 12 meses parcialmente fora da base, Mês-Base parcial, SKU Novo, SKU que parou, base baixa e líquido negativo, e por uma **reconciliação** com o banco real.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-087.1** | **Massa sintética:** a tabela da seção 5 (SKUs 1001 a 1010; o 1008, descontinuado, e o 1009, sem cadastro, existem na massa para provar a exclusão de P-072.2) com `dataReferencia = 2026-11-09`, `primeiraData = 2025-01-07`. Os testes de domínio usam o agregado mensal (DataFrame/dict) sem banco; os testes de repositório usam conexão mockada e validam que a SQL passa por `is_readonly_query`, não usa `CONCAT`, usa parâmetro vinculado e não referencia `Cod Cliente`/`Pedido`. |
| **P-087.2** | **Todo teste de série inclui a devolução** (SKU 1001, set/26) para garantir o abatimento. |
| **P-087.3** | **Reconciliação (manual, no PR):** para o Mês-Base padrão, a soma de `atual` da janela de 1 mês de todos os SKUs listados (faturamento e quantidade) DEVE ser igual à soma direta no SQL de `VENDA + DEVOLU%` do mês **restrita a produtos com `Pc.Venda > 0`**; a diferença para o total do mês (vendas de produtos fora do catálogo ativo, excluídas por P-072.2) DEVE ser reportada no PR em valor e em %, junto com o número de SKUs listados e o de SKUs excluídos, de células `NOVO`/`SEM_BASE` e a calibração de P-079.1 (distribuição real do volume da Janela Anterior). |
| **P-087.4** | Cobertura de testes ≥ 80% nas regras P-072 a P-093. |
| **P-087.5** | **Massa de fornecedores:** a seção 5 atribui fornecedores aos SKUs 1001 a 1010 (tabela "Fornecedores da massa"); os testes de agrupamento verificam que a soma dos filhos é igual à linha do fornecedor em todas as janelas (P-089.3, P-090.4). |

---

### `P-088`: Alternador de agrupamento (`groupBy`)

- **Declaração Mandatória:** O sistema DEVE oferecer a mesma tabela em duas visões, escolhidas por `groupBy ∈ {product, supplier}`: **por produto** (padrão, `DEFAULT_GROUP_BY = product`, regras P-072 a P-087) ou **por fornecedor**, em que cada linha é um fornecedor com seus produtos agrupados (P-089 a P-093).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-088.1** | `groupBy` ausente equivale a `product`; valor fora de `product\|supplier` → **400** `TND-001` (campo `groupBy`). |
| **P-088.2** | Valem nas duas visões, com o mesmo significado: Mês-Base (P-074), `metric` (P-073), as quatro colunas e o cálculo de P-075 a P-078, `sortWindow`/`sortDir` (P-080), `view`, `minVolume`, `q`, `limit`/`offset`; o universo de SKUs (P-072) é o mesmo nas duas visões. Na visão por fornecedor, `q` busca o **nome do fornecedor** (P-091.2). |
| **P-088.3** | A visão por produto NÃO muda de comportamento por causa de `groupBy`; os números de um SKU são idênticos nas duas visões (a linha filha de um fornecedor é a mesma linha da visão por produto, mais a contribuição). |
| **P-088.4** | A troca de `groupBy` é uma consulta à mesma rota da lista, sem nova leitura do banco (P-073.5, P-093.3). |

---

### `P-089`: Linha de fornecedor — identidade, soma e estados

- **Declaração Mandatória:** Na visão por fornecedor, a linha do fornecedor DEVE ser calculada sobre a **soma líquida de todos os SKUs do fornecedor em cada janela**, aplicando depois P-076 a P-078 à soma. O sistema NÃO DEVE calcular a variação do fornecedor como média (simples ou ponderada) das variações percentuais dos produtos.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-089.1** | **Identidade:** o fornecedor é o campo `Fornecedor` de `Externo01.Produto` do **catálogo atual** (P-072.4). Duas grafias que diferem só por maiúsculas, acentos ou espaços (trim e colapso) são o **mesmo** fornecedor (chave = texto normalizado pela mesma regra de P-081.1(a)); o nome exibido é a grafia de menor ordem alfabética (ordinal) entre as encontradas, para ser determinístico. Cada fornecedor aparece **uma única vez**. (Premissa A-20.) |
| **P-089.2** | **Sem fornecedor:** SKU ativo com `Fornecedor` nulo, vazio ou só espaços no catálogo ativo (P-072.4) entra no grupo **"Sem fornecedor"** (`NO_SUPPLIER_LABEL`), que é uma linha normal da tabela (sem tratamento de erro) com chave reservada `NO_SUPPLIER_KEY`. (Premissa A-21.) |
| **P-089.3** | **Soma:** para cada janela, `atualF = Σ atual` e `anteriorF = Σ anterior` dos SKUs **ativos** do fornecedor no universo (P-072; SKUs fora do catálogo ativo não entram na soma, P-072.2), usando o **líquido bruto** de cada SKU (sem piso zero por SKU: um SKU com devoluções acima das vendas reduz a soma, como ocorre de fato). Em seguida valem a cobertura e a base de comparação de P-076 (totais ou média diária), o piso zero **do fornecedor** de P-077.1 (`devolucaoLiquida`) e a fórmula de P-077. |
| **P-089.4** | **Estados do fornecedor** (mesma tabela de P-078, aplicada a `atualF`/`anteriorF`): `SEM_BASE`, `VARIACAO` (`anteriorF > 0`), `NOVO` (`anteriorF = 0` e `atualF > 0`) e `SEM_MOVIMENTO`. **"Novo" só ocorre quando a soma líquida da janela anterior de TODOS os produtos do fornecedor é zero**: um fornecedor com um produto novo e outros com vendas na anterior é `VARIACAO` (o produto novo entra na soma, só que sem % própria na linha filha). Produto ativo novo ou retomado dentro do fornecedor entra na soma como qualquer outro; produto descontinuado NÃO entra (P-072.2), e por isso o fornecedor "Novo" também só considera produtos ativos. |
| **P-089.5** | **Cobertura e base parcial:** a cobertura (P-076.2) depende só das janelas, igual para todos os SKUs; logo, o fornecedor herda `baseParcial` e `SEM_BASE` exatamente como os produtos (janela anterior < 50% coberta = `SEM_BASE` na linha do fornecedor e em todos os filhos; Mês-Base parcial ou anterior parcialmente fora da base = média diária e selo "Base parcial"). |
| **P-089.6** | **Base Baixa do fornecedor:** P-079.1 aplicado ao `anteriorF` total (mesmos limiares). Um filho com base baixa continua exibindo o próprio selo e **continua somado** (o selo é informativo). |
| **P-089.7** | **Fornecedor que mudou:** não há histórico de fornecedor na base; vale o fornecedor do catálogo atual para **todo** o histórico do SKU (as vendas antigas de um SKU migram com ele). Limitação registrada. (Premissa A-17.) |
| **P-089.8** | O número de SKUs do fornecedor no universo é exposto como `qtdProdutos`. |

- **Exemplo (massa da seção 5, Mês-Base out/26, `metric = quantity`, 1m, fornecedor "LABORATÓRIO ALFA" com 1001 e 1003):** 1001 vai de 20 a 30 un (**+50,0%**) e 1003 de 50 a 0 (**−100,0%**). Fornecedor: `anteriorF = 70`, `atualF = 30`, variação = **−57,1%** (média das % dos produtos seria −25,0%, errado).

---

### `P-090`: Contribuição do produto para o fornecedor

- **Declaração Mandatória:** Cada produto filho DEVE informar quanto contribuiu para a variação do fornecedor, em **pontos percentuais** (`contribuicaoPp`) e em **valor** (`contribuicaoValor`), por janela, para explicar quem puxou a alta ou a queda.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-090.1** | `contribuicaoPp = (atual − anterior) ÷ anteriorF × 100`, com `atual`/`anterior` do **SKU** (líquido bruto, na mesma base de comparação da janela: totais ou média diária) e `anteriorF` da soma do fornecedor; 1 casa decimal, meio para cima (P-077.4). Positiva = puxou a alta; negativa = puxou a queda. |
| **P-090.2** | `contribuicaoValor = atual − anterior` do SKU, na base de comparação da janela, na unidade da métrica (un ou R$). Quando a célula é `baseParcial`, o valor é **por dia** (média diária), e a tela rotula "por dia" no tooltip. |
| **P-090.3** | **Indefinida:** com `SEM_BASE` (P-089.5), ambos são `null`. Com `anteriorF ≤ 0` (fornecedor `NOVO` ou `SEM_MOVIMENTO`), `contribuicaoPp = null` (divisão por zero) e `contribuicaoValor` é calculado normalmente. Um SKU `NOVO` ou `SEM_MOVIMENTO` na própria linha tem contribuição normal quando `anteriorF > 0` (um SKU `NOVO` com +40 un contribui +40 ÷ `anteriorF`). |
| **P-090.4** | **Fecho da conta:** `Σ contribuicaoValor` dos filhos = `atualF − anteriorF` (brutos) e, sem piso zero no fornecedor, `Σ contribuicaoPp` (sem arredondar) = variação % do fornecedor. Com arredondamento de exibição a soma pode diferir em até 0,1 p.p. Quando o piso zero do fornecedor atua (`devolucaoLiquida = true`), a soma dos p.p. pode ficar abaixo de −100,0 e **não** é igual ao % da linha (o % do fornecedor fica em −100,0%). |
| **P-090.5** | A linha filha mantém a **própria variação** (P-077/P-078, com o piso zero do SKU) ao lado da contribuição, que usa o líquido bruto. Ex.: SKU com atual bruto −7 e anterior 20 mostra −100,0% de variação própria e contribuição de −27 un. |
| **P-090.6** | As contribuições só existem nas linhas filhas (P-092); a lista de fornecedores não as traz. |

- **Exemplo (Alfa, 1m, quantidade):** 1001 contribui `+10 ÷ 70 × 100 =` **+14,3 p.p.** (+10 un); 1003 contribui `−50 ÷ 70 × 100 =` **−71,4 p.p.** (−50 un); soma = −57,1 p.p. = variação do fornecedor.

---

### `P-091`: Lista de fornecedores — busca, filtros, ordenação e paginação

- **Declaração Mandatória:** Na visão por fornecedor, a lista DEVE ser paginada, ordenável pelas quatro colunas, buscável pelo nome do fornecedor, com os mesmos atalhos e filtros da visão por produto aplicados às **linhas de fornecedor**.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-091.1** | **Universo:** fornecedores com pelo menos um SKU **ativo** com movimento no período (P-072); fornecedor cujos produtos com movimento são todos não ativos não aparece. As somas e os filhos consideram só SKUs ativos (P-072.2), sem exceção e sem filtro; o detalhe (P-092) usa o mesmo universo, o que fecha a conta com a linha do fornecedor. (Decisão fechada, antiga premissa A-22.) |
| **P-091.2** | **Busca `q` (por nome do fornecedor):** mesma normalização e validação de tamanho de P-081.1(a) e (b) (sem acento, sem maiúsculas); casa quando o nome normalizado do fornecedor **contém** `q`. `q` só com dígitos também casa por contenção (nomes podem ter números). `q` inválido → **400** `TND-001`. "Sem fornecedor" casa por seu rótulo. A busca não olha os produtos (Premissa A-23). |
| **P-091.3** | **Visões `rising`/`falling`/`new`** (P-080.4) e **`minVolume`** (P-079.3) aplicam-se às linhas de fornecedor: `minVolume` compara com `anteriorF` total da `sortWindow`, só em linhas `VARIACAO`; `NOVO`, `SEM_MOVIMENTO` e `SEM_BASE` não são filtradas. O filtro **nunca** é aplicado aos filhos no detalhe. |
| **P-091.4** | **Ordenação:** P-080 inteira (grupos `VARIACAO` → `NOVO` → `SEM_BASE` → `SEM_MOVIMENTO`, independentemente de `sortDir`; % sem arredondar). **Desempate** de % igual: maior variação absoluta `\|atualF − anteriorF\|` primeiro; depois nome normalizado crescente; depois chave. "Sem fornecedor" não tem posição privilegiada. |
| **P-091.5** | **Paginação:** P-081.4 (`limit` 50, máx 200, `offset`); `totalItems` = número de fornecedores após os filtros. |
| **P-091.6** | **Ordem de aplicação:** universo de SKUs ativos (P-072) → agrupamento por fornecedor (P-089) → `q` → `view` → `minVolume` → ordenação → paginação. |

---

### `P-092`: Detalhe do fornecedor (produtos filhos, paginados, sob demanda)

- **Declaração Mandatória:** Os produtos de um fornecedor NÃO DEVEM vir no payload da lista de fornecedores; DEVEM ser obtidos por **rota de detalhe própria, paginada**, chamada quando o usuário expande a linha. (Premissa A-18.)
- **Justificativa:** um fornecedor pode ter centenas de SKUs; a lista traria até 200 fornecedores × centenas de SKUs × 4 janelas × (variação + contribuição), um payload de dezenas de milhares de objetos para uma tela que normalmente expande uma ou duas linhas. O custo da rota extra é pequeno porque tudo sai do snapshot em memória (P-083.5).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-092.1** | **Rota** (sugestão, o Arquiteto confirma): `GET /api/v1/sales-trend/supplier-products` (mesmo prefixo da lista), com o fornecedor em `supplierKey` na **query string** (o nome pode ter barra, acento e espaço, então não vai no path). `supplierKey` é a `fornecedorChave` devolvida pela lista (valor opaco; `NO_SUPPLIER_KEY` para "Sem fornecedor"). Ausente → **400** `TND-001`; inexistente no universo → **404** `TND-003`. |
| **P-092.2** | **Parâmetros do universo, obrigatórios para fechar a conta com a linha do fornecedor:** `baseMonth`, `metric` (os mesmos da lista). Mais: `sortBy` (`contribution` padrão \| `variation`), `sortWindow`, `sortDir`, `q` (busca de SKU, P-081.1), `limit`, `offset`. `view` e `minVolume` NÃO se aplicam ao detalhe (P-091.3). |
| **P-092.3** | **Filhos** = SKUs do fornecedor no universo (com movimento no período, P-072.1); SKU do fornecedor sem nenhuma linha de venda no período não é listado (contribuição seria 0). Cada filho traz a linha de produto de P-084.2 (código, descrição, 4 janelas) e, por janela, `contribuicaoPp` e `contribuicaoValor` (P-090). |
| **P-092.4** | **Ordenação padrão** (`sortBy = contribution`): por `contribuicaoValor` da `sortWindow` (mesma ordem de `contribuicaoPp`, que só difere por um divisor positivo), com `sortDir = desc` mostrando primeiro quem **mais puxou a alta** e `asc` quem **mais puxou a queda**. Linhas com contribuição `null` (`SEM_BASE`) vão ao final por `atual` decrescente. Empate: código crescente. Com `sortBy = variation`, vale P-080 (grupos e desempate por \|Δ\|, depois código). |
| **P-092.5** | **Paginação:** P-081.4; `totalItems` = número de filhos após `q`. Com `q`, os filhos exibidos podem não somar a linha do fornecedor; `meta.fornecedor` continua trazendo a soma completa. |
| **P-092.6** | **`meta` do detalhe:** campos de P-084.3 mais `meta.fornecedor` = `{ fornecedor, fornecedorChave, qtdProdutos, janelas[] }` com a **mesma** linha de fornecedor que a lista devolve, para a tela conferir e exibir o total acima dos filhos. |
| **P-092.7** | **Coerência lista × detalhe:** como lista e detalhe podem cair em snapshots diferentes (recarga entre as chamadas), o detalhe devolve `dataReferencia` no `meta`; se for diferente da `dataReferencia` da lista exibida, a tela DEVE recarregar a lista (P-086.7). |

- **Exemplo (Alfa, 1m, quantidade, `desc`):** 1001 (+14,3 p.p., +10 un) antes de 1003 (−71,4 p.p., −50 un); em `asc`, 1003 vem primeiro (quem mais puxou a queda).

---

### `P-093`: Agregação e cache para a visão por fornecedor

- **Declaração Mandatória:** O agregado SQL DEVE continuar no grão **`Cod Produto × mês`** (P-073.3), **sem** o fornecedor na consulta; o fornecedor é resolvido **no domínio** por meio do catálogo ativo em cache (P-072.4, P-083.1).
- **Justificativa:** (a) um único agregado alimenta as duas visões e as duas métricas, sem recarga ao alternar; (b) o catálogo já está no snapshot, e o fornecedor muda raramente; (c) a consulta mantém a projeção mínima, sem `JOIN` e sem coluna a mais (P-085.1); (d) a soma por fornecedor exige o líquido **por SKU** de qualquer forma (para os filhos e a contribuição), então agrupar depois é gratuito (~1,9 mil SKUs).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-093.1** | Agrupar por fornecedor, somar as janelas e calcular contribuições é cálculo **em memória por requisição** (lista e detalhe), sobre o snapshot (P-083.5); o resultado de `(baseMonth, metric)` PODE ser memoizado no snapshot e descartado com ele. Nenhum SQL por requisição. |
| **P-093.2** | Catálogo e agregado pertencem ao **mesmo snapshot** (P-083.1), portanto o mapa SKU → fornecedor é sempre o da mesma carga dos totais. Mudança de fornecedor no ERP só aparece na próxima recarga (TTL de 6 h ou `force_reload`). |
| **P-093.3** | Alternar `groupBy`, expandir fornecedores ou trocar `metric` com o snapshot quente NÃO lê o banco; a regra de voo único e a de falha preservando o snapshot (P-083.2) valem para o detalhe também. |
| **P-093.4** | Valem P-085 (sem dado de cliente; logs só com contagens: fornecedores, SKUs, duração; nunca nome de fornecedor nem lista de SKUs). |

---

## 3. Enquadramento LGPD & Privacidade (Art. 7º e 11 da LGPD)

| Dado / Atributo | Classificação LGPD | Base Legal Aplicada | Finalidade Específica e Proporcional |
| :--- | :--- | :--- | :--- |
| `Cod Produto`, `Descricao`, `Fornecedor` (e `Pc.Venda`, só no filtro de catálogo ativo) | Dado de catálogo (não pessoal) | Não se aplica | Identificar o SKU na tabela e restringir ao catálogo ativo |
| Quantidade e valor líquidos por SKU × mês | Dado comercial agregado, sem pessoa natural | Não se aplica | Medir tendência de vendas |
| `Fornecedor` (nome do laboratório/fornecedor, usado no agrupamento) | Dado de catálogo; pessoa jurídica (o campo é nome de fabricante/marca, não de cliente) | Não se aplica | Agrupar SKUs e somar a tendência por fornecedor (P-089). Se aparecer fornecedor que seja pessoa natural, o `reviewer` reavalia |
| `Cod Cliente`, `Pedido`, nome, documento, endereço, contatos | Dado pessoal (indireto no caso de MEI) | **Não tratado** nesta feature | Minimização: não selecionados, não expostos, não logados (P-085) |

> Sem dado pessoal, sem decisão automatizada (Art. 20) e sem sensível: não há RIPD. A conclusão deve ser confirmada pelo `reviewer` contra P-085.

---

## 4. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP |
| :--- | :--- | :--- | :--- |
| **C-01** | Requisição sem parâmetros (hoje 2026-11-09) | Mês-Base `2026-10`, `metric = revenue`, ordenação 3 meses `desc`, `limit 50`, `offset 0` | `200` |
| **C-02** | SKU com venda líquida positiva nas duas janelas completas | `VARIACAO` por totais (P-076.3) | `200` |
| **C-03** | Janela anterior de 12m com 298 de 365 dias cobertos | `VARIACAO` por média diária + `baseParcial` (P-076.4) | `200` |
| **C-04** | Janela anterior totalmente fora da base (ou < 50% coberta) | `SEM_BASE`, "—", nunca 0% (P-076.6) | `200` |
| **C-05** | Mês-Base = mês corrente (09/nov) | Atual cobre 01–08/nov; média diária; `baseParcial`; `mesBaseParcial = true` | `200` |
| **C-06** | Mês-Base = mês corrente no dia 1 | Nenhum dia fechado: `TND-002` | `422` |
| **C-07** | Mês-Base futuro (`2026-12`) | `TND-001` | `400` |
| **C-08** | `baseMonth = "2026-13"` ou `"26-10"` ou `"outubro"` | `TND-001` | `400` |
| **C-09** | Mês-Base `2024-12` (antes da base) | `TND-002` | `422` |
| **C-10** | Mês-Base `2025-01` | Válido; as 4 janelas `SEM_BASE` (P-078.7) | `200` |
| **C-11** | SKU sem venda na anterior e com venda na atual | `NOVO`; fora do cálculo por %, presente na tabela | `200` |
| **C-12** | SKU com venda na anterior e 0 na atual | `VARIACAO = −100,0%` | `200` |
| **C-13** | Ambas as janelas com líquido 0 | `SEM_MOVIMENTO`, "—" | `200` |
| **C-14** | Atual negativa (devoluções > vendas) | Piso 0; −100,0% + `devolucaoLiquida` | `200` |
| **C-15** | Anterior negativa | Piso 0; `NOVO` ou `SEM_MOVIMENTO` + `devolucaoLiquida` | `200` |
| **C-16** | Anterior 1 un, atual 3 un (+200%) | `VARIACAO` com `baseBaixa = true`; presente | `200` |
| **C-17** | `minVolume = 10` (un) | Remove só `VARIACAO` com anterior < 10 na `sortWindow` | `200` |
| **C-18** | SKU descontinuado (`Pc.Venda ≤ 0`) com venda no período | Excluído da tabela, da busca e da soma de qualquer fornecedor; sem filtro nem selo (P-072.2) | `200` |
| **C-19** | SKU em `Vendas` sem cadastro em `Produto` | Excluído de tudo, como o descontinuado (P-072.2) | `200` |
| **C-20** | Três SKUs com −100,0% | Desempate por maior perda absoluta, depois código (P-080.3) | `200` |
| **C-21** | `sortDir = asc` com SKUs `NOVO` e `—` | Grupos sem % continuam depois dos com % | `200` |
| **C-22** | `view = rising` / `falling` / `new` | Filtra por sinal/estado da `sortWindow` | `200` |
| **C-23** | `q = "cha"` | Filtra por descrição sem acento; ordem de P-080 | `200` |
| **C-24** | `q = "a"` (1 letra) ou > 60 caracteres | `TND-001` (campo `q`) | `400` |
| **C-25** | `metric = "profit"`, `sortWindow = 2`, `view = "top"`, `sortDir = "up"` | `TND-001` com o campo | `400` |
| **C-26** | `limit = 0`, `limit = 201`, `offset = −1`, `minVolume = −5` | `TND-001` | `400` |
| **C-27** | `offset ≥ totalItems` | `data` vazio e totais corretos | `200` |
| **C-28** | Banco indisponível | `TND-004`, sem stacktrace | `503` |
| **C-29** | 10 requisições simultâneas com cache vazio | Uma única carga | `200` |
| **C-30** | Trocar `metric` com cache quente | Sem leitura do banco | `200` |
| **C-31** | Devolução com sinal negativo no mês | Subtrai do líquido do mês da devolução (P-073.1, P-073.2) | `200` |
| **C-32** | SKU com venda só depois do Mês-Base | Não aparece (P-072.1) | `200` |
| **C-33** | `groupBy` ausente | Visão por produto (padrão) | `200` |
| **C-34** | `groupBy = "brand"` | `TND-001` (campo `groupBy`) | `400` |
| **C-35** | `groupBy = supplier`, fornecedor com um produto em alta e outro em queda | % do fornecedor sobre a soma líquida, não sobre a média das % (P-089.3) | `200` |
| **C-36** | SKU ativo com `Fornecedor` nulo, vazio ou só espaços | Grupo "Sem fornecedor" (P-089.2) | `200` |
| **C-37** | Duas grafias do mesmo fornecedor ("Alfa Lab", "ALFA  lab ") | Um único fornecedor (P-089.1) | `200` |
| **C-38** | Fornecedor com produto novo e outros já vendendo na janela anterior | Linha `VARIACAO` (não `NOVO`); o produto novo entra na soma (P-089.4) | `200` |
| **C-39** | Fornecedor em que todos os produtos têm venda anterior zero e há venda atual | Linha `NOVO` (P-089.4) | `200` |
| **C-40** | Fornecedor com produto descontinuado | O produto fica fora da soma e dos filhos; os totais históricos do fornecedor ignoram descontinuados (P-072.2, P-089.3) | `200` |
| **C-41** | Janela anterior < 50% coberta (ex.: 6m com Mês-Base 2025-07) | Fornecedor e todos os filhos `SEM_BASE`, contribuições `null` | `200` |
| **C-42** | Mês-Base parcial ou anterior de 12m parcial | Linha do fornecedor em média diária com `baseParcial`; contribuição `por dia` (P-089.5, P-090.2) | `200` |
| **C-43** | Filho com base baixa | Mantém o selo e continua na soma do fornecedor (P-089.6) | `200` |
| **C-44** | Soma dos filhos | `Σ contribuicaoValor = atualF − anteriorF`; `Σ contribuicaoPp` = % do fornecedor (P-090.4) | `200` |
| **C-45** | Fornecedor com piso zero (devoluções > vendas na soma) | % = −100,0% com `devolucaoLiquida`; Σ p.p. pode divergir (P-090.4) | `200` |
| **C-46** | `q` por nome do fornecedor (`groupBy = supplier`) | Filtra fornecedores, sem acento, contém (P-091.2) | `200` |
| **C-47** | Detalhe com `supplierKey` inexistente ou que sumiu ao trocar o Mês-Base | `TND-003` | `404` |
| **C-48** | Detalhe sem `supplierKey` | `TND-001` | `400` |
| **C-49** | Detalhe de fornecedor com centenas de SKUs | Paginado (`limit` 50, máx 200); lista de fornecedores não traz filhos (P-092.1) | `200` |
| **C-50** | Recarga do snapshot entre a lista e o detalhe | Detalhe traz outra `dataReferencia`; a tela recarrega a lista (P-092.7) | `200` |
| **C-51** | Troca `product` ↔ `supplier` ou expansão de fornecedor com cache quente | Sem leitura do banco (P-093.3) | `200` |
| **C-52** | Recarga manual antes de 15 min da última carga | `TND-005`, sem tocar no banco (P-083.2) | `429` |
| **C-53** | `q` casa só com produto fora do catálogo ativo (ex.: código do SKU descontinuado) | `data` vazio, totais corretos (P-072.2, P-081.1) | `200` |

---

## 5. Critérios de Aceitação (CA-xx)

### Massa sintética (P-087.1)

`dataReferencia = 2026-11-09` (último dia coberto 2026-11-08), `primeiraData = 2025-01-07`. Preço de R$ 10,00 por unidade, salvo onde indicado. Valores são **líquidos de devolução** (un). Meses não citados não têm venda.

| SKU | Descrição | Catálogo ativo (`Pc.Venda > 0`) | Movimento |
| :-: | :--- | :-: | :--- |
| **1001** | CHÁ VERDE 100G | sim | jan/25 = 8; fev–out/25 = 10 por mês; nov/25–ago/26 = 20 por mês; **set/26 = VENDA 26 + DEVOLU −6 = 20**; **out/26 = 30 un a R$ 12,00 (R$ 360,00)**; nov/26 (01–08) = 4 |
| **1002** | CÁPSULA DE HIBISCO | sim | out/26 = 40 |
| **1003** | GUARANÁ EM PÓ | sim | set/26 = 50 |
| **1004** | CHÁ BRANCO 50G | sim | set/26 = 20; out/26 = VENDA 5 + DEVOLU −12 = −7 |
| **1005** | MEL SILVESTRE | sim | set/26 = VENDA 2 + DEVOLU −5 = −3; out/26 = 10 |
| **1006** | SPIRULINA 60 CÁPS | sim | mar/25 = 10 |
| **1007** | ÓLEO DE COCO | sim | set/26 = 1; out/26 = 3 |
| **1008** | CHÁ MATE LEGACY | **não** (`Pc.Venda = 0`, descontinuado): **excluído de tudo** | set/26 = 40 |
| **1009** | PRODUTO SEM CADASTRO | **não** (sem registro em `Produto`): **excluído de tudo** | set/26 = 15; out/26 = 25 |
| **1010** | BARRA DE CEREAL | sim | nov/26 (01–08) = 4 |

Em set/26 o SKU 1001 vende a R$ 10,00 (faturamento líquido set/26 = 260 − 60 = R$ 200,00).

**Fornecedores da massa** (usados nos CA-28 a CA-37; `Fornecedor` do catálogo atual):

| Fornecedor (campo `Fornecedor`) | SKUs |
| :--- | :--- |
| `LABORATÓRIO ALFA` | 1001, 1003, 1010 |
| `LABORATÓRIO BETA` | 1007 (o 1008, descontinuado, é excluído; P-072.2) |
| `LABORATÓRIO GAMA` | 1002, 1005 |
| nulo (1004) e `"   "` em branco (1006) | 1004, 1006 → grupo "Sem fornecedor" |

Valores líquidos de 1m (set/26 → out/26, un) usados nos exemplos: 1001: 20 → 30; 1002: 0 → 40; 1003: 50 → 0; 1004: 20 → −7; 1005: −3 → 10; 1006: 0 → 0; 1007: 1 → 3. Os SKUs 1008 (40 → 0) e 1009 (15 → 25) não entram em nenhuma conta.

### Critérios

- **CA-01 — Janelas de meses:** **Dado** Mês-Base `2026-10`, **então** as janelas atual/anterior são out/26 vs set/26 (1m), ago–out/26 vs mai–jul/26 (3m), mai–out/26 vs nov/25–abr/26 (6m) e nov/25–out/26 vs nov/24–out/25 (12m); com Mês-Base `2026-11`: nov/26 vs out/26, set–nov/26 vs jun–ago/26, jun–nov/26 vs dez/25–mai/26, dez/25–nov/26 vs dez/24–nov/25. (P-075)
- **CA-02 — Devolução abatida (quantidade):** **Dado** o SKU 1001 e `metric = quantity`, **então** a janela de 1m (out/26 vs set/26) é **+50,0%** (30 vs 20; se a devolução fosse ignorada seria 30 vs 26 = +15,4%). Janelas 3m = **+16,7%** (70 vs 60), 6m = **+8,3%** (130 vs 120). Todas completas, `baseParcial = false`. (P-073, P-076.3, P-077)
- **CA-03 — Janela de 12m parcialmente fora da base:** **Dado** SKU 1001, `metric = quantity`, Mês-Base `2026-10`, **então** janela 12m = **+108,3%** com `baseParcial = true`, `anterior.diasCobertos = 298` de 365, `atual.diasCobertos = 365`, `anterior` bruto = 98 e `atual` bruto = 250 (média diária 0,6849 vs 0,3289). Comparar totais (+155,1%) é incorreto. (P-076.4)
- **CA-04 — Mês-Base parcial:** **Dado** Mês-Base `2026-11`, SKU 1001, `quantity`, **então** janela 1m = **−48,3%** (4 un em 8 dias vs 30 un em 31 dias) e `baseParcial = true`, `mesBaseParcial = true`, `ultimoDiaCoberto = 2026-11-08`; janela 3m = **+20,0%** (54 un em 69 dias cobertos de 91 vs 60 un em 92 dias), `baseParcial = true`. (P-074.3, P-076.4)
- **CA-05 — Faturamento vs quantidade:** **Dado** SKU 1001 e Mês-Base `2026-10`, **então** janela 1m com `metric = revenue` é **+80,0%** (R$ 360,00 vs R$ 200,00) e com `metric = quantity` é **+50,0%**; o padrão sem `metric` é `revenue`. (P-073)
- **CA-06 — Sem base:** **Dado** Mês-Base `2025-06` (janela anterior de 6m = jul–dez/24, 0% coberta) e `2025-07` (anterior ago/24–jan/25: 25 de 184 dias, 13,6% < 50%), **então** a coluna 6m é `SEM_BASE` ("—", `variacaoPct = null`) para todos os SKUs, nunca 0%, e a resposta é **200**. Com Mês-Base `2025-01` as quatro colunas são `SEM_BASE`, 200. (P-076.6, P-078.7)
- **CA-07 — SKU Novo:** **Dado** o SKU 1002 (0 em set/26 e 40 em out/26), **então** janela 1m é `NOVO`, `variacaoPct = null`, o SKU está na tabela, e **não** disputa posição com SKUs de %: em ordem `desc` e `asc` ele vem após todos os `VARIACAO`. (P-078.1, P-080.2)
- **CA-08 — SKU que parou:** **Dado** o SKU 1003 (50 em set/26 e 0 em out/26), **então** 1m = **−100,0%**. (P-077.3, P-078.2)
- **CA-09 — Sem movimento:** **Dado** o SKU 1006 (só mar/25), **então** 1m é `SEM_MOVIMENTO` ("—") e o SKU continua listado. (P-078.3, P-072.1)
- **CA-10 — Líquido negativo:** **Dado** o SKU 1004, **então** 1m = **−100,0%** com `devolucaoLiquida = true`, `atual` bruto = −7. **Dado** o SKU 1005, **então** 1m é `NOVO` com `devolucaoLiquida = true` e `anterior` bruto = −3. Nenhuma célula tem variação < −100,0%. (P-077.1, P-078.4, P-078.5)
- **CA-11 — Base baixa:** **Dado** o SKU 1007 (1 un → 3 un), **então** 1m = **+200,0%**, `baseBaixa = true`, o SKU está listado e em 1º lugar na ordem `desc`. O SKU 1001 (anterior = 20 un) tem `baseBaixa = false`. Com `metric = revenue`, o limiar é R$ 500,00. (P-079.1)
- **CA-12 — Volume mínimo:** **Dado** `minVolume = 10`, `metric = quantity`, `sortWindow = 1`, **então** o SKU 1007 sai (anterior 1 < 10) e 1001, 1003, 1004 permanecem; `NOVO` (1002, 1005) e `SEM_MOVIMENTO` (1006) permanecem; sem `minVolume` o SKU 1007 permanece. `totalItems` reflete o filtro. (P-079.3)
- **CA-13 — Itens do universo:** **Dado** Mês-Base `2026-10`, **então** `totalItems = 7` (1001 a 1007) e o SKU 1010 (venda só em nov/26) **não** aparece; com Mês-Base `2026-11` o SKU 1010 aparece como `NOVO` (`totalItems = 8`). Os SKUs 1008 e 1009 não aparecem em nenhum Mês-Base (CA-14). (P-072.1, P-072.2)
- **CA-14 — Fora do catálogo ativo (exclusão total):** **Dado** o SKU 1008 (`Pc.Venda = 0`, 40 un em set/26) e o SKU 1009 (sem registro em `Produto`, 15 → 25 un), **então** nenhum dos dois aparece na tabela por produto (nem com selo, nem com filtro), nem nas buscas (`q = "1008"` e `q = "mate"` devolvem 200 com `data` vazio), nem nas somas e nos filhos de fornecedor. Prova numérica: com a exclusão, `LABORATÓRIO BETA` (só o 1007) = **+200,0%** (anterior 1, atual 3); se o 1008 contasse, seria **−92,7%**. Não existe parâmetro de filtro de ativos nem campo de status do produto na resposta. (P-072.2, P-072.3)
- **CA-15 — Ordenação e desempate:** **Dado** `metric = quantity`, `sortWindow = 1`, **então** em `desc`: 1007 (+200,0%), 1001 (+50,0%), 1003, 1004 (os dois −100,0%, desempatados por perda absoluta 50 e 20), depois `NOVO` 1002 (40) e 1005 (10), depois `SEM_MOVIMENTO` 1006. Em `asc`: 1003, 1004, 1001, 1007, 1002, 1005, 1006. (P-080)
- **CA-16 — Visões:** **Dado** a mesma configuração de CA-15, `view = rising` devolve 1007, 1001; `view = falling` devolve 1003, 1004 (em `asc` por padrão); `view = new` devolve 1002, 1005. (P-080.4)
- **CA-17 — Busca:** **Dado** `q = "cha"`, **então** retornam 1001 e 1004 (sem acento, contém; o CHÁ MATE LEGACY, 1008, não aparece por estar fora do catálogo ativo); `q = "1003"` retorna só o 1003; `q = "a"` → 400 `TND-001`. A normalização e os limites de tamanho de P-081.1 valem sem depender de outro módulo. (P-081.1, P-081.2)
- **CA-18 — Paginação:** **Dado** CA-15 em `desc` com `limit = 3&offset = 3`, **então** `data` = 1004, 1002, 1005 e `meta` traz `page = 2`, `totalItems = 7`, `totalPages = 3`, `timestamp`. Sem `limit`, o padrão é 50. `offset = 7` devolve 200 com `data` vazio. (P-081.4)
- **CA-19 — Validação:** `baseMonth = 2026-12` → 400 `TND-001`; `baseMonth = 2026-13`, `metric = profit`, `sortWindow = 2`, `limit = 0`, `limit = 201`, `offset = -1`, `minVolume = -5` → 400 `TND-001` listando o campo; `baseMonth = 2024-12` → 422 `TND-002`; nenhuma resposta de erro contém stacktrace nem o valor recebido. (P-074, P-082)
- **CA-20 — Mês corrente sem dia fechado:** **Dado** `dataReferencia = 2026-11-01` e `baseMonth = 2026-11`, **então** 422 `TND-002`; sem `baseMonth`, o padrão é `2026-10`. (P-074.5, P-076.1)
- **CA-21 — Arredondamento:** **Dado** 400 → 449 (+12,25%) e 400 → 351 (−12,25%), **então** `+12,3%` e `−12,3%`; −0,04% é exibido `0,0%` sem sinal com `status = VARIACAO`; ordenação usa o valor sem arredondar. (P-077.4, P-077.5)
- **CA-22 — Envelope e `meta`:** a resposta traz `data` (com 4 janelas por SKU) e `meta` com `timestamp`, `page`, `limit`, `offset`, `totalItems`, `totalPages`, `dataReferencia`, `ultimoDiaCoberto`, `mesBase`, `mesBasePadrao`, `mesBaseMinimo = 2025-01`, `mesBaseMaximo = 2026-11`, `metrica`, `mesBaseParcial` e `janelas[]` com `diasCobertos`. (P-084)
- **CA-23 — Carga única e TTL:** **Dado** cache vazio e 10 requisições simultâneas, **então** o repositório é chamado uma única vez; antes de 6 h não recarrega; depois de 6 h recarrega; carga com falha mantém o snapshot anterior e devolve 503 `TND-004`. (P-083.2)
- **CA-24 — Métrica sem nova leitura:** **Dado** snapshot quente, **quando** a requisição alterna `quantity` e `revenue`, **então** o repositório não é chamado de novo. (P-073.5, P-083.5)
- **CA-25 — Mês parcial no cache:** **Dado** snapshot carregado em `dataReferencia = 2026-11-09`, **quando** uma requisição chega após a meia-noite dentro do TTL, **então** a resposta usa `dataReferencia = 2026-11-09` e `ultimoDiaCoberto = 2026-11-08` (consistentes com os totais em cache). (P-083.3, P-083.4)
- **CA-26 — SQL segura e privacidade:** a SQL do agregado passa por `is_readonly_query`, não contém `CONCAT`, usa parâmetro vinculado para o corte e **não referencia** `Cod Cliente` nem `Pedido`; os logs da massa de teste não contêm SKUs, `q` ou payload. (P-073.3, P-085)
- **CA-27 — Reconciliação:** no PR, soma de `atual` da janela 1m (Mês-Base padrão) por métrica = soma direta no SQL de `VENDA + DEVOLU%` do mês restrita a produtos com `Pc.Venda > 0`, com a diferença para o total do mês (produtos fora do catálogo ativo) reportada em valor e em %, e a distribuição real do volume da Janela Anterior é apresentada para calibrar P-079.1. (P-087.3)

### Critérios do agrupamento por fornecedor (P-088 a P-093; massa "Fornecedores da massa")

Salvo indicação, `metric = quantity`, Mês-Base `2026-10`, `sortWindow = 1`.

- **CA-28 — Alternador de visão:** `groupBy` ausente devolve linhas de SKU (CA-15 inalterado); `groupBy = supplier` devolve linhas de fornecedor; `groupBy = brand` → 400 `TND-001` (campo `groupBy`). O SKU 1001 tem os mesmos números (1m = +50,0%) nas duas visões (como linha filha no detalhe). (P-088)
- **CA-29 — % sobre a soma, não média das %:** **Dado** `LABORATÓRIO ALFA` (1001: 20 → 30 un; 1003: 50 → 0 un), **então** a linha do fornecedor tem `anterior = 70`, `atual = 30` e 1m = **−57,1%** (e **não** −25,0%, a média de +50,0% e −100,0%); `qtdProdutos = 2`. (P-089.3)
- **CA-30 — Demais fornecedores da massa:** **Então** `LABORATÓRIO BETA` (só o 1007: A = 3, B = 1; o 1008 está fora) = **+200,0%** com `baseBaixa = true` e `qtdProdutos = 1`; `LABORATÓRIO GAMA` (A = 50, B bruto = −3 → piso 0) é `NOVO` com `devolucaoLiquida = true` e `anterior` bruto −3; **Sem fornecedor** (1004 e 1006; A bruto = −7 → piso 0, B = 20) = **−100,0%** com `devolucaoLiquida = true`. (P-089.3, P-089.4, P-077.1)
- **CA-31 — Sem fornecedor:** **Dado** SKU 1004 com `Fornecedor` nulo e SKU 1006 com `Fornecedor = "   "` (ambos ativos), **então** os dois caem no **mesmo** grupo "Sem fornecedor" (`fornecedorChave = NO_SUPPLIER_KEY`), aparece uma única linha e ela casa `q = "sem"`. O SKU 1009, sem registro em `Produto`, **não** entra nesse grupo: está fora de tudo (P-072.2). Duas grafias do mesmo fornecedor ("Alfa Lab" e "ALFA  lab ") formam **um** fornecedor, exibido como "ALFA lab". (P-089.1, P-089.2)
- **CA-32 — Ordenação e paginação de fornecedores:** `desc`: Beta (+200,0%), Alfa (−57,1%), Sem fornecedor (−100,0%), depois Gama (`NOVO`); `asc`: Sem fornecedor, Alfa, Beta, Gama. `limit = 2&offset = 2` em `desc` traz Sem fornecedor e Gama, com `page = 2`, `totalItems = 4`, `totalPages = 2`. `view = falling` devolve Sem fornecedor e Alfa (em `asc`); `view = rising` devolve só Beta; `view = new` devolve Gama. (P-091.4, P-091.5, P-080.4)
- **CA-33 — Filtros do fornecedor:** `q = "alfa"` devolve só Alfa (sem acento, contém); `q = "a"` → 400 `TND-001`. `minVolume = 50` remove Beta (B = 1) e Sem fornecedor (B = 20) e mantém Alfa (B = 70) e Gama (`NOVO`). Não há filtro de ativos: o universo já é só de SKUs ativos (Beta = só o 1007, CA-14). (P-091.1, P-091.2, P-091.3)
- **CA-34 — Contribuição e fecho da conta:** **Dado** o detalhe de Alfa, **então** 1001 tem variação própria **+50,0%**, `contribuicaoValor = +10` e `contribuicaoPp = +14,3`; 1003 tem **−100,0%**, `contribuicaoValor = −50` e `contribuicaoPp = −71,4`. Para Alfa e Beta, `Σ contribuicaoValor = atual − anterior` do fornecedor (−40 e +2) e `Σ contribuicaoPp` sem arredondar = % do fornecedor (−57,1 e +200,0). Beta tem um único filho, o 1007: `+2` / `+200,0 p.p.` (+200,0% próprio, com `baseBaixa = true`, continua somado); o 1008 não aparece (P-072.2). Para Gama, `contribuicaoPp = null` e `Σ contribuicaoValor = +53` (1002: +40; 1005: +13). Para Sem fornecedor, 1004 contribui `−27` / `−135,0 p.p.` e 1006 `0` / `0,0 p.p.`; a soma de p.p. (−135,0) **difere** do −100,0% do fornecedor por causa do piso zero. (P-090)
- **CA-35 — Soma dos filhos = linha do fornecedor:** para **todas** as janelas (1, 3, 6, 12) e os quatro fornecedores, `Σ atual` e `Σ anterior` brutos dos filhos são iguais ao `atual` e `anterior` da linha do fornecedor, em ambas as métricas. (P-089.3, P-090.4, P-087.5)
- **CA-36 — Base parcial no fornecedor (12m):** **Dado** Alfa e Mês-Base `2026-10`, janela 12m, **então** `anteriorF` = 98 un (298 de 365 dias cobertos), `atualF` = 300 un, variação = **+149,9%** (média diária: 300 ÷ 365 vs 98 ÷ 298) com `baseParcial = true`; filhos: 1001 contribui **+108,3 p.p.** (própria +108,3%) e 1003 **+41,7 p.p.** (1003 própria é `NOVO` na janela, mas contribui). Soma = +149,9. (P-089.5, P-090.1, P-090.3)
- **CA-37 — Mês-Base parcial e produto novo dentro do fornecedor:** **Dado** Mês-Base `2026-11` (hoje 2026-11-09), 1m, **então** Alfa tem `qtdProdutos = 3` (1001, 1003, 1010), `atualF` = 8 un em 8 dias cobertos (1,0/dia), `anteriorF` = 30 un em 31 dias (0,9677/dia), variação = **+3,3%**, `baseParcial = true`, status `VARIACAO` (**não** `NOVO`, apesar de 1010 ser `NOVO`); contribuições: 1001 **−48,3 p.p.**, 1003 `0,0 p.p.` (`SEM_MOVIMENTO`), 1010 **+51,7 p.p.** (soma sem arredondar = +3,3). (P-089.4, P-089.5, P-090)
- **CA-38 — Sem base no fornecedor:** **Dado** Mês-Base `2025-07` e janela de 6m (anterior 13,6% coberta), **então** a coluna 6m é `SEM_BASE` na linha de **todos** os fornecedores e de todos os filhos (variação, `contribuicaoPp` e `contribuicaoValor` = `null`), com 200. (P-089.5, P-090.3)
- **CA-39 — Detalhe: rota, paginação e erros:** a lista de fornecedores NÃO traz filhos; o detalhe de Alfa por `sortBy = contribution` traz 1001 e 1003 em `desc` e 1003 e 1001 em `asc`; `q = "verde"` mostra só o 1001 e `meta.fornecedor` continua com `atual = 30`, `anterior = 70`; `meta.dataReferencia` está presente. Fornecedor sintético com 120 SKUs: `limit = 50&offset = 100` devolve 20 itens, `page = 3`, `totalItems = 120`, `totalPages = 3`. `supplierKey` ausente → 400 `TND-001`; chave inexistente (ou de fornecedor que sumiu ao trocar o Mês-Base) → 404 `TND-003`, sem stacktrace nem eco do valor. (P-092)
- **CA-40 — Agregação e cache do agrupamento:** a SQL do agregado **não** referencia `Fornecedor` nem faz `JOIN` com `Produto`; com snapshot quente, alternar `groupBy`, expandir fornecedor e trocar `metric` não chamam o repositório; recarga manual/TTL mantém o voo único; os logs da massa não contêm nome de fornecedor nem SKUs. (P-093, P-085)
- **CA-41 — Recarga manual e intervalo mínimo:** **Dado** um snapshot carregado há 10 min, **quando** `force_reload` é pedido, **então** 429 `TND-005` e o repositório não é chamado; com 15 min ou mais, a recarga ocorre uma única vez mesmo com várias chamadas simultâneas (quem chega durante a carga reaproveita o resultado); recarga com falha mantém o snapshot anterior e devolve 503 `TND-004`. (P-083.2, P-083.7)

---

## 6. Premissas (priorizadas)

Prioridade **Alta** = altera números ou o comportamento visível; **Média** = parâmetro calibrável; **Baixa** = detalhe de apresentação ou técnico.

**Situação no checkpoint de 2026-11-09:** **A-1 a A-5 e A-17 a A-19 foram aceitas pelo usuário como estão** (A-4 foi substituída por uma decisão diferente, ver abaixo). **A-4 e A-22 são decisões fechadas** (produtos fora do catálogo ativo ficam fora da feature). As demais seguem como proposta do Analista, sem bloqueio.

| # | Prio. | Premissa | Valor proposto | Justificativa / Recomendação |
| :--- | :-: | :--- | :--- | :--- |
| A-1 | Alta | Comparação em **totais** quando as duas janelas estão completas; em **média diária** quando alguma está incompleta | Totais se 100%/100%; média diária caso contrário, com selo "Base parcial" | Atende ao conceito do usuário (comparar totais) e evita quedas/altas falsas. Efeito de calendário (fev 28 dias vs jan 31) permanece nas janelas completas; alternativa seria normalizar sempre por dia (mais justo, menos intuitivo) |
| A-2 | Alta | Janela anterior com cobertura < 50% vira "Sem base" ("—") | `MIN_PREVIOUS_COVERAGE_RATIO = 0.5` | 12m de out/26 tem 82% (OK); 6m de jul/25 tem 13,6% (sem base). Valor menor aceita médias de poucos dias (ruído) |
| A-3 | Alta | "Hoje" não entra: último dia coberto = ontem (dia fechado) | `dataReferencia − 1 dia`; no dia 1 o mês corrente dá `TND-002` | Evita média diária distorcida por dia incompleto (o dia corrente ainda está em andamento) |
| A-4 | Alta | **DECISÃO FECHADA (usuário, 2026-11-09):** produtos fora do catálogo ativo NÃO existem na feature, sem filtro e sem selo. Só entram os produtos do catálogo ativo atual (`Externo01.Produto` com `Pc.Venda > 0`); venda histórica de produto descontinuado ou sem cadastro é excluída da tabela e das somas de fornecedor | Excluir (P-072.2, P-072.3) | Substitui a proposta anterior (incluir descontinuados com selo e filtro). **Consequência aceita:** os totais históricos do fornecedor ignoram produtos descontinuados e não reconciliam com o faturamento total da base; a reconciliação do PR (P-087.3) reporta a diferença |
| A-5 | Alta | Líquido negativo numa janela vale 0 no cálculo (piso zero), com selo "Devoluções superam vendas" | Piso zero | Impede % < −100% ou com sinal enganoso |
| A-6 | Média | Rótulo "Novo" para toda célula com anterior = 0 e atual > 0 (inclui produto retomado, não só lançamento) | "Novo", com tooltip explicando | Não há como distinguir lançamento de retomada só pela janela de 1–12 meses |
| A-7 | Média | Limiares de "Base Baixa" | 10 un / R$ 500,00 (anterior total) | Chute informado; calibrar com a distribuição real antes do release (CA-27). Filtro `minVolume` padrão 0 (decidido) |
| A-8 | Média | Início da base: Mês-Base mínimo = mês da primeira venda (jan/2025, parcial a partir de 07/01) | Lido do banco | Janeiro/25 já nasce com 25 de 31 dias; é tratado como Base Parcial |
| A-9 | Média | Faturamento nominal, sem inflação | Nominal | Evita escolha de índice; a métrica de quantidade é o contraponto |
| A-10 | Baixa | Média diária em dias **corridos**, não úteis | Corridos | Sem calendário de feriados; limitação conhecida (fins de semana desiguais em janelas curtas) |
| A-11 | Baixa | Percentual com 1 casa decimal, meio para cima | `PERCENT_DECIMALS = 1` | Legível e suficiente para ranking |
| A-12 | Baixa | Ordenação padrão da tela: coluna de 3 meses, decrescente | `DEFAULT_SORT_WINDOW = 3` | 1 mês é ruidoso, 12 meses é lento; o usuário pode clicar em qualquer coluna |
| A-13 | Baixa (técnica) | Erros de validação do framework (tipo e faixa de parâmetros) precisam sair como `TND-001`, e não no 422 genérico | Arquiteto decide o mecanismo (P-082.3) | Mantém o contrato de erro único da feature |
| A-14 | Baixa | Sem invalidação do cache na virada do dia; mês corrente congelado até 6 h | Só TTL | Rótulo "dados até" garante coerência; recarga manual disponível |
| A-15 | Baixa | Devolução pertence ao mês da própria devolução (não ao mês da venda original) | Mês da devolução | Simplicidade; efeito ~0,4% do faturamento (97% das devoluções têm pedido original, mas o vínculo exigiria o grão `Pedido`) |
| A-16 | Baixa | Visão extra "Novos" além de "Maiores altas/quedas" | Incluída | Custo mínimo; dá visibilidade a quem não tem % |

**Premissas do requisito "por produto / por fornecedor" (P-088 a P-093):**

| # | Prio. | Premissa | Valor proposto | Justificativa / Recomendação |
| :--- | :-: | :--- | :--- | :--- |
| A-17 | Alta | O fornecedor de um SKU é o do **catálogo atual** para todo o histórico (a base não guarda fornecedor histórico) | Catálogo atual | Único dado disponível; SKU que trocou de fornecedor leva todo o histórico para o novo (limitação registrada) |
| A-18 | Alta | Produtos filhos vêm por **rota de detalhe paginada**, carregada ao expandir, e não no payload da lista | Rota de detalhe (P-092) | Fornecedores com centenas de SKUs; payload da lista continua pequeno. Alternativa (filhos embutidos) só serviria se o maior fornecedor tiver poucos SKUs: **conferir a contagem real** antes da Etapa 2 |
| A-19 | Alta | Contribuição = pontos percentuais sobre a base do fornecedor (primária) + valor em un/R$ (secundária) | `contribuicaoPp` e `contribuicaoValor` | p.p. somam o % do fornecedor e tornam "quem puxou" direto; valor dá a ordem de grandeza. Com piso zero no fornecedor a soma de p.p. diverge (documentado) |
| A-20 | Média | Fornecedor = texto de `Fornecedor` normalizado (maiúsculas, acentos, espaços); exibição pela menor grafia ordinal | Normalizado | Evita duplicar fornecedor por erro de digitação; **conferir no catálogo real** se há grafias conflitantes |
| A-21 | Média | "Sem fornecedor" é um grupo normal (nulo, vazio, espaços ou SKU sem cadastro) | Grupo comum | Mantém a soma fechada: nenhum SKU fica fora das duas visões |
| A-22 | Média | **DECISÃO FECHADA (usuário, 2026-11-09):** o universo de SKUs ativos (A-4) vale antes de agrupar, sem filtro opcional; `minVolume` e `view` só atuam sobre as linhas de fornecedor, nunca sobre os filhos | Conforme P-091.1 e P-091.3 | Filhos precisam fechar a conta com a linha do pai. Substitui a antiga proposta de filtro opcional de ativos |
| A-23 | Baixa | Na visão por fornecedor, `q` busca só o nome do fornecedor (não os produtos) | Só nome | Simples; "qual fornecedor vende o produto X" pode virar busca por produto que destaca o fornecedor (evolução) |
| A-24 | Baixa | Filhos listados = SKUs do fornecedor com movimento no período; ordenação padrão do detalhe por contribuição (`desc` = quem mais puxou a alta) | Conforme P-092.3, P-092.4 | Coerente com P-072; SKU sem movimento contribuiria 0 |
| A-25 | Baixa | Limiares de "Base Baixa" do fornecedor = os do SKU (10 un / R$ 500,00) aplicados ao `anteriorF` | Mesmos limiares | Fornecedor raramente cai nesse limite; se for irrelevante, a tela pode ocultar o selo na linha de fornecedor |
| A-26 | Baixa | Ao alternar `groupBy` a tela preserva Mês-Base, métrica, `sortWindow` e `sortDir` | Preservar | Evita o usuário refazer a configuração |

---

## 7. Definition of Done

- [ ] Todas as regras P-072 a P-093 (exceto a P-081.3, revogada) têm testes automatizados (domínio com agregado sintético, repositório com conexão mockada, API com serviço mockado) e cobertura ≥ 80%.
- [ ] CA-01 a CA-26 e CA-28 a CA-41 passam com a massa sintética da seção 5; CA-27 (reconciliação e calibração) reportado no PR, incluindo o maior fornecedor (nº de SKUs) e eventuais grafias duplicadas de fornecedor.
- [ ] Termos alinhados ao `.agents/docs/GLOSSARY.md` (seção 4, Tendência de Vendas).
- [ ] Nenhuma lógica de negócio em router/componentes; domínio puro, sem acesso a banco nem a driver.
- [ ] Feature independente: nenhuma importação de módulo de outra feature e nenhuma dependência de código de erro, cache ou rota de outra feature.
- [ ] Nenhum dado de cliente na consulta, na resposta ou nos logs (P-085).
- [ ] Contrato `api_contracts/analytics-sales-trend.md` publicado pelo Arquiteto antes do TDD.
- [ ] Design Plan `design/plans/analytics-sales-trend.md` publicado pelo Designer antes da implementação do frontend.
