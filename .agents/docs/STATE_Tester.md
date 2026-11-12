# STATE_Tester — Fase 1 Analytics Comercial (F4 Cross-sell) — Etapa 3 (TDD)

| Campo | Valor |
| :--- | :--- |
| Agente | `tester` |
| Data | 2026-11-06 |
| Branch | `feature/analytics-cross-sell` (sem commit; commits na Etapa 5) |
| Status | T-01 a T-18 escritos; aguardando `developer` |

## Arquivos criados / alterados

Backend (`pytest`):
- `tests/analytics/__init__.py`, `tests/analytics/conftest.py`, `tests/analytics/fixtures/{__init__,synthetic_data}.py`
- T-01 `tests/analytics/test_pagination.py`
- T-02 `tests/analytics/test_sales_repository.py`
- T-03 `tests/analytics/test_analytics_cache.py`
- T-04 `tests/analytics/test_analytics_api_foundation.py`
- T-05 `tests/analytics/test_analytics_privacy.py`
- T-06 `tests/test_basket_mining.py` (acréscimo de 3 testes; os 7 existentes intactos)
- T-07 `tests/analytics/test_cross_sell_rules.py`
- T-08 `tests/analytics/test_cross_sell_returns.py`
- T-09 `tests/analytics/test_cross_sell_product.py`
- T-10 `tests/analytics/test_cross_sell_customer.py`
- T-11 `tests/analytics/test_cross_sell_explanation.py`
- T-12 `tests/analytics/test_cross_sell_api.py`
- T-16 `tests/analytics/test_cross_sell_backtest.py`
- T-17 `tests/analytics/test_product_search.py`

Frontend (Karma/Jasmine), em `frontend/src/app/`:
- Apoio: `features/analytics/testing/cross-sell-test-data.ts`, `features/analytics/testing/fake-cross-sell-store.ts`
- T-13 `features/analytics/services/analytics.service.spec.ts`, `features/analytics/utils/analytics-error.spec.ts`
- T-14 `features/analytics/services/cross-sell.store.spec.ts`
- T-15 `features/analytics/components/product-cross-sell-panel/…spec.ts`, `features/analytics/components/customer-cross-sell-panel/…spec.ts`, `features/analytics/analytics.routes.spec.ts`, `core/layout/navbar/navbar.component.spec.ts`
- T-18 `features/analytics/components/code-search-form/code-search-form.component.spec.ts`

Checklist: seções "Audit" das Tarefas 1 a 4 preenchidas em `tasks/analytics-cross-sell.md`.

## Resultado atual
- `pytest --continue-on-collection-errors`: 64 passam; 13 módulos de `tests/analytics/` com `ModuleNotFoundError: src.modules.analytics` (esperado); 2 novos de T-06 falham com `TypeError: unexpected keyword 'max_len'` (esperado); **2 falhas pré-existentes** em `tests/test_dynamic_sku_pricing.py` (já falhavam antes, sem relação com esta fase).
- Sem `--continue-on-collection-errors`, o pytest interrompe na coleta até existir `src/modules/analytics/` (B-01).
- `tsc -p tsconfig.spec.json`: só erros de módulo inexistente (TS2307) e `any` implícito derivado deles.

## Decisões de interface tomadas pelo Tester (o checklist não fixava)
1. Repositório: `fetch_order_baskets(cutoff: date)` e `fetch_catalog()`; conexão por `pyodbc.connect(...)` via módulo.
2. Cache: `_build_snapshot()` (carga), `get_cache_status()` → `.state`/`.load_duration_ms`, `reset_cache()` (apoio a teste), `ReloadTooSoonError` em `analytics_cache`. A data de referência da carga sai de `analytics_cache._utc_now()` em UTC-3; corte = referência + 1 dia. `AnalyticsSnapshot` expõe `reference_day`.
3. Serviço chamado pelo router via módulo (`analytics_service.get_health/reload_cache/get_product_cross_sell/get_customer_cross_sell/search_products`), com `PageRequest`.
4. Domínio: `build_valid_baskets` devolve colunas `Pedido`, `Cod Produto`, `Qtd Venda` (`int8`); `assert_base_is_sufficient(valid_basket_count, useful_rule_count)`; `snapshot_view` = objeto com `rules_by_antecedent`, `catalog`, `skus_with_basket` (produto) ou `customer_history`, `reference_day` (cliente); `recommend_for_customer(view, customer_code, apply_stock_filter=True)`; itens com `rule`, `entry`, `reason`, `days_since_last_purchase`, `related_antecedent_count`, `unit_margin`, `score`; `ProductRecommendation` com `rule`, `entry`, `is_out_of_stock`, `has_non_positive_margin`.
5. Explicação: `build_customer_explanation(rule, (desc_a, desc_b), days_since_last_purchase|None)`; retorno com chaves/atributos `frequencia`, `intensidade`, `evidencia`, `motivo`.
6. Backtest: `evaluate_month(order_baskets, catalog_df, "YYYY-MM")`; `excluded_by_reason` com `SEM_PERFIL` > `SEM_COMPRA_NO_MES` > `SEM_RECOMENDACAO` (precedência), população = todo cliente com VENDA até o fim de N.
7. Frontend: serviço devolve o envelope completo; store com `mode/setMode`, `product`/`customer` (`status`, `response`, `error`, `pageRequest`), `goToPage(n)` no modo ativo, `error() === null` = falha genérica; `CodeSearchFormComponent` em `components/code-search-form/` com input `enableProductSearch`; rótulo da navbar "Análises de Vendas" (D-2 do Design Plan, aprovado) em vez de "Analytics Comercial" do F-06.

## Riscos de implementação detectados pelos testes
- Ponto flutuante nos limites inclusivos: o mlxtend calcula a confiança 50/500 como `0.09999999999999999`; o filtro `>=` atual de `mine_association_rules` descarta a regra. O domínio precisa de tolerância ou de recálculo por contagens inteiras.
- Arredondamento de exibição: `Decimal(str(x))` + `ROUND_HALF_UP` (1,15 → "1,2"; 0,345 → 35%); `Decimal(x)` binário falha.

---

# Etapa 4 — Quality Gate 360 (Tester) — 2026-11-10

## Números
| Verificação | Resultado |
|---|---|
| `pytest tests/analytics tests/test_basket_mining.py` | **267 passam, 0 falham** (25 s). Antes das correções: 258 passam / 3 falham (privacidade). |
| `tests/analytics` com cobertura (`--cov=src/modules/analytics --cov-branch`) | 260 passam; **93 %** no total (1.122 linhas, 74 sem cobertura). Sem o script CLI `backtest/run_cross_sell_backtest.py` (0 %, 64 linhas), o módulo fica em ~99 %. |
| Suíte completa `pytest tests` | **Não termina**: trava em testes legados que conectam no SQL Server real pelo `.env` (ver abaixo). Por partes: 260 analytics + 57 legados passam, 0 falham; 7 legados ficam travados, sem resultado. |
| Ruff (E, W, F, B, C90; linha 120) nos arquivos da fase | `src/modules/analytics`: 5 achados (3 E501, 2 B905), todos em produção. `tests/analytics`: 0, depois das correções. `src/api.py`: só achados preexistentes. |
| Karma `ng test --watch=false --browsers=ChromeHeadless` | **73/73 SUCCESS** |
| `ng build` | Sem erros nem avisos. Bundle inicial **511,99 kB** (511.993 bytes), transferência estimada 116,00 kB. O orçamento `maximumWarning: 500kB` vale 512.000 bytes: **sobram 7 bytes** antes do aviso. Chunks lazy: `cross-sell-page-component` 64,07 kB e `analytics-routes` 3,27 kB. |

Ferramentas: o projeto não tem configuração de ruff, flake8, pylint ou mypy (`requirements.txt` só traz `pytest`; não há `pyproject.toml` nem `setup.cfg`) e o frontend não tem ESLint (`ng lint` indisponível). Para esta auditoria, `ruff 0.17.4`, `coverage` e `pytest-cov` foram instalados só no scratchpad da sessão (`pip --target`), sem alterar o ambiente nem o repositório.

## Suíte completa: testes lentos e motivo (preexistente, fora da fase)
Os testes abaixo chamam o pipeline de `pricing` sem mock: `get_cached_base_data()` / `get_cached_etl_data()` → `fetch_sales_from_database()` no SQL Server real (`.env` presente e banco acessível) → `mine_association_rules` (FP-Growth do mlxtend) sobre a base inteira. É o mesmo gargalo que travou a carga do cross-sell (>10 min, ~4 GB) e levou à contagem direta (DA-04 revisada). Com o banco inacessível, esses testes falhavam rápido. Por isso a Etapa 3 registrou "2 falhas antigas" em `test_dynamic_sku_pricing.py`. Agora eles travam.

| Teste | Situação |
|---|---|
| `tests/test_api.py::test_predict_endpoint_success` | travado por mais de 15 min (timeout de 900 s) |
| `tests/test_api.py::test_export_csv_endpoint`, `::test_predict_variable_k_ratio`, `::test_auto_tune_endpoint` | mesmo caminho (`/predict`, `/export`, `/auto-tune`); não terminaram em 240 s |
| `tests/test_dynamic_sku_pricing.py` (2 testes) | `execute_pricing_computation` → banco real; travou mais de 10 min |
| `tests/test_meta_tuner.py::test_fitness_evaluation_strategies`, `::test_genetic_algorithm_run` | fixture `prepared_data` → `get_cached_etl_data()` + FP-Growth completo; travou |

Nenhum desses arquivos nem `src/modules/pricing/**` foi alterado pela fase (`git diff main` vazio depois da reversão B-1). Classificação: **preexistente / ambiente**. Sugestão (fora da fase; T7 ou dívida técnica): marcar esses testes como `@pytest.mark.integration`, excluí-los por padrão (`-m "not integration"`) ou trocar a fonte por mock/massa sintética, e adotar `pytest-timeout`. O CI (`deploy-cloud-run.yml`) roda só `test_auth.py` e `test_elasticity_model.py` e não é afetado.

Legados que passam (57): `test_auth` 5, `test_backtest_simulation` 4, `test_basket_mining` 7, `test_database` 7, `test_elasticity_model` 3, `test_etl` 6, `test_inventory_api` 7, `test_inventory_engine` 7, `test_meta_tuner` 3 de 5, `test_price_optimizer` 1, `test_pricing_cache` 2, `test_api` 5 de 9 (health, config, validation_error, auto_tune_invalid_strategy, db_status).

## Falhas classificadas
| Falha | Classe | Ação |
|---|---|---|
| 3 testes em `test_analytics_privacy.py` | da fase, **teste errado** (decisão do `privacy-officer`) | corrigidos pelo Tester conforme a decisão, sem mudar produção; 6/6 passam |
| `test_direct_count_matches_fp_growth_*` (novo teste, 1ª versão) | do teste | ver "Auto-Healer" |
| Testes de pricing com banco real (7) | preexistente / ambiente | fora da fase; ver acima |

## Correções aplicadas pelo Tester (somente testes)
1. `tests/analytics/test_analytics_privacy.py`, conforme a decisão do `privacy-officer`:
   - `TEST_CLIENT_LOGGERS = ("httpx", "httpcore")` e `_is_test_client_record`: só ignora `record.name` igual a `httpx`/`httpcore` ou que comece com `httpx.`/`httpcore.`. Conferido à parte que registros de `root`, `uvicorn.access`, `starlette`, `fastapi`, `src.*` e `httpxfoo` continuam reprovando o teste. Nível DEBUG mantido.
   - `PARAMETER_KEYS` (7 chaves) e `_assert_parameters_are_scalar_numbers` (`int`/`float`, nunca `bool`), usados em produto (`meta.parametros`) e health (`data.parametros`). No laço de `_all_keys`, só o par `(".meta.parametros", "customerProfileDays")` fica isento.
   - Health: allowlists de `data` (9 chaves) e `meta` (`timestamp`, `version`, `dataReferencia`). A verificação de texto agora usa `copy.deepcopy` + `del data.parametros.customerProfileDays` + `json.dumps(...).lower()` sem "customer" nem "cliente". A checagem dos códigos de cliente em `response.text` foi mantida.
2. `tests/analytics/test_cross_sell_rules.py`: cabeçalho trocado para "mesmo formato do mlxtend, por contagem direta de pares (DA-04 revisada)" (N-5). Testes novos de equivalência:
   - `test_direct_count_matches_fp_growth_on_every_cooccurring_pair[3,11,29]`: limites zerados (monkeypatch), todo par com 1 ou mais pedidos em comum. Mesmos pares e métricas da contagem direta e do `mine_association_rules(build_basket_matrix(...))` **sem `max_len`**, filtrado para regras 1 -> 1 (`atol=1e-12`). A massa tem cestas de 2 a 4 itens, então o FP-Growth também gera itemsets de 3 e 4 itens, que o filtro descarta.
   - `test_direct_count_matches_fp_growth_with_production_limits[3,11,29]`: limites reais de P-059.2/P-060. Mesmo conjunto de regras, mesmas Regras Úteis (pares e contagens inteiras exatos, métricas com `rtol=1e-12`) e mesma ordem P-061.1 por antecedente. A massa tem 30 SKUs em 6 famílias; 120 regras úteis por semente, com pares fora das famílias cortados.
   - `test_direct_count_keeps_boundary_rules_that_fp_growth_loses_to_float_error`: na massa do contrato, a única diferença admitida são as regras exatamente no limite inclusivo (A -> X, conf. 0,10; A -> F, lift 1,2), que o FP-Growth perde por erro binário. As demais são idênticas.
   - `test_direct_count_on_empty_base_returns_empty_rule_table`: cobre o ramo vazio (`cross_sell.py:162`).
3. Lint nos testes: `zip(..., strict=True)` (B905), quebra de linhas > 120 em `test_cross_sell_rules.py`, `test_recommendation_curation.py` e `fixtures/synthetic_data.py`, e `import pytest` não usado removido de `test_cross_sell_returns.py`.

## Auto-Healer (tentativas no teste novo)
1. `select_useful_rules(direct) == select_useful_rules(fp)` falhou por **ordem**: a tupla segue a ordem das linhas da tabela de entrada, e o contrato é a ordem do índice P-061.1.
2. A comparação por `set` falhou por **1 ULP**: o mlxtend calcula confiança e lift dividindo suportes; a contagem direta divide contagens (0.14893617021276595 vs ...598). A asserção passou a ser exata nos pares e contagens inteiras e `rtol=1e-12` nas métricas.
3. Com 12 SKUs populares, as sementes 3 e 11 não davam nenhuma Regra Útil, porque todos os itens eram triviais (suporte acima de 15 %). A massa passou a 30 SKUs em famílias. Resultado: verde.

Não houve falha de produção causada pela fase.

## Achados de lint em produção (para o `developer`; não bloqueiam)
- `src/modules/analytics/api/router.py:49` e `:50`: E501 (121 e 126 > 120).
- `src/modules/analytics/api/schemas.py:265`: E501 (123).
- `src/modules/analytics/domain/cross_sell_backtest.py:168`: E501 (123).
- `src/modules/analytics/domain/cross_sell_backtest.py:137` e `domain/cross_sell_customer.py:51`: B905 `zip()` sem `strict=`. Sugestão: `zip(..., strict=True)` se as sequências têm sempre o mesmo tamanho; esconder uma diferença de tamanho seria um bug silencioso.
- `src/api.py:25-26`: E402 nos 2 imports novos do analytics; o arquivo inteiro já segue esse padrão (imports depois do `load_dotenv`/logging). Preexistente: `src/api.py:93` F401 (`HTTPException` sem uso) e `:103`/`:108` F821 (`Response` não importado; dívida técnica já registrada no `STATE.md`).
- Regras `UP*`/`I001` (default do ruff 0.17) dão 185 achados de estilo (`typing.List` → `list`, ordem de imports). O projeto não adota ruff, então não foram tratados.

## Linhas sem cobertura (analytics)
`cross_sell.py:247, 303, 319`; `cross_sell_backtest.py:229` (resumo sem clientes avaliados); `cross_sell_customer.py:55`; `analytics_cache.py:123` (`_utc_now` real, sempre mockado) e `:181`; `analytics_service.py:52-53` (`reload_cache`: a rota é testada com o serviço mockado); `backtest/run_cross_sell_backtest.py` inteiro (CLI que lê o banco).

## Revisão dos testes do Orquestrador
- `test_recommendation_curation.py` (P-094): boa cobertura de variante, linha, faixa de prioridade, corte em 10, fornecedor vazio (N-1) e regra principal no modo cliente; 100 % de linhas e ramos de `recommendation_curation.py`. Faltam:
  (a) teste de API em que um antecedente tenha **11 ou mais regras úteis de linhas distintas**, provando `totalItems == 10`, `totalPages` coerente e `offset` sobre a lista curada (contrato 1.1.0). Hoje nenhum teste de rota exercita o corte;
  (b) consequente ausente do catálogo no `curate` (hoje só o antecedente ausente é testado);
  (c) curadoria aplicada no backtest (hit rate@5 sobre a lista curada); `test_cross_sell_backtest.py` não referencia P-094.
  Cosmético: o nome `test_curate_skips_items_whose_antecedent_left_the_catalog_check` é confuso; a importação `priority_tier, curate` está fora de ordem alfabética; há 3 linhas em branco antes da seção de priorização.
- `test_cross_sell_api.py::test_product_mode_of_customer_mass_lists_g_and_b`: correto para P-094.2 (G, do mesmo fornecedor que A, antes de B apesar do lift menor), mas só confere a ordem final. Sugestão: afirmar também `lift(B) > lift(G)` na resposta, para o teste falhar se a massa mudar e a ordem passar a sair do ranking por lift, e não do fornecedor.

## Pendências
1. Decidir o tratamento dos 7 testes legados que dependem do banco real (marcador `integration` + `pytest-timeout`), fora do escopo da fase.
2. `developer`: 5 achados de lint em `src/modules/analytics` (opcionais).
3. Testes faltantes (a), (b) e (c) da curadoria P-094.
4. Orçamento do bundle: 7 bytes de folga até o aviso de 500 kB. Qualquer import novo no bundle inicial dispara o aviso.
5. Arquivo solto `navbar.component.html` na raiz do repositório (untracked, 10/11 09:19), não criado pelo Tester: verificar a origem e remover (governança: nada na raiz).
6. Testes de `version` já esperam `1.1.0` (atualizados pelo Orquestrador) e passam.
