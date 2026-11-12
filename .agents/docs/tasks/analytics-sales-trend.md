# Entidade / Feature: Tendência de Vendas por Item (módulo `sales_trend`)

> O slug `analytics-sales-trend` dos documentos é **histórico** (nasceu como aba do módulo `analytics`). Desde o checkpoint de 2026-11-09 a feature é **independente do cross-sell**: backend em `src/modules/sales_trend/`, frontend em `frontend/src/app/features/sales-trend/`, página `/tendencia-vendas`, branch `feature/sales-trend` a partir de `main`.

Este documento centraliza o escopo, as especificações e as etapas de execução da Tendência de Vendas: tabela de todos os produtos ativos (ou fornecedores) com a variação % de vendas em 1, 3, 6 e 12 meses.

| Campo | Valor |
| :--- | :--- |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-sales-trend.md` (P-072 a P-093, CA-01 a CA-40, premissas A-1 a A-26) |
| **Glossário** | `.agents/docs/GLOSSARY.md`, seção 4 |
| **Plano mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` (§2.3 devoluções, §2.5 agregar no SQL, §2.7 contrato, §2.8 LGPD, §2.9 convenções) |
| **ADR** | `.agents/docs/adr/ADR-003-tendencia-vendas.md` (DA-01 a DA-16, R-2 a R-12, DC-2 a DC-9) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-sales-trend.md` (versão 1.0.0; rotas sob `/api/v1/sales-trend`) |
| **Design Plan** | `.agents/docs/design/plans/analytics-sales-trend.md` (página própria `/tendencia-vendas`) |
| **Tipo na esteira** | T1 (Full-Stack: FastAPI + Angular), módulo novo e independente |
| **Branch** | `feature/sales-trend`, criada a partir de **`main`** (sem a Fase 1 do cross-sell). Ver 4.0 |
| **Faixa de IDs** | P-072 a P-093 (IDs mantidos) |
| **Status** | Etapa 1 concluída; Etapa 2 (Arquitetura) revisada em 2026-11-10 com as decisões do usuário (independência, `TND-004/005`, só produtos ativos); premissas Altas aceitas pelo usuário (A-1 a A-5, A-17 a A-19); aguardando o checkpoint das decisões DC-2 a DC-9 do ADR |
| **Dono deste arquivo** | Arquiteto (assumido em 2026-11-10; o Analista mantém seções 1 e 3) |

---

## 1. Dúvidas Resolvidas (Especificação e Arquitetura)

- **Dúvida:** Qual métrica? **Decisão (usuário):** ambas, com alternador: **quantidade líquida** ou **faturamento líquido (R$)**. Padrão: faturamento (P-073).
- **Dúvida:** Como são as janelas de 1, 3, 6 e 12 meses? **Decisão (usuário):** X meses para trás a partir de um **Mês-Base**, independentemente do ano; a janela atual termina no Mês-Base e é comparada com a imediatamente anterior, de mesmo tamanho (P-075).
- **Dúvida:** O Mês-Base é fixo? **Decisão (usuário):** definível; padrão = último mês **completo** (out/2026 em 2026-11-09); pode incluir o mês corrente (parcial) (P-074).
- **Dúvida:** Quais itens aparecem? **Decisão (usuário):** todos os produtos **ativos**, não só um top N; paginada e ordenável por qualquer coluna de %; atalhos "Maiores altas / Maiores quedas / Novos" (P-080, P-081).
- **Dúvida:** Por produto ou por fornecedor? **Decisão (usuário):** alternador `groupBy = product | supplier` (padrão produto); por fornecedor, % sobre a soma líquida, linhas expansíveis com variação própria e contribuição (P-088 a P-093).
- **Dúvida:** Janela incompleta (base desde 07/01/2025; mês corrente parcial)? **Decisão (premissas A-1 a A-3, aceitas):** totais se as duas janelas completas; média diária + "Base parcial" se alguma incompleta; anterior com cobertura < 50% = "Sem base"; o dia corrente fica fora (P-076).
- **Dúvida:** Casos de borda de itens? **Decisão (A-4 revisada, A-5 a A-7):** "Novo" fora da ordenação por %; parou = −100,0%; líquido negativo vale 0 (piso zero) com selo; "Base baixa" informativa e `minVolume` opcional (P-077 a P-079).
- **Dúvida:** Fornecedor (troca, sem fornecedor, filhos)? **Decisão (A-17 a A-19, aceitas):** vale o fornecedor do catálogo atual; "Sem fornecedor" é grupo normal; filhos por rota de detalhe paginada; contribuição em p.p. e valor (P-089 a P-093).
- **Dúvida (checkpoint 2026-11-09, usuário): a tendência depende do cross-sell? Decisão:** **não**. Módulo e feature Angular próprios, desenvolvidos em `feature/sales-trend` a partir de `main`; nenhum import de `src.modules.analytics.*` nem de arquivos da Fase 1; exceções, tratamento de erro, cache, busca e normalização próprios (ADR-003 DA-01, DA-09, DA-10).
- **Dúvida (checkpoint): códigos de erro? Decisão:** autocontidos. `ANL-001` → `TND-004` (503, base indisponível); `ANL-002` → `TND-005` (429, recarga recente); `TND-001` (400), `TND-002` (422) e `TND-003` (404) permanecem.
- **Dúvida (checkpoint): produtos inativos? Decisão:** **fora de tudo.** Só produtos ativos do catálogo atual (`Pc.Venda > 0`) entram na lista e nas somas de fornecedor. Sem `activeOnly`, sem campo `ativo`, sem selo "Inativo" e sem "Sem cadastro". **Consequência registrada** (ADR-003 DA-16, R-10): o histórico de produto descontinuado não entra em nenhum total; fornecedor que descontinuou produtos aparece com crescimento inflado.
- **Dúvida (Arquiteto, A-13): `TND-001` frente ao handler de validação?** O conflito com `XSL-004` deixou de existir (sem a Fase 1). **Decisão:** `TrendAPIRoute` (classe de rota do módulo) traduz todos os erros do módulo, sem registro global, para não colidir com o handler global de `RequestValidationError` da Fase 1 quando as duas estiverem em `main` (ADR-003 DA-09).
- **Dúvida (Designer, Q-17): o proxy do dev server cobre `/api/v1/sales-trend`? Decisão:** sim. `frontend/proxy.conf.json` de `main` tem `"/api"` → `http://127.0.0.1:8000`; nenhuma edição nem tarefa.

### Premissas
- **Aceitas pelo usuário:** A-1 a A-5 e A-17 a A-19.
- **Médias e baixas** (A-6 a A-16, A-20 a A-26): valores propostos do Analista valem; A-7 (limiares de base baixa) é calibrada no relatório de B-14.
- **Novas de arquitetura** (ADR-003 DC-8, a confirmar): AR-1 desempate pós-piso; AR-2 `SEM_BASE` sem selos; AR-3 `baseParcial` por janela em todo status; AR-4 chave `f:`; AR-9 `view=new` ignora `sortDir`; AR-10 `meta.total`; AR-11 `limit` padrão 20 no detalhe; AR-12 primeira data de venda global.

---

## 2. Tarefas e Etapas de Desenvolvimento

### Tarefa 1: Backend — módulo `sales_trend` (domínio, repositório, cache e API)

**Descritivo Detalhado:**
Criar `src/modules/sales_trend/` (api, service, domain, repository, diagnostics): agregado SQL mensal por SKU (VENDA + devoluções, líquido, só leitura) restrito ao catálogo ativo, snapshot em memória próprio com TTL de 6 h e voo único, domínio puro que calcula janelas, cobertura, base parcial, % de variação, estados da célula, sinalizadores, agrupamento por fornecedor com contribuições, ordenação, filtros e paginação; rotas sob `/api/v1/sales-trend` (lista com `groupBy`, detalhe do fornecedor, health e recarga) no envelope `data`/`meta`, com os erros `TND-001` a `TND-005`. Toda a lógica numérica vive no domínio; o router só recebe, chama o service e devolve (`.agents/rules/architecture-business-logic-isolation-rules.md`).

**Critérios de Aceite:**
- [ ] Janelas atual/anterior de 1, 3, 6 e 12 meses a partir do Mês-Base (padrão = último mês completo; aceita o mês corrente; valida formato, futuro e anterior à base) conforme P-074 e P-075 (CA-01, CA-19, CA-20).
- [ ] Quantidade e faturamento líquidos abatem devoluções (`DEVOLU%`, sinal original); trocar a métrica não relê o banco (P-073; CA-02, CA-05, CA-24).
- [ ] Cobertura, média diária, "Base parcial", "Sem base" (< 50%) e dia corrente fora da base conforme P-076 (CA-03, CA-04, CA-06).
- [ ] % de variação = (atual − anterior) ÷ |anterior| × 100, 1 casa, meio para cima, piso zero e piso de −100% (P-077; CA-08, CA-10, CA-21), com aritmética exata (inteiros escalados e `Fraction`).
- [ ] Estados `VARIACAO`, `NOVO`, `SEM_MOVIMENTO`, `SEM_BASE`; "Novo" fora do cálculo de ordenação por % mas presente na tabela (P-078; CA-07, CA-09).
- [ ] `baseBaixa` e `minVolume` (padrão 0) conforme P-079 (CA-11, CA-12).
- [ ] Ordenação determinística por coluna de %, asc/desc, desempate por |Δ| e código; visões `all|rising|falling|new`; busca por código/descrição com normalização própria; paginação `limit` 50 (máx 200) e `offset` (P-080, P-081; CA-13 a CA-18).
- [ ] **Só produtos ativos do catálogo (`Pc.Venda > 0`) com movimento no período** aparecem; produto inativo ou sem cadastro (SKUs 1008 e 1009 da massa) fica fora da lista **e das somas de fornecedor**; SKU com venda só depois do Mês-Base não aparece (P-072; CA-13, CA-14). Não existe `activeOnly`.
- [ ] `groupBy = supplier`: % do fornecedor sobre a soma líquida (nunca média das %); "Sem fornecedor" só para produto ativo sem fornecedor; fornecedor "Novo" só com toda a janela anterior em zero; base parcial/sem base herdada; ordenação, `q` por nome, `view`, `minVolume` e paginação de fornecedores (P-088, P-089, P-091; CA-28 a CA-33, CA-36 a CA-38).
- [ ] Detalhe do fornecedor: rota paginada (padrão 20), filhos com variação própria e contribuição (p.p. e valor), `meta.fornecedor`, `TND-003`; soma dos filhos = linha do fornecedor (P-090, P-092; CA-34, CA-35, CA-39).
- [ ] `meta.total` ("Todos os produtos"), `meta.totaisPorVisao`, `meta.parametros` e `meta.janelas[]` conforme o contrato (Q-1, Q-4, Q-9).
- [ ] Agregado no grão `Cod Produto × mês` sem o fornecedor na SQL; catálogo ativo próprio; SQL por `is_readonly_query`, sem `CONCAT`, com parâmetro vinculado e sem `Cod Cliente`/`Pedido` (P-073.3, P-093; CA-26, CA-40).
- [ ] Snapshot com voo único, TTL 6 h, falha preserva o anterior e mês corrente congelado até a recarga com `dataReferencia`/`ultimoDiaCoberto` do snapshot (P-083; CA-23, CA-25); `GET /health` não carrega; `POST /reload` com `TND-005` em 15 min.
- [ ] Envelope `data`/`meta` em `camelCase`; erros `TND-001` (400), `TND-002` (422), `TND-003` (404), `TND-004` (503) e `TND-005` (429) no corpo `{error:{code,message,fields}}`, sem stacktrace nem eco de valores (P-082; CA-19, CA-22); validação de `pricing`/`inventory` inalterada.
- [ ] Nenhum dado de cliente na consulta, na resposta nem nos logs; logs só com contagens (P-085; CA-26).
- [ ] Nenhum import de `src.modules.analytics.*`, `pricing` ou `inventory`; domínio sem `pyodbc`, `fastapi` ou `src.core.database`.
- [ ] Constantes nomeadas no topo de `domain/sales_trend.py`, sem números mágicos; funções ≤ ~30 linhas, no máximo 3 parâmetros (plano §2.9).
- [ ] Reconciliação com o banco, calibração dos limiares de base baixa e medição de memória reportadas no PR (P-087.3; CA-27).

**Etapas de Execução (Checklist Técnico):** ver seção 4.1 (testes, `T-01` a `T-13`) e 4.2 (implementação, `B-01` a `B-14`).

**Audit (Testes e Validação):**
*(A ser preenchido pelo Tester. Base: massa sintética e CA-01 a CA-40, incluindo devolução na série, janela de 12m parcial, mês-base parcial, item novo, fornecedor com produto em alta e outro em queda, soma dos filhos igual à linha do fornecedor, produto sem fornecedor e produtos inativos/sem cadastro fora de tudo.)*
- [ ] **Cenário 1:** _(Tester)_

---

### Tarefa 2: Frontend — página "Tendência de Vendas" (`/tendencia-vendas`)

**Descritivo Detalhado:**
Criar `frontend/src/app/features/sales-trend/` com página própria (sem shell de abas), rota lazy `/tendencia-vendas` e item na navbar: tabela paginada e ordenável por qualquer das 4 colunas de % (1, 3, 6, 12 meses); alternador de métrica (faturamento padrão / quantidade); seletor de Mês-Base (mês corrente rotulado "parcial até DD/MM", padrão último mês completo); alternador **Por produto / Por fornecedor**; controle de visão (Todos / Maiores altas / Maiores quedas / Novos); busca; "Volume mínimo" com a unidade da métrica. Na visão por fornecedor, linhas expansíveis que carregam o detalhe paginado sob demanda e exibem variação própria e contribuição (p.p. e valor). Selos com texto ("Novo", "Base parcial", "Base baixa", "Sem base", "Devoluções superam vendas") e direção por ícone + sinal, não só cor. Nota "apenas produtos ativos do catálogo". Estados: skeleton, vazio, erro e "histórico anterior insuficiente". Componentes só desenham; formatação pt-BR e estado ficam em service/utilitário. Paginação, banner de erro, estado vazio, skeleton, `SegmentedControl` e formatação pt-BR são **próprios da feature** (não existem em `main`). O Design Plan é a especificação visual.

**Critérios de Aceite:**
- [ ] A tabela mostra sempre as 4 colunas de % e os cabeçalhos de período vindos de `meta.janelas` (ex.: "ago–out/26 vs mai–jul/26"); clique no cabeçalho alterna desc/asc (P-080, P-084.3, P-086).
- [ ] Percentuais em pt-BR com sinal explícito (`+50,0%`, `−100,0%` com U+2212, `0,0%`), rótulos "Novo" e "—"; faturamento `R$ 1.234,56`; quantidade com milhar (P-086.1, P-086.2).
- [ ] Selos e tooltips com os períodos, valores atual/anterior e, em base parcial, média por dia e dias cobertos (P-086.2, P-086.3); números vindos de `meta.parametros`, nunca fixos na copy.
- [ ] Alternador de métrica e de agrupamento preservam Mês-Base e ordenação, sem recarga do banco (P-086.7, P-088, P-093.3).
- [ ] Seletor de Mês-Base usa `mesBaseMinimo`, `mesBaseMaximo` e `mesBasePadrao` da API; mês corrente indicado como parcial; "Dados até DD/MM/AAAA" visível (P-074, P-086.4, P-086.5).
- [ ] Controle de visão (altas/quedas/novos) com `meta.totaisPorVisao` e ordenação funcionam nas duas visões (P-080.4, P-091).
- [ ] Linha de fornecedor expansível com detalhe paginado (20 por página) e contribuição em p.p. e valor; recolhe com aviso em `TND-003`; recarrega a lista se `dataReferencia` do detalhe divergir (P-092, P-086.7).
- [ ] Linha "Todos os produtos" (`meta.total`) quando presente.
- [ ] Estados skeleton, vazio (com "limpar filtros"), erro (`TND-001/002/003/004`; `TND-005` só por defesa) e "histórico anterior insuficiente" implementados (P-086.5, P-078.7). **Sem** controle "Somente ativos", selo "Inativo" ou "Sem cadastro".
- [ ] Estado da consulta nos query params da URL (Design Plan D-12), sem storage.
- [ ] Nenhum `any`; sem lógica de negócio no componente; testes de componente com serviço mockado cobrindo carregando, vazio e erro (plano §2.9, §2.10).
- [ ] Acessibilidade: direção não depende só de cor; foco e navegação por teclado nos cabeçalhos ordenáveis e nas linhas expansíveis.
- [ ] Nenhum import de `features/analytics/**`; link "Tendência de Vendas" na navbar (também no menu mobile).

**Etapas de Execução (Checklist Técnico):** ver seção 4.3 (testes, `T-14` a `T-19`) e 4.4 (implementação, `F-01` a `F-12`).

**Audit (Testes e Validação):**
*(A ser preenchido pelo Tester e pelo UX Reviewer.)*
- [ ] **Cenário 1:** _(Tester)_

---

## 3. Definition of Done (DoD)

- [x] Premissas de prioridade **Alta** (A-1 a A-5, A-17 a A-19) aceitas pelo usuário (2026-11-09).
- [ ] Todas as regras `P-072` a `P-093` com testes automatizados e cobertura ≥ 80%; CA-01 a CA-26 e CA-28 a CA-40 passando com a massa sintética; CA-27 (reconciliação e calibração) no PR.
- [x] Contrato `api_contracts/analytics-sales-trend.md` (envelope `data`/`meta`, lista, detalhe, health, recarga, `TND-001..005`) e Design Plan publicados antes do TDD e da implementação.
- [ ] Termos alinhados ao `.agents/docs/GLOSSARY.md` (seção 4).
- [ ] Nenhuma lógica de negócio em router/componente; domínio sem I/O (sem `pyodbc`/`core.database`).
- [ ] Nenhum import de `src.modules.analytics.*` nem de `features/analytics/**`; as únicas edições em arquivos de `main` são as listadas em 4.0.
- [ ] Nenhum dado de cliente na consulta, na resposta ou nos logs; sem stacktrace nas respostas de erro.
- [ ] Quality Gate (reviewer, ux_reviewer) aprovado; Auto-Healer até 3 tentativas antes de escalar.
- [ ] Commits atômicos em Conventional Commits rastreando `P-XXX`, sobre `main`; PR com reconciliação, calibração de "base baixa", contagem do maior fornecedor, medição de memória e o impacto dos produtos inativos fora (R-10).

### Bypasses sugeridos (a registrar pelo Orquestrador; o Analista não altera `STATE.md`)
- **product_owner:** demanda única e coesa, escopo já fatiado por decisão do usuário.
- **dba:** somente leitura em `Externo01.Vendas` e `Externo01.Produto`, sem schema nem migration.
- **ai_specialist:** cálculo determinístico, sem modelo.
- **privacy_officer:** sem dado pessoal (P-085); checagem fica com o `reviewer`.
- **security dedicado:** sem autenticação nem superfície crítica nova além de rotas somente leitura. (Arquiteto: as rotas operacionais `GET /sales-trend/health` e `POST /sales-trend/reload` ficam atrás do mesmo `HTTPBasicAuthASGIMiddleware` global, o `POST` é limitado a uma recarga a cada 15 min e nenhuma delas recebe corpo nem aceita entrada que chegue ao SQL; o bypass continua válido.)

---

## 4. Checklist Técnico Atômico (Arquiteto, Etapa 2, revisado em 2026-11-10)

> **Convenções.** `T-xx` = testes (Tester, escritos ANTES do código; backend em `tests/sales_trend/`, frontend em `*.spec.ts`); `B-xx` = backend; `F-xx` = frontend. A numeração é **local a esta feature**; em commits e PR cite como `[TND T-05]`, `[TND B-08]`. `[PARALLEL]` marca o que pode rodar em paralelo entre as frentes Backend e Frontend, pois ambas dependem só do contrato 1.0.0. Cada `B-xx` só começa depois dos `T-xx` que ele faz passar. Funções de até ~30 linhas, no máximo 3 parâmetros, early return, constantes nomeadas, docstring de topo em todo arquivo (ADR-003 DA-15).
>
> **Regra de independência:** nenhum arquivo novo importa `src.modules.analytics.*`, `src.modules.pricing.*`, `src.modules.inventory.*` nem `features/analytics/**`. Dependências permitidas de `main`: `src.core.database` (`is_readonly_query`, `get_db_connection_string`, `DatabaseSecurityError`), `src.core.auth` (já global), `styles.scss` (tokens). Verificar com `git show main:<arquivo>`; a working tree da Fase 1 não vale.

### 4.0 Pré-requisitos, branch e edições em arquivos de `main`

- [ ] **B-01 (não é código): branch e ambiente.** Criar `feature/sales-trend` a partir de **`main`** sem mexer na working tree da Fase 1 (que tem alterações **não commitadas** em `feature/analytics-cross-sell`): `git worktree add ../fitoherb-sales-trend -b feature/sales-trend main`. **`.agents/` e `AGENTS.md` são gitignored**, então o worktree não os tem: criar uma junção (`mklink /J <worktree>\.agents <repo>\.agents`) ou copiar as pastas; preparar `.env`, ambiente Python e `npm install` (`frontend/`). Rodar `pytest` e `npx ng test --watch=false --browsers=ChromeHeadless` na base e registrar o resultado. *Bloqueia tudo; os testes T-01 a T-19 (só arquivos novos) já podem ser escritos no worktree.*
- **Edições em arquivos existentes de `main` (as únicas; todas aditivas e de poucas linhas):**

| Arquivo | Edição | Tarefa | Conflito com a Fase 1 |
| :--- | :--- | :--- | :--- |
| `src/api.py` | 1 `import` de `sales_trend_router` + 1 `app.include_router(sales_trend_router, prefix="/api/v1")` | B-13 | **Sim** (a Fase 1 edita as mesmas linhas). Resolver mantendo as duas |
| `frontend/src/app/app.routes.ts` | 1 rota `{ path: 'tendencia-vendas', loadComponent: ... }` **antes** do curinga `**` | F-04 | **Sim** (a Fase 1 adiciona a rota `analytics`). Resolver mantendo as duas, curinga por último |
| `frontend/src/app/core/layout/navbar/navbar.component.html` | 1 `<li class="nav-item">` "Tendência de Vendas" após o de "Estoque e Compras" | F-04 | **Sim** (a Fase 1 adiciona "Análises de Vendas"). Resolver mantendo os dois |
| `frontend/src/styles.scss` | token `--navbar-height: 64px` em `:root` e `58px` em `@media (max-width: 768px)` (Design Plan D-5) | F-05 | Não (a Fase 1 não altera este arquivo) |
| `frontend/proxy.conf.json` | **nenhuma** (a entrada `"/api"` já cobre `/api/v1/sales-trend`; Q-17) | — | — |

  *Instrução de resolução (ADR-003 R-3):* em conflito, manter **ambas** as entradas; depois do merge rodar `pytest`, `ng test` e `ng build` e conferir que `api.py` registra os dois routers.

### 4.1 Testes de backend (Tester, TDD, domínio sem banco) — `tests/sales_trend/`

- [ ] **T-01:** `tests/sales_trend/__init__.py` e `trend_sample.py` — **massa sintética compartilhada** (seção 5 das regras): builder do `MonthlySales` com os SKUs 1001 a 1010, o catálogo ativo (`LABORATÓRIO ALFA/BETA/GAMA`, 1004 com `Fornecedor` nulo, 1006 com `"   "`), o **SKU 1008 inativo e o 1009 sem cadastro presentes só no agregado bruto** (para provar que são descartados), `reference_date = 2026-11-09`, `first_sale_date = 2025-01-07`, valores nas duas métricas (R$ 10,00/un; 1001 em out/26 a R$ 12,00) e um gerador de fornecedor com 120 SKUs (CA-39). Mais `test_sample.py` que confere os totais da massa (autoteste da fixture). *Dep.: nenhuma.*
- [ ] **T-02:** `test_month_windows.py` — janelas atual/anterior de 1, 3, 6, 12 meses com virada de ano (CA-01, Mês-Base `2026-10` e `2026-11`); `diasJanela` (fev bissexto e não bissexto); dias cobertos (CA-03: 298 de 365; CA-04: 8 de 30; CA-06: `2025-06` 0% e `2025-07` 25 de 184 = 13,6%; `2025-01`); corte de 50% (exatos 50% **não** é `SEM_BASE`); `ultimoDiaCoberto = referência − 1`; Mês-Base futuro/anterior/mês corrente no dia 1 (CA-20) como funções puras de validação; `baseMonth = 0000-01` não levanta `ValueError`. *Dep.: T-01.*
- [ ] **T-03:** `test_domain_utils.py` — `pagination` (CA-18: `limit=3&offset=3`; 120 itens `limit=50&offset=100` → 20 itens, `page=3`, `totalPages=3`; `offset ≥ total` vazio; `totalPages = 0` sem itens), `search_text` (normalização NFKD sem acento/maiúsculas/espaços colapsados; `is_valid_search_query`: 1 a 60 só dígitos, 2 a 60 nos demais; predicado: dígitos → código igual ou que começa com, texto → contém; fornecedor por nome, inclusive dígitos), `rounding` (12,25 → 12,3; −12,25 → −12,3; −0,04 → `0.0`; `Fraction` e inteiros escalados, sem float), exceções (`TND-001..003` com mensagens fixas e `fields`, sem valor recebido). *Dep.: nenhuma.*
- [ ] **T-04:** `test_sales_trend_cells.py` — célula: CA-02 (+50,0%, +16,7%, +8,3%, devolução abatida; sem abatimento daria +15,4%), CA-03 (+108,3%, `baseParcial`, médias 0,6849/0,3289), CA-04 (−48,3% e +20,0%), CA-05 (revenue +80,0%, `baseBaixa` com R$ 200 < R$ 500), CA-07, CA-08, CA-09, CA-10 (−100,0% com `devolucaoLiquida`; `NOVO` com `devolucaoLiquida`), CA-11, CA-21, precedência `SEM_BASE → VARIACAO → NOVO → SEM_MOVIMENTO`, AR-2 (todos os selos `false` em `SEM_BASE`), AR-3 (`baseParcial` em `NOVO` e `SEM_MOVIMENTO`), invariante Q-1 (`cell.baseParcial` = janela), **exatidão**: venda 100,10 e devolução −100,10 somam 0 exato e viram `SEM_MOVIMENTO`/`NOVO` corretos; piso −100,0 e sem teto; `build_monthly_sales` converte `Decimal` em inteiro escalado e **descarta SKU fora do catálogo ativo** (1008, 1009) mantendo a `first_sale_date` global (AR-12). *Dep.: T-01, T-02, T-03.*
- [ ] **T-05:** `test_ranking.py` — universo (P-072: só SKU **ativo** com movimento em `[M−23, M]`, linha com líquido 0 conta, venda só depois do Mês-Base não entra, 1008 e 1009 nunca; CA-13, CA-14, C-32), `q` (CA-17: `"cha"` → 1001 e 1004; código `1003`; em branco = sem filtro; `"a"` inválido), `view` (CA-16), `minVolume` (CA-12, C-17), ordenação com grupos `VARIACAO → NOVO → SEM_BASE → SEM_MOVIMENTO` em `desc` e `asc` (CA-15, C-21), desempate por perda absoluta e código (CA-15, C-20; AR-1), AR-9, `totaisPorVisao` (7/2/2/2), `meta.total` (valores de 3.1.3 do contrato; ignora `q`/`view`/`minVolume`), paginação e estabilidade da ordem entre páginas (Q-15). *Dep.: T-01, T-03.*
- [ ] **T-06:** `test_suppliers.py` — CA-28 a CA-38 sobre produtos ativos: % sobre a soma (Alfa −57,1%, não −25,0%), Beta = só o 1007 (+200,0% com `baseBaixa`), Gama `NOVO` com `devolucaoLiquida`, Sem fornecedor −100,0%; identidade (CA-31: nulo e `"   "` no mesmo grupo; o 1009 **não** entra; "Alfa Lab" e "ALFA  lab " → um grupo exibido "ALFA lab"); chave `f:` e `sem-fornecedor` sem colisão (AR-4); ordenação/paginação/`view`/`q`/`minVolume` de fornecedores (CA-32, CA-33); contribuição e **fecho da conta** (CA-34, CA-35: `Σ contribuicaoValor = atualF − anteriorF` e `Σ contribuicaoPp` exato = % do fornecedor, **parametrizado** por 4 janelas × 2 métricas × fornecedores), CA-36 (12m, +149,9%), CA-37 (Mês-Base parcial, `NOVO` interno), CA-38 (`SEM_BASE` com contribuições `null`); detalhe: `sortBy` `contribution`/`variation`, `q` de produto com `meta.fornecedor` completo (CA-39), `TND-003` (C-47). *Dep.: T-01, T-04.*
- [ ] **T-07:** `test_repository.py` (cursor `pyodbc` mockado) — SQL do agregado passa por `is_readonly_query`, não contém `CONCAT`, `Cod Cliente`, `Pedido`, `Fornecedor`, `JOIN`, `SELECT *`; contém `[Operação] = 'VENDA'`, `LIKE 'DEVOLU%'`, `GROUP BY`; **sem** `HAVING`; corte como **bind parameter** (`execute(sql, cutoff)`); leitura por `fetchmany` (nunca `fetchall`) com conversão para inteiros escalados (`Decimal('12.5') → 125000`), meio para cima; linhas de SKU fora do catálogo ativo descartadas **durante** a leitura; `first_sale_date` = mínimo dos mínimos de **todas** as linhas; base vazia → `None`; catálogo `SELECT Codigo, Descricao, Fornecedor ... WHERE [Pc.Venda] > 0` (sem preço, sem `is_active`); `pyodbc.Error`/`ConnectionError`/`ValueError` → `TrendDataSourceError` (`TND-004`) sem a mensagem do driver no log (CA-26, CA-40). *Dep.: nenhuma.*
- [ ] **T-08:** `test_cache.py` — CA-23 (10 threads, loader chamado 1 vez; 5h59 não recarrega, 6h recarrega; falha mantém o anterior e levanta `TND-004`), CA-24 (trocar métrica/Mês-Base/`groupBy`/expandir fornecedor **não** chama o repositório), CA-25 (relógio `_utc_now` após a meia-noite dentro do TTL: `dataReferencia = 2026-11-09`, `ultimoDiaCoberto = 2026-11-08`), `force_reload` respeita lock e `TND-005`, estados `FRIO`/`CARREGANDO`/`QUENTE`/`EXPIRADO`, ordem de carga (catálogo ativo antes do agregado). *Dep.: T-01, T-07.*
- [ ] **T-09:** `test_error_route.py` (`TestClient(app)` de `main`) — **`TrendAPIRoute`**: validação inválida em `/api/v1/sales-trend` e `/supplier-products` → `400 TND-001` com `fields` (nomes, ordem da query, sem duplicata, **sem** valor); `TND-001/002/003/004/005` com HTTP 400/422/404/503/429 e corpo `{error:{code,message,fields}, meta:{timestamp,version}}`; **regressão**: payload inválido em `/api/v1/inventory/predict` continua 422 padrão do FastAPI; o módulo **não registra** handler global (`app.exception_handlers` sem entradas novas de `sales_trend`); `q` curto, `limit`, `offset`, `baseMonth` malformado e futuro, `minVolume` negativo/`NaN`, `supplierKey` ausente (CA-19, C-07, C-08, C-24 a C-26, C-47, C-48); `activeOnly` enviado é **ignorado** (sem erro). *Dep.: T-01.*
- [ ] **T-10:** `test_sales_trend_api.py` (`TestClient`, snapshot sintético injetado) — exemplos do contrato 3.1.3, 3.1.4 e 3.2 **idênticos** (campos, tipos, casas decimais, ordem, `meta` completo incluindo `total`, `parametros`, `totaisPorVisao`, `ordenacao`); **sem** `ativo` em nenhuma linha; invariante Q-1 (`cell.baseParcial` = `meta.janelas[i].baseParcial` em todas as células e em `SEM_BASE`); matriz C-01 a C-51 aplicável; `TND-002` com `fields:["baseMonth"]` (informado) e `fields:[]` (padrão/base vazia, Q-7), CA-20; ordem de avaliação 400 → 503 → 400/422 (mês) → 404; detalhe com `limit` padrão 20 e 120 SKUs (`limit=50&offset=100` → 20 itens, `page=3`, CA-39); lista sem filhos (CA-39); `GET /health` não dispara carga (cache frio → `FRIO`, `dataReferencia = null`); `POST /reload` 200/429/503; `response_model` Union resolve por `meta.agrupamento`; `TND-005` **só** no `POST /reload` (Q-16). *Dep.: T-01, T-04, T-05, T-06, T-08, T-09.*
- [ ] **T-11:** `test_privacy.py` — P-085, CA-26, CA-40: `caplog` na carga e nas rotas com massa sintética: nenhum registro contém SKU, `q`, nome de fornecedor, `supplierKey` ou DataFrame/payload; só contagens e duração; allowlist exata de chaves das respostas (sem `customerCode`/`Pedido`/custo/estoque/preço); a SQL não referencia `Cod Cliente` nem `Pedido`. *Dep.: T-07, T-10.*
- [ ] **T-12:** `test_report_cli.py` — a saída do CLI de B-14 contém só agregados (sem SKU, fornecedor, `q`), formata p10/p25/p50/p75/p90, a diferença da reconciliação em centavos e o total do mês **com e sem** restrição aos ativos, com repositório e banco falsos. *Dep.: T-01.*
- [ ] **T-13:** `test_performance.py` (`@pytest.mark.slow`, fora do CI padrão) — massa de **2.500 SKUs × 36 meses × 150 fornecedores**: lista por produto e por fornecedor (qualquer `sortWindow`) abaixo de **300 ms** por chamada, e `tracemalloc` do snapshot abaixo de **20 MB**. Reprovar aqui reabre a memoização (ADR-003 DA-06, alternativa 7). *Dep.: B-05 a B-08, B-10, B-11.*

### 4.2 Backend — `src/modules/sales_trend/`

- [ ] **B-02:** `__init__.py` de cada pacote (`api`, `service`, `domain`, `repository`, `diagnostics`), `domain/exceptions.py` (`TrendDomainException(code, message, fields=())`, `InvalidTrendParametersError` `TND-001`, `BaseMonthWithoutSalesError(fields=())` `TND-002`, `SupplierNotFoundError` `TND-003`; mensagens fixas de P-082, sem HTTP, sem valor recebido) e `domain/pagination.py` (`PageRequest`, `PageResult`, `paginate`, `DEFAULT_PAGE_LIMIT = 50`, `MAX_PAGE_LIMIT = 200`). Faz T-03 (parte) passar. *Dep.: T-03, B-01.*
- [ ] **B-03:** `domain/search_text.py` (`normalize_text`, `is_valid_search_query`, predicado de busca de produto e de fornecedor, constantes `MIN_TEXT_QUERY_LENGTH`, `MIN_DIGITS_QUERY_LENGTH`, `MAX_QUERY_LENGTH`) e `domain/rounding.py` (`round_fraction_half_up`, `round_scaled_half_up`; sem float). Faz T-03 passar. *Dep.: T-03.*
- [ ] **B-04:** `domain/month_windows.py` — índice de mês (`ano*12+mês-1`), `parse_base_month`, `previous_month`, `window_pair(base_month_index, size)`, `days_in_span`, `covered_days(span, first_sale_date, last_covered_day)`, validação do Mês-Base (`TND-001` futuro, `TND-002` anterior/dia 1/base vazia). Faz T-02 passar. *Dep.: T-02, B-02, B-05 (constantes).*
- [ ] **B-05:** `domain/sales_trend.py` (1/2) — tabela de constantes P-072 a P-093 no topo (`VALUE_SCALE = 10_000`, `WINDOW_SIZES_MONTHS`, `TREND_SPAN_MONTHS`, `MIN_PREVIOUS_COVERAGE_RATIO`, limiares de base baixa, `NO_SUPPLIER_LABEL`/`NO_SUPPLIER_KEY`, `CACHE_TTL_HOURS`...), `SkuSeries`/`MonthlySales`/`TrendCatalogEntry` (`frozen dataclass`), `build_monthly_sales(rows, active_skus, first_sale_date)` (converte `Decimal(str(v))` para inteiro escalado meio para cima, **descarta SKUs fora do catálogo ativo**, monta tuplas densas e `movement_mask`), `has_movement_between(...)`. *Dep.: T-04 (parte), B-02.*
- [ ] **B-06:** `domain/sales_trend.py` (2/2) — célula: `compute_cell(...)` com piso zero, `Fraction`, status, `baseParcial`, `baseBaixa`, `devolucaoLiquida`, médias por dia, arredondamento por `rounding.py`; `rank_window(...)` (Fase A) e `build_cells(...)` (Fase B). Faz T-04 passar. *Dep.: T-04, B-03, B-04, B-05.*
- [ ] **B-07:** `domain/ranking.py` — universo, `q`, `view`, `minVolume`, ordenação por grupos e desempate (AR-1, AR-9), `totaisPorVisao`, paginação. Faz T-05 passar. *Dep.: T-05, B-03, B-06.*
- [ ] **B-08:** `domain/suppliers.py` — `normalize_supplier`, `build_supplier_index(catalog)` (chave `f:`/`sem-fornecedor`, nome exibido pela menor grafia ordinal), soma do fornecedor (bruto), linha de fornecedor, linha `total` (AR-10), contribuição (`Fraction`, `null` em `SEM_BASE`/`anteriorF ≤ 0`), detalhe (`sortBy`, `TND-003`). Faz T-06 passar. *Dep.: T-06, B-06, B-07.*
- [ ] **B-09:** `repository/errors.py` (`TrendInfrastructureException(code, message)`, `TrendDataSourceError` `TND-004`) e `repository/sales_trend_repository.py` — `SALE_OPERATION`, `RETURN_OPERATION_PATTERN`, `FETCH_CHUNK_SIZE = 50_000`, `_execute_readonly(sql, params)` com `is_readonly_query` de `src.core.database`, `fetch_active_catalog()` e `fetch_monthly_net_sales(cutoff, active_skus)` (DA-02), leitura em blocos filtrando durante a leitura, traduzindo `pyodbc.Error`/`ConnectionError`/`ValueError` em `TND-004` com log só do tipo. Faz T-07 passar. *Dep.: T-07, B-01, B-05.*
- [ ] **B-10:** `service/sales_trend_cache.py` — `SalesTrendSnapshot`, `get_snapshot(force_reload=False)`, `peek_snapshot()`, `get_cache_status()`, `reset_cache()`, `_utc_now()`, `business_date`, voo único, TTL, troca atômica, `force_reload` com `ReloadTooSoonError` (`TND-005`); `_build_snapshot()` carrega o catálogo ativo, depois o agregado, monta `MonthlySales` e o índice de fornecedor; log só com contagens e duração (P-085.2). Faz T-08 passar. *Dep.: T-08, B-05, B-08, B-09.*
- [ ] **B-11:** `service/sales_trend_service.py` — `get_sales_trend(query)` (despacha `product`/`supplier`), `get_supplier_products(query)`, `get_cache_state()`, `reload_cache()`; ordem de P-082.1 (snapshot → Mês-Base → `TND-003`); sem `try/except`; sem log de parâmetros. *Dep.: B-07, B-08, B-10.*
- [ ] **B-12:** `api/schemas.py` + `api/mappers.py` — `CamelModel`, `TrendErrorResponse`, modelos de resposta do contrato (`ProductTrendResponse`, `SupplierTrendResponse`, `SupplierDetailResponse`, `SalesTrendCacheResponse`; `TrendParameters` a partir das constantes), `Literal` para enums, `Field(description=...)` PT-BR, `json_schema_extra` com os exemplos, `SALES_TREND_CONTRACT_VERSION = "1.0.0"`; mappers arredondam só na saída e montam `meta`. *Dep.: B-06, B-08.*
- [ ] **B-13:** `api/route.py` (`TrendAPIRoute`, mapa código → HTTP, corpo único de erro) + `api/query_params.py` (`TrendListQuery`/`TrendDetailQuery` com `baseMonth` regex, `AfterValidator` de `sortWindow`, `q` em branco → `None`, `minVolume` com `allow_inf_nan=False` e `le=1_000_000_000`, `limit` 1..200 (detalhe default 20), `supplierKey` 1..200) + `api/router.py` (`sales_trend_router`, prefix `/sales-trend`, 4 rotas só recebem/chamam/devolvem, `responses={400,404,422,429,503}`) + **edição de `src/api.py`** (1 import + 1 `include_router` com `prefix="/api/v1"`). Faz T-09 e T-10 passarem. *Dep.: T-09, T-10, B-01, B-11, B-12.*
- [ ] **B-14:** `diagnostics/run_sales_trend_report.py` — CLI somente leitura (`python -m src.modules.sales_trend.diagnostics.run_sales_trend_report`): tempo de carga, pico `tracemalloc` e RSS máximo (`resource.getrusage` no Linux), tamanho aproximado do snapshot, contagens (SKUs lidos, retidos, descartados por inativos/sem cadastro, meses, linhas, fornecedores, **SKUs do maior fornecedor**, fornecedores com mais de uma grafia, `NOVO`/`SEM_BASE` por janela no Mês-Base padrão), **reconciliação P-087.3** (soma de `atual` da janela de 1 mês, por métrica, dos SKUs ativos vs soma direta `VENDA + DEVOLU%` do mês restrita aos mesmos SKUs; e o total do mês sem restrição, para dimensionar o efeito dos inativos fora, R-10) e percentis p10/p25/p50/p75/p90 do volume da Janela Anterior (calibração de P-079.1). Saída só com agregados; nenhum arquivo gravado. Faz T-12 passar. *Dep.: T-12, B-10, B-11.*

### 4.3 Testes de frontend (Tester) `[PARALLEL]` com os testes de backend

- [ ] **T-14:** `services/sales-trend.service.spec.ts` (`HttpTestingController`) — URLs e `HttpParams` de `getTrend` (overloads por `groupBy`), `getSupplierProducts` (`supplierKey` codificado, `limit` 20 por padrão) e `getHealth`; parâmetros **iguais ao padrão são omitidos**; **nenhum** `activeOnly`; respostas tipadas; sem storage nem `console.log`. *Dep.: contrato.*
- [ ] **T-15:** `utils/trend-error.spec.ts` — type guard aceita `TND-001` a `TND-005` com `fields`, mensagens de tela por `code`, `TND-002` com `fields:["baseMonth"]` vs `[]` (Q-7), `TND-004` com o corpo exato do contrato, 500/0 e corpo malformado → genérico; nenhuma mensagem derivada de texto da API. *Dep.: contrato.*
- [ ] **T-16:** `utils/pt-br-format.spec.ts`, `trend-format.spec.ts`, `trend-url.spec.ts`, `trend-view.spec.ts` — `roundHalfUp`, `formatDecimal`, `formatCurrency`, `formatIsoDate`; variação com sinal (`+50,0%`, `−100,0%` com U+2212, `0,0%` sem sinal, `+1.250,5%`), p.p., faixa de meses (`ago–out/26`, `nov/25–out/26`, `out/26`), valor por métrica; `trend-url` ida e volta (estado ↔ params, omitindo padrões, sem `activeOnly`); `trend-view`: células por `status`/selos, colunas a partir de `meta.janelas`, divisor "sem percentual", texto de selo e tooltip com `parametros` (sem número fixo), estado "histórico anterior insuficiente" (todas `semBase`), mês corrente parcial. *Dep.: contrato, Design Plan.*
- [ ] **T-17:** `services/sales-trend.store.spec.ts` — transições `idle → loading → success | empty | error`; cancelamento da requisição anterior; trocar `groupBy` preserva Mês-Base, métrica, `sortWindow`, `sortDir` e zera `view`, `minVolume`, `q` (P-086.7, A-26); trocar métrica zera `minVolume` (P-079.5); qualquer mudança volta `offset` a 0 e recolhe expansões; clique repetido no cabeçalho alterna `desc`/`asc`; expansão de fornecedor chama o detalhe com os mesmos `baseMonth` (= `meta.mesBase`) e `metric`, `limit` 20, páginas e ordem independentes por fornecedor, vários grupos abertos; `TND-003` recolhe com aviso; `dataReferencia` do detalhe divergente recarrega a lista (C-50); `TND-002` com `fields:["baseMonth"]` oferece voltar ao padrão; estado na URL; sem `localStorage`/`sessionStorage`. *Dep.: contrato.*
- [ ] **T-18:** specs de componentes burros (store/serviço mockados) — `TrendPager`, `TrendErrorBanner`, `TrendEmptyState`, `SegmentedControl`, toolbar (alternadores, seletor de mês com mês corrente "parcial até DD/MM", `‹`/`›`, "Volume mínimo" com a unidade da métrica, "limpar filtros", **sem** controle de ativos), tabela e cartões (4 colunas de `meta.janelas`, ordenação por teclado, `aria-sort`, `aria-expanded`, direção por ▲/▼ + sinal + texto, selos com texto, **sem** selo "Inativo"), linha de fornecedor expansível com paginador de 20, sub-tabela "Valores por janela" (com média por dia só em `baseParcial`), skeleton, vazio com ação, erro por `code` e "histórico anterior insuficiente"; nenhum componente injeta `HttpClient`. *Dep.: Design Plan.*
- [ ] **T-19:** `features/sales-trend/sales-trend.route.spec.ts` — `routes` de `app.routes.ts` contém `tendencia-vendas` com `loadComponent` lazy **antes** do curinga `**` e o import resolve para `SalesTrendPageComponent`; **regressão** dos specs de `main` (`app.component.spec.ts`, `pricing-page.component.spec.ts`). **Não** criar spec de navbar (evita arquivo duplicado com o `navbar.component.spec.ts` da Fase 1); o link é conferido manualmente. *Dep.: Design Plan.*

### 4.4 Frontend — `frontend/src/app/features/sales-trend/` `[PARALLEL]` com B-02 a B-14 (depende do contrato e do Design Plan)

- [ ] **F-01:** `models/sales-trend.model.ts` (tipos de 7 do contrato, inclusive `TrendErrorCode` e `TrendApiError`) e `utils/trend-error.ts` (`toTrendApiError`, `TREND_ERROR_MESSAGES`). Faz T-15 passar. *Dep.: T-15, B-01.*
- [ ] **F-02:** `services/sales-trend.service.ts` — `getTrend` (overloads), `getSupplierProducts`, `getHealth`; `baseUrl = '/api/v1/sales-trend'`; omite padrões; devolve o envelope completo. Faz T-14 passar. *Dep.: T-14, F-01.*
- [ ] **F-03:** `utils/pt-br-format.ts` (própria), `utils/trend-format.ts`, `utils/trend-url.ts`, `pipes/trend-format.pipes.ts` — formatação pura (U+2212, p.p., faixa de meses, valor por métrica) e serialização estado ↔ query params. Faz T-16 (parte) passar. *Dep.: T-16, F-01.*
- [ ] **F-04:** **Edições em `main`:** rota lazy `tendencia-vendas` em `app.routes.ts` (antes do `**`) e `<li>` "Tendência de Vendas" em `navbar.component.html`. Faz T-19 passar. *Dep.: T-19, B-01.*
- [ ] **F-05:** **Edição em `main`:** token `--navbar-height` em `styles.scss` (`64px`; `58px` em `max-width: 768px`) e `styles/_trend-ui.scss` da feature (mixins e constantes só com tokens). *Dep.: B-01.*
- [ ] **F-06:** `services/sales-trend.store.ts` — signals, regras de transição (T-17), sincronização com a URL via `trend-url.ts`, cancelamento de requisição, expansões imutáveis (`Map` recriado), aviso de cache frio (`getHealth()` ao abrir + aviso por tempo > 4 s). Faz T-17 passar. *Dep.: T-17, F-02, F-03.*
- [ ] **F-07:** `utils/trend-view.ts` e `services/viewport.service.ts` — view-models puros e `isCompact` (< 768 px). Faz T-16 (parte) passar. *Dep.: T-16, F-03.*
- [ ] **F-08:** componentes base próprios — `TrendPagerComponent`, `TrendErrorBannerComponent`, `TrendEmptyStateComponent`, `TrendTableSkeletonComponent`, `SegmentedControlComponent`, `InlineNoticeComponent`. Faz T-18 (parte) passar. *Dep.: T-18, F-05, F-07.*
- [ ] **F-09:** controles — `BaseMonthPickerComponent`, `TrendSearchFieldComponent` (debounce de 300 ms no store), `TrendToolbarComponent`. Faz T-18 (parte) passar. *Dep.: T-18, F-08.*
- [ ] **F-10:** tabela e cartões — `TrendTableComponent`, `TrendColumnHeaderComponent`, `TrendRowComponent`, `TrendCellComponent`, `TrendRowValuesComponent`, `TrendCardListComponent`/`TrendCardComponent`, `MobileSortControlComponent`, `PeriodLegendComponent`. Faz T-18 (parte) passar. *Dep.: T-18, F-07, F-08.*
- [ ] **F-11:** `TrendSupplierGroupComponent` — linha de fornecedor expansível com detalhe (contribuição em p.p. e valor, paginador de 20, ordem por contribuição/variação, skeleton, erro e `TND-003` com aviso, vários grupos abertos). Faz T-18 (parte) passar. *Dep.: T-18, F-10.*
- [ ] **F-12:** `ReadingGuideComponent` e `SalesTrendPageComponent` (único componente inteligente; cabeçalho próprio, nota "apenas produtos ativos", compõe store e componentes; região viva e foco). Smoke com o backend real. Fecha T-18. *Dep.: T-18, F-06, F-09, F-10, F-11.*

---

## 5. Ordem de execução e paralelismo

```
Checkpoint Etapa 2 (DC-2..DC-9, premissas AR-*)
   │
   B-01 (worktree a partir de main + junção de .agents)  ────────────────────┐ (bloqueia B-02, B-09, B-13, F-01, F-04, F-05)
   │
   ├── Frente Backend ───────────────────────────────────────────┐  [PARALLEL]
   │   T-01 → T-02,T-03 → B-02,B-03,B-04,B-05                    │
   │   T-04 → B-06 ; T-05 → B-07 ; T-06 → B-08  (domínio, sem banco)
   │   T-07 → B-09 (repositório)                                 │
   │   T-08 → B-10 (cache) → B-11 (service)                      │
   │   T-09,T-10 → B-12 → B-13 (API + api.py) → T-11 (privacidade)
   │   T-12 → B-14 (CLI) ;  T-13 (desempenho, slow)              │
   │                                                             │
   └── Frente Frontend ──────────────────────────────────────────┘  [PARALLEL]
       T-14,T-15 → F-01,F-02 ; T-16 → F-03,F-07 ; T-19 → F-04 ; F-05
       T-17 → F-06 ; T-18 → F-08 → F-09,F-10 → F-11 → F-12   (depende do Design Plan)
```

- Backend e frontend dependem **só do contrato 1.0.0** e andam juntos; o frontend usa serviço mockado até a integração.
- Dentro do backend, **sem conflito de arquivo** (podem ser desenvolvedores diferentes `[PARALLEL]`): domínio (B-02 a B-08), repositório (B-09) e CLI (B-14). B-10 espera B-08/B-09; B-13 espera B-11/B-12.
- Os testes (T-01 a T-19) só adicionam arquivos novos e podem ser escritos antes de B-01 estar concluído.
- Integração final: smoke com `uvicorn` e `ng serve` (o proxy `/api` já existe) contra a base real; **B-14 rodado contra a base real** e o relatório colado no PR (reconciliação, calibração de "base baixa", maior fornecedor, pico de memória, efeito dos inativos fora).

## 6. Commits atômicos sugeridos (Conventional Commits, sobre `main`, em `feature/sales-trend`)

> A documentação em `.agents/docs/` é **gitignored**: não há commit de docs.

1. `test(sales-trend): adiciona massa sintetica e testes de calendario e utilitarios de dominio [P-072..P-079]` (T-01..T-03)
2. `feat(sales-trend): adiciona excecoes TND, paginacao, busca, arredondamento e calendario de janelas [P-074, P-075, P-081, P-082]` (B-02..B-04)
3. `feat(sales-trend): calcula serie mensal e celula de variacao com piso zero e estados [P-073, P-076..P-079]` (B-05, B-06)
4. `test(sales-trend): adiciona testes de ranking, visoes e busca [P-080, P-081]` (T-05) → `feat(sales-trend): ordena e filtra a tendencia por produto ativo [P-072, P-080, P-081]` (B-07)
5. `test(sales-trend): adiciona testes do agrupamento por fornecedor e da contribuicao [P-088..P-092]` (T-06) → `feat(sales-trend): agrupa por fornecedor com soma liquida e contribuicao [P-089..P-092]` (B-08)
6. `test(sales-trend): adiciona testes do repositorio do agregado mensal [P-073.3, P-085]` (T-07) → `feat(sales-trend): adiciona agregado mensal liquido e catalogo ativo [P-073.3, P-072]` (B-09)
7. `test(sales-trend): adiciona testes do snapshot [P-083]` (T-08) → `feat(sales-trend): adiciona snapshot com voo unico e TTL [P-083]` (B-10, B-11)
8. `test(sales-trend): adiciona testes de erros TND e de contrato da API [P-082, P-084]` (T-09..T-11) → `feat(sales-trend): expoe rotas da tendencia, detalhe do fornecedor, health e reload [P-083, P-084, P-092]` (B-12, B-13, **edita `src/api.py`**)
9. `test(sales-trend): adiciona teste do relatorio de reconciliacao` (T-12) → `feat(sales-trend): adiciona CLI de memoria, reconciliacao e calibracao [P-087]` (B-14); `test(sales-trend): adiciona teste de desempenho (slow)` (T-13)
10. `test(sales-trend-ui): adiciona specs de servico, erros, formatacao, url e store` (T-14..T-17)
11. `feat(sales-trend-ui): adiciona modelos, servico, utilitarios e store da tendencia [P-084, P-086]` (F-01..F-03, F-06, F-07)
12. `feat(sales-trend-ui): adiciona rota /tendencia-vendas e item na navbar [P-086]` (F-04, T-19; **edita `app.routes.ts` e `navbar.component.html`**)
13. `feat(sales-trend-ui): adiciona token --navbar-height e estilos da feature` (F-05; **edita `styles.scss`**)
14. `test(sales-trend-ui): adiciona specs dos componentes` (T-18) → `feat(sales-trend-ui): adiciona componentes base, controles, tabela e cartoes [P-080, P-086]` (F-08..F-10)
15. `feat(sales-trend-ui): adiciona linhas expansiveis de fornecedor com contribuicao [P-090, P-092]` (F-11)
16. `feat(sales-trend-ui): adiciona pagina Tendencia de Vendas com estados e legenda [P-086]` (F-12)

Cada `test` precede o `feat` correspondente; commits de frentes paralelas podem se intercalar. Nenhum commit é breaking (rotas e arquivos novos; edições aditivas em `main`). Os commits 8, 12 e 13 tocam arquivos que a Fase 1 também edita (exceto `styles.scss`): são os pontos de conflito de merge (R-3).

## 7. Dependências novas

**Nenhuma.** Backend: biblioteca padrão (`decimal`, `fractions`, `dataclasses`, `tracemalloc`, `resource`) e o que já está em `requirements.txt` (`fastapi`, `pydantic`, `pyodbc`). Frontend: Angular 18 e RxJS já instalados; `viewport.service.ts` usa `matchMedia` (sem `@angular/cdk`, que não está em `package.json`).

## 8. Audit técnico adicional (Tester / Reviewer, Etapa 4)

- [ ] **Memória:** relatório de B-14 contra a base real no PR: pico `tracemalloc` e RSS máximo da carga, tamanho do snapshot (esperado ≈ 3 a 6 MB residual; ≈ 20 a 30 MB de pico), e T-13 verde. Anexar nota sobre o pico de ~3 GB do `pricing` (preexistente) ao `devops`.
- [ ] **Reconciliação (P-087.3, CA-27):** soma de `atual` da janela de 1 mês, por métrica, dos produtos ativos, igual à soma direta no SQL restrita aos mesmos SKUs; total do mês sem restrição (efeito dos inativos fora); nº de SKUs listados; células `NOVO`/`SEM_BASE`; calibração de `LOW_BASE_MIN_QUANTITY`/`LOW_BASE_MIN_REVENUE`; SKUs do maior fornecedor (A-18) e grafias duplicadas (A-20).
- [ ] **Independência:** `grep` por `src.modules.analytics` e `features/analytics` nos arquivos novos sem ocorrência; `pytest` inteiro e `ng test` verdes sobre `main`; regressão do 422 de `inventory`/`pricing` (T-09).
- [ ] **SQL segura (CA-26, CA-40):** query capturada do cursor mockado sem `CONCAT`, `Cod Cliente`, `Pedido`, `Fornecedor`, `JOIN`; corte vinculado; `fetchmany`.
- [ ] **Frontend:** `npx ng test --watch=false --browsers=ChromeHeadless` e `ng build` sem erros; a rota é lazy, então o bundle inicial não cresce; manual em 320, 375, 768 e 1280 px, teclado e leitor de tela nas linhas expansíveis; link na navbar (desktop e mobile).
