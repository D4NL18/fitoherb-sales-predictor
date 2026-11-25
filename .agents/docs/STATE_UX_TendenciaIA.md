# UX Review (Vibe Check) - Painel "Por que?" (F7, fase 7.3)

Escopo: commit e84783f e anteriores da fase 7.3, em `frontend/src/app/features/sales-trend/`.
Referências: `design/plans/analytics-tendencia-ia.md`, `DESIGN_SYSTEM.md`, `frontend-ui-anti-patterns.md`.
Método: análise estática do código; `ng build` passa (só o warning de budget do bundle inicial, 552 kB contra 512 kB). Não foi feita verificação em navegador: o painel depende de backend e dados autenticados não disponíveis neste ambiente. Os itens marcados (a verificar) precisam de conferência visual.

Veredito: APROVADO COM RESSALVAS. Não há bloqueante estético nem de privacidade. Há 4 itens importantes a corrigir antes do PR.

## Conformidade verificada (OK)

- Anti-IA: sem gradiente azul-roxo, sem 3 colunas com ícones, sem sparkles, sem buzzwords. Fonte de título (`--font-family-headline`) pareada com corpo. Cores só por tokens (nenhum hex/rgb nos componentes); os `px` são hairlines, anéis de foco e alvos de toque.
- Sem valor em dólar, tokens ou saldo na UI. As únicas ocorrências são comentários e o enum `ORCAMENTO_ESGOTADO`, que vira texto neutro. `orcamento.nivel` não é renderizado.
- Rótulos por `meta.origem`: `llm` e `fallback` viram "Gerada por IA", `cache` vira "Análise salva", `template` vira "Resumo automático (sem IA)". O aviso fixo some no `template`. O modelo só aparece em "Detalhes técnicos".
- 8 estados do bloco de IA: vazio, gerando, sucesso, salva, confirmando, template, limite e erro estão implementados. Existe também `semVariacao`. Há skeleton no carregamento, no recarregamento e na geração (sem spinner isolado), sem barra de percentual, com `role="status"` e contador `aria-hidden`.
- Empty states: `SEM_VARIACAO`, grupo afim vazio e bloco de IA vazio têm ícone, título e texto. O botão fica logo abaixo.
- Texto da IA por interpolação (sem `innerHTML`). `sugestoesBuscaHtml` fica só em `iframe sandbox` sem `allow-scripts`, com `referrerpolicy="no-referrer"`. Fontes usam `rel="noopener noreferrer"`.
- Diálogo: `role="dialog"`, `aria-modal`, `aria-labelledby`/`describedby`, foco no `h2`, `Esc` (cancela a confirmação antes de fechar), focus trap, `lockBodyScroll`, botão Fechar com `aria-label` (44x44), devolução de foco ao gatilho (com fallback no `h1`), `prefers-reduced-motion`.
- Geometria: `min(720px,100vw)`; 640 px entre 768 e 1023; tela cheia e sem raio abaixo de 768 px, com backdrop transparente.
- `?porque=` é lido com validação por regex `^\d{1,10}$`, aplicado com `replaceUrl` e removido ao fechar. `?abrir=` sai do painel pelos links de canibalização e é consumido em `cannibalization-page`.
- Contraste: `--text-muted` (#666F67) sobre `--bg-canvas` (#F5F2EB) dá cerca de 4,6:1. `--text-secondary`, o badge `--feedback-info-bg` e `--brand-primary` passam em AA.

## Importante (corrigir antes do PR)

1. **A navbar não fica `inert` com o painel aberto.** Arquivo: `pages/sales-trend-page/sales-trend-page.component.ts:54`. Só `.trend-container` recebe `inert`; o plano §6.1 exige `<main>` e navbar. O trap de foco só atua quando o foco está em primeiro ou último. Se o usuário clicar em área não focável e apertar Tab, o foco vai para a navbar atrás do painel (viola a regra a11y de focus trap).
   Correção: aplicar `inert` à navbar (via serviço ou atributo no layout) enquanto `insights.context()` existir. No `onKeydown`, tratar também o caso de `activeElement` fora do painel: forçar o foco no primeiro focável.
2. **O seletor de janela é desabilitado durante o GET e o foco se perde.** Arquivos: `trend-insight-panel.component.ts:289-291` e `segmented-control` (botão `[disabled]`). Um botão desabilitado que tem o foco o perde (volta ao `body`). O plano §6.1 diz "o foco fica no seletor".
   Correção: usar `aria-disabled="true"` com bloqueio do clique, ou devolver o foco ao rádio ativo após o GET, em `queueMicrotask`.
3. **O recarregamento empilha skeleton e conteúdo antigo.** Arquivo: `trend-insight-panel.component.ts:126-128`. O plano §8 pede conteúdo esmaecido e skeleton só na cascata. O código renderiza o skeleton completo do painel (resumo, 7 linhas, afins) acima do conteúdo esmaecido, o que empurra o conteúdo e causa salto de layout (CLS).
   Correção: usar skeleton só no lugar da cascata (`part="waterfall"`), ou sobrepor o skeleton em posição absoluta. Alternativa: manter só o `opacity` com `aria-busy`.
4. **Região viva do painel com anúncio da janela obsoleto.** Arquivo: `trend-insight-panel.component.ts:285,368-385,403-410`. `windowAnnouncement` é um campo comum escrito dentro de um `effect` e lido dentro de um `computed`. O `computed` pode ser avaliado antes da escrita, então "Janela alterada para X" sai atrasado ou não sai. O campo também nunca é limpo e reaparece depois.
   Correção: tornar `windowAnnouncement` um `signal`, limpando-o em um `setTimeout` ou ao mudar o estado da IA.

## Nit

5. **O aviso fixo de IA não aparece no estado vazio.** `insight-view.ts:375` define `showFixedNotice: false` em `vazio`, mas o plano §7 pede "e também no estado vazio, para o usuário saber antes de clicar". Correção: `showFixedNotice: true` no `vazio` quando `geraComIa`.
6. **Duplo anúncio em leitores de tela.** `role="alert"` (limite e erro) e `role="status"` (gerando) no bloco repetem a região viva do painel (`liveMessage`). Mantenha só uma fonte de anúncio por estado.
7. **`aria-describedby` do diálogo aponta para `summaryId`.** Esse elemento só existe depois do GET, então durante o carregamento o id está pendente. Condicione o atributo a `insight()`.
8. **Empty state do bloco de IA sem caixa de ícone.** O DESIGN_SYSTEM §6.3 pede o ícone em caixa `--color-neutral-100` equivalente (`--bg-muted`); hoje o SVG fica solto. O bloco também não tem o CTA dentro do empty state; o botão fica abaixo.
9. **Estados `:active` e hover incompletos.** `.btn-secondary` não tem `:active` (a matriz do plano §9 só exige no primário, mas o Design System pede os 8 estados). `.link-btn` não tem hover com sublinhado de 2 px.
10. **Deep link `?porque=` mostra o título provisório "Diagnóstico de produto 123"** até o GET terminar. Usar "Diagnóstico do produto {sku}" e evitar o texto minúsculo. A leitura é só do `snapshot`, então o botão voltar do navegador não reabre nem fecha o painel (a verificar se é desejado).
11. **Bundle inicial acima do budget** (552 kB contra 512 kB). Verificar se o painel e seus 10 componentes podem entrar em chunk lazy via `@defer`, conforme `frontend-asset-optimization-rules.md` (Modais devem usar Code Splitting).
12. **Verificações visuais pendentes (a verificar no navegador)** em 320, 375, 414 e 768 px: quebra do rótulo "Por que?", rolagem horizontal da cascata (grid de 2 colunas no mobile) e alvo de toque de 44 px dos `[›]` (plano pede 40x40).

## Resumo de correções sugeridas por arquivo

- `sales-trend-page.component.ts`: `inert` na navbar (item 1).
- `trend-insight-panel.component.ts`: trap de foco para foco externo (1), foco no seletor (2), skeleton só na cascata (3), signal para o anúncio (4), `aria-describedby` condicional (7).
- `segmented-control.component.ts`: `aria-disabled` em vez de `disabled` (2).
- `insight-view.ts`: aviso fixo no `vazio` (5).
- `ai-diagnosis-block.component.ts`: roles duplicados (6), caixa do ícone (8), estados `:active` e hover (9).
