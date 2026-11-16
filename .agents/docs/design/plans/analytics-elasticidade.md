# Design Plan: Analytics Comercial — F5 Calculadora Unificada de Preço, Margem e Estoque (v3)

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-elasticidade.md`
> **Responsável:** Designer (`designer`) / `uiux-expert`
> **Auditor:** UX Reviewer (`ux_reviewer`)
> **Status:** v3 — Calculadora Unificada Enxuta (Custo Editável + Margem Unitária/Total + Estoque 60 Dias)
> **Alinhamento:** `frontend/src/styles.scss`, `frontend/src/app/features/analytics/styles/_analytics-ui.scss` e `.agents/rules/frontend-ui-anti-patterns.md`

/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 */

---

## 1. Identificação, Objetivo de UX e Escopo v3

- **User Story Relacionada:** US-F5 — *Como gestor comercial ou analista de pricing da Fitoherb, quero buscar um produto, conferir e ajustar seu custo unitário se necessário, e simular variações de preço para visualizar instantaneamente o impacto na margem unitária, no lucro bruto estimado e na cobertura do estoque sob a política de 60 dias.*
- **Mudança Estrutural v3 (Simplificação Focada em Decisão):**
  - **Removidos da página `/analytics/elasticity`:** seção separada de Diagnóstico (`<app-elasticity-diagnostic-card>`) e seção inteira de Análise por Comprador / Tabela de Clientes (`<app-elasticity-customers-table>`).
  - **Mantidos e Aprimorados:** Painel de busca de produto (`<app-code-search-form>`) + **Calculadora Unificada** (`<app-elasticity-simulator-panel>`) com cabeçalho compacto do produto no topo, editor de custo unitário com origem e restauração, controle de reajuste de preço e 4 cards de impacto orientados à decisão comercial.
- **Filosofia Visual (Papel & Tinta):**
  - Superfícies sólidas em papel quente (`--bg-canvas: #F5F2EB`, `--bg-surface: #FFFFFF`, `--bg-subtle: #ECE7DC`, `--bg-muted: #E2DDD0`, `--bg-table-row-zebra: #FAF8F4`), tinta escura (`--text-primary: #181D19`) e verde botânico (`--brand-primary: #1D4528`).
  - Tipografia editorial: `Signika` (`--font-family-headline`), `Source Sans 3` (`--font-family-body`) e `Overpass Mono` (`--font-family-mono`) com `tabular-nums` e formatação pt-BR (`BrlPipe`, `PtDecimalPipe`, `PtPercentPipe`).

---

## 2. Checklist Anti-IA (Filtro Anti-Slop Obrigatório)

- [x] **Sem "AI Purple":** nenhum gradiente genérico azul-roxo; toda ênfase usa verde botânico `--brand-primary` (`#1D4528`) e neutros Papel & Tinta.
- [x] **Sem 3 Colunas Mecânicas SaaS:** workbench analítico com cabeçalho compacto + controles integrados de preço/custo + grade 2×2 de decisão com destaque hierárquico no Lucro Bruto e Cobertura de Estoque 60 dias.
- [x] **Sem Glassmorphism / Fake Chrome:** popovers `<app-info-help>` e painéis usam superfícies sólidas (`--bg-surface`) com bordas `1px solid` (`--border-default`/`--border-strong`) e sombras secas (`--shadow-xs`/`--shadow-lg`).
- [x] **Pureza Tipográfica:** `Signika` nos títulos (sem itálico em headers), `Source Sans 3` no corpo e `Overpass Mono` em códigos/valores.
- [x] **Copy Honesto (Zero Métricas Inventadas):** quando `recentVolume60d === 0`, a tela não exibe volume fictício nem cobertura em dias inventada; exibe `—` com aviso claro de ausência de vendas nos últimos 60 dias.
- [x] **Zero Spinners Solitários no Carregamento:** `<app-elasticity-skeleton>` espelha exclusivamente a geometria da Calculadora Unificada (sem skeleton de diagnóstico separado nem de tabela).
- [x] **Zero Telas Vazias:** `<app-result-state>` cobre estado inicial (`initial`) e histórico insuficiente (`ELA-003`).

---

## 3. Tokens do Design System Aplicados (`styles.scss` & `_analytics-ui.scss`)

*O Desenvolvedor NÃO deve usar hexadecimais hardcoded nem criar tokens fora de `styles.scss`.*

| Categoria | Tokens / Mixins Utilizados | Aplicação na Calculadora v3 |
| :--- | :--- | :--- |
| **Superfícies** | `--bg-canvas`, `--bg-surface`, `--bg-subtle`, `--bg-muted`, `--bg-table-row-zebra` | Canvas geral, cards da calculadora (`ui.panel`), caixa de controles de preço/custo, faixa resumo, cabeçalho compacto |
| **Textos** | `--text-primary` (`#181D19`), `--text-secondary` (`#434B44`), `--text-on-brand` (`#FFFFFF`) | Títulos, rótulos e subtítulos sobre bege (`--text-secondary` garante contraste >= 4.5:1 em `--bg-subtle` e `--bg-table-row-zebra`; **proibido `--text-muted` sobre bege**) e texto em tags escuras |
| **Marca** | `--brand-primary` (`#1D4528`), `--brand-primary-hover`, `--brand-primary-active`, `--brand-primary-subtle` (`#E5EFE7`), `--brand-secondary-subtle` (`#F9EFE5`) | Ações primárias, card destaque de Lucro Bruto, badges SKU, avisos `role="note"` |
| **Feedback Sólido** | `--feedback-positive-bg`, `--feedback-warning-bg`, `--feedback-critical-bg`, `--feedback-info-bg`, `--feedback-neutral-bg` | Tags `.tag-positive`, `.tag-warning`, `.tag-critical`, `.tag-info`, `.tag-neutral` (sempre com `--text-on-brand`) e deltas positivos/negativos com ícones SVG |
| **Bordas & Raios** | `--border-subtle`, `--border-default`, `--border-strong`, `--border-focus`, `--radius-xs`, `--radius-sm`, `--radius-full` | Divisórias `1px solid`, anel de foco `2px solid var(--border-focus)`, barras de estoque |
| **Mixins / Placeholders** | `@include ui.panel`, `@extend %button-primary`, `@extend %button-secondary`, `@include ui.hover`, `@include ui.reduced-motion`, `@include ui.sr-only` | Botões de atalho, botão "Restaurar custo do catálogo", skeleton acessível e hover seguro em touch |

---

## 4. Anatomia dos Componentes e Layout v3

### 4.1 Página Principal (`elasticity-page.component.html`)
1. **Painel de Busca (`section.search-panel`):**
   - **Eyebrow:** `Decisão de Preço & Lucro`
   - **Título (`h2`):** `Simulador de Preço e Reação de Vendas` + `<app-info-help>` (`elasticityOverview`)
   - **Subtítulo:** `Teste aumentos ou descontos para ver na hora o impacto na margem unitária, no lucro bruto e na cobertura de estoque para 60 dias.`
   - **`<app-code-search-form>`:** `label="Escolha o produto"`, `hint="Digite o código ou nome do produto e selecione na lista."`, `submitLabel="Analisar produto"`.
2. **Área de Conteúdo (`@switch (loadState())`):**
   - `initial`: `<app-result-state>` (`buildElasticityInitialState`) focado no fluxo em 3 passos (1. Buscar produto → 2. Conferir ou ajustar custo → 3. Simular preço, margem e estoque 60 dias).
   - `loading`: `<app-elasticity-skeleton>` (geometria enxuta de 1 painel único de calculadora).
   - `insufficient-data`: `<app-result-state>` (`buildElasticityInsufficientDataState`) para `ELA-003`.
   - `error`: `<app-error-banner>` com código e botão `"Tentar novamente"`.
   - `loaded`: exibe **diretamente `<app-elasticity-simulator-panel>`** recebendo `product`, `elasticity`, `priceChangePct`, `costPriceInput`, `simulationResult`, `isSimulating`, `simulationError`.

### 4.2 Calculadora Unificada (`elasticity-simulator-panel.component.html`)

Organizada em **5 faixas verticais claras** dentro de `section.simulator-card`:

#### Faixa A — Cabeçalho Compacto do Produto (Topo da Calculadora)
- **Esquerda (`.product-compact-identity`):**
  - `.product-sku-badge`: `SKU #{{ product().code }}`
  - `h3.product-description`: `{{ product().description }}`
  - `.product-compact-meta`: `Fornecedor: {{ product().supplier }}` · `Estoque atual: {{ formattedStock() }} un.` · `Vendas líquidas 60d: {{ formattedRecentVolume60d() }} un.`
- **Direita (`.product-compact-badges`):**
  - Mantém apenas a pílula compacta **`Ver detalhes estatísticos`** + `<app-info-help>` (`technicalSummary` — exibe em texto limpo os detalhes técnicos: **Beta (`coefficient`), IC 95% (`confidenceInterval`), $R^2$ (`rSquared`), Erro padrão (`standardError`), Meses válidos (`observationsCount`)** e tradução prática em `+10%`), removendo as tags visuais de classificação e confiança da barra superior.
- **Avisos Contextuais `role="note"` (logo abaixo do cabeçalho compacto):**
  - Se `elasticity().fallbackApplied`: aviso `--brand-secondary-subtle` explicando o uso da estimativa padrão de segurança (`-1,20`).
  - Senão se `!elasticity().isReliable`: aviso `--brand-secondary-subtle` explicando baixa precisão estatística.
  - Se `product().recentVolume60d <= 0`: aviso neutro informativo (`--bg-table-row-zebra`, borda esquerda `--feedback-info-bg`) informando que não houve vendas líquidas nos últimos 60 dias, portanto a projeção de dias de estoque aparece como indisponível (`—`), enquanto o cálculo unitário de preço e margem permanece ativo.

#### Faixa B — Controles de Preço e Custo Unitário (`.controls-panel`)
Disposição responsiva em dois blocos coordenados dentro da área de controle (`--bg-subtle`, borda `--border-subtle`):
1. **Controle de Variação de Preço (`%`):**
   - Linha de atalhos rápidos (`Testar rápido:` `-10%`, `-5%`, `0% (Atual)`, `+5%`, `+10%`, `+20%`) com `aria-pressed`.
   - Slider contínuo (`-50%` a `+100%`, marcações `-50%`, `0%`, `+50%`, `+100%`, legenda `Desconto · Preço atual · Aumento`) + input numérico (`%`).
2. **Controles Lado a Lado de Preço Atual e Custo Unitário Editáveis (`R$`):**
   - **Preço atual (R$)** (`#current-price-input`, `min="0.01"`, `step="0.01"`): badge `Catálogo ERP` vs `Editado manualmente`, `<app-info-help>` (`currentPriceInput`), validação `> 0`, commit imediato com `Enter`/`change` e botão `"Restaurar preço do catálogo ({{ catalogPrice | brl }})"`.
   - **Custo unitário (R$)** (`#cost-price-input`, `min="0"`, `step="0.01"`): badge de origem (`Catálogo ERP`, `Estimado (60% do preço)`, `Editado manualmente`), `<app-info-help>` (`unitCostInput`), validação `>= 0` e botão `"Restaurar custo do catálogo ({{ catalogCost | brl }})"`.
   - Validação cruzada: qualquer campo inválido exibe alerta próprio (`aria-invalid="true"`, `role="alert"`) e bloqueia novas simulações até correção.

#### Faixa C — Faixa Resumo da Simulação (`.simulation-summary-strip`)
- Chips horizontais com wrap fluido:
  - `Preço atual: {{ sim.currentPrice | brl }}` → `Preço projetado: {{ sim.projectedPrice | brl }} ({{ formatSignedPct(sim.priceChangePct) }})`
  - `Custo aplicado: {{ effectiveCost | brl }}` *(com indicação curta `(ERP)` / `(60% est.)` / `(Manual)`)*
  - `Sensibilidade aplicada: {{ sim.appliedElasticity | ptDecimal:2 }}` + `<app-info-help>` (`appliedElasticity`)
- Indicador discreto `Atualizando projeção…` quando `isSimulating()` está ativo (`aria-busy="true"`).

#### Faixa D — Grid de Impacto e Decisão (4 Cards em Grid 2×2 Desktop / 1 Coluna Mobile)
`grid-template-columns: repeat(2, minmax(0, 1fr))` acima de `640px` (1 coluna abaixo de `640px`):

1. **Card 1 — Margem Unitária (`%` principal + `R$/un.` entre parênteses):**
   - Subtítulo: `Ganho por unidade vendida` + `<app-info-help>` (`unitMarginCard`)
   - Valor principal: `{{ projectedUnitMarginPct }}` `<span class="unit-label">({{ projectedUnitMargin | brl }}/un.)</span>`
   - Delta com ícone direcional (`tone-positive` / `tone-negative` / `tone-neutral`): `{{ formatSignedPp(unitMarginPctChangePp) }} ({{ formatSignedBrl(unitMarginDiff) }}/un.)`
   - Baseline: `Atual: {{ currentUnitMarginPct }} ({{ currentUnitMargin | brl }}/un.)` — se `projectedUnitMargin <= 0`, exibe alerta semântico `"Atenção: preço igual ou abaixo do custo"`.

2. **Card 2 — Lucro Bruto Estimado (60 dias)** *(Destaque `.sim-card-highlight`)*:
   - Subtítulo: `Margem de Contribuição no ciclo` + `<app-info-help>` (`projectedMargin`)
   - Valor principal: `{{ sim.projectedMargin | brl }}`
   - Delta com ícone direcional: `{{ formatSignedBrl(sim.marginChangeAbs) }} ({{ formatSignedPct(sim.marginChangePct) }})`
   - Baseline: `Atual (60d): {{ sim.currentMargin | brl }}`

3. **Card 3 — Vendas & Faturamento (60 dias):**
   - Subtítulo: `Volume e receita bruta no ciclo` + `<app-info-help>` (`projectedVolumeAndRevenue`)
   - Valor principal: `{{ formatQty(sim.projectedVolume) }} <span class="unit-label">un.</span>`
   - Delta de volume com ícone direcional: `{{ formatSignedUnits(volumeChangeUnits) }} ({{ formatSignedPct(sim.volumeChangePct) }}) · Atual: {{ formatQty(sim.currentVolume) }} un.`
   - Sub-bloco de Faturamento (`.sim-submetric`): `Faturamento previsto: {{ sim.projectedRevenue | brl }}` · `{{ formatSignedBrl(sim.revenueChangeAbs) }} ({{ formatSignedPct(sim.revenueChangePct) }})` · `Atual: {{ sim.currentRevenue | brl }}`

4. **Card 4 — Cobertura de Estoque (Meta: 60 dias):**
   - Subtítulo: `Comparativo hoje (0%) vs após mudança` + `<app-info-help>` (`stockCoverage60d`)
   - Valor principal:
     - Se `projectedStockDays !== null`: `{{ formatDays(projectedStockDays) }} <span class="unit-label">dias</span>`
     - Se `stock <= 0` e há vendas: `0 <span class="unit-label">dias (Sem estoque)</span>`
     - Se `recentVolume60d <= 0` (sem vendas nos 60d): `— <span class="unit-label">Sem vendas 60d</span>`
   - **Comparativo Direto Hoje vs Proposto + Meta 60d:**
     - Linha comparativa: `Hoje (0%): {{ currentStockDaysText }} → Proposto: {{ projectedStockDaysText }}` + delta em dias (`stockDaysDelta`, ex.: `+5,5 dias` / `-8,2 dias`).
     - Barra visual comparativa (`0d` a `90d+`, com marcador vertical tracejado/sólido exatamente em `60d` = `Meta 60d`), usando cor sólida da faixa (sem gradientes).
     - Badge semântico colorblind-safe (`.tag` com ícone + texto):
       - `giro-rapido` (`<= 15d`): `.tag-warning` — `Giro muito rápido (≤ 15d)`
       - `dentro-meta` (`15d < d <= 60d`): `.tag-positive` — `Dentro da meta (≤ 60d)`
       - `excesso` (`> 60d`): `.tag-info` — `Excesso (> 60d)`
       - `sem-estoque` (`stock <= 0`): `.tag-critical` — `Estoque zerado`
       - `sem-vendas` (`vendas 60d == 0`): `.tag-neutral` — `Sem giro nos últimos 60d`
   - Baseline: `Estoque: {{ formatQty(stock) }} un. · Ritmo: {{ currentDailyText }} → {{ projectedDailyText }} un./dia`

#### Faixa E — Barra de Recomendação (`.simulation-recommendation-bar`)
- Mantém o feedback contextual da simulação com ícone e borda lateral (`rec-tone-positive`, `rec-tone-negative`, `rec-tone-neutral`).

---

## 5. Matriz dos 8 Estados Interativos Mandatórios

| Estado | Experiência na Calculadora Unificada v3 |
| :--- | :--- |
| **1. Initial / Idle** | `<app-result-state>` (`buildElasticityInitialState`) sem chamada automática de API até busca ou `?sku=` na URL. CTA foca o campo de busca. |
| **2. Loading** | `<app-elasticity-skeleton>` espelhando 1 único painel unificado (cabeçalho compacto + barra de controles + grade 2×2 de cards skeleton) com `aria-busy="true"` e `@include ui.reduced-motion`. |
| **3. Success** | Dados em `pt-BR`, custo com origem e restauração, margem unitária/total e estoque 60 dias renderizados + `p.sr-only[role="status"][aria-live="polite"]`. |
| **4. Empty / Sem Vendas 60d** | Quando `recentVolume60d === 0`, exibe aviso `role="note"` honesto de zero vendas nos últimos 60 dias e cobertura `—` (`Sem giro nos últimos 60d`), mantendo preço e margem unitária funcionais. |
| **5. Error** | `<app-error-banner>` amigável (`ELA-001`..`ANL-002`) com retry; erro na chamada de simulação aparece inline sem destruir os controles. |
| **6. Busy / Disabled** | Durante simulação em voo (`isSimulating()`), slider e input de custo permanecem editáveis; presets rápidos e botão `"Restaurar custo do catálogo"` ficam desabilitados e a grade recebe `aria-busy="true"`. |
| **7. Invalid** | Percentual fora de `[-50, 100]`, custo unitário `< 0` ou SKU inválido marcam `aria-invalid="true"`, exibem mensagem inline e bloqueiam chamadas HTTP inválidas. |
| **8. Partial / Low-Confidence** | Bloco `role="note"` contrastante no topo da calculadora explicando fallback `-1,20` (`fallbackApplied`) ou baixa confiabilidade (`!isReliable`). |

---

## 6. Especificação de `<app-info-help>` (Tópicos v3)

- Mantém `InfoHelpCoordinatorService`, zero `[innerHTML]`, `position: fixed` no desktop e bottom sheet em `< 640px`.
- Tópicos removidos por não existirem mais na tela: chaves exclusivas da antiga tabela de clientes (`customerLookup`, `tableShrinkageWeight`, `tableEmpiricalElasticity`, `tableAdjustedElasticity`, `tableProfile`, `productBaselineElasticity`, `customerEmpiricalElasticity`, `shrinkageElasticity`, `shrinkageWeight`).
- Novos tópicos adicionados em `elasticity-help-copy.ts`:
  - `technicalDiagnostics`: consolida **Beta, IC 95%, R², Erro padrão e Meses válidos** em linguagem acessível + nota técnica.
  - `unitCostControl`: explica `[Pc.Ultimo Custo]` do ERP vs fallback 60% vs simulação com custo editado manualmente.
  - `unitMarginImpact`: explica margem unitária em `R$/un.`, `%` e variação em pontos percentuais (`p.p.`).
  - `projectedVolumeAndRevenue`: combina leitura de volume nos 60 dias e receita bruta.
  - `stockCoverage60d`: explica cálculo `Estoque / (Vendas 60d / 60)`, meta corporativa de 60 dias e alertas (`<= 15d` giro muito rápido vs `> 60d` excesso).

---

## 7. Responsividade e Critérios de Aceite WCAG AA

| Breakpoint | Comportamento do Layout |
| :--- | :--- |
| **Mobile (`320px / 375px / 414px`, `< 640px`)** | Coluna única vertical, padding `--space-4`, controles de preço e custo empilhados, 4 cards de decisão em 1 coluna, botões `min-height: 40px`, popover `<app-info-help>` em bottom sheet, zero scroll horizontal (`min-width: 0; overflow-wrap: anywhere`). |
| **Tablet (`640px – 1024px`)** | Cabeçalho compacto em wrap fluido, controles lado a lado ou empilhados conforme largura, cards em grade 2×2. |
| **Desktop (`> 1024px`)** | Busca compacta no topo + Calculadora Unificada em largura integral do workspace, grade 2×2 equilibrada, `15–20%` de respiro visual. |

**Critérios de Aceite (DoD Visual):**
- [ ] Zero referências a `<app-elasticity-diagnostic-card>` e `<app-elasticity-customers-table>` em `ElasticityPageComponent`.
- [ ] Todos os elementos consomem exclusivamente tokens de `styles.scss` e mixins de `_analytics-ui.scss` (Papel & Tinta).
- [ ] Contraste >= 4.5:1 em todos os textos (`--text-secondary` sobre fundos bege, `--text-on-brand` em tags escuras).
- [ ] Todos os 8 estados interativos e alvos de toque `>= 40px` validados em `320 / 375 / 414 / 768 px`.
- [ ] Nenhuma violação de `.agents/rules/frontend-ui-anti-patterns.md` nem regressão de `css:S8776` (`&` sempre no componente).
