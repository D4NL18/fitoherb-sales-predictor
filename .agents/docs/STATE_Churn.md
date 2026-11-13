# STATE — Churn de Clientes com Score de Prioridade (FASE F3)

**Feature:** Analytics Comercial — "Churn de Clientes com Score de Prioridade" (slug `analytics-churn`)  
**Worktree Exclusiva:** `C:\Users\danie\Documents\Github\fitoherb-analytics-churn`  
**Branch:** `feature/analytics-churn`  
**Faixa de Regras Exclusiva:** P-117 a P-127 (prefixo de erro: `CHU-XXX`)  
**Categoria:** A — Engenharia de Software, tipo **T1** (Full-Stack: FastAPI + Angular), estendendo o módulo `analytics`  
**Etapa Atual:** Concluída até Etapa 4 (Quality Gate 360 Aprovado) — Pronta para Etapa 5 (Release)  

---

## 1. Decisões do Usuário e Premissas da Feature (Fase F3 / §7)
| # | Decisão | Descrição |
|---|---|---|
| **D1** | **60 dias em risco** | Cliente sem comprar há $\ge 60$ dias a partir do último pedido de `VENDA` é considerado em risco. Priorização combina tempo sem comprar e faturamento médio mensal. |
| **D3** | **1 cliente = 1 código** | Um cliente = um único `Cod Cliente`. Sem agrupamento de filiais nem deduplicação cadastral externa. |
| **D4** | **Devoluções abatidas** | Devoluções (`[Operação] LIKE 'DEVOLU%'`) abatem quantidade e faturamento líquido, mas NUNCA renovam recência de compra nem criam novas transações. |
| **D-SCORE** | **Score de Retenção** | $\text{scorePrioridade} = \text{faturamentoMedioMensal} \times \text{fatorTempo}$ (em R$). $\text{fatorTempo} = \min(\text{diasSemComprar} / \text{diasReferencia}, 2.0)$. $\text{diasReferencia} = \max(60, 1.5 \times \text{gapTipico})$. |
| **D-INAT** | **Inativos Antigos** | Clientes com $\text{diasSemComprar} > 180$ saem da lista ativa de risco e vão para a lista de recuperação/inativos antigos. |
| **D-HIST** | **Histórico Curto** | Clientes com $< 3$ pedidos recebem selo "histórico curto" e divisor mínimo de 3 meses para cálculo do faturamento médio mensal. |

---

## 2. Checklist da Esteira (Etapas 1 a 4)
- [x] **Etapa 1: Descoberta e Especificação (`analyst`)**
  - [x] `.agents/docs/business_rules/analytics-churn.md` (P-117 a P-127)
  - [x] `.agents/docs/tasks/analytics-churn.md` (Checklist de tarefas atômicas)
  - [x] Atualização do `GLOSSARY.md` com termos ubíquos da feature
- [x] **Etapa 2: Arquitetura, Design e Privacy by Design**
  - [x] `architect`: ADR em `.agents/docs/adr/ADR-006-churn-clientes.md` e contrato REST em `.agents/docs/api_contracts/analytics-churn.md` (envelope data/meta, GET /analytics/churn/customers, GET /analytics/churn/customers/{customerCode}, GET /analytics/churn/inactive)
  - [x] `designer`: Design Plan em `.agents/docs/design/plans/analytics-churn.md` (tabela priorizada, chips de status, drawer de detalhes, exportação CSV, 8 estados)
  - [x] `dba`: BYPASS justificado (somente leitura em views/tabelas existentes)
  - [x] `ai_specialist`: BYPASS justificado (score determinístico em pandas/numpy)
  - [x] `privacy_officer`: Parecer obrigatório em `.agents/docs/privacy/analytics-churn.md` (clientes PJ/PF, minimização, sem PII nos contratos, sem dados pessoais em logs)
- [x] **Etapa 3: TDD e Implementação**
  - [x] `tester`: Testes primeiro em `tests/analytics/test_churn_*.py` (17 testes passando)
  - [x] `developer`: Implementação backend (`churn.py`, schemas, queries no repository, service, router)
  - [x] `developer`: Implementação frontend (models, service/store, componentes, drawer, rota `/analytics/churn`)
- [x] **Etapa 4: Quality Gate 360 + Auto-Healer**
  - [x] `reviewer`: Clean Code, sem números mágicos, conformidade com `.agents/rules/`
  - [x] `ux_reviewer`: Auditoria de fidelidade ao Design Plan, tokens Papel & Tinta (`styles.scss`), acessibilidade WCAG 2.1 AA, responsividade (< 640px) e LGPD na UI
  - [x] `privacy_officer`: Auditoria LGPD de código com aprovação formal (LGPD-CHU-01..06)
  - [x] `tester`: Execução final dos testes (17/17 pytest, 112/112 karma, build angular completo) e validação quantitativa de superioridade do score no backtest (P-127)

---

## 3. Bypasses Justificados
- **product_owner:** Escopo já fatiado no Plano Mestre de Analytics Comercial (§7 de `ia-analytics-vendas.md`).
- **dba:** Consultas analíticas somente leitura em `Externo01.Vendas`, sem migrations nem escrita de banco.
- **ai_specialist:** Algoritmo de score determinístico de retenção baseado em recência, mediana de compras e faturamento médio ponderado (sem LLM / Deep Learning).
- **security dedicado:** Apenas novas rotas GET de leitura dentro da política de autorização já existente do módulo; auditoria securitária coberta pelo `reviewer`.

---

## 4. Log de Execução
- **2026-11-12**: Início da Fase F3. Branch `feature/analytics-churn`.
- **2026-11-12**: Etapa 1 concluída (`business_rules/analytics-churn.md`, `tasks/analytics-churn.md`, `GLOSSARY.md`).
- **2026-11-12**: Etapa 2 concluída (`ADR-006`, `api_contracts`, `design/plans`, `privacy`).
- **2026-11-12**: Etapa 3 concluída com TDD First: 17 testes pytest e 4 specs karma verdes.
- **2026-11-12**: Etapa 4 concluída: Quality Gate 360 aprovado em todas as frentes. Pronto para release.
- **2026-11-13**: Revisão sênior UI/UX e Frontend concluída:
  - Removidas ~90 cores hardcoded nos SCSS de F3 em favor dos tokens Papel & Tinta (`styles.scss` + `_analytics-ui.scss`), respeitando tags globais (`.tag-positive`/`warning`/`critical`/`neutral`), contraste AA/AAA (`--text-secondary` sobre `--bg-subtle`/`--bg-table-header`), `tabular-nums`, alvos `>= 40px` e layout mobile em cartões (`< 639.98px`).
  - Adicionados `ChangeDetectionStrategy.OnPush`, `switchMap` + `takeUntilDestroyed` (lista e drawer, com cancelamento ao fechar), filtros completos (`TODOS`), `dataReferencia`, `<app-list-pager>`, alinhamento com API de inativos sem inventar `scorePrioridade`, histórico mensal ordenado e variação trimestral sem multiplicação por 100.
  - Implementados WCAG 2.1 AA no drawer e tabela: `aria-live="polite"`, `aria-busy`, `inert` no fundo, Focus Trap (`Tab`/`Shift+Tab`), foco inicial imediato (`visibility 0s` na abertura), restauração de foco, `Escape`/backdrop, scroll lock e estado de erro com retry.
  - Exportação CSV blindada contra Formula Injection (`=`, `+`, `-`, `@`, `\t`, `\r`), BOM UTF-8, escape RFC 4180 e verificação LGPD (zero `customerCode` em URL/storage/`console.log`, zero PII).
  - Validação final pós-revisão: `112 SUCCESS` (`ng test --watch=false --browsers=ChromeHeadless`), `ng build` limpo (`churn-page-component` 59.86 kB) e `17 passed` (`pytest tests/analytics/test_churn_*.py`).
