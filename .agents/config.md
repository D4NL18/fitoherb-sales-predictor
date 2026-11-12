# AI Agent Guidelines

Este repositório utiliza a esteira de 5 Macro-Etapas consolidada, adaptativa e orientada a contexto definida em `AGENTS.md` e orquestrada por `.agents/agents/orchestrator.md`.

---

## 1. Regras Anti-Sobrecarga Cognitiva (Context Pruning & Triagem)
Para manter a performance de raciocínio da IA impecável e evitar o esgotamento da Janela de Contexto (*Context Window*), aplicam-se obrigatoriamente as seguintes travas de leitura e despacho:

- **Triagem Prévia de Escopo:** O Orquestrador avalia o escopo e o tipo de demanda (Backend Only, Frontend/UI, Hotfix, DB Only, DevOps, Refactor) ANTES de invocar qualquer agente. É expressamente PROIBIDO acionar agentes ou etapas irrelevantes (ex: mudanças de backend não passam por Designer/UX Reviewer; mudanças de CSS ou refactors técnicos sem dados pessoais não passam por Privacy Officer nem SecOps formal; bugfixes pontuais vão direto para TDD/Fix sem PO/Analista).
- **Leitura Dinâmica (Lazy Loading):** Ao ser ativada, a IA carrega na memória APENAS este arquivo (`config.md`), o `STATE.md`, e o descritivo do Agente atual em execução (ex: `developer.md`). É proibido tentar ler toda a pasta `.agents/` ao mesmo tempo.
- **Firewall de Raciocínio (Isolamento de Domínio):** O **Desenvolvedor** e o **Reviewer** não leem regras de negócio extensas (`.agents/docs/business_rules/`). O papel deles é ler APENAS o checklist técnico enxuto gerado pelo Arquiteto (`.agents/docs/tasks/`). Quem consolida regras de negócio é o **Analista** e o **Arquiteto**.
- **Arquivamento e Limpeza (Archive):** Terminada uma feature, os arquivos concluídos daquela task podem ser arquivados em `.agents/docs/.archive/`. Agentes ignoram a pasta `.archive/` em buscas ativas.

---

## 2. Instruções Base da Esteira Adaptativa (5 Macro-Etapas)
1. **Orquestrador é o Maestro:** Conduz a triagem e o roteamento adaptativo da esteira de 5 macro-etapas ou despacha diretamente Agentes Auxiliares (Finanças, Negociação, Liderança, LGPD, Ética IA, Inovação, N8N).
2. **Gestão de Contexto:** Mantém `.agents/docs/STATE.md` atualizado com a etapa em andamento e os bypasses justificados.
3. **As 5 Macro-Etapas:**
   - **Etapa 1 (PO + Analista):** Discovery e escopo no `ROADMAP.md` e regras `P-XXX` em `business_rules/` *(Pula se bugfix, refactor ou técnico)*.
   - **Etapa 2 (Arquitetura, UI Plan, Modelagem & Privacy):** Contratos REST `{ data, meta }`, Design Plan (se frontend), migrations seguras (se banco), esteira ML (se IA) e Privacy by Design (se PII).
   - **Etapa 3 (TDD e Execução):** Tester escreve testes unitários/contrato ANTES do Desenvolvedor codificar em branch isolada.
   - **Etapa 4 (Quality Gate 360 & Auto-Healer):** Code review, UX review (se front), LGPD (se PII), SecOps (se auth/crítico) e Auto-Healer (até 3 tentativas).
   - **Etapa 5 (Release & FinOps):** Validação de CI/CD, FinOps Scorecard >= 4.80, Docker enxuto e abertura de Pull Request.
4. **Governança Estrita:** Toda documentação reside em `.agents/docs/` (veto absoluto à raiz `/`).
