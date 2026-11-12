# STATE (isolado) — Arquitetura da Tendência de Vendas (módulo `sales_trend`)

> Estado paralelo ao `STATE.md` da Fase 1 (cross-sell), que **não** foi alterado. Responsável: Arquiteto. Criado em 2026-11-09; **revisado em 2026-11-10** após o checkpoint do usuário. Etapa: 2 (Arquitetura), aguardando checkpoint.
> O slug `analytics-sales-trend` nos nomes dos documentos é **histórico**; o código está em `src/modules/sales_trend/` e `frontend/src/app/features/sales-trend/`.

## Decisões do usuário aplicadas na revisão (checkpoint)

1. **Independência total do cross-sell.** Módulo próprio `src/modules/sales_trend/` e feature Angular `features/sales-trend/` (página `/tendencia-vendas`), branch `feature/sales-trend` a partir de `main`. Nenhum import de `src.modules.analytics.*` nem de arquivos da Fase 1. Rotas sob `/api/v1/sales-trend`; exceções, tratamento de erro, cache/snapshot, busca, paginação, arredondamento e componentes de UI próprios.
2. **Códigos autocontidos:** `ANL-001` → `TND-004` (503), `ANL-002` → `TND-005` (429); `TND-001/002/003` permanecem. Corpo `{error:{code,message,fields}, meta}` definido no próprio contrato (§5).
3. **Inativos fora de tudo:** sem `activeOnly`, sem `ativo`, sem selo "Inativo" nem "Sem cadastro". Só produtos ativos do catálogo atual (`Pc.Venda > 0`) entram na lista, nas somas de fornecedor e em `meta.total`. Consulta de catálogo e estimativa de memória ajustadas (ADR-003 DA-02, DA-03, DA-16).
4. **Premissas A-1..A-5 e A-17..A-19** do Analista aceitas pelo usuário; IDs P-072..P-093 mantidos.
5. **Arquiteto é dono de `tasks/analytics-sales-trend.md`** (reescrito: caminhos, T-/B-/F-, commits sobre `main`, branch).

**Descartados por esta revisão (resolvidos pela independência):** DC-1 (commit da Fase 1 como pré-requisito), DC-4 (edições em arquivos da Fase 1), R-1 (quebra por mudança de símbolo da Fase 1) e R-8 (D-14: editar `ListPager`/`ErrorBanner`/`ResultState`).

## Verificado em `main` (`git show main:<arquivo>`)

- Existe: `src/core/database.py` (`is_readonly_query`, `get_db_connection_string`, `DatabaseSecurityError`), `src/core/auth.py` (middleware global já ligado em `src/api.py`), módulos `pricing`/`inventory` (`api/`, `service/`, `domain/`), `tests/` plano, `requirements.txt` (sem dependência nova necessária).
- **Não** existe: paginação, normalização de texto, arredondamento meio-para-cima, snapshot/cache por TTL, exceções `XXX-NNN`, handlers de erro, `shared/` no frontend (nenhum pager, banner, estado vazio, skeleton, pipes pt-BR).
- Frontend: `app.routes.ts` com rotas eager `pricing`/`inventory` e `**`; navbar com 2 `<li>`; `styles.scss` com os tokens (sem `--navbar-height`); `provideHttpClient()`.
- **Q-17:** `frontend/proxy.conf.json` tem `"/api"` → `http://127.0.0.1:8000` (usado em `angular.json`), que já cobre `/api/v1/sales-trend`. **Sem edição e sem tarefa F-xx.**
- `.agents/` e `AGENTS.md` são **gitignored**: um worktree novo não os contém (junção ou cópia, R-11).

## Artefatos (todos revisados em 2026-11-10)

| Artefato | Caminho |
| :--- | :--- |
| ADR | `.agents/docs/adr/ADR-003-tendencia-vendas.md` (DA-01..DA-16, histórico de revisões, riscos R-2..R-12, DC-2..DC-9) |
| Contrato de API 1.0.0 | `.agents/docs/api_contracts/analytics-sales-trend.md` (rotas `/api/v1/sales-trend`, `TND-001..005`, exemplos recalculados só com produtos ativos; respostas Q-1..Q-17 em §6.1) |
| Checklist técnico | `.agents/docs/tasks/analytics-sales-trend.md` (T-01..T-19, B-01..B-14, F-01..F-12, commits sobre `main`) |

## Decisões de arquitetura (resumo)

- **DA-01:** 8 arquivos de domínio/serviço/repositório/API do módulo e `diagnostics/`; só 4 edições em arquivos de `main`: `src/api.py` (import + `include_router`), `app.routes.ts` (rota lazy `tendencia-vendas`), `navbar.component.html` (1 `<li>`) e `styles.scss` (token `--navbar-height`, D-5).
- **DA-02:** agregado SQL `Cod Produto × mês` (todo o histórico), catálogo **ativo** próprio (`WHERE [Pc.Venda] > 0`, sem preço), carga do catálogo antes do agregado, descarte de SKU fora do catálogo durante a leitura em blocos; primeira data de venda **global** (AR-12).
- **DA-03:** inteiros escalados (`VALUE_SCALE = 10_000`) + máscara de movimento; snapshot residente ≈ 3 a 6 MB, pico de carga ≈ 20 a 30 MB (com ~1,4 mil SKUs ativos retidos de ~1,9 mil lidos).
- **DA-04:** snapshot próprio `sales_trend_cache.py` (voo único, TTL 6 h, `force_reload` com `TND-005`), sem nenhum `analytics_cache.py`; dívida: extrair `SnapshotCache` para `src/core` no terceiro consumidor.
- **DA-06:** cálculo em duas fases; `Fraction` para % e ordenação exata; sem memoização.
- **DA-08:** lista única com `groupBy` + detalhe `supplier-products` + `GET /health` + `POST /reload`.
- **DA-09 (A-13 reavaliada):** sem a Fase 1 o conflito com `XSL-004` some, mas a Fase 1, ao ser mesclada, registra um handler global de `RequestValidationError`, e só pode haver um. Solução mais simples: `TrendAPIRoute` (classe de rota do módulo) traduz **todos** os erros do módulo (validação → `TND-001`, domínio, infraestrutura) sem registro global; `src/api.py` só ganha o `include_router`.
- **DA-12:** estado da consulta nos query params da SPA (Design Plan D-12); componentes de UI próprios; `utils/trend-error.ts`.
- **DA-13:** `git worktree add ../fitoherb-sales-trend -b feature/sales-trend main` (a Fase 1 está não commitada e não deve ser tocada) + junção de `.agents`.
- **DA-16:** inativos fora de tudo e sua consequência de negócio.

## Respostas ao Design Plan (Q-n, contrato §6.1)

Aceitas: Q-1, Q-2, Q-4, Q-5, Q-6, Q-7, Q-8 (agora `descricao` sempre preenchida), Q-9, Q-10, Q-11, Q-12, Q-13 (substituída: universo só de ativos), Q-14 (`GET /sales-trend/health`), Q-15, **Q-16** (`TND-005` só em `POST /reload`, nunca na UI; corpo de `TND-004` fixado com `fields: []`) e **Q-17** (proxy já cobre; sem tarefa). Aceita em parte: Q-3 (recusado o boolean `porDia`; `contribuicaoValor` é por dia se e somente se `baseParcial`).

## Premissas de arquitetura novas (ADR-003 DC-8, a confirmar)

AR-1 desempate pós-piso; AR-2 `SEM_BASE` sem selos; AR-3 `baseParcial` por janela em todo status; AR-4 chave `f:`; AR-9 `view=new` ignora `sortDir`; AR-10 `meta.total`; AR-11 `limit` 20 no detalhe; AR-12 primeira data de venda global (não só dos ativos).

## Pontos abertos (priorizados)

1. **DC-6 (operacional):** criar o worktree a partir de `main` e a junção de `.agents/` (ou cópia); preparar `.env`, venv e `npm install` nele. Sem isso os agentes não enxergam as regras.
2. **DC-7:** reconhecer a consequência de excluir inativos: o histórico de produtos descontinuados não entra em nenhum total; o "parou de vender" de produto retirado de linha deixa de aparecer; fornecedor que descontinuou produtos aparece com crescimento inflado (R-10). B-14 dimensiona (total do mês com e sem restrição).
3. **R-3 (merge):** `src/api.py`, `app.routes.ts` e `navbar.component.html` também são editados pela Fase 1; resolver mantendo as duas entradas; rodar testes e `ng build` depois.
4. **R-2:** o processo da API chega a ~3 GB no pré-aquecimento do `pricing` (preexistente, `STATE.md`), acima do limite de 2 Gi; a Tendência acrescenta ~20 a 30 MB de pico, mas só a medição (B-14/T-13) confirma. Escalar ao `devops` (Etapa 5).
5. **DC-2 e DC-3:** lista única com `groupBy` (vs duas rotas); rotas `health` e `reload` aceitas.
6. **DC-8:** confirmar as premissas AR-*; **DC-9:** duplicação deliberada com a Fase 1 e extração futura para `src/core`/`shared`.
7. **Dados reais a conferir (B-14):** tipo e casas de `Valor Venda`/`Qtd Venda`, SKUs do maior fornecedor (A-18), grafias duplicadas de fornecedor (A-20), calibração de "base baixa" (A-7).
8. **Acréscimos além do texto das regras:** `meta.total`, `meta.parametros`, `meta.totaisPorVisao`, `GET /health`, `limit` 20 no detalhe, `TND-002.fields`. O Arquiteto não editou `business_rules/`; o Analista decide se registra P-094+ ou notas.
9. Preexistente em `main`, fora do escopo: `custom_404_handler` de `src/api.py` usa `Response` sem importá-lo.

## Hand-off

- `tester`: começar por T-01 (massa sintética, com 1008 inativo e 1009 sem cadastro só no agregado bruto) e T-02/T-03; testes só de arquivos novos podem preceder o worktree.
- `developer` backend: B-02 a B-08 (domínio) sem tocar `main`; B-09/B-13 após B-01; B-13 edita `src/api.py`.
- `developer` frontend: F-01..F-03, F-06..F-12 sem tocar `main`; F-04 edita `app.routes.ts` e `navbar.component.html`; F-05 edita `styles.scss`.
- `reviewer`: conferir independência (nenhum import de `analytics`), P-085.1/P-085.2 e o relatório de B-14. Bypass de `security` e `privacy_officer` mantido (P-085).
