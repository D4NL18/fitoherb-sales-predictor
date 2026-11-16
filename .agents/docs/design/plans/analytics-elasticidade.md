# Design Plan: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-elasticidade.md`
> **Responsável:** Designer (`designer`) / `uiux-expert`
> **Auditor:** UX Reviewer (`ux_reviewer`)
> **Status:** v2 — Camada Didática, Linguagem Acessível e Guias Contextuais (`<app-info-help>`)
> **Alinhamento:** `frontend/src/styles.scss`, `frontend/src/app/features/analytics/styles/_analytics-ui.scss` e `.agents/rules/frontend-ui-anti-patterns.md`

/* Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V4 */

---

## 1. Visão Geral e Filosofia Visual (Papel & Tinta + Clareza Didática)

A funcionalidade de Elasticidade-Preço atende gestores comerciais e usuários não especialistas dentro da shell compartilhada de Analytics, seguindo integralmente o sistema visual **Papel & Tinta** (editorial, sólido, sem gradientes genéricos, sem glassmorphism e sem cores Tailwind hardcoded):
- Superfícies em papel quente (`--bg-canvas: #F5F2EB`, `--bg-surface: #FFFFFF`, `--bg-subtle: #ECE7DC`, `--bg-muted: #E2DDD0`), tinta vegetal escura (`--text-primary: #181D19`) e verde botânico (`--brand-primary: #1D4528`).
- Tipografia oficial: títulos em `Signika` (`--font-family-headline`), corpo em `Source Sans 3` (`--font-family-body`) e números tabulares/códigos em `Overpass Mono` (`--font-family-mono`) com `tabular-nums` e formatação brasileira (`BrlPipe`, `PtDecimalPipe`, `PtPercentPipe`).
- **Camada Didática v2 (Divulgação Progressiva):** a página combina **linguagem cotidiana** nos rótulos principais, **traduções práticas imediatas** (ex.: efeito de `+10%` no preço e lucro unitário) e o componente contextual **`<app-info-help>`** (botão `"i"`) que preserva a profundidade estatística (`Beta`, `IC 95%`, `R²`, `Shrinkage Bayesiano`, diferença entre `Faturamento` e `Margem de Contribuição`) sem poluir a leitura principal.

---

## 2. Checklist Anti-IA (Filtro Anti-Slop)

- [x] **Sem "AI Purple":** nenhum gradiente azul-roxo; toda ênfase usa verde botânico `--brand-primary` (`#1D4528`) e neutros Papel & Tinta.
- [x] **Sem Glassmorphism no Popover:** `<app-info-help>` usa superfície sólida `--bg-surface` (`#FFFFFF`) com borda `--border-strong` e sombra seca `--shadow-lg`.
- [x] **Font Pairing Editorial:** `Signika` nos títulos (sem itálico em headers), `Source Sans 3` no texto e `Overpass Mono` nos valores.
- [x] **Copywriting Humano e Honesto:** zero buzzwords e zero métricas fictícias; exemplos nos guias são explicitamente hipotéticos (*"Ex.: se for -1,50..."*).
- [x] **Zero Spinners Solitários no Carregamento:** `<app-elasticity-skeleton>` espelha a geometria da tela.
- [x] **Zero Telas Vazias:** `<app-result-state>` cobre estado inicial, histórico insuficiente (`ELA-003`) e lista de clientes vazia.

---

## 3. Mapeamento de Linguagem Acessível (Camada Didática v2)

### 3.1 Cabeçalho e Estados (`elasticity-page.component.html`, `elasticity-view.ts`)
- **Eyebrow:** `Decisão de Preço & Lucro`
- **Título (`h2`):** `Simulador de Preço e Reação de Vendas` + `<app-info-help>` (`elasticityOverview`)
- **Subtítulo:** `Veja como os compradores reagem quando o preço muda e teste cenários de aumento ou desconto antes de decidir.`
- **Busca (`app-code-search-form`):** `label="Escolha o produto"`, `hint="Digite o código ou nome do produto e selecione na lista."`, `submitLabel="Analisar produto"`.
- **Estado Inicial (`buildElasticityInitialState`):** título `"Veja como o preço afeta as vendas antes de reajustar"`, texto orientado aos 3 passos (ver sensibilidade → testar reajuste → comparar clientes), CTA `"Escolher um produto"`.
- **Histórico Insuficiente (`buildElasticityInsufficientDataState`):** título `"Ainda não há histórico suficiente para este produto"`, explicando em linguagem simples a exigência mínima de meses regulares líquidos de devoluções.

### 3.2 Diagnóstico do Produto (`elasticity-diagnostic-card.component.html`)
- **Badges (`getClassificationMeta`, `getConfidenceMeta`):**
  - `ELASTICO` → `Muito sensível a preço` (`shortLabel` na tabela: `Sensível`)
  - `INELASTICO` → `Pouco sensível a preço` (`shortLabel` na tabela: `Pouco sensível`)
  - `ALTA` / `MEDIA` / `BAIXA` → `Confiança alta` / `Confiança média` / `Confiança baixa (usar com cautela)`
  - Cada badge tem `<app-info-help>` posicionado **fora** da pill `.tag` (wrapper `.badge-with-help`) para manter contraste sobre `--bg-surface`.
- **Avisos `role="note"`:**
  - `fallbackApplied`: `"Estimativa padrão de segurança (-1,20): como este produto quase não mudou de preço no passado (ou teve poucos meses de venda), não foi possível medir a reação real dos clientes. Aplicamos uma referência conservadora de mercado (-1,20) para evitar simulações irreais."`
  - `!isReliable`: `"Previsão com baixa precisão: as vendas passadas variaram por outros motivos além do preço. Use os resultados abaixo como ponto de partida junto com a visão comercial."`
- **4 Cards Métricos (`metrics-grid`):**
  1. `Sensibilidade ao preço` (`+ <app-info-help>`): exibe `coefficient` (`-1,45`) + tradução prática calculada em helper puro (`"A cada +10% no preço, o volume cai cerca de 14,5%"`).
  2. `Faixa provável de reação` (`+ <app-info-help>`): exibe intervalo `de -1,80 até -1,10` + tradução em `+10%` (`"Com +10% no preço, queda entre 11,0% e 18,0% · Erro padrão: ±0,18"`).
  3. `Qualidade do cálculo e histórico` (`+ <app-info-help>`): exibe `rSquared` (`58,0%`) + subtexto `"O preço explica 58,0% das variações de venda · 18 meses válidos"`.
  4. `Preço, Custo e Lucro Unitário` (`+ <app-info-help>`): exibe `currentPrice` + subtexto `"Custo: R$ 12,00 · Lucro por un.: R$ 13,50 (52,9%) · Estoque: 420 un."` (margem unitária calculada localmente sem nova chamada HTTP).
- **Insight Box:** prefixo `Resumo da análise:` seguido de `elasticity().insightMessage`.

### 3.3 Simulador de Impacto (`elasticity-simulator-panel.component.html`)
- **Título e subtítulo:** `Simulador de Reajuste de Preço` (`+ <app-info-help>`) · `Mova a barra ou escolha um percentual para ver na hora o efeito nas unidades vendidas, no faturamento e no lucro.`
- **Atalhos:** rótulo `Testar rápido:` com presets `-10%`, `-5%`, `0% (Atual)`, `+5%`, `+10%`, `+20%`.
- **Bloco de Cliente Selecionado (`customer-scope-card`):**
  - Título: `Simulação personalizada para este cliente` · Botão: `Voltar para visão geral do produto`.
  - Estatísticas `<dl>` com `<app-info-help>` em cada item:
    1. `Média geral do produto` (`productElasticity`)
    2. `Reação própria do cliente` (`customerEmpiricalElasticity`)
    3. `Sensibilidade usada na simulação` (`customerElasticity`, sub-rótulo `Média ajustada (Shrinkage)`) — popover explica por que mistura cliente e média do produto ($w = n / (n + 10)$).
    4. `Peso do histórico dele (n pedidos)` (`shrinkageWeight` + `totalUnits`) — popover traduz exemplos de $n = 3, 10, 30$ pedidos.
- **Slider:** label `Quanto você quer alterar no preço?` + marcas `-50%`, `0%`, `+50%`, `+100%` com legenda discreta (`Desconto` · `Preço atual` · `Aumento`).
- **Faixa Resumo:** `Preço atual` → `Preço projetado` + `Sensibilidade aplicada` (`+ <app-info-help>`).
- **3 Cards de Resultado:**
  1. `Quantidade prevista` (sub: `Volume projetado` + `<app-info-help>`)
  2. `Faturamento previsto` (sub: `Receita bruta` + `<app-info-help>` alertando sobre faturar vs lucrar)
  3. `Lucro bruto estimado` (sub: `Margem de Contribuição`, destaque `.sim-card-highlight` + `<app-info-help>` detalhando por que preço maior com menos unidades pode gerar mais lucro).
- **Barra de Recomendação:** prefixo `Recomendação:` + `sim.recommendation`.

### 3.4 Tabela de Clientes (`elasticity-customers-table.component.html`)
- **Cabeçalho:** eyebrow `Análise por comprador` · título `Como cada cliente reage ao preço` · subtítulo `Compare a sensibilidade de cada comprador e clique em "Simular" para testar um reajuste específico para ele.`
- **Faixa de Orientação Comercial (compacta acima da tabela):** resume em 3 pontos objetivos como usar `Pouco sensível` vs `Sensível` e a ordenação por Volume/Sensibilidade para priorizar reajustes sem perda de vendas.
- **Busca:** label `Buscar cliente pelo código` (`+ <app-info-help>` explicando filtro local na página vs `Consultar cliente` na base inteira `ELA-002`).
- **Cabeçalhos da tabela:** `Cód. Cliente` | `Pedidos` | `Volume (un.)` | `Peso histórico` (`+ <app-info-help>`) | `Reação própria` (`+ <app-info-help>`) | `Sensibilidade usada` (`+ <app-info-help>`) | `Perfil` (`+ <app-info-help>`) | `Ação`.

---

## 4. Especificação do Componente `<app-info-help>`

### 4.1 Localização e Segurança
- **Componente:** `frontend/src/app/features/analytics/components/info-help/info-help.component.ts` (`.html`, `.scss`), `ChangeDetectionStrategy.OnPush`.
- **Coordenador:** `InfoHelpCoordinatorService` (`providedIn: 'root'`) mantendo `activeHelpId = signal<string | null>(null)` para garantir **no máximo 1 popover aberto por vez**.
- **Copy tipada:** `frontend/src/app/features/analytics/utils/elasticity-help-copy.ts` com `InfoHelpContent { title, whatIs, howToAnalyze, insight, technicalNote? }`.
- **Segurança XSS:** **zero `[innerHTML]`** — renderização 100% via interpolação Angular e `@if`.

### 4.2 Anatomia, Posicionamento e Responsividade
- **Botão gatilho (`.info-help-trigger`):**
  - Círculo `20px × 20px` (`size="sm"`) ou `22px × 22px` (`size="md"`), ícone `"i"` SVG (`aria-hidden="true"`), `aria-label="Ajuda sobre {{ topicLabel() }}"`, `aria-expanded`, `aria-controls`.
  - Hit target acessível >= `40px` (`$touch-target`) via `::before { content: ''; position: absolute; inset: -10px; }` sem deformar `<th>` ou labels.
- **Popover (`.info-help-popover`, `role="dialog"`, `aria-modal="false"`):**
  - **Posicionamento `position: fixed` dinâmico (`getBoundingClientRect()`):** evita corte pelo `overflow-x: auto` da `.table-wrap`.
  - **Desktop/Tablet (`>= 640px`):** largura `min(340px, calc(100vw - 24px))`. Calcula alinhamento horizontal automático (`start` / `center` / `end`) respeitando margem de `12px` das bordas e faz flip vertical para cima se não couber abaixo. Recalcula em `scroll`/`resize` enquanto aberto.
  - **Mobile (`< 640px`):** assume apresentação em folha inferior ancorada (`left: var(--space-3); right: var(--space-3); bottom: var(--space-3); max-height: 75vh; overflow-y: auto;`) com backdrop translúcido neutro, evitando cortar em `320px`/`375px`/`414px` ou cobrir o campo de busca no topo.
- **Seções internas:** Header (Título + botão fechar `×`) → `O que é` → `Como analisar` → `Qual insight tirar` (caixa `--brand-primary-subtle` com borda `--brand-primary`) → `Detalhe técnico` (opcional, caixa `--bg-table-row-zebra` com texto `--text-secondary`).
- **Abertura/fechamento:** abre/fecha apenas por clique/toque/teclado (`Enter`/`Space`); fecha em `Escape` (devolvendo foco ao botão gatilho), clique fora (`document` pointerdown/click), clique em `×`, ou abertura de outro `<app-info-help>`.

---

## 5. Os 8 Estados Interativos Mandatórios

| Estado | Experiência Implementada |
| :--- | :--- |
| **1. Initial / Idle** | `<app-result-state>` (`buildElasticityInitialState`) sem chamada automática de API até que o usuário busque ou abra URL com `?sku=`. Botão foca o input de busca. |
| **2. Loading** | `<app-elasticity-skeleton>` fiel à geometria do diagnóstico, simulador e tabela com `aria-busy="true"` e `@include ui.reduced-motion`. |
| **3. Success** | Dados renderizados em `pt-BR` com traduções práticas, margens unitárias e região `p.sr-only[role="status"][aria-live="polite"]`. |
| **4. Empty** | Produto sem clientes individuais exibe `<app-result-state>` na tabela sem ocultar diagnóstico/simulador; filtro local vazio exibe botão `"Limpar filtro"`. |
| **5. Error** | `<app-error-banner>` amigável via `analytics-error.ts` (`ELA-001`..`ANL-002`) + retry; `ELA-003` renderiza estado de histórico insuficiente. |
| **6. Busy / Disabled** | Durante simulação em voo, slider permanece manipulável; atalhos e ações de linha ficam desabilitados e a grade recebe `aria-busy="true"`. `<app-info-help>` permanece legível sem bloquear o fluxo. |
| **7. Invalid** | Percentual fora de `[-50, 100]` ou SKU inválido marcam `aria-invalid="true"`, exibem alerta inline e bloqueiam chamadas HTTP inválidas. |
| **8. Partial / Low-Confidence** | Bloco `role="note"` contrastante explicando em linguagem cotidiana o fallback `-1,20` (`fallbackApplied`) ou baixa confiabilidade amostral (`!isReliable`). |

---

## 6. Tokens, Contraste WCAG AA e Acessibilidade

- **Tokens obrigatórios (`frontend/src/styles.scss`):**
  - `--bg-canvas`, `--bg-surface`, `--bg-subtle`, `--bg-muted`, `--bg-table-header`, `--bg-table-row-hover`, `--bg-table-row-zebra`.
  - `--brand-primary`, `--brand-primary-hover`, `--brand-primary-subtle`, `--brand-secondary-subtle`.
  - `--text-primary`, `--text-secondary`, `--text-on-brand`, `--border-subtle`, `--border-default`, `--border-strong`, `--border-focus`.
  - `--shadow-xs`, `--shadow-lg`, `--radius-xs`, `--radius-md`, `--radius-full`, `--transition-fast`.
- **Regras de contraste verificadas (>= 4.5:1):**
  - `--text-primary` (`#181D19`) sobre `--bg-surface` (`#FFFFFF`) e `--brand-primary-subtle` (`#E5EFE7`).
  - `--text-secondary` (`#434B44`) sobre `--bg-table-row-zebra` (`#FAF8F4`) e `--bg-subtle` (`#ECE7DC`) — **proibido `--text-muted` sobre fundos bege**.
  - `--text-on-brand` (`#FFFFFF`) sobre `--brand-primary` (`#1D4528`) e classes `.tag-*`.
- **Regras CSS / Sonar:** manter `&` sempre no arquivo do componente (nunca dentro de mixins em `_analytics-ui.scss`) e respeitar `@include ui.hover` e `@include ui.reduced-motion`.
