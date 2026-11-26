# Regras de Negócio: Analytics Comercial — F6 Relatório de Canibalização por Migração de Clientes e Equilíbrio de Preço (v2)

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-canibalizacao.md`  
> **Responsável:** Analista (`business-rules-expert` / `analyst.md`) & Especialista em IA (`ai_specialist.md`)  
> **Referências de Regras:** `.agents/rules/security-anti-patterns.md`, `workflow-documentation-governance-rules.md`, `privacy/analytics-canibalizacao.md` (`LGPD-CAN-01..08`), `ADR-007-canibalizacao.md`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Relatório Global de Canibalização por Migração de Clientes e Equilíbrio de Preço (v2) |
| **Módulo** | `analytics` (`src/modules/analytics/domain/cannibalization_report.py`; índice de afinidade em `domain/product_affinity.py` + `service/product_affinity_service.py`) |
| **Revisão 2026-11-24 (Analista, F7)** | Documentação alinhada ao código em produção (#13): a migração não exige mais o mesmo `Tipo`; é ponderada pelo **Índice de Afinidade Semântica** e agnóstica de fornecedor (P-129.4, P-130 reescritos; nova seção P-130.4 a P-130.12) |
| **Branch** | `feature/analytics-canibalizacao` |
| **Faixa de Regras** | `P-128` a `P-138` (revisão v2 — pivô de DiD isolado para Relatório Global de Migração) |
| **Prefixo de Erro** | `CAN-XXX` (`CAN-001`, `CAN-003`, `CAN-004`, `CAN-005`) + `ANL-001` (503) |
| **Versão do Contrato** | `1.1.0` |
| **Status** | Especificado (v2) — Pronto para Execução (Etapa 3) |

---

## 1. Contexto e Objetivo (Pivô v2)

- **User Story Relacionada:** US-F6 (v2) — *Como gestor comercial ou precificador da Fitoherb, quero visualizar um relatório global dos produtos que estão sendo canibalizados dentro da mesma categoria, identificando exatamente quais produtos estão capturando seus clientes (migração direcional líquida), quanto de faturamento (% e R$) foi perdido para a canibalização e qual ajuste de equilíbrio de preço devo aplicar entre vítima e canibalizador para estancar a erosão de margem.*
- **Objetivo da Feature:**
  1. **Diagnóstico Global de Vítimas:** Listar todos os produtos ativos que perderam faturamento relevante entre períodos comparáveis (`PRE` vs `CUR`) por migração comprovada de clientes para **produtos afins** (Índice de Afinidade Semântica, score ≥ 0,50), de qualquer fornecedor. *(Revisão 2026-11-24: o texto original dizia "mesma categoria (`Tipo`)", critério substituído no código.)*
  2. **Atribuição por Migração Direcional Líquida:** Medir a migração real de clientes que reduziram/pararam o produto A (`PRE`) e passaram/aumentaram a comprar o produto B (`CUR`), descontando o fluxo reverso ($B \to A$) para eliminar ruído bidirecional.
  3. **Diagnóstico de Mecanismo e Equilíbrio de Preço:** Comparar preço e margem unitária de cada par `(Vítima A, Canibalizador B)`, classificar se há destruição de margem e sugerir preços de equilíbrio (`suggestedVictimPrice`, `suggestedCannibalPrice`) que reduzam o gap de preço em ~40% preservando a margem mínima de contribuição.
- **Fora do escopo:** Alteração automática de tabelas de preço no ERP, exposição de códigos/nomes de clientes (LGPD), migração entre produtos **não afins** (score abaixo de 0,50 ou bloqueados pelas travas de compatibilidade, P-130.8). O `Tipo` do ERP deixou de delimitar a migração.

---

## 2. Tabela de Constantes e Parâmetros Numéricos

> [!IMPORTANT]
> Todos os parâmetros abaixo DEVEM ser declarados como constantes no topo de `src/modules/analytics/domain/cannibalization.py`.

| Constante | Valor Padrão | Regra | Significado / Justificativa |
| :--- | :--- | :--- | :--- |
| `ALLOWED_WINDOW_DAYS` | `(30, 60, 90)` | P-128 | Janelas comparáveis selecionáveis pelo usuário (`PRE` vs `CUR`) |
| `DEFAULT_WINDOW_DAYS` | `90` | P-128 | Janela padrão: últimos 90 dias vs 90 dias anteriores |
| `RETURN_OPERATION_PATTERN` | `'DEVOLU%'` | P-128 | Padrão de devoluções abatidas algebricamente no SQL |
| `MIN_PRE_REVENUE` | `500.0` (R$) | P-129 | Faturamento mínimo no período `PRE` para o SKU ser elegível como vítima |
| `DEFAULT_MIN_DROP_PCT` | `5.0` (%) | P-129 | Queda percentual mínima de faturamento de `PRE` para `CUR` (limites API: `1.0` a `80.0`) |
| `DEFAULT_MIN_MIGRATED_CLIENTS` | `3` | P-131 | Mínimo de clientes em migração direcional líquida $A \to B$ (limites API: `1` a `50`) |
| `COST_FALLBACK_RATIO` | `0.60` | P-133 | Custo estimado (60% do preço) quando `Pc.Ultimo Custo` é nulo, $\le 0$ ou $\ge$ preço |
| `PRICE_GAP_THRESHOLD_PCT` | `3.0` (%) | P-134 | Gap mínimo de preço ($P_A > P_B$) para atribuir migração ao fator preço |
| `GAP_REDUCTION_TARGET` | `0.40` (40%) | P-135 | Redução alvo sobre a diferença absoluta $\Delta P = P_A - P_B$ no equilíbrio de preço |
| `MIN_CONTRIBUTION_MARGIN_PCT` | `0.20` (20%) | P-135 | Piso mínimo de margem de contribuição preservado no preço sugerido da vítima |
| `MAX_CANNIBAL_PRICE_HIKE_PCT` | `0.12` (12%) | P-135 | Teto máximo de reajuste sugerido no preço do canibalizador para evitar choque de demanda |
| `MAX_CANNIBALIZERS_PER_VICTIM` | `10` | P-136 | Limite máximo de canibalizadores retornados por vítima no detalhe |
| `CACHE_TTL_HOURS` | `6` | P-137 | TTL do cache em memória indexado por `windowDays` |
| `DEFAULT_TOP_K_AFFINITIES` | `25` | P-130.9 | Vizinhos afins guardados por SKU no índice (`product_affinity.py`) |
| `MIN_STORED_AFFINITY_SCORE` | `0.30` | P-130.9 | Piso de score para um vizinho ser guardado no índice |
| `DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD` | `0.50` | P-130.11 | Score mínimo para um par entrar na migração (e no Grupo Afim da F7 e no Produto Novo) |
| `GALLERY_MATCH_MIN_SCORE` | `0.50` | P-130.5 | Score mínimo para vincular um SKU do ERP a um produto da galeria pública |

---

## 3. Catálogo de Regras de Negócio (P-128 a P-138)

### `P-128`: Janelas Temporais Comparativas (`PRE` vs `CUR`) e Abatimento de Devoluções

- **Declaração Mandatória:** A análise DEVE comparar dois intervalos contíguos e idênticos de `windowDays` dias ($\in \{30, 60, 90\}$, padrão `90`), abatendo devoluções em quantidade e faturamento.
- **Sub-regras:**
  - **P-128.1 (Limites Temporais):** Dada a data de corte exclusiva $D_{ref}$ (data atual / última referência disponível) e $N = \text{windowDays}$:
    - $D_{mid} = D_{ref} - N\text{ dias}$
    - $D_{pre\_start} = D_{ref} - 2N\text{ dias}$
    - **Período Anterior (`PRE`):** $[D_{pre\_start}, D_{mid})$
    - **Período Atual (`CUR`):** $[D_{mid}, D_{ref})$
  - **P-128.2 (Abatimento de Devoluções):** Linhas de `Externo01.Vendas` com `[Operação] = 'VENDA'` ou `[Operação] LIKE 'DEVOLU%'` são somadas algebricamente em `[Qtd Venda]` e `[Valor Venda]`. Saldos líquidos negativos de um par `(cliente, SKU, período)` são truncados em `0.0` antes do cálculo de migração.
- **Exceção:** `windowDays` fora de `{30, 60, 90}` retorna `CAN-004` (HTTP 400). Se não houver movimentação transacional suficiente nas duas janelas para compor o relatório, retorna `CAN-003` (HTTP 422).

---

### `P-129`: Critérios de Elegibilidade de Produto Vítima (Canibalizado)

- **Declaração Mandatória:** Um SKU ativo $A$ só é reportado como vítima de canibalização se apresentar retração real de faturamento e pelo menos um canibalizador válido entre os seus produtos afins (P-130.11).
- **Sub-regras:**
  - **P-129.1 (Catálogo Ativo e Categoria):** $A$ deve existir no catálogo ativo (`Externo01.Produto`) com atributo `Tipo` não vazio. *(O código ainda exige `Tipo` preenchido para a vítima ser elegível; o `Tipo` não restringe mais quem é canibalizador.)*
  - **P-129.2 (Relevância Financeira Prévia):** O faturamento líquido total de $A$ em `PRE` deve satisfazer $R_A^{PRE} \ge \text{MIN\_PRE\_REVENUE}$ (`R$ 500,00`).
  - **P-129.3 (Queda Mínima de Faturamento):**
    $$\text{revenueDrop}_A = R_A^{PRE} - R_A^{CUR} > 0$$
    $$\text{revenueDropPct}_A = \frac{\text{revenueDrop}_A}{R_A^{PRE}} \times 100 \ge \text{minDropPct}$$
    com `minDropPct` padrão `5.0%`.
  - **P-129.4 (Existência de Canibalizador):** $A$ deve possuir ao menos um SKU $B \neq A$ **afim** (P-130.11), ativo, de qualquer fornecedor e de qualquer `Tipo`, que atenda integralmente `P-131`. *(Revisão 2026-11-24: substitui "do mesmo `Tipo`".)*

---

### `P-130`: Cálculo da Migração Direcional Bruta de Clientes entre Produtos Afins (agnóstica de fornecedor)

> *Revisão 2026-11-24 (Analista, F7):* a versão anterior desta regra descrevia a migração "na mesma categoria (`Tipo`)" com alocação por `F_{c,T}`. O código em produção (`compute_directional_migration(rows, catalog, affinity_map)`) usa o **Índice de Afinidade Semântica** como critério de substituição e pondera o fluxo pelo `affinityScore`, sem olhar `Tipo` nem fornecedor. O texto abaixo reflete o código.

- **Declaração Mandatória:** A transferência de demanda entre dois produtos **afins** $A$ e $B$ (de qualquer fornecedor e de qualquer `Tipo`) DEVE ser mensurada individualmente por cliente $c$ em memória volátil, ponderada pela afinidade do par e com conservação de fluxo nos dois lados (sem dupla contagem de receita perdida ou ganha).
- **Sub-regras:**
  - **P-130.1 (Perdas e Ganhos por Cliente):** só entram linhas de SKUs ativos do catálogo com saldo positivo em alguma janela (saldos negativos já truncados em 0, P-128.2) e clientes com pelo menos 2 SKUs no recorte. Para cada cliente $c$ e SKU $j$, com $d_{c,j} = R_{c,j}^{PRE} - R_{c,j}^{CUR}$:
    - Perda: $L_{c,A} = d_{c,A}$ quando $d_{c,A} > 0$;
    - Ganho: $G_{c,B} = -d_{c,B}$ quando $d_{c,B} < 0$.
  - **P-130.2 (Alocação ponderada pela afinidade, sem dupla contagem):**
    1. **Ganhos compatíveis de $A$:** os $B$ com ganho no cliente e $\text{aff}(A,B) > 0$ no mapa de afinidade (que só contém pares com score ≥ 0,50, P-130.11). Peso de cada um: $w_{c,B} = G_{c,B} \times \text{aff}(A,B)$.
    2. **Distribuição da perda de $A$:** $T_c(A \to B) = L_{c,A} \times \dfrac{w_{c,B}}{\sum_{B'} w_{c,B'}}$.
    3. **Teto pelo ganho de $B$:** com $I_{c,B} = \sum_{A} T_c(A \to B)$ (tudo o que chega em $B$ vindo de várias perdas):
       $$M_c(A \to B) = T_c(A \to B) \times \min\left(1, \frac{G_{c,B}}{I_{c,B}}\right)$$
    Garante-se que $\sum_B M_c(A \to B) \le L_{c,A}$ e $\sum_A M_c(A \to B) \le G_{c,B}$. O fornecedor não entra no cálculo: um substituto de outro fornecedor pesa o mesmo que um do mesmo fornecedor com o mesmo score.
  - **P-130.3 (Agregação Bruta do Par $A \to B$):**
    $$\text{grossRev}(A \to B) = \sum_{c} M_c(A \to B), \qquad N_{\text{gross}}(A \to B) = \left|\{c : M_c(A \to B) > 0\}\right|$$
  - **P-130.3a (Fallback sem índice):** se o índice de afinidade não estiver carregado (`affinity_map = None`), a F6 usa como compatível todo $B$ que compartilha ao menos um token de família de produto com $A$ (`extract_product_family_tokens`, sem marca, gramatura e sabor), com peso $w_{c,B} = G_{c,B}$. Consumidores novos (ex.: F7, P-153.3) podem proibir esse fallback.

#### Índice de Afinidade Semântica (sub-regras P-130.4 a P-130.12)

> Fonte única de "produto semelhante" do projeto: usada pela Canibalização (P-130.2), pelo Produto Novo (cold start) e pelo Diagnóstico de Tendência com IA (F7, Grupo Afim). Código: `analytics/domain/product_affinity.py` e `analytics/service/product_affinity_service.py`.

- **P-130.4 (Finalidade e princípio):** o índice DEVE devolver, para cada SKU ativo, a lista em ordem decrescente dos produtos mais substituíveis por ele, com score em $[0, 1]$, **com peso igual entre fornecedores**: tokens de nomes de fornecedor/marca (do ERP e da galeria) são removidos de todo texto vetorizado.
- **P-130.5 (Vínculo ERP × galeria pública):** cada SKU ativo é vinculado a, no máximo, um produto da galeria do fitoherb.com.br (`gallery_client.fetch_fitoherb_gallery_products`) quando:
  - o fornecedor normalizado (só letras e números) é igual, ou um contém o outro;
  - a cobertura dos tokens nucleares do nome do ERP no nome da galeria é ≥ 0,50;
  - a forma física é compatível (iguais, ou o par pó × líquido), os modificadores críticos (`zero`, `kids`, `kit`, `proteica`, `creapure`, `dark`, `hair`, `sem_cafeina`) são idênticos e não há composto (`+`, `c/`, `com`) de um lado só com tokens extras;
  - o score `0,40 × Jaccard + 0,30 × cobertura do nome ERP + 0,30 × cobertura nuclear` é ≥ `GALLERY_MATCH_MIN_SCORE` (0,50); vence o maior score.
  O vínculo traz `gallery_name`, `gallery_description`, `gallery_category` e `presentation`.
- **P-130.6 (Documento de afinidade):** cada SKU vira um texto em dois canais, `núcleo ||| descrição rica`:
  - **Núcleo:** se o nome tem **função primária** (`detect_primary_function`, lista ordenada e mutuamente exclusiva, ex.: `acessorio`, `barraproteina`, `pretreino_sem_cafeina`, `pretreino`, `creatina_composta`, `creatina`, `whey`, `colageno_tipo2`, `colageno_pele`, `omega`, `polivitaminico`, `termogenico`, `cha_infusao`), o núcleo é só essa função (para que nomes fantasia de fornecedores diferentes fiquem próximos); em `cha_infusao`, função + ervas do nome; sem função, os tokens nucleares do ERP e da galeria. Se o nome for sigla/fantasia, a função pode vir da abertura da descrição da galeria (só pré-treino, e nunca para cápsula, chá, barra ou acessório).
  - **Descrição rica:** até 120 palavras da descrição da galeria (sem stopwords, sem quantidades, sem tokens de fornecedor), a categoria da galeria e até 20 palavras de apresentação.
  - Um `content_hash` (SHA-256, 24 caracteres) do documento detecta mudanças.
- **P-130.7 (Vetorização e score):** TF-IDF por canal, normalizado (L2) e combinado com pesos **0,80 núcleo + 0,15 palavras da descrição (1 e 2-gramas) + 0,05 caracteres da descrição (3 a 5-gramas)**; score = similaridade de cosseno, arredondada em 4 casas. *(A docstring de `_vectorize_documents` ainda cita 60/40; vale o código: 80/15/5.)*
- **P-130.8 (Travas de compatibilidade):** antes da seleção, cada par recebe um multiplicador:
  - **0 (bloqueado):** funções primárias diferentes; um lado com função "isolada" (acessório, barras, antissépticos, vinagres, óleo essencial, sabonete, shampoo, condicionador, creme, óleo capilar, chá, polivitamínicos, ômega+Q10) e o outro com função diferente ou sem função; termo negado de um lado presente no núcleo do outro (ex.: "sem cafeína" × cafeína); público diferente (`kids`, `gestante`, `senior`, `mulher`, `homem`, `geral`); modificador `zero` ou `proteica` de um lado só; formas incompatíveis (acessório, tópicos, óleo essencial, comestíveis não cápsula como barra/goma/bala/chá/sachê/spray com outra forma, cápsula × pó/líquido/spray, pó × líquido); em chá, óleo essencial, óleo capilar ou par sem função, ausência de token nuclear comum;
  - **0,50:** composto multiativo × produto isolado com núcleos diferentes;
  - **1,0:** demais pares.
- **P-130.9 (Seleção de vizinhos):** para cada SKU guardam-se os até `DEFAULT_TOP_K_AFFINITIES` (25) vizinhos com score ≥ `MIN_STORED_AFFINITY_SCORE` (0,30) após as travas, em ordem decrescente.
- **P-130.10 (Persistência e sincronismo):**
  - o índice (`meta`, `skus`, `affinities`) é salvo em `data/cache/product_affinity_index.json` por escrita atômica (arquivo temporário + troca) e mantido em memória após a 1ª leitura;
  - o sincronismo incremental (`sync_product_affinity_index`) lê catálogo ativo e galeria, compara `content_hash` com o índice anterior (novos, alterados, removidos, inalterados) e, se houver qualquer mudança, ou `force=true`, ou não houver índice, **recalcula a matriz inteira** preservando documento e hash dos inalterados (o preço é sempre atualizado); sem mudança, só atualiza `last_check_at`;
  - dispara às 00:00 (horário local) por um laço dentro do processo da API e sob demanda em `POST /api/v1/analytics/affinity/sync?force=`; quando recalcula, limpa o cache do relatório de Canibalização;
  - **não há reconstrução automática na partida:** se o arquivo não existir (ex.: cold start no Cloud Run com disco efêmero), o índice fica indisponível até o próximo sincronismo, e a Canibalização usa o fallback de P-130.3a. A ida do índice para o GCS com Cloud Scheduler é a tarefa 7.0 (c) da F7 (Q-8).
- **P-130.11 (Consumo):**
  - **Migração:** `get_affinity_lookup_map(min_score = DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD)` devolve `{A: {B: score}}` só com pares ≥ 0,50, ou `None` sem índice;
  - **Lista de afins:** `get_product_affinities(sku, top_k)` devolve os vizinhos com `description`, `supplier`, `category`, `galleryCategory`, `currentPrice`, `affinityScore` e `sameSupplier` (fornecedor igual ao do SKU, comparado em maiúsculas sem espaços nas pontas; falso se o SKU não tem fornecedor); `None` se não houver índice ou o SKU não estiver nele. Exposto em `GET /api/v1/analytics/affinity/{sku}?topK=` (1 a 50, padrão 20; 404 se ausente);
  - **Produto Novo:** `find_similar_for_new_product(name, description, category, top_k=10)` vetoriza o candidato contra os documentos indexados (score ≥ 0,30).
- **P-130.12 (Limitações conhecidas):** SKUs sem vínculo com a galeria têm documento mais pobre (só nome do ERP); o score é relativo ao vocabulário do catálogo atual (muda quando o catálogo muda); o índice não cobre produtos descontinuados.

---

### `P-131`: Desconto de Fluxo Reverso (Migração Direcional Líquida) e Corte Mínimo

- **Declaração Mandatória:** Para distinguir canibalização real de rodízio aleatório entre produtos equivalentes, o fluxo reverso ($B \to A$) DEVE ser descontado do fluxo direto ($A \to B$).
- **Sub-regras:**
  - **P-131.1 (Fluxo Direcional Líquido):**
    $$\text{netRev}(A \to B) = \max\left(0,\; \text{grossRev}(A \to B) - \text{grossRev}(B \to A)\right)$$
    $$\text{netClients}(A \to B) = \max\left(0,\; N_{\text{gross}}(A \to B) - N_{\text{gross}}(B \to A)\right)$$
  - **P-131.2 (Limiar de Validação do Par):** O produto $B$ é confirmado como canibalizador de $A$ se e somente se:
    $$\text{netClients}(A \to B) \ge \text{minMigratedClients} \quad \text{AND} \quad \text{netRev}(A \to B) > 0$$
    onde `minMigratedClients` tem valor padrão `3`.

---

### `P-132`: Quantificação do Faturamento Canibalizado e KPIs Consolidados

- **Declaração Mandatória:** Para cada vítima $A$ e para o relatório global, o sistema DEVE apurar o valor em R$ e o percentual do faturamento perdido atribuído à canibalização.
- **Sub-regras:**
  - **P-132.1 (Faturamento Canibalizado da Vítima $A$):**
    $$\text{cannibalizedRevenue}_A = \min\left(\text{revenueDrop}_A,\; \sum_{B \in \text{Canibalizadores}(A)} \text{netRev}(A \to B)\right)$$
  - **P-132.2 (Percentual do Faturamento Reduzido Atribuído à Canibalização):**
    $$\text{cannibalizedRevenuePct}_A = \frac{\text{cannibalizedRevenue}_A}{R_A^{PRE}} \times 100$$
    Complementarmente, expõe-se a parcela da queda explicada por canibalização:
    $$\text{dropExplainedPct}_A = \frac{\text{cannibalizedRevenue}_A}{\text{revenueDrop}_A} \times 100$$
  - **P-132.3 (Participação de Cada Canibalizador $B$):**
    $$\text{shareOfCannibalizationPct}_{A \to B} = \frac{\text{netRev}(A \to B)}{\sum_{k} \text{netRev}(A \to k)} \times 100$$
  - **P-132.4 (KPIs Globais do Relatório):**
    - `totalVictims`: quantidade de SKUs vítimas encontrados.
    - `totalCannibalizedRevenue`: soma de `cannibalizedRevenue` de todas as vítimas (R$).
    - `avgCannibalizedRevenuePct`: média ponderada $\frac{\sum \text{cannibalizedRevenue}_A}{\sum R_A^{PRE}} \times 100$.
    - `totalNetMarginImpact`: soma do impacto líquido de margem (R$) em todos os pares válidos (`P-133.4`).
    - `marginDestroyingPairsCount`: contagem de pares classificados como `PRECO_MENOR_DESTROI_MARGEM`.

---

### `P-133`: Comparação de Preço, Margem Unitária e Fallback de Custo

- **Declaração Mandatória:** Cada par `(Vítima A, Canibalizador B)` DEVE ter preço, custo, margem unitária e impacto líquido de margem calculados com regra determinística de fallback.
- **Sub-regras:**
  - **P-133.1 (Preço de Referência $P$):** Utiliza-se `Pc.Venda` do catálogo ativo; caso seja nulo ou $\le 0$, utiliza-se o preço médio efetivo praticado em `CUR` ($R^{CUR} / Q^{CUR}$) ou em `PRE` ($R^{PRE} / Q^{PRE}$).
  - **P-133.2 (Gap Percentual de Preço):**
    $$\text{priceGapPct}_{A,B} = \begin{cases} \frac{P_A - P_B}{P_B} \times 100, & \text{se } P_B > 0 \\ 0.0, & \text{se } P_B = 0 \end{cases}$$
    Valores positivos indicam que a vítima $A$ está mais cara que o canibalizador $B$.
  - **P-133.3 (Margem Unitária e Fallback 60%):**
    - Se `Pc.Ultimo Custo` for válido ($0 < C < P$): $C_{ef} = \text{Pc.Ultimo Custo}$ e `costFallbackUsed = false`.
    - Caso contrário: $C_{ef} = P \times \text{COST\_FALLBACK\_RATIO}$ (`0.60`) e `costFallbackUsed = true` (margem estimada de 40%).
    - Margem unitária: $M_u = P - C_{ef}$; Margem percentual: $m = M_u / P$.
  - **P-133.4 (Impacto Líquido de Margem do Par):**
    $$\text{netMarginImpact}_{A \to B} = \text{netRev}(A \to B) \times (m_B - m_A)$$
    Valores negativos representam destruição direta de margem em R$ causada pela migração de $A$ para $B$.

---

### `P-134`: Classificação do Mecanismo de Canibalização

- **Declaração Mandatória:** Cada par `(Vítima A, Canibalizador B)` DEVE receber exatamente uma classificação dentre as três abaixo:
  - **P-134.1 (`PRECO_MENOR_DESTROI_MARGEM`):** `priceGapPct > PRICE_GAP_THRESHOLD_PCT` (`3.0%`) **E** $M_{u,B} < M_{u,A}$ (ou $m_B < m_A$). O canibalizador está mais barato e entrega menor rentabilidade — prioridade máxima de ajuste comercial.
  - **P-134.2 (`PRECO_MENOR_MARGEM_PRESERVADA`):** `priceGapPct > PRICE_GAP_THRESHOLD_PCT` (`3.0%`) **E** $M_{u,B} \ge M_{u,A}$ (e $m_B \ge m_A$). O canibalizador está mais barato, porém preserva ou melhora a margem unitária.
  - **P-134.3 (`MIGRACAO_POR_VALOR`):** `priceGapPct <= PRICE_GAP_THRESHOLD_PCT` (`3.0%`). Os clientes migraram para um produto de preço equivalente ou superior (valor percebido, embalagem, marca ou ruptura de estoque da vítima).

---

### `P-135`: Motor de Equilíbrio de Preço (Preços Sugeridos e Ação Comercial)

- **Declaração Mandatória:** Para cada par `(Vítima A, Canibalizador B)`, o sistema DEVE calcular os preços sugeridos de equilíbrio (`suggestedVictimPrice`, `suggestedCannibalPrice`) e um resumo acionável (`actionSummary`) visando reduzir o gap de preço em ~40% preservando a margem mínima de contribuição.
- **Sub-regras:**
  - **P-135.1 (Piso de Margem da Vítima e Teto de Reajuste do Canibalizador):**
    $$P_{\text{floor}, A} = \frac{C_{ef, A}}{1 - \text{MIN\_CONTRIBUTION\_MARGIN\_PCT}} = \frac{C_{ef, A}}{0.80}$$
    $$P_{\text{cap}, B} = P_B \times (1 + \text{MAX\_CANNIBAL\_PRICE\_HIKE\_PCT}) = P_B \times 1.12$$
  - **P-135.2 (Cálculo para `PRECO_MENOR_DESTROI_MARGEM`):**
    Com $\Delta P = P_A - P_B > 0$ e redução alvo $\delta_{\text{total}} = \text{GAP\_REDUCTION\_TARGET} \times \Delta P = 0.40 \times \Delta P$:
    1. Aplica-se redução de até metade na vítima, respeitando o piso de margem:
       $$P_A^* = \max\left(P_{\text{floor}, A},\; P_A - 0.50 \times \delta_{\text{total}}\right)$$
    2. A diferença remanescente para atingir 40% de fechamento do gap é aplicada como reajuste no canibalizador, respeitando o teto de 12%:
       $$\delta_A = P_A - P_A^*, \quad \delta_B = \min\left(P_{\text{cap}, B} - P_B,\; \delta_{\text{total}} - \delta_A\right)$$
       $$P_B^* = P_B + \max(0, \delta_B)$$
    3. Todos os preços são arredondados para 2 casas decimais (`round(..., 2)`).
  - **P-135.3 (Cálculo para `PRECO_MENOR_MARGEM_PRESERVADA`):**
    Aplica-se ajuste moderado priorizando competitividade sem sacrificar o piso de margem:
    $$P_A^* = \max\left(P_{\text{floor}, A},\; P_A - 0.25 \times \Delta P\right), \quad P_B^* = \min\left(P_{\text{cap}, B},\; P_B + 0.15 \times \Delta P\right)$$
  - **P-135.4 (Cálculo para `MIGRACAO_POR_VALOR`):**
    Não há distorção negativa de preço; mantém-se $P_A^* = P_A$ e $P_B^* = P_B$, com `actionSummary` recomendando verificar ruptura de estoque (`currentStock`), apresentação ou posicionamento comercial de $A$.
  - **P-135.5 (Gap Projetado e Resumo Acionável):** Calcula-se `projectedPriceGapPct = ((P_A* - P_B*) / P_B*) * 100` e gera-se `actionSummary` objetivo em português (ex.: `"Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."`).

---

### `P-136`: Ordenação, Filtros Dinâmicos e Consulta de Detalhe por SKU

- **Declaração Mandatória:**
  - **P-136.1 (Relatório Global):** `GET /api/v1/analytics/cannibalization/report` ordena vítimas por `cannibalizedRevenue` decrescente, expondo `topCannibal` (maior `netRev`) e resumo de `cannibalizers[]`, além das listas `availableCategories` e `availableSuppliers` para filtros instantâneos. Aceita filtros opcionais: `category`, `supplier`, `mechanism` e `search` (por SKU ou descrição).
  - **P-136.2 (Detalhe por Vítima):** `GET /api/v1/analytics/cannibalization/report/{sku}` retorna o diagnóstico completo da vítima com todos os canibalizadores válidos (até `MAX_CANNIBALIZERS_PER_VICTIM = 10`, ordenados por `netRev` decrescente) e os cálculos completos de equilíbrio de preço. Se o SKU não existir no catálogo ativo, lança `CAN-001` (404). Se o SKU existir mas não estiver sendo canibalizado na janela, retorna `200 OK` com `isCannibalized: false` e `cannibalizers: []`.

---

### `P-137`: Restrições SQL Server, Cache por `windowDays` e Governança LGPD

- **Declaração Mandatória:**
  - **P-137.1 (Validação Somente Leitura e Subquery SQL):** Toda query passa por `is_readonly_query`, DEVE iniciar com `SELECT` (proibido `WITH` CTE), usar subquery `SELECT ... FROM (SELECT ...) AS base GROUP BY ...`, proibido `CONCAT`, e todos os parâmetros de data vão via bind parameters `?`.
  - **P-137.2 (Cache em Memória por `windowDays`):** O relatório base (pré-filtros de visualização, com `minDropPct` e `minMigratedClients` parametrizados ou sobre a matriz agregada de pares por `windowDays`) é cacheado no `AnalyticsCache` com lock concorrente e TTL de `CACHE_TTL_HOURS = 6` horas, indexado por `(windowDays, referenceDate)`.
  - **P-137.3 (LGPD-CAN-01 a LGPD-CAN-06):** `[Cod Cliente]` é selecionado exclusivamente na query de migração (sem nome/CPF/e-mail), processado em estrutura volátil `by_cli` em memória e descartado explicitamente (`del by_cli`) **antes** de gravar no cache ou serializar qualquer DTO. Zero `Cod Cliente` em DTOs, cache ou logs.

---

### `P-138`: Padronização de Erros (`CAN-XXX` / `ANL-001`) e Envelope REST (`1.1.0`)

- **Declaração Mandatória:** Todas as respostas utilizam envelope `{ "data": ..., "meta": ... }` em `camelCase` com `meta.version = "1.1.0"`.
- **Matriz de Erros:**
  - `CAN-001` (`404 Not Found`): SKU não encontrado no catálogo ativo.
  - `CAN-003` (`422 Unprocessable Entity`): Histórico transacional insuficiente nas janelas `PRE`/`CUR` para gerar o relatório.
  - `CAN-004` (`400 Bad Request`): Parâmetros inválidos (`windowDays` fora de `{30,60,90}`, `minDropPct` ou `minMigratedClients` fora dos limites, `sku` não numérico, `mechanism` inválido).
  - `CAN-005` (`500 Internal Server Error`): Erro interno inesperado de processamento (sem stacktrace).
  - `ANL-001` (`503 Service Unavailable`): Indisponibilidade ou timeout do SQL Server.

---

## 4. Enquadramento LGPD (Resumo de Salvaguardas)

Mantém-se o parecer formal de `.agents/docs/privacy/analytics-canibalizacao.md` (**Bypass de RIPD Completo** — Base Legal: Legítimo Interesse Art. 7º, IX):
- **LGPD-CAN-01:** Query SQL seleciona estritamente `[Cod Cliente]`, `[Cod Produto]`, `[Qtd Venda]` e `[Valor Venda]`.
- **LGPD-CAN-02:** Zero identificadores de cliente em payloads JSON.
- **LGPD-CAN-03:** Zero `Cod Cliente` em logs.
- **LGPD-CAN-04:** Dicionário volátil `by_cli` liberado explicitamente (`del by_cli`) logo após o cálculo de migração direcional.
- **LGPD-CAN-05:** Cache armazena exclusivamente métricas agregadas por SKU e par `(Vítima, Canibalizador)`.
- **LGPD-CAN-06:** Mensagens de erro nunca ecoam inputs brutos ou dados de clientes.

---

## 5. Matriz de Cenários e Edge Cases

| ID | Cenário | Comportamento Esperado | HTTP | Código |
| :--- | :--- | :--- | :--- | :--- |
| **C-01** | `GET /report?windowDays=90` com vítimas e migrações válidas | Retorna KPIs globais, lista de vítimas ordenadas por `cannibalizedRevenue`, `availableCategories` e `availableSuppliers` | `200` | — |
| **C-02** | Fluxo bidirecional simétrico ($5$ clientes $A\to B$ e $5$ clientes $B\to A$) | `netClients = 0`, par descartado (não é canibalização) | `200` | — |
| **C-03** | Par com `priceGapPct = +36%` e $M_{u,B} < M_{u,A}$ | Classificado `PRECO_MENOR_DESTROI_MARGEM`; preços sugeridos fecham gap ~40% respeitando piso de margem 20% | `200` | — |
| **C-04** | `Pc.Ultimo Custo` nulo ou $\ge$ preço | Aplica fallback 60% (`costFallbackUsed: true`, margem 40%) | `200` | — |
| **C-05** | `GET /report?windowDays=45` | Rejeita janela não permitida (`{30, 60, 90}`) | `400` | `CAN-004` |
| **C-06** | `GET /report/999999` (SKU inexistente) | Retorna produto não encontrado | `404` | `CAN-001` |
| **C-07** | `GET /report/100234` (SKU ativo sem canibalização na janela) | Retorna `isCannibalized: false`, `cannibalizers: []` | `200` | — |
| **C-08** | Base sem vendas nas janelas `PRE`/`CUR` | Informa insuficiência de histórico | `422` | `CAN-003` |
| **C-09** | Timeout ou erro de conexão no SQL Server | Intercepta e retorna erro sanitizado | `503` | `ANL-001` |
