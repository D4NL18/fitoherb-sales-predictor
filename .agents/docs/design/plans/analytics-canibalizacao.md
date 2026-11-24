# Design Plan (v2): Relatório de Canibalização por Migração de Clientes e Equilíbrio de Preço (F6)

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-canibalizacao.md`  
> **Versão:** `2.0` (Pivô Funcional F6 — substitui integralmente o modo DiD de evento isolado e a aba Mapa de Substitutos)  
> **Responsável:** Designer UI/UX (`uiux-expert` / `designer.md`) — Etapa 2  
> **Fonte Única de Design Tokens:** `frontend/src/styles.scss` (**Papel & Tinta**) e `frontend/src/app/features/analytics/styles/_analytics-ui.scss`. *(O arquivo `.agents/docs/design/DESIGN_SYSTEM.md` contém placeholders genéricos não customizados e **NÃO** deve ser usado para cores, fontes ou tokens CSS).*  
> **Referência de Padrão de Tabela & Combobox:** `frontend/src/app/features/analytics/components/product-catalog-explorer/product-catalog-explorer.component.html`

---

## Pre-Emit Critique Stamp (Hallmark v1.1)

`/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 */`

- **Identidade & Paleta (Filtro Anti-IA Slop):** 100% aderente ao sistema editorial utilitário **Papel & Tinta** de `frontend/src/styles.scss` (`--bg-canvas: #F5F2EB`, `--bg-surface: #FFFFFF`, `--brand-primary: #1D4528`, `--brand-secondary: #8A4B14`, `--text-primary: #181D19`, `Signika` + `Source Sans 3` + `Overpass Mono`). Zero hexadecimais hardcoded em componentes, zero gradientes, zero glassmorphism, zero cabeçalhos em itálico, zero ícones decorativos clichês.
- **Contraste AA/AAA & Segurança para Daltonismo:** Os tokens `--feedback-positive-bg` (`#185A2E`), `--feedback-warning-bg` (`#7A4607`), `--feedback-critical-bg` (`#8F1B1B`), `--feedback-info-bg` (`#1B4B7A`) e `--feedback-neutral-bg` (`#3B423C`) são **fundos sólidos escuros para texto branco (`--text-on-brand: #FFFFFF`)**, usados exclusivamente em badges `.tag-*` ou como cor de texto e **borda esquerda de `3px` sobre `--bg-surface`**. Toda severidade e ação de equilíbrio combina **cor + símbolo (`▼`, `▲`, `↗`) + sinal tipográfico (`−` `U+2212` / `+`) + rótulo textual**.
- **Arquétipo & Densidade:** Dashboard Operacional/Analítico orientado a diagnóstico acionável (**Padrão F**, máximo de 4 blocos visíveis no viewport principal, 15–20% de área livre em `--bg-canvas`, zero gráficos decorativos redundantes).
- **Reuso Real do Módulo `analytics`:** Reutiliza `AnalyticsShellComponent`, `ANALYTICS_SECTIONS`, `ANALYTICS_ROUTES`, `ErrorBannerComponent`, `ResultStateComponent`, `ListPagerComponent`, `analytics-error.ts`, `pt-br-format.pipes.ts`, `_analytics-ui.scss` e o padrão acessível de **combobox pesquisável + tabela ordenável** de `ProductCatalogExplorerComponent`.
- **Copy Honesto & Governança LGPD:** PT-BR direto voltado a gestores comerciais e precificadores; valores numéricos nos wireframes explicitamente marcados como ilustrativos; **zero `Cod Cliente` ou PII** em telas, tooltips, URLs ou logs (exibe apenas contagens agregadas de clientes migrados).

---

## 1. Alinhamento com o Design System Real ("Papel & Tinta")

### 1.1. Tokens Canônicos (`frontend/src/styles.scss` + `_analytics-ui.scss`)

| Categoria | Token Real (`styles.scss` / `_analytics-ui.scss`) | Valor / Regra no Projeto | Onde Aplicar na F6 (v2) |
| :--- | :--- | :--- | :--- |
| **Superfícies** | `--bg-canvas` | `#F5F2EB` | Fundo geral da página dentro do `AnalyticsShellComponent` |
| | `--bg-surface` | `#FFFFFF` | Cards de KPI, painel da tabela (`@include ui.panel`), banners, cards mobile e drawer lateral |
| | `--bg-subtle` | `#ECE7DC` | Controle segmentado inativo (período), resumo da vítima no drawer, hover de botões secundários |
| | `--bg-muted` | `#E2DDD0` | Skeleton loaders (`.skeleton-box` / `.skeleton-line`) e estado `:active` de botão secundário |
| | `--bg-table-header` | `#F0ECE1` | Cabeçalho `<thead>` da tabela principal de produtos canibalizados |
| | `--bg-table-row-hover` | `#F7F5EE` | Hover de linhas clicáveis em desktop (`@include ui.hover`) |
| | `--bg-table-row-zebra` | `#FAF8F4` | Linhas alternadas (zebra) da tabela |
| | `--bg-table-col-sorted` | `#F6F8F6` | Realce sutil da coluna atualmente ordenada |
| | `--bg-overlay` | `rgba(24, 28, 24, 0.55)` | Backdrop escurecido do Drawer de Equilíbrio de Preço |
| **Tipografia** | `--font-family-headline` | `'Signika', 'Trebuchet MS', sans-serif` | Título `<h2>`, valores hero dos 4 KPIs e título `<h3>` do drawer (sempre estilo romano, nunca itálico) |
| | `--font-family-body` | `'Source Sans 3', sans-serif` | Subtítulo, labels de filtro, descrições de produto, justificativas de equilíbrio e botões |
| | `--font-family-mono` | `'Overpass Mono', monospace` | SKUs, preços (`R$`), faturamento, `R$ Perdido`, `% Redução`, gap `%`, margens e contagens (`tabular-nums`) |
| **Hierarquia Texto** | `--text-primary` | `#181D19` | Títulos, descrições de produto, valores principais e corpo de texto |
| | `--text-secondary` | `#434B44` | Subtítulos, labels de filtro, metadados (`Categoria · Fornecedor`) e **texto obrigatório sobre `--bg-subtle`, `--bg-table-header` e `--brand-primary-subtle`** |
| | `--text-muted` | `#666F67` | Legendas auxiliares e valores riscados (faturamento anterior) **exclusivamente sobre `--bg-surface` (`#FFFFFF`) ou `--bg-canvas` (`#F5F2EB`)** (garantia WCAG AA $\ge 4{,}5:1$) |
| | `--text-on-brand` | `#FFFFFF` | Texto dentro de botões primários, período ativo e badges `.tag-*` |
| **Marca & Ação** | `--brand-primary` | `#1D4528` | Período selecionado, ação primária (`%button-primary`), foco e indicador de ordenação ativa |
| | `--brand-primary-hover` | `#14321C` | Hover de controles primários (`@include ui.hover`) |
| | `--brand-primary-active` | `#0E2414` | Estado `:active` de controles primários |
| | `--brand-primary-subtle` | `#E5EFE7` | Badge de contagem de resultados, opção selecionada no combobox e linha selecionada para o drawer (sempre com texto `--text-primary` ou `--brand-primary`) |
| | `--brand-secondary` | `#8A4B14` | Realce secundário discreto quando necessário |
| **Bordas & Foco** | `--border-subtle` | `#DFD9CC` | Divisórias internas de tabela, separadores de cards e blocos internos do drawer |
| | `--border-default` | `#CBC3B2` | Contorno de painéis (`@include ui.panel`), inputs, comboboxes e selects |
| | `--border-strong` | `#9E9686` | Contorno em hover de inputs e borda estrutural de destaque |
| | `--border-focus` | `#1D4528` | Anel `:focus-visible` global (`2px solid var(--border-focus); outline-offset: 2px`) |
| **Espaço & Raio** | `--space-1` .. `--space-8` | `4px` a `32px` | Ritmo entre blocos (`--space-4` / `--space-5`) e padding interno (`--space-4` / `--space-6`) |
| | `--radius-xs` / `--radius-sm` / `--radius-md` | `3px` / `5px` / `7px` | Badges/inputs (`--radius-xs`), painéis/cards (`--radius-sm`), dropdown/drawer (`--radius-md`) |
| **Breakpoints & Touch** | `$bp-mobile` / `$bp-tablet` / `$touch-target` | `639.98px` / `1023.98px` / `40px` | Cards mobile abaixo de `640px`; controles tocáveis sempre $\ge 40\text{px}$ ($\ge 44\text{px}$ em ações móveis e botão fechar) |

### 1.2. Regra Crítica de Contraste Semântico (Zero Pastel Ilegível)

> [!CAUTION]
> Em `frontend/src/styles.scss`, todos os tokens `--feedback-*-bg` são **fundos sólidos escuros** projetados para texto branco (`#FFFFFF`). Jamais usar `--feedback-*-bg` como fundo de banner com texto escuro. Em banners e blocos de recomendação, usar `--bg-surface` + `border-left: 3px solid var(--feedback-*-bg)` + texto `--text-primary`.

| Semântica na F6 (v2) | Token Sólido | Padrão 1: Badge `.tag-*` | Padrão 2: Bloco / Banner Lateral | Padrão 3: Valor Inline na Tabela |
| :--- | :--- | :--- | :--- | :--- |
| **Queda Severa ($\ge 30\%$) / Perda Financeira / Erro Crítico** | `--feedback-critical-bg: #8F1B1B` | `.tag.tag-critical` (`▼ −34,2%`) — texto `#FFFFFF` | `--bg-surface` + `border: 1px solid var(--border-subtle)` + `border-left: 3px solid var(--feedback-critical-bg)` | Texto `--feedback-critical-bg` sobre `--bg-surface` com sinal `−` (`−R$ 4.820,00`) |
| **Queda Moderada ($15\%$–$29{,}9\%$) / Ação: `Reajustar canibalizador`** | `--feedback-warning-bg: #7A4607` | `.tag.tag-warning` (`▼ −21,5%` ou `▲ Reajustar canibalizador`) — texto `#FFFFFF` | `--bg-surface` + `border-left: 3px solid var(--feedback-warning-bg)` + título `--feedback-warning-bg` | Texto `--feedback-warning-bg` sobre `--bg-surface` |
| **Ação: `Ajustar preço da vítima`** | `--feedback-info-bg: #1B4B7A` | `.tag.tag-info` (`▼ Ajustar preço da vítima`) — texto `#FFFFFF` | `--bg-surface` + `border-left: 3px solid var(--feedback-info-bg)` + título `--feedback-info-bg` | Texto `--feedback-info-bg` sobre `--bg-surface` |
| **Ação: `Migração por valor` (saudável)** | `--feedback-positive-bg: #185A2E` | `.tag.tag-positive` (`↗ Migração por valor`) — texto `#FFFFFF` | `--bg-surface` + `border-left: 3px solid var(--feedback-positive-bg)` + título `--feedback-positive-bg` | Texto `--feedback-positive-bg` sobre `--bg-surface` com prefixo `↗` |
| **Queda Leve ($< 15\%$) / Neutro** | `--feedback-neutral-bg: #3B423C` | `.tag.tag-neutral` (`▼ −9,4%`) — texto `#FFFFFF` | `--bg-surface` + `border: 1px solid var(--border-subtle)` | Texto `--text-secondary` |

---

## 2. Reuso do Módulo `analytics` e Inventário de Componentes

A feature F6 reside na rota `/analytics/canibalizacao` dentro de `AnalyticsShellComponent` (que já declara `<h1>Análises de Vendas</h1>` e a barra de navegação de seções). Portanto, a página F6 inicia sua hierarquia de títulos em **`<h2>`**, sem repetir `<h1>`.

### 2.1. Substituição Completa da v1 (Limpeza Arquitetural)

Ficam **removidos** da interface de F6:
- `ModeSwitchComponent` (não existem mais duas abas; a visão única é o Relatório de Canibalização e Equilíbrio de Preço).
- `CodeSearchFormComponent` de busca de SKU isolado e formulário de eventos DiD (`promo`/`price`/`launch`, `eventDate`, `windowWeeks`).
- `NetImpactCardComponent`, `CannibalizationTimelineComponent` (gráfico SVG $T_0$) e `SubstitutionMapPanelComponent`.

### 2.2. Reuso Obrigatório de Infraestrutura Existente

| Artefato Existente (`frontend/src/app/features/analytics/`) | Uso na F6 (v2) |
| :--- | :--- |
| `pages/analytics-shell/` + `analytics.routes.ts` | Mantém rota `/analytics/canibalizacao` e item `{ id: 'canibalizacao', label: 'Canibalização', route: '/analytics/canibalizacao' }` em `ANALYTICS_SECTIONS`. |
| `components/error-banner/` | Banner de erro de API/rede (`CAN-005`, `ANL-001`, timeout) com botão `"Tentar novamente"`. |
| `components/result-state/` | Estado vazio do período (nenhum produto canibalizado detectado nos últimos `N` dias) com CTA para ampliar período (`90 dias`). |
| `components/list-pager/` | Paginação cliente 1-based (`20` itens por página; oculta automaticamente quando `totalPages <= 1`). |
| `utils/analytics-error.ts` | Parsing sanitizado de `{ error: { code, message, fields }, meta }` (zero stacktrace, zero eco de input bruto). |
| `pipes/pt-br-format.pipes.ts` | `brl`, `ptDecimal`, `ptDate` e formatação com sinal menos tipográfico `−` (`U+2212`) e `tabular-nums`. |
| `styles/_analytics-ui.scss` | `@include ui.panel`, `%button-primary`, `%button-secondary`, `@include ui.hover`, `@include ui.reduced-motion`, `@include ui.sr-only`, `@include ui.caption`. |
| Padrão `ProductCatalogExplorerComponent` | Referência direta de HTML/SCSS/acessibilidade para a **toolbar com busca + comboboxes pesquisáveis (Fornecedor e Categoria)**, subbar de contagem + `"Limpar filtros"` e tabela ordenável com `aria-sort`. |

### 2.3. Componentes Específicos da F6 (v2)

1. `pages/cannibalization-page/` (`CannibalizationPageComponent` + `CannibalizationStore` provida localmente na página) — cabeçalho, seletor de período (`30` / `60` / `90` dias), orquestração dos KPIs, tabela e drawer.
2. `components/cannibalization-kpi-strip/` — faixa de 4 KPIs executivos no topo da tela.
3. `components/cannibalization-report-table/` — painel completo com barra de busca, **2 comboboxes pesquisáveis** (`Fornecedor` e `Categoria`), select de ordenação, tabela clicável desktop (`>= 640px`), cards empilhados mobile (`< 640px`) e `ListPagerComponent`.
4. `components/price-equilibrium-drawer/` — drawer lateral (`role="dialog" aria-modal="true"`) com resumo da vítima + lista de produtos canibalizadores + comparativo de preço/margem + bloco de recomendação de equilíbrio de preço.
5. `components/cannibalization-skeleton/` — skeleton solid-pulse geométrico (4 KPIs + toolbar + 6 linhas) + aviso de consulta lenta após `4000ms` (`SLOW_QUERY_NOTICE_MS`).
6. `components/searchable-combobox/` *(opcional/recomendado extrair como componente burro reutilizável dentro de `analytics/components/`)* — encapsula o padrão ARIA combobox/listbox com busca interna, teclado e botão limpar `×` usado tanto para **Fornecedor** quanto para **Categoria (`Tipo`)**, evitando duplicação de lógica.

---

## 3. Arquitetura da Informação, Wireframes e Anatomia Visual

### 3.1. Visão Desktop (`>= 1024px`) — Tela Principal (Padrão F)

```text
+-----------------------------------------------------------------------------------------+
| [BLOCO 1: CABEÇALHO & SELETOR DE PERÍODO]                                               |
|                                                                                         |
|  [h2] Relatório de Canibalização e Equilíbrio de Preço     Período: [30d][60d][● 90d]   |
|  Produtos com queda de faturamento atribuída à migração de clientes para outros itens   |
|  do portfólio, com recomendações de preço para restaurar o equilíbrio de margem.        |
|  Base: últimos 90 dias vs. 90 dias anteriores · Pedidos até 12/11/2026                  |
+-----------------------------------------------------------------------------------------+

+-----------------------------------------------------------------------------------------+
| [BLOCO 2: KPIs EXECUTIVOS — grid 4 colunas minmax(0, 1fr), gap --space-3]               |
|                                                                                         |
| +--------------------+ +--------------------+ +--------------------+ +----------------+ |
| | PRODUTOS           | | FATURAMENTO PERDIDO| | QUEDA MÉDIA        | | PRINCIPAL      | |
| | CANIBALIZADOS      | | (CANIBALIZAÇÃO)    | | ATRIBUÍDA          | | CATEGORIA      | |
| |                    | | [borda esq. 3px    | | [borda esq. 3px    | | AFETADA        | |
| |  18                | |  critical-bg]      | |  critical-bg]      | |  EXTRATOS      | |
| |  SKUs afetados     | |  −R$ 42.850,00     | |  ▼ −28,4%          | |  7 SKUs ·      | |
| |  no período        | |  por migração      | |  sobre fat. ant.   | |  −R$ 19.400,00 | |
| +--------------------+ +--------------------+ +--------------------+ +----------------+ |
+-----------------------------------------------------------------------------------------+
*(Valores numéricos nos wireframes são meramente ilustrativos da geometria e formatação.)*

+-----------------------------------------------------------------------------------------+
| [BLOCO 3 & 4: PAINEL DO RELATÓRIO — @include ui.panel]                                  |
|                                                                                         |
| [TOOLBAR DE FILTROS — role="search"]                                                    |
|  Busca (SKU / produto)            Fornecedor (combobox)     Categoria / Tipo (combobox) |
|  [🔍 Buscar SKU, produto...]      [Todos (14)          ▾]   [Todas (8)             ▾]   |
|                                                                                         |
|  Ordenação                                                                              |
|  [% Redução por Canibalização (maior ↓)                                            ▾]   |
|                                                                                         |
|  Mostrando 1–18 de 18 produtos canibalizados   [Limpar filtros]                         |
|-----------------------------------------------------------------------------------------|
| Produto             | Preço    | Faturamento         | % Redução    | R$ Perdido   | Principal Canibalizador | Ação             |
|                     | atual ▲▼ | Anterior → Atual ▲▼ | (Canib.) ▼   | ▲▼           | (Clientes migrados) ▲▼  |                  |
|---------------------|----------|---------------------|--------------|--------------|-------------------------|------------------|
| 100235              | R$ 22,00 | R$ 14.200,00 →      | [.tag-crit.] | −R$ 4.820,00 | Extrato Própolis Verde  | [Equilibrar      |
| Extrato Própolis    |          | R$ 9.380,00         | ▼ −33,9%     |              | 14 clientes migrados    |  preço]          |
| Aquoso 30ml         |          |                     |              |              | +2 outros               |                  |
| EXTRATOS · Apis     |          |                     |              |              |                         |                  |
|---------------------|----------|---------------------|--------------|--------------|-------------------------|------------------|
| 100288              | R$ 28,00 | R$ 8.640,00 →       | [.tag-warn.] | −R$ 1.890,00 | Extrato Própolis Verde  | [Equilibrar      |
| Extrato Equinácea   |          | R$ 6.750,00         | ▼ −21,9%     |              | 8 clientes migrados     |  preço]          |
| EXTRATOS · BioNat   |          |                     |              |              |                         |                  |
|---------------------|----------|---------------------|--------------|--------------|-------------------------|------------------|
| [ListPagerComponent — oculto quando totalPages <= 1]                                    |
+-----------------------------------------------------------------------------------------+
```

#### Detalhes de Layout e Comportamento da Tabela Base

1. **Seletor de Período (`30 dias` / `60 dias` / `90 dias`):**
   - Implementado como controle segmentado (`role="group" aria-label="Período de análise"`) com 3 `<button type="button" [attr.aria-pressed]="period() === opt">`.
   - Padrão inicial: **`90 dias`**.
   - Altura mínima `40px` (`$touch-target`), fundo inativo `--bg-subtle` com texto `--text-secondary`; ativo `--brand-primary` com texto `--text-on-brand`.
   - Ao trocar o período, dispara nova consulta (cancelando requisição anterior via `switchMap`), fecha o drawer se aberto e mantém filtros compatíveis (resetando `fornecedor`/`categoria` apenas se não existirem mais no novo período).

2. **Comboboxes Pesquisáveis (`Fornecedor` e `Categoria / Tipo`):**
   - Seguem fielmente a mecânica acessível de `ProductCatalogExplorerComponent`:
     - Botão trigger com `aria-haspopup="listbox"`, `[attr.aria-expanded]`, `[attr.aria-controls]`, label truncada com `text-overflow: ellipsis`, chevron rotativo e botão limpar `×` quando há seleção ativa.
     - Dropdown ancorado (`position: absolute; z-index: 20; background: var(--bg-surface); border: 1px solid var(--border-default); box-shadow: var(--shadow-md)`), contendo input `type="search"` com foco automático ao abrir (`"Buscar fornecedor..."` / `"Buscar categoria..."`) e `<ul role="listbox">`.
     - Cada opção `<li role="option">` mostra o nome à esquerda e a contagem de produtos canibalizados (`tabular-nums`) à direita; suporte a navegação por setas (`ArrowDown`/`ArrowUp`), `Enter` para selecionar e `Escape` para fechar devolvendo foco ao trigger.
     - Busca interna case-insensitive e sem acentos (normalização NFD), exibindo mensagem amigável quando nenhuma opção corresponder.

3. **Ordenação Completa de Colunas (6 critérios obrigatórios):**
   - O `<select>` de ordenação na toolbar e os botões `<button class="sort-header-btn">` no `<thead>` ficam **100% sincronizados**, suportando direção crescente/decrescente para todos os critérios:
     1. `% Redução por Canibalização` (padrão inicial: **maior redução primeiro**, `▼`)
     2. `R$ Perdido`
     3. `Faturamento Anterior`
     4. `Faturamento Atual`
     5. `Preço Atual`
     6. `Canibalizadores` (quantidade de produtos canibalizadores associados à vítima)
   - Na coluna `Faturamento`, o cabeçalho oferece ordenação clara (ex.: clique alterna `Faturamento Atual` e o `<select>` expõe explicitamente `Faturamento Anterior (maior/menor)` e `Faturamento Atual (maior/menor)`, ou duas sub-ações discretas no cabeçalho). A coluna ativa recebe fundo `--bg-table-col-sorted` e `aria-sort="ascending" | "descending"`.

4. **Interação de Clique na Linha + Botão Semântico:**
   - Toda linha `<tr>` tem `cursor: pointer`, hover `--bg-table-row-hover` (`@include ui.hover`) e abre o **Drawer de Equilíbrio de Preço** ao clicar.
   - A última coluna mantém sempre o botão semântico `<button type="button" class="btn-row-action">Equilibrar preço</button>` (`$event.stopPropagation()`), garantindo acessibilidade total para teclado e leitores de tela (`aria-label="Equilibrar preço de [SKU] [Descrição]"`).
   - Enquanto o drawer está aberto para um item, sua linha na tabela recebe a classe `.is-selected` (`background: var(--brand-primary-subtle)` com borda esquerda `3px solid var(--brand-primary)`).

---

### 3.2. Versão Tablet (`640px`–`1023.98px`) e Mobile (`< 640px`)

- **Tablet (`640px`–`1023.98px`, `$bp-tablet: 1023.98px`):**
  - Cabeçalho empilha subtítulo e seletor de período se necessário; seletor de período ocupa linha própria com botões distribuídos igualmente (`flex: 1`).
  - KPIs viram grid `2 × 2` (`grid-template-columns: repeat(2, minmax(0, 1fr))`).
  - Toolbar de filtros vira grid `2 × 2` com `Busca` ocupando `grid-column: 1 / -1` na primeira linha, `Fornecedor` e `Categoria` na segunda linha, e `Ordenação` logo abaixo.
  - Tabela permanece visível em container `.table-scroll-wrap` compacto; coluna `Principal Canibalizador` trunca nome em 1 linha.

- **Mobile (`< 640px`, `$bp-mobile: 639.98px` — 320 / 375 / 414 px):**
  - Zero scroll horizontal (`overflow-x: clip` global, grids `minmax(0, 1fr)`, `overflow-wrap: anywhere; min-width: 0` em descrições).
  - Seletor de período: 3 botões iguais em linha única (`30d` / `60d` / `90d` ou `30 dias` / `60 dias` / `90 dias` sem quebra de linha, altura `>= 44px`).
  - KPIs: empilhados em grid `2 × 2` compacto em `>= 375px` ou `1fr` em `320px`, sem textos truncados.
  - Toolbar de filtros: coluna única (`1fr`), todos os inputs/comboboxes com altura `>= 44px`.
  - **Cards Empilhados substituem a tabela** (`<ol class="cannibalization-card-list">`):
    - **Linha 1:** SKU (`--font-family-mono`) + badge `.tag-*` (`▼ −33,9%`).
    - **Linha 2:** Descrição do produto (`--text-primary`, bold) + `Categoria · Fornecedor` (`--text-secondary`).
    - **Linha 3 (grid 2 colunas `minmax(0, 1fr)`):** `R$ Perdido` (`−R$ 4.820,00`) e `Preço atual` (`R$ 22,00`).
    - **Linha 4:** `Faturamento: R$ 14.200,00 → R$ 9.380,00` (`tabular-nums`).
    - **Linha 5:** `Principal canibalizador:` Nome + `14 clientes migrados` (+ `+N outros` se aplicável).
    - **Linha 6:** Botão secundário full-width **`Equilibrar preço`** (`min-height: 44px`) abrindo o drawer full-screen sheet.

---

### 3.3. Drawer de Detalhe e Equilíbrio de Preço (`PriceEquilibriumDrawerComponent`)

```text
+---------------------------------------------------------------+
| [DIALOG HEADER — role="dialog" aria-modal="true"]             |
|  SKU 100235  [.tag-critical ▼ −33,9%]                  [ × ]  |
|  [h3] EXTRATO DE PRÓPOLIS AQUOSO 30ML                         |
|  Categoria: EXTRATOS · Fornecedor: APIS BRASIL                |
+---------------------------------------------------------------+
| [SEÇÃO 1: RESUMO DA VÍTIMA — fundo --bg-subtle, texto primary]|
|  +---------------------------+ +----------------------------+ |
|  | Faturamento (90d)         | | Perda por Canibalização    | |
|  | R$ 14.200,00 → R$ 9.380   | | −R$ 4.820,00 (▼ −33,9%)    | |
|  +---------------------------+ +----------------------------+ |
|  +---------------------------+ +----------------------------+ |
|  | Preço Atual               | | Margem Atual               | |
|  | R$ 22,00                  | | 43,2% (R$ 9,50 / un)       | |
|  +---------------------------+ +----------------------------+ |
|  *Nota discreta se fallback de custo (40% margem) foi usado*  |
+---------------------------------------------------------------+
| [SEÇÃO 2: PRODUTOS CANIBALIZADORES (3)]                       |
|  Contagem agregada de clientes migrados (sem dados pessoais). |
|                                                               |
|  +---------------------------------------------------------+  |
|  | #1 · SKU 100234 — EXTRATO DE PRÓPOLIS VERDE 30ML        |  |
|  | EXTRATOS · APIS BRASIL        [14 clientes migrados]    |  |
|  |                                                         |  |
|  | Impacto atribuído a este canibalizador:                 |  |
|  | −R$ 3.180,00  (66,0% da queda da vítima)                |  |
|  |                                                         |  |
|  | COMPARATIVO PREÇO             COMPARATIVO MARGEM        |  |
|  | Vítima:        R$ 22,00       Vítima:        43,2%      |  |
|  | Canibalizador: R$ 18,90       Canibalizador: 26,5%      |  |
|  | Gap: −14,1% mais barato       Diferença: −16,7 p.p.     |  |
|  |                                                         |  |
|  | +--[BLOCO EQUILÍBRIO DE PREÇO — borda esq. 3px]-------+ |  |
|  | | [.tag-warning ▲ Reajustar canibalizador]            | |  |
|  | | Preço sugerido (canibalizador): R$ 20,90 (+10,6%)   | |  |
|  | | Alternativa (ajustar vítima):   R$ 20,20 (−8,2%)    | |  |
|  | | O canibalizador está 14,1% abaixo da vítima com     | |  |
|  | | margem menor; reajustá-lo preserva rentabilidade.   | |  |
|  | +-----------------------------------------------------+ |  |
|  +---------------------------------------------------------+  |
|                                                               |
|  +---------------------------------------------------------+  |
|  | #2 · SKU 100290 — PRÓPOLIS VERDE PREMIUM 30ML           |  |
|  | ...                                                     |  |
|  | +--[BLOCO EQUILÍBRIO — borda esq. positive-bg]--------+ |  |
|  | | [.tag-positive ↗ Migração por valor]                | |  |
|  | | Manter preços atuais (canibalizador +27,3% mais     | |  |
|  | | caro e com margem superior: 48,0% vs 43,2%).        | |  |
|  | +-----------------------------------------------------+ |  |
|  +---------------------------------------------------------+  |
+---------------------------------------------------------------+
| [RODAPÉ FIXO DO DRAWER]                     [ Fechar painel ] |
+---------------------------------------------------------------+
```

#### Especificação dos 3 Estados do Bloco de Equilíbrio de Preço

| Ação Recomendada | Badge `.tag-*` (Cor + Símbolo) | Borda Esquerda `3px` | Dados Exibidos no Bloco |
| :--- | :--- | :--- | :--- |
| **`Reajustar canibalizador`** | `.tag.tag-warning` · `▲ Reajustar canibalizador` | `--feedback-warning-bg` | Preço sugerido para o **canibalizador** (`brl` + variação `%` em `tabular-nums`), preço alternativo para a vítima (se fornecido pelo contrato) e justificativa curta de proteção de margem. |
| **`Ajustar preço da vítima`** | `.tag.tag-info` · `▼ Ajustar preço da vítima` | `--feedback-info-bg` | Preço sugerido para a **vítima** (`brl` + variação `%` em `tabular-nums`), margem projetada pós-ajuste (se fornecida) e justificativa curta de competitividade. |
| **`Migração por valor`** | `.tag.tag-positive` · `↗ Migração por valor` | `--feedback-positive-bg` | Orientação para manter preços atuais (migração favorável para item de maior preço/margem), destacando o ganho de preço/margem relativa. |

#### Geometria, Acessibilidade e Teclado do Drawer
- **Largura:** `width: min(560px, 100vw)` em desktop/tablet; `100vw` full-height sheet em mobile (`< 640px`).
- **Semântica:** `<aside role="dialog" aria-modal="true" [attr.aria-labelledby]="titleId">` com cabeçalho e rodapé sticky e corpo rolável internamente (`overscroll-behavior: contain`).
- **Focus Trap & `inert`:** Ao abrir, o container principal da página recebe `[attr.inert]="drawerOpen() ? '' : null"`, o foco move-se programaticamente para o botão Fechar ou título (`tabindex="-1"`), `Tab`/`Shift+Tab` permanecem confinados no drawer, e `Esc` (ou clique no backdrop) fecha o drawer devolvendo o foco exatamente ao botão `"Equilibrar preço"` (ou linha) que o acionou.
- **Redução de Movimento:** `@include ui.reduced-motion` desativa a transição de slide lateral.

---

## 4. Matriz Completa dos 8 Estados Interativos

| # | Estado | Gatilho / Condição | Comportamento Visual e de Interação |
| :--- | :--- | :--- | :--- |
| **1** | **Default** | `200 OK` com lista de produtos canibalizados (`>= 1` item) | Exibe cabeçalho + período (`90 dias` ativo) + 4 KPIs executivos + painel da tabela com filtros, contagem e linhas clicáveis. |
| **2** | **Hover** | Ponteiro desktop (`@include ui.hover`) | Linhas da tabela usam `--bg-table-row-hover`; botões de ordenação destacam texto `--text-primary`; opções dos comboboxes usam `--bg-subtle`; botão `"Equilibrar preço"` eleva contraste de borda para `--brand-primary`. |
| **3** | **Focus-visible** | Navegação por teclado (`Tab` / setas) | Todos os botões, período, inputs, triggers de combobox, cabeçalhos ordenáveis e controles do drawer exibem `outline: 2px solid var(--border-focus); outline-offset: 2px`. |
| **4** | **Active** | Seleção de período, coluna ordenada, filtro ou drawer aberto | Período selecionado em `--brand-primary` + `--text-on-brand`; coluna ordenada em `--bg-table-col-sorted` + glifo `▲`/`▼`; linha aberta no drawer em `--brand-primary-subtle` + borda esquerda `3px solid var(--brand-primary)`; chips/combobox selecionados com botão `×`. |
| **5** | **Disabled** | Requisição em voo (`loading() === true`) ou limites do paginador | Botões de período (`30d`/`60d`/`90d`) ficam `disabled` durante carregamento; botões "Anterior"/"Próxima" do `ListPagerComponent` desabilitados nos extremos com `opacity: 0.5; cursor: not-allowed`. |
| **6** | **Loading** | Carregamento inicial ou troca de período (`loading() === true`) | **Zero spinner solitário.** `CannibalizationSkeletonComponent` replica a geometria real (4 cards de KPI + barra de filtros + 6 linhas da tabela) usando `.skeleton-box` e `.skeleton-line` (`@keyframes pulseSolid` de `styles.scss`, sem gradientes). Após `4000ms` (`SLOW_QUERY_NOTICE_MS`), exibe aviso `role="status"` com `aria-live="polite"`: *"Calculando migração de clientes e equilíbrio de preço na base de vendas — a primeira consulta pode levar alguns segundos."* |
| **7** | **Empty** | **(a)** `200 OK` com `0` produtos canibalizados no período;<br>**(b)** `0` resultados após aplicar busca/Fornecedor/Categoria | **(a) Período sem canibalização:** `ResultStateComponent` (alinhado à esquerda, sem borda tracejada) informando que não houve queda atribuída à migração de clientes nos últimos `N` dias, com CTA `"Analisar últimos 90 dias"` (quando período `< 90`) ou `"Atualizar relatório"`.<br>**(b) Filtros sem resultado:** Bloco empty state dentro do painel da tabela explicando que nenhum produto corresponde aos filtros atuais, com CTA secundário `"Limpar filtros"`. |
| **8** | **Error** | Falha de rede, timeout, `400 CAN-004`, `500 CAN-005` ou `503 ANL-001` | `ErrorBannerComponent` (`--bg-surface` + borda esquerda `3px solid var(--feedback-critical-bg)`), mensagem amigável sanitizada (nunca exibe stacktrace nem ecoa input bruto) e botão `"Tentar novamente"` que reexecuta a consulta do período atual. |

---

## 5. Diretrizes Técnicas para a Etapa 3 (Angular 18)

1. **Arquitetura Reativa:** Todos os componentes `standalone: true`, `changeDetection: ChangeDetectionStrategy.OnPush`, Signals (`signal`, `computed`, `input`, `output`).
2. **Controle de Concorrência (`switchMap` + `takeUntilDestroyed`):** `CannibalizationStore` (provida localmente em `CannibalizationPageComponent`, nunca `providedIn: 'root'`) deve disparar requisições por `Subject<PeriodDays>` ligado a `switchMap` + `takeUntilDestroyed`, cancelando chamadas obsoletas ao alternar rapidamente entre `30`, `60` e `90` dias.
3. **Filtros e Ordenação Client-Side Instantâneos:** Sobre o conjunto retornado para o período selecionado, a busca (SKU/descrição/canibalizador com normalização NFD sem acento), os comboboxes de `Fornecedor` e `Categoria (Tipo)`, a ordenação pelas 6 colunas e a paginação (`20` itens/página) operam via `computed()` com latência zero, atualizando contadores de opções dinamicamente.
4. **Sincronização Segura de URL (`replaceUrl: true`):**
   - Query params canônicos: `?periodo=30|60|90&busca=...&fornecedor=...&categoria=...&ordenar=...`.
   - Sanitização estrita na leitura inicial (`periodo` só aceita `30 | 60 | 90`, caindo para `90` se inválido).
   - **Proibição de Armazenamento Local:** Zero `localStorage` ou `sessionStorage`.
5. **Privacidade LGPD (Zero PII):** Nenhum campo de cliente individual (`Cod Cliente`, nome, documento) existe nos modelos TypeScript, templates, query params ou logs do frontend.
6. **Formatação Numérica Consistente:** Todos os valores monetários (`brl`), percentuais e contagens usam `.tabular-nums` (`font-variant-numeric: tabular-nums`), `--font-family-mono` e sinal menos tipográfico `−` (`U+2212`).

---

## 6. Copywriting e Checklist de Verificação do `ux_reviewer` (Etapa 4)

### 6.1. Guia de Microcopy

- **Título (`<h2>`):** `Relatório de Canibalização e Equilíbrio de Preço`
- **Subtítulo:** `Identifique produtos com queda de faturamento atribuída à migração de clientes para outros itens do portfólio e simule o preço de equilíbrio para proteger a margem.`
- **Seletor de Período:** `30 dias` · `60 dias` · `90 dias` *(padrão)*
- **KPIs:** `Produtos canibalizados` · `Faturamento perdido (canibalização)` · `Queda média atribuída` · `Principal categoria afetada`
- **Ação da Linha:** `Equilibrar preço`
- **Ações Recomendadas no Drawer:** `Reajustar canibalizador` · `Ajustar preço da vítima` · `Migração por valor`

### 6.2. Checklist DoD Visual (Etapa 4 — `ux_reviewer`)

- [ ] **Tokens 100% Papel & Tinta:** Todos os estilos consomem exclusivamente variáveis de `frontend/src/styles.scss` e mixins de `_analytics-ui.scss` (zero hexadecimais hardcoded, zero gradientes, zero cabeçalhos em itálico).
- [ ] **Contraste AA/AAA & Daltonismo:** Badges `.tag-*` com texto `#FFFFFF` sobre `--feedback-*-bg`; banners/blocos de equilíbrio em `--bg-surface` + borda esquerda `3px` + texto escuro; nenhum `--text-muted` sobre `--bg-subtle`, `--bg-table-header` ou `--brand-primary-subtle`; toda severidade e ação combina cor + símbolo + texto.
- [ ] **Substituição Limpa da v1:** Sem `ModeSwitch`, sem busca isolada de SKU DiD e sem aba "Mapa de Substitutos".
- [ ] **Filtros & Ordenação:** Busca por nome/SKU + combobox pesquisável acessível (`Fornecedor` e `Categoria`) com navegação por teclado e botão `×` + ordenação sincronizada pelos 6 critérios obrigatórios.
- [ ] **Drawer de Equilíbrio de Preço:** `role="dialog" aria-modal="true"`, focus trap, `inert` no fundo, fechamento por `Esc`/backdrop e restauração de foco ao disparador; exibe resumo da vítima + lista de canibalizadores + comparativo preço/margem + bloco de equilíbrio com ação recomendada e preços sugeridos.
- [ ] **Responsividade Completa:** Zero scroll horizontal em `320px`, `375px`, `414px`, `768px` e `1280px`; cards empilhados substituem a tabela abaixo de `640px`; alvos tocáveis $\ge 40\text{px}$ ($\ge 44\text{px}$ em ações móveis e botão fechar).
- [ ] **8 Estados Interativos:** `default`, `hover`, `focus-visible`, `active`, `disabled`, `loading` (skeleton solid-pulse + aviso 4s), `empty` (período vazio e filtros vazios) e `error` (`ErrorBanner` com retry) validados.
- [ ] **LGPD:** Zero `Cod Cliente` ou PII na UI, URL ou console.
