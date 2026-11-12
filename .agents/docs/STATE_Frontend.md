# STATE_Frontend — Fase 1 Analytics Comercial (F4 Cross-sell) — Etapa 3 (Developer Frontend)

| Campo | Valor |
| :--- | :--- |
| Agente | `developer` (frente Frontend, `[PARALLEL]` com o Backend) |
| Data | 2026-11-09 |
| Branch | `feature/analytics-cross-sell` (sem commit; commits na Etapa 5) |
| Status | F-01 a F-12 (incl. F-11a) concluídos; aguardando Etapa 4 (`reviewer`, `ux_reviewer`) |

## Resultado
- `npx ng test --watch=false --browsers=ChromeHeadless`: **73/73 SUCCESS** (inclui T-13, T-14, T-15, T-18 e specs pré-existentes). Nenhum spec alterado.
- `npx ng build`: sem erro nem aviso. Initial total 511,99 kB (antes: 502,48 kB); lazy `cross-sell-page-component` 69,8 kB e `analytics-routes` 3,3 kB. **Atenção:** o initial fica a ~10 bytes do aviso de budget de 500 kB (o CLI mede em KiB); o acréscimo vem de código de router/rxjs promovido ao chunk compartilhado.
- `tsc -p tsconfig.spec.json --noEmit`: limpo.

## Arquivos (todos em `frontend/src/app/`)
- Alterados: `app.routes.ts` (rota lazy `analytics` antes do `**`), `core/layout/navbar/navbar.component.html` (item "Análises de Vendas").
- Criados em `features/analytics/`: `analytics.routes.ts`; `models/{analytics,cross-sell}.model.ts`; `services/{analytics.service,cross-sell.store}.ts`; `utils/{analytics-error,cross-sell-view,pt-br-format}.ts`; `pipes/pt-br-format.pipes.ts`; `styles/{_analytics-ui,recommendation-list,cross-sell-panel}.scss`; `pages/{analytics-shell,cross-sell-page}/`; `components/{code-search-form,product-cross-sell-panel,customer-cross-sell-panel,product-recommendations-list,customer-recommendations-list,recommendation-numbers,query-context-header,result-state,recommendation-list-skeleton,list-pager,error-banner,mode-switch}/`.

## Desvios em relação ao checklist / Design Plan
1. **Rótulo da navbar** "Análises de Vendas" (D-2 aprovado) no lugar de "Analytics Comercial" do F-06, como já registrado pelo Tester.
2. **`product-recommendations-list`** em vez de `product-recommendations-table` (F-09): o Design Plan pede lista ranqueada `<ol>`, não tabela. As linhas ficam no template da lista (sem `*RowComponent` separado) e a navegação de seções fica inline na casca (sem `AnalyticsSectionNavComponent`), com a constante `ANALYTICS_SECTIONS`.
3. **Estado no `CrossSellStore`** (decisão do Tester, F-07), provido na `CrossSellPageComponent` (morre com a página), em vez de signals locais na página (§4 do Design Plan). Os painéis por modo leem o store; os demais componentes são burros.
4. **Nova busca descarta o resultado anterior** do modo. Com erro de campo (XSL-001/002/004), a área volta ao estado inicial em vez de "estado anterior à busca" (§6.1 #8). Motivo: não mostrar sugestões de outro código sob a busca nova (também LGPD no modo cliente).
5. **Banner de falha técnica sem botão "Fechar aviso"**: fechar deixaria a área de resultado vazia. Ficou só "Tentar de novo" (refaz a mesma página via `goToPage`).
6. **Copy do `empty-page`**: "volte para o começo" em vez de "voltamos para o começo", porque não há redirecionamento automático; a ação é o botão "Ir para a primeira página".
7. **Combobox (F-12)**: `inputmode="search"` no modo produto (aceita descrição); a seleção só preenche o SKU, sem disparar a busca (D-7 / T-18). O placeholder e o hint do modo produto citam a busca por descrição.
8. **D-6**: `?modo=produto&sku=` é lido ao abrir (dispara a busca) e reescrito com `replaceUrl`; `?modo=cliente` nunca leva o código.
9. **Formatação pt-BR** por pipes próprios (`Intl` + arredondamento meio para cima em texto decimal), sem registrar `LOCALE_ID` pt-BR no app. Assim os chips ("4,3×") batem com as frases do backend (P-065).

## Specs possivelmente questionáveis (não alterados)
- Nenhum spec impede o contrato. Observação: `code-search-form.component.spec.ts` exige "Digite só números, sem pontos ou letras." ao enviar texto livre no combobox. Com a busca por descrição, uma mensagem como "Escolha um produto da lista ou digite o código" seria mais clara (avaliar com o UX Reviewer).

## Pontos para o UX Reviewer
- Aviso de cache frio aparece abaixo do ModeSwitch até a primeira resposta chegar; o skeleton mostra o aviso de lentidão após 4 s.
- Foco vai ao `h3` do cabeçalho após paginar; a região viva `role="status"` de cada modo anuncia o resultado.
- Tags/selos usam as classes globais `.tag-*`; o chip de lift e "N pedidos" usam `--brand-primary` sobre `--brand-primary-subtle`.
- Destaque D-9 (5 primeiras, divisor "Outras sugestões") só na página 1 do modo cliente.
- Conferir responsividade em 320/375/414/768 px e o anel de foco do campo (`:focus-within`).

---

## Auto-healer Etapa 4 (veto do `ux_reviewer`, `STATE_UX.md`) — 2026-11-10
Sem commits (ficam para a Etapa 5). Caminhos relativos a `frontend/src/app/features/analytics/`.

### Bloqueantes
- **B-1** `components/code-search-form/code-search-form.component.{ts,html}`: `debounceTime` trocado por `switchMap` + `timer`, com sentinela `queries.next(null)` → `EMPTY`. Enviar, escolher uma opção, limpar, Escape e `blur` cancelam a busca pendente e a que está em voo (`cancelSearch()`). A resposta só abre a lista se o termo ainda é o valor do campo, o campo está focado (`activeElement`) e não há carregamento. `expanded` também exige `!loading()`.
- **B-2** `components/mode-switch/mode-switch.component.scss`: `.segment.selected:focus-visible { outline-color: var(--text-on-brand) }`, anel branco interno (offset -3px) sobre `--brand-primary`; contraste ~11:1. `overflow: hidden` do grupo mantido (o anel é interno).
- **B-3**: input novo `invalidFormatMessage` no formulário (padrão = XSL-004). O modo produto passa `PRODUCT_INVALID_FORMAT_MESSAGE` (`utils/analytics-error.ts`): "Escolha um produto da lista ou digite o código (só números)." O modo cliente e o XSL-004 vindo da API continuam com "Digite só números, sem pontos ou letras.". Busca sem resultado mostra `Nenhum produto encontrado para "{termo}".` numa região `role="status"` (sempre no DOM, `sr-only` quando vazia). Enter sem opção ativa e com uma única opção seleciona essa opção. Rótulo "Produto (código ou descrição)". Estado inicial: "Digite o código ou parte da descrição de um produto…".

### Não bloqueantes
- **NB-1**: durante o carregamento, Enter com código **diferente** do último enviado emite `search` (o store cancela o `inFlight`); com o mesmo código, ignora. O SKU vindo da URL conta como último enviado.
- **NB-2**: um aviso só, `COLD_CACHE_NOTICE` (`utils/cross-sell-view.ts`): "A primeira consulta após um período sem uso monta a base de pedidos e pode levar até meio minuto." A página o mostra antes da primeira busca e o esconde durante o carregamento; o skeleton o mostra após 4 s numa região `role="status" aria-live="polite"` sempre presente. Saiu a variante com a duração do health (`formatDuration`).
- **NB-3**: skeleton com a mesma grade, gap, filete esquerdo e breakpoints de `styles/recommendation-list.scss` (explicação em largura total no tablet, sinais em largura total e `padding: var(--space-4)` no mobile).
- **NB-4**: "Principal produto que sai junto com…" / "Principais produtos que saem junto com…".
- **NB-5**: vazio do produto: "Não achamos produtos que saiam junto com este com frequência suficiente para virar sugestão. Variações dele mesmo (outro sabor, cor ou tamanho) não entram na lista." (não afirma a causa).
- **NB-6**: `.active` depois do hover, com `&.active, &.active:hover`.

### Specs (alterações de expectativa + novos)
- `code-search-form.component.spec.ts`: rótulo novo; `invalidFormatMessage` do modo produto no `beforeEach`; T-18 de texto livre agora espera a mensagem nova; helper `type` foca o campo (a lista só abre com foco). Novos: XSL-004 da API mantém a mensagem; enviar fecha e mantém fechada a lista com busca pendente e com busca em voo; lista fecha ao entrar em loading; "Nenhum produto encontrado" em `role=status`; Enter com opção única seleciona; Enter durante loading envia código diferente e ignora o mesmo; Enter no campo do cliente envia a consulta.
- `product-cross-sell-panel.component.spec.ts`: validação local espera a mensagem nova do modo produto.

### Resultado
- `npx ng test --watch=false --browsers=ChromeHeadless`: **81/81 SUCCESS** (antes 73).
- `npx ng build`: sem erro nem aviso. Initial total **511,94 kB** (antes 511,99 kB); lazy `cross-sell-page-component` 66,29 kB, `analytics-routes` 3,27 kB.
- `tsc -p tsconfig.spec.json --noEmit`: limpo.

### Fora do escopo
- **NB-7** (anunciar "{n} produtos encontrados"): não pedido nesta rodada; só o caso sem resultado é anunciado.
- **NB-8** (bundle inicial a ~10 bytes do budget de 500 kB): investigação com `--stats-json` fica com DevOps na Etapa 5.
- **NB-9**: só registro de copy.
