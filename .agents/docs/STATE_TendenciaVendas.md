# STATE — Tendência de Vendas por Item (estado isolado)

**Feature:** Analytics Comercial — "Tendência de Vendas por Item" (slug `analytics-sales-trend`)
**Por que um arquivo à parte:** o `STATE.md` principal pertence à Fase 1 (cross-sell), ainda em implementação na branch `feature/analytics-cross-sell`. Este arquivo evita corrida de edição; ao final, as decisões são mescladas no `STATE.md`.
**Categoria:** A — Engenharia de Software, tipo **T1** (Full-Stack: FastAPI + Angular), estendendo o módulo `analytics`
**Etapa atual:** 1 — Descoberta e Especificação (`analyst`)
**Faixa de IDs:** regras a partir de `P-072` (último usado: `P-071`); erros `TND-NNN`

## Pedido do usuário (2026-11-09)
Tabela com TODOS os itens e a % de crescimento ou queda de vendas dos últimos 1, 3, 6 e 12 meses, para identificar maiores altas e maiores quedas.

## Decisões do usuário
| # | Decisão |
|---|---------|
| T1 | Métrica: **quantidade líquida e faturamento líquido (R$), com alternador** na tela; padrão faturamento |
| T2 | Janela de X meses para trás a partir de um **mês-base**, comparada com a janela imediatamente anterior de mesmo tamanho (1m: out vs set; 3m: ago–out vs mai–jul; 12m: nov/25–out/26 vs nov/24–out/25) |
| T3 | **Mês-base definível manualmente**, podendo contar ou não o mês corrente (parcial). Padrão: último mês completo |
| T4 | Devoluções abatidas (D4 do plano mestre) |
| T5 | A tabela tem **visão por produto** (individual) ou **por fornecedor**, com todos os produtos do fornecedor agrupados (% do fornecedor sobre a soma líquida, não média das %) |
| T6 | **Feature independente do cross-sell** (checkpoint 2026-11-09): módulo próprio, branch `feature/sales-trend` a partir de `main`, página própria `/tendencia-vendas` com item na navbar; sem importar nada da Fase 1 |
| T7 | **Produtos inativos não existem na feature** (sem filtro, sem selo): só produtos ativos do catálogo atual (`Pc.Venda > 0`) entram, inclusive nas somas de fornecedor |
| T8 | Premissas A-1 a A-5 e A-17 a A-19 do analista aceitas como escritas |

## Checklist das 5 Macro-Etapas
- [x] **Etapa 1** — Especificação (`analyst`) → `business_rules/analytics-sales-trend.md` (P-072 a P-093, CA-01 a CA-40, A-1 a A-26), `GLOSSARY.md` (seção 4), `tasks/analytics-sales-trend.md`
- [x] **Etapa 2** — Arquitetura (`architect`, `STATE_Arquitetura_Tendencia.md`) ∥ Design Plan (`designer`, `STATE_Design_Tendencia.md`) → `adr/ADR-003-tendencia-vendas.md` (DA-01..DA-16), `api_contracts/analytics-sales-trend.md` (1.0.0), `design/plans/analytics-sales-trend.md` (D-1..D-23), checklist T-01..T-19 / B-01..B-14 / F-01..F-12 em `tasks/analytics-sales-trend.md` (validado pelo usuário)
- [x] **Etapa 3** — TDD (`tester`) → Implementação (`developer`). Worktree em `../fitoherb-sales-trend` (branch `feature/sales-trend`); todos os 16 commits convencionais atômicos entregues + fix de normalização de datetime para date (`8221a7e`).
- [x] **Etapa 4** — Quality Gate 360 (`reviewer`, `ux-reviewer`, `tester`). 50/50 testes Pytest aprovados, 52/52 specs Karma Angular aprovadas, Angular Build de produção aprovado sem erros (bundle inicial de 506.82 kB). Clean code, sanitização, acessibilidade WCAG AA e governança estrita de docs respeitados.
- [x] **Etapa 5** — Release (`devops`) + compressão de contexto. Branch `feature/sales-trend` enviada ao GitHub `origin` sem interferir na branch `feature/analytics-cross-sell`. Relatório de diagnóstico em tempo real no banco executado: pico de carga de 15.93 MB (meta < 30 MB), memória residente de 3.97 MB (meta < 6 MB), 2.188 SKUs ativos retidos. PR pronto para merge.

## Bypasses justificados
- **product-owner:** pedido é uma única story coesa, dentro do módulo `analytics` já fatiado no plano mestre.
- **dba:** somente leitura em `Externo01.Vendas` e `Externo01.Produto`; sem schema nem migration.
- **ai-specialist:** cálculo determinístico (variação percentual entre janelas); sem modelo, LLM ou RAG.
- **privacy-officer:** a feature opera por produto e não usa `Cod Cliente`; a projeção mínima e a regra de não logar payloads são conferidas pelo `reviewer`.
- **security:** só rotas GET somente leitura, sem autenticação ou superfície nova; checagem OWASP básica fica com o `reviewer`.

## Revisão pós-checkpoint
- `designer`: **concluído** (página própria `/tendencia-vendas`, sem inativos, `TND-004`/`TND-005`, D-14 reescrita como feature autônoma, novas D-21 e D-23, Q-16 e Q-17 repassadas ao `architect`). Edições em arquivos de `main`: `app.routes.ts`, `navbar.component.html`, token `--navbar-height` em `styles.scss` e, se faltar, `proxy.conf.json`.
- `analyst`: interrompido pela queda da sessão com a revisão parcial (cabeçalho de revisão presente; corpo ainda com `activeOnly`/`ANL-00x`). **Retomado e concluído em 2026-11-10:** inativos fora (P-072.2/.3, exemplo Beta +200,0%), `TND-004`/`TND-005`, P-083 e P-081 autocontidas, CA-41 e C-52/C-53 novos, glossário atualizado; só A-6..A-9, A-20, A-21 e baixas seguem abertas, sem bloqueio.
- `architect`: **concluído em 2026-11-10** (ADR-003 reescrito, contrato 1.0.0 em `/api/v1/sales-trend`, checklist T-01..T-19 / B-01..B-14 / F-01..F-12, 16 commits sobre `main`, `TrendAPIRoute` sem handler global, Q-16/Q-17 respondidas: o `proxy.conf.json` de `main` já cobre o prefixo). Itens abertos para o usuário: worktree `feature/sales-trend` (a Fase 1 está não commitada), R-10 (fornecedor que descontinuou produtos aparece inflado), DC-2/DC-3/DC-8 e R-2 (pico de ~3 GB do pré-aquecimento do `pricing`, preexistente). Histórico: interrompido pela queda da sessão com a revisão parcial (ADR começou a citar `sales_trend`; contrato e checklist ainda no desenho antigo). **Retomado em 2026-11-10**, com Q-16 e Q-17 do designer.

## Dependência (resolvida no checkpoint)
Versão inicial do ADR-003 reaproveitava a fundação do módulo `analytics` (Fase 1, não commitada). **Decisão T6:** a feature é independente; ADR-003, contrato, Design Plan, regras e checklist estão em revisão para módulo próprio (`src/modules/sales_trend/`, `features/sales-trend/`), com códigos `TND-004`/`TND-005` no lugar de `ANL-001`/`ANL-002`. Pontos de merge com a Fase 1: `src/api.py`, `app.routes.ts`, `navbar.component.html`. Os slugs dos documentos (`analytics-sales-trend.*`) permanecem por razão histórica.

## Log
- 2026-11-09 — Demanda recebida via `/o`. Triagem T1 com os bypasses acima. Usuário respondeu métrica (ambas com alternador) e definiu o conceito de janela e mês-base. Etapa 1 despachada ao `analyst`.
- 2026-11-09 — Usuário acrescentou T5 (visão por produto ou por fornecedor agrupado). Repassado ao `analyst` ainda em execução.
- 2026-11-09 — Etapa 1 concluída (P-072 a P-093; novo erro `TND-003`; premissas de prioridade alta: A-1 a A-5, A-17 a A-19). Pendência técnica A-13 (`error_handlers.py` converte toda validação em `XSL-004`) entregue ao `architect`. Etapa 2 despachada em paralelo: `architect` ∥ `designer`. Designer concluído (`design/plans/analytics-sales-trend.md`, D-1 a D-20, Q-1 a Q-15 repassadas ao `architect`; mobile em cartões abaixo de 768px; D-14 prevê ajustes aditivos em componentes não commitados da Fase 1). Arquiteto concluído: ADR-003, contrato 1.0.0 (rotas `/analytics/sales-trend`, `/supplier-products`, `/health`, `/reload`; `TND-001..003`, `ANL-001/002`), A-13 resolvido com `TrendAPIRoute` (sem tocar o handler da Fase 1), memória estimada em ~5 a 8 MB residentes. Q-1..Q-15 respondidas (Q-3 aceito em parte). Riscos: R-1 (Fase 1 não commitada), R-8 (ajustes aditivos em ListPager/ErrorBanner/ResultState). Checkpoint apresentado ao usuário. Dados do usuário ainda a confirmar no checkpoint: A-1/A-2 (base parcial), A-3 (dia corrente fora), A-4 (inativos), A-5 (piso zero), A-17 (fornecedor do catálogo atual).
- 2026-11-10 — Usuário aprovou desenho das Etapas 1 e 2 e ordenou início da Etapa 3 (TDD e Execução). Worktree criado em `../fitoherb-sales-trend` na branch `feature/sales-trend` a partir de `main` (`7004f96`). Junção de `.agents/` e `frontend/node_modules` estabelecida. Baseline de testes confirmada.
- 2026-11-10 — Etapas 3, 4 e 5 concluídas com sucesso total:
  - 16 commits convencionais atômicos (T-01..T-19, B-01..B-14, F-01..F-12) + fix de normalização de data SQL Server.
  - Testes: 50/50 unitários e integração Python (pytest), 52/52 Jasmine/Karma Angular (100% de sucesso).
  - Build Angular de produção (`ng build`) concluído com bundle enxuto (lazy chunk de 96.63 kB).
  - Diagnóstico real de banco (`fitoherb.ddns.net:6060`): pico tracemalloc de 15.93 MB (< 30 MB), snapshot 3.97 MB (< 6 MB), 2.188 SKUs ativos, 53 fornecedores, faturamento 1m atual de R$ 4.656.025,02.
  - Branch remota `feature/sales-trend` criada e sincronizada em `origin`. Zero interferência com a working tree do cross-sell (`feature/analytics-cross-sell`). Pull Request formalizado.
