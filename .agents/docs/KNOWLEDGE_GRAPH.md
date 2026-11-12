# Knowledge Graph — Memória Consolidada do Projeto (`context-compressor`)

## Módulo `inventory` — Previsão de Estoque e Compras

### Regras de Negócio Ativas (`P-053` a `P-056`, substituindo `P-042` a `P-046`)
- **`P-053` (Política Mín/Máx por Dias de Cobertura):**
  - Padrão: `minCoverageDays = 30`, `maxCoverageDays = 60`, `historyWindowDays = 60`, `leadTimeDays = 15`.
  - Invariantes (`DA-05`): `maxCoverageDays > minCoverageDays` (`INV-001`) e `leadTimeDays < maxCoverageDays` (`INV-002`).
  - Fórmula: `estoqueMinimo = ceil_units(VMD × minCoverageDays)` e `estoqueMaximo = ceil_units(VMD × maxCoverageDays)`, com `VMD` em precisão integral (`DA-02`: `ceil_units(v) = math.ceil(round(v, 6))` para neutralizar resíduo IEEE 754 sem inflar itens de giro baixo como 1 un/60d). Para `VMD <= 0`, mínimo = 0 e máximo = 0.
- **`P-054` (Gatilho e Quantidade Sugerida sem Travas):**
  - Gatilho: `VMD > 0` e (`estoqueAtual <= estoqueMinimo` ou `diasCobertura < leadTimeDays`).
  - Quantidade: `max(0, ceil_units(estoqueMaximo - estoqueAtual))` quando acionado; `0` caso contrário.
  - Fallback de custo unitário: `0.60 × precoVenda` quando custo ≤ 0 e preço > 0.
- **`P-055` (Status Operacional e Capital Imobilizado):**
  - `CRITICAL_STOCKOUT` ("Ruptura Iminente"): `VMD > 0` e `diasCobertura < leadTimeDays`.
  - `REORDER_NEEDED` ("Abaixo do Mínimo"): `VMD > 0`, `diasCobertura >= leadTimeDays` e `estoqueAtual <= estoqueMinimo` (com `qtdSugeridaCompra > 0`).
  - `HEALTHY` ("Estoque Saudável"): `estoqueMinimo < estoqueAtual <= estoqueMaximo`, ou `VMD == 0` com `estoqueAtual == 0`, ou caso de borda `estoqueMinimo == estoqueMaximo` sem compra.
  - `OVERSTOCK` ("Acima do Máximo"): `estoqueAtual > estoqueMaximo` (inclui `VMD == 0` com `estoqueAtual > 0`). Capital imobilizado = `(estoqueAtual - estoqueMaximo) × custoUnitario`.
- **`P-056` (Revogação Integral de Modelo Estatístico e Travas):**
  - Revogados: `estoqueSeguranca`, `rop`, `estoqueIdeal`, `serviceLevel` (z-score), `targetCoverageDays`, trava física percentual (`P-044.4`) e teto orçamentário (`P-046.3`).
  - Clientes legados que enviem campos antigos no `POST /predict` ou `POST /export-csv` têm esses campos ignorados silenciosamente (`extra="ignore"`), sem efeito no cálculo.

### Arquitetura e Contratos (`ADR-001` & Contrato `2.0.0`)
- **Backend (`src/modules/inventory/`):**
  - `domain/replenishment_policy.py`: Value Objects imutáveis `ReplenishmentPolicy`, `StockLevels`, `PolicyViolation`, checagens puras `check_max_coverage_greater_than_min` / `check_lead_time_below_max_coverage` e `ceil_units`.
  - `domain/inventory_engine.py`: pipeline funcional decomposto (`prepare_product_catalog`, `build_sales_lookup`, `evaluate_product`, `build_kpis`, `calculate_inventory_replenishment`).
  - `api/schemas.py` & `api/router.py`: Contrato `2.0.0`, eco da política aplicada em `data.politica`, sanitização de nome de arquivo CSV (`[a-z0-9_]`) e supressão total de `str(e)` em respostas HTTP 500 (`DA-11`).
- **Frontend (`frontend/src/app/features/inventory/`):**
  - Estado reativo com Signals separando rascunho do modal e `appliedPolicy` efetiva.
  - Cache local migrado para `fitoherb_inventory_cache_v3` com *type guard* `isInventoryCachePayload` e remoção ativa de `fitoherb_inventory_cache_v2`.


---

## Módulo `sales_trend` — Tendência de Vendas por Item (Fevereiro 2026)

### Regras de Negócio Ativas (`P-072` a `P-093`, Erros `TND-001` a `TND-005`)
- **`P-072` (Catálogo Ativo & Inativos Fora):** Somente produtos ativos do catálogo atual com `Pc.Venda > 0` são considerados. Não há filtro, busca nem listagem para produtos inativos. Nas somas por fornecedor, entram exclusivamente produtos ativos.
- **`P-073` a `P-079` (Janelas de 1, 3, 6 e 12 meses):** Variação percentual entre a janela atual terminada no mês-base e a imediatamente anterior de mesmo tamanho.
  - Devoluções abatidas. Se volume líquido resultante for < 0, arredonda-se para 0 com flag `NEGATIVE_FLOORED_TO_ZERO`.
  - Estados de célula: `SEM_BASE` (< 50% de cobertura de histórico na janela anterior), `BASE_BAIXA` (volume anterior < 10 un ou R$ 500,00), `BASE_PARCIAL` (mês-base é mês corrente parcial ou primeiro mês de venda inicia na janela atual), `NORMAL`.
  - Normalização: quando uma janela possui cobertura parcial de dias, compara-se pela média diária equivalente (`V_norm = (total / dias_cobertos) * dias_totais`).
- **`P-080` a `P-082` (Ordenação, Filtro e Paginação):** Ordenação prioritária por maior alta/queda com base na janela selecionada (`sort_window`), paginada no servidor (padrão 50 itens).
- **`P-089` a `P-092` (Visão por Fornecedor):** Agrupamento por fornecedor através da SOMA líquida dos produtos ativos. Cada produto filho exibe sua contribuição em pontos percentuais (`pp`) para a variação total do fornecedor.

### Arquitetura e Contratos (`ADR-003`, Contrato `1.0.0`)
- **Backend (`src/modules/sales_trend/`):**
  - Módulo 100% isolado do módulo `analytics`.
  - Roteamento sob `/api/v1/sales-trend` com classe `TrendAPIRoute` para mapeamento padronizado de exceções (`TND-001` a `TND-005`) sem interferir no handler global.
  - Algoritmo de 2 Fases (`DA-06`): Fase A computa apenas `sort_window` para ordenação e contagem; Fase B (`LazyJanelas`) computa as demais janelas apenas para os itens da página corrente.
  - Snapshot de vendas em memória com TTL de 300s e controle de voo único (`Single-Flight`) evitando requisições concorrentes ao SQL Server.
  - Consumo de memória medido no banco real: Pico de 15.93 MB em carga (< 30 MB), 3.97 MB residente (< 6 MB).
- **Frontend (`frontend/src/app/features/sales-trend/`):**
  - Arquitetura reativa Angular com Signals (`SalesTrendStore`).
  - Responsividade completa: Tabela rica para desktop (>= 768px) e cartões colapsáveis para mobile (< 768px).
  - Acessibilidade WCAG AA, Skeleton loaders, Empty states, badges com suporte a alto contraste.

---

## Módulo `analytics` — Cross-sell (Fase 1 do plano de IA comercial, novembro 2026)

**Plano mestre:** `tasks/ia-analytics-vendas.md` (fases F4 → F5 → F6 → F1 → F3 → F2). **Branch/PR:** `feature/analytics-cross-sell` (11 commits). **Fontes:** `business_rules/analytics-cross-sell.md`, `adr/ADR-002-modulo-analytics-cross-sell.md`, `api_contracts/analytics-cross-sell.md` (1.1.0), `privacy/analytics-cross-sell.md`.

### Regras de Negócio Ativas (`P-058` a `P-071` e `P-094`; erros `XSL-001` a `XSL-004`, `ANL-001`, `ANL-002`)
- **Base:** cestas só de `VENDA` (devoluções não formam cesta, D4); Cesta Válida tem ≥ 2 SKUs; um cliente = um `Cod Cliente` (D3, confirmado: 0 pedidos com 2 clientes).
- **Regra Útil 1→1:** suporte ≥ 0,2%, ≥ 10 pedidos em comum, confiança ≥ 10%, lift ≥ 1,2 (inclusivos com tolerância 1e-9); consequente com suporte > 15% é Item Trivial e sai.
- **Modo produto:** ordem lift ↓, confiança ↓, pedidos em comum ↓, código ↑. **Modo cliente:** perfil = 365 dias; candidato nunca comprado ou dormente (> 90 dias); viável só com estoque > 0 e margem > 0; pontuação = lift × confiança × margem unitária; regra principal = máximo, não soma.
- **`P-094` (Curadoria, pedida pelo usuário):** descarta variante da origem (mesmo fornecedor + 1ª palavra significativa da descrição, sem tamanhos, singularizada); prioriza mesmo fornecedor → similar (palavra em comum) → resto, mantendo o ranking dentro da faixa; uma sugestão por linha; no máximo 10. Fornecedor vazio é desconhecido. *(IDs P-072 a P-093 pertencem a `sales_trend`.)*
- **Backtest (`P-071`)** mede o top-5 da lista curada.

### Decisões técnicas
- **Mineração por contagem direta de pares (Xᵀ·X esparso)**, não FP-Growth: o mlxtend não terminava em 10 min e passava de 4 GB na base real (54,5 mil cestas, 1.934 SKUs). Resultado idêntico (teste de equivalência); 2,3 s e 135 MB. O `max_len` em `basket_mining` foi revertido: o `pricing` não muda.
- **Cache:** snapshot imutável, lock de voo único, TTL 6 h, recarga manual com intervalo mínimo de 15 min, carga preguiçosa (sem lifespan). Carga completa ~22–28 s e pico ~320 MB.
- **Frontend:** sem exibição de margem nem do disclosure "Ver números" (pedido do usuário); a URL do modo cliente não leva o código (LGPD).
- **Repositório público:** `.agents/` é versionado, exceto `.agents/docs/db/` (catálogo do banco do ERP). Não colocar códigos reais de cliente em docs versionados.

### Resultado medido (backtest na base real, 2026-08 a 2026-10)
- hit rate@5: **modelo 22,6%** × **popularidade 43,6%** (4.415 clientes avaliados). Sem curadoria: 20,3%. Meta A-12 (informativa) não atingida. **Lição:** antes das próximas fases, investigar valor incremental do cross-sell (ex.: misturar popularidade, medir venda incremental) em vez de assumir que regras de associação vencem a linha de base.

### Pendências herdadas
- Condição LGPD C-2 (IAM do Cloud Logging, sem sink de longo prazo com `/cross-sell/customer/*`); `Cache-Control: no-store` na rota por cliente (NB-01).
- UX: aviso de cold start dentro de `aria-busy`; quantidade de resultados do combobox não anunciada.
- Bundle inicial 511,94 kB, no limite do aviso de 500 kB.
- 7 testes antigos do `pricing` usam o SQL Server real sem mock e travam `pytest tests`.
- Testes faltantes da curadoria: rota com > 10 regras (`totalItems == 10`), consequente fora do catálogo.
