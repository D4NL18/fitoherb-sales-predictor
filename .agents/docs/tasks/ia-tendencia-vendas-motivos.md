# Plano de Implementação — Diagnóstico de Motivos da Tendência de Vendas com IA (F7)

| Campo | Valor |
| :--- | :--- |
| **Status** | Plano **v2 aprovado** pelo usuário em 2026-11-24 (Q-1..Q-8 decididas); Etapas 1 e 2 em andamento |
| **Data** | 2026-11-23 (v1) · 2026-11-24 (v2) |
| **Branch / worktree** | `claude/ai-sales-trend-analysis-8b0d75` — **precisa de merge de `origin/main` (`b66809a`) antes da Etapa 3**, pois a worktree foi criada em `06e0f78`, antes da F6 |
| **Tipo de demanda** | Categoria A · **T1 Full-Stack** com IA (LLM + busca na web) |
| **Faixa de regras reservada** | `P-150` em diante (P-128..P-138 = canibalização, P-139..P-149 = produto novo) |
| **Prefixo de erro** | `TIA-XXX` (Tendência · IA) |
| **ADR previsto** | `ADR-009-diagnostico-tendencia-ia.md` (ADR-007 = canibalização, ADR-008 = produto novo) |
| **Modelos** | Google **Gemini 4 Hydrogen** (padrão, barato e rápido) e **Gemini 4 Neon** (escalonamento para casos difíceis) |

### O que mudou da v1 para a v2
1. **"Produto semelhante" passa a ter uma fonte única:** o **Índice de Afinidade Semântica** (`analytics/domain/product_affinity.py` + `service/product_affinity_service.py`), em produção desde a F6 (#13) e já adotado pelo Produto Novo. A v1 usava "mesmo `Tipo`" e a similaridade TF-IDF própria do F2, que foi removida.
2. **Canibalização já está em produção** e a migração ficou **agnóstica de fornecedor** (ponderada pelo `affinityScore`). A F7 chama o motor de migração direto, nas janelas da Tendência (1/3/6/12 meses), e separa **mesmo fornecedor × outro fornecedor** com o campo `sameSupplier` do índice.
3. **Produto novo deixou de ser dependência bloqueante:** "lançamento semelhante" = vizinho afim (score ≥ 0,50) cuja 1ª venda cai na janela atual. Só a constante `LAUNCH_CUTOFF_DATE` e o `compute_cannibalization_risk` do F2 são reaproveitados quando ele chegar ao `main`.
4. **Novo diagnóstico de mercado × concorrência:** compara a venda do **grupo afim** (o SKU e seus vizinhos) com a do SKU. Se o grupo inteiro caiu, a causa é de mercado (sazonalidade, clima, economia, regulação); se o grupo ficou estável e o SKU perdeu participação, a causa é concorrência interna. Isso orienta o que o LLM pesquisa na web.
5. **Risco novo:** o índice é salvo em disco local do container (`data/cache/product_affinity_index.json`) e o sincronismo roda às 00:00 dentro do processo. No Cloud Run (escala para zero, disco efêmero) ele se perde e é reconstruído no cold start. A F7 depende dele, então o plano inclui levá-lo para o GCS (§3.5).

---

## 1. Objetivo

Para cada produto (e fornecedor) da tela **Tendência de Vendas**, responder **"por que subiu?"** ou **"por que caiu?"**:

- **Queda:** separar quanto vem de **canibalização por produto afim de outro fornecedor**, **canibalização por produto afim do mesmo fornecedor**, **lançamento afim** (produto novo), **sazonalidade**, **mudança de preço**, **promoção**, **perda de clientes**, **ruptura** e **fatores externos** (clima, política/regulação, matéria-prima, notícias do setor).
- **Alta:** dizer quais fatores explicam o aumento e **quem perdeu venda para ele** (vítimas da migração), separando canibalização interna do portfólio (mesmo fornecedor) de ganho de participação sobre concorrentes (outro fornecedor).
- Toda afirmação traz **evidência**: número interno do sistema ou fonte externa com link e data.

### 1.1 Princípio central: números primeiro, LLM depois
O LLM **não calcula nada e não inventa número**. A solução tem duas camadas:

1. **Motor de Evidências (determinístico, Python):** reaproveita os módulos existentes e decompõe a variação observada em parcelas (cascata). O que nenhum fator interno explica fica num **resíduo**.
2. **Narrador com IA (Gemini 4):** recebe só o pacote de evidências (JSON, sem dado de cliente), pesquisa na web **apenas o que o resíduo e o diagnóstico de mercado pedem** e devolve um diagnóstico estruturado com fatores, peso, confiança e fontes.

---

## 2. Fontes reaproveitadas

| Fator | Fonte no sistema | Situação | Uso na F7 |
| :--- | :--- | :--- | :--- |
| Variação observada | `sales_trend` (P-072..P-093) | Produção | Ponto de partida: `variacaoPct`, estado da célula (`SEM_BASE`, `BASE_BAIXA`…), contribuição em pp no fornecedor |
| **Produtos afins** | `product_affinity_service.get_product_affinities(sku, top_k)` | **Produção (F6)** | Vizinhos ordenados por `affinityScore` com `supplier`, `category`, `galleryCategory`, `currentPrice` e **`sameSupplier`**. Base para canibalização, lançamentos afins e grupo afim |
| **Canibalização** | `cannibalization_report.compute_directional_migration(rows, catalog, affinity_map)` + `sales_repository.fetch_customer_sku_window_sales(pre_start, mid, ref)` | **Produção (F6)** | Migração líquida A→B nas **janelas da Tendência**. Queda: SKU como vítima. Alta: SKU como canibalizador. Mecanismo de preço (`classify_mechanism`, `calculate_price_equilibrium`) reaproveitado para dizer se a migração destrói margem |
| Lançamento afim | Índice de afinidade + 1ª venda do vizinho (`monthly_sales`) | Produção | Vizinho com `affinityScore ≥ 0,50` e 1ª venda na janela atual (e ≥ `LAUNCH_CUTOFF_DATE`, P-139). Quando o F2 chegar ao `main`, reaproveitar `compute_cannibalization_risk` para o selo de risco |
| Sazonalidade | `seasonality.get_seasonality_index` (P-106..P-116) | Produção | Variação esperada pela época do ano (razão dos índices atual × anterior); só com confiança ≠ `BAIXA` |
| Preço / elasticidade | `elasticity.py` (P-095..P-105) | Produção | Δpreço médio praticado × elasticidade = Δvolume esperado por preço |
| Perda de clientes | `churn.py` (P-117..P-127, `evaluate_lost_products`) | Produção | Faturamento anterior de clientes do SKU hoje em risco/inativos e que **não** migraram para um afim (só contagens e somas) |
| Complementos | cross-sell (P-058..P-071) | Produção | Arrasto: âncora caiu/subiu e o complemento acompanhou |
| Ruptura | `inventory` (P-053..P-056) + `current_stock` da F6 | Produção | Estoque atual 0 / `CRITICAL_STOCKOUT`. Sem histórico de estoque (Q-5) |
| Promoções | `fetch_promo_calendar`, `fetch_promo_skus_in_window` | Produção | Participação de venda em promoção atual × anterior, do SKU e dos afins |
| Região | `[UF]` em `Externo01.Vendas` | Dado disponível (query nova) | A variação se concentra em uma UF? Base para correlacionar com clima/evento regional |
| Contexto semântico | `galleryCategory`, `detect_primary_function` do índice | Produção | Função primária (ex.: `creatina`, `pretreino`, `colageno_pele`, `cha_infusao`) e categoria da galeria montam a **consulta de busca** do LLM pelo insumo/categoria, não pelo nome comercial |
| Fatores externos | **novo** — Gemini 4 com busca no Google | A construir | Clima, eventos políticos/regulatórios (ex.: ANVISA para suplementos e fitoterápicos), matéria-prima (safra, câmbio, escassez), notícias do fornecedor/categoria |

> **Documentação defasada:** as regras e o ADR-007 no `main` ainda descrevem a migração "na mesma categoria (`Tipo`)", mas o código usa o índice de afinidade e não documenta `product_affinity`. Antes da Etapa 2 da F7, o `analyst` precisa registrar as regras do índice (limiar 0,50, top-K 25, piso 0,30, travas de função primária/forma/público) para a F7 poder referenciá-las. Sugestão: abrir esse ajuste de documentação na própria F6.

---

## 3. Arquitetura proposta (a formalizar no ADR-009)

### 3.1 Novo módulo `src/modules/trend_insights/`
O `sales_trend` é isolado do `analytics` (ADR-003). O diagnóstico fica num **módulo novo** que consome os dois por **portas**:

```
src/modules/trend_insights/
├── api/            router.py, schemas.py            # /api/v1/sales-trend/insights/*
├── service/        insights_service.py              # orquestra: evidências → cache → LLM
├── domain/
│   ├── evidence.py         # DTOs imutáveis do pacote de evidências
│   ├── windows.py          # converte janela 1/3/6/12 meses + Mês-Base em datas PRE/CUR
│   ├── affinity_group.py   # grupo afim, participação do SKU, diagnóstico mercado × concorrência
│   ├── decomposition.py    # cascata: observado = sazonal + preço + canibalização (mesmo/outro) + lançamento + ... + resíduo
│   ├── factor_rules.py     # limiares e classificação de fatores (sem I/O)
│   └── ports.py            # TrendSource, AffinitySource, MigrationSource, SeasonalitySource, ElasticitySource...
├── adapters/       # implementações das portas chamando sales_trend e analytics (sem duplicar lógica)
├── llm/
│   ├── gemini_client.py    # LlmClient sobre o SDK oficial google-genai, sem LangChain (§3.10): timeout, retry com backoff, tokens, custo
│   ├── prompts/            # prompts modulares versionados
│   └── output_schema.py    # Pydantic do diagnóstico
└── store/          insight_store.py                # diagnósticos persistidos no GCS (§3.5)
```

Toda porta tem implementação "não avaliado": se uma fonte falhar (ex.: índice de afinidade ainda sendo reconstruído), o fator aparece como **"não avaliado"** e a tela não quebra.

### 3.2 Migração nas janelas da Tendência
A F6 trabalha com 30/60/90 dias corridos; a Tendência compara meses (1, 3, 6, 12) terminados no Mês-Base. A F7:

- monta `PRE = [início da janela anterior, início da janela atual)` e `CUR = [início da janela atual, fim do Mês-Base]` com as mesmas datas do `sales_trend` (mesma normalização de cobertura parcial);
- chama `fetch_customer_sku_window_sales(pre_start, mid, ref)` **uma vez por (janela, Mês-Base)** para o catálogo inteiro e passa o resultado para `compute_directional_migration(..., affinity_map=get_affinity_lookup_map())`;
- guarda só o `MigrationSnapshot` (pares A→B agregados, **sem `Cod Cliente`**, o motor já faz `del by_cli`) no cache, TTL 6 h, chave `(janela, mesBase, dataReferencia)`;
- **janela de 12 meses:** a anterior começaria antes do início da base (2025-01) para a maioria dos Mês-Base; nesse caso a migração fica "não avaliado" e a célula segue a regra `SEM_BASE` do `sales_trend`.

Medir memória e tempo da query por janela no banco real (a F6 já lê em blocos de `FETCH_CHUNK_SIZE`); meta de pico abaixo do limite de 2Gi do Cloud Run junto com os outros caches.

### 3.3 Grupo afim: mercado × concorrência
Para o SKU `A`, o **grupo afim** é `A` + vizinhos com `affinityScore ≥ 0,50` (mesmo limiar da F6 e do F2).

| Medida | Cálculo |
| :--- | :--- |
| Variação do grupo | soma da métrica do grupo, atual × anterior |
| Participação de `A` no grupo | `A / grupo`, atual × anterior (em pp) |
| Variação dos afins por fornecedor | soma dos vizinhos `sameSupplier = true` e dos `false`, separadas |

Classificação (limiares finais nas regras P-15X):
- **`MERCADO_EM_QUEDA` / `MERCADO_EM_ALTA`:** grupo variou no mesmo sentido de `A` e a participação de `A` mudou pouco → causas de mercado. O LLM pesquisa clima, economia, regulação e matéria-prima **da categoria**.
- **`PERDA_DE_PARTICIPACAO` / `GANHO_DE_PARTICIPACAO`:** grupo estável ou no sentido oposto e a participação de `A` mudou muito → causas competitivas. A cascata detalha quem ganhou (mesmo × outro fornecedor, lançamento ou não); o LLM pesquisa notícias do fornecedor e dos concorrentes.
- **`MISTO`:** os dois efeitos são relevantes.

Este diagnóstico capta também a concorrência **sem migração comprovada** (o afim cresceu com clientes novos, não com os clientes de `A`), que a F6 sozinha não enxerga.

### 3.4 Cascata de atribuição
Para um SKU, uma métrica (`quantity`/`revenue`) e uma janela:

| Parcela | Cálculo (resumo; fórmulas finais nas regras P-15X) |
| :--- | :--- |
| Observado | `atual − anterior` da célula do `sales_trend` |
| Sazonal esperado | `anterior × (índice médio dos meses da janela atual ÷ índice médio da anterior − 1)` |
| Preço | `anterior × elasticidade × Δpreço%` |
| **Lançamento afim** | `Σ netRev(A→B)` dos canibalizadores `B` que são lançamentos (1ª venda na janela atual) |
| **Canibalização — mesmo fornecedor** | `Σ netRev(A→B)` dos demais `B` com `sameSupplier = true` |
| **Canibalização — outro fornecedor** | `Σ netRev(A→B)` dos demais `B` com `sameSupplier = false` |
| Clientes perdidos | faturamento anterior dos clientes de `A` hoje em risco/inativos, menos o que já migrou para afins |
| Ruptura / promoção | flags com evidência (sem valor enquanto não houver histórico de estoque) |
| **Resíduo** | `observado − Σ parcelas` → o que o LLM tenta explicar com fatores externos |

Regras de sanidade:
- cada `B` entra em **uma só** parcela (lançamento tem prioridade sobre canibalização);
- as parcelas são cortadas para não passar do observado;
- cada parcela leva `confianca` (`ALTA`/`MEDIA`/`BAIXA`) do módulo de origem; migração com `netClients` abaixo do mínimo da F6 (`DEFAULT_MIN_MIGRATED_CLIENTS = 3`) fica como `BAIXA`;
- células `SEM_BASE`/`BASE_BAIXA` recebem diagnóstico só qualitativo;
- métrica `quantity`: a migração da F6 é em R$; converte-se pela razão quantidade/faturamento do SKU no período (ou mostra-se só em R$, decisão do `analyst`).

**Para alta:** mesma cascata com sinal invertido, mais **`impactoEmOutrosProdutos`**: pares em que `A` é o canibalizador (`netRev(B→A)`), com o mecanismo de preço da F6 (`PRECO_MENOR_DESTROI_MARGEM` etc.), separados em canibalização interna (mesmo fornecedor: o portfólio troca seis por meia dúzia, avaliar margem) e ganho sobre concorrentes (outro fornecedor).

### 3.5 Persistência (diagnósticos e índice de afinidade)
O Cloud Run escala para zero e o disco é efêmero.
- **Diagnósticos da IA:** bucket GCS, um JSON por `(sku|fornecedor, métrica, janela, mesBase, dataReferencia, versão do prompt)`, regra de ciclo de vida de 90 dias.
- **Índice de afinidade (pré-requisito, tarefa 7.0):** hoje salvo em `data/cache/product_affinity_index.json` no container e sincronizado por um laço às 00:00 dentro do processo; com escala para zero, ele some e o laço não roda. Proposta: gravar/ler o JSON no mesmo bucket e disparar o sincronismo por **Cloud Scheduler** chamando a rota de sync. Isso também beneficia a F6 e o F2. Precisa do aval do dono da F6 (Q-8).

### 3.6 Camada de IA (Gemini 4)
- **Modelo padrão:** `gemini-4-hydrogen`. **Escalonamento** para `gemini-4-neon` quando resíduo > 50% da variação **e** variação relevante (ex.: ≥ R$ 5 mil ou top 20 do ranking), ou com "análise aprofundada". IDs em variável de ambiente (`TREND_AI_MODEL_DEFAULT`, `TREND_AI_MODEL_DEEP`).
- **Busca externa:** *grounding* com Google Search da API do Gemini. O backend monta as consultas a partir de **função primária e categoria da galeria** (ex.: "creatina preço matéria-prima 2026"), fornecedor, UFs com maior variação, período e o diagnóstico de mercado (§3.3). Fontes voltam como citações (URL, título, data).
- **Saída estruturada obrigatória** (JSON Schema + Pydantic):
  `{ direcao, diagnosticoMercado, resumo, fatores: [{ tipo, sentido, parcelaEstimada?, confianca, evidenciaInterna?, fontes[] }], impactoEmOutrosProdutos[], hipotesesNaoConfirmadas[], recomendacoes[] }`.
  `tipo` ∈ `SAZONALIDADE, PRECO, CANIBALIZACAO_MESMO_FORNECEDOR, CANIBALIZACAO_OUTRO_FORNECEDOR, PRODUTO_NOVO, PERDA_PARTICIPACAO_SEM_MIGRACAO, CLIENTES_PERDIDOS, RUPTURA, PROMOCAO, REGIONAL, CLIMA, POLITICO_REGULATORIO, MATERIA_PRIMA, CONCORRENCIA_MERCADO, OUTRO`.
- **Antialucinação:**
  1. números dos fatores internos são **copiados pelo backend** do Motor de Evidências, nunca lidos da resposta do LLM;
  2. o LLM só pode citar SKUs que estão no pacote de evidências (validação contra a lista);
  3. fator externo sem fonte citada, ou com fonte fora do período, vira **hipótese não confirmada**;
  4. resposta fora do schema → 1 nova tentativa; persistindo, a tela mostra só a cascata com aviso.
- **Prompt injection indireto:** conteúdo da web é dado, nunca instrução; o prompt delimita o material externo, o modelo não tem ferramentas de ação (só busca) e a saída passa por validação estrita. A descrição da galeria (fitoherb.com.br) também é texto externo e recebe o mesmo tratamento. Revisão do `security`.
- **Privacidade:** o pacote enviado ao LLM tem só agregados por produto, fornecedor, categoria e UF. **Nenhum `Cod Cliente`**. Log só de tamanho, modelo, tokens e custo.

### 3.7 Cache, custo e teto de gasto
- **A IA só é chamada quando o usuário aperta o botão "Gerar análise com IA"** (decisão do usuário, 2026-11-24, para evitar desperdício). Abrir o painel "Por que?" mostra apenas a cascata numérica e o grupo afim, que não custam token. Nenhuma rota `GET`, carga de página, cron ou lote chama o LLM; só o `POST /generate`.
- Se já existe diagnóstico no GCS para a mesma chave, o painel mostra o salvo (com a data em que foi gerado) e o botão vira "Gerar de novo", que pede confirmação. "Análise aprofundada" (Neon) é um botão separado, também explícito.
- O botão fica desabilitado enquanto uma geração está em andamento (sem clique duplo) e o backend ignora pedidos repetidos para a mesma chave enquanto houver um em voo.
- Teto diário por variável de ambiente (`TREND_AI_DAILY_BUDGET_USD`); ao atingir, só a cascata. Limite por usuário/minuto.
- Estimativa grosseira (preços de terceiros, confirmar na doc do Google): ~3–5 mil tokens de entrada + busca + ~1 mil de saída → **centavos de dólar por diagnóstico no Hydrogen**, cerca do dobro no Neon, mais a tarifa do grounding.
- **Sem lote noturno nem pré-geração** (descartado pelo usuário).

> **Revisão de custo (2026-11-24, decisão do usuário) — prevalece sobre o texto acima e sobre §3.6/§3.9:**
> - **Neon removido.** Modelo único `gemini-4-hydrogen`; sem escalonamento automático, sem botão "Análise aprofundada" (`deep`).
> - **Fallback de modelo:** `gemini-3.8-flash` (só por falha de infraestrutura do Hydrogen). Preços oficiais (por 1M): Hydrogen US$ 1,50/7,50; Flash US$ 0,75/3,75 até 31/12/2026 e US$ 1,50/7,50 depois.
> - **Teto: US$ 2,00/mês** no total (LLM + grounding + infra). Teto de LLM no livro: US$ 1,80/mês; diário US$ 0,20. Fornecedor: Vertex AI. A IA não escreve números (só marcadores).
> - **Custo por geração:** ~US$ 0,014 (sem grounding) a ~0,018 (com grounding na cota grátis); ~0,046 se o grounding fosse cobrado. Capacidade: **~100 gerações/mês** (~55 no pior caso). Cache hit e resumo por template custam US$ 0.
> - **Como:** cache GCS compartilhado por `evidenceHash`, single-flight, pacote de 8 mil caracteres, saída curta, `thinking low`, grounding só por gate determinístico (≤ 2 consultas), template sem LLM para variação não explicável, livro de gastos no GCS, kill-switch e Billing Budget de US$ 2. Cache de contexto do Gemini **não compensa**. Detalhe e cálculos: `.agents/docs/architecture/trend-insights-llm.md` §14.
> - Regras/constantes/contrato a alterar: `.agents/docs/STATE_IA_TendenciaIA.md` ("Impactos nas regras e no contrato").

### 3.8 API (contrato `trend-insights` 1.0.0, a detalhar pelo `architect`)
| Método | Rota | Descrição |
| :--- | :--- | :--- |
| `GET` | `/api/v1/sales-trend/insights/product/{sku}?metric&window&baseMonth` | Cascata + grupo afim + diagnóstico (do cache, se existir) |
| `POST` | `/api/v1/sales-trend/insights/product/{sku}/generate` | Gera (ou regenera, `deep=true` para Neon) o diagnóstico com IA |
| `GET` | `/api/v1/sales-trend/insights/supplier/{supplierKey}?...` | Agrega a cascata dos produtos do fornecedor e destaca canibalização interna entre eles |
| `GET` | `/api/v1/sales-trend/insights/health` | Modelo configurado, orçamento usado, estado do cache e do índice de afinidade |

Envelope `data`/`meta`, camelCase, erros `TIA-001..` (ex.: `TIA-001` parâmetros, `TIA-002` SKU fora do catálogo ativo, `TIA-003` base insuficiente, `TIA-004` IA indisponível/orçamento esgotado → 503, com a cascata ainda disponível no `GET`, `TIA-005` índice de afinidade indisponível → fatores de afinidade "não avaliado").

### 3.9 Frontend (`frontend/src/app/features/sales-trend/`)
- Ação **"Por que?"** em cada linha abre painel lateral (desktop) ou tela cheia (mobile) com a parte numérica (sem IA).
- Dentro do painel, botão **"Gerar análise com IA"** (e "Análise aprofundada"); só ele dispara o LLM (§3.7).
- **Selo de diagnóstico de mercado** no topo ("Mercado em queda" × "Perdeu participação").
- **Cascata (waterfall):** sazonalidade, preço, lançamento afim, canibalização mesmo fornecedor, canibalização outro fornecedor, clientes perdidos, resíduo.
- **Grupo afim:** lista dos vizinhos com afinidade (%), fornecedor, variação e se ganhou clientes de `A`; link para o relatório de Canibalização e o drawer de equilíbrio de preço já existentes.
- **Diagnóstico da IA:** resumo, fatores com selo de confiança, fontes clicáveis com data, hipóteses separadas das evidências, e bloco "Esta alta está tirando vendas de…" nas altas.
- Estados: carregando (skeleton), gerando IA (~10–30 s), sem base, IA indisponível/orçamento esgotado (só cascata), índice de afinidade reconstruindo, erro.
- Aviso fixo: "Diagnóstico gerado por IA a partir de dados internos e notícias públicas; confira as fontes".
- Reusar componentes da F6 (`searchable-combobox`, pipes `pt-br-format`, `analytics-error`) em vez de duplicar.

### 3.10 Orquestração do LLM: sem LangChain e sem LangGraph (decisão 2026-11-24)
Avaliado com as skills `langchain-expert` e `langgraph-expert`. **Decisão: SDK oficial `google-genai` atrás de uma interface própria (`LlmClient` em `llm/gemini_client.py`), com o fluxo em Python puro.**

O fluxo da F7 é curto e fixo: `evidências → cache? → montar prompt → Gemini (Hydrogen) → validar schema → [1 nova tentativa | escalar Neon] → gravar | fallback`. Uma chamada de LLM por diagnóstico, sem conversa, sem RAG e sem agentes.

| Critério | LangChain | LangGraph | SDK direto |
| :--- | :--- | :--- | :--- |
| Ganho real na F7 | Troca de fornecedor de LLM; já resolvida pela interface `LlmClient` | Arestas condicionais e checkpointer; o fluxo tem 1 desvio e não precisa de estado entre requisições | — |
| Grounding com Google Search e citações | Depende do wrapper `langchain-google-genai` expor a ferramenta e o `grounding_metadata` dos modelos Gemini 4 (lançados há poucos dias); risco de perder as fontes, que são requisito central | Mesmo risco (usa os modelos do LangChain) | Acesso nativo e imediato a grounding, saída estruturada e metadados de citação |
| Saída estruturada + busca na mesma chamada | Combinação nem sempre suportada pelo `with_structured_output` | Idem | Controle total; se a API não combinar os dois, fazemos 2 chamadas explícitas |
| Custo de infraestrutura (Cloud Run 2Gi, cold start) | `langchain-core` + integrações | + `langgraph` | Só `google-genai` |
| Testabilidade | Precisa mockar o Runnable | Bom (nós isolados) | Igual: cada etapa é uma função pura testável; o cliente é mockado pela interface |

**Boas práticas das skills que entram mesmo sem as bibliotecas:**
- estado do diagnóstico em DTO imutável tipado; cada etapa é uma função de responsabilidade única que devolve só o que mudou;
- retry com backoff exponencial e **limite fixo de tentativas** (1 nova tentativa por schema inválido, até 3 por erro transitório de rede/rate limit);
- caminhos de erro explícitos (fallback para a cascata numérica), nunca exceção crua para a tela;
- log estruturado por etapa (nome, latência, modelo, tokens, custo, status), sem payload e sem PII;
- prompts modulares compostos por blocos (persona, instruções de fatores, evidências, formato de saída), versionados.

**Quando revisitar (gatilhos para adotar LangGraph):** se a F7 evoluir para uma investigação agêntica em que o LLM decide sozinho quais dados internos consultar (ex.: "abra por UF", "veja as promoções dos afins") em várias rodadas (ciclo ReAct), se houver chat de acompanhamento sobre o diagnóstico (memória por `thread_id`) ou se surgir um segundo agente (ex.: revisor de fontes). Nesse caso, o `LlmClient` e as funções de etapa viram nós do grafo sem reescrever o domínio.

---

## 4. Fases de entrega

| Fase | Entrega | Depende de |
| :-: | :--- | :--- |
| **7.0** | (a) Merge de `origin/main` nesta worktree. (b) Documentar as regras do Índice de Afinidade (lacuna na doc da F6). (c) Índice de afinidade persistido no GCS + Cloud Scheduler (Q-8) | Nada; (c) depende de Q-8 |
| **7.1** | Motor de Evidências sem IA: janelas, migração nas janelas da Tendência, grupo afim, cascata completa (incluindo canibalização mesmo × outro fornecedor e lançamento afim); rota `GET`; testes sintéticos | 7.0 (a) |
| **7.2** | Cliente Gemini (Hydrogen/Neon), prompts versionados, grounding, schema, antialucinação, GCS, teto de gasto; rota `POST /generate` | 7.1 |
| **7.3** | Frontend: painel "Por que?", cascata, grupo afim, diagnóstico e fontes | 7.1 (cascata) e 7.2 (IA) |
| **7.4** | Visão por fornecedor (canibalização interna do portfólio do fornecedor) | 7.1 |
| **7.5** | Avaliação com 30–50 casos reais rotulados pelo time comercial: concordância do fator principal, taxa de fontes válidas, precisão do diagnóstico mercado × concorrência | 7.2 |

Produto Novo (F2) **não bloqueia** nenhuma fase. Quando chegar ao `main`, a F7 passa a usar `LAUNCH_CUTOFF_DATE` e `compute_cannibalization_risk` do F2 (tarefa pequena, dentro da 7.1 ou depois).

---

## 5. Rota da esteira (Triagem Prévia)

| Pergunta de impacto | Resposta | Consequência |
| :--- | :--- | :--- |
| 1. Novo escopo? | Sim | `analyst` (regras P-150+ e a doc do índice de afinidade). `product_owner` dispensado: escopo fatiado aqui |
| 2. UI? | Sim | `designer` (Design Plan, reusando o padrão Papel & Tinta da F6/F2) e `ux_reviewer` |
| 3. Banco? | Não no ERP (só leitura); persistência em GCS | `dba` dispensado; `architect` define o armazenamento |
| 4. PII / decisão automatizada? | Lê `Cod Cliente` só dentro do motor de migração da F6 (já aprovado em LGPD-CAN); nada sai do processo | `privacy_officer` em **revisão leve**: zero `Cod Cliente` no cache, no pacote do LLM e nos logs |
| 5. Superfície crítica? | Sim: chave de API, conteúdo externo no prompt, custo | `security` dedicado na Etapa 4 |
| 6. LLM? | Sim | `ai_specialist` nas Etapas 2 e 3 |
| 7. Release? | Sim, Cloud Run | `devops`: `GEMINI_API_KEY` no Secret Manager, bucket GCS com ciclo de vida, Cloud Scheduler do índice, orçamento |

**Etapas:** 1 `analyst` → 2 `architect` + `ai_specialist` + `designer` (+ `privacy_officer` leve) → **Checkpoint** → 3 `tester` → `developer` + `ai_specialist` → 4 `reviewer` + `security` + `ux_reviewer` + `tester` → 5 `devops`. Opcional: `ai_governance_auditor` na avaliação da fase 7.5.

---

## 6. Testes (TDD)
- **Janelas:** 1/3/6/12 meses + Mês-Base geram as mesmas datas PRE/CUR do `sales_trend`; 12 meses sem base anterior → migração "não avaliado".
- **Cascata:** séries sintéticas com causas plantadas (ex.: queda de 30% = 10 pp sazonal + 12 pp canibalização outro fornecedor + 3 pp mesmo fornecedor + 5 pp preço) recuperadas dentro da tolerância; soma das parcelas nunca passa do observado; cada `B` em uma só parcela; devolução abatida.
- **Mesmo × outro fornecedor:** migração para vizinho com `sameSupplier = true` vai para a parcela certa, e vice-versa.
- **Lançamento afim:** vizinho com 1ª venda na janela atual vira `PRODUTO_NOVO`, não canibalização.
- **Grupo afim:** grupo caiu junto → `MERCADO_EM_QUEDA`; grupo estável e participação caiu → `PERDA_DE_PARTICIPACAO`; afim cresceu sem migração → `PERDA_PARTICIPACAO_SEM_MIGRACAO`.
- **Alta com canibalização:** SKU em alta que recebe `netRev` de uma vítima aparece em `impactoEmOutrosProdutos` com o mecanismo de preço.
- **Índice indisponível:** porta de afinidade falha → fatores afins "não avaliado", resto da cascata funciona.
- **LLM com dublê:** resposta fora do schema → nova tentativa → fallback; fator externo sem fonte → hipótese; número do LLM ignorado; SKU citado fora do pacote é descartado.
- **Privacidade:** teste inspeciona o payload do LLM e o cache e falha se houver `Cod Cliente`.
- **Orçamento:** teto estourado → `POST /generate` devolve `TIA-004`, `GET` continua com a cascata.
- **Prompt injection:** página e descrição de galeria simuladas com "ignore as instruções…" não alteram schema nem fatores.

---

## 7. Riscos e limitações
- **Índice de afinidade efêmero no Cloud Run** (§3.5): sem a tarefa 7.0 (c), o primeiro pedido após o cold start pode pegar o índice ainda sendo reconstruído (busca na galeria + TF-IDF), e os fatores afins ficam "não avaliado".
- **Qualidade do índice:** a F6 calibrou pesos e travas auditando 1.339 SKUs, mas produtos sem par na galeria têm documento mais pobre. A F7 mostra o `affinityScore` e não usa vizinhos abaixo de 0,50.
- **Migração mede só clientes que já compravam `A`.** Perda de participação para clientes novos do concorrente aparece no grupo afim (§3.3), não na migração.
- **Base curta (~23 meses):** sazonalidade com no máximo 2 ciclos e janela de 12 meses quase sempre sem base anterior.
- **Sem histórico de estoque:** ruptura passada não é mensurável (Q-5).
- **Correlação ≠ causa:** fatores externos sempre aparecem como "possível" com fonte, e o resíduo mostra quanto ficou sem explicação numérica.
- **Modelos recém-lançados (Hydrogen 12/11/2026, Neon 18/11/2026):** confirmar ID, preço, grounding e saída estruturada na documentação oficial do Google antes da Etapa 3; cliente atrás de interface para trocar de modelo.

---

## 8. Decisões pendentes do usuário (Checkpoint)

| # | Pergunta | Recomendação |
| :-: | :--- | :--- |
| Q-1 | ~~Diagnóstico sob demanda ou também em lote noturno?~~ | **Decidido (2026-11-24):** só ao apertar o botão "Gerar análise com IA"; sem lote |
| Q-2 | Hydrogen padrão, Neon no escalonamento/"análise aprofundada" | ~~Aprovado~~ **Revisado (2026-11-24): só Hydrogen; Neon removido; `gemini-3.8-flash` como fallback** |
| Q-3 | Diagnósticos em GCS | **Aprovado (2026-11-24)** |
| Q-4 | Teto de gasto com IA | ~~US$ 30/mês~~ **Revisado (2026-11-24): US$ 2,00/mês no total**, configurável por variável de ambiente. Neon removido; Flash como fallback (§3.7) |
| Q-5 | Histórico de estoque no ERP | **Aprovado (2026-11-24):** verificar com `/banco` na Etapa 3; até lá a regra assume só estoque atual |
| Q-6 | Limiar do grupo afim 0,50 (igual F6/F2) | **Aprovado (2026-11-24)** |
| Q-7 | Produto primeiro, fornecedor na 7.4 | **Aprovado (2026-11-24)** |
| Q-8 | Índice de afinidade no GCS + Cloud Scheduler | **Aprovado (2026-11-24):** tarefa 7.0 (c) separada |
