# STATE — FASE F6: Canibalização e Substituição (Orquestrador de Feature)

| Campo | Valor |
| :--- | :--- |
| **Feature** | F6: Canibalização e Substituição (`analytics-canibalizacao`) |
| **Branch** | `feature/analytics-canibalizacao` |
| **Worktree** | `C:\Users\danie\Documents\Github\fitoherb-analytics-canibalizacao` |
| **Faixa de Regras** | `P-128` a `P-138` |
| **Prefixo de Erros** | `CAN-XXX` (`CAN-001` a `CAN-005`) |
| **Etapa Atual** | Etapa 4 Concluída (v2 — Relatório de Canibalização por Migração de Clientes e Equilíbrio de Preço) |
| **Status** | **V2 IMPLEMENTADA E APROVADA NO QUALITY GATE 360** — Backend (`427 passed`), Frontend (`22 SUCCESS`, `ng build` OK), `reviewer`, `privacy_officer` e `ux_reviewer` **APROVADOS** |
| **Bypasses Homologados** | **DBA** (somente leitura de agregados SQL Server existentes, sem migrations); **Privacy Officer** (revisão de minimização e Privacy by Design com bypass formal de RIPD completo homologado) |

---

## 1. Escopo e Diretrizes da Feature F6

- **Objetivo Central:** Identificar se uma ação sobre um SKU alvo (início de promoção `promo`, variação de preço `price` ou novo lançamento `launch`) provocou perda de volume em itens substitutos (`CANIBALIZACAO`), ganho conjunto (`COMPLEMENTO`) ou se o efeito é indistinguível de ruído (`SEM_EFEITO`), quantificando o **efeito líquido** em volume, receita e margem de contribuição.
- **Conexão com F5 (Elasticidade):** A arquitetura e contratos desenham a interface `CrossElasticityProvider` com a futura F5 para decompor a parcela da variação explicada por elasticidade cruzada $\epsilon_{ji} \times \Delta P_i$. A implementação de código (Etapas 3 e 4) fica suspensa até a entrega de F5.

---

## 2. Documentação Técnica Gerada na Esteira

| Documento | Localização Mandatória | Papel Responsável | Status |
| :--- | :--- | :--- | :--- |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-canibalizacao.md` | `analyst` | P-128 a P-138 formalizadas |
| **Tarefas e DoD** | `.agents/docs/tasks/analytics-canibalizacao.md` | `analyst` / `architect` / `ux_reviewer` | Tarefas 1 a 7 alinhadas aos componentes compartilhados e tokens reais |
| **Decisão de Arquitetura** | `.agents/docs/adr/ADR-007-canibalizacao.md` | `architect` / `ai_specialist` | DA-01 a DA-08 aprovadas |
| **Contrato de API REST** | `.agents/docs/api_contracts/analytics-canibalizacao.md` | `architect` | Rotas `/cannibalization/{sku}` e `/substitution/{sku}`, `timelineSeries`, `meta.dataReferencia`, `error.fields[]` (`CAN-001..005`, `ANL-001`) |
| **Design Plan UI/UX** | `.agents/docs/design/plans/analytics-canibalizacao.md` | `designer` / `ux_reviewer` | Revisado: tokens reais Papel & Tinta (`styles.scss`), contraste `.tag-*`, reuso `features/analytics/`, acessibilidade, mobile `<640px`, 8 estados e diretrizes Etapa 3 |
| **Parecer de Privacidade** | `.agents/docs/privacy/analytics-canibalizacao.md` | `privacy_officer` | Bypass de RIPD e regras LGPD-CAN-01..08 |

---

## 3. Log de Progresso da Esteira

- **2026-11-12 (Início):** Inicialização do orquestrador de feature isolado em worktree própria.
- **2026-11-12 (Etapa 1 - analyst):** Mapeamento de P-128 a P-138 em `.agents/docs/business_rules/analytics-canibalizacao.md` e planejamento técnico em `.agents/docs/tasks/analytics-canibalizacao.md`. Commit atômico `a8646f7`.
- **2026-11-12 (Etapa 2 - architect / ai_specialist):** Elaboração da `ADR-007-canibalizacao.md` detalhando modelo de Diferença em Diferenças, FDR Benjamini-Hochberg, agregação SQL sem OOM e contrato desacoplado de elasticidade F5.
- **2026-11-12 (Etapa 2 - architect):** Formalização do contrato de API em `.agents/docs/api_contracts/analytics-canibalizacao.md` com endpoints `/cannibalization/{sku}` e `/substitution/{sku}`.
- **2026-11-12 (Etapa 2 - designer):** Criação do Design Plan em `.agents/docs/design/plans/analytics-canibalizacao.md` cobrindo linha do tempo interativa, card de efeito líquido e os 8 estados visuais obrigatórios.
- **2026-11-12 (Etapa 2 - dba):** Homologação de BYPASS TOTAL de banco de dados (leitura pura em views existentes).
- **2026-11-12 (Etapa 2 - privacy_officer):** Emissão de parecer em `.agents/docs/privacy/analytics-canibalizacao.md` com bypass formal de RIPD e exigência de salvaguardas de minimização.
- **2026-11-12 (Etapa 2 - Revisão UX/UI Sênior):** Auditoria completa do Design Plan contra `frontend/src/styles.scss`, `_analytics-ui.scss`, componentes compartilhados de `features/analytics/` e contrato REST: correção dos tokens Papel & Tinta e contraste AA de `--feedback-*-bg` (`.tag-*` com texto branco vs banners `--bg-surface` + borda esquerda `3px`), reuso explícito de `AnalyticsShell`/`CodeSearchForm`/`ModeSwitch`/`QueryContextHeader`/`ErrorBanner`/`ResultState`/`ListPager`, adição de `timelineSeries`, `priceDirection`, `isExpandedControl`, `costFallbackUsed`, `MIGRACAO_POSITIVA`, `meta.dataReferencia` e `error.fields[]` no contrato, especificação de tabela acessível da linha do tempo, foco/trap do drawer, cards mobile `< 640px`, degradação graciosa de F5 (`NAO_INTEGRADO`), 8 estados com skeleton solid-pulse + aviso 4s e diretrizes Angular 18 (`OnPush`, `switchMap` + `takeUntilDestroyed`, URL sync sanitizado, zero `any`).
- **2026-11-12 (Etapa 2 - Checkpoint):** Congelamento e parada mandatória. Não avançar para Etapa 3.
- **2026-11-17 (Pull `main`):** Merge de `origin/main` trazendo F1 (Sazonalidade), F3 (Churn), F5 (Elasticidade) e Tendência de Vendas.
- **2026-11-17 (Etapa 3 - TDD First & Implementação):** Criação das suítes TDD Backend (`test_substitution_candidates.py`, `test_cannibalization_domain.py`, `test_cannibalization_api.py`) e Frontend (`cannibalization.service.spec.ts`, `cannibalization-page.component.spec.ts`); implementação completa do domínio DiD/Jaccard/FDR/Financeiro, endpoints `/analytics/cannibalization/{sku}` e `/analytics/substitution/{sku}` (`392 passed` em `tests/analytics/`) e interface Angular (`Canibalização` em `AnalyticsShellComponent` + `NetImpactCard` + Timeline SVG + Drawer acessível).
- **2026-11-17 (Etapa 4 - Quality Gate 360):** `reviewer` (**APROVADO**), `privacy_officer` (**APROVADO** — zero `Cod Cliente` em DTOs/cache/logs, erros `CAN-004`/`ANL-001` sanitizados) e `ux_reviewer` (**APROVADO** — tokens Papel & Tinta, 8 estados, acessibilidade e mobile `< 640px`).
- **2026-11-23 (Pivô v2 — Etapas 1 e 2):** Novo escopo validado com o usuário (Relatório global de produtos canibalizados por migração direcional líquida de clientes em `30d/60d/90d`, medido em `%` e `R$` de faturamento reduzido + sugestão de equilíbrio de preço). Bypasses homologados: `product_owner` (feature já fatiada), `dba` (leitura pura), `security` dedicado (sem auth/cripto). Documentação v2 atualizada em `.agents/docs/` (`business_rules`, `adr`, `api_contracts`, `design/plans`, `tasks`). Aguardando validação do Checkpoint para Etapa 3.
- **2026-11-23 (Pivô v2 — Etapas 3 e 4):** TDD First + implementação completa de `cannibalization_report.py`, `_CLIENT_PERIOD_MIGRATION_SQL`, `/analytics/cannibalization/report` e `/report/{sku}` (`427 passed`) e nova UI Angular (`Relatório de Canibalização e Equilíbrio de Preço`, `PriceEquilibriumDrawerComponent`, `22 SUCCESS` + `ng build` limpo). Quality Gate 360: `reviewer`, `privacy_officer` e `ux_reviewer` **APROVADOS**.
