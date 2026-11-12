# Contrato de API: Analytics Comercial — Canibalização e Substituição (F6)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-canibalizacao.md`  
> **Responsável:** Arquiteto (`api-contract-expert` / `architect.md`)  
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `.agents/rules/architecture-error-handling-rules.md`, `business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`), `ADR-007-canibalizacao.md`

---

## 1. Visão Geral

- **Prefixo Base da Rota:** `/api/v1/analytics`
- **Protocolo:** HTTP/REST
- **Convenção de Nomenclatura:** `camelCase` rigoroso em todas as chaves JSON de request e response.
- **Formato dos Dados:** `application/json; charset=utf-8`
- **Autenticação:** HTTP Basic Auth (padrão `src/core/auth.py` herdado globalmente).
- **Tratamento de Erros:** Exceções de domínio mapeadas para códigos internos `CAN-001` a `CAN-005` com status HTTP semântico, sem exposição de stacktrace.

---

## 2. Padrão de Envelope de Resposta

Conforme `.agents/rules/backend-api-contract-rules.md`, nenhuma resposta HTTP 2xx deve retornar dados soltos na raiz. O envelope `{ "data": ..., "meta": ... }` é obrigatório.

```json
{
  "data": {},
  "meta": {
    "timestamp": "2026-11-12T14:30:00Z",
    "sku": "100234",
    "eventType": "promo",
    "windowWeeks": 4
  }
}
```

---

## 3. Endpoints

### 3.1. `GET /api/v1/analytics/cannibalization/{sku}`

- **Objetivo:** Analisar a canibalização e o efeito de rede provocado por uma ação comercial no SKU alvo (promoção, alteração de preço ou lançamento), confrontando contra o grupo de controle categorial via Diferença em Diferenças (DiD) e reportando o impacto líquido consolidado.
- **Regras de Negócio:** `P-128` a `P-138`.

#### Parâmetros de Rota (Path Parameters)
| Parâmetro | Tipo | Obrigatório? | Descrição |
| :--- | :--- | :--- | :--- |
| `sku` | `string` | Sim | Código do produto alvo analisado (ex: `"100234"`). Validação: numérico ou alfanumérico não-vazio. |

#### Parâmetros de Consulta (Query Parameters)
| Parâmetro | Tipo | Obrigatório? | Default | Validação / Limites | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `eventType` | `string` | Não | `"promo"` | Enum: `promo`, `price`, `launch` | Tipo de evento que motivou a análise. |
| `eventDate` | `string` (date) | Não | `null` | Formato `YYYY-MM-DD` | Data de referência do evento ($T_0$). Se omitida, seleciona o evento mais recente detectado no histórico. |
| `windowWeeks` | `integer` | Não | `4` | Mín: `2`, Máx: `12` | Tamanho da janela simétrica de análise em semanas (pré e pós evento). |
| `includeNonSignificant` | `boolean` | Não | `false` | `true` ou `false` | Se `true`, inclui também produtos com classificação `SEM_EFEITO` na listagem detalhada. |

#### Resposta de Sucesso (`200 OK`)

```json
{
  "data": {
    "targetProduct": {
      "sku": "100234",
      "description": "EXTRATO DE PROPOLIS VERDE 30ML",
      "category": "EXTRATOS",
      "eventType": "promo",
      "eventDate": "2026-09-01",
      "prePeriod": {
        "startDate": "2026-08-04",
        "endDate": "2026-08-31",
        "volume": 420.0,
        "avgPrice": 24.50,
        "revenue": 10290.00,
        "estimatedMargin": 4116.00
      },
      "postPeriod": {
        "startDate": "2026-09-01",
        "endDate": "2026-09-28",
        "volume": 980.0,
        "avgPrice": 18.90,
        "revenue": 18522.00,
        "estimatedMargin": 4900.00
      },
      "deltaVolume": 560.0,
      "deltaVolumePct": 133.33,
      "deltaRevenue": 8232.00,
      "deltaMargin": 784.00
    },
    "controlGroup": {
      "category": "EXTRATOS",
      "sampleSize": 14,
      "growthFactor": 1.05,
      "controlStrategy": "CATEGORIAL",
      "description": "14 produtos estáveis da categoria EXTRATOS sem promoções ou alterações de preço no período."
    },
    "affectedProducts": [
      {
        "sku": "100235",
        "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.42,
        "commonBuyersCount": 38,
        "preVolume": 310.0,
        "postVolume": 165.0,
        "counterfactualVolume": 325.5,
        "deltaVolume": -160.5,
        "deltaVolumePct": -49.31,
        "unitPrice": 22.00,
        "unitMargin": 9.50,
        "deltaRevenue": -3531.00,
        "deltaMargin": -1524.75,
        "classification": "CANIBALIZACAO",
        "pValue": 0.0018,
        "qValue": 0.0072,
        "isSignificant": true,
        "confidenceInterval": [-192.0, -129.0],
        "elasticityDecomposition": null
      },
      {
        "sku": "100288",
        "description": "EXTRATO DE EQUINACEA 30ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.28,
        "commonBuyersCount": 21,
        "preVolume": 180.0,
        "postVolume": 110.0,
        "counterfactualVolume": 189.0,
        "deltaVolume": -79.0,
        "deltaVolumePct": -41.80,
        "unitPrice": 28.00,
        "unitMargin": 12.00,
        "deltaRevenue": -2212.00,
        "deltaMargin": -948.00,
        "classification": "CANIBALIZACAO",
        "pValue": 0.0094,
        "qValue": 0.0188,
        "isSignificant": true,
        "confidenceInterval": [-104.0, -54.0],
        "elasticityDecomposition": null
      },
      {
        "sku": "100512",
        "description": "SPRAY BUCAL PROPOLIS E GENGIBRE 35ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.31,
        "commonBuyersCount": 29,
        "preVolume": 95.0,
        "postVolume": 145.0,
        "counterfactualVolume": 99.75,
        "deltaVolume": 45.25,
        "deltaVolumePct": 45.36,
        "unitPrice": 16.50,
        "unitMargin": 6.80,
        "deltaRevenue": 746.63,
        "deltaMargin": 307.70,
        "classification": "COMPLEMENTO",
        "pValue": 0.0120,
        "qValue": 0.0192,
        "isSignificant": true,
        "confidenceInterval": [22.0, 68.5],
        "elasticityDecomposition": null
      }
    ],
    "netImpact": {
      "targetDeltaVolume": 560.0,
      "affectedDeltaVolume": -194.25,
      "netDeltaVolume": 365.75,
      "targetDeltaRevenue": 8232.00,
      "affectedDeltaRevenue": -4996.37,
      "netDeltaRevenue": 3235.63,
      "targetDeltaMargin": 784.00,
      "affectedDeltaMargin": -2165.05,
      "netDeltaMargin": -1381.05,
      "commercialVerdict": "ILUSAO_DE_VOLUME",
      "summaryMessage": "A promoção aumentou o giro em +365,75 unidades e o faturamento em +R$ 3.235,63, mas destruiu -R$ 1.381,05 de margem líquida ao canibalizar itens de maior valor agregado (Própolis Aquoso e Equinácea)."
    },
    "elasticityIntegration": {
      "status": "NAO_INTEGRADO",
      "message": "Módulo de Elasticidade-Preço (Fase F5) ainda não acoplado. Decomposição de choque de preço operando em modo gracioso."
    }
  },
  "meta": {
    "timestamp": "2026-11-12T14:30:00Z",
    "sku": "100234",
    "eventType": "promo",
    "windowWeeks": 4,
    "executionTimeMs": 84
  }
}
```

---

### 3.2. `GET /api/v1/analytics/substitution/{sku}`

- **Objetivo:** Listar os produtos substitutos diretos do SKU alvo com base em similaridade de categoria (`Tipo`) e sobreposição de compradores (Jaccard), com dados de estoque atual e preço de venda.
- **Regras de Negócio:** `P-128`.

#### Parâmetros de Rota (Path Parameters)
| Parâmetro | Tipo | Obrigatório? | Descrição |
| :--- | :--- | :--- | :--- |
| `sku` | `string` | Sim | Código do produto alvo (ex: `"100234"`). |

#### Parâmetros de Consulta (Query Parameters)
| Parâmetro | Tipo | Obrigatório? | Default | Validação / Limites | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `minJaccard` | `float` | Não | `0.15` | Mín: `0.05`, Máx: `0.50` | Limiar mínimo de similaridade de Jaccard. |
| `limit` | `integer` | Não | `20` | Mín: `1`, Máx: `50` | Quantidade máxima de substitutos retornados. |

#### Resposta de Sucesso (`200 OK`)

```json
{
  "data": {
    "targetSku": "100234",
    "targetDescription": "EXTRATO DE PROPOLIS VERDE 30ML",
    "targetCategory": "EXTRATOS",
    "targetCurrentPrice": 24.50,
    "targetStock": 340,
    "substitutes": [
      {
        "sku": "100235",
        "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.42,
        "commonBuyersCount": 38,
        "currentPrice": 22.00,
        "currentStock": 185
      },
      {
        "sku": "100288",
        "description": "EXTRATO DE EQUINACEA 30ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.28,
        "commonBuyersCount": 21,
        "currentPrice": 28.00,
        "currentStock": 92
      },
      {
        "sku": "100240",
        "description": "EXTRATO DE PROPOLIS VERMELHO 30ML",
        "category": "EXTRATOS",
        "jaccardSimilarity": 0.22,
        "commonBuyersCount": 16,
        "currentPrice": 32.00,
        "currentStock": 45
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T14:30:00Z",
    "targetSku": "100234",
    "totalFound": 3,
    "executionTimeMs": 28
  }
}
```

---

## 4. Matriz de Erros HTTP e Payloads de Falha

| Código HTTP | Código Interno | Causa Raiz | Exemplo de Mensagem Amigável |
| :--- | :--- | :--- | :--- |
| **`400 Bad Request`** | `CAN-004` | Parâmetro de query inválido (ex: `eventType=invalido`, `windowWeeks=20`, `eventDate` malformada). | `"O parâmetro windowWeeks deve estar entre 2 e 12 semanas."` |
| **`404 Not Found`** | `CAN-001` | SKU alvo não existe no catálogo ativo da Fitoherb. | `"Produto de código 999999 não localizado no catálogo ativo."` |
| **`422 Unprocessable`**| `CAN-002` | Evento especificado não localizado no histórico transacional do produto. | `"Nenhum evento promocional recente registrado para o produto informado."` |
| **`422 Unprocessable`**| `CAN-003` | Histórico de vendas insuficiente para formar janelas pré/pós ou tamanho de controle inválido. | `"Histórico transacional insuficiente para compor as janelas pré e pós de 4 semanas."` |
| **`500 Internal Error`**| `CAN-005` | Falha de conectividade com o SQL Server ou erro interno não tratado. | `"Não foi possível processar a análise de canibalização no momento. Tente novamente mais tarde."` |

### Formato de Erro Padronizado (HTTP 4xx / 5xx)

```json
{
  "error": {
    "code": "CAN-002",
    "message": "Nenhum evento promocional recente registrado para o produto informado.",
    "details": {
      "sku": "100234",
      "eventType": "promo",
      "suggestion": "Tente informar eventType=price para analisar variações de preço regulares ou informe uma data explícita via eventDate."
    }
  }
}
```

---

## 5. Garantias de Segurança e Não Vazamento

1. **Zero Stacktraces:** Em hipótese alguma o payload de retorno conterá rastreamento de pilha (stacktrace), nomes de classes internas ou fragments de código Python.
2. **Sanitização de Driver:** Mensagens de erro de banco (`pyodbc.Error`) são interceptadas na camada de infraestrutura e mascaradas sob `CAN-005`.
3. **Privacidade Preservada:** Os endpoints não contêm, não recebem e não devolvem nenhuma informação identificável de clientes (`Cod Cliente`, nomes, documentos ou e-mails).
