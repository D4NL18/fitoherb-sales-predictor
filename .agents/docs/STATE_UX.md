# STATE_UX — Fase 1 Analytics Comercial (F4 Cross-sell) — Etapa 4 (UX Review)

| Campo | Valor |
| :--- | :--- |
| Agente | `ux-reviewer` |
| Data | 2026-11-10 |
| Branch | `feature/analytics-cross-sell` (sem commits) |
| Escopo | `frontend/src/app/features/analytics/**`, `app.routes.ts`, `core/layout/navbar/navbar.component.html` |
| Referências | `design/plans/analytics-cross-sell.md`, `frontend/src/styles.scss` (D-1), `~/.claude/rules/frontend-ui-anti-patterns.md` |
| Método | Leitura do código + verificação em Chrome headless (CDP) contra `ng serve` local (:4211) e API local: Enter nos dois modos, combobox durante o loading, overflow em 320/375/414/768 px, anel de foco por teclado |
| **Veredito** | ~~VETADO~~ (2026-11-10, 1ª rodada) → **APROVADO COM RESSALVAS** após revalidação (ver §5) |

Desvios aprovados e fora da auditoria: remoção de "Ver números" e de toda exibição de margem; curadoria P-094 (≤ 10 itens) e títulos "Principais produtos…"; desvios 1–9 de `STATE_Frontend.md`; URL do modo cliente só com `?modo=cliente` (D-6).

---

## 1. Bloqueantes

### B-1 — Lista de sugestões do combobox reabre durante "Buscando…" (achado 1 do Orquestrador: CONFIRMADO)
- **Arquivo:** `components/code-search-form/code-search-form.component.ts:113-126` (`onSubmit`) e `:165-183` (`listenProductSearch`).
- **Reprodução (headless):** digitar `780119` e dar Enter. A rede mostra `cross-sell/product/780119` e, **depois** dele, `products/search?q=780119`. Em 200, 600 e 1200 ms: `aria-expanded="true"` com o botão em "Buscando…".
- **Causa:** `onSubmit` chama `closeList()`, mas não cancela a consulta pendente no `debounceTime(300)` nem a requisição em voo do `switchMap`. Quando a resposta chega, o `subscribe` faz `listOpen.set(options.length > 0)` e reabre a lista, até sem foco no campo (clique no botão já disparou `blur`). No cold start a busca de produto também espera a carga (~25 s), então a lista aparece no meio do skeleton.
- **Correção:**
  1. Cancelar a busca ao enviar, selecionar, limpar e no `blur`: emitir um sentinela (`this.queries.next(null)`) e no pipe usar `switchMap(q => q === null ? EMPTY : …)`, ou um `Subject` de cancelamento com `takeUntil` por consulta.
  2. No `subscribe`, só abrir se a consulta ainda corresponde ao valor atual (`query === this.value().trim()`), se o input está focado (`document.activeElement === input`) e se não está carregando.
  3. Defesa no template: `expanded = computed(() => this.listOpen() && this.suggestions().length > 0 && !this.loading())`.
  4. Spec novo (Tester): "digitar, enviar antes do debounce → lista não abre durante o loading".

### B-2 — Foco invisível no segmento selecionado do ModeSwitch (WCAG 2.4.7)
- **Arquivo:** `components/mode-switch/mode-switch.component.scss:40-47`.
- **Verificação (Shift+Tab a partir do campo):** `#xs-tab-product` em `:focus-visible` com `outline: solid rgb(29,69,40) 2px; offset -3px` sobre `background: rgb(29,69,40)`. O anel tem a cor do fundo e não aparece.
- **Causa:** `--border-focus` = `--brand-primary` (`#1D4528`), e o `outline-offset: -3px` desenha o anel **dentro** do segmento selecionado, que tem o mesmo fundo. Com roving tabindex, o foco do teclado **sempre** cai no segmento selecionado, então o usuário de teclado nunca vê onde está.
- **Correção:** no `.segment.selected:focus-visible`, usar `outline-color: var(--text-on-brand)` com offset negativo (anel branco interno), ou manter `--border-focus` com `outline-offset: 2px` externo. Para o anel externo, trocar `overflow: hidden` do `.mode-switch` (linha 9) por raios nos segmentos extremos, porque o `overflow: hidden` corta o anel.

### B-3 — Mensagem "Digite só números, sem pontos ou letras." contradiz a busca por descrição (achado 4 / spec T-18: a mensagem NÃO faz sentido no modo produto)
- **Arquivos:** `code-search-form.component.ts:118-121` (usa `ANALYTICS_ERROR_MESSAGES['XSL-004']` nos dois modos); `product-cross-sell-panel.component.html:3-5`; spec `code-search-form.component.spec.ts:164`.
- **Problema:** o placeholder diz "ex.: 10432 ou chá verde" e o hint diz "digite parte da descrição e escolha na lista". Quem digita "chá verde" e dá Enter sem escolher uma opção (caminho natural) vê "Digite só números, sem pontos ou letras.", que manda abandonar a busca por descrição anunciada pela própria tela. O mesmo acontece quando a busca não acha nada: a lista não abre e não há aviso de que não houve resultado, então o Enter também cai nessa mensagem.
- **Correção:**
  1. No modo produto, para texto não numérico: `Escolha um produto da lista ou digite o código (só números).` No modo cliente e no `XSL-004` vindo da API, manter a mensagem atual. Sugestão: input `invalidFormatMessage` no `CodeSearchFormComponent`.
  2. Opcional, recomendado: Enter com a lista aberta e só **uma** opção seleciona essa opção.
  3. Busca sem resultado (≥ 2 caracteres, 0 itens): linha não interativa `Nenhum produto encontrado para "{termo}"` dentro do listbox ou abaixo do campo, anunciada por `role="status"`.
  4. O **Tester** atualiza o spec T-18 (linha 164) para a nova copy. A mudança é do spec, não um teste "removido".
  5. Ajustar a copy do modo produto: rótulo `Produto` (ou `Código ou descrição do produto`) no lugar de `Código do produto`, e o texto do estado inicial (`utils/cross-sell-view.ts:117`) para `Digite o código ou parte da descrição de um produto…`.

---

## 2. Não bloqueantes

| # | Arquivo:linha | Problema | Correção sugerida |
| :--- | :--- | :--- | :--- |
| NB-1 | `code-search-form.component.ts:116` | **Achado 2 (Enter no cliente) NÃO reproduzido:** em headless, digitar `2316` + Enter dispara `GET …/customer/2316` tanto entrando por `?modo=cliente` quanto trocando pela aba. O caminho de código está correto (envio implícito do `<form>`, `onKeydown` sai cedo sem lista). Causa provável do que o Orquestrador viu: durante o loading (25 s no cold start) o `onSubmit` faz `return` em silêncio. Se o usuário corrige o código e dá Enter, nada acontece e nada avisa. | Permitir nova busca durante o loading quando o código é **diferente** do que está em voo (o store já cancela o `inFlight`); se for igual, ignorar. Spec explícito "Enter no campo do cliente emite `search`" para travar regressão. |
| NB-2 | `recommendation-list-skeleton.component.html:29-33` e `cross-sell-page.component.html:9-18` | **Achado 3 (cold start ~25 s):** o skeleton e o aviso informam, mas com duas falhas. (a) Com `estadoCache ≠ QUENTE`, a página mostra o aviso do health ("pode levar cerca de 26 segundos") e, após 4 s, o skeleton acrescenta outro aviso com outra redação ("depois de algumas horas…"): duas mensagens ao mesmo tempo, e "algumas horas" não descreve um cold start de Cloud Run. (b) Nenhum dos avisos está em região viva: o leitor de tela só ouve "Buscando sugestões…" por 25 s. | Um aviso só, dentro do skeleton, com a duração do health quando houver (`coldCacheNotice`), e o texto genérico sem "algumas horas" ("A primeira consulta monta a base de pedidos e pode levar até meio minuto. As próximas são rápidas."). Atualizar a região viva para esse texto após 4 s. Opcional: contador de segundos decorridos. |
| NB-3 | `recommendation-list-skeleton.component.scss:46-56` | Geometria do skeleton diverge da linha real em ≤ 1023 px: grid `40px minmax(0,1fr)` com 4 filhos põe o bloco de explicação (barra fixa de 120 px) na coluna de 40 px. Além disso, o padding não cai para `--space-4` no mobile. Sem scroll horizontal da página (medido), mas o skeleton "pula" ao virar lista. | Replicar as regras de `recommendation-list.scss:164-180`: explicação `grid-column: 1 / -1` no tablet, sinais em largura total no mobile e `padding: var(--space-4)` < 640 px. |
| NB-4 | `utils/cross-sell-view.ts:188` | Concordância no singular: "Principal produto **que saem** junto com X". | `count === 1 ? 'Principal produto que sai junto com' : 'Principais produtos que saem junto com'`. |
| NB-5 | `utils/cross-sell-view.ts:124` | O vazio do produto ("nenhum se repete com frequência suficiente") não cobre o caso da curadoria P-094 em que a única regra era uma variante da origem (ex.: 870009). | Texto neutro: "Não achamos produtos que costumam sair junto com este, além de variações dele mesmo." |
| NB-6 | `code-search-form.component.scss:135-141` | No combobox, o `:hover` vem depois de `.active` e sobrescreve o destaque da opção ativa por teclado quando o mouse está em cima. | Mover `.active` para depois do hover, ou `&.active, &.active:hover`. |
| NB-7 | `code-search-form.component.ts:178-182` | A quantidade de opções encontradas não é anunciada (só `aria-expanded`). | Região viva "{n} produtos encontrados" (junto com o item 3 de B-3). |
| NB-8 | Bundle inicial (`STATE_Frontend.md`) | **Achado 5:** 511,99 kB (base 1000) ≈ 499,99 KiB, a ~10 bytes do `maximumWarning: 500kB` do `angular.json`. O código do analytics é lazy (69,8 kB + 3,3 kB); o acréscimo de ~9,5 kB vem de router/rxjs promovidos ao chunk compartilhado. Efeito no LCP desprezível (~2 %), mas qualquer próxima feature quebra o aviso. | Não bloqueia UX. Developer/DevOps: `ng build --stats-json` + `source-map-explorer` para ver o que subiu ao initial (provável `debounceTime`/`switchMap`, já usados no lazy). Rever o budget com decisão registrada, sem só aumentá-lo. Rodar Lighthouse CI (LCP/CLS) na Etapa 5. |
| NB-9 | `analytics-shell.component.html` | Rótulo da navbar e do hero "Análises de Vendas" e seção "Cross-sell" (anglicismo), aprovado em D-2/D-3. Só registro. | Avaliar "Venda casada" **não** (CDC); manter "Cross-sell" ou "Ofertas combinadas" numa revisão de copy futura. |

---

## 3. Conformidade verificada (OK)

- **Tokens (D-1):** todas as regras novas usam `var(--…)` de `styles.scss`; nenhum hex/rgba literal nem fallback hex em `features/analytics/**/*.scss`. `outline: none` só no input, com `:focus-within` no container (`code-search-form.component.scss:51-55`), e no `h3` com `:focus-visible` substituto.
- **Anti-IA:** sem gradiente, sem "AI Purple", sem 3 colunas com ícones, sem ✨, sem buzzwords, sem itálico em títulos, sem fake chrome. Lista ledger alinhada à esquerda, font pairing Signika / Source Sans 3 / Overpass Mono, estados vazios alinhados à esquerda.
- **Estados:** skeleton com 5 linhas na geometria real (pulse sólido, `prefers-reduced-motion` respeitado), spinner só dentro do botão com rótulo, estado inicial guiado, 4 vazios com ação, `XSL-003` com filete de aviso, banner de falha técnica com "Tentar de novo", sem `detail` cru. Erros de campo inline com `aria-invalid` + `aria-describedby`.
- **Acessibilidade:** labels visíveis, `role="search"`, combobox com `aria-activedescendant`, tablist com roving tabindex e setas/Home/End, regiões vivas por modo, foco no `h3` ao paginar, `<ol start>` com posição `aria-hidden`, tags com texto (não só cor), alvos ≥ 40 px, `aria-current` no nav de seções.
- **Responsividade (medido com dados reais, 10 linhas):** `scrollWidth === clientWidth` em 320, 375, 414 e 768 px; nenhum elemento passa da viewport; nenhum botão quebra em duas linhas.
- **Rotas/navbar:** `/analytics` lazy antes do `**`, redireciona para `cross-sell`; item "Análises de Vendas" com ícone `aria-hidden` e `routerLinkActive` cobrindo as filhas.
- **Privacidade na UI:** só o código do cliente aparece; nada em storage; URL do modo cliente sem código (D-6).

## 4. Retorno à esteira
Devolver ao **developer** (B-1, B-2, B-3 + NB recomendados) e ao **tester** (spec T-18 linha 164; novos specs de B-1 e NB-1). Depois da correção, o `ux-reviewer` revalida só B-1 a B-3 (foco por teclado no ModeSwitch, combobox durante o loading, copy do modo produto).

---

## 5. Revalidação (2026-11-10, após o auto-healer do developer)

**Escopo:** só B-1 a B-3 e a ressalva sobre `aria-busy` (pedido do Orquestrador). Método: `ng serve` próprio em `127.0.0.1:4212` (encerrado ao final; a 4210 do Orquestrador não foi tocada) + API local :8000, Chrome headless via CDP. A resposta de `cross-sell/*` foi segurada 7 s (`Fetch.requestPaused`) para simular o cold start. Resumo do developer em `STATE_Frontend.md` § "Auto-healer Etapa 4"; Karma 81/81 e `ng build` sem aviso, conforme o Orquestrador.

| Item | Resultado | Evidência no navegador |
| :--- | :--- | :--- |
| **B-1** lista aberta durante "Buscando…" | **RESOLVIDO** | Digitar `780119` + Enter imediato: `aria-expanded="false"` e 0 opções em 300, 800, 1500, 3000 e 5000 ms com o botão em "Buscando…". A busca de produto **não sai** (só `cross-sell/product/780119`): o sentinela `queries.next(null)` cancela o `timer` do debounce. Com texto ("cha verde"), a lista abre normalmente (13 opções) quando o campo está focado e nada carrega. Código: `code-search-form.component.ts:139-154`, `:182-187`, `:228-239`; `expanded` com `!loading()` (`:87-89`). |
| **B-2** foco invisível no ModeSwitch | **RESOLVIDO** | Shift+Tab do campo → `#xs-tab-product` `:focus-visible` com `outline: solid rgb(255,255,255) 2px; offset -3px` sobre `rgb(29,69,40)`. Após →, `#xs-tab-customer` selecionado e focado com o mesmo anel branco. Contraste do anel ≈ 11:1 (≥ 3:1 de WCAG 1.4.11). `mode-switch.component.scss` (`&.selected:focus-visible`). |
| **B-3** mensagem numérica no modo produto | **RESOLVIDO** | Texto livre + Enter no produto: "Escolha um produto da lista ou digite o código (só números)." Rótulo "Produto (código ou descrição)". Estado inicial "Digite o código ou parte da descrição de um produto…". Busca sem resultado (`zzqxw`): `role="status"` com `Nenhum produto encontrado para "zzqxw".`. Modo cliente com `abc`: mantém "Digite só números, sem pontos ou letras.". |

### Ressalva do developer: região viva do aviso de cold start dentro de `aria-busy="true"`
- **Situação:** `recommendation-list-skeleton.component.html:32` (`<p class="slow-notice" role="status" aria-live="polite">`) fica dentro de `<section class="result-panel" [attr.aria-busy]="'true'">` (`product-cross-sell-panel.component.html:16`, `customer-cross-sell-panel.component.html:13`) durante todo o carregamento.
- **O que o Chrome faz (medido):** com 7 s de loading, o texto "A primeira consulta após um período sem uso…" está **exposto** na árvore de acessibilidade (`StaticText`, `ignored: false`). Logo o conteúdo não some: dá para lê-lo navegando.
- **O anúncio automático não é garantido.** Pela WAI-ARIA 1.2, `aria-busy="true"` indica que as tecnologias assistivas *podem* ignorar mudanças na região até o fim do carregamento. NVDA, JAWS e VoiceOver tendem a segurar ou descartar anúncios `polite` de descendentes de um contêiner ocupado, e o aviso só faz sentido **durante** o loading, justamente o período em que o contêiner está ocupado. Na prática o aviso pode chegar tarde ou não chegar. Não testei com leitor de tela real; o veredito se apoia na especificação e no comportamento conhecido.
- **Bloqueante? Não.** O mínimo da 1ª rodada (o aviso existe e é visível; a região `role="status"` do painel anuncia "Buscando sugestões…" fora do contêiner ocupado) está cumprido, e o caso afeta só um aviso informativo do cold start, não uma tarefa.
- **Correção recomendada (pequena, pode ir junto com a Etapa 5 ou numa próxima fase):** tirar a região viva do skeleton e reaproveitar o `<p class="sr-only" role="status">` do painel, que já fica **fora** da `section` ocupada (`*-cross-sell-panel.component.html`, última linha). Por exemplo, um sinal `slowLoading` no painel (timer de 4 s ligado ao `kind() === 'loading'`) faz `live()` trocar "Buscando sugestões…" pelo texto do aviso. O `<p>` visual do skeleton pode continuar, sem `role="status"`. Alternativa: mover `aria-busy` da `section` para o próprio contêiner do skeleton.

### Ressalvas que permanecem (não bloqueantes)
- **R-1:** região viva do cold start dentro de `aria-busy` (acima).
- **R-2 (NB-7):** quantidade de produtos encontrados no combobox não é anunciada (só o caso sem resultado).
- **R-3 (NB-8):** bundle inicial 511,94 kB, ainda a ~60 bytes do aviso de budget. Investigação com `--stats-json` fica com o DevOps na Etapa 5, e o Lighthouse CI (LCP/CLS) roda no release.
- NB-1 a NB-6 foram declarados corrigidos pelo developer e cobertos por specs. Não os revalidei no navegador (fora do escopo pedido), exceto o que aparece acima.

### Veredito final: **APROVADO COM RESSALVAS**
B-1, B-2 e B-3 estão resolvidos e verificados no navegador. As ressalvas R-1 a R-3 não bloqueiam a Etapa 5; R-1 é a correção de acessibilidade recomendada para a próxima oportunidade.
