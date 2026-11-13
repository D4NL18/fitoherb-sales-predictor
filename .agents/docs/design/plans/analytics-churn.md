# Design Plan — Analytics Comercial · F3 Churn de Clientes com Score de Prioridade

<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 · macrostructure: workbench analítico com ledger ranqueado, kpis de impacto, drawer acessível com diagnóstico completo, paginação padronizada e exportação CSV segura -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | US-F3 — Detecção e Priorização de Churn de Clientes por Urgência e Receita |
| **Branch** | `feature/analytics-churn` |
| **Regras** | `.agents/docs/business_rules/analytics-churn.md` (P-117 a P-127) |
| **Contrato** | `.agents/docs/api_contracts/analytics-churn.md` (v1.0.0) |
| **Design System** | Papel & Tinta (`frontend/src/styles.scss` + `_analytics-ui.scss`) — Signika, Source Sans 3, Overpass Mono |
| **Autor / Etapa** | Designer de UI/UX (`uiux-expert`) — Etapa 2 · Revisão Sênior UI/UX |

---

## 1. Identificação e Objetivos de UX

### Atores e Dores Resolvidas
- **Coordenador Comercial / Televendas:** Precisa enxergar o volume financeiro sob risco (`receitaMensalEmRisco`), a data de corte da base (`Pedidos até dd/MM/yyyy`), e alternar rapidamente entre clientes ativos (`EM_RISCO`, `ALERTA`, `SAUDAVEL`, `TODOS`) e a fila de recuperação de `Inativos Antigos (> 180d)`.
- **Vendedor / Televendas Ativo:** Precisa visualizar dias sem comprar, cadência típica e score monetário (nos ativos) ou último pedido e faturamento médio (nos inativos), além de abrir o diagnóstico completo com decomposição do score, tendência trimestral, série mensal cronológica e SKUs perdidos.

### Objetivos de Interface
1. **Hierarquia de Impacto Imediato:** Cabeçalho com selo `Pedidos até dd/MM/yyyy` (`meta.dataReferencia`) + faixa de 4 KPIs (`Em risco`, `Em alerta`, `Saudáveis`, `Inativos antigos > 180d`) com skeleton equivalente na carga inicial (sem CLS).
2. **Priorização Clara (Ledger Responsivo):** Tabela semântica ordenada pelo backend por `scorePrioridade` decrescente nos ativos e `faturamentoMedioMensal` nos inativos (sem inventar score sintético no frontend quando a API não o calcula). No mobile (`< 640px`), converte-se em cartões empilhados sem corte nem overflow horizontal.
3. **Diagnóstico em Drawer Acessível:** Painel deslizante (`role="dialog"`, `aria-modal="true"`) com focus trap, foco inicial no botão de fechar, restauração de foco ao botão acionador, fechamento por `Escape`/backdrop, `inert` na página de fundo, travamento de scroll no `body`, série mensal ordenada cronologicamente, tendência trimestral direcional (`▲`/`▼`/`▬`), produtos perdidos e tratamento de erro com botão `Tentar novamente`.
4. **Filtros Completos e Paginação Unificada:** Chips para `EM_RISCO`, `ALERTA`, `SAUDAVEL`, `TODOS` e `INATIVO_RECUPERACAO` com `aria-pressed` e contadores; paginação via componente compartilhado `<app-list-pager>`.
5. **Exportação CSV Segura e LGPD:** Exportação UTF-8 com BOM (`\uFEFF`), delimitador `;`, vírgula decimal pt-BR, neutralização contra CSV/Formula Injection e somente campos operacionais sem PII (`Cod Cliente` e métricas).

---

## 2. Checklist Anti-IA (Hallmark Anti-AI-Slop)

- [x] **Zero Hexes / Zero Vidro / Zero Gradientes:** Uso exclusivo dos tokens sólidos de `styles.scss` e mixins de `_analytics-ui.scss` (inclusive `--bg-overlay` sólido no backdrop do drawer, sem `backdrop-filter`).
- [x] **Tipografia com Propósito & Alinhamento:** Títulos em Signika (`--font-family-headline`), interface em Source Sans 3 (`--font-family-body`) e valores/datas/códigos com `--font-family-mono` + `font-variant-numeric: tabular-nums`.
- [x] **Skeletons Sólidos Papel & Tinta:** Classes globais `.skeleton-box` / `.skeleton-line` (`styles.scss`) alinhadas às proporções dos KPIs, linhas da tabela e cartões do drawer, respeitando `@include ui.reduced-motion`.
- [x] **Status Multi-Sensorial:** Todo chip `.tag` combina fundo escuro sólido global (`.tag-critical`, `.tag-warning`, `.tag-positive`, `.tag-neutral`), ícone SVG inline dedicado e texto humano legível (`Em risco`, `Em alerta`, `Saudável`, `Inativo antigo`).
- [x] **Resiliência Concorrente:** Requisições reativas com `switchMap` + `takeUntilDestroyed` evitam race conditions ao alternar filtros, paginar ou clicar rapidamente em clientes distintos.

---

## 3. Tokens do Design System (`styles.scss` e `_analytics-ui.scss`)

| Categoria | Token / Classe CSS | Aplicação na Interface & Contraste WCAG AA |
| :--- | :--- | :--- |
| **Tipografia** | `--font-family-headline` | Títulos de página, seções e drawer |
| | `--font-family-body` | Rótulos, filtros e descrições |
| | `--font-family-mono` | Códigos `#XXX`, dias, valores R$, datas e variação `%` (`tabular-nums`) |
| **Superfície** | `--bg-canvas` / `--bg-surface` | Fundo da aplicação e superfície dos cartões/tabela/drawer |
| | `--bg-table-header` | Cabeçalho da tabela (`thead th`) |
| | `--bg-table-row-zebra` / `--bg-table-row-hover` | Zebra e hover condicional (`@include ui.hover`) nas linhas |
| | `--bg-subtle` / `--bg-muted` | Painéis internos do drawer, trilhas das barras mensais e skeletons |
| | `--bg-overlay` / `--shadow-modal` | Backdrop sólido e sombra seca do drawer |
| **Texto** | `--text-primary` | Valores e títulos principais |
| | `--text-secondary` | Rótulos e metadados sobre `--bg-surface`, `--bg-subtle` e `--bg-table-header` (8,0:1+ AA/AAA) |
| | `--text-on-brand` | Texto branco sobre `--brand-primary` e tags `.tag-*` |
| **Bordas** | `--border-subtle` / `--border-default` / `--border-focus` | Divisórias internas, contornos de cards/botões e outline de teclado |
| **Feedback & Tags** | `.tag-critical` (`--feedback-critical-bg`) | Badge `Em risco` (`EM_RISCO`) + acento de queda/erro sobre `--bg-surface` |
| | `.tag-warning` (`--feedback-warning-bg`) | Badge `Em alerta` (`ALERTA`) + borda superior KPI Alerta |
| | `.tag-positive` (`--feedback-positive-bg`) | Badge `Saudável` (`SAUDAVEL`) + acento de alta sobre `--bg-surface` |
| | `.tag-neutral` (`--feedback-neutral-bg`) | Badge `Inativo antigo` (`INATIVO_RECUPERACAO`) + KPI Inativos |

> **Regra de Contraste:** `--feedback-critical-bg`, `--feedback-warning-bg`, `--feedback-positive-bg` e `--feedback-neutral-bg` são cores **escuras sólidas** destinadas a texto branco (`--text-on-brand`) ou a texto/borda de acento sobre `--bg-surface`. Nunca usar `--text-muted` sobre `--bg-subtle` ou `--bg-table-header`.

---

## 4. Estrutura Visual da Página (`/analytics/churn`)

```
+---------------------------------------------------------------------------------------------------+
| Retenção de Carteira   [Pedidos até 12/11/2026]                                                    |
| Churn de Clientes                                                       [ [↓] Exportar CSV ]      |
| Priorização por score de impacto mensal para recuperação ativa dos clientes em risco.             |
+---------------------------------------------------------------------------------------------------+
| [ Em risco: 350 | Rec.: R$ 1.854.200,50/mês ] [ Em alerta: 210 ] [ Saudáveis: 1.400 ] [ Inat.: 80]|
+---------------------------------------------------------------------------------------------------+
| Filtros: (Em risco 350)  (Em alerta 210)  (Saudáveis 1.400)  (Todos os ativos 1.960)  (Inat. 80)  |
+---------------------------------------------------------------------------------------------------+
| TABELA PRIORIZADA (Ativos) / FILA DE INATIVOS                                                     |
| Cód. Cliente | Status     | Dias s/ comprar | Cadência / Últ. Pedido | Fat. médio/mês | Score  |  |
| #1042        | [▲ Em risco]| 74 dias        | 18,0d (régua 60d)      | R$ 48.250,00   | R$...  |Detalhes ›|
| Paginação (<app-list-pager>): 1–50 de 350     ‹ Anterior   Página 1 de 7   Próxima ›              |
+---------------------------------------------------------------------------------------------------+
| DRAWER LATERAL (`inert` na página ao abrir)                                                       |
| Diagnóstico de retenção · Cliente #1042                                                  [ X ]    |
| [▲ Em risco] · Score de prioridade: R$ 59.347,50 (Fat. Médio × fator 1,23×)                       |
| Dias sem comprar | Último pedido | Cadência típica | Faturamento médio                            |
| Tendência trimestral: ▼ -25,4% (queda dos últimos 3 meses frente aos 3 meses anteriores)          |
| Faturamento mensal recente (ordenado cronologicamente com barras proporcionais)                    |
| Produtos que deixou de comprar (> 60 dias)                                                        |
|                                                                             [ Fechar painel ]     |
+---------------------------------------------------------------------------------------------------+
```

---

## 5. Matriz dos 8 Estados Interativos Obrigatórios

| Componente | 1. Default | 2. Hover | 3. Focus | 4. Active | 5. Disabled | 6. Loading | 7. Empty | 8. Error |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Linha / Botão Detalhes** | Fundo `--bg-surface`, botão secundário `40px` | `@include ui.hover`: `--bg-table-row-hover` | Outline `--border-focus` 2px no `<button>` | `.row-selected` (`--brand-primary-subtle`) | — | `.table-skeleton` + `aria-busy="true"` | `.empty-state` com ícone SVG e texto contextual | `.error-banner` (`role="alert"`) + retry |
| **Botão Exportar CSV** | `%button-secondary` (`40px`) | `--bg-subtle` (`ui.hover`) | Ring `--border-focus` | `--bg-muted` | Opacidade `0.5` em loading, erro ou vazio | Texto `Exportando...` e bloqueio de clique | Desabilitado quando lista vazia | Desabilitado em falha da lista |
| **Chips de Filtro** | Fundo `--bg-surface`, borda `--border-default`, `40px` | `--bg-subtle` (`ui.hover`) | Outline visível | `--brand-primary` + `--text-on-brand` + `aria-pressed="true"` | — | Skeleton de KPIs na 1ª carga | Contador `0` preservado | Estado do filtro mantido com retry |
| **Drawer de Detalhes** | Fechado (`visibility: hidden`, `inert`, `aria-hidden="true"`) | `@include ui.hover` nos botões fechar/retry | Focus Trap (`Tab`/`Shift+Tab`), foco inicial no fechar, restauração no trigger | Painel aberto com scroll do body travado | — | `.drawer-loading` + `aria-busy="true"` + título `#XXX` | Blocos `.empty-block` para série/SKUs vazios | `.drawer-error` (`role="alert"`) + `Tentar novamente` |
| **Paginação (`app-list-pager`)** | Faixa `a–b de total` + controles `40px` | `--bg-subtle` | Outline visível | Página destacada | Desabilitada quando `loading()` ou extremos | `[disabled]="loading()"` | Oculta quando `totalPages <= 1` | Oculta com erro na lista |

---

## 6. Acessibilidade (WCAG 2.1 AA) e LGPD na UI

- **Semântica e Leitores de Tela:** Tabela semântica nativa (sem `role="button"` em `<tr>`); ação via `<button>` com `aria-expanded` e `aria-label`; regiões `aria-live="polite"` + `[attr.aria-busy]` na página e no drawer; `role="alert"` nos erros.
- **Gestão de Foco do Dialog:** Drawer com `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `[attr.inert]` no conteúdo principal enquanto aberto, Focus Trap cíclico (`Tab`/`Shift+Tab`), fechamento via `Escape`/backdrop e restauração de foco ao botão acionador.
- **Alvos e Responsividade:** Alvos interativos com altura mínima de `40px` (`$touch-target`) e layout em cartões abaixo de `639.98px`.
- **Privacidade (LGPD-CHU-01..06):** `customerCode` trafega apenas no path HTTP e memória volátil (nunca em URL, storage ou `console.log`); CSV exporta somente código e métricas numéricas agregadas, protegidas contra Formula Injection.
