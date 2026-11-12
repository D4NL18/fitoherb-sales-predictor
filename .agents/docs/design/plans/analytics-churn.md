# Design Plan — Analytics Comercial · F3 Churn de Clientes com Score de Prioridade

<!-- Hallmark · pre-emit critique: P5 H5 E5 S5 R5 V5 · macrostructure: workbench analítico com ledger ranqueado, kpis de impacto, drawer de detalhes e exportação CSV -->

| Campo | Valor |
| :--- | :--- |
| **Feature** | US-F3 — Detecção e Priorização de Churn de Clientes por Urgência e Receita |
| **Branch** | `feature/analytics-churn` |
| **Regras** | `.agents/docs/business_rules/analytics-churn.md` (P-117 a P-127) |
| **Contrato** | `.agents/docs/api_contracts/analytics-churn.md` (v1.0.0) |
| **Design System** | Papel & Tinta (`frontend/src/styles.scss`) — Signika, Source Sans 3, Overpass Mono |
| **Autor / Etapa** | Designer de UI/UX (`uiux-expert`) — Etapa 2 |

---

## 1. Identificação e Objetivos de UX

### Atores e Dores Resolvidas
- **Coordenador Comercial / Televendas:** Não sabe quais clientes parados priorizar no dia a dia. Relatórios brutos com centenas de clientes sem comprar há 60 dias geram paralisia analítica.
- **Vendedor / Televendas Ativo:** Precisa saber rapidamente há quantos dias o cliente não compra, qual era seu ritmo habitual, o faturamento em jogo e quais produtos essenciais ele parou de comprar, para ligar com uma abordagem altamente consultiva.

### Objetivos de Interface
1. **Hierarquia de Impacto Imediato:** O topo da tela destaca o montante total de receita mensal sob risco (`receitaMensalEmRisco`) e o número de clientes em perigo imediato (`EM_RISCO`).
2. **Priorização Clara (Ledger):** Tabela única ordenada por `scorePrioridade` decrescente, destacando código do cliente, status em chip semântico, dias sem comprar, faturamento médio mensal e o score monetário.
3. **Diagnóstico sem Sair do Fluxo (Drawer):** Ao clicar em qualquer linha da tabela, um painel lateral deslizante (drawer) abre com a decomposição do score, tendência recente e lista dos 5 produtos perdidos.
4. **Filtros e Fila de Inativos:** Abas rápidas/filtros para alternar entre `EM_RISCO`, `ALERTA`, `SAUDAVEL` e a fila especializada de `Inativos Antigos (> 180 dias)`.
5. **Exportação Operacional:** Botão "Exportar CSV" que gera a relação priorizada para ação externa do time comercial.

---

## 2. Checklist Anti-IA (Hallmark Anti-AI-Slop)

- [x] **Sem AI Purple ou gradientes genéricos:** Cores exclusivamente sólidas do tema Papel & Tinta (tons de verde erva-mate, pergaminho, bordas sépia sutis).
- [x] **Tipografia com Propósito:** Títulos em Signika (`--font-family-headline`), textos de leitura em Source Sans 3 (`--font-family-body`) e números/códigos/valores monetários em Overpass Mono (`--font-family-mono`).
- [x] **Copy Humano e Comercial:** Sem chavões como "previsão mágica", "inteligência hiper-avançada", "potencialize retenção". Textos diretos: "Clientes em Risco", "Score de Prioridade", "Último Pedido há X dias".
- [x] **Sem Spinners Soltos no Vazio:** Skeletons geométricos fiéis à tabela (linhas com placeholders) e ao drawer lateral.
- [x] **Status Multi-Sensorial:** Todo chip possui texto explícito e ícone semântico, nunca dependendo exclusivamente da cor para acessibilidade WCAG AA.
- [x] **Drawer com Foco Gerenciado:** Abertura com tecla `Esc` para fechar e foco restaurado à linha de origem.

---

## 3. Tokens do Design System (`styles.scss`)

| Categoria | Token CSS | Aplicação na Interface |
| :--- | :--- | :--- |
| **Tipografia** | `--font-family-headline` | Cabeçalho da página e títulos dos cartões/drawer |
| | `--font-family-body` | Rótulos, explicações, textos descritivos |
| | `--font-family-mono` | Códigos de cliente, dias parados, valores R$ e score |
| **Superfície** | `--bg-canvas` | Fundo principal da página |
| | `--bg-surface` | Fundo dos cartões KPI, tabela e drawer |
| | `--bg-subtle` | Cabeçalho da tabela, faixas de destaque |
| | `--bg-table-row-hover` | Hover interativo de linhas clicáveis da tabela |
| **Texto** | `--text-primary` | Conteúdo textual principal, valores em destaque |
| | `--text-secondary` | Rótulos de metadados, unidades, cabeçalhos |
| | `--text-muted` | Textos secundários, avisos de histórico curto |
| **Bordas** | `--border-subtle` | Linhas divisórias da tabela e cartões |
| | `--border-default` | Contornos de botões secundários e inputs |
| | `--border-focus` | Contorno de acessibilidade em foco de teclado |
| **Feedback** | `.tag-critical` | Chip de status `EM_RISCO` |
| | `.tag-warning` | Chip de status `ALERTA` |
| | `.tag-neutral` | Chip de status `SAUDAVEL` e `INATIVO_RECUPERACAO` |

---

## 4. Estrutura Visual da Página (`/analytics/churn`)

```
+---------------------------------------------------------------------------------------------------+
| Aba: [ Cross-sell ]   [ Churn de Clientes (Ativo) ]                                               |
+---------------------------------------------------------------------------------------------------+
| Cabeçalho: Churn de Clientes                                                                      |
| Subtítulo: Clientes parados priorizados pela combinação de tempo sem comprar e faturamento médio |
+---------------------------------------------------------------------------------------------------+
| [ KPI Card 1: R$ 1.854.200,50 em Risco ]   [ KPI Card 2: 350 Clientes em Risco ] [ 210 em Alerta] |
+---------------------------------------------------------------------------------------------------+
| Filtros: (o) Em Risco (350)   ( ) Em Alerta (210)   ( ) Saudáveis (1.400)   ( ) Inativos (>180d)  |
|                                                                    [ [↓] Exportar Lista (CSV) ]   |
+---------------------------------------------------------------------------------------------------+
| TABELA PRIORIZADA (Ledger)                                                                        |
| Cliente  | Status    | Dias Parado | Cadência Habitual | Faturamento Médio | Score Prioridade     |
| #1042    | [EM_RISCO]| 74 dias     | 18 dias (ref 60d) | R$ 48.250,00      | R$ 59.347,50  [>]    |
| #2891    | [EM_RISCO]| 65 dias [!] | Histórico curto   | R$ 12.400,00      | R$ 13.392,00  [>]    |
| ...      |           |             |                   |                   |                      |
| Paginação: < Anterior   1 2 3 4 5 ... 7   Próxima >                                               |
+---------------------------------------------------------------------------------------------------+
| DRAWER LATERAL (Aberto ao clicar no cliente #1042)                                                |
| [X] Fechar (Esc)                                                                                  |
| Cliente #1042 — Detalhes do Churn                                                                |
| Status: [EM_RISCO]  | Último Pedido: 30/08/2026 (há 74 dias)                                      |
| Decomposição: Fator Tempo 1.23x × Faturamento Médio R$ 48.250,00 = Score R$ 59.347,50            |
| Variação Recente: Queda de -38,4% nos últimos 3 meses vs 3 meses anteriores                       |
| Produtos Perdidos Mais Relevantes:                                                                |
| • #501 Extrato de Própolis Verde 30ml — Última compra: 15/06/2026 (R$ 14.200,00 hist.)            |
+---------------------------------------------------------------------------------------------------+
```

---

## 5. Matriz dos 8 Estados Interativos Obrigatórios

| Componente | 1. Default | 2. Hover | 3. Focus | 4. Active | 5. Disabled | 6. Loading | 7. Empty | 8. Error |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Linha da Tabela** | Fundo `--bg-surface`, borda sutil | `--bg-table-row-hover`, cursor pointer | Outline `--border-focus` 2px | Fundo sutilmente pressionado | Opacidade 0.5 (se inativa) | Skeleton retangular mono | Mensagem informativa com CTA | Borda de alerta |
| **Botão Exportar CSV** | Borda sólida `--border-default`, texto primário | Fundo `--bg-subtle`, cor ativa | Ring de foco visível | Leve escala ou depressão | Opacidade 0.4, cursor not-allowed | Spinner circular compacto com texto "Exportando..." | Oculto se lista vazia | Feedback de erro discreto |
| **Filtro de Status (Pills)** | Pill neutra `--bg-subtle` | Realce na borda e fundo | Outline visível | Seleção com `--brand-primary` | Indisponível se count = 0 | Pulsação de shimmer | Contador (0) visível | Estado mantido |
| **Drawer de Detalhes** | Fechado (fora da viewport) | - | Foco preso no botão fechar | Transição suave 250ms | - | Skeleton dos cartões de detalhe | Alerta de sem dados adicionais | Banner com botão recarregar |
| **Paginação** | Botões com texto e número de página | Realce de hover na página | Foco no teclado | Página atual preenchida | `Anterior` desabilitado na pág 1 | Desabilitada durante fetch | Oculta se totalItems = 0 | Mantém estado anterior |

---

## 6. Acessibilidade (WCAG 2.1 AA)
- Relação de contraste mínima de 4.5:1 para todo texto informativo.
- Cabeçalhos de tabela com atributos `scope="col"` e navegação via teclado com `Enter` para abrir o drawer.
- Atributo `aria-expanded="true/false"` e `role="dialog"` no drawer lateral com anúncio via leitor de tela.
- Fechamento do drawer via tecla `Escape`.
