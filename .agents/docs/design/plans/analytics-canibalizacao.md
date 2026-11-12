# Design Plan: Analytics Comercial — Canibalização e Substituição (Fase F6) 📐🎨

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-canibalizacao.md`  
> **Autor:** Designer (`designer.md` / `uiux-expert`)  
> **Auditor:** UX Reviewer (`ux_reviewer.md`)  
> **Executor:** Desenvolvedor (`developer.md`)  
> **Referências:** `.agents/docs/design/DESIGN_SYSTEM.md`, `.agents/rules/frontend-ui-anti-patterns.md`, `business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`)

---

## 1. Identificação & Objetivo da Tarefa

- **User Story Relacionada:** US-F6 — *Como gestor comercial ou comprador da Fitoherb, quero visualizar graficamente o impacto real de ações comerciais (promoções, descontos ou lançamentos) na venda de outros produtos do catálogo, entendendo se o resultado final compensou financeiramente ou se houve canibalização predatória de margem.*
- **Objetivo de UX:**
  1. Apresentar de forma visual e intuitiva uma análise estatística complexa (Diferença em Diferenças), tornando o impacto causal imediatamente compreensível sem exigir conhecimento de econometria.
  2. Destacar com máxima clareza o **Efeito Líquido** da ação em três dimensões: volume (unidades), faturamento (R$) e margem de contribuição (R$), sintetizado por um veredito comercial inconfundível.
  3. Permitir a exploração temporal do evento através de uma linha do tempo interativa que contextualiza a janela pré ($W$) e a janela pós ($W$) contra a linha de base da categoria.
- **Decisões de Design:**
  - Evitar sobrecarga de números na visualização primária: cards de resumo com tipografia de alta legibilidade (`JetBrains Mono` para moedas e percentuais) e tabela detalhada expansível com selos de significância.
  - Alinhamento rigoroso com a paleta institucional *Soft SaaS Premium* (Teal 600, Slate Neutros, Emerald/Amber/Red para feedback).

---

## 2. Checklist Anti-IA (Filtro Anti-Slop Obrigatório)

- [x] **Sem "AI Purple":** Zero gradientes genéricos azul-roxo. Utilização estrita do Teal institucional (`#0D9488`), Slate profundo e tons terrosos suaves.
- [x] **Sem 3 Colunas Mecânicas:** Layout assimétrico inteligente: cabeçalho com contexto de evento, linha do tempo temporal em largura total, card executivo de destaque à esquerda e tabela de produtos afetados à direita/abaixo.
- [x] **Tipografia com Font Pairing:** Títulos e cabeçalhos em `'Plus Jakarta Sans'`, corpo de texto e legendas em `'Inter'`, e valores numéricos em `'JetBrains Mono'`.
- [x] **White Space Ativo:** Espaçamentos generosos (`--space-6` e `--space-8`), evitando adensamento cognitivo em telas de densidade analítica.
- [x] **Copywriting Humano e Direto:** Termos comerciais claros (*"Ganho Líquido de Margem"*, *"Ilusão de Volume"*, *"Canibalização Direta"*) em vez de jargões técnicos herméticos como *"Tratamento Quase-Experimental"*.
- [x] **Zero Spinners Solitários:** Especificação completa de **Skeleton Loaders Shimmer** para todas as seções durante o carregamento.
- [x] **Zero Telas Brancas Vazias:** Empty States dedicados e desenhados para cada cenário de exceção (produto sem evento, sem busca, sem substitutos).

---

## 3. Tokens do Design System Aplicados nesta Tela

| Categoria | Token | Valor HEX | Aplicação nesta Interface |
| :--- | :--- | :--- | :--- |
| **Superfície Base** | `--color-neutral-50` | `#F8FAFC` | Fundo principal da página `/analytics/canibalizacao` |
| **Superfície Card** | `#FFFFFF` | `#FFFFFF` | Cartões executivos e containers da tabela |
| **Superfície Header/Tabela** | `--color-neutral-100` | `#F1F5F9` | Fundo do cabeçalho da tabela de afetados e filtros |
| **Bordas Sutis** | `--color-neutral-200` | `#E2E8F0` | Divisórias de linhas, bordas de cards e inputs |
| **Texto Título** | `--color-neutral-900` | `#0F172A` | Títulos de seção, SKU e valores financeiros principais |
| **Texto Secundário** | `--color-neutral-600` | `#475569` | Descrições, categorias e rótulos de métricas |
| **Ação Primária** | `--color-primary` | `#0D9488` | Botões de busca, seleção de evento ativa e abas |
| **Hover Primário** | `--color-primary-hover` | `#0F766E` | Estado hover de botões e links interativos |
| **Canibalização (Perda)** | `--color-danger` / `--color-danger-bg` | `#EF4444` / `#FEF2F2` | Badge e indicador de $\Delta$ negativo em canibalização |
| **Complemento (Ganho)** | `--color-success` / `--color-success-bg` | `#10B981` / `#ECFDF5` | Badge de itens complementares e margem líquida positiva |
| **Alerta / Ilusão de Volume** | `--color-warning` / `--color-warning-bg` | `#F59E0B` / `#FFFBEB` | Veredito de ação que gerou volume mas perdeu margem |
| **Tipografia Display** | `'Plus Jakarta Sans'` | 600 / 700 / 800 | H2 e títulos de blocos métricos |
| **Tipografia Numérica** | `'JetBrains Mono'` | 500 / 600 | Tabelas de $\Delta$, unidades, valores em R$ |
| **Sombras** | Nível 1 (`--shadow-sm`) | `0 1px 3px rgba(15,23,42,0.06)` | Elevação base de cards e containers |

---

## 4. Anatomia dos Componentes e Hierarquia de Layout

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ HEADER DA FEATURE                                                                │
│ [ Busca de SKU: Input + Autocomplete ] [ Evento: Promoção ▼ ] [ Janela: 4 sem ▼ ]│
└──────────────────────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LINHA DO TEMPO DO EVENTO (Interactive Timeline Component)                        │
│ [ Janela Pré: 4 semanas ]  ◄─── [ T0: Início Promoção 01/09 ] ───►  [ Janela Pós ]│
│ Baseline Categoria (Grupo de Controle): +5.0% no período                         │
└──────────────────────────────────────────────────────────────────────────────────┘
┌───────────────────────────────────────┬──────────────────────────────────────────┐
│ CARD EXECUTIVO DE EFEITO LÍQUIDO      │ RESUMO DO PRODUTO ALVO                   │
│ Veredito: [ ILUSÃO DE VOLUME ]        │ SKU 100234 - EXTRATO DE PRÓPOLIS VERDE   │
│ Δ Volume Líquido:  +365,75 un. (▲)    │ Volume Pré: 420 un. -> Pós: 980 un.      │
│ Δ Receita Líquida: +R$ 3.235,63 (▲)   │ Preço Médio: R$ 24,50 -> R$ 18,90 (-23%) │
│ Δ Margem Líquida:  -R$ 1.381,05 (▼)   │ Δ Margem Alvo: +R$ 784,00                │
│ "A ação gerou giro, mas destruiu R$ 1,3 mil de margem ao canibalizar Aquoso."   │
└───────────────────────────────────────┴──────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────────────────────┐
│ TABELA DE PRODUTOS AFETADOS (Diferença em Diferenças)                            │
│ [ Filtros: Todos | Só Canibalizados | Só Complementares ] [ [x] Incluir Ruído ]  │
│ ┌────────┬───────────────────────────┬─────────┬──────────┬──────────┬─────────┐ │
│ │ Status │ Produto                   │ Jaccard │ Esperado │ Real Pós │ Δ Margem│ │
│ ├────────┼───────────────────────────┼─────────┼──────────┼──────────┼─────────┤ │
│ │ CANIB. │ EXTRATO PRÓPOLIS AQUOSO   │  42%    │ 325 un.  │ 165 un.  │-R$ 1.524│ │
│ │ CANIB. │ EXTRATO DE EQUINÁCEA      │  28%    │ 189 un.  │ 110 un.  │ -R$ 948 │ │
│ │ COMPL. │ SPRAY BUCAL PRÓPOLIS      │  31%    │ 100 un.  │ 145 un.  │ +R$ 307 │ │
│ └────────┴───────────────────────────┴─────────┴──────────┴──────────┴─────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 4.1. Barra de Controle e Busca Superior
- Input de SKU com busca rápida por código ou descrição (autocomplete integrado).
- Seletor de Tipo de Evento (`Promoção`, `Alteração de Preço`, `Lançamento`).
- Seletor de Janela Simétrica ($W$): chips rápidos `[2 sem]`, `[4 sem (Recomendado)]`, `[8 sem]`, `[12 sem]`.
- Botão Primário com ícone de lupa: `[ Analisar Impacto ]`.

### 4.2. Linha do Tempo do Evento (Timeline Component)
- Gráfico compacto horizontal mostrando as duas janelas simétricas separadas pelo marco temporal $T_0$.
- Linha pontilhada cinza claro representando a evolução contrafactual projetada pelo grupo de controle da categoria (+5%).
- Linha sólida colorida do SKU alvo (verde esmeralda) e dos substitutos canibalizados (vermelho coral).

### 4.3. Card Executivo de Efeito Líquido (Net Impact Summary)
- Badge em destaque no topo:
  - `VALEU_A_PENA`: Fundo `--color-success-bg`, texto `--color-success`, ícone de check.
  - `ILUSAO_DE_VOLUME`: Fundo `--color-warning-bg`, texto `--color-warning`, ícone de alerta triangular.
  - `PREJUIZO_TOTAL`: Fundo `--color-danger-bg`, texto `--color-danger`, ícone de X.
- Grid de 3 métricas em `JetBrains Mono`:
  - **Volume Líquido:** Unidades adicionais líquidas da família.
  - **Receita Líquida:** Faturamento incremental gerado.
  - **Margem Líquida:** Rentabilidade real em R$ (com cores semânticas verde/vermelho).
- Texto de síntese executiva em linguagem natural contextualizando as conclusões.

### 4.4. Tabela de Produtos Afetados (Diferença em Diferenças)
- Colunas:
  1. `Classificação`: Badges semânticos (`Canibalização`, `Complemento`, `Sem Efeito`).
  2. `Produto`: SKU, descrição e tag de categoria.
  3. `Similaridade`: % de Jaccard e tooltip com número de compradores em comum.
  4. `Venda Pré`: Média semanal e volume total na janela pré.
  5. `Esperado Pós (Contrafactual)`: Volume projetado caso a ação não ocorresse.
  6. `Observado Pós`: Volume real vendido.
  7. `Impacto Causal (Δ DiD)`: Diferença em unidades e percentual causal.
  8. `Δ Margem (R$)`: Impacto monetário na margem de contribuição.
  9. `Significância`: Indicador visual de certeza estatística (q-valor $\le 0.05$ com selo de 95% de confiança).

---

## 5. Matriz Completa dos 8 Estados Visuais Obrigatórios

### 5.1. Estado 1: Default (Ocioso com Dados Carregados)
- Todos os cards e tabelas preenchidos com os dados da análise.
- Transições de entrada suaves (`opacity` 0 a 1 em 200ms).
- Tooltips funcionais sobre os termos estatísticos (ex: *"Diferença em Diferenças neutralizou +5% de crescimento geral da categoria"*).

### 5.2. Estado 2: Interativo (Hover, Focus-Visible e Active)
- **Linhas da Tabela:** No hover, fundo escurece para `--color-neutral-100` com transição de 150ms e cursor `pointer`.
- **Botões e Chips:** Elevação sutil `transform: translateY(-1px)` e sombra nível 2 no hover; anel de foco `outline: 2px solid var(--color-primary); outline-offset: 2px;` na navegação por teclado.
- **Linha do Tempo:** Hover em pontos temporais exibe tooltip flutuante com data, volume alvo e volume do controle.

### 5.3. Estado 3: Carregamento (Loading com Skeleton Shimmer)
- **Proibido expressamente:** Spinner giratório isolado no centro da tela.
- **Estrutura Shimmer Espelhada:**
  - Barra superior: 3 retângulos de `140px x 40px` com gradiente animado cinza neutro (`#E2E8F0` para `#F1F5F9`).
  - Linha do tempo: Bloco horizontal de `100% x 120px` com efeito shimmer contínuo.
  - Card executivo: 2 cartões de `50% x 160px` com blocos de texto skeleton.
  - Tabela: Cabeçalho estático e 4 linhas com 6 barras horizontais simulando dados.

### 5.4. Estado 4: Empty State Inicial (Nenhum Produto Selecionado)
- Apresentado ao acessar `/analytics/canibalizacao` antes da primeira consulta.
- **Ilustração/Ícone:** Ícone temático de balança comercial ou diagrama de conjuntos suave sobre fundo `--color-primary-subtle`.
- **Título (H3):** *"Descubra o impacto real das suas ações comerciais"*.
- **Texto explicativo:** *"Informe um código de produto acima para analisar se promoções ou lançamentos geraram ganho genuíno de margem ou canibalizaram itens concorrentes."*
- **Sugestão de Ação Rápida:** Chips clicáveis com 3 produtos sugeridos com eventos recentes conhecidos (ex: `[Extrato de Própolis Verde]`, `[Chá Digestivo 50g]`).

### 5.5. Estado 5: Erro de API / Falha de Conexão (`CAN-005` ou Rede)
- Banner contextual fixado no topo da área de conteúdo com fundo `--color-danger-bg`, borda fina `--color-danger` e ícone de exclamação.
- **Título:** *"Não foi possível processar a análise no momento"*.
- **Mensagem:** *"Houve uma instabilidade na consulta ao banco de dados. Os dados transacionais não foram comprometidos."*
- **Botão:** Botão secundário outline `[ Tentar Novamente ]` com foco automático.

### 5.6. Estado 6: Sem Eventos Elegíveis Encontrados (`CAN-002`)
- Quando o SKU existe no catálogo, mas não possui campanhas promocionais ou variações de preço $\ge 5\%$ no histórico.
- **Container Amigável:** Card centralizado com fundo `--color-neutral-100` e borda pontilhada `--color-neutral-300`.
- **Título:** *"Nenhum evento detectado para este produto"*.
- **Texto:** *"O SKU 100234 não teve campanhas de promoção registradas nos últimos 12 meses. Você pode alternar o seletor para 'Alteração de Preço' ou informar uma data específica manualmente."*
- **Ação:** Botão de atalho `[ Analisar Variações de Preço ]`.

### 5.7. Estado 7: Controle Categorial Insuficiente (`CAN-003` / Fallback)
- Quando a categoria do produto (`Tipo`) possui menos de 5 SKUs sem intervenção para compor o grupo de controle.
- Se o fallback para Fornecedor foi acionado com sucesso: Badge informativo amarelo discreto no cabeçalho do controle:
  - *"Controle Expandido: Utilizando 8 produtos estáveis do mesmo fornecedor devido ao tamanho reduzido da categoria."*
- Se a análise for inviável: Card de aviso explicando a limitação amostral de dados sem jargão estatístico punitivo.

### 5.8. Estado 8: Parâmetro Inválido / Janela Incoerente (`CAN-004`)
- Erro de validação de formulário (ex: data futura informada ou janela menor que 2 semanas).
- Borda vermelha inline no seletor correspondente com mensagem de suporte abaixo do campo:
  - *"A janela de análise deve conter entre 2 e 12 semanas para garantir estabilidade estatística."*

---

## 6. Responsividade e Breakpoints

| Breakpoint | Comportamento do Layout |
| :--- | :--- |
| **Mobile (< 640px)** | Barra de controle empilhada verticalmente; linha do tempo simplificada com rolagem horizontal; card de efeito líquido em coluna única vertical; tabela de afetados convertida em lista de cards resumidos com gaveta expansível para ver detalhes de $\Delta$ margem. |
| **Tablet (640px - 1024px)** | Barra de controle em 2 linhas; linha do tempo completa responsiva; cards executivos lado a lado (2 colunas); tabela com scroll horizontal suave preservando a primeira coluna fixa (Produto). |
| **Desktop (> 1024px)** | Layout balanceado em container máximo de 1280px com respiro lateral amplo (`--space-8`); linha do tempo expansiva; card executivo e dados do alvo alinhados em proporção 60/40; tabela com todas as colunas visíveis sem necessidade de rolagem. |

---

## 7. Critérios de Aceite para UX Reviewer (DoD Visual)

- [ ] Todos os elementos utilizam estritamente as variáveis de `:root` do `DESIGN_SYSTEM.md`.
- [ ] O visual não contém gradientes roxos genéricos de IA ou sombras pretas pesadas.
- [ ] A linha do tempo do evento e a projeção do grupo de controle são exibidas com clareza.
- [ ] O card executivo de efeito líquido exibe com destaque o Veredito Comercial (`VALEU_A_PENA`, `ILUSAO_DE_VOLUME`, `PREJUIZO_TOTAL`).
- [ ] A tabela de afetados apresenta a classificação correta, $\Delta$ unidades, $\Delta$ margem e indicação de significância estatística.
- [ ] Todos os 8 estados visuais obrigatórios possuem especificação explícita e comportamentos detalhados.
- [ ] Zero spinners de tela cheia: carregamento estruturado com Skeleton Loaders Shimmer.
- [ ] Layout perfeitamente responsivo nas faixas mobile, tablet e desktop.
