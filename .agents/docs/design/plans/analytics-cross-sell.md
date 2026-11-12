# Design Plan — Analytics Comercial · F4 Recomendação de Cross-sell (+ casca `/analytics`)

<!-- Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 · macrostructure: workbench (consulta → resultado) com lista ranqueada "ledger" -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | US-F4 — Recomendação de cross-sell por produto e por cliente; fundação da rota `/analytics` |
| **Branch** | `feature/analytics-cross-sell` |
| **Regras** | `.agents/docs/business_rules/analytics-cross-sell.md` (P-058 a P-071, `XSL-001` a `XSL-004`) |
| **Plano mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` §3.1 item 6 e §3.5 |
| **Contrato** | `.agents/docs/api_contracts/analytics-cross-sell.md` (Arquiteto, em paralelo). Os campos de que a tela precisa estão em §11. |
| **Telas de referência** | `features/inventory/pages/inventory-page/`, `features/pricing/pages/pricing-page/`, `core/layout/navbar/`, `frontend/src/styles.scss` |
| **Autor / Etapa** | Designer — Etapa 2 · 2026-11-05 · decisões D-n a validar no checkpoint |

---

## 1. Identificação e objetivos de UX

**Story:** como vendedor/comprador, quero saber o que costuma ser comprado junto com um produto e o que oferecer a cada cliente, para aumentar o ticket com sugestões que têm estoque e dão margem.

**Perguntas que a tela responde em uma busca**
1. "O que oferecer junto com o produto X?" (modo **Por produto**).
2. "O que oferecer ao cliente 1234?" (modo **Por cliente**).

**Objetivos de UX**
1. Um campo, um botão, uma lista. Nenhuma configuração antes da primeira resposta.
2. Cada sugestão se explica sozinha em português ("Em 34% dos pedidos com A também há B"). Lift, confiança, suporte e pontuação ficam atrás de "Ver números".
3. No modo produto, item sem estoque ou sem margem aparece, mas com sinal claro (A-8), para o comprador não oferecer o que não pode entregar.
4. Lista vazia é resposta válida e explica o porquê; nunca parece erro.
5. A casca `/analytics` comporta as 6 abas do roadmap sem redesenho.

**Arquétipo:** Analítico sob demanda (consulta pontual, sem KPIs de cabeçalho). Não há gráficos; a densidade fica em 1 formulário + 1 lista por modo, bem abaixo do limite de 6–8 blocos.

**Discovery:** sem brainstorming interativo (instrução do Orquestrador). As decisões estão marcadas como **D-n (a validar no checkpoint)** e consolidadas em §12.

---

## 2. Checklist Anti-IA (auditado)

- [x] **Sem "AI Purple"** e sem gradiente: superfícies sólidas de `styles.scss` (Papel & Tinta). Nenhuma cor nova.
- [x] **Sem 3 colunas mecânicas:** resultado é uma lista ranqueada de linhas (ledger), alinhada à esquerda, com número de posição em mono. Nada de cards de feature com ícones.
- [x] **Font pairing:** títulos em `--font-family-headline` (Signika), interface em `--font-family-body` (Source Sans 3), números em `--font-family-mono` (Overpass Mono).
- [x] **White space:** respiro de `--space-6`/`--space-8` entre consulta e resultado; linhas da lista separadas por hairline, sem card dentro de card.
- [x] **Copy humano:** zero "inteligente", "IA", "motor", "seamless", "potencialize", "desbloqueie". Sem ✨. Nunca usar "venda casada" (termo de prática proibida pelo CDC).
- [x] **Sem spinner isolado:** skeleton com a geometria das linhas. Spinner só dentro do botão com rótulo, padrão já existente.
- [x] **Sem tela vazia:** estado inicial guiado e 4 variantes de vazio com ação.
- [x] **Sem título em itálico, sem fake chrome, sem métrica inventada:** os números exibidos vêm todos da API.
- [x] **Status nunca só por cor:** toda tag tem ícone ou texto que carrega o sentido sozinho.

---

## 3. Tokens consumidos

> **D-1 (a validar):** `DESIGN_SYSTEM.md` descreve teal + Plus Jakarta Sans + Inter, mas o código em produção (`frontend/src/styles.scss`) usa **Papel & Tinta** (verde erva-mate, Signika, Source Sans 3, Overpass Mono). Este plano segue `styles.scss`, como o plano aprovado `estoque-min-max.md`, para a aba não destoar das telas existentes. Recomenda-se atualizar `DESIGN_SYSTEM.md` numa tarefa à parte.

**Nenhum token novo.** Regras novas consomem só `var(--token)`, **sem fallback hex** (as telas antigas usam `var(--x, #hex)`; não copiar esse padrão).

| Grupo | Tokens |
| :--- | :--- |
| Tipografia | `--font-family-headline`, `--font-family-body`, `--font-family-mono` |
| Superfície | `--bg-canvas` (página), `--bg-surface` (painéis), `--bg-subtle` (campo de busca, faixa de contexto), `--bg-muted` (skeleton), `--bg-table-row-hover` (hover de linha) |
| Texto | `--text-primary`, `--text-secondary`, `--text-muted` (só sobre `--bg-surface`/`--bg-canvas`), `--text-on-brand` |
| Marca | `--brand-primary`, `--brand-primary-hover`, `--brand-primary-active`, `--brand-primary-subtle` |
| Feedback (tags via classes globais) | `.tag-critical` (Sem estoque), `.tag-warning` (Margem zero ou negativa · Parou de comprar), `.tag-neutral` (Nunca comprou · Custo estimado), `.tag-info` (não usado); `--feedback-critical-bg` para erro de campo |
| Borda / foco | `--border-subtle`, `--border-default`, `--border-strong`, `--border-focus` |
| Espaço | `--space-1` a `--space-8` |
| Raio | `--radius-xs` (tags, inputs, botões, como o resto do app), `--radius-sm` (painéis) |
| Sombra | `--shadow-xs` (painéis) |
| Movimento | `--transition-fast` |

Tamanhos de fonte reaproveitam a escala já usada nas páginas: `1.85rem` (título da página), `1.25rem` (título de resultado), `0.95rem` (descrição do produto), `0.88rem` (corpo), `0.78rem` (tags/legendas), `0.74rem` (rótulo em caixa alta).

**Contraste verificado (WCAG 2.1)**

| Par | Razão | Resultado |
| :--- | :--- | :--- |
| `--text-primary` sobre `--bg-surface` | ~17:1 | AA |
| `--text-secondary` sobre `--bg-subtle` | 8,0:1 | AA |
| `--text-muted` sobre `--bg-surface` | 5,2:1 | AA |
| `--text-muted` sobre `--bg-canvas` | 4,65:1 | AA (limite; só para legenda ≥ 0.78rem) |
| `--text-muted` sobre `--bg-subtle` | 4,2:1 | **Reprova** → dentro do campo de busca e da faixa de contexto usar `--text-secondary` |
| `--brand-primary` sobre `--brand-primary-subtle` (aba/segmento ativo alternativo) | 9,2:1 | AA |
| `--text-on-brand` sobre `--feedback-warning-bg` | 7,7:1 | AA |
| `--text-on-brand` sobre `--feedback-critical-bg` | 8,9:1 | AA |
| `--text-on-brand` sobre `--feedback-neutral-bg` | 10,3:1 | AA |
| `--feedback-critical-bg` sobre `--bg-surface` (erro de campo) | 8,9:1 | AA |

---

## 4. Arquitetura de componentes (burros × dados do service)

**Regra:** um único componente "inteligente" por modo de tela (o container da aba). Todos os outros só recebem `input()` e emitem `output()`. Nenhum componente calcula pontuação, filtra viabilidade ou reordena: a ordem é a da API (P-061.1, P-064.2). Formatação (percentual, vírgula decimal, R$) é feita por pipes no template.

| Componente | Tipo | Recebe / emite | Origem dos dados |
| :--- | :--- | :--- | :--- |
| `AnalyticsPageComponent` (rota `/analytics`, lazy) | Casca | Renderiza o cabeçalho da página, `AnalyticsSectionNav` e `<router-outlet>` | Constante `ANALYTICS_SECTIONS` (lista de abas) |
| `AnalyticsSectionNavComponent` | Burro | `sections: {label, path, description}[]` | Constante acima |
| `CrossSellPageComponent` (rota filha `cross-sell`) | **Inteligente** | Guarda `mode`, consulta corrente, página e estado de cada modo; chama `AnalyticsService` | `AnalyticsService` (HTTP + mapeamento de erro) |
| `ModeSwitchComponent` | Burro | `mode`, `(modeChange)` | — |
| `CodeSearchFormComponent` | Burro (reutilizado nos dois modos) | `label`, `hint`, `submitLabel`, `loading`, `fieldError`, `initialValue`; `(search)` emite inteiro positivo | Validação de formato é só de UI (dígitos); a regra de negócio fica no backend |
| `QueryContextHeaderComponent` | Burro | `title` (insight já montado), `subtitle`, `dataReferencia`, `totalItems` | `meta` + `data` da resposta |
| `RecommendationListComponent` | Burro | `items`, `variant: 'product' \| 'customer'`, `pageOffset` (para numerar a posição) | `data[]` |
| `ProductRecommendationRowComponent` | Burro | 1 item do modo produto | idem |
| `CustomerRecommendationRowComponent` | Burro | 1 item do modo cliente | idem |
| `RecommendationNumbersComponent` | Burro | `lift`, `confianca`, `suporte?`, `pedidosEmComum`, `pontuacao?`, `margemUnitaria?` | idem |
| `ResultStateComponent` | Burro | `kind` (`intro`, `empty-product`, `empty-customer`, `empty-customer-inactive`, `empty-page`, `insufficient-data`, `error`), `contextLabel`, `(action)` | Derivado pelo container a partir da resposta/erro |
| `RecommendationListSkeletonComponent` | Burro | `rows` (padrão 5) | — |
| `ListPagerComponent` | Burro | `page`, `totalPages`, `offset`, `limit`, `totalItems`; `(pageChange)` | `meta` |

**`AnalyticsService`** (em `features/analytics/services/`): métodos `getProductCrossSell(sku, {limit, offset})`, `getCustomerCrossSell(customerCode, {limit, offset})` e `getHealth()`. Desembrulha o envelope e converte `HttpErrorResponse` em `{ code: 'XSL-001' | 'XSL-002' | 'XSL-003' | 'XSL-004' | 'NETWORK' | 'SERVER', fields?: string[] }`. **A tela nunca exibe `err.error.detail` cru** nem stacktrace; a mensagem vem do mapa de copy (§9).

**Estado:** signals locais no `CrossSellPageComponent` (cada modo guarda sua última consulta e resultado). Não vai para estado global. Resultado do modo cliente **não** é salvo em `localStorage`/`sessionStorage` (P-070.4).

---

## 5. Anatomia e hierarquia

### 5.1 Navbar

Novo item após "Estoque e Compras", mesmo padrão de `nav-link` com `routerLinkActive`:

```
[ícone 16px barras verticais]  Análises de Vendas
```

- **D-2 (a validar):** rótulo `Análises de Vendas` (segue o padrão "substantivo + complemento" de "Preços e Descontos" e "Estoque e Compras"; "Analytics" em inglês destoa). `title="Consultas sobre o histórico de pedidos"` (sem "em breve": não prometer seções que ainda não existem).
- Ícone: SVG inline 16×16 (3 barras verticais de alturas diferentes, `stroke="currentColor"`, `aria-hidden="true"`).
- `routerLinkActive` deve marcar ativo em qualquer filha de `/analytics`.

### 5.2 Página `/analytics` (casca)

```
┌────────────────────────────────────────────────────────────────────────────┐ border-top 3px --brand-primary
│ Análises de Vendas                                                          │ h1, headline 1.85rem
│ Consultas sobre o histórico de pedidos. Clientes aparecem só pelo código.   │ 0.88rem --text-secondary
│ ─────────────────────────────────────────────────────────────────────────── │
│ [Cross-sell]                                                                │ nav de seções (sublinhado ativo)
└────────────────────────────────────────────────────────────────────────────┘
  <router-outlet>  → conteúdo da seção ativa
```

- Container: mesma largura e padding do `.inventory-container` (`max-width: 1600px`, gap `--space-5`). Cabeçalho segue a anatomia de `.feature-hero` (fundo `--bg-surface`, borda `--border-default`, `border-top: 3px solid var(--brand-primary)`, `--radius-sm`, `--shadow-xs`).
- **Navegação de seções (D-3):** `<nav aria-label="Seções de análise">` com **links** (`routerLink`), não `role="tablist"`: cada seção é uma rota filha (`/analytics/cross-sell`, depois `/analytics/elasticidade`, `/canibalizacao`, `/sazonalidade`, `/churn`, `/produto-novo`), com `aria-current="page"` no ativo. Motivo: URL própria por análise, lazy load por seção e botão voltar funcionando. `/analytics` redireciona para a primeira seção.
  - Visual: links em linha, `font-family-body` 0.88rem peso 600, `--text-secondary`; ativo em `--text-primary` com sublinhado de 3px `--brand-primary` colado à base do cabeçalho. Hover: `--text-primary` + sublinhado 3px `--border-default`.
  - Cada nova fase só acrescenta uma entrada em `ANALYTICS_SECTIONS` e uma rota filha.
  - **D-4 (a validar):** seções futuras **não** aparecem desabilitadas/"em breve" nesta fase (sem UI morta). Com 6 itens o nav cabe em desktop; abaixo de 768px rola horizontalmente dentro do próprio nav (ver §8).

### 5.3 Seção Cross-sell

```
O que oferecer junto                                          h2 1.25rem headline
Produtos que costumam sair no mesmo pedido, a partir do histórico de vendas.   0.88rem --text-secondary

[ Por produto | Por cliente ]                                 ModeSwitch (segmentado, à esquerda)

┌ painel de consulta (--bg-surface) ──────────────────────────────────────────┐
│ Código do produto                                                           │ label 0.82rem 600
│ [ 🔍  ex.: 10432                     ]  [ Ver sugestões ]                     │
│ Use o código do catálogo (o mesmo da tabela de preços).                     │ hint 0.78rem --text-muted
└─────────────────────────────────────────────────────────────────────────────┘

┌ painel de resultado (--bg-surface) ─────────────────────────────────────────┐
│ QueryContextHeader                                                          │
│ ─────────────────────────────────────────────────────────────────────────── │
│ RecommendationList (linhas)                                                 │
│ ─────────────────────────────────────────────────────────────────────────── │
│ ListPager                                                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

- Consulta e resultado são dois painéis irmãos (não aninhados), gap `--space-6`.
- **ModeSwitch (D-5):** controle segmentado com padrão ARIA de abas (`role="tablist"` com 2 `role="tab"`, `aria-selected`, `aria-controls` apontando para o painel do modo, setas ←/→ alternam e ativam, Home/End). Aqui é tablist porque os dois modos são painéis da mesma rota. Visual: grupo com borda `--border-default`, `--radius-xs`; segmento ativo `--brand-primary` + `--text-on-brand`; inativo `--bg-surface` + `--text-secondary`. Altura mínima 40px.
- **Cada modo guarda seu estado** ao alternar (a última busca de produto não some ao olhar um cliente e vice-versa).
- **URL (D-6, privacidade):** o modo produto reflete a busca em query param (`/analytics/cross-sell?modo=produto&sku=10432`), para o comprador compartilhar o link. O modo cliente **não** coloca o código do cliente na URL do frontend (`?modo=cliente` apenas): evita o código no histórico do navegador e em logs de acesso do servidor do frontend (minimização, P-070, A-11).

### 5.4 Formulário de consulta (`CodeSearchFormComponent`)

| Modo | Label | Placeholder | Hint | Botão |
| :--- | :--- | :--- | :--- | :--- |
| Produto | Código do produto | `ex.: 10432` | Use o código do catálogo (o mesmo da tabela de preços). | Ver sugestões |
| Cliente | Código do cliente | `ex.: 1234` | Só o código: a tela não mostra nome nem documento do cliente. | Ver o que oferecer |

- `<form role="search">` com `<label for>` visível; `<input type="text" inputmode="numeric" autocomplete="off" enterkeyhint="search">`. Enter envia.
- Validação local antes de chamar a API: só dígitos, sem zero inicial isolado, valor > 0. Mensagem: `Digite só números, sem pontos ou letras.` (evita a maioria dos `XSL-004`).
- O campo reaproveita a geometria de `.search-box` (fundo `--bg-subtle`, ícone de lupa `aria-hidden`), **com correção de foco**: a regra antiga zera `outline` do input; aqui o container recebe `:focus-within { outline: 2px solid var(--border-focus); outline-offset: 2px; }`.
- Botão "×" de limpar aparece quando há valor: `aria-label="Limpar código"`.
- **D-7 (a validar):** nesta fase a busca é **por código**, sem autocomplete por descrição (o endpoint `/analytics/products/search` é da Fase 4). Se o Arquiteto antecipar esse endpoint, o campo vira combobox (ver pergunta Q-1 em §11).

### 5.5 Cabeçalho do resultado (`QueryContextHeaderComponent`)

Título como **insight**, montado só com dados da resposta:

| Modo | Título (h3) | Linha de contexto |
| :--- | :--- | :--- |
| Produto | `Quem compra {descrição A} costuma levar {totalItems} produtos junto` (singular: `costuma levar 1 produto junto`) | `Cód. {sku} · {fornecedor A}` |
| Cliente | `{totalItems} produtos para oferecer ao cliente {código}` (singular: `1 produto para oferecer…`) | `Baseado nas compras dos últimos 12 meses. Só entram produtos com estoque e margem.` |

- À direita (quebra para baixo em mobile): selo no estilo `.cache-badge` com ícone de relógio: `Pedidos até {dataReferencia dd/MM/yyyy}`. Sobre `--bg-subtle`, texto em `--text-secondary` (não `--text-muted`, ver contraste).
- O título é `h3` com `tabindex="-1"` (alvo de foco só em paginação, ver §7.3).

### 5.6 Linha do modo produto (`ProductRecommendationRowComponent`)

```
 01 │ Cápsula de Hibisco 60 un                         [▲ 4,3× mais que o normal]
    │ Cód. 20871 · Fitoherb                             170 pedidos
    │ Em 34% dos pedidos com Chá Verde 100g também há Cápsula de Hibisco.
    │ ███████░░░░░░░░░░░░░  34%                          [⊘ Sem estoque] [Custo estimado]
    │ Ver números ▸
```

- Grid desktop: `[posição 40px] [produto minmax(0,1.1fr)] [explicação minmax(0,1.6fr)] [sinais auto]`. Linhas separadas por `1px solid var(--border-subtle)`, padding vertical `--space-4`. Hover da linha: `--bg-table-row-hover` (dentro de `@media (hover: hover)`); a linha em si não é clicável.
- **Posição:** `--font-family-mono` 0.78rem `--text-muted`, dois dígitos (`01`), relativa à lista completa (`offset + índice + 1`).
- **Produto:** descrição 0.95rem peso 600 `--text-primary`, `overflow-wrap: anywhere`; abaixo `Cód. {código} · {fornecedor}` 0.78rem `--text-muted`, código em mono.
- **Explicação (texto principal):** frase P-065.1 em 0.88rem `--text-primary`. A frase P-065.2 ("aparece 4,3 vezes mais…") vira o chip `▲ 4,3× mais que o normal` e a P-065.3 vira `170 pedidos` (mono). O texto completo das três frases fica no `aria-label`/texto sr-only da linha para leitor de tela (ver §7).
- **Barra de proporção:** 120px × 6px, trilho `--bg-muted`, preenchimento `--brand-primary` em `confianca × 100%`, `aria-hidden="true"` (o número já está na frase). Sem animação de largura.
- **Sinais (A-8, P-061.4):**
  - `semEstoque` → `.tag.tag-critical` com ícone ⊘ (SVG) + `Sem estoque`.
  - `margemNaoPositiva` → `.tag.tag-warning` com ícone ! + `Margem zero ou negativa`.
  - `custoEstimado` (se o contrato trouxer no modo produto) → `.tag.tag-neutral` `Custo estimado`, com `title="Sem último custo no cadastro: usamos 60% do preço de venda."`.
  - **D-8 (a validar):** linhas sinalizadas **não** são esmaecidas nem reordenadas (a ordem é a da API); a tag basta. Esmaecer reduziria contraste do texto abaixo de AA.
- **Ver números:** `RecommendationNumbersComponent` (§5.8).

### 5.7 Linha do modo cliente (`CustomerRecommendationRowComponent`)

```
 01 │ Óleo de Coco 500 ml                    [Nunca comprou]        Margem R$ 30,00/un.
    │ Cód. 30455 · Fitoherb
    │ Sugerido porque o cliente compra Chá Verde 100g. O cliente nunca comprou Óleo de Coco 500 ml.
    │ Em 20% dos pedidos com Chá Verde 100g também há Óleo de Coco 500 ml.
    │ + 1 outro produto que o cliente compra também leva a esta sugestão.
    │ Ver números ▸
```

- Mesmo grid da linha de produto; a coluna de sinais mostra **motivo** e **margem**.
- **Motivo (P-062.5):** `NUNCA_COMPROU` → `.tag.tag-neutral` `Nunca comprou`; `DORMENTE` → `.tag.tag-warning` com ícone de relógio + `Parou há {dias} dias`.
- **Margem:** `Margem R$ {margemUnitaria}/un.` em mono 0.88rem; se `custoEstimado`, acrescentar `.tag.tag-neutral` `Custo estimado` (mesmo `title` do §5.6).
- **Explicação:** frase P-065.4 (prefixo + motivo) em `--text-primary`; frase P-065.1 abaixo em `--text-secondary`.
- `qtdAntecedentesRelacionados > 1` → linha 0.78rem `--text-muted`: `+ {n−1} outro(s) produto(s) que o cliente compra também leva(m) a esta sugestão.`
- **Prioridade de abordagem (D-9, a validar):** na página 1, as 5 primeiras linhas recebem filete esquerdo de 3px `--brand-primary`, e depois da 5ª há um divisor rotulado `Outras sugestões` (0.74rem caixa alta, `--text-secondary`). Liga a tela ao critério hit rate@5 (P-071) e diz ao vendedor por onde começar. Leitor de tela: as 5 primeiras ficam numa `<ol aria-label="Prioridade: 5 primeiras sugestões">` e as demais em outra `<ol start="6" aria-label="Outras sugestões">`.
- Nenhum dado do cliente além do código aparece na tela (P-070.1).

### 5.8 "Ver números" (`RecommendationNumbersComponent`)

- `<button type="button" aria-expanded aria-controls>` com texto `Ver números` / `Ocultar números` e chevron que gira (rotação de 90°, `--transition-fast`; sem animação com `prefers-reduced-motion`).
- Conteúdo: `<dl>` em linha, mono 0.78rem, rótulos em `--text-secondary`:

| Modo produto | Modo cliente |
| :--- | :--- |
| `Lift 4,25` · `Confiança 34%` · `Suporte 1,7%` · `Pedidos em comum 170` | `Pontuação 9,00` · `Lift 1,50` · `Confiança 20%` · `Margem R$ 30,00` · `Pedidos em comum {n}` (se vier) |

- Abaixo, uma linha de glossário em 0.78rem `--text-muted`: `Lift: quantas vezes o par aparece a mais do que o acaso. Confiança: % dos pedidos com o primeiro produto que também têm o segundo.` (no modo cliente acrescentar `Pontuação = lift × confiança × margem por unidade.`).
- **D-10 (a validar):** cada linha tem seu próprio botão; não há "mostrar números em todas" nesta fase.

### 5.9 Paginação (`ListPagerComponent`)

- Paginação **no servidor** (P-066). Tamanho fixo de 50 (padrão da API), **sem seletor de itens por página (D-11, YAGNI)**.
- Rodapé: à esquerda `{offset+1}–{offset+itens} de {totalItems}` (mono, `role="status"` não; ver §7); à direita `‹ Anterior` · `Página {page} de {totalPages}` · `Próxima ›`, botões `.btn-secondary` com `aria-label` completos.
- Oculto quando `totalPages ≤ 1`.

---

## 6. Matriz de estados visuais

### 6.1 Estados da área de resultado (por modo)

| # | Estado | Condição | O que aparece |
| :--- | :--- | :--- | :--- |
| 1 | **Inicial (guia)** | Nenhuma busca feita no modo | `ResultStateComponent kind="intro"` (ver §6.3). Não é erro nem vazio. |
| 2 | **Loading** | Requisição em curso | Skeleton (§6.2); botão de busca com spinner + `Buscando…`, desabilitado; campo continua editável. |
| 3 | **Default (sucesso)** | 200 com itens | Cabeçalho + lista + paginação. |
| 4 | **Vazio — produto** | Modo produto, 200, `totalItems = 0` (P-061.5) | `empty-product` |
| 5 | **Vazio — cliente** | Modo cliente, 200, `totalItems = 0`, sem `motivoVazio` (C-06) | `empty-customer` |
| 6 | **Vazio — cliente sem compras recentes** | 200, `meta.motivoVazio = "SEM_COMPRAS_RECENTES"` (P-062.7) | `empty-customer-inactive` |
| 7 | **Vazio — página além do fim** | 200, `data = []`, `totalItems > 0` (P-066.4) | `empty-page` |
| 8 | **Erro de campo** | `XSL-001` (produto), `XSL-002` (cliente), `XSL-004` | Erro inline no formulário (§6.4); a área de resultado volta ao estado anterior à busca. |
| 9 | **Sem dados suficientes** | `XSL-003` (422) | `insufficient-data` (vale para os dois modos). |
| 10 | **Falha técnica** | Rede, timeout, 5xx | `error` com "Tentar de novo". |

### 6.2 Loading (skeleton com a geometria real)

- Pulse sólido global `.skeleton-line` (sem gradiente). Com `prefers-reduced-motion: reduce`, `animation: none`.
- Cabeçalho: 1 barra 60% × 1.25rem + 1 barra 35% × 0.78rem; selo de data 140px × 28px à direita.
- Lista: **5 linhas** com o mesmo grid da linha real: posição 20px × 0.78rem; produto 70% × 0.95rem + 45% × 0.78rem; explicação 2 barras (95% e 70% × 0.88rem) + barra de proporção 120px × 6px; sinais 1 bloco 96px × `--space-5`.
- Container com `aria-busy="true"`; skeleton com `aria-hidden="true"`.
- Região viva (`role="status"`, sempre no DOM, visualmente oculta): `Buscando sugestões…`.
- **Primeira consulta lenta (cache frio, P-068):** se o loading passar de 4 s, aparece abaixo do skeleton, em 0.78rem `--text-secondary`: `A primeira consulta depois de algumas horas monta a base de pedidos e demora mais. As próximas são rápidas.` (texto honesto, sem prometer tempo).
- Ao paginar, o skeleton substitui só a lista; o cabeçalho continua.

### 6.3 Inicial e vazios (`ResultStateComponent`)

Anatomia comum, alinhada à esquerda (não centralizar bloco de texto): ícone SVG 36×36 `aria-hidden` em caixa 56×56 `--bg-subtle` `--radius-xs` · título 1rem headline peso 600 · texto 0.88rem `--text-secondary` (máx. 60ch) · ação `.btn-secondary`.

| `kind` | Ícone | Título | Texto | Ação |
| :--- | :--- | :--- | :--- | :--- |
| `intro` (produto) | duas caixas ligadas | Escolha um produto | Digite o código de um produto para ver o que os clientes costumam levar no mesmo pedido. | `Ir para o campo` (foca o input) |
| `intro` (cliente) | pessoa + caixa | Escolha um cliente | Digite o código do cliente para ver produtos que ele ainda não compra, ou parou de comprar, e que combinam com o que ele já leva. | `Ir para o campo` |
| `empty-product` | caixa com traço | Nenhuma combinação forte para {descrição A} | Este produto sai em pedidos com outros itens, mas nenhum se repete com frequência suficiente para virar sugestão. | `Buscar outro produto` (limpa e foca o campo) |
| `empty-customer` | caixa com check | Nada novo para oferecer ao cliente {código} agora | Ele já comprou nos últimos 90 dias os produtos que costumam acompanhar o que leva, ou as sugestões estão sem estoque ou sem margem. | `Consultar outro cliente` |
| `empty-customer-inactive` | relógio | O cliente {código} não compra há mais de 12 meses | As sugestões partem do que o cliente comprou no último ano, então não há base para recomendar. | `Consultar outro cliente` |
| `empty-page` | lista | Esta página não tem itens | A lista tem {totalItems} sugestões; voltamos para o começo. | `Ir para a primeira página` |

> Os números "90 dias" e "12 meses" refletem `DORMANT_DAYS` e `CUSTOMER_PROFILE_DAYS` (premissas A-4/A-5). Se o contrato expuser esses valores em `meta`, a copy deve interpolá-los (ver Q-5).

### 6.4 Erros

**Erro de campo (inline, sem popup):** abaixo do input, ícone alert-circle 14×14 + texto em `--feedback-critical-bg` 0.82rem peso 600; input com `aria-invalid="true"` e `aria-describedby` apontando para o erro; borda do campo `--feedback-critical-bg`. O valor digitado é mantido e o foco volta ao input. O erro some ao editar o campo.

| Código | Onde | Mensagem (literal de P-067) |
| :--- | :--- | :--- |
| `XSL-001` | campo produto | Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item. |
| `XSL-002` | campo cliente | Cliente sem histórico de compras. (não ecoar nada além do código já digitado) |
| `XSL-004` | campo do modo | Parâmetros inválidos: {campos}. → na tela, traduzir: `sku`/`customerCode` → `Digite só números, sem pontos ou letras.`; `limit`/`offset` → tratar como falha técnica (é bug do frontend) |

**Sem dados suficientes (`XSL-003`, 422) — `insufficient-data`:**
- Ícone: gráfico com poucos pontos. Título: `Ainda não dá para recomendar com segurança`. Texto: `Não há pedidos suficientes para gerar recomendações confiáveis. Isso vale para todos os produtos e clientes, não só para este código.` Ação: `Tentar de novo` (refaz a consulta).
- Fundo `--bg-surface` com filete esquerdo 3px `--feedback-warning-bg` + ícone; não é vermelho (não é falha do usuário nem do sistema).

**Falha técnica (rede, timeout, 5xx) — `error`:**
- Banner `.alert-danger` (`role="alert"`) dentro do painel de resultado, ícone + `Não foi possível buscar as sugestões agora. Tente de novo em instantes.` + botão `Tentar de novo` (refaz a última consulta, mesma página). Botão fechar: `aria-label="Fechar aviso"`.
- Se havia uma lista anterior do mesmo modo, ela é substituída pelo banner (evita mostrar sugestões de outro código sob a busca nova).
- Nunca exibir `detail`, stacktrace ou a instrução de terminal que a tela de preços mostra.

### 6.5 Matriz dos 8 estados por elemento interativo

| Elemento | Default | Hover | Focus-visible | Active | Disabled | Loading | Error | Success |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Link de seção (nav `/analytics`) | `--text-secondary` | `--text-primary` + sublinhado `--border-default` | outline global 2px `--border-focus`, offset 2px | `aria-current="page"`: `--text-primary` + sublinhado 3px `--brand-primary` | n/a | n/a (rota lazy: o outlet mostra o skeleton da seção) | n/a | = active |
| ModeSwitch (segmento) | `--bg-surface`, `--text-secondary` | `--bg-subtle` | outline global | pressionado: `--brand-primary-active`; selecionado: `--brand-primary` + `--text-on-brand` | n/a | segue clicável durante a busca do outro modo | n/a | = selecionado |
| Campo de código | `--bg-subtle`, borda `--border-subtle` | borda `--border-default` | `:focus-within` outline 2px `--border-focus` | n/a | n/a (nunca desabilitado) | continua editável | borda e mensagem `--feedback-critical-bg` + `aria-invalid` | n/a |
| Botão "Ver sugestões" / "Ver o que oferecer" | `.btn-primary` | `--brand-primary-hover` | outline global | `--brand-primary-active` | campo vazio: opacity 0.5 + `not-allowed` | spinner + `Buscando…`, `aria-disabled="true"` | volta ao default | volta ao default |
| Botão limpar "×" | glifo `--text-muted` | `--text-primary` | outline global | `--text-primary` | oculto sem valor | n/a | n/a | n/a |
| "Ver números" | `--brand-primary` 0.78rem peso 600, sem sublinhado | sublinhado | outline global | `--brand-primary-active` | n/a | n/a | n/a | aberto: `aria-expanded="true"`, chevron 90° |
| Pager Anterior/Próxima | `.btn-secondary` | `--bg-subtle` | outline global | `--bg-muted` | primeira/última página: opacity 0.5 | desabilitados durante a carga | n/a | n/a |
| Ações dos estados (`Buscar outro produto`, `Tentar de novo`…) | `.btn-secondary` | `--bg-subtle` | outline global | `--bg-muted` | n/a | `Tentar de novo` vira spinner + `Tentando…` | n/a | n/a |
| Linha da lista (não interativa) | `--bg-surface` | `--bg-table-row-hover` | n/a | n/a | n/a | skeleton | n/a | n/a |

Hovers em `@media (hover: hover)`. Transições só de cor/borda (`--transition-fast`), nunca de `width`/`height`/`padding`. `translateY(-1px)` nos botões é opcional e fica desligado com `prefers-reduced-motion`.

---

## 7. Acessibilidade

1. **Teclado:** ordem do DOM = ordem visual (nav de seções → ModeSwitch → campo → botão → resultado → pager). ModeSwitch com roving tabindex (só o segmento selecionado tem `tabindex="0"`).
2. **Regiões vivas:** um `role="status"` por modo, sempre no DOM, anuncia: `Buscando sugestões…` → `{n} sugestões para {descrição A}.` / `{n} sugestões para o cliente {código}.` / o título do estado vazio. Erros de campo são anunciados via `aria-describedby` + foco no input; falha técnica via `role="alert"`.
3. **Foco:** após a busca o foco **fica** no botão (a região viva informa o resultado). Ao trocar de página, o foco vai para o `h3` do cabeçalho (`tabindex="-1"`), senão o usuário de teclado fica preso no rodapé.
4. **Listas:** `<ol>` semânticas; cada `<li>` com o nome do produto como primeiro texto. A barra de proporção e os ícones são `aria-hidden`. O chip `▲ 4,3× mais que o normal` tem texto sr-only `4,3 vezes mais nesses pedidos do que no geral` (frase P-065.2 completa).
5. **Tags:** o sentido está no texto (`Sem estoque`, `Parou há 120 dias`), não na cor.
6. **Rótulos:** label visível em todos os campos (WCAG 2.5.3); botões só-ícone com `aria-label`.
7. **Alvos de toque:** mínimo 40×40px em segmentos, botões e "×" (24px mínimo exigido, 40px adotado).
8. **Idioma e números:** `lang="pt-BR"` herdado; números com vírgula decimal e `R$` pelo `LOCALE_ID` pt-BR.

---

## 8. Responsividade (testar em 320 / 375 / 414 / 768 px, sem scroll horizontal da página)

| Faixa | Comportamento |
| :--- | :--- |
| **Mobile < 640px** | Padding lateral `--space-4`. Nav de seções rola na horizontal **dentro do nav** (`overflow-x: auto`, `scroll-snap`, sem quebrar rótulo; `white-space: nowrap`), com o ativo `scrollIntoView` ao carregar. ModeSwitch ocupa 100% com 2 segmentos iguais. Formulário em coluna: campo 100%, botão 100% abaixo. Cabeçalho do resultado: selo de data quebra para baixo do título. Linha da lista em 1 coluna: posição + produto na 1ª linha, explicação, barra, sinais (tags com `flex-wrap`), "Ver números". `<dl>` de números em 2 colunas. Pager: `‹` e `›` com rótulo curto (`Anterior`/`Próxima`), contador acima. |
| **Tablet 640–1024px** | Formulário em linha (campo flex 1, botão auto). Linha da lista em 2 colunas: `[posição][produto + sinais]` em cima, explicação ocupando a largura toda embaixo. |
| **Desktop > 1024px** | Grid de 4 colunas da §5.6. Painel de consulta com largura máxima de 720px alinhado à esquerda (o resto fica em respiro), painel de resultado com a largura do container. |

Regras gerais: `grid-template-columns` com `minmax(0, …)`; `min-width: 0` + `overflow-wrap: anywhere` em descrições longas de produto; breakpoints `@media (max-width: 639.98px)` e `@media (max-width: 1023.98px)`, como nas telas atuais.

---

## 9. Copy deck

| Local | Texto |
| :--- | :--- |
| Navbar | Análises de Vendas |
| Página, título / subtítulo | Análises de Vendas / Consultas sobre o histórico de pedidos. Clientes aparecem só pelo código. |
| Seção | Cross-sell |
| Seção, h2 / apoio | O que oferecer junto / Produtos que costumam sair no mesmo pedido, a partir do histórico de vendas. |
| ModeSwitch | Por produto · Por cliente |
| Formulários, rótulos, hints e botões | ver §5.4 |
| Validação local | Digite só números, sem pontos ou letras. |
| Cabeçalhos de resultado | ver §5.5 |
| Selo de data | Pedidos até {dd/MM/yyyy} |
| Chips | ▲ {L}× mais que o normal · {N} pedidos · Sem estoque · Margem zero ou negativa · Custo estimado · Nunca comprou · Parou há {D} dias |
| Margem | Margem R$ {valor}/un. |
| Antecedentes extras | + {n} outro(s) produto(s) que o cliente compra também leva(m) a esta sugestão. |
| Divisor (D-9) | Outras sugestões |
| Disclosure | Ver números · Ocultar números |
| Loading | Buscando… (botão) · Buscando sugestões… (região viva) · aviso de primeira consulta (§6.2) |
| Estados vazios e erros | ver §6.3 e §6.4 |
| Pager | {a}–{b} de {total} · Anterior · Página {p} de {t} · Próxima |

Frases de explicação: **formato literal de P-065** (percentual inteiro, lift com 1 casa e vírgula). Termos "lift", "confiança", "suporte" e "pontuação" só aparecem dentro de "Ver números".

---

## 10. Fora de escopo nesta fase

- Autocomplete por descrição (depende de Q-1).
- Exportar CSV das sugestões (não pedido; no modo cliente exigiria avaliação do `privacy_officer`).
- Filtros/ordenação no cliente (quebrariam a paginação do servidor e a ordem definida nas regras).
- Gráficos, rede de associações, animações Anime.js (nada aqui pede movimento além das transições de estado; YAGNI).

---

## 11. Campos que a tela precisa do contrato (para o Arquiteto)

**Modo produto — `GET /analytics/cross-sell/product/{sku}`**
- `data` precisa identificar o **produto consultado** (antecedente): `codigo`, `descricao`, `fornecedor` — mesmo quando a lista vem vazia (o título do vazio usa a descrição). Sugestão: `data = { produto: {...}, recomendacoes: [...] }` ou o produto em `meta`. **(Q-2)**
- Por item: `codigo`, `descricao`, `fornecedor`, `confianca`, `lift`, `suporte`, `pedidosEmComum`, `estoqueAtual`, `semEstoque`, `margemNaoPositiva`, `custoEstimado` (se calculado no modo produto) e a explicação.
- **Explicação (Q-3):** preferência do Designer: o backend devolve as frases prontas e testadas (P-065), separadas, por exemplo `explicacao: { frequencia, intensidade, evidencia }` (produto) e `explicacao: { motivo, frequencia }` (cliente), e não um parágrafo único. A tela precisa separá-las (chips, ordem visual e texto sr-only).

**Modo cliente — `GET /analytics/cross-sell/customer/{customerCode}`**
- Por item: `codigo`, `descricao`, `fornecedor`, `antecedente { codigo, descricao }`, `lift`, `confianca`, `margemUnitaria`, `custoEstimado`, `pontuacao`, `motivo`, `diasDesdeUltimaCompra`, `qtdAntecedentesRelacionados` e explicação. `pedidosEmComum` também é útil para "Ver números" **(Q-4)**.
- `meta.motivoVazio` (`SEM_COMPRAS_RECENTES`) e eco do `customerCode` consultado (só o código).

**Comum (`meta`)**: `timestamp`, `dataReferencia`, `page`, `limit`, `offset`, `totalItems`, `totalPages`.

**Perguntas**
- **Q-1:** o endpoint `/analytics/products/search?q=` (Fase 4) pode ser antecipado para esta fase? Comprador costuma lembrar a descrição, não o código. Sem ele, a busca é por código (D-7).
- **Q-2:** onde vem o produto consultado (descrição/fornecedor) — em `data` ou `meta` — inclusive com lista vazia?
- **Q-3:** explicação montada no backend em frases separadas (recomendado) ou campos estruturados para o frontend montar?
- **Q-4:** `pedidosEmComum` e `suporte` no item do modo cliente?
- **Q-5:** `meta` pode expor `dormantDays` e `customerProfileDays` para a copy dos vazios não fixar 90 dias/12 meses?
- **Q-6:** formato do corpo de erro (`code`, `message`, `fields[]` no `XSL-004`) — a tela mapeia por `code`, nunca por texto.
- **Q-7:** `GET /analytics/health` informa se o cache está frio? Se sim, a tela pode avisar antes da busca que a primeira consulta demora (§6.2), em vez de esperar 4 s.

---

## 12. Decisões de design a validar no checkpoint

| # | Decisão |
| :--- | :--- |
| D-1 | Seguir os tokens reais de `styles.scss` (Papel & Tinta), não os de `DESIGN_SYSTEM.md` (teal/Plus Jakarta), e atualizar o `DESIGN_SYSTEM.md` em tarefa separada. |
| D-2 | Item da navbar: "Análises de Vendas". |
| D-3 | Seções do `/analytics` como rotas filhas lazy com nav de links (`aria-current`), não tablist. |
| D-4 | Seções futuras não aparecem como "em breve"; entram uma a uma. |
| D-5 | Produto/Cliente como controle segmentado com semântica de abas (mesma rota), estado preservado por modo. |
| D-6 | SKU vai para a URL; código do cliente não vai (privacidade). |
| D-7 | Busca por código nesta fase (sem autocomplete), salvo resposta positiva a Q-1. |
| D-8 | Itens sinalizados no modo produto não são esmaecidos nem reordenados; só recebem tags. |
| D-9 | Destaque das 5 primeiras sugestões do cliente ("Prioridade") e divisor "Outras sugestões". |
| D-10 | "Ver números" por linha, fechado por padrão. |
| D-11 | Página fixa de 50 itens, sem seletor de tamanho. |

---

## 13. Critérios de aceite visuais (UX Reviewer, Etapa 4)

- [ ] `/analytics` abre na seção Cross-sell; o item da navbar fica ativo; adicionar uma seção nova exige só uma entrada de configuração e uma rota.
- [ ] Os textos principais das linhas não contêm "lift", "suporte", "confiança" nem "pontuação" (CA-14); esses termos só aparecem em "Ver números".
- [ ] Modo produto: item com `semEstoque` mostra a tag "Sem estoque" com ícone; com `margemNaoPositiva`, "Margem zero ou negativa" (CA-10, A-8).
- [ ] Modo cliente: motivo "Nunca comprou" ou "Parou há {D} dias" em todas as linhas; nenhum dado do cliente além do código (CA-22).
- [ ] Lista vazia (C-02, C-06, C-07) mostra o vazio específico com ação, nunca erro; `XSL-001`/`XSL-002` aparecem inline no campo; `XSL-003` mostra "Ainda não dá para recomendar com segurança"; falha técnica mostra banner com "Tentar de novo"; nenhum `detail` cru.
- [ ] Skeleton com 5 linhas durante a busca; nenhum vazio aparece enquanto carrega; aviso de primeira consulta após 4 s.
- [ ] Código do cliente ausente da URL, do `localStorage` e do `sessionStorage`.
- [ ] ModeSwitch operável por setas; foco visível em todos os elementos; regiões vivas anunciam resultado.
- [ ] Sem scroll horizontal da página em 320/375/414/768 px; nav de seções rola dentro de si.
- [ ] Nenhum hex/rgba literal nem fallback hex nas regras novas; nenhum `outline: none` sem `:focus-within` substituto.
