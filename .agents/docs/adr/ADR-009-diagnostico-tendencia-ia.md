# ADR-009: Diagnóstico de Motivos da Tendência de Vendas com IA (F7): módulo `trend_insights` por portas, migração nas janelas da Tendência, persistência em GCS e Gemini 4 Hydrogen (fallback Gemini 3.8 Flash) via Vertex AI, sem LangChain/LangGraph, com teto de US$ 2/mês

> **Status:** Proposto (Etapa 2). **Revisão v2 (2026-11-24):** incorpora as decisões do usuário (Hydrogen sempre, Neon removido, fallback Gemini 3.8 Flash, teto de US$ 2/mês, Vertex AI, texto da IA sem números, geração só por botão) e a estratégia de custo do `ai_specialist` (`trend-insights-llm.md` §14). Aguarda o checkpoint do usuário nos pontos que seguem abertos (CP-10).
> **Data:** 2026-11-24
> **Autor:** Arquiteto (`architect.md`)
> **Localização Mandatória:** `.agents/docs/adr/ADR-009-diagnostico-tendencia-ia.md`

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | F7 — Diagnóstico de Motivos da Tendência de Vendas com IA. Worktree `claude/ai-sales-trend-analysis-8b0d75` (com `origin/main` mesclado, F6 incluída) |
| **Plano aprovado** | `.agents/docs/tasks/ia-tendencia-vendas-motivos.md` (v2, Q-1..Q-8 decididas em 2026-11-24) |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-tendencia-ia.md` (`P-150` a `P-188`, erros `TIA-001` a `TIA-007`; revisões v2 de P-174..P-181, P-183 e P-185.4 a cargo do `analyst`) |
| **Contrato de API** | `.agents/docs/api_contracts/sales-trend-insights.md` (`trend-insights` **1.1.0**) |
| **Checklist técnico** | `.agents/docs/tasks/analytics-tendencia-ia.md` |
| **Camada de IA (prompt, schema, grounding)** | `.agents/docs/architecture/trend-insights-llm.md` (responsável: `ai_specialist`; este ADR só referencia) |
| **ADRs relacionados** | `ADR-003` (isolamento do `sales_trend`), `ADR-007` (migração direcional da F6, `MigrationSnapshot`, LGPD-CAN) |
| **Parecer de privacidade** | `.agents/docs/privacy/analytics-tendencia-ia.md` (aprovado com condições `LGPD-TIA-01..14`, RIPD não exigido) |
| **Design Plan** | `.agents/docs/design/plans/analytics-tendencia-ia.md` (dúvidas Q-D1..Q-D9 respondidas no contrato §5.1) |

---

## 1. Contexto do Problema

1. **Pergunta de negócio.** A Tendência de Vendas mostra *quanto* cada SKU subiu ou caiu em janelas de 1/3/6/12 meses. O gestor precisa saber *por quê*: sazonalidade, preço, lançamento afim, canibalização (mesmo × outro fornecedor), clientes perdidos, ruptura, promoção, região e fatores externos. Os módulos que medem cada causa já existem (Tendência, Sazonalidade, Elasticidade, Churn, Canibalização e Índice de Afinidade), mas não conversam.
2. **Isolamento herdado.** O ADR-003 proíbe o `sales_trend` de importar `analytics`. A F7 precisa dos dois.
3. **Janelas incompatíveis.** A F6 mede migração em 30/60/90 dias corridos com `PRE` e `CUR` contíguos. A Tendência compara meses com `comparisonMode` ∈ {`point`, `average`}. No `point` com X > 1, `CUR = [M]` e `PRE = [M − X]` **não são contíguos**, e `fetch_customer_sku_window_sales(pre_start, mid, ref)` não consegue representá-los (achado 1 do `analyst`, P-153.1).
4. **Índice de afinidade efêmero.** `product_affinity_service` grava o índice em `data/cache/product_affinity_index.json` (disco do contêiner) e o atualiza num laço `asyncio` às 00:00 dentro do processo. O Cloud Run escala para zero (`--min-instances=0`, `--cpu-throttling`): o arquivo some a cada instância nova, o laço quase nunca dispara e não há reconstrução no cold start. A F7 proíbe o fallback por palavras da F6 (P-153.3), então sem índice ela perde metade do diagnóstico (achado 3).
5. **LLM com custo, latência e superfície de ataque.** Gemini 4 Hydrogen (fallback Gemini 3.8 Flash) pelo **Vertex AI**, com *grounding* no Google Search, só por botão (Q-1), **teto total de US$ 2,00/mês** (revisão v2; antes US$ 30), conteúdo da web dentro do prompt e instâncias efêmeras (até 3) que precisam compartilhar orçamento, trava de voo e diagnósticos salvos. Com escala a zero, nada em memória sobrevive: cache, livro de gastos e travas ficam no GCS.
6. **Memória.** O contêiner tem 2Gi e já carrega os snapshots de `pricing`, `analytics` e `sales_trend`. A leitura por `(cliente, SKU)` é a etapa mais pesada da F7.

---

## 2. Decisão Arquitetural

### DA-01 — Módulo novo `src/modules/trend_insights/` (portas e adaptadores)

```
src/modules/trend_insights/
├── __init__.py
├── config.py                 # TrendInsightsSettings (frozen), lido do ambiente uma vez; nenhum segredo em log
├── api/
│   ├── router.py             # insights_router (prefix="/sales-trend/insights", route_class=InsightsAPIRoute)
│   ├── internal_router.py    # internal_router (prefix="/internal/v1"): sync do índice (DA-06)
│   ├── route.py              # InsightsAPIRoute: validação -> 400 TIA-001; exceções de porta -> TIA/ANL (DA-11)
│   ├── query_params.py       # InsightsQuery, GenerateBody
│   ├── schemas.py            # Pydantic camelCase (alias_generator=to_camel)
│   └── mappers.py            # domínio -> schemas; arredondamento só na saída (P-169.6)
├── service/
│   ├── insights_service.py   # casos de uso: get_product_insight, generate_product_insight, get_health
│   ├── migration_cache.py    # TrendMigrationSnapshot por chave, voo único, TTL, LRU (DA-04)
│   ├── evidence_cache.py     # EvidencePackage por chave completa, TTL, LRU (DA-05)
│   ├── generation_guard.py   # dedup em voo (local + lease GCS), rate limit, orçamento (DA-08, DA-09)
│   └── llm_orchestrator.py   # fluxo fixo: kill-switch -> cache -> gates -> reserva -> Hydrogen -> [Flash] -> validação -> template (DA-10, DA-12)
├── domain/                   # Python puro: sem I/O, sem fastapi, pyodbc, google-*, src.core
│   ├── constants.py          # constantes da seção 2 das regras (as "(reuso)" são importadas, não redeclaradas)
│   ├── exceptions.py         # TrendInsightsDomainException, TIA-001..003
│   ├── windows.py            # TrendWindowSpec: datas PRE/CUR e fator k a partir de window_pair (P-151)
│   ├── evidence.py           # DTOs imutáveis: EvidencePackage, CascadeParcel, AffineNeighbor, ImpactedProduct...
│   ├── cell_mode.py          # estado da célula -> QUANTITATIVO | QUALITATIVO | SEM_VARIACAO (P-152)
│   ├── migration_scaling.py  # aplica k às linhas (P-153.2) e agrega clientes perdidos (P-164)
│   ├── affinity_group.py     # grupo afim, shift-share, diagnóstico de mercado (P-154..P-156)
│   ├── decomposition.py      # cascata, corte, resíduo, altas e impacto em outros produtos (P-157..P-171)
│   ├── supplier_rollup.py    # visão por fornecedor (P-172, fase 7.4)
│   ├── model_policy.py       # Hydrogen -> Flash só por falha de infraestrutura (P-177 revisada, DA-12)
│   ├── budget.py             # níveis NORMAL/ALERTA/ESGOTADO, reserva e acerto (P-178 revisada), usando llm/pricing.py
│   ├── gates.py              # gates de não chamada e de grounding (P-188, P-180; DA-12), funções puras
│   ├── template_summary.py   # resumo determinístico sem LLM (DA-12)
│   └── ports.py              # Protocol de cada fonte (lista abaixo)
├── adapters/                 # implementações das portas; ÚNICO lugar que importa outros módulos
│   ├── trend_adapter.py      # sales_trend: snapshot, compute_cell, catálogo ativo, 1ª venda por SKU
│   ├── affinity_adapter.py   # analytics.product_affinity_service
│   ├── migration_adapter.py  # analytics.sales_repository (variante 4 datas) + compute_directional_migration
│   ├── seasonality_adapter.py, elasticity_adapter.py, churn_adapter.py, stock_adapter.py,
│   └── promo_adapter.py, region_adapter.py, price_equilibrium_adapter.py
├── store/
│   ├── insight_store.py      # diagnósticos salvos no GCS (DA-07)
│   └── budget_ledger.py      # livro de gastos no GCS com reserva e CAS (DA-09)
├── llm/                      # layout e conteúdo: .agents/docs/architecture/trend-insights-llm.md (ai_specialist)
│   ├── client.py             # porta LlmClient + DTOs (LlmRequest, LlmResponse, LlmUsage, GroundingCitation)
│   ├── gemini_client.py      # adaptador google-genai em modo Vertex AI com ADC (ÚNICO arquivo de llm/ com I/O)
│   ├── prompts/tia_v2/       # blocos versionados (PROMPT_VERSION = "tia-v2")
│   ├── output_schema.py      # Pydantic da resposta do LLM
│   ├── evidence_payload.py   # pacote P-179 por lista branca (LGPD-TIA-03/04/06)
│   ├── search_queries.py     # consultas sugeridas (P-180, LGPD-TIA-12)
│   ├── validation.py         # antialucinação P-181/P-182, funções puras
│   └── pricing.py            # custo por chamada (tokens + consultas executadas), função pura
└── diagnostics/
    └── run_migration_memory_report.py  # CLI somente leitura: memória, linhas, tempo por (modo, janela) (DA-04)
tests/trend_insights/          # pasta própria
```

**Portas (`domain/ports.py`, `typing.Protocol`).** `TrendSource`, `AffinitySource`, `MigrationSource`, `SeasonalitySource`, `ElasticitySource`, `ChurnSource`, `StockSource`, `PromoSource`, `RegionSource`, `PriceEquilibriumSource`, `InsightStore`, `BudgetLedger`, `InFlightLease`, `LlmClient`. Cada método devolve um resultado tipado **ou** um `NotEvaluated(reason)` (P-173): a falha de uma fonte vira `NAO_AVALIADO` com `motivoNaoAvaliado` e o diagnóstico segue. A única exceção que interrompe é `TrendSourceUnavailable` (a própria célula, `503 ANL-001`).

**Regras de dependência (verificadas por teste de importação no `tester`):**

| Camada | Pode importar | Não pode importar |
| :--- | :--- | :--- |
| `trend_insights/domain` | stdlib, `pydantic` (só DTOs), **funções puras** de `sales_trend.domain` (`window_pair`, `covered_days`, `days_in_span`, `WINDOW_SIZES_MONTHS`, constantes) e de `analytics.domain` (constantes de afinidade/canibalização/churn, `calculate_price_equilibrium`, `classify_mechanism`) | `fastapi`, `pyodbc`, `google.*`, `src.core.*`, qualquer `service`/`repository`/`api` de outro módulo |
| `trend_insights/adapters`, `store/`, `llm/gemini_client.py` | `service` e `repository` de `sales_trend` e `analytics`, `src.core.*`, `google.genai` (só `gemini_client.py`), `google.cloud.storage` (via `src/core/object_storage.py`) | `trend_insights/api` |
| demais arquivos de `trend_insights/llm` | mesmas restrições do `domain` (funções puras) | SDKs, I/O |
| `trend_insights/service` | `domain`, `ports`, `store`, `config` (adaptadores chegam por injeção na montagem do router) | SDKs diretamente |
| `trend_insights/api` | `service`, `schemas`, `mappers` | regra de negócio (nenhum `if` de domínio no router) |
| `sales_trend` (inalterado) | — | `trend_insights`, `analytics` (ADR-003 continua valendo) |

**Pontos de contato com código existente (aditivos, sem mudar contratos 1.0.0/1.1.0):**
1. `src/api.py`: 2 `import` + 2 `include_router` (`insights_router` com prefixo `/api/v1`, `internal_router` sem prefixo); remoção do laço `_daily_affinity_cron` (DA-06).
2. `src/core/auth.py`: isenção do Basic Auth **somente** para `POST /internal/v1/affinity-index/sync`, que exige token OIDC do Google (DA-06).
3. `src/core/object_storage.py` (novo): wrapper fino do GCS usado por `analytics` (índice) e `trend_insights` (diagnósticos, orçamento, travas). É a extração para `src/core/` prevista no ADR-003 quando um terceiro módulo precisasse do mesmo mecanismo.
4. `analytics/repository/sales_repository.py`: 2 funções novas (`fetch_customer_sku_split_window_sales`, `fetch_sku_region_window_sales`). Toda SQL que lê `Cod Cliente` continua num único arquivo auditado pela LGPD-CAN.
5. `analytics/service/product_affinity_service.py`: carga/gravação por `AffinityIndexStore` (local ou GCS) e refresh por geração (DA-06).
6. `analytics/service/analytics_service.py`: função pública `get_cannibalization_catalog()` (hoje só existe a privada `_get_cannibalization_catalog_cached`).
7. `requirements.txt`: `google-genai` e `google-cloud-storage` (versões fixadas na Etapa 3 após confirmar suporte aos modelos Gemini 4). Importados de forma preguiçosa nos adaptadores para não pesar o cold start de rotas que não os usam.

### DA-02 — Fluxo do diagnóstico

```
GET /insights/product/{sku}                       POST /insights/product/{sku}/generate
        │                                                   │
        ▼                                                   ▼
 validar (400 TIA-001) ─► TrendSource.cell ──► 503 ANL-001 se a base cair
        │  404 TIA-002 / 422 TIA-003                        │
        ▼                                                   │
 EvidenceCache.get_or_build(chave) ◄────────────────────────┤ (mesmo pacote)
   ├─ windows.py (datas, k)                                 │
   ├─ MigrationCache (DA-04) ─ NAO_AVALIADO se índice/cobertura faltar
   ├─ AffinitySource ─ grupo afim, shift-share, P-156      │
   ├─ Seasonality/Elasticity/Churn/Stock/Promo/Region      │
   └─ decomposition.py ─ cascata, corte, resíduo, impacto  │
        │                                                   ▼
        ▼                                       modo SEM_VARIACAO? ─► 422 TIA-003
 InsightStore.get(chave) (só leitura,           InsightStore.get(chave) e !force ─► devolve salvo (reutilizado)
   zero token, P-174)                           gates e kill-switch (DA-12) ─► rate limit (429) ─► reserva de orçamento (negada = template)
        │                                         ─► lease local+GCS (dedup, DA-08)
        ▼                                       LlmOrchestrator (DA-10) ─► validação P-181/P-182
 200 { cascata, grupoAfim,                      ─► InsightStore.put (só sucesso, P-175.5)
       diagnosticoIa | null }                   ─► BudgetStore.add(custo real)
                                                200 { ..., diagnosticoIa } (ou fallback 200 sem IA)
```

- **Chave do diagnóstico (P-175 revisada, DA-12):** `(escopo, id, metric, window, baseMonth, comparisonMode, PROMPT_VERSION, evidenceHash)`. `dataReferencia` **saiu da chave**: carga nova do ERP com evidência arredondada igual reaproveita o diagnóstico salvo (custo US$ 0).
- **`dataReferencia` única:** a da **snapshot da Tendência** (`SalesTrendSnapshot.reference_date`, data de negócio UTC−3). Ela deixa de compor a chave do diagnóstico (DA-12), mas continua como corte da migração: para que célula e migração vejam os mesmos dias. (A F6 usa `datetime.now(timezone.utc).date()`; a diferença não afeta a F7 e fica registrada como débito da F6.)
- **Nenhuma rota `GET` recebe o `LlmClient`** por injeção: o router do `GET` monta o serviço sem o cliente. O teste de P-174 usa dublê com contador.

### DA-03 — Janelas: `TrendWindowSpec` reaproveita `window_pair`

`domain/windows.py` recebe `(baseMonthIndex, window, comparisonMode, firstSaleDate, lastCoveredDay)` e devolve:

```
TrendWindowSpec(pre_start, pre_end_exclusive, cur_start, cur_end_exclusive,
                pre_covered_days, pre_total_days, cur_covered_days, cur_total_days,
                scale_k: Fraction, is_previous_fully_covered: bool, is_contiguous: bool)
```

- Meses vêm de `window_pair(base, X, mode)` (P-151, sem reimplementar aritmética). `pre_end_exclusive` = 1º dia do mês seguinte ao último mês de `PRE`; `cur_end_exclusive` = `min(1º dia após o Mês-Base, dataReferencia)` (o corte da Tendência é `[Data] < dataReferencia`); `pre_start = max(1º dia do 1º mês de PRE, primeiraData)`.
- `k` exatamente como `compute_cell` (P-151.3), em `Fraction`. Teste de propriedade: `Δobs ÷ baseAjustada × 100` reproduz `variacaoPct` da célula com diferença ≤ 0,05 pp para 1/3/6/12 × `point`/`average` × Mês-Base cheio/parcial.
- O modo `range` não é aceito na API (P-151.1) mas o `TrendWindowSpec` o suporta sem código extra, porque vem do `window_pair`.

### DA-04 — Migração nas janelas da Tendência (achado 1)

**Uma única variante de leitura com 4 datas, usada em todos os modos.** Em vez de dois caminhos (contíguo × não contíguo), a F7 usa sempre `fetch_customer_sku_split_window_sales(pre_start, pre_end, cur_start, cur_end)`; nos modos contíguos `pre_end == cur_start` e o resultado é idêntico ao de `fetch_customer_sku_window_sales` (o `tester` prova a equivalência com a mesma massa). A função da F6 fica intacta e a F7 **nunca** a chama: **4 datas sempre** (reafirmado na revisão v2), inclusive em `average` e quando `pre_end == cur_start`.

```sql
SELECT
    base.customer_code,
    base.sku,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_qty ELSE 0 END) AS pre_qty,
    SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) AS pre_rev,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_qty ELSE 0 END) AS cur_qty,
    SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) AS cur_rev
FROM (
    SELECT
        [Cod Cliente] AS customer_code,
        [Cod Produto] AS sku,
        CASE WHEN [Data] >= ? THEN 1 ELSE 0 END AS period_flag,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Qtd Venda]) ELSE [Qtd Venda] END AS net_qty,
        CASE WHEN [Operação] LIKE '{RETURN_OPERATION_PATTERN}' THEN -ABS([Valor Venda]) ELSE [Valor Venda] END AS net_rev
    FROM Externo01.Vendas
    WHERE ([Operação] = '{SALE_OPERATION}' OR [Operação] LIKE '{RETURN_OPERATION_PATTERN}')
      AND [Cod Cliente] IS NOT NULL
      AND [Cod Produto] IS NOT NULL
      AND (   ([Data] >= ? AND [Data] < ?)
           OR ([Data] >= ? AND [Data] < ?) )
) AS base
GROUP BY base.customer_code, base.sku
HAVING SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) > 0
    OR SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) > 0
```

| Escolha | Motivo |
| :--- | :--- |
| Começa com `SELECT`, subconsulta em vez de `WITH`, sem `CONCAT`, sem `;` | `is_readonly_query` e SQL Server legado (ADR-007 DA-03) |
| Bind params `(cur_start, pre_start, pre_end, cur_start, cur_end)` | `period_flag = 1` sse `[Data] >= cur_start`; correto porque o Python valida `pre_start < pre_end <= cur_start < cur_end <= dataReferencia` antes de executar (senão `ValueError`, nunca SQL) |
| Constantes `SALE_OPERATION`/`RETURN_OPERATION_PATTERN` do módulo interpoladas; datas sempre `?` | Nada do cliente entra no texto SQL |
| Mesmas colunas da F6 (`Cod Cliente`, `Cod Produto`, `Qtd Venda`, `Valor Venda`, `Operação` só no filtro) | LGPD-CAN-01 |
| Leitura com `cursor.fetchmany(FETCH_CHUNK_SIZE)` | Nunca `fetchall` |
| Saída em **tuplas compactas** `(customer_code:int, sku:str internado, pre_qty, pre_rev, cur_qty, cur_rev)` | `_unpack_row` do motor aceita tuplas; ~55% menos memória que a lista de `dict` da F6 |

**Como alimenta o motor sem duplicar lógica (`adapters/migration_adapter.py`):**

1. `TrendWindowSpec` com cobertura de `PRE` < 100% → não lê o banco; devolve `NotEvaluated("JANELA_ANTERIOR_INCOMPLETA")` (P-153.4).
2. `affinity_map = get_affinity_lookup_map()`; se `None` → `NotEvaluated("INDICE_AFINIDADE_INDISPONIVEL")`, **sem** chamar o motor (P-153.3: o fallback por tokens nunca roda na F7).
3. Lê as linhas; `domain/migration_scaling.scale_previous(rows, k)` multiplica `pre_qty`/`pre_rev` por `k` (P-153.2) gerando novas tuplas.
4. Chama **`compute_directional_migration(rows_scaled, catalog, affinity_map=affinity_map)`** da F6, sem cópia nem adaptação do algoritmo (o mapa já vem filtrado em score ≥ 0,50).
5. Na mesma etapa volátil, `domain/migration_scaling.aggregate_lost_customers(rows_scaled, lost_customer_codes, affinity_map)` produz, por SKU, `LostCustomersAggregate(count, revenue, quantity)` (P-164). `lost_customer_codes` vem do `ChurnSource` (snapshot de churn já existente e aprovado em LGPD) como `frozenset[int]` só dentro desta função.
6. **LGPD-TIA-02:** `rows`, `rows_scaled` e `lost_customer_codes` são variáveis locais da função de construção (nunca atributo, cache, disco ou retorno) e recebem `del` explícito **antes** de gravar o `TrendMigrationSnapshot` no cache, no mesmo padrão do `del raw_rows` da F6. O motor já faz `del by_cli`. `evaluate_lost_products` (grão cliente) não é usado.
7. Publica `TrendMigrationSnapshot(migration: MigrationSnapshot, lost_by_sku: Mapping[str, LostCustomersAggregate], window_spec, affinity_index_generation, built_at)`. Zero `Cod Cliente` (P-185.1; teste C-35 serializa o objeto e procura códigos de cliente da massa).

**Cache (`service/migration_cache.py`):**

| Item | Decisão |
| :--- | :--- |
| Chave | `(comparisonMode, window, baseMonth, dataReferencia, affinityIndexGeneration)`. O 5º componente invalida sozinho o cache quando o índice muda em qualquer instância (DA-06); sem `Cod Cliente` |
| TTL | `MIGRATION_CACHE_TTL_HOURS` = `CACHE_TTL_HOURS` da F6 (6 h, reuso) |
| Voo único | Lock **por chave** (dicionário de `threading.Lock` protegido por um lock global curto): pedidos da mesma chave esperam a mesma carga; chaves diferentes não se bloqueiam na espera |
| Concorrência de carga | `threading.BoundedSemaphore(MIGRATION_BUILD_CONCURRENCY = 1)`: no máximo uma leitura `(cliente, SKU)` por instância ao mesmo tempo, para o pico não somar |
| Limite | LRU de `MIGRATION_CACHE_MAX_ENTRIES = 8` (2 modos × 4 janelas do Mês-Base em uso) |
| Falha | Exceção de infraestrutura na leitura vira `NotEvaluated("FONTE_INDISPONIVEL")` só para as parcelas de migração; nada é gravado no cache |

**Estimativa de memória (Cloud Run 2Gi).** Referências medidas: base com ~54,5 mil pedidos em ~23 meses e 1.934 SKUs (1.339 ativos); snapshot do cross-sell ~320 MB de pico na carga (KNOWLEDGE_GRAPH). Hipótese de trabalho, **a confirmar na tarefa 7.1-M**: ~20 mil pares `(cliente, SKU)` distintos por mês.

| Item | `point` X=1 (2 meses) | `average` X=12 (13 meses, pior caso) |
| :--- | :--- | :--- |
| Linhas lidas | ~35 mil | ~150–250 mil |
| Tuplas compactas (~250 B/linha) | ~9 MB | ~40–65 MB |
| Bloco do cursor (50 mil linhas) | ~10 MB | ~10 MB |
| `by_cli` do motor + acumuladores | ~6 MB | ~25–40 MB |
| Agregação de clientes perdidos | < 5 MB | ~10–15 MB |
| **Pico transitório da carga** | **~30 MB** | **~90–130 MB** |
| `TrendMigrationSnapshot` residente (pares + totais) | ~1–2 MB | ~3–5 MB |
| Cache cheio (8 entradas) | | **≤ 40 MB** |
| `EvidenceCache` (200 pacotes × ~30 KB) | | **≤ 6 MB** |

Meta: **pico incremental ≤ 200 MB e residente ≤ 50 MB** por instância, com o semáforo impedindo duas cargas simultâneas. Com a lista de `dict` da F6 o pior caso passaria de ~160 MB só nas linhas; por isso as tuplas.

**Como medir (gate da fase 7.1, antes do deploy):**
- `diagnostics/run_migration_memory_report.py` (CLI somente leitura, mesmo padrão do DA-14 do ADR-003): para cada `(modo, janela)` do Mês-Base padrão, mede `tracemalloc` (pico Python), `resource.getrusage(RUSAGE_SELF).ru_maxrss` antes/depois (pico do processo, inclui pyodbc), tempo da query e do motor, nº de linhas, clientes distintos, pares e SKUs. Imprime só contagens e tempos (nada de código de cliente).
- Em produção: log estruturado por carga com `rows`, `pairs`, `query_ms`, `engine_ms`, `rss_delta_mb` (sem payload) e o gráfico "Memory utilization" do Cloud Run na primeira semana. **Gatilho:** pico > 300 MB ou `query_ms` > 20 s → abrir tarefa para leitura em dois passes por cliente ou para restringir `HAVING` aos SKUs do grupo afim.

### DA-05 — Pacote de evidências e cache do `GET`

- `EvidenceCache` (LRU 200 entradas, TTL 6 h) por `(sku, metric, window, baseMonth, comparisonMode, dataReferencia, affinityIndexGeneration)`. As fontes por SKU (elasticidade lê pontos de preço do banco; UF é query nova) só rodam na primeira abertura do painel daquele SKU.
- Promoções por janela (`fetch_promo_skus_in_window`) são cacheadas por `(cur_start, cur_end)` e `(pre_start, pre_end)`, não por SKU.
- **Lançamento afim (P-160):** a 1ª venda de cada SKU vem da série mensal da snapshot da Tendência (primeiro mês com faturamento líquido > 0). Como as janelas são alinhadas a mês, a granularidade mensal basta; o corte `primeiraData + 90 dias` é aplicado no mês que contém essa data. Nenhuma SQL nova.
- **Região (P-167):** `fetch_sku_region_window_sales(sku, pre_start, pre_end, cur_start, cur_end)` em `analytics/repository`: `SELECT [UF], somas pre/cur e COUNT(DISTINCT [Cod Cliente])` agrupado por UF, só para o SKU pedido. Devolve só UF, somas e contagens, nunca códigos (LGPD-TIA-01). O agrupamento é feito no domínio antes de qualquer saída (LGPD-TIA-05): UF com < 3 clientes vai para `OUTRAS`; se `OUTRAS` ficar com < 3 clientes, absorve a menor UF exibida até atingir o piso; se nem assim, a quebra regional inteira fica `NAO_AVALIADO` com motivo `ANONIMIZACAO`. As contagens nunca saem do domínio.
- **Contagens pequenas (LGPD-TIA-06 e pedido do coordenador para a API):** `clientesMigrados` e `clientesPerdidosQtd` menores que 3 saem como a faixa `"<3"` na API, no GCS e no pacote do LLM; a confiança `BAIXA` carrega a mesma informação.
- **`meta.ia` no `GET` (Design Plan Q-D7):** o `GET` lê o **nível** do orçamento (`NORMAL`/`ALERTA`/`ESGOTADO`, do livro de gastos, cache de 60 s por instância; valores em dólar, tokens e consultas nunca saem da API), consulta a existência do lease de geração em voo da chave (uma leitura de metadados no GCS) e a data do diagnóstico salvo, para a tela desabilitar o botão antes do primeiro clique. Nenhuma dessas leituras chama o LLM.

### DA-06 — Índice de afinidade no GCS e sync por Cloud Scheduler (tarefa 7.0 c, achado 2)

**Armazenamento.** `product_affinity_service` passa a ler e gravar por uma porta `AffinityIndexStore` com duas implementações:

| Implementação | Quando | Comportamento |
| :--- | :--- | :--- |
| `LocalFileAffinityIndexStore` | `AFFINITY_INDEX_GCS_URI` ausente (dev, testes) | Comportamento atual (`data/cache/product_affinity_index.json`, gravação atômica) |
| `GcsAffinityIndexStore` | `AFFINITY_INDEX_GCS_URI=gs://<bucket>/affinity/product_affinity_index.json` (produção) | Leitura do objeto inteiro; gravação com `if_generation_match=<geração lida>` (concorrência otimista; `0` quando não existe). Conflito `412` → descarta o resultado local, relê o objeto e registra log `AFFINITY_SYNC_CONFLICT` |

**Leitura nas instâncias.** Primeira chamada a `get_loaded_affinity_index()` baixa o objeto (alguns MB) e guarda `(payload, generation)`. A cada `AFFINITY_INDEX_REFRESH_MINUTES = 15`, a instância consulta só os metadados do objeto (uma chamada barata); se a geração mudou, baixa de novo, troca atomicamente e chama `reset_cannibalization_report_cache()`. A geração entra na chave do cache de migração da F7 (DA-04), que se invalida sozinho.

**Sem reconstrução no cold start.** Reconstruir exige baixar a galeria do site e recalcular TF-IDF; fazer isso na partida atrasaria todas as rotas e cobraria CPU a cada escala de zero. Se o objeto não existe (primeiro deploy) ou está inválido:
- `get_affinity_lookup_map()` e `get_product_affinities()` devolvem `None`;
- **F7:** Grupo Afim, Diagnóstico de Mercado, `PRODUTO_NOVO`, `CANIBALIZACAO_*`, `CLIENTES_PERDIDOS` e `impactoEmOutrosProdutos` ficam `NAO_AVALIADO`, resposta `200` com aviso `TIA-005` em `meta.avisos` (P-173). **Nunca** usa o fallback por palavras;
- **F6:** mantém o comportamento atual dela (fallback por tokens), que não muda nesta feature;
- o `GET /insights/health` mostra `indiceAfinidade.disponivel = false`, e o runbook do `devops` manda disparar o job do Scheduler manualmente (`gcloud scheduler jobs run`).

**Sincronização.** O laço `_daily_affinity_cron` sai do `lifespan` de `src/api.py` (com escala para zero ele não roda de forma confiável e, com até 3 instâncias, rodaria em paralelo). No lugar:

| Peça | Decisão |
| :--- | :--- |
| Rota | `POST /internal/v1/affinity-index/sync` (contrato `sales-trend-insights.md` §3.5), router interno do `trend_insights` chamando `product_affinity_service.sync_product_affinity_index` |
| Autenticação | Token **OIDC do Google** no `Authorization: Bearer`, emitido pelo Cloud Scheduler com a conta de serviço `sa-affinity-scheduler`. A rota valida assinatura, `aud == AFFINITY_SYNC_AUDIENCE` (URL do serviço), `email == AFFINITY_SYNC_INVOKER_SA` e `email_verified` com `google.oauth2.id_token.verify_oauth2_token`. O middleware Basic isenta **só** esse método+caminho exatos; qualquer outro `/internal/*` continua exigindo Basic |
| Exclusão mútua | Lease GCS `locks/affinity-sync.lock` (criação com `if_generation_match=0`, validade 10 min, lease vencido é removido com `if_generation_match` da geração lida). Lease ocupado → `409` |
| Agendamento | Cloud Scheduler `0 0 * * *`, fuso `America/Sao_Paulo`, `attempt-deadline=300s` (limite do Cloud Run), 2 novas tentativas com backoff. Mantém o horário 00:00 da F6 |
| Rota manual existente | `POST /api/v1/analytics/affinity/sync` (Basic) continua, passa a gravar pelo mesmo `AffinityIndexStore` e respeita o mesmo lease |
| Pós-sync | `reset_cannibalization_report_cache()` na instância que sincronizou; as demais pegam a nova geração em até 15 min |

### DA-07 — Persistência dos diagnósticos e demais estados no GCS

Um bucket por ambiente, `fitoherb-trend-insights-<env>`, região `southamerica-east1` (a mesma do Cloud Run), classe Standard, *uniform bucket-level access*, *public access prevention* ativo, sem versionamento. A conta de serviço de runtime recebe `roles/storage.objectUser` **só neste bucket**.

| Prefixo | Conteúdo | Ciclo de vida |
| :--- | :--- | :--- |
| `insights/v1/product/{sku}/{metric}/{comparisonMode}/w{window}/{baseMonth}/{promptVersion}/{evidenceHash}.json` | Diagnóstico validado (`StoredInsight`: diagnóstico, `sugestoesBuscaHtml`, `modelo`, `origem`, `geradoEm`, `promptVersion`, `evidenceHash`, tokens, consultas, custo). **Sem** usuário, e-mail ou IP de quem gerou (LGPD-TIA-09) | Exclusão com 90 dias (`INSIGHT_RETENTION_DAYS`, Q-3), configurada **no bucket** (regra de ciclo de vida no script de deploy), não só no código |
| `insights/v1/supplier/{supplierKeyHash}/...` | Idem para fornecedor (fase 7.4); a chave opaca vira SHA-256 truncado para caber no caminho | 90 dias |
| `affinity/product_affinity_index.json` | Índice de afinidade (DA-06) | Sem exclusão |
| `ai-budget/{AAAA-MM}.json` | Livro de gastos do mês com reservas (DA-09). Só agregados em dólar; sem usuário | 400 dias |
| `locks/...` | Leases de geração (`locks/insights/{sha256(chave)}.lock`) e de sync; corpo só `{expiresAt}`, sem identificador de pessoa (LGPD-TIA-10) | 1 dia (limpeza de leases órfãos) |

- Gravação do diagnóstico: `if_generation_match=0` na primeira vez; em "Gerar de novo" (`force=true`) sobrescreve com a geração lida. Escrita só depois da validação (P-175.5: fallback nunca é salvo).
- `evidenceHash` = SHA-256 do pacote de evidências **canônico** (o mesmo que iria ao LLM: listas ordenadas, números arredondados, sem timestamp nem nonce). Faz parte da chave do objeto: o `GET` monta o pacote, calcula o hash e procura o objeto; achando, devolve o diagnóstico; não achando, `diagnosticoIa = null`. Sem listagem de histórico (P-175.4 resolvido). **TTL lógico** de `INSIGHT_SOFT_TTL_DAYS = 30`: vencido, a resposta traz `meta.vencido = true` e a tela oferece "Atualizar" (explícito; nada regenera sozinho); diagnóstico sem fator externo não vence por tempo. Teste de contrato "mesmo dado, mesmo hash" obrigatório.
- Conteúdo salvo: só agregados de produto/fornecedor, texto do LLM já validado e URLs de fonte. Zero dado de cliente (P-185.1).

### DA-08 — Deduplicação de pedidos em voo (P-176.2)

Duas camadas:
1. **Na instância:** dicionário `chave → asyncio.Future`; o segundo pedido aguarda o mesmo `Future`.
2. **Entre instâncias:** lease `locks/insights/{sha256(chave)}.lock` criado com `if_generation_match=0` e corpo `{expiresAt}`. Quem não consegue criar o lease faz polling do objeto do diagnóstico a cada 2 s até `IN_FLIGHT_LOCK_TTL_SECONDS`; se o diagnóstico aparece, devolve-o (`meta.reutilizado = true`); se o lease vence sem resultado, tenta adquiri-lo uma vez (conta no rate limit). Lease vencido é removido com `if_generation_match` da geração lida. O lease é sempre liberado em `finally`.

**Prazos (alinhado ao `ai_specialist`, `trend-insights-llm.md` §8.5 e CP-5):** toda a camada de IA de uma geração (tentativas transitórias, nova tentativa por schema e eventual modo de 2 chamadas) tem prazo total `LLM_TOTAL_DEADLINE_SECONDS = 110`; ao estourar, fallback `200` sem IA. Como 110 s < `IN_FLIGHT_LOCK_TTL_SECONDS = 120`, o lease não vence com a chamada em curso e a constante do `analyst` fica como está. Com montagem do pacote e gravação no GCS, o `POST` termina em até ~125 s, abaixo dos 300 s do Cloud Run; a tela usa timeout HTTP de **150 s**.

**Por que síncrono (sem 202 + polling de job):** o Cloud Run roda com `--cpu-throttling`, então trabalho em segundo plano depois da resposta fica sem CPU. A chamada síncrona de 10–30 s típicos cabe no timeout de 300 s; a tela já tem o estado "gerando IA".

### DA-09 — Teto de US$ 2/mês, livro de gastos, kill-switch e rate limit (revisado v2)

- **Meta e teto:** gasto total da F7 (LLM + *grounding* + infra) ≤ **US$ 2,00/mês**. `TREND_AI_MONTHLY_BUDGET_USD = 1,80` (LLM + *grounding*; ~US$ 0,10 de infra e ~US$ 0,10 de margem) e `TREND_AI_DAILY_BUDGET_USD = 0,20` (evita queimar o mês em um dia). Estimativa: ~US$ 0,014 a 0,018 por geração, **~104 gerações/mês** (~55 no pior caso com *grounding* todo cobrado); cache e template custam US$ 0 e são ilimitados (`trend-insights-llm.md` §14.10).
- **Tabela de preços em configuração** (`TREND_AI_PRICING_JSON`), nunca no código: `gemini-4-hydrogen` US$ 1,50/7,50 por 1M tokens (entrada/saída, saída inclui *thinking*); `gemini-3.8-flash` US$ 0,75/3,75 **até 31/12/2026** e US$ 1,50/7,50 **a partir de 01/01/2027** (a configuração leva a data de virada; revisar na virada); *grounding* US$ 0,014 por consulta executada acima da cota. Preços do Vertex AI **não confirmados** na documentação: usar esta tabela e conferir no Billing.
- **Custo real:** `llm/pricing.py` = tokens informados pela API (inclui *thinking*) + `consultas_executadas × preço`, com as primeiras `GROUNDING_FREE_QUERIES_ASSUMED = 1500` consultas do mês tratadas como grátis (premissa conservadora; a cota real é 5.000 e o escopo não está confirmado).
- **Livro de gastos** (`ai-budget/AAAA-MM.json` no GCS, `BudgetLedger`): `gastoMes`, `gastoDia` (com a data), `reservado` (lista de reservas com `expiresAt`) e `consultasMes`. Escrita *read-modify-write* com `if_generation_match` e até 5 novas tentativas em conflito. Mês e dia civis em UTC−3.
- **Reserva e acerto (substitui a pré-checagem e o "excesso aceito"):** antes de cada chamada ao LLM, reserva-se `custoEstimadoMaximo` (8.000 tokens de entrada + 2.500 de saída = ~US$ 0,031; +3 × 0,014 = ~US$ 0,073 se acima da cota grátis assumida). Depois da chamada, acerta-se com o `usage` real (inclusive falhas que consumiram tokens). Reservas sem acerto vencem em `RESERVATION_TTL_SECONDS = 150` e são liberadas. Pedidos simultâneos não estouram o teto porque cada um reserva antes.
- **Falha fechada:** se o livro não puder ser lido ou escrito (GCS fora), **não se chama o LLM**; responde-se com template.
- **Níveis e degradação (P-178 revisada):**

| Nível | Condição | Efeito |
| :--- | :--- | :--- |
| `NORMAL` | gasto do mês < 80% do teto e do dia < teto diário | Comportamento completo |
| `ALERTA` | ≥ 80% (US$ 1,44) | Log `tia.budget.alert`; *grounding* só com resíduo ≥ 0,50; `force=true` e "Atualizar" desabilitados |
| `ESGOTADO` | ≥ 100% (US$ 1,80), diário estourado ou saldo menor que a reserva | **Sem LLM:** resposta `200` com resumo por template (`meta.ia.origem = "template"`, `motivoTemplate = ORCAMENTO_ESGOTADO`). Volta no dia 1º (ou no dia seguinte, se foi o teto diário) |

- **Kill-switch:** `TREND_AI_ENABLED=false` (variável de ambiente, sem deploy de código) é o 1º passo do fluxo; com ele desligado o `POST` responde template (`motivoTemplate = IA_DESLIGADA`) e o `GET` sinaliza `meta.ia.motivoBloqueio = IA_DESLIGADA`. Nova revisão do Cloud Run com a variável alterada basta para aplicar.
- **Medição independente:** **Cloud Billing Budget de US$ 2,00** no projeto, alertas em 50/80/100% por e-mail (pendência do `devops`). Ele **não corta** gasto; o livro é a trava preventiva e a fatura é a verificação.
- **Rate limit (P-176 revisada; PC-04 / LGPD-TIA-11):** janela deslizante de 60 s **só em memória**, por instância (`service/generation_guard.py`), `GENERATE_RATE_LIMIT_PER_MINUTE = 2`; limites diários por usuário `GENERATE_MAX_PER_USER_PER_DAY = 10` e `FORCE_MAX_PER_USER_PER_DAY = 3`, também em memória. A chave é `HMAC-SHA256(sal, identificador)` (usuário do Basic ou 1º IP de `X-Forwarded-For`), sal por processo (`secrets.token_bytes(32)`, nunca persistido); entradas expiradas são removidas a cada acesso; usuário, IP e hash não vão para log, GCS, resposta ou nome de objeto. Só pedidos que **chamam** o LLM contam (cache e template não contam). Excedido → `429 TIA-004` com `motivo = LIMITE_DE_PEDIDOS` (minuto) ou `LIMITE_DIARIO` (dia/`force`) e `Retry-After`. **Limitação aceita:** com escala a zero e até 3 instâncias, os contadores zeram e multiplicam; como todos os usuários compartilham a credencial Basic, é praticamente um limite global por instância. A proteção financeira real é o livro (diário e mensal), não este limite.
- **Nada de custo vai ao cliente:** a API não expõe valores em dólar, tokens, consultas de busca, preços, tetos nem o livro (contrato 1.1.0, §2.1 e §3.4). A tela recebe só o `nivel` do orçamento e a `origem` da resposta.

### DA-10 — Camada de LLM: SDK `google-genai`, sem LangChain e sem LangGraph

- `llm/gemini_client.py` implementa a porta `LlmClient` (`llm/client.py`: `generate(LlmRequest) -> LlmResponse`, `is_configured() -> bool`) sobre o SDK oficial `google-genai` em **modo Vertex AI** (credencial da conta de serviço do Cloud Run por ADC; endpoint `global`, processamento `us`/`eu`), com *grounding* `google_search` como única ferramenta, saída estruturada, `thinking_level` explícito, timeout `LLM_TIMEOUT_SECONDS`. Usa a Interactions API se estiver disponível no Vertex e, senão, `generate_content` (confirmar no spike 7.2-S). Devolve texto validável, citações `url_citation`, URLs dos resultados da busca, nº de consultas executadas, `search_suggestions` (HTML do Google) e uso de tokens. Nenhuma exceção do SDK sai sem conversão; logs nunca usam `str(exc)` do SDK (LGPD-TIA-07). Detalhes: `trend-insights-llm.md` §3, §4 e §8.
- `service/llm_orchestrator.py` é o fluxo fixo em Python (DA-12): `kill-switch → cache → gates → rate limit → reserva de orçamento → Hydrogen → [falha de infraestrutura: 1 chamada Gemini 3.8 Flash] → validar (P-181/P-182) → [1 nova tentativa por schema no mesmo modelo | até LLM_TRANSIENT_RETRY_LIMIT = 2 por erro transitório com backoff] → resultado | template`, tudo dentro de `LLM_TOTAL_DEADLINE_SECONDS = 110` (limite duro, cabe com 2 tentativas + Flash). Cada etapa é uma função pura testável sobre um DTO imutável; log estruturado por etapa (etapa, latência, modelo, tokens, consultas, custo, status, tamanho do pacote, `PROMPT_VERSION`), sem prompt, pacote ou resposta (P-185.2).
- **Modo de chamada (`TREND_AI_CALL_MODE = single | two_step`, padrão `single`):** saída estruturada + Google Search na mesma chamada é suportada nos Gemini 4, mas está em **Preview**. Por isso o orquestrador também implementa o modo de 2 chamadas (pesquisa com busca e texto livre → estruturação **sem** busca, com a lista de URLs da etapa 1 como allow-list). A troca é por configuração ou **automática na mesma geração** quando a API recusa a combinação (`400`) ou devolve fator externo sem nenhuma citação. A troca automática não conta como nova tentativa por schema, mas o custo da 1ª chamada entra no orçamento.
- **Fornecedor do LLM (decisão do usuário, resolve PC-01 e CP-9):** **Vertex AI**, sem chave de API (ADC). `TREND_AI_BACKEND` e `GEMINI_API_KEY` deixam de existir; a conta de runtime recebe `roles/aiplatform.user` no projeto. **Nível gratuito da Gemini API proibido** (LGPD-TIA-08) e a Gemini API com chave não é mais backend suportado. Na documentação, o Hydrogen no Vertex tem *grounding* e saída estruturada no endpoint `global`; **não confirmados** preço no Vertex e Interactions API no Vertex (spike 7.2-S; contingência `generate_content`). Retenção: o *grounding* tem retenção própria do Google de 30 dias de prompt e saída (Termos); processamento em `us`/`eu` (nenhuma região no Brasil). O pacote não tem dado pessoal (LGPD-TIA-03..06), então não há transferência internacional de dado pessoal; o que sai é segredo comercial, coberto pelo contrato do projeto pago.
- **Temperatura (exceção registrada a `ai-llm-integration-rules.md` §3, CP-6 do `ai_specialist`):** não se envia `temperature`. Para Gemini 3 o Google recomenda manter 1.0 e, para Gemini 4, o parâmetro não tem efeito documentado; o determinismo vem do JSON Schema fechado (`enum`, `maxItems`, `additionalProperties: false`), do `thinking_level` explícito (`low` no Hydrogen e no Flash; `minimal` dá erro no Flash) e da validação estrita. Revisitar se o Google documentar `temperature` para os Gemini 4.
- **Sugestões de busca do Google (Termos do *grounding*), ponto aberto CP-10 do checkpoint:** os Termos exigem exibir as *Search Suggestions* (HTML fornecido pelo Google) junto do resultado e proíbem modificar ou intercalar conteúdo nos *Grounded Results*. Isso conflita com P-184.5 (texto puro) e com a troca de marcadores pelos números do motor (P-182.1). Desenho provisório: o HTML é guardado no GCS com o diagnóstico e exposto no campo opcional `diagnosticoIa.sugestoesBuscaHtml`, que a tela só pode renderizar num `iframe` com `sandbox` (sem scripts do nosso domínio) abaixo do diagnóstico, como única exceção ao texto puro; no modo de 2 chamadas, o texto exibido vem da chamada **sem** *grounding*, o que separa o *Grounded Result* (notas) da redação final. Precisa de avaliação do `security` e jurídica (ou `ai_governance_auditor`) antes da Etapa 3.
- **Datas das fontes:** o *grounding* não devolve data de publicação. A data vem da leitura do modelo, cruzada com data no caminho da URL (`origemData = MODELO | URL`); sem data, o fator externo vira hipótese `SEM_DATA` (P-182.4). O contrato aceita `dataPublicacao` nula nas fontes das hipóteses.
- **Segredo:** nenhum para a IA. Sem chave de API, o Secret Manager deixa de ser usado por ela (a migração de `AUTH_PASSWORD`/`DB_PASSWORD` do CP-8 permanece). O livro, os diagnósticos e o cache não guardam credencial. `config.py` expõe só `ia_ligada: bool` (`TREND_AI_ENABLED`) para o health. IA desligada ou Vertex indisponível desde o início → `POST` responde template (`IA_DESLIGADA`/`IA_INDISPONIVEL`), `GET` intacto.
- **IDs de modelo e limites** em variáveis: `TREND_AI_MODEL_DEFAULT = gemini-4-hydrogen`, `TREND_AI_MODEL_FALLBACK = gemini-3.8-flash`, `TREND_AI_THINKING_DEFAULT = low`, `TREND_AI_MAX_OUTPUT_TOKENS_DEFAULT = 2500`. Nada de modelo "aprofundado": **o Neon foi removido** e não existe caminho de código que o use (teste de aceite na 7.2).
- **IA sem números no texto (decisão do usuário):** `resumo`, `explicacao`, `recomendacoes` e a `descricao` das hipóteses saem **sem nenhum dígito, valor, percentual ou código de SKU**; o LLM cita produtos pela descrição e as grandezas ficam nos campos numéricos do motor (`parcelaEstimada`, `pontosPercentuais`, cascata), exibidos pela tela ao lado do texto. A validação (P-182.1 revisada) rejeita dígitos no texto (pedido de reescrita 1×, depois descarta o trecho) e o pacote enviado ao LLM não contém marcadores de substituição numérica. Isso elimina a troca de marcadores no texto e reduz o conflito com os Termos do *grounding* (CP-10).

**Gatilhos para revisitar a decisão (adotar LangGraph):** (1) investigação agêntica em várias rodadas em que o LLM escolhe quais dados internos consultar (ciclo ReAct com ferramentas de leitura); (2) chat de acompanhamento sobre o diagnóstico com memória por conversa; (3) segundo agente (ex.: revisor de fontes) com estado compartilhado; (4) necessidade de checkpoint/retomada de um fluxo de mais de ~3 chamadas. Nesses casos, `LlmClient` e as funções de etapa viram nós sem reescrever o domínio.

### DA-11 — Erros e envelope

- `InsightsAPIRoute` (mesmo padrão do `TrendAPIRoute`, sem handler global): `RequestValidationError` → `400 TIA-001` com nomes de campo; exceções de domínio `TIA-002/003`; `GenerationRefused(motivo)` → `TIA-004` (503 ou 429); `TrendSourceUnavailable` → `503 ANL-001`; inesperado → 500 genérico sem stacktrace.
- Os adaptadores traduzem `TrendDataSourceError` (TND-004) e `AnalyticsDataSourceError` (ANL-001) em exceções de porta; nenhuma exceção de outro módulo sobe até a rota (evita que o handler global do `analytics` responda no formato dele).
- Corpo: `{ "error": { "code", "message", "fields", "motivo"? }, "meta": { "timestamp", "version" } }`.

### DA-12 — Decisão de chamada: cache por `evidenceHash`, gates, template e fallback de modelo (revisão v2)

Ordem do `POST /generate`, da etapa mais barata à mais cara; cada etapa que responde custa US$ 0 (`trend-insights-llm.md` §14.2):

1. **Kill-switch** (`TREND_AI_ENABLED=false`) ou Vertex indisponível → template.
2. **Cache de resultado** no GCS (chave com `evidenceHash`, sem usuário, compartilhado; L1 em memória de 5 min só para evitar leituras repetidas) → devolve o salvo (`origem = "cache"`). `force=true` é o único jeito de pular o cache.
3. **Gate de explicabilidade** (P-188): `|variacaoPct| < 2%`, `SEM_BASE`, `|Δ faturamento| < R$ 1.000` (`LLM_MIN_ABS_REVENUE_DELTA`) ou resíduo < 0,20 (`LLM_MIN_RESIDUAL_SHARE`) sem `REGIONAL` e sem diagnóstico de mercado → template. (`SEM_VARIACAO` continua `422 TIA-003`.)
4. **Rate limit** (DA-09) → `429`.
5. **Reserva de orçamento** (DA-09): negada → template.
6. **Single-flight** (DA-08): seguidor aguarda o resultado do pedido em voo.
7. **Hydrogen**, com *grounding* só se o gate de *grounding* liberar (mercado em queda/alta, ou resíduo ≥ 0,30, ou `REGIONAL` com resíduo ≥ 0,15; a 80% do orçamento o limiar sobe a 0,50), `MAX_SEARCH_QUERIES = 2` (1 no `QUALITATIVO`).
8. **Falha de infraestrutura** do Hydrogen (timeout, 5xx, 429, indisponível) após 2 tentativas → **uma** chamada ao Gemini 3.8 Flash (`origem = "fallback"`); se schema + *grounding* não funcionar no Flash, roda sem *grounding* com aviso. Falha de schema repete no mesmo modelo (1×) e nunca vai ao Flash. Falhando tudo → template. A chave de cache não inclui o modelo.

- **Template (`template_summary.py`):** texto determinístico a partir de tipo, sentido e `pontosPercentuais` das parcelas e do diagnóstico de mercado; rotulado "Resumo automático (sem IA)"; `diagnosticoIa = null`; não é erro e **não é salvo** como diagnóstico. Respeita a regra de texto sem números (os valores ficam nos campos da cascata).
- **Substitui o fallback antigo** "200 + `IA_FALHOU` + `diagnosticoIa = null`" por "200 + template" (preserva a UX e o gasto zero); o aviso `IA_FALHOU` continua sinalizando que a tentativa de IA falhou.
- **Sem erro 503 de IA:** `ORCAMENTO_ESGOTADO`, `IA_INDISPONIVEL` e `IA_DESLIGADA` deixam de ser `503 TIA-004` e viram `200` com `origem = "template"` e `motivoTemplate`. `TIA-004` fica só para `429`.
- **Prompt `tia-v2`:** pacote de 8.000 caracteres, saída curta (5 fatores, 2 fontes por fator, `resumo` ≤ 400, `explicacao` ≤ 160), `max_output_tokens = 2500`; o texto muda, logo `PROMPT_VERSION = "tia-v2"` (conteúdo em `trend-insights-llm.md` §14.5).

---

## 3. Alternativas Consideradas

| Alternativa | Motivo do descarte |
| :--- | :--- |
| **Pôr o diagnóstico dentro do `sales_trend`** | Quebra o ADR-003 (o `sales_trend` passaria a importar `analytics`) |
| **Pôr o diagnóstico dentro do `analytics`** | O `analytics` já concentra 6 features; o diagnóstico é um orquestrador de várias delas mais um LLM. Módulo próprio isola custo, segredos e dependências novas |
| **Dois caminhos de leitura (função da F6 para contíguos + variante para `point`)** | Dois códigos para o mesmo resultado; a variante de 4 datas cobre os dois casos com prova de equivalência |
| **Montar `point` com X > 1 a partir de duas leituras da F6** | Dobra o custo da query e exige juntar as linhas por cliente no Python |
| **`UNION ALL` de duas faixas de data** | Funciona, mas repete o bloco inteiro e dobra os parâmetros; o `OR` de duas faixas na mesma varredura é mais curto e mantém o `GROUP BY` único |
| **Lista de `dict` como a F6** | ~2× a memória das tuplas no pior caso (13 meses) |
| **Reconstruir o índice no cold start** | Busca na galeria + TF-IDF em toda instância nova; atrasa todas as rotas e custa CPU |
| **Manter o laço 00:00 no processo** | Não roda com escala para zero; com várias instâncias roda em paralelo |
| **Cloud Scheduler com Basic Auth no cabeçalho** | A senha ficaria em texto na configuração do job e passaria a ser credencial de máquina; OIDC é o padrão do GCP e não exige segredo novo |
| **Firestore/Redis (Memorystore) para trava, orçamento e diagnósticos** | Serviço novo e custo fixo (Memorystore) para volume de poucas dezenas de gerações por mês; GCS com precondição de geração atende |
| **Disco local / `/tmp` para diagnósticos** | Efêmero no Cloud Run |
| **Geração assíncrona (202 + job + polling)** | Sem CPU após a resposta com `--cpu-throttling`; exigiria Cloud Tasks e uma segunda rota |
| **LangChain** | Ganho só na troca de fornecedor (já resolvido pela porta `LlmClient`); risco de o wrapper não expor *grounding* e citações dos modelos Gemini 4 recém-lançados; mais dependências no cold start |
| **LangGraph** | O fluxo tem um desvio e nenhum estado entre requisições; ver gatilhos em DA-10 |
| **Gemini API com chave (`TREND_AI_BACKEND=gemini_api`)** | Descartada pela decisão do usuário (Vertex AI): evita segredo novo, chave em log e retenção de interações; preço e Interactions API no Vertex ficam sob spike |
| **Gemini API no nível gratuito** | Proibido: sem *grounding* no Hydrogen e com uso dos dados para melhoria de produto (LGPD-TIA-08) |
| **Neon e "Análise aprofundada" (escalonamento)** | Removidos pela decisão do usuário: ~US$ 0,13 a 0,20 por análise inviabiliza o teto de US$ 2 |
| **Chave de cache com `dataReferencia`** | Cada carga do ERP invalidaria o salvo mesmo com evidência igual e geraria gasto à toa; `evidenceHash` reaproveita |
| **Cache de contexto do Gemini (implícito/explícito)** | Explícito não é suportado no Hydrogen e o storage custaria ~US$ 1/mês para economizar ≤ ~US$ 0,17; implícito exige ≥ 4.096 tokens (não vale engordar o prompt). Ver `trend-insights-llm.md` §14.4 |
| **Só Cloud Billing Budget como controle** | Alerta, não corta gasto; mantido como medição independente, com o livro como trava preventiva |
| **Livro de gastos em memória ou só no log** | Perdido a cada escala a zero; GCS com precondição de geração atende |
| **Buscar as páginas no backend para ler a data de publicação** | Custo, latência, nova superfície de SSRF e possível conflito com os Termos do *grounding*; a data vem do modelo + URL |
| **Contador de rate limit compartilhado no GCS** | Exigiria guardar hash de usuário/IP fora do processo (LGPD-TIA-11) para pouco ganho; o teto mensal já limita o custo |
| **Fallback por palavras quando o índice falta** | Proibido por P-153.3: mistura produtos não substitutos e contaminaria a cascata |

---

## 4. Consequências e Trade-offs

- **Pontos Positivos:**
  - Reuso real: motor de migração, preço de equilíbrio, sazonalidade, elasticidade e churn são chamados, não copiados; o domínio da F7 só contém o que é novo (janelas com `k`, grupo afim, cascata, validação).
  - Degradação por fonte: qualquer porta pode falhar sem derrubar o painel.
  - Índice de afinidade sobrevive a escala para zero e beneficia F6 e F2.
  - Custo do LLM controlado em camadas: botão explícito, cache compartilhado por `evidenceHash`, gates determinísticos (não chamada e *grounding*), template sem LLM, livro de gastos com reserva (mensal US$ 1,80, diário US$ 0,20), kill-switch e Cloud Billing Budget de US$ 2.
  - Sem `Cod Cliente` fora da etapa volátil; as SQLs com cliente continuam num só arquivo auditado.
- **Pontos Negativos / Débito Técnico Aceito:**
  - Primeira abertura de uma janela sem cache paga a query `(cliente, SKU)` (estimativa 2–10 s; medir em 7.1-M); a tela mostra skeleton.
  - Rate limit por usuário é aproximado entre instâncias (DA-09); o orçamento em dólar é exato por reserva no GCS (sem GCS, template).
  - Com o teto de US$ 2 a capacidade é de ~55 a ~104 gerações novas por mês; esgotado o orçamento, o usuário recebe resumo por template (menos rico) até a virada.
  - O Flash dobra de preço em 01/01/2027; `TREND_AI_PRICING_JSON` deve ser revisto na virada.
  - Edições em `src/core/auth.py` e `src/api.py` mexem em código compartilhado: revisão obrigatória do `security`.
  - Até 15 min de defasagem do índice entre instâncias após um sync.
  - Primeira venda por mês (não por dia) no Lançamento Afim.
  - Dependências novas (`google-genai`, `google-cloud-storage`) aumentam a imagem; importação preguiçosa limita o efeito no cold start.

---

## 5. Pontos para o Checkpoint (divergências ou lacunas nas regras, sem editar o arquivo do `analyst`)

| # | Ponto | Proposta do Arquiteto |
| :-: | :--- | :--- |
| CP-1 | P-153.1 manda usar `fetch_customer_sku_window_sales` nos modos contíguos e a variante só no `point` | Usar a variante de 4 datas em todos os modos (DA-04), com teste de equivalência. Mesmo resultado, um caminho só |
| CP-2 | `IN_FLIGHT_LOCK_TTL_SECONDS = 120` ("2× o timeout") é menor que o pior caso sem prazo total (60 s × tentativas) | Resolvido com a constante nova do `ai_specialist` `LLM_TOTAL_DEADLINE_SECONDS = 110` (DA-08): a trava de 120 s fica como está; tela com timeout HTTP de 150 s. Só falta o `analyst` registrar a constante |
| CP-3 | A rota interna de sync precisa de erros de autenticação e de concorrência | **Resolvido (revisão v2):** `TIA-006` (401, token OIDC ausente/inválido/chamador não autorizado, sem dizer qual) e `TIA-007` (409, sync já em andamento) entram no catálogo oficial (contrato 1.1.0); o `analyst` registra nas regras |
| CP-4 | P-176.3 fala "por usuário"; o Basic Auth tem uma credencial compartilhada e os contadores vivem em memória | **Resolvido:** limite 2/min, 10/dia e `force` 3/dia, aproximados por instância (DA-09); o teto financeiro real é o livro de gastos |
| CP-5 | P-175.4 deixa ao arquiteto listar o diagnóstico de dados anteriores | **Resolvido:** sem histórico. A chave inclui `evidenceHash` (DA-07, DA-12); `diagnosticoIa.desatualizado` e o aviso `DIAGNOSTICO_DESATUALIZADO` deixam de existir; entra `meta.vencido` (TTL lógico de 30 dias) |
| CP-6 | Cache de migração (P-153.5) com chave de 4 elementos | Acrescentar a geração do índice de afinidade à chave, para invalidar sozinho após o sync |
| CP-7 | Rotas de produto aceitam `comparisonMode`; a lista de erros não cita `comparisonMode=range` | `range` responde `400 TIA-001` até a Tendência expor o modo (P-151.1) |
| CP-8 | Fora do escopo da F7, achado de segurança no `deploy-cloud-run.yml`: `AUTH_PASSWORD` tem valor padrão literal no workflow e as senhas do banco vão por `--set-env-vars` | Encaminhar ao `security`/`devops`: mover `AUTH_PASSWORD` e `DB_PASSWORD` para o Secret Manager junto com `GEMINI_API_KEY` (mesma mudança de deploy) e remover o padrão literal |
| CP-9 | **Fornecedor do LLM** | **Resolvido pelo usuário:** Vertex AI (DA-10). Gemini API com chave removida. Spike 7.2-S confirma preço e Interactions no Vertex |
| CP-10 | **Termos do *grounding*** (exibir *Search Suggestions* em HTML; não modificar *Grounded Results*) × texto puro (P-184.5) e troca de números (P-182.1) | **Aberto.** Desenho provisório em DA-10 (`sugestoesBuscaHtml` em `iframe sandbox`; modo de 2 chamadas separa a redação final do resultado com busca). Exige parecer do `security` e jurídico/`ai_governance_auditor` antes da Etapa 3 |
| CP-11 | P-180 diz consultas "montadas pelo backend", mas o modelo decide as consultas; P-178.1 cobra *grounding* "por pedido", mas o Google cobra por consulta executada; P-182.4 exige data que o *grounding* não devolve | Aceitar as propostas do `ai_specialist` (CP-2, CP-3, CP-10 dele): "sugeridas pelo backend", custo por consulta executada, data lida pelo modelo com `origemData`. O contrato já aceita `dataPublicacao` nula nas hipóteses |
| CP-12 | Contagens de clientes < 3 (LGPD-TIA-06) e diferença de "Outras UFs" (LGPD-TIA-05) não estão em P-167/P-179 (privacidade PC-02, PC-03) | Contrato e domínio já aplicam `"<3"` (API, GCS e pacote) e o piso de 3 clientes em `OUTRAS`, com supressão `ANONIMIZACAO`; o `analyst` atualiza P-167 e P-179 |
| CP-13 | Campos que o `ai_specialist` pediu no fator e nas hipóteses (`explicacao`, motivo `SKU_FORA_DO_PACOTE`) e que o Design Plan pediu na API (`pontosPercentuais`, `TrendCell` do afim, `meta.ia`) | Já refletidos no contrato 1.0.0; o `analyst` atualiza P-181 |
| CP-14 | **Texto da IA sem números** (decisão do usuário) altera P-182.1 e o desenho de marcadores `{{parcela:TIPO}}`/`{{sku:COD}}` | O `analyst` revisa P-181/P-182: texto sem dígitos, validação rejeita dígitos, números só nos campos do motor (DA-10) |
| CP-15 | Preço do Vertex AI para Hydrogen e 3.8 Flash, Interactions API no Vertex, schema + *grounding* no 3.8 Flash e escopo da cota grátis de *grounding* não confirmados | Spike **7.2-S** antes de codar o cliente; `devops` confere SKU/preço no Billing e cria o Cloud Billing Budget de US$ 2 |
