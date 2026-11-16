# Contrato de API: Analytics Comercial — F5 Elasticidade-preço e Calculadora Unificada

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-elasticidade.md`
> **Responsável:** Arquiteto (`api-contract-expert`)
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Módulo Backend** | `src/modules/analytics/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/analytics/` (Angular 18) |
| **Versão do Contrato** | **1.0.0 (Extensão Retrocompatível v3)** (`meta.version`: `"1.0.0"`) |
| **Regras** | P-095 a P-105 (`business_rules/analytics-elasticidade.md`) |
| **Decisões** | `adr/ADR-004-elasticidade-preco.md` |
| **Privacidade** | `privacy/analytics-elasticidade.md` |
| **Autenticação** | HTTP Basic global ativo em produção (P-033) |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/analytics`
- **Protocolo:** HTTP/REST, `application/json; charset=utf-8`
- **Convenção de Nomenclatura:** `camelCase` em todos os campos do JSON (`alias_generator=to_camel`, `populate_by_name=True` em `CamelModel`).
- **Identificação de Cliente:** Estritamente `customerCode` (inteiro positivo). Nenhum dado nominal (nome, CNPJ, razão social) trafega no contrato.
- **Compatibilidade Retroativa (v3):** Todos os novos campos adicionados a `ProductHeader` e `SimulationImpactData` possuem valores padrão (`default`) no Pydantic v2, e `costPrice` em `ElasticitySimulationRequest` é opcional (`None`), preservando 100% de compatibilidade com os testes e consumidores existentes.
- **Limpeza Estrutural em `src/modules/analytics/api/schemas.py`:** Remover o bloco duplicado inicial das definições de elasticidade (`ResponseMeta`, `ProductHeader`, `CustomerElasticityItem`, `ProductElasticityDetail`, `ProductElasticityResponse`, `CustomerElasticityDetail`, `CustomerElasticityResponse`, `ElasticitySimulationRequest`, `ElasticitySimulationResponse` — linhas 295–371 legadas com `elasticity: dict` / `data: dict`), mantendo **uma única definição tipada** de cada schema com `ProductElasticityMetrics` e `SimulationImpactData`.

### Endpoints da Feature

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/elasticity/product/{sku}` | Elasticidade agregada do produto, cabeçalho com baseline 60d/custo/estoque e lista paginada | P-095 a P-100, P-103 |
| `GET` | `/api/v1/analytics/elasticity/product/{sku}/customer/{customerCode}` | Elasticidade refinada do par produto × cliente via shrinkage (mantido por retrocompatibilidade da API) | P-097, P-098, P-104 |
| `POST` | `/api/v1/analytics/elasticity/simulate` | Simulação de impacto de preço e custo editável sobre volume 60d, margem unitária/total e dias de estoque | P-101 |

---

## 2. Modelos de Dados e Schemas

### 2.1 Envelopes Padrão

```json
// Sucesso (2xx)
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-11-16T12:00:00Z",
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
    "timestamp": "2026-11-16T12:00:00Z",
    "version": "1.0.0"
  }
}
```

### 2.2 Campos de `ProductHeader` (Extensão Retrocompatível)

| Campo JSON | Atributo Python | Tipo | Default | Descrição |
| :--- | :--- | :--- | :---: | :--- |
| `code` | `code` | `int` | *(obrigatório)* | Código do SKU |
| `description` | `description` | `str` | *(obrigatório)* | Descrição do produto |
| `supplier` | `supplier` | `str` | *(obrigatório)* | Nome do fornecedor / fabricante |
| `currentPrice` | `current_price` | `float` | *(obrigatório)* | Preço de venda praticado atual (`Pc.Venda`) |
| `costPrice` | `cost_price` | `float` | *(obrigatório)* | Custo unitário resolvido (`Pc.Ultimo Custo` ou fallback `60%`) |
| `stock` | `stock` | `float` | *(obrigatório)* | Estoque disponível atual (`Estoque`) |
| `isCostEstimated` | `is_cost_estimated` | `bool` | `False` | `true` se o custo do catálogo veio do fallback de `60%` (`[Pc.Ultimo Custo] <= 0`) |
| `recentVolume60d` | `recent_volume_60d` | `float` | `0.0` | Volume líquido de vendas nos últimos 60 dias (`VENDA - DEVOLU%`, mínimo `0.0`) |
| `stockTargetDays` | `stock_target_days` | `int` | `60` | Meta corporativa de cobertura de estoque em dias (`STOCK_TARGET_DAYS = 60`) |

### 2.3 Campos de `ElasticitySimulationRequest`

| Campo JSON | Atributo Python | Tipo | Validação / Default | Descrição |
| :--- | :--- | :--- | :---: | :--- |
| `sku` | `sku` | `int` | `gt=0` (obrigatório) | Código do produto avaliado |
| `customerCode` | `customer_code` | `int \| null` | `gt=0`, default `None` | Código do cliente opcional (retrocompatível; omitido na UI v3) |
| `priceChangePct` | `price_change_pct` | `float` | `ge=-50.0, le=100.0` (obrigatório) | Variação percentual de preço pretendida |
| `costPrice` | `cost_price` | `float \| null` | `ge=0.0`, default `None` | Custo unitário manual opcional em R$; se omitido/`null`, usa custo de catálogo (ou fallback `60%`) |

### 2.4 Campos de `SimulationImpactData` (Extensão Retrocompatível)

| Campo JSON | Atributo Python | Tipo | Default | Descrição |
| :--- | :--- | :--- | :---: | :--- |
| `sku` | `sku` | `int` | *(obrigatório)* | Código do produto |
| `customerCode` | `customer_code` | `int \| null` | `None` | Código do cliente quando individualizado |
| `appliedElasticity` | `applied_elasticity` | `float` | *(obrigatório)* | Elasticidade (`beta`) aplicada na projeção |
| `priceChangePct` | `price_change_pct` | `float` | *(obrigatório)* | Percentual de variação de preço informado |
| `currentPrice` | `current_price` | `float` | *(obrigatório)* | Preço de venda atual (`R$`) |
| `projectedPrice` | `projected_price` | `float` | *(obrigatório)* | Preço de venda projetado (`R$`) |
| `currentVolume` | `current_volume` | `float` | *(obrigatório)* | Volume baseline no ciclo de 60 dias (`recentVolume60d`, ou volume do cliente se `customerCode` informado) |
| `projectedVolume` | `projected_volume` | `float` | *(obrigatório)* | Volume projetado no ciclo (`un.`) |
| `volumeChangePct` | `volume_change_pct` | `float` | *(obrigatório)* | Variação percentual de volume (`%`) |
| `currentRevenue` | `current_revenue` | `float` | *(obrigatório)* | Faturamento baseline (`R$`) |
| `projectedRevenue` | `projected_revenue` | `float` | *(obrigatório)* | Faturamento projetado (`R$`) |
| `revenueChangePct` | `revenue_change_pct` | `float` | *(obrigatório)* | Variação percentual de faturamento (`%`) |
| `revenueChangeAbs` | `revenue_change_abs` | `float` | *(obrigatório)* | Variação monetária de faturamento (`R$`) |
| `currentMargin` | `current_margin` | `float` | *(obrigatório)* | Lucro bruto total atual no ciclo (`Margem de Contribuição`, `R$`) |
| `projectedMargin` | `projected_margin` | `float` | *(obrigatório)* | Lucro bruto total projetado no ciclo (`R$`) |
| `marginChangePct` | `margin_change_pct` | `float` | *(obrigatório)* | Variação percentual de lucro bruto total (`%`) |
| `marginChangeAbs` | `margin_change_abs` | `float` | *(obrigatório)* | Variação monetária de lucro bruto total (`R$`) |
| `recommendation` | `recommendation` | `str` | *(obrigatório)* | Recomendação comercial do cenário |
| `costPrice` | `cost_price` | `float` | `0.0` | Custo unitário efetivamente utilizado na simulação (`R$`) |
| `isCostEstimated` | `is_cost_estimated` | `bool` | `False` | `true` se usou fallback de `60%` sem override manual |
| `isCostOverride` | `is_cost_override` | `bool` | `False` | `true` se o usuário informou `costPrice` manualmente |
| `stock` | `stock` | `float` | `0.0` | Estoque disponível atual do SKU (`un.`) |
| `stockTargetDays` | `stock_target_days` | `int` | `60` | Meta de cobertura de estoque em dias (`60`) |
| `currentUnitMargin` | `current_unit_margin` | `float` | `0.0` | Margem unitária atual (`currentPrice - costPrice`, `R$/un.`) |
| `projectedUnitMargin` | `projected_unit_margin` | `float` | `0.0` | Margem unitária projetada (`projectedPrice - costPrice`, `R$/un.`) |
| `currentUnitMarginPct` | `current_unit_margin_pct` | `float` | `0.0` | Margem unitária percentual atual (`%` sobre `currentPrice`) |
| `projectedUnitMarginPct` | `projected_unit_margin_pct` | `float` | `0.0` | Margem unitária percentual projetada (`%` sobre `projectedPrice`) |
| `unitMarginPctChangePp` | `unit_margin_pct_change_pp` | `float` | `0.0` | Variação da margem unitária em pontos percentuais (`p.p.`) |
| `volumeChangeUnits` | `volume_change_units` | `float` | `0.0` | Variação absoluta de volume (`projectedVolume - currentVolume`, `un.`) |
| `currentDailyUnits` | `current_daily_units` | `float` | `0.0` | Ritmo diário atual (`currentVolume / 60`, `un./dia`) |
| `projectedDailyUnits` | `projected_daily_units` | `float` | `0.0` | Ritmo diário projetado (`projectedVolume / 60`, `un./dia`) |
| `currentStockDays` | `current_stock_days` | `float \| null` | `None` | Duração estimada do estoque hoje (`0%`) em dias; `null` se `currentDailyUnits <= 0` |
| `projectedStockDays` | `projected_stock_days` | `float \| null` | `None` | Duração estimada do estoque após o reajuste em dias; `null` se `projectedDailyUnits <= 0` |
| `stockDaysDelta` | `stock_days_delta` | `float \| null` | `None` | Variação na duração do estoque em dias (`projectedStockDays - currentStockDays`); `null` se algum dos dois for `null` |

---

## 3. Especificação dos Endpoints

### 3.1 `GET /api/v1/analytics/elasticity/product/{sku}`

Retorna os parâmetros de elasticidade estimados para o produto, o cabeçalho comercial com custo/origem, estoque e vendas líquidas dos últimos 60 dias (`recentVolume60d`), além da listagem paginada de clientes (mantida por compatibilidade de contrato).

#### Parâmetros de Path e Query
- `sku` (path, int, `1..2147483647`): Código do produto consultado.
- `limit` (query, int, `1..200`, default `50`): Tamanho da página da lista de clientes.
- `offset` (query, int, `>= 0`, default `0`): Deslocamento da paginação de clientes.

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
      "stock": 420.0,
      "isCostEstimated": false,
      "recentVolume60d": 360.0,
      "stockTargetDays": 60
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
      "insightMessage": "Demanda elástica: sensibilidade alta a preço; elevações tendem a reduzir o volume comercializado."
    },
    "customers": [
      {
        "customerCode": 4501,
        "ordersCount": 12,
        "totalUnits": 350.0,
        "empiricalElasticity": -1.60,
        "shrinkageElasticity": -1.52,
        "classification": "ELASTICO",
        "shrinkageWeight": 0.55
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-16T12:00:00Z",
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

Mantido intacto para compatibilidade retroativa da API e cobertura de testes (`test_elasticity_api.py`).

#### Parâmetros de Path
- `sku` (path, int, `1..2147483647`): Código do produto.
- `customerCode` (path, int, `1..2147483647`): Código do cliente.

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
    "totalUnits": 350.0,
    "confidenceLevel": "MEDIA",
    "isReliable": true,
    "insightMessage": "Cliente com 12 pedidos analisados; elasticidade refinada via shrinkage para -1.52."
  },
  "meta": {
    "timestamp": "2026-11-16T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

### 3.3 `POST /api/v1/analytics/elasticity/simulate`

Simula o impacto em volume (baseline 60 dias), faturamento, margem unitária (`R$/un.`, `%`, `p.p.`), lucro bruto total e cobertura de estoque em dias contra a meta de 60 dias, aceitando custo unitário manual opcional (`costPrice >= 0`).

#### Payload de Requisição
```json
{
  "sku": 1001,
  "priceChangePct": 5.0,
  "costPrice": 13.50
}
```
> *Nota:* `customerCode` (opcional `> 0`) e `costPrice` (opcional `>= 0`) podem ser omitidos ou enviados como `null`.

#### Exemplo de Resposta 200 OK
```json
{
  "data": {
    "sku": 1001,
    "customerCode": null,
    "appliedElasticity": -1.45,
    "priceChangePct": 5.0,
    "currentPrice": 25.50,
    "projectedPrice": 26.78,
    "currentVolume": 360.0,
    "projectedVolume": 333.9,
    "volumeChangePct": -7.25,
    "volumeChangeUnits": -26.1,
    "currentRevenue": 9180.0,
    "projectedRevenue": 8941.84,
    "revenueChangePct": -2.59,
    "revenueChangeAbs": -238.16,
    "currentMargin": 4320.0,
    "projectedMargin": 4434.19,
    "marginChangePct": 2.64,
    "marginChangeAbs": 114.19,
    "costPrice": 13.50,
    "isCostEstimated": false,
    "isCostOverride": true,
    "stock": 420.0,
    "stockTargetDays": 60,
    "currentUnitMargin": 12.00,
    "projectedUnitMargin": 13.28,
    "currentUnitMarginPct": 47.06,
    "projectedUnitMarginPct": 49.59,
    "unitMarginPctChangePp": 2.53,
    "currentDailyUnits": 6.0,
    "projectedDailyUnits": 5.565,
    "currentStockDays": 70.0,
    "projectedStockDays": 75.5,
    "stockDaysDelta": 5.5,
    "recommendation": "Reajuste viável com expansão de margem financeira líquida."
  },
  "meta": {
    "timestamp": "2026-11-16T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

## 4. Tabela de Códigos de Erro

| Código | Status HTTP | Causa / Mensagem Padronizada |
| :--- | :---: | :--- |
| `ELA-001` | 404 | Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade. |
| `ELA-002` | 404 | Cliente sem compras registradas para este produto. |
| `ELA-003` | 422 | Histórico de vendas insuficiente para estimar elasticidade do produto. |
| `ELA-004` | 400 | Parâmetros inválidos fornecidos para consulta ou simulação de elasticidade (ex.: `priceChangePct` fora de `[-50, 100]`, `costPrice < 0`, `sku <= 0`). |
| `ANL-001` | 503 | Base de dados de vendas temporariamente indisponível. |

---

## 5. Diretrizes de Integração no Frontend

- **Serviço:** `frontend/src/app/features/analytics/services/analytics.service.ts` (`getProductElasticity(sku, page)`, `simulatePriceChange(request)`).
- **Modelos TypeScript (`frontend/src/app/features/analytics/models/elasticity.models.ts`):**
```typescript
export interface ProductHeader {
  code: number;
  description: string;
  supplier: string;
  currentPrice: number;
  costPrice: number;
  stock: number;
  isCostEstimated?: boolean;
  recentVolume60d?: number;
  stockTargetDays?: number;
}

export interface ElasticitySimulationRequest {
  sku: number;
  customerCode?: number | null;
  priceChangePct: number;
  costPrice?: number | null;
}

export interface SimulationImpactData {
  sku: number;
  customerCode?: number | null;
  appliedElasticity: number;
  priceChangePct: number;
  currentPrice: number;
  projectedPrice: number;
  currentVolume: number;
  projectedVolume: number;
  volumeChangePct: number;
  currentRevenue: number;
  projectedRevenue: number;
  revenueChangePct: number;
  revenueChangeAbs: number;
  currentMargin: number;
  projectedMargin: number;
  marginChangePct: number;
  marginChangeAbs: number;
  recommendation: string;
  costPrice?: number;
  isCostEstimated?: boolean;
  isCostOverride?: boolean;
  stock?: number;
  stockTargetDays?: number;
  currentUnitMargin?: number;
  projectedUnitMargin?: number;
  currentUnitMarginPct?: number;
  projectedUnitMarginPct?: number;
  unitMarginPctChangePp?: number;
  volumeChangeUnits?: number;
  currentDailyUnits?: number;
  projectedDailyUnits?: number;
  currentStockDays?: number | null;
  projectedStockDays?: number | null;
  stockDaysDelta?: number | null;
}
```
> *Nota:* Os novos campos nas interfaces TypeScript podem ser opcionais ou normalizados com fallback seguro em helpers puros (`elasticity-view.ts`) para manter compatibilidade com mocks de testes existentes.
