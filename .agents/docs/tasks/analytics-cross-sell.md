# Entidade / Feature: Analytics Comercial — F4 Recomendação de Cross-sell (+ fundação do módulo `analytics`)

| Campo | Valor |
| :--- | :--- |
| **Branch** | `feature/analytics-cross-sell` |
| **Plano mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` (§1, §2, §3) |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-cross-sell.md` (P-058 a P-071) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-cross-sell.md` (versão 1.0.0) |
| **ADR** | `.agents/docs/adr/ADR-002-modulo-analytics-cross-sell.md` (DA-01 a DA-12, DC-1 a DC-5) |
| **Design Plan** | `.agents/docs/design/plans/analytics-cross-sell.md` (a criar pelo Designer) |
| **Privacidade** | `.agents/docs/privacy/analytics-cross-sell.md` (LGPD-01 a LGPD-12) |
| **Glossário** | `.agents/docs/GLOSSARY.md`, seção 3 |
| **Status** | Etapa 2 — checklist técnico preenchido pelo Arquiteto; aguardando checkpoint |

**User Story (US-F4):** *Como vendedor/comprador da Fitoherb, quero saber quais produtos costumam ser comprados junto com um produto e o que oferecer a cada cliente, para aumentar o ticket médio com sugestões que têm estoque e dão margem.*

**Escopo:**
- Fundação do módulo `analytics` (estrutura `api/service/domain/repository`, repositório somente leitura, cache com lock e TTL de 6 h, `AnalyticsDomainException` com códigos `XSL-xxx`, envelope `data`/`meta`, paginação, `GET /analytics/health`, rota `/analytics` lazy no Angular com abas e item na navbar).
- Recomendação por produto (`GET /analytics/cross-sell/product/{sku}`).
- Recomendação por cliente (`GET /analytics/cross-sell/customer/{customerCode}`; variante POST no Apêndice A do contrato, conforme DC-1).
- Recarga manual (`POST /analytics/cache/reload`, conforme DC-2).
- Backtest de hit rate@5 (P-071).

**Fora do escopo:** envio automático de ofertas; regras com mais de um antecedente; alteração do filtro de devolução no código legado de `pricing`/`inventory` (dívida técnica); Fases 2 a 6; autocomplete de produto por descrição (DC-5).

---

## 1. Dúvidas Resolvidas (Especificação)

- **Dúvida:** Ordem das fases do módulo Analytics.
  - **Decisão:** F4, F5, F6, F1, F3, F2 (D5). Esta é a Fase 1 e contém a fundação.
- **Dúvida:** Como identificar um cliente (filiais, CNPJ raiz)?
  - **Decisão:** um cliente = um `Cod Cliente`, sem agrupamento (D3).
- **Dúvida:** Devoluções entram nas cestas?
  - **Decisão:** não. Cestas usam só `[Operação] = 'VENDA'`; devolução não é compra nem co-ocorrência (D4, plano §2.3).
- **Dúvida:** Parâmetros numéricos (confiança mínima, item trivial, dormência, janelas, meta do hit rate@5).
  - **Decisão:** propostos pelo Analista como Premissas A-1 a A-12 (seção 6 das regras), a confirmar no checkpoint da Etapa 2.
- **Dúvida (Arquiteto):** Como carregar `Pedido × SKU` com cliente e data sem estourar 2Gi?
  - **Proposta:** agregado único todo em `int32` (`DENSE_RANK` do pedido, dias desde 2000-01-01), `HAVING SUM(Qtd) > 0` no SQL e leitura em blocos de 50 mil. ~13 MB finais, pico de carga estimado em 150–250 MB, residente < 30 MB (ADR-002, DA-02/DA-03).
- **Dúvida (Arquiteto):** A-11, `Cod Cliente` no path.
  - **Proposta:** manter GET com path (alinhado ao Privacy Officer); variante POST especificada. Decisão final no checkpoint (DC-1).

---

## 2. Tarefas e Etapas de Desenvolvimento

> **Convenções do checklist.** `T-xx` = testes (Tester, escritos ANTES do código, em `tests/analytics/` e `*.spec.ts`); `B-xx` = backend; `F-xx` = frontend. `[PARALLEL]` marca o que pode rodar em paralelo entre as frentes Backend e Frontend, pois ambas dependem só do contrato 1.0.0. Cada `B-xx` só começa depois dos `T-xx` que ele faz passar.

### Tarefa 1: Fundação do módulo `analytics`

**Descritivo Detalhado:**
Criar a base comum do módulo reaproveitada pelas Fases 2 a 6: estrutura de pastas (plano §2.4), repositório somente leitura com o agregado `order_baskets` (`Pedido × Cod Produto`, com `Cod Cliente` e data do pedido, só VENDA) e a constante `RETURN_OPERATION_PATTERN`, cache com lock/TTL/`force_reload`, exceções de domínio com handler global, schemas base de envelope e paginação, rota de saúde e esqueleto do frontend (`/analytics` com abas e `analytics.service.ts` tipado).

**Critérios de Aceite:** (regras P-058.4, P-058.5, P-066 a P-070)
- [ ] CA-15 — Envelope e paginação
- [ ] CA-16 — Validação de paginação
- [ ] CA-17 — Códigos de erro
- [ ] CA-19 — Carga única sob concorrência
- [ ] CA-20 — Expiração do cache
- [ ] CA-21 — Health
- [ ] CA-22 — Privacidade

**Etapas de Execução (Checklist Técnico):**

*Testes (Tester, antes do código):*
- [ ] **T-01:** `tests/analytics/test_pagination.py` — `paginate()` puro: CA-15 (120 itens, `limit=50&offset=100` → 20 itens, `page=3`, `totalPages=3`), `offset ≥ totalItems` → vazio com totais (P-066.4), `totalPages = 0` sem itens.
- [ ] **T-02:** `tests/analytics/test_sales_repository.py` (cursor `pyodbc` mockado):
  - SQL passa em `is_readonly_query`, contém `[Operação] = 'VENDA'`, `HAVING SUM([Qtd Venda]) > 0`, `DENSE_RANK`, `DATEDIFF`, **não** contém `CONCAT`, `UF`, `Valor Venda`, `Cod Promocao`, `EAN`, `Tipo`, `SELECT *` (LGPD-01).
  - A data de corte vai como **bind parameter** (`execute(sql, cutoff)`), nunca interpolada (LGPD-02).
  - Leitura por `fetchmany` (nunca `fetchall`), resultado com colunas exatas `order_idx, sku, customer_code, order_day` em `int32`.
  - `RETURN_OPERATION_PATTERN == 'DEVOLU%'` existe (P-058.5).
  - `pyodbc.Error` vira `AnalyticsDataSourceError` (`ANL-001`) e o log não contém a mensagem do driver.
  - Query de catálogo seleciona exatamente `Codigo, Descricao, Fornecedor, Estoque, Pc.Ultimo Custo, Pc.Venda` com `[Pc.Venda] > 0`.
- [ ] **T-03:** `tests/analytics/test_analytics_cache.py` — `estadoCache` derivado corretamente (`FRIO` sem snapshot, `CARREGANDO` durante a carga, `QUENTE` dentro do TTL, `EXPIRADO` após o TTL), `duracaoUltimaCargaMs` preenchida, flag de carga limpa mesmo quando a carga falha; CA-19 (10 threads com cache vazio → loader chamado 1 vez), CA-20 (relógio `_utc_now` substituído: 5h59 não recarrega, 6h recarrega), `force_reload` respeita o lock, falha na carga mantém o snapshot anterior e propaga (P-068.4), reload antes de 15 min → `ReloadTooSoonError` sem chamar o loader, base insuficiente vira snapshot com `is_base_sufficient=False` (não recarrega a cada chamada).
- [ ] **T-04:** `tests/analytics/test_analytics_api_foundation.py` (`TestClient`, serviço mockado) — `GET /api/v1/analytics/health` com cache vazio responde 200 no envelope e **não chama** o loader (CA-21); `XSL-001..004`, `ANL-001`, `ANL-002` com HTTP e corpo do contrato §4, sem stacktrace nem valor recebido (CA-17, LGPD-05); `limit=0`, `limit=201`, `offset=-1`, `limit=1.5`, `sku=abc`, `customerCode=-5`, `customerCode="1 OR 1=1"` → 400 `XSL-004` com `fields` (CA-16, C-04, C-13); **regressão**: payload inválido em `/api/v1/inventory/predict` continua 422 no formato padrão do FastAPI; com `ENVIRONMENT=production` sem credencial a rota por cliente responde 401 (LGPD-10).
- [ ] **T-05:** `tests/analytics/test_analytics_privacy.py` — CA-22: `caplog` na carga e nas duas rotas com massa sintética; nenhum registro contém o `customerCode` de teste, SKUs recomendados, DataFrame ou payload; allowlist exata de chaves das respostas (LGPD-03); modo produto sem nenhuma chave de cliente.

*Backend:*
- [x] **B-01:** Esqueleto do pacote `src/modules/analytics/` conforme ADR-002 DA-01 (`api/`, `service/`, `domain/`, `repository/`, `backtest/`, todos com `__init__.py` e docstring de topo).
  - *Descritivo:* sem lógica; só a estrutura e as docstrings que citam as regras de cada arquivo.
- [x] **B-02:** `domain/exceptions.py` — `AnalyticsDomainException(code, message, fields=())` e `ProductNotFoundError` (`XSL-001`), `CustomerWithoutHistoryError` (`XSL-002`), `InsufficientBaseError` (`XSL-003`), `InvalidParametersError` (`XSL-004`). Mensagens fixas de P-067, sem valor recebido. Sem HTTP.
- [x] **B-03:** `domain/pagination.py` — `PageRequest(limit, offset)` (`frozen dataclass`, constantes `DEFAULT_PAGE_LIMIT=50`, `MAX_PAGE_LIMIT=200`), `PageResult(items, total_items, page, total_pages)`, `paginate(items, page_request)`. Faz T-01 passar.
- [x] **B-04:** `api/schemas.py` (base) — `CamelModel` (`alias_generator=to_camel`, `populate_by_name=True`), `AnalyticsMeta`, `PagedMeta`, `CustomerPagedMeta`, `ErrorDetail`, `AnalyticsErrorResponse`, `AnalyticsHealthData/Response`, constante `ANALYTICS_CONTRACT_VERSION = "1.0.0"`. `Field(description=...)` em PT-BR.
- [x] **B-05:** `repository/sales_repository.py` + `repository/errors.py` — query `order_baskets` e de catálogo exatamente como ADR-002 DA-02; `SALE_OPERATION`, `RETURN_OPERATION_PATTERN`, `ORDER_DAY_EPOCH`, `FETCH_CHUNK_SIZE=50_000`; `_execute_readonly(sql, params)` com `is_readonly_query`; conexão via `get_db_connection_string` de `src/core/database.py` (`timeout=30`, fechada em `finally`); tradução de `pyodbc.Error`/`ConnectionError`/`ValueError` de configuração em `AnalyticsDataSourceError` logando só o tipo. Faz T-02 passar.
  - *Pré-requisito (DC-4):* rodar uma vez, fora do código versionado, `SELECT COUNT(*) FROM (SELECT [Pedido] FROM Externo01.Vendas WHERE [Operação] = 'VENDA' GROUP BY [Pedido] HAVING COUNT(DISTINCT [Cod Cliente]) > 1) x` e registrar o resultado no `STATE`. Se > 0, avisar o Arquiteto antes de seguir.
- [x] **B-06:** `service/analytics_cache.py` — `AnalyticsSnapshot` (`frozen dataclass`), `_SNAPSHOT`, `_LOCK = threading.Lock()`, `_utc_now()`, flag `_is_loading` (definida e limpa dentro do lock em `try/finally`) e `load_duration_ms` para o `estadoCache` do health, `get_snapshot(force_reload=False)` com double-checked locking, TTL `CACHE_TTL_HOURS`, `MIN_RELOAD_INTERVAL_MINUTES = 15` (`ReloadTooSoonError`, `ANL-002`), troca atômica só após sucesso, `peek_snapshot()` sem lock para o health. Log só com contagens e duração. Faz T-03 passar.
- [x] **B-07:** `api/error_handlers.py` — `register_analytics_error_handlers(app)`: mapa `{XSL-001: 404, XSL-002: 404, XSL-003: 422, XSL-004: 400, ANL-001: 503, ANL-002: 429}`; handler de `RequestValidationError` escopado ao prefixo `/api/v1/analytics` (400 `XSL-004` com nomes dos campos) e delegação ao handler padrão do FastAPI para os demais paths.
- [x] **B-08:** `api/router.py` (fundação) — `analytics_router = APIRouter(prefix="/analytics", tags=["Analytics Comercial"])`, `GET /health` e `POST /cache/reload`; rotas só recebem, chamam `analytics_service` e devolvem. Registrar em `src/api.py` (`app.include_router(analytics_router, prefix="/api/v1")` + `register_analytics_error_handlers(app)`), sem pré-aquecimento no `lifespan`. Faz T-04 (parte de fundação) e T-05 (parte de logs) passarem.

*Frontend `[PARALLEL]` com B-01 a B-08:*
- [x] **F-01:** `features/analytics/models/analytics.model.ts` e `cross-sell.model.ts` — tipos do contrato §5, sem `any`.
- [x] **F-02:** `features/analytics/services/analytics.service.ts` — `getHealth()`, `getProductCrossSell(sku, page)`, `getCustomerCrossSell(customerCode, page)` com `HttpParams` (`limit`, `offset`); sem `console.log`, sem storage.
- [x] **F-03:** `features/analytics/utils/analytics-error.ts` — `toAnalyticsApiError(err: unknown)` (type guard sobre `HttpErrorResponse`) e `ANALYTICS_ERROR_MESSAGES: Record<AnalyticsErrorCode, string>`; fallback genérico para 500/0.
- [x] **F-04:** Rota lazy — `app.routes.ts` ganha `{ path: 'analytics', loadChildren: () => import('./features/analytics/analytics.routes').then(m => m.ANALYTICS_ROUTES) }` antes do `**`; `analytics.routes.ts` com `AnalyticsShellComponent` e filho padrão `cross-sell`.
- [x] **F-05:** `pages/analytics-shell/` — abas por `routerLink` (só "Cross-sell" nesta fase, estrutura pronta para novas abas), conforme Design Plan.
- [x] **F-06:** Navbar — item "Analytics Comercial" (`routerLink="/analytics"`, `routerLinkActive`, ícone e `title` conforme Design Plan), também no menu mobile.

**Audit (Testes e Validação):** *(Tester, Etapa 3)*
- [ ] `pytest tests/analytics/test_pagination.py test_sales_repository.py test_analytics_cache.py test_analytics_api_foundation.py test_analytics_privacy.py` verde (T-01..T-05).
- [ ] CA-15/CA-16: `limit=50&offset=100` sobre 120 itens; `limit=0|201|1.5`, `offset=-1`, `sku=abc|-5|0|2147483648`, `customerCode=-5|"1 OR 1=1"` -> 400 `XSL-004` com `fields`, sem eco do valor.
- [ ] CA-17/LGPD-05: corpo `{error:{code,message,fields}, meta:{timestamp,version}}` para XSL-001..004, ANL-001 (503), ANL-002 (429); 500 genérico sem stacktrace.
- [ ] CA-19/CA-20: 10 threads -> 1 carga; TTL 5h59 não recarrega, 6h recarrega; reload < 15 min -> 429 sem tocar no banco; falha mantém snapshot anterior.
- [ ] CA-21: `/health` com cache frio -> 200, `estadoCache=FRIO`, sem chamar `_build_snapshot`/repositório.
- [ ] LGPD-01/02: SQL capturado do cursor mockado: só colunas permitidas, corte como bind parameter, `fetchmany` (nunca `fetchall`), `int32`.
- [ ] CA-22/LGPD-03/04: `caplog` limpo (sem `customerCode`, SKUs recomendados, DataFrame); allowlist exata de chaves.
- [ ] Regressão: `POST /api/v1/inventory/predict` inválido continua 422 FastAPI; produção sem credencial -> 401 na rota de cliente.
- [ ] Frontend: `analytics.service.spec.ts`, `analytics-error.spec.ts`, `analytics.routes.spec.ts`, `navbar.component.spec.ts` verdes (`npx ng test --watch=false --browsers=ChromeHeadless`).
- [ ] Manual: `/analytics` abre em `/analytics/cross-sell`; item "Análises de Vendas" ativo na navbar (desktop e mobile).

---

### Tarefa 2: Motor de cross-sell (domínio)

**Descritivo Detalhado:**
Formar Cestas Válidas, minerar Regras de Associação 1 → 1 reaproveitando `basket_mining`, aplicar os critérios de Regra Útil e Par Trivial, gerar a Recomendação por Produto e a Recomendação por Cliente (perfil, Produto Dormente, viabilidade, Pontuação de Cross-sell) e a explicação em linguagem simples.

**Critérios de Aceite:** (regras P-058 a P-065)
- [ ] CA-01 — Associação plantada recuperada
- [ ] CA-02 — Devolução não cria co-ocorrência
- [ ] CA-03 — Cesta de 1 item descartada
- [ ] CA-04 — Limites de Regra Útil
- [ ] CA-05 — Par Trivial excluído
- [ ] CA-06 — Mínimo de pedidos em comum
- [ ] CA-07 — Ordenação por produto
- [ ] CA-08 — Candidato só se não compra ou dormente
- [ ] CA-09 — Fronteira de dormência
- [ ] CA-10 — Sem estoque não é sugerido ao cliente
- [ ] CA-11 — Margem não positiva excluída
- [ ] CA-12 — Custo com fallback
- [ ] CA-13 — Pontuação e ordenação por cliente
- [ ] CA-14 — Explicação em linguagem simples
- [ ] CA-18 — Lista vazia não é erro

**Etapas de Execução (Checklist Técnico):**

*Testes (Tester, antes do código; domínio só com arrays/DataFrames sintéticos, sem banco):*
- [ ] **T-06:** `tests/test_basket_mining.py` (acréscimo) — `mine_association_rules(..., max_len=2)` só gera regras 1 → 1; sem `max_len` o resultado é idêntico ao atual (regressão do `pricing`). Os testes existentes não mudam.
- [ ] **T-07:** `tests/analytics/test_cross_sell_rules.py` — CA-01 (associação plantada com confiança 0,34 e lift exato), CA-03, CA-04 (R1..R5 → só R1 e R5, limites inclusivos), CA-05 (C em 30% nunca é consequente, pode ser antecedente), CA-06 (9 pedidos em comum descartado, 10 aceito), P-059.6 (A → A inexistente), `pedidosEmComum`/`pedidosComAntecedente` inteiros exatos, `XSL-003` quando < 1.000 cestas ou zero regras úteis.
- [ ] **T-08:** `tests/analytics/test_cross_sell_returns.py` — CA-02/C-12 no nível do repositório + domínio: o SQL do agregado só aceita `VENDA` (asserção sobre a query) e, na massa sintética, um par só com devolução não aparece no agregado mockado e não gera regra.
- [ ] **T-09:** `tests/analytics/test_cross_sell_product.py` — CA-07 (ordenação lift ↓, confiança ↓, `pedidosEmComum` ↓, código ↑), P-061.3 (consequente fora do catálogo excluído), CA-10 parte produto (`semEstoque=true`), C-10 parte produto (`margemNaoPositiva=true`), C-02 (lista vazia), C-03 (`XSL-001` fora do catálogo e sem cesta válida).
- [ ] **T-10:** `tests/analytics/test_cross_sell_customer.py` — CA-08, CA-09 (90 dias não, 91 sim), CA-10, CA-11, CA-12 (`25,00` e custo 0 → margem `10,00`, `custoEstimado=true`), CA-13 (G 9,00 antes de B 7,23; G uma vez com `qtdAntecedentesRelacionados=2`), P-062.1 (pedido de 1 SKU conta para o perfil), P-062.6, C-06, C-07 (`SEM_COMPRAS_RECENTES`), C-08 (`XSL-002`), fronteira de 365 dias do perfil, filtros antes da paginação (P-063.5).
- [ ] **T-11:** `tests/analytics/test_cross_sell_explanation.py` — frases separadas nas chaves `frequencia`, `intensidade`, `evidencia`, `motivo` (`null` no modo produto); CA-14 (frases exatas de R1: "Em 34% ...", "4,3 vezes mais", "Baseado em 170 pedidos."), arredondamento meio para cima (0,345 → 35%; lift 1,25 → "1,3"), milhar com ponto ("1.234"), frases de motivo `NUNCA_COMPROU`/`DORMENTE`, ausência das palavras "lift", "suporte", "confiança" no texto.

*Backend (cada item faz os testes indicados passarem):*
- [x] **B-09:** `src/modules/pricing/domain/basket_mining.py` — acrescentar `*, max_len: Optional[int] = None` em `mine_association_rules` e repassar ao `fpgrowth`. Única mudança fora do módulo (DC-3). Faz T-06 passar.
- [x] **B-10:** `domain/cross_sell.py` (constantes + cestas + mineração) — tabela de constantes das regras no topo, inclusive `SALE_OPERATION` (`ORDER_DAY_EPOCH` e `RETURN_OPERATION_PATTERN` ficam no repositório); `UsefulRule` (`frozen dataclass`); `build_valid_baskets(order_baskets)` (reusa `filter_orphan_baskets` com coluna `Qtd Venda` sintética `int8`); `mine_one_to_one_rules(valid_baskets)` (reusa `build_basket_matrix` + `mine_association_rules(max_len=2)`); `select_useful_rules(rules, total_baskets)` (P-059.3, P-059.6, P-060); `find_trivial_skus`; `index_rules_by_antecedent` (ordem P-061.1); `assert_base_is_sufficient`. Faz T-07 e T-08 passarem.
- [x] **B-11:** `domain/cross_sell.py` (modo produto) — `CatalogEntry` (`frozen dataclass`: código, descrição, fornecedor, estoque, preço, custo unitário, `is_cost_estimated`), `build_catalog_lookup(catalog_df)` com fallback de 60% (P-063.3), `calculate_unit_margin`, `recommend_for_product(snapshot_view, sku)` retornando lista ordenada de `ProductRecommendation`. Faz T-09 passar.
- [x] **B-12:** `domain/cross_sell_customer.py` — `build_customer_history(order_baskets)` (último `order_day` por cliente × SKU, `int32`), `build_customer_profile(history, reference_day)`, `classify_candidate` (`NUNCA_COMPROU`/`DORMENTE`), `is_commercially_viable` (P-063), `calculate_cross_sell_score`, `aggregate_best_rule_per_candidate` (máximo, contagem de antecedentes, P-064.1), `recommend_for_customer(...)` → `CustomerRecommendationResult(items, empty_reason)`; parâmetro `apply_stock_filter: bool = True` (backtest usa `False`). Funções ≤ ~30 linhas, ≤ 3 parâmetros (DTO `CustomerRecommendationQuery` se precisar de mais). Faz T-10 passar.
- [x] **B-13:** `domain/cross_sell_explanation.py` — `build_product_explanation(rule, antecedent_desc, consequent_desc)` e `build_customer_explanation(...)`; `Decimal.quantize(ROUND_HALF_UP)`; formatação pt-BR sem depender de `locale` do sistema. Faz T-11 passar.

**Audit (Testes e Validação):** *(Tester, Etapa 3)*
- [ ] `pytest tests/test_basket_mining.py` verde, inclusive a saída congelada do pricing sem `max_len` (T-06) e `max_len` somente por nome.
- [ ] `pytest tests/analytics/test_cross_sell_rules.py test_cross_sell_returns.py test_cross_sell_product.py test_cross_sell_customer.py test_cross_sell_explanation.py` verde (T-07..T-11).
- [ ] Limites inclusivos com aritmética real (CA-04): A -> F (lift 1,2) e A -> X (confiança 50/500 = 0,1, que o mlxtend calcula como 0,09999999999999999) sobrevivem à mineração.
- [ ] CA-02: devolução com quantidade positiva não cria A -> B; controle prova que as mesmas linhas como VENDA criariam a regra.
- [ ] CA-08..CA-13, C-06..C-08, fronteiras 90/91 dias (dormência) e 365/366 dias (perfil).
- [ ] CA-14: frases exatas, meio para cima (0,345 -> 35%; 1,15 -> "1,2"; 1,25 -> "1,3"), milhar com ponto, sem `locale`, sem "lift/suporte/confiança/pontuação".

---

### Tarefa 3: API e aba "Cross-sell" no frontend

**Descritivo Detalhado:**
Expor os dois modos nas rotas do contrato e construir a aba "Cross-sell" com busca por produto (explicação "em X% dos pedidos com A também há B", sinalização de sem estoque/margem) e busca por cliente (lista priorizada com motivo), com estados de carregamento, vazio e erro, conforme o Design Plan.

**Critérios de Aceite:** (regras P-061 a P-067)
- [ ] Os CA da Tarefa 2 são observáveis pela API no envelope `data`/`meta`.
- [ ] Tela exibe as frases de P-065 e os estados carregando, vazio (inclusive `SEM_COMPRAS_RECENTES`) e erro (`XSL-001` a `XSL-004`).

**Etapas de Execução (Checklist Técnico):**

*Testes (Tester, antes do código):*
- [ ] **T-12:** `tests/analytics/test_cross_sell_api.py` (`TestClient`, snapshot sintético injetado no cache) — exemplos do contrato §3.3 e §3.4 (campos, tipos, casas decimais, ordem), `data.produto` presente também com lista vazia, `pedidosEmComum` no modo cliente, `meta.parametros` igual às constantes do domínio, `meta` paginado completo, `motivoVazio` sempre presente na rota por cliente, ordem de avaliação 400 → 503 → 422 → 404 → 200, ausência de `customerCode` na resposta.
- [ ] **T-13:** `frontend/.../analytics.service.spec.ts` (`HttpTestingController`) — URLs, `HttpParams` de paginação, tipos de resposta; `analytics-error.spec.ts` — type guard aceita só corpos do contrato §4 e cai no genérico em 500/0.
- [ ] **T-14:** `frontend/.../cross-sell.store.spec.ts` — transições `idle → loading → success | empty | error`; vazio com `SEM_COMPRAS_RECENTES` distinto do vazio comum; troca de página reaproveita o último termo; nada gravado em `localStorage`/`sessionStorage` (LGPD-09).
- [ ] **T-15:** Specs de componente (serviço/store mockados) — painel de produto e de cliente: skeleton de carregamento, vazio, erro por código (`XSL-001`, `XSL-002`, `XSL-003`, `XSL-004`, genérico), sinalização `semEstoque`/`margemNaoPositiva`, motivo `DORMENTE` com dias, paginação; rota `/analytics` carrega lazy e redireciona para `cross-sell`; navbar exibe o item.

*Backend:*
- [x] **B-14:** `api/schemas.py` (cross-sell) e `api/mappers.py` — `ProductRef`, `Explanation`, `ProductRecommendationItem`, `ProductCrossSellData/Response`, `CustomerRecommendationItem`, `CustomerCrossSellData/Response`; `Literal` para `motivo`/`motivoVazio`; arredondamento de exibição só no mapper (§2.4 do contrato). `json_schema_extra` com os exemplos do contrato.
- [x] **B-15:** `service/analytics_service.py` + rotas de cross-sell em `api/router.py` — `get_product_cross_sell(sku, page_request)` e `get_customer_cross_sell(customer_code, page_request)`: obtém snapshot → valida base (`XSL-003`) → domínio → `paginate` → mapper. Rotas com `Path(gt=0, le=2_147_483_647)` e `Query(ge/le)`; `responses={400,404,422,503}` documentados. Nenhum `try/except` nas rotas. Faz T-12 passar.
  - *Se DC-1 = C:* trocar a rota por cliente pela variante POST do Apêndice A (`CustomerCrossSellQuery`, `extra="forbid"`).

*Frontend `[PARALLEL]` com B-09 a B-15 (usa o contrato e o serviço mockado; depende do Design Plan):*
- [x] **F-07:** `services/cross-sell.store.ts` — `signal`s por modo (`status`, `response`, `error`, `pageRequest`), métodos `searchProduct(sku)`, `searchCustomer(customerCode)`, `goToPage(n)`; sem lógica de negócio além de orquestrar chamadas; `customerCode` só em memória.
- [x] **F-08:** `pages/cross-sell-page/` — página que compõe os dois painéis (modo produto e modo cliente) conforme Design Plan; estado do cliente fora da URL da SPA.
- [x] **F-09:** `components/product-cross-sell-panel/` + `components/product-recommendations-table/` — campo de SKU (inteiro positivo validado na tela), cabeçalho do produto antecedente, tabela com frases de `explicacao`, detalhes técnicos sob demanda (`lift`, `confianca`, `suporte`), selos `semEstoque`/`margemNaoPositiva`.
- [x] **F-10:** `components/customer-cross-sell-panel/` + `components/customer-recommendations-list/` — campo de `customerCode`, lista priorizada com `pontuacao`, `margemUnitaria`, `custoEstimado`, motivo e frases.
- [x] **F-11a:** Aviso de cache frio: a página consulta `getHealth()` ao abrir e, com `estadoCache` ≠ `QUENTE`, avisa que a primeira consulta pode demorar (usa `duracaoUltimaCargaMs`); textos dos vazios interpolam `meta.parametros` (`dormantDays`, `customerProfileDays`).
- [x] **F-11:** Componentes de estado compartilhados do módulo — skeleton, vazio (texto específico para `SEM_COMPRAS_RECENTES`), erro por código (F-03) e paginador `limit/offset`, conforme os 8 estados do Design Plan.

*Opcional — só se o checkpoint aprovar DC-5 (busca de produto por código ou descrição, contrato §3.6):*
- [ ] **T-17:** `tests/analytics/test_product_search.py` — normalização sem acento/maiúsculas ("chá" encontra "CHA"), prioridade código exato → prefixo de código → descrição que começa com `q` → descrição que contém `q`, limite de 20, `q` inválido → 400 `XSL-004` com `fields: ["q"]`, a busca **não** chama o loader das cestas.
- [ ] **T-18:** Spec do combobox (debounce de 300 ms, mínimo de 2 caracteres, navegação por teclado, seleção preenche o SKU).
- [x] **B-19:** `domain/product_search.py` (puro) + `get_catalog()` com cache próprio em `service/analytics_cache.py` (DA-06).
- [x] **B-20:** Rota `GET /products/search` e schemas `ProductSearchItem`/`ProductSearchResponse`.
- [x] **F-12:** `CodeSearchFormComponent` do modo produto vira combobox acessível que usa `searchProducts(q, page)` (Design Plan, D-7).

**Audit (Testes e Validação):** *(Tester, Etapa 3)*
- [ ] `pytest tests/analytics/test_cross_sell_api.py` verde: exemplos §3.3 e §3.4 idênticos (inclusive `pontuacao` 7,23 e "4,3 vezes"), `data.produto` com lista vazia, `motivoVazio` sempre presente no modo cliente, `meta.parametros` = constantes, ordem 400 -> 503 -> 422 -> 404.
- [ ] `pytest tests/analytics/test_product_search.py` verde (T-17): "chá" = "CHA", prioridade código exato -> prefixo / começa com -> contém, limite 20, `q` inválido -> 400 `fields:["q"]`, busca não carrega as cestas e reaproveita o catálogo em cache.
- [ ] Frontend verde: `cross-sell.store.spec.ts` (T-14), painéis de produto/cliente (T-15), `code-search-form.component.spec.ts` (T-18: debounce 300 ms, mínimo 2 caracteres, setas/Enter/Escape).
- [ ] Manual (smoke com backend real): SKU com regras, SKU sem regras, SKU inexistente, cliente com candidatos, cliente inativo (`SEM_COMPRAS_RECENTES`), cliente inexistente; skeleton na primeira consulta com cache frio; `customerCode` fora da URL e do storage (DevTools > Application).

---

### Tarefa 4: Backtest de hit rate@5

**Descritivo Detalhado:**
Implementar o backtest temporal de P-071 (N ∈ {2026-08, 2026-09, 2026-10}, treino até N−1, linha de base por popularidade) e anexar o resultado ao PR.

**Critérios de Aceite:** (regra P-071)
- [ ] CA-23 — Backtest sem vazamento
- [ ] CA-24 — hit rate@5 medido e reportado

**Etapas de Execução (Checklist Técnico):**

*Testes (Tester, antes do código):*
- [ ] **T-16:** `tests/analytics/test_cross_sell_backtest.py` — CA-23 (par inédito A-B só no mês N não vira regra no treino de N); CA-24 em massa sintética com resposta conhecida (hit rate@5 exato do modelo e da popularidade); P-071.3 (clientes excluídos contados por motivo: sem perfil, sem compra em N, sem recomendação); P-071.5 (filtro de estoque desligado; margem aplicada); popularidade exclui SKUs comprados pelo cliente nos últimos 90 dias e respeita catálogo/margem; saída sem nenhum `customerCode` (LGPD-11).

*Backend:*
- [x] **B-16:** `domain/cross_sell_backtest.py` — `BacktestMonthResult` (hit rate modelo, hit rate popularidade, avaliados, excluídos por motivo), `split_train_and_eval(order_baskets, month)`, `recommend_by_popularity(...)`, `evaluate_month(...)` reaproveitando B-10 a B-12 com `apply_stock_filter=False`, `summarize(results)` com a média dos meses. Faz T-16 passar.
- [x] **B-17:** `backtest/run_cross_sell_backtest.py` — CLI (`python -m src.modules.analytics.backtest.run_cross_sell_backtest --months 2026-08 2026-09 2026-10`): uma carga do repositório com corte exclusivo `2026-11-01`, catálogo atual, imprime tabela markdown só com agregados e a nota da limitação de estoque (P-071.5); mede e imprime o pico de memória da carga (`tracemalloc` e, no Linux, `resource.getrusage` para o RSS máximo; sem adicionar dependência) e o tempo.
- [ ] **B-18:** Executar o backtest contra a base real, colar o resultado no PR (Etapa 5) e registrar no `STATE` se a meta A-12 (modelo ≥ popularidade na média) foi atingida.

**Audit (Testes e Validação):** *(Tester, Etapa 3)*
- [ ] `pytest tests/analytics/test_cross_sell_backtest.py` verde (T-16): sem vazamento do mês N (CA-23), hit rate@5 exato na massa conhecida (modelo 0,50; popularidade 0,75; 4 avaliados; excluídos 2/1/1), média por `summarize`, mês sem avaliados sem divisão por zero, resultado sem `customerCode` (LGPD-11).
- [ ] Execução real (B-18): tabela markdown só com agregados e nota de estoque (P-071.5) colada no PR; pico de memória e tempo medidos.

---

## 3. Ordem de execução e paralelismo

```
Checkpoint Etapa 2 (DC-1..DC-5, A-1..A-13)
        │
        ├── Frente Backend ──────────────────────────────┐   [PARALLEL]
        │   T-01..T-05 → B-01..B-08 (fundação)            │
        │   T-06..T-11 → B-09..B-13 (domínio)             │
        │   T-12      → B-14..B-15 (API cross-sell)       │
        │   T-16      → B-16..B-18 (backtest)             │
        │                                                 │
        └── Frente Frontend ─────────────────────────────┘   [PARALLEL]
            T-13 → F-01..F-06 (fundação Angular; não depende do Design Plan, exceto F-05/F-06 visuais)
            T-14, T-15 → F-07..F-11 (aba Cross-sell; depende do Design Plan)
```

- Dentro do backend, B-10..B-13 (domínio) e B-05..B-07 (repositório, cache, handlers) não compartilham arquivos e podem ser feitos por desenvolvedores diferentes `[PARALLEL]`, desde que B-01 e B-02 estejam prontos.
- B-16/B-17 dependem de B-10..B-12 e de B-05.
- Integração final: smoke test com o backend real (`ng serve` + `uvicorn`) antes do Quality Gate.

## 4. Commits atômicos sugeridos (Conventional Commits, em ordem)

1. `docs(analytics): adiciona ADR-002, contrato 1.0.0 e checklist do cross-sell`
2. `test(analytics): adiciona testes de paginacao, repositorio, cache e fundacao da API [P-066..P-070]` (T-01..T-05)
3. `feat(analytics): cria estrutura do modulo, excecoes de dominio e paginacao [P-066, P-067]` (B-01..B-03)
4. `feat(analytics): adiciona repositorio somente leitura com agregado order_baskets [P-058]` (B-05)
5. `feat(analytics): adiciona cache por snapshot com lock, TTL e recarga manual [P-068]` (B-06)
6. `feat(analytics): registra router, health e handlers globais de erro XSL/ANL [P-067, P-069]` (B-04, B-07, B-08)
7. `test(analytics): adiciona testes do motor de cross-sell e da explicacao [P-058..P-065]` (T-06..T-11)
8. `feat(pricing): adiciona max_len opcional em mine_association_rules` (B-09)
9. `feat(analytics): minera regras uteis 1 para 1 e itens triviais [P-059, P-060]` (B-10)
10. `feat(analytics): recomendacao de cross-sell por produto [P-061]` (B-11)
11. `feat(analytics): recomendacao de cross-sell por cliente com pontuacao [P-062..P-064]` (B-12)
12. `feat(analytics): explicacao em linguagem simples das recomendacoes [P-065]` (B-13)
13. `test(analytics): adiciona testes de contrato das rotas de cross-sell` (T-12)
14. `feat(analytics): expoe rotas de cross-sell por produto e por cliente` (B-14, B-15)
15. `test(analytics): adiciona testes do backtest de hit rate@5 [P-071]` (T-16)
16. `feat(analytics): adiciona backtest temporal de hit rate@5 [P-071]` (B-16, B-17)
17. `test(frontend): adiciona specs do servico, store e erros de analytics` (T-13, T-14)
18. `feat(frontend): adiciona rota lazy /analytics, abas, navbar e analytics.service` (F-01..F-06)
19. `test(frontend): adiciona specs dos componentes da aba cross-sell` (T-15)
20. `feat(frontend): adiciona aba cross-sell com busca por produto e por cliente` (F-07..F-11)
21. *(se DC-5)* `test(analytics): adiciona testes da busca de produtos` (T-17, T-18) → `feat(analytics): adiciona busca de produtos por codigo ou descricao` (B-19, B-20) → `feat(frontend): adiciona combobox de busca de produto` (F-12)

Commits de frentes paralelas podem se intercalar, desde que cada `test` preceda o `feat` correspondente. Nenhum commit é breaking (rotas novas; `mine_association_rules` muda de forma compatível).

## 5. Dependências novas

**Nenhuma.** Backend usa `pandas`, `numpy`, `scipy`, `mlxtend`, `pydantic`, `fastapi`, `pyodbc` já presentes em `requirements.txt`; medição de memória usa `tracemalloc`/`resource` da biblioteca padrão. Frontend usa apenas Angular 18 e RxJS já instalados.
