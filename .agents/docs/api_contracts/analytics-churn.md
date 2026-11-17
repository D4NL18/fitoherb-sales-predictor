# Contrato de API: Analytics Comercial — Churn de Clientes (FASE F3)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-churn.md`  
> **Responsável:** Arquiteto (`api-contract-expert`)  
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`  

| Campo | Valor |
| :--- | :--- |
| **Módulo backend** | `src/modules/analytics/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/analytics/` (Angular 18) |
| **Versão do contrato** | **1.0.0** (`meta.version = "1.0.0"`) |
| **Regras** | P-117 a P-127 (`business_rules/analytics-churn.md`) |
| **Decisões** | `adr/ADR-006-churn-clientes.md` (DA-01 a DA-08) |
| **Privacidade** | `privacy/analytics-churn.md` |
| **Autenticação** | HTTP Basic global ativo em produção (`HTTPBasicAuthASGIMiddleware`) |

---

## 1. Visão Geral dos Endpoints

- **Prefixo Base:** `/api/v1/analytics/churn`
- **Protocolo:** HTTP/REST, `application/json; charset=utf-8`
- **Nomenclatura:** `camelCase` em todos os campos JSON (Pydantic com `to_camel`)
- **Minimização LGPD:** O único identificador do cliente é `customerCode` (inteiro). Nenhum nome pessoal, razão social, documento, endereço ou e-mail é exposto.

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/customers` | Listagem priorizada de clientes por score de retenção | P-117 a P-124 |
| `GET` | `/customers/{customerCode}` | Detalhes explicativos, decomposição e produtos perdidos | P-126 |
| `GET` | `/inactive` | Fila especializada de clientes inativos antigos (> 180 dias) | P-125 |

---

## 2. Envelopes Padrão de Resposta

### 2.1 Metadados Paginados (`PagedMeta`)
```json
{
  "timestamp": "2026-11-12T12:00:00Z",
  "version": "1.0.0",
  "dataReferencia": "2026-11-12",
  "limit": 50,
  "offset": 0,
  "totalItems": 350,
  "totalPages": 7
}
```

### 2.2 Formato Geral de Erro
```json
{
  "error": {
    "code": "CHU-001",
    "message": "Cliente não encontrado ou sem histórico de compras válidas.",
    "fields": []
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0"
  }
}
```

---

## 3. Especificação dos Endpoints

### 3.1 `GET /api/v1/analytics/churn/customers`
Lista clientes da carteira classificados conforme o status de churn, ordenados decrescentemente por `scorePrioridade`.

#### Parâmetros de Query
| Parâmetro | Tipo | Obrigatório | Padrão | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `status` | string | Não | `EM_RISCO` | Enum: `EM_RISCO`, `ALERTA`, `SAUDAVEL`, `TODOS` | Filtro por status de risco |
| `limit` | int | Não | `50` | $1 \le \text{limit} \le 200$ | Itens por página |
| `offset` | int | Não | `0` | $\ge 0$ | Deslocamento inicial |

#### Resposta de Sucesso `200 OK`
```json
{
  "data": {
    "resumo": {
      "totalEmRisco": 350,
      "totalAlerta": 210,
      "totalSaudavel": 1400,
      "totalInativos": 1402,
      "receitaMensalEmRisco": 1854200.50
    },
    "items": [
      {
        "customerCode": 1042,
        "status": "EM_RISCO",
        "diasSemComprar": 74,
        "gapTipico": 18.5,
        "diasReferencia": 60,
        "fatorTempo": 1.23,
        "faturamentoMedioMensal": 48250.00,
        "scorePrioridade": 59347.50,
        "historicoCurto": false
      },
      {
        "customerCode": 2891,
        "status": "EM_RISCO",
        "diasSemComprar": 65,
        "gapTipico": null,
        "diasReferencia": 60,
        "fatorTempo": 1.08,
        "faturamentoMedioMensal": 12400.00,
        "scorePrioridade": 13392.00,
        "historicoCurto": true
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-12",
    "limit": 50,
    "offset": 0,
    "totalItems": 350,
    "totalPages": 7
  }
}
```

---

### 3.2 `GET /api/v1/analytics/churn/customers/{customerCode}`
Devolve o diagnóstico explicativo detalhado para o cliente consultado.

#### Parâmetros de Path
| Parâmetro | Tipo | Validação | Descrição |
| :--- | :--- | :--- | :--- |
| `customerCode` | int | $1 \le \text{code} \le 2.147.483.647$ | Identificador do cliente no ERP |

#### Resposta de Sucesso `200 OK`
```json
{
  "data": {
    "customerCode": 1042,
    "status": "EM_RISCO",
    "diasSemComprar": 74,
    "dataUltimoPedido": "2026-08-30",
    "gapTipico": 18.5,
    "diasReferencia": 60,
    "fatorTempo": 1.23,
    "faturamentoMedioMensal": 48250.00,
    "scorePrioridade": 59347.50,
    "historicoCurto": false,
    "variacaoReceitaTrimestralPct": -38.4,
    "historicoMensal": [
      { "anoMes": "2025-12", "faturamentoLiquido": 51200.00, "qtdPedidos": 3 },
      { "anoMes": "2026-01", "faturamentoLiquido": 49100.00, "qtdPedidos": 2 }
    ],
    "produtosPerdidos": [
      {
        "sku": 501,
        "descricao": "EXTRATO DE PROPOLIS VERDE 30ML",
        "fornecedor": "APIS FLORA",
        "faturamentoHistorico": 14200.00,
        "dataUltimaCompra": "2026-06-15"
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-12"
  }
}
```

#### Respostas de Erro
- `404 Not Found` (`CHU-001`): Cliente não encontrado ou sem pedidos válidos de venda.
- `400 Bad Request` (`CHU-003`): `customerCode` fora dos limites permitidos.

---

### 3.3 `GET /api/v1/analytics/churn/inactive`
Lista clientes inativos antigos ($\text{diasSemComprar} > 180$), ordenados decrescentemente por faturamento histórico médio.

#### Parâmetros de Query
| Parâmetro | Tipo | Padrão | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `limit` | int | `50` | $1 \le \text{limit} \le 200$ | Tamanho da página |
| `offset` | int | `0` | $\ge 0$ | Deslocamento da listagem |

#### Resposta de Sucesso `200 OK`
```json
{
  "data": {
    "totalInativos": 1402,
    "items": [
      {
        "customerCode": 308,
        "status": "INATIVO_RECUPERACAO",
        "diasSemComprar": 245,
        "dataUltimoPedido": "2026-03-12",
        "faturamentoMedioMensal": 32100.00,
        "historicoCurto": false
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-12",
    "limit": 50,
    "offset": 0,
    "totalItems": 1402,
    "totalPages": 29
  }
}
```

---

## 4. Códigos de Erro Internos (CHU-XXX)

| Código | HTTP | Motivo | Ação Recomendada |
| :--- | :--- | :--- | :--- |
| `CHU-001` | `404 Not Found` | Cliente não existe no ERP ou não possui compras de VENDA. | Verificar código consultado. |
| `CHU-002` | `422 Unprocessable` | Base analítica sem registros de vendas válidos. | Aguardar carga ou verificar conexão do banco. |
| `CHU-003` | `400 Bad Request` | Parâmetros de requisição inválidos (status, paginação). | Corrigir valores passados na rota ou query string. |
| `ANL-001` | `503 Service Unavailable` | Falha de infraestrutura/conexão com banco de dados. | Verificar disponibilidade do SQL Server. |
