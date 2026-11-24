# Checklist Técnico: Analytics Comercial — F6 Canibalização por Migração de Clientes e Equilíbrio de Preço (v2)

> **Localização Mandatória:** `.agents/docs/tasks/analytics-canibalizacao.md`  
> **Branch:** `feature/analytics-canibalizacao`  
> **Referências:** `business_rules/analytics-canibalizacao.md` (`P-128..P-138`), `ADR-007-canibalizacao.md`, `api_contracts/analytics-canibalizacao.md` (`v1.1.0`), `privacy/analytics-canibalizacao.md` (`LGPD-CAN-01..08`)

---

## 1. Decisões Consolidadas do Pivô v2

1. **Modelo Analítico:** Substitui o fluxo DiD isolado por evento pela **Migração Direcional Líquida de Clientes** dentro da mesma categoria (`Tipo`), comparando `CUR` (últimos $N$ dias) vs `PRE` ($N$ dias anteriores) com $N \in \{30, 60, 90\}$ (padrão `90`).
2. **Qualidade do Sinal:** Fluxo conservativo sem dupla contagem por cliente, desconto do fluxo reverso (`net = max(0, gross(A->B) - gross(B->A))`), mínimo de 3 clientes migrando (`minMigratedClients = 3`), queda mínima de 5% (`minDropPct = 5.0`) e faturamento prévio $\ge$ R$ 500.
3. **Equilíbrio de Preço:** Classificação em `PRECO_MENOR_DESTROI_MARGEM`, `PRECO_MENOR_MARGEM_PRESERVADA` ou `MIGRACAO_POR_VALOR` e cálculo determinístico de `suggestedVictimPrice` e `suggestedCannibalPrice` para reduzir o gap em ~40% preservando margem mínima de contribuição de 20% (e teto de +12% no canibalizador).
4. **SQL & LGPD:** Subquery iniciando com `SELECT` (sem `WITH`, sem `CONCAT`, bind params `?`), abatimento de devoluções (`LIKE 'DEVOLU%'`), leitura em blocos (`fetchmany(50_000)`) e descarte explícito `del by_cli` antes do cache (zero `Cod Cliente` em DTOs/cache/logs).

---

## 2. Checklist Backend (`src/modules/analytics/`)

### Tarefa B1: Repositório SQL Somente Leitura (`repository/sales_repository.py`)
- [ ] **B1.1:** Implementar `fetch_customer_sku_window_sales(pre_start_date, mid_date, reference_date)` usando subquery `SELECT ... FROM (SELECT ...) AS base GROUP BY ...` (sem `WITH`, sem `CONCAT`, com bind params `?`).
- [ ] **B1.2:** Garantir filtro `([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%')` e validação obrigatória por `is_readonly_query`.
- [ ] **B1.3:** Selecionar estritamente `[Cod Cliente]`, `[Cod Produto]`, `[Qtd Venda]`, `[Valor Venda]` (LGPD-CAN-01) e iterar via `cursor.fetchmany(FETCH_CHUNK_SIZE)`.
- [ ] **B1.4:** Reutilizar `fetch_cannibalization_catalog()` com `Codigo`, `Descricao`, `Tipo`, `Fornecedor`, `Estoque`, `Pc.Ultimo Custo`, `Pc.Venda`.

### Tarefa B2: Motor de Domínio v2 (`domain/cannibalization.py`)
- [ ] **B2.1:** Declarar todas as constantes da tabela de `P-128..P-137` no topo do módulo (zero números mágicos).
- [ ] **B2.2:** Implementar agregação por cliente na mesma categoria (`Tipo`) com conservação de fluxo $M_c(A \to B) = F_{c,T} \cdot \frac{L_{c,A}}{L_{c,T}} \cdot \frac{G_{c,B}}{G_{c,T}}$ (`P-130`) e executar `del by_cli` imediatamente após consolidar os pares (`LGPD-CAN-04`).
- [ ] **B2.3:** Implementar desconto de fluxo reverso (`net_rev`, `net_clients`) (`P-131`) e quantificação de `cannibalizedRevenue`, `cannibalizedRevenuePct` e `dropExplainedPct` (`P-132`).
- [ ] **B2.4:** Implementar cálculo de preço de referência, `priceGapPct`, margem unitária com fallback 60% (`costFallbackUsed`) e `netMarginImpact` (`P-133`).
- [ ] **B2.5:** Implementar classificador de mecanismo (`PRECO_MENOR_DESTROI_MARGEM`, `PRECO_MENOR_MARGEM_PRESERVADA`, `MIGRACAO_POR_VALOR`) (`P-134`).
- [ ] **B2.6:** Implementar motor de equilíbrio de preço (`suggestedVictimPrice`, `suggestedCannibalPrice`, `projectedPriceGapPct`, `victimMarginFloorPrice`, `actionSummary`) respeitando piso de 20% na vítima e teto de +12% no canibalizador (`P-135`).
- [ ] **B2.7:** Implementar builder do relatório global (KPIs, `availableCategories`, `availableSuppliers`, filtros e ordenação por `cannibalizedRevenue` desc) e builder de detalhe por SKU (`P-136`).

### Tarefa B3: Serviço, Cache e Camada de API (`service/`, `api/`)
- [ ] **B3.1:** Atualizar `AnalyticsService` para cachear o snapshot agregado (sem `by_cli`) no `AnalyticsCache` com TTL de 6h por `(windowDays, referenceDate)` e `asyncio.Lock` (`P-137.2`).
- [ ] **B3.2:** Aplicar `minDropPct`, `minMigratedClients` e filtros (`category`, `supplier`, `mechanism`, `search`) em memória sobre o snapshot cacheado.
- [ ] **B3.3:** Atualizar `api/schemas.py` e `api/mappers.py` com DTOs v2 estritamente em `camelCase` e `meta.version = "1.1.0"`.
- [ ] **B3.4:** Expor `GET /api/v1/analytics/cannibalization/report` e `GET /api/v1/analytics/cannibalization/report/{sku}` em `api/router.py` com validação de query/path params (`CAN-004`), 404 (`CAN-001`), 422 (`CAN-003`), 500 (`CAN-005`) e 503 (`ANL-001`).

### Tarefa B4: Testes Automatizados Backend (`tests/analytics/`)
- [ ] **B4.1 (Domínio):** Testes unitários de migração direcional líquida (fluxo unidirecional, fluxo reverso simétrico anulado, conservação de fluxo com múltiplos B's sem dupla contagem, corte `minMigratedClients` e `MIN_PRE_REVENUE`).
- [ ] **B4.2 (Equilíbrio de Preço):** Testes dos 3 mecanismos (`PRECO_MENOR_DESTROI_MARGEM`, `PRECO_MENOR_MARGEM_PRESERVADA`, `MIGRACAO_POR_VALOR`), fallback de custo 60%, piso de margem 20% e teto de +12%.
- [ ] **B4.3 (SQL & LGPD):** Teste garantindo `is_readonly_query(sql) == True`, ausência de `WITH`/`CONCAT`, ausência de `Cod Cliente` no objeto cacheado e nas respostas HTTP.
- [ ] **B4.4 (API Contract):** Testes `TestClient(app)` cobrindo `/report`, `/report/{sku}`, filtros, `200 OK` sem canibalização (`isCannibalized: false`), `400 CAN-004`, `404 CAN-001`, `422 CAN-003`, `503 ANL-001` e `meta.version == "1.1.0"`.

---

## 3. Checklist Frontend (`frontend/src/app/features/analytics/`)

### Tarefa F1: Modelos e Serviço HTTP
- [ ] **F1.1:** Atualizar interfaces TypeScript para o contrato v2 (`CannibalizationReportResponse`, `CannibalizationVictimSummary`, `CannibalizerDetail`, `CannibalizationDetailResponse`, `CannibalizationMechanism`) sem uso de `any`.
- [ ] **F1.2:** Atualizar `AnalyticsApiService` para consumir `GET /api/v1/analytics/cannibalization/report` e `GET /api/v1/analytics/cannibalization/report/{sku}` com `switchMap` + `takeUntilDestroyed`.

### Tarefa F2: Interface do Relatório Global e Drawer de Equilíbrio de Preço
- [ ] **F2.1:** Implementar seletor de janela `windowDays` (`30d`, `60d`, `90d` padrão) e barra de filtros (`category`, `supplier`, `mechanism`, `search`, `minDropPct`, `minMigratedClients`) sincronizados na URL.
- [ ] **F2.2:** Implementar cards de KPIs globais (Total de Vítimas, Faturamento Canibalizado R$, % Médio Canibalizado, Impacto Líquido de Margem R$, Pares Destruindo Margem).
- [ ] **F2.3:** Implementar tabela/cards responsivos de vítimas exibindo `%` e `R$` canibalizados, faturamento `PRE` vs `CUR`, preço, margem (badge se `costFallbackUsed`), nº de canibalizadores e preview do `topCannibal` com badge acessível de mecanismo (cor + ícone + rótulo).
- [ ] **F2.4:** Implementar Drawer/Painel de detalhe (`role="dialog" aria-modal="true"`) consumindo `/report/{sku}` com tabela de canibalizadores, comparativo de preço/margem (`P_A` vs `P_B`, `priceGapPct`), preços sugeridos de equilíbrio (`suggestedVictimPrice`, `suggestedCannibalPrice`, `projectedPriceGapPct`) e `actionSummary`.
- [ ] **F2.5:** Garantir cobertura dos 8 estados interativos (incluindo Skeleton solid-pulse + aviso de 4s para cold cache, Empty State quando sem vítimas e ErrorBanner para `CAN-001/003/004/005` + `ANL-001`) e `ChangeDetectionStrategy.OnPush`.

### Tarefa F3: Testes Frontend & Build
- [ ] **F3.1:** Atualizar testes unitários (Karma/Jasmine ou Vitest) da página e do serviço de canibalização v2.
- [ ] **F3.2:** Validar `ng build` limpo e conformidade visual com os tokens Papel & Tinta (`styles/_analytics-ui.scss`).
