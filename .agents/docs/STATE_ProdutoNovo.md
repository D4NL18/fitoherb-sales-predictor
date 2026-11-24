# Estado da Feature: Viabilidade de Produto Novo (`feature/analytics-produto-novo`)

> **Arquivo de Estado Exclusivo:** `.agents/docs/STATE_ProdutoNovo.md`  
> **Branch:** `feature/analytics-produto-novo`  
> **Orquestrador de Feature:** FASE F2 (Viabilidade de produto novo - conservadora)  
> **Faixa Exclusiva de Regras:** `P-139` a `P-149` (prefixo `NEW-XXX`)  
> **Status Geral:** ETAPA 3 E ETAPA 4 CONCLUÍDAS — APROVADO NO QUALITY GATE 360 (`370/370` pytest · `34/34` Karma F2 · `ng build` OK)

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

## 3. Log de Execução — Etapas 3 e 4 (Desenvolvimento e Quality Gate 360)

### ETAPA 3 — TDD e Execução (`tester` + `developer` + `ai_specialist`)
- **Merge prévio:** `main` mesclada em `feature/analytics-produto-novo` trazendo F1 Sazonalidade (`get_seasonality_index`), F3 Churn, F5 Elasticidade e Tendência de Vendas.
- **TDD First (`tester`):** 29 testes criados em `tests/analytics/test_new_product_domain.py`, `test_new_product_repository.py` e `test_new_product_api.py` (fase Red validada).
- **Backend + AI (`developer` + `ai_specialist`):** implementado domínio `src/modules/analytics/domain/new_product.py`, exceções `NEW-001`..`NEW-005` (`exceptions.py`), consultas somente-leitura (`sales_repository.py`), cache 6h com lock (`analytics_cache.py`), integração F1 com fallback neutro (`analytics_service.py`), schemas `camelCase` (`schemas.py`), error handlers e rotas (`/analytics/new-product/options` e `/forecast`).
  - **Resultado `pytest tests/analytics/`:** `370 passed, 1 warning in 42.88s`.
- **Frontend Angular 18 (`developer`):** implementada rota `/analytics/produto-novo` (`NewProductStore`, `NewProductFormComponent`, `NewProductBandChartComponent`, `NewProductResultsComponent`, `NewProductSimilarsDrawerComponent`), seguindo Design Plan Papel & Tinta, 8 estados e Focus Trap.
  - **Resultado Karma F2:** `34 SUCCESS` (0 falhas).
  - **Resultado `ng build`:** limpo (chunk lazy `83.63 kB`).

### ETAPA 4 — Quality Gate 360 (`reviewer` + `ux_reviewer`)
- **`reviewer`:** **APROVADO** — Clean Code, SOLID, LGPD-05 (sem eco de valores/stacktraces), `is_readonly_query`, invariante `Q <= P25`, `OnPush`, `switchMap` + `takeUntilDestroyed()`, zero `any`.
- **`ux_reviewer`:** **APROVADO** — Fidelidade integral ao Design Plan Papel & Tinta, WCAG 2.1 AA, gráfico SVG colorblind-safe + tabela ledger, bloco `Teto Maduro (P75)` segregado, Drawer acessível com `[attr.inert]` e restauração de foco, responsividade `< 640px`.
- **Status:** **CONCLUÍDO E APROVADO**


---

## 4. Integração com Motor Compartilhado de Afinidade Semântica (Merge `main` / PR #13)

- **Triagem (`/o`):** Categoria A (Evolução de Feature Backend + Frontend). Bypass justificado para `product_owner`, `analyst`, `dba`, `privacy_officer` (sem PII) e `designer` (mantém Papel & Tinta).
- **Merge `origin/main` (`76759bb`):** incorporados Canibalização (F6) + Índice de Afinidade Semântica (`product_affinity.py` e `product_affinity_service.py`), resolvendo os 10 conflitos aditivos de rotas/schemas/exceções/utilitários.
- **Reutilização sem duplicação de NLP/TF-IDF:**
  - `src/modules/analytics/service/product_affinity_service.py`: `find_similar_for_new_product(...)` agora aplica `detect_primary_function` + `build_sku_compatibility_profile` + `_pair_compatibility_multiplier` sobre o produto candidato novo vs catálogo ativo, com `auto_sync=True` / fallback gracioso quando o índice em disco ainda não existir.
  - `src/modules/analytics/domain/new_product.py`: removida toda lógica duplicada de TF-IDF/stopwords; adicionados `select_similars_from_affinities`, percentis conservadores ponderados por `affinityScore` (mantendo trava `Q <= P25`), `compute_reference_price_range` e `compute_cannibalization_risk`.
  - `src/modules/analytics/service/analytics_service.py` & `schemas.py`: `POST /api/v1/analytics/new-product/forecast` consome `product_affinity_service.find_similar_for_new_product(...)` e retorna `referencePriceRange`, `cannibalizationRisk` e `affinityScore` por item de referência.
  - **Frontend Angular 18:** exibe Faixa de Preço de Referência, Risco de Canibalização no Portfólio (mesmo fornecedor vs outros fornecedores) e coluna `Afinidade` (%) na tabela de Produtos de Referência e no Drawer de explicabilidade.
