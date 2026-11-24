# ADR-007: Arquitetura v2 — Relatório Global de Canibalização por Migração de Clientes e Equilíbrio de Preço (Fase F6)

> **Status:** Aprovado para Implementação (Pivô v2)  
> **Data:** 2026-11-23  
> **Autores:** Arquiteto (`architect.md`) & Especialista em IA (`ai_specialist.md`)  
> **Localização Mandatória:** `.agents/docs/adr/ADR-007-canibalizacao.md`  
> **Módulo:** `src/modules/analytics/` (`domain/cannibalization.py`)  
> **Branch:** `feature/analytics-canibalizacao`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Relatório Global de Canibalização por Migração de Clientes e Equilíbrio de Preço (F6 v2) |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-canibalizacao.md` (`version: "1.1.0"`, prefixo `CAN-XXX`) |
| **Checklist Técnico** | `.agents/docs/tasks/analytics-canibalizacao.md` |
| **Parecer LGPD** | `.agents/docs/privacy/analytics-canibalizacao.md` (`LGPD-CAN-01..08`, Bypass de RIPD) |

---

## 1. Contexto e Motivação do Pivô v2

Na v1 (baseada em evento DiD isolado por SKU), o usuário precisava adivinhar previamente qual SKU sofreu promoção/reajuste para então consultar o impacto. Na prática comercial da Fitoherb, a necessidade real é **proativa e global**:
1. **Descobrir automaticamente** quais produtos do portfólio estão perdendo faturamento por canibalização (`%` e `R$`).
2. **Identificar com evidência comportamental direta** quais produtos da mesma categoria (`Tipo`) estão capturando os clientes de cada vítima — sem depender de eventos cadastrados em `Cod Promocao`.
3. **Orientar a decisão de preço** com números prontos (`suggestedVictimPrice`, `suggestedCannibalPrice`) para o time comercial equilibrar o gap de preço e estancar a destruição de margem.

---

## 2. Arquitetura de Componentes (v2)

```
            ┌───────────────────────────────────────────────────────────┐
            │            FastAPI Router (/api/v1/analytics)             │
            │  GET /cannibalization/report                              │
            │  GET /cannibalization/report/{sku}                        │
            └─────────────────────────────┬─────────────────────────────┘
                                          │
                                          ▼
            ┌───────────────────────────────────────────────────────────┐
            │                    AnalyticsService                       │
            │  - Cache TTL 6h por (windowDays, referenceDate)           │
            │  - asyncio.Lock contra thundering herd                    │
            │  - Filtros dinâmicos (category/supplier/mechanism/search) │
            └──────────────┬─────────────────────────────┬──────────────┘
                           │                             │
                           ▼                             ▼
┌─────────────────────────────────────────┐  ┌──────────────────────────────────────────┐
│     SalesRepository (SQL Server)        │  │   Domain: cannibalization.py (puro)      │
│ - fetch_cannibalization_catalog()       │  │ - P-130: Migração Direcional Bruta       │
│ - fetch_customer_sku_window_sales(      │  │   (by_cli em memória + del by_cli)       │
│     pre_start, mid, ref)                │  │ - P-131: Fluxo Líquido (A->B - B->A)     │
│ - Subquery SELECT (sem WITH/CONCAT)     │  │ - P-132: R$ e % Canibalizado + KPIs      │
│ - Devoluções abatidas (LIKE 'DEVOLU%')  │  │ - P-133/134: Gap, Margem e Mecanismo     │
│ - fetchmany(50_000), bind params `?`    │  │ - P-135: Motor de Equilíbrio de Preço    │
└─────────────────────────────────────────┘  └──────────────────────────────────────────┘
```

---

## 3. Decisões Arquiteturais (DA-01 a DA-07)

### DA-01 — Migração Direcional Líquida com Conservação de Fluxo (Substitui DiD + Jaccard)

- **Problema do Jaccard puro:** Mede apenas co-compra simultânea (não distingue complemento de canibalização nem direção do fluxo).
- **Solução v2 (`P-130`, `P-131`):** Para cada cliente $c$ dentro de cada categoria `Tipo`:
  - Mede-se a queda de receita $L_{c,A} = \max(0, R_{c,A}^{PRE} - R_{c,A}^{CUR})$ e o ganho $G_{c,B} = \max(0, R_{c,B}^{CUR} - R_{c,B}^{PRE})$.
  - Aloca-se proporcionalmente o fluxo migrável $F_{c,T} = \min(L_{c,T}, G_{c,T})$:
    $$M_c(A \to B) = F_{c,T} \times \frac{L_{c,A}}{L_{c,T}} \times \frac{G_{c,B}}{G_{c,T}}$$
    Isso elimina dupla contagem quando um cliente reduz 1 item e aumenta 3 itens na mesma categoria.
  - Desconta-se o fluxo reverso:
    $$\text{netRev}(A \to B) = \max(0, \text{grossRev}(A \to B) - \text{grossRev}(B \to A))$$
    $$\text{netClients}(A \to B) = \max(0, N_{\text{gross}}(A \to B) - N_{\text{gross}}(B \to A))$$
  - Exige-se `netClients >= minMigratedClients` (padrão `3`), `preRevenue >= R$ 500` e `revenueDropPct >= minDropPct` (padrão `5%`), eliminando ruído estatístico de pequenos volumes.

### DA-02 — Motor Determinístico de Equilíbrio de Preço (`P-133`, `P-134`, `P-135`)

- Compara $P_A$ vs $P_B$, calcula `priceGapPct = (P_A - P_B) / P_B * 100` e margem unitária (com fallback `COST_FALLBACK_RATIO = 0.60` se `Pc.Ultimo Custo` for ausente ou inconsistente).
- Classifica cada par em:
  - `PRECO_MENOR_DESTROI_MARGEM` (`priceGapPct > 3%` e $M_{u,B} < M_{u,A}$)
  - `PRECO_MENOR_MARGEM_PRESERVADA` (`priceGapPct > 3%` e $M_{u,B} \ge M_{u,A}$)
  - `MIGRACAO_POR_VALOR` (`priceGapPct <= 3%`)
- Calcula `suggestedVictimPrice` e `suggestedCannibalPrice` para fechar ~40% do gap $\Delta P = P_A - P_B$, com duas travas de segurança financeira:
  1. **Piso de margem da vítima:** $P_{\text{floor},A} = C_{ef,A} / (1 - 0.20)$ (mínimo 20% de contribuição).
  2. **Teto de reajuste no canibalizador:** $P_{\text{cap},B} = P_B \times 1.12$ (máximo +12% para evitar ruptura de demanda).

### DA-03 — Query SQL Única em Subquery (Compatibilidade `is_readonly_query` e SQL Server Legado)

- `is_readonly_query` exige que a SQL inicie com `SELECT` (proíbe `WITH` CTE). Além disso, `CONCAT` é proibido no SQL Server legado.
- **Query canônica (`fetch_customer_sku_window_sales`):**
  ```sql
  SELECT
      base.customer_code,
      base.sku,
      SUM(CASE WHEN base.period_flag = 0 THEN base.net_qty ELSE 0 END) AS pre_qty,
      SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) AS pre_rev,
      SUM(CASE WHEN base.period_flag = 1 THEN base.net_qty ELSE 0 END) AS cur_qty,
      SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) AS cur_rev
  FROM (
      SELECT
          [Cod Cliente] AS customer_code,
          [Cod Produto] AS sku,
          CASE WHEN [Data] >= ? THEN 1 ELSE 0 END AS period_flag,
          SUM([Qtd Venda]) AS net_qty,
          SUM([Valor Venda]) AS net_rev
      FROM Externo01.Vendas
      WHERE ([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%')
        AND [Data] >= ?
        AND [Data] < ?
        AND [Cod Cliente] IS NOT NULL
        AND [Cod Produto] IS NOT NULL
      GROUP BY [Cod Cliente], [Cod Produto], CASE WHEN [Data] >= ? THEN 1 ELSE 0 END
  ) AS base
  GROUP BY base.customer_code, base.sku
  HAVING SUM(CASE WHEN base.period_flag = 0 THEN base.net_rev ELSE 0 END) > 0
      OR SUM(CASE WHEN base.period_flag = 1 THEN base.net_rev ELSE 0 END) > 0
  ```
- **Bind params `?`:** `(mid_date, pre_start_date, reference_date, mid_date)`.
- **Memória Cloud Run (2Gi):** Leitura em streaming com `cursor.fetchmany(50_000)` evitando `fetchall()` de toda a tabela.

### DA-04 — Governança LGPD em Memória Volátil (`LGPD-CAN-01..06`)

- O dicionário `by_cli: dict[int, dict[str, tuple[float, float]]]` existe exclusivamente durante a execução da função de domínio que agrega os fluxos `(A -> B)` por categoria.
- Imediatamente após consolidar as matrizes de pares agregados `(victim_sku, cannibal_sku)` e totais por SKU, executa-se **`del by_cli`** antes de retornar o resultado ao serviço ou gravar no `AnalyticsCache`.
- Zero `Cod Cliente` em DTOs, cache ou logs.

### DA-05 — Estratégia de Cache (TTL 6h por `windowDays`)

- O cálculo pesado (query SQL + agregação de clientes `by_cli` -> matriz líquida de pares e totais por SKU) depende apenas de `(windowDays, referenceDate)`.
- O `AnalyticsCache` armazena o snapshot agregado de pares e totais de SKU por chave `cannibalization_v2:{windowDays}:{referenceDate}` com TTL de **6 horas** e `asyncio.Lock`.
- Variações de `minDropPct`, `minMigratedClients` e filtros (`category`, `supplier`, `mechanism`, `search`) são aplicadas em memória em `< 5 ms` sobre o snapshot cacheado (sem reconsultar o SQL Server e sem manter `by_cli` em cache).

### DA-06 — Separação de Rotas v2 (`/report` e `/report/{sku}`)

- `GET /api/v1/analytics/cannibalization/report`: visão global consolidada com KPIs, filtros disponíveis (`availableCategories`, `availableSuppliers`) e lista de vítimas com `topCannibal` e resumo de `cannibalizers[]`.
- `GET /api/v1/analytics/cannibalization/report/{sku}`: drill-down completo da vítima com todos os canibalizadores (até 10) e recomendações detalhadas de equilíbrio de preço.
- Envelopes `data`/`meta` com `meta.version = "1.1.0"`, estritamente em `camelCase`.

### DA-07 — Bypasses Formalizados

- **DBA:** Bypass total — somente leitura em `Externo01.Vendas` e `Externo01.Produto`, sem migrations.
- **Privacy Officer:** Mantido Bypass de RIPD de `privacy/analytics-canibalizacao.md` sob estrito cumprimento de `LGPD-CAN-01..08` (`del by_cli`).

---

## 4. Alternativas Descartadas

| Alternativa | Motivo do Descarte |
| :--- | :--- |
| **DiD isolado por evento (v1)** | Exigia escolha manual de SKU e existência de `Cod Promocao` explícito; não entregava visão global de quais produtos estão sendo canibalizados hoje. |
| **CTE `WITH base AS (...)`** | Rejeitada pelo validador `is_readonly_query` que exige instrução iniciando por `SELECT`. |
| **Cachear `by_cli` para re-filtrar** | Violação direta de `LGPD-CAN-04` e `LGPD-CAN-05` (proibição de manter `Cod Cliente` em cache). Cachear a matriz agregada `(A, B)` resolve performance com 100% de privacidade. |
| **Migração entre categorias diferentes** | Introduz correlações espúrias entre linhas não substitutas (ex.: chá vs cosmético). Restringir ao mesmo `Tipo` garante substitutibilidade real. |

---

## 5. Trade-offs e Mitigações

- **Cold Cache (~1–3s na 1ª consulta de uma janela):** Mitigado por cache de 6h por `windowDays` + `asyncio.Lock` e Skeleton Loader com aviso de 4s no Frontend.
- **Produtos sem `Pc.Ultimo Custo` cadastrado:** Mitigado por fallback determinístico de 60% (`costFallbackUsed: true`) sinalizado explicitamente na API e na UI.
