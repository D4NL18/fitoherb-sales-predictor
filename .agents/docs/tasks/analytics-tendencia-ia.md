# Entidade / Feature: Diagnóstico de Motivos da Tendência de Vendas com IA (F7)

Checklist técnico de execução da F7. Plano de produto: `.agents/docs/tasks/ia-tendencia-vendas-motivos.md` (v2 aprovado). Decisões técnicas: `.agents/docs/adr/ADR-009-diagnostico-tendencia-ia.md`. Contrato: `.agents/docs/api_contracts/sales-trend-insights.md` (**1.2.0**; radar externo, ADR-009 DA-13). Regras: `.agents/docs/business_rules/analytics-tendencia-ia.md` (P-150..P-188). Camada de IA (custo e teto: §14): `.agents/docs/architecture/trend-insights-llm.md`. Privacidade: `.agents/docs/privacy/analytics-tendencia-ia.md` (LGPD-TIA-01..14). Design Plan: `.agents/docs/design/plans/analytics-tendencia-ia.md`.

**Status Etapa 3 (tester, 2026-11-24):** suite RED escrita em `tests/trend_insights/` (262 testes; ver `STATE_Testes_TendenciaIA.md`). Cobertos: T-7.1.1..7.1.7, 7.1.12, 7.1.13 (parcial), 7.1.17/18 (parcial), 7.2B.1..8, 7.2.1..7.2.4, 7.2.6..7.2.9. Pendentes: T-7.0c.*, T-7.1.14, 7.4.

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
  - **Decisão (Q-2, revisada 2026-11-24):** `gemini-4-hydrogen` **sempre**; `gemini-3.8-flash` só como fallback de falha de infraestrutura; **Neon removido** (sem escalonamento e sem "Análise aprofundada"). Backend **Vertex AI** (ADC, sem chave).
- **Dúvida:** Onde guardar diagnósticos, índice, orçamento e travas?
  - **Decisão (Q-3, Q-8, ADR-009 DA-06/DA-07):** um bucket GCS por ambiente, prefixos separados, ciclo de vida no bucket.
- **Dúvida:** Teto de gasto?
  - **Decisão (Q-4, revisada 2026-11-24):** **US$ 2,00/mês no total** (LLM + *grounding* + infra): `TREND_AI_MONTHLY_BUDGET_USD = 1,80`, `TREND_AI_DAILY_BUDGET_USD = 0,20`, livro de gastos no GCS com reserva, kill-switch `TREND_AI_ENABLED`, Cloud Billing Budget de US$ 2. IA só pelo botão; texto da IA **sem números**; esgotado o orçamento, **resumo por template** (200, sem LLM).
- **Dúvida:** Orquestração do LLM?
  - **Decisão (plano §3.10, ADR-009 DA-10):** SDK `google-genai` atrás de `LlmClient`, sem LangChain/LangGraph.
- **Dúvida:** Leitura da migração no modo `point` (janelas não contíguas)?
  - **Decisão do arquiteto (ADR-009 DA-04, CP-1):** variante de 4 datas usada em todos os modos.
- **Resolvidas na revisão v2:** CP-3 (`TIA-006` 401 e `TIA-007` 409 oficiais), CP-4 (limites 2/min, 10/dia, `force` 3/dia, por instância), CP-5 (chave com `evidenceHash`, sem histórico), CP-9 (Vertex AI).
- **Abertas para o checkpoint:** ADR-009 CP-10 (Termos do *grounding*; reduzido pelo texto sem números), CP-11..CP-14 (ajustes de texto nas regras, a cargo do `analyst`), CP-15 (preço e Interactions no Vertex: spike 7.2-S).

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
- [x] Sem `AFFINITY_INDEX_GCS_URI`, o comportamento local atual é mantido (arquivo em `data/cache/`).
- [x] Com a variável, o índice é lido do GCS na 1ª chamada e relido quando a geração do objeto muda (verificação a cada 15 min, só metadados).
- [x] Gravação com `if_generation_match`; conflito `412` não sobrescreve e é registrado.
- [x] Objeto ausente/ inválido → `get_affinity_lookup_map()` e `get_product_affinities()` devolvem `None` sem reconstruir na partida.
- [x] A rota interna só aceita token OIDC válido do chamador configurado; qualquer outro `/internal/*` e todo `/api/*` continuam exigindo Basic.
- [x] Sincronizações simultâneas: só uma roda (lease GCS); a outra recebe `409`.
- [x] O laço `_daily_affinity_cron` não existe mais no `lifespan`.

**Etapas de Execução (Checklist Técnico):**
- [x] **T-7.0c.1** `[PARALLEL]` Testes de `src/core/object_storage.py` com dublê do cliente GCS: `read_json` (ausente → `None`), `write_json(if_generation_match)`, `try_acquire_lease`/`release_lease` (criação com geração 0, lease vencido removido com geração lida, lease válido recusado). *DA-06, DA-08* *(feito: `tests/trend_insights/test_affinity_gcs_store.py`, dublê do cliente GCS)*
- [x] **T-7.0c.2** `[PARALLEL]` Testes de `AffinityIndexStore` (local × GCS) e de `product_affinity_service`: carga preguiçosa, refresh por geração com relógio injetado, conflito 412, `None` sem objeto, `reset_cannibalization_report_cache` chamado quando a geração muda. *P-130.4..P-130.12, P-173* *(feito no mesmo arquivo)*
- [x] **T-7.0c.3** `[PARALLEL]` Testes da rota interna e do middleware: sem token → 401; token com `aud` errado / e-mail errado / não verificado → 401 (mesma resposta); token válido → 200 com o resumo do contrato §3.5; lease ocupado → 409; `/internal/v1/outra-rota` sem Basic → 401 Basic; `/api/v1/...` sem Basic → 401. Verificador OIDC injetado como dependência (sem rede). *ADR-009 DA-06, LGPD-TIA-14* *(feito: `test_internal_affinity_sync.py`)*
- [x] **D-7.0c.4** Criar `src/core/object_storage.py` (wrapper fino de `google-cloud-storage`, importação preguiçosa; erros convertidos, sem `str(exc)` em log). *DA-07* *(implementado em `src/core/object_storage.py`, compartilhado com `analytics`)*
- [x] **D-7.0c.5** Introduzir `AffinityIndexStore` (local/GCS) em `product_affinity_service.py`, refresh por geração (`AFFINITY_INDEX_REFRESH_MINUTES = 15`), lease `locks/affinity-sync.lock` em `sync_product_affinity_index`. A rota manual `POST /api/v1/analytics/affinity/sync` passa a usar o mesmo store e lease. *DA-06*
- [x] **D-7.0c.6** Criar `trend_insights/api/internal_router.py` e `trend_insights/config.py` (`AFFINITY_SYNC_AUDIENCE`, `AFFINITY_SYNC_INVOKER_SA`); validar com `google.oauth2.id_token.verify_oauth2_token`. Registrar o router em `src/api.py` e remover `_daily_affinity_cron`. *DA-06* *(rota em `trend_insights/api/internal_router.py`, verificador em `trend_insights/auth/oidc_verifier.py`, `SchedulerAuthSettings` em `config.py`)*
- [x] **D-7.0c.7** Isenção mínima em `src/core/auth.py` para `POST /internal/v1/affinity-index/sync` (método + caminho exatos). Revisão obrigatória do `security`. *DA-06* *(revisão do `security` ainda pendente)*
- [x] **D-7.0c.8** `requirements.txt`: `google-cloud-storage` (versão fixada).
- [ ] **D-7.0c.9 (`devops`, PENDENTE, bloqueia release; auditoria LGPD A-1)** Verificável no script de deploy: lifecycle GCS de 90 dias em `insights/` (a constante `INSIGHT_RETENTION_DAYS` não tem consumidor no código), Public Access Prevention ativo, Uniform access e IAM mínimo (papel só no bucket). Bucket `fitoherb-trend-insights-<env>` (`southamerica-east1`, mesma região do Cloud Run, UBLA, PAP, sem versionamento, ciclo de vida por prefixo: `insights/` 90 d, `ai-budget/` 400 d, `locks/` 1 d), conta de runtime com `roles/storage.objectUser` só no bucket, conta `sa-affinity-scheduler`, job Cloud Scheduler `0 0 * * *` `America/Sao_Paulo` com OIDC e `attempt-deadline=300s` (**contar os jobs da conta**: grátis até 3, US$ 0,10/mês acima), variáveis no deploy, carga inicial do índice (`gcloud scheduler jobs run`). `TIA-006`/`TIA-007` são códigos oficiais. *DA-06, DA-07, LGPD-TIA-09/10* *(scripts e runbook entregues em `infra/trend-insights/` e `.agents/docs/devops/trend-insights-infra.md`; EXECUCAO no GCP e `06-verify.sh` pendentes do usuario)*

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
- [x] **T-7.1.1** (testes escritos, red) `[PARALLEL]` `test_windows.py`: datas PRE/CUR e `k` para os 2 modos × 4 janelas × Mês-Base cheio/parcial/corrente; `point` X>1 não contíguo; equivalência com `compute_cell` (C-04, C-05); cobertura de PRE < 100% → `is_previous_fully_covered = False` (C-06). *P-151, P-153.4, DA-03*
- [x] **T-7.1.2** (testes escritos, red) `[PARALLEL]` `test_cell_mode.py`: mapeamento estado da célula → `QUANTITATIVO`/`QUALITATIVO`/`SEM_VARIACAO`, limiar de 2% (C-07, C-08). *P-152*
- [x] **T-7.1.3** (testes escritos, red) `[PARALLEL]` `test_affinity_group.py`: composição (score ≥ 0,50, catálogo ativo, `sameSupplier`, fornecedor ausente), shift-share e classificação (C-10, C-11), `SEM_GRUPO_AFIM` por base baixa. *P-154..P-156*
- [x] **T-7.1.4** (testes escritos, red) `[PARALLEL]` `test_decomposition.py`: sazonal (elegibilidade, confiança, mesmos meses), preço (quantidade × receita, truncamento, observação de promoção), lançamento × canibalização (C-12, C-13), confiança por `netClients` (C-14), conversão R$→un (C-17), clientes perdidos e recência (C-18), ruptura/promoção/regional como indicadores (C-19, C-20), corte e compensatórias (C-15, C-16), teto por parcela, resíduo e `PERDA_PARTICIPACAO_SEM_MIGRACAO`, altas e `impactoEmOutrosProdutos` (C-22), modo qualitativo sem valores, `pontosPercentuais`. Inclui os números dos exemplos 3.1.8 e 3.2.1 do contrato como casos de teste. *P-157..P-171*
- [x] **T-7.1.5** (testes escritos, red) `[PARALLEL]` `test_migration_scaling.py`: `scale_previous(rows, k)` e `aggregate_lost_customers` (sem dupla contagem com quem ganhou afim). *P-153.2, P-164*
- [x] **T-7.1.6** (testes escritos, red) `[PARALLEL]` `test_privacy_aggregation.py`: anonimização por UF — UF < 3 clientes em `OUTRAS`; `OUTRAS` < 3 absorve a menor UF exibida; impossível → `NAO_AVALIADO` `ANONIMIZACAO` (C-21 + ataque por diferença); contagens < 3 viram `"<3"` em `clientesMigrados` e `clientesPerdidosQtd`. *P-167, LGPD-TIA-05, LGPD-TIA-06*
- [x] **T-7.1.7** (testes escritos, red) `test_import_boundaries.py`: `trend_insights/domain` e `llm/` (exceto `gemini_client.py`) não importam `fastapi`, `pyodbc`, `google.*`, `src.core.*` nem `service`/`repository`/`api` de outros módulos; `sales_trend` não importa `trend_insights` nem `analytics`. *DA-01, ADR-003*
- [x] **D-7.1.8** `domain/constants.py`, `exceptions.py`, `evidence.py`, `ports.py` (com `NotEvaluated(reason)`). *P-150..P-187 §2*
- [x] **D-7.1.9** `[PARALLEL]` `domain/windows.py`, `cell_mode.py`. *P-151, P-152*
- [x] **D-7.1.10** `[PARALLEL]` `domain/affinity_group.py`. *P-154..P-156*
- [x] **D-7.1.11** `[PARALLEL]` `domain/decomposition.py`, `migration_scaling.py`. *P-157..P-171*

*Bloco B — repositório e adaptadores*
- [x] **T-7.1.12** (testes escritos, red) `[PARALLEL]` Testes de repositório (`analytics/repository`) com cursor falso: `fetch_customer_sku_split_window_sales` — texto SQL começa com `SELECT`, sem `WITH`/`CONCAT`/`;`, passa `is_readonly_query`, colunas exatamente as de LGPD-CAN-01, 5 bind params na ordem `(cur_start, pre_start, pre_end, cur_start, cur_end)`, `fetchmany` (nunca `fetchall`), saída em tuplas com SKU `str`; pré-condição de datas inválida → `ValueError` sem executar; **equivalência** com `fetch_customer_sku_window_sales` quando `pre_end == cur_start`. **4 datas sempre:** espião no `migration_adapter` prova que a F7 nunca chama `fetch_customer_sku_window_sales`, inclusive em `average` e nas janelas contíguas (ADR-009 DA-04, revisão v2). `fetch_sku_region_window_sales` devolve só UF, somas e `COUNT(DISTINCT)`, nunca código de cliente. *P-153.1, P-167, LGPD-TIA-01*
- [ ] **T-7.1.13** `[PARALLEL]` Testes do `migration_adapter` e `migration_cache`: cobertura < 100% → `NotEvaluated(JANELA_ANTERIOR_INCOMPLETA)` sem ler o banco; `affinity_map=None` → `NotEvaluated(INDICE_AFINIDADE_INDISPONIVEL)` e o motor **não** é chamado (espião); motor da F6 chamado com linhas escaladas por `k`; chave com geração do índice; voo único por chave; semáforo de carga = 1; LRU de 8; TTL 6 h; falha de SQL não grava cache. **LGPD-TIA-02:** serialização recursiva do `TrendMigrationSnapshot` e de todo objeto do cache não contém `customer_code` nem os códigos sintéticos únicos (ex.: `987654321`); espião confirma que a lista de linhas não sobrevive à função. *P-153, DA-04, LGPD-TIA-02*
- [x] **T-7.1.14** `[PARALLEL]` Testes dos demais adaptadores com dublês: tradução de `TrendDataSourceError`/`AnalyticsDataSourceError` em exceções de porta; cada fonte com falha → `NotEvaluated(FONTE_INDISPONIVEL)`; 1ª venda por SKU a partir da série mensal; churn devolve `frozenset` usado só dentro da construção. *P-160, P-164, P-173* *(feito: `test_factor_parcels.py`, `test_factor_adapters.py`, `test_evidence_builder_factors.py`)*
- [x] **D-7.1.15** `analytics/repository/sales_repository.py`: `fetch_customer_sku_split_window_sales` e `fetch_sku_region_window_sales` (aditivas; a função da F6 fica intacta). `analytics/service/analytics_service.py`: `get_cannibalization_catalog()` pública. *DA-04, DA-05*
 *(parcial: as duas leituras SQL feitas; `get_cannibalization_catalog()` publica pendente)*
- [x] **D-7.1.16** `adapters/*` e `service/migration_cache.py`, `service/evidence_cache.py` (LRU 200, TTL 6 h, cache de promoções por janela). *DA-04, DA-05*

*Bloco C — serviço e API*
- [x] **T-7.1.17** (testes escritos, red) Testes de contrato da rota `GET /api/v1/sales-trend/insights/product/{sku}` com `TestClient` e serviço com dublês: envelope e `meta` (inclui `modoComparacao`, `indiceAfinidade`, `avisos` e `meta.ia` com `geraComIa`, `motivoTemplate`, `podeForcar`, `diagnosticoVencido` e `orcamento.nivel`; **nenhum valor em dólar**), exemplos 3.1.7/3.1.8/3.1.9 do contrato, `400 TIA-001` (C-01, `comparisonMode=range`), `404 TIA-002` (C-02), `422 TIA-003` (C-03), `503 ANL-001` (C-36), corpo de erro sem eco de parâmetro (LGPD-TIA-13), sem credencial Basic → 401 (LGPD-TIA-14), dublê do `LlmClient` com contador = 0 em todas as rotas `GET` (C-24). *P-150, P-173, P-174, P-186*
- [ ] **T-7.1.18** Teste de `GET /insights/health` (parte não-IA): índice, cache de migração sem SKUs/clientes. *P-187*
- [x] **D-7.1.19** `service/insights_service.py` (`get_product_insight`, `get_health`), `api/route.py` (`InsightsAPIRoute`), `query_params.py`, `schemas.py`, `mappers.py`, `router.py`; registrar em `src/api.py`. *DA-02, DA-11*

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

### Tarefa 7.2-S: Spike de calibração (Vertex AI, tokens, *grounding* + schema no Flash)

**Descritivo Detalhado:** 1 a 2 h com o SDK `google-genai` em modo Vertex, **antes** de codar o cliente e o orçamento, para trocar as estimativas de `trend-insights-llm.md` §14 por números reais. Sem código de produção; teto de gasto do spike US$ 0,50. Responsável: `ai_specialist` + `developer`.

**Critérios de Aceite:**
- [ ] **Calibração de tokens:** 10 pacotes reais congelados (queda de mercado, queda competitiva, alta, `QUALITATIVO`, regional) rodados com e sem *grounding*; registrar entrada, saída, *thinking* e consultas executadas por chamada e comparar com a estimativa (3.800/1.100 sem busca; 5.300/1.300 com busca). Se a média passar de 1,5× a estimada: reduzir `max_output_tokens`/pacote ou subir o gate de *grounding* para 0,50 (decisão registrada).
- [ ] **Schema + *grounding* no `gemini-3.8-flash`:** testar `google_search` + JSON Schema + `thinking low` (nunca `minimal`). Resultado define se o fallback roda **com** busca ou **sem** busca (aviso `SEM_BUSCA_EXTERNA`).
- [ ] **Vertex:** confirmar SKU e preço do Hydrogen e do 3.8 Flash, disponibilidade da Interactions API (senão `generate_content`), citações presentes junto com saída JSON, campos de `usage` e contagem de consultas executadas, endpoint `global`, ausência de retenção de interação, escopo da cota grátis de 5.000 consultas.
- [ ] **Pacote determinístico:** o mesmo dado gera o mesmo `evidenceHash` em execuções repetidas.
- [ ] **(v3, DA-13) Vertex grounding e preço:** confirmar no projeto real, por Billing e página oficial, (a) SKU e preço do grounding no Vertex para Gemini 4 e Gemini 3.8 Flash (documentação com versões divergentes: US$ 14/1.000 consultas ou US$ 35/1.000 *prompts*; aviso de mudança de 13/11/2026), (b) escopo e valor da cota grátis (5.000/mês agregada?), (c) cobrança **por consulta executada** no Gemini 4 (confirmada só no Gemini 3), (d) busca + JSON Schema na mesma chamada **no Vertex** em `gemini-4-hydrogen` e `gemini-3.8-flash` (Preview no AI Studio), (e) citações e `usage` com a busca. Resultado decide `TREND_AI_MODEL_RADAR`, o fallback Flash do radar e `GROUNDING_HARD_CAP_QUERIES`.
- [ ] **(v3) Calibração do radar:** 5 a 8 assuntos reais, medir entrada (estimada 3.300), saída (1.000), consultas executadas (esperado ≤ 5) e custo por radar (meta ≤ US$ 0,05; se passar, reduzir para 4 consultas fundindo a 6). Medir também o diagnóstico com radar em cache (estimado 4.250/1.300) e o contexto do radar (~450 tokens).
- [ ] Números reais gravados em `STATE_IA_TendenciaIA.md` e em `trend-insights-llm.md` §14 e §15; `TREND_AI_PRICING_JSON` e `GROUNDING_FREE_QUERIES_ASSUMED` ajustados.

---

### Tarefa 7.2-B: Orçamento (US$ 2/mês), livro de gastos, kill-switch, gates e template

**Descritivo Detalhado:** controle de custo da F7 como **portão obrigatório** antes de qualquer chamada ao LLM (ADR-009 DA-09 e DA-12; `trend-insights-llm.md` §14.2, §14.6 a §14.8). Pode correr em paralelo com a camada de IA da 7.2 (arquivos distintos). Depende da 7.0c (bucket) e dos DTOs da 7.1. Sem LLM real: dublês `LlmClient` e `BudgetLedger` com contadores.

**Critérios de Aceite (custo, testáveis):**
- [ ] **Nenhum caminho usa Neon:** `gemini-4-neon` não existe no código, na configuração nem na tabela de preços; qualquer chamada registrada pelo espião do `LlmClient` em **todos** os cenários (inclusive `force`, `deep` no corpo, erro, *grounding*) usa só `gemini-4-hydrogen` ou `gemini-3.8-flash`.
- [ ] **Teto mensal e diário:** com gasto + reserva acima de US$ 1,80 (mês) ou US$ 0,20 (dia) o `LlmClient` não é chamado e a resposta é `200` com template; em 80% entra `ALERTA` (grounding só com resíduo ≥ 0,50, `force` negado); o mês e o dia viram em UTC−3.
- [ ] **Acerto de cache custa zero:** diagnóstico salvo para a chave devolve `origem = "cache"` com 0 chamadas ao LLM, 0 reservas, gasto inalterado, sem contar no rate limit.
- [ ] **Template não chama LLM:** gate, kill-switch ou orçamento esgotado → `origem = "template"`, 0 chamadas ao LLM, 0 reservas, nada salvo.
- [ ] **Falha fechada:** livro de gastos ilegível/inescrevível → template (nunca chamada sem reserva).
- [ ] **Capacidade:** simulação com custo médio de US$ 0,0173 por geração (e 0,0325 no pior caso) esgota o teto em ~104 (~55) gerações, nunca acima de US$ 1,80 + 1 reserva.
- [ ] Nada de custo na API (contrato 4.4): varredura das respostas.

**Etapas de Execução (Checklist Técnico):**
- [x] **T-7.2B.1** (testes escritos, red) `[PARALLEL]` `test_budget_ledger.py` com `BudgetLedger` sobre dublê do GCS: reserva e acerto com `usage` real; `if_generation_match` com conflito e até 5 novas tentativas; reserva órfã expira em `RESERVATION_TTL_SECONDS = 150` (relógio falso) e é liberada; reservas simultâneas somam e não estouram o teto; mês/dia UTC−3 e virada de mês/dia; objeto sem usuário/IP; GCS indisponível → falha fechada. *P-178, DA-09*
- [x] **T-7.2B.2** (testes escritos, red) `[PARALLEL]` `test_budget_levels.py`: `NORMAL`/`ALERTA`/`ESGOTADO` por mensal (1,44 e 1,80) e diário (0,20); `custoEstimadoMaximo` (~0,031 sem busca e ~0,073 com 3 consultas acima da cota); log `tia.budget.alert` uma vez por mês; em `ALERTA` o gate de *grounding* sobe a 0,50 e `podeForcar = false`. *P-178, P-180*
- [x] **T-7.2B.3** (testes escritos, red) `[PARALLEL]` `test_cache_zero_cost.py`: acerto de cache = 0 chamadas ao LLM, 0 reservas, gasto inalterado, não conta no rate limit; carga nova do ERP (`dataReferencia` diferente) com **evidência igual** → acerto; evidência diferente, `PROMPT_VERSION` novo ou `force=true` → perda; **mesmo dado, mesmo hash** (listas ordenadas, arredondamento, sem timestamp/nonce); L1 de 5 min não serve após `force`; TTL lógico de 30 dias marca `vencido` sem regenerar sozinho. *P-175 revisada, DA-07*
- [x] **T-7.2B.4** (testes escritos, red) `[PARALLEL]` `test_template_no_llm.py` e `test_gates.py`: cada gate de P-188 (variação < 2%, `SEM_BASE`, delta < R$ 1.000, resíduo < 0,20 sem `REGIONAL` e sem diagnóstico de mercado) → template com contadores zerados e `motivoTemplate` correto; gate de *grounding* (mercado em queda/alta, resíduo ≥ 0,30, `REGIONAL` + resíduo ≥ 0,15) liga/desliga a ferramenta de busca; texto do template sem dígitos e rotulado "Resumo automático (sem IA)"; template nunca é salvo no `InsightStore`. *P-188, P-180*
- [x] **T-7.2B.5** (testes escritos, red) `[PARALLEL]` `test_no_neon.py`: varredura estática do pacote `trend_insights` e dos arquivos de configuração por `neon`/`deep`/`escalon` (falha se existir); config com `TREND_AI_MODEL_DEFAULT=gemini-4-neon` falha na validação (lista permitida = Hydrogen e 3.8 Flash); `TREND_AI_PRICING_JSON` só com esses dois modelos; espião registra o `model` de toda chamada em todos os cenários. *P-177 revisada*
- [x] **T-7.2B.6** (testes escritos, red) `[PARALLEL]` `test_kill_switch.py`: `TREND_AI_ENABLED=false` → template (`IA_DESLIGADA`) antes de qualquer outra etapa, `GET` com `meta.ia.geraComIa = false`, `health.ia.ligada = false`; Vertex indisponível desde o início → template (`IA_INDISPONIVEL`). *P-178.5*
- [x] **T-7.2B.7** (testes escritos, red) `[PARALLEL]` `test_model_policy.py`: falha de infraestrutura do Hydrogen após `LLM_TRANSIENT_RETRY_LIMIT = 2` → **uma** chamada ao Flash (`origem = "fallback"`); falha de schema repete no mesmo modelo 1× e **nunca** vai ao Flash; Flash falha → template + aviso `IA_FALHOU`; Flash sem *grounding* (conforme o spike) → aviso `SEM_BUSCA_EXTERNA`; preço do Flash muda em 01/01/2027 (relógio falso); a chave de cache não inclui o modelo; prazo total de 110 s cobre 2 tentativas + Flash. *P-177, P-183*
- [x] **T-7.2B.8** (testes escritos, red) `[PARALLEL]` `test_rate_limits.py`: 2/min, 10/dia por usuário, `force` 3/dia; acertos de cache e templates não contam; estado só em memória com chave HMAC (LGPD-TIA-11); `429 TIA-004` com `motivo` e `Retry-After`. *P-176*
- [x] **D-7.2B.9** `domain/gates.py`, `domain/budget.py` (níveis, reserva, `custoEstimadoMaximo`), `domain/model_policy.py`, `domain/template_summary.py`, `store/budget_ledger.py`, `TrendInsightsSettings` (`TREND_AI_ENABLED`, `TREND_AI_MONTHLY_BUDGET_USD`, `TREND_AI_DAILY_BUDGET_USD`, `TREND_AI_MODEL_DEFAULT`, `TREND_AI_MODEL_FALLBACK`, `TREND_AI_PRICING_JSON`, `GROUNDING_FREE_QUERIES_ASSUMED`, `INSIGHT_SOFT_TTL_DAYS`, demais constantes da revisão v2 listadas em `STATE_IA_TendenciaIA.md`). *DA-09, DA-12*
- [ ] **D-7.2B.10 (`devops`)** **Cloud Billing Budget de US$ 2,00** no projeto, alertas em 50/80/100% por e-mail (medição independente; não corta gasto); conferir SKU/preço do Vertex AI para Hydrogen e 3.8 Flash e o escopo da cota de *grounding*; `TREND_AI_ENABLED` e demais variáveis no deploy (alterar a variável exige só nova revisão do Cloud Run); lifecycle `ai-budget/` 400 d. *DA-09* *(scripts e runbook entregues em `infra/trend-insights/` e `.agents/docs/devops/trend-insights-infra.md`; EXECUCAO no GCP e `06-verify.sh` pendentes do usuario)*

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** rodar o fluxo em homologação com `TREND_AI_MONTHLY_BUDGET_USD=0,05`: as primeiras gerações usam o LLM, depois o `POST` devolve template (`ORCAMENTO_ESGOTADO`), `GET` intacto.
- [ ] **Cenário 2:** `TREND_AI_ENABLED=false` → todo `POST` em template; religar volta ao normal.
- [ ] **Cenário 3:** após uma semana de uso, comparar o livro de gastos com a fatura (Billing): diferença ≤ 20%; senão ajustar `GROUNDING_FREE_QUERIES_ASSUMED` e a reserva.

---

### Tarefa 7.2: Camada de IA + `POST /generate` + persistência e dedup

**Descritivo Detalhado:** cliente Vertex AI atrás de `LlmClient`, prompts `tia-v2`, pacote de evidências por lista branca (8.000 caracteres), consultas sugeridas, validação antialucinação **com texto sem números**, orquestrador (fluxo de ADR-009 DA-12), `InsightStore` por `evidenceHash`, lease de geração e rota `POST` (ADR-009 DA-07, DA-08, DA-10, DA-12; contrato §3.2; `trend-insights-llm.md` §14). Depende da 7.1, da 7.0c (bucket), da 7.2-S (calibração) e da 7.2-B (orçamento/gates/template). **Antes de começar:** decisão do checkpoint sobre CP-10.

**Critérios de Aceite:**
- [ ] Cache, `force`, dedup e rate limit como no contrato §3.2 (C-25, C-26, C-27); `origem` ∈ `cache`/`template`/`llm`/`fallback` correto em cada caminho.
- [ ] Orçamento, gates e kill-switch conforme a 7.2-B; acumulado sobrevive a reinício.
- [ ] Antialucinação e injection (C-30..C-34); **texto da IA sem nenhum dígito**; SKU só em `skusCitados`.
- [ ] Fallback e template nunca são salvos como diagnóstico; prazo total de 110 s respeitado.
- [ ] Zero dado de cliente no pacote, no GCS e nos logs (C-35); nenhum campo de custo na API (contrato 4.4).

**Etapas de Execução (Checklist Técnico):**
- [x] **T-7.2.1** (testes escritos, red) `[PARALLEL]` `test_evidence_payload.py`: lista branca de campos; base sintética com códigos de cliente únicos → JSON enviado ao dublê não contém esses valores nem as chaves `customer`, `cliente`, `codCliente`, `nome`, `cpf`, `cnpj`, `email` (LGPD-TIA-03); sem `Pc.Ultimo Custo`/custo unitário (LGPD-TIA-04); par com `netClients = 1` vai como `"<3"` (LGPD-TIA-06); UF agregada por LGPD-TIA-05; descrição da galeria sanitizada e truncada (P-184.2); **limite de 8.000 caracteres** com a ordem de corte (afins 10, migração 5, UFs 3, só parcelas ≥ 5% de abs(Δ)); sem marcadores numéricos. *P-179, P-184*
- [x] **T-7.2.2** (testes escritos, red) `[PARALLEL]` `test_search_queries.py`: só função primária, categoria da galeria, fornecedor, UF agregada e período; nunca texto do usuário nem dado de cliente; `MAX_SEARCH_QUERIES = 2` (1 no `QUALITATIVO`); consultas apenas sugeridas. *P-180, LGPD-TIA-12*
- [x] **T-7.2.3** (testes escritos, red) `[PARALLEL]` `test_validation.py`: **qualquer dígito em `resumo`, `explicacao`, `recomendacoes` e `descricao` de hipótese é rejeitado** (reescrita 1× e depois descarte do trecho); SKU fora do pacote (C-32), fator interno sem evidência descartado, fonte externa sem citação/sem data/fora do período → hipótese (C-33, `SEM_DATA`), `origemData`, teto `MEDIA` em externos, `QUALITATIVO` sem valores, limites (5 fatores, 2 fontes por fator, 3 hipóteses, 3 recomendações, `resumo` ≤ 400, `explicacao` ≤ 160), URLs só `http(s)`; `titulo` da fonte não é validado como texto da IA. *P-181, P-182*
- [x] **T-7.2.4** (testes escritos, red) `[PARALLEL]` `test_pricing.py`: custo = tokens + consultas executadas × preço (cota grátis assumida de 1.500); preços do Hydrogen e do Flash (com a virada de 01/01/2027) vindos de `TREND_AI_PRICING_JSON`; o acerto usa o `usage` real, inclusive nas falhas que consumiram tokens. *P-178.1*
- [x] **T-7.2.6** (testes escritos, red) `test_llm_orchestrator.py` com dublê do `LlmClient`: ordem kill-switch → cache → gates → rate limit → reserva → single-flight → Hydrogen → Flash → template; transitório com backoff até 2; schema inválido → 1 nova tentativa com códigos de violação → template (C-30); combinação tools+schema recusada ou sem citações → modo 2 chamadas na mesma geração (contingência); prazo total 110 s com relógio falso; injection na galeria/página (C-34) não muda schema, tipos nem números; log com `caplog` só com os campos de P-185.2 e erro do dublê cuja mensagem contém o pacote não aparece no log (LGPD-TIA-07). *P-183, P-184, P-185.2*
- [x] **T-7.2.7** (testes escritos, red) `test_generation_guard.py`: dedup local (`Future`) e entre instâncias (lease dublê, polling, lease vencido); seguidor recebe `origem = "cache"`; objeto de lease contém só `expiresAt` (LGPD-TIA-10). *P-176.2*
- [x] **T-7.2.8** (testes escritos, red) `test_insight_store.py`: caminho do objeto `.../{promptVersion}/{evidenceHash}.json`; gravação só após validação e só para `llm`/`fallback`; `force` sobrescreve; `StoredInsight` guarda custo/tokens/consultas mas o mapper da API os descarta; varredura do JSON gravado sem dado de cliente nem usuário/IP (LGPD-TIA-09). *P-175, DA-07*
- [x] **T-7.2.9** (testes escritos, red) Testes de contrato do `POST /generate` e do `meta.ia` no `GET`: exemplo 3.2.1; `origem`/`motivoTemplate`/`reutilizado`; `422 TIA-003` em `SEM_VARIACAO`; `429 TIA-004` com `motivo` (`LIMITE_DE_PEDIDOS`, `LIMITE_DIARIO`) e `Retry-After`; template com `resumoAutomatico` e `diagnosticoIa = null`; aviso `IA_FALHOU`; **nenhum 503 de IA**; `deep` no corpo ignorado; `health` com `ia.ligada` e `orcamento.nivel` (sem credencial, sem dólar); **varredura das respostas sem as chaves `usd`, `custo`, `token`, `consultas`, `preco`, `teto`, `gasto`, `saldo`, `evidenceHash`** (contrato 4.4). *P-174..P-188*
- [x] **D-7.2.10** `llm/client.py`, `llm/gemini_client.py` (modo Vertex com ADC, `thinking_level`, sem `temperature`, Interactions API ou `generate_content` conforme o spike), `llm/prompts/tia_v2/`, `output_schema.py`, `evidence_payload.py`, `search_queries.py`, `validation.py`, `pricing.py` (conteúdo: `trend-insights-llm.md` §14.5). *DA-10*
- [x] **D-7.2.11** `service/llm_orchestrator.py`, `service/generation_guard.py`, `store/insight_store.py` (chave com `evidenceHash`, L1 de 5 min, TTL lógico de 30 dias), integração com os módulos da 7.2-B. *DA-07, DA-08, DA-12*
- [x] **D-7.2.12** `insights_service.generate_product_insight` e rota `POST`; `meta.ia` no `GET`. `requirements.txt`: `google-genai` (versão fixada). *DA-02*
- [ ] **D-7.2.13 (`devops`, PENDENTE, bloqueia release; auditoria LGPD A-1/A-2)** Fixar `TREND_AI_LOCATION` em região us/eu do Vertex (hoje o default é `global`, `config.py:18`) e registrar no ADR-009; reauditar antes do deploy. Conta de runtime com `roles/aiplatform.user`; **sem** segredo `gemini-api-key` e sem `GEMINI_API_KEY`; variáveis `TREND_AI_*` e `TREND_INSIGHTS_BUCKET`; projeto com faturamento (nível gratuito proibido, LGPD-TIA-08). Aproveitar para mover `AUTH_PASSWORD`/`DB_PASSWORD` ao Secret Manager (ADR-009 CP-8). *(scripts e runbook entregues em `infra/trend-insights/` e `.agents/docs/devops/trend-insights-infra.md`; EXECUCAO no GCP e `06-verify.sh` pendentes do usuario)*

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** gerar análise real em homologação → números da cascata na tela, texto sem números, fontes clicáveis, custo registrado em `ai-budget/` (e fora da API).
- [ ] **Cenário 2:** clicar duas vezes / duas abas → uma chamada; segundo clique no mesmo dado → `origem = "cache"` e gasto inalterado.
- [ ] **Cenário 3:** reduzir o teto para US$ 0,01 → `POST` devolve template (`ORCAMENTO_ESGOTADO`), `GET` intacto.
- [ ] **Cenário 4:** `TREND_AI_ENABLED=false` ou Vertex fora → template (`IA_DESLIGADA`/`IA_INDISPONIVEL`).

---

### Tarefa 7.2-R: Investigação externa v3 (radar externo compartilhado, 8 dimensões, matéria-prima, teto de consultas)

**Descritivo Detalhado:** implementa o ADR-009 **DA-13** e `trend-insights-llm.md` §15 e §15.14, sobre o que a 7.2 e a 7.2-B já entregaram (`PROMPT_VERSION` `tia-v2` → `tia-v3`). Contrato: `sales-trend-insights.md` 1.2.0 (`fatoresExternos[8]`, `radar`, `radarExterno`, `meta.ia.radar`, avisos e motivos novos). Depende da 7.2, da 7.2-B e do spike 7.2-S ampliado; fases R1 a R3 podem ser escritas antes do spike. Regras `P-180.1` a `P-180.5`, `P-181`, `P-182.x`, `P-184`, `P-178.x` revisadas pelo `analyst` (CP-18) antes de fechar a R5. Sem LLM real nos testes: dublê do `LlmClient`, do `RadarStore` e do `BudgetLedger`.

**Critérios de Aceite:**
- [ ] **LLM chamado sempre leva radar** (ou `SEM_RADAR` explícito): nenhuma resposta com `diagnosticoIa` traz menos de 8 `fatoresExternos`; `SEM_EVIDENCIA` nunca vira `NEUTRA` nem "não houve".
- [ ] Radar sem dado da empresa: JSON enviado à chamada com busca não contém SKU, cliente, variação, valor nem descrição da galeria; chave do objeto sem usuário/SKU.
- [ ] **Nenhuma string da web chega ao radar armazenado nem à API:** só enums, `tema` fechado e frases fixas do backend.
- [ ] Teto duro de 1.500 consultas/mês: acima dele, nenhum radar novo e nenhuma busca do produto, e **nunca** se paga busca; a API não expõe o motivo em termos de custo.
- [ ] Custo: radar dentro da reserva (~US$ 0,02, 6 consultas); capacidade simulada de ~83 diagnósticos/mês no teto de US$ 1,80 com 15 radares/mês; chave de cache do diagnóstico sem o radar.
- [ ] Prazos: `LLM_TOTAL_DEADLINE_SECONDS = 125`, `IN_FLIGHT_LOCK_TTL_SECONDS = 150`, `RADAR_DEADLINE_SECONDS = 55`, `RESERVATION_TTL_SECONDS = 180`; HTTP da tela 150 s.

**Etapas de Execução (Checklist Técnico):**

*Fase R1: matéria-prima e assunto do radar `[PARALLEL]`*
- [x] **T-7.2R.1** (tester, red) `test_radar_subject.py`: função primária → matéria-prima; **fusão de famílias** (`colageno_pele` e `colageno_tipo2` geram o mesmo slug); palavra-chave só por lista fechada (descrição da galeria apenas comparada, nunca vai ao prompt); fallback categoria/`Tipo`; sem termo → `SEM_TERMO_BUSCA`; slug estável (minúsculas, sem acento, `-`). *P-180.4*
- [x] **D-7.2R.2** `domain/raw_material.py`: tabela de matéria-prima (`PRIMARY_FUNCTION_RAW_MATERIAL_TERMS`, `RAW_MATERIAL_KEYWORDS`, famílias) e `infer_radar_subject(evidence) -> RadarSubject(slug, termo, tipo)`.

*Fase R2: dimensões, tabelas fechadas e sanitização `[PARALLEL]`*
- [x] **T-7.2R.3** (tester, red) `test_external_dimensions.py` e `test_radar_themes.py`: 8 dimensões em ordem fixa; mapeamento para `fatores[].tipo`; `RADAR_THEMES` por dimensão (lista fechada, inclui `OUTRO`) e `RADAR_THEME_TEXTS` sem dígitos e sem dado de produto; `temporal_relation` (`ANTERIOR`/`CONTEMPORANEA`/`POSTERIOR`/`SEM_DATA`/`ANTIGA`) nas bordas da Janela Atual; `directional_coherence`. *P-180.5*
- [x] **T-7.2R.4** (tester, red) `test_radar_injection.py` **(C-42)**: saída do radar com tema fora da lista, texto livre, URL, `<>{}` ou marcador (`ignore`, `instruç`, `system`, `prompt`, `http`) é **rejeitada inteira** e não gravada; radar envenenado não altera schema, tipos nem cria número; página com instrução não chega ao armazenado; log `tia.radar.injectionSuspect` sem payload. *P-184*
- [x] **D-7.2R.5** `domain/external_dimensions.py`, `domain/radar_themes.py`, `llm/radar_schema.py` (`RadarOutput` raso: `movimento`, `intensidade`, `tema`, `fonteIdx`; sem string livre), sanitização e lista fechada em `llm/validation.py`.

*Fase R3: radar externo (store, serviço, runner, política) `[PARALLEL]` com R2*
- [x] **T-7.2R.6** (tester, red) `test_radar_store_policy.py` **(C-37)**: chave `radar/{versão}/{slug}/{AAAA-MM}.json` sem SKU/usuário; TTL 30 dias (corrente e anterior) e 180 (meses antigos), *stale* até 120; `force` não renova; single-flight (2 usuários e 2 instâncias compartilham 1 geração); escrita `if_generation_match`; objeto sem dado da empresa. *P-180.3*
- [x] **T-7.2R.7** (tester, red) `test_gates_template.py` ampliado **(C-36)**: `radar_policy(radar_state, budget_level, daily_new, share_spent, hard_cap)` → `USE_FRESH | GENERATE | USE_STALE | NONE`; `product_search_enabled` só com `SEM_RADAR`, modo ≠ `QUALITATIVO`, `NORMAL`, resíduo ≥ 0,30 e abaixo do teto duro; `evaluate_llm_gates` inalterado; todo diagnóstico por LLM leva radar. *P-180.1, P-188*
- [x] **T-7.2R.8** (tester, red) `test_evidence_payload.py` ampliado: radar **fora do `evidenceHash`**; bloco do radar ≤ `MAX_RADAR_CONTEXT_CHARS = 2.000`, sem dado de cliente; ordem do prompt system → radar → evidências. *P-179*
- [x] **D-7.2R.9** `store/radar_store.py`, `service/radar_service.py` (`get_or_create`, lease próprio 90 s), `RadarRunner` em `service/llm_runner.py` (modelo `TREND_AI_MODEL_RADAR`, 1 nova tentativa por schema, fallback Flash conforme o spike, `two_step` como contingência), `domain/gates.py` (`radar_policy`, `product_search_enabled`), `llm/search_queries.py` (`build_radar_queries` por `RADAR_QUERY_TEMPLATES`; `build_product_query`), `llm/prompts.py` (`radar_v1`, `tia_v3`, bloco `<radar_externo_{nonce}>`).

*Fase R4: teto duro de consultas e orçamento `[PARALLEL]` com R3*
- [x] **T-7.2R.10** (tester, red) `test_budget.py` ampliado **(C-43, C-44)**: reserva do radar (6 consultas); `RADAR_BUDGET_SHARE = 0,25`; `RADAR_MAX_NEW_PER_DAY = 3`; `GROUNDING_HARD_CAP_QUERIES = 1.500`: no teto, sem radar novo e sem busca do produto, radar *stale* ou `SEM_RADAR`, **nunca** cobrança de busca; campos `gastoRadarMes`, `radaresNovosMes`, `radaresNovosDia` no livro; a 80% sem busca do produto e radar só se ausente; esgotado → template com `radarExterno` *stale* sem nova chamada; simulação de capacidade (~83 diagnósticos com 15 radares). *P-178.2..P-178.5*
- [x] **D-7.2R.11** `domain/budget.py` (variante radar), `store/budget_ledger.py` (`reserve`/`settle` por tipo `RADAR`/`DIAGNOSTICO`, consultas assumidas, trava `RADAR_BUDGET_SHARE`, teto duro), `llm/pricing.py` (preço de busca por consulta, sem cobrar acima do teto), `config.py` (`TREND_AI_MODEL_RADAR`, `GROUNDING_HARD_CAP_QUERIES`, `RADAR_*`; validação da lista permitida de modelos).

*Fase R5: diagnóstico com 8 dimensões, causalidade e orquestração*
- [x] **T-7.2R.12** (tester, red) `test_external_validation.py` **(C-38 a C-41)**: 8 dimensões sempre (omitida → `NAO_AVALIADA`/`DIMENSAO_OMITIDA_PELA_IA`); `SEM_EVIDENCIA` ≠ `NEUTRA`; `POSTERIOR`/`SEM_DATA`/`ANTIGA` nunca em `fatores[]`; coerência direcional; confiança nunca `ALTA`; no máximo 3 externos; sem `parcelaEstimada`; `fonteIds` fora do radar ∪ busca rejeitado; dígito em `nota` bloqueia; `fonteIds` com gramática `^[FP][0-9]{1,2}$`. *P-180.5, P-181, P-182*
- [x] **T-7.2R.13** (tester, red) `test_llm_orchestrator.py` ampliado **(C-45)**: ordem da §15.8 (kill-switch → cache → gate → orçamento → single-flight → radar → diagnóstico → Flash); radar falha → diagnóstico segue com `SEM_RADAR` e aviso `SEM_RADAR_EXTERNO` (sem `IA_FALHOU`); Flash do diagnóstico usa o mesmo radar sem ferramentas; **cache do diagnóstico não depende do radar**; revisar **C-28b** (resíduo 25% agora chama o LLM com radar e sem busca do produto) e **C-29a** (a 80% a busca do produto desliga); prazos 125/150 s com relógio falso. *P-183*
- [x] **D-7.2R.14** `llm/output_schema.py` (`avaliacoesExternas`), `llm/validation.py` (8 dimensões, `fonteIds`, promoção a `fatores[]`), `llm/evidence_payload.py` (bloco do radar fora do hash), `store/insight_store.py` (`radarRef`, TTL de 30 dias para todo diagnóstico por LLM), `service/llm_orchestrator.py` (passos 6 a 8 da §15.8), `domain/template_summary.py` (`radarExterno` somente leitura, texto do resumo inalterado), constantes e `PROMPT_VERSION = "tia-v3"`.

*Fase R6: contrato e API*
- [x] **T-7.2R.15** (tester, red) `test_api_contract.py` ampliado: `fatoresExternos` (8 itens, enums de 2.4), `fontes[].id`, `radar` (`origem`, `diasDesdeGeracao`, `desatualizado`), `meta.ia.radar.estado`, `data.radarExterno` (GET e `POST` em template, sem `direcao`), avisos `RADAR_DESATUALIZADO` e `SEM_RADAR_EXTERNO`, motivos `POSTERIOR_AO_PERIODO`/`SEM_COERENCIA_DIRECIONAL`, `health.radar` e `ia.modeloRadar`, `promptVersion = "tia-v3"`, `version = "1.2.0"`; **varredura de custo (contrato 4.4) estendida:** nenhuma chave `usd`, `custo`, `token`, `consultas`, `preco`, `teto`, `gasto`, `saldo`, `evidenceHash`, `radarHash` nem caminho `radar/` em qualquer resposta.
- [x] **D-7.2R.16** `service/insights_service.py` e `api/router.py` (campos novos, `meta.ia.radar`, avisos, `radarExterno` no `GET`), mapper que descarta `radarRef`, `radarHash` e campos de custo; `GET` nunca gera radar.

*Fase R7: infraestrutura e script de budget (`devops`)*
- [ ] **D-7.2R.17 (`devops`)** Atualizar `infra/trend-insights/lifecycle.json` com o prefixo `radar/` (retenção **210 dias**, acima de 180 dias de validade do passado e 120 de *stale*) e `01-bucket.sh` (comentário de prefixos); `env.sh` e `.github/workflows/deploy-cloud-run.yml` repassam `TREND_AI_MODEL_RADAR`, `GROUNDING_HARD_CAP_QUERIES`, `RADAR_*`, `LLM_TOTAL_DEADLINE_SECONDS=125`, `IN_FLIGHT_LOCK_TTL_SECONDS=150`, `RESERVATION_TTL_SECONDS=180`; `pricing.json` ganha o preço de busca por consulta **após o spike** (valor do Vertex confirmado); `verify_checks.py`/`06-verify.sh` conferem o ciclo de vida de `radar/` e as novas variáveis; `04-budget.sh` (Cloud Billing Budget de US$ 2, 50/80/100%) **inalterado**, mas o alerta de 50% passa a ser lido junto com o contador de consultas do livro; runbook `.agents/docs/devops/trend-insights-infra.md` ganha: invalidar radar suspeito (subir `RADAR_PROMPT_VERSION` ou apagar `radar/{versão}/{slug}/`), conferir SKU de grounding no Billing e acompanhar o teto de 1.500 consultas.
- [ ] **D-7.2R.18 (`privacy_officer`)** Registrar no RIPD/parecer que a chamada com busca do radar não leva dado comercial nem pessoal (só termo de assunto, mês e lista de dimensões).
- [ ] **D-7.2R.19 (`security`)** Red team da §15.11 sobre o radar (página com instrução, fonte `POSTERIOR` como causa, fonte sem data, "sem evidência" convertida em "neutra") antes do release.

*Fase R8: frontend e avaliação*
- [x] **D-7.2R.20 (`designer`/`developer`)** Painel de fatores externos: 8 linhas fixas com `SEM_EVIDENCIA` como "não encontramos evidência na pesquisa feita" (nunca "não houve"), selo de idade do radar e `RADAR_DESATUALIZADO`, bloco `radarExterno` somente leitura com o rótulo "Radar externo de N dias (sem análise de IA para este produto)"; ajustar o Design Plan.

**Audit (Testes e Validação):**
- [ ] **Cenário 1:** dois produtos da mesma matéria-prima no mesmo mês: 1 radar gerado (`GERADO_AGORA`) e o segundo diagnóstico com `radar.origem = "CACHE"`; consultas de busca do mês +5 no livro.
- [ ] **Cenário 2:** `GROUNDING_HARD_CAP_QUERIES` baixado para 5 em homologação: segundo radar não é gerado; diagnóstico sai com `SEM_RADAR` ou radar *stale*; fatura sem item de busca.
- [ ] **Cenário 3:** orçamento esgotado com radar existente: `POST` devolve template com `radarExterno`; sem nenhuma chamada ao Vertex.
- [ ] **Cenário 4:** objeto de radar com `tema` inválido plantado no GCS é rejeitado e ignorado.

---

### Tarefa 7.3: Frontend — painel "Por que?"

**Descritivo Detalhado:** painel lateral/tela cheia na página `/tendencia-vendas`, conforme `design/plans/analytics-tendencia-ia.md` e contrato §5. Pode começar com a 7.1 pronta (cascata) usando dublê HTTP para a parte de IA.

**Etapas de Execução (Checklist Técnico):**
- [x] **T-7.3.1** `[PARALLEL]` Testes de `trend-insights.service.ts` e do store do painel (tipos do contrato sem `any`; estados carregando/gerando/erro; decisão por `error.code`/`motivo`; timeout de 150 s; polling quando `meta.ia.geracaoEmAndamento`). *P-174..P-176*
- [x] **T-7.3.2** `[PARALLEL]` Testes de componentes: cascata com `pontosPercentuais`, célula do afim com o componente `TrendCell` existente, "Gerar de novo"/"Atualizar" com confirmação antes de `force=true` (sem "Análise aprofundada"), rótulo "Resumo automático (sem IA)" em `origem = "template"` com o motivo, botão "Gerar resumo automático" quando `geraComIa = false`, nenhuma exibição de custo ou orçamento em dólar, botões desabilitados por `meta.ia`, fontes com `rel="noopener noreferrer"` e domínio, texto do LLM como texto puro, `"<3"` exibido como "menos de 3 clientes". *P-175, P-184.5*
- [x] **D-7.3.3** Serviço, store, componentes e utilitários da feature (Design Plan).
- [x] **D-7.3.4 (F6, tarefa pequena)** Página de Canibalização aceita `?abrir={sku}` e abre o drawer de equilíbrio de preço (Design Plan Q-D2). O link do painel usa `periodo=90` com a nota de diferença de períodos (Q-D8).
- [x] **D-7.3.5** Refatorações aprovadas no Design Plan: focus trap para `shared/a11y/dialog-focus.ts` (Q-D4) e `MECHANISM_VISUAL_META` para `analytics/utils/cannibalization-mechanism.ts` (Q-D5), sem mudança de comportamento e com os testes da F6 verdes.
- [x] **D-7.3.6 (condicional ao checkpoint CP-10)** Renderizar `sugestoesBuscaHtml` só em `<iframe sandbox>`.

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
- [ ] **D-7.5.2** Medir concordância do fator principal, taxa de fontes válidas, fontes com `origemData = MODELO` e precisão de mercado × concorrência; **medir a perda de concordância causada pelos gates (resíduo < 0,20 vira template), pelo pacote de 8.000 caracteres e pelo texto sem números**; recalibrar limiares (`MIN_EXPLAINABLE_VARIATION_PCT`, `DOMINANT_EFFECT_RATIO`, `LLM_MIN_RESIDUAL_SHARE`, `GROUNDING_MIN_RESIDUAL_SHARE`) se necessário, subindo só o que couber no teto de US$ 2.
- [ ] **D-7.5.4 (v3)** Métricas do radar (`trend-insights-llm.md` §15.13 e red team §15.11): falso positivo causal ≤ 10% dos fatores externos promovidos; cobertura 100% das 8 dimensões; 100% das fontes de `fatores[]` externos `ANTERIOR`/`CONTEMPORANEA`; consultas médias por radar ≤ 5 e custo ≤ US$ 0,05; radares com injeção bloqueada 100% nos casos de red team; taxa de `SEM_EVIDENCIA` por dimensão (consulta fundida 3+4+5) e de tema `OUTRO` (> 20%: ampliar `RADAR_THEMES`); comparar Hydrogen × Flash no radar para decidir `TREND_AI_MODEL_RADAR`.
- [ ] **D-7.5.3** Registrar o custo real por diagnóstico (do livro e da fatura), comparar com ~US$ 0,014 a 0,018 e ajustar `TREND_AI_PRICING_JSON`, `GROUNDING_FREE_QUERIES_ASSUMED` e as reservas. Revisar o preço do Flash na virada de 01/01/2027.

---

## 3. Matriz de rastreio das condições de privacidade (Etapa 4)

| Condição | Teste / verificação |
| :--- | :--- |
| LGPD-TIA-01 | T-7.1.12 |
| LGPD-TIA-02 | T-7.1.13 |
| LGPD-TIA-03, 04 | T-7.2.1, D-7.5.1 |
| LGPD-TIA-05, 06 | T-7.1.6, T-7.2.1 |
| LGPD-TIA-07 | T-7.2.6 |
| LGPD-TIA-08 | T-7.2.9, D-7.2.13 (`devops`: Vertex com faturamento, sem chave de API) |
| LGPD-TIA-09, 10 | T-7.2.7, T-7.2.8, T-7.2B.1, D-7.0c.9 (`devops`) |
| LGPD-TIA-11 | T-7.2.7 |
| LGPD-TIA-12 | T-7.2.2, T-7.2R.4 (radar sem dado da empresa e sem texto livre), D-7.2R.18 |
| LGPD-TIA-13 | T-7.1.17 |
| LGPD-TIA-14 | T-7.0c.3, T-7.1.17 |

## 4. Ordem e paralelismo

```
7.0c ───────────────┐ (pode ir a produção sozinha)
7.1 (A ∥, B ∥) → 7.1-M ─┬─► 7.2-S (spike, ampliado v3) ─┬─► 7.2 ─► 7.2-R (radar; R1..R3 ∥, R4 ∥) ─► 7.5
                        │                   └─► 7.2-B (orçamento, ∥ com 7.2) ─┘
                        ├─► 7.3 (cascata; IA após 7.2)
                        └─► 7.4
```
