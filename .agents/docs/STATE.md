# STATE — Esteira Consolidada (Orquestrador)

**Feature ativa:** F7 — Diagnóstico de motivos da Tendência de Vendas com IA (Gemini 4 Hydrogen/Neon) · worktree `claude/ai-sales-trend-analysis-8b0d75`
**Etapa atual:** Plano v2 aprovado (2026-11-24); Etapa 1 (`analyst`) em andamento
**Faixa reservada para F7:** `P-150+`, erros `TIA-XXX`, `ADR-009` (P-128..P-138 canibalização e P-139..P-149 produto novo estão nas worktrees de origem)
**Último ID de regra usado:** `P-094` (P-058..P-071 e P-094: cross-sell; P-072..P-093: tendência de vendas)

## Última fase concluída
- **Fase 1 — F4 Cross-sell** (`feature/analytics-cross-sell`, 2026-11-05 a 2026-11-12): consolidada em `KNOWLEDGE_GRAPH.md`, seção "Módulo `analytics` — Cross-sell". PR aberto: https://github.com/D4NL18/fitoherb-sales-predictor/pull/8 (Auto-fix ligado).

## Próxima fase do plano mestre
- **Fase 2 — F5 Elasticidade-preço por produto e cliente** (`tasks/ia-analytics-vendas.md`). Antes de começar, revisar a lição do backtest da Fase 1 e as premissas de churn da Fase 5, que ainda aguardam confirmação do usuário.

## Log
- **2026-11-23 — F7 planejada (Orquestrador).** Triagem: Categoria A, T1 full-stack com LLM. Acionar: `analyst` (Etapa 1), `architect` + `ai_specialist` + `designer` + `privacy_officer` leve (Etapa 2), `tester`/`developer`/`ai_specialist` (Etapa 3), `reviewer` + `security` + `ux_reviewer` (Etapa 4), `devops` (Etapa 5). Dispensados: `product_owner` (escopo já fatiado no plano) e `dba` (ERP só leitura; cache de diagnósticos em GCS, sem migration). Dependências: F6 canibalização v2 e F2 produto novo ainda em worktrees; Fase 7.1 desenhada para rodar sem elas (portas "não avaliado").
- **2026-11-24 — F7 plano v2.** F6 Canibalização entrou em produção (#13) com Índice de Afinidade Semântica (`product_affinity`), também adotado pelo F2 Produto Novo (worktree). Plano revisado: afinidade como fonte única de "produto semelhante"; migração da F6 recalculada nas janelas da Tendência e separada por `sameSupplier`; lançamento afim sem depender do F2; diagnóstico mercado × concorrência pelo grupo afim. Pendências novas: merge de `origin/main` na worktree, doc do índice ausente nas regras/ADR-007, índice salvo em disco efêmero do Cloud Run (Q-8).
- **2026-11-24 — F7 orquestração do LLM.** Avaliadas as skills `langchain-expert` e `langgraph-expert`: decisão de **não usar** LangChain nem LangGraph. SDK oficial `google-genai` atrás da interface `LlmClient`, fluxo linear em Python (1 chamada por diagnóstico, 1 retry, escalonamento Neon, fallback). Gatilhos para revisitar registrados no §3.10 do plano (investigação agêntica multi-rodada, chat sobre o diagnóstico, segundo agente).
- **2026-11-24 — Q-1 decidida pelo usuário.** A análise de IA só é gerada ao apertar o botão "Gerar análise com IA" (sem lote noturno, sem chamada em GET ou carga de página). Plano §3.7 e §3.9 atualizados.
