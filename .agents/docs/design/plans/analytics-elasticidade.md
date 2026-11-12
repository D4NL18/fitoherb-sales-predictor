# Design Plan: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/design/plans/analytics-elasticidade.md`
> **Responsável:** Designer (`designer`) / `uiux-expert`
> **Auditor:** UX Reviewer (`ux_reviewer`)
> **Status:** Aprovado para Implementação (Etapa 2)
> **Alinhamento:** `DESIGN_SYSTEM.md` e regras anti-pattern (`frontend-ui-anti-patterns.md`)

---

## 1. Visão Geral e Filosofia Visual

A funcionalidade de Elasticidade-Preço entrega transparência analítica para tomadores de decisão comercial. O design segue o conceito **Soft SaaS Premium**:
- Evita gráficos genéricos e gradientes artificiais.
- Apresenta métricas claras: Coeficiente $\beta$, Classificação (`ELÁSTICO` vs `INELÁSTICO`), Intervalo de Confiança e Simulação Reativa.
- Oferece um simulador interativo onde o usuário ajusta um controle deslizante de preço e observa em tempo real o impacto em Volume, Receita e Margem em R$.

---

## 2. Macroestrutura da Tela (`/analytics/elasticity`)

A página é composta por 4 blocos visuais ordenados logicamente:

1. **Barra de Busca e Seleção de Produto (Hero Search):**
   - Campo de entrada com busca reativa por código ou descrição.
   - Dropdown de autocomplete com código, descrição e fornecedor.
2. **Card de Diagnóstico de Elasticidade do Produto:**
   - Badge principal de sensibilidade: `ELÁSTICO` (Teal suave / Amber sutil) ou `INELÁSTICO` (Emerald suave).
   - Badge de confiança estatística: `CONFIANÇA ALTA` (Emerald), `CONFIANÇA MÉDIA` (Amber), `BAIXA CONFIANÇA / HISTÓRICO CURTO` (Neutro/Cinza).
   - Métricas em grid editorial: Coeficiente de Elasticidade, Intervalo 95%, $R^2$ e Observações Válidas.
   - Mensagem de insight em linguagem natural de negócios.
3. **Painel do Simulador de Reajuste de Preço:**
   - Slider com controle de -50% a +100% com marcações em 0%, +5%, +10%, +20%.
   - Input numérico sincronizado para ajuste fino.
   - Cards de impacto em 3 colunas:
     - **Volume:** Unidades atuais vs projetadas e $\Delta\%$.
     - **Receita:** Faturamento atual vs projetado e $\Delta$ R$.
     - **Margem de Contribuição:** Margem atual vs projetada e $\Delta$ R$ com destaque de rentabilidade.
4. **Tabela de Clientes do Produto com Elasticidade Individual:**
   - Listagem com paginação e busca rápida por `customerCode`.
   - Colunas: Código do Cliente, Total de Pedidos, Unidades Totais, Elasticidade Empírica, Elasticidade Suavizada (Shrinkage) e Ação de Simular Individualmente.

---

## 3. Os 8 Estados Interativos Mandatórios

| Estado | Descrição da Experiência Visual |
| :--- | :--- |
| **1. Initial / Idle** | Campo de busca focado com placeholder amigável; área de conteúdo com banner convidativo e instrução clara ("Busque um produto por código ou nome para analisar sua sensibilidade de preço"). |
| **2. Loading** | Skeleton loader no formato dos cards de métricas e tabela de clientes, com shimmer sutil de 1.5s, prevenindo Cumulative Layout Shift (CLS). |
| **3. Success** | Dados renderizados com transições suaves (fade-in 200ms); números formatados no padrão brasileiro (`pt-BR`). |
| **4. Empty** | Estado vazio ilustrado quando o produto não possui clientes com mais de um pedido, com texto orientativo claro. |
| **5. Error** | Banner de alerta estilizado no padrão do Design System (`--color-danger-bg`), exibindo código semântico (`ELA-001`, `ELA-003`) e botão de ação "Tentar Novamente". |
| **6. Disabled** | Controles de slider e botões desabilitados com opacidade 0.6 e cursor `not-allowed` durante chamadas ativas de API. |
| **7. Invalid** | Feedback de validação inline caso o usuário digite um percentual fora de [-50%, +100%], com borda vermelha suave e mensagem abaixo do input. |
| **8. Partial / Low-Confidence** | Card com badge âmbar sutil informando "Baixa Variação Histórica de Preço", explicando de forma didática que a elasticidade de -1.2 foi aplicada como estimador canônico defensivo. |

---

## 4. Tokens e Estilos Aplicados

- **Cores:**
  - Primária: `--color-primary` (`#0D9488`) para botões de ação e tabs ativas.
  - Alerta/Atenção: `--color-warning` (`#F59E0B`) para produtos elásticos e avisos de confiança média.
  - Sucesso/Inelástico: `--color-success` (`#10B981`) para produtos inelásticos de oportunidade.
  - Superfícies: Cartões com borda `--color-neutral-200` (`#E2E8F0`), fundo `#FFFFFF` e sombra suave `0 1px 3px rgba(0,0,0,0.05)`.
- **Tipografia:**
  - Títulos: Inter / Sans-serif 600 com tracking -0.01em.
  - Números e métricas: Tabular figures para alinhamento perfeito de decimais.
- **Acessibilidade:**
  - Todos os elementos interativos possuem `:focus-visible` com outline contrastante.
  - Controles de slider possuem atributos `aria-valuemin`, `aria-valuemax` e `aria-valuenow`.
