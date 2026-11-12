# Contrato de API: Analytics Comercial — Sazonalidade por Produto

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-sazonalidade.md`  
> **Responsável:** Arquiteto (`api-contract-expert`)  
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`  

| Campo | Valor |
| :--- | :--- |
| **Módulo backend** | `src/modules/analytics/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/analytics/` (Angular 18) |
| **Versão do contrato** | **1.0.0** (`meta.version`) |
| **Regras** | P-106 a P-116 (`business_rules/analytics-sazonalidade.md`) |
| **Decisões** | `adr/ADR-005-sazonalidade-produto.md` |
| **Privacidade** | Bypass justificado (sem dados de cliente; somente SKU/Produto) |
| **Autenticação** | HTTP Basic global em produção |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/analytics`
- **Formato:** `application/json; charset=utf-8`
- **Nomenclatura:** `camelCase` nas propriedades JSON; datas e timestamps em formato ISO-8601 UTC.
- **Envelope Padronizado:**
  - Sucesso: `{ "data": ..., "meta": { ... } }`
  - Erro: `{ "error": { "code": "...", "message": "...", "fields": [...] }, "meta": { ... } }`

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/products/search?q=` | Busca rápida de produtos ativos no catálogo | P-115 |
| `GET` | `/api/v1/analytics/seasonality/{sku}` | Detalhes da sazonalidade, curva mensal e diagnóstico do produto | P-106 a P-113 |
| `GET` | `/api/v1/analytics/seasonality/ranking?order=most\|least` | Rankings de mais sazonais ou menos mensuráveis | P-114 |

---

## 2. Padrão de Envelope

### 2.1 Metadados Base (`AnalyticsMeta`)
```json
{
  "timestamp": "2026-11-12T12:00:00Z",
  "version": "1.0.0",
  "dataReferencia": "2026-10-31"
}
```

### 2.2 Metadados Paginados (`PagedMeta`)
```json
{
  "timestamp": "2026-11-12T12:00:00Z",
  "version": "1.0.0",
  "dataReferencia": "2026-10-31",
  "page": 1,
  "limit": 50,
  "totalItems": 142,
  "totalPages": 3
}
```

---

## 3. Especificação dos Endpoints

### 3.1 `GET /api/v1/analytics/seasonality/{sku}`

Retorna o diagnóstico completo de sazonalidade de um produto, incluindo série de 12 meses do calendário, períodos de pico e vale, força e métricas de consistência.

- **Path Parameters:**
  - `sku` (integer, obrigatório): Código numérico do produto (`gt=0`).
- **Respostas de Sucesso:** `200 OK`
```json
{
  "data": {
    "produto": {
      "codigo": 1042,
      "descricao": "EXTRATO DE PROPOLIS 30ML",
      "fornecedor": "APIS FLORA",
      "estoque": 120,
      "precoVenda": 28.50
    },
    "elegivel": true,
    "forca": "FORTE",
    "motivoInsuficiencia": null,
    "amplitude": 0.58,
    "correlacaoYoY": 0.78,
    "pico": {
      "mesInicio": 5,
      "mesFim": 7,
      "nomePeriodo": "Mai–Jul",
      "indice": 1.42,
      "confianca": "ALTA"
    },
    "vale": {
      "mesInicio": 11,
      "mesFim": 1,
      "nomePeriodo": "Nov–Jan",
      "indice": 0.84,
      "confianca": "MEDIA"
    },
    "serieMensal": [
      {
        "mes": 1,
        "nomeMes": "Janeiro",
        "indice": 0.86,
        "confianca": "ALTA",
        "observacoesDisponiveis": 2,
        "razao2025": 0.84,
        "razao2026": 0.88,
        "volumeLiquidoHistorico": 450,
        "receitaLiquidaHistorica": 12825.00
      },
      {
        "mes": 5,
        "nomeMes": "Maio",
        "indice": 1.40,
        "confianca": "ALTA",
        "observacoesDisponiveis": 2,
        "razao2025": 1.38,
        "razao2026": 1.42,
        "volumeLiquidoHistorico": 790,
        "receitaLiquidaHistorica": 22515.00
      },
      {
        "mes": 12,
        "nomeMes": "Dezembro",
        "indice": 0.88,
        "confianca": "BAIXA",
        "observacoesDisponiveis": 1,
        "razao2025": 0.88,
        "razao2026": null,
        "volumeLiquidoHistorico": 230,
        "receitaLiquidaHistorica": 6555.00
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-10-31"
  }
}
```

- **Respostas de Erro:**
  - `400 Bad Request` (`SEA-002`): Parâmetro `sku` inválido (`sku <= 0` ou não numérico).
  - `404 Not Found` (`SEA-001`): Produto inexistente no catálogo ou sem qualquer venda registrada.
  - `503 Service Unavailable` (`ANL-001`): Base de dados inacessível.

---

### 3.2 `GET /api/v1/analytics/seasonality/ranking`

Lista produtos ordenados por grau de sazonalidade ou categorizados como pouco mensuráveis.

- **Query Parameters:**
  - `order` (string, obrigatório): `"most"` (mais sazonais) ou `"least"` (pouco mensuráveis).
  - `limit` (integer, opcional): Padrão `50`, mínimo `1`, máximo `200`.
  - `offset` (integer, opcional): Padrão `0`, mínimo `0`.
- **Respostas de Sucesso:** `200 OK`
```json
{
  "data": [
    {
      "sku": 1042,
      "descricao": "EXTRATO DE PROPOLIS 30ML",
      "fornecedor": "APIS FLORA",
      "forca": "FORTE",
      "amplitude": 0.58,
      "mesPico": "Mai–Jul",
      "mesVale": "Nov–Jan",
      "faturamentoTotal": 185400.00,
      "motivoInsuficiencia": null
    },
    {
      "sku": 2085,
      "descricao": "VITAMINA C 1000MG 60CPS",
      "fornecedor": "CATARINENSE",
      "forca": "MODERADA",
      "amplitude": 0.32,
      "mesPico": "Junho",
      "mesVale": "Fevereiro",
      "faturamentoTotal": 94200.00,
      "motivoInsuficiencia": null
    }
  ],
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-10-31",
    "page": 1,
    "limit": 50,
    "totalItems": 320,
    "totalPages": 7
  }
}
```

Para `order=least`:
```json
{
  "data": [
    {
      "sku": 3050,
      "descricao": "CHA DE ERVA DOCE ORGANICO",
      "fornecedor": "CHÁ MAIS",
      "forca": "INSUFICIENTE",
      "amplitude": 0.0,
      "mesPico": "-",
      "mesVale": "-",
      "faturamentoTotal": 4120.00,
      "motivoInsuficiencia": "HISTORICO_CURTO"
    }
  ],
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-10-31",
    "page": 1,
    "limit": 50,
    "totalItems": 85,
    "totalPages": 2
  }
}
```

- **Respostas de Erro:**
  - `400 Bad Request` (`SEA-002`): Parâmetro `order` inválido ou fora dos limites de paginação (`fields: ["order"]`).
  - `503 Service Unavailable` (`ANL-001`): Base de dados indisponível.

---

### 3.3 `GET /api/v1/analytics/products/search?q=`

Busca rápida no catálogo ativo em cache para o componente de autocomplete.

- **Query Parameters:**
  - `q` (string, obrigatório): Trecho do código ou descrição (1 a 100 caracteres).
  - `limit` (integer, opcional): Padrão `20`, máx `20`.
- **Respostas de Sucesso:** `200 OK`
```json
{
  "data": [
    {
      "codigo": 1042,
      "descricao": "EXTRATO DE PROPOLIS 30ML",
      "fornecedor": "APIS FLORA",
      "estoque": 120,
      "precoVenda": 28.50
    }
  ],
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-10-31",
    "page": 1,
    "limit": 20,
    "totalItems": 1,
    "totalPages": 1
  }
}
```

---

## 4. Tratamento de Erros e Códigos Internos

Todos os erros retornam corpo estruturado com `error` e `meta`:

```json
{
  "error": {
    "code": "SEA-001",
    "message": "Produto não encontrado ou sem histórico de vendas.",
    "fields": []
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0"
  }
}
```

| Código | Status HTTP | Significado | Exemplo de Cenário |
| :--- | :---: | :--- | :--- |
| `SEA-001` | `404` | Produto não encontrado | SKU não existe ou não tem vendas |
| `SEA-002` | `400` | Parâmetros inválidos | `order=abc` ou `sku=-1` |
| `SEA-003` | `422` | Base de vendas insuficiente | Menos de 20 SKUs válidos na base |
| `ANL-001` | `503` | Falha na base de dados | Erro de conexão ODBC |
