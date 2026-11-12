# ADR-003: Tendência de Vendas por Item (módulo próprio `sales_trend`): agregado mensal único, snapshot próprio, aritmética exata e erros `TND` autocontidos

> **Status:** Proposto (revisado em 2026-11-09 após o checkpoint do usuário: independência total do cross-sell e exclusão de produtos inativos). Aguarda checkpoint da Etapa 2.
> **Data:** 2026-11-09
> **Autor:** Arquiteto (`architect.md`)
> **Localização Mandatória:** `.agents/docs/adr/ADR-003-tendencia-vendas.md`
> **Nota sobre o slug:** os documentos mantêm o nome histórico `analytics-sales-trend.*` (regras, contrato, tasks) e o `ADR-003-tendencia-vendas` para não quebrar referências. **O código não está mais no módulo `analytics`**: backend em `src/modules/sales_trend/`, frontend em `frontend/src/app/features/sales-trend/`.

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | Tendência de Vendas por Item. Branch `feature/sales-trend`, criada a partir de **`main`** (sem a Fase 1 do cross-sell) |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-sales-trend.md` (P-072 a P-093, CA-01 a CA-40, A-1 a A-26; revisada pelo Analista com as decisões abaixo, mesmos IDs) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-sales-trend.md` (versão 1.0.0; nada foi implementado ainda, então a revisão não muda a versão) |
| **Checklist técnico** | `.agents/docs/tasks/analytics-sales-trend.md` (T-xx, B-xx, F-xx desta feature) |
| **Design Plan** | `.agents/docs/design/plans/analytics-sales-trend.md` (Designer, em revisão paralela: página própria `/tendencia-vendas`) |
| **Plano mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` §2 (convenções que continuam valendo: agregar no SQL, devoluções, envelope, LGPD) |
| **Parecer de privacidade** | Dispensado (P-085.4): nenhuma coluna de cliente é lida, trafegada ou logada. A conferência de P-085.1/P-085.2 fica com o `reviewer` |

### Histórico de revisões

| Data | Revisão |
| :--- | :--- |
| 2026-11-09 (1ª versão) | Feature como seção do módulo `analytics`, reaproveitando fundação, handlers e shell da Fase 1 (`ADR-002`) |
| 2026-11-09 (checkpoint do usuário) | (1) **Independência total do cross-sell:** módulo `sales_trend` e feature Angular próprios, sobre `main`; nenhum import de `src.modules.analytics.*` nem de arquivos da Fase 1. (2) **Códigos de erro autocontidos:** `ANL-001` → `TND-004`, `ANL-002` → `TND-005`. (3) **Inativos fora de tudo:** sem `activeOnly`, sem selo/campo `ativo`; só produtos do catálogo ativo (`Pc.Venda > 0`). Descartados por esta decisão: DC-1 (commit da Fase 1 como pré-requisito), DC-4 (edições em arquivos da Fase 1), R-1 (quebra por mudança na Fase 1), R-8 (D-14: editar `ListPager`/`ErrorBanner`/`ResultState`). Premissas A-1..A-5 e A-17..A-19 do Analista aceitas pelo usuário |

---

## 1. Contexto do Problema

1. **Feature de leitura pura, autocontida.** A Tendência compara, por SKU (ou por fornecedor), a venda líquida de janelas de 1, 3, 6 e 12 meses terminando em um Mês-Base escolhível. O usuário decidiu que ela **não tem por que depender do cross-sell**: vira um módulo próprio, desenvolvido em `feature/sales-trend` a partir de `main`, que pode ser mesclado antes ou depois da Fase 1.
2. **O que existe de fato em `main`** (verificado com `git show main:<arquivo>`; a working tree atual tem a Fase 1 não commitada e **não** vale):
   - Backend: `src/core/database.py` (`is_readonly_query`, `get_db_connection_string`, `DatabaseSecurityError`), `src/core/auth.py` (`HTTPBasicAuthASGIMiddleware`, já global em `src/api.py`), módulos `pricing` e `inventory` no padrão `api/ service/ domain/` (sem camada `repository/` própria: usam `src/core/database.py`), `src/api.py` com `app.include_router(<router>, prefix="/api/v1")` e **sem** handlers globais de erro, `tests/` plano com `TestClient(app)`. Não existem em `main`: paginação, normalização de texto, arredondamento meio-para-cima, cache por snapshot, exceções com código `XXX-NNN`, envelope tipado em camelCase com `to_camel`.
   - Frontend: Angular 18, `provideHttpClient()` e `provideRouter(routes)` em `app.config.ts`, `app.routes.ts` com rotas **eager** `pricing` e `inventory` e curinga `**`, navbar com dois `<li>` (`/pricing`, `/inventory`), tokens de design em `frontend/src/styles.scss` (Papel & Tinta), Karma/Jasmine. **Não existe** `shared/` nem componente reutilizável de paginação, banner de erro, estado vazio, skeleton ou pipes pt-BR.
   - `.agents/` e `AGENTS.md` são **gitignored**: a documentação existe só na working tree local.
3. **Um único agregado serve a tudo.** O Mês-Base muda a cada interação; consultar o banco por mês-base seria inviável (P-083.5). Basta um agregado `Cod Produto × mês` com quantidade e faturamento líquidos de todo o histórico; o domínio fatia as janelas em memória. É o `monthly_sales` do plano mestre §2.5.
4. **Memória no Cloud Run (2Gi).** Os commits #5 e #6 corrigiram OOM por vendas brutas no Python. O `STATE.md` registra que o processo já chega a ~3 GB de pico por causa do pré-aquecimento do `pricing` (preexistente). A Tendência não pode somar uma cópia bruta nem um pico relevante (DA-03, DA-14).
5. **SQL Server legado.** Sem `CONCAT`; o acento de `[Operação]` chega corrompido (`LIKE 'DEVOLU%'` para devolução; `= 'VENDA'` funciona); `YEAR()`, `MONTH()`, `SUM`, `MIN`, `CASE` existem desde 2005. Toda SQL passa por `is_readonly_query` (que exige `SELECT` inicial, sem `;` intermediário e sem `CREATE`, `EXEC`, `MERGE`... no texto).
6. **Exatidão numérica.** O resultado é um percentual com 1 casa, meio para cima, ordenado de forma determinística (P-077.4, P-080). Float binário gera "resíduo" (`1e-13` que vira falso `NOVO`) e empates que não empatam.
7. **Erros e validação.** `main` não tem tratamento global de erro; `pricing`/`inventory` usam o 422 padrão do FastAPI. As regras exigem códigos `TRES_LETRAS-NUMERO`, HTTP semântico, 400 para validação e nenhum stacktrace, **sem mudar** os contratos de `pricing`/`inventory`. A Fase 1 (quando for mesclada) registra um handler **global** de `RequestValidationError` com escopo `/api/v1/analytics`; só pode existir um handler por exceção na aplicação, então a Tendência **não pode** registrar o seu (colidiriam).

---

## 2. Decisões Arquiteturais

### DA-01 — Módulo próprio `sales_trend`, sem nenhum import da Fase 1

```
src/modules/sales_trend/
├── __init__.py
├── api/
│   ├── router.py        # sales_trend_router (prefix="/sales-trend", route_class=TrendAPIRoute); só recebe, chama service, devolve
│   ├── route.py         # TrendAPIRoute: tradução centralizada de erros do módulo (DA-09)
│   ├── query_params.py  # dependências de query com validação (TrendListQuery, TrendDetailQuery)
│   ├── schemas.py       # Pydantic (camelCase por alias): envelope, meta, linhas, célula, erro
│   └── mappers.py       # domínio -> schemas, arredondamento de exibição, meta
├── service/
│   ├── sales_trend_cache.py    # SalesTrendSnapshot, voo único, TTL, force_reload, estado (DA-04)
│   └── sales_trend_service.py  # casos de uso: lista (product|supplier), detalhe do fornecedor, health, recarga
├── domain/              # Python puro, sem I/O, sem pyodbc/fastapi/src.core
│   ├── exceptions.py    # TrendDomainException e TND-001/002/003
│   ├── pagination.py    # PageRequest, PageResult, paginate (limit 50 padrão, máx 200)
│   ├── search_text.py   # normalize_text, is_valid_search_query, predicado de busca
│   ├── rounding.py      # arredondamento meio para cima exato (Fraction/Decimal)
│   ├── month_windows.py # aritmética de mês (índice inteiro), janelas atual/anterior, dias, cobertura
│   ├── sales_trend.py   # constantes P-072..P-093 (topo), MonthlySales/SkuSeries, build, célula (piso zero, %, status, selos)
│   ├── suppliers.py     # identidade/normalização, grupos, soma, contribuição, linha total
│   └── ranking.py       # universo, q, view, minVolume, ordenação (grupos + desempate), totais por visão
├── repository/
│   ├── sales_trend_repository.py  # única camada com SQL: agregado mensal e catálogo ativo
│   └── errors.py        # TrendInfrastructureException, TrendDataSourceError (TND-004)
└── diagnostics/
    └── run_sales_trend_report.py  # CLI somente leitura: memória, contagens, reconciliação, calibração (DA-14)
tests/sales_trend/       # __init__.py, trend_sample.py, test_*.py (pasta própria; não mistura com tests/analytics)
```

- **Dependências permitidas** (todas em `main`): `src.core.database` (`is_readonly_query`, `get_db_connection_string`, `DatabaseSecurityError`), `src.core.auth` (já aplicado globalmente), `fastapi`, `pydantic`, `pyodbc` e biblioteca padrão. **Proibido** importar `src.modules.analytics.*`, `src.modules.pricing.*`, `src.modules.inventory.*`.
- O domínio **não** importa `pyodbc`, `fastapi` nem `src.core.database`. Camadas e direção de dependência: router → service → domain/repository; o service chama os mappers (padrão de `pricing`/`inventory`).
- **Duplicação deliberada** (independência > DRY): paginação, normalização de texto, arredondamento, mecanismo de lock do snapshot e `_execute_readonly` são reescritos aqui. Dívida: se um terceiro módulo precisar, extrair para `src/core/` depois que Tendência e cross-sell estiverem em `main`.
- **Pontos de contato com arquivos existentes de `main` (4 edições mínimas):** `src/api.py` (1 `import` + 1 `include_router`), `frontend/src/app/app.routes.ts` (1 rota lazy), `frontend/src/app/core/layout/navbar/navbar.component.html` (1 `<li>`) e `frontend/src/styles.scss` (token `--navbar-height`, Design Plan D-5). O `frontend/proxy.conf.json` **não** precisa de edição (DA-12). Ver DA-13 e R-3.
- `requirements.txt` não muda.

**Frontend** (`frontend/src/app/features/sales-trend/`), página própria sem shell de abas:

```
pages/sales-trend-page/          # único componente inteligente (SalesTrendPageComponent)
models/sales-trend.model.ts      # tipos do contrato 1.0.0 (sem any) + códigos de erro TND-001..005
services/sales-trend.service.ts  # HTTP tipado (getTrend com overloads, getSupplierProducts, getHealth)
services/sales-trend.store.ts    # Signals: consulta, status, resposta, expansões; sincroniza com a URL; provido pela página
services/viewport.service.ts     # signal isCompact (tabela >= 768 px, cartões abaixo)
utils/pt-br-format.ts            # formatação pt-BR própria (formatDecimal, formatCurrency, formatIsoDate, roundHalfUp)
utils/trend-format.ts            # variação com sinal U+2212, p.p., faixa de meses, valor por métrica
utils/trend-view.ts              # funções puras resposta -> view-models
utils/trend-url.ts               # estado da consulta <-> query params (Design Plan D-12)
utils/trend-error.ts             # type guard do corpo de erro TND-001..005 + mensagens de tela por código
pipes/trend-format.pipes.ts      # pipes finos
components/                      # burros e próprios da feature: toolbar, segmented-control, base-month-picker, search-field,
                                 # table, cards, row, cell, row-values, supplier-group, pager, error-banner, empty-state, inline-notice,
                                 # table-skeleton, reading-guide, period-legend (lista final: Design Plan §4.2)
styles/_trend-ui.scss            # mixins e constantes SCSS da feature, só com tokens de styles.scss
```

- Rota **lazy** `{ path: 'tendencia-vendas', loadComponent: () => import(...).then(m => m.SalesTrendPageComponent) }` em `app.routes.ts` (antes do curinga) e um item "Tendência de Vendas" na navbar (`routerLink="/tendencia-vendas"`, `routerLinkActive`).
- Nada de `analytics-shell`, `ANALYTICS_ROUTES`, `ListPager`, `ErrorBanner`, `ResultState`, `pt-br-format.ts`/pipes ou `analytics-error.ts` da Fase 1. Como `main` não tem `shared/`, tudo o que o Design Plan chamava de "reaproveitar" passa a ser **criado dentro da feature**. O Design Plan D-14 deixa de existir.

### DA-02 — Um único agregado mensal no SQL (grão `Cod Produto × mês`) e catálogo ativo

Uma única consulta, parametrizada pelo corte exclusivo, cobrindo **todo o histórico**:

```sql
SELECT
    [Cod Produto]                                                  AS sku,
    YEAR([Data]) * 100 + MONTH([Data])                             AS year_month,
    SUM([Qtd Venda])                                               AS quantity,
    SUM([Valor Venda])                                             AS revenue,
    MIN(CASE WHEN [Operação] = 'VENDA' THEN [Data] END)            AS first_sale_date
FROM Externo01.Vendas
WHERE ([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%')
  AND [Data] < ?
GROUP BY [Cod Produto], YEAR([Data]) * 100 + MONTH([Data])
```

| Escolha | Motivo |
| :--- | :--- |
| `SALE_OPERATION` e `RETURN_OPERATION_PATTERN` como **constantes do módulo** interpoladas (nada vindo do cliente), corte `[Data] < ?` como **bind parameter** | Garantia de SQLi/LGPD-02; `main` não tem a constante de devolução (P-058.5 vivia na Fase 1), então ela nasce em `sales_trend_repository.py` |
| Sem `HAVING` | P-072.1: SKU com venda e devolução que somam zero **tem movimento** e precisa aparecer |
| `SUM` das duas colunas na mesma consulta | Trocar a métrica não relê o banco (P-073.5) |
| `MIN(CASE WHEN 'VENDA' ...)` por grupo | A **primeira data de VENDA** (P-074.2, P-076.1) sai da mesma varredura: o Python toma o mínimo dos mínimos de **todas** as linhas lidas, **antes** de descartar SKUs fora do catálogo ativo (a cobertura é propriedade da base, não do catálogo) |
| Só `Cod Produto`, `Data`, `Qtd Venda`, `Valor Venda` e `Operação` (esta só no filtro) | P-073.3/P-085.1. Sem `Cod Cliente`, `Pedido`, `Fornecedor` nem `JOIN` (CA-26, CA-40) |
| Sem `CONCAT`; `YEAR*100+MONTH` | Servidor legado; inteiro `AAAAMM` é compacto |
| Corte = `dataReferencia` | P-076.1: o dia corrente é parcial e fica fora; `ultimoDiaCoberto = dataReferencia - 1 dia` |

**Leitura em blocos.** `cursor.fetchmany(FETCH_CHUNK_SIZE = 50_000)`, nunca `fetchall`. Cada bloco é convertido **imediatamente** para inteiros escalados (DA-03), filtrado pelo conjunto de SKUs ativos e descartado; só o acumulador compacto sobrevive.

**Catálogo ativo (decisão do usuário: inativos fora de tudo).** Consulta própria, projeção mínima, só produtos ativos:

```sql
SELECT [Codigo], [Descricao], [Fornecedor]
FROM Externo01.Produto
WHERE [Pc.Venda] > 0
```

(mesmo critério de ativo que `main` usa em `fetch_products_from_database`; `Pc.Venda` nulo não satisfaz `> 0`.) ~1,4 mil linhas (a navbar de `main` exibe "1.398 produtos" ativos), lidas com `fetchall`. **Ordem na carga:** primeiro o catálogo ativo, depois o agregado, descartando durante a leitura as linhas de SKU fora do catálogo. Ver DA-16 para a consequência.

Ambas as consultas passam por `_execute_readonly` (que chama `is_readonly_query` antes de conectar) e traduzem `pyodbc.Error`/`ConnectionError`/`ValueError` (variável de ambiente ausente) em `TrendDataSourceError` (`TND-004`), logando só o tipo da exceção.

### DA-03 — Representação em memória: inteiros escalados e máscara de movimento; estimativa

Os valores do agregado são guardados como **inteiros escalados** por `VALUE_SCALE = 10_000` (4 casas; cobre `money` e quantidade fracionária), convertidos de `Decimal(str(valor))` com meio-para-cima na leitura:

```python
@dataclass(frozen=True)
class SkuSeries:
    quantity: Tuple[int, ...]   # um valor por mês, a partir de MonthlySales.first_month (0 onde não há linha)
    revenue: Tuple[int, ...]
    movement_mask: int          # bit i = existe linha de VENDA/devolução no mês i (distingue "líquido 0" de "sem linha")

@dataclass(frozen=True)
class MonthlySales:
    first_month: int            # índice de mês (ano * 12 + mês - 1) do primeiro mês do agregado
    month_count: int
    series: Mapping[int, SkuSeries]   # só SKUs do catálogo ativo
    first_sale_date: Optional[date]   # None = base de vendas vazia -> TND-002
```

Inteiros escalados deixam soma e comparação com zero **exatas** (venda 100,10 e devolução −100,10 somam 0, sem resíduo que vire falso `NOVO`), e a máscara dá a P-072.1 ("tem movimento" ≠ "líquido diferente de zero").

**Estimativa de memória (≈ 1,9 mil SKUs com venda lidos, ≈ 1,4 mil retidos, × 23 meses × 2 métricas):**

| Item | Conta | Tamanho |
| :--- | :--- | :--- |
| Linhas lidas do agregado | 1.935 × 23 = **44.505** (teto; real tende a 60–80%) | transitório |
| Séries retidas (só catálogo ativo) | ~1,4 mil SKUs × 2 tuplas × 23 inteiros × ~36 B + overhead ≈ 2 KB/SKU | ~2,8 MB (teto 3,9 MB com 1,9 mil) |
| Projeção para 36 meses | 1,4 a 1,9 mil × 2 × 36 × ~36 B | ~4 a 5,6 MB |
| Catálogo ativo (descrição, fornecedor, descrição normalizada) | ~1,4 mil × ~350 B | ~0,5 MB |
| Índice de fornecedores | ~150 grupos | < 0,1 MB |
| **Residente do snapshot** | | **≈ 3 a 6 MB** |
| Leitura transitória (1 bloco de ~45 mil `pyodbc.Row` com 2 `Decimal`) | 45.000 × ~300 B | ~13 MB, liberado por bloco |
| **Pico da carga** (transitório + acumulador + catálogo) | | **≈ 20 a 30 MB** acima do baseline |
| Por requisição (rank de 1 janela em ~1,4 mil SKUs + célula de ≤ 200 linhas) | objetos efêmeros | ~1 a 2 MB; ≤ ~80 MB no pior caso teórico (40 threads do pool simultâneas) |

**Conclusão:** acréscimo residente **< 0,3% de 2 GiB**; pico de carga ~25 MB. O agregado bruto que causou os OOMs (~825 mil linhas × 9 colunas de objetos, 400-700 MB) **nunca existe** aqui: o SQL entrega ~44 mil linhas já agregadas. Há folga ampla **para esta feature**; o que ameaça os 2 GiB é o pré-aquecimento do `pricing` (~3 GB de pico, `STATE.md`), preexistente e fora desta feature. Mesmo assim a medição real é obrigatória (B-14 e T-12) e o resultado vai ao PR.

### DA-04 — Snapshot próprio (`sales_trend_cache.py`), sem nenhum `analytics_cache.py`

- `SalesTrendSnapshot` (`frozen dataclass`): `reference_date`, `loaded_at`, `monthly_sales: MonthlySales`, `catalog: Mapping[int, TrendCatalogEntry]` (código → descrição, fornecedor, descrição normalizada), `supplier_index` (grupos por chave, DA-07), `counts` (só inteiros, para log, health e recarga).
- API do módulo: `get_snapshot(force_reload=False)`, `peek_snapshot()`, `get_cache_status()`, `reset_cache()`. Voo único com `threading.Lock` e *double-checked locking*; TTL de `CACHE_TTL_HOURS = 6` (6 h exatas expiram); troca atômica só após sucesso; falha preserva o snapshot anterior e propaga `TrendDataSourceError` (`TND-004`); `force_reload` respeita o lock e o intervalo mínimo `MIN_RELOAD_INTERVAL_MINUTES = 15` (`ReloadTooSoonError`, `TND-005`, sem tocar no banco).
- Relógio próprio `_utc_now()` (substituível em teste, CA-23/CA-25); `business_date(moment)` próprio (UTC-3, offset fixo `BUSINESS_UTC_OFFSET_HOURS = -3`, sem `tzdata`); estados `FRIO | CARREGANDO | QUENTE | EXPIRADO` próprios.
- Estados lidos **sem lock** (`peek_snapshot`, flag `_is_loading`, `_load_duration_ms`) para o health.
- Carga **preguiçosa** na primeira requisição (nada no `lifespan`, para não somar ao pré-aquecimento do `pricing`).
- **Dívida registrada:** o mecanismo de lock é parecido com o de `pricing_service.get_cached_base_data` e com o da Fase 1; extrair um `SnapshotCache[T]` em `src/core/` quando houver um terceiro consumidor (Fases 3, 4 ou 6 reaproveitam o agregado `monthly_sales`).

### DA-05 — Datas do snapshot e congelamento do mês corrente (P-083.3, P-083.4)

- `reference_date = business_date(loaded_at)`, calculada **na carga**. `ultimo_dia_coberto = reference_date - 1 dia`. O corte do SQL é `[Data] < reference_date`.
- Toda cobertura (P-076), `mesBasePadrao` (mês anterior ao de `reference_date`), `mesBaseMaximo` (mês de `reference_date`), o rótulo "dados até" e a validação do Mês-Base derivam **do snapshot**, nunca do relógio da requisição. Mesmo após a meia-noite, dentro do TTL, resposta e totais em cache são coerentes (CA-25).
- O total do mês corrente fica **congelado** até a próxima recarga: no máximo 6 h, ou `POST /reload`. Sem invalidação por virada de dia (A-14).
- A aritmética de mês usa um **índice inteiro** (`ano * 12 + mês - 1`); `date` só é criado depois de o Mês-Base ter sido validado contra `[mesBaseMinimo, mesBaseMaximo]`, para que `baseMonth=0000-01` produza `TND-002` e não um `ValueError` de `date`.

### DA-06 — Cálculo em duas fases, aritmética exata e sem memoização

1. **Fase A (todos os SKUs ativos com movimento, uma janela):** para a `sortWindow` escolhida, calcula `status` e a chave de ordenação. Com isso saem `view`, `minVolume`, `totaisPorVisao`, `meta.total`, a ordenação e a paginação.
2. **Fase B (só a página, 4 janelas):** monta as 4 células completas (com `atualPorDia`, selos e, no detalhe, contribuições) **apenas** para os ≤ 200 itens da página.

Por requisição o custo é ~1,4 mil células + ≤ 800, não 1,4 mil × 4. Sem memoização (P-083.5 é opcional); reavaliar só se T-12 mostrar p95 acima de 300 ms.

**Aritmética exata.** Seja `a`/`b` o líquido da janela atual/anterior (inteiros escalados, **após o piso zero**), `cc`/`cp` os dias cobertos de cada janela, e `daily = cobertura incompleta em alguma das duas`:

- `status` por inteiros (`SEM_BASE` por `2 * cp < diasJanelaAnterior`; `b > 0` → `VARIACAO`; `b == 0 and a > 0` → `NOVO`; senão `SEM_MOVIMENTO`): sem ponto flutuante.
- Razão de comparação: com `daily`, `ratio = (a * cp) / (b * cc)`; sem `daily` (totais), `cc = cp = 1`. Variação = `(ratio - 1) * 100` como **`fractions.Fraction`**.
- Chave de ordenação = o próprio `Fraction` (exata, sem empates falsos). Exibição: `domain/rounding.py` arredonda o `Fraction` **meio para cima sobre a magnitude** por aritmética de inteiros (12,25 → 12,3; −12,25 → −12,3), sem passar por float binário (P-077.4). `-0,04%` vira `0.0` sem sinal e continua `VARIACAO` (P-077.5).
- Desempate (P-080.3) por `|a * cp - b * cc|` (inteiro exato; o denominador `cc * cp` é igual para todos os SKUs da janela), depois código. Premissa **AR-1:** o desempate usa os valores **após o piso zero**.
- Contribuição (P-090.1): `contribuicaoPp = (a_sku*cp - b_sku*cc) / (anteriorF * cc) * 100` com `a_sku`/`b_sku` **brutos** (sem piso) e `anteriorF` bruto do fornecedor; `Fraction` também. A soma exata dos `Fraction` dos filhos é a variação do fornecedor (P-090.4): teste de fecho sem tolerância (a tolerância de 0,1 p.p. só existe na **exibição** arredondada).

### DA-07 — Fornecedor: resolvido no domínio, a partir do catálogo ativo do mesmo snapshot (P-093)

- A SQL do agregado **não** traz fornecedor. No `build` do snapshot, `suppliers.build_supplier_index(catalog)` produz os grupos por chave normalizada (`normalize_text` de `domain/search_text.py`, P-089.1). Nome exibido = menor grafia ordinal entre as variantes já aparadas e com espaços colapsados. Produto **ativo** com `Fornecedor` nulo, vazio ou só espaços vai para o grupo reservado "Sem fornecedor" (`NO_SUPPLIER_LABEL`). Produto ausente do catálogo ativo **não entra** (DA-16).
- **`supplierKey` opaco e sem colisão:** `fornecedorChave = "f:" + chave_normalizada` para fornecedores reais; `NO_SUPPLIER_KEY = "sem-fornecedor"` para o grupo reservado (o prefixo `f:` impede que um nome real colida com a chave reservada). Premissa **AR-4**.
- Catálogo e agregado são do **mesmo snapshot**: o mapa SKU → fornecedor é sempre o da mesma carga (P-093.2). Mudança de fornecedor no ERP só aparece na próxima recarga.

### DA-08 — Rotas: uma lista com `groupBy`, um detalhe, um health e uma recarga; seletor de mês pelo `meta`

| Método | Rota | Papel |
| :--- | :--- | :--- |
| `GET` | `/api/v1/sales-trend` | Lista paginada; `groupBy=product` (padrão) ou `supplier`. Traz no `meta` tudo do seletor de Mês-Base |
| `GET` | `/api/v1/sales-trend/supplier-products` | Produtos de um fornecedor (`supplierKey` na query string), paginado (padrão 20), com contribuição |
| `GET` | `/api/v1/sales-trend/health` | Estado do snapshot, sem carga e sem banco (aviso de cache frio, Design Plan Q-14) |
| `POST` | `/api/v1/sales-trend/reload` | Recarga manual (`TND-005` em 15 min) |

- **Lista única com `groupBy`** porque as regras (P-084.1, P-084.6, P-088.1, P-088.4, C-33, C-34, CA-28) e o Design Plan tratam a troca como "a mesma rota, outro `groupBy`", e `groupBy` inválido é um `TND-001` testável. Tipagem limpa com dois modelos de resposta distintos (`ProductTrendResponse`, `SupplierTrendResponse`) distinguidos por `meta.agrupamento` (`Literal`); o router declara `response_model=Union[...]` e o service despacha por `groupBy`. No frontend, `getTrend` com *overloads* chama a mesma URL.
- **Sem rota própria para o seletor de Mês-Base:** a primeira chamada (sem `baseMonth`) já devolve `mesBasePadrao/Minimo/Maximo` e `ultimoDiaCoberto`.
- **Health e recarga próprios** (P-083.2, P-083.6): sem a Fase 1 no caminho, não há `GET /analytics/health` nem `POST /analytics/cache/reload` a estender; cada um é desta feature. Sem botão de recarga na tela.
- Rotas síncronas (`def`): a carga usa `pyodbc` e o FastAPI as executa no threadpool, como `pricing`/`inventory`.
- `meta.total` ("Todos os produtos", Q-4) e `meta.parametros` (Q-9) entram no `meta` da lista; `total` reutiliza o cálculo de fornecedor sobre um único grupo (todo o universo ativo com movimento).

### DA-09 — Erros `TND-001..005` e A-13 reavaliada: `TrendAPIRoute` centraliza o tratamento do módulo

A-13 era "como obter `TND-001` sem mudar o `XSL-004` do cross-sell". Sem a Fase 1 em `main`, o conflito original desaparece, mas surge outro: **a Fase 1, quando mesclada, registra um handler global de `RequestValidationError`**, e só pode existir **um** por aplicação. Se a Tendência registrasse o seu, o último a ser registrado venceria e quebraria o outro módulo (ou os 422 de `pricing`/`inventory`).

**Solução mais simples e sem colisão:** uma `APIRoute` customizada (`TrendAPIRoute`, `api/route.py`) usada só pelo `sales_trend_router`, que traduz **todos** os erros do módulo para o corpo único e o HTTP semântico, num único ponto (não há `try/except` por rota):

```python
class TrendAPIRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                return _error_response(InvalidTrendParametersError(fields=_invalid_field_names(exc.errors())))
            except (TrendDomainException, TrendInfrastructureException) as exc:
                return _error_response(exc)

        return handler
```

| Classe | Camada | Código | HTTP |
| :--- | :--- | :--- | :--- |
| `InvalidTrendParametersError` (também gerada a partir de `RequestValidationError`) | domínio | `TND-001` | 400 |
| `BaseMonthWithoutSalesError` | domínio | `TND-002` | 422 |
| `SupplierNotFoundError` | domínio | `TND-003` | 404 |
| `TrendDataSourceError` | repositório | `TND-004` | 503 |
| `ReloadTooSoonError` | serviço | `TND-005` | 429 |

- O mapa código → HTTP vive em `api/route.py` (o domínio não conhece HTTP). Mensagens **fixas**, sem valor recebido (P-082.4, LGPD-05); `fields` só com nomes (`loc[-1]`).
- **Corpo de `TND-004` fixado (Design Plan Q-16):** `{ "error": { "code": "TND-004", "message": "Base de vendas indisponível no momento. Tente novamente em instantes.", "fields": [] }, "meta": { "timestamp": "...", "version": "1.0.0" } }` (503), sem detalhe do driver. **`TND-005` nunca ocorre na UI:** só `POST /reload` chama `get_snapshot(force_reload=True)`; `GET /`, `GET /supplier-products` e `GET /health` usam `get_snapshot()` sem `force_reload` (ou nem carregam, no health) e jamais devolvem 429. A tela não tem botão de recarga; a copy de `TND-005` existe só por defesa.
- **Zero registro global:** `src/api.py` recebe só o `include_router`. Handlers globais da Fase 1 (ou de qualquer outro módulo) seguem intactos, e erros de validação de `pricing`/`inventory` continuam com o 422 padrão (teste de regressão T-08).
- `include_router` preserva a `route_class` de cada rota (FastAPI usa `route_class_override=type(route)`).
- Exceções não previstas seguem para o 500 genérico do Starlette (`debug=False`, corpo `Internal Server Error`, sem stacktrace); o erro de resposta (`ResponseValidationError`) também.
- Corpo de erro **definido neste módulo** (contrato §5): `{ "error": { "code", "message", "fields" }, "meta": { "timestamp", "version" } }`.
- Erros que dependem de snapshot nascem no service/domínio: Mês-Base futuro → `TND-001` (`baseMonth`); anterior à base, mês corrente sem dia fechado ou base vazia → `TND-002`; `supplierKey` inexistente → `TND-003` (P-082.1).
- **Alternativa descartada:** `register_trend_error_handlers(app)` com handlers globais (exige 2 linhas a mais em `api.py` e colide no `RequestValidationError`).

### DA-10 — Domínio autocontido: busca, paginação e arredondamento próprios

- `search_text.py`: `normalize_text` (NFKD sem acento, minúsculas, trim e colapso de espaços), `is_valid_search_query` (1 a 60 caracteres se só dígitos, 2 a 60 nos demais) e o predicado de filtro (só dígitos → código igual ou que começa com `q`; senão descrição normalizada contém `q`; fornecedor: nome normalizado contém `q`, inclusive só dígitos, P-091.2). A regra textual de P-081.1 é reescrita pelo Analista de forma autocontida; a descrição normalizada é pré-calculada no snapshot. `q` em branco após trim equivale a sem filtro: o `AfterValidator` da rota devolve `None`.
- `pagination.py`: `PageRequest`, `PageResult`, `paginate` (`page = floor(offset/limit)+1`, `totalPages = ceil`, 0 sem itens), `DEFAULT_PAGE_LIMIT = 50`, `MAX_PAGE_LIMIT = 200` (P-081.4).
- `rounding.py`: `round_fraction_half_up(fraction, places)` e `round_scaled_half_up(valor_escalado, places)`; sem `float` no caminho de arredondamento.

### DA-11 — Contrato: números estruturados no backend, copy no frontend

- O backend entrega **números e enums**; rótulos ("Base parcial", "Novo", "Devoluções superam vendas"), tooltips e títulos de coluna ("ago–out/26 vs mai–jul/26") são montados no frontend a partir de campos estruturados. Copy fixa por enum, sem regra de negócio; evita carregar texto em 50 a 200 linhas × 4 células por resposta.
- Exceção: valores **derivados** (média por dia) vêm prontos: `atualPorDia`/`anteriorPorDia` (só quando `baseParcial`).
- O sinal negativo exibido é o `−` (U+2212), como em P-086.1, tratado em `trend-format.ts`, porque `Intl` usa hífen.
- Precisões: `variacaoPct` e `contribuicaoPp` 1 casa; `atual`/`anterior`/`contribuicaoValor` 2 casas (faturamento) ou 3 (quantidade); valores por dia 4 casas.
- Sem campo `ativo` e sem filtro `activeOnly` (DA-16).

### DA-12 — Frontend: feature própria, página própria, store com Signals, componentes burros

- `SalesTrendStore` (`@Injectable()` provido pela página; morre com ela): `signal`s de consulta (`baseMonth`, `metric`, `groupBy`, `view`, `sortWindow`, `sortDir`, `q`, `minVolume`, `offset`, `limit`), `status` (`idle|loading|success|empty|error`), `response`, `error`, e `expansions` (mapa imutável `supplierKey → { status, response, error, page }`). Cancela a requisição anterior ao disparar outra. Regras de transição no **store** (P-086.7, P-079.5, A-26): trocar `groupBy` preserva Mês-Base, métrica, `sortWindow` e `sortDir` e zera `view`, `minVolume` e `q`; trocar métrica zera `minVolume`; qualquer mudança volta `offset` a 0 e recolhe as expansões; detalhe com `TND-003` recolhe a linha com aviso; `meta.dataReferencia` do detalhe diferente do da lista dispara recarga da lista.
- **Estado da consulta na URL** (Design Plan D-12, aceito): query params da SPA, fonte única de verdade, via `utils/trend-url.ts` (nomes iguais aos da API). Sem dado pessoal; nada em `localStorage`/`sessionStorage`.
- Componentes só desenham e emitem eventos; nenhum chama HTTP nem formata número inline (pipes e `trend-format.ts` da própria feature). Tudo que o Design Plan chamava de "reaproveitar da Fase 1" é **criado na feature**; o Design Plan revisado deve apontar para esses componentes próprios.
- Nenhum spec de navbar novo (evita conflito de arquivo com o `navbar.component.spec.ts` da Fase 1); a presença do link é conferida manualmente e a rota por spec próprio da feature.
- **Proxy do dev server (Design Plan Q-17), verificado em `main`:** `frontend/proxy.conf.json` tem uma única entrada `"/api"` → `http://127.0.0.1:8000` (e `angular.json` o referencia em `serve.options.proxyConfig`), que **já cobre** `/api/v1/sales-trend`. Em produção a API serve o Angular compilado na mesma origem (`src/api.py` monta `frontend/dist`). Logo, **nenhuma edição** em `proxy.conf.json` e nenhuma tarefa F-xx para isso. `SalesTrendService` fixa `baseUrl = '/api/v1/sales-trend'`, como `InventoryService`.
- **Token `--navbar-height` (Design Plan D-5):** `frontend/src/styles.scss` de `main` **não** o tem. Acrescentar em `:root` `--navbar-height: 64px` e, em `@media (max-width: 768px)`, `58px` (os valores já usados em `navbar.component.scss`, que é `position: sticky; top: 0`). Edição aditiva de 2 a 4 linhas; consumido só pela tabela da feature. Sem o token, a tabela fica sem cabeçalho fixo (degrada sem quebrar).

### DA-13 — Independência de código, branch e pontos de contato (risco de merge)

- **Branch:** `feature/sales-trend` criada a partir de **`main`** (hoje `7004f96`). Como a working tree atual tem a Fase 1 **não commitada** na branch `feature/analytics-cross-sell`, **não** trocar de branch nela: usar um `git worktree` ao lado, preservando a working tree da Fase 1:

  ```
  git worktree add ../fitoherb-sales-trend -b feature/sales-trend main
  ```

- **`.agents/` e `AGENTS.md` são gitignored**, então o worktree **não** os tem. Compartilhar a mesma pasta de documentação com uma junção de diretório (Windows: `mklink /J ..\fitoherb-sales-trend\.agents <repo>\.agents`) ou copiar `.agents/` e `AGENTS.md`; sem isso os agentes no worktree não enxergam as regras, o ADR e o contrato. Preparar também `.env`, ambiente Python e `npm install` no worktree.
- **Edições em arquivos existentes de `main`** (as únicas, cada uma em poucas linhas):
  1. `src/api.py`: `from src.modules.sales_trend.api.router import sales_trend_router` e `app.include_router(sales_trend_router, prefix="/api/v1")` (junto aos demais `include_router`).
  2. `frontend/src/app/app.routes.ts`: uma rota `{ path: 'tendencia-vendas', loadComponent: ... }` antes do curinga `**`.
  3. `frontend/src/app/core/layout/navbar/navbar.component.html`: um `<li class="nav-item">` após o de "Estoque e Compras".
  4. `frontend/src/styles.scss`: token `--navbar-height` (DA-12).
  - **Sem edição:** `frontend/proxy.conf.json` (já cobre `/api`), `requirements.txt`, `navbar.component.scss`, `app.config.ts`.
- **Risco de merge (R-3):** a Fase 1 edita as mesmas três primeiras regiões (import, `include_router` e `register_analytics_error_handlers` em `api.py`; rota `analytics` em `app.routes.ts`; `<li>` "Análises de Vendas" na navbar). O conflito é textual e as mudanças são **aditivas e independentes**: ao mesclar a segunda, **manter as duas** (união) nas três regiões; nenhuma depende da outra; conferir depois que `src/api.py` ainda importa e registra os dois routers e que `app.routes.ts` mantém o curinga `**` por último. O `styles.scss` não é tocado pela Fase 1 (`git status` não o lista), então não deve conflitar. Nenhum teste muda.
- Ordem de merge indiferente. Quem entrar depois resolve os 3 conflitos de união.

### DA-14 — Medição, reconciliação e calibração (P-087, CA-27)

CLI `python -m src.modules.sales_trend.diagnostics.run_sales_trend_report` (B-14), só leitura, sem gravar arquivo, saída **só com agregados** (nunca SKU, nome de fornecedor, `q` ou linha):

- Tempo de carga, `tracemalloc` (pico) e RSS máximo (`resource.getrusage` no Linux; sem dependência nova), tamanho aproximado do snapshot.
- Contagens: SKUs lidos, SKUs retidos (catálogo ativo), SKUs descartados por inativos, meses, linhas do agregado, fornecedores, **SKUs do maior fornecedor** (A-18), grupos de fornecedor com mais de uma grafia (A-20), células `NOVO`/`SEM_BASE` por janela no Mês-Base padrão.
- Reconciliação (P-087.3): soma de `atual` da janela de 1 mês, por métrica, **dos SKUs ativos**, igual à soma direta `VENDA + DEVOLU%` do mês restrita aos mesmos SKUs no SQL (diferença em centavos; tolerância R$ 0,01 por SKU-mês só se a coluna tiver mais de 2 casas). Reportar também o total do mês sem restrição, para dimensionar o que os inativos representam.
- Calibração de P-079.1: percentis (p10, p25, p50, p75, p90) do volume da Janela Anterior.

### DA-15 — Governança de documentação e comentários

Docstring de topo em todo arquivo; docstring estilo Google com `Regra: P-0XX` e o **porquê** em funções públicas e constantes; `Field(description=...)` em PT-BR, `Literal[...]` para enums e `responses={400, 404, 422, 429, 503}` documentados no OpenAPI; TypeScript sem `any` e com TSDoc nas exportações. Funções de até ~30 linhas e no máximo 3 parâmetros (DTO acima disso); early return; constantes nomeadas no topo de `domain/sales_trend.py`.

### DA-16 — Inativos fora de tudo (decisão do usuário) e sua consequência

- Só entram na lista, nas somas de fornecedor, em `meta.total` e em `qtdProdutos` os produtos **ativos** do catálogo atual (`Pc.Venda > 0`). Produto com venda histórica e fora do catálogo ativo é **excluído** de tudo, inclusive da soma do fornecedor. Não há `activeOnly`, campo `ativo` nem selo "Inativo". Produto com venda e sem cadastro também é excluído (P-072.3 deixa de existir; `descricao` nunca é `null`).
- Efeitos técnicos: o filtro acontece na carga (SKU fora do catálogo ativo é descartado enquanto o agregado é lido), o snapshot fica menor, `TND-003` só ocorre por troca de Mês-Base ou por mudança do catálogo entre cargas, e a primeira data de venda continua global.
- **Consequência de negócio (registrada):** o **histórico de um produto descontinuado não entra em nenhum total**. Dois efeitos esperados: (1) "parou de vender" (−100%) deixa de aparecer para produtos retirados de linha, que é justamente o caso que o Analista queria enxergar em P-072.2; (2) o total e o % de um fornecedor que descontinuou produtos ficam **superestimados para cima** (a janela anterior perde o volume dos descontinuados, então o fornecedor parece crescer mais, ou cair menos, do que o faturamento real). O relatório de B-14 dimensiona isso (total do mês com e sem restrição aos ativos).

---

## 3. Alternativas Consideradas

1. **Manter a feature dentro do módulo `analytics` (1ª versão):** reaproveitava cache, handlers, shell e componentes, mas acoplava a entrega à Fase 1 não commitada. Descartada pelo usuário.
2. **Uma consulta SQL por Mês-Base:** menos memória, mas dispara o banco a cada mudança de mês-base (proibido por P-083.5). Descartada.
3. **Fornecedor na SQL (`JOIN Produto`, `GROUP BY Fornecedor`):** quebra a projeção mínima (P-085.1) e impede a contribuição por SKU. Descartada (P-093).
4. **Filtrar inativos na SQL do agregado (`WHERE [Cod Produto] IN (SELECT [Codigo] ... WHERE [Pc.Venda] > 0)`):** reduziria linhas, mas introduz referência a `Produto` no agregado (CA-40) e acopla a carga. Filtrar em Python durante a leitura em blocos dá o mesmo ganho de memória retida.
5. **Guardar o agregado em `pandas.DataFrame`/`numpy`:** a Fase A trabalha ~1,4 mil SKUs numa janela e a Fase B ≤ 200 linhas; Python puro mantém o domínio sem dependência pesada e com inteiros exatos. Reavaliar só se T-12 reprovar.
6. **Float64 para quantidade e faturamento:** resíduos geram falsos `NOVO` e empates instáveis. Descartada.
7. **Memoizar linhas por `(baseMonth, metric)`:** ~2 MB por chave e lógica de descarte; a Fase A/B já barateia a requisição. Descartada por ora.
8. **Handlers globais de erro registrados em `api.py` (`register_trend_error_handlers`):** colidem com o handler global de `RequestValidationError` da Fase 1 quando ambas estiverem em `main`. Descartada (DA-09).
9. **Duas rotas de lista (`/products`, `/suppliers`) em vez de `groupBy`:** melhor tipagem nativa, mas contradiz as regras e o Design Plan (P-088.4, C-34, CA-28). Resolvido com `Union` e `meta.agrupamento`. Se o usuário preferir duas rotas, a mudança é local ao router e ao `sales-trend.service.ts`.
10. **Extrair já um `src/core/` compartilhado (paginação, texto, snapshot):** exigiria mexer em código que a Fase 1 também usará e criar dependência cruzada. Adiada para o terceiro consumidor.
11. **Reutilizar o cache/catálogo de `inventory` (`get_inventory_catalog`) ou de `pricing` (`_DATA_CACHE`):** acopla contextos delimitados, usa catálogo completo (inclui inativos) e arrasta o pré-aquecimento do `pricing`. Descartada.
12. **Pré-aquecer o snapshot no `lifespan`:** somaria ao pico de partida (já ~3 GB com o `pricing`). Carga preguiçosa.
13. **Rota de metadados do seletor de Mês-Base:** o `meta` da lista já traz o necessário. Descartada (YAGNI).

---

## 4. Consequências e Trade-offs

- **Pontos Positivos:**
  - Módulo e feature Angular independentes: podem ser mesclados em qualquer ordem em relação ao cross-sell; zero import de arquivo da Fase 1.
  - Uma varredura SQL, ~44 mil linhas lidas, ~3 a 6 MB residentes; trocar métrica, Mês-Base, visão, ordenação ou expandir fornecedor **nunca** toca o banco (CA-24, CA-51).
  - Resultados exatos e determinísticos (inteiros e `Fraction`); fecho da conta dos filhos testável sem tolerância.
  - Erros `TND-001..005` autocontidos e sem registro global: não colidem com nenhum handler de outro módulo.
  - Apenas 3 edições pequenas em arquivos existentes (`api.py`, `app.routes.ts`, `navbar.component.html`).
  - O agregado e o snapshot são reaproveitáveis como `monthly_sales` pelas Fases 3, 4 e 6.
- **Pontos Negativos / Débito Técnico Aceito:**
  - Duplicação deliberada de utilitários (paginação, normalização de texto, arredondamento, lock de snapshot, `_execute_readonly`, componentes de UI) com a Fase 1; extrair para `src/core`/`shared` no terceiro consumidor.
  - Histórico de produtos descontinuados fora de qualquer total (DA-16): fornecedores que descontinuaram produtos aparecem com crescimento inflado.
  - Fornecedor vale o do catálogo atual para todo o histórico (A-17); mês corrente congelado até 6 h (A-14).
  - A 1ª requisição após o TTL espera a carga (alguns segundos).
  - `fornecedorChave` não é estável se o ERP renomear o fornecedor (o detalhe responde `TND-003`; a tela recolhe a linha com aviso, P-086.7).
  - O pico de ~3 GB do `pricing` no pré-aquecimento continua sendo o risco real do limite de 2 Gi; a Tendência não o agrava de forma mensurável, mas também não o resolve (item para o `devops`).
  - Preexistente em `main` e fora do escopo: `custom_404_handler` de `src/api.py` usa `Response` sem importá-lo.

---

## 5. Riscos

| # | Risco | Prob. | Impacto | Mitigação |
| :-: | :--- | :-: | :-: | :--- |
| R-2 | Pico de memória do processo (pricing ~3 GB) derruba o Cloud Run | Alta (preexistente) | Alto | Medição B-14/T-12 no PR; escalar ao `devops` (Etapa 5); carga preguiçosa; a Tendência acrescenta ~25 MB de pico |
| R-3 | **Conflito de merge** com a Fase 1 em `src/api.py`, `app.routes.ts` e `navbar.component.html` (as duas features editam as mesmas regiões); `styles.scss` (token `--navbar-height`) tende a não conflitar | Alta | Baixo (textual, aditivo) | Edições de 1 a 4 linhas cada (DA-13). **Resolução:** manter as duas entradas (união) nas três regiões; conferir que `api.py` registra os dois routers e que o curinga `**` permanece por último; rodar `pytest` e `ng test` após o merge |
| R-4 | `Valor Venda`/`Qtd Venda` com mais casas que o esperado ou tipo `float` com ruído | Baixa | Médio | `Decimal(str())` meio-para-cima em escala 10^4; reconciliação com tolerância documentada (DA-14) |
| R-5 | Grafias duplicadas de fornecedor ou maior fornecedor com centenas de SKUs | Média | Baixo | Normalização (P-089.1) e detalhe paginado (P-092); contagens no CLI (A-18, A-20) |
| R-6 | Limiares de "Base baixa" mal calibrados (A-7) | Média | Baixo (informativo) | Percentis no CLI antes do release; constantes nomeadas |
| R-7 | Variação de calendário (fev vs jan) e fins de semana desiguais distorcem janelas curtas (A-1, A-10) | Certa | Baixo | Limitação registrada nas regras; selo "Base parcial" onde há normalização |
| R-8 | `route_class` não captura algum `RequestValidationError` (ex.: erro dentro de dependência) | Baixa | Baixo | T-08 cobre query, tipo, faixa, `Literal` e `AfterValidator` |
| R-9 | Estado na URL (D-12) vazando dado pessoal ou divergindo do store | Baixa | Baixo | Só parâmetros de consulta sem PII; `trend-url.ts` com teste de ida e volta; sem storage |
| R-10 | **Viés pelos inativos fora (DA-16):** fornecedor que descontinuou produtos parece crescer mais do que cresceu | Média | Médio (leitura de negócio) | Registrado; B-14 dimensiona o impacto (total com e sem restrição); a tela pode explicar na legenda "Como ler a tabela" (decisão do Designer) |
| R-11 | **Worktree sem `.agents/`** (gitignored): agentes no worktree não veem regras, ADR nem contrato | Alta (se não tratado) | Médio | Junção de diretório ou cópia de `.agents/` e `AGENTS.md` (DA-13); preparar `.env`, venv e `npm install` |
| R-12 | Mudança de massa sintética pelo Analista (ex.: SKU 1008 deixa de ser listado por ser inativo) altera exemplos do contrato | Média | Baixo | Os exemplos do contrato assumem o catálogo ativo sem o 1008 e sem SKU sem cadastro; recalcular se a massa mudar (T-09 compara os exemplos) |

---

## 6. Pontos para decisão no checkpoint

Descartados por esta revisão: **DC-1** (commit da Fase 1 como pré-requisito), **DC-4** (edições em arquivos da Fase 1), **R-1** e **R-8** antigos (resolvidos pela independência).

| # | Ponto | Proposta |
| :-: | :--- | :--- |
| DC-2 | Lista única com `groupBy` (proposta) ou duas rotas (`/products`, `/suppliers`) | Lista única; reverter é barato, mas altera regras, testes e Design Plan |
| DC-3 | Rotas operacionais `GET /sales-trend/health` e `POST /sales-trend/reload` (P-083.2, P-083.6, Q-14) | Aceitar; sem botão de recarga na tela |
| DC-5 | `meta.totaisPorVisao` e `meta.total` ("Todos os produtos") no 1.0.0 | Aceitar (custo baixo; o Designer decide se usa) |
| DC-6 | **Criar o worktree** `../fitoherb-sales-trend` a partir de `main` com junção de `.agents` (DA-13), em vez de commitar/stashar a Fase 1 para trocar de branch | Aceitar; é a única forma de não mexer na Fase 1 em andamento |
| DC-7 | Reconhecer a consequência de DA-16 (descontinuados fora de todo total; fornecedor com crescimento inflado) | Aceitar, ou reverter para uma opção explícita no futuro |
| DC-8 | Premissas novas de arquitetura: AR-1 (desempate pós-piso), AR-2 (`SEM_BASE` sem selos), AR-3 (`baseParcial` por janela em todo status), AR-4 (chave `f:`), AR-9 (`view=new` ignora `sortDir`), AR-10 (`meta.total`), AR-11 (`limit` 20 no detalhe), AR-12 (`first_sale_date` global, não só dos ativos) | Aceitar; todas aditivas ou de desempate |
| DC-9 | Duplicação deliberada com a Fase 1 (utilitários e componentes) e extração futura para `src/core`/`shared` | Aceitar |
