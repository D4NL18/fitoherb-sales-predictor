# Design Plan — Analytics Comercial · F1 Detecção de Sazonalidade por Produto

<!-- Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V5 · macrostructure: workbench de produto + ledger de rankings -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | US-F1 — Detecção de Sazonalidade por Produto (Aba `/analytics/sazonalidade`) |
| **Branch** | `feature/analytics-sazonalidade` |
| **Regras** | `.agents/docs/business_rules/analytics-sazonalidade.md` (P-106 a P-116, `SEA-001` a `SEA-003`) |
| **Plano Mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` §2 e §6 |
| **Contrato** | `.agents/docs/api_contracts/analytics-sazonalidade.md` (1.0.0) |
| **Design System** | Padrão Papel & Tinta (`frontend/src/styles.scss`) |
| **Autor / Etapa** | Designer — Etapa 2 · 2026-11-12 |

---

## 1. Identificação e Objetivos de UX

**Story:** *Como comprador ou gestor comercial, quero consultar a curva de sazonalidade de qualquer produto e visualizar os rankings de sazonalidade da empresa, sabendo exatamente quais meses têm vendas acima da média, o período de pico e vale, e se o histórico é confiável ou insuficiente.*

**Perguntas que a tela responde:**
1. "Qual é o mês ou época do ano que este produto mais vende?" (Período de pico e intensidade).
2. "Quando as vendas caem para seu nível mais baixo?" (Período de vale).
3. "Essa sazonalidade é consistente ou foi um acaso?" (Força da sazonalidade e repetição ano a ano).
4. "Posso confiar no dado de cada mês?" (Selo de confiança `ALTA`, `MEDIA`, `BAIXA` em cada barra).
5. "Quais são os produtos mais sazonais da distribuidora e quais ainda têm histórico insuficiente?" (Rankings paginados).

**Arquétipo de UX:** *Workbench Analítico Híbrido* (busca direta do produto com visualização gráfica + listas ranqueadas de apoio em abas secundárias).

---

## 2. Checklist Anti-IA (Filtro Anti-Slop Obrigatório)

- [x] **Sem "AI Purple" / Sem Gradientes:** Estética sólida Papel & Tinta (`--bg-canvas`, `--bg-surface`, `--bg-subtle`).
- [x] **Tipografia Editorial:** Títulos em Signika (`--font-family-headline`), textos em Source Sans 3 (`--font-family-body`) e números tabulares em Overpass Mono (`--font-family-mono`).
- [x] **Sem 3 Colunas Mecânicas:** Layout em 4 blocos assimétricos (Busca/Cabeçalho $\rightarrow$ Cards de Diagnóstico $\rightarrow$ Gráfico Mensal $\rightarrow$ Tabelas de Ranking).
- [x] **Sem Spinners Solitários:** Especificação de Skeleton Shimmer reproduzindo a silhueta das barras do gráfico e linhas de tabela.
- [x] **Sem Telas Brancas Vazias:** Empty State guiado com sugestão de produtos populares e rankings interativos.
- [x] **Acessibilidade WCAG AA:** O gráfico mensal utiliza barras proporcionais com linha de referência 1.0 (neutro), padrões de hachura/borda e textos acessíveis (`aria-label` e tabela oculta para leitores de tela).
- [x] **Copywriting Humano e Transparente:** Linguagem direta sem jargões de IA; termos claros como "Pico", "Vale", "Alta Confiança", "Histórico Curto".

---

## 3. Tokens do Design System Consumidos

| Categoria | Tokens Utilizados (`styles.scss`) | Aplicação nesta Tela |
| :--- | :--- | :--- |
| **Superfícies** | `--bg-canvas` (`#F5F2EB`), `--bg-surface` (`#FFFFFF`), `--bg-subtle` (`#ECE7DC`), `--bg-table-header` (`#F0ECE1`), `--bg-table-row-hover` (`#F7F5EE`), `--bg-table-row-zebra` (`#FAF8F4`) | Fundo da tela, cards de KPI, inspetor mensal e tabelas |
| **Tipografia** | `--font-family-headline`, `--font-family-body`, `--font-family-mono` | Títulos (`Signika`), textos (`Source Sans 3`) e códigos/índices (`Overpass Mono` com `tabular-nums`) |
| **Texto** | `--text-primary` (`#181D19`), `--text-secondary` (`#434B44`), `--text-muted` (`#666F67`), `--text-on-brand` (`#FFFFFF`) | Rótulos, explicações, legendas e contraste AA sobre fundos sólidos |
| **Marca / Ações** | `--brand-primary` (`#1D4528`), `--brand-primary-hover` (`#14321C`), `--brand-primary-subtle` (`#E5EFE7`), `--brand-secondary` (`#8A4B14`), `--brand-secondary-subtle` (`#F9EFE5`) | Barras de pico (verde sólido), barras de vale (areia tracejada), botões e destaques ativos |
| **Feedback / Badges** | `.tag-positive` (`--feedback-positive-bg` `#185A2E`), `.tag-info` (`--feedback-info-bg` `#1B4B7A`), `.tag-warning` (`--feedback-warning-bg` `#7A4607`), `.tag-neutral` (`--feedback-neutral-bg` `#3B423C`), `.tag-critical` (`--feedback-critical-bg` `#8F1B1B`) | Badges sólidos de força/confiança com texto branco `--text-on-brand` e ícones auxiliares |
| **Bordas** | `--border-subtle` (`#DFD9CC`), `--border-default` (`#CBC3B2`), `--border-strong` (`#9E9686`), `--border-focus` (`#1D4528`) | Contorno de painéis, combobox, divisores e anel de foco acessível |
| **Espaçamento** | `--space-1` (4px), `--space-2` (8px), `--space-3` (12px), `--space-4` (16px), `--space-5` (20px), `--space-6` (24px), `--space-8` (32px) | Grid modular, alvos táteis `>= 40px` (`ui.$touch-target`) e respiros |

---

## 4. Anatomia da Tela e Layout

A tela organiza-se em 3 seções verticais integradas:

```
+-----------------------------------------------------------------------------------+
| CASCA: /analytics  [ Abas: Cross-sell | Sazonalidade (ativa) ]                     |
+-----------------------------------------------------------------------------------+
| 1. CONTROLE DE CONSULTA (BUSCA COM AUTOCOMPLETE)                                  |
| [ Buscar produto por código ou nome...                             ] [ Buscar ]   |
+-----------------------------------------------------------------------------------+
| 2. PAINEL DE DIAGNÓSTICO DO PRODUTO SELECIONADO                                   |
| Header: [1042] EXTRATO DE PROPOLIS 30ML · APIS FLORA · Estoque: 120 un.           |
|                                                                                   |
| [ Card Pico ]       [ Card Vale ]       [ Card Força ]      [ Card Confiança ]    |
| Mai–Jul (1.42x)     Nov–Jan (0.84x)     FORTE (Repete 78%)  ALTA (2 anos conc.)   |
|                                                                                   |
| 3. GRÁFICO MENSAL DE SAZONALIDADE (Índice 1.0 = Média Anual)                       |
|   1.6 |                                                                           |
|   1.4 |               [PICO]                                                      |
|   1.2 |             +---+ +---+                                                   |
|   1.0 |-------------|---| |---|-------------------------------- [Linha Neutra]   |
|   0.8 | +---+ +---+ |   | |   | +---+ +---+ +---+ +---+ +---+ +---+ [VALE]        |
|   0.6 | |   | |   | |   | |   | |   | |   | |   | |   | |   | |   | +---+ +---+   |
|       +-------------------------------------------------------------------------  |
|         Jan   Fev   Mar   Abr   Mai   Jun   Jul   Ago   Set   Out   Nov*  Dez*  |
|        [Alta][Alta][Alta][Alta][Alta][Alta][Alta][Alta][Alta][Alta][Baixa][Baixa] |
|                                                                                   |
| * Aviso: Novembro e Dezembro baseados em 1 ano de histórico (2025).               |
+-----------------------------------------------------------------------------------+
| 4. RANKINGS DE SAZONALIDADE                                                       |
| [ Botões de Alternância: (●) Mais Sazonais  ( ) Pouco Mensuráveis ]               |
|                                                                                   |
| Tabela: SKU | Descrição | Fornecedor | Força | Amplitude | Pico | Vale | Ação     |
| [1042] EXTRATO DE PROPOLIS 30ML | APIS FLORA | FORTE | 0.58 | Mai-Jul | Nov-Jan   |
| [ Paginação: < 1 2 3 > ]                                                          |
+-----------------------------------------------------------------------------------+
```

---

## 5. Especificação do Gráfico Mensal de Sazonalidade

- **Construção:** SVG ou HTML Flexbox puro com colunas responsivas, sem biblioteca pesada de terceiros (zero overhead de bundle).
- **Eixo Y:** Varia de 0.0 até `max(1.8, max_indice + 0.2)`. Linha tracejada horizontal marcando o índice 1.0 (nível neutro).
- **Eixo X:** 12 colunas correspondentes aos meses de Janeiro a Dezembro.
- **Destaque Visual:**
  - Meses de Pico: barra verde escura (`--brand-primary`), topo com indicador de valor (ex: `1.42x`).
  - Meses de Vale: barra âmbar/areia sutil (`--bg-subtle` com borda `--border-default`), topo com indicador (ex: `0.84x`).
  - Meses Normais: barra neutra suave com altura proporcional ao índice sazonal.
- **Badge de Confiança:** Embaixo de cada mês:
  - `ALTA`: Tag sutil verde clara (`Alta`).
  - `MEDIA`: Tag sutil neutra (`Média`).
  - `BAIXA`: Tag sutil de alerta (`1 ano`).
- **Acessibilidade:**
  - Cada coluna possui atributo `tabindex="0"`, `role="graphics-symbol"` e `aria-label="Mês: Maio, Índice Sazonal: 1.40x, Pico de Demanda, Confiança Alta"`.
  - Tabela semântica oculta com classe `.sr-only` contendo os 12 valores numéricos para leitores de tela.

---

## 6. Os 8 Estados Interativos Obrigatórios

1. **Default:** Tela inicial com campo de busca focado e tabela de rankings carregada no topo dos "Mais Sazonais".
2. **Hover:**
   - Barras do gráfico elevam sutilmente com sombra (`--shadow-xs`) e exibem tooltip com volume e receita média do mês.
   - Linhas da tabela de ranking ganham fundo `--bg-table-row-hover`.
3. **Focus:** Anel de foco nítido de 2px `--border-focus` com offset de 2px em inputs, botões e barras do gráfico navegadas via teclado (Tab).
4. **Active:** Clique em botão de busca ou seleção de item no ranking aciona feedback tátil visual imediato.
5. **Disabled:** Botão de busca desabilitado enquanto a query tiver menos de 1 caractere ou requisição em curso.
6. **Loading (Skeleton Shimmer):**
   - 4 blocos de skeleton para os cards de métricas.
   - Silhueta retangular com animação shimmer para o gráfico de 12 meses.
   - 5 linhas de skeleton para a tabela de rankings.
7. **Empty State:**
   - Busca sem resultado: Ilustração de lupa sutil, mensagem *"Nenhum produto encontrado com o termo pesquisado"*, botão *"Limpar busca"*.
   - Produto sem histórico suficiente: Banner informativo amigável explicando o motivo (`HISTORICO_CURTO` ou `VENDA_ESPORADICA`) sem quebrar o layout.
8. **Error State:**
   - Banner padronizado `app-error-banner` com código interno (`SEA-001`, `SEA-002` ou `ANL-001`), mensagem em português e botão *"Tentar novamente"*.
