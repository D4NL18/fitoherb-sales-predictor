# STATE_Design_Tendencia — Tendência de Vendas por Item (slug `analytics-sales-trend`)

| Campo | Valor |
| :--- | :--- |
| Agente | `designer` (Etapa 2, em paralelo com `architect`) |
| Data | 2026-11-09 (v1) · revisão pós-checkpoint 2026-11-09 (v2) |
| Status | Design Plan v2 entregue — aguardando checkpoint |
| Artefato | `.agents/docs/design/plans/analytics-sales-trend.md` |
| Observação | Estado isolado: o `STATE.md` principal não foi alterado. |

## Feito
- v1: Design Plan completo (wireframes desktop/tablet/mobile, célula ▲/▼ com sinal, selos, visão por fornecedor com linha expansível, contribuição em p.p., 8 estados, skeleton, vazios, erros, a11y, copy, componentes burros).
- v2 (revisão do usuário): feature **independente do cross-sell**, branch `feature/sales-trend` a partir de `main`.
  - Página própria `/tendencia-vendas` com item "Tendência de Vendas" na navbar e cabeçalho próprio (sem shell Analytics, sem abas, sem `mode-switch`).
  - Reaproveita só o que existe em `main`: `styles.scss` (tokens, `.tag-*`, `.skeleton-*`), navbar, padrões visuais de `inventory`/`pricing`. Paginação, banner de erro, estado vazio, skeleton, `SegmentedControl`, formatação pt-BR e mixins SCSS viram componentes/arquivos próprios em `features/sales-trend/`. D-14 (editar componentes da Fase 1) removida.
  - Sem inativos: removidos o controle "Somente ativos", o selo "Inativo", "Sem cadastro" e Q-13 antiga; nota "Mostra apenas produtos ativos do catálogo" no cabeçalho, na legenda e nos vazios.
  - Erros autocontidos: `ANL-001` → `TND-004` (503), `ANL-002` → `TND-005` (429); `TND-001..003` iguais.

## Decisões a validar (resumo)
D-2 página própria `/tendencia-vendas` · D-4 mobile em cartões com grade 4-up · D-5 token novo `--navbar-height` · D-6 direção por triângulo + sinal + palavra · D-7 `Base parcial`/`Sem base` no cabeçalho da coluna · D-8 disclosure em tabela comum (não treegrid) · D-9 filhos com `TrendPager` (20 por página) · D-12 estado em query params · D-14 feature autônoma (sem import de `features/analytics`) · D-21 só produtos ativos · D-22 cabeçalho próprio · D-23 erros `TND-004/005`.

## Pendências para o contrato (Arquiteto)
Q-1 a Q-15 (respostas do Arquiteto continuam valendo) e novas: Q-13 substituída (universo só de ativos), Q-16 (`TND-005` não deve ocorrer na UI; formato do corpo de `TND-004`), Q-17 (prefixo `/api/v1/sales-trend` e `proxy.conf.json`).

## Handoff
- Anexar o link do Design Plan ao checklist `.agents/docs/tasks/analytics-sales-trend.md` (Tarefa 2) quando o Arquiteto consolidar o checklist; não editado aqui para evitar conflito de escrita.
- Alterações previstas em arquivos de `main` (a cargo do Desenvolvedor): `app.routes.ts` (rota lazy), `navbar.component.html` (um `<li>`), `--navbar-height` (token novo, D-5) e, se necessário, `frontend/proxy.conf.json` (Q-17).
