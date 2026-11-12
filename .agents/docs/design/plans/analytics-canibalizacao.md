# Design Plan: Canibalização e Substituição de Produtos (F6)

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-canibalizacao.md`  
> **Responsável:** Designer UI/UX (`uiux-expert` / `designer.md`) — Revisado e otimizado na Etapa 2  
> **Rastreabilidade:** Regras `P-128` a `P-138` (`.agents/docs/business_rules/analytics-canibalizacao.md`), Contrato REST (`.agents/docs/api_contracts/analytics-canibalizacao.md`), `ADR-007-canibalizacao.md`, Privacidade `LGPD-CAN-01..08` (`.agents/docs/privacy/analytics-canibalizacao.md`).  
> **Fonte Única de Design Tokens:** `frontend/src/styles.scss` (**Papel & Tinta**) e `frontend/src/app/features/analytics/styles/_analytics-ui.scss`. *(O arquivo `.agents/docs/design/DESIGN_SYSTEM.md` contém placeholders genéricos não customizados e **NÃO** deve ser usado para cores, fontes ou tokens CSS).*

---

## Pre-Emit Critique Stamp (Hallmark v1.1)

- **Identidade & Paleta:** 100% aderente ao sistema **Papel & Tinta** implementado em `frontend/src/styles.scss` (`--bg-canvas: #F5F2EB`, `--bg-surface: #FFFFFF`, `--brand-primary: #1D4528`, `--brand-secondary: #8A4B14`, `--text-primary: #181D19`, `Signika` + `Source Sans 3` + `Overpass Mono`). Zero hexadecimais avulsos, zero gradientes de fundo ou shimmer gradiente ("AI Purple"), zero fallbacks inventados em SCSS.
- **Contraste & Daltons:** `--feedback-positive-bg` (`#185A2E`), `--feedback-warning-bg` (`#7A4607`), `--feedback-critical-bg` (`#8F1B1B`), `--feedback-info-bg` (`#1B4B7A`) e `--feedback-neutral-bg` (`#3B423C`) são **fundos sólidos escuros para texto branco (`--text-on-brand: #FFFFFF`)**, usados exclusivamente via `.tag-*` ou como **cor de texto / borda esquerda de `3px` sobre `--bg-surface`**. Toda classificação combina símbolo (`▲`, `▼`, `↗`, `▬`), sinal tipográfico (`+` / `−`) e rótulo textual (`CANIBALIZACAO`, `COMPLEMENTO`, `MIGRACAO_POSITIVA`, `SEM_EFEITO`).
- **Reuso do Módulo `analytics`:** Reutiliza `AnalyticsShellComponent`, `ANALYTICS_SECTIONS`, `ANALYTICS_ROUTES`, `CodeSearchFormComponent`, `ModeSwitchComponent`, `QueryContextHeaderComponent`, `ErrorBannerComponent`, `ResultStateComponent`, `ListPagerComponent`, `analytics-error.ts`, `pt-br-format` e `_analytics-ui.scss` com extensões tipadas mínimas.
- **Cobertura Funcional Completa:** Cobre os dois endpoints do contrato (`/cannibalization/{sku}` e `/substitution/{sku}`), seleção opcional de `eventDate`, fallback de controle expandido (`isExpandedControl`), fallback de custo 30% (`costFallbackUsed`), degradação graciosa de Elasticidade F5 (`elasticityIntegration.status === "NAO_INTEGRADO"`), tabela acessível para a linha do tempo ($T_0$), drawer com focus trap, cards mobile `< 640px` sem scroll horizontal e os 8 estados interativos.
- **Copy Honesto & Privacidade:** Rótulos em PT-BR direto (sem jargões como "Ruído" ou exclamações excessivas); valores monetários/percentuais de wireframe explicitamente marcados como ilustrativos do contrato; zero `Cod Cliente` ou PII na UI e na URL.

---

## 1. Alinhamento com o Design System Real ("Papel & Tinta")

### 1.1. Tokens Canônicos (`frontend/src/styles.scss` + `_analytics-ui.scss`)

| Categoria | Token Real (`styles.scss` / `_analytics-ui.scss`) | Valor / Regra no Projeto | Onde Aplicar na Feature F6 |
| :--- | :--- | :--- | :--- |
| **Superfícies** | `--bg-canvas` | `#F5F2EB` | Fundo geral da página dentro de `AnalyticsShellComponent` |
| | `--bg-surface` | `#FFFFFF` | Painéis, cards (`@include ui.panel`), tabela, banners e drawer lateral |
| | `--bg-subtle` | `#ECE7DC` | Pills secundárias, controles segmentados inativos, blocos de resumo |
| | `--bg-table-header` | `#F0ECE1` | Cabeçalho `<thead>` das tabelas de afetados e substitutos |
| | `--bg-table-row-hover` | `#F7F5EE` | Hover de linhas em desktop (`@include ui.hover`) |
| | `--bg-table-row-zebra` | `#FAF8F4` | Linhas pares alternadas da tabela |
| | `--bg-overlay` | `rgba(24, 28, 24, 0.55)` | Backdrop do Drawer de detalhe do produto |
| **Tipografia** | `--font-family-headline` | `'Signika', system-ui, sans-serif` | Títulos `<h2>`/`<h3>` e valores hero do `NetImpactCard` |
| | `--font-family-body` | `'Source Sans 3', system-ui, sans-serif` | Labels, descrições, veredito comercial e controles |
| | `--font-family-mono` | `'Overpass Mono', ui-monospace, monospace` | SKUs, valores monetários, deltas, datas, `pValue`, `qValue`, IC 95% (`tabular-nums`) |
| **Hierarquia Texto** | `--text-primary` | `#181D19` | Títulos, métricas principais, texto de corpo |
| | `--text-secondary` | `#434B44` | Metadados, subtítulos e texto obrigatório sobre `--bg-subtle`, `--bg-table-header` e `--brand-primary-subtle` |
| | `--text-muted` | `#666F67` | Legendas e notas secundárias **exclusivamente sobre `--bg-surface` (`#FFFFFF`) ou `--bg-canvas` (`#F5F2EB`)** (para preservar contraste AA $\ge 4{,}5:1$) |
| | `--text-on-brand` | `#FFFFFF` | Texto dentro de botões primários e badges `.tag-*` |
| **Marca & Ação** | `--brand-primary` | `#1D4528` | Botão principal (`%button-primary`), aba ativa, série do produto alvo no gráfico, foco |
| | `--brand-primary-hover` | `#14321C` | Estado `:hover` do botão principal (`@include ui.hover`) |
| | `--brand-primary-active` | `#0E2414` | Estado `:active` do botão principal |
| | `--brand-primary-subtle` | `#E5EFE7` | Destaque de janela ativa/seleção leve (sempre pareado com texto `--text-primary` ou `--brand-primary`) |
| | `--brand-secondary` | `#8A4B14` | Série do Grupo de Controle no gráfico + marcadores de evento $T_0$ (contraste visual e cromático contra `#1D4528`) |
| | `--brand-secondary-subtle` | `#F9EFE5` | Realce suave de marcação $T_0$ sobre fundo claro (texto sempre `--text-primary` ou `--brand-secondary`) |
| **Bordas & Foco** | `--border-subtle` | `#DFD9CC` | Contorno de cards, divisórias de tabela e drawer |
| | `--border-default` | `#CBC3B2` | Contorno de inputs e seletores |
| | `--border-strong` | `#9E9686` | Contorno em hover de inputs e divisória forte pré/pós $T_0$ |
| | `--border-focus` | `#1D4528` | Anel `:focus-visible` global (`2px solid var(--border-focus); outline-offset: 2px`) |
| **Espaço & Raio** | `--space-1` .. `--space-8` | `4px` a `48px` | Ritmo entre painéis (`--space-4`/`--space-5`) e padding interno (`--space-4`/`--space-5`) |
| | `--radius-sm` / `--radius-md` / `--radius-lg` | `5px` / `7px` / `10px` | Badges, inputs/botões, cards e painéis |
| **Breakpoints & Touch** | `$bp-mobile` / `$bp-tablet` / `$touch-target` | `639.98px` / `1023.98px` / `40px` | Cards mobile abaixo de `640px`; controles tocáveis sempre $\ge 40\text{px}$ |

### 1.2. Regra Crítica de Contraste (Correção de Bug de Projeto)

> [!CAUTION]
> Em `frontend/src/styles.scss`, os tokens `--feedback-*-bg` (e seus aliases `--color-success-bg`, `--color-warning-bg`, `--color-danger-bg`) são **fundos escuros sólidos**, jamais tintas claras pastel. Usá-los com texto escuro gera contraste próximo de `1:1` (ilegível).

| Estado Semântico | Token Sólido | Padrão 1: Badge Sólido (`.tag-*`) | Padrão 2: Banner / Card Lateral (`ErrorBannerComponent` pattern) | Padrão 3: Delta Inline em Tabela |
| :--- | :--- | :--- | :--- | :--- |
| **Positivo** (`COMPLEMENTO`, `VALEU_A_PENA`) | `--feedback-positive-bg: #185A2E` | Fundo `--feedback-positive-bg` + texto `--text-on-brand` (`#FFFFFF`) | Fundo `--bg-surface`, `border: 1px solid var(--border-subtle)`, `border-left: 3px solid var(--feedback-positive-bg)`, título `--feedback-positive-bg`, corpo `--text-primary` | Texto `--feedback-positive-bg` sobre `--bg-surface` + prefixo `▲ +` |
| **Alerta** (`ILUSAO_DE_VOLUME`, `isExpandedControl`, `CAN-003`) | `--feedback-warning-bg: #7A4607` | Fundo `--feedback-warning-bg` + texto `--text-on-brand` (`#FFFFFF`) | Fundo `--bg-surface`, `border: 1px solid var(--border-subtle)`, `border-left: 3px solid var(--feedback-warning-bg)`, título `--feedback-warning-bg`, corpo `--text-primary` | Texto `--feedback-warning-bg` sobre `--bg-surface` |
| **Crítico** (`CANIBALIZACAO`, `PREJUIZO_TOTAL`, `CAN-005`/`ANL-001`) | `--feedback-critical-bg: #8F1B1B` | Fundo `--feedback-critical-bg` + texto `--text-on-brand` (`#FFFFFF`) | Fundo `--bg-surface`, `border: 1px solid var(--feedback-critical-bg)`, `border-left: 3px solid var(--feedback-critical-bg)`, título `--feedback-critical-bg`, corpo `--text-primary` | Texto `--feedback-critical-bg` sobre `--bg-surface` + prefixo `▼ −` |
| **Informativo** (`MIGRACAO_POSITIVA`, F5 `NAO_INTEGRADO`) | `--feedback-info-bg: #1B4B7A` | Fundo `--feedback-info-bg` + texto `--text-on-brand` (`#FFFFFF`) | Fundo `--bg-surface`, `border: 1px solid var(--border-subtle)`, `border-left: 3px solid var(--feedback-info-bg)`, título `--feedback-info-bg`, corpo `--text-primary` | Texto `--feedback-info-bg` + prefixo `↗ +` |
| **Neutro** (`SEM_EFEITO`) | `--feedback-neutral-bg: #3B423C` | Fundo `--feedback-neutral-bg` + texto `--text-on-brand` (`#FFFFFF`) | Fundo `--bg-surface`, `border: 1px solid var(--border-subtle)`, corpo `--text-secondary` | Texto `--text-secondary` + prefixo `▬` |

---

## 2. Reuso do Módulo `analytics` e Arquitetura Angular

A feature F6 vive dentro do domínio existente `/analytics` (`AnalyticsShellComponent` já fornece `<h1>Análises de Vendas</h1>` e `<nav aria-label="Seções de análise">` lendo `ANALYTICS_SECTIONS`). Portanto, a página da F6 **não** declara `<h1>`, iniciando sua hierarquia de headings em `<h2>` e `<h3>`.

### 2.1. Inventário de Reuso Obrigatório (Zero Reinvenção)

| Artefato Existente (`frontend/src/app/features/analytics/`) | Como Será Reaproveitado em F6 | Ajuste Mínimo Tipado Permitido na Etapa 3 |
| :--- | :--- | :--- |
| `pages/analytics-shell/` + `analytics.routes.ts` | Adiciona rota filha `canibalizacao` ao `ANALYTICS_ROUTES` e entrada `{ id: 'canibalizacao', label: 'Canibalização', route: '/analytics/canibalizacao' }` em `ANALYTICS_SECTIONS`. | Nenhum visual; mantém navegação consistente com `cross-sell`. |
| `components/code-search-form/` | Campo de busca do SKU alvo com `enableProductSearch="true"`, autocomplete via `AnalyticsService.searchProducts()`, validação `/^[1-9]\d*$/` e botão `"Analisar"`. | Converter o `number` emitido em `(search)` para `string` na camada de página/store (`String(code)`), mantendo o componente intacto. |
| `components/mode-switch/` | Alternância com `role="tablist"` e roving `tabindex` entre **"Impacto de evento (DiD)"** (`/cannibalization/{sku}`) e **"Mapa de substitutos"** (`/substitution/{sku}`). | Generalizar o input `options: ModeOption<T>[]` e `value: T` em `ModeSwitchComponent` mantendo `CrossSellMode` retrocompatível. |
| `components/query-context-header/` | Cabeçalho de contexto da consulta com descrição do produto, estratégia/modo e `Pedidos até {{ meta.dataReferencia | ptDate }}`. | Nenhum (o contrato já fornece `meta.dataReferencia`). |
| `components/error-banner/` | Banner de erro transitório/servidor (`CAN-005`, `ANL-001`) com botão `"Tentar novamente"`. | Adicionar `message = input<string>(DEFAULT_CROSS_SELL_ERROR)` preservando o texto default da F4. |
| `components/result-state/` | Estados de aviso/vazio estruturados (`CAN-001`, `CAN-002`, `CAN-003`, listas vazias), alinhados à esquerda e sem borda tracejada. | Mover `ResultStateView`/`ResultStateAction` de `cross-sell-view.ts` para `analytics.model.ts` (reexportando em `cross-sell-view.ts`). |
| `components/list-pager/` | Paginação cliente 1-based quando `affectedProducts.length > 20` ou `substitutes.length > 20` (oculta automaticamente quando `totalPages <= 1`). | Nenhum. |
| `utils/analytics-error.ts` | Parsing tipado de `{ error: { code, message, fields }, meta }` e roteamento de erro de validação para campo específico via `error.fields[]`. | Estender `ANALYTICS_ERROR_CODES` com `CAN-001`..`CAN-005` e `resolveFieldError` para `CAN-001`/`CAN-004`. |
| `utils/pt-br-format.ts` & `pipes/pt-br-format.pipes.ts` | Reuso direto de `ptDecimal`, `ptPercent` (para `jaccardSimilarity` e `priceExplainedShare` em escala `0..1`), `brl` e `ptDate`. | **Cuidado de escala:** `deltaVolumePct` e `avgPriceChangePct` chegam da API em **pontos percentuais** (ex: `-49.31` = `−49,31%`). Adicionar pipes `signedDecimal`, `signedBrl` e `signedPercent: 'points' | 'ratio'` usando o sinal menos tipográfico `−` (`U+2212`) e evitando multiplicar `deltaVolumePct` por 100. |
| `styles/_analytics-ui.scss` | `@include ui.panel`, `%button-primary`, `%button-secondary`, `@include ui.hover`, `@include ui.reduced-motion`, `@include ui.sr-only`, `@include ui.caption`. | Nenhum. |

### 2.2. Novos Componentes Específicos de F6 (Escopo Fechado)

1. `pages/cannibalization-page/` (`CannibalizationPageComponent` + `CannibalizationStore` provida localmente na página).
2. `services/cannibalization.service.ts` + `models/cannibalization.model.ts`.
3. `components/net-impact-card/` — card executivo de Veredito Comercial (`VALEU_A_PENA` / `ILUSAO_DE_VOLUME` / `PREJUIZO_TOTAL`) + 3 pilares (Volume, Receita, Margem).
4. `components/cannibalization-timeline/` — gráfico SVG responsivo construído 100% sobre `timelineSeries[]` + marcador $T_0$ + alternativa em `<table>` acessível.
5. `components/affected-products-list/` — filtros locais, tabela desktop (`>= 640px`) e cards empilhados mobile (`< 640px`) + colunas condicionais de F5.
6. `components/substitute-detail-drawer/` — drawer com `role="dialog" aria-modal="true"`, focus trap, fechamento por `Esc` e CTA para pivotar SKU.
7. `components/substitution-map-panel/` — visão dedicada do endpoint `GET /api/v1/analytics/substitution/{sku}`.
8. `components/cannibalization-skeleton/` — skeleton solid-pulse (`.skeleton-box` / `.skeleton-line`) + aviso de 4s para cold cache (`SLOW_QUERY_NOTICE_MS = 4000`).

---

## 3. Arquitetura da Informação, Wireframes e Fluxos

Orçamento visual respeitando **padrão F**, máximo de **6 blocos** em viewport normal e **15–20% de área livre em `--bg-canvas` (`#F5F2EB`)**:

### 3.1. Modo A: "Impacto de evento (DiD)" — `GET /api/v1/analytics/cannibalization/{sku}`

```
+-----------------------------------------------------------------------------------+
| [h2] Análise de Canibalização e Substituição                                      |
| Descubra se promoções, mudanças de preço ou lançamentos deslocaram vendas         |
| de outros produtos do portfólio ou ampliaram a margem líquida da categoria.       |
|                                                                                   |
| [ModeSwitch]  ( Impacto de evento (DiD) )  |  ( Mapa de substitutos )             |
+-----------------------------------------------------------------------------------+
| [Painel de Parâmetros - @include ui.panel]                                        |
|  SKU ou nome do produto [CodeSearchFormComponent + autocomplete]  [ Analisar ]    |
|  Tipo de evento: ( Promoção ) ( Preço ) ( Lançamento )                            |
|  Data do evento (opcional): [ YYYY-MM-DD / Mais recente ]  [ Limpar data ]        |
|  Janela simétrica: [ 4 semanas (padrão) v ] (2, 4, 6, 8, 12 semanas)              |
+-----------------------------------------------------------------------------------+

================ BLOCO 1: CONTEXTO & AVISOS CONDICIONAIS =============================
| [QueryContextHeader] EXTRATO DE PROPOLIS VERDE 30ML (SKU 100234)                  |
|   Categoria EXTRATOS • Evento promo em 01/09/2026 • Controle: 14 itens estáveis   |
|   Queda de preço ▼ −22,86% (PRICE_DROP)                Pedidos até 12/11/2026     |
|                                                                                   |
| [Aviso se isExpandedControl === true — borda esquerda --feedback-warning-bg]      |
|   Controle expandido (estratégia FORNECEDOR): categoria sem base suficiente.      |
|                                                                                   |
| [Aviso se costFallbackUsed === true — caption discreto]                           |
|   Margem estimada com fallback padrão de 30% por ausência de custo no cadastro.   |
|                                                                                   |
| [Aviso F5 se elasticityIntegration.status === "NAO_INTEGRADO" — borda --info-bg]  |
|   Decomposição por elasticidade-preço indisponível no momento (módulo F5 ainda    |
|   não integrado). Os deltas DiD exibidos permanecem válidos.                      |
+-----------------------------------------------------------------------------------+

================ BLOCO 2: CARD EXECUTIVO DE IMPACTO LÍQUIDO ==========================
| [.tag-warning] ILUSÃO DE VOLUME                                                   |
| "A promoção aumentou o giro em +365,75 un e o faturamento em +R$ 3.235,63, mas    |
|  destruiu −R$ 1.381,05 de margem líquida ao canibalizar itens de maior valor."    |
|                                                                                   |
| +-----------------------+ +-----------------------+ +---------------------------+ |
| | VOLUME LÍQUIDO        | | RECEITA LÍQUIDA       | | MARGEM LÍQUIDA            | |
| | ▲ +365,75 un          | | ▲ +R$ 3.235,63        | | ▼ −R$ 1.381,05            | |
| | Alvo: +560,00 un      | | Alvo: +R$ 8.232,00    | | Alvo: +R$ 784,00          | |
| | Rede: −194,25 un      | | Rede: −R$ 4.996,37    | | Rede: −R$ 2.165,05        | |
| +-----------------------+ +-----------------------+ +---------------------------+ |
+-----------------------------------------------------------------------------------+
*(Valores numéricos acima reproduzem o exemplo ilustrativo do contrato de API.)*

================ BLOCO 3: LINHA DO TEMPO DO EVENTO (T0) ==============================
| [h3] Produto alvo avançou no pós-evento enquanto grupo de controle manteve base   |
| Janela Pré (04/08–31/08/2026) | Evento T0 (01/09/2026) | Janela Pós (01/09–28/09) |
| Legenda: [───● Produto alvo (un)]  [- -◆ Controle categorial (un)]  [┆ Evento T0] |
|                                                                                   |
|  un alvo |         (Área Pré: --bg-subtle)     ┆ (Área Pós: --brand-primary-subtle)|
|    300   |                                     ┆     ●                             |
|    200   |                       ●             ┆ ●       ●       ●                 |
|    100   |   ●-------●-------●                 ┆                                   |
|          |   ◆ - - - ◆ - - - ◆ - - - ◆         ┆ ◆ - - - ◆ - - - ◆ - - - ◆         |
|          +-------------------------------------+---------------------------------+ |
|            S-4     S-3     S-2     S-1    T0     S+1     S+2     S+3     S+4       |
|                                                                                   |
| [ Botão secundário: Ver dados da linha do tempo em tabela acessível ]             |
+-----------------------------------------------------------------------------------+

================ BLOCO 4: PORTFÓLIO AFETADO (TABELA DESKTOP >= 640px) ================
| [h3] Produtos afetados na categoria                                               |
| Filtros: [Todos (3)] [Canibalização (2)] [Complemento (1)] [Migração (+)]        |
|          [ ] Mostrar itens sem efeito relevante                                   |
|                                                                                   |
| Produto | Classificação | Similaridade | Pré / Pós / Esperado | Δ Volume | Δ Receita | Δ Margem | [F5*] | Ação |
|---------|---------------|--------------|----------------------|----------|-----------|----------|-------|------|
| 100235  | .tag-critical | 0,42         | 310 / 165 / 325,5 un | ▼ −160,5 | −R$ 3.531 | ▼ −R$ 1.524 | (oculta | [Detalhar] |
| Aquoso  | ▼ Canibaliz.  | 38 comp.     | q = 0,0072           | (−49,3%) |           |             |  se NAO |            |
|---------|---------------|--------------|----------------------|----------|-----------|----------| _INT.)|------------|
| 100512  | .tag-positive | 0,31         | 95 / 145 / 99,8 un   | ▲ +45,3  | +R$ 746,6 | ▲ +R$ 307,7 |       | [Detalhar] |
| Spray   | ▲ Complemento | 29 comp.     | q = 0,0192           | (+45,4%) |           |             |       |            |
+-----------------------------------------------------------------------------------+
| [ListPagerComponent — se total > 20 itens]                                        |
+-----------------------------------------------------------------------------------+
```

> **Regras de Exibição por Campo do Contrato (`/cannibalization/{sku}`):**
> - **Classificação (`affectedProducts[].classification`):**
>   - `CANIBALIZACAO` $\rightarrow$ `.tag.tag-critical` (`▼ Canibalização`)
>   - `COMPLEMENTO` $\rightarrow$ `.tag.tag-positive` (`▲ Complemento`)
>   - `MIGRACAO_POSITIVA` $\rightarrow$ `.tag.tag-info` (`↗ Migração positiva`, aplicado em `PRICE_HIKE` conforme `P-134.4`)
>   - `SEM_EFEITO` $\rightarrow$ `.tag.tag-neutral` (`▬ Sem efeito relevante`, visível apenas quando `includeNonSignificant === true`)
> - **Coluna F5 (`elasticityDecomposition`):** A coluna *"Decomposição de preço (F5)"* e o card correspondente no Drawer só são renderizados quando `elasticityIntegration.status` é `"INTEGRADO"` ou `"PARCIAL"`. Quando `"NAO_INTEGRADO"`, a coluna é omitida (sem células vazias `—`) e o aviso contextual explica o motivo no Bloco 1.
> - **Custo fallback (`costFallbackUsed`):** Quando `true` no produto alvo ou em linha afetada, exibe indicador textual `"Margem estimada (30%)"` próximo ao valor de margem, garantindo transparência sobre `P-135.4`.

### 3.2. Versão Mobile (`< 640px`, `$bp-mobile: 639.98px`)

Em telas menores que `640px`, o layout evita qualquer overflow horizontal (`minmax(0, 1fr)`, zero tabela larga com scroll quebrado):
1. Filtros de `eventType`, `eventDate` e `windowWeeks` empilham em coluna única com controles $\ge 44\text{px}$ de altura (`>= $touch-target`).
2. `NetImpactCardComponent` empilha os 3 pilares (Volume, Receita, Margem) verticalmente em `1fr`.
3. `CannibalizationTimelineComponent` reduz rótulos do eixo X para `S-W`, `T0`, `S+W` e disponibiliza por padrão a alternância imediata para a `<table class="timeline-accessible-table">` para leitura confortável no toque.
4. A tabela de afetados é substituída por `<ol class="affected-card-list">` com cards independentes:
   - Linha 1: SKU em `--font-family-mono` + `.tag-*` de classificação.
   - Linha 2: Descrição do produto com `overflow-wrap: anywhere`.
   - Linha 3 (grid 2 colunas `1fr 1fr`): `Δ Volume` e `Δ Margem`, com `Pré / Pós / Esperado` e `qValue` em linha secundária.
   - Linha 4: Botão secundário full-width `"Ver detalhes estatísticos"` ($\ge 44\text{px}$) abrindo o Drawer.

### 3.3. Drawer de Detalhes do Produto Afetado (`SubstituteDetailDrawerComponent`)

Acionado exclusivamente por botão semântico `<button type="button">` na linha/card (nunca por `<tr>` clicável sem affordance):
- **Geometria:** Slide-over à direita (`width: min(460px, 100vw)`) em desktop/tablet; sheet full-width em mobile (`< 640px`), fundo `--bg-surface`, sombra `--shadow-modal`, overlay `--bg-overlay`.
- **Seções internas:**
  1. Cabeçalho: Código SKU + Descrição + Categoria + Classificação (`.tag-*`) + Botão Fechar (`aria-label="Fechar detalhes de [descrição]"`, `min-width: 44px; min-height: 44px`).
  2. Evidência DiD & Confiança: `preVolume`, `postVolume`, `counterfactualVolume`, `deltaVolume`, `deltaVolumePct`, `confidenceInterval` (`[inf, sup]`), `pValue`, `qValue` (FDR), `isSignificant` (`Sim` / `Não`), `jaccardSimilarity` (`ptPercent` ou `ptDecimal:2`), `commonBuyersCount`.
  3. Impacto Financeiro Unitário: `unitPrice` (`brl`), `unitMargin` (`brl`), `deltaRevenue` (`signedBrl`), `deltaMargin` (`signedBrl`), badge discreto se `costFallbackUsed === true`.
  4. Decomposição de Elasticidade (F5): se `elasticityDecomposition !== null`, exibe `crossElasticity`, `priceExplainedDeltaVolume`, `residualDeltaVolume` e `priceExplainedShare`; se `elasticityIntegration.status === "NAO_INTEGRADO"`, exibe nota informativa curta sem parecer falha.
  5. Ação Primária no Rodapé: `"Analisar este SKU como alvo"` — fecha o drawer, atualiza o SKU consultado e aciona nova análise com a mesma janela.

### 3.4. Modo B: "Mapa de substitutos" — `GET /api/v1/analytics/substitution/{sku}`

Permite consultar rapidamente substitutos diretos sem exigir que tenha ocorrido um evento promocional (`P-128`):
- **Filtros:** `minJaccard` (`0,05` a `0,50`, passo `0,05`, default `0,15`) e `limit` (`10`, `20` padrão, `35`, `50`).
- **Card do Alvo:** `targetSku`, `targetDescription`, `targetCategory`, `targetCurrentPrice` (`brl`), `targetStock` (`ptDecimal:0` un).
- **Tabela Desktop / Cards Mobile (`substitutes[]`):** SKU, Descrição, Categoria, Similaridade Jaccard (`jaccardSimilarity` via `ptPercent` / `0..1`), Compradores em comum (`commonBuyersCount`), Preço atual (`currentPrice`), Estoque atual (`currentStock`), e botão `"Analisar impacto DiD"` (muda `ModeSwitch` para `"Impacto de evento (DiD)"` com aquele SKU).

---

## 4. Acessibilidade, Daltons e Gráfico Inclusivo

1. **Segurança para Daltonismo (Red-Green / Deuteranopia):**
   - `--feedback-positive-bg` (`#185A2E`) e `--feedback-critical-bg` (`#8F1B1B`) possuem luminância relativa muito próxima. Portanto, **nenhuma informação depende apenas da cor**:
     - Toda classificação exibe **ícone/glifo + texto** (`▼ Canibalização`, `▲ Complemento`, `↗ Migração positiva`, `▬ Sem efeito relevante`).
     - Todo delta positivo/negativo exibe sinal explícito (`+` / `−` `U+2212`) e unidade (`un`, `R$`, `%`).
   - Na linha do tempo SVG, as duas séries são distinguidas por **3 canais simultâneos**: cor (`--brand-primary` vs `--brand-secondary`), traço (`solid` vs `stroke-dasharray="6 4"`) e marcador de ponto (`<circle>` preenchido vs `<rect>` rotacionado/losango). A linha vertical do evento $T_0$ usa `stroke-dasharray="3 3"` e rótulo textual fixo `T0`.
2. **Gráfico SVG Acessível para Leitores de Tela e Teclado:**
   - O container SVG recebe `role="region"` e `aria-labelledby` descrevendo o título de insight e intervalo de datas.
   - Os pontos semanais do gráfico podem ser percorridos via teclado (`tabindex="0"`, setas/Tab com tooltip visível tanto em `:hover` quanto em `:focus-visible`).
   - Logo abaixo do gráfico, um botão expansível (`aria-expanded`) abre a **`<table>` acessível completa** (`<caption>`, `<th scope="col">`) listando todas as linhas de `timelineSeries[]` (`weekOffset`, `startDate`–`endDate`, `period`, `targetVolume`, `controlTotalVolume`), além de um bloco `.sr-only` garantindo que leitores de tela acessem o resumo quantitativo imediatamente.
3. **Focus Trap & Marcos (`Drawer`):**
   - Ao abrir `SubstituteDetailDrawerComponent`, o foco move-se programaticamente para o título/botão de fechar do drawer.
   - Os containers irmãos recebem `[attr.inert]="drawerOpen() ? '' : null"` (fallback seguro em browsers modernos + `keydown.escape` para fechar).
   - Ao fechar (por `Esc`, botão fechar ou clique no backdrop), o foco retorna obrigatoriamente ao botão exato `"Detalhar"` que abriu o drawer.
4. **Regiões Vivas e Redução de Movimento:**
   - O container principal de resultados possui `[attr.aria-busy]="loading()"` e um elemento `<div class="sr-only" role="status" aria-live="polite">` anunciando mudanças de estado (`"Análise concluída para o SKU..."`, `"Carregando análise..."`, erro ou vazio).
   - `@include ui.reduced-motion` zera animações de abertura de drawer, transições e o pulse do skeleton quando `prefers-reduced-motion: reduce`.

---

## 5. Matriz Completa dos 8 Estados Interativos + Edge Cases

| # | Estado | Gatilho / Condição de API | Comportamento Visual e de Interação Especificado |
| :--- | :--- | :--- | :--- |
| **1** | **Default** | Inicial (sem SKU) ou Resultado `200 OK` | Inicial: painel de busca limpo com sugestão discreta de uso (`CodeSearchFormComponent`). Populado: 4 blocos principais (`QueryContext`, `NetImpactCard`, `Timeline`, `AffectedProducts` ou `SubstitutionMap`) com espaçamento `--bg-canvas` preservado. |
| **2** | **Hover** | Ponteiro desktop (`@include ui.hover`) | Linhas da tabela usam `--bg-table-row-hover`; botões primários usam `--brand-primary-hover`; pontos do gráfico exibem tooltip com `weekOffset`, período, `targetVolume` e `controlTotalVolume`. |
| **3** | **Focus-visible** | Navegação por `Tab` / setas | Todos os controles herdam `outline: 2px solid var(--border-focus); outline-offset: 2px`. `ModeSwitchComponent` usa roving `tabindex` e setas esquerda/direita; pontos SVG do gráfico destacam anel de foco. |
| **4** | **Active** | Seleção / Clique em filtro ou aba | Aba ativa do `ModeSwitch` e chips de filtro (`promo/price/launch`, filtros de classificação) usam destaque sólido `--brand-primary` + `--text-on-brand`; linha selecionada para o drawer recebe fundo `--brand-primary-subtle`. |
| **5** | **Disabled** | `loading === true`, campo inválido ou recurso F5 ausente | Botão `"Analisar"` desabilitado durante requisição em voo ou enquanto SKU é inválido; botão `"Limpar data"` desabilitado quando `eventDate` está vazio; colunas/abas de Elasticidade F5 omitidas quando `elasticityIntegration.status === "NAO_INTEGRADO"`. |
| **6** | **Loading** | Requisição em voo (`loading() === true`) | **Zero spinner solitário.** `CannibalizationSkeletonComponent` replica a estrutura do card executivo, gráfico e 5 linhas de tabela usando `.skeleton-box` e `.skeleton-line` (`@keyframes pulseSolid` de `styles.scss`, sem gradientes). Após `4000ms` (`SLOW_QUERY_NOTICE_MS`), exibe aviso `role="status"`: *"Calculando comparação histórica na base de vendas — a primeira consulta pode levar alguns segundos."* |
| **7** | **Empty** | (a) `200 OK` com `affectedProducts: []`; (b) `422 CAN-002`; (c) `200 OK` `/substitution/{sku}` com `substitutes: []` | **(a)** `ResultStateComponent` (`tone="neutral"`) informando ausência de itens significativos na janela atual, com botão `"Mostrar itens sem efeito relevante"` quando `includeNonSignificant === false`. **(b) `CAN-002`:** `ResultStateComponent` (`tone="warning"`) explicando que não há evento `promo`/`price`/`launch` elegível na data escolhida, com CTA para limpar `eventDate` ou alternar para **"Mapa de substitutos"**. **(c) Substitutos vazios:** `ResultStateComponent` com CTA para reduzir `minJaccard` para `0,05`. |
| **8** | **Error** | `400 CAN-004`, `404 CAN-001`, `422 CAN-003`, `500 CAN-005`, `503 ANL-001` | Ver tabela de roteamento abaixo (`utils/analytics-error.ts`). |

### 5.1. Matriz de Roteamento de Erros de API (`CAN-001..005` + `ANL-001`)

| Código / HTTP | Origem (`error.fields`) | Componente Alvo na UI | Comportamento e Recuperação |
| :--- | :--- | :--- | :--- |
| **`400 CAN-004`** | `["sku"]`, `["eventDate"]`, `["windowWeeks"]`, `["eventType"]`, `["minJaccard"]` ou `["limit"]` | Erro inline no campo correspondente (via `resolveFieldError`) | Exibe mensagem amigável sob o input afetado e borda `--feedback-critical-bg`. Nunca reflete o input bruto na mensagem (`LGPD-CAN-06`). |
| **`404 CAN-001`** | `[]` ou `["sku"]` | `ResultStateComponent` + erro contextual no campo SKU | Informa *"Produto não encontrado no catálogo ativo."* e sugere usar o autocomplete por nome no `CodeSearchFormComponent`. |
| **`422 CAN-002`** | `[]` | `ResultStateComponent` (`tone="warning"`) | Informa ausência de evento elegível (ex: promo/preço/lançamento) e oferece atalho para limpar `eventDate` ou abrir `/substitution/{sku}`. *(Não confunde erro com lista vazia).* |
| **`422 CAN-003`** | `[]` | `ResultStateComponent` (`tone="warning"`) | Informa que o histórico transacional é insuficiente para compor a janela $W$ ou grupo de controle mínimo (distinto do status `200 OK` com `isExpandedControl === true`). Sugere testar janela menor (`2 semanas`). |
| **`500 CAN-005` / `503 ANL-001`** | `[]` | `ErrorBannerComponent` | Banner crítico com borda esquerda `3px` `--feedback-critical-bg`, mensagem sanitizada (zero stacktrace) e botão `"Tentar novamente"`. |

---

## 6. Diretrizes Técnicas Obrigatórias para a Etapa 3 (Angular 18)

1. **Detecção de Mudanças e Reatividade:**
   - Todos os componentes da feature devem declarar `changeDetection: ChangeDetectionStrategy.OnPush`, `standalone: true` e usar exclusivamente Signals (`signal`, `computed`, `input`, `output`).
2. **Controle de Concorrência (`switchMap` + `takeUntilDestroyed`):**
   - `CannibalizationStore` (provido apenas na `CannibalizationPageComponent`, nunca `providedIn: 'root'` para estado de página) deve processar buscas por meio de um `Subject<QueryParams>` conectado a `switchMap` + `takeUntilDestroyed(destroyRef)`, cancelando automaticamente requisições antigas ao alterar rapidamente `sku`, `eventType`, `eventDate`, `windowWeeks`, `includeNonSignificant` ou aba (`ModeSwitch`).
3. **Sincronização Segura de URL (`ActivatedRoute` + `Router`):**
   - Query params canônicos: `?aba=impacto|substitutos&sku=100234&evento=promo&data=2026-09-01&janela=4&todos=0&jaccard=0.15&limite=20`.
   - Toda leitura inicial da URL deve validar/sanitizar estritamente `sku` (`^[1-9]\d*$`), `evento` (`promo|price|launch`), `data` (`YYYY-MM-DD`), `janela` (`[2..12]`), `todos` (`0|1`), `jaccard` (`[0.05..0.50]`) e `limite` (`[1..50]`) antes de disparar o fetch; parâmetros inválidos não executam chamada cega e acionam estado de validação seguro.
   - Atualizações de URL usam `replaceUrl: true` para não poluir o histórico de voltar do navegador.
   - **Proibição de Armazenamento Local:** Zero uso de `localStorage` ou `sessionStorage` para guardar tokens, histórico ou payload de análises.
4. **Tipagem Estrita & Conversão de Unidades:**
   - Zero uso de `any` em serviços, stores, specs e templates (`strict: true`).
   - Os campos `targetProduct.deltaVolumePct`, `targetProduct.avgPriceChangePct` e `affectedProducts[].deltaVolumePct` vêm do backend em escala percentual (`-49.31` = `−49,31%`), enquanto `jaccardSimilarity` (`0.42`) e `elasticityDecomposition.priceExplainedShare` (`0.65`) vêm em fração (`0..1`). A Etapa 3 deve encapsular essa distinção em pipe/utilitário tipado (`SignedPercentPipe` com parâmetro `'points' | 'ratio'`) e validar em testes unitários para impedir o erro `133,33` $\rightarrow$ `13.333%`.
5. **Alvos Mínimos de Testes da Etapa 3 (`tester` TDD First):**
   - Cancelamento de corrida via `switchMap` ao trocar rapidamente SKU / `eventType` / `windowWeeks`.
   - Formatação segura PT-BR (`−` tipográfico, separação entre fração `0..1` e pontos percentuais).
   - Renderização condicional da coluna/card F5 quando `elasticityIntegration.status === "NAO_INTEGRADO"` vs `"INTEGRADO"`.
   - Comportamento de `isExpandedControl === true` (`200 OK` + aviso) vs `422 CAN-003` (`ResultStateComponent`).
   - Acessibilidade do Drawer (`aria-modal`, `Esc` fecha e restaura foco ao botão disparador) e tabela acessível da linha do tempo.

---

## 7. Copywriting e Critérios de Aceite do UX Reviewer (Etapa 4)

### 7.1. Guia de Microcopy (Direto, Técnico e Sem Jargões)

- **Título da Seção (`<h2>`):** `Análise de Canibalização e Substituição`
- **Subtítulo:** `Avalie se uma promoção, alteração de preço ou lançamento gerou ganho líquido real ou transferiu vendas e margem de outros itens do portfólio.`
- **Labels das Abas (`ModeSwitch`):** `Impacto de evento (DiD)` | `Mapa de substitutos`
- **Toggle de Itens Não Significativos:** `Mostrar itens sem efeito relevante` *(substitui o jargão anterior "Ruído")*
- **Vereditos Comerciais (`.tag-*` + ícone):**
  - `VALEU_A_PENA` $\rightarrow$ `.tag-positive` `▲ Ganho líquido comprovado`
  - `ILUSAO_DE_VOLUME` $\rightarrow$ `.tag-warning` `▼ Ilusão de volume`
  - `PREJUIZO_TOTAL` $\rightarrow$ `.tag-critical` `▼ Prejuízo líquido`
- **Aviso de Elasticidade F5 (`NAO_INTEGRADO`):** `Decomposição por elasticidade-preço (Fase F5) ainda não integrada. Os deltas líquidos de volume, receita e margem seguem válidos pelo modelo DiD.`

### 7.2. Checklist de Verificação do `ux_reviewer` (Definition of Done Visual)

- [ ] Todos os estilos de F6 importam exclusivamente tokens de `frontend/src/styles.scss` e mixins de `_analytics-ui.scss` (zero hexadecimais hardcoded e zero `--color-neutral-*` ou `#0D9488`).
- [ ] Badges `.tag-*` possuem texto branco `#FFFFFF` sobre `--feedback-*-bg`; banners/cards de alerta usam `--bg-surface` + borda esquerda `3px` + texto escuro `--feedback-*-bg` (contraste AA $\ge 4{,}5:1$ verificado em todo o DOM).
- [ ] Nenhum uso de `--text-muted` sobre `--bg-subtle`, `--bg-table-header` ou `--brand-primary-subtle`.
- [ ] Reaproveitamento efetivo de `CodeSearchFormComponent`, `ModeSwitchComponent`, `QueryContextHeaderComponent`, `ErrorBannerComponent`, `ResultStateComponent` e `ListPagerComponent`.
- [ ] Linha do tempo SVG distingue séries por cor + padrão de linha + marcador e oferece `<table>` acessível + pontos navegáveis por teclado.
- [ ] Responsividade sem scroll horizontal em `320px`, `375px`, `414px`, `768px` e `1280px`; cards mobile substituem a tabela larga abaixo de `640px`.
- [ ] Todos os alvos interativos (botões, abas, chips, botão fechar do drawer) têm área mínima de `40px` (`>= 44px` em ações primárias móveis).
- [ ] Drawer implementa `role="dialog" aria-modal="true"`, trap de foco com `inert` no fundo e retorno de foco ao botão disparador após `Esc`.
- [ ] Todos os 8 estados interativos validados, incluindo Skeleton solid-pulse (`.skeleton-box`/`.skeleton-line`), aviso de consulta lenta aos 4s, estado `NAO_INTEGRADO` de F5 e roteamento de erros `CAN-001..005` + `ANL-001`.
