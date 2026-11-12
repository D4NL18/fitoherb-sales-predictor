---
name: o
description: "Atalho curto para /orquestrador. Aciona o Orquestrador Autonomo para conduzir a esteira adaptativa de 5 Macro-Etapas (com triagem previa de impacto para acionar apenas as etapas e agentes necessarios) ou despachar Agentes Auxiliares sob demanda."
---

# Execucao do Workflow /o (Alias de /orquestrador)

1. Leia imediatamente @.agents/agents/orchestrator.md e @.agents/docs/STATE.md (e @.agents/docs/KNOWLEDGE_GRAPH.md, se existir).
2. Classifique a demanda do usuario:
   - **Categoria B (Consultoria Estrategica / Negocios / Financas / Governanca / N8N):** invoque diretamente o subagente auxiliar correspondente em `.agents/agents/` via `invoke_subagent` (`finance_advisor`, `negotiator`, `strategic_leader`, `privacy_officer`, `ai_governance_auditor`, `innovation_consultant`, `n8n_specialist`).
   - **Categoria A (Engenharia de Software - Features, Bugs, APIs, UI, Banco, DevOps):**
     1. **Triagem Previa de Escopo & Matriz de Impacto (obrigatoria):** identifique o tipo de demanda (T1 Full Feature, T2 Backend Only, T3 Frontend/UI, T4 Hotfix, T5 DB Only, T6 DevOps, T7 Refactor) e aplique as 7 perguntas de impacto da secao 2 do `orchestrator.md` para acionar APENAS os agentes e etapas estritamente necessarios:
        - *Backend Only:* pula `designer` e `ux_reviewer`. Sem dados pessoais, pula `privacy_officer`.
        - *Frontend / UI / CSS:* pula `dba`, `privacy_officer` e `security` dedicado. Ajuste visual de tela existente pula `product_owner` e `analyst`.
        - *Hotfix / Bugfix:* pula PO, Analista, Arquiteto e Designer. Rota: diagnostico -> `tester` (reproduz) -> `developer` (fix) -> `reviewer`.
        - *DB / Migrations:* pula Designer e UX Reviewer. Rota: `dba` -> `developer` -> `reviewer`.
        - *DevOps / Infra:* pula etapas de codigo. Rota: `devops` -> `reviewer`.
        - *Refatoracao Tecnica:* pula PO, Analista e Designer. Rota: `developer` + `tester` -> `reviewer`.
     2. **Esteira de 5 Etapas (somente o que a triagem aprovou)**, atualizando o `.agents/docs/STATE.md` a cada etapa e invocando os subagentes via `invoke_subagent`:
        1. **Etapa 1 - Descoberta, Escopo e Especificacao** (se houver novo escopo): `product_owner` -> `analyst`.
        2. **Etapa 2 - Arquitetura, UI Design Plan, Modelagem Segura e Privacy by Design:** `architect`, `designer` (se Frontend), `dba` (se Banco), `ai_specialist` (se IA), `privacy_officer` (se PII).
        3. **Etapa 3 - TDD e Execucao:** `tester` (testes primeiro) -> `developer` (+ `ai_specialist`).
        4. **Etapa 4 - Quality Gate 360 e Auto-Healer:** `reviewer`, `privacy_officer` (se PII), `ux_reviewer` (se Frontend), `security` (se Auth/Cripto/superficie critica), `tester` <-> `developer` (ate 3 tentativas).
        5. **Etapa 5 - Release, CI/CD, FinOps e Compressao** (se houver release): `devops` -> orquestrador (`context-compressor`, reset do `STATE.md`).
3. **Checkpoint Obrigatorio de Arquitetura (se a Etapa 2 for executada):** apos gerar especificacoes, contratos de API, modelagem de banco, validacao LGPD e Design Plan, apresente um resumo executivo ao usuario e valide antes de prosseguir para a Etapa 3 (TDD e Codigo), a menos que o usuario tenha ordenado execucao direta sem pausas.
4. **Regras permanentes:** veto a documentacao na raiz (tudo em `.agents/docs/`); tarefas `[PARALLEL]` com estados isolados (`STATE_<Frente>.md`) mesclados no `STATE.md`; registrar no `STATE.md` quais agentes foram acionados e quais foram pulados (com justificativa); manter `.agents/hooks.json` e `.agents/mcp_config.json` sincronizados com a stack.
