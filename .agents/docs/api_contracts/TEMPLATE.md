# Contrato de API: [Nome da Entidade/Feature]

> **Localização Mandatória:** `.agents/docs/api_contracts/<nome-da-entidade-ou-feature>.md`  
> **Responsável:** Arquiteto (`api-contract-expert`)  
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`

---

## 1. Visão Geral
- **Prefixo Base da Rota:** `/api/v1/[recurso]`
- **Protocolo:** HTTP/REST (ou WebSocket / SSE se streaming)
- **Convenção de Nomenclatura:** `snake_case` (Python/FastAPI) ou `camelCase` (Node/Java) — [Defina o padrão unificado aqui]
- **Formato dos Dados:** `application/json`

---

## 2. Padrão de Envelope de Resposta

> [!IMPORTANT]
> Conforme `.agents/rules/backend-api-contract-rules.md`, nenhuma resposta HTTP 2xx deve retornar dados soltos na raiz. O envelope é obrigatório.

```json
{
  "data": {},
  "meta": {
    "timestamp": "2026-09-10T16:00:00Z",
    "page": 1,
    "total_items": 100
  }
}
```

---

## 3. Endpoints

### 3.1. `GET /api/v1/[recurso]`
- **Objetivo:** Listar registros com paginação obrigatória.
- **Autenticação:** `Bearer <JWT_TOKEN>` (ou pública se indicado)

**Query Parameters:**
| Parâmetro | Tipo | Obrigatório? | Default | Descrição |
| :--- | :--- | :--- | :--- | :--- |
| `page` | `integer` | Não | `1` | Número da página solicitada |
| `page_size` | `integer` | Não | `20` | Quantidade de itens por página (máx: 100) |
| `status` | `string` | Não | `null` | Filtro por status do registro |

**Resposta de Sucesso (`200 OK`):**
```json
{
  "data": [
    {
      "id": "a1b2c3d4-0000-0000-0000-000000000001",
      "name": "Exemplo",
      "status": "ACTIVE",
      "created_at": "2026-09-10T16:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_items": 1,
    "total_pages": 1
  }
}
```

---

### 3.2. `POST /api/v1/[recurso]`
- **Objetivo:** Criar um novo registro atendendo às regras `P-XXX`.
- **Autenticação:** `Bearer <JWT_TOKEN>`
- **Headers:** `Content-Type: application/json`

**Payload de Requisição (Request Body):**
```json
{
  "name": "Nome do Objeto",
  "category_id": "b2c3d4e5-0000-0000-0000-000000000001"
}
```

**Resposta de Sucesso (`201 Created`):**
```json
{
  "data": {
    "id": "a1b2c3d4-0000-0000-0000-000000000001",
    "name": "Nome do Objeto",
    "status": "ACTIVE",
    "created_at": "2026-09-10T16:00:00Z"
  }
}
```

---

## 4. Matriz de Erros HTTP Mapeados

| Status Code | Causa | Formato do Payload |
| :--- | :--- | :--- |
| `400 Bad Request` | Parâmetros inválidos ou schema violado | `{"error": "Validation Error", "details": [...]}` |
| `401 Unauthorized` | Token ausente, expirado ou inválido | `{"error": "Unauthorized", "message": "Token expired"}` |
| `403 Forbidden` | Usuário autenticado sem permissão | `{"error": "Forbidden", "message": "Access denied"}` |
| `404 Not Found` | Recurso não localizado | `{"error": "Not Found", "message": "Resource not found"}` |
| `409 Conflict` | Conflito de integridade (ex: duplicidade) | `{"error": "Conflict", "message": "Already exists"}` |
| `422 Unprocessable` | Quebra de regra de negócio (`P-XXX`) | `{"error": "Business Rule Violation", "rule": "P-001"}` |

---

## 5. Diretrizes de Integração no Frontend
- **Serviço/Client:** [Ex: `resources.service.ts` ou `apiClient.ts`]
- **Gestão de Estado:** Estados esperados `loading`, `success`, `error`.
- **Tipagem (TypeScript):**
```typescript
export interface ResourceResponse {
  data: ResourceItem[];
  meta: ResponseMeta;
}
```
