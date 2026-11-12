# Design Plan — Tendência de Vendas por Item (página `/tendencia-vendas`)

<!-- Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 · macrostructure: workbench (controles → tabela "ledger" densa) com disclosure por linha -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | US-TND — tabela de todos os produtos ativos (ou fornecedores) com a variação % de vendas em 1, 3, 6 e 12 meses |
| **Branch** | `feature/sales-trend`, a partir de `main` (feature **independente** do cross-sell; revisão pós-checkpoint, 2026-11-09) |
| **Regras** | `.agents/docs/business_rules/analytics-sales-trend.md` (P-072 a P-093, CA-01 a CA-40, A-1 a A-26) · `GLOSSARY.md` §4. A feature só trata **produtos ativos** (sem inativos, ver D-21) |
| **Tarefa** | `.agents/docs/tasks/analytics-sales-trend.md` (Tarefa 2, Frontend) |
| **Contrato** | `.agents/docs/api_contracts/analytics-sales-trend.md` (Arquiteto, refazendo: rotas sob `/api/v1/sales-trend`, erros `TND-001` a `TND-005`). Os campos de que a tela precisa e as dúvidas estão em §11. |
| **Base de reaproveitamento** | **Somente o que existe em `main`** (verificado com `git show main:<arquivo>`): `frontend/src/styles.scss` (tokens e classes globais `.tag-*`, `.skeleton-line`, `.skeleton-box`), `core/layout/navbar/`, padrões visuais de `features/inventory/pages/inventory-page/` e `features/pricing/`. **Nada** de `features/analytics/**` nem de `_analytics-ui.scss` (não estão em `main`). Código novo em `frontend/src/app/features/sales-trend/` |
| **Autor / Etapa** | Designer — Etapa 2 · 2026-11-09 (revisão pós-checkpoint) · decisões D-n a validar |

---

## 1. Identificação e objetivos de UX

**Story (US-TND):** como comprador/gestor da Fitoherb, quero ver todos os produtos ativos com a variação percentual de vendas em 1, 3, 6 e 12 meses, ordenável, para identificar rapidamente o que mais cresce e o que mais cai. Com um alternador, quero ver o mesmo por fornecedor e abrir um fornecedor para saber quais produtos puxaram a alta ou a queda.

**Perguntas que a tela responde**
1. "O que mais subiu e o que mais caiu em 3 meses?" (abertura padrão: coluna de 3 meses, maiores altas primeiro).
2. "Esse número é confiável?" (Base parcial, Base baixa, Sem base, devoluções: sempre explicados em texto).
3. "Qual fornecedor está arrastando o resultado, e por qual produto?" (visão por fornecedor + contribuição em p.p.).

**Objetivos de UX**
1. Ler "subiu/caiu" de relance, **sem depender de cor**: triângulo, sinal (+/−) e texto, com contraste AA nos dois sentidos.
2. Deixar óbvio **qual mês-base está ativo** e **o que cada coluna compara** ("ago–out/26 vs mai–jul/26"), sem o usuário fazer conta.
3. Tabela densa e honesta: células sem percentual (`Novo`, `—`) explicadas e nunca confundidas com 0%.
4. Nenhum controle exige digitar antes da primeira resposta: a tela abre já com dados (mês-base padrão, 3 meses, faturamento).
5. Mobile de 375px usável com a mesma informação (cartões, §8), sem rolagem horizontal da página.
6. Página própria, com item próprio na navbar e cabeçalho próprio (título e subtítulo com o período comparado), no mesmo vocabulário visual de "Preços e Descontos" e "Estoque e Compras".

**Arquétipo (Dashboard Designer):** **Analítico sob demanda**, Nível 3 (tabela com filtros, ordenação, paginação e drill-down). **Sem KPI herói e sem gráfico** nesta fase: a API não devolve totais nem série mensal, e inventar números é proibido (Hallmark, Copy Honesto). Há um ponto de extensão para uma linha "Todos os produtos" (Q-4). Blocos por tela: controles, avisos, legenda, tabela e paginação (5, abaixo do limite de 6 a 8). F-Pattern: controles no topo-esquerda, leitura desce pela coluna ordenada.

**Discovery:** sem brainstorming interativo (instrução do Orquestrador). Decisões marcadas **D-n (a validar no checkpoint)** e consolidadas em §12; dúvidas de contrato em §11.

---

## 2. Checklist Anti-IA (auditado)

- [x] **Sem "AI Purple"** nem gradiente: superfícies sólidas do `styles.scss` (Papel & Tinta). Verde = alta, vermelho-tijolo = queda, azul-aço = "Novo", âmbar escuro = base baixa. Nenhuma cor nova.
- [x] **Sem 3 colunas mecânicas / sem cards de feature:** a tela é uma tabela de dados com colunas de larguras desiguais (produto largo, 4 colunas numéricas à direita). Os controles seguem grade assimétrica (`auto auto 1fr`), não 3 cartões iguais. Nenhum ícone decorativo de foguete/engrenagem.
- [x] **Sem "dashboard preguiçoso":** sem menu lateral, sem barra de KPI genérica, sem gráfico de barras decorativo. O "visual" é a própria tabela ordenada.
- [x] **Font pairing:** títulos e rótulos de coluna em `--font-family-headline` (Signika), interface em `--font-family-body` (Source Sans 3), números em `--font-family-mono` (Overpass Mono, tabular).
- [x] **White space ativo:** `--space-5` entre painéis, `--space-4`/`--space-6` internos; densidade só na tabela, com separadores hairline.
- [x] **Copy humano:** sem "inteligente", "IA", "insights acionáveis", "seamless", "potencialize". Sem ✨. Títulos dizem o que a lista mostra ("Maiores quedas em 3 meses").
- [x] **Sem spinner isolado:** skeleton com a geometria da tabela e dos cartões; recargas mantêm a tabela (esmaecida). Spinner só dentro do botão de expandir, junto de skeleton de linhas.
- [x] **Sem tela vazia:** 5 estados vazios/informativos desenhados, cada um com ação.
- [x] **Sem título em itálico, sem fake chrome, sem métrica inventada:** todo número vem da API; textos explicativos usam `meta`.
- [x] **Status nunca só por cor:** triângulo + sinal + palavra (sr-only) em toda variação; selos sempre em texto.
- [x] **Sem animação decorativa:** `animejs-animation` e `image-generator` não são necessários (ícones são SVG inline, sem raster). Movimento limitado a transições de cor e à rotação de 90° do chevron.

---

## 3. Tokens consumidos

> **D-1 (como `inventory` e `pricing`):** seguir os tokens reais de `frontend/src/styles.scss` (Papel & Tinta: verde erva-mate, Signika, Source Sans 3, Overpass Mono), não os de `DESIGN_SYSTEM.md` (teal, Plus Jakarta, Inter). Atualizar o `DESIGN_SYSTEM.md` segue como tarefa à parte. `styles.scss` em `main` é idêntico ao da working tree (conferido).

**Regras novas consomem só `var(--token)`, sem fallback hex** (as telas `inventory`/`pricing` usam `var(--x, #hex)`; não copiar). Dimensões sem token (ícone de 10px, largura de coluna) viram **constantes SCSS nomeadas** no topo do arquivo.

| Grupo | Tokens |
| :--- | :--- |
| Tipografia | `--font-family-headline`, `--font-family-body`, `--font-family-mono` |
| Superfície | `--bg-canvas`, `--bg-surface` (painéis, células), `--bg-subtle` (campo, coluna ordenada nos cartões), `--bg-muted` (skeleton, pressionado), `--bg-table-header` (cabeçalho da tabela), `--bg-table-row-hover` (hover de linha), `--bg-table-row-zebra` (linhas filhas e divisor de grupo) |
| Texto | `--text-primary`, `--text-secondary`, `--text-muted` (só sobre `--bg-surface`/`--bg-table-row-hover`), `--text-on-brand` |
| Marca | `--brand-primary`, `--brand-primary-hover`, `--brand-primary-active`, `--brand-primary-subtle` (linha expandida, chip/segmento "pré-selecionado") |
| Direção e selos | alta: `--feedback-positive-bg` · queda: `--feedback-critical-bg` · estável/sem percentual: `--text-secondary` · Novo: `--feedback-info-bg` · Base baixa e devoluções: `--feedback-warning-bg`. Usados **como cor de texto/ícone/borda** sobre superfície clara (os tokens `--feedback-*-bg` são escuros e servem como cor de texto; as telas de `main` já os usam como fundo de tag). Nas bordas dos selos, `--feedback-*-border` |
| Borda / foco | `--border-subtle`, `--border-default`, `--border-strong`, `--border-focus` |
| Espaço | `--space-1` a `--space-8` |
| Raio | `--radius-xs` (campos, botões, chips, selos), `--radius-sm` (painéis) |
| Sombra | `--shadow-xs` (painéis); `--shadow-md` (lista do `<select>` customizado, se houver) |
| Movimento | `--transition-fast` |

**Um token novo (D-5):** `--navbar-height: 64px` (`58px` em `max-width: 768px`, os mesmos valores já usados em `core/layout/navbar/navbar.component.scss` de `main`, que é `position: sticky; top: 0`), declarado em `:root` (ou no `.platform-navbar`) e consumido por `top: var(--navbar-height)` no cabeçalho fixo da tabela. Se o token for recusado, o cabeçalho fica sem `position: sticky` (degrada sem quebrar).

**Estilos próprios da feature** (`features/sales-trend/styles/_trend-ui.scss`, novo, **autossuficiente**, sem `@use` de nada de `features/analytics`): constantes `$bp-mobile: 639.98px`, `$bp-cards: 767.98px`, `$bp-wide: 1279.98px`, `$bp-tiny: 359.98px`, `$touch-target: 40px`, `$arrow-size: 10px`, `$chevron-hit: 40px`, `$dimmed-opacity: 0.55`, `$skeleton-rows: 10`; mixins `hover` (`@media (hover: hover)`), `reduced-motion`, `panel`, `button-base/primary/secondary`, `spinner`, `sr-only`, `caption`. O padrão visual vem de `inventory-page.component.scss` (botões `.btn`, `.table-wrapper`, `th` de 0.72rem em caixa alta, `.col-*` em mono tabular), reescrito só com tokens e sem fallback hex.

### Contraste verificado (WCAG 2.1; razões calculadas com a luminância relativa dos tokens)

| Par | Razão | Resultado |
| :--- | :--- | :--- |
| `--feedback-positive-bg` (alta) sobre `--bg-surface` | 8,3:1 | AA |
| `--feedback-positive-bg` sobre `--bg-table-row-hover` / `--bg-table-header` / `--brand-primary-subtle` | 7,6 / 7,0 / 7,0 | AA |
| `--feedback-critical-bg` (queda) sobre `--bg-surface` | 9,0:1 | AA |
| `--feedback-critical-bg` sobre `--bg-table-row-hover` / `--bg-table-header` / `--brand-primary-subtle` | 8,2 / 7,6 / 7,6 | AA |
| `--feedback-info-bg` (Novo) sobre `--bg-surface` | 9,0:1 | AA |
| `--feedback-warning-bg` (Base baixa, devoluções) sobre `--bg-surface` | 7,9:1 | AA |
| `--text-secondary` sobre `--bg-surface` / `--bg-table-header` | 9,0 / 7,6 | AA |
| `--text-muted` sobre `--bg-surface` / `--bg-table-row-hover` | 5,2 / 4,8 | AA |
| `--text-muted` sobre `--bg-table-header` / `--brand-primary-subtle` / `--bg-subtle` | 4,4 / 4,4 / 4,2 | **Reprova** → nesses fundos usar `--text-secondary` (cabeçalho da tabela, linha expandida, campos) |
| `--text-on-brand` sobre `--brand-primary` (segmento/chip selecionado) | 10,9:1 | AA |

> **Limite honesto:** `--feedback-positive-bg` (verde) e `--feedback-critical-bg` (vermelho-tijolo) têm luminância parecida (0,077 e 0,067). Para daltônicos a cor **não distingue** alta de queda; quem distingue é o triângulo (▲/▼), o sinal (+/−) e o texto. Por isso a regra D-6 proíbe cor isolada.

---

## 4. Arquitetura de componentes (burros × dados do store/serviço)

**Regra** (`architecture-business-logic-isolation-rules.md`): um único componente inteligente (a página). Todos os outros só recebem `input()` e emitem `output()`. Nenhum componente calcula variação, ordena, filtra, soma contribuição ou decide estado: tudo vem da API ou de **funções puras** em `utils/trend-*.ts`. Formatação por pipes e utilitários, nunca inline no template.

### 4.1 Reaproveitar (somente o que existe em `main`) e o que vira código próprio

Conferido com `git show main:<arquivo>`. **Existe em `main` e pode ser reaproveitado:**

| Item de `main` | Uso aqui |
| :--- | :--- |
| `frontend/src/styles.scss` | todos os tokens (§3); classes globais `.tag`, `.tag-info`, `.tag-warning`, `.tag-critical`, `.tag-neutral`, `.tag-dot`; `@keyframes pulseSolid` e `.skeleton-line`/`.skeleton-box` (pulso sólido, sem gradiente) para o skeleton |
| `core/layout/navbar/` | recebe o item "Tendência de Vendas" (§5.1); `position: sticky; top: 0` define a altura usada em `--navbar-height` |
| `app.routes.ts` | recebe a rota lazy `/tendencia-vendas` |
| Padrões visuais de `features/inventory/pages/inventory-page/` | **só como referência de estilo** (hero, `.filters-panel`, `.search-box`, `.inventory-table`, `.col-*` em mono tabular, `.cache-badge`); nada é importado: `.btn`, `.alert`, `.pill-btn`, `.table-wrapper` etc. são **locais** daquele componente, não globais |

**Não existe em `main` e vira componente próprio em `features/sales-trend/`** (nenhum import de `features/analytics/**`, D-14):

| Necessidade | Componente / arquivo próprio |
| :--- | :--- |
| Paginação (principal e do detalhe do fornecedor) | `TrendPagerComponent` (`aria-label` por input; oculto com 1 página; "{a}–{b} de {total}", Anterior, "Página p de t", Próxima) |
| Banner de falha técnica | `TrendErrorBannerComponent` (`role="alert"`, `message` por input, ação "Tentar de novo") |
| Estados vazios e informativos | `TrendEmptyStateComponent` (ícone em caixa 56×56, título, texto, ação; view-model em `utils/trend-view.ts`) |
| Skeleton | `TrendTableSkeletonComponent` (usa as classes globais `.skeleton-*` de `styles.scss`) |
| Alternadores `Ver`, `Medir por`, `Mostrar` | `SegmentedControlComponent` (`role=radiogroup`; roving tabindex, ←/→, Home/End) |
| Formatação pt-BR | `utils/pt-br-format.ts` próprio (`roundHalfUp`, `formatDecimal`, `formatCurrency`, `formatIsoDate`) + `utils/trend-format.ts` e `pipes/trend-format.pipes.ts` (`PtDecimalPipe`, `BrlPipe`, `PtDatePipe`, `SignedPercentPipe`, `SignedDecimalPipe`) |
| Mapeamento de erro | `utils/trend-error.ts` (códigos `TND-001` a `TND-005`) |
| Mixins e constantes de estilo | `styles/_trend-ui.scss` (§3) |

### 4.2 Criar

| Componente / arquivo | Tipo | Inputs → Outputs |
| :--- | :--- | :--- |
| `SalesTrendPageComponent` (rota `/tendencia-vendas`, lazy, com o cabeçalho próprio da página) | **Inteligente** | injeta `SalesTrendStore`; só liga store → componentes e foco/região viva |
| `TrendToolbarComponent` | Burro (composição) | `query`, `bounds`, `metricUnit`, `fieldErrors`, `hasActiveFilters` → `(queryChange)` parcial tipado, `(clearFilters)` |
| `TrendPagerComponent` | Burro | `page`, `totalPages`, `totalItems`, `offset`, `itemCount`, `ariaLabel`, `disabled` → `(pageChange)` |
| `TrendErrorBannerComponent` | Burro | `message`, `retryLabel?` → `(retry)` |
| `TrendEmptyStateComponent` | Burro | `view: TrendEmptyView` (`icon`, `title`, `text`, `actionLabel`, `action`, `tone`) → `(action)` |
| `SegmentedControlComponent<T>` | Burro, `role=radiogroup` | `label`, `options: {value,label}[]`, `value`, `appearance: 'segmented' \| 'chips'` → `(valueChange)` |
| `BaseMonthPickerComponent` | Burro | `months: {value,label}[]`, `value`, `canPrev`, `canNext`, `helper`, `error`, `loading` → `(monthChange)` |
| `TrendSearchFieldComponent` | Burro | `label`, `placeholder`, `value`, `error` → `(valueChange)` (a store faz o debounce de 300 ms) |
| `TrendTableComponent` (≥768px) | Burro | `columns: TrendColumnView[]`, `rows: TrendRowView[]`, `sort`, `groupBy`, `expandedKeys`, `details: Record<key, DetailView>`, `totalRow?`, `loading` → `(sortChange)`, `(toggleRow)`, `(detailPageChange)`, `(detailSortChange)`, `(detailRetry)` |
| `TrendColumnHeaderComponent` (`th[appTrendColumnHeader]`) | Burro | `column`, `sorted` → `(sort)` |
| `TrendSupplierGroupComponent` (`tbody[appTrendSupplierGroup]`) | Burro | linha do fornecedor + região do detalhe (cabeçalho, filhos, skeleton, erro, pager) |
| `TrendRowComponent` | Burro | `row`, `level: 'parent' \| 'child'` → `(toggle)` |
| `TrendCellComponent` | Burro, **compartilhado por tabela e cartões** | `cell: TrendCellView`, `variant: 'table' \| 'card'` (sem eventos) |
| `TrendRowValuesComponent` | Burro | `values: TrendValuesView` (tabela "Valores por janela", §5.6) |
| `TrendCardListComponent` / `TrendCardComponent` (<768px) | Burro | mesmas entradas e saídas da tabela |
| `MobileSortControlComponent` | Burro | `sort`, `columns` → `(sortChange)` (select de coluna + par "Altas primeiro / Quedas primeiro") |
| `PeriodLegendComponent` | Burro | `columns` → nada (lista "Períodos comparados", usada nos cartões e na legenda) |
| `ReadingGuideComponent` | Burro | `<details>` "Como ler a tabela" (§5.8) |
| `InlineNoticeComponent` | Burro | `tone: 'info' \| 'warning'`, `title?`, `text`, `actionLabel?`, `dismissible` → `(action)`, `(dismiss)` |
| `TrendTableSkeletonComponent` | Burro | `variant: 'table' \| 'cards'`, `rows` (padrão 10), `groupBy` |

### 4.3 Divisão store / serviço / utilitários

| Camada | Responsabilidade (e só ela) |
| :--- | :--- |
| `SalesTrendService` | HTTP: `getTrend(params)` e `getSupplierProducts(supplierKey, params)`; desembrulha `data`/`meta`; converte `HttpErrorResponse` em `{code, fields}` (`TND-001`, `TND-002`, `TND-003`, `TND-004`, `TND-005`, `NETWORK`, `SERVER`). Nunca expõe `detail` cru |
| `SalesTrendStore` (escopo da página, `providers` do componente) | estado da consulta em signals (`groupBy`, `metric`, `baseMonth \| null`, `sortWindow`, `sortDir`, `view`, `q`, `minVolume`, `page`); máquina `idle → loading → success \| empty \| error`; cancela a requisição anterior (`switchMap`); aplica as regras de troca de agrupamento de P-086.7; `Map<supplierKey, DetailState>` com um estado por fornecedor expandido; recarga da lista quando `meta.dataReferencia` do detalhe diverge (P-092.7); guarda o último `meta` para montar o seletor de mês e as cópias. **Nenhuma regra de negócio**: ordem, filtros, percentuais e contribuições vêm da API |
| `utils/trend-url.ts` | estado da consulta ↔ query params (D-12) |
| `utils/trend-format.ts` | `formatSignedPercent(v)` (`+12,3%`, `−100,0%`, `0,0%`), `formatSignedDecimal(v, 1)` + `p.p.`, `formatSignedAmount(v, metric)`, `formatMonth('2026-10')` → `out/2026`, `formatPeriod(inicio, fim)` → `ago–out/26` |
| `utils/trend-view.ts` | **funções puras** que transformam resposta em view-models: `buildColumns(meta.janelas, sort)`, `buildCellView(janela, metric)` (direção, `display`, `srText`, `flags`), `buildRowView`, `buildDetailView`, `withGroupDividers(rows, sortWindow)`, `headline(...)`, `resolveTrendState(...)`, `liveMessage(...)`, textos de selos. Testáveis sem DOM |
| `services/viewport.service.ts` | signal `isCompact` por `matchMedia('(max-width: 767.98px)')` (ou `BreakpointObserver`, se `@angular/cdk` já for dependência). A página renderiza **tabela ou cartões**, nunca os dois |

**Estado:** signals locais no store da página. A lista não vai para estado global nem para `localStorage`/`sessionStorage` (state-management-rules §4: a API é dona do dado; a URL é a única persistência, §12 D-12).

---

## 5. Anatomia e hierarquia

### 5.1 e 5.2 Rota, navbar e cabeçalho da página

- **Rota própria (D-2):** `/tendencia-vendas`, carregada por `loadComponent` (lazy) em `app.routes.ts`, **antes** do curinga `**`. Não há shell, nem abas, nem `mode-switch` de abas.
- **Item na navbar** (`core/layout/navbar/navbar.component.html`, de `main`), terceiro item da lista, mesmo padrão de `nav-link` com `routerLinkActive="active"` e `(click)="closeMobileMenu()"`:

```
[ícone 16px: linha de tendência ascendente]  Tendência de Vendas
```

  - `title="Acessar a Tendência de Vendas por produto e por fornecedor"`. Rótulo em Title Case, como "Preços e Descontos" e "Estoque e Compras".
  - Ícone SVG inline 16×16, `stroke="currentColor"`, `stroke-width="2"`, `stroke-linecap="round"`, `stroke-linejoin="round"`, `aria-hidden="true"`: `<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>` e `<polyline points="17 6 23 6 23 12"/>`.
  - Cabe no menu hambúrguer mobile existente (3 itens). A mudança em `navbar.component.html` é de uma `<li>`; não altera o `.scss`, exceto o token `--navbar-height` (D-5).
- **Cabeçalho da página (D-22):** anatomia de `.feature-hero` do `inventory` (fundo `--bg-surface`, borda `--border-default`, `border-top: 3px solid var(--brand-primary)`, `--radius-sm`, `--shadow-xs`), container `max-width: 1600px`, padding `--space-5` `--space-6`, gap `--space-5` (mesmos valores de `.inventory-container`, escritos com tokens).

```
Tendência de Vendas                                                   [relógio] Vendas até 08/11/2026
O que subiu e o que caiu: cada coluna compara os meses até out/2026 com os meses imediatamente anteriores, de mesmo tamanho.
Mostra apenas produtos ativos do catálogo.
```

  - `h1` `--font-family-headline` 1.85rem peso 700 (como `.hero-title` do inventory); subtítulo 0.88rem `--text-secondary`, com o mês-base vindo de `meta.mesBase` (antes da resposta chegar: `Compara períodos de 1, 3, 6 e 12 meses com os períodos imediatamente anteriores.`).
  - Nota de escopo, 0.78rem `--text-secondary`: `Mostra apenas produtos ativos do catálogo.` (D-21).
  - À direita (quebra para baixo no mobile): selo no padrão `.cache-badge` do inventory (ícone de relógio `aria-hidden`), texto `Vendas até {ultimoDiaCoberto dd/MM/yyyy}`, `--text-secondary` sobre `--bg-subtle`.
  - O título do painel da tabela (§5.4) é `h2` (o `h1` é o da página).

### 5.3 Controles (painel `--bg-surface`, `--radius-sm`, `--shadow-xs`, padding `--space-5` `--space-6`)

Três faixas, separadas por hairline `--border-subtle`, em grade assimétrica (não 3 colunas iguais):

| Faixa | Conteúdo (ordem do DOM = ordem visual) |
| :--- | :--- |
| 1. O que medir | **Ver** (`Por produto` · `Por fornecedor`) · **Medir por** (`Faturamento (R$)` · `Quantidade (un)`) · **Mês-base** (`‹` select `›` + linha de ajuda) |
| 2. Quais itens | **Buscar** (campo, flex 1) · **Volume mínimo** (número + unidade) |
| 3. Atalhos | **Mostrar** (`Todos` · `Maiores altas` · `Maiores quedas` · `Novos`) · ação `Limpar filtros` à direita (só aparece com filtro ativo) |

Detalhes por controle:

- **Ver / Medir por / Mostrar:** `SegmentedControlComponent` (`role=radiogroup` com `radio`s, `aria-checked`, roving tabindex, ←/→ movem e selecionam, Home/End). Altura mínima 40px. Visual do segmento: ativo `--brand-primary` + `--text-on-brand`; inativo `--bg-surface` + `--text-secondary`; grupo com borda `--border-default` e `--radius-xs` (componente próprio, D-16). "Mostrar" usa `appearance: 'chips'`: botões soltos separados por `--space-2`, com `--radius-xs` como o resto do app (nada de pílulas `--radius-full`).
  - Rótulos curtos nos segmentos para não quebrar linha (D-15): `Faturamento (R$)` / `Quantidade (un)`. A definição completa ("Faturamento líquido, com devoluções descontadas") aparece na linha de contexto da tabela (§5.4).
  - Rótulo do grupo "Ver" (e `aria-label="Agrupar a tabela"`): no Glossário "Visão" são os atalhos; para não confundir, o grupo de agrupamento se chama **"Ver"** e os atalhos **"Mostrar"**.
- **Mês-base:** `<label>` visível + `<select>` nativo (acessível, bom no mobile) entre dois botões só-ícone `‹`/`›` (`aria-label="Mês-base anterior, set/2026"` e `"Próximo mês-base, nov/2026"`; desabilitados nos limites `mesBaseMinimo`/`mesBaseMaximo`). Opções em ordem decrescente: `nov/2026 · mês corrente, parcial até 08/11` · `out/2026 · último mês completo` (pré-selecionada) · `set/2026` … `jan/2026`… até `mesBaseMinimo`. Abaixo, linha de ajuda 0.78rem `--text-secondary` (dinâmica, de `meta.janelas[0]`): `Ex.: a coluna de 1 mês compara out/2026 vs set/2026.`
  - A opção ativa nunca é só "o valor do select": o cabeçalho da página tem o subtítulo com o mês-base e cada coluna mostra o período (§5.4). Três pontos de leitura do mês-base ativo.
- **Buscar:** `TrendSearchFieldComponent`, geometria de `.field-box` (fundo `--bg-subtle`, ícone de lupa `aria-hidden`, `:focus-within` com anel `--border-focus` 2px; **sem** `outline: none` solto). Rótulo e placeholder mudam com o agrupamento: produto `Código ou descrição do produto`; fornecedor `Nome do fornecedor` (P-091.2: a busca olha só o nome do fornecedor). Botão "×" `aria-label="Limpar busca"`. Debounce de 300 ms no store; Enter aplica na hora. Validação local igual à de P-081.1 (só dígitos: 1 a 60; demais: 2 a 60) para evitar `TND-001`; mensagem inline (§6.4).
- **Volume mínimo:** `<input type="number" inputmode="decimal" min="0">` + sufixo fixo `un` ou `R$` (muda com a métrica; **zera ao trocar a métrica**, P-079.5, e o `aria-live` avisa: "Volume mínimo zerado: a unidade mudou"). `placeholder="0"`. Hint 0.78rem: `Esconde variações cuja base de comparação é menor que isso. Novo, sem base e sem movimento continuam na lista.`
- **Sem controle de ativos/inativos (D-21):** a feature só trata produtos ativos; não há switch, selo nem filtro para isso. O escopo é dito em texto no cabeçalho (`Mostra apenas produtos ativos do catálogo.`), na legenda e nos estados vazios.
- **Limpar filtros:** botão-texto `--brand-primary` 0.82rem 600, visível só se `q`, `minVolume` ou `view` forem diferentes do padrão. Não mexe em mês-base, métrica, agrupamento nem ordenação (são "visualização", não filtro).
- **Troca de agrupamento (P-086.7, A-26):** mantém mês-base, métrica, coluna e sentido de ordenação; zera `view`, `minVolume` e `q`. A tela avisa por `InlineNotice` info + região viva: `Trocamos para a visão por fornecedor. A busca, o atalho e o volume mínimo foram limpos.` (só se algum estava ativo).

### 5.4 Tabela (≥768px)

**Painel da tabela** (`--bg-surface`, `--radius-sm`, `--shadow-xs`; **sem `overflow: hidden`**, para o cabeçalho fixo e o anel de foco não serem cortados).

**Cabeçalho do painel (insight, não nome da métrica)** — `h2` `--font-family-headline` 1.1rem + subtítulo 0.82rem `--text-secondary`:

| Estado | Título (`h2`) |
| :--- | :--- |
| `all`, `desc` | `Maiores altas em {X}` |
| `all`, `asc` | `Maiores quedas em {X}` |
| `rising` / `falling` / `new` | `Produtos que subiram em {X}` / `Produtos que caíram em {X}` / `Produtos novos ou retomados em {X}` |
| fornecedor | mesmos textos com "Fornecedores" no lugar de "Produtos"; `Maiores altas`/`quedas` não muda |

`{X}` = `1 mês`, `3 meses`, `6 meses`, `12 meses`. Subtítulo: `{n} produtos · faturamento líquido, com devoluções descontadas` (ou `quantidade líquida`; `{n}` = `meta.totalItems`; singular: `1 produto`/`1 fornecedor`).

**Colunas** (`<table>`, `table-layout: fixed`, `width: 100%`; **sem rolagem horizontal**: a tabela só existe a partir de 768px, onde as colunas cabem):

| # | Coluna | Largura | Conteúdo |
| :-: | :--- | :--- | :--- |
| 1 | (controle) | `$chevron-hit` | botão de expandir (§5.6) |
| 2 | Produto / Fornecedor | `minmax(0, 1fr)`, mínimo 220px | nome + linha de apoio (código e fornecedor) |
| 3–6 | `1 mês`, `3 meses`, `6 meses`, `12 meses` | 4 × `minmax(104px, 168px)`; no desktop ≥1280 cada uma cresce até 168px | célula de variação |

**Cabeçalho de coluna de %** (`<th scope="col" aria-sort>` contendo um `<button>`; fundo `--bg-table-header`; alinhado à direita como os números):

```
 3 MESES  ↓              ← headline 0.72rem caixa alta, tracking .04em; seta = ordenação ativa
 ago–out/26              ← 0.75rem --text-secondary, mono tabular
 vs mai–jul/26
 [Base parcial]          ← selo de janela (só se a janela for parcial); ou [Sem base]
```

- O período vem de `meta.janelas[]` (`formatPeriod`). Sempre em 2 linhas (`período atual` / `vs período anterior`), para caber em 104px.
- **Coluna ordenada:** `aria-sort`, seta ↓/↑ visível, sublinhado de 3px `--brand-primary` colado à base do cabeçalho (mesmo vocabulário do link ativo da navbar) e valores em peso 700 (demais colunas 600).
- **Coluna não ordenada:** ícone de duas setas discreto (`--text-secondary`), `aria-sort="none"`.
- **Clique/Enter/Espaço:** coluna nova ordena `desc` (maiores altas primeiro); na ativa, alterna `desc`/`asc`. A região viva anuncia `Ordenado por 12 meses, maiores quedas primeiro.`
- **Selo de janela (D-7):** `Base parcial` e `Sem base` são propriedades da **janela** (P-089.5: mesma cobertura para todos os SKUs), então ficam **uma vez no cabeçalho**, não em cada linha. Isso evita a tabela inteira repetir "Base parcial" na coluna de 12 meses (cenário normal com a base começando em jan/2025). O texto do selo é o rótulo; o detalhe (`janela anterior com 298 de 365 dias`) está em `title` **e** na legenda "Como ler a tabela" (nunca só em tooltip).
- **Cabeçalho fixo:** `position: sticky; top: var(--navbar-height)` (D-5).

**Linha de produto** (`<tr>`; primeira célula `<th scope="row">`):

```
 [›]  ÓLEO DE COCO 500 ML                 ▲ +200,0%    ▲ +180,5%    ▲ +95,2%    ▲ +40,1%
      Cód. 1007 · LABORATÓRIO BETA        Base baixa
```

- Linha 1: descrição `--font-family-body` 0.88rem 600 `--text-primary`, máximo 2 linhas (`line-clamp`), `overflow-wrap: anywhere`.
- Linha 2: `Cód. {codigo}` em `--font-family-mono` 0.75rem `--text-secondary` + ` · {fornecedor}` (omitido nas linhas filhas, o fornecedor já é o pai).
- Altura mínima 56px; divisor `1px solid var(--border-subtle)`; hover de linha `--bg-table-row-hover` em `@media (hover: hover)`; a linha em si não é clicável (só o botão).

**Linha de fornecedor** (visão por fornecedor): linha 1 nome em `--font-family-headline` 0.9rem 600; linha 2 `{qtdProdutos} produtos` (singular `1 produto`) em 0.75rem. `Sem fornecedor` é uma linha comum, **sem** estilo de erro, sem itálico, sem posição privilegiada.

### 5.5 Célula de variação (hierarquia visual de "subiu/caiu")

`TrendCellComponent` com `cell: TrendCellView`. Alinhada à direita; número em `--font-family-mono`, `font-variant-numeric: tabular-nums`, 0.88rem; **slot fixo de 10px à esquerda** para o triângulo, de modo que as casas decimais e vírgulas formem colunas alinhadas e o olho desça pela coluna lendo só triângulos.

| `kind` | Visual | Texto visível | Texto para leitor de tela (`sr-only`; o visível é `aria-hidden`) | Cor |
| :--- | :--- | :--- | :--- | :--- |
| `up` | triângulo ▲ SVG 10px (`fill: currentColor`) + número | `+12,3%` | `Alta de 12,3 por cento` | `--feedback-positive-bg` |
| `down` | triângulo ▼ + número | `−12,3%` (menos tipográfico U+2212) | `Queda de 12,3 por cento` | `--feedback-critical-bg` |
| `flat` (arredonda para 0,0) | barra ▬ SVG 10×2px + número, **sem sinal** | `0,0%` | `Estável, 0,0 por cento` | `--text-secondary` |
| `new` (`NOVO`) | losango ◆ SVG 10px + rótulo; abaixo, o vendido na janela (`R$ 360,00` ou `40 un`), 0.75rem | `Novo` | `Novo: sem venda líquida no período anterior. Vendeu R$ 360,00 no período atual` | `--feedback-info-bg` |
| `no-base` (`SEM_BASE`) | travessão | `—` | `Sem base: o período anterior tem menos da metade dos dias na base` | `--text-secondary` |
| `no-movement` (`SEM_MOVIMENTO`) | travessão | `—` | `Sem vendas líquidas nos dois períodos` | `--text-secondary` |

- O **sinal** (`+`/`−`) é obrigatório em qualquer valor diferente de 0,0; sempre ao lado do triângulo. Pior caso de largura: `▲ +1.250,5%` ≈ 80px em 0.88rem mono, cabe nos 104px mínimos.
- `no-base` e `no-movement` têm o mesmo `—` (P-078); a diferença está no texto de leitor de tela, no `title` e na legenda. Para `no-base` o cabeçalho da coluna já mostra o selo `Sem base`.
- **Selos de célula (microselos de contorno, não as `.tag` escuras globais):** 0.72rem peso 600, borda `1px solid var(--feedback-warning-border)`, fundo `--bg-surface`, texto `--feedback-warning-bg`, `--radius-xs`, ícone de 10px (`!`) à esquerda. Aparecem **abaixo** do número e só quando necessários:

| Selo | Quando | Texto visível | Dica (`title`) e legenda |
| :--- | :--- | :--- | :--- |
| `Base baixa` | `baseBaixa = true` | `Base baixa` | `Poucas vendas no período anterior (menos de {10 un \| R$ 500,00}). O percentual pode exagerar.` (limites de `meta.parametros`, Q-9) |
| `Devoluções superam vendas` | `devolucaoLiquida = true` | `Devoluções superam vendas` (quebra em 2 linhas na célula; é raro) | `As devoluções foram maiores que as vendas em um dos períodos; o valor entrou como zero na conta.` |

- **Mais de um selo** na mesma célula empilham (máximo 2 linhas); a linha da tabela cresce, sem truncar.
- **Intensidade, sem poluir:** não há fundo colorido nas células (os tokens de feedback são sólidos escuros) nem barras em cada linha. A leitura de relance vem de 3 sinais empilhados: (1) triângulo e sinal alinhados em coluna, (2) coluna ordenada em peso 700 com sublinhado no cabeçalho, (3) a própria ordenação (maiores altas no topo, quedas no fim ao inverter).
- **Divisor de grupo (D-11):** por P-080.2, `NOVO`, `SEM_BASE` e `SEM_MOVIMENTO` vêm **depois** dos com percentual, nos dois sentidos. Para o usuário não achar que "Novo" é a maior alta, `withGroupDividers` insere, na primeira linha sem percentual da coluna ordenada, uma linha `<tr class="group-divider"><th scope="rowgroup" colspan="6">` com `Sem percentual em 3 meses: Novo, sem base ou sem movimento` (`--bg-table-row-zebra`, 0.75rem `--text-secondary`, caixa alta). Não aparece em `view=new` nem quando a página inteira já é do grupo sem percentual e não há linha com percentual antes (a legenda cobre).

### 5.6 Linha expansível: valores por janela (todas as linhas) e produtos do fornecedor

**D-8 — padrão disclosure dentro de tabela simples, não `treegrid`.** Toda linha (produto, fornecedor e produto filho) tem, na primeira célula, um botão de 40×40 com chevron (`›` fechado, `⌄` aberto; gira 90° em `--transition-fast`, sem rotação com `prefers-reduced-motion`):

```html
<button type="button" aria-expanded="false" aria-controls="detail-{key}" aria-label="Ver valores de ÓLEO DE COCO 500 ML">
```

Motivo da escolha: `treegrid` obriga navegação por setas em grade, modo de formulário do leitor de tela e foco por célula; para ~50 linhas com um botão cada, a tabela comum com disclosure mantém a leitura linear, o Tab previsível e o `aria-expanded` bem suportado. Custo aceito: sem setas entre linhas (Tab move de linha em linha).

**Conteúdo expandido, por tipo de linha**

1. **Produto (visão por produto, e filho):** `TrendRowValuesComponent`, uma sub-tabela "Valores por janela" (a única forma de ver valores, períodos e média por dia para teclado e toque; o `title` do mouse é só atalho):

```
 Valores de ÓLEO DE COCO 500 ML (faturamento líquido)
 Janela    Período atual   Atual         Período anterior   Anterior      Variação
 1 mês     out/26          R$ 360,00     set/26             R$ 120,00     ▲ +200,0%
 12 meses  nov/25–out/26   R$ 4.300,00   nov/24–out/25      R$ 2.100,00   ▲ +108,3%
           Base parcial: média por dia R$ 11,78 (365 dias) vs R$ 7,05 (298 dias)
```

   - A linha "média por dia" só existe com Base parcial e usa `atualPorDia`/`anteriorPorDia` e `diasCobertos` da API (Q-3). Nenhuma conta na tela.
   - Nos **filhos**, a sub-tabela acrescenta a coluna `Contribuição (valor)` em un ou R$ (e `por dia` quando Base parcial), completando o que a célula mostra em p.p.

2. **Fornecedor:** região do detalhe (`<tr id="detail-{key}">` com `<td colspan="6">`) com, em ordem: (a) `TrendRowValuesComponent` da soma do fornecedor (`meta.fornecedor`); (b) barra de contexto dos produtos; (c) as linhas filhas; (d) rodapé.

**Barra de contexto dos produtos do fornecedor**

```
 Produtos de LABORATÓRIO ALFA · 2 com vendas no período               Ordenar por [Contribuição ▾]
 Contribuição mostra quanto cada produto somou (+) ou tirou (−) da variação do fornecedor, em pontos percentuais.
```

- `<select>` "Ordenar por": `Contribuição` (padrão, P-092.4) ou `Variação do produto`. Segue a coluna e o sentido da tabela (`sortWindow`/`sortDir`): quem mais puxou a alta primeiro em `desc`, a queda em `asc`.
- Título `h3` com `tabindex="-1"` (alvo de foco na troca de página dos filhos).

**Linha filha** (`<tr>` com `th scope="row"` que começa com `sr-only` "Produto do fornecedor {nome}: "): recuo `--space-6`, trilho esquerdo de 3px `--border-default` (`--brand-primary` quando o grupo está expandido), fundo `--bg-table-row-zebra`. Cada célula de janela tem **2 linhas**:

```
        ▲ +50,0%          ← variação própria do produto (igual à visão por produto, P-088.3)
   +14,3 p.p.             ← contribuição, 0.75rem mono, direção por sinal + triângulo pequeno
```

- **Contribuição (A-19, D-10):** linha 2 mostra `p.p.` (primária) com o mesmo vocabulário ▲/▼ e sinal; com a célula ≥ 168px (container query `@container (min-width: 168px)`) acrescenta o valor: `+14,3 p.p. · +10 un` ou `−71,4 p.p. · −R$ 12.345,00`. Em larguras menores o valor fica na sub-tabela expandida do próprio filho. `contribuicaoPp = null` (fornecedor `NOVO`, `SEM_BASE`) mostra `—` e o valor segue (quando existir). Quando `baseParcial`, o valor leva o sufixo `por dia`.
- **Fecho da conta:** a soma dos p.p. pode diferir da % do fornecedor com piso zero (P-090.4). O rodapé do grupo mostra, em 0.75rem `--text-secondary`, essa ressalva **apenas** se `meta.fornecedor` tiver `devolucaoLiquida` em alguma janela: `Com devoluções acima das vendas, a soma das contribuições pode passar de −100 p.p.`

**Rodapé do grupo:** `TrendPagerComponent` (limit 20, D-9; `ariaLabel="Paginação dos produtos de {fornecedor}"`) em `<tr><td colspan="6">`. Oculto com 1 página. Vários fornecedores podem ficar abertos ao mesmo tempo.

### 5.7 Wireframes

**Desktop ≥1280px** (container `max-width: 1600px`; escala de colunas aproximada)

```
┌─ navbar (main) ────────────────────────────────────────────────────────────────────────────────────────┐
│ [logo] │ [$] Preços e Descontos   [caixa] Estoque e Compras   [↗] Tendência de Vendas (ativo)           │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ cabeçalho da página (hero, borda superior 3px --brand-primary) ───────────────────────────────────────┐
│ Tendência de Vendas                                                  (relógio) Vendas até 08/11/2026    │
│ O que subiu e o que caiu: cada coluna compara os meses até out/2026 com os meses imediatamente         │
│ anteriores, de mesmo tamanho.   Mostra apenas produtos ativos do catálogo.                             │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌ controles ───────────────────────────────────────────────────────────────────────────────────────────┐
│ VER                              MEDIR POR                       MÊS-BASE                              │
│ [Por produto│Por fornecedor]     [Faturamento (R$)│Quantidade]   [‹] [out/2026 · último mês completo ▾] [›]│
│                                                                  Ex.: a coluna de 1 mês compara        │
│                                                                  out/2026 vs set/2026.                 │
│ ─────────────────────────────────────────────────────────────────────────────────────────────────── │
│ BUSCAR                                       VOLUME MÍNIMO                                             │
│ [lupa Código ou descrição do produto   ×]    [ 0      ] R$                                             │
│ ─────────────────────────────────────────────────────────────────────────────────────────────────── │
│ MOSTRAR  (Todos)(Maiores altas)(Maiores quedas)(Novos)                                Limpar filtros   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
 ▸ Como ler a tabela                                                       (details fechado)

┌ tabela ──────────────────────────────────────────────────────────────────────────────────────────────┐
│ Maiores altas em 3 meses                                                                               │
│ 1.842 produtos · faturamento líquido, com devoluções descontadas                                       │
├────┬───────────────────────────┬────────────┬─────────────┬─────────────┬───────────────────┤
│    │ Produto                   │ 1 MÊS      │ 3 MESES  ↓  │ 6 MESES     │ 12 MESES          │
│    │                           │ out/26     │ ago–out/26  │ mai–out/26  │ nov/25–out/26     │
│    │                           │ vs set/26  │ vs mai–jul/26│ vs nov/25–abr/26│ vs nov/24–out/25│
│    │                           │            │ ▔▔▔▔▔▔▔▔▔▔▔ │             │ [Base parcial]    │
├────┼───────────────────────────┼────────────┼─────────────┼─────────────┼───────────────────┤
│ [›]│ ÓLEO DE COCO 500 ML       │   ▲ +200,0%│   ▲ +180,5% │    ▲ +95,2% │      ▲ +40,1%     │
│    │ Cód. 1007 · LAB. BETA     │ ⚠Base baixa│             │             │                   │
│ [›]│ CHÁ VERDE 100G            │    ▲ +50,0%│    ▲ +16,7% │     ▲ +8,3% │     ▲ +108,3%     │
│    │ Cód. 1001 · LAB. ALFA     │            │             │             │                   │
│ [›]│ GUARANÁ EM PÓ             │   ▼ −100,0%│   ▼ −100,0% │    ▼ −83,4% │      ▼ −51,0%     │
│    │ Cód. 1003 · LAB. ALFA     │            │             │             │                   │
│ ·· SEM PERCENTUAL EM 3 MESES: NOVO, SEM BASE OU SEM MOVIMENTO ·······························     │
│ [›]│ CÁPSULA DE HIBISCO        │     ◆ Novo │      ◆ Novo │      ◆ Novo │       ◆ Novo      │
│    │ Cód. 1002 · LAB. GAMA     │ R$ 400,00  │  R$ 400,00  │  R$ 400,00  │    R$ 400,00      │
│ [›]│ SPIRULINA 60 CÁPS         │          — │           — │           — │            —      │
│    │ Cód. 1006 · Sem fornecedor│            │             │             │                   │
├────┴───────────────────────────┴────────────┴─────────────┴─────────────┴───────────────────┤
│ 1–50 de 1.842                                     ‹ Anterior    Página 1 de 37    Próxima ›       │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

> Os números do wireframe são ilustrativos de layout (não são dados reais); no desenvolvimento usar a massa sintética de `business_rules` §5.

**Visão por fornecedor, com um grupo expandido e um carregando** (≥1280px)

```
├────┬───────────────────────────┬────────────┬─────────────┬─────────────┬───────────────────┤
│    │ Fornecedor                │ 1 MÊS      │ 3 MESES  ↓  │ 6 MESES     │ 12 MESES          │
├────┼───────────────────────────┼────────────┼─────────────┼─────────────┼───────────────────┤
│ [⌄]│ LABORATÓRIO ALFA          │   ▼ −57,1% │   ▼ −20,3%  │    ▲ +12,0% │     ▲ +149,9%     │  fundo --brand-primary-subtle
│    │ 2 produtos                │            │             │             │ (trilho 3px --brand-primary)
│ ┃  Produtos de LABORATÓRIO ALFA · 2 com vendas no período               Ordenar por [Contribuição ▾]  │
│ ┃  Contribuição mostra quanto cada produto somou (+) ou tirou (−) da variação do fornecedor, em p.p.  │
│ ┃ [›]│ CHÁ VERDE 100G         │    ▲ +50,0% │    ▲ +16,7% │     ▲ +8,3% │     ▲ +108,3%     │
│ ┃    │ Cód. 1001              │ +14,3 p.p.  │ +6,2 p.p.   │ +3,1 p.p.   │ +108,3 p.p.       │
│ ┃ [›]│ GUARANÁ EM PÓ          │   ▼ −100,0% │   ▼ −100,0% │    ▼ −83,4% │      ▲ Novo       │
│ ┃    │ Cód. 1003              │ −71,4 p.p.  │ −26,5 p.p.  │ −8,9 p.p.   │ +41,7 p.p.        │
│ ┃    Mostrando 1–2 de 2                                                                              │
│ [›]│ LABORATÓRIO BETA          │   ▼ −92,7%  │   ...                                                 │
│    │ 2 produtos                │                                                                     │
│ [◌]│ LABORATÓRIO GAMA          │   (spinner no botão; aria-busy) ...                                  │
│ ┃  ░░░░░░░░░░░░░░ ░░░░░░  ░░░░░░  ░░░░░░  ░░░░░░      ← 2 linhas skeleton (geometria da linha filha)   │
```

**Tablet 768–1279px** (tabela compacta; mesma estrutura, colunas fluidas)

```
 Tendência de Vendas                                          (relógio) Vendas até 08/11/2026
 O que subiu e o que caiu: cada coluna compara os meses até out/2026 ...
 Mostra apenas produtos ativos do catálogo.

┌ controles ──────────────────────────────────────────────────────────────┐
│ VER                      MEDIR POR                                       │
│ [Por produto│Por fornec.] [Faturamento (R$)│Quantidade (un)]              │
│ MÊS-BASE                                                                 │
│ [‹] [out/2026 · último mês completo ▾] [›]  Ex.: 1 mês = out/2026 vs set/2026│
│ ─────────────────────────────────────────────────────────────────────── │
│ [lupa Código ou descrição ...  ×]   VOLUME MÍN. [0   ] R$                │
│ MOSTRAR (Todos)(Maiores altas)(Maiores quedas)(Novos)      Limpar filtros│
└─────────────────────────────────────────────────────────────────────────┘
┌ tabela ─────────────────────────────────────────────────────────────────┐
│ [›]│ Produto             │ 1 MÊS     │ 3 MESES ↓ │ 6 MESES   │ 12 MESES   │
│    │                     │ out/26    │ ago–out/26│ mai–out/26│ nov/25–    │
│    │                     │ vs set/26 │ vs mai–jul│ vs nov/25–│ out/26 vs  │
│    │                     │           │           │ abr/26    │ nov/24–... │
│ [›]│ ÓLEO DE COCO 500 ML │  ▲ +200,0%│ ▲ +180,5% │  ▲ +95,2% │  ▲ +40,1%  │
│    │ Cód. 1007 · LAB. BETA│ Base baixa│           │           │ [Base parc]│
```

**Mobile 375px** (cartões; D-4)

```
 Tendência de Vendas
 O que subiu e o que caiu: cada
 coluna compara os meses até
 out/2026 com os meses
 imediatamente anteriores.
 Mostra apenas produtos ativos
 do catálogo.
 (relógio) Vendas até 08/11/2026

┌─────────────────────────────────────┐
│ Ver                                   │
│ [Por produto   │ Por fornecedor    ]  │  100% da largura, 2 segmentos iguais
│ Medir por                             │
│ [Faturamento (R$)│Quantidade (un)  ]  │
│ Mês-base                              │
│ [‹][out/2026 · último mês completo ▾][›]│
│ Buscar                                │
│ [lupa Código ou descrição        ×]   │
│ Volume mínimo                         │
│ [ 0            ] R$                   │  campo comum (sem <details>: só há um filtro extra)
│ Mostrar                               │
│ (Todos)(Maiores altas)                │  chips quebram em 2 linhas (flex-wrap)
│ (Maiores quedas)(Novos)               │
│ Ordenar por [3 meses ▾]               │
│ [Altas primeiro │ Quedas primeiro ]   │
└─────────────────────────────────────┘
 ▸ Períodos comparados  (com out/2026)    <details>: lista de 4 linhas (PeriodLegend)
 Maiores altas em 3 meses
 1.842 produtos · faturamento líquido

┌─────────────────────────────────────┐
│ [›] ÓLEO DE COCO 500 ML               │
│     Cód. 1007 · LABORATÓRIO BETA       │
│ ┌───────┬───────┬───────┬───────┐    │
│ │ 1 MÊS │3 MESES│6 MESES│12 MESES│   │  rótulos 0.72rem; "3 MESES" com fundo
│ │▲+200,0│▲+180,5│ ▲+95,2│ ▲+40,1│    │  --brand-primary-subtle (coluna ordenada)
│ │  %    │  %    │  %    │  %    │    │  (o % cabe numa linha; ≤359px vira grade 2×2)
│ └───────┴───────┴───────┴───────┘    │
│ 1 mês: Base baixa                      │  microselos com o prefixo da janela
└─────────────────────────────────────┘
 ... (50 cartões por página)
 1–50 de 1.842           ‹ Anterior  Página 1 de 37  Próxima ›
```

- Cartão = `<li>` de uma `<ol>` com `aria-label` do cabeçalho; sem sombra (hairline `--border-default`, `--radius-sm`), sem card dentro de card: o cartão do fornecedor expandido lista os produtos em **linhas internas separadas por hairline**, não em cartões aninhados.

### 5.8 Legenda "Como ler a tabela" (`ReadingGuideComponent`, `<details>`)

Fechada por padrão; abre por teclado/toque (o conteúdo essencial **não** depende de hover). Lista de definição, 0.82rem, uma linha por item, com o mesmo glifo/cor da célula:

`▲ +12,3% alta · ▼ −12,3% queda · ▬ 0,0% estável · ◆ Novo: sem venda líquida no período anterior (produto novo ou retomado), por isso não tem percentual · — sem percentual: sem base ou sem vendas nos dois períodos · Base parcial: os períodos têm dias diferentes na base (início da base ou mês corrente) e a conta usa a média por dia · Base baixa: poucas vendas no período anterior, o percentual pode exagerar · Devoluções superam vendas: o valor entrou como zero · p.p.: ponto percentual, a contribuição de um produto para a variação do fornecedor · Escopo: a tabela mostra apenas produtos ativos do catálogo.`

---

## 6. Matriz de estados visuais

### 6.1 Estados da tela (área de resultado)

| # | Estado | Condição | O que aparece |
| :--- | :--- | :--- | :--- |
| 1 | **Carregando inicial** | 1ª carga, ou troca de agrupamento | Cabeçalho do painel real + skeleton (§6.2); seletor de mês como skeleton de 220×40px até o `meta` chegar |
| 2 | **Recarregando** | mudança de filtro, ordenação, página ou métrica com dados já na tela | Tabela/cartões **ficam**, esmaecidos (`$dimmed-opacity`), `aria-busy="true"`, sem skeleton (a troca de métrica não lê o banco, P-073.5, e costuma ser instantânea). Subtítulo troca para `Atualizando…` |
| 3 | **Sucesso** | 200 com itens | Cabeçalho + tabela + pager |
| 4 | **Vazio por filtro** | 200, `totalItems = 0`, há filtro ativo | `TrendEmptyState kind='empty-filters'` (§6.3) |
| 5 | **Vazio por atalho** | 200, `view ≠ all`, sem itens | `empty-view` (§6.3) |
| 6 | **Página além do fim** | 200, `data = []`, `totalItems > 0` | `empty-page` |
| 7 | **Histórico insuficiente** | 200, as 4 janelas `semBase` (P-078.7) | `InlineNotice warning` acima da tabela **e** tabela de `—` (a tabela fica: é 200) |
| 8 | **Mês-base parcial** | `meta.mesBaseParcial = true` | `InlineNotice info` persistente (§6.3) |
| 9 | **Mês-base inválido / fora da base** | `TND-002` (422) | `TrendEmptyState kind='invalid-base-month'` no lugar da tabela; controles continuam ativos |
| 10 | **Falha técnica** | rede, 5xx, `TND-004` (503), `TND-005` (429) | `TrendErrorBanner` com `Tentar de novo`; controles continuam ativos |
| 11 | **Detalhe carregando** | expandiu fornecedor | skeleton de 3 linhas filhas dentro do grupo; botão com spinner |
| 12 | **Detalhe com erro** | falha no detalhe | linha de erro dentro do grupo (§6.4); resto da tabela intacto |
| 13 | **Detalhe sumiu / base atualizada** | `TND-003` ou `dataReferencia` diferente | grupo recolhe com `InlineNotice` (§6.4) |

### 6.2 Skeleton Loader

- Pulso sólido global `.skeleton-line`/`.skeleton-box` (sem gradiente), `animation: none` com `prefers-reduced-motion: reduce`. `aria-hidden="true"` no skeleton e `aria-busy="true"` no painel.
- **Tabela (10 linhas, `$skeleton-rows`)** com o **mesmo grid** da tabela real e o cabeçalho **real** (as colunas já são conhecidas): por linha, botão 40×40 (bloco `$chevron-hit`), duas barras na coluna do nome (68% × 0.88rem e 42% × 0.75rem) e 4 pares de barras alinhadas à direita (72px × 0.88rem e 40px × 0.75rem, o segundo só em ~1 de 4 linhas, para dar ritmo). Altura de linha 56px idêntica à real (sem salto de layout).
- **Visão por fornecedor:** mesma geometria, 1ª coluna com barra de 55% e `{n} produtos` curto.
- **Cartões (mobile, 5 cartões):** barra de título 70%, linha de apoio 45%, grade 4-up de blocos 100% × 36px.
- **Detalhe do fornecedor:** 3 linhas filhas skeleton recuadas, com o trilho esquerdo; mínimo `min(qtdProdutos, 3)` linhas para o grupo não saltar quando fechar o carregamento.
- **Seletor de mês-base** enquanto o `meta` não chega: bloco 220×40px (`$skeleton`), campo desabilitado com `aria-busy`.
- **Cache frio (backend, P-083):** se o carregamento passar de 4 s, abaixo do skeleton: `A primeira consulta depois de algumas horas monta a base de vendas e demora mais. As próximas são rápidas.` (texto honesto, sem prometer tempo; o aviso só aparece antes da 1ª busca se o contrato expuser o estado do cache, Q-14).

### 6.3 Vazios e avisos (`TrendEmptyState` e `InlineNotice`)

Anatomia comum do `TrendEmptyState` (componente próprio): ícone SVG 36×36 `aria-hidden` em caixa 56×56 `--bg-subtle`, título 1rem, texto 0.88rem `--text-secondary` (máx. 60ch), ação `.btn-secondary`, alinhado à esquerda (não centralizar).

| `kind` | Ícone | Título | Texto | Ação |
| :--- | :--- | :--- | :--- | :--- |
| `empty-filters` | lupa com traço | Nenhum produto com esses filtros | `Ajuste a busca ou o volume mínimo para ver mais produtos. A tabela mostra apenas produtos ativos do catálogo.` + linha `Filtros ativos: busca "cha" · Volume mínimo 10 un` | `Limpar filtros` |
| `empty-view` (`rising`) | seta para cima vazia | Nenhum produto subiu em 3 meses | `Com os filtros atuais, nenhum produto tem variação positiva nesta coluna. Veja todos ou troque a coluna.` | `Mostrar todos` |
| `empty-view` (`falling`) | seta para baixo vazia | Nenhum produto caiu em 3 meses | `Com os filtros atuais, nenhum produto tem variação negativa nesta coluna. Veja todos ou troque a coluna.` | `Mostrar todos` |
| `empty-view` (`new`) | losango vazio | Nenhum produto novo em 3 meses | `Novo é o produto sem venda líquida no período anterior. Com os filtros atuais, não há nenhum nesta coluna.` | `Mostrar todos` |
| `empty-page` | lista | Esta página não tem itens | `A lista tem {totalItems} produtos; voltamos para o começo.` | `Ir para a primeira página` |
| `invalid-base-month` | calendário com traço | Sem vendas neste mês-base | `O mês-base escolhido não possui dias com vendas registradas na base.` (literal de `TND-002`) | `Voltar para out/2026` (usa `mesBasePadrao` do último `meta`; sem `meta` ainda: `Tentar de novo`) |
| `empty-supplier` (detalhe) | caixa com traço | Nenhum produto com vendas neste período | `{fornecedor} não tem produtos com movimento entre {nov/24} e {out/26}.` | `Recolher` |

Variantes de fornecedor: onde está "produto(s)", usar "fornecedor(es)"; `empty-filters` na visão fornecedor cita `busca "alfa"` (só os filtros realmente ativos entram na linha `Filtros ativos`) e a nota passa a ser `A tabela agrupa apenas produtos ativos do catálogo.`

**`InlineNotice`** (faixa fina, `role="status"`, não bloqueia a tela; filete esquerdo 3px):

| Aviso | Tom | Texto | Ação / dispensável |
| :--- | :--- | :--- | :--- |
| Mês-base parcial (`mesBaseParcial`) | info (`--feedback-info-bg`) | `Mês-base parcial: nov/2026 tem vendas só até 08/11. A conta usa a média por dia.` | persistente, sem dispensar |
| Histórico insuficiente (4 × `semBase`) | warning (`--feedback-warning-bg`) | `Histórico anterior insuficiente para este mês-base. A base de vendas começa em jan/2025, então não há período anterior para comparar. Escolha um mês-base mais recente.` | `Usar out/2026` (`mesBasePadrao`) |
| Troca de agrupamento com filtros limpos | info | `Trocamos para a visão por fornecedor. A busca, o atalho e o volume mínimo foram limpos.` | dispensável |
| Fornecedor sumiu (`TND-003`) | warning | `{fornecedor} não aparece mais com os filtros atuais, então recolhemos a linha.` | dispensável |
| Base atualizada (detalhe com `dataReferencia` diferente, P-092.7) | info | `A base foi atualizada (vendas até 09/11/2026). Recarregamos a lista.` | dispensável |
| Volume mínimo zerado por troca de métrica | info | `Volume mínimo zerado: a unidade mudou de un para R$.` | some em 8 s e fica na região viva |

### 6.4 Erros (copy humana, sem stack, sem eco de valores)

| Código | Onde aparece | Texto |
| :--- | :--- | :--- |
| `TND-004` (503, base indisponível) | `TrendErrorBanner` (`role="alert"`) no lugar da tabela | `Base de vendas indisponível no momento. Tente novamente em instantes.` + `Tentar de novo` |
| `TND-005` (429, recarga recente) | `TrendErrorBanner` | `A base foi recarregada há pouco. Tente de novo em alguns minutos.` + `Tentar de novo`. A tela **não** oferece botão de recarga (nunca envia `force_reload`), então o código só aparece por defesa (Q-16) |
| Rede / timeout / 5xx | `TrendErrorBanner` | `Não foi possível carregar a tendência de vendas agora. Tente de novo em instantes.` + `Tentar de novo` |
| `TND-001` campo `baseMonth` | inline no seletor | `Escolha um mês entre jan/2025 e nov/2026.` (limites do último `meta`) |
| `TND-001` campo `q` | inline no campo | `Digite ao menos 2 letras ou 1 número, até 60 caracteres.` |
| `TND-001` campo `minVolume` | inline no campo | `Informe um número maior ou igual a zero.` |
| `TND-001` outros campos (`sortWindow`, `view`, `limit`, `offset`, `groupBy`, `metric`) | `TrendErrorBanner` genérico (é falha do front, não do usuário) | texto da falha técnica |
| `TND-002` (422) | `TrendEmptyState invalid-base-month` + erro inline no seletor | ver §6.3 |
| `TND-003` (404, detalhe) | grupo recolhido + `InlineNotice warning` | ver §6.3 |
| Falha ao carregar o detalhe | **linha de erro dentro do grupo**: ícone + `Não foi possível carregar os produtos de {fornecedor}.` + `Tentar de novo` | foco permanece no botão de expandir |

Erro inline de campo: ícone 14px + texto 0.82rem 600 em `--feedback-critical-bg`, `aria-invalid="true"` e `aria-describedby` no controle; borda do campo `--feedback-critical-bg`; valor digitado mantido. Nunca `detail` cru, stack nem a instrução de terminal que a tela de preços mostra.

### 6.5 Matriz dos 8 estados por elemento interativo

| Elemento | Default | Hover | Focus-visible | Active | Disabled | Loading | Error | Selected / Expandido |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Segmento / chip (`Ver`, `Medir por`, `Mostrar`) | `--bg-surface`, `--text-secondary`, borda `--border-default` | `--bg-subtle` | anel 2px `--border-focus`, `outline-offset: -3px` (inset) | `--brand-primary-active` + `--text-on-brand` | n/a (sempre operável) | segue operável; o painel da tabela mostra o estado 2 | n/a | `--brand-primary` + `--text-on-brand` + `aria-checked="true"` |
| Select de mês-base | `--bg-subtle`, borda `--border-subtle` | borda `--border-default` | anel 2px `--border-focus`, offset 2px | n/a | enquanto o `meta` não chega: `opacity .5`, `not-allowed` + skeleton | skeleton 220×40 + `aria-busy` | borda e texto `--feedback-critical-bg`, `aria-invalid` | opção ativa pré-marcada |
| Botões `‹` `›` do mês (só ícone) | ícone `--text-secondary`, caixa 40×40 | `--text-primary` + `--bg-subtle` | anel 2px | `--bg-muted` | no limite: `opacity .5` + `aria-disabled` | n/a | n/a | n/a |
| Campo de busca | `--bg-subtle`, borda `--border-subtle` | borda `--border-default` | `:focus-within`, anel 2px offset 2px no container | n/a | n/a (nunca desabilitado) | continua editável (debounce 300 ms) | borda e mensagem `--feedback-critical-bg` | com valor: botão `×` visível |
| Volume mínimo | idem busca | idem | idem | n/a | n/a | n/a | erro inline | valor ≠ 0 conta como filtro ativo |
| Cabeçalho ordenável (botão) | `--text-primary` sobre `--bg-table-header`, ícone de duas setas | `--bg-subtle`, `--brand-primary` no texto | anel 2px **inset** (`outline-offset: -3px`) | `--bg-muted` | n/a | seta substituída por skeleton curto só na 1ª carga | n/a | seta ↓/↑ + sublinhado 3px `--brand-primary` + `aria-sort` |
| Botão de expandir (chevron) | 40×40, ícone `--text-secondary` | `--bg-subtle` | anel 2px **inset** | `--bg-muted` | n/a (sempre operável) | spinner (mixin `spinner` de `_trend-ui.scss`) no lugar do chevron, `aria-busy`, `aria-label` vira `Carregando produtos de {nome}` | se o detalhe falhou: ícone de alerta e `aria-label` `Tentar de novo: produtos de {nome}` | chevron 90°, `aria-expanded="true"`, linha com `--brand-primary-subtle` e trilho 3px `--brand-primary` |
| Linha da tabela | `--bg-surface` | `--bg-table-row-hover` (`@media (hover: hover)`) | n/a (a linha não é focável) | n/a | n/a | skeleton / esmaecida | n/a | expandida: ver chevron |
| Linha filha | `--bg-table-row-zebra`, trilho `--border-default` | `--bg-table-row-hover` | n/a | n/a | n/a | skeleton recuado | linha de erro com `Tentar de novo` | idem (pode abrir os valores do filho) |
| `Limpar filtros` / `Tentar de novo` / ações dos estados | `--brand-primary` / `.btn-secondary` | sublinhado / `--bg-subtle` | anel 2px | `--brand-primary-active` / `--bg-muted` | `Limpar filtros`: oculto (não desabilitado) quando não há filtro | `Tentar de novo`: spinner + `Tentando…` | n/a | n/a |
| `TrendPager` Anterior/Próxima | `.btn-secondary` | `--bg-subtle` | anel 2px | `--bg-muted` | primeira/última página: `opacity .5` | `disabled` durante a carga | n/a | n/a |
| `<details>` "Como ler" / "Períodos comparados" | resumo `--text-secondary` 0.82rem 600 com chevron | `--text-primary` | anel 2px | n/a | n/a | n/a | n/a | aberto: chevron 90°, `aria-expanded` nativo |

Hovers em `@media (hover: hover)`; transições só de cor/borda/rotação (`--transition-fast`), nunca de `width`/`height`/`padding`. Com `prefers-reduced-motion: reduce`: sem pulso de skeleton, sem rotação de chevron, sem transição de opacidade.

---

## 7. Acessibilidade

1. **Estrutura da tabela:** `<table>` real; `<caption class="sr-only">` com o resumo (`Variação de vendas por produto. Faturamento líquido. Mês-base out/2026. Ordenada por 3 meses, maiores altas primeiro.`); cabeçalhos `<th scope="col">`; primeira célula de cada linha `<th scope="row">`; divisor de grupo `<th scope="rowgroup">`; cada fornecedor expandido num `<tbody>` próprio (linha pai + detalhe), de modo que os filhos ficam agrupados para o leitor de tela. `aria-sort="ascending|descending"` só na coluna ordenada e `aria-sort="none"` nas demais ordenáveis; o `<button>` dentro do `<th>` tem nome `Ordenar por 3 meses (ago–out/26 vs mai–jul/26)`; o estado atual vem de `aria-sort`, não do nome.
2. **Ordenação e atalhos por teclado:** Tab chega aos botões de cabeçalho; Enter/Espaço ordenam. `Mostrar`, `Ver` e `Medir por` são `radiogroup`: um Tab entra no grupo, ←/→ movem e selecionam, Home/End vão às pontas. Sem atalhos de tecla única (WCAG 2.1.4).
3. **Expandir/recolher:** o botão de cada linha tem `aria-expanded` e `aria-controls`. Enter/Espaço alternam; **Esc** dentro do detalhe recolhe e devolve o foco ao botão.
4. **Foco ao carregar filhos:** o foco **permanece no botão** (não pular). A região viva anuncia o carregamento e o fim. O próximo Tab entra na ordem natural do DOM (barra do detalhe → filhos → pager). Ao trocar de página dos filhos, o foco vai para o `h3` da barra do detalhe (`tabindex="-1"`). Em erro do detalhe, o foco continua no botão e o botão de nova tentativa é o próximo Tab. Em `TND-003`, o grupo recolhe e o foco vai para o botão do fornecedor (se a linha existir) ou para o título da tabela.
5. **Regiões vivas (um `role="status"` educado, sempre no DOM, visualmente oculto):** `Carregando a tendência de vendas…` → `{n} produtos, ordenados por maiores altas em 3 meses. Página 1 de 37.`; mudança de ordenação (`Ordenado por 12 meses, maiores quedas primeiro.`); expandir (`Carregando produtos de LABORATÓRIO ALFA…` → `2 produtos de LABORATÓRIO ALFA carregados.`); recolher; troca de agrupamento e de métrica; avisos do §6.3. Erros: `role="alert"` (banner) ou `aria-describedby` no campo.
6. **Direção sem cor:** cada célula tem texto `sr-only` com palavra ("Alta de…", "Queda de…", "Estável"), e o visível é `aria-hidden` (o leitor não lê "mais" nem "menos" ambíguos). Ícones e triângulos `aria-hidden="true"`.
7. **Botões só-ícone com `aria-label`:** `‹`/`›` do mês, `×` da busca, chevrons de expandir, ícone de ordenação (decorativo, dentro do botão com texto). Rótulo visível contido no nome acessível (WCAG 2.5.3).
8. **Tooltips nunca são a única via:** tudo que o `title` diz está na legenda "Como ler a tabela" e na sub-tabela "Valores por janela" (alcançáveis por teclado e toque).
9. **Foco visível:** anel global `2px solid var(--border-focus)` com offset 2px; **inset** (`outline-offset: -3px`) em cabeçalhos, chevrons e segmentos, para não ser cortado. Nenhum `outline: none` sem `:focus-within`/inset substituto.
10. **Alvos de toque:** 40×40px mínimo em segmentos, chips, chevrons, botões de mês, `×` e pager.
11. **Idioma e números:** `lang="pt-BR"`; vírgula decimal e `R$` pelos utilitários; menos tipográfico `−` (U+2212) só no visível, o `sr-only` diz "queda".
12. **`prefers-reduced-motion`:** ver §6.5.
13. **Cartões (mobile):** `<ol>` com `<li>`; a grade 4-up é uma lista de 4 itens com rótulo visível por mini-célula (`1 mês`, `3 meses`…), lidos como "3 meses: alta de 16,7 por cento".

---

## 8. Responsividade (testar em 320 / 375 / 414 / 768 / 1024 / 1280 px, sem scroll horizontal da página)

| Faixa | Comportamento |
| :--- | :--- |
| **Mobile < 768px** | **Cartões** no lugar da tabela (decisão abaixo). Padding lateral `--space-4`. Controles empilhados em coluna (cada um 100%): `Ver`, `Medir por`, `Mês-base` (`‹ select ›`), `Buscar`, `Volume mínimo`, chips de `Mostrar` (com quebra de linha), `Ordenar por` (select de janela + `Altas primeiro \| Quedas primeiro`). Selo de data quebra para baixo do título. `Períodos comparados` em `<details>` acima da lista. Pager: contador em cima, `‹ Anterior` / `Próxima ›` abaixo |
| **Tablet 768–1279px** | **Tabela compacta**: mesmas 6 colunas fluidas (nome `minmax(0, 1fr)` ≥ 220px, janelas ≥ 104px, `table-layout: fixed`), cabeçalho com período em 2 linhas, selos de janela em linha própria; controles em 3 faixas que quebram em duas linhas cada |
| **Desktop ≥ 1280px** | Tabela com janelas até 168px (a contribuição mostra p.p. e valor na mesma linha, §5.6); controles da faixa 1 em uma só linha; painel de controles `max-width: 100%` (a tabela é o centro) |

Regras gerais: `grid-template-columns` com `minmax(0, …)`; `min-width: 0` e `overflow-wrap: anywhere` em descrições; breakpoints com as constantes SCSS (`$bp-mobile = 639.98px`, `$bp-cards = 767.98px`, `$bp-wide = 1279.98px` e `$bp-tiny = 359.98px`, todas em `_trend-ui.scss` da própria feature; a navbar de `main` troca de altura em 768px); `html, body { overflow-x: clip }` já vigente.

### Decisão de mobile: cartões com grade 4-up (D-4), não tabela com coluna fixa e rolagem horizontal

**Por que cartões**
1. **A leitura central é comparar as 4 janelas de um produto lado a lado** (1 mês sobe, 12 meses cai: "acelerou" ou "perdeu fôlego"). Em 375px, uma coluna fixa útil (≥ 140px com nome e código) deixa ~200px: **duas** janelas visíveis por vez. As colunas de 6 e 12 meses ficam fora da tela justamente em linhas que o usuário quer comparar. Num cartão, as 4 cabem juntas (4 × ~80px).
2. **Rolagem horizontal dentro da tabela** cria um segundo contêiner de rolagem (conflita com o gesto de voltar do navegador, exige região focável para teclado, e anula o cabeçalho `sticky` da tabela). Cartões evitam os três problemas.
3. **Descrição longa + selos** (`Base baixa`, `Devoluções superam vendas`) precisam de 2 a 3 linhas; a célula de uma tabela estreita as espremeria.
4. **Custo:** dois renderizadores. Mitigado porque os dois consomem o **mesmo** `TrendRowView`/`TrendCellView` e o mesmo `TrendCellComponent`; só o invólucro muda. A página renderiza um ou outro (`viewport.isCompact`), nunca os dois.
5. **O que se perde** (honesto): a comparação vertical entre linhas da mesma coluna. Compensações: coluna ordenada destacada em cada cartão (fundo `--brand-primary-subtle` + rótulo em 700), título "Maiores altas em 3 meses" e controle `Ordenar por` visível, já que não há cabeçalhos clicáveis.

**Grade 4-up:** `grid-template-columns: repeat(4, minmax(0, 1fr))`; cada mini-célula é uma pilha rótulo (0.72rem, caixa alta) → valor (mono 0.82rem). `▲ +1.250,5%` cabe em ~78px; **≤ 359px** vira **2×2** (`$bp-tiny`). Microselos dos cartões vêm num rodapé com o prefixo da janela (`1 mês: Base baixa`), porque não há cabeçalho de coluna para qualificá-los; `Base parcial` e `Sem base` ficam na legenda `Períodos comparados` (uma vez, não por cartão).

**Fornecedor expandido no mobile:** o botão do cartão abre uma lista interna de produtos (linhas separadas por hairline, cada uma com a mesma grade 4-up e a linha de contribuição `+14,3 p.p.`), com o `TrendPager` no fim do grupo. "Valores por janela" vira lista vertical de 4 itens.

---

## 9. Copy deck (pt-BR)

| Local | Texto |
| :--- | :--- |
| Item da navbar | Tendência de Vendas |
| `h1` / subtítulo / escopo | Tendência de Vendas / O que subiu e o que caiu: cada coluna compara os meses até {mês-base} com os meses imediatamente anteriores, de mesmo tamanho. / Mostra apenas produtos ativos do catálogo. |
| Selo de data | Vendas até {dd/MM/yyyy} |
| Rótulos dos controles | Ver · Medir por · Mês-base · Buscar · Volume mínimo · Mostrar · Ordenar por |
| `Ver` | Por produto · Por fornecedor |
| `Medir por` | Faturamento (R$) · Quantidade (un) |
| Linha de contexto da métrica | faturamento líquido, com devoluções descontadas · quantidade líquida, com devoluções descontadas |
| Mês-base (opções) | {mmm/aaaa} · último mês completo · {mmm/aaaa} · mês corrente, parcial até {dd/MM} |
| Mês-base (ajuda) | Ex.: a coluna de 1 mês compara out/2026 vs set/2026. |
| Mês-base (botões `aria-label`) | Mês-base anterior, set/2026 · Próximo mês-base, nov/2026 |
| Busca | Código ou descrição do produto · Nome do fornecedor · Limpar busca |
| Volume mínimo | Volume mínimo · sufixo `un` ou `R$` · dica no §5.3 |
| `Mostrar` | Todos · Maiores altas · Maiores quedas · Novos |
| Ação | Limpar filtros |
| Ordenar (mobile) | 1 mês · 3 meses · 6 meses · 12 meses · Altas primeiro · Quedas primeiro |
| Colunas | Produto · Fornecedor · 1 mês · 3 meses · 6 meses · 12 meses |
| Período no cabeçalho | {atual} / vs {anterior}: `out/26` / `vs set/26`; `ago–out/26` / `vs mai–jul/26`; `nov/25–out/26` / `vs nov/24–out/25` |
| Célula | +12,3% · −100,0% · 0,0% · Novo · — |
| Selos | Base parcial (janela) · Sem base (janela) · Base baixa · Devoluções superam vendas |
| Fornecedor | {n} produtos · Sem fornecedor · Contribuição · +14,3 p.p. · −71,4 p.p. · por dia |
| Disclosures | Como ler a tabela · Períodos comparados · Ver valores de {nome} · Valores por janela |
| Divisor de grupo | Sem percentual em 3 meses: Novo, sem base ou sem movimento |
| Pager | {a}–{b} de {total} · Anterior · Página {p} de {t} · Próxima |
| Estados | ver §6.3 e §6.4 |

Formatos pt-BR: 1 casa decimal e vírgula (`+12,3%`), milhar com ponto (`+1.250,5%`), sinal explícito exceto em `0,0%`, menos tipográfico `−`, moeda `R$ 1.234,56`, quantidade inteira com milhar (`1.234 un`; até 2 casas se a base tiver fração), datas `dd/MM/yyyy`, meses `mmm/aa` em minúsculas e abreviados (`jan`, `fev`, `mar`, `abr`, `mai`, `jun`, `jul`, `ago`, `set`, `out`, `nov`, `dez`), intervalo com travessão curto `ago–out/26`. Nunca "Seamless", "Elevate", "insights", "inteligente", "IA". Termo "item": na tela "Produto" (Glossário); "venda casada" nunca.

---

## 10. Fora de escopo nesta fase

- Gráfico de linha/sparkline por produto e KPI herói (a API não traz série nem totais; ver Q-4).
- Exportar CSV (fora do escopo das regras).
- Ordenar por nome/código/valor absoluto, filtros por categoria, comparação de dois meses-base lado a lado.
- Seleção de várias linhas, edição, favoritos.
- Busca por produto dentro da visão por fornecedor (A-23: busca só pelo nome do fornecedor).
- Busca por `q` dentro do detalhe do fornecedor (o contrato aceita, a tela não expõe; evolução).
- Animações com Anime.js e imagens geradas (nada aqui pede).

---

## 11. Campos que a tela precisa do contrato (Arquiteto) e dúvidas Q-n

**Lista (`GET /api/v1/sales-trend`; nomes finais de rota no contrato refeito)** — o que a UI consome. Universo = só produtos ativos; **sem** `activeOnly` e **sem** `ativo`:
- `data[]` (produto): `codigo`, `descricao`, `fornecedor` (`null` quando sem fornecedor), `janelas[4]` com `meses`, `atual`, `anterior`, `variacaoPct`, `status`, `baseParcial`, `baseBaixa`, `devolucaoLiquida`.
- `data[]` (fornecedor): `fornecedor`, `fornecedorChave`, `qtdProdutos`, `janelas[4]` (sem `codigo`/`descricao`).
- `meta`: `page`, `limit`, `offset`, `totalItems`, `totalPages`, `dataReferencia`, `ultimoDiaCoberto`, `mesBase`, `mesBasePadrao`, `mesBaseMinimo`, `mesBaseMaximo`, `metrica`, `mesBaseParcial`, `janelas[]` (`meses`, `atual{inicio,fim,diasJanela,diasCobertos}`, `anterior{…}`, `semBase`).

**Detalhe (rota de detalhe sob `/api/v1/sales-trend`, ex.: `/supplier-products`)**: filhos com a linha de produto e, por janela, `contribuicaoPp`, `contribuicaoValor`; `meta.fornecedor` (`fornecedor`, `fornecedorChave`, `qtdProdutos`, `janelas[]`), `meta.dataReferencia`, paginação.

**Dúvidas (cada uma com a recomendação do Designer)**

- **Q-1 — `baseParcial` e `semBase` como propriedade da janela.** Os selos `Base parcial` e `Sem base` ficam no cabeçalho da coluna (D-7). Pelas regras (P-089.5, P-076.7) todo SKU compartilha a cobertura da janela. *Recomendo* `meta.janelas[].baseParcial` (boolean) e `meta.janelas[].semBase` explícitos, e confirmar no contrato que `janelas[].baseParcial` por item é sempre igual ao da janela. Se divergir em algum caso, a célula volta a mostrar o selo.
- **Q-2 — Formato de `inicio`/`fim`.** *Recomendo* `YYYY-MM-DD` (primeiro e último dia da janela), de onde a UI monta `ago–out/26` (mesmo ano: `ago–out/26`; vira o ano: `nov/25–out/26`; um mês: `out/26`). `mesBase*` em `YYYY-MM`. `ultimoDiaCoberto` e `dataReferencia` em `YYYY-MM-DD`.
- **Q-3 — Média por dia pronta.** P-086.2 manda mostrar "média por dia" e dias cobertos quando `baseParcial`. Dividir na tela seria regra de negócio no front. *Recomendo* por célula `atualPorDia` e `anteriorPorDia` (`null` fora da base parcial); os dias vêm de `meta.janelas[].diasCobertos`. No detalhe, `contribuicaoValor` já é por dia nesse caso (P-090.2): *recomendo* um boolean `porDia` na janela do filho (ou `meta`) para rotular.
- **Q-4 — Linha "Todos os produtos".** Um total por janela da base inteira daria o ponto de referência ("a empresa subiu 8% em 3 meses; este fornecedor caiu 20%"). *Recomendo* `meta.total` com a mesma forma de uma linha de fornecedor (`janelas[4]` com `atual`, `anterior`, `variacaoPct`, `status`…), calculado sobre o universo (produtos ativos), **ignorando** `q`, `view` e `minVolume`. É opcional: a tela renderiza a linha só se o campo existir.
- **Q-5 — Detalhe: tamanho de página e ordem.** *Recomendo* `limit` padrão **20** no detalhe (a lista fica em 50) e confirmar `sortBy=contribution` como padrão com `sortWindow`/`sortDir` herdados da lista. O `meta.fornecedor` precisa trazer os mesmos valores (`atual`, `anterior`) de cada janela para a sub-tabela "Valores por janela" do fornecedor.
- **Q-6 — Formato do erro.** Confirmar `{ error: { code, message, fields[] } }` também para `TND-001` a `TND-005` e que `fields` lista os nomes (`baseMonth`, `q`, `minVolume`, …) para a tela mapear erro inline por campo, **sempre por `code`/`fields`, nunca por texto**. Sem eco do valor recebido.
- **Q-7 — Distinguir `TND-002` por mês escolhido de "base vazia".** Ambos usam o mesmo código (P-082). *Recomendo* `fields: ['baseMonth']` no primeiro caso e `fields: []` no segundo, para a ação do vazio ser "Voltar para {padrão}" ou "Tentar de novo".
- **Q-8 — "Sem fornecedor" e `descricao`.** *Recomendo* a API devolver `fornecedor: "Sem fornecedor"` já rotulado (como `NO_SUPPLIER_LABEL`) para o grupo. Como só há produtos ativos do catálogo, a tela assume `descricao` sempre preenchida (a tela não tem texto "Sem cadastro"); confirmar. `fornecedorChave` opaco; a tela o envia por `encodeURIComponent` em `supplierKey`.
- **Q-9 — Parâmetros efetivos em `meta` (`meta.parametros`).** Para a tela não fixar "10 un / R$ 500,00" (A-7, a calibrar) nem "50%" na copy: `meta.parametros` com `limiteBaseBaixaQuantidade`, `limiteBaseBaixaFaturamento`, `coberturaMinimaAnterior`, `limiteBuscaMin`/`Max` (ou documentar as constantes no contrato).
- **Q-10 — Rótulos dos selos e dos períodos.** *Recomendo* o backend devolver **só dados estruturados** (booleans, números, datas) e a tela montar os textos em `utils/trend-view.ts` (copy testável, sem acoplar o domínio ao pt-BR). Confirmar (P-084.5 deixa em aberto).
- **Q-11 — Query params.** Nomes e valores aceitos exatamente como em P-084.1/P-092.2 (`baseMonth`, `metric`, `sortWindow`, `sortDir`, `view`, `q`, `minVolume`, `groupBy`, `limit`, `offset`; detalhe: `supplierKey`, `sortBy`), **sem** `activeOnly`. A tela omite parâmetros iguais ao padrão.
- **Q-12 — `meta` do detalhe repete `mesBase`, `metrica`, `janelas[]`** (P-092.6), para a tela conferir que lista e detalhe falam do mesmo universo, além de `dataReferencia` (P-092.7).
- **Q-13 — (substituída) Universo só de ativos.** Confirmar que o universo do contrato é "produtos ativos do catálogo" e que um produto que deixou de ser ativo some da lista e do detalhe (um fornecedor cujo único produto saiu devolve `TND-003` no detalhe). A tela não expõe nem trata `activeOnly`/`ativo`.
- **Q-14 — Cache frio.** O módulo tem endpoint de estado do cache/health próprio sob `/api/v1/sales-trend` (P-083.6 opcional)? Se sim, a tela mostra o aviso antes da 1ª busca; se não, só o aviso por tempo (> 4 s).
- **Q-15 — Ordenação por contribuição com `sortWindow` em `SEM_BASE`.** Linhas com contribuição `null` vão ao fim (P-092.4). Confirmar que a ordem continua estável entre páginas.
- **Q-16 (nova) — `TND-005` (429).** A tela nunca envia `force_reload`, então não deveria receber 429. Confirmar que nenhuma rota chamada pela UI devolve `TND-005`; se devolver, a copy está em §6.4 (`A base foi recarregada há pouco…`, com `Tentar de novo`). Também confirmar o corpo de `TND-004` (503) no mesmo formato `{ error: { code, message, fields[] } }`.
- **Q-17 (nova) — Prefixo e proxy.** Em `main`, `InventoryService` usa `baseUrl = '/api/v1/inventory'` fixo e o dev server usa `frontend/proxy.conf.json`. `SalesTrendService` seguirá o mesmo padrão com `'/api/v1/sales-trend'`. Confirmar que o prefixo `/api/v1/sales-trend` já é coberto pelo proxy (se o `proxy.conf.json` filtra por `/api/v1/inventory`/`/api/v1/pricing`, precisa de entrada nova).

---

## 12. Decisões de design a validar no checkpoint

| # | Decisão |
| :--- | :--- |
| D-1 | Seguir os tokens reais de `styles.scss` (Papel & Tinta), como `inventory` e `pricing`. |
| D-2 | **(revisada)** Página própria em `/tendencia-vendas` (lazy, antes do curinga), item próprio "Tendência de Vendas" na navbar; sem shell, sem abas, sem `mode-switch`. |
| D-3 | Macroestrutura "workbench": controles → tabela ledger. **Sem KPI herói nem gráfico** (a API não traz totais nem série); linha "Todos os produtos" opcional (Q-4). |
| D-4 | **Mobile (<768px): cartões com grade 4-up (2×2 abaixo de 360px)**, ordenação por controle dedicado; tabela só a partir de 768px, sem rolagem horizontal (justificativa em §8). |
| D-5 | Um token novo, `--navbar-height`, para o cabeçalho fixo da tabela; sem ele, sem `sticky`. |
| D-6 | Direção por triângulo + sinal (menos tipográfico) + palavra para leitor de tela + cor; verde e vermelho têm luminância parecida, então a cor nunca é o único sinal. |
| D-7 | `Base parcial` e `Sem base` no **cabeçalho da coluna** (propriedade da janela, evita repetir em todas as linhas); `Base baixa` e `Devoluções superam vendas` em microselos de contorno na célula; legenda "Como ler a tabela". |
| D-8 | Toda linha expansível com botão disclosure (`aria-expanded`) em tabela comum, **não `treegrid`**: produto mostra "Valores por janela"; fornecedor mostra valores + produtos. Esc recolhe. |
| D-9 | Produtos do fornecedor: `TrendPager` (próprio) no rodapé do grupo, 20 por página, vários grupos abertos ao mesmo tempo, ordenação padrão por contribuição. |
| D-10 | Contribuição na 2ª linha da célula filha: p.p. sempre, valor ao lado quando a célula tem ≥168px (container query); o valor completo está na sub-tabela do filho. Sem barras divergentes (YAGNI). |
| D-11 | Divisor "Sem percentual em X meses" na transição para `Novo`/`—`, porque esses grupos ficam sempre no fim, nos dois sentidos de ordem. |
| D-12 | Estado da consulta (agrupamento, métrica, mês-base, coluna e sentido, atalho, busca, volume, página) em **query params** da URL, fonte única de verdade (voltar/compartilhar). Nada de dado pessoal; nada em `localStorage`/`sessionStorage`. |
| D-13 | Primeira carga e troca de agrupamento usam skeleton; as demais mudanças mantêm a tabela esmaecida (sem flash de skeleton). |
| D-14 | **(revisada)** Feature autônoma: nenhum import de `features/analytics/**` nem de `_analytics-ui.scss` (não existem em `main`). Paginação, banner de erro, estado vazio, skeleton, `SegmentedControl`, formatação pt-BR e mixins SCSS são próprios em `features/sales-trend/`. A edição de componentes da Fase 1 deixa de existir. |
| D-15 | Rótulos curtos nos segmentos (`Faturamento (R$)` / `Quantidade (un)`) para nunca quebrar linha; o nome completo está na linha de contexto da tabela. |
| D-16 | `SegmentedControlComponent` próprio com semântica `radiogroup` (alternadores são filtros, não abas). |
| D-17 | Rótulo "Fornecedor" na coluna e nos textos (o Glossário §4 evita "laboratório" nas regras; a tela de estoque usa "Laboratório / Fornecedor", e o Designer prefere o termo neutro do contrato). |
| D-18 | Célula `Novo` mostra o vendido na janela (`R$ 360,00`), útil porque não há percentual. |
| D-19 | Botões `‹`/`›` ao lado do seletor de mês para andar mês a mês. |
| D-20 | Valores não reais nos wireframes; nenhum número de negócio é inventado na copy. |
| D-21 | **Só produtos ativos:** sem controle "Somente ativos", sem selo "Inativo", sem "Sem cadastro". O escopo vira texto: nota no cabeçalho ("Mostra apenas produtos ativos do catálogo."), na legenda e nos estados vazios. |
| D-22 | Cabeçalho próprio da página (hero no padrão do `inventory`): `h1` "Tendência de Vendas", subtítulo com o período comparado, selo "Vendas até {data}". |
| D-23 | Erros autocontidos: `TND-004` (503, base indisponível) e `TND-005` (429, recarga recente) substituem `ANL-001`/`ANL-002`; `TND-001` a `TND-003` inalterados. |

---

## 13. Critérios de aceite visuais (UX Reviewer, Etapa 4)

- [ ] O item "Tendência de Vendas" aparece na navbar (também no menu hambúrguer mobile) e fica ativo em `/tendencia-vendas`; a página tem `h1` próprio; nenhum import de `features/analytics/**`; a página abre com dados no padrão (mês-base padrão, 3 meses, `desc`, faturamento) sem digitar nada.
- [ ] O mês-base ativo e o que cada coluna compara são legíveis em 3 lugares (subtítulo, seletor com exemplo, cabeçalho de cada coluna), nos dois formatos (tabela e cartão).
- [ ] Toda variação tem triângulo + sinal visíveis e texto `sr-only` com a palavra; `0,0%` sem sinal; `−` tipográfico; contraste ≥ 4,5:1 nos dois sentidos, nos fundos normal, hover e expandido; inspecionar em escala de cinza e com simulação de protanopia: alta e queda continuam distinguíveis.
- [ ] `Novo`, `—` (sem base), `—` (sem movimento), `Base baixa`, `Devoluções superam vendas` aparecem como texto; não há controle nem selo de produto inativo, e a nota "apenas produtos ativos do catálogo" está visível; `Base parcial` e `Sem base` aparecem no cabeçalho da janela e não se repetem em cada linha.
- [ ] A coluna ordenada tem `aria-sort`, seta e sublinhado; clicar alterna `desc`/`asc`; a região viva anuncia a ordenação; `Novo`/`—` ficam depois dos percentuais nos dois sentidos, com o divisor.
- [ ] Chevron de cada linha com `aria-expanded`/`aria-controls`; expandir fornecedor carrega o detalhe sem mover o foco; erro do detalhe aparece dentro do grupo; `TND-003` recolhe com aviso; Esc recolhe.
- [ ] Filhos com variação própria e contribuição em p.p. (valor visível ≥ 1280px e na sub-tabela); `Sem fornecedor` sem estilo de erro.
- [ ] Skeleton com a geometria da tabela/cartões durante a 1ª carga; recargas esmaecem sem pular; nenhum spinner isolado; nenhum vazio durante o carregamento.
- [ ] Vazio por filtro, por atalho, página além do fim, mês-base inválido (`TND-002`) e histórico insuficiente (4 × sem base) mostram o estado com ação; `TND-004`, `TND-005` e falha técnica mostram banner com `Tentar de novo`; nenhum `detail`, stack ou eco de valor.
- [ ] Sem scroll horizontal da página em 320/375/414/768/1024/1280; abaixo de 768px a lista é de cartões com grade 4-up (2×2 ≤ 359px); a tabela só aparece de 768px em diante e sem rolagem lateral.
- [ ] Nenhum hex/rgba literal nem fallback hex nas regras novas; só tokens e constantes SCSS nomeadas; um único token novo (`--navbar-height`); nenhum `outline: none` sem substituto.
- [ ] Componentes só têm `input()`/`output()`; nenhuma conta de variação, ordenação, soma ou média na camada de componentes; formatação em pipes/utilitários; testes de componente com store/serviço mockado cobrindo carregando, vazio e erro.
