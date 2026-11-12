# Regras de Negócio: Analytics Comercial — F4 Recomendação de Cross-sell (+ fundação do módulo `analytics`)

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-cross-sell.md`
> **Responsável:** Analista (`business-rules-expert`)
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Recomendação de cross-sell por produto e por cliente, mais a fundação do módulo `analytics` |
| **Módulo** | `analytics` (contexto delimitado novo: Analytics Comercial) |
| **Branch** | `feature/analytics-cross-sell` |
| **Regras novas** | P-058 a P-071 |
| **Regras reaproveitadas** | P-005 (filtro de cestas órfãs, `pricing`), custo com fallback de P-054.5 (`inventory`) |
| **Origem** | Plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§1, §2, §3) e decisões D1–D5 do `STATE.md` |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado — aguardando Etapa 2 (Arquitetura, Design Plan, Privacy by Design) |

---

## 1. Contexto e Objetivo

- **User Story Relacionada:** US-F4 — *Como vendedor/comprador da Fitoherb, quero saber quais produtos costumam ser comprados junto com um produto e o que oferecer a cada cliente, para aumentar o ticket médio com sugestões que têm estoque e dão margem.*
- **Objetivo da Feature:** responder duas perguntas:
  1. **Por produto:** "quem compra A também leva o quê?" (consequentes ordenados, com explicação simples).
  2. **Por cliente:** "o que oferecer a este cliente?" (produtos que ele não compra ou deixou de comprar, ordenados por pontuação que combina força da associação e margem).
- **Fundação:** esta fase cria a base comum do módulo `analytics` (repositório somente leitura, cache com lock e TTL, envelope `data`/`meta`, paginação, exceções de domínio com código interno, rota de saúde, aba no frontend) que as Fases 2 a 6 reaproveitam.
- **Atores Envolvidos:** Vendedor / time comercial (consulta), Comprador (consulta por produto), Sistema (ERP SQL Server, somente leitura).
- **Fora do escopo:** envio automático de ofertas, campanhas, alteração do código legado de `pricing`/`inventory` (que continua filtrando só `VENDA`), regras com mais de um item no antecedente, filiais (D3).

---

## 2. Catálogo de Regras de Negócio (P-XXX)

> [!IMPORTANT]
> Os parâmetros numéricos abaixo DEVEM existir como constantes nomeadas no topo de `domain/cross_sell.py` (sem números mágicos). Valores marcados com "Premissa A-n" estão listados na seção 6 e serão confirmados no checkpoint da Etapa 2.

### Tabela de constantes

| Constante | Valor | Regra | Situação |
| :--- | :--- | :--- | :--- |
| `SALE_OPERATION` | `'VENDA'` | P-058 | Decidido (D4) |
| `MIN_SKUS_PER_BASKET` | `2` | P-058 | Decidido (P-005) |
| `MIN_SUPPORT` | `0.002` | P-059 | Premissa A-1 (padrão já usado em `basket_mining`) |
| `MIN_PAIR_ORDERS` | `10` | P-059 | Premissa A-1 |
| `MIN_LIFT` | `1.2` | P-060 | Decidido (plano §3.3) |
| `MIN_CONFIDENCE` | `0.10` | P-060 | Premissa A-2 |
| `TRIVIAL_ITEM_SUPPORT` | `0.15` | P-060 | Premissa A-3 |
| `CUSTOMER_PROFILE_DAYS` | `365` | P-062 | Premissa A-4 |
| `DORMANT_DAYS` | `90` | P-062 | Premissa A-5 |
| `COST_FALLBACK_RATIO` | `0.60` | P-063 | Reaproveitado de P-054.5 |
| `MIN_VALID_BASKETS` | `1000` | P-067 | Premissa A-7 |
| `DEFAULT_PAGE_LIMIT` / `MAX_PAGE_LIMIT` | `50` / `200` | P-066 | Decidido (plano §2.7) |
| `CACHE_TTL_HOURS` | `6` | P-068 | Decidido (plano §2.6) |
| `HIT_RATE_K` | `5` | P-071 | Decidido (plano §3.3) |

---

### `P-058`: Origem dos dados e formação da Cesta

- **Declaração Mandatória:** O sistema DEVE formar as Cestas exclusivamente a partir de linhas de `Externo01.Vendas` com `[Operação] = 'VENDA'`. Devoluções (`[Operação] LIKE 'DEVOLU%'`) NÃO DEVEM entrar em nenhuma Cesta, nem como item, nem como abatimento.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-058.1** | **Cesta** = conjunto de SKUs distintos (`Cod Produto`) de um mesmo `Pedido` de VENDA. Quantidade e valor não influenciam a Cesta: um SKU está ou não está no pedido. |
| **P-058.2** | Um par `Pedido × SKU` só entra na Cesta se a soma de `Qtd Venda` desse par, considerando só linhas de VENDA, for **> 0** (comportamento atual de `build_basket_matrix`). |
| **P-058.3** | **Cesta Válida:** Cestas com menos de `MIN_SKUS_PER_BASKET` (2) SKUs distintos DEVEM ser descartadas antes da mineração (reaproveita P-005 / `filter_orphan_baskets`). O número de pedidos descartados é registrado em log **apenas como contagem**. |
| **P-058.4** | A agregação DEVE ocorrer no SQL Server no grão `Pedido × Cod Produto` (agregado `order_baskets`), carregando também `Cod Cliente` e a data do pedido, necessários a P-062 e P-071. Nenhuma linha bruta por item é trazida ao Python (plano §2.5). A query passa por `is_readonly_query` e não usa `CONCAT`. |
| **P-058.5** | A constante `RETURN_OPERATION_PATTERN = 'DEVOLU%'` DEVE existir no repositório do módulo (fundação), mesmo que esta fase só a use para **excluir** devoluções; há teste com devolução na massa garantindo que ela não cria co-ocorrência. |
| **P-058.6** | **Janela de mineração:** todo o histórico de VENDA disponível até a data de corte (em produção, até agora; no backtest, até o fim do mês N−1, ver P-071). (Premissa A-6.) |

- **Condições de Ativação:** carga (ou recarga) da base do módulo.
- **Resultado Esperado:** conjunto de Cestas Válidas pronto para a mineração.
- **Exceção / Mensagem de Erro:** se o número de Cestas Válidas for menor que `MIN_VALID_BASKETS`, ver P-067 (`XSL-003`).

---

### `P-059`: Mineração das Regras de Associação

- **Declaração Mandatória:** O sistema DEVE minerar Regras de Associação com FP-Growth reaproveitando `build_basket_matrix` e `mine_association_rules` de `src/modules/pricing/domain/basket_mining.py`, calculando para cada regra Suporte, Confiança e Lift.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-059.1** | Somente regras **1 → 1** (um SKU Antecedente, um SKU Consequente) são consideradas. Regras com mais itens são descartadas. Motivo: explicação simples ao usuário (P-065) e menor consumo de memória no Cloud Run. (Premissa A-1.) |
| **P-059.2** | **Suporte** do par `{A, B}` = pedidos com A e B ÷ total de Cestas Válidas. Itemsets com suporte < `MIN_SUPPORT` (0,002) não geram regra. |
| **P-059.3** | **Pedidos em comum** (`pedidosEmComum`) = número absoluto de Cestas Válidas que contêm A e B. Regras com `pedidosEmComum < MIN_PAIR_ORDERS` (10) DEVEM ser descartadas, para que a regra não dependa de poucos pedidos quando a base for pequena (ex.: backtest). |
| **P-059.4** | **Confiança** de A → B = pedidos com A e B ÷ pedidos com A. |
| **P-059.5** | **Lift** de A → B = Confiança de A → B ÷ (pedidos com B ÷ total de Cestas Válidas). Lift 1,0 significa "B aparece com A na mesma frequência que em qualquer pedido". |
| **P-059.6** | A regra A → A (antecedente igual ao consequente) NUNCA é válida. |
| **P-059.7** | As regras mineradas DEVEM ser cacheadas junto com a base (P-068) e não podem ser recalculadas a cada requisição. |

- **Condições de Ativação:** após P-058, na primeira consulta de cross-sell sem cache válido.
- **Resultado Esperado:** tabela de regras 1 → 1 com `antecedente`, `consequente`, `suporte`, `confianca`, `lift`, `pedidosEmComum`, `pedidosComAntecedente`.
- **Exceção / Mensagem de Erro:** se nenhuma regra sobreviver a P-059 e P-060, ver P-067 (`XSL-003`).

---

### `P-060`: Critérios de Regra Útil e exclusão de Pares Triviais

- **Declaração Mandatória:** O sistema DEVE usar em qualquer recomendação apenas **Regras Úteis**: `lift ≥ MIN_LIFT (1,2)` **e** `confiança ≥ MIN_CONFIDENCE (0,10)` **e** consequente que não seja Item Trivial.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-060.1** | Os limites são inclusivos: lift exatamente 1,2 e confiança exatamente 0,10 são aceitos. |
| **P-060.2** | **Item Trivial:** SKU presente em **mais de** `TRIVIAL_ITEM_SUPPORT` (15%) das Cestas Válidas (`pedidos com o SKU ÷ total de Cestas Válidas > 0,15`). É o item que "quase todo pedido leva"; recomendá-lo não acrescenta informação. |
| **P-060.3** | **Par Trivial:** regra cujo **consequente** é Item Trivial. Pares Triviais DEVEM ser excluídos de todas as recomendações (por produto e por cliente). Um Item Trivial PODE aparecer como **antecedente** (ex.: "quem compra o carro-chefe A também leva C" continua válido). |
| **P-060.4** | A lista de Itens Triviais é recalculada a cada recarga da base, junto com as regras. O número de SKUs classificados como triviais é registrado em log (só contagem) para calibração. |

- **Exemplo numérico (10.000 Cestas Válidas):**

| # | Regra | Pedidos com A | Pedidos com B | Pedidos com A e B | Confiança | Lift | Útil? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| R1 | A → B | 500 | 800 | 170 | 0,34 | 0,34 ÷ 0,08 = **4,25** | Sim |
| R2 | A → C | 500 | 3.000 | 200 | 0,40 | 0,40 ÷ 0,30 = 1,33 | **Não** (C está em 30% > 15%: Par Trivial) |
| R3 | A → D | 500 | 400 | 30 | 0,06 | 1,5 | **Não** (confiança < 0,10) |
| R4 | A → E | 500 | 2.000 | 110 | 0,22 | 1,1 | **Não** (lift < 1,2) |
| R5 | A → F | 500 | 1.000 | 60 | 0,12 | **1,2** | Sim (limite inclusivo) |

---

### `P-061`: Recomendação por Produto

- **Declaração Mandatória:** Dado um SKU, o sistema DEVE devolver os consequentes das Regras Úteis cujo antecedente é esse SKU, ordenados e paginados.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-061.1** | **Ordenação:** lift decrescente; empate por confiança decrescente; empate por `pedidosEmComum` decrescente; empate final por código do SKU crescente (ordem determinística). |
| **P-061.2** | Cada item devolve: código, descrição e fornecedor do consequente; `suporte`, `confianca`, `lift`, `pedidosEmComum`; estoque atual; e a explicação de P-065. |
| **P-061.3** | Consequente que não está no catálogo ativo (`Externo01.Produto` com `Pc.Venda > 0`) DEVE ser excluído (não pode ser vendido). |
| **P-061.4** | Consequente com `Estoque ≤ 0` ou Margem Unitária ≤ 0 **não é excluído** neste modo (é uma visão analítica de associação), mas DEVE vir sinalizado (`semEstoque`, `margemNaoPositiva`) para a tela destacar. (Premissa A-8.) |
| **P-061.5** | SKU válido, com venda, mas sem nenhuma Regra Útil como antecedente DEVE retornar **200** com lista vazia (não é erro), e `meta` indica `totalItems = 0`. |
| **P-061.6** | SKU inexistente no catálogo ou sem nenhuma Cesta Válida no histórico DEVE retornar **404** `XSL-001` (P-067). |

---

### `P-062`: Recomendação por Cliente — perfil e candidatos

- **Declaração Mandatória:** Dado um `Cod Cliente`, o sistema DEVE aplicar as Regras Úteis aos produtos que o cliente compra e propor como candidatos apenas os consequentes que ele **não compra** ou que são **Produtos Dormentes** para ele.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-062.1** | **Perfil de compra do cliente** (antecedentes) = SKUs comprados pelo cliente em pedidos de VENDA nos últimos `CUSTOMER_PROFILE_DAYS` (365) dias até a data de corte. Pedidos de 1 SKU contam para o perfil (o filtro P-058.3 vale só para a mineração). Devoluções não contam. |
| **P-062.2** | **Histórico do cliente** = para cada SKU, a data do último pedido de VENDA do cliente que contém o SKU (todo o histórico). |
| **P-062.3** | **Produto Dormente** para o cliente = SKU já comprado pelo cliente cuja última compra ocorreu há **mais de** `DORMANT_DAYS` (90) dias da data de corte. 90 dias exatos não é dormente. |
| **P-062.4** | **Candidato** = consequente de Regra Útil cujo antecedente pertence ao perfil (P-062.1) **e** que (a) nunca foi comprado pelo cliente, ou (b) é Produto Dormente para ele. SKU comprado nos últimos 90 dias NUNCA é candidato. |
| **P-062.5** | Cada candidato carrega o tipo do motivo: `NUNCA_COMPROU` ou `DORMENTE` (com `diasDesdeUltimaCompra`). |
| **P-062.6** | Um SKU do perfil nunca é recomendado a si mesmo; um candidato que também é antecedente do perfil já foi excluído por P-062.4 (comprado recentemente). |
| **P-062.7** | Cliente sem nenhum pedido de VENDA no histórico DEVE retornar **404** `XSL-002`. Cliente com histórico mas sem compras nos últimos 365 dias tem perfil vazio e recebe **200** com lista vazia e `meta.motivoVazio = "SEM_COMPRAS_RECENTES"`. (Premissa A-4.) |

---

### `P-063`: Viabilidade comercial do candidato

- **Declaração Mandatória:** No modo por cliente, o sistema NÃO DEVE recomendar produto sem estoque, fora do catálogo ou sem margem positiva.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-063.1** | Excluir candidato com `Estoque ≤ 0` em `Externo01.Produto`. |
| **P-063.2** | Excluir candidato fora do catálogo ativo (`Pc.Venda > 0`). |
| **P-063.3** | **Margem Unitária** = `Pc.Venda − Custo Unitário`, onde Custo Unitário = `Pc.Ultimo Custo`; se `Pc.Ultimo Custo` for ≤ 0 ou ausente, usar `COST_FALLBACK_RATIO × Pc.Venda` (60%, mesma regra de P-054.5), e o item recebe a sinalização `custoEstimado = true`. (Premissa A-9.) |
| **P-063.4** | Excluir candidato com **Margem Unitária ≤ 0**. |
| **P-063.5** | Os filtros de viabilidade são aplicados **antes** da paginação, para que `totalItems` reflita só os itens recomendáveis. |

---

### `P-064`: Pontuação de Cross-sell e ordenação por cliente

- **Declaração Mandatória:** O sistema DEVE ordenar os candidatos viáveis pela **Pontuação de Cross-sell** = `lift × confiança × Margem Unitária` (em R$).
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-064.1** | Quando mais de um antecedente do perfil leva ao mesmo candidato, vale a regra de **maior pontuação** (máximo, não soma), para que clientes com perfis grandes não inflem a pontuação. A resposta informa o antecedente dessa regra (motivo principal) e `qtdAntecedentesRelacionados` (quantos produtos do perfil sugerem o candidato). (Premissa A-10.) |
| **P-064.2** | **Ordenação:** pontuação decrescente; empate por lift decrescente; empate final por código do SKU crescente. |
| **P-064.3** | A pontuação é exposta arredondada a 2 casas; a ordenação usa o valor sem arredondamento. |
| **P-064.4** | Cada item devolve: código, descrição e fornecedor do candidato; antecedente principal (código e descrição); `lift`, `confianca`, `margemUnitaria`, `custoEstimado`, `pontuacao`, `motivo` (`NUNCA_COMPROU` / `DORMENTE`), `diasDesdeUltimaCompra` (quando dormente) e a explicação de P-065. |

- **Exemplo numérico:**

| Candidato | Antecedente | Lift | Confiança | Margem Unitária | Pontuação | Posição |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| B | A | 4,25 | 0,34 | R$ 5,00 | 7,23 | 2 |
| G | A | 1,50 | 0,20 | R$ 30,00 | **9,00** | **1** |
| G | H | 2,00 | 0,15 | R$ 30,00 | 9,00 | (mesma pontuação, não soma) |
| K | H | 3,00 | 0,30 | R$ 0,00 | — | excluído (P-063.4) |

---

### `P-065`: Explicação em linguagem simples

- **Declaração Mandatória:** Toda recomendação DEVE vir acompanhada de uma explicação compreensível por quem não conhece estatística, sem os termos "lift", "suporte" ou "confiança" no texto principal.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-065.1** | **Frase de confiança:** `"Em {X}% dos pedidos com {descrição A} também há {descrição B}."`, com X = confiança × 100 arredondado para inteiro (meio para cima). |
| **P-065.2** | **Frase de lift:** `"{descrição B} aparece {L} vezes mais nesses pedidos do que no geral."`, com L = lift com 1 casa decimal e vírgula decimal. |
| **P-065.3** | **Base de evidência:** `"Baseado em {N} pedidos."`, com N = `pedidosEmComum`. |
| **P-065.4** | **Motivo por cliente:** `"O cliente nunca comprou {B}."` ou `"O cliente não compra {B} há {D} dias."`, prefixado por `"Sugerido porque o cliente compra {A}."`. |
| **P-065.5** | Os valores numéricos (`confianca`, `lift`, `pedidosEmComum`) também vêm como campos estruturados, para a tela exibir detalhes técnicos sob demanda. Onde o texto é montado (domínio ou frontend) é decisão do Arquiteto; o formato acima é obrigatório. |

- **Exemplo:** R1 de P-060 → "Em 34% dos pedidos com Chá Verde 100g também há Cápsula de Hibisco. Cápsula de Hibisco aparece 4,3 vezes mais nesses pedidos do que no geral. Baseado em 170 pedidos."

---

### `P-066`: Fundação — Envelope de resposta e paginação

- **Declaração Mandatória:** Toda resposta 2xx do módulo `analytics` DEVE seguir o envelope `{ "data": ..., "meta": { ... } }` em `camelCase`, e toda lista DEVE ser paginada.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-066.1** | `meta` contém sempre `timestamp` (ISO-8601) e, em listas, `page`, `limit`, `offset`, `total`/`totalItems` e `totalPages`. Também `dataReferencia` (data de corte da base em cache). |
| **P-066.2** | `limit`: inteiro, padrão **50**, mínimo **1**, máximo **200**. `offset`: inteiro ≥ 0, padrão 0. Valores fora da faixa ou não inteiros → **400** `XSL-004`. Não há truncamento silencioso de `limit`. |
| **P-066.3** | `page = floor(offset ÷ limit) + 1`; `totalPages = teto(totalItems ÷ limit)` (0 quando não há itens). |
| **P-066.4** | `offset ≥ totalItems` devolve **200** com `data` vazio e os totais corretos (não é erro). |
| **P-066.5** | Ambos os modos (produto e cliente) usam a mesma paginação. |

---

### `P-067`: Fundação — Exceções de domínio e códigos `XSL`

- **Declaração Mandatória:** Erros de regra de negócio DEVEM ser lançados como subclasses de `AnalyticsDomainException`, traduzidos pelo handler global (sem `try/catch` por rota), com código interno e HTTP semântico. Nunca devolver stacktrace.

| Código | HTTP | Quando | Mensagem ao usuário |
| :--- | :--- | :--- | :--- |
| `XSL-001` | 404 | SKU inexistente no catálogo ativo ou sem nenhuma Cesta Válida no histórico | `"Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item."` |
| `XSL-002` | 404 | `Cod Cliente` sem nenhum pedido de VENDA no histórico | `"Cliente sem histórico de compras."` |
| `XSL-003` | 422 | Base com menos de `MIN_VALID_BASKETS` (1.000) Cestas Válidas **ou** zero Regras Úteis após P-059/P-060 | `"Não há pedidos suficientes para gerar recomendações confiáveis."` |
| `XSL-004` | 400 | `sku` ou `customerCode` não é inteiro positivo; `limit`/`offset` fora da faixa (P-066.2). O corpo lista os campos inválidos | `"Parâmetros inválidos: {campos}."` |

- **Observações:** lista vazia legítima (P-061.5, P-062.7, P-066.4) é **200**, nunca 404/422. Falha de conexão com o banco é erro de infraestrutura (HTTP 5xx genérico), fora do catálogo `XSL`; o formato é decisão do Arquiteto. A mensagem do `XSL-002` NÃO DEVE ecoar dados do cliente além do próprio código recebido.

---

### `P-068`: Fundação — Cache e concorrência

- **Declaração Mandatória:** A base agregada, as Regras Úteis e a lista de Itens Triviais DEVEM ficar em cache em memória com TTL de **6 h**, seguindo o padrão de `get_cached_base_data` do `pricing_service`.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-068.1** | **Carga única:** requisições simultâneas com cache vazio ou expirado DEVEM disparar **uma única** carga do banco e uma única mineração; as demais aguardam o lock e reutilizam o resultado. |
| **P-068.2** | Após 6 h da carga, a próxima requisição recarrega. Durante a recarga, a regra de carga única continua valendo. |
| **P-068.3** | Deve existir `force_reload` manual (mecanismo definido pelo Arquiteto), que respeita o lock. |
| **P-068.4** | Se a carga falhar, o cache anterior (se existir) NÃO é substituído por resultado parcial, e o erro é propagado (P-067, observações). |
| **P-068.5** | Recomendações por cliente PODEM ser cacheadas por chave (`customerCode`), invalidadas junto com a base. |

---

### `P-069`: Fundação — Verificação de saúde do módulo

- **Declaração Mandatória:** `GET /analytics/health` DEVE responder **200** no envelope `data`/`meta`, indicando se o cache está carregado e a `dataReferencia` da base, **sem** disparar carga do banco nem mineração.

---

### `P-070`: Privacidade (LGPD)

- **Declaração Mandatória:** O módulo DEVE identificar clientes **somente** por `Cod Cliente`.
- **Sub-regras:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-070.1** | Nenhuma resposta, tela ou exportação desta fase contém nome, razão social, CPF/CNPJ, endereço, telefone, e-mail ou `UF` do cliente. As queries do repositório não selecionam essas colunas. |
| **P-070.2** | É proibido logar DataFrames, listas de recomendações, perfis de compra ou payloads de cliente. Logs só podem conter contagens agregadas (cestas, regras, itens triviais, tempo de carga). |
| **P-070.3** | O `Cod Cliente` não pode aparecer em mensagens de log de domínio/serviço. A exposição em logs de acesso HTTP (path `/customer/{customerCode}`) DEVE ser avaliada pelo `privacy_officer` na Etapa 2. (Premissa A-11.) |
| **P-070.4** | Dados do cliente ficam só no cache em memória do processo, sem persistência em disco ou em serviço externo. |

---

### `P-071`: Critério de aceite quantitativo — hit rate@5 em backtest temporal

- **Declaração Mandatória:** O sistema DEVE ter um backtest automatizado e reprodutível que mede o **hit rate@5** das recomendações por cliente.
- **Protocolo:**

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-071.1** | **Mês de avaliação principal N = 2026-10** (último mês completo; novembro de 2026 está incompleto). Para estabilidade, repetir para **N ∈ {2026-08, 2026-09, 2026-10}** e reportar cada mês e a média. |
| **P-071.2** | **Treino:** Cestas, Regras Úteis, Itens Triviais, perfil (P-062.1) e Produtos Dormentes calculados só com pedidos de VENDA até o último dia do mês N−1 (data de corte = 1º dia de N). Nada do mês N vaza para o treino. |
| **P-071.3** | **Clientes avaliados:** clientes com perfil não vazio no corte **e** com pelo menos um pedido de VENDA no mês N **e** com pelo menos uma recomendação gerada. Os excluídos são contados e reportados (sem regra, sem compra em N). |
| **P-071.4** | **Acerto:** o cliente comprou, em algum pedido de VENDA do mês N, ao menos um dos 5 primeiros SKUs recomendados (P-064). `hit rate@5 = clientes com acerto ÷ clientes avaliados`. |
| **P-071.5** | **Viabilidade no backtest:** o filtro de estoque (P-063.1) NÃO é aplicado, porque a base não tem estoque histórico; a margem usa preço e custo atuais. Essa limitação DEVE constar do relatório. |
| **P-071.6** | **Linha de base:** calcular também o hit rate@5 de uma recomendação por **popularidade** (os 5 SKUs com mais Cestas no treino que o cliente não comprou nos últimos 90 dias, com os mesmos filtros de catálogo e margem). |
| **P-071.7** | **Critério de aprovação:** obrigatório **medir e reportar** (hit rate@5 do modelo, da popularidade, cobertura de clientes e tamanho da amostra) no PR. **Meta proposta:** hit rate@5 do modelo ≥ hit rate@5 da popularidade na média dos 3 meses. (Premissa A-12: meta bloqueante ou apenas informativa.) |

### P-094 — Curadoria das Sugestões (pedido do usuário em 2026-11-09)

**Motivo:** na base real, as listas tinham de 100 a 280 linhas, e a maioria era a mesma linha do fornecedor em outro sabor, aroma ou tamanho (WHEY 100% PURE CHOC para quem compra WHEY 100% PURE BAUN; seis sabores de CRISP BAR). O usuário pediu só as principais, sem linhas repetidas, **priorizando produtos do mesmo fornecedor ou similares**. A curadoria vale nos dois modos e roda depois do ranking (P-061.1 / P-064.2). Implementação: `domain/recommendation_curation.py`.

| Sub-regra | Enunciado |
| :--- | :--- |
| **P-094.1** | **Variante do produto de origem é descartada.** Variante = mesmo fornecedor **e** mesmo nome-base. Nome-base é a 1ª palavra significativa da descrição: sem acento, sem conectivos (DE, E, COM…), sem unidades (G, ML, CAPS…), sem palavras com dígito (300G, 500MG, 100%) e no singular (BALAS → BALA). Exemplos: ARGILA VERDE ~ ARGILA BRANCA; CREATINA 300G ~ CREATINA 150G. No modo cliente a origem é o `antecedentePrincipal` de cada item. |
| **P-094.2** | **Prioridade por faixa:** (1) mesmo fornecedor da origem; (2) produto **similar** de outro fornecedor, ou seja, com ao menos uma palavra significativa em comum na descrição (ÓLEO DE RÍCINO ~ ÓLEO DE ABACATE); (3) os demais. Dentro de cada faixa vale o ranking original. |
| **P-094.3** | **Uma sugestão por linha de produto** (fornecedor + nome-base): fica a primeira após a priorização. |
| **P-094.4** | **No máximo 10 sugestões** por consulta (`MAX_RECOMMENDATIONS`). `meta.totalItems` passa a contar a lista curada. |
| **P-094.5** | O backtest (P-071) mede o top-5 **da lista curada**, ou seja, o que a tela mostra. |

> Limitação: o catálogo não tem campo de família ou categoria, então "linha" e "similar" são heurísticas sobre a descrição. Se o cadastro ganhar categoria, ela substitui o nome-base.

---

## 3. Enquadramento LGPD & Privacidade (Art. 7º e 11 da LGPD)

| Dado / Atributo | Classificação LGPD | Base Legal Aplicada | Finalidade Específica e Proporcional |
| :--- | :--- | :--- | :--- |
| `Cod Cliente` | Dado pessoal **indireto** quando o cliente é empresário individual/MEI (identifica pessoa natural via ERP); dado de PJ nos demais casos | Legítimo interesse do controlador (Art. 7º, IX), a confirmar pelo `privacy_officer` | Agrupar pedidos e recomendar produtos ao cliente na relação comercial existente. |
| Histórico de compras por cliente (SKU, data do pedido) | Dado pessoal indireto (mesma condição acima); não sensível | Legítimo interesse (Art. 7º, IX) | Montar perfil de compra e Produtos Dormentes (P-062). Mantido só em memória. |
| Nome, CPF/CNPJ, endereço, UF, contatos | Dado pessoal | **Não tratado** nesta fase | Minimização: não selecionados nem expostos (P-070.1). |

> Decisão automatizada (Art. 20): as recomendações são sugestões ao vendedor, sem efeito jurídico ou restritivo sobre o cliente. O `privacy_officer` confirma se cabe RIPD.

---

## 4. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP |
| :--- | :--- | :--- | :--- |
| **C-01** | SKU com Regras Úteis | Lista de consequentes ordenada por lift (P-061.1) | `200` |
| **C-02** | SKU válido sem Regras Úteis | `data` vazio, `totalItems = 0` | `200` |
| **C-03** | SKU inexistente ou só em pedidos de 1 item | `XSL-001` | `404` |
| **C-04** | `sku = "abc"` ou `sku = -5` | `XSL-004` com campo inválido | `400` |
| **C-05** | Cliente com perfil e candidatos | Lista ordenada por pontuação (P-064.2) | `200` |
| **C-06** | Cliente que já compra todos os consequentes nos últimos 90 dias | `data` vazio | `200` |
| **C-07** | Cliente sem compra nos últimos 365 dias | `data` vazio, `motivoVazio = SEM_COMPRAS_RECENTES` | `200` |
| **C-08** | Cliente sem nenhum pedido de VENDA (só devoluções ou inexistente) | `XSL-002` | `404` |
| **C-09** | Candidato com estoque 0 | Excluído no modo cliente; sinalizado `semEstoque` no modo produto | `200` |
| **C-10** | Candidato com custo ≥ preço | Excluído no modo cliente; sinalizado `margemNaoPositiva` no modo produto | `200` |
| **C-11** | Candidato com `Pc.Ultimo Custo = 0` | Custo = 60% do preço; `custoEstimado = true` | `200` |
| **C-12** | Pedido com A (VENDA) e devolução de B | Não cria co-ocorrência A-B | — |
| **C-13** | `limit = 0`, `limit = 201`, `offset = -1` | `XSL-004` | `400` |
| **C-14** | `offset` ≥ `totalItems` | `data` vazio com totais | `200` |
| **C-15** | Base com < 1.000 Cestas Válidas ou zero Regras Úteis | `XSL-003` | `422` |
| **C-16** | 10 requisições simultâneas com cache vazio | Uma única carga e mineração | `200` |
| **C-17** | Consequente é Item Trivial (> 15% das cestas) | Não aparece em nenhum modo | `200` |
| **C-18** | Última compra do candidato há exatamente 90 dias | Não é dormente, não é candidato | `200` |
| **C-19** | `GET /analytics/health` com cache vazio | `200` sem disparar carga | `200` |

---

## 5. Critérios de Aceitação (CA-xx)

- **CA-01 — Associação plantada recuperada:** **Dado** uma massa sintética em que B está em 34% dos pedidos com A e lift ≥ 1,2, **quando** a recomendação por produto de A é pedida, **então** B aparece com confiança 0,34 e o lift calculado. (P-059, P-061)
- **CA-02 — Devolução não cria co-ocorrência:** **Dado** pedidos em que B só aparece como `DEVOLUÇÃO DE VENDA` junto de A, **quando** as regras são mineradas, **então** não existe regra A → B. (P-058)
- **CA-03 — Cesta de 1 item descartada:** **Dado** pedidos com um único SKU, **quando** as cestas são formadas, **então** eles não entram na mineração. (P-058.3)
- **CA-04 — Limites de Regra Útil:** **Dado** as regras R1 a R5 do exemplo de P-060, **quando** os filtros são aplicados, **então** só R1 e R5 permanecem. (P-060)
- **CA-05 — Par Trivial excluído:** **Dado** um SKU C presente em 30% das cestas, **quando** qualquer recomendação é gerada, **então** C nunca aparece como consequente, mas pode ser antecedente. (P-060.2, P-060.3)
- **CA-06 — Mínimo de pedidos em comum:** **Dado** um par com 9 pedidos em comum e lift alto, **quando** as regras são mineradas, **então** a regra é descartada. (P-059.3)
- **CA-07 — Ordenação por produto:** **Dado** consequentes com lifts 3,0; 2,0; 2,0 (confianças 0,2 e 0,3), **quando** a lista é gerada, **então** a ordem é lift 3,0, depois lift 2,0/conf. 0,3, depois lift 2,0/conf. 0,2. (P-061.1)
- **CA-08 — Candidato só se não compra ou dormente:** **Dado** um cliente que comprou B há 30 dias e D há 120 dias, **quando** as regras A → B e A → D se aplicam, **então** só D é recomendado, com motivo `DORMENTE` e 120 dias. (P-062)
- **CA-09 — Fronteira de dormência:** **Dado** última compra do candidato há exatamente 90 dias, **então** ele não é recomendado; com 91 dias, é. (P-062.3)
- **CA-10 — Sem estoque não é sugerido ao cliente:** **Dado** candidato com `Estoque = 0`, **então** ele não aparece na recomendação por cliente e aparece sinalizado na recomendação por produto. (P-063.1, P-061.4)
- **CA-11 — Margem não positiva excluída:** **Dado** candidato com `Pc.Venda = 10,00` e `Pc.Ultimo Custo = 10,00`, **então** ele é excluído no modo cliente. (P-063.4)
- **CA-12 — Custo com fallback:** **Dado** candidato com `Pc.Venda = 25,00` e `Pc.Ultimo Custo = 0`, **então** a Margem Unitária é 10,00 e `custoEstimado = true`. (P-063.3)
- **CA-13 — Pontuação e ordenação por cliente:** **Dado** o exemplo de P-064, **então** G (9,00) vem antes de B (7,23) e G aparece uma única vez, com `qtdAntecedentesRelacionados = 2`. (P-064)
- **CA-14 — Explicação em linguagem simples:** **Dado** a regra R1, **então** o texto contém "Em 34% dos pedidos com A também há B", "4,3 vezes mais" e "Baseado em 170 pedidos", sem as palavras "lift", "suporte" ou "confiança". (P-065)
- **CA-15 — Envelope e paginação:** **Dado** 120 recomendações, **quando** é pedido `limit=50&offset=100`, **então** `data` tem 20 itens e `meta` traz `page=3`, `totalItems=120`, `totalPages=3`, `timestamp`. Sem `limit`, vêm 50 itens. (P-066)
- **CA-16 — Validação de paginação:** `limit=0`, `limit=201` e `offset=-1` retornam 400 `XSL-004` listando o campo. (P-066.2, P-067)
- **CA-17 — Códigos de erro:** SKU inexistente → 404 `XSL-001`; cliente sem histórico → 404 `XSL-002`; base insuficiente → 422 `XSL-003`; nenhum erro devolve stacktrace. (P-067)
- **CA-18 — Lista vazia não é erro:** SKU válido sem regras e cliente sem compras recentes retornam 200 com `data` vazio. (P-061.5, P-062.7)
- **CA-19 — Carga única sob concorrência:** **Dado** cache vazio e 10 requisições simultâneas, **então** o repositório é chamado uma única vez e a mineração roda uma única vez. (P-068.1)
- **CA-20 — Expiração do cache:** **Dado** cache carregado há mais de 6 h, **então** a próxima requisição recarrega; antes de 6 h, não recarrega. (P-068.2)
- **CA-21 — Health:** `GET /analytics/health` responde 200 no envelope sem acessar o banco. (P-069)
- **CA-22 — Privacidade:** nenhuma resposta contém campos além de `Cod Cliente` para identificar o cliente; os logs da massa de teste não contêm `Cod Cliente`, listas de SKUs por cliente nem DataFrames. (P-070)
- **CA-23 — Backtest sem vazamento:** **Dado** um pedido do mês N com par inédito A-B, **então** a regra A → B não existe no treino do backtest de N. (P-071.2)
- **CA-24 — hit rate@5 medido e reportado:** o backtest de N ∈ {2026-08, 2026-09, 2026-10} produz hit rate@5 do modelo e da popularidade, nº de clientes avaliados e excluídos, e o resultado consta do PR. Em massa sintética com resposta conhecida, o hit rate@5 calculado é exato. (P-071)

---

## 6. Premissas a confirmar no checkpoint (Etapa 2)

| # | Premissa | Valor proposto | Justificativa |
| :--- | :--- | :--- | :--- |
| A-1 | Suporte mínimo, mínimo de pedidos em comum e regras só 1 → 1 | `0,002`, `10`, 1 → 1 | Reaproveita o padrão de `basket_mining`; 1 → 1 facilita a explicação e reduz memória |
| A-2 | Confiança mínima | `0,10` (10%) | Abaixo de 1 em 10 pedidos a sugestão perde credibilidade para o vendedor |
| A-3 | Item Trivial | presente em > 15% das cestas | Mensurável e simples; calibrar com a contagem real de SKUs acima do limiar |
| A-4 | Janela do perfil do cliente | 365 dias; sem compras nesse período → lista vazia | Usa o comportamento recente sem descartar sazonais anuais |
| A-5 | `DORMANT_DAYS` | 90 dias | Maior que o limiar de churn do cliente (60 dias, D1), para medir abandono do **produto** e não do cliente |
| A-6 | Janela de mineração | Todo o histórico de VENDA até o corte (~23 meses) | Mais cestas, regras mais estáveis |
| A-7 | `MIN_VALID_BASKETS` | 1.000 | Proteção para bases ou recortes muito pequenos |
| A-8 | Modo por produto mostra itens sem estoque/margem com sinalização | Sim, sinalizados | É visão analítica; o filtro duro fica no modo cliente |
| A-9 | Custo ausente usa fallback de 60% (P-054.5) | Sim, com `custoEstimado` | Consistência com o módulo `inventory` |
| A-10 | Vários antecedentes para o mesmo candidato | Máximo, não soma | Evita favorecer clientes com perfis grandes |
| A-11 | `Cod Cliente` em logs de acesso HTTP | Avaliar com o `privacy_officer` | O path da rota contém o código |
| A-12 | Meta do hit rate@5 | ≥ popularidade, na média de 3 meses; proposta como não bloqueante na primeira entrega | Sem histórico prévio de métrica; primeira medição vira linha de base |

---

## 7. Definition of Done

- [ ] Todas as regras P-058 a P-071 têm testes automatizados (domínio com DataFrames sintéticos, repositório com conexão mockada) e cobertura ≥ 80%.
- [ ] Termos alinhados ao `.agents/docs/GLOSSARY.md` (seção Analytics Comercial).
- [ ] Enquadramento LGPD revisado e aprovado pelo `privacy_officer`.
- [ ] Nenhuma lógica de negócio em router/componentes.
- [ ] Backtest P-071 executado e resultado no PR.
