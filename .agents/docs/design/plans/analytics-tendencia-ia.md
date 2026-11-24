# Design Plan — Diagnóstico de Motivos da Tendência com IA (F7, painel "Por que?")

<!-- Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4 · macrostructure: long-document (painel de leitura vertical) com ledger numérico (cascata em tabela) antes do bloco de IA -->

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-tendencia-ia.md`
> **Autor:** Designer (`uiux-expert`) — Etapa 2 · 2026-11-24
> **Auditor:** UX Reviewer · **Executor:** Desenvolvedor (fase 7.3)
> **Referências:** `.agents/docs/tasks/ia-tendencia-vendas-motivos.md` (§3.7, §3.9), `.agents/docs/business_rules/analytics-tendencia-ia.md` (P-150..P-187), `GLOSSARY.md` §6, planos `analytics-sales-trend.md` e `analytics-canibalizacao.md`, `.agents/rules/frontend-*.md`
> **Fonte de tokens:** `frontend/src/styles.scss` (Papel & Tinta). O `DESIGN_SYSTEM.md` ainda tem placeholders genéricos (teal, Plus Jakarta) e **não** é usado para cores e fontes, como nas F4/F6 (D-1).
> **Contrato:** `api_contracts/sales-trend-insights.md` **v1.1.0** (§0, §2.1, §4.2, §4.4). Sem "Análise aprofundada" e sem modelo Neon; **a UI não mostra nenhum valor de gasto, dólar, saldo ou percentual de orçamento** (o contrato só expõe `meta.ia.orcamento.nivel`, e a tela nem usa o nível para texto de custo). Campos na §11; onde um nome `camelCase` aqui divergir do contrato, vale o contrato.

---

## 1. Identificação e objetivos de UX

**User Story (US-F7):** como gestor comercial, quero entender por que um produto subiu ou caiu na Tendência de Vendas, com a parte numérica separada por causa e, quando eu pedir, uma análise de IA com fatores externos e fontes, para decidir preço, mix e compra sem adivinhar.

**Perguntas que o painel responde, nesta ordem (números primeiro, IA depois):**
1. Quanto mudou e em que período? (resumo)
2. Foi o mercado todo ou só este produto? (selo de diagnóstico de mercado)
3. Quanto de cada causa os dados internos medem, e quanto sobra sem explicação? (cascata)
4. Para quem foram os clientes (queda) ou de quem vieram (alta)? (detalhe da migração e bloco "Esta alta está tirando vendas de…")
5. Como os produtos semelhantes se saíram? (grupo afim)
6. O que pode explicar o resto, com fonte? (análise com IA, só ao clicar)

**Objetivos de UX**
1. Abrir o painel nunca aciona a IA: a parte numérica aparece sozinha; a IA tem botão próprio e explícito (P-174).
2. Ler a cascata sem estatística: rótulos em português comum ("Época do ano", "Mudança de preço"), valor em R$ (ou un) e em pontos percentuais da variação.
3. Deixar visível o que **não** foi medido ("não avaliado", com o motivo) e o que sobrou sem explicação (resíduo), sem esconder em tooltip.
4. Separar, a olho nu, o que é evidência (número interno ou notícia com fonte e data) do que é hipótese.
5. Mesma informação no mobile de 320 px, em tela cheia, sem rolagem horizontal.

**Arquétipo (Dashboard Designer):** analítico de detalhe (drill-down de uma linha). Blocos no painel: resumo, cascata, migração/impacto, grupo afim, IA (5, abaixo do limite de 6–8). Leitura em coluna única (F vertical): o número herói fica no topo esquerdo do painel.

**Decisões de discovery:** sem brainstorming (escopo aprovado pelo usuário, instrução do Orquestrador). Decisões de design marcadas **D-n** e consolidadas na §12; dúvidas na §13.

---

## 2. Checklist Anti-IA (auditado)

- [x] **Sem "AI Purple", sem gradiente, sem glassmorphism.** O bloco de IA usa as mesmas superfícies sólidas (`--bg-surface`, `--bg-canvas`) do resto; nada de fundo especial, brilho ou borda colorida "mágica". As listras das barras de alta são `<pattern>` SVG (não `linear-gradient`).
- [x] **Sem emoji nem ✨.** O botão é "Gerar análise com IA", sem ícone de estrela, robô ou varinha. A palavra "IA" aparece só onde é informação (botão, aviso, rótulo "Gerada por IA").
- [x] **Sem cards genéricos aninhados:** o painel é um documento com seções separadas por hairline (`--border-subtle`) e títulos `h3`; só o bloco de hipóteses e os avisos têm contorno próprio, por função (separar hipótese de evidência).
- [x] **Sem 3 colunas mecânicas:** a cascata é uma tabela com colunas de larguras desiguais; o resumo é uma linha herói assimétrica (número grande à esquerda, contexto à direita).
- [x] **Font pairing:** `--font-family-headline` (Signika) em títulos e no número herói; `--font-family-body` (Source Sans 3) em texto; `--font-family-mono` (Overpass Mono, `tabular-nums`) em todo número, código de produto e domínio de fonte.
- [x] **Sem título em itálico.** Ênfase por peso e cor.
- [x] **Copy humano, sem buzzword:** proibidos "inteligente", "insights", "poderoso", "seamless", "revolucionar", "mágica". Títulos dizem o achado ("As causas medidas explicam 72% da queda"), com número vindo da API.
- [x] **Sem spinner solitário:** skeleton com a geometria do painel; durante a geração da IA, skeleton do bloco + tempo decorrido (sem percentual inventado).
- [x] **Sem métrica inventada:** todo número vem de `data`/`meta`; os valores dos wireframes são ilustrativos de layout.
- [x] **Status nunca só por cor:** ▲/▼ + sinal `+`/`−` (U+2212) + texto; barras de alta listradas e de queda lisas; confiança em texto.
- [x] **Sem animação decorativa:** só o deslizar do painel (200 ms, desligado em `prefers-reduced-motion`). `animejs-animation` e `image-generator` não são necessários.

---

## 3. Tokens consumidos (todos já existem em `styles.scss`; nenhum token novo)

| Grupo | Tokens | Onde |
| :--- | :--- | :--- |
| Tipografia | `--font-family-headline`, `--font-family-body`, `--font-family-mono` | títulos/número herói; texto; números, códigos, domínios |
| Superfície | `--bg-surface` (painel), `--bg-canvas` (bloco de hipóteses, fundo do aviso de IA), `--bg-subtle` (faixa do resumo, hover de botões secundários), `--bg-muted` (skeleton, barra do resíduo), `--bg-table-header` (cabeçalho das tabelas do painel), `--bg-table-row-hover`, `--bg-overlay` (backdrop) | — |
| Texto | `--text-primary`, `--text-secondary`, `--text-muted` (só sobre `--bg-surface` e `--bg-canvas`), `--text-on-brand` | `--text-muted` nunca sobre `--bg-subtle`, `--bg-table-header` ou `--brand-primary-subtle` (reprova AA, ver plano da Tendência §3) |
| Marca | `--brand-primary`, `--brand-primary-hover`, `--brand-primary-active`, `--brand-primary-subtle` (linha da tabela com painel aberto) | botões, links, seleção |
| Direção e selos | queda `--feedback-critical-bg`; alta `--feedback-positive-bg`; mercado `--feedback-info-bg`; participação `--feedback-warning-bg`; misto/neutro `--feedback-neutral-bg`; bordas `--feedback-*-border` | como cor de texto/ícone/borda sobre superfície clara, ou fundo de `.tag-*` com texto branco (regra do plano F6 §1.2) |
| Borda / foco | `--border-subtle`, `--border-default`, `--border-strong` (contorno tracejado de hipótese e resíduo), `--border-focus` | anel `2px solid var(--border-focus); outline-offset: 2px` |
| Espaço / raio / sombra | `--space-1..--space-8`; `--radius-xs` (botões, selos), `--radius-sm` (avisos), `--radius-md` (painel em desktop, só no canto esquerdo); `--shadow-md` (painel) | — |
| Movimento | `--transition-fast` | slide e hover |
| Camada | — | o painel cobre a viewport inteira (`top: 0`, acima da navbar), como o drawer da F6; não usa `--navbar-height` |

Dimensões sem token viram constantes SCSS no topo de `styles/_insight-ui.scss` (novo, `@use` de `../styles/trend-ui`): `$panel-width-wide: 720px`, `$panel-width-medium: 640px`, `$bp-cards: 767.98px` (reuso do valor da Tendência), `$touch-target: 40px`, `$touch-target-mobile: 44px`, `$bar-height: 14px`, `$waterfall-label-col: 34%`, `$slow-notice-ms: 4000`, `$ai-slow-notice-s: 30`.

### 3.1 Contraste (razões do plano da Tendência §3, mesmos tokens)

| Par | Razão | Uso |
| :--- | :--- | :--- |
| `--feedback-critical-bg` / `--feedback-positive-bg` / `--feedback-info-bg` / `--feedback-warning-bg` sobre `--bg-surface` | 9,0 / 8,3 / 9,0 / 7,9 | valores e selos de contorno |
| `--text-on-brand` sobre qualquer `--feedback-*-bg` (`.tag-*`) | ≥ 9:1 | selo de diagnóstico de mercado |
| `--text-secondary` sobre `--bg-subtle` / `--bg-table-header` | ≥ 7,6 | faixa do resumo, cabeçalhos |
| `--text-muted` sobre `--bg-canvas` | ≥ 4,5 (AA) | metadados do bloco de hipóteses |
| Barras (componente não textual) sobre `--bg-surface` | ≥ 3:1 (WCAG 1.4.11) | todas as cores de barra são escuras; o resíduo (`--bg-muted`) tem contorno `--border-strong` para chegar a 3:1 |

> **Daltonismo (D-6):** verde e vermelho dos tokens têm luminância parecida e se confundem em deuteranopia/protanopia. Na cascata, a diferença entre alta e queda é dada por **quatro** canais: direção da barra (para a direita = soma, para a esquerda = tira), textura (alta listrada em diagonal, queda lisa), glifo ▲/▼ e sinal no valor. Funciona também em impressão em tons de cinza.

---

## 4. Arquitetura de componentes

Código novo em `frontend/src/app/features/sales-trend/insights/` (a feature mora na página da Tendência; D-2). Um componente inteligente (a página existente, que já é o orquestrador) + um store; todo o resto é burro (`input()`/`output()`), `standalone`, `OnPush`. Nenhuma regra de negócio na tela: parcelas, cortes, confiança, diagnóstico, rótulos de motivo vêm da API; a tela só mapeia enum → texto e formata.

### 4.1 Reaproveitar (sem duplicar)

| Existente | Uso no F7 |
| :--- | :--- |
| `sales-trend/components/segmented-control` | Seletor de janela dentro do painel (`1 mês` · `3 meses` · `6 meses` · `12 meses`) |
| `sales-trend/components/trend-cell` (`variant="card"`) | Variação de cada afim no grupo afim, **se** o contrato devolver a célula do afim no mesmo formato `TrendCell` (P-154.1; Q-D3) |
| `sales-trend/components/inline-notice` | Avisos `TIA-005`, "Fornecedor do produto não informado", "Base pequena…", "Produto novo ou retomado…", aviso fixo de IA (`tone="info"`, `dismissible=false`) |
| `sales-trend/components/trend-error-banner` | Erro da parte numérica (com "Tentar de novo") |
| `sales-trend/components/trend-empty-state` | "Sem variação relevante", grupo afim vazio |
| `sales-trend/pipes/trend-format.pipes` (`trendPercent`, `trendPoints`, `trendValue`, `trendSpan`, `ptBrDate`) e `services/viewport.service` (`isCompact`) | Formatação de % / p.p. / valores por métrica / períodos; troca painel lateral × tela cheia |
| `analytics/pipes/pt-br-format.pipes` (`brl`, `signedBrl`, `signedPercent`, `ptDecimal`) | Valores em R$ com sinal na cascata, migração e impacto (a Tendência não tem `signedBrl`) |
| `analytics/.../cannibalization.store.ts` → `MECHANISM_VISUAL_META` | Selo do mecanismo de preço (`PRECO_MENOR_DESTROI_MARGEM` etc.) nos pares de migração e no impacto. **Extrair** para `analytics/utils/cannibalization-mechanism.ts` e importar dos dois lados (Q-D5) |
| `price-equilibrium-drawer` (padrão) | Mesmo padrão de diálogo: `FOCUSABLE_SELECTOR`, `trapFocus`, travar rolagem do `body`, Esc, backdrop, devolução de foco. **Extrair** para `shared/a11y/dialog-focus.ts` (funções puras + `lockBodyScroll`) e usar nos dois drawers, em vez de copiar (Q-D4) |
| `analytics/utils/analytics-error.ts` (padrão `toCannibalizationApiError`) | Modelo para `insights/utils/insight-error.ts` (`TIA-001..005`, `ANL-001`, `NETWORK`, `SERVER`, `motivo`) |
| Classes globais `.tag-*`, `.skeleton-line`, `.skeleton-box` (`pulseSolid`, sem gradiente), `.sr-only` | Selos, skeletons, textos para leitor de tela |
| Página de Canibalização (`/analytics/canibalizacao?periodo=&busca=`) | Destino dos links "Ver no relatório de Canibalização" |

**Não entra:** `searchable-combobox` (o painel não tem filtro por lista; os afins são no máximo 25 e cabem numa lista com "Mostrar todos").

### 4.2 Criar

| Componente / arquivo | Tipo | Entradas → saídas |
| :--- | :--- | :--- |
| `TrendInsightsService` | HTTP | `getProductInsight(sku, params)` (GET), `generate(sku, params, {force})` (POST; sem `deep`). Desembrulha `data`/`meta`; converte erro em `InsightApiError` |
| `TrendInsightsStore` (provida **na página** `SalesTrendPageComponent`, não no painel) | Estado | `openKey`, máquina da parte numérica `idle → loading → success \| error`, máquina da IA (§7), `Map<chave, GenerationState>` para que fechar o painel não cancele uma geração (D-9). `switchMap` no GET; o POST **não** é cancelado por troca de janela |
| `TrendInsightPanelComponent` | Burro (diálogo) | `view: InsightPanelView \| null`, `windowOptions`, `returnFocusTo` → `(close)`, `(windowChange)`, `(retry)`, `(generate)`, `(confirmRegenerate)`, `(cancelConfirm)` |
| `InsightSummaryComponent` | Burro | `summary: InsightSummaryView` (número herói, período, selo, frase de mercado, atalho para a IA) |
| `MarketDiagnosisSealComponent` | Burro | `diagnosis: MarketDiagnosisView` |
| `AttributionWaterfallComponent` | Burro | `waterfall: WaterfallView` → `(toggleParcel: tipo)` (abre a lista de produtos da parcela de migração) |
| `InsightSignalsComponent` | Burro | `signals: SignalView[]`, `mode: 'quantitativo' \| 'qualitativo'` |
| `AffineGroupComponent` | Burro | `group: AffineGroupView` → `(showAll)` |
| `ImpactedProductsComponent` | Burro | `impact: ImpactView` (só altas e `NOVO`) |
| `AiDiagnosisBlockComponent` | Burro | `state: AiBlockView` (§7) → `(generate)`, `(requestRegenerate)`, `(confirm)`, `(cancel)`, `(retry)` |
| `AiFactorItemComponent`, `SourceLinkComponent` | Burros | `factor: AiFactorView`; `source: SourceView` |
| `TrendInsightSkeletonComponent` | Burro | `part: 'panel' \| 'ai'` |
| `insights/utils/insight-view.ts` | Funções puras | `buildSummaryView`, `buildWaterfallView` (posição/largura das barras em % do eixo a partir dos valores da API), `buildAffineGroupView`, `buildAiBlockView`, `liveMessage` |
| `insights/utils/insight-copy.ts` | Constantes | rótulos de `tipo`, `status`, `motivoNaoAvaliado`, `diagnosticoMercado`, `confianca`, `motivo` de hipótese, `TIA-004.motivo` (§10) |
| `insights/utils/insight-error.ts` | Funções puras | `toInsightApiError`, `resolveInsightMessage` |

Mudanças em componentes existentes da Tendência: `TrendRowComponent` e `TrendCardListComponent` ganham o botão "Por que?" e a saída `(explain: {key, triggerEl})`; `TrendTableComponent`/`TrendSupplierGroupComponent` repassam; `SalesTrendPageComponent` liga store ↔ painel, aplica `inert` e a região viva.

---

## 5. Ponto de entrada "Por que?"

### 5.1 Tabela (≥ 768 px)

Sem coluna nova (a tabela de 6 colunas já usa toda a largura em 768 px). O botão entra na **linha 2 da célula do produto**, alinhado à direita, na mesma linha do fornecedor:

```
 [›]  ÓLEO DE COCO 500 ML                               ▲ +200,0%   ▲ +180,5%   ...
      1007 · LABORATÓRIO BETA              [Por que?]
```

- `<button type="button" class="btn-explain" aria-haspopup="dialog">`; texto visível `Por que?`; `aria-label` com o contexto da coluna ordenada: `Por que ÓLEO DE COCO 500 ML subiu em 3 meses? Abrir diagnóstico` (`caiu` na queda; `mudou` em `NOVO`/`SEM_BASE`/`SEM_MOVIMENTO`).
- Visual: botão-texto `--brand-primary`, 0.78rem peso 600, borda `1px solid var(--border-default)`, `--radius-xs`, fundo `--bg-surface`, padding `0 var(--space-2)`, `min-height: 32px` (alvo ≥ 24 px, WCAG 2.5.8; D-4). Sem ícone.
- Hover (`@media (hover: hover)`): borda `--brand-primary`, fundo `--brand-primary-subtle`. Active: fundo `--bg-muted`. Focus-visible: anel global.
- **Linha com painel aberto:** fundo `--brand-primary-subtle` + `box-shadow: inset 3px 0 0 var(--brand-primary)` (mesmo vocabulário da F6) e o botão em `aria-expanded` não se aplica (é diálogo); usar só a classe `.is-explaining`.
- **Onde aparece:** linhas de produto na visão por produto e linhas filhas (produtos) na visão por fornecedor. **Não** aparece na linha de fornecedor até a fase 7.4 (D-3); nem na linha "Todos os produtos".
- **Janela inicial do painel:** a coluna ordenada da tabela (`sortWindow`). Métrica, Mês-Base e `comparisonMode` são os da página (o painel mostra, não altera).

### 5.2 Cartões (< 768 px)

No rodapé de cada cartão de produto, ao lado de "Ver detalhes", um botão secundário de largura total em 320 px (ou meia largura a partir de 375 px, grade `repeat(2, minmax(0, 1fr))`), `min-height: 44px`, texto `Por que?`, mesmo `aria-label`.

### 5.3 URL

`?porque={sku}` entra na URL com `replaceUrl: true` ao abrir e sai ao fechar, para o link poder ser compartilhado (D-8). Na leitura inicial: só dígitos; se o SKU não estiver na página atual, o painel abre mesmo assim (o GET resolve; `TIA-002` mostra o erro). A janela do painel não vai para a URL (segue `sortWindow`).

---

## 6. Painel do diagnóstico

### 6.1 Geometria e acessibilidade do diálogo

| Largura | Forma |
| :--- | :--- |
| ≥ 1024 px | Painel lateral à direita, `width: min(720px, 100vw)`, altura total, `--radius-md` só nos cantos esquerdos, `--shadow-md`, backdrop `--bg-overlay` |
| 768–1023 px | Painel lateral `width: min(640px, 100vw)`; a coluna "Confiança" da cascata dobra para baixo do rótulo |
| < 768 px | Tela cheia (`inset: 0`), sem backdrop visível, sem raio |

- `<aside role="dialog" aria-modal="true" aria-labelledby="{titleId}" aria-describedby="{summaryId}">`. Cabeçalho e rodapé `position: sticky`; corpo com rolagem própria (`overscroll-behavior: contain`); `body` travado.
- **Ao abrir:** `inert` no `<main>` da página e na navbar; foco vai para o título `h2` (`tabindex="-1"`), não para o "Fechar", porque o conteúdo é longo e o leitor de tela precisa do contexto (D-5). A região viva da página anuncia `Diagnóstico de {descricao} aberto.`
- **Foco preso:** `Tab`/`Shift+Tab` circulam dentro do painel (função extraída do drawer da F6).
- **Fechar:** botão "Fechar" no cabeçalho (`44×44`, `aria-label="Fechar diagnóstico"`, glifo `×` `aria-hidden`), `Esc` e clique no backdrop. Exceção: com a confirmação de "Gerar de novo" aberta, `Esc` cancela a confirmação e não fecha o painel.
- **Devolução de foco:** ao botão "Por que?" que abriu. Se a linha não existir mais (lista recarregada, outra página), foco no `h2` da tabela (`tabindex="-1"`).
- **Movimento:** `transform: translateX(100%) → 0` em 200 ms (`--transition-fast`); em `prefers-reduced-motion: reduce`, sem transição.
- Trocar a janela no seletor dispara novo GET; a rolagem volta ao topo e o foco fica no seletor.

### 6.2 Cabeçalho (sticky)

```
 1007 · LABORATÓRIO BETA                                              [ × ]
 Por que ÓLEO DE COCO 500 ML caiu?                                     (h2)
 Faturamento líquido · Mês-base out/2026 · ago–out/26 vs mai–jul/26
 JANELA  [1 mês][● 3 meses][6 meses][12 meses]
```

- Linha 1: código (`mono` 0.75rem `--text-secondary`) + fornecedor; se `sameSupplier` indisponível por falta de fornecedor, aparece o aviso da §6.4.
- `h2` (o `h1` é o da página): `--font-family-headline` 1.25rem 700, até 3 linhas, `overflow-wrap: anywhere`. Texto: `Por que {descricao} caiu?` / `subiu?` / `mudou?` (este para `NOVO`, `SEM_BASE`, `SEM_MOVIMENTO`).
- Linha de contexto 0.8rem `--text-secondary`: métrica (`Faturamento líquido` / `Quantidade líquida`), Mês-Base e períodos de `meta` (mesmo `trendSpan` da tabela); se `comparisonMode = average`: `ago–out/26 vs média de mai–jul/26`.
- Seletor de janela: `SegmentedControlComponent`, `aria-label="Janela do diagnóstico"`; desabilitado durante o GET.

### 6.3 Corpo — ordem das seções

1. **Resumo** (`InsightSummaryComponent`) — faixa `--bg-subtle`, padding `--space-4`:

```
 −18,4%                         de R$ 14.200,00 para R$ 11.587,20
 em 3 meses                     (−R$ 2.612,80)
 [▼ Perdeu participação]  Os 7 produtos semelhantes cresceram +2,1%; a fatia deste
                          produto no grupo caiu de 31,0% para 25,7% (−5,3 p.p.).
 Análise com IA: ainda não gerada · Ir para a análise ↓
```

   - Número herói: `variacaoPct` em `--font-family-headline` 2rem 700, cor da direção, com ▲/▼ e sinal. Abaixo, `em {X}`.
   - À direita: `de {baseAjustada} para {atual}` e `({deltaObservado} com sinal)` em `mono`. Com Base Parcial: nota 0.75rem `Período anterior ajustado para a mesma quantidade de dias.`
   - Selo + frase de mercado: §6.5.
   - Linha de atalho para a IA (link âncora para o `h3` do bloco de IA, que recebe foco): `Análise com IA: ainda não gerada` / `gerada em {dd/MM/yyyy}` / `em andamento` / `indisponível`. Resolve a distância do bloco no fim do painel, principalmente no mobile.

2. **Cascata** (`AttributionWaterfallComponent`, §6.6) + **sinais sem valor** (`InsightSignalsComponent`, §6.7).
3. **Migração e impacto** — na queda, dentro da cascata (linhas de migração expansíveis, §6.6); na alta e em `NOVO`, a seção "Esta alta está tirando vendas de…" (§6.9).
4. **Grupo afim** (`AffineGroupComponent`, §6.8).
5. **Análise com IA** (`AiDiagnosisBlockComponent`, §7).

Seções separadas por `border-top: 1px solid var(--border-subtle)` e `padding-block: var(--space-5)`; títulos `h3` `--font-family-headline` 1rem 700 escritos como achado (§10).

**Rodapé (sticky):** à esquerda, `Ver no relatório de Canibalização` (link, §6.8); à direita, botão secundário `Fechar`. Altura 56 px; no mobile os dois ocupam meia largura cada.

### 6.4 Avisos no topo do corpo (`InlineNoticeComponent`, acima do resumo)

| Condição | Tom | Texto |
| :--- | :--- | :--- |
| `meta.avisos` contém `TIA-005` | warning | `Índice de produtos afins em atualização: canibalização e grupo afim não avaliados.` Ação: `Atualizar painel` (refaz o GET) |
| Fornecedor de `A` ausente (P-154.2) | info | `Fornecedor do produto não informado: todos os semelhantes aparecem como "outro fornecedor".` |
| Modo `QUALITATIVO` por Base Baixa ou `SEM_BASE` (P-170) | info | `Base pequena: a análise mostra só os sinais, sem estimar valores.` |
| Estado `NOVO` (P-170) | info | `Produto novo ou retomado nesta janela: não há período anterior para comparar.` |
| `SEM_BUSCA_EXTERNA` em `meta.avisos` do POST | info (dentro do bloco de IA) | `Esta análise não consultou notícias externas; os fatores abaixo vêm só dos dados internos.` |
| `IA_FALHOU` em `meta.avisos` do POST | info (dentro do bloco de IA) | `Não foi possível gerar a análise com IA agora; mostramos o resumo automático.` |

> **Removido (v1.1.0):** o aviso `DIAGNOSTICO_DESATUALIZADO` e o `ESCALONAMENTO_NEGADO_POR_ORCAMENTO` não existem mais; a tela não os trata. Diagnóstico salvo antigo é indicado só pela data no rodapé e, se `meta.ia.diagnosticoVencido`, por `Gerada há {N} dias` (texto neutro, sem alerta).

### 6.5 Selo de diagnóstico de mercado (`MarketDiagnosisSealComponent`)

`.tag` global (fundo escuro sólido + texto branco) com glifo e rótulo; ao lado, a frase explicativa interpolada.

| `diagnosticoMercado` | Selo (`.tag-*`, glifo) | Frase (valores de `data.grupoAfim`) |
| :--- | :--- | :--- |
| `MERCADO_EM_QUEDA` | `.tag-info` `▼ Mercado em queda` | `Os {n} produtos semelhantes caíram {vMercado} no mesmo período. A causa provável é de mercado (época, clima, economia, regras).` |
| `MERCADO_EM_ALTA` | `.tag-info` `▲ Mercado em alta` | `Os {n} produtos semelhantes subiram {vMercado}. O produto acompanhou o mercado.` |
| `PERDA_DE_PARTICIPACAO` | `.tag-warning` `▼ Perdeu participação` | `Os {n} produtos semelhantes {cresceram\|ficaram estáveis} ({vMercado}); a fatia deste produto no grupo caiu de {sPre} para {sCur} ({deltaSPp}).` |
| `GANHO_DE_PARTICIPACAO` | `.tag-warning` `▲ Ganhou participação` | `A fatia deste produto no grupo subiu de {sPre} para {sCur} ({deltaSPp}), acima do que os semelhantes variaram ({vMercado}).` |
| `MISTO` | `.tag-neutral` `◆ Mercado e concorrência` | `O mercado variou {vMercado} e a fatia do produto mudou {deltaSPp}: as duas coisas pesaram.` |
| `SEM_GRUPO_AFIM` | contorno `--border-default`, texto `--text-secondary`, `— Sem comparação` | `Não há produtos semelhantes o bastante para comparar com o mercado.` |
| `NAO_AVALIADO` | idem, `— Não avaliado` | `Comparação com o mercado não avaliada nesta consulta.` |

Cores escolhidas por **tipo de causa**, não por direção (direção = glifo e sinal): azul = mercado (externo), âmbar escuro = concorrência (interno), neutro = misto (D-7). `ficaram estáveis` quando `|vMercado| < MIN_EXPLAINABLE_VARIATION_PCT` vindo de `meta.parametros` (a tela não decide o limiar; se o contrato não trouxer, usar `cresceram`/`caíram` pelo sinal).

### 6.6 Cascata acessível (`AttributionWaterfallComponent`)

**Decisão D-6:** a cascata é uma **`<table>` visível** com uma coluna de barra (`aria-hidden="true"`). A própria tabela é a versão para leitor de tela; não há tabela oculta duplicada nem gráfico em `<canvas>`.

**Título (`h3`, achado):** `As causas medidas explicam {coberturaExplicacaoPct} da queda` (ou `da alta`). Se `coberturaExplicacaoPct < 50`: `A maior parte da queda ({100 − cobertura}) não tem causa nos dados internos` — o complemento vem pronto da API ou é `100 − x` em `insight-view.ts` (formatação, não regra).
**Subtítulo:** `Valores em {R$ \| unidades} na escala do período atual. p.p. = pontos percentuais da variação de {variacaoPct}.`
`<caption class="sr-only">Decomposição da variação de {variacaoPct} de {descricao} em {X}, por causa</caption>`

**Colunas**

| Coluna | Largura (≥ 1024) | Conteúdo |
| :--- | :--- | :--- |
| Causa (`th scope="row"`) | 34% | rótulo (§10.1) + linha 2 com status/motivo/observação em 0.75rem |
| Barra (`aria-hidden`) | `minmax(0, 1fr)` | SVG `viewBox="0 0 100 14" preserveAspectRatio="none"` com `<rect>` posicionado por `buildWaterfallView` |
| Valor | 124 px, direita, `mono` | `−R$ 1.420,00` (em `quantity`: `−96 un` e, abaixo, `−R$ 1.420,00` de `valorReceita`) |
| p.p. | 72 px, direita, `mono` | `−10,0 p.p.` (campo da API, Q-D1) |
| Confiança | 88 px | `Alta` / `Média` / `Baixa`, texto 0.75rem + 3 marcas `●●○` `aria-hidden` |

**Linhas, na ordem de P-157 (fixa, mesmo quando sem efeito, para o usuário aprender o layout):**

```
 Causa                                   Barra (eixo 0 → variação)        Valor          p.p.    Confiança
 Época do ano                            ░░░░▏                           +R$ 780,00     +5,5    Média
   Esta época costuma vender mais; compensa parte da queda.
 Mudança de preço                             ████▏                      −R$ 710,00     −5,0    Alta
   Preço médio praticado subiu 8,2%.
 Lançamento semelhante                   —                               Sem efeito
   Nenhum lançamento semelhante com clientes deste produto.
 Migração de clientes · mesmo fornecedor      ██▏                        −R$ 426,00     −3,0    Média  [›]
 Migração de clientes · outro fornecedor        ███████▏                 −R$ 1.704,00  −12,0    Alta   [›]
   Limitada ao total observado.
 Clientes que pararam de comprar         —                               Não avaliado
   Só dá para medir em meses recentes.
 Sem explicação nos dados internos              ┆┆┆┆┆▏                   −R$ 552,80     −3,9      —
 ───────────────────────────────────────────────────────────────────────────────────────────────────
 Variação total                          ███████████████████▏            −R$ 2.612,80  −18,4
```

- **Eixo:** de 0 (sem mudança) até `deltaObservado`, ampliado para caber compensatórias (`[min(0, mínimo acumulado), max(0, máximo acumulado)]`). Linha vertical do zero em `--border-strong` 1px. Cada barra vai do acumulado anterior ao novo acumulado (ponte). Conectores finos `--border-subtle` entre o fim de uma barra e o início da próxima.
- **Codificação:** queda `--feedback-critical-bg` lisa; alta `--feedback-positive-bg` com listras diagonais (`<pattern>` de 4 px, traço `--bg-surface` 1,5 px); resíduo `--bg-muted` com contorno tracejado `--border-strong`; total contorno `--text-primary` 1,5 px com preenchimento da direção. Glifo ▲/▼ no valor.
- **Status `SEM_EFEITO`:** sem barra (célula com `—` `aria-hidden` + `sr-only` "sem barra"), valor `Sem efeito` em `--text-secondary`, motivo na linha 2.
- **Status `NAO_AVALIADO`:** sem barra, valor `Não avaliado` em `--text-secondary` com microselo de contorno `--border-default`; motivo (§10.2) na linha 2. Nunca mostrar 0.
- **`cortada = true`:** linha 2 `Limitada ao total observado.` + marcador `*` no valor; `title` não é o único lugar do texto.
- **`observacao = PRECO_INFLUENCIADO_POR_PROMOCAO`:** linha 2 `Inclui descontos de promoção.`
- **Linhas de migração** (`PRODUTO_NOVO`, `CANIBALIZACAO_*`) com pares: botão disclosure `[›]` (40×40, `aria-expanded`, `aria-label="Ver os {n} produtos para onde foram clientes"`) abre uma sub-lista dentro de `<tr><td colspan>`:

```
     Para onde foram os clientes (outro fornecedor)
     4012 · PRÓPOLIS VERDE 30 ML · APIS BRASIL   semelhança 82%   −R$ 1.180,00   9 clientes   [▲ Reajustar canibalizador]
     4020 · EXTRATO DE PRÓPOLIS 20 ML · MELCO    semelhança 61%   −R$ 524,00     4 clientes   [↗ Migração por valor]
     Ver equilíbrio de preço no relatório de Canibalização →
```
  Contagem de clientes é agregada (`netClients`/`clientesMigrados`), nunca identificação (LGPD); valor `"<3"` aparece como `menos de 3 clientes` (§7.3). Selo do mecanismo com `MECHANISM_VISUAL_META`. Na alta, o título da sub-lista é `De onde vieram os clientes`.
- **Alta:** rótulos invertidos (§10.1); `Lançamento semelhante` e `Clientes que pararam de comprar` ficam `Sem efeito` com motivo `Não se aplica a altas.`
- **Modo `QUALITATIVO`:** a tabela não aparece; em seu lugar a lista de sinais (§6.7) com presença sim/não/não avaliado (P-170), título `Sinais encontrados (sem estimar valores)`.
- **Mobile (< 768 px):** cada linha vira um bloco em grade de 2 colunas: linha 1 rótulo | valor; linha 2 barra em largura total; linha 3 `p.p. · Confiança` e o motivo. A semântica continua `<table>` com `display: grid` nas linhas e cabeçalhos `sr-only` (os `th` de coluna seguem presentes para o leitor de tela).

### 6.7 Sinais sem valor (`InsightSignalsComponent`)

Lista `<ul>` abaixo da cascata, título `h4` `Outros sinais no período` (0.85rem 700). Cada item: glifo de estado (`●` presente, `○` ausente, `–` não avaliado; `aria-hidden`) + texto + evidência:

| Sinal | Texto (interpolado) |
| :--- | :--- |
| `RUPTURA` ativo | `Estoque atual: {estoqueAtual} un. Pode ter faltado produto.` + se houver: `A migração pode ter sido forçada por falta de estoque.` |
| `PROMOCAO` negativo / positivo | `Teve promoção no período anterior e não teve agora.` / `Está em promoção no período atual.` ; afins: `Semelhantes em promoção no período: {lista de códigos}.` |
| `REGIONAL` | `{pct} da {queda\|alta} ficou em {UF}.` Não soma na cascata: rodapé `Mostra onde a variação aconteceu; não é uma causa à parte.` |
| `PERDA_PARTICIPACAO_SEM_MIGRACAO` | `Semelhantes cresceram sem levar clientes deste produto (cerca de {valor}).` + códigos dos afins |
| Lançamento sem migração (P-160.2) | `Houve lançamento semelhante ({codigo}), sem migração comprovada de clientes.` |

Sem sinais: `Nenhum outro sinal encontrado (estoque, promoção, região).`

### 6.8 Grupo afim (`AffineGroupComponent`)

**Título (`h3`, achado):** `{n} produtos semelhantes · {m} ganharam clientes deste` (alta: `{m} perderam clientes para este`).
**Resumo em duas células** (grade `repeat(2, minmax(0, 1fr))`, empilha em < 375 px):

```
 MESMO FORNECEDOR (3)            OUTRO FORNECEDOR (4)
 ▲ +6,4%                         ▼ −1,2%
```
**Lista** (tabela ≥ 768 px; lista de itens < 768 px), ordenada por semelhança (vem da API):

| Coluna | Conteúdo |
| :--- | :--- |
| Produto | `código · descrição` (2 linhas, `overflow-wrap: anywhere`) |
| Fornecedor | nome + microselo de contorno `Mesmo fornecedor` (`--brand-primary`) ou `Outro fornecedor` (`--text-secondary`) — texto, não cor |
| Semelhança | `82%` (`affinityScore × 100`, inteiro) com rótulo de coluna "Semelhança" e ajuda em `<details>` `Como a semelhança é calculada` (texto curto do índice: nome, categoria e função do produto; só entram produtos com 50% ou mais) |
| Variação | `TrendCellComponent` `variant="card"` (Q-D3) |
| Ganhou clientes deste? | `Sim · 9 clientes · R$ 1.180,00` (`--text-primary`) ou `Não` (`--text-secondary`) |

- Mostra 8 linhas; botão `Mostrar todos os {n}` (disclosure, `aria-expanded`). No máximo 25 (P-154).
- **Links:** no fim da seção, `Ver estes produtos no relatório de Canibalização →` para `/analytics/canibalizacao?periodo=90&busca={sku}` (navegação interna; fecha o painel). Em cada afim com `ganhouClientesDeA`, link `Ver equilíbrio de preço` para a mesma rota com o SKU do afim e o parâmetro que abre o drawer (Q-D2). Nota 0.75rem honesta logo abaixo: `O relatório de Canibalização usa os últimos 90 dias; os números podem diferir desta janela.`
- **Vazio (`SEM_GRUPO_AFIM`):** `TrendEmptyStateComponent` com ícone de dois quadrados sobrepostos (SVG 24 px), título `Sem produtos semelhantes para comparar`, texto `Nenhum produto ativo tem semelhança de {limiar} ou mais com este. A comparação com o mercado não foi feita.`, ação `Como a semelhança é calculada` (abre o `<details>`).
- **Não avaliado (`TIA-005`):** a seção mostra só o título `Produtos semelhantes` e a linha `Lista de produtos semelhantes em atualização. Tente de novo em alguns minutos.` com botão `Atualizar painel`.

### 6.9 "Esta alta está tirando vendas de…" (`ImpactedProductsComponent`; altas e `NOVO`)

Dado do motor (P-171), disponível sem IA (aparece já ao abrir o painel; Q-D6).

```
 Esta alta está tirando vendas de 3 produtos                                         (h3)
 Do mesmo fornecedor (troca interna)   R$ 2.140,00      De concorrentes   R$ 3.860,00
 ┌ borda esq. 3px --feedback-warning-bg ───────────────────────────────────────────────┐
 │ [▲ Atenção à margem] Parte da alta vem de outro item do mesmo fornecedor com margem   │
 │ maior: o portfólio troca venda e perde margem.                                        │
 └───────────────────────────────────────────────────────────────────────────────────────┘
 4011 · PRÓPOLIS AQUOSO 30 ML · APIS BRASIL   Mesmo fornecedor   −R$ 2.140,00   12 clientes   Alta   [▲ Reajustar canibalizador]
 ...
```

- Totais `totalInterno` e `totalConcorrentes` em `mono`. O alerta de margem aparece só se algum item `CANIBALIZACAO_INTERNA` tiver `PRECO_MENOR_DESTROI_MARGEM` (decisão vem da API; a tela só testa o enum).
- Até 10 itens (P-171). Sem itens: `Nenhum produto semelhante perdeu clientes para este no período.`
- Em `NOVO`, título `Este lançamento está tirando vendas de {n} produtos`.

---

## 7. Bloco "Análise com IA" — 8 estados

Âncora `id="analise-ia"`, `h3` `Análise com IA` (`tabindex="-1"`, alvo do atalho do resumo). Estrutura fixa: cabeçalho → aviso fixo (quando há conteúdo de IA) → área de estado → conteúdo → rodapé de metadados.

**Aviso fixo** (`InlineNoticeComponent tone="info" dismissible=false`, fundo `--bg-canvas`, borda esq. 3px `--feedback-info-bg`), visível sempre que houver diagnóstico na tela e também no estado vazio, para o usuário saber antes de clicar:
`Diagnóstico gerado por IA a partir de dados internos e notícias públicas; confira as fontes.`

**Botão único** (`min-height` 40 px desktop / 44 px mobile; **não existe "Análise aprofundada"**). Rótulo e habilitação vêm de `meta.ia` do GET:
- `geraComIa = true`, sem salvo: `Gerar análise com IA`. Com `diagnosticoSalvo`: `Gerar de novo` (com `diagnosticoVencido`: `Atualizar`, ao lado do texto `Gerada há {N} dias`).
- `geraComIa = false` (gate, orçamento, IA desligada/indisponível; `motivoTemplate`): `Gerar resumo automático`, com linha de ajuda 0.75rem `--text-secondary` por motivo (§10.6). O clique é permitido e devolve o resumo sem IA.
- Desabilitado só por `podeGerar = false` (`SEM_VARIACAO`, `geracaoEmAndamento`) ou durante o POST (P-176.1); `Gerar de novo`/`Atualizar` também com `podeForcar = false`, com texto neutro por `aria-describedby`: `Já existe uma análise salva para esta janela.` Nada de valor, saldo ou "créditos restantes".
- A tela **não calcula nem exibe** gasto; `meta.ia.orcamento.nivel` não gera texto próprio.

| # | Estado | Condição | Visual e texto | Foco / anúncio |
| :-: | :--- | :--- | :--- | :--- |
| 1 | **Vazio — ainda não gerada** | GET sem `diagnosticoIa`; modo ≠ `SEM_VARIACAO` | Ícone de documento com linhas (SVG 24 px, `--text-secondary`) + título `Ainda não há análise com IA para esta janela` + texto `A IA lê os números acima, pesquisa notícias do período (clima, preço de matéria-prima, regras, concorrência) e aponta o que pode explicar a parte sem explicação. O resultado fica salvo para esta janela.` + botão | — |
| 2 | **Gerando** (~10–30 s) | POST em voo para a chave | Botões desabilitados, o primário com texto `Gerando…`. Área: skeleton do conteúdo (1 linha de 60% + 3 linhas do resumo + 3 itens de fator com selo) e a linha `role="status"`: `Lendo os números e pesquisando notícias do período. Costuma levar de 10 a 30 segundos.` + contador `{s} s` (`aria-hidden`, atualiza a cada segundo). **Sem barra de percentual** (o backend não informa progresso). Aos 30 s, troca o texto: `Está demorando mais que o normal. Pode fechar este painel: a análise continua enquanto a página estiver aberta.` | Anúncio só no início e aos 30 s (não a cada segundo) |
| 3 | **Sucesso (recém-gerada)** | POST 200 com `meta.origem = llm` ou `fallback` | Conteúdo (§7.1) + rodapé `Gerada agora`. Selo de origem (§7.2). Botão vira `Gerar de novo`. `fallback` não mostra aviso nem nome de modelo (só em "Detalhes técnicos") | Foco no `h3`; anúncio `Análise com IA pronta.` |
| 4 | **Salva (com data)** | GET com `diagnosticoIa` salvo, ou POST com `meta.origem = cache` (`reutilizado`) | Conteúdo + selo `Análise salva` + rodapé `Gerada em {dd/MM/yyyy} às {HH:mm}`. Se veio do POST: `InlineNotice` info `Já havia uma análise salva para esta janela; mostramos a de {dd/MM}.` (sem mencionar crédito ou custo) | Anúncio `Análise salva de {dd/MM} exibida.` |
| 5 | **Confirmação de regeneração** | Clique em `Gerar de novo`/`Atualizar` com diagnóstico salvo e `podeForcar = true` (P-175.2/175.3) | **Confirmação inline** (não abre outro diálogo): o botão é substituído por uma caixa `--bg-surface`, borda 1px `--border-default`, borda esq. 3px `--feedback-warning-bg`, `role="group" aria-labelledby`: `Gerar de novo substitui a análise salva desta janela. Continuar?` + `[Continuar]` primário + `[Cancelar]` secundário. Sem menção a créditos. O diagnóstico salvo continua visível | Foco no texto da pergunta (`tabindex="-1"`) para evitar Enter acidental; `Esc` = Cancelar; ao cancelar, foco volta ao botão de origem |
| 6 | **Resumo automático (IA indisponível / orçamento esgotado / IA desligada / gate)** | POST **200** com `meta.origem = template` (`motivoTemplate`); ou GET com `geraComIa = false` | Não é erro. Exibe `data.resumoAutomatico` (texto puro) sob o selo `Resumo automático (sem IA)` e a nota neutra por `motivoTemplate` (§10.6); sem fatores, fontes nem hipóteses. Tom `info`, borda esq. `--feedback-neutral-bg`. **Nunca culpa o usuário** e não fala de limite, saldo ou valor. A parte numérica segue visível | Anúncio `Resumo automático exibido.` |
| 7 | **Limite de pedidos (429 `TIA-004`)** | `motivo = LIMITE_DE_PEDIDOS` (2/min) ou `LIMITE_DIARIO` (10/dia; `force` 3/dia) | Caixa borda esq. 3px `--feedback-warning-bg`. `LIMITE_DE_PEDIDOS`: `Muitos pedidos de análise em sequência. Aguarde um minuto e tente de novo.`, botão reabilitado após `Retry-After` (contador `aria-hidden`). `LIMITE_DIARIO`: `Você chegou ao limite de análises por hoje. A parte numérica continua disponível e o limite renova amanhã.` (sem contador, botão desabilitado até a data; sem `Retry-After` em segundos na tela). Salvo, se houver, continua visível | Anúncio da mensagem |
| 8 | **Erro** | Rede; 500; timeout do cliente (120 s); `TIA-001` no POST | Caixa borda esq. 3px `--feedback-critical-bg`: `Não foi possível gerar a análise agora. A parte numérica está disponível.` + `[Tentar de novo]` (mesmo POST, sem `force`). Nada de código técnico nem stacktrace. (Falha da IA com 200 + `IA_FALHOU` não é este estado: cai no estado 6.) | Foco no botão `Tentar de novo` |

**Sem variação relevante (`SEM_VARIACAO`):** o bloco não mostra botão; texto `Não há variação relevante para analisar nesta janela (menos de {limiar}). Escolha outra janela acima.` (P-152; limiar de `meta.parametros`).
**Modo `QUALITATIVO`:** antes dos botões, linha `Com base pequena, a IA aponta sinais e notícias, sem estimar valores.`

### 7.1 Conteúdo do diagnóstico

```
 Análise com IA                                                                   (h3)
 [i] Diagnóstico gerado por IA a partir de dados internos e notícias públicas; confira as fontes.

 O que a IA encontrou                                                             (h4)
 A queda acompanha a alta do preço do própolis bruto no Sul e a chegada de um item
 concorrente mais barato. Parte da perda foi para outro fornecedor (−R$ 1.704,00).

 Fatores com evidência (4)                                                        (h4)
 ▼ Migração de clientes · outro fornecedor        −R$ 1.704,00   Confiança alta
   Dado interno · ver na cascata ↑
 ▼ Matéria-prima  [Possível]                      —              Confiança média
   Preço do própolis bruto subiu na safra 2026.
   Fontes: Safra de própolis tem quebra no PR — agrolink.com.br · 14/09/2026 ↗
           Cotação do própolis — cepea.esalq.usp.br · 02/10/2026 ↗

 ┌ ┄ ┄ Hipóteses sem fonte confirmada (2) ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┐
 ┆ Clima: inverno mais quente pode ter reduzido a procura.                            ┆
 ┆   Não confirmada: notícia fora do período analisado.                               ┆
 └ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┄ ┘

 Próximos passos sugeridos                                                        (h4)
 1. Comparar o preço com o item 4012 no relatório de Canibalização.
 2. ...
 [Análise salva]  Gerada em 22/11/2026 às 14:05
 [Gerar de novo]
```

- **Resumo:** `<p>` em texto puro (interpolação Angular, nunca `[innerHTML]`; P-184.5), máx. 800 caracteres. Os números do texto já chegam substituídos pelo backend (P-182.1).
- **Fatores com evidência** (`AiFactorItemComponent`, `<ul>`): linha 1 glifo de sentido + rótulo do `tipo` (§10.1) + `parcelaEstimada` (se houver; `—` se externo) + confiança em texto. Fatores externos ganham o microselo de contorno `Possível` (P-182.5; `--feedback-info-bg` como texto e borda). Linha 2: `Dado interno · ver na cascata ↑` (link que foca a linha correspondente da cascata, `th` com `tabindex="-1"`) quando há `evidenciaInterna`; ou o texto da evidência. Linha 3: fontes.
- **Fonte clicável com data** (`SourceLinkComponent`): `<a href target="_blank" rel="noopener noreferrer">{titulo}</a>` + domínio em `mono` 0.75rem `--text-secondary` (extraído da URL por função pura, sem `www.`) + `· {dataPublicacao dd/MM/yyyy}` + ícone de saída `↗` `aria-hidden` + `sr-only` `(abre em nova aba)`. Título longo: 2 linhas com `overflow-wrap: anywhere`. Até 5 por fator.
- **Hipóteses separadas das evidências (D-10):** contêiner próprio, depois dos fatores, com borda **tracejada** 1px `--border-strong`, fundo `--bg-canvas`, título `h4` `Hipóteses sem fonte confirmada ({n})` e texto introdutório 0.75rem `--text-muted`: `A IA levantou, mas não achou fonte válida para o período. Não trate como causa.` Itens sem selo de confiança, com o motivo (§10.3). Separação por posição, borda, fundo e título — não só por cor.
- **Recomendações:** `<ol>`, título `Próximos passos sugeridos`, até 5.
- **`impactoEmOutrosProdutos`** não é repetido aqui: já está na §6.9 (parte numérica).
- **Rodapé de metadados:** 0.75rem `--text-secondary`: data/hora e selo de origem (§7.2); sem tipo de análise. Modelo (`meta.modelo`) só em `title`/`<details>` "Detalhes técnicos" (não é informação de negócio).
- **Sem fatores válidos** (todos viraram hipótese): título `Fatores com evidência (0)` + `A IA não encontrou fator com fonte válida. Veja as hipóteses abaixo e a cascata acima.`

---

### 7.2 Selo de origem (`meta.origem`; o GET com salvo equivale a `cache`)

Microselo de contorno (`--border-default`, texto `--text-secondary`, 0.75rem) ao lado do `h3`, sempre texto, sem cor própria:

| `origem` | Rótulo | Observação |
| :--- | :--- | :--- |
| `llm` | `Gerada por IA` | Recém-gerada |
| `fallback` | `Gerada por IA` | Mesmo rótulo do `llm`; o usuário não precisa saber qual modelo (nome só em "Detalhes técnicos") |
| `cache` | `Análise salva` | Mais a data no rodapé; custo zero, sem mencioná-lo |
| `template` | `Resumo automático (sem IA)` | Sem aviso fixo de "gerado por IA" (não há IA); o aviso fixo só aparece com `llm`/`fallback`/`cache` |

### 7.3 Detalhes de conteúdo derivados do contrato 1.1.0

- **`explicacao` do fator** (≤ 160 caracteres, texto da IA sem números): linha 2 de cada fator, antes de `Dado interno · ver na cascata ↑` e das fontes. Números do fator vêm de `parcelaEstimada`/cascata, nunca do texto.
- **Contagens `"<3"`** (`clientesMigrados`, `clientesPerdidosQtd`; LGPD): exibir `menos de 3 clientes` (célula compacta `<3` com `sr-only` `menos de 3 clientes`); valor em R$ correspondente, quando `null`, como `—`. Nunca somar nem converter `"<3"` em número; a tela não tenta inferir identidades. Tipo `number | '<3'` tratado por função pura em `insight-view.ts`.
- **Fonte com `dataPublicacao = null`** (`SEM_DATA`, só em hipóteses): na linha da fonte, no lugar da data, `sem data de publicação` (`--text-secondary`); nunca em fator aceito. A hipótese mostra o motivo `Fonte sem data de publicação.` (§10.3).
- **Hipótese com `SKU_FORA_DO_PACOTE`:** texto `Citou um produto fora da análise; ignorado.`

| Estado | Visual |
| :--- | :--- |
| **Carregando** (GET) | `TrendInsightSkeletonComponent part="panel"` com a geometria real: faixa do resumo (bloco 96×36 + 2 linhas), selo (120×24), 7 linhas da cascata (rótulo 40% + barra 30% + valor 18%), 4 linhas do grupo afim; `.skeleton-*` com `pulseSolid`. Cabeçalho do painel já com descrição e código (vêm da linha da tabela). Após 4 s: `role="status"` `Calculando a migração de clientes desta janela; a primeira consulta pode levar alguns segundos.` |
| **Recarregando** (troca de janela) | Mantém o conteúdo anterior esmaecido (`opacity` 0.55, `aria-busy="true"`) + skeleton só na cascata, para não "piscar" o painel |
| **Erro** | `TrendErrorBannerComponent` no topo do corpo; mensagem por código (§10.4); `[Tentar de novo]` refaz o GET. `TIA-002` não tem retry: ação `Fechar`. `TIA-003`: sem retry, texto sugere outra janela (o seletor continua ativo) |
| **Sem variação** (`SEM_VARIACAO`) | `TrendEmptyStateComponent`: ícone de linha horizontal, título `Sem variação relevante em {X}`, texto `A venda mudou menos de {limiar} entre os dois períodos; não há o que explicar.`, ação `Ver 3 meses` (ou a primeira janela com variação, se o GET de resumo informar; senão o seletor). Grupo afim continua listado se vier |
| **Qualitativo / Novo** | §6.4 + §6.6 (lista de sinais em vez da tabela) |
| **Fatores "não avaliado"** | Linha visível na cascata com `Não avaliado` + motivo (§10.2); nunca some, nunca vira 0 |

---

## 9. Matriz dos 8 estados interativos (controles do F7)

| Estado | "Por que?" | Seletor de janela | Botão de IA | Disclosures (`[›]`, "Mostrar todos") | Links (fonte, Canibalização) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Default | contorno `--border-default`, texto `--brand-primary` | `SegmentedControl` padrão | primário sólido / secundário contorno | 40×40, `--text-secondary` | `--brand-primary`, sublinhado 1px |
| Hover | fundo `--brand-primary-subtle`, borda `--brand-primary` | do componente | primário `--brand-primary-hover`; secundário fundo `--bg-subtle` | fundo `--bg-subtle` | sublinhado 2px |
| Focus-visible | anel 2px `--border-focus`, offset 2px | idem | idem | idem | idem |
| Active | fundo `--bg-muted` | `--brand-primary-active` | `--brand-primary-active` | — | — |
| Disabled | — (sempre ativo) | durante GET | durante geração, `geracaoEmAndamento`, `podeForcar = false`, `LIMITE_DE_PEDIDOS` (até `Retry-After`), `LIMITE_DIARIO`, `SEM_VARIACAO` (oculto); orçamento esgotado **não** desabilita (gera resumo automático); `cursor: not-allowed`, opacidade 0.55, motivo neutro por `aria-describedby` | — | — |
| Loading | — | — | `Gerando…` + skeleton do bloco | — | — |
| Error | — | — | caixa de erro + `Tentar de novo` | — | — |
| Success | linha `.is-explaining` enquanto aberto | opção ativa `--brand-primary` | rótulo vira `Gerar de novo` | `aria-expanded="true"`, chevron 90° | — |

Todas as transições em `--transition-fast`; nenhuma com `transform: scale` em texto.

---

## 10. Copy (pt-BR, sem jargão; números sempre interpolados de `data`/`meta`)

### 10.1 Rótulos de causa (`tipo`)

| `tipo` | Queda | Alta |
| :--- | :--- | :--- |
| `SAZONALIDADE` | Época do ano | Época do ano |
| `PRECO` | Mudança de preço | Mudança de preço |
| `PRODUTO_NOVO` | Lançamento semelhante | (não se aplica) |
| `CANIBALIZACAO_MESMO_FORNECEDOR` | Migração de clientes · mesmo fornecedor | Clientes vindos do mesmo fornecedor |
| `CANIBALIZACAO_OUTRO_FORNECEDOR` | Migração de clientes · outro fornecedor | Clientes vindos de outro fornecedor |
| `CLIENTES_PERDIDOS` | Clientes que pararam de comprar | (não se aplica) |
| Resíduo | Sem explicação nos dados internos | Sem explicação nos dados internos |
| `PERDA_PARTICIPACAO_SEM_MIGRACAO` | Semelhantes cresceram sem levar clientes | Ganho sem migração de clientes |
| `RUPTURA` / `PROMOCAO` / `REGIONAL` | Falta de estoque / Promoção / Concentração em um estado | idem |
| `CLIMA` / `POLITICO_REGULATORIO` / `MATERIA_PRIMA` / `CONCORRENCIA_MERCADO` / `OUTRO` | Clima / Regras e governo / Matéria-prima / Concorrência no mercado / Outro fator | idem |

Linha 2 das parcelas avaliadas (exemplos com campos da API): `SAZONALIDADE` `Esta época costuma vender {mais\|menos}; {explica\|compensa} parte da {queda\|alta}.` · `PRECO` `Preço médio praticado {subiu\|caiu} {deltaPrecoPct}.` · migração `{netClients} clientes passaram a comprar {n} produtos semelhantes.` · `CLIENTES_PERDIDOS` `{clientesPerdidosQtd} clientes estão em risco ou inativos e não compraram semelhantes.`

Confiança: `Alta`, `Média`, `Baixa`, com `title` e legenda `<details>` `Como ler a confiança`: `Alta: medida com muitos clientes ou histórico firme. Média: sinal claro, base menor. Baixa: poucos casos; use como pista.`

### 10.2 Motivos de "não avaliado" / "sem efeito"

| Motivo | Texto |
| :--- | :--- |
| `JANELA_ANTERIOR_INCOMPLETA` | O período anterior não está completo na base. |
| `MES_BASE_ANTIGO` | Só dá para medir em meses recentes. |
| `SEM_PRECO_MEDIO` | Sem preço médio para converter em unidades; valor em R$ como referência. |
| `HISTORICO_CURTO` | Histórico curto para medir a época do ano. |
| `VENDA_ESPORADICA` | Vendas esporádicas demais para medir a época do ano. |
| `FRACA` | A época do ano tem efeito pequeno neste produto. |
| `INDICE_AFINIDADE_INDISPONIVEL` | Lista de produtos semelhantes em atualização. |
| `FONTE_INDISPONIVEL` (genérico de P-173) | Dado indisponível nesta consulta. |
| Desconhecido | Não avaliado nesta consulta. |

### 10.3 Motivos de hipótese (P-182.4)

`SEM_FONTE` Nenhuma fonte encontrada. · `FONTE_NAO_CITADA` A fonte não foi confirmada pela busca. · `SEM_DATA` Fonte sem data de publicação. · `FORA_DO_PERIODO` Notícia fora do período analisado.

### 10.4 Erros

| Código | Texto na tela |
| :--- | :--- |
| `TIA-001` | Não foi possível montar o diagnóstico com estes filtros. Recarregue a página. |
| `TIA-002` | Este produto não está mais no catálogo ativo. |
| `TIA-003` (GET) | Não há base de vendas suficiente para diagnosticar esta janela. Escolha outra janela. |
| `TIA-003` (POST) | Não há variação relevante para analisar. |
| `TIA-004` (429) | por `motivo` (`LIMITE_DE_PEDIDOS`, `LIMITE_DIARIO`), §7 estado 7. Nunca é 503 nem fala de orçamento |
| `TIA-005` (aviso) | §6.4 |
| `TIA-006` / `TIA-007` | Só rota interna; a tela não os trata |
| `ANL-001` | A base de vendas está indisponível agora. Tente de novo em alguns minutos. |
| Rede / 500 | Não foi possível carregar o diagnóstico. Verifique a conexão e tente de novo. |

### 10.6 Notas do resumo automático (`motivoTemplate`; tom neutro, sem culpar o usuário, sem custo)

| `motivoTemplate` | Nota (também ajuda do botão `Gerar resumo automático`) |
| :--- | :--- |
| `GATE_VARIACAO` / `GATE_VALOR_BAIXO` | `A variação é pequena demais para uma análise com IA; veja o resumo automático.` |
| `GATE_RESIDUO_BAIXO` | `Os dados internos já explicam quase tudo; a IA não foi necessária.` |
| `ORCAMENTO_ESGOTADO` / `IA_DESLIGADA` / `IA_INDISPONIVEL` | `A análise com IA não está disponível agora. Mostramos o resumo automático; a parte numérica está completa.` |

### 10.5 Regiões vivas

`Diagnóstico de {descricao} aberto.` · `Janela alterada para {X}.` · `Análise com IA iniciada. Costuma levar de 10 a 30 segundos.` · `Análise com IA pronta.` · `Análise salva de {dd/MM} exibida.` · mensagens de erro do bloco.

---

## 11. Campos de contrato de que a tela depende (para o `architect`)

1. Por parcela: `tipo`, `valor`, `valorReceita`, `sentido`, `confianca`, `status`, `motivoNaoAvaliado`, `cortada`, `observacao`, **`pontosPercentuais`** (valor ÷ baseAjustada × 100, para a coluna p.p. sem cálculo na tela) e `pares[]` (`sku`, `descricao`, `fornecedor`, `affinityScore`, `netRev`, `netClients`, `confianca`, `mecanismo`).
2. Resumo: `variacaoPct`, `baseAjustada`, `atual`, `deltaObservado`, `residuo`, `coberturaExplicacaoPct`, `direcao`, `modo`, estado da célula, períodos (ou reaproveitar `meta.janelas` da Tendência).
3. Grupo afim: `vMercado`, `participacaoPre`, `participacaoCur`, `deltaParticipacaoPp`, variações separadas mesmo/outro fornecedor com contagem, e cada afim com sua célula da Tendência **no formato `TrendCell`**, `sameSupplier`, `ganhouClientesDeA`, `clientesMigrados`, `receitaMigrada`.
4. `impactoEmOutrosProdutos`, `totalInterno`, `totalConcorrentes` **no GET** (não só dentro do diagnóstico de IA).
5. `meta.parametros`: `minExplainableVariationPct`, `affineGroupMinScore` (para a copy não fixar 2% e 50%).
6. `meta.ia` no GET (contrato 1.1.0): `podeGerar`, `motivoBloqueio`, `geraComIa`, `motivoTemplate`, `diagnosticoSalvo`, `diagnosticoSalvoEm`, `diagnosticoVencido`, `podeForcar`, `geracaoEmAndamento`, `orcamento.nivel` (a tela **não** exibe o nível nem qualquer valor de custo; §4.4 do contrato).
7. POST: `meta.origem` (`llm`/`cache`/`template`/`fallback`), `meta.motivoTemplate`, `meta.reutilizado`, `data.resumoAutomatico`, `meta.avisos` (`IA_FALHOU`, `SEM_BUSCA_EXTERNA`). Diagnóstico: `geradoEm`, `modelo` (só detalhes técnicos), `fatores[].explicacao`/`rotulo`, `fontes[]` com `url`, `dominio`, `titulo`, `dataPublicacao` (anulável), `hipotesesNaoConfirmadas[].motivo`. Contagens `clientesMigrados`/`clientesPerdidosQtd` como `number | "<3"`. Erro `429 TIA-004` com `error.motivo`. **Removidos:** `deep`, `tipoAnalise`, `escalonadoAutomaticamente`, `DIAGNOSTICO_DESATUALIZADO`.
8. Enum fechado dos motivos de `NAO_AVALIADO`/`SEM_EFEITO` (§10.2).

---

## 12. Decisões de design (D-n)

| # | Decisão |
| :-: | :--- |
| D-1 | Tokens de `styles.scss` (Papel & Tinta), não do `DESIGN_SYSTEM.md` (placeholders), como F4/F6 |
| D-2 | Código em `features/sales-trend/insights/`; reusa componentes da Tendência e, onde ela não tem equivalente, pipes e metadados da F6 (a restrição D-14 do plano da Tendência caiu: `analytics` já está em `main`) |
| D-3 | "Por que?" só em linhas de produto (inclusive filhas na visão por fornecedor); linha de fornecedor fica para a fase 7.4 |
| D-4 | Botão na linha 2 da célula do produto, sem coluna nova; 32 px de altura no desktop, 44 px no cartão |
| D-5 | Foco inicial no título do painel (conteúdo longo); Esc cancela a confirmação antes de fechar o painel |
| D-6 | Cascata como tabela visível com barra `aria-hidden`; alta listrada × queda lisa × resíduo tracejado; eixo só da variação (não do total) para as parcelas ficarem legíveis |
| D-7 | Selo de mercado colorido pelo tipo de causa (mercado azul, concorrência âmbar, misto neutro); direção pelo glifo |
| D-8 | `?porque={sku}` na URL com `replaceUrl` |
| D-9 | Store na página: fechar o painel ou trocar de janela não cancela uma geração em voo; reabrir a mesma chave mostra "Gerando…" |
| D-10 | Hipóteses em contêiner tracejado separado, depois dos fatores, sem selo de confiança |
| D-11 | Confirmação de "Gerar de novo" inline no bloco, não um segundo diálogo |
| D-12 | Progresso da IA honesto: tempo decorrido e texto fixo, sem percentual |
| D-13 | Bloco "Esta alta está tirando vendas de…" na parte numérica (dado do motor), não no bloco de IA |

---

## 13. Dúvidas para o checkpoint

| # | Dúvida | Proposta |
| :-: | :--- | :--- |
| Q-D1 | A API devolve `pontosPercentuais` por parcela? | Sim, pedir ao `architect`; sem isso, `insight-view.ts` calcula `valor ÷ baseAjustada × 100` como formatação |
| Q-D2 | A página de Canibalização não abre o drawer por URL (só lê `periodo` e `busca`) | Adicionar `?abrir={sku}` na F6 (tarefa pequena na 7.3); até lá, o link usa só `busca={sku}` |
| Q-D3 | A célula do afim vem no formato `TrendCell`? | Sim, para reusar `TrendCellComponent`; senão, mostrar `variacaoPct` com `trendPercent` |
| Q-D4 | Extrair o focus trap do `price-equilibrium-drawer` para `shared/a11y/dialog-focus.ts` mexe em código da F6 | Aceitar a extração (sem mudança de comportamento, coberta pelos testes do drawer) |
| Q-D5 | `MECHANISM_VISUAL_META` está no store da página de Canibalização | Mover para `analytics/utils/cannibalization-mechanism.ts` |
| Q-D6 | `impactoEmOutrosProdutos` vem no GET? | Sim (é do motor, P-171); se vier só no POST, o bloco passa para dentro da IA |
| Q-D7 | O GET informa orçamento esgotado / geração em voo (`meta.ia`)? | **Resolvida (contrato 1.1.0):** `geraComIa`/`motivoTemplate`/`geracaoEmAndamento`; orçamento esgotado vira resumo automático (200), sem expor gasto |
| Q-D8 | Janela da Tendência (1/3/6/12 meses) × período da Canibalização (30/60/90 dias) | Link sempre com `periodo=90` e nota de que os números podem diferir |
| Q-D9 | Pipes duplicados (`sales-trend/utils/pt-br-format.ts` e `analytics/utils/pt-br-format.ts`) | Não consolidar na F7; usar os da Tendência e só `signedBrl`/`brl` da F6. Consolidação como refatoração T7 à parte |
