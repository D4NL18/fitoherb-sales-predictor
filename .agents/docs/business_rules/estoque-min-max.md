# Regras de Negócio — Política de Estoque Mínimo/Máximo 30/60 (Previsão de Estoque)

| Campo | Valor |
| :--- | :--- |
| **Feature** | Política de Estoque Mínimo/Máximo por dias de cobertura |
| **Módulo** | `inventory` (Previsão de Estoque e Compras) |
| **Branch** | `feature/P-053-estoque-min-max-30-60` |
| **Regras novas** | P-053, P-054, P-055, P-056 |
| **Regras substituídas** | P-042, P-043, P-044.3, P-045 |
| **Regras revogadas** | P-044.4, P-046.3 |
| **Regras mantidas** | P-041, P-047.1, Curva ABC por receita, custo com fallback, exportação CSV (colunas ajustadas) |
| **Origem** | Discovery de 2026-11-05 (decisões D1–D4 em `.agents/docs/STATE.md`) |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado — aguardando Etapa 2 (Arquitetura) |

---

## 1. Contexto

A Fitoherb Nordeste Distribuidora opera com uma política simples de reposição: **manter sempre entre 30 e 60 dias de estoque de cada produto**. Quando o estoque de um produto cai para o equivalente a 30 dias de venda, compra-se a quantidade necessária para voltar a 60 dias de venda.

O motor atual (P-041 a P-047) usa outro modelo: estoque de segurança estatístico (z-score e nível de serviço), ponto de reposição (ROP), estoque ideal com cobertura alvo única, uma trava percentual de variação física da compra (P-044.4) e um teto orçamentário com priorização (P-046.3). As travas cortam a sugestão de compra e fazem o resultado divergir da política praticada.

Esta especificação substitui o modelo antigo pela **Política Mín/Máx por dias de cobertura**, calculada **apenas com a venda atual (VMD) e o estoque atual**, sem limites de valor ou de variação.

---

## 2. Mapa de rastreabilidade (antes x depois)

| Regra anterior | O que fazia | Situação nesta feature | Regra nova |
| :--- | :--- | :--- | :--- |
| P-041 | VMD = quantidade vendida na janela ÷ dias da janela | **Mantida sem mudança** | Referenciada por P-053.1 |
| P-042 / P-043 | Estoque de segurança = z × desvio-padrão × raiz(lead time); ROP = VMD × lead time + ES | **Substituída** | P-053 |
| P-044.3 | Compra = estoque ideal − estoque atual; gatilho: estoque ≤ ROP ou cobertura ≤ lead time + 5 | **Substituída** | P-054 |
| P-044.4 | Trava % de variação física da compra (teto físico e piso operacional) | **Revogada** | P-056.1 |
| P-045 | Status operacional (ruptura, reposição, excesso acima de 75 dias ou 1,5 × (alvo + lead time)) | **Substituída** | P-055 |
| P-046.3 | Teto orçamentário em R$ com priorização (ruptura > reposição; A > B > C) e corte de quantidades | **Revogada** | P-056.2 |
| P-047.1 | Filtro opcional por fornecedor | **Mantida sem mudança** | — |
| Curva ABC (sem ID próprio) | Classificação global por receita acumulada: A ≤ 80%, B ≤ 95%, C restante | **Mantida sem mudança** | — |
| Custo com fallback (sem ID próprio) | Custo = último custo; se ≤ 0, 60% do preço de venda | **Mantida sem mudança** | Referenciada por P-054.5 |
| Exportação CSV (sem ID próprio) | Plano de compras em CSV (`;`, decimal `,`, BOM UTF-8) | **Mantida com colunas ajustadas** | P-056.5 |

---

## 3. Regras

### P-053 — Política Mínimo/Máximo por dias de cobertura

**Descrição:** O sistema DEVE calcular, para cada produto, um **Estoque Mínimo** e um **Estoque Máximo** em unidades, multiplicando a venda média diária atual pelos dias de cobertura definidos na política (padrão 30 e 60). Esta regra substitui o estoque de segurança, o ROP e o estoque ideal (P-042, P-043, P-044.3).

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-053.1** | A VMD DEVE ser calculada conforme P-041 (sem mudança): `VMD = quantidade vendida na janela ÷ dias da janela`. A janela padrão é **60 dias**, ajustável de **15 a 180 dias**. |
| **P-053.2** | O sistema DEVE aceitar dois parâmetros de política: **Dias Mínimo** (padrão **30**) e **Dias Máximo** (padrão **60**). Ambos são números inteiros de dias, ajustáveis pelo usuário na tela. Os parâmetros valem para todos os produtos do cálculo. |
| **P-053.3** | O sistema DEVE rejeitar a requisição inteira quando **Dias Máximo ≤ Dias Mínimo** ou quando qualquer um deles for menor que 1 ou não for inteiro. Nenhum resultado parcial pode ser devolvido. O erro DEVE indicar o parâmetro inválido. A tela DEVE impedir a aplicação dos parâmetros nessa situação e explicar o motivo, sem corrigir os valores sozinha. |
| **P-053.4** | `Estoque Mínimo (un) = teto(VMD × Dias Mínimo)` |
| **P-053.5** | `Estoque Máximo (un) = teto(VMD × Dias Máximo)` |
| **P-053.6** | Mínimo e máximo DEVEM ser números inteiros de unidades, arredondados **para cima** (teto). O resultado DEVE ser equivalente a `teto(quantidade vendida na janela × dias ÷ dias da janela)`. Ou seja, o arredondamento da VMD para exibição (2 casas) ou para armazenamento intermediário (4 casas) não pode acrescentar unidades, e o teto não pode ser acionado por resíduo de ponto flutuante. |
| **P-053.7** | O cálculo NÃO DEVE usar estoque de segurança estatístico, z-score, nível de serviço nem desvio-padrão da demanda. O lead time NÃO entra no cálculo de mínimo e máximo. |
| **P-053.8** | Quando **VMD = 0** (sem venda na janela), o sistema DEVE definir **mínimo = máximo = 0** e NÃO DEVE sugerir compra. |
| **P-053.9** | O estoque atual negativo vindo do ERP DEVE ser tratado como 0 (comportamento atual mantido). |

**Exemplos numéricos (Dias Mínimo 30, Dias Máximo 60, janela 60 dias, salvo indicação):**

| # | Venda na janela | VMD | Dias Mín./Máx. | Estoque Mínimo | Estoque Máximo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| E1 | 120 un | 2,0 | 30 / 60 | teto(60) = **60** | teto(120) = **120** |
| E2 | 75 un | 1,25 | 30 / 60 | teto(37,5) = **38** | teto(75) = **75** |
| E3 | 30 un | 0,5 | 30 / 60 | **15** | **30** |
| E4 | 120 un | 2,0 | 20 / 45 | **40** | **90** |
| E5 | 1 un | 0,01666… | 30 / 60 | teto(0,5) = **1** | teto(1,0) = **1** (não 2) |
| E6 | 0 un | 0 | 30 / 60 | **0** | **0** |

> E5 ilustra P-053.6: com a VMD gravada em 4 casas (0,0167), o cálculo ingênuo daria `teto(0,0167 × 60) = teto(1,002) = 2`. O correto pela política é **1** (1 unidade cobre exatamente 60 dias).

**Critérios de aceite:**

- **CA-P053-01 — Cálculo padrão**
  - **Dado** um produto que vendeu 120 unidades nos últimos 60 dias (VMD 2,0)
  - **Quando** o cálculo é executado com os parâmetros padrão (30/60)
  - **Então** o Estoque Mínimo é 60 un e o Estoque Máximo é 120 un.
- **CA-P053-02 — Arredondamento para cima**
  - **Dado** um produto com VMD 1,25
  - **Quando** o cálculo é executado com 30/60
  - **Então** o Estoque Mínimo é 38 un e o Estoque Máximo é 75 un.
- **CA-P053-03 — Parâmetros ajustados**
  - **Dado** um produto com VMD 2,0
  - **Quando** o usuário define Dias Mínimo 20 e Dias Máximo 45
  - **Então** o Estoque Mínimo é 40 un e o Estoque Máximo é 90 un.
- **CA-P053-04 — Validação máx. > mín.**
  - **Dado** que o usuário informou Dias Mínimo 60 e Dias Máximo 60 (ou Dias Máximo 45 e Dias Mínimo 50)
  - **Quando** a requisição de cálculo é enviada
  - **Então** a requisição é rejeitada com erro de validação que identifica o parâmetro, e nenhum resultado é devolvido.
- **CA-P053-05 — Validação na tela**
  - **Dado** que o usuário está no modal de parâmetros
  - **Quando** ajusta Dias Máximo para um valor menor ou igual a Dias Mínimo
  - **Então** a ação "Aplicar e Recalcular" fica indisponível e uma mensagem explica que o máximo deve ser maior que o mínimo, sem alterar os valores digitados.
- **CA-P053-06 — Produto sem venda**
  - **Dado** um produto sem vendas na janela (VMD 0)
  - **Quando** o cálculo é executado
  - **Então** Estoque Mínimo = 0, Estoque Máximo = 0 e Quantidade Sugerida = 0.
- **CA-P053-07 — Sem estoque de segurança**
  - **Dado** dois produtos com a mesma VMD (2,0) e volatilidades diferentes (um vende 2 un/dia, outro 10 un a cada 5 dias)
  - **Quando** o cálculo é executado com 30/60
  - **Então** ambos têm Estoque Mínimo 60 e Estoque Máximo 120 (a volatilidade não influencia).
- **CA-P053-08 — Precisão de giro baixo**
  - **Dado** um produto que vendeu 1 unidade nos últimos 60 dias
  - **Quando** o cálculo é executado com 30/60
  - **Então** o Estoque Mínimo é 1 un e o Estoque Máximo é 1 un.

---

### P-054 — Gatilho e quantidade de compra

**Descrição:** O sistema DEVE sugerir compra somente quando o produto tem venda e atingiu o mínimo (ou está em ruptura iminente). A quantidade sugerida DEVE levar o estoque de volta ao máximo, sem cortes, tetos ou travas.

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-054.1** | **Gatilho:** a compra DEVE ser sugerida quando `VMD > 0` **e** (`estoque atual ≤ Estoque Mínimo` **ou** o produto estiver em Ruptura Iminente conforme P-055.2). |
| **P-054.2** | **Quantidade sugerida (com gatilho):** `Quantidade Sugerida = max(0, Estoque Máximo − estoque atual)`, em unidades inteiras. Se o estoque atual for fracionário, a diferença DEVE ser arredondada **para cima** (comportamento atual mantido). |
| **P-054.3** | **Sem gatilho:** a Quantidade Sugerida DEVE ser 0. Inclui o produto com estoque entre o mínimo e o máximo: a política não antecipa compra antes de o estoque chegar ao mínimo. |
| **P-054.4** | A Quantidade Sugerida NÃO DEVE ser reduzida por nenhum limite: sem trava percentual de variação física, sem teto/piso físico, sem teto orçamentário e sem priorização por orçamento (ver P-056). |
| **P-054.5** | **Investimento do item** = `Quantidade Sugerida × Custo Unitário`, com 2 casas decimais. **Custo Unitário** = último custo do produto; se o último custo for ≤ 0 ou ausente, usar **60% do preço de venda**, arredondado a 2 casas (regra atual mantida). Se o custo resultante for 0, o investimento do item é 0 e a quantidade sugerida NÃO é alterada. |
| **P-054.6** | **Investimento Total Sugerido** = soma dos investimentos de todos os itens do resultado (após o filtro de fornecedor P-047.1, quando aplicado). Não há limite máximo. |

**Exemplos numéricos (VMD 2,0; Dias 30/60 → Mínimo 60, Máximo 120; lead time 15; custo R$ 10,00):**

| # | Estoque atual | Dias de cobertura | Gatilho? | Quantidade Sugerida | Investimento |
| :--- | :--- | :--- | :--- | :--- | :--- |
| C1 | 50 | 25,0 | Sim (50 ≤ 60) | 120 − 50 = **70** | R$ 700,00 |
| C2 | 10 | 5,0 | Sim (ruptura iminente e 10 ≤ 60) | 120 − 10 = **110** | R$ 1.100,00 |
| C3 | 0 | 0,0 | Sim (ruptura iminente) | **120** | R$ 1.200,00 |
| C4 | 60 | 30,0 | Sim (60 ≤ 60, limite inclusivo) | **60** | R$ 600,00 |
| C5 | 61 | 30,5 | Não (entre mínimo e máximo) | **0** | R$ 0,00 |
| C6 | 120 | 60,0 | Não | **0** | R$ 0,00 |
| C7 | 150 | 75,0 | Não (acima do máximo) | **0** | R$ 0,00 |
| C8 | 50,4 | 25,2 | Sim | teto(69,6) = **70** | R$ 700,00 |

Exemplo de custo com fallback: último custo R$ 0,00 e preço de venda R$ 25,00 → Custo Unitário = R$ 15,00; com Quantidade Sugerida 70 → investimento R$ 1.050,00.

**Critérios de aceite:**

- **CA-P054-01 — Compra até o máximo**
  - **Dado** um produto com VMD 2,0, estoque 50 un, custo R$ 10,00 e parâmetros 30/60
  - **Quando** o cálculo é executado
  - **Então** a Quantidade Sugerida é 70 un e o investimento do item é R$ 700,00.
- **CA-P054-02 — Ruptura iminente compra até o máximo**
  - **Dado** um produto com VMD 2,0, estoque 10 un e lead time 15 dias
  - **Quando** o cálculo é executado com 30/60
  - **Então** a Quantidade Sugerida é 110 un (sem qualquer teto físico).
- **CA-P054-03 — Limite inclusivo do mínimo**
  - **Dado** um produto com VMD 2,0 e estoque exatamente 60 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** a compra é sugerida e a Quantidade Sugerida é 60 un.
- **CA-P054-04 — Sem compra entre mínimo e máximo**
  - **Dado** um produto com VMD 2,0 e estoque 61 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** a Quantidade Sugerida é 0.
- **CA-P054-05 — Sem corte por volume**
  - **Dado** um produto com VMD 5,0 e estoque 0 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** a Quantidade Sugerida é 300 un (Estoque Máximo), sem limitação por base física ou piso operacional.
- **CA-P054-06 — Sem corte por orçamento**
  - **Dado** um conjunto de produtos cujo investimento total sugerido é R$ 500.000,00
  - **Quando** o cálculo é executado
  - **Então** o Investimento Total Sugerido é R$ 500.000,00 e nenhuma quantidade é reduzida.
- **CA-P054-07 — Custo com fallback**
  - **Dado** um produto com último custo R$ 0,00, preço de venda R$ 25,00 e Quantidade Sugerida 70 un
  - **Quando** o cálculo é executado
  - **Então** o Custo Unitário é R$ 15,00 e o investimento do item é R$ 1.050,00.
- **CA-P054-08 — Total consistente**
  - **Dado** qualquer resultado de cálculo
  - **Quando** os investimentos dos itens são somados
  - **Então** a soma é igual ao Investimento Total Sugerido (tolerância de R$ 0,01).

---

### P-055 — Status operacional (substitui P-045)

**Descrição:** O sistema DEVE classificar cada produto em exatamente um status operacional, comparando o estoque atual com o mínimo e o máximo da política. O lead time é usado **apenas** para sinalizar ruptura iminente.

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-055.1** | **Dias de Cobertura** = `estoque atual ÷ VMD`, arredondado a 1 casa decimal, quando VMD > 0. Quando VMD = 0: **999** se estoque > 0 (exibido como "∞"); **0** se estoque = 0. (Regra atual mantida.) |
| **P-055.2** | O status DEVE ser avaliado na ordem de precedência abaixo; o primeiro critério atendido define o status. |
| **P-055.3** | **Lead Time** (padrão **15 dias**) é apenas um sinalizador de ruptura iminente. Ele NÃO altera mínimo, máximo nem a fórmula da quantidade sugerida. |
| **P-055.4** | **Capital Imobilizado do item** = `(estoque atual − Estoque Máximo) × Custo Unitário`, calculado somente para itens com status OVERSTOCK. O KPI **Capital Imobilizado** (`capitalImobilizadoOverstock`) é a soma dos itens, com 2 casas decimais. Para SKU sem venda (máximo 0), o capital imobilizado é o estoque inteiro × custo. |
| **P-055.5** | Os indicadores (KPIs) DEVEM contar os produtos por status: Ruptura Iminente, Abaixo do Mínimo, Estoque Saudável e Acima do Máximo, além do total de SKUs analisados. |
| **P-055.6** | A ordenação padrão da lista é mantida: status (Ruptura Iminente → Abaixo do Mínimo → Estoque Saudável → Acima do Máximo), depois Curva ABC (A → B → C), depois VMD decrescente. |

**Tabela de status (P-055.2 — ordem de precedência):**

| Ordem | Código | Rótulo exibido | Condição |
| :--- | :--- | :--- | :--- |
| 1 | `CRITICAL_STOCKOUT` | **Ruptura Iminente** | `VMD > 0` e `Dias de Cobertura < Lead Time` |
| 2 | `REORDER_NEEDED` | **Abaixo do Mínimo** | `VMD > 0` e `estoque atual ≤ Estoque Mínimo` e `Quantidade Sugerida > 0` |
| 3 | `OVERSTOCK` | **Acima do Máximo** | `estoque atual > Estoque Máximo` (inclui SKU sem venda com estoque > 0) |
| 4 | `HEALTHY` | **Estoque Saudável** | demais casos: `Estoque Mínimo < estoque atual ≤ Estoque Máximo`; SKU sem venda e sem estoque; caso de borda da linha 2 |

> **Caso de borda (linha 2):** em produtos de giro muito baixo o mínimo pode ser igual ao máximo (ex.: E5, mínimo = máximo = 1). Com estoque = 1, o gatilho de P-054.1 é atendido mas a quantidade é 0. Nesse caso o status é **Estoque Saudável**, porque não há o que comprar. A condição `Quantidade Sugerida > 0` já existia no motor anterior.

**Exemplos numéricos (VMD 2,0; Dias 30/60 → Mínimo 60, Máximo 120; lead time 15; custo R$ 15,00):**

| # | Estoque | Dias de cobertura | Status | Compra | Capital Imobilizado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| S1 | 10 | 5,0 | Ruptura Iminente (5 < 15) | 110 | — |
| S2 | 30 | 15,0 | Abaixo do Mínimo (15 não é < 15; 30 ≤ 60) | 90 | — |
| S3 | 50 | 25,0 | Abaixo do Mínimo | 70 | — |
| S4 | 60 | 30,0 | Abaixo do Mínimo (limite inclusivo) | 60 | — |
| S5 | 90 | 45,0 | Estoque Saudável | 0 | — |
| S6 | 120 | 60,0 | Estoque Saudável (limite inclusivo do máximo) | 0 | — |
| S7 | 150 | 75,0 | Acima do Máximo | 0 | (150 − 120) × 15,00 = **R$ 450,00** |
| S8 | 300 (VMD 0) | 999 ("∞") | Acima do Máximo | 0 | 300 × 15,00 = **R$ 4.500,00** |
| S9 | 0 (VMD 0) | 0 | Estoque Saudável | 0 | — |

**Critérios de aceite:**

- **CA-P055-01 — Ruptura iminente**
  - **Dado** um produto com VMD 2,0, estoque 10 un e lead time 15 dias
  - **Quando** o cálculo é executado
  - **Então** os Dias de Cobertura são 5,0, o status é `CRITICAL_STOCKOUT` com rótulo "Ruptura Iminente" e a Quantidade Sugerida é 110 un.
- **CA-P055-02 — Abaixo do mínimo**
  - **Dado** um produto com VMD 2,0, estoque 50 un e lead time 15 dias
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é `REORDER_NEEDED` com rótulo "Abaixo do Mínimo".
- **CA-P055-03 — Fronteira do lead time**
  - **Dado** um produto com VMD 2,0, estoque 30 un (cobertura 15,0) e lead time 15 dias
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é "Abaixo do Mínimo" (e não "Ruptura Iminente") e a Quantidade Sugerida é 90 un.
- **CA-P055-04 — Saudável**
  - **Dado** um produto com VMD 2,0 e estoque 90 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é `HEALTHY` com rótulo "Estoque Saudável" e a Quantidade Sugerida é 0.
- **CA-P055-05 — Acima do máximo e capital imobilizado**
  - **Dado** um produto com VMD 2,0, estoque 150 un e custo R$ 15,00
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é `OVERSTOCK` com rótulo "Acima do Máximo" e o item contribui com R$ 450,00 para o Capital Imobilizado.
- **CA-P055-06 — SKU sem venda com estoque**
  - **Dado** um produto sem vendas na janela, com estoque 300 un e custo R$ 5,00
  - **Quando** o cálculo é executado
  - **Então** os Dias de Cobertura são 999 (exibidos como "∞"), o status é "Acima do Máximo" e o item contribui com R$ 1.500,00 para o Capital Imobilizado.
- **CA-P055-07 — SKU sem venda e sem estoque**
  - **Dado** um produto sem vendas na janela e com estoque 0
  - **Quando** o cálculo é executado
  - **Então** os Dias de Cobertura são 0, o status é "Estoque Saudável" e a Quantidade Sugerida é 0.
- **CA-P055-08 — Mínimo igual ao máximo**
  - **Dado** um produto que vendeu 1 un em 60 dias (mínimo = máximo = 1) e tem estoque 1 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** a Quantidade Sugerida é 0 e o status é "Estoque Saudável".
- **CA-P055-09 — KPIs coerentes**
  - **Dado** qualquer resultado de cálculo
  - **Quando** os KPIs são exibidos
  - **Então** a soma das contagens por status é igual ao total de SKUs analisados.

---

### P-056 — Revogação de limites e de parâmetros do modelo anterior

**Descrição:** O sistema DEVE deixar de aplicar qualquer limite que corte ou altere a quantidade sugerida pela política Mín/Máx, e DEVE remover parâmetros e saídas do modelo anterior que não fazem mais sentido.

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-056.1** | **Revoga P-044.4** (trava % de variação física): deixam de existir o teto físico de compra, o piso operacional para estoque zerado e o parâmetro "Margem Máxima de Variação de Compra (%)". Os indicadores "Limitado por Espaço Físico", "Teto Físico de Compra", "Demanda Teórica Plena", "Estoque Ideal Teórico" e o KPI "SKUs com trava física" deixam de ser calculados e exibidos. |
| **P-056.2** | **Revoga P-046.3** (teto orçamentário): deixam de existir o parâmetro "Teto Orçamentário Máximo", a priorização por orçamento e qualquer redução de quantidade por valor em R$. |
| **P-056.3** | **Remove os parâmetros do modelo estatístico:** "Nível de Serviço" (z-score) e "Autonomia Alvo de Estoque" (cobertura alvo única) saem da tela e do cálculo. Estoque de Segurança, Ponto de Reposição (ROP) e Estoque Ideal deixam de ser calculados e exibidos e são substituídos por Estoque Mínimo e Estoque Máximo (P-053). |
| **P-056.4** | Parâmetros revogados (nível de serviço, cobertura alvo, teto orçamentário, margem de variação), se ainda forem enviados por um cliente antigo, NÃO PODEM alterar o resultado do cálculo. (A forma de tratamento, ignorar ou rejeitar, é decisão do Arquiteto.) |
| **P-056.5** | **Saídas ajustadas.** Tela, KPIs e CSV DEVEM refletir a política Mín/Máx. O CSV exportado DEVE conter, nesta ordem: Código; Descrição; EAN; Fornecedor; Tipo/Linha; Estoque Físico Atual; Venda Média Diária (VMD); Dias de Cobertura; Lead Time (Dias); **Estoque Mínimo (un)**; **Estoque Máximo (un)**; Qtd Sugerida de Compra; Último Custo Real (R$); Preço de Venda (R$); Investimento Total Sugerido (R$); Status Operacional; Curva ABC. As colunas Estoque de Segurança, Ponto de Reposição (ROP), Estoque Ideal, Demanda Teórica Plena, Limitado por Espaço Físico e Teto Físico de Compra DEVEM ser removidas. O formato é mantido (separador `;`, decimal `,`, BOM UTF-8). |
| **P-056.6** | O CSV DEVE reproduzir exatamente o mesmo cálculo exibido na tela para os mesmos parâmetros (janela, lead time, Dias Mínimo, Dias Máximo e fornecedor). |

**Critérios de aceite:**

- **CA-P056-01 — Sem trava física**
  - **Dado** um produto com VMD 2,0, estoque 10 un e parâmetros 30/60 (o antigo teto de +100% limitaria a compra a 20 un)
  - **Quando** o cálculo é executado
  - **Então** a Quantidade Sugerida é 110 un.
- **CA-P056-02 — Sem teto orçamentário**
  - **Dado** que um cliente antigo envia um teto orçamentário de R$ 1.000,00 junto com a requisição
  - **Quando** o cálculo é executado
  - **Então** o resultado é idêntico ao cálculo sem esse parâmetro.
- **CA-P056-03 — Parâmetros antigos não aparecem**
  - **Dado** que o usuário abre o modal de parâmetros da Previsão de Estoque
  - **Quando** o modal é exibido
  - **Então** ele mostra apenas Janela de Vendas, Lead Time, Dias Mínimo e Dias Máximo; não mostra Nível de Serviço, Autonomia Alvo, Teto Orçamentário nem Margem Máxima de Variação.
- **CA-P056-04 — Colunas do CSV**
  - **Dado** um cálculo concluído
  - **Quando** o usuário baixa o CSV do plano de compras
  - **Então** o arquivo contém as colunas Estoque Mínimo (un) e Estoque Máximo (un), não contém nenhuma coluna listada como removida em P-056.5 e os valores coincidem com os da tela.

---

### P-057 — Exclusão de SKUs inativos

**Descrição:** SKUs com estoque físico igual a 0 e Venda Média Diária (VMD) igual a 0 (consequentemente giro e dias de cobertura 0) NÃO DEVEM aparecer na lista, nos KPIs nem no CSV.

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-057.1** | O filtro é aplicado no motor, após a avaliação; `totalSkusAnalisados` e todos os KPIs consideram apenas os SKUs restantes. |
| **P-057.2** | SKU com estoque 0 e VMD > 0 (ruptura) ou estoque > 0 e VMD = 0 (sem giro) continuam listados. |

---

## 4. Regras mantidas sem mudança (referência)

- **P-041 — VMD:** `quantidade vendida na janela ÷ dias da janela`; janela padrão 60 dias.
- **Curva ABC:** global (sobre a receita de todos os SKUs, independentemente do filtro de fornecedor), por receita acumulada na janela: **A** até 80%, **B** até 95%, **C** restante. SKU sem venda na janela é **C**.
- **P-047.1 — Filtro por fornecedor:** opcional; "TODOS", "ALL" ou vazio significam sem filtro; comparação pelo nome em maiúsculas, sem espaços nas pontas.
- **Custo Unitário com fallback:** último custo; se ≤ 0, 60% do preço de venda (2 casas).

---

## 5. Pontos em aberto para a Etapa 2

| # | Ponto | Comportamento especificado até decisão em contrário |
| :--- | :--- | :--- |
| A1 | Faixas permitidas para Dias Mínimo e Dias Máximo (só a regra máx. > mín. foi decidida no discovery). | Inteiros ≥ 1 com máx. > mín. Proposta não vinculante: mínimo 5–120 e máximo 10–180, passo 5. |
| A2 | Lead time maior que Dias Máximo gera "Ruptura Iminente" com compra 0 em itens acima do máximo (ex.: Dias 20/40, lead time 45, VMD 2,0, estoque 84 → cobertura 42 < 45, máximo 80, compra 0). | Precedência de P-055.2 mantida (status Ruptura Iminente, compra 0). Avaliar se convém validar `lead time < Dias Máximo`. |
| A3 | A VMD é gravada com 4 casas nos dois caminhos de cálculo (SQL e memória), o que contraria P-053.6 em produtos de giro baixo (ver E5). | P-053.6 prevalece: mínimo e máximo calculados com precisão integral. |
| A4 | Janela de vendas: a regra e a tela usam 15–180 dias, mas a API aceita até 365. | Regra de negócio: 15–180. |
| A5 | Lead time: faixas divergentes entre API (1–90), configuração (1–60) e tela (5–60). | Padrão 15; faixa a harmonizar pelo Arquiteto. |
