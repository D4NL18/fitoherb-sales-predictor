---
name: init
description: "Kickoff de novo projeto - Brainstorming Global com Arquiteto, DBA, Designer, PO e DevOps para gerar DESIGN_SYSTEM.md, GLOSSARY.md, ARCHITECTURE.md e ROADMAP.md em .agents/docs/."
---

# Execucao do Workflow /init (Fundacao do Projeto)

1. Leia imediatamente @.agents/agents/orchestrator.md, @AGENTS.md e @.agents/docs/STATE.md. Assuma o papel de Orquestrador.
2. **Brainstorming Global com o usuario** (perguntas objetivas sobre produto, publico, stack, dados, IA e restricoes de custo/LGPD). Invoque via `invoke_subagent`:
   - `architect` -> consolida `.agents/docs/architecture/ARCHITECTURE.md` e ADRs iniciais em `.agents/docs/adr/`.
   - `dba` -> define a estrategia de dados (SGBD, padroes de migration, LGPD) e documenta em `.agents/docs/db/`.
   - `designer` (se houver Frontend) -> gera `.agents/docs/design/DESIGN_SYSTEM.md` a partir de `.agents/docs/design/TEMPLATE_DESIGN_SYSTEM.md`, com filtro Anti-IA.
   - `analyst` (skill `domain-expert`) -> inicia `.agents/docs/GLOSSARY.md` com a linguagem ubiqua.
3. Invoque `product_owner` para fatiar o backlog inicial em User Stories INVEST em `.agents/docs/ROADMAP.md`, marcando `[PARALLEL]`.
4. Invoque `devops` para a fundacao do repositorio (estrutura, CI/CD base, Docker multi-stage, FinOps) e sincronize `.agents/hooks.json` e `.agents/mcp_config.json` com a stack escolhida.
5. **Planejamento obrigatorio de Branches e CI/CD** (sempre, em todo kickoff): `devops` (com `architect` e skill `git-expert`) elabora o plano e o documenta em `.agents/docs/architecture/BRANCHING_CICD.md` (decisao formal em ADR em `.agents/docs/adr/`), contendo:
   - **Branches de ambiente permanentes:** `develop` (integracao/dev), `qa` (homologacao) e `prod` (producao; opcionalmente espelhada em `main`), com o fluxo de promocao `feature/* -> develop -> qa -> prod` e hotfix `hotfix/* -> prod` com back-merge para `qa` e `develop`.
   - **Protecao de branches:** fluxo via PR (sem exigir aprovacao/review humano, pois o projeto e solo: 0 approvals obrigatorios e o autor pode fazer merge do proprio PR), status checks de CI obrigatorios antes do merge, proibicao de force-push e delecao (mais rigor em `qa` e `prod`), Conventional Commits.
   - **Pipelines CI/CD por ambiente:** CI (lint, testes, build, SAST/scan de secrets) em todo PR; CD automatico `develop -> ambiente dev`, `qa -> ambiente QA` (com testes E2E/contrato) e `prod -> producao` (aprovacao manual, versionamento/tag semantica, rollback).
   - **Ambientes e secrets:** separacao de secrets/variaveis por ambiente, estrategia de banco/migrations por ambiente e diretrizes FinOps (Scale-to-Zero em dev/qa).
   - **Checklist de execucao:** tarefas atomicas em `.agents/docs/tasks/` para criar as branches, configurar protecoes e implementar os workflows. As branches so sao criadas apos confirmacao do usuario.
6. Atualize `.agents/docs/STATE.md` com o resumo do kickoff e apresente ao usuario os artefatos gerados. Nenhum arquivo de documentacao pode ser salvo na raiz do repositorio.
