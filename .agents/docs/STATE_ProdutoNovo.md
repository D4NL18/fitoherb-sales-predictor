# Estado da Feature: Viabilidade de Produto Novo (`feature/analytics-produto-novo`)

> **Arquivo de Estado Exclusivo:** `.agents/docs/STATE_ProdutoNovo.md`  
> **Branch:** `feature/analytics-produto-novo`  
> **Orquestrador de Feature:** FASE F2 (Viabilidade de produto novo - conservadora)  
> **Faixa Exclusiva de Regras:** `P-139` a `P-149` (prefixo `NEW-XXX`)  
> **Status Geral:** Etapa 1 CONCLUÍDA | Etapa 2 EM ANDAMENTO

---

## 1. Triagem Prévia de Escopo e Decisão de Roteamento

- **Classificação:** Categoria A / T1 (Feature Completa com Backend e Frontend).
- **Escopo Confinado:** Execução delimitada EXCLUSIVAMENTE até o Checkpoint da Etapa 2 (Arquitetura, Modelagem e Design).
- **Etapa 3 e 4:** Bloqueadas por dependência de interface da Fase F1 (Índice de Sazonalidade).
- **Matriz de Bypass Justificado:**
  - `dba`: **BYPASS APROVADO** — Operação 100% somente leitura sobre views e tabelas pré-existentes (`Externo01.Vendas`, `Externo01.Produto`). Sem migrations, sem criação de tabelas.
  - `privacy_officer`: **PARECER FORMAL DE ISENÇÃO** — A funcionalidade avalia atributos genéricos de produtos e agregados estatísticos; não coleta, não processa e não expõe nenhum dado de cliente (sem PII).

---

## 2. Log de Execução por Macro-Etapa

### ETAPA 1 — Descoberta, Escopo e Especificação
- **Papel:** Analista de Requisitos (`analyst.md` / `business-rules-expert`)
- **Ações Realizadas:**
  - Mapeamento completo das regras `P-139` a `P-149` em `.agents/docs/business_rules/analytics-produto-novo.md`.
  - Incorporação das decisões fundamentais do usuário: D2 (produto hipotético sem SKU) e D4 (abatimento de devoluções nos similares).
  - Formalização do critério temporal de Lançamento Real (`LAUNCH_CUTOFF_DATE = '2025-04-01'` e $\ge 3$ meses de histórico).
  - Estruturação do backlog de tarefas e critérios de aceitação em `.agents/docs/tasks/analytics-produto-novo.md`.
- **Status:** **CONCLUÍDO**

### ETAPA 2 — Arquitetura, Modelagem Segura e Design Plan
- **Papéis:**
  - `architect`: Elaboração do `ADR-008-produto-novo.md` e do contrato REST `api_contracts/analytics-produto-novo.md`.
  - `ai_specialist`: Modelagem matemática do score híbrido (TF-IDF + Fornecedor + Log-Preço) e calibração do Haircut conservador (P25 $\times$ 0.70) com meta $\ge 80\%$ de acerto no backtest.
  - `designer`: Elaboração do Design Plan em `.agents/docs/design/plans/analytics-produto-novo.md` com os 8 estados interativos e filtro Anti-IA.
  - `dba`: Bypass confirmado.
  - `privacy_officer`: Emissão de parecer formal em `.agents/docs/privacy/analytics-produto-novo.md`.
- **Status:** **EM ANDAMENTO**
