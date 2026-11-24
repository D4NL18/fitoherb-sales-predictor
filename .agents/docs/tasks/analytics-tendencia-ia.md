# Entidade / Feature: Diagnóstico de Motivos da Tendência de Vendas com IA (F7)

Checklist técnico de execução da F7. Plano de produto: `.agents/docs/tasks/ia-tendencia-vendas-motivos.md` (v2 aprovado). Decisões técnicas: `.agents/docs/adr/ADR-009-diagnostico-tendencia-ia.md`. Contrato: `.agents/docs/api_contracts/sales-trend-insights.md` (1.0.0). Regras: `.agents/docs/business_rules/analytics-tendencia-ia.md` (P-150..P-187). Camada de IA: `.agents/docs/architecture/trend-insights-llm.md`. Privacidade: `.agents/docs/privacy/analytics-tendencia-ia.md` (LGPD-TIA-01..14). Design Plan: `.agents/docs/design/plans/analytics-tendencia-ia.md`.

**Convenções deste checklist**
- **TDD:** em toda tarefa, os itens `T-` (tester) vêm antes dos `D-` (developer); o `developer` só começa a etapa quando os testes dela existem e falham.
- `[PARALLEL]` = pode rodar ao mesmo tempo que as outras marcadas no mesmo bloco, sem tocar os mesmos arquivos.
- Cada item cita as regras (`P-XXX`), decisões (`DA-XX`) e condições de privacidade (`LGPD-TIA-XX`) que cobre; o ID vai no nome ou na docstring do teste.
- Testes em `tests/trend_insights/` (pasta própria). Nenhum teste chama o Gemini, o GCS ou o SQL Server reais: dublês das portas (`LlmClient`, `InsightStore`, `BudgetStore`, `InFlightLease`, fontes) e massa sintética. Testes com banco real só nos diagnósticos CLI (7.1-M).
- **DoD comum a toda tarefa:** testes da tarefa verdes; cobertura do domínio `trend_insights` ≥ 80%; `ruff`/linters limpos; nenhum número mágico (constantes nomeadas, "(reuso)" importadas); docstrings conforme contrato §6; nenhum `Cod Cliente` fora da etapa volátil; commits atômicos em Conventional Commits citando `P-XXX`.

---

## 1. Dúvidas Resolvidas (Especificação)

- **Dúvida:** IA chamada automaticamente ou só por botão?
  - **Decisão (Q-1):** só pelo `POST /generate` (botão). Sem lote, sem pré-geração.
- **Dúvida:** Modelos?
  - **Decisão (Q-2):** Hydrogen padrão; Neon no escalonamento e na "Análise aprofundada".
- **Dúvida:** Onde guardar diagnósticos, índice, orçamento e travas?
  - **Decisão (Q-3, Q-8, ADR-009 DA-06/DA-07):** um bucket GCS por ambiente, prefixos separados, ciclo de vida no bucket.
- **Dúvida:** Teto de gasto?
  - **Decisão (Q-4):** US$ 30/mês, configurável.
- **Dúvida:** Orquestração do LLM?
  - **Decisão (plano §3.10, ADR-009 DA-10):** SDK `google-genai` atrás de `LlmClient`, sem LangChain/LangGraph.
- **Dúvida:** Leitura da migração no modo `point` (janelas não contíguas)?
  - **Decisão do arquiteto (ADR-009 DA-04, CP-1):** variante de 4 datas usada em todos os modos.
- **Abertas para o checkpoint:** ADR-009 CP-3 (`TIA-006`/`TIA-007`), CP-4 (rate limit por instância), CP-9 (Gemini API × Vertex AI), CP-10 (Termos do *grounding*), CP-11..CP-13 (ajustes de texto nas regras).

---

## 2. Tarefas e Etapas de Desenvolvimento

### Tarefa 7.0a: Merge de `origin/main` na worktree — **CONCLUÍDA**

- [x] Merge `911a1ef` (F6 Canibalização e índice de afinidade disponíveis na worktree).

### Tarefa 7.0b: Documentar as regras do Índice de Afinidade — **CONCLUÍDA (`analyst`)**

- [x] P-130.3a e P-130.4..P-130.12 em `business_rules/analytics-canibalizacao.md`; glossário seção 6.

---

### Tarefa 7.0c: Índice de afinidade no GCS + sincronização por Cloud Scheduler

**Descritivo Detalhado:** tirar o índice do disco efêmero do contêiner, gravá-lo/lê-lo no GCS com concorrência otimista, remover o laço 00:00 do processo e expor a rota de máquina `POST /internal/v1/affinity-index/sync` autenticada por OIDC, chamada pelo Cloud Scheduler (ADR-009 DA-06, contrato §3.5). Beneficia F6 e F2. Pode ser entregue e implantada antes do resto da F7.

**Critérios de Aceite:**
- [ ] Sem `AFFINITY_INDEX_GCS_URI`, o comportamento local atual é mantido (arquivo em `data/cache/`).
- [ ] Com a variável, o índice é lido do GCS na 1ª chamada e relido quando a geração do objeto muda (verificação a cada 15 min, só metadados).
- [ ] Gravação com `if_generation_match`; conflito `412` não sobrescreve e é registrado.
- [ ] Objeto ausente/ inválido → `get_affinity_lookup_map()` e `get_product_affinities()` devolvem `None` sem reconstruir na partida.
- [ ] A rota interna só aceita token OIDC válido do chamador configurado; qualquer outro `/internal/*` e todo `/api/*` continuam exigindo Basic.
- [ ] Sincronizações simultâneas: só uma roda (lease GCS); a outra recebe `409`.
- [ ] O laço `_daily_affinity_cron` não existe mais no `lifespan`.

**Etapas de Execução (Checklist Técnico):**
- [ ] **T-7.0c.1** `[PARALLEL]` Testes de `src/core/object_storage.py` com dublê do cliente GCS: `read_json` (ausente → `None`), `write_json(if_generation_match)`, `try_acquire_lease`/`release_lease` (criação com geração 0, lease vencido removido com geração lida, lease válido recusado). *DA-06, DA-08*
- [ ] **T-7.0c.2** `[PARALLEL]` Testes de `AffinityIndexStore` (local × GCS) e de `product_affinity_service`: carga preguiçosa, refresh por geração com relógio injetado, conflito 412, `None` sem objeto, `reset_cannibalization_report_cache` chamado quando a geração muda. *P-130.4..P-130.12, P-173*
- [ ] **T-7.0c.3** `[PARALLEL]` Testes da rota interna e do middleware: sem token → 401; token com `aud` errado / e-mail errado / não verificado → 401 (mesma resposta); token válido → 200 com o resumo do contrato §3.5; lease ocupado → 409; `/internal/v1/outra-rota` sem Basic → 401 Basic; `/api/v1/...` sem Basic → 401. Verificador OIDC injetado como dependência (sem rede). *ADR-009 DA-06, LGPD-TIA-14*
- [ ] **D-7.0c.4** Criar `src/core/object_storage.py` (wrapper fino de `google-cloud-storage`, importação preguiçosa; erros convertidos, sem `str(exc)` em log). *DA-07*
- [ ] **D-7.0c.5** Introduzir `AffinityIndexStore` (local/GCS) em `product_affinity_service.py`, refresh por geração (`AFFINITY_INDEX_REFRESH_MINUTES = 15`), lease `locks/affinity-sync.lock` em `sync_product_affinity_index`. A rota manual `POST /api/v1/analytics/affinity/sync` passa a usar o mesmo store e lease. *DA-06*
- [ ] **D-7.0c.6** Criar `trend_insights/api/internal_router.py` e `trend_insights/config.py` (`AFFINITY_SYNC_AUDIENCE`, `AFFINITY_SYNC_INVOKER_SA`); validar com `google.oauth2.id_token.verify_oauth2_token`. Registrar o router em `src/api.py` e remover `_daily_affinity_cron`. *DA-06*
- [ ] **D-7.0c.7** Isenção mínima em `src/core/auth.py` para `POST /internal/v1/affinity-index/sync` (método + caminho exatos). Revisão obrigatória do `security`. *DA-06*
- [ ] **D-7.0c.8** `requirements.txt`: `google-cloud-storage` (versão fixada).
- [ ] **D-7.0c.9 (`devops`)** Bucket `fitoherb-trend-insights-<env>` (`southamerica-east1`, UBLA, PAP, sem versionamento, ciclo de vida por prefixo: `insights/` 90 d, `budget/` 400 d, `locks/` 1 d), conta de runtime com `roles/storage.objectUser` só no bucket, conta `sa-affinity-scheduler`, job Cloud Scheduler `0 0 * * *` `America/Sao_Paulo` com OIDC e `attempt-deadline=300s`, variáveis no deploy, carga inicial do índice (`gcloud scheduler jobs run`). *DA-06, DA-07, LGPD-TIA-09/10*

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** subir instância nova sem objeto no bucket → `GET /api/v1/sales-trend/insights/health` mostra `indiceAfinidade.disponivel = false`; nenhuma chamada à galeria na partida.
- [ ] **Cenário 2:** rodar o job do Scheduler → 200; segunda instância passa a ver o índice em até 15 min.
- [ ] **Cenário 3:** dois disparos simultâneos → um 200, um 409.
- [ ] **Cenário 4:** `curl` na rota interna com Basic válido e sem OIDC → 401.

---

### Tarefa 7.1: Motor de Evidências sem IA + `GET /insights/product/{sku}` + health (parte não-IA)

**Descritivo Detalhado:** criar o módulo `src/modules/trend_insights/` (ADR-009 DA-01) com domínio puro, portas, adaptadores sobre `sales_trend` e `analytics`, cache de migração e de evidências, e a rota `GET` (contrato §3.1). Nenhuma dependência de IA nesta tarefa.

**Critérios de Aceite:**
- [ ] `Δobs ÷ baseAjustada × 100` reproduz `variacaoPct` da Tendência (≤ 0,05 pp) para 1/3/6/12 × `point`/`average` × Mês-Base cheio/parcial. *P-151*
- [ ] Cascata com causas plantadas recuperada em 1 pp; `Σ parcelas + resíduo = Δobs`; resíduo nunca com sinal oposto; cada `B` em uma parcela. *P-157..P-169*
- [ ] Afinidade indisponível → 200 com `TIA-005` e parcelas afins `NAO_AVALIADO`; nunca o fallback por palavras. *P-153.3, P-173*
- [ ] Nenhuma rota `GET` aciona o `LlmClient`. *P-174*
- [ ] Zero `Cod Cliente` em snapshot, cache, resposta e logs. *P-185, LGPD-TIA-02*

**Etapas de Execução (Checklist Técnico):**

*Bloco A — domínio puro (os quatro grupos podem correr em paralelo, arquivos distintos)*
- [ ] **T-7.1.1** `[PARALLEL]` `test_windows.py`: datas PRE/CUR e `k` para os 2 modos × 4 janelas × Mês-Base cheio/parcial/corrente; `point` X>1 não contíguo; equivalência com `compute_cell` (C-04, C-05); cobertura de PRE < 100% → `is_previous_fully_covered = False` (C-06). *P-151, P-153.4, DA-03*
- [ ] **T-7.1.2** `[PARALLEL]` `test_cell_mode.py`: mapeamento estado da célula → `QUANTITATIVO`/`QUALITATIVO`/`SEM_VARIACAO`, limiar de 2% (C-07, C-08). *P-152*
- [ ] **T-7.1.3** `[PARALLEL]` `test_affinity_group.py`: composição (score ≥ 0,50, catálogo ativo, `sameSupplier`, fornecedor ausente), shift-share e classificação (C-10, C-11), `SEM_GRUPO_AFIM` por base baixa. *P-154..P-156*
- [ ] **T-7.1.4** `[PARALLEL]` `test_decomposition.py`: sazonal (elegibilidade, confiança, mesmos meses), preço (quantidade × receita, truncamento, observação de promoção), lançamento × canibalização (C-12, C-13), confiança por `netClients` (C-14), conversão R$→un (C-17), clientes perdidos e recência (C-18), ruptura/promoção/regional como indicadores (C-19, C-20), corte e compensatórias (C-15, C-16), teto por parcela, resíduo e `PERDA_PARTICIPACAO_SEM_MIGRACAO`, altas e `impactoEmOutrosProdutos` (C-22), modo qualitativo sem valores, `pontosPercentuais`. Inclui os números dos exemplos 3.1.8 e 3.2.1 do contrato como casos de teste. *P-157..P-171*
- [ ] **T-7.1.5** `[PARALLEL]` `test_migration_scaling.py`: `scale_previous(rows, k)` e `aggregate_lost_customers` (sem dupla contagem com quem ganhou afim). *P-153.2, P-164*
- [ ] **T-7.1.6** `[PARALLEL]` `test_privacy_aggregation.py`: anonimização por UF — UF < 3 clientes em `OUTRAS`; `OUTRAS` < 3 absorve a menor UF exibida; impossível → `NAO_AVALIADO` `ANONIMIZACAO` (C-21 + ataque por diferença); contagens < 3 viram `"<3"` em `clientesMigrados` e `clientesPerdidosQtd`. *P-167, LGPD-TIA-05, LGPD-TIA-06*
- [ ] **T-7.1.7** `test_import_boundaries.py`: `trend_insights/domain` e `llm/` (exceto `gemini_client.py`) não importam `fastapi`, `pyodbc`, `google.*`, `src.core.*` nem `service`/`repository`/`api` de outros módulos; `sales_trend` não importa `trend_insights` nem `analytics`. *DA-01, ADR-003*
- [ ] **D-7.1.8** `domain/constants.py`, `exceptions.py`, `evidence.py`, `ports.py` (com `NotEvaluated(reason)`). *P-150..P-187 §2*
- [ ] **D-7.1.9** `[PARALLEL]` `domain/windows.py`, `cell_mode.py`. *P-151, P-152*
- [ ] **D-7.1.10** `[PARALLEL]` `domain/affinity_group.py`. *P-154..P-156*
- [ ] **D-7.1.11** `[PARALLEL]` `domain/decomposition.py`, `migration_scaling.py`. *P-157..P-171*

*Bloco B — repositório e adaptadores*
- [ ] **T-7.1.12** `[PARALLEL]` Testes de repositório (`analytics/repository`) com cursor falso: `fetch_customer_sku_split_window_sales` — texto SQL começa com `SELECT`, sem `WITH`/`CONCAT`/`;`, passa `is_readonly_query`, colunas exatamente as de LGPD-CAN-01, 5 bind params na ordem `(cur_start, pre_start, pre_end, cur_start, cur_end)`, `fetchmany` (nunca `fetchall`), saída em tuplas com SKU `str`; pré-condição de datas inválida → `ValueError` sem executar; **equivalência** com `fetch_customer_sku_window_sales` quando `pre_end == cur_start`. `fetch_sku_region_window_sales` devolve só UF, somas e `COUNT(DISTINCT)`, nunca código de cliente. *P-153.1, P-167, LGPD-TIA-01*
- [ ] **T-7.1.13** `[PARALLEL]` Testes do `migration_adapter` e `migration_cache`: cobertura < 100% → `NotEvaluated(JANELA_ANTERIOR_INCOMPLETA)` sem ler o banco; `affinity_map=None` → `NotEvaluated(INDICE_AFINIDADE_INDISPONIVEL)` e o motor **não** é chamado (espião); motor da F6 chamado com linhas escaladas por `k`; chave com geração do índice; voo único por chave; semáforo de carga = 1; LRU de 8; TTL 6 h; falha de SQL não grava cache. **LGPD-TIA-02:** serialização recursiva do `TrendMigrationSnapshot` e de todo objeto do cache não contém `customer_code` nem os códigos sintéticos únicos (ex.: `987654321`); espião confirma que a lista de linhas não sobrevive à função. *P-153, DA-04, LGPD-TIA-02*
- [ ] **T-7.1.14** `[PARALLEL]` Testes dos demais adaptadores com dublês: tradução de `TrendDataSourceError`/`AnalyticsDataSourceError` em exceções de porta; cada fonte com falha → `NotEvaluated(FONTE_INDISPONIVEL)`; 1ª venda por SKU a partir da série mensal; churn devolve `frozenset` usado só dentro da construção. *P-160, P-164, P-173*
- [ ] **D-7.1.15** `analytics/repository/sales_repository.py`: `fetch_customer_sku_split_window_sales` e `fetch_sku_region_window_sales` (aditivas; a função da F6 fica intacta). `analytics/service/analytics_service.py`: `get_cannibalization_catalog()` pública. *DA-04, DA-05*
- [ ] **D-7.1.16** `adapters/*` e `service/migration_cache.py`, `service/evidence_cache.py` (LRU 200, TTL 6 h, cache de promoções por janela). *DA-04, DA-05*

*Bloco C — serviço e API*
- [ ] **T-7.1.17** Testes de contrato da rota `GET /api/v1/sales-trend/insights/product/{sku}` com `TestClient` e serviço com dublês: envelope e `meta` (inclui `modoComparacao`, `indiceAfinidade`, `avisos`, `meta.ia`), exemplos 3.1.7/3.1.8/3.1.9 do contrato, `400 TIA-001` (C-01, `comparisonMode=range`), `404 TIA-002` (C-02), `422 TIA-003` (C-03), `503 ANL-001` (C-36), corpo de erro sem eco de parâmetro (LGPD-TIA-13), sem credencial Basic → 401 (LGPD-TIA-14), dublê do `LlmClient` com contador = 0 em todas as rotas `GET` (C-24). *P-150, P-173, P-174, P-186*
- [ ] **T-7.1.18** Teste de `GET /insights/health` (parte não-IA): índice, cache de migração sem SKUs/clientes. *P-187*
- [ ] **D-7.1.19** `service/insights_service.py` (`get_product_insight`, `get_health`), `api/route.py` (`InsightsAPIRoute`), `query_params.py`, `schemas.py`, `mappers.py`, `router.py`; registrar em `src/api.py`. *DA-02, DA-11*

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** SKU real em queda, `point` X=3 → célula idêntica à da Tendência; cascata soma ao observado.
- [ ] **Cenário 2:** mesmo SKU em `average` X=12 → migração calculada com a mesma leitura; tempo e memória dentro do gate 7.1-M.
- [ ] **Cenário 3:** apagar o índice do bucket em homologação → painel com aviso `TIA-005`, sazonal/preço presentes.

---

### Tarefa 7.1-M: Gate de memória e tempo no banco real (antes do deploy da 7.1)

**Descritivo Detalhado:** medir a carga da migração por `(modo, janela)` no SQL Server real (ADR-009 DA-04, tabela de estimativa).

- [ ] **D-7.1-M.1** `trend_insights/diagnostics/run_migration_memory_report.py` (somente leitura): por `(point|average) × (1,3,6,12)` do Mês-Base padrão, imprime linhas, clientes distintos, pares, SKUs, `query_ms`, `engine_ms`, pico `tracemalloc` e `ru_maxrss` antes/depois. Saída só com contagens.
- [ ] **D-7.1-M.2** Rodar contra a base real e registrar os números no ADR-009 (seção de estimativa) e no `STATE_Arquitetura_TendenciaIA.md`.
- **DoD:** pico incremental ≤ 200 MB e residente ≤ 50 MB; `query_ms` ≤ 20 s no pior caso. Acima disso, abrir tarefa de leitura em dois passes antes do deploy.

---

### Tarefa 7.2: Camada de IA + `POST /generate` + persistência, orçamento e dedup

**Descritivo Detalhado:** cliente Gemini atrás de `LlmClient`, prompts `tia-v1`, pacote de evidências por lista branca, consultas sugeridas, validação antialucinação, orquestrador com retry/fallback/2 chamadas, `InsightStore`, `BudgetStore`, lease de geração, rate limit e rota `POST` (ADR-009 DA-07..DA-10, contrato §3.2, `trend-insights-llm.md`). Depende da 7.1 e da 7.0c (bucket). **Antes de começar:** spike de 1 h com o SDK `google-genai` instalado (Interactions API, `store=false`, *grounding* + schema, formato das citações) e decisão do checkpoint sobre CP-9 e CP-10.

**Critérios de Aceite:**
- [ ] Reuso, força, dedup e rate limit como no contrato §3.2 (C-25, C-26, C-27).
- [ ] Escalonamento e orçamento (C-28, C-29); acumulado sobrevive a reinício.
- [ ] Antialucinação e injection (C-30..C-34).
- [ ] Fallback nunca é salvo; prazo total de 110 s respeitado.
- [ ] Zero dado de cliente no pacote, no GCS e nos logs (C-35).

**Etapas de Execução (Checklist Técnico):**
- [ ] **T-7.2.1** `[PARALLEL]` `test_evidence_payload.py`: lista branca de campos; base sintética com códigos de cliente únicos → JSON enviado ao dublê não contém esses valores nem as chaves `customer`, `cliente`, `codCliente`, `nome`, `cpf`, `cnpj`, `email` (LGPD-TIA-03); sem `Pc.Ultimo Custo`/custo unitário (LGPD-TIA-04); par com `netClients = 1` vai como `"<3"` (LGPD-TIA-06); UF agregada por LGPD-TIA-05; descrição da galeria sanitizada e truncada (P-184.2). *P-179, P-184*
- [ ] **T-7.2.2** `[PARALLEL]` `test_search_queries.py`: só função primária, categoria da galeria, fornecedor, UF agregada e período; nunca texto do usuário nem dado de cliente; limites 3/5. *P-180, LGPD-TIA-12*
- [ ] **T-7.2.3** `[PARALLEL]` `test_validation.py`: números só por marcador (C-31), SKU fora do pacote (C-32), fator interno sem evidência descartado, fonte externa sem citação/sem data/fora do período → hipótese (C-33), `origemData`, teto `MEDIA` em externos, modo qualitativo sem marcador de parcela, `explicacao` ≤ 300, URLs só `http(s)`. *P-181, P-182*
- [ ] **T-7.2.4** `[PARALLEL]` `test_pricing_budget.py`: custo = tokens + consultas executadas × preço; pré-checagem por tentativa com pior caso (~0,13 / ~0,30); 80% gera log de alerta; mês civil UTC−3; CAS com conflito e nova tentativa no `BudgetStore` dublê. *P-178*
- [ ] **T-7.2.5** `[PARALLEL]` `test_model_selection.py`: `deep`, escalonamento automático (C-28), escalonamento negado por orçamento, sem escalonar por falha de schema. *P-177*
- [ ] **T-7.2.6** `test_llm_orchestrator.py` com dublê do `LlmClient`: transitório com backoff até 3; schema inválido → 1 nova tentativa com códigos de violação → fallback (C-30); combinação tools+schema recusada ou sem citações → modo 2 chamadas na mesma geração; prazo total 110 s com relógio falso; injection na galeria/página (C-34) não muda schema, tipos nem números; log com `caplog` só com os campos de P-185.2, e erro do dublê cuja mensagem contém o pacote não aparece no log (LGPD-TIA-07). *P-183, P-184, P-185.2*
- [ ] **T-7.2.7** `test_generation_guard.py`: dedup local (`Future`) e entre instâncias (lease dublê, polling, lease vencido); rate limit 5/min só para pedidos que chamam o LLM, reusos não contam; **LGPD-TIA-11:** estado do limitador só em memória com chave HMAC (sem usuário/IP em claro), nenhum log com usuário/IP no 429; objeto de lease contém só `expiresAt` (LGPD-TIA-10). *P-176, LGPD-TIA-10/11*
- [ ] **T-7.2.8** `test_insight_store.py`: caminho do objeto pela chave completa; gravação só após validação; `force` sobrescreve; `evidenceHash` e `desatualizado`; varredura do JSON gravado sem dado de cliente nem usuário/IP (LGPD-TIA-09). *P-175, DA-07*
- [ ] **T-7.2.9** Testes de contrato do `POST /generate` e do `meta.ia` no `GET`: exemplo 3.2.1; `reutilizado`; `422 TIA-003` em `SEM_VARIACAO`; `429`/`503 TIA-004` com `motivo` e `Retry-After`; fallback 200 com aviso `IA_FALHOU`; credencial ausente; `health` com `credencialConfigurada` booleano e nunca o valor da chave (LGPD-TIA-08). *P-174..P-187*
- [ ] **D-7.2.10** `llm/client.py`, `llm/gemini_client.py` (Interactions API, `store=false`, `TREND_AI_BACKEND = gemini_api | vertex`, `thinking_level`, sem `temperature`), `llm/prompts/tia_v1/`, `output_schema.py`, `evidence_payload.py`, `search_queries.py`, `validation.py`, `pricing.py` (conteúdo: `trend-insights-llm.md`). *DA-10*
- [ ] **D-7.2.11** `domain/model_selection.py`, `domain/budget.py`, `service/llm_orchestrator.py`, `service/generation_guard.py`, `store/insight_store.py`, `store/budget_store.py`. *DA-07..DA-10*
- [ ] **D-7.2.12** `insights_service.generate_product_insight` e rota `POST`; `meta.ia` no `GET`. `requirements.txt`: `google-genai` (versão fixada). *DA-02*
- [ ] **D-7.2.13 (`devops`)** Segredo `gemini-api-key` no Secret Manager (`--set-secrets` com versão fixada, `secretAccessor` só nele), variáveis `TREND_AI_*`, `TREND_INSIGHTS_BUCKET`; projeto com faturamento (nível gratuito proibido, LGPD-TIA-08). Aproveitar para mover `AUTH_PASSWORD`/`DB_PASSWORD` ao Secret Manager (ADR-009 CP-8).

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** gerar análise real em homologação → fontes clicáveis, números iguais aos da cascata, custo registrado no `budget/`.
- [ ] **Cenário 2:** clicar duas vezes / duas abas → uma chamada.
- [ ] **Cenário 3:** reduzir o teto para US$ 0,01 → `503 TIA-004 ORCAMENTO_ESGOTADO`, `GET` intacto.
- [ ] **Cenário 4:** remover a chave → `503 TIA-004 IA_INDISPONIVEL`.

---

### Tarefa 7.3: Frontend — painel "Por que?"

**Descritivo Detalhado:** painel lateral/tela cheia na página `/tendencia-vendas`, conforme `design/plans/analytics-tendencia-ia.md` e contrato §5. Pode começar com a 7.1 pronta (cascata) usando dublê HTTP para a parte de IA.

**Etapas de Execução (Checklist Técnico):**
- [ ] **T-7.3.1** `[PARALLEL]` Testes de `trend-insights.service.ts` e do store do painel (tipos do contrato sem `any`; estados carregando/gerando/erro; decisão por `error.code`/`motivo`; timeout de 150 s; polling quando `meta.ia.geracaoEmAndamento`). *P-174..P-176*
- [ ] **T-7.3.2** `[PARALLEL]` Testes de componentes: cascata com `pontosPercentuais`, célula do afim com o componente `TrendCell` existente, "Gerar de novo"/"Análise aprofundada" com confirmação antes de `force=true`, botões desabilitados por `meta.ia`, fontes com `rel="noopener noreferrer"` e domínio, texto do LLM como texto puro, `"<3"` exibido como "menos de 3 clientes". *P-175, P-184.5*
- [ ] **D-7.3.3** Serviço, store, componentes e utilitários da feature (Design Plan).
- [ ] **D-7.3.4 (F6, tarefa pequena)** Página de Canibalização aceita `?abrir={sku}` e abre o drawer de equilíbrio de preço (Design Plan Q-D2). O link do painel usa `periodo=90` com a nota de diferença de períodos (Q-D8).
- [ ] **D-7.3.5** Refatorações aprovadas no Design Plan: focus trap para `shared/a11y/dialog-focus.ts` (Q-D4) e `MECHANISM_VISUAL_META` para `analytics/utils/cannibalization-mechanism.ts` (Q-D5), sem mudança de comportamento e com os testes da F6 verdes.
- [ ] **D-7.3.6 (condicional ao checkpoint CP-10)** Renderizar `sugestoesBuscaHtml` só em `<iframe sandbox>`.

**Audit:** fidelidade ao Design Plan (`ux_reviewer`), 8 estados, acessibilidade do painel e do foco.

---

### Tarefa 7.4: Visão por fornecedor

**Descritivo Detalhado:** `GET /insights/supplier/{supplierKey}` e o `POST` equivalente (contrato §3.3), soma das cascatas e canibalização interna do portfólio. Depende da 7.1 (e da 7.2 para o `POST`). Detalhamento final do contrato (1.1.0) feito pelo `architect` no início da fase.

- [ ] **T-7.4.1** `test_supplier_rollup.py`: soma parcela a parcela, pares do mesmo fornecedor se anulam no total e aparecem em `canibalizacaoInternaPortfolio`, diagnóstico de mercado contra afins de outros fornecedores. *P-172*
- [ ] **T-7.4.2** Testes de contrato das rotas de fornecedor (`404 TIA-002` com chave inexistente). *P-150, P-172*
- [ ] **D-7.4.3** `domain/supplier_rollup.py`, serviço, rotas, chave do GCS com hash da `supplierKey`.

---

### Tarefa 7.5: Avaliação com casos reais

**Descritivo Detalhado:** 30–50 casos rotulados pelo time comercial (`trend-insights-llm.md` §12). Depende da 7.2. Opcional: `ai_governance_auditor`.

- [ ] **D-7.5.1** `tests/eval/trend_insights/cases.jsonl` com pacotes congelados (o teste de privacidade LGPD-TIA-03 roda também nesse arquivo).
- [ ] **D-7.5.2** Medir concordância do fator principal, taxa de fontes válidas, fontes com `origemData = MODELO` e precisão de mercado × concorrência; recalibrar limiares (`MIN_EXPLAINABLE_VARIATION_PCT`, `DOMINANT_EFFECT_RATIO`) se necessário.
- [ ] **D-7.5.3** Registrar custo real por diagnóstico e ajustar `TREND_AI_PRICING_JSON`.

---

## 3. Matriz de rastreio das condições de privacidade (Etapa 4)

| Condição | Teste / verificação |
| :--- | :--- |
| LGPD-TIA-01 | T-7.1.12 |
| LGPD-TIA-02 | T-7.1.13 |
| LGPD-TIA-03, 04 | T-7.2.1, D-7.5.1 |
| LGPD-TIA-05, 06 | T-7.1.6, T-7.2.1 |
| LGPD-TIA-07 | T-7.2.6 |
| LGPD-TIA-08 | T-7.2.9, D-7.2.13 (`devops`) |
| LGPD-TIA-09, 10 | T-7.2.7, T-7.2.8, D-7.0c.9 (`devops`) |
| LGPD-TIA-11 | T-7.2.7 |
| LGPD-TIA-12 | T-7.2.2 |
| LGPD-TIA-13 | T-7.1.17 |
| LGPD-TIA-14 | T-7.0c.3, T-7.1.17 |

## 4. Ordem e paralelismo

```
7.0c ───────────────┐ (pode ir a produção sozinha)
7.1 (A ∥, B ∥) → 7.1-M ─┬─► 7.2 ─► 7.5
                        ├─► 7.3 (cascata; IA após 7.2)
                        └─► 7.4
```
