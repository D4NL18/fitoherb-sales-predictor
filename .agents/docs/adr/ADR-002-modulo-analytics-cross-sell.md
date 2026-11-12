# ADR-002: Módulo `analytics` (fundação) e motor de Cross-sell com agregado enxuto, cache por snapshot e erros com código interno

> **Status:** Proposto (aguarda checkpoint da Etapa 2)
> **Data:** 2026-11-05
> **Autor:** Arquiteto (`architect.md`)
> **Localização Mandatória:** `.agents/docs/adr/ADR-002-modulo-analytics-cross-sell.md`

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | Fase 1 do Analytics Comercial (F4 Cross-sell + fundação) — `feature/analytics-cross-sell` |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-cross-sell.md` (P-058 a P-071, CA-01 a CA-24, A-1 a A-12) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-cross-sell.md` (versão 1.0.0) |
| **Checklist técnico** | `.agents/docs/tasks/analytics-cross-sell.md` (T-xx, B-xx, F-xx) |
| **Plano mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` §2 e §3 |
| **Parecer de privacidade** | `.agents/docs/privacy/analytics-cross-sell.md` (LGPD-01 a LGPD-12), em paralelo |

---

## 1. Contexto do Problema

1. **Módulo novo, reaproveitado por 6 fases.** A Fase 1 cria a fundação de `src/modules/analytics/` (repositório somente leitura, cache, exceções, envelope, paginação, health, aba no Angular). Decisões aqui viram padrão para F5, F6, F1, F3 e F2.
2. **Memória no Cloud Run (2Gi).** Os commits #5 e #6 corrigiram OOM causados por vendas brutas no Python. O `pricing_service` ainda mantém `clean_sales` (linhas por item, ~825 mil) no cache do processo; o módulo novo divide o mesmo processo e não pode somar outra cópia bruta.
3. **SQL Server legado.** Não aceita `CONCAT` (indica versão anterior a 2012); o acento de `[Operação]` chega corrompido no ODBC (`LIKE 'DEVOLU%'` para devolução; `= 'VENDA'` funciona). `DENSE_RANK() OVER` e `DATEDIFF` existem desde 2005.
4. **Reuso obrigatório (P-059).** `build_basket_matrix` e `mine_association_rules` de `src/modules/pricing/domain/basket_mining.py` (FP-Growth sobre matriz esparsa).
5. **Erros.** Hoje não há handler global: `pricing`/`inventory` devolvem `HTTPException(500, str(e))` e o 422 padrão do FastAPI. As regras exigem `XSL-NNN`, HTTP semântico, 400 para validação (P-066.2/P-067) e nenhum stacktrace, sem mudar o contrato dos módulos existentes.
6. **Privacidade.** `Cod Cliente` é dado pessoal indireto (pior caso). Premissa A-11: o código no path aparece nos logs de acesso.

---

## 2. Decisão Arquitetural

### DA-01 — Estrutura do módulo (Clean Architecture, mesmo padrão de `pricing`/`inventory`)

```
src/modules/analytics/
├── __init__.py
├── api/
│   ├── router.py            # analytics_router (prefix="/analytics"): recebe, chama service, devolve
│   ├── schemas.py           # AnalyticsMeta, PagedMeta, ErrorBody, schemas de cross-sell (camelCase por alias)
│   ├── mappers.py           # objetos de domínio -> schemas de resposta (sem regra)
│   └── error_handlers.py    # register_analytics_error_handlers(app): mapa código -> HTTP
├── service/
│   ├── analytics_cache.py   # AnalyticsSnapshot + lock de voo único + TTL + force_reload + troca atômica
│   └── analytics_service.py # orquestra cache + domínio (casos de uso)
├── domain/
│   ├── exceptions.py        # AnalyticsDomainException e subclasses XSL-001..004 (sem HTTP)
│   ├── pagination.py        # PageRequest, PageResult, paginate() (P-066)
│   ├── cross_sell.py        # constantes P-058..P-071 + cestas, mineração 1->1, Regra Útil, Item Trivial, modo produto
│   ├── cross_sell_customer.py     # perfil, Produto Dormente, candidatos, viabilidade, pontuação (P-062..P-064)
│   ├── cross_sell_explanation.py  # frases de P-065 (texto montado no domínio)
│   └── cross_sell_backtest.py     # hit rate@5, linha de base por popularidade (P-071), puro
├── repository/
│   ├── sales_repository.py  # única camada com SQL; RETURN_OPERATION_PATTERN; order_baskets; catálogo
│   └── errors.py            # AnalyticsDataSourceError (infra, ANL-001)
└── backtest/
    └── run_cross_sell_backtest.py  # CLI: repository + domínio; imprime só métricas agregadas
```

- O domínio não importa `pyodbc`, `fastapi` nem `src.core.database`. Exceções de domínio não conhecem HTTP; o mapa `código → status` mora em `api/error_handlers.py`.
- Router registrado em `src/api.py` com `prefix="/api/v1"`, depois de `inventory_router`, e protegido pelo `HTTPBasicAuthASGIMiddleware` já global (LGPD-10).
- Schemas Pydantic com `ConfigDict(alias_generator=to_camel, populate_by_name=True)`: atributos em `snake_case` no Python, JSON em `camelCase`. Os campos de negócio em PT-BR (`confianca`, `pedidosEmComum`) seguem o glossário.

### DA-02 — Agregado `order_baskets` mínimo, todo em inteiros, com leitura em blocos

Uma única query, parametrizada pela data de corte, no grão `Pedido × Cod Produto` (P-058.4):

```sql
SELECT
    DENSE_RANK() OVER (ORDER BY b.[Pedido]) AS order_idx,
    b.[Cod Produto]                          AS sku,
    b.customer_code,
    b.order_day
FROM (
    SELECT
        [Pedido],
        [Cod Produto],
        MIN([Cod Cliente])                     AS customer_code,
        DATEDIFF(day, '20000101', MIN([Data])) AS order_day
    FROM Externo01.Vendas
    WHERE [Operação] = 'VENDA'
      AND [Data] < ?
    GROUP BY [Pedido], [Cod Produto]
    HAVING SUM([Qtd Venda]) > 0
) AS b
```

| Escolha | Motivo |
| :--- | :--- |
| `HAVING SUM([Qtd Venda]) > 0` no SQL | Implementa P-058.2 antes do tráfego; o Python não recebe quantidade. |
| `DENSE_RANK()` em vez de `[Pedido]` | O número do pedido nunca sai do banco (minimização, LGPD-01) e chega como `int32` denso de 0..N, pronto para índice de matriz. Funciona mesmo se `Pedido` for texto. |
| `DATEDIFF(day, '20000101', ...)` | Data como inteiro (dias desde 2000-01-01, constante `ORDER_DAY_EPOCH`). Evita objetos `datetime` do pyodbc (~50 B cada) e não usa `CONCAT`. |
| `MIN([Cod Cliente])` | Premissa A-13 (nova): um `Pedido` pertence a um único cliente. O Desenvolvedor valida uma vez com `COUNT(DISTINCT [Cod Cliente])` por pedido (consulta de diagnóstico, não versionada) e registra o resultado no `STATE`. |
| `[Data] < ?` (bind parameter) | Data de corte exclusiva. Produção: `data_referencia + 1 dia`; backtest: 1º dia do mês N+1 (uma carga cobre treino e avaliação). Nada interpolado (regra de SQLi, LGPD-02). |
| Só colunas permitidas | `Pedido`, `Cod Cliente`, `Cod Produto`, `Data`; `Operação` e `Qtd Venda` só em `WHERE`/`HAVING` (LGPD-01). `fetch_sales_from_database` não é reaproveitada (seleciona `UF` e `Valor Venda`). |

A constante `RETURN_OPERATION_PATTERN = 'DEVOLU%'` e `SALE_OPERATION = 'VENDA'` ficam no topo de `sales_repository.py` (P-058.5). `SALE_OPERATION` também existe em `domain/cross_sell.py` como constante documental exigida pela tabela de constantes; o repositório importa a do domínio para haver uma única fonte (o domínio não importa o repositório, a direção inversa é permitida).

**Leitura em blocos.** O repositório executa com `cursor.execute(sql, cutoff)` e lê com `cursor.fetchmany(FETCH_CHUNK_SIZE = 50_000)`, convertendo cada bloco direto para `numpy.int32` e concatenando ao final. Nunca usa `fetchall()` nem `DataFrame.from_records` sobre a base inteira.

**Catálogo.** Query própria e mínima: `SELECT [Codigo], [Descricao], [Fornecedor], [Estoque], [Pc.Ultimo Custo], [Pc.Venda] FROM Externo01.Produto WHERE [Pc.Venda] > 0` (sem `EAN`/`Tipo`, LGPD-01). ~2,2 mil linhas.

Toda SQL passa por `is_readonly_query` antes de executar; falha → `DatabaseSecurityError`.

### DA-03 — Estimativa de memória e o que fica residente

Base: ~821 mil linhas de VENDA → no máximo ~820 mil pares `Pedido × SKU` (ordem de grandeza usada abaixo: 800 mil).

| Etapa | Estrutura | Estimativa | Observação |
| :--- | :--- | :--- | :--- |
| Leitura (transitório) | 1 bloco de 50 mil `pyodbc.Row` | ~10 MB | Liberado a cada bloco |
| Agregado final | 4 colunas `int32` × 800 mil | **~13 MB** | Contra ~400–700 MB de vendas brutas com 9 colunas de objetos |
| `filter_orphan_baskets` + `build_basket_matrix` (transitório) | `groupby`, `MultiIndex`, cópia filtrada | ~60–100 MB | Coluna `Qtd Venda` sintética `int8 = 1` só para reaproveitar a função |
| Matriz esparsa (1.935 colunas) | `SparseDtype[bool]` | ~5–10 MB | Só pares vendidos |
| ~~FP-Growth `max_len=2` (transitório)~~ **Superado:** contagem direta Xᵀ·X | pares | **135 MB medidos na base real** | Ver revisão de DA-04 |
| **Pico estimado da carga** | | **~150–250 MB** acima do baseline | A medir (B-16 e Etapa 5) |
| **Residente após a carga** (`AnalyticsSnapshot`) | regras úteis + índice, itens triviais, SKUs com cesta, histórico cliente × SKU (`int32` × 3, ~250 mil linhas), catálogo | **< 30 MB** | Agregado e matriz descartados ao fim da carga |

- Nada é carregado no `lifespan` (plano §9): a carga é preguiçosa na primeira requisição do módulo, para não somar o pico ao pré-aquecimento do `pricing` no cold start.
- O log de carga registra só contagens e tempo: pares, cestas válidas, cestas descartadas, regras úteis, itens triviais, duração (P-070.2).
- Risco residual: pico do `pricing` (já residente) + pico do `analytics` sob a mesma instância. Mitigação: carga preguiçosa, troca atômica e medição obrigatória do pico na Etapa 5.

### DA-04 — Reuso de `basket_mining` com uma única mudança aditiva

> **Revisão 2026-11-09 (Orquestrador, aprovada pelo usuário):** a mineração do `analytics` **não usa mais FP-Growth**. Na base real (54.541 cestas válidas, 1.934 SKUs), o `fpgrowth` do mlxtend sobre DataFrame esparso não terminou em 10 min e levou o processo a ~4 GB, acima do limite de 2 Gi do Cloud Run. Os testes não pegaram isso porque usam massa sintética pequena. Como P-059.1 só pede regras 1 → 1, todo itemset frequente é um par, e a contagem direta `Xᵀ·X` sobre a matriz esparsa Pedido × SKU dá o **mesmo resultado** (15.541 regras úteis nas duas formas). Ela leva 2,3 s, com pico de 135 MB na mineração e 319 MB na carga completa. `mine_one_to_one_rules` mantém o formato de saída do mlxtend, então `select_useful_rules`, o backtest e os testes não mudam. Continuam valendo o item 1 (só `filter_orphan_baskets`) e o item 3. O item 2 foi **revertido** na Etapa 4 (achado B-1 do reviewer, YAGNI): `basket_mining.py` e `tests/test_basket_mining.py` voltaram ao estado da `main`, e o módulo `pricing` sai do diff da fase.

1. `filter_orphan_baskets(df, min_skus=MIN_SKUS_PER_BASKET)` e `build_basket_matrix(df)` são usadas **sem alteração**, sobre um DataFrame com colunas `Pedido` (= `order_idx`), `Cod Produto` (= `sku`) e `Qtd Venda` (= 1, `int8`).
2. ~~**[Superado na Etapa 4: revertido, ver revisão acima]**~~ `mine_association_rules` recebe **um parâmetro opcional, somente por nome**: `*, max_len: Optional[int] = None`, repassado ao `fpgrowth`. Com `None` o comportamento do `pricing` é idêntico (regressão coberta pelos testes atuais de `test_basket_mining.py` e `test_meta_tuner.py`, que não mudam). O `analytics` chama com `max_len=2`, `min_lift=MIN_LIFT`, `min_confidence=MIN_CONFIDENCE`, `min_support=MIN_SUPPORT`.
   - Por quê: P-059.1 pede só regras 1 → 1. Sem `max_len`, o FP-Growth gera itemsets de 3+ itens que seriam descartados depois, o que gasta memória e CPU sem uso.
   - Essa é a **única** linha alterada fora de `src/modules/analytics/`. É uma mudança de assinatura compatível, não altera o filtro de devolução do legado (fora de escopo).
3. O domínio do `analytics` converte o resultado em `UsefulRule` (`frozen dataclass`): `antecedent`, `consequent`, `support`, `confidence`, `lift`, `pair_orders = round(support × N)`, `antecedent_orders = round(antecedent_support × N)`. Aplica `pair_orders ≥ MIN_PAIR_ORDERS`, `A ≠ B`, Item Trivial (`consequent support > TRIVIAL_ITEM_SUPPORT`) e indexa por antecedente já ordenado por P-061.1 (`Dict[int, Tuple[UsefulRule, ...]]`).
4. `MIN_LIFT`/`MIN_CONFIDENCE` são inclusivos (P-060.1): o `mlxtend` usa `>=` em `min_threshold` e o filtro de confiança existente também usa `>=`.

### DA-05 — Datas de referência e janelas (sem ambiguidade de fronteira)

- `data_referencia` = último dia incluído na base. Produção: data corrente em UTC−3 (`BUSINESS_UTC_OFFSET_HOURS = -3`, offset fixo, sem depender de `tzdata` na imagem). Backtest: último dia do mês N−1.
- `dias_desde = data_referencia − data_da_ultima_compra` (em dias inteiros, ambos como `order_day`).
- Perfil (P-062.1): SKUs com `dias_desde ≤ CUSTOMER_PROFILE_DAYS`. Dormente (P-062.3): `dias_desde > DORMANT_DAYS` (90 exato não é dormente; 91 é).
- Mineração (A-6): todos os pedidos com `order_day ≤ data_referencia`.

### DA-06 — Cache por snapshot imutável com lock de voo único, TTL e troca atômica

- `AnalyticsSnapshot` (`frozen dataclass`): `reference_date`, `loaded_at`, `valid_basket_count`, `is_base_sufficient`, `rules_by_antecedent`, `trivial_skus`, `skus_with_basket`, `customer_history`, `catalog`, `counts` (só números para o health).
- `get_snapshot(force_reload=False)`: double-checked locking com `threading.Lock` (padrão de `get_cached_base_data`). Expira quando `now − loaded_at ≥ CACHE_TTL_HOURS` (6 h). O relógio é a função `_utc_now()` do módulo, substituível em teste (CA-20).
- A carga monta o snapshot em variáveis locais e só então publica a referência (`_SNAPSHOT = new`). Falha na carga propaga a exceção e mantém o snapshot anterior (P-068.4).
- Base insuficiente (`< MIN_VALID_BASKETS` cestas ou zero regras úteis) **é** um snapshot válido com `is_base_sufficient = False`: as rotas de cross-sell lançam `XSL-003` sem recarregar a cada requisição; o health mostra o estado.
- **Sem cache por cliente** (P-068.5 permite, não exige): o cálculo por cliente percorre só o perfil e o índice de regras (milissegundos). Isso também elimina o requisito de LRU do LGPD-08.
- `health()` lê só a referência atual, sem lock e sem carga (P-069). Para a tela avisar sobre o cache frio (Q-7 do Design Plan), o cache mantém uma flag `_is_loading` (definida e limpa dentro do lock, num `try/finally`, lida sem lock) e a `load_duration_ms` da última carga; o health deriva `estadoCache` = `FRIO` | `CARREGANDO` | `QUENTE` | `EXPIRADO`.
- **Catálogo em cache próprio** (`get_catalog()`, lock e TTL próprios, < 2 MB): alimenta a busca opcional de produtos (DC-5) sem disparar a carga das cestas. A carga do snapshot reaproveita esse catálogo.

### DA-07 — `force_reload` manual (P-068.3)

- `POST /api/v1/analytics/cache/reload`, protegido pela autenticação global. Chama `get_snapshot(force_reload=True)`, que respeita o lock (quem chega durante uma carga espera e reaproveita). Responde 200 com o mesmo `data` do health.
- **Intervalo mínimo** `MIN_RELOAD_INTERVAL_MINUTES = 15`: um reload antes disso devolve **429 `ANL-002`** sem tocar no banco. Isso impede que qualquer usuário autenticado dispare cargas pesadas em sequência.
- Sem botão na tela nesta fase (uso operacional via `curl`). A rota e o código `ANL-002` precisam de aceite no checkpoint (seção 5).

### DA-08 — Erros: hierarquia de domínio, infraestrutura separada e handlers globais

| Classe | Camada | Código | HTTP (mapa na API) |
| :--- | :--- | :--- | :--- |
| `ProductNotFoundError` | domínio | `XSL-001` | 404 |
| `CustomerWithoutHistoryError` | domínio | `XSL-002` | 404 |
| `InsufficientBaseError` | domínio | `XSL-003` | 422 |
| `InvalidParametersError` (+ `RequestValidationError` em rotas do módulo) | API | `XSL-004` | 400 |
| `AnalyticsDataSourceError` | repositório | `ANL-001` | 503 |
| `ReloadTooSoonError` | serviço | `ANL-002` | 429 |

- Todas as exceções de domínio herdam de `AnalyticsDomainException(code, message, fields=())`. A mensagem é **fixa** (P-067) e nunca contém o valor recebido (LGPD-05).
- `register_analytics_error_handlers(app)` registra em `src/api.py`:
  1. `AnalyticsDomainException` e `AnalyticsInfrastructureException` → `JSONResponse` com o corpo de erro do contrato.
  2. `RequestValidationError`: se o path começa com `/api/v1/analytics`, devolve **400 `XSL-004`** listando só os **nomes** dos campos (`loc[-1]`), sem `input`; caso contrário delega a `fastapi.exception_handlers.request_validation_exception_handler` (o 422 de `pricing`/`inventory` não muda).
- Sem `try/except` nas rotas. O repositório traduz `pyodbc.Error`/`ConnectionError` em `AnalyticsDataSourceError` e loga só `type(exc).__name__` (sem `str(e)` do driver).
- Exceções não previstas caem no 500 padrão do Starlette (`debug=False`, corpo `Internal Server Error`, sem stacktrace).
- Os erros do módulo são `JSONResponse` próprios, não `HTTPException(404)`, então o `custom_404_handler` do SPA em `src/api.py` não os intercepta.

### DA-09 — Contrato: envelope, paginação e explicação montada no domínio

- 2xx: `{ "data": ..., "meta": { "timestamp", "version": "1.0.0", "dataReferencia", ... } }`. Listas: `meta` acrescenta `page`, `limit`, `offset`, `totalItems`, `totalPages` (P-066). Paginação calculada por `domain/pagination.py` sobre a lista já filtrada e ordenada (P-063.5).
- Os filtros de viabilidade e a ordenação acontecem antes de `paginate()`; o serviço devolve `PageResult(items, total_items)`.
- **P-065.5 — o texto é montado no domínio** (`cross_sell_explanation.py`), não no Angular. Motivo: uma única implementação testável em Python das regras de arredondamento (meio para cima via `Decimal.quantize(ROUND_HALF_UP)`, vírgula decimal, milhar com ponto), reaproveitável no backtest e em fases futuras; o componente só exibe (frontend "burro"). As frases vêm **separadas** (`explicacao { frequencia, intensidade, evidencia, motivo }`, Q-3) para a tela ordenar e destacar sem concatenar; os números também vêm estruturados.
- `meta.parametros` ecoa as constantes efetivas do domínio (Q-5), para a copy não fixar "90 dias"/"12 meses".
- O modo produto sempre devolve `data.produto { codigo, descricao, fornecedor }`, inclusive com lista vazia (Q-2). O modo cliente inclui `pedidosEmComum` (métrica global da regra, Q-4) e não ecoa `customerCode`.
- Rótulos de status e números com casas fixas definidas no contrato.

### DA-10 — Decisão sobre A-11 (`Cod Cliente` no path)

Avaliadas três formas:

| Opção | Aparece no log de acesso do Uvicorn? | Aparece em `httpRequest.requestUrl` do Cloud Run? | Custo |
| :--- | :--- | :--- | :--- |
| A. `GET /analytics/cross-sell/customer/{customerCode}` | Sim | Sim | Nenhum; REST idiomático |
| B. `GET ...?customerCode=` | Sim | Sim | Nenhum ganho sobre A |
| C. `POST /analytics/cross-sell/customer/query` com corpo `{customerCode, limit, offset}` | Não | Não | Verbo não idempotente para leitura; contrato e testes um pouco maiores; Angular usa `post` |

**Proposta do Arquiteto: Opção A**, alinhada ao parecer do Privacy Officer (`privacy/analytics-cross-sell.md` §4): o código é pseudonimizado, o log revela só "consultou X em tal hora" (útil como trilha de auditoria) e o acesso ao Cloud Logging é restrito por IAM com retenção de 30 dias (LGPD-06). Query string (B) é descartada por não trazer ganho.

**Variante C fica especificada no contrato (Apêndice A)** para adoção imediata caso o usuário prefira eliminar o código dos logs. A troca afeta só o router, o schema de request e um método do `analytics.service.ts`; domínio e serviço não mudam.

Condições da Opção A: nenhum middleware de log de request na aplicação; o Angular **não** coloca `customerCode` na URL da SPA (estado da tela fica no serviço, sem *deep link*) nem em `localStorage`/`sessionStorage` (LGPD-09).

### DA-11 — Frontend

- Rota lazy `{ path: 'analytics', loadChildren: () => import('./features/analytics/analytics.routes') }`, com shell de abas e filho padrão `cross-sell` (as fases seguintes acrescentam filhos).
- `features/analytics/`: `models/` (tipos do contrato, sem `any`), `services/analytics.service.ts` (HTTP tipado), `services/cross-sell.store.ts` (estado com `signal`: carregando, sucesso, vazio, erro, por modo), `utils/analytics-error.ts` (type guard de `HttpErrorResponse` → `AnalyticsApiError` e mapa código → mensagem de tela), `pages/` e `components/` só de apresentação.
- O componente decide a mensagem pelo `code`, nunca pelo texto (regra de erros).

### DA-12 — Backtest (P-071)

- Domínio puro `cross_sell_backtest.py`: recebe o agregado (`int32`), o catálogo e o mês N; corta o treino por `order_day ≤ último dia de N−1`, reaproveita as mesmas funções de mineração e de recomendação por cliente com `apply_stock_filter=False` (P-071.5) e calcula hit rate@5 do modelo e da popularidade, clientes avaliados e excluídos por motivo.
- Runner `python -m src.modules.analytics.backtest.run_cross_sell_backtest --months 2026-08 2026-09 2026-10`: uma carga com corte exclusivo em 2026-11-01, imprime tabela markdown **só com agregados** (LGPD-11), sem gravar arquivo.

---

## 3. Alternativas Consideradas

1. **Reaproveitar `fetch_sales_from_database` e agregar em pandas:** traz linhas por item com `UF`/`Valor Venda` (fere LGPD-01) e repete o padrão que causou OOM.
2. **Trazer `[Pedido]` original e fatorar no Python:** objeto Python por linha (o número pode ser texto) e exposição desnecessária do pedido. `DENSE_RANK` resolve no servidor.
3. **Duas queries (`order_baskets` sem cliente/data + cabeçalho por pedido):** um pouco menos tráfego, mas duas leituras e junção em Python. Com o agregado todo em `int32` (~13 MB) a diferença é irrelevante.
4. **Co-ocorrência por produto de matrizes (`Xᵀ·X`) em vez de FP-Growth:** mais rápida e exata para pares, mas contraria o reuso exigido em P-059. Fica registrada como otimização futura se o FP-Growth pesar.
5. *(Contexto original; superado pela revisão de DA-04.)* **Copiar `basket_mining` para o `analytics`:** duplicação; a mudança aditiva `max_len` é menor e testada.
6. **Reutilizar o cache do `pricing` (`rules_df`):** parâmetros diferentes (suporte/lift do `pricing`, ETL próprio) e acoplamento entre contextos delimitados.
7. **Cache por cliente com LRU:** desnecessário pelo custo do cálculo; adicionaria superfície de retenção de dado pessoal (LGPD-08).
8. **Handler global que muda o 422 de toda a aplicação para 400:** quebraria o contrato de `pricing`/`inventory` (ADR-001, ALT-11). O handler é escopado pelo prefixo `/api/v1/analytics`.
9. **Texto da explicação montado no Angular:** duplicaria regra de arredondamento no cliente e no backtest; o frontend deve ser "burro".
10. **Pré-aquecer o `analytics` no `lifespan`:** somaria o pico ao pré-aquecimento do `pricing` no cold start.
11. **`force_reload` só como função interna:** em produção não há como acioná-la no processo do Cloud Run sem rota.

---

## 4. Consequências e Trade-offs

- **Pontos Positivos:**
  - Memória residente do módulo < 30 MB; pico de carga estimado em 150–250 MB, sem linhas brutas.
  - Fundação reaproveitável: snapshot com lock/TTL, exceções com código, envelope/paginação e handler escopado servem às Fases 2 a 6.
  - Contratos de erro de `pricing`/`inventory` intactos.
  - Domínio testável só com DataFrames/arrays sintéticos; repositório testável com cursor mockado.
- **Pontos Negativos / Débito Técnico Aceito:**
  - ~~Uma linha muda em `pricing/domain/basket_mining.py` (`max_len` opcional).~~ **Superado:** o `pricing` não muda nesta fase (revisão de DA-04).
  - Primeira requisição após o TTL espera a carga (segundos). Aceito; a tela mostra carregamento.
  - Premissa A-13 (pedido com cliente único) precisa de verificação de dados uma vez.
  - Com a Opção A, `customerCode` aparece no log de acesso do Cloud Run (risco baixo, aceito pelo Privacy Officer com LGPD-06/07).
  - Pré-existentes observados, fora do escopo: `src/api.py` usa `Response` no `custom_404_handler` sem importá-lo (rota `/api` inexistente em produção gera 500); `test_db_connection` devolve `str(e)` do driver. Registrar como dívida técnica.

---

## 5. Pontos para decisão no checkpoint

| # | Ponto | Proposta |
| :--- | :--- | :--- |
| DC-1 | A-11: GET com path (A) ou POST com corpo (C) | A (alinhada ao Privacy Officer); C pronta no Apêndice A do contrato |
| DC-2 | Rota `POST /analytics/cache/reload` com intervalo mínimo de 15 min e códigos `ANL-001`/`ANL-002` fora do catálogo `XSL` | Aceitar; o Analista registra `ANL-*` como códigos da fundação |
| DC-3 | Parâmetro `max_len` opcional em `mine_association_rules` (única mudança no `pricing`) | Aceitar → **superado na Etapa 4 (revertido)** |
| DC-4 | Premissa A-13: um `Pedido` tem um único `Cod Cliente` | Verificar com consulta de diagnóstico antes de B-05 |
| DC-5 | Antecipar `GET /analytics/products/search?q=` (código ou descrição, sem acento/maiúsculas, até 20 resultados), pedido pelo Designer (Q-1) | Opcional, especificado no contrato §3.6. Custo: backend ~0,5 dia + frontend ~1 dia, < 2 MB, sem dependência nova, sem dado pessoal. Recomendo **aceitar**: o comprador lembra a descrição, não o código, e a Fase 4 reaproveita a rota |
| DC-6 | Acrescentar `pedidosEmComum` (métrica global da regra) à allowlist do modo cliente (LGPD-03) | Confirmar com o Privacy Officer |
