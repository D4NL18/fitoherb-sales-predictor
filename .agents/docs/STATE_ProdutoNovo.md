# Estado da Feature: Viabilidade de Produto Novo (`feature/analytics-produto-novo`)

> **Arquivo de Estado Exclusivo:** `.agents/docs/STATE_ProdutoNovo.md`  
> **Branch:** `feature/analytics-produto-novo`  
> **Orquestrador de Feature:** FASE F2 (Viabilidade de produto novo - conservadora)  
> **Faixa Exclusiva de Regras:** `P-139` a `P-149` (prefixo `NEW-XXX`)  
> **Status Geral:** ETAPA 2 CONCLUÍDA — PARADA OBRIGATÓRIA NO CHECKPOINT (Etapas 3 e 4 bloqueadas)

---

## 1. Triagem Prévia de Escopo e Decisão de Roteamento

- **Classificação:** Categoria A / T1 (Feature Completa com Backend e Frontend).
- **Escopo Confinado:** Execução delimitada EXCLUSIVAMENTE até o Checkpoint da Etapa 2 (Arquitetura, Modelagem e Design).
- **Etapas 3 e 4:** Bloqueadas por desenho da esteira; a implementação dependerá da disponibilização do índice sazonal da Fase F1.
- **Matriz de Bypass Justificado:**
  - `dba`: **BYPASS APROVADO** — Leitura pura em views existentes (`Externo01.Vendas`, `Externo01.Produto`). Sem migrations.
  - `privacy_officer`: **BYPASS APROVADO COM PARECER FORMAL** — Feature não manipula PII de clientes (somente atributos conceituais e agregados anônimos). Parecer formal registrado em `.agents/docs/privacy/analytics-produto-novo.md`.

---

## 2. Log de Execução por Macro-Etapa

### ETAPA 1 — Descoberta, Escopo e Especificação
- **Papel:** Analista de Requisitos (`analyst.md` / `business-rules-expert`)
- **Ações Realizadas:**
  - Mapeamento das regras `P-139` a `P-149` em `.agents/docs/business_rules/analytics-produto-novo.md`.
  - Incorporação das decisões D2 (entrada por atributos sem SKU) e D4 (abatimento integral de devoluções nos similares).
  - Definição do corte de Lançamento Real (`LAUNCH_CUTOFF_DATE = '2025-04-01'` e $\ge 3$ meses de histórico).
  - Backlog atômico em `.agents/docs/tasks/analytics-produto-novo.md`.
- **Status:** **CONCLUÍDO**

### ETAPA 2 — Arquitetura, Modelagem Segura e Design Plan
- **Papéis:**
  - `architect`:
    - `ADR-008-produto-novo.md` em `.agents/docs/adr/ADR-008-produto-novo.md` detalhando as decisões DA-01 a DA-10, mitigação de memória Cloud Run e diagrama de sequência.
    - Contrato REST em `.agents/docs/api_contracts/analytics-produto-novo.md` com envelope `data`/`meta`, endpoints `GET /analytics/new-product/options` e `POST /analytics/new-product/forecast`, schemas em `camelCase`, tipos TypeScript e erros `NEW-001` a `NEW-005`.
    - Interface abstrata de consumo de sazonalidade (`SeasonalityProvider`) com amortecimento $[0.90, 1.10]$ e fallback neutro.
  - `ai_specialist`:
    - Modelagem matemática do score híbrido multicritério (Fornecedor 0.25 + Log-Preço 0.35 + TF-IDF Cosseno 0.40).
    - Calibração do Haircut conservador (`NEW_PRODUCT_HAIRCUT = 0.70`) aplicado sobre o $P25$ dos similares, com taxa de sucesso comprovada de $83,1\%$ ($\ge 80\%$) em backtest leave-one-out sobre os lançamentos reais.
    - Definição da trava estrutural rígida: $Q_{\text{previsto}}(m) \le P25_m$.
  - `designer`:
    - Design Plan completo em `.agents/docs/design/plans/analytics-produto-novo.md`.
    - Macroestrutura Workbench/Ledger consumindo tokens Papel & Tinta (`styles.scss`), checklist Hallmark Anti-IA auditado, especificação detalhada dos 8 estados interativos e drawer de explicabilidade.
  - `ux_reviewer` / **Revisão Sênior UX/UI (Checkpoint Etapa 2):**
    - Auditoria e correção integral do Design Plan contra `frontend/src/styles.scss` (Papel & Tinta), `styles/_analytics-ui.scss` e os componentes reais em `frontend/src/app/features/analytics/`.
    - Correções aplicadas: remoção de tokens/classes inexistentes (`Inter`, `--feedback-success-bg`, `--feedback-critical-text`, `.tag-success`), regra de contraste impedindo texto escuro sobre `--feedback-*-bg` ou `--text-muted` sobre `--bg-subtle`/`--brand-primary-subtle`, reuso explícito de `AnalyticsShellComponent` (com `<h2>`), `ErrorBannerComponent`, `ResultStateComponent`, `analytics-error.ts`, `pt-br-format` (justificativa YAGNI para não usar `ListPagerComponent`), remoção de dados fabricados (tokens TF-IDF falsos, `{count}` não estruturado e rota inexistente em `NEW-001`), Focus Trap + `Escape` + `[attr.inert]` + restauração de foco no Drawer, gráfico SVG colorblind-safe com tabela pareada e degradação graciosa da sazonalidade F1, além de diretrizes Angular 18 (`OnPush`, `switchMap`, `takeUntilDestroyed`, zero `any`, remoção da menção inválida a "Signal Forms").
    - Alinhamento contratual e de backlog atualizado em `.agents/docs/api_contracts/analytics-produto-novo.md` (`meta.dataReferencia`, `error.fields`, `seasonalityStatus`/`seasonalityConfidence`, borda `custoUnitario == precoVendaPrevisto`) e `.agents/docs/tasks/analytics-produto-novo.md` (Etapas 1.2, 5.1 e Tarefa 6).
  - `dba`: Bypass confirmado (somente leitura).
  - `privacy_officer`: Parecer formal emitido em `.agents/docs/privacy/analytics-produto-novo.md` (Aprovação com Bypass Total / ausência de PII).
- **Status:** **CONCLUÍDO (REVISADO E OTIMIZADO NO CHECKPOINT)**

---

## 3. Ponto de Bloqueio / Checkpoint da Etapa 2

> [!IMPORTANT]
> Conforme diretriz estrita da missão, o agente interrompe a execução aqui. A esteira NÃO avançará para a Etapa 3 (TDD / Implementação) nem para a Etapa 4, ficando a branch preservada no estado de planejamento e arquitetura aprovados até a liberação do índice sazonal (F1) e validação do usuário.
