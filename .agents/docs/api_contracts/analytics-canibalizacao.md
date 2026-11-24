# Contrato de API: Analytics Comercial — Canibalização por Migração de Clientes e Equilíbrio de Preço (F6 v2)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-canibalizacao.md`  
> **Responsável:** Arquiteto (`api-contract-expert` / `architect.md`)  
> **Referências:** `business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`), `ADR-007-canibalizacao.md`, `privacy/analytics-canibalizacao.md` (`LGPD-CAN-01..08`)

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/analytics`
- **Versão do Contrato (`meta.version`):** `"1.1.0"`
- **Convenção:** `camelCase` rigoroso em query params, path params e payloads JSON.
- **Formato:** `application/json; charset=utf-8`
- **Autenticação:** HTTP Basic Auth (`src/core/auth.py`).
- **Privacidade (LGPD-CAN-02):** Zero `Cod Cliente` ou qualquer dado identificável de cliente nos payloads.

---

## 2. Envelope Padrão de Resposta

Todas as respostas `200 OK` seguem o envelope `{ "data": ..., "meta": ... }` estendendo `AnalyticsMeta`:

```json
{
  "data": {},
  "meta": {
    "timestamp": "2026-11-23T19:00:00Z",
    "version": "1.1.0",
    "dataReferencia": "2026-11-23",
    "windowDays": 90,
    "prePeriod": { "startDate": "2026-05-27", "endDate": "2026-08-24" },
    "curPeriod": { "startDate": "2026-08-25", "endDate": "2026-11-22" },
    "executionTimeMs": 142
  }
}
```

---

## 3. Endpoints

### 3.1. `GET /api/v1/analytics/cannibalization/report`

- **Objetivo:** Retornar o **Relatório Global de Canibalização**, contendo KPIs consolidados, filtros disponíveis (`availableCategories`, `availableSuppliers`) e a lista de produtos vítimas ordenados por `cannibalizedRevenue` decrescente, com `topCannibal` e resumo de `cannibalizers[]`.
- **Regras:** `P-128` a `P-138`.

#### Query Parameters

| Parâmetro | Tipo | Obrigatório? | Default | Validação / Limites | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `windowDays` | `integer` | Não | `90` | Enum: `30`, `60`, `90` | Janela comparativa em dias (`CUR` vs `PRE`). |
| `minDropPct` | `float` | Não | `5.0` | Mín: `1.0`, Máx: `80.0` | Queda percentual mínima de faturamento da vítima. |
| `minMigratedClients` | `integer` | Não | `3` | Mín: `1`, Máx: `50` | Mínimo de clientes em migração direcional líquida $A \to B$. |
| `category` | `string` | Não | `null` | Texto livre sanitizado | Filtra vítimas pela categoria (`Tipo`). |
| `supplier` | `string` | Não | `null` | Texto livre sanitizado | Filtra vítimas pelo fornecedor (`Fornecedor`). |
| `mechanism` | `string` | Não | `null` | Enum: `PRECO_MENOR_DESTROI_MARGEM`, `PRECO_MENOR_MARGEM_PRESERVADA`, `MIGRACAO_POR_VALOR` | Filtra vítimas cujo `topCannibal` (ou algum canibalizador) possua o mecanismo informado. |
| `search` | `string` | Não | `null` | Máx: `80` chars | Busca textual por SKU ou descrição da vítima. |

#### Resposta de Sucesso (`200 OK`)

```json
{
  "data": {
    "kpis": {
      "totalVictims": 18,
      "totalCannibalizedRevenue": 42850.40,
      "avgCannibalizedRevenuePct": 21.35,
      "totalNetMarginImpact": -4120.80,
      "marginDestroyingPairsCount": 14
    },
    "availableCategories": ["CAPSULAS", "CHAS", "EXTRATOS", "SUPLEMENTOS"],
    "availableSuppliers": ["FITOHERB", "HERBARIUM", "NATUVIDA"],
    "victims": [
      {
        "sku": "100235",
        "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
        "category": "EXTRATOS",
        "supplier": "FITOHERB",
        "preRevenue": 18400.00,
        "curRevenue": 12100.00,
        "revenueDrop": 6300.00,
        "revenueDropPct": 34.24,
        "cannibalizedRevenue": 4420.50,
        "cannibalizedRevenuePct": 24.02,
        "dropExplainedPct": 70.17,
        "currentPrice": 30.00,
        "unitCost": 16.00,
        "unitMargin": 14.00,
        "marginPct": 46.67,
        "costFallbackUsed": false,
        "currentStock": 185,
        "cannibalizerCount": 2,
        "netMarginImpact": -685.18,
        "topCannibal": {
          "sku": "100234",
          "description": "EXTRATO DE PROPOLIS VERDE 30ML",
          "migratedClients": 11,
          "migratedRevenue": 3180.50,
          "shareOfCannibalizationPct": 71.95,
          "currentPrice": 22.00,
          "unitMargin": 8.50,
          "marginPct": 38.64,
          "costFallbackUsed": false,
          "priceGapPct": 36.36,
          "netMarginImpact": -255.39,
          "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
          "suggestedVictimPrice": 28.40,
          "suggestedCannibalPrice": 23.60,
          "projectedPriceGapPct": 20.34,
          "actionSummary": "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
        },
        "cannibalizers": [
          {
            "sku": "100234",
            "description": "EXTRATO DE PROPOLIS VERDE 30ML",
            "migratedClients": 11,
            "migratedRevenue": 3180.50,
            "shareOfCannibalizationPct": 71.95,
            "currentPrice": 22.00,
            "unitMargin": 8.50,
            "marginPct": 38.64,
            "costFallbackUsed": false,
            "priceGapPct": 36.36,
            "netMarginImpact": -255.39,
            "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
            "suggestedVictimPrice": 28.40,
            "suggestedCannibalPrice": 23.60,
            "projectedPriceGapPct": 20.34,
            "actionSummary": "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
          },
          {
            "sku": "100290",
            "description": "EXTRATO DE PROPOLIS COMPOSTO 30ML",
            "migratedClients": 4,
            "migratedRevenue": 1240.00,
            "shareOfCannibalizationPct": 28.05,
            "currentPrice": 24.00,
            "unitMargin": 9.60,
            "marginPct": 40.00,
            "costFallbackUsed": true,
            "priceGapPct": 25.00,
            "netMarginImpact": -82.71,
            "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
            "suggestedVictimPrice": 28.80,
            "suggestedCannibalPrice": 25.20,
            "projectedPriceGapPct": 14.29,
            "actionSummary": "Reduzir vítima para R$ 28,80 (-4,0%) e reajustar canibalizador para R$ 25,20 (+5,0%) para fechar o gap de 25,0% para 14,3%."
          }
        ]
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-23T19:00:00Z",
    "version": "1.1.0",
    "dataReferencia": "2026-11-23",
    "windowDays": 90,
    "minDropPct": 5.0,
    "minMigratedClients": 3,
    "prePeriod": { "startDate": "2026-05-27", "endDate": "2026-08-24" },
    "curPeriod": { "startDate": "2026-08-25", "endDate": "2026-11-22" },
    "totalFound": 18,
    "executionTimeMs": 142
  }
}
```

---

### 3.2. `GET /api/v1/analytics/cannibalization/report/{sku}`

- **Objetivo:** Retornar o detalhe completo de uma vítima específica, incluindo todos os seus canibalizadores válidos (até 10, ordenados por `migratedRevenue` decrescente) e recomendações completas de equilíbrio de preço.
- **Regras:** `P-128` a `P-138`.

#### Path Parameters

| Parâmetro | Tipo | Obrigatório? | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `sku` | `string` | Sim | `^[1-9]\d*$` | Código inteiro positivo do produto no catálogo (`Externo01.Produto.Codigo`). |

#### Query Parameters

| Parâmetro | Tipo | Obrigatório? | Default | Validação / Limites | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `windowDays` | `integer` | Não | `90` | Enum: `30`, `60`, `90` | Janela comparativa em dias (`CUR` vs `PRE`). |
| `minDropPct` | `float` | Não | `5.0` | Mín: `1.0`, Máx: `80.0` | Queda percentual mínima considerada. |
| `minMigratedClients` | `integer` | Não | `3` | Mín: `1`, Máx: `50` | Mínimo de clientes em migração direcional líquida. |

#### Resposta de Sucesso (`200 OK`)

```json
{
  "data": {
    "isCannibalized": true,
    "victim": {
      "sku": "100235",
      "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
      "category": "EXTRATOS",
      "supplier": "FITOHERB",
      "preRevenue": 18400.00,
      "curRevenue": 12100.00,
      "revenueDrop": 6300.00,
      "revenueDropPct": 34.24,
      "cannibalizedRevenue": 4420.50,
      "cannibalizedRevenuePct": 24.02,
      "dropExplainedPct": 70.17,
      "currentPrice": 30.00,
      "unitCost": 16.00,
      "unitMargin": 14.00,
      "marginPct": 46.67,
      "costFallbackUsed": false,
      "currentStock": 185,
      "cannibalizerCount": 2,
      "netMarginImpact": -685.18
    },
    "cannibalizers": [
      {
        "sku": "100234",
        "description": "EXTRATO DE PROPOLIS VERDE 30ML",
        "category": "EXTRATOS",
        "supplier": "FITOHERB",
        "migratedClients": 11,
        "grossClientsToCannibal": 13,
        "reverseClientsToVictim": 2,
        "migratedRevenue": 3180.50,
        "shareOfCannibalizationPct": 71.95,
        "preRevenue": 9200.00,
        "curRevenue": 14800.00,
        "currentPrice": 22.00,
        "unitCost": 13.50,
        "unitMargin": 8.50,
        "marginPct": 38.64,
        "costFallbackUsed": false,
        "currentStock": 340,
        "priceGapPct": 36.36,
        "netMarginImpact": -255.39,
        "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
        "suggestedVictimPrice": 28.40,
        "suggestedCannibalPrice": 23.60,
        "projectedPriceGapPct": 20.34,
        "victimMarginFloorPrice": 20.00,
        "actionSummary": "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-23T19:00:00Z",
    "version": "1.1.0",
    "dataReferencia": "2026-11-23",
    "sku": "100235",
    "windowDays": 90,
    "prePeriod": { "startDate": "2026-05-27", "endDate": "2026-08-24" },
    "curPeriod": { "startDate": "2026-08-25", "endDate": "2026-11-22" },
    "executionTimeMs": 12
  }
}
```

> **Caso sem canibalização (`200 OK`):** Quando o `sku` existe no catálogo ativo, mas não satisfaz critérios de vítima ou não possui canibalizadores válidos na janela, retorna `isCannibalized: false`, `victim` com métricas de faturamento/preço/margem (e `cannibalizedRevenue: 0.0`, `cannibalizedRevenuePct: 0.0`, `cannibalizerCount: 0`) e `cannibalizers: []`.

---

## 4. Enums Oficiais

- **`mechanism` (`P-134`):**
  - `"PRECO_MENOR_DESTROI_MARGEM"`
  - `"PRECO_MENOR_MARGEM_PRESERVADA"`
  - `"MIGRACAO_POR_VALOR"`

---

## 5. Matriz de Erros HTTP e Payloads de Falha

| HTTP | Código | Causa Raiz | `fields` | Mensagem Amigável |
| :--- | :--- | :--- | :--- | :--- |
| **`400 Bad Request`** | `CAN-004` | Parâmetro inválido (`windowDays` fora de `{30,60,90}`, `minDropPct` ou `minMigratedClients` fora dos limites, `mechanism` inválido, `sku` não numérico). | Nomes dos parâmetros (ex: `["windowDays"]`) | `"Parâmetros inválidos: windowDays."` |
| **`404 Not Found`** | `CAN-001` | SKU não encontrado no catálogo ativo. | `[]` | `"Produto não encontrado no catálogo ativo."` |
| **`422 Unprocessable`** | `CAN-003` | Histórico transacional insuficiente nas janelas `PRE`/`CUR` para calcular o relatório. | `[]` | `"Histórico transacional insuficiente para compor a análise de canibalização na janela selecionada."` |
| **`500 Internal Error`** | `CAN-005` | Erro interno inesperado no processamento. | `[]` | `"Não foi possível processar o relatório de canibalização no momento. Tente novamente mais tarde."` |
| **`503 Service Unavailable`** | `ANL-001` | Indisponibilidade ou timeout do SQL Server. | `[]` | `"Base de vendas indisponível no momento. Tente novamente em instantes."` |

### Envelope de Erro Padronizado

```json
{
  "error": {
    "code": "CAN-004",
    "message": "Parâmetros inválidos: windowDays.",
    "fields": ["windowDays"],
    "details": null
  },
  "meta": {
    "timestamp": "2026-11-23T19:00:00Z",
    "version": "1.1.0"
  }
}
```

> **Segurança e Privacidade (LGPD-CAN-06):** Nunca ecoar valores brutos recebidos em `message` ou `details`, nunca expor stacktraces ou mensagens do driver `pyodbc`, e nunca retornar `Cod Cliente`.
