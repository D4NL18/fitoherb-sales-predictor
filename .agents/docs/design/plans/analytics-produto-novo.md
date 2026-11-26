# Design Plan: Viabilidade de Produto Novo — Conservadora (Fase F2)

- **Feature:** `analytics-produto-novo` (`feature/analytics-produto-novo`)
- **Rota Angular:** `/analytics/produto-novo` (rota filha lazy dentro de `AnalyticsShellComponent`)
- **Regras de Negócio:** `P-139` a `P-149` (`.agents/docs/business_rules/analytics-produto-novo.md`)
- **Contrato de API:** `.agents/docs/api_contracts/analytics-produto-novo.md` (`GET /api/v1/analytics/new-product/options` e `POST /api/v1/analytics/new-product/forecast`)
- **Decisões Arquiteturais:** `.agents/docs/adr/ADR-008-produto-novo.md`
- **Privacidade (LGPD):** `.agents/docs/privacy/analytics-produto-novo.md` (zero PII; `fields[]` sem eco de valores na resposta de erro)
- **Design System Fonte da Verdade:** **Papel & Tinta** definido em `frontend/src/styles.scss` e `frontend/src/app/features/analytics/styles/_analytics-ui.scss`

> [!IMPORTANT]
> **Precedência do Design System Real:** O arquivo `.agents/docs/design/DESIGN_SYSTEM.md` contém um rascunho legado (Slate/Teal/`Inter`/`Plus Jakarta Sans`) que **não é usado em produção**. A implementação real da aplicação em `frontend/src/styles.scss` e `frontend/src/index.html` usa exclusivamente o tema **Papel & Tinta** (`Signika`, `Source Sans 3`, `Overpass Mono`, papel `#F5F2EB`, tinta `#181D19` e verde-fito `#1D4528`). É **terminantemente proibido** usar `Inter`, `Plus Jakarta Sans`, Teal (`#0D9488`), cores hardcoded de fallback ou tokens inexistentes.

---

## Crítica Pré-Emissão (Auto-Auditoria Hallmark v1.1)

| Critério | Decisão do Design Plan |
| :--- | :--- |
| **Perfil e Persona** | Comprador Fitoherb em análise pré-compra de um item inédito (sem SKU cadastrado no ERP). |
| **Macroestrutura** | **Workbench Assimétrico (Esquerda-Direita)** dentro do `AnalyticsShellComponent` (`15–20%` de respiro visual, máximo 5 blocos visuais). |
| **4 Perguntas em 10s** | 1. É viável frente à margem mínima desejada? · 2. Quanto vende no cenário conservador vs piso `P10` e mediana `P50`? · 3. Quais lançamentos reais ancoram a previsão e por quê? · 4. A sazonalidade de F1 foi aplicada ou caiu em neutro? |
| **Anti-Viés de Otimismo (`P-149`)** | `marketCeiling.tetoMaduroP75` é segregado em bloco próprio abaixo da projeção mensal com rótulo explícito *"não utilizar como meta inicial de compra"* e nunca compete como meta principal. |
| **Honestidade de Dados (Copy Honesto)** | Não exibe termos TF-IDF grifados inventados nem contagem `{count}` não estruturada ou rota inexistente em `NEW-001`; cada elemento visual mapeia 1:1 para os campos reais de `NewProductForecastData`. |

---

## 1. Objetivos de UX & Arquitetura de Decisão (Dashboard Designer)

### User Story (`US-NEW`)
> **Como** comprador ou gestor da Fitoherb avaliando a introdução de um produto não cadastrado (sem SKU), **quero** simular a demanda conservadora mensal e a margem bruta prevista a partir de `Tipo`, `Fornecedor`, `Descrição` e `Preço`, **para** decidir com segurança a compra inicial sem comprometer capital de giro nem superestimar o giro.

### Hierarquia de Leitura em 3 Níveis (Padrão F/Z)
1. **Nível 1 (Veredito Imediato):** Selo obrigatório de estimativa conservadora + Card de Viabilidade (`financialViability`) exibindo `parecer`, tag de status (`viavel: true | false | null`), Demanda Conservadora Total (`aggregatedTotals.totalQuantity`), Receita Bruta Conservadora (`aggregatedTotals.totalRevenue`) e Margem Bruta (`financialViability.margemBrutaPercentual`).
2. **Nível 2 (Evolução Mensal e Faixas):** Gráfico SVG de faixas (`p10Quantity`, `conservativeQuantity`, `p50Quantity`) pareado com tabela ledger mês a mês (`monthlyForecast`) e bloco segregado `marketCeiling.tetoMaduroP75`.
3. **Nível 3 (Evidência e Explicabilidade):** Lista/tabela dos até 10 lançamentos similares reais (`similarsUsed`, `P-143.1`), com abertura de Drawer acessível para auditar os 3 scores (`scoreFornecedor` 25%, `scorePreco` 35%, `scoreTfidf` 40%) e `quantidadesPrimeirosMeses` (`P-144`).

---

## 2. Checklist Hallmark Anti-IA (Proibições Explícitas)

- [x] **Zero fontes ou paletas estranhas:** proibido `Inter`, `Plus Jakarta Sans`, Teal (`#0D9488`), roxo/indigo generativo, neon ou gradientes decorativos.
- [x] **Zero cores hardcoded ou tokens inventados:** proibidos hexes fora de `styles.scss` e tokens inexistentes como `--feedback-success-bg`, `--feedback-critical-text`, `--color-danger-bg` ou `.tag-success`.
- [x] **Zero fundos escuros com texto escuro:** todos os `--feedback-*-bg` em `styles.scss` são tons escuros sólidos desenhados exclusivamente para texto branco (`--text-on-brand`).
- [x] **Zero microcopy de hype:** proibido *"IA Mágica"*, *"Previsão Inteligente"*, *"Score Geral"* ou *"Alta Confiança"*.
- [x] **Zero dados fabricados:** `SimilarProductItem` retorna apenas `scoreFinal`, `scoreFornecedor`, `scorePreco` e `scoreTfidf`; é **proibido** fabricar chips de palavras-chave TF-IDF (como `"tintura"`, `"melissa"` ou `"50ml"`, inclusive porque termos de embalagem são removidos em `P-142.4`).
- [x] **Zero rotas inexistentes:** é **proibido** instruir o usuário a navegar para uma inexistente *"aba Tendência de Vendas"*; ações de recuperação permanecem no fluxo real (`/analytics/produto-novo`).
- [x] **Zero loading apenas com spinner:** usar skeletons estruturais (`.skeleton-box` / `.skeleton-line`) tanto no carregamento de `/options` quanto na simulação de `/forecast`.

---

## 3. Tokens Reais (Papel & Tinta) e Matriz de Contraste WCAG 2.1 AA

Todo SCSS da feature deve importar `@use '../../styles/analytics-ui' as ui;` e consumir exclusivamente as CSS Custom Properties de `frontend/src/styles.scss`:

### 3.1 Inventário Oficial de Tokens Consumidos

| Categoria | Tokens Exatos (`frontend/src/styles.scss`) | Uso Obrigatório na Feature |
| :--- | :--- | :--- |
| **Tipografia** | `--font-family-headline` (`Signika`), `--font-family-body` (`Source Sans 3`), `--font-family-mono` (`Overpass Mono`) | Títulos em `Signika`; formulários/mensagens em `Source Sans 3`; preços, margens, quantidades, scores e SKUs em `Overpass Mono` com `font-variant-numeric: tabular-nums`. |
| **Superfícies** | `--bg-canvas` (`#F5F2EB`), `--bg-surface` (`#FFFFFF`), `--bg-subtle` (`#ECE7DC`), `--bg-muted` (`#E2DDD0`), `--bg-table-header` (`#F0ECE1`), `--bg-table-row-hover` (`#F7F5EE`), `--bg-table-row-zebra` (`#FAF8F4`), `--bg-overlay` (`rgba(24, 28, 24, 0.55)`) | Canvas herdado do shell; painéis e cards em `--bg-surface`; prefixos `R$`/`%`, bloco P75 e trilhas secundárias em `--bg-subtle`/`--bg-muted`; backdrop do drawer em `--bg-overlay`. |
| **Textos** | `--text-primary` (`#181D19`), `--text-secondary` (`#434B44`), `--text-muted` (`#666F67`), `--text-on-brand` (`#FFFFFF`) | `--text-primary` para dados e títulos; `--text-secondary` para labels, cabeçalhos de tabela e qualquer texto sobre `--bg-subtle`/`--brand-primary-subtle`; `--text-muted` somente em microtextos sobre `--bg-surface` ou `--bg-canvas`. |
| **Marca & Ênfase** | `--brand-primary` (`#1D4528`), `--brand-primary-hover` (`#14321C`), `--brand-primary-active` (`#0E2414`), `--brand-primary-subtle` (`#E5EFE7`), `--brand-secondary` (`#8A4B14`), `--brand-secondary-subtle` (`#F9EFE5`) | Botão primário e série Conservadora em `--brand-primary`; selo conservador em `--brand-primary-subtle`; série Mediana `P50` em `--brand-secondary`. |
| **Bordas & Foco** | `--border-subtle` (`#DFD9CC`), `--border-default` (`#CBC3B2`), `--border-strong` (`#9E9686`), `--border-focus` (`#1D4528`) | Bordas de cards/inputs em `--border-default`; linhas de tabela em `--border-subtle`; anel `:focus-visible` `2px solid var(--border-focus)` com `outline-offset: 2px`. |
| **Feedback Sólido (Fundos Escuros)** | `--feedback-positive-bg` (`#185A2E`), `--feedback-warning-bg` (`#7A4607`), `--feedback-critical-bg` (`#8F1B1B`), `--feedback-info-bg` (`#1B4B7A`), `--feedback-neutral-bg` (`#3B423C`) + respectivos `--feedback-*-border` | **Uso dual estrito:** (a) como fundo sólido de `.tag-*` com texto obrigatoriamente `--text-on-brand` (`#FFFFFF`), OU (b) como cor de texto/borda/faixa lateral de `3px` sobre fundo claro `--bg-surface`. |
| **Classes Globais** | `.tag`, `.tag-dot`, `.tag-positive`, `.tag-warning`, `.tag-critical`, `.tag-info`, `.tag-neutral`, `.skeleton-box`, `.skeleton-line` | Reutilizadas diretamente sem redefinição local nos SCSS dos componentes. |
| **Espaçamento, Raio e Elevação** | `--space-1`..`--space-8`, `--radius-xs` (`3px`), `--radius-sm` (`5px`), `--radius-md` (`7px`), `--radius-full`, `--shadow-xs`, `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-modal`, `--transition-fast` | Padrão `@include ui.panel` (`--bg-surface`, `--border-default`, `--radius-md`, `--shadow-xs`). |

### 3.2 Regras Inegociáveis de Contraste (Bug Fixes Críticos)

> [!CAUTION]
> 1. **Nunca colocar texto escuro sobre `--feedback-*-bg`:** todas as variáveis `--feedback-*-bg` em `styles.scss` são escuras (`#185A2E`, `#7A4607`, `#8F1B1B`, `#1B4B7A`, `#3B423C`). Quando usadas como background (badges `.tag-*` e botões), o texto **deve** ser `var(--text-on-brand)` (`#FFFFFF`). Para cards, alertas e avisos claros, use `background: var(--bg-surface); border-left: 3px solid var(--feedback-*-bg); color: var(--text-primary);`.
> 2. **Nunca usar `--text-muted` sobre `--bg-subtle`, `--bg-table-header` ou `--brand-primary-subtle`:** `#666F67` sobre `#ECE7DC`, `#F0ECE1` ou `#E5EFE7` cai abaixo de `4.5:1` (`4.2:1` a `4.4:1`). Nesses fundos, use obrigatoriamente `var(--text-secondary)` (`#434B44`, contraste `> 7.2:1`).

| Elemento | Cor de Frente | Cor de Fundo | Contraste | Status |
| :--- | :--- | :--- | :--- | :--- |
| Texto principal & valores | `--text-primary` (`#181D19`) | `--bg-surface` (`#FFFFFF`) | `16.8 : 1` | AAA |
| Texto em selo conservador | `--text-primary` (`#181D19`) | `--brand-primary-subtle` (`#E5EFE7`) | `14.1 : 1` | AAA |
| Subtítulos em selo/cabeçalhos/prefixos | `--text-secondary` (`#434B44`) | `--bg-subtle` (`#ECE7DC`) / `--brand-primary-subtle` | `7.3 : 1` / `7.6 : 1` | AAA |
| Microtexto de apoio | `--text-muted` (`#666F67`) | `--bg-surface` (`#FFFFFF`) | `5.0 : 1` | AA |
| Botão primário / badge ativo | `--text-on-brand` (`#FFFFFF`) | `--brand-primary` (`#1D4528`) | `11.1 : 1` | AAA |
| Badge `.tag-positive` | `--text-on-brand` (`#FFFFFF`) | `--feedback-positive-bg` (`#185A2E`) | `8.2 : 1` | AAA |
| Badge `.tag-warning` | `--text-on-brand` (`#FFFFFF`) | `--feedback-warning-bg` (`#7A4607`) | `8.3 : 1` | AAA |
| Badge `.tag-critical` | `--text-on-brand` (`#FFFFFF`) | `--feedback-critical-bg` (`#8F1B1B`) | `8.4 : 1` | AAA |
| Badge `.tag-info` | `--text-on-brand` (`#FFFFFF`) | `--feedback-info-bg` (`#1B4B7A`) | `8.8 : 1` | AAA |
| Erro inline de formulário | `--feedback-critical-bg` (`#8F1B1B`) | `--bg-surface` (`#FFFFFF`) | `8.4 : 1` | AAA |
| Série Mediana `P50` no gráfico | `--brand-secondary` (`#8A4B14`) | `--bg-surface` (`#FFFFFF`) | `6.7 : 1` | AA+ |

---

## 4. Arquitetura de Componentes, Reuso Obrigatório & Performance Angular 18

### 4.1 Integração no Módulo `analytics`
- **Rota:** registrar `{ path: 'produto-novo', loadComponent: ... }` em `frontend/src/app/features/analytics/analytics.routes.ts` como rota filha de `AnalyticsShellComponent`.
- **Navegação do Shell:** adicionar entrada em `ANALYTICS_SECTIONS` no `AnalyticsShellComponent` (`label: 'Produto Novo'`, `path: '/analytics/produto-novo'`).
- **Hierarquia de Cabeçalhos (`WCAG 1.3.1`):** `AnalyticsShellComponent` já renderiza `<h1 class="hero-title">Análises de Vendas</h1>`. Portanto, **a feature NÃO cria outro `<h1>`** nem breadcrumb redundante; o título da seção usa `<h2>` (`Viabilidade de Produto Novo — Estimativa Conservadora`) e sub-blocos usam `<h3>`.

### 4.2 Mapa de Reuso Explícito (Sem Duplicação de Código)

| Artefato Existente em `features/analytics/` | Como Será Reutilizado / Estendido na Etapa 3 |
| :--- | :--- |
| `AnalyticsShellComponent` & `analytics.routes.ts` | Hospeda `/analytics/produto-novo`, fornece barra de seções e canvas `--bg-canvas`. |
| `styles/_analytics-ui.scss` (`@use '../../styles/analytics-ui' as ui;`) | Fornece `$bp-mobile` (`639.98px`), `$bp-tablet` (`1023.98px`), `$touch-target` (`40px`), mixins `panel`, `hover`, `reduced-motion`, `spinner`, `sr-only`, `caption` e placeholders `%button-base`, `%button-primary`, `%button-secondary`. |
| `components/error-banner/` (`ErrorBannerComponent`) | Reutilizado para erros de servidor/rede (`NEW-005` e falha de `GET /options`) com botão `Tentar novamente`. Na Etapa 3, adicionar input opcional `message = input<string>(...)` preservando a mensagem padrão atual do Cross-sell. |
| `components/result-state/` (`ResultStateComponent`) | Reutilizado para o Estado Inicial vazio, catálogo de `/options` vazio e `NEW-001` (base insuficiente com `tone: 'warning'`). Na Etapa 3, generalizar `ResultStateView`/`ResultStateAction` (em modelo compartilhado) adicionando ícone `'document'` e ação genérica sem quebrar o Cross-sell. |
| `utils/analytics-error.ts` | Estender `ANALYTICS_ERROR_CODES` com `'NEW-001'..'NEW-005'` e reutilizar `toAnalyticsApiError(err)` + `resolveFieldError(error, field)` para vincular `error.fields` aos campos do formulário. |
| `utils/pt-br-format.ts` & `pipes/pt-br-format.pipes.ts` | Reutilizar `brl` (`formatCurrency`), `ptDecimal` (`formatDecimal`), `ptPercent` (`formatPercent` — recebe razão `0..1` diretamente, ex.: `0.5506 | ptPercent:1` -> `"55,1%"`, **sem multiplicar por 100**) e `ptDate` (`formatIsoDate`). Adicionar helper único `parsePtBrNumber` em `utils/` para parsing monetário/percentual do formulário. |
| `services/analytics.service.ts` | Adicionar métodos tipados `getNewProductOptions()` e `simulateNewProductForecast(req)` apontando para `/api/v1/analytics/new-product/*`. |
| `components/list-pager/` (`ListPagerComponent`) | **Não utilizado por decisão YAGNI explícita:** `POST /forecast` retorna no máximo `TOP_K_SIMILARS = 10` itens (`P-143.1`), todos exibidos de uma vez em uma lista/tabela enxuta sem paginação artificial. |

### 4.3 Árvore de Componentes e Estratégia Reativa (Angular `^18.2.0`)

> [!NOTE]
> O repositório utiliza Angular `^18.2.0` (`frontend/package.json`), versão anterior a Signal Forms experimentais. O formulário utiliza **Signals nativos do Angular 18 com validação reativa tipada** (zero `any`), alinhado ao restante do módulo `analytics`.

- `NewProductPageComponent` (**Smart**, `ChangeDetectionStrategy.OnPush`):
  - Injeta `NewProductStore`; coordena `[attr.inert]="store.selectedSimilar() ? '' : null"` no container principal quando o Drawer está aberto; mantém região `aria-live="polite"` para anúncios de resultado/erro/reset.
- `NewProductStore` (Signals + RxJS `Subject` + `switchMap` + `takeUntilDestroyed()`):
  - Gerencia `optionsState` (`loading | error | ready`), `simulationState` (`idle | loading | success | insufficient | error`), `isDirtySinceLastResult` (aviso de resultado desatualizado ao editar após simular) e `selectedSimilar`.
  - Dispara `loadOptions$` e `simulate$` via `switchMap` + `takeUntilDestroyed()`: cliques rápidos ou re-envios cancelam automaticamente requisições anteriores em voo (zero *race condition* ou *double-submit*).
- `NewProductFormComponent` (**Dumb**, `ChangeDetectionStrategy.OnPush`):
  - Recebe `options`, `optionsLoading`, `optionsError`, `submitting`, `apiError`, `isDirtySinceResult`; emite `submitForecast`, `resetSimulation`, `formChanged`, `retryOptions`.
- `NewProductResultsComponent` (**Dumb**, `ChangeDetectionStrategy.OnPush`):
  - Renderiza Selo Conservador (`P-146.1`), aviso gracioso de Sazonalidade F1, Card de Viabilidade (`P-147`/`P-148`), `NewProductBandChartComponent` + tabela mensal, Bloco Segregado `marketCeiling.tetoMaduroP75` (`P-149`) e Lista Top-10 Similares (`similarsUsed`, `P-143.1`).
- `NewProductBandChartComponent` (**Dumb**, `ChangeDetectionStrategy.OnPush`):
  - Renderiza o SVG acessível de faixas (`p10Quantity`, `conservativeQuantity`, `p50Quantity`) com símbolos distintos e `aria-label` completo.
- `NewProductSimilarsDrawerComponent` (**Dumb**, `ChangeDetectionStrategy.OnPush`):
  - Painel lateral `role="dialog"` `aria-modal="true"` com **Focus Trap nativo**, `Escape`, fechamento por backdrop/`×` e restauração de foco para o botão `"Explicar"` acionador.

---

## 5. Anatomia Visual, Ergonomia e Regras de Renderização

### 5.1 Estrutura Global da Tela (Desktop `>= 1024px`)

```text
+---------------------------------------------------------------------------------------------------+
| [AnalyticsShellComponent: <h1> Análises de Vendas | Navegação: Cross-sell · Produto Novo]        |
+---------------------------------------------------------------------------------------------------+
| <h2> Viabilidade de Produto Novo — Estimativa Conservadora            Referência: DD/MM/AAAA      |
| Simule demanda inicial e margem antes da compra, sem precisar de SKU cadastrado.                  |
+-----------------------------------+---------------------------------------------------------------+
| WORKBENCH ESQUERDO (340–400px)    | WORKBENCH DIREITO (minmax(0, 1fr))                            |
|                                   |                                                               |
| [Se /options falhar -> ErrorBanner| [SELO OBRIGATÓRIO: --brand-primary-subtle + borda esquerda]   |
|  com Tentar novamente]            |  Estimativa Conservadora: calculada para proteger seu estoque |
| [Se /options carregando ->        |---------------------------------------------------------------|
|  Skeleton de Tipo/Fornecedor]     | [AVISO F1 SAZONALIDADE — se FALLBACK_NEUTRAL / UNAVAILABLE]   |
|                                   |  Sazonalidade neutra (1,00x): projeção sem ajuste sazonal.    |
| [1. Tipo do Produto *] <select>   |---------------------------------------------------------------|
| [2. Fornecedor *] Combobox ARIA   | [CARD DE VIABILIDADE (viavel: true | false | null)]           |
| [3. Descrição *] (3–120 chars)    |  Badge [.tag-positive/.tag-warning/.tag-neutral]              |
| [4. Preço de Venda Previsto *] R$ |  Demanda Total · Receita Conservadora · Margem · N Similares  |
| [5. Custo Unitário (opc.)] R$     |---------------------------------------------------------------|
| [6. Margem Mínima (opc.)] %       | [GRÁFICO DE FAIXAS SVG + TABELA LEDGER MENSAL (M1..Mx)]       |
| [7. Horizonte] (1m | 2m | *3m*)   |  ▽ P10 (tracejado) · ● Conservador (sólido) · □ P50 (pont.)   |
|                                   |  + Bloco Segregado P75: Referência Madura (não usar como meta)|
| [Simular Viabilidade] [Limpar]    |---------------------------------------------------------------|
|                                   | [LISTA TOP-10 SIMILARES] Linha -> [Explicar] -> abre Drawer   |
+-----------------------------------+---------------------------------------------------------------+
```

### 5.2 Ergonomia e Validação do Formulário Sem SKU (`NewProductFormComponent`)

| Campo (API `camelCase`) | Controle Acessível | Parsing, Escala & Validação Inline (pt-BR) | Casos de Borda |
| :--- | :--- | :--- | :--- |
| **`tipo`** *(obrigatório — `P-140.1`)* | `<select>` nativo alimentado por `options.tipos`, opção vazia `"Selecione o tipo..."` | Obrigatório. Erro inline se sair sem selecionar ou no submit (`"Selecione o tipo do produto para localizar lançamentos similares."`). Também mapeia erro backend `NEW-002` (`fields: ['tipo']`). | Se `/options` estiver carregando, exibir `.skeleton-line` (`height: 40px`) e bloquear submit; se `/options` retornar `tipos: []`, exibir `ResultStateComponent` informativo. |
| **`fornecedor`** *(obrigatório — `P-140.1`)* | **Combobox ARIA acessível** (`role="combobox"`, `aria-expanded`, `aria-controls`, `aria-activedescendant`, `aria-autocomplete="list"`) filtrando `options.fornecedores` | Obrigatório (`P-140.1` exige valor pertencente ao catálogo ativo). Suporta `ArrowDown`/`ArrowUp`/`Enter`/`Escape` e botão `"×"` (`40×40px`) para limpar filtro/seleção. Também mapeia `NEW-003` (`fields: ['fornecedor']`). | Ao digitar texto sem correspondência exata na lista de `options.fornecedores`, exibe feedback inline claro (`"Selecione um fornecedor ativo da lista."`) e não envia texto solto inválido. |
| **`descricao`** *(obrigatório — `P-140.1`)* | `<input type="text">` com contador `{{ len }}/120` em `--text-secondary` | Obrigatório; `trim().length` entre `3` e `120` caracteres (`NEW-004`). Hint: `"Sem SKU — informe nome, princípio ativo, volume ou linha (ex.: Tintura de Melissa 50ml)."` | Valores `< 3` ou `> 120` caracteres exibem erro inline claro (`"A descrição deve ter entre 3 e 120 caracteres."`). |
| **`precoVendaPrevisto`** *(obrigatório — `P-140.1`)* | `<input type="text" inputmode="decimal">` com prefixo visual `R$` (`--bg-subtle` + `--text-secondary`) | Aceita vírgula ou ponto (`49,90`, `1.299,00`, `49.90`); formata em `pt-BR` no `blur`. Deve ser numérico finito `> 0` (`NEW-004`). | Mensagem para `<= 0`, `NaN` ou vazio: `"Informe um preço de venda previsto maior que R$ 0,00."` |
| **`custoUnitario`** *(opcional — `P-140.2`)* | `<input type="text" inputmode="decimal">` com prefixo `R$` | Opcional. Se preenchido, deve ser numérico finito `> 0,00` e `<= precoVendaPrevisto` (`P-140.2`, `NEW-004`). | **Caso `custoUnitario <= 0`:** erro inline (`"Quando informado, o custo unitário deve ser maior que R$ 0,00."`).<br>**Caso `custoUnitario > precoVendaPrevisto`:** erro inline em `--feedback-critical-bg` (`"O custo unitário não pode ser maior que o preço de venda previsto."`), bloqueando submit.<br>**Caso `custoUnitario === precoVendaPrevisto`:** envio **permitido** (`margemBrutaPercentual = 0.00`); exibe dica informativa em `--feedback-warning-bg` (`"Com custo igual ao preço, a margem bruta prevista é 0,00%."`). |
| **`margemMinimaDesejada`** *(opcional — `P-140.2`)* | `<input type="text" inputmode="decimal">` com sufixo `%` (`--bg-subtle` + `--text-secondary`) | UI exibe percentual humano `0` a `100` (ex.: `35,0%`); **ao serializar `NewProductForecastRequest`, divide por `100`** (`35,0` -> `0.35`) conforme contrato (`0.00` a `1.00`, `NEW-004`). | **Caso `margemMinimaDesejada` preenchida sem `custoUnitario`:** envio **permitido** (`viavel: null`), com nota inline em `--feedback-info-bg` (`"Informe também o custo unitário para avaliar se esta margem mínima será atingida."`). |
| **`horizonMonths`** *(obrigatório — `P-140.2`)* | `<fieldset>` + `<legend>` com radiogroup segmentado (`1 mês`, `2 meses`, `3 meses`; padrão `3`) | Botões de rádio estilizados com alvo mínimo `>= 40px` de altura e destaque `--brand-primary` quando selecionado. | Garante `{1, 2, 3}` sem estados inválidos. |

- **Botão `Limpar simulação` (`%button-secondary`):** limpa campos para o padrão (`horizonMonths: 3`), remove resultados/erros e devolve foco ao `<select>` de `Tipo` anunciando `"Simulação limpa."` na região `aria-live="polite"`.
- **Proteção de Resultado Desatualizado (Stale State):** se já existe simulação visível e o usuário altera qualquer campo antes de clicar em `"Simular Viabilidade"`, a área de resultados exibe uma barra sutil no topo (`--bg-subtle`, `border-left: 3px solid var(--brand-secondary)`, `--text-primary`): `"Parâmetros alterados — clique em 'Simular Viabilidade' para atualizar as projeções."`

### 5.3 Selo Conservador, Degradação Graciosa de Sazonalidade F1 e Viabilidade

1. **Selo Obrigatório (`P-146` / `P-145`):**
   - Fundo `--brand-primary-subtle` (`#E5EFE7`), borda esquerda `4px solid var(--brand-primary)` (`#1D4528`), ícone de escudo (`aria-hidden="true"`), título em `--text-primary` (`Signika 600`): **"Estimativa Conservadora: calculada para proteger seu estoque"**, e subtítulo em `--text-secondary` (`#434B44`): exibindo `methodologyNotice` (fallback padrão: *"Projeção calibrada abaixo do 1º quartil histórico (`P25 × 0,70`), nunca superando o piso inferior dos lançamentos similares."*).
2. **Degradação Graciosa da Sazonalidade de F1:**
   - Quando `seasonalityStatus === 'FALLBACK_NEUTRAL'` ou `'UNAVAILABLE'` (ou algum mês retorna `seasonalityConfidence` igual a `'BAIXA'`, `'INSUFICIENTE'` ou `'PADRAO'`), exibir imediatamente abaixo do selo um callout informativo claro (`background: var(--bg-surface); border-left: 3px solid var(--feedback-info-bg); color: var(--text-primary)`):
     - *"Sazonalidade aplicada em fator neutro (1,00×): histórico sazonal da categoria ainda indisponível ou com confiança baixa. A previsão utiliza apenas a curva real dos produtos similares."*
   - Quando `seasonalityStatus === 'APPLIED'` (`ALTA`/`MEDIA`), mostrar descrição discreta junto à tabela mensal indicando os fatores amortecidos (`[0,90× – 1,10×]`).
3. **Cartão de Viabilidade (`financialViability`, `P-148`):**
   - Fundo `--bg-surface`, borda `1px solid var(--border-default)` + acento lateral `3px` conforme `financialViability.viavel` e presença de `custoUnitario`:
     - `viavel === true`: borda `--feedback-positive-bg` + tag `.tag.tag-positive` (`Viável para Lançamento`)
     - `viavel === false`: borda `--feedback-warning-bg` + tag `.tag.tag-warning` (`Margem Abaixo do Esperado`)
     - `viavel === null` com `custoUnitario == null`: borda `--feedback-neutral-bg` + tag `.tag.tag-neutral` (`Simulação de Demanda (sem custo)`)
     - `viavel === null` com `custoUnitario != null`: borda `--feedback-info-bg` + tag `.tag.tag-info` (`Margem Calculada (sem meta mínima)`)
   - Subtítulo com `financialViability.parecer` (quando presente).
   - Grade de 4 métricas em `--font-family-mono` (`tabular-nums`):
     1. **Demanda Conservadora (M1–M{{ horizonMonths }})**: `{{ aggregatedTotals.totalQuantity | ptDecimal:0 }} un` (média `{{ aggregatedTotals.averageMonthlyQuantity | ptDecimal:0 }} un/mês`)
     2. **Receita Bruta Conservadora**: `{{ aggregatedTotals.totalRevenue | brl }}`
     3. **Margem Bruta Prevista**: `{{ financialViability.margemBrutaPercentual | ptPercent:1 }}` (exibe `—` + nota `"Informe o custo unitário"` quando `null`; exibe comparação `Meta: {{ financialViability.margemMinimaDesejada | ptPercent:1 }}` quando informada; atenção: **`ptPercent` recebe fração `0..1`, nunca multiplicar por `100`**!)
     4. **Base de Similares**: `{{ similarsUsed.length }} lançamentos` + botão secundário `"Ver detalhes dos similares"` (`min-height: 40px`)

### 5.4 Gráfico Acessível de Faixas + Tabela Mensal + Bloco Segregado P75

- **Regra Colorblind-Safe & Anti-Viés (`P-147` / `P-149`):** O SVG renderiza **exclusivamente as 3 séries de faixa de lançamento** (`p10Quantity`, `conservativeQuantity`, `p50Quantity`) para evitar que o olho do comprador ancore no teto maduro. A área sombreada entre `P10` e `P50` usa preenchimento sutil `--brand-primary-subtle` com `fill-opacity: 0.45`.
  - **`P10` (Piso Pessimista — `p10Quantity`):** traço tracejado (`stroke-dasharray="5 4"`), cor `--text-secondary` (`#434B44`), marcador **triângulo invertido `▽`**.
  - **`Conservador` (Previsão Oficial — `conservativeQuantity`):** traço sólido espesso (`2.5px`), cor `--brand-primary` (`#1D4528`), marcador **círculo sólido `●`** + rótulo numérico destacado junto ao ponto.
  - **`Mediana P50` (Desempenho Típico — `p50Quantity`):** traço pontilhado longo (`stroke-dasharray="8 4"`), cor `--brand-secondary` (`#8A4B14`), marcador **quadrado vazado `□`**.
  - **`Teto Maduro (P75)` (`marketCeiling.tetoMaduroP75`):** **não** aparece competindo na curva principal de lançamento para cumprir `P-147.3`.
- **Acessibilidade do SVG:** `<svg role="img" [attr.aria-label]="chartAriaSummary">` acompanhado imediatamente pela **Tabela Ledger Mensal** (`<table class="forecast-ledger">` com `<caption class="sr-only">`, `<th scope="col">`, `<th scope="row">`) contendo:
  - Colunas: `Mês` (`M{{ item.month }}` + mês civil abreviado quando `calendarMonth` presente, ex. `M1 · Nov`), `Sazonal.` (`{{ item.seasonalityFactor | ptDecimal:2 }}×` + indicador neutro se fallback), `P10 (▽)`, **`Conservador (● Oficial)`**, `Mediana P50 (□)` e `Receita Conservadora` (`item.revenue | brl`).
- **Bloco Segregado `Teto Maduro (P75)` (`marketCeiling`, `P-147.2` / `P-147.3`):**
  - Caixa isolada abaixo da tabela com `background: var(--bg-subtle); border: 1px solid var(--border-subtle); color: var(--text-secondary);`:
  - Título `Signika 600` em `--text-primary`: **"Referência Histórica de Maturidade (`P75`) — Não utilizar como meta inicial"**
  - Valor: `{{ marketCeiling.tetoMaduroP75 | ptDecimal:0 }} un/mês` + `marketCeiling.descricao`.

### 5.5 Lista Top-10 Similares (`similarsUsed`) & Drawer de Explicabilidade Acessível

- **Lista Top-10 Similares (Desktop Ledger / Mobile Cards):**
  - Cabeçalho com resumo de critério: *"Top {{ similarsUsed.length }} lançamentos similares do mesmo Tipo (Fornecedor 25%, Log-Preço 35% e Descrição TF-IDF 40%; devoluções já abatidas)."*
  - Colunas (Desktop): `Produto` (`descricao` + `sku` em mono `--text-secondary`), `Fornecedor`, `Preço` (`precoHistorico | brl`), `Líquido M1 / M2 / M3` (`quantidadesPrimeirosMeses[0..2]`, com fallback `—` se ausente), `Similaridade` (`{{ scoreFinal | ptPercent:1 }}` + barra horizontal `--brand-primary` em `--bg-muted`) e ação `Explicar` (`%button-secondary`, `min-height: 40px`).
- **Drawer de Explicabilidade (`NewProductSimilarsDrawerComponent`):**
  - **Semântica & Focus Trap (sem dependência externa `@angular/cdk`):**
    1. Container do drawer com `role="dialog"`, `aria-modal="true"`, `aria-labelledby="drawer-similar-title"`, `aria-describedby="drawer-similar-subtitle"`.
    2. Enquanto aberto, o wrapper principal da página recebe `[attr.inert]="store.selectedSimilar() ? '' : null"` e o backdrop (`--bg-overlay`) bloqueia cliques fora do painel.
    3. **Focus Trap nativo (`Tab` / `Shift+Tab`):** listener no elemento dialog mantém o foco ciclando exclusivamente entre os elementos focáveis internos (botão `×` fechar e controles internos).
    4. **Fechamento & Restauração de Foco:** tecla `Escape`, clique no backdrop `--bg-overlay` ou botão `×` (`aria-label="Fechar detalhamento do produto similar"`, `40×40px`) fecham o drawer e **devolvem `.focus()` ao botão `Explicar` exato que disparou a abertura**. Ao abrir, o foco inicial vai para o botão `×` (ou título com `tabindex="-1"`).
  - **Conteúdo do Drawer (Fidelidade 100% ao Contrato):**
    - Cabeçalho: `descricao`, `sku`, `inputSummary.tipo`, `fornecedor`, `precoHistorico` (`brl`) e `primeiraVenda` (`ptDate`).
    - Comparação lado a lado (*Produto Simulado* vs *Similar Histórico*): `Tipo` (idêntico), `Fornecedor` (`.tag-positive` *"Mesmo fornecedor"* quando `scoreFornecedor === 1` vs `.tag-neutral` *"Fornecedor diferente"*), `Preço` (`inputSummary.precoVendaPrevisto | brl` vs `precoHistorico | brl`) e `Descrição` completa de ambos — **sem tokens TF-IDF grifados fabricados**.
    - Decomposição do Score:
      - **Descrição / Texto TF-IDF (peso 40%):** `scoreTfidf | ptPercent:1` + barra `--brand-primary`
      - **Proximidade Log-Preço (peso 35%):** `scorePreco | ptPercent:1` + barra `--brand-primary`
      - **Mesmo Fornecedor (peso 25%):** `scoreFornecedor | ptPercent:0` (`0%` ou `100%`) + barra
      - **Score Composto Final:** `scoreFinal | ptPercent:1` (`0,25×F + 0,35×P + 0,40×T`)
    - **Histórico Líquido de Lançamento (`M1`, `M2`, `M3`):** barras horizontais proporcionais com `quantidadesPrimeirosMeses` em `tabular-nums`, explicitando que devoluções (`DEVOLU%`) já foram deduzidas (`P-144.2`).

---

## 6. Os 8 Estados Interativos, Erros `NEW-001`–`NEW-005` e Matriz por Elemento

### 6.1 Cobertura Integral dos 8 Estados Obrigatórios

| # | Estado | Gatilho / Condição | Comportamento Visual, Tokens & Reuso | Acessibilidade & Recuperação |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Inicial** | Tela recém-aberta; `/options` pronto (`tipos.length > 0`), nenhuma simulação executada | Form pronto (`horizonMonths: 3`). Painel direito exibe `ResultStateComponent` (`tone: 'neutral'`, `icon: 'document'`): *"Simule um lançamento sem precisar de SKU"*. Enquanto `/options` carrega, campos `Tipo`/`Fornecedor` mostram `.skeleton-line` (`aria-busy="true"`). | `aria-live="polite"`; foco natural no `<select>` de Tipo ou fluxo sequencial. |
| **2** | **Preenchido Válido** | Campos obrigatórios válidos (`tipo`, `fornecedor`, `descricao`, `precoVendaPrevisto`) + opcionais válidos | Botão `"Simular Viabilidade"` habilitado em `--brand-primary`. Se houver resultado anterior e usuário editar qualquer campo, faixa discreta indica resultado desatualizado (*stale*). | Zero mensagens de erro; dica informativa se `custoUnitario === precoVendaPrevisto` ou margem sem custo. |
| **3** | **Preenchido Inválido (`NEW-002`/`003`/`004`)** | Erro inline (antes ou via resposta `400` com `fields[]`) | Borda `1.5px solid var(--feedback-critical-bg)` no(s) input(s) inválido(s) + texto abaixo do campo em `--feedback-critical-bg` (`role="alert"`) usando `resolveFieldError(error, field)`. Preserva todos os dados digitados. | `aria-invalid="true"`, `aria-describedby` apontando para o erro e foco movido ao primeiro campo inválido no submit. |
| **4** | **Carregando (Skeleton)** | Submit válido em voo (`POST /forecast`) | Botão `"Simular Viabilidade"` desabilitado com `@include ui.spinner` + *"Calculando projeção..."*. Painel direito renderiza skeleton estrutural (`.skeleton-box`/`.skeleton-line`) replicando selo, 4 KPIs, gráfico e 4 linhas de tabela. | `aria-busy="true"` na região de resultados; `switchMap` cancela chamadas anteriores caso haja re-disparo programático. |
| **5** | **Sucesso (`200 OK`)** | Retorno válido (`viavel: true`, `false` ou `null`) | Renderiza Selo Conservador, aviso opcional de sazonalidade F1, Card de Viabilidade, Gráfico SVG + Tabela Mensal, Bloco P75 e Top-10 Similares. | Anúncio resumido em `aria-live="polite"` (*"Simulação concluída: N unidades conservadoras e parecer ..."*). |
| **6** | **Base Insuficiente (`NEW-001`)** | API retorna `422` `code: 'NEW-001'` (`< 3` similares no `Tipo`) | **Nunca** estilizado como erro fatal de sistema. Renderiza `ResultStateComponent` (`tone: 'warning'`, fundo `--bg-surface`, borda lateral `--feedback-warning-bg`) exibindo `error.message` sem inventar `{count}` no cliente e explicando o corte `01/04/2025` + `3 meses`. | Botão `"Escolher outro Tipo"` (`min-height: 44px`) foca diretamente o `<select>` de `Tipo`, mantendo os demais campos intactos. |
| **7** | **Vazio** | Pré-simulação ou `GET /options` retorna `tipos: []` ou `fornecedores: []` | Pré-simulação usa `ResultStateComponent` inicial; se catálogo vier vazio, exibe `ResultStateComponent` explicando ausência de opções elegíveis no catálogo e desabilita o submit. | `aria-live="polite"` informando indisponibilidade de opções elegíveis. |
| **8** | **Erro de Servidor / Rede (`NEW-005` / `/options`)** | `500`, `503`, timeout ou rede fora do ar | Renderiza `ErrorBannerComponent` (`--bg-surface`, borda esquerda `--feedback-critical-bg`, `role="alert"`) com mensagem amigável (zero stacktrace) e botão `"Tentar novamente"`. Todos os inputs digitados permanecem intactos. | Clique em `"Tentar novamente"` reexecuta `loadOptions()` (se erro no `/options`) ou `simulate()` (se erro no `/forecast`). |

### 6.2 Matriz de Estados por Elemento Interativo

| Elemento | Default | Hover | Focus-Visible | Active | Disabled / Loading | Erro |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Botão Primário (`Simular Viabilidade`)** | `--brand-primary` + `--text-on-brand` | `--brand-primary-hover` (`@include ui.hover`) | `outline: 2px solid var(--border-focus); outline-offset: 2px` | `--brand-primary-active` | `opacity: 0.65`, `cursor: not-allowed`, spinner inline + `aria-busy` | N/A (desabilitado se catálogo `/options` falhou) |
| **Botão Secundário (`Limpar`, `Explicar`, `Escolher outro Tipo`)** | `--bg-surface`, borda `--border-default`, `--text-primary` | `--bg-subtle` + `--border-strong` | `outline: 2px solid var(--border-focus); outline-offset: 2px` | `--bg-muted` | `opacity: 0.55`, `pointer-events: none` | N/A |
| **Select `tipo` & Inputs `descricao`/`preco`/`custo`/`margem`** | `--bg-surface`, borda `--border-default`, `--text-primary` | Borda `--border-strong` | Borda `--border-focus` + `box-shadow: 0 0 0 2px var(--brand-primary-subtle)` | N/A | `--bg-subtle` + `.skeleton-line` durante carga inicial de `/options` | Borda `1.5px solid var(--feedback-critical-bg)` + `aria-invalid="true"` |
| **Combobox `fornecedor`** | `--bg-surface`, listbox fechada | Borda `--border-strong`; item hover `--bg-table-row-hover` | Anel `--border-focus`; opção ativa `--brand-primary-subtle` | Opção selecionada com check `--brand-primary` | `.skeleton-line` enquanto `/options` carrega | Borda `1.5px solid var(--feedback-critical-bg)` + `aria-invalid="true"` (se vazio ou fora do catálogo) |
| **Radiogroup `horizonMonths`** | `--bg-surface`, borda `--border-default`; selecionado `--brand-primary` + `--text-on-brand` | `--bg-subtle` (não selecionado) | Anel `--border-focus` ao focar o input radio | `--brand-primary-active` | `opacity: 0.6` durante simulação | N/A |
| **Linha / Botão `Explicar` (Top-10)** | Linha `--bg-surface`/`--bg-table-row-zebra` | Linha `--bg-table-row-hover` | Anel `--border-focus` no botão `Explicar` | Fundo `--brand-primary-subtle` na linha selecionada | Desabilitado enquanto requisição de nova simulação estiver em voo | N/A |
| **Drawer Close (`×`) & Backdrop** | Botão `×` `40×40px` transparente sobre `--bg-surface` | `--bg-subtle` | Anel `--border-focus` | `--bg-muted` | N/A | `Escape` e clique no `--bg-overlay` sempre fecham |

---

## 7. Acessibilidade (WCAG 2.1 AA) & Performance Angular

- **Landmarks e Leitores de Tela:**
  - `<h2>` no cabeçalho da página (respeitando `<h1>` do `AnalyticsShellComponent`), `<form [attr.aria-busy]="...">`, `<fieldset>`/`<legend>` no horizonte, `<table class="forecast-ledger">` com `<caption class="sr-only">` e `<th scope="col">`/`<th scope="row">`.
  - Região dedicada `<div class="sr-only" aria-live="polite" aria-atomic="true">` anunciando início/conclusão da simulação, limpeza e erro `NEW-001`.
- **Keyboard-Only Navigation:**
  - Ordem lógica de `Tab`: Navegação do Shell -> `Tipo` -> `Fornecedor` (combobox completo por teclado) -> `Descrição` -> `Preço` -> `Custo` -> `Margem Mínima` -> `Horizonte` -> `Simular` -> `Limpar` -> `Ver detalhes dos similares` / botões `Explicar` -> dentro do Drawer (`Focus Trap`) com retorno ao botão gatilho no `Escape`.
- **Movimento Reduzido:** animações de skeleton e transição de abertura do Drawer devem respeitar `@include ui.reduced-motion` (`animation: none; transition: none;`).
- **Qualidade Angular 18 (para Etapa 3):**
  - `ChangeDetectionStrategy.OnPush` em **todos** os componentes.
  - Zero `any` em modelos, stores e templates; `@for (...; track ...)` obrigatório.
  - `switchMap` + `takeUntilDestroyed()` no `NewProductStore` garantindo cancelamento de chamadas sobrepostas e prevenção de memory leaks.

---

## 8. Responsividade Multidevice (Breakpoints de `_analytics-ui.scss`)

| Breakpoint | Largura | Adaptação de Layout e Componentes |
| :--- | :--- | :--- |
| **Desktop Amplo** | `>= 1280px` | Workbench `400px` (Form) + `minmax(0, 1fr)` (Resultados); grade 4 KPIs em 1 linha (`repeat(4, minmax(0, 1fr))`); tabela mensal e Top-10 completas; Drawer `460px` fixo à direita. |
| **Desktop Compacto** | `1024px – 1279px` | Workbench `minmax(340px, 370px) minmax(0, 1fr)`; grade 4 KPIs em `2×2`; tabelas com espaçamento compacto; Drawer `440px`. |
| **Tablet** (`max-width: ui.$bp-tablet`) | `640px – 1023.98px` | Empilhamento vertical em 1 coluna (Form topo -> Resultados abaixo); KPIs em `2×2`; tabela mensal legível com wrapper `overflow-x: auto` defensivo; Drawer `420px`. |
| **Mobile** (`max-width: ui.$bp-mobile`) | `<= 639.98px` (`320px`, `375px`, `414px`) | Empilhamento total em 1 coluna sem scroll horizontal na janela; KPIs em `1` coluna; botões `"Simular Viabilidade"` e `"Limpar simulação"` em largura total (`min-height: 44px`); **tabela mensal e lista Top-10 Similares transformam-se em cards empilhados** (cada card similar mostra descrição, fornecedor, preço, `M1/M2/M3`, barra de score e botão `"Explicar"` `100%` largura `>= 44px`); Drawer ocupa `100%` da largura (`100vw`) com cabeçalho sticky e botão `×` `44×44px`. Todos os alvos interativos `>= 40px` (`ui.$touch-target`). |

---

## 9. Copy Deck Oferecido em Português (`pt-BR`)

- **Título da Seção (`<h2>`):** `Viabilidade de Produto Novo — Estimativa Conservadora`
- **Subtítulo:** `Simule a demanda inicial de produtos sem SKU usando o histórico real de lançamentos similares.`
- **Selo Conservador:** `Estimativa Conservadora: calculada para proteger seu estoque`
- **Sazonalidade Neutra (F1 indisponível / confiança baixa):** `Sazonalidade aplicada em fator neutro (1,00×): histórico sazonal da categoria indisponível ou com confiança baixa. Projeção baseada integralmente nos similares de lançamento.`
- **Tags de Viabilidade:**
  - `viavel === true`: `Viável para Lançamento`
  - `viavel === false`: `Margem Abaixo do Esperado`
  - `viavel === null` (sem custo): `Simulação de Demanda (sem custo)`
  - `viavel === null` (com custo, sem meta): `Margem Calculada (sem meta mínima)`
- **Bloco Referência P75:** `Referência Histórica de Maturidade (P75) — Não utilizar como meta inicial`
- **Estado Inicial (`ResultStateComponent`):**
  - Título: `Simule um lançamento sem precisar de SKU`
  - Corpo: `Selecione o Tipo e o Fornecedor, descreva o produto e informe o preço previsto. O sistema projeta o volume conservador de compra a partir de lançamentos reais recentes.`
- **Erro `NEW-001` (`ResultStateComponent` `tone: 'warning'`):**
  - Título: `Base histórica insuficiente neste Tipo`
  - Corpo: exibe `error.message` retornado pela API + complemento orientativo: `É necessário haver ao menos 3 lançamentos recentes (desde 01/04/2025 com mínimo de 3 meses de histórico).`
  - Ação: `Escolher outro Tipo`
- **Erro `NEW-005` / Falha `/options` (`ErrorBannerComponent`):**
  - Título: `Não foi possível concluir a simulação agora`
  - Corpo: exibe `error.message` amigável (sem detalhes técnicos) mantendo todos os campos preenchidos.
  - Ação: `Tentar novamente`

---

## 10. Checklist de Alinhamento UI ↔ Contrato API ↔ Regras `P-139` a `P-149`

- [x] Sem SKU na entrada (`P-140`): formulário usa exclusivamente `tipo`, `fornecedor`, `descricao`, `precoVendaPrevisto`, `custoUnitario`, `margemMinimaDesejada`, `horizonMonths`.
- [x] Fonte dinâmica obrigatória de `Tipo` e `Fornecedor`: `GET /analytics/new-product/options` (`P-140.1`, `P-141`, erros `NEW-002` / `NEW-003`).
- [x] Conversão transparente `margemMinimaDesejada`: UI aceita `0–100%` e envia `0.00–1.00` na requisição (`P-140.2`, `NEW-004`).
- [x] Devoluções abatidas e histórico `M1..M3`: exibidos fielmente via `quantidadesPrimeirosMeses` (`P-144`).
- [x] Explicabilidade dos 3 pesos (`0,25` `scoreFornecedor`, `0,35` `scorePreco`, `0,40` `scoreTfidf`): exibida no Drawer sem fabricar tokens inexistentes (`P-142`, `P-143.3`).
- [x] Degradação graciosa F1: consome `seasonalityStatus` e `seasonalityConfidence` sem falhar quando neutro (`P-146`).
- [x] Trava anti-otimismo (`P-145`, `P-147.3`): selo obrigatório + `marketCeiling.tetoMaduroP75` segregado e marcado como não-meta.
- [x] Viabilidade opcional (`P-148`): trata `viavel: true`, `false` e `null` (com e sem `custoUnitario`), além da borda `custoUnitario === precoVendaPrevisto` (`0,00%`).
- [x] Envelope de erros LGPD-05 (`{ error: { code, message, fields } }`): mapeado via `analytics-error.ts` sem ecoar valores digitados.

---

## 11. Critérios de Aceite para o UX Reviewer (Gate Etapa 4)

1. Nenhuma fonte estranha (`Inter`, `Plus Jakarta Sans`), nenhuma cor hardcoded nem tokens inventados (`--feedback-success-bg`, `.tag-success`, `--feedback-critical-text`) em `.html`/`.scss`.
2. Nenhum bloco usa `--feedback-*-bg` com texto escuro; todas as `.tag-*` usam `--text-on-brand`, e nenhum `--text-muted` aparece sobre `--bg-subtle` ou `--brand-primary-subtle`.
3. Reuso comprovado de `AnalyticsShellComponent`, `ErrorBannerComponent`, `ResultStateComponent`, `analytics-error.ts`, `pt-br-format` (usando `ptPercent` sobre razão `0..1` sem `* 100`) e `_analytics-ui.scss` (`ChangeDetectionStrategy.OnPush`, `switchMap` + `takeUntilDestroyed`, zero `any`).
4. Formulário com `/options` skeleton + retry, `tipo` em `<select>` e `fornecedor` obrigatório em combobox ARIA acessível, validação pt-BR inline, botão `Limpar simulação` e bloqueio de double-submit.
5. Gráfico SVG com legenda diferenciada por forma + traço + cor, `aria-label` completo, tabela ledger pareada, bloco segregado `P75` e aviso gracioso de sazonalidade F1.
6. Drawer com `role="dialog"`, `aria-modal="true"`, Focus Trap, `[attr.inert]`, fechamento via `Escape` e restauração exata do foco ao gatilho.
7. Todos os 8 estados e larguras `320px`, `375px`, `768px`, `1024px`, `1280px` validados sem overflow horizontal e com alvos `>= 40px`.
