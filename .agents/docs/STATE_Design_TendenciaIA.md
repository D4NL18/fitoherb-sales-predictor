# STATE — F7 Diagnóstico de Motivos da Tendência com IA (Designer)

> Estado paralelo ao `STATE.md` (não editado). Responsável: `designer`. Etapa 2, 2026-11-24, sem brainstorming (escopo aprovado pelo usuário; instrução do Orquestrador).

| Campo | Valor |
| :--- | :--- |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **Entrega** | `.agents/docs/design/plans/analytics-tendencia-ia.md` |
| **Regras de base** | P-150..P-187 (`business_rules/analytics-tendencia-ia.md`), §3.7 e §3.9 do plano de tarefas |
| **Tokens** | `frontend/src/styles.scss` (Papel & Tinta); nenhum token novo |
| **Próximo** | Checkpoint com o usuário; `architect` confirma os campos da §11 do plano; `developer` na fase 7.3 |

## Resumo
- **Entrada:** botão "Por que?" na linha 2 da célula do produto (tabela ≥ 768 px, sem coluna nova) e no rodapé do cartão (< 768 px). Abre na janela ordenada da tabela; `?porque={sku}` na URL.
- **Painel:** diálogo lateral (720 px ≥ 1024; 640 px no tablet) ou tela cheia (< 768 px), `aria-modal`, `inert` no fundo, foco preso, foco inicial no título, devolução ao botão de origem. Cabeçalho fixo com seletor de janela.
- **Ordem do corpo:** resumo (número herói + selo de mercado + atalho para a IA) → cascata em tabela visível com barras `aria-hidden` (alta listrada, queda lisa, resíduo tracejado; R$/un, p.p. e confiança; "não avaliado" com motivo) + sinais sem valor → "Esta alta está tirando vendas de…" (altas/novos) → grupo afim (mesmo × outro fornecedor, semelhança %, variação, links para a Canibalização) → bloco de IA.
- **Bloco de IA, 8 estados (contrato 1.1.0):** vazio, gerando (tempo decorrido, sem percentual), sucesso (`llm`/`fallback`), salva com data (`cache`), confirmação inline de "Gerar de novo", resumo automático (`template`: 200 neutro para IA indisponível/orçamento esgotado/gates), limite de pedidos (429 `LIMITE_DE_PEDIDOS`/`LIMITE_DIARIO`), erro. Botão único; sem "Análise aprofundada"/Neon. **Nenhum gasto, dólar, saldo ou nível de orçamento na UI.** Selo de origem: `Gerada por IA` / `Análise salva` / `Resumo automático (sem IA)`. `explicacao` por fator; contagens `"<3"` como "menos de 3 clientes"; fonte `SEM_DATA` com "sem data de publicação"; `DIAGNOSTICO_DESATUALIZADO` removido. Aviso fixo de IA (só quando há IA); fontes com domínio e data; hipóteses em contêiner tracejado separado.
- **Reuso:** `SegmentedControl`, `TrendCell`, `InlineNotice`, `TrendErrorBanner`, `TrendEmptyState`, pipes da Tendência, `ViewportService`; da F6: `brl`/`signedBrl`, `MECHANISM_VISUAL_META` (extrair), padrão de focus trap do `price-equilibrium-drawer` (extrair), padrão de `analytics-error`. `searchable-combobox` não é usado (sem filtro no painel).

## Dúvidas para o checkpoint (detalhe na §13 do plano)
1. `pontosPercentuais` por parcela no contrato (Q-D1).
2. Deep link `?abrir={sku}` na página de Canibalização para abrir o drawer (Q-D2).
3. Célula do afim no formato `TrendCell` (Q-D3).
4. Extrair focus trap e `MECHANISM_VISUAL_META` da F6 para utilitários compartilhados (Q-D4, Q-D5).
5. `impactoEmOutrosProdutos` já no GET (Q-D6); `meta.ia` (Q-D7) resolvida pelo contrato 1.1.0.
6. Janela em meses × período de 90 dias da Canibalização nos links (Q-D8).

## Log
- **2026-11-24 — designer:** Plano alinhado ao contrato `sales-trend-insights.md` 1.1.0 (origem, template 200, limites 429, sem custo na UI, sem Neon/aprofundada).
- **2026-11-24 — designer:** Design Plan F7 criado (painel "Por que?", cascata acessível, grupo afim, impacto, bloco de IA com 8 estados, copy completa, filtro Anti-IA).
