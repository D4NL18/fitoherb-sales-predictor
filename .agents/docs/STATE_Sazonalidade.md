# STATE — Detecção de Sazonalidade por Produto (FASE F1)

**Feature:** Analytics Comercial — "Detecção de Sazonalidade por Produto" (FASE F1, slug `analytics-sazonalidade`)
**Worktree Exclusiva:** `C:\Users\danie\Documents\Github\fitoherb-analytics-sazonalidade`
**Branch:** `feature/analytics-sazonalidade`
**Por que um arquivo à parte:** O `STATE.md` principal é coordenado pelo orquestrador central. Este arquivo isolado registra o progresso exclusivo da FASE F1.
**Categoria:** A — Engenharia de Software, tipo **T1** (Full-Stack: FastAPI + Angular), estendendo o módulo `analytics`
**Etapa atual:** 4 — Quality Gate 360 e Finalização
**Faixa de IDs:** Regras `P-106` a `P-116`; prefixo de erro `SEA-XXX`

---

## 1. Escopo e Objetivos da FASE F1
- [x] Buscar produto por código ou nome (autocomplete com catálogo em cache).
- [x] Exibir série temporal líquida de vendas mensais (excluindo mês corrente parcial e abatendo devoluções `DEVOLU%`).
- [x] Calcular o índice sazonal mês a mês (1 a 12) por razão ano a ano após remoção de tendência linear (detrending).
- [x] Identificar pico e vale de sazonalidade, agrupando meses adjacentes (índice >= 90% do pico).
- [x] Medir a força da sazonalidade (`FORTE`, `MODERADA`, `FRACA`, `INSUFICIENTE`) baseada na correlação ano a ano (YoY) e amplitude do índice.
- [x] Avaliar a confiança por mês (`ALTA`, `MEDIA`, `BAIXA`) distinguindo meses com 2 observações consistentes, divergentes ou 1 única observação (nov/dez).
- [x] Fornecer rankings paginados: produtos **mais sazonais** (filtrados por fatia mínima de faturamento) e produtos **menos mensuráveis** (com motivo: histórico curto ou venda esporádica).
- [x] Expor explicitamente no domínio a função pública reutilizável `get_seasonality_index(...)` para consumo por F6 (canibalização) e F2 (produto novo).

---

## 2. Decisões e Bypasses Justificados
| Papel | Status | Motivo |
| :--- | :--- | :--- |
| `product_owner` | **Bypass** | Escopo já fatiado na seção §6 do plano mestre `ia-analytics-vendas.md`. |
| `analyst` | **Concluído** | Regras P-106 a P-116 e tarefas da feature. |
| `architect` | **Concluído** | ADR-005, contratos REST e decomposição técnica. |
| `designer` | **Concluído** | Design Plan da aba Sazonalidade seguindo o Design System Papel & Tinta. |
| `dba` | **Bypass** | Consulta somente leitura agregada em `Externo01.Vendas`, sem migrations nem DDL. |
| `ai_specialist` | **Bypass** | Algoritmo determinístico ano a ano com detrend linear; sem modelos de IA/ML ou bibliotecas pesadas externas. |
| `privacy_officer` | **Bypass** | Operação estritamente sobre SKU/Produto; sem dados pessoais ou identificação de cliente. |
| `tester` | **Concluído** | TDD First com suíte `tests/analytics/test_seasonality_*.py` (17/17 aprovados). |
| `developer` | **Concluído** | Implementação backend e frontend Angular (`ng build` concluído, 112/112 specs Karma aprovados). |
| `reviewer` | **Concluído** | Quality Gate 360, Clean Code, contrato `correlacaoYoy`, ausência de `any` e pipeline RxJS (`switchMap` + `takeUntilDestroyed`). |
| `ux_reviewer` | **Concluído** | Auditoria profunda Papel & Tinta (`styles.scss` + `_analytics-ui.scss`), ARIA combobox, inspetor interativo do gráfico e acessibilidade WCAG AA. |

---

## 3. Checklist das 5 Macro-Etapas
- [x] **Etapa 1 — Especificação (`analyst`)**
  - [x] `business_rules/analytics-sazonalidade.md` (P-106 a P-116)
  - [x] `tasks/analytics-sazonalidade.md`
- [x] **Etapa 2 — Arquitetura e Design (`architect` + `designer`)**
  - [x] `adr/ADR-005-sazonalidade-produto.md`
  - [x] `api_contracts/analytics-sazonalidade.md`
  - [x] `design/plans/analytics-sazonalidade.md` (tokens alinhados a `styles.scss`)
- [x] **Etapa 3 — TDD e Implementação (`tester` + `developer`)**
  - [x] Testes TDD: `tests/analytics/test_seasonality_*.py` (17/17 aprovados)
  - [x] Backend: domínio `seasonality.py`, `get_seasonality_index` exportada, schemas, service, cache, repository e router
  - [x] Frontend: aba sazonalidade (`OnPush`, `switchMap`, ARIA combobox, inspetor mensal, sincronia `?sku=`), serviços e modelos
- [x] **Etapa 4 — Quality Gate 360 (`reviewer` + `ux_reviewer` + `tester`)**
  - [x] Execução e aprovação de `pytest tests/analytics/test_seasonality_*.py` (17 passed)
  - [x] Execução de testes de frontend e build de produção (`ng build` exit 0, 112/112 specs aprovados)
  - [x] Verificação de governança, remoção de cores hardcoded, responsividade mobile e ausência de regressões em arquivos compartilhados
  - [x] **Auditoria Sênior UI/UX & Frontend (revisão pós-implementação):** correção de `correlacaoYoy`, error handling dedicado (`SEA-001`..`003`/`ANL-001`..`002`), alinhamento matemático da linha `1,00x`, guarda de série plana, inspetor interativo e cobertura completa em `.spec.ts`
