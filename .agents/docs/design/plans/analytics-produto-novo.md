# Design Plan — Analytics Comercial · FASE F2: Viabilidade de Produto Novo

<!-- Hallmark · pre-emit critique: P4 H5 E4 S5 R5 V4 · macrostructure: workbench analítico (parâmetros à esquerda/topo → projeção e ledger de similares à direita) -->

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-produto-novo.md`  
> **Status:** Versão 1.0.0 (Etapa 2 - Checkpoint de Design e UX)  
> **Responsável:** Designer de UI/UX (`designer.md` / `uiux-expert`)  
> **Feature:** US-NEW — Simulação de Viabilidade de Produto Não Cadastrado  
> **Branch:** `feature/analytics-produto-novo`  
> **Regras Associadas:** `P-139` a `P-149` (em `.agents/docs/business_rules/analytics-produto-novo.md`)  
> **Contrato REST:** `.agents/docs/api_contracts/analytics-produto-novo.md`  
> **Sistema de Cores e Tipografia:** Papel & Tinta (`frontend/src/styles.scss`)

---

## 1. Identificação e Objetivos de UX

### 1.1 Story do Usuário
*Como comprador ou gestor comercial da Fitoherb, quero simular a introdução de um produto ainda não cadastrado no ERP informando suas características comerciais, obtendo uma estimativa de vendas conservadora, uma comparação transparente com lançamentos reais semelhantes e um parecer de margem, para aprovar ou rejeitar a compra com segurança de caixa.*

### 1.2 Perguntas que a Tela Responde em uma Consulta
1. "Quanto se espera vender deste produto nos primeiros 3 meses sem correr risco de encalhe?"
2. "A margem bruta estimada atinge a rentabilidade mínima que a distribuidora exige?"
3. "Em quais lançamentos reais passados esta estimativa está ancorada e por quê?"
4. "Qual é o teto máximo de mercado que produtos maduros desse mesmo tipo conseguem atingir?"

### 1.3 Objetivos de Experiência
1. **Entrada Descomplicada sem SKU:** Formulário claro que aceita atributos conceituais com preenchimento assistido nos selects de tipo e fornecedor.
2. **Pedagogia do Conservadorismo:** Explicar visualmente e sem jargões por que o número é prudente ("estimativa calculada para proteger seu estoque"), evitando frustrações com metas comerciais infladas.
3. **Explicabilidade Radical:** Todo similar utilizado possui pontuação transparente (preço, fornecedor e descrição) para que o comprador compreenda o critério do cálculo.
4. **Respeito ao Sistema Papel & Tinta:** Fidelidade aos tokens de `styles.scss`, sem introduzir gradientes sintéticos ou estilos estranhos à aplicação.

---

## 2. Checklist Hallmark Anti-IA (Auditado)

- [x] **Sem "AI Purple" ou gradientes futuristas:** Uso exclusivo da paleta Papel & Tinta (tons de verde erva-mate, off-white, cinzas quentes e acentos sóbrios de feedback).
- [x] **Sem cards genéricos flutuantes:** Layout estruturado no arquétipo Workbench / Ledger (painel de parâmetros operacionais + painel de projeção quantitativa tabular e gráfica).
- [x] **Tipografia Identitária:** Títulos em `--font-family-headline` (*Signika*), textos em `--font-family-body` (*Source Sans 3*), tabelas e números financeiros em `--font-family-mono` (*Overpass Mono*).
- [x] **Copy Humano e Objetivo:** Proibição terminante de termos como "inteligência preditiva avançada", "algoritmo revolucionário", "potencialize seu catálogo" ou ícones de estrelas/varinha mágica (✨). Rótulos simples: "Previsão Conservadora", "Margem Bruta Estimada", "Lançamentos Similares".
- [x] **Feedback Rico e Estados Completos:** Skeleton loaders correspondentes à exata silhueta dos dados e tratamento minucioso de avisos de base insuficiente (`NEW-001`).
- [x] **Acessibilidade Inclusiva (WCAG AA):** Relação de contraste de texto $\ge 4.5:1$ em todos os elementos e mensagens de status que combinam texto explícito e ícone (nunca apenas cor).

---

## 3. Tokens de Design Consumidos (`frontend/src/styles.scss`)

| Categoria | Tokens Utilizados | Aplicação na Tela |
| :--- | :--- | :--- |
| **Tipografia** | `--font-family-headline`<br>`--font-family-body`<br>`--font-family-mono` | Títulos e subtítulos de seções.<br>Instruções, rótulos de campos e descrições.<br>Valores em R$, unidades de venda, percentuais e datas. |
| **Superfície** | `--bg-canvas`<br>`--bg-surface`<br>`--bg-subtle`<br>`--bg-muted` | Fundo principal da página.<br>Painéis de formulário e cartões de resultados.<br>Campos de input, cabeçalhos de tabela e selos informativos.<br>Linhas de skeleton durante o carregamento. |
| **Bordas** | `--border-subtle`<br>`--border-default`<br>`--border-strong`<br>`--border-focus` | Divisórias de tabelas e drawers.<br>Contornos de inputs e painéis.<br>Linhas de separação de seções.<br>Contorno de foco acessível em campos ativos. |
| **Acentos / Marca** | `--brand-primary`<br>`--brand-primary-hover`<br>`--brand-primary-subtle` | Botão principal "Simular Viabilidade".<br>Estado hover do botão de ação.<br>Destaque de fundo da linha de previsão conservadora. |
| **Feedback** | `.tag-success` / `--feedback-success-bg`<br>`.tag-warning` / `--feedback-warning-bg`<br>`.tag-critical` / `--feedback-critical-bg`<br>`.tag-neutral` | Selo "Viável" (margem atingida).<br>Selo "Margem Abaixo do Esperado" e Alerta de Base Insuficiente (`NEW-001`).<br>Erros de validação em campos numéricos (`NEW-004`).<br>Selo metodológico "Estimativa Conservadora". |
| **Espaçamento** | `--space-2` a `--space-8` | Ritmo visual padronizado de padding e margins. |

---

## 4. Anatomia e Estrutura da Página

A tela organiza-se em duas colunas funcionais com proporção equilibrada (40% formulário de entrada / 60% área de resultados e diagnóstico):

```
+---------------------------------------------------------------------------------------------------+
| BREADCRUMB: Analytics / Viabilidade de Produto Novo                                               |
| TITULO: Viabilidade de Produto Novo (Simulação Comercial)                                         |
| SELO METODOLÓGICO: [Estimativa Conservadora: calculada sob o P25 com haircut de 30%]            |
+-------------------------------------------------+-------------------------------------------------+
| COLUNA ESQUERDA: PARÂMETROS HIPOTÉTICOS         | COLUNA DIREITA: PROJEÇÃO E VIABILIDADE          |
|                                                 |                                                 |
| [1] Atributos do Produto                        | [A] Cartão de Viabilidade Financeira            |
| - Tipo (Select com busca)                       |   - Margem Bruta: 55,1% [Badge: VIÁVEL]         |
| - Fornecedor (Select com busca)                 |   - Receita Trimestral Prevista: R$ 5.652,50    |
| - Descrição Comercial (Input texto 120 car.)    |   - Lucro Bruto Estimado: R$ 3.112,20           |
|                                                 |                                                 |
| [2] Premissas Comerciais                        | [B] Curva Mensal e Faixas de Dispersão          |
| - Preço de Venda Previsto (R$) *                |   - Gráfico de Linha/Faixa (P10, P50 e Conserv) |
| - Custo Unitário de Aquisição (R$) (opcional)   |   - Tabela Mensal detalhada com volumes e R$    |
| - Margem Mínima Desejada (%) (opcional)         |   - Linha de Teto Maduro de Mercado (P75)       |
| - Horizonte de Projeção (1, 2 ou 3 meses)       |                                                 |
|                                                 | [C] Lançamentos Similares Utilizados (Top-10)   |
| [ Botão: Simular Viabilidade ]                  |   - Tabela resumida com SKU, Nome e Score       |
|                                                 |   - Ação: "Ver detalhes da similaridade"        |
+-------------------------------------------------+-------------------------------------------------+
```

---

## 5. Especificação dos 8 Estados Interativos Obrigatórios

### Estado 1: Inicial / Convidativo (Empty Form)
- **Aparência:** O formulário é renderizado com os seletores de `Tipo` e `Fornecedor` já carregados via options.
- **Painel Direito:** Exibe uma área neutra de orientação:
  - Ícone de documento analítico sóbrio em `--text-muted`.
  - Título: *"Nenhuma simulação realizada"*.
  - Mensagem: *"Preencha os dados do produto à esquerda e clique em 'Simular Viabilidade' para estimar os volumes de venda dos primeiros meses com base em lançamentos reais semelhantes."*

### Estado 2: Preenchido Válido
- **Aparência:** Todos os campos obrigatórios preenchidos corretamente (`tipo`, `fornecedor`, `descricao`, `precoVendaPrevisto > 0`). Se `custoUnitario` for preenchido, respeita $\le \text{precoVendaPrevisto}$.
- **Comportamento:** O botão principal *"Simular Viabilidade"* passa para o estado interativo com cor `--brand-primary` e cursor pointer.

### Estado 3: Preenchido Inválido (Client Validation)
- **Aparência:** Borda do campo infrator em `--feedback-critical-border` com mensagem de erro inline em texto `--feedback-critical-text`:
  - `custoUnitario > precoVendaPrevisto`: *"O custo não pode exceder o preço de venda."*
  - `precoVendaPrevisto <= 0`: *"Informe um preço de venda positivo."*
  - `margemMinimaDesejada > 100%`: *"A margem máxima permitida é 100%."*
- **Comportamento:** Botão de submissão desabilitado com cursor `not-allowed`.

### Estado 4: Carregando / Loading (Skeleton Screen)
- **Aparência:**
  - O botão de ação exibe spinner inline de 16px e texto *"Calculando projeção..."*.
  - A coluna da direita exibe skeletons cinzas pulsantes em `--bg-muted`, desenhando exatamente a geometria do cartão de margem (bloco retangular de 80px), da tabela de 3 linhas e da lista de similares.
  - Zero spinners centrais soltos na tela.

### Estado 5: Sucesso / Resultado Completo
- **Aparência:**
  - **Cartão de Viabilidade:** Se `viavel === true`, fundo sutil `--feedback-success-bg` e tag `.tag-success` *"VIÁVEL"*. Se `viavel === false`, tag `.tag-warning` *"MARGEM ABAIXO DO DESEJADO"*. Se custo omitido, tag `.tag-neutral` *"SEM DADOS DE CUSTO"*.
  - **Tabela de Projeção:** Exibe as colunas *Mês*, *Estimativa Conservadora (un)*, *Receita Prevista (R$)*, *Margem Bruta (R$)*, *Faixa dos Similares (P10 - Mediana)*.
  - **Linha de Teto Maduro:** Exibida no rodapé da tabela com fundo sutil e legenda explicando o $P75$.
  - **Lista de Similares:** Tabela com barra de progresso horizontal em mono indicando o score de similaridade (ex.: `91%` similar).

### Estado 6: Base Insuficiente (`NEW-001`)
- **Aparência:** Banner amarelo em `--feedback-warning-bg` com borda `--feedback-warning-border`:
  - Ícone de atenção sóbrio.
  - Título: *"Base de Lançamentos Insuficiente"*.
  - Mensagem: *"A categoria '{tipo}' possui apenas {count} lançamentos reais registrados desde abril/2025 (mínimo exigido: 3). Por segurança metodológica, o sistema não gera previsões com amostragem insuficiente para evitar compras equivocadas."*
  - Ação sugerida: *"Recomendamos analisar itens semelhantes manualmente na aba Tendência de Vendas."*

### Estado 7: Vazio Funcional (Catálogo sem Opções)
- **Aparência:** Ocorre se a requisição de opções falhar ou retornar listas vazias.
- **Mensagem:** *"Catálogo de opções não disponível. Não foi possível carregar os tipos e fornecedores ativos."*
- **Ação:** Botão *"Recarregar Catálogo"*.

### Estado 8: Erro de Servidor / Timeout (`NEW-005`)
- **Aparência:** Banner vermelho discreto em `--feedback-critical-bg`:
  - Mensagem: *"Falha na comunicação com o servidor de dados. Tente novamente em alguns segundos."*
  - Botão secundário *"Tentar Novamente"*, preservando todos os campos já preenchidos no formulário sem perda de digitação.

---

## 6. Drawer de Detalhes dos Similares (Explicabilidade)

Ao clicar em um similar na lista de resultados, abre-se um painel lateral retrátil (Drawer) à direita da tela:
- **Cabeçalho:** SKU e Descrição Completa do item similar com data da primeira venda.
- **Gráfico dos 3 Primeiros Meses:** Barras comparativas mês a mês ($M_1, M_2, M_3$) com quantidades líquidas (vendas reais com devoluções abatidas).
- **Detalhamento do Score Composto:**
  - *Fornecedor:* 100% (Mesmo fornecedor) ou 0% (Fornecedor distinto).
  - *Preço de Venda:* Razão percentual calculada em escala logarítmica contra o preço previsto.
  - *Descrição (TF-IDF):* Palavras e termos coincidentes destacados (ex.: `"tintura"`, `"melissa"`, `"50ml"`).

---

## 7. Conformidade de Acessibilidade (WCAG 2.1 AA)

1. **Navegação por Teclado:** Ordem lógica de tabulação em todos os campos de entrada, com contorno de foco de 2px sólido (`--border-focus`).
2. **Leitores de Tela (Aria):**
   - Inputs com `aria-required="true"` e referências `aria-describedby` para erros inline.
   - Tabelas com tags semânticas `<caption>`, `<th scope="col">` e formatos monetários com leitura clara em pt-BR.
3. **Contraste de Cores:**
   - Textos primários sobre superfície: razão de contraste $> 12:1$.
   - Textos de badges sobre seus respectivos fundos de alerta: razão $> 5:1$.
