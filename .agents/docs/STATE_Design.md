# STATE_Design — Fase 1 Analytics Comercial (F4 Cross-sell)

| Campo | Valor |
| :--- | :--- |
| Agente | `designer` (Etapa 2, em paralelo com `architect` e `privacy-officer`) |
| Data | 2026-11-05 |
| Status | Design Plan entregue — aguardando checkpoint |
| Artefato | `.agents/docs/design/plans/analytics-cross-sell.md` |

## Feito
- Design Plan com casca `/analytics` (rotas filhas lazy + nav de seções), seção Cross-sell com modos Por produto / Por cliente, componentes burros x container, 10 estados de resultado, matriz de 8 estados por elemento, a11y, responsividade, copy e filtro anti-IA.
- Sem brainstorming interativo (instrução do Orquestrador): decisões D-1 a D-11 marcadas para validação no checkpoint.

## Decisões a validar (resumo)
D-1 tokens de `styles.scss` (divergência com `DESIGN_SYSTEM.md`) · D-2 navbar "Análises de Vendas" · D-3 seções como rotas filhas · D-4 sem abas "em breve" · D-5 segmentado Produto/Cliente com estado por modo · D-6 SKU na URL, código do cliente fora · D-7 busca só por código · D-8 itens sinalizados sem esmaecer · D-9 destaque das 5 primeiras sugestões · D-10 "Ver números" por linha · D-11 página fixa de 50.

## Pendências para o contrato (Arquiteto)
Q-1 a Q-7 em §11 do plano (produto consultado em `data`/`meta`, explicação em frases separadas, `pedidosEmComum` no modo cliente, `dormantDays`/`customerProfileDays` em `meta`, formato do erro, cache frio no health, antecipar `/analytics/products/search`).

## Handoff
- Link do Design Plan a anexar no checklist `.agents/docs/tasks/analytics-cross-sell.md` quando o Arquiteto consolidar o checklist (não editado aqui para evitar conflito de escrita em paralelo).
- Ponto para o `privacy_officer`: D-6 (código do cliente fora da URL e do storage do navegador).
