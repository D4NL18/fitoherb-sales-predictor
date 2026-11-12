# Fluxo de Desenvolvimento com IA (AI Agents Workflow) 🤖🚀

Fluxo obrigatório para qualquer tarefa assistida por IA neste projeto. O diretório `.agents/` é a fonte única da verdade: `agents/` (subagentes), `skills/` (1º nível, `<nome>/SKILL.md`, servindo também como slash commands), `rules/` (flat, com frontmatter de trigger) e `docs/` (documentação e estado).

---

## REGRA DE OURO: Governança de Documentação (`.agents/docs/`)
> [!CAUTION]
> **É TERMINANTEMENTE PROIBIDO SALVAR ARQUIVOS DE DOCUMENTAÇÃO NA RAIZ DO REPOSITÓRIO (`/`).** Todo artefato reside em `.agents/docs/`, seguindo os templates oficiais:
> - **Design System Mestre:** `.agents/docs/design/DESIGN_SYSTEM.md` (Template: `design/TEMPLATE_DESIGN_SYSTEM.md`)
> - **Design Plan por Feature:** `.agents/docs/design/plans/<feature>.md` (Template: `design/TEMPLATE_DESIGN_PLAN.md`)
> - **Banco de Dados (Schema & Seeds):** `.agents/docs/db/<modulo>.md` (Template: `db/TEMPLATE.md`; seeds em `db/seeds/`)
> - **Regras de Negócio (P-XXX):** `.agents/docs/business_rules/<feature>.md` (Template: `business_rules/TEMPLATE.md`)
> - **Contratos de API REST:** `.agents/docs/api_contracts/<entidade>.md` (Template: `api_contracts/TEMPLATE.md`)
> - **Tarefas e Checklists:** `.agents/docs/tasks/<feature>.md` (Template: `tasks/TEMPLATE.md`)
> - **Decisões de Arquitetura (ADR):** `.agents/docs/adr/ADR-<num>-<nome>.md` (Template: `adr/TEMPLATE.md`)
> - **Privacidade (RIPD/DPIA):** `.agents/docs/privacy/`
> - **Arquitetura Base:** `.agents/docs/architecture/ARCHITECTURE.md` · **Glossário:** `.agents/docs/GLOSSARY.md`
> - **Backlog e Roadmap:** `.agents/docs/ROADMAP.md` · **Estado:** `.agents/docs/STATE.md` · **Memória:** `.agents/docs/KNOWLEDGE_GRAPH.md`

---

## Roteamento Autônomo e Repertórios Delimitados 🚦
> [!IMPORTANT]
> 1. **Zero chamadas manuais de skills:** o **Orquestrador** (`.agents/agents/orchestrator.md`) classifica a demanda e invoca o subagente correto via `invoke_subagent`.
> 2. **Repertório fechado:** cada subagente (`subagent: true`) executa seu **Boot Protocol** e lê apenas os `SKILL.md` homologados para seu domínio (anti context bloat).
> 3. **Categoria A (Engenharia)** segue a Esteira de 5 Macro-Etapas **após a Triagem Prévia de Escopo** (abaixo). **Categoria B (Consultoria)** — finanças, negociação, liderança, LGPD corporativa, governança de IA, inovação, N8N — aciona diretamente o agente auxiliar.
> 4. **Zero execução cega de etapas:** o Orquestrador avalia a demanda ANTES de disparar qualquer agente; etapas e agentes só são acionados se houver real necessidade comprovada.

### Triagem Prévia de Escopo — Matriz por Tipo de Demanda (Categoria A)
1. **T1: Nova Feature Completa (Full-Stack):** executa as 5 Macro-Etapas com os agentes de domínio aplicáveis.
2. **T2: Backend Only (API, Service, Regra de Negócio, Query):**
   - **Bypass Automático:** NÃO passa por `designer` nem `ux_reviewer`. Se não coleta nem manipula dados pessoais (PII), NÃO passa por `privacy_officer`.
   - Rota: `architect` (se houver novo contrato) → `tester` + `developer` → `reviewer` → `devops`.
3. **T3: Frontend / UI / CSS / Estilização:**
   - **Bypass Automático:** NÃO passa por `dba` (sem banco), NÃO passa por `privacy_officer` (sem coleta nova de dados), NÃO passa por `security` dedicado (validação padrão no `reviewer`). Se for ajuste de estilo ou componente existente, dispensa `product_owner` e `analyst`.
   - Rota: `designer` (se exigir novo mockup) → `developer` → `tester` + `ux_reviewer` → `reviewer`.
4. **T4: Hotfix / Bugfix Pontual:**
   - **Bypass Automático:** dispensa PO, Analista, Arquiteto e Designer.
   - Rota direta: diagnóstico → `tester` (reproduz com teste) → `developer` (corrige) → `reviewer` (validação e commit).
5. **T5: Database / Migrations Only:**
   - **Bypass Automático:** dispensa Designer, UX Reviewer e PO/Analista se for técnico.
   - Rota: `dba` (migration com travas anti-perda) → `developer` (executa/testa) → `reviewer`.
6. **T6: DevOps / CI/CD / Infra Only:**
   - **Bypass Automático:** dispensa todas as etapas de produto/código.
   - Rota direta: `devops` → `reviewer`.
7. **T7: Refatoração Técnica Interna:**
   - **Bypass Automático:** dispensa PO, Analista e Designer.
   - Rota: `developer` + `tester` → `reviewer`.

> As 7 Perguntas de Decisão de Impacto que fundamentam cada bypass estão em `.agents/agents/orchestrator.md` (seção 2). Toda decisão de acionar ou pular agentes é registrada no `.agents/docs/STATE.md`.

---

## Esteira Consolidada de Desenvolvimento (5 Macro-Etapas · Execução Condicional)

> Cada etapa e cada papel abaixo só é executado se a Triagem Prévia o tornar necessário.

**ETAPA 1 — Descoberta, Escopo e Especificação** (`product_owner` + `analyst`) — *apenas quando houver novo escopo funcional de produto*
- **PO:** fatia a demanda em User Stories INVEST em `.agents/docs/ROADMAP.md` e marca tarefas paralelizáveis com `[PARALLEL]`.
- **Analista:** discovery com o usuário, regras `P-XXX` em `.agents/docs/business_rules/<feature>.md`, linguagem ubíqua e escopo inicial em `.agents/docs/tasks/<feature>.md`.

**ETAPA 2 — Arquitetura, UI Design Plan, Modelagem Segura e Privacy by Design** (`architect` + `designer` + `dba` + `ai_specialist` + `privacy_officer`) — *apenas os papéis impactados pela demanda*
- **Arquiteto:** arquitetura, ADRs (`.agents/docs/adr/`), contratos REST com envelope `data`/`meta` (`.agents/docs/api_contracts/<entidade>.md`) e checklist técnico atômico em `.agents/docs/tasks/<feature>.md`.
- **Designer (se Frontend):** Design Plan obrigatório em `.agents/docs/design/plans/<feature>.md` via `uiux-expert`, seguindo `DESIGN_SYSTEM.md`, 8 estados interativos e filtro Hallmark Anti-IA (`frontend-ui-anti-patterns.md`).
- **DBA (se Banco):** Migrations seguras com travas anti-perda de dados, schema em `.agents/docs/db/<modulo>.md` e seeds em `.agents/docs/db/seeds/`.
- **AI Specialist (se IA):** esteira de ML, RAG, prompts modulares e orquestração de tokens.
- **Privacy Officer (se houver dados pessoais/PII ou decisão automatizada de IA):** Privacy by Design — minimização/anti-overfetching nos contratos, 10 Bases Legais (Art. 7º e 11), Privacy by Default na UI e RIPD/DPIA em `.agents/docs/privacy/` se houver dados sensíveis ou decisões automatizadas de IA.
- **Checkpoint Obrigatório:** resumo executivo ao usuário e validação antes da Etapa 3 (salvo ordem de execução direta).

**ETAPA 3 — TDD e Execução** (`tester` + `developer` + `ai_specialist`)
- **Tester (TDD First):** suíte de testes unitários e de contrato ANTES de qualquer lógica produtiva.
- **Desenvolvedor (+ AI Specialist):** código em branch isolada até os testes passarem, usando tokens do `DESIGN_SYSTEM.md`, Design Plan, contratos de API e `.agents/rules/`; commits via `git-expert` rastreando `P-XXX`.

**ETAPA 4 — Quality Gate 360, Auditorias e Auto-Healer** (`reviewer` + `privacy_officer` + `ux_reviewer` + `security` + `tester`) — *auditorias especializadas acionadas por impacto*
- **Reviewer:** Clean Code, SOLID, complexidade cognitiva, conformidade com `.agents/rules/` e veto a documentação fora de `.agents/docs/`.
- **Privacy Officer (se PII):** Auditoria de Código LGPD (PII em controllers, services, DTOs e logs; isolamento multi-tenant) com **poder de veto imediato**.
- **UX Reviewer (se Frontend):** fidelidade ao Design Plan e `DESIGN_SYSTEM.md`, filtro Anti-IA, Skeleton Loaders, Empty States e 8 estados.
- **Security (se Auth/Cripto/superfície crítica; caso contrário a checagem básica fica com o `reviewer`):** OWASP (Injections, XSS, JWT no localStorage, Indirect Prompt Injection em RAG, secrets expostos) — bloqueia a esteira.
- **Tester ↔ Developer (Auto-Healer):** testes e linters; em falha, correção autônoma guiada pelo Stack Trace por até **3 tentativas** antes de escalar ao humano.

**ETAPA 5 — Release, CI/CD, FinOps e Compressão de Contexto** (`devops` + `orchestrator`)
- **DevOps:** CI/CD, Docker multi-stage enxuto, FinOps (Scale-to-Zero, ciclo de vida GCS, Scorecard >= 4.80) e Pull Request com descrição pré-preenchida.
- **Orquestrador:** `context-compressor` consolida decisões em `.agents/docs/KNOWLEDGE_GRAPH.md` e reseta o `.agents/docs/STATE.md`.

---

## Diretrizes Operacionais
- **Paralelismo Seguro (`[PARALLEL]`):** subagentes paralelos via `invoke_subagent`, cada um com estado isolado (ex.: `STATE_Frontend.md`, `STATE_Backend.md`), mesclados no `STATE.md` ao final.
- **Infra Dinâmica (Hooks e MCP):** o Orquestrador mantém `.agents/mcp_config.json` e `.agents/hooks.json` sincronizados com a stack.
- **Bypass Justificado:** pular sub-etapa só se comprovadamente irrelevante (sem tela → sem Designer/UX Reviewer; sem banco → sem DBA), registrando o motivo no `STATE.md`.

---

## Matriz de Agentes x Repertório Autorizado (`.agents/agents/` · skills em `.agents/skills/<nome>/SKILL.md`)

| Agente | Atuação | Repertório de Skills Autorizadas |
| :--- | :--- | :--- |
| `orchestrator` | Coordenador | `context-compressor`, `agent-creator`, `agent-manager-skill` |
| `product_owner` | Etapa 1 | `agile-coach`, `pm-skills`, `copywriting`, `ai-seo` |
| `analyst` | Etapa 1 | `business-rules-expert`, `domain-expert`, `pm-skills`, `gemini-deep-research` |
| `architect` | Etapa 2 | `api-contract-expert`, `springboot-expert`, `fastapi-expert`, `domain-expert`, `springboot-swagger`, `architecture-patterns`, `architect-review`, `cloud-architect`, `framework-migration-legacy-modernize`, `auth-implementation-patterns`, `n8n-deploy`, `gcp-finops-expert` |
| `designer` | Etapa 2 | `uiux-expert`, `animejs-animation`, `image-generator` |
| `dba` | Etapa 2 | `dba-expert`, `springboot-jpa-audit`, `database-architect`, `database-admin` |
| `privacy_officer` | Etapas 2 e 4 + Auxiliar | `lgpd-privacy-expert` |
| `ai_specialist` | Etapas 2 e 3 | `ai-expert`, `rag-expert`, `ml-pipeline-expert`, `deep-learning-cv-expert`, `fastapi-ai-expert`, `mlops-lifecycle-expert`, `gemini-live-api-dev`, `gemini-omni-flash-api`, `hybrid-search-implementation`, `embedding-strategies`, `hugging-face-model-trainer`, `image-generator`, `openai-api-*` (4), `nlp-*` (4), `genai-*` (4), `ga-*` (5), `gcp-finops-expert`, `cloud-architect` |
| `tester` | Etapas 3 e 4 | `springboot-unit-testing`, `angular-expert`, `e2e-testing-patterns` |
| `developer` | Etapa 3 | `angular-expert`, `springboot-expert`, `springboot-dto-mapper`, `springboot-error-handling`, `springboot-security`, `springboot-jpa-audit`, `springboot-swagger`, `fastapi-expert`, `fastapi-ai-expert`, `git-expert`, `fastapi-pro`, `fastapi-router-py`, `async-python-patterns`, `frontend-optimistic-mutations`, `frontend-data-contracts`, `framework-migration-code-migrate`, `auth-implementation-patterns`, `n8n-fundamentos`, `n8n-openai`, `openai-api-fundamentos`, `openai-api-chatbot` |
| `reviewer` | Etapa 4 | `git-expert`, `springboot-dto-mapper`, `springboot-error-handling`, `clean-code-guard`, `code-reviewer` |
| `ux_reviewer` | Etapa 4 | `uiux-expert`, `frontend-lighthouse` |
| `security` | Etapa 4 | `cybersecurity-infra-expert`, `springboot-security`, `lgpd-privacy-expert`, `api-security-best-practices`, `auth-implementation-patterns` |
| `devops` | Etapa 5 | `devops-executive`, `gcp-finops-expert`, `git-expert`, `mlops-lifecycle-expert`, `gcp-cloud-run`, `cloud-devops`, `geminiignore-finops` |
| `finance_advisor` | Auxiliar | `tech-finance-expert`, `gcp-finops-expert` |
| `negotiator` | Auxiliar | `negotiation-stakeholder-expert` |
| `strategic_leader` | Auxiliar | `strategic-tech-leader`, `tech-lead-mentor` |
| `ai_governance_auditor` | Auxiliar | `responsible-ai-governance` |
| `innovation_consultant` | Auxiliar | `tech-innovation-expert`, `pm-skills`, `copywriting`, `ai-seo` |
| `n8n_specialist` | Auxiliar | `n8n-fundamentos`, `n8n-deploy`, `n8n-openai`, `n8n-groq-deepseek`, `n8n-google-slack-telegram-supabase`, `n8n-rag-memory`, `n8n-multi-agents`, `n8n-mcp`, `openai-api-fundamentos` |

> As descrições de cada skill vivem no frontmatter do respectivo `SKILL.md` (gatilho semântico "Use quando..."); não são duplicadas aqui para evitar context bloat.

### Integrações Externas Opcionais (MCP / plugins — usar somente se disponíveis no ambiente)
Não fazem parte de `.agents/skills/`; complementam o repertório acima quando o conector/plugin estiver instalado. Na ausência, o agente segue apenas com as skills do template.

| Agente | Integrações Opcionais |
| :--- | :--- |
| `orchestrator` | `twg-setup` (Atlassian TWG / Jira) |
| `product_owner` | `twg-setup` (Jira: backlog, epics), Mobbin (`search`, `best-practices`), Canva (decks e briefs visuais) |
| `analyst` | `twg-setup` (Jira), Mobbin (benchmark funcional) |
| `architect` | GCP (`gcloud`, `finding-google-skills`), Supabase (`supabase`, `supabase-postgres-best-practices`) |
| `designer` | Figma MCP & Skills (`figma-generate-design`, `figma-create-new-file`, `figma-spec`, `figma-use-figjam`, `figma-shaders`, `figma-implement-motion`), Canva MCP & Skills (`edit-design`, `brand-check`, `bulk-create`, `get-design-feedback`, `resize-for-social-media`), Mobbin (`search`, `redesign-screen`, `best-practices`), Stitch MCP |
| `dba` | Supabase MCP & Skills (migrations, RLS, indexes), Postgres MCP (`query`) |
| `tester` | Chrome DevTools MCP (`a11y-debugging`, `troubleshooting`, `memory-leak-debugging`) |
| `developer` | Figma to Code (`figma-design-to-code`, `figma-code-connect`), Supabase (SDK client, types TypeScript, Edge Functions) |
| `ux_reviewer` | Figma MCP (`get_design_context`, `get_screenshot`), Mobbin (`best-practices`), Chrome DevTools (`a11y-debugging`) |
| `security` | Supabase Security (`get_advisors`, `query_logs`) |
| `devops` | GCP (`gcloud`, `google-cloud-recipe-auth`), Supabase Deploy (`apply_migration`, `deploy_edge_function`) |
| `innovation_consultant` | Canva MCP |

---

## Slash Commands (Atalhos Nativos via `.agents/skills/<nome>/`)
- `/orquestrador`, `/orquestrar`, `/o` — esteira completa de 5 Macro-Etapas ou despacho de auxiliares · `/init` — kickoff/fundação do projeto.
- Pipeline: `/po`, `/analyst`, `/architect`, `/designer`, `/dba`, `/developer`, `/reviewer`, `/tester`, `/security`, `/devops`, `/ai_specialist`, `/privacy`.
- Auxiliares: `/finance`, `/negotiator`, `/leader`, `/responsible_ai`, `/innovation`, `/n8n`.
