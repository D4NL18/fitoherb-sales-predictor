# Design Plan: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-elasticidade.md`
> **Responsável:** Designer (`designer`) / `uiux-expert`
> **Auditor:** UX Reviewer (`ux_reviewer`)
> **Status:** Atualizado pós-revisão UI/UX (Design System Papel & Tinta)
> **Alinhamento:** `frontend/src/styles.scss`, `frontend/src/app/features/analytics/styles/_analytics-ui.scss` e `frontend-ui-anti-patterns.md`

---

## 1. Visão Geral e Filosofia Visual (Papel & Tinta)

A funcionalidade de Elasticidade-Preço entrega transparência analítica para tomadores de decisão comercial dentro da shell compartilhada de Analytics (`AnalyticsShellComponent`), seguindo integralmente o sistema visual **Papel & Tinta** (editorial, orgânico, sem gradientes genéricos nem cores Tailwind hardcoded):
- Superfícies em papel quente (`--bg-canvas: #F5F2EB`, `--bg-surface: #FFFFFF`, `--bg-subtle: #ECE7DC`, `--bg-muted: #E2DDD0`), tinta vegetal escura (`--text-primary: #181D19`) e verde botânico (`--brand-primary: #1D4528`).
- Métricas econômicas claras: Coeficiente Beta ($\beta$), Classificação (`ELASTICO` vs `INELASTICO`), Intervalo de Confiança 95%, Peso Bayesiano (*Shrinkage*) por cliente e Simulação Reativa.
- Tipografia alinhada ao sistema: títulos em `Signika` (`--font-display`), corpo em `Source Sans 3` (`--font-sans`) e métricas numéricas / códigos em `Overpass Mono` (`--font-mono`) com `tabular-nums` e formatação brasileira (`BrlPipe`, `PtDecimalPipe`, `PtPercentPipe`).

---

## 2. Macroestrutura da Tela (`/analytics/elasticidade`)

Fluxo flush dentro da largura do `AnalyticsShellComponent`, composto por 4 blocos ordenados e componetizados com `ChangeDetectionStrategy.OnPush`:

1. **Busca de Produto (`CodeSearchFormComponent` compartilhado):**
   - Campo unificado com autocomplete por código SKU ou descrição (`[enableProductSearch]="true"`).
   - Sincronização bidirecional segura apenas com `?sku=` na URL (LGPD: `customerCode` nunca vai para URL, `localStorage` ou `sessionStorage`).
2. **Card de Diagnóstico (`ElasticityDiagnosticCardComponent`):**
   - Badges semânticos usando `.tag` globais (`tag-warning` / `tag-positive` / `tag-info` / `tag-neutral`) acompanhados de ícones SVG direcionais (nunca depender só de cor).
   - 4 tiles com `Overpass Mono`: Coeficiente Beta, Intervalo de Confiança 95% + Erro Padrão, $R^2$ + Meses Válidos e Preço/Custo/Estoque atuais.
   - Aviso `role="note"` quando `fallbackApplied=true` (estimador defensivo `-1,20`) ou `isReliable=false` (baixa confiabilidade estatística).
3. **Painel do Simulador de Reajuste (`ElasticitySimulatorPanelComponent`):**
   - Header com atalhos rápidos (`-10%`, `-5%`, `0% (Atual)`, `+5%`, `+10%`, `+20%`) com `min-height: 40px` (`$touch-target`).
   - Quando um cliente é selecionado/consultado, card dedicado de detalhe individual (`GET /elasticity/products/{sku}/customers/{customerCode}`) exibindo Elasticidade do Produto vs Empírica vs Shrinkage e peso histórico (`shrinkageWeight`), com botão de retorno à visão geral.
   - Slider (`-50%` a `+100%`) com marcas posicionadas geometricamente (`0%` em `33.33%`), debounce de `180ms` + `switchMap`, **sem jamais desabilitar o slider durante arrasto** (apenas trava atalhos e sinaliza `aria-busy="true"` nos cards), sincronizado com input numérico rotulado.
   - Barra de comparação Preço Atual $\rightarrow$ Preço Projetado (`projectedPrice`) + Elasticidade Aplicada (`appliedElasticity`), seguida de 3 cards de impacto (Volume, Faturamento, Margem de Contribuição) com ícones SVG de tendência, deltas assinados pt-BR (`-R$ 232,21`, `+5,0%`) e barra de recomendação adaptativa.
4. **Tabela de Clientes Paginada (`ElasticityCustomersTableComponent`):**
   - Filtro local na página + consulta direta de código exato na API (`GET .../customers/{customerCode}` com isolamento `ELA-002`), botão limpar e ordenação acessível (`aria-sort`) por Código, Pedidos, Volume e Elasticidade Ajustada.
   - Paginação server-side via `<app-list-pager>` (`DEFAULT_PAGE_LIMIT = 50`, usando `meta.totalItems` / `meta.totalPages`), preservando a página atual em caso de erro de troca de página.
   - Abaixo de `$bp-mobile` (`639.98px`), tabela converte-se em cards empilhados com `data-label` sem overflow horizontal.

---

## 3. Os 8 Estados Interativos Mandatórios

| Estado | Experiência Implementada |
| :--- | :--- |
| **1. Initial / Idle** | `<app-result-state>` (`buildElasticityInitialState`) sem chamada automática de API até que o usuário busque ou abra URL com `?sku=`. Botão de ação foca o input de busca. |
| **2. Loading** | `<app-elasticity-skeleton>` fiel à geometria do diagnóstico, simulador e tabela com `aria-busy="true"` e `@include ui.reduced-motion`. |
| **3. Success** | Dados renderizados em `pt-BR` via `BrlPipe`, `PtDecimalPipe`, `PtPercentPipe` e região `p.sr-only[role="status"][aria-live="polite"]` anunciando produto e simulação. |
| **4. Empty** | Produto sem clientes individuais exibe `<app-result-state>` específico na tabela sem ocultar diagnóstico/simulador; filtro sem correspondência exibe botão "Limpar filtro". |
| **5. Error** | `<app-error-banner>` amigável via `analytics-error.ts` (`ELA-001`..`ANL-002` mapeados; 500/rede caem no fallback genérico sem expor `detail` ou fabricar códigos falsos) + retry. `ELA-003` renderiza estado de histórico insuficiente. |
| **6. Busy / Disabled** | Durante simulação em voo, slider permanece manipulável (não perde foco/ponteiro); atalhos e ações de linha ficam desabilitados e a grade de projeção recebe `aria-busy="true"`. |
| **7. Invalid** | Percentual fora de `[-50, 100]` ou SKU inválido marcam `aria-invalid="true"`, exibem alerta inline e bloqueiam chamadas HTTP inválidas. |
| **8. Partial / Low-Confidence** | Bloco `role="note"` com destaque visual de alerta contrastante explicando fallback `-1,20` (`fallbackApplied`) ou baixa confiabilidade amostral (`!isReliable`). |

---

## 4. Tokens, Contraste WCAG AA e Acessibilidade

- **Tokens Papel & Tinta obrigatórios (`frontend/src/styles.scss`):**
  - `--bg-canvas`, `--bg-surface`, `--bg-subtle`, `--bg-muted`, `--bg-table-header`, `--bg-table-row-hover`, `--bg-table-row-zebra`.
  - `--brand-primary`, `--brand-primary-hover`, `--brand-primary-subtle`, `--brand-secondary`, `--brand-secondary-subtle`.
  - `--text-primary`, `--text-secondary`, `--text-muted`, `--text-on-brand`, `--border-default`, `--border-strong`, `--border-focus`.
  - `--feedback-positive-bg` (`#185A2E`), `--feedback-warning-bg` (`#7A4607`), `--feedback-critical-bg` (`#8F1B1B`), `--feedback-info-bg` (`#1B4B7A`), `--feedback-neutral-bg` (`#3B423C`): usados apenas com texto branco `--text-on-brand`, ou como cor de texto/borda sobre superfícies claras.
  - Sobre `--bg-subtle`, usar `--text-secondary` ou `--text-primary` (nunca `--text-muted`, evitando contraste < 4.5:1).
- **Acessibilidade:**
  - Região `aria-live="polite"` exclusiva da página para resultado de busca e simulação.
  - Inputs com `<label>` explícito, `aria-invalid`, `aria-describedby`, `role="alert"` em erros, `aria-pressed` em presets e seleção de cliente, `aria-sort` em colunas ordenáveis, `aria-valuemin`/`aria-valuemax`/`aria-valuenow`/`aria-valuetext` no slider e área de toque mínima de `40px` (`$touch-target`).
