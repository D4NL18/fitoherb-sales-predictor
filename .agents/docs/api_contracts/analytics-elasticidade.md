# Contrato de API: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-elasticidade.md`
> **Responsável:** Arquiteto (`api-contract-expert`)
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Módulo Backend** | `src/modules/analytics/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/analytics/` (Angular 18) |
| **Versão do Contrato** | **1.0.0** (`meta.version`) |
| **Regras** | P-095 a P-105 (`business_rules/analytics-elasticidade.md`) |
| **Decisões** | `adr/ADR-004-elasticidade-preco.md` |
| **Privacidade** | `privacy/analytics-elasticidade.md` |
| **Autenticação** | HTTP Basic global ativo em produção (P-033) |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/analytics`
- **Protocolo:** HTTP/REST, `application/json; charset=utf-8`
- **Convenção de Nomenclatura:** `camelCase` em todos os campos do JSON.
- **Identificação de Cliente:** Estritamente `customerCode` (inteiro positivo). Nenhum dado nominal (nome, CNPJ, razão social) trafega no contrato.

### Endpoints da Feature

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/elasticity/product/{sku}` | Elasticidade agregada do produto e lista paginada de seus clientes | P-095 a P-100, P-103 |
| `GET` | `/api/v1/analytics/elasticity/product/{sku}/customer/{customerCode}` | Elasticidade refinada do par produto × cliente via shrinkage | P-097, P-098, P-104 |
| `POST` | `/api/v1/analytics/elasticity/simulate` | Simulação de impacto de reajuste de preço em volume, receita e margem | P-101 |

---

## 2. Modelos de Dados e Schemas

### 2.1 Envelopes Padrão

```json
// Sucesso (2xx)
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "totalItems": 150,
    "totalPages": 3,
    "limit": 50,
    "offset": 0
  }
}

// Erro (4xx/5xx)
{
  "error": {
    "code": "ELA-004",
    "message": "Parâmetros inválidos: priceChangePct.",
    "fields": ["priceChangePct"]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

## 3. Especificação dos Endpoints

### 3.1 `GET /api/v1/analytics/elasticity/product/{sku}`

Retorna os parâmetros de elasticidade estimados para o produto e a listagem paginada dos clientes que adquiriram o SKU.

#### Parâmetros de Path e Query
- `sku` (path, int, 1..2147483647): Código do produto consultado.
- `limit` (query, int, 1..200, default 50): Tamanho da página da lista de clientes.
- `offset` (query, int, >= 0, default 0): Deslocamento da paginação de clientes.

#### Exemplo de Resposta 200 OK
```json
{
  "data": {
    "product": {
      "code": 1001,
      "description": "EXTRATO DE PROPOLIS VERDE 30ML",
      "supplier": "FITOHERB LAB",
      "currentPrice": 25.50,
      "costPrice": 12.00,
      "stock": 420
    },
    "elasticity": {
      "coefficient": -1.45,
      "classification": "ELASTICO",
      "rSquared": 0.58,
      "standardError": 0.18,
      "confidenceInterval": [-1.80, -1.10],
      "confidenceLevel": "ALTA",
      "isReliable": true,
      "observationsCount": 18,
      "fallbackApplied": false,
      "insightMessage": "Demanda elástica: elevação de preços tende a reduzir volume proporcionalmente maior."
    },
    "customers": [
      {
        "customerCode": 4501,
        "ordersCount": 12,
        "totalUnits": 350,
        "empiricalElasticity": -1.60,
        "shrinkageElasticity": -1.52,
        "classification": "ELASTICO",
        "shrinkageWeight": 0.55
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "totalItems": 1,
    "totalPages": 1,
    "limit": 50,
    "offset": 0
  }
}
```

---

### 3.2 `GET /api/v1/analytics/elasticity/product/{sku}/customer/{customerCode}`

Retorna os detalhes de elasticidade calculados especificamente para o cliente sobre aquele produto.

#### Parâmetros de Path
- `sku` (path, int): Código do produto.
- `customerCode` (path, int): Código do cliente.

#### Exemplo de Resposta 200 OK
```json
{
  "data": {
    "sku": 1001,
    "customerCode": 4501,
    "productElasticity": -1.45,
    "customerEmpiricalElasticity": -1.60,
    "customerElasticity": -1.52,
    "classification": "ELASTICO",
    "shrinkageWeight": 0.55,
    "ordersCount": 12,
    "totalUnits": 350,
    "confidenceLevel": "MEDIA",
    "isReliable": true,
    "insightMessage": "Cliente sensível a variações de preço neste SKU; histórico com 12 pedidos."
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

### 3.3 `POST /api/v1/analytics/elasticity/simulate`

Simula o impacto em volume, receita e margem para uma variação percentual de preço informada.

#### Payload de Requisição
```json
{
  "sku": 1001,
  "customerCode": 4501, // Opcional: se omitido, simula com a elasticidade global do produto
  "priceChangePct": 5.0 // Entre -50.0 e +100.0%
}
```

#### Exemplo de Resposta 200 OK
```json
{
  "data": {
    "sku": 1001,
    "customerCode": 4501,
    "appliedElasticity": -1.52,
    "priceChangePct": 5.0,
    "currentPrice": 25.50,
    "projectedPrice": 26.78,
    "currentVolume": 350.0,
    "projectedVolume": 323.4,
    "volumeChangePct": -7.6,
    "currentRevenue": 8925.0,
    "projectedRevenue": 8660.65,
    "revenueChangePct": -2.96,
    "revenueChangeAbs": -264.35,
    "currentMargin": 4725.0,
    "projectedMargin": 4780.20,
    "marginChangePct": 1.17,
    "marginChangeAbs": 55.20,
    "recommendation": "Reajuste viável com expansão de margem financeira apesar da queda moderada de volume."
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

## 4. Tabela de Códigos de Erro

| Código | Status HTTP | Mensagem Padronizada |
| :--- | :---: | :--- |
| `ELA-001` | 404 | Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade. |
| `ELA-002` | 404 | Cliente sem compras registradas para este produto. |
| `ELA-003` | 422 | Histórico de vendas insuficiente para estimar elasticidade do produto. |
| `ELA-004` | 400 | Parâmetros inválidos fornecidos para consulta ou simulação de elasticidade. |
| `ANL-001` | 503 | Base de dados de vendas temporariamente indisponível. |
