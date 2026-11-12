# Design Plan — Política de Estoque Mínimo/Máximo 30/60 (Previsão de Estoque)

<!-- Hallmark · pre-emit critique: P4 H4 E4 S5 R5 V3 · macrostructure: workbench (preservada — evolução de tela existente) -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | P-053 a P-056 — Política Mín/Máx por dias de cobertura |
| **Branch** | `feature/P-053-estoque-min-max-30-60` |
| **Tela** | `frontend/src/app/features/inventory/pages/inventory-page/inventory-page.component.{html,scss,ts}` |
| **Regras** | `.agents/docs/business_rules/estoque-min-max.md` · `.agents/docs/GLOSSARY.md` |
| **Contrato** | Nomes fixados pelo Orquestrador: `historyWindowDays`, `leadTimeDays`, `minCoverageDays`, `maxCoverageDays`; item `estoqueMinimo`, `estoqueMaximo`. Formato de erro 422: ver contrato do Arquiteto em `.agents/docs/api_contracts/`. |
| **Design system de fato** | Tokens de `frontend/src/styles.scss` (Papel & Tinta: Signika + Source Sans 3 + Overpass Mono). Não existe `DESIGN_SYSTEM.md` neste repositório. |
| **Autor / Etapa** | Designer — Etapa 2 · 2026-11-05 |

---

## 1. User Story e objetivos de UX

**Story:** como comprador(a), quero ver Estoque Mínimo e Estoque Máximo de cada produto e quanto comprar para voltar ao máximo, para repor no ritmo real da distribuidora (tasks/estoque-min-max.md §2).

**Objetivos de UX**
1. A tela diz, sem abrir o modal, qual política gerou os números exibidos ("Política 30–60 dias", janela e lead time).
2. KPIs e status usam a mesma linguagem da política (mínimo/máximo, dias de venda); somem termos estatísticos (ROP, nível de serviço, ideal).
3. O modal mostra só 4 parâmetros e impede uma combinação inválida, explicando o motivo em texto sem corrigir os valores sozinho (CA-P053-05, CA-06, CA-08).
4. Nenhum resquício visual de trava física ou teto orçamentário (CA-07).

**Arquétipo de dashboard:** Operacional (5 KPIs de status + tabela de detalhamento). Macroestrutura existente preservada; mudanças são de conteúdo, estado e copy.

---

## 2. Checklist Anti-IA (auditado)

- [x] Sem gradiente azul-roxo; nenhuma cor nova. Superfícies sólidas do design system.
- [x] Tag do hero troca `tag-info` (azul) por `tag-neutral`: azul é a cor semântica de "Acima do Máximo" e não pode marcar a política.
- [x] Sem ✨, sem buzzwords. Removidos "Reposição Inteligente", "Inteligência Operacional B2B", "motor preditivo", "hiperparâmetros", "orçado".
- [x] Sem spinner isolado: skeleton para KPIs e tabela (spinner só dentro de botão com rótulo, padrão já existente).
- [x] Sem tela vazia: 3 variantes de empty state com ação.
- [x] Sem título em itálico; sem fake chrome; nenhum valor hex novo (regras novas consomem tokens sem fallback hex).
- [x] Erro nunca só por cor: ícone + texto + `aria-invalid`.

---

## 3. Tokens consumidos (`:root` de `styles.scss`)

**Nenhum token novo.** As regras novas ou alteradas usam apenas:

| Grupo | Tokens |
| :--- | :--- |
| Tipografia | `--font-family-headline`, `--font-family-body`, `--font-family-mono` |
| Superfície | `--bg-surface`, `--bg-subtle`, `--bg-muted` (skeleton) |
| Texto | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-on-brand` |
| Marca | `--brand-primary`, `--brand-primary-hover`, `--brand-primary-active` |
| Feedback | `--feedback-critical-bg` (erro), `--feedback-neutral-bg` e `--feedback-neutral-border` (tag do hero, via classe global `.tag-neutral`) |
| Borda / foco | `--border-subtle`, `--border-default`, `--border-focus` |
| Espaço | `--space-1` a `--space-6` |
| Raio / movimento | `--radius-xs`, `--transition-fast` |

**Proibido nas regras novas:** `--tag-bg-*` (não existem em `styles.scss`, só funcionam pelo fallback hex) e hex/rgba literais. Tamanhos de fonte reaproveitam os valores já usados na página (`0.74rem`, `0.78rem`, `0.85rem`, `1.65rem`).

**Contraste verificado (WCAG 2.1):**

| Par | Razão | Resultado |
| :--- | :--- | :--- |
| `--feedback-critical-bg` (#8F1B1B) sobre `--bg-surface` | 8,9:1 | AA texto |
| `--feedback-critical-bg` sobre `--bg-subtle` (rodapé do modal) | 7,3:1 | AA texto |
| `--text-on-brand` sobre `--feedback-critical-bg` (tag de valor inválida) | 8,9:1 | AA texto |
| `--text-on-brand` sobre `--feedback-neutral-bg` (tag do hero) | 10,3:1 | AA texto |
| `--text-muted` sobre `--bg-surface` (helpers, kpi-sub) | 5,2:1 | AA texto |
| `--text-muted` sobre `--bg-subtle` | **4,2:1** | **Reprova** → no rodapé do modal usar `--text-secondary` (8,0:1) ou `--feedback-critical-bg` |

---

## 4. Estado de parâmetros (pré-requisito visual)

Hoje os sliders gravam direto nos signals usados pelo cálculo: "Cancelar" não desfaz nada e uma combinação inválida vazaria para "Recalcular Estoque" e para o CSV. Como o hero e os KPIs passam a exibir `{min}`/`{max}`, a tela precisa separar o rascunho dos parâmetros aplicados:

| Conceito | Regra |
| :--- | :--- |
| `appliedParams` | `{ historyWindowDays: 60, leadTimeDays: 15, minCoverageDays: 30, maxCoverageDays: 60 }`. Só muda quando um cálculo **termina com sucesso**, recebendo os parâmetros enviados. Alimenta o hero, os subtítulos dos KPIs, os `title` dos cabeçalhos, "Recalcular Estoque" e o CSV (P-056.6). Fica salvo no cache local junto com o resultado. Cache sem esses campos é tratado como inválido (CA-12). |
| Rascunho do modal | Copiado de `appliedParams` ao abrir. Cancelar, "×", Esc ou clique no backdrop descartam o rascunho. "Aplicar e Recalcular" envia o rascunho. |
| Validação (computed sobre o rascunho) | `isMinMaxInvalid = max <= min` · `isLeadTimeInvalid = leadTime >= max` · `canApplyParams = !isMinMaxInvalid && !isLeadTimeInvalid`. Avaliada a cada movimento do slider. Os limites dos sliders são fixos: um slider nunca altera o valor do outro. |

Se o cálculo falhar, `appliedParams` não muda e a tela continua coerente com os números do cálculo anterior.

---

## 5. Anatomia por área

### 5.1 Hero

```
[h2] Previsão de Estoque e Compras   [tag-neutral] Política 30–60 dias
[p ] Compra quando o estoque chega ao mínimo e repõe até o máximo.
     Base: venda média dos últimos 60 dias · lead time de 15 dias.
                                   [Último cálculo] [Parâmetros] [Recalcular] [CSV]
```

- Título: `Previsão de Estoque e Compras`. "Estoque Ideal" é termo obsoleto no glossário e o menu já usa "Estoque e Compras".
- Tag: `<span class="tag tag-neutral">` sem `.tag-dot`. Conteúdo: `<span aria-hidden="true">Política {min}–{max} dias</span><span class="sr-only">Política de {min} a {max} dias de estoque</span>` (o leitor de tela costuma pular o travessão "–").
- Subtítulo (`.hero-subtitle`, sem mudança de estilo): `Compra quando o estoque chega ao mínimo e repõe até o máximo. Base: venda média dos últimos {janela} dias · lead time de {lead} dias.`
- Todos os valores vêm de `appliedParams`. Durante o loading, a tag e o subtítulo continuam com os valores aplicados (sem skeleton): eles só mudam quando o novo resultado chega, junto com a tabela.
- "Baixar Pedido CSV": acrescentar `|| isLoading()` ao `[disabled]` para não exportar durante um recálculo.

### 5.2 KPIs (proof bar)

Grid, ordem e cores sem mudança. Mudam rótulos e subtítulos:

| Card | Rótulo (`.kpi-label`) | Subtítulo (`.kpi-sub`) |
| :--- | :--- | :--- |
| `card-danger` | Ruptura Iminente | `Estoque acaba antes de um pedido chegar ({lead} dias)` |
| `card-warning` | **Abaixo do Mínimo** | `Cobre {min} dias de venda ou menos` |
| `card-healthy` | Estoque Saudável | `Cobre entre {min} e {max} dias de venda` |
| `card-overstock` | **Acima do Máximo** | linha 1: `Mais de {max} dias de venda, ou sem venda` · linha 2: `Capital parado: R$ {capitalImobilizadoOverstock}` (dois `div.kpi-sub`) |
| `card-financial` | Investimento Sugerido | `Compra até o máximo, a preço de custo` (o chip de trava física sai) |

- `{min}`, `{max}` e `{lead}` vêm de `appliedParams`, como inteiros sem formatação.
- "ou sem venda" no card Acima do Máximo explica por que SKUs sem venda com estoque (S8, CA-P055-06) entram nessa contagem.

### 5.3 Filtros de status (pílulas)

- Rótulos: `Todos (N)` · `Ruptura` · **`Abaixo do mínimo`** · `Saudável` · **`Acima do máximo`**.
- Acrescentar `[attr.aria-pressed]="statusFilter() === '<STATUS>'"` em cada pílula e `white-space: nowrap` em `.pill-btn` (o rótulo não pode quebrar em 320 px; o grupo já tem `flex-wrap`).

### 5.4 Tabela

**Colunas:** `Est. Mín.` e `Est. Máx.` ocupam as posições de `ROP` e `Est. Ideal` (entre Autonomia e Sug. Compra). O total continua em 13 colunas, então `colspan="13"` do empty state não muda.

```html
<th scope="col" class="text-center col-min"
    [title]="'Estoque mínimo: ' + appliedParams().minCoverageDays + ' dias de venda, em unidades'">
  <span aria-hidden="true">Est. Mín.</span><span class="sr-only">Estoque mínimo</span>
</th>
<!-- col-max: mesmo padrão com "Estoque máximo" / maxCoverageDays -->
...
<td class="text-center text-muted col-min">{{ prod.estoqueMinimo | number:'1.0-0' }}</td>
<td class="text-center font-medium col-max">{{ prod.estoqueMaximo | number:'1.0-0' }}</td>
```

- Hierarquia: o mínimo fica em `--text-muted` (referência) e o máximo em peso 600 (é o alvo da compra), como ROP e Est. Ideal estavam antes.
- VMD = 0: exibe `0` nas duas colunas (P-053.8). Não usar "—": o zero explica por que um SKU sem venda com estoque aparece como "Acima do Máximo".
- As colunas não são ordenáveis, como ROP e Ideal antes (YAGNI; evita 2 paradas de Tab a mais).
- SCSS: `.col-min, .col-max` entram nos grupos de alinhamento central e de `font-family-mono`/`tabular-nums`, com `min-width: 85px` (mesmo valor já usado em `.col-ideal`/`.col-estoque`, sem número novo).
- Cabeçalho Autonomia: acrescentar `[title]="'Dias de cobertura = estoque atual ÷ giro/dia. Política: ' + min + '–' + max + ' dias.'"`. O destaque `.text-danger` da autonomia em ruptura fica como está (o texto do status já cobre o sinal sem cor).
- `td.col-compra`: remover o `[title]` de "Demanda teórica / Limitado pela capacidade física".

**Decisão: barra de posição na faixa mín–máx — recusada (YAGNI).**
1. **Repete informação:** a faixa já está codificada em cada linha pelo status (Abaixo do Mínimo / Saudável / Acima do Máximo) e, em número, pela Autonomia. Uma barra colorida seria o terceiro sinal da mesma coisa ao lado de um badge já colorido.
2. **Não muda a decisão:** pela P-054.3 a compra é binária (estoque ≤ mínimo → compra até o máximo; senão, 0). Saber se o produto está em 35 ou 58 dias não muda nenhuma ação.
3. **Densidade:** a tabela tem 13 colunas e já rola na horizontal abaixo de ~1400 px. Uma barra legível pede célula mais larga ou fica ilegível.
4. **Casos de borda sem significado visual:** com VMD = 0 (mín = máx = 0, cobertura "∞") e com mín = máx (E5) não existe faixa para desenhar, o que exigiria estados especiais só para a barra.

Para dar contexto sem custo de layout ficam os `title` dos cabeçalhos (Est. Mín., Est. Máx. e Autonomia). Reavaliar só se compradores pedirem.

### 5.5 Modal de parâmetros

**Semântica e foco** (obrigatório, já que o modal é reescrito):
- `.modal-card`: `role="dialog" aria-modal="true" aria-labelledby="paramsModalTitle" aria-describedby="paramsModalDesc"`.
- Foco inicial em `#minCoverageInput`. Ao fechar, o foco volta ao botão "Parâmetros".
- Esc fecha e descarta o rascunho. Botão "×": `aria-label="Fechar parâmetros"`.
- Focus trap sem dependência nova (`@angular/cdk` não está instalado): `[attr.inert]="isSettingsModalOpen() ? '' : null"` nas `<section>` irmãs do modal (hero, filtros, tabela) e no bloco de alertas.

**Anatomia (ordem do DOM = ordem visual):**

```
Parâmetros da política de estoque                                   [×]
Valem para todos os produtos do próximo cálculo.
───────────────────────────────────────────────────────────────────────
POLÍTICA DE REPOSIÇÃO                                    (fieldset/legend)
  Dias de estoque mínimo                                    [ 30 dias ]
  ──●──────────────────────  (5–120, passo 5)
  Ao chegar a esse número de dias de venda, o produto entra na lista de compra.

  Dias de estoque máximo                                    [ 60 dias ]
  ─────●───────────────────  (10–180, passo 5)
  A compra sugerida leva o estoque até esse número de dias de venda.
  ⚠ (erro R1 substitui este helper)
- - - - - - - - - - - - - - - - (1px --border-subtle) - - - - - - - - - -
BASE DO CÁLCULO
  Janela de vendas recentes                                 [ 60 dias ]
  ────●────────────────────  (15–180, passo 15 — sem mudança)
  Período de vendas usado para calcular a venda média diária (VMD).

  Lead time de ressuprimento                                [ 15 dias ]
  ──●──────────────────────  (5–60, passo 1 — sem mudança, A5 fora de escopo)
  Prazo médio entre o pedido e a chegada no CD. Usado só para alertar
  ruptura iminente; não altera mínimo, máximo nem a compra.
  ⚠ (erro R2 substitui este helper)
───────────────────────────────────────────────────────────────────────
⚠ Corrija os avisos acima para aplicar.        [Cancelar] [Aplicar e Recalcular]
```

**Marcação de referência (slider máximo; os demais seguem o mesmo padrão):**

```html
<div class="param-row">
  <div class="param-label">
    <label for="maxCoverageInput">Dias de estoque máximo</label>
    <span class="param-value-tag" [class.is-invalid]="isMinMaxInvalid() || isLeadTimeInvalid()">{{ draftMax }} dias</span>
  </div>
  <input id="maxCoverageInput" type="range" min="10" max="180" step="5"
         [ngModel]="draftMax" (ngModelChange)="..."
         [attr.aria-valuetext]="draftMax + ' dias'"
         [attr.aria-invalid]="isMinMaxInvalid() || isLeadTimeInvalid()"
         [attr.aria-describedby]="(isMinMaxInvalid() ? 'minMaxError' : 'maxCoverageHelp') + (isLeadTimeInvalid() ? ' leadTimeError' : '')" />
  <div class="param-feedback">
    @if (isMinMaxInvalid()) {
      <p id="minMaxError" class="param-error"><svg aria-hidden="true" width="14" height="14" ...alert-circle.../>
        O máximo precisa ser maior que o mínimo. Aumente o máximo ou reduza o mínimo.</p>
    } @else {
      <p id="maxCoverageHelp" class="param-desc">A compra sugerida leva o estoque até esse número de dias de venda.</p>
    }
  </div>
</div>
```

**Ligação ARIA por campo:**

| Campo | `aria-invalid` | `aria-describedby` |
| :--- | :--- | :--- |
| Mínimo | R1 | `minCoverageHelp` + (`minMaxError` se R1) |
| Máximo | R1 ou R2 | (`minMaxError` se R1, senão `maxCoverageHelp`) + (`leadTimeError` se R2) |
| Janela | nunca | `historyWindowHelp` |
| Lead time | R2 | `leadTimeError` se R2, senão `leadTimeHelp` |

- Remover os `aria-label` atuais dos ranges: o `<label for>` visível passa a ser o nome acessível (WCAG 2.5.3).
- Mensagens de erro sem números interpolados: o texto não muda enquanto o slider se move, e os valores já aparecem nas tags.
- Rodapé: `<p id="paramsApplyHint" class="modal-footer-hint" role="status">` fica **sempre no DOM** (para a região viva funcionar). O conteúdo só aparece quando `!canApplyParams()`: ícone + `Corrija os avisos acima para aplicar.` É anunciado uma vez a cada vez que o formulário fica inválido.
- "Aplicar e Recalcular": `[disabled]="!canApplyParams()"` e `[attr.aria-describedby]="canApplyParams() ? null : 'paramsApplyHint'"`.

**Estilos novos (SCSS da página):**

| Seletor | Regra |
| :--- | :--- |
| `fieldset.param-group` | `border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-4)` |
| `.param-group + .param-group` | `border-top: 1px solid var(--border-subtle); padding-top: var(--space-4)` |
| `.param-group legend` | `font-family: var(--font-family-headline); font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--text-secondary); margin-bottom: var(--space-3)` (mesma tipografia de `.kpi-label`) |
| `.param-row .param-label` | acrescentar `flex-wrap: wrap; gap: var(--space-2)` |
| `.param-row input[type="range"]` | `width: 100%; min-height: var(--space-6)` (alvo de 24 px, WCAG 2.5.8) |
| `.param-row input[type="range"][aria-invalid="true"]` | `accent-color: var(--feedback-critical-bg)` |
| `.param-value-tag.is-invalid` | `background: var(--feedback-critical-bg); color: var(--text-on-brand)` |
| `.param-feedback` | `min-height: calc(2 * 1.35em)`: reserva 2 linhas para o erro não empurrar o layout |
| `.param-error` | `display: flex; align-items: flex-start; gap: var(--space-1); font-family: var(--font-family-body); font-size: 0.78rem; font-weight: 600; line-height: 1.35; color: var(--feedback-critical-bg)`; svg `flex-shrink: 0; margin-top: 1px` |
| `.modal-footer` | `align-items: center; gap: var(--space-3)`; filhos: `.modal-footer-hint` (flex 1) e `.modal-footer-actions` (`display: flex; gap: var(--space-2)`) |
| `.modal-footer-hint` | mesmo padrão de `.param-error` com `color: var(--feedback-critical-bg)`. Nunca `--text-muted` sobre `--bg-subtle` (4,2:1). |
| `.btn-primary:active:not(:disabled)` | `background: var(--brand-primary-active); border-color: var(--brand-primary-active)` |
| `.btn-secondary:active:not(:disabled)` | `background: var(--bg-muted)` |

Ícone de erro: o mesmo "alert-circle" do `.alert-danger` (circle + 2 lines), 14×14, `stroke="currentColor"`, `aria-hidden="true"`, com `width`/`height` no HTML.

---

## 6. Loading, empty e error

### 6.1 Loading (skeleton com a geometria real; pulse sólido global `.skeleton-line`, sem gradiente)

| Área | Quando | Especificação |
| :--- | :--- | :--- |
| Proof bar | `isLoading()` | 5 `.kpi-card` com `aria-hidden="true"`; dentro, 3 `.skeleton-line` em `display:block`: rótulo 55% × 0.74rem, valor 40% × 1.65rem, sub 80% × 0.74rem. `.proof-bar` recebe `aria-busy="true"`. |
| Tabela | `isLoading()` | `tbody` com 10 linhas skeleton (`aria-hidden="true"`, `tbody aria-busy="true"`). Descrição em 2 linhas (nome 70%, EAN 45%) para igualar a altura da linha real. Células numéricas: 1 linha de 60%, centralizada, altura 0.82rem. Curva, Laboratório e Status: bloco de altura `var(--space-5)` (altura de badge) com 28 px / 80% / 100 px. |
| Contador | `isLoading()` | `.table-header-info` recebe `role="status"` e mostra `Calculando a previsão…`; ao terminar, volta a `Exibindo X de Y produtos` (isso também anuncia o resultado dos filtros). |
| Botões do hero | sem mudança | O spinner dentro do botão com rótulo "Calculando..." continua permitido (não é spinner isolado). |
| Movimento | `prefers-reduced-motion: reduce` | `.skeleton-line { animation: none; }` no SCSS da página. |

Durante qualquer recálculo, KPIs e tabela viram skeleton: com parâmetros novos, mostrar mín./máx. antigos esmaecidos induziria a erro.

### 6.2 Empty (todos com ícone SVG 36×36 `aria-hidden`, texto e ação `.btn .btn-secondary`)

| Variante | Condição | Texto | Ação |
| :--- | :--- | :--- | :--- |
| Filtros sem resultado | `products().length > 0` e lista filtrada vazia | `Nenhum produto com esses filtros.` | `Limpar filtros` (zera busca, status, curva e fornecedor) |
| Cálculo sem produtos | `products().length === 0`, `!isLoading()`, sem erro | `Nenhum produto com venda ou estoque para calcular.` | `Ajustar parâmetros` (abre o modal) |
| Falha no primeiro cálculo | `products().length === 0` e `errorMessage()` | `Não foi possível carregar a previsão.` | `Tentar de novo` (`calculateInventory()`) |

KPI com contagem 0 não é estado vazio: mostra `0 SKUs` normalmente.

### 6.3 Error

- Alerta `.alert-danger` com `role="alert"`; os botões "×" de todos os alertas recebem `aria-label="Fechar aviso"`.
- Nunca renderizar `err.error.detail` cru: no FastAPI, o 422 traz `detail` como lista. Mensagens:
  - **422 (parâmetros):** `O servidor recusou os parâmetros: o máximo precisa ser maior que o mínimo e o lead time menor que o máximo. Revise em Parâmetros.`
  - **Demais erros:** `Não foi possível calcular a previsão agora. Tente de novo em instantes.` Se já houver resultado na tela, acrescentar: ` A tabela mostra o cálculo de {lastCalculatedAt}.`
- Depois de um erro de recálculo, a tabela e os KPIs voltam ao resultado anterior, e o hero continua mostrando `appliedParams` (ainda os antigos). A tela inteira fica coerente.

---

## 7. Matriz de estados dos elementos alterados

| Elemento | Default | Hover | Focus-visible | Active | Disabled | Loading | Empty | Error |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Sliders (mín., máx., janela, lead) | `accent-color: --brand-primary`; tag `--feedback-neutral-bg` | nativo (cursor pointer) | outline global 2 px `--border-focus`, offset 2 px | arraste nativo; tag e erro mudam ao vivo | n/a (nunca desabilitados) | n/a (o modal fecha ao aplicar) | n/a (sempre têm valor) | `accent-color` crítico + tag `.is-invalid` + `.param-error` (ícone + texto) + `aria-invalid` + `aria-describedby` |
| Aplicar e Recalcular | `.btn-primary` | `--brand-primary-hover` (já existe) | outline global | `--brand-primary-active` (novo) | opacity 0.5 + `not-allowed` + `#paramsApplyHint` visível e ligado por `aria-describedby` | n/a (fecha o modal; o loading vai para a página) | n/a | n/a (o erro fica nos campos) |
| Cancelar / × | `.btn-secondary` / glifo `--text-muted` | `--bg-subtle` / `--text-primary` | outline global | `--bg-muted` (novo) | n/a | n/a | n/a | n/a |
| Pílulas de status | já existente | `--bg-subtle` | outline global | `.active` + `aria-pressed="true"` | n/a | n/a | lista vazia → empty "Filtros sem resultado" | n/a |
| Cards KPI | rótulo e sub novos | borda `--border-strong` (já existe) | n/a (não interativo) | n/a | n/a | skeleton 3 linhas | `0 SKUs` | o resultado anterior continua; alerta acima da tabela |
| Células Est. Mín./Máx. | mono, tabular; mín. muted, máx. 600 | hover da linha (já existe) | n/a | n/a | n/a | skeleton 60% | VMD 0 → `0` | n/a (erro é global) |
| Tag "Política" e subtítulo do hero | `tag-neutral`, valores aplicados | n/a | n/a | n/a | n/a | mantém os valores aplicados | n/a | mantém os valores aplicados |

Hovers novos ficam dentro de `@media (hover: hover)`. Nenhuma transição em `width`, `height` ou `padding`. O focus ring aparece na hora (sem fade).

---

## 8. Responsividade (testar em 320 / 375 / 414 / 768 px, sem scroll horizontal da página)

| Faixa | Comportamento |
| :--- | :--- |
| **Mobile < 640 px** | Modal: `.modal-backdrop` com padding `var(--space-3)`; `.modal-footer` em coluna (hint em cima, ações embaixo); `.modal-footer-actions` em coluna com `.btn { width: 100% }` e ordem do DOM Cancelar → Aplicar mantida. `.param-label` quebra linha (rótulo em cima, tag embaixo) sem estourar. KPIs em 1 coluna (grid `auto-fit minmax(210px, 1fr)` já existente). A tag "Política" quebra para baixo do título (`.title-with-badge` já tem `flex-wrap`). Pílulas quebram entre si, nunca dentro do rótulo. Tabela rola dentro de `.table-wrapper`. |
| **Tablet 640–1024 px** | KPIs em 2 a 4 colunas pelo `auto-fit`. Modal com 580 px centralizado; rodapé em linha (hint à esquerda, ações à direita). |
| **Desktop > 1024 px** | Sem mudança estrutural. |

Breakpoint no SCSS: `@media (max-width: 639.98px)`.

---

## 9. Copy deck (antes → depois)

| Local | Antes | Depois |
| :--- | :--- | :--- |
| Hero, título | Estoque Ideal & Previsão de Compras | Previsão de Estoque e Compras |
| Hero, tag | Reposição Inteligente | Política {min}–{max} dias |
| Hero, subtítulo | Inteligência Operacional B2B • Prevenção de Rupturas… | Compra quando o estoque chega ao mínimo e repõe até o máximo. Base: venda média dos últimos {janela} dias · lead time de {lead} dias. |
| `title` do botão Parâmetros | Ajustar hiperparâmetros de reposição | Ajustar dias mínimo e máximo, janela de vendas e lead time |
| `title` do botão Recalcular | Disparar novo cálculo analítico de reposição | Recalcular com os parâmetros aplicados |
| KPIs / pílulas / colunas | ver §5.2, §5.3 e §5.4 | — |
| Modal, título | Parâmetros de Simulação de Estoque | Parâmetros da política de estoque |
| Modal, descrição | Ajuste os parâmetros matemáticos do motor preditivo | Valem para todos os produtos do próximo cálculo. |
| Rótulos dos sliders | Janela de Vendas Recentes (Dias) · Lead Time de Ressuprimento (Dias) | Janela de vendas recentes · Lead time de ressuprimento (a unidade fica na tag) |
| Novos rótulos | — | Dias de estoque mínimo · Dias de estoque máximo |
| Helpers e erros | — | ver §5.5 (texto literal) |

---

## 10. Remoções obrigatórias (sem código morto)

Linhas de referência no commit `7004f96`.

**HTML (`inventory-page.component.html`)**
- [ ] L7–8: título e `<span class="tag tag-info"><span class="tag-dot"></span>Reposição Inteligente</span>` → substituir (§5.1).
- [ ] L11: subtítulo "Inteligência Operacional B2B…" → substituir.
- [ ] L94, L97, L106, L112: rótulos e subtítulos antigos dos KPIs → substituir (§5.2).
- [ ] L127–133: texto "Total de compra orçado…" e o bloco `@if (kpi.skusLimitadosPorEspaco)` com `.proof-capped-chip`.
- [ ] L199 "Reposição" e L215 "Excesso" → novos rótulos.
- [ ] L302–303: `<th>` ROP e Est. Ideal; L342–345: `<td>` com `prod.rop`, `prod.estoqueIdeal`, `limitadoPorEspaco` e `estoqueIdealTeorico`.
- [ ] L349: `[title]` de `td.col-compra` (com `qtdSugeridaTeorica` e `tetoCompraFisica`).
- [ ] L408–409: título e descrição do modal.
- [ ] L429, L448: `aria-label` dos ranges mantidos.
- [ ] L453–551: blocos inteiros de Autonomia Alvo (`#targetCoverageInput`), Nível de Serviço (`#serviceLevelSelect` e options), Teto Orçamentário (`#budgetLimitInput`) e Margem de Variação (`#maxPurchaseVariationInput`, `#enablePhysicalLimitToggle`, `.param-label-group`, `.toggle-switch-wrapper`, `.switch`, `.slider-round`, `.switch-text`, binding `tag-disabled`).
- [ ] L554–557: rodapé reestruturado (§5.5).

**SCSS (`inventory-page.component.scss`)**
- [ ] L460–461, L601–602, L613–614: `.col-rop` e `.col-ideal` → `.col-min` e `.col-max`.
- [ ] L827–830: `.param-value-tag.tag-disabled`.
- [ ] L845–858: `.form-select, .form-input` (só eram usados por nível de serviço e teto orçamentário).
- [ ] L869–961: comentário "Governança de Espaço Físico & Trava de Variação", `.capped-badge` (já sem uso), `.proof-capped-chip`, `.param-label-group`, `.toggle-switch-wrapper`, `.switch` e `.slider-round`.
- [ ] **Manter** `.sr-only` (L963–973): é reutilizado na tag do hero e nos cabeçalhos Est. Mín./Máx.

**TS (`inventory-page.component.ts`)**
- [ ] L26–30: signals `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct` e `enablePhysicalLimit`.
- [ ] L150–154 e L184–188: esses campos no `InventoryParams` montado em `calculateInventory` e `downloadCsv` (os dois passam a usar `appliedParams`/rascunho, §4).
- [ ] L245–246 e L263–268: gravação e restauração de `maxPurchaseVariationPct` e `enablePhysicalLimit` no cache (trocar por `appliedParams`; nova chave de cache, CA-12).
- [ ] L9: import `InventoryStatus`, se continuar sem uso.

**Model (`inventory.model.ts`)**: remover `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct`, `skusLimitadosPorEspaco`, `estoqueSeguranca`, `rop`, `estoqueIdeal`, `estoqueIdealTeorico`, `qtdSugeridaTeorica`, `limitadoPorEspaco` e `tetoCompraFisica`. Os blocos correspondentes de `InventoryConfigResponse` seguem o contrato do Arquiteto, que também decide se `desvioPadraoDemanda` fica. Se `/config` passar a expor as faixas de `minCoverageDays` e `maxCoverageDays`, consumi-las; senão, manter os literais de §5.5.

---

## 11. Critérios de aceite visuais (para o UX Reviewer, Etapa 4)

- [ ] O modal mostra só Janela, Lead time, Dias mínimo e Dias máximo, em dois `fieldset` (CA-08 / CA-P056-03).
- [ ] Com mínimo 60 e máximo 60: o botão fica desabilitado, aparece o erro com ícone sob "Dias de estoque máximo", as tags dos dois ficam vermelhas, os dois inputs têm `aria-invalid="true"` e os valores digitados se mantêm (CA-P053-05).
- [ ] Com máximo 15 e lead time 15: o erro aparece sob Lead time, com o mesmo bloqueio.
- [ ] Cancelar ou Esc depois de mudar valores: o hero, os KPIs e o próximo "Recalcular" usam os parâmetros anteriores.
- [ ] Hero e KPIs mostram `{min}`/`{max}` do último cálculo bem-sucedido, inclusive depois de recarregar a página.
- [ ] Nenhum texto "ROP", "Ideal", "Excesso", "Reposição Necessária", "trava física" ou "orçado" na tela.
- [ ] Skeleton em KPIs e tabela durante o cálculo; nenhum empty state aparece enquanto carrega.
- [ ] Sem scroll horizontal da página em 320, 375, 414 e 768 px; o rodapé do modal empilha abaixo de 640 px.
- [ ] Tab não sai do modal aberto; o foco volta ao botão "Parâmetros" ao fechar.
