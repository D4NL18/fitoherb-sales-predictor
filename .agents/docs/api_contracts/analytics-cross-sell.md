# Contrato de API: Analytics Comercial — Cross-sell (+ fundação do módulo `analytics`)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-cross-sell.md`
> **Responsável:** Arquiteto (`api-contract-expert`)
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Módulo backend** | `src/modules/analytics/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/analytics/` (Angular 18), único consumidor |
| **Versão do contrato** | **1.1.0** (`meta.version`, constante `ANALYTICS_CONTRACT_VERSION`) |
| **Regras** | P-058 a P-071 e P-094 (`business_rules/analytics-cross-sell.md`) |
| **Decisões** | `adr/ADR-002-modulo-analytics-cross-sell.md` (DA-01 a DA-12) |
| **Privacidade** | `privacy/analytics-cross-sell.md` (LGPD-01 a LGPD-12) |
| **Autenticação** | HTTP Basic do middleware global `HTTPBasicAuthASGIMiddleware`, ativo em produção (P-033). Vale para todas as rotas abaixo. Sem 401 específico do módulo. |
| **Autor / Data** | Arquiteto (Etapa 2) — 2026-11-05; revisão 1.1.0 pelo Orquestrador (Etapa 4) — 2026-11-10 |

### Changelog
| Versão | Data | Mudança |
| :--- | :--- | :--- |
| 1.0.0 | 2026-11-05 | Versão inicial (Etapa 2). |
| **1.1.0** | 2026-11-10 | **Curadoria das sugestões (P-094)**, pedida pelo usuário. Schema e campos não mudam (MINOR); mudam a ordenação e a cardinalidade documentadas das rotas §3.3 e §3.4: (a) variantes do produto de origem são omitidas; (b) ordem por faixa: mesmo fornecedor da origem → similar → demais, mantendo dentro da faixa a ordem de P-061.1 / P-064.2; (c) uma sugestão por linha de produto; (d) no máximo **10** itens. `meta.totalItems` e `totalPages` contam a lista curada. A tela deixou de exibir margem e números (os campos continuam na resposta). |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/analytics`
- **Protocolo:** HTTP/REST, `application/json; charset=utf-8`
- **Convenção de Nomenclatura:** `camelCase` em todos os payloads (atributos Python em `snake_case` com `alias_generator=to_camel`)
- **Identificação de cliente:** só `customerCode` (= `Cod Cliente`). Nenhum nome, documento, `UF`, contato, número de pedido ou data absoluta de compra em qualquer resposta (P-070, LGPD-03).

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/health` | Estado do cache, sem tocar no banco | P-069 |
| `POST` | `/api/v1/analytics/cache/reload` | Recarga manual da base (respeita o lock) | P-068.3 |
| `GET` | `/api/v1/analytics/cross-sell/product/{sku}` | Recomendação por produto | P-058 a P-061, P-065 a P-067 |
| `GET` | `/api/v1/analytics/cross-sell/customer/{customerCode}` | Recomendação por cliente | P-062 a P-067, P-070 |
| `GET` | `/api/v1/analytics/products/search?q=` | **Opcional, a decidir no checkpoint (DC-5).** Busca de produto por código ou descrição | Q-1 do Designer |

> A rota por cliente depende da decisão DC-1 do checkpoint (A-11). A proposta é manter GET com `customerCode` no path, como recomenda o parecer de privacidade (§4). A variante com `POST` está no Apêndice A.

### 1.1 Respostas às perguntas do Design Plan (`design/plans/analytics-cross-sell.md` §11)

| Pergunta | Resposta no contrato |
| :--- | :--- |
| Q-1 busca por descrição | `GET /products/search` especificado em 3.6 como **opcional** (DC-5), com custo estimado |
| Q-2 produto consultado | `data.produto { codigo, descricao, fornecedor }` sempre presente no modo produto, inclusive com `recomendacoes: []` (3.3) |
| Q-3 explicação | Frases separadas e prontas, montadas no domínio: `explicacao { frequencia, intensidade, evidencia, motivo }` (3.5) |
| Q-4 números no modo cliente | `pedidosEmComum` incluído; `suporte` **não** (métrica sem uso na tela do cliente; minimização) |
| Q-5 parâmetros para a copy | `meta.parametros` com os valores efetivos (2.3) nas rotas de cross-sell e no health |
| Q-6 corpo de erro | `{ error: { code, message, fields[] } }` em todos os erros; `fields` lista os nomes inválidos no 400 (§4) |
| Q-7 cache frio | `data.estadoCache` = `FRIO` \| `CARREGANDO` \| `QUENTE` \| `EXPIRADO`, `carregadoEm` (o `loadedAt`) e `duracaoUltimaCargaMs`, sem acessar o banco (3.1) |
| Eco do `customerCode` | **Não** é ecoado: a tela já o conhece; o parecer permite omitir (§3.2) |

---

## 2. Padrão de Envelope de Resposta

### 2.1 `meta` base (`AnalyticsMeta`) — toda resposta 2xx

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `timestamp` | string ISO-8601 UTC | Momento da resposta |
| `version` | string | `"1.1.0"` |
| `dataReferencia` | string `YYYY-MM-DD` \| `null` | Último dia incluído na base em cache. `null` só no health com cache vazio. |

### 2.2 `meta` de lista (`PagedMeta`, estende `AnalyticsMeta`) — P-066

| Campo | Tipo | Regra |
| :--- | :--- | :--- |
| `page` | int | `floor(offset ÷ limit) + 1` |
| `limit` | int | Valor efetivo (padrão 50) |
| `offset` | int | Valor efetivo (padrão 0) |
| `totalItems` | int | Itens após filtros de viabilidade, antes da paginação (P-063.5) |
| `totalPages` | int | `ceil(totalItems ÷ limit)`; 0 sem itens |
| `motivoVazio` | `"SEM_COMPRAS_RECENTES"` \| `null` | Só na rota por cliente (P-062.7). Sempre presente nessa rota, `null` quando não se aplica. |
| `parametros` | `CrossSellParameters` | Só nas rotas de cross-sell (ver abaixo) |

**`meta.parametros` (`CrossSellParameters`, Q-5).** Eco das constantes do domínio em vigor, para a tela interpolar textos ("não compra há mais de {dormantDays} dias") sem fixar números. Valores globais do módulo, sem dado de cliente.

| Campo | Tipo | Constante | Valor atual |
| :--- | :--- | :--- | :--- |
| `minLift` | number | `MIN_LIFT` | 1.2 |
| `minConfidence` | number | `MIN_CONFIDENCE` | 0.10 |
| `minPairOrders` | int | `MIN_PAIR_ORDERS` | 10 |
| `trivialItemSupport` | number | `TRIVIAL_ITEM_SUPPORT` | 0.15 |
| `dormantDays` | int | `DORMANT_DAYS` | 90 |
| `customerProfileDays` | int | `CUSTOMER_PROFILE_DAYS` | 365 |
| `cacheTtlHours` | int | `CACHE_TTL_HOURS` | 6 |

> Exceção de nomenclatura consciente: as chaves de `parametros` usam o nome em inglês das constantes do domínio (`dormantDays`, como pedido pelo Designer), para rastreio direto entre tela, contrato e código. Continuam em `camelCase`.

### 2.3 Paginação (query params das rotas de lista)

| Parâmetro | Tipo | Obrigatório? | Default | Faixa | Erro fora da faixa |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `limit` | integer | Não | `50` | 1 a 200 | 400 `XSL-004` (sem truncamento silencioso) |
| `offset` | integer | Não | `0` | ≥ 0 | 400 `XSL-004` |

`offset ≥ totalItems` → 200 com `recomendacoes: []` e totais corretos (P-066.4).

> Nota sobre o template: o projeto adota `limit`/`offset` (decisão do plano §2.7 e P-066) em vez de `page`/`page_size`; `page` é devolvido em `meta` para navegação.

### 2.4 Precisão numérica

| Campo | Tipo | Precisão |
| :--- | :--- | :--- |
| `suporte`, `confianca` | number | 4 casas |
| `lift` | number | 2 casas |
| `margemUnitaria`, `pontuacao` | number | 2 casas (a ordenação usa o valor integral, P-064.3) |
| `estoqueAtual` | number | 1 casa (estoque negativo do ERP é exibido como está; a regra usa `≤ 0`) |
| `pedidosEmComum`, `diasDesdeUltimaCompra`, `qtdAntecedentesRelacionados`, `codigo` | int | — |

---

## 3. Endpoints

### 3.1 `GET /api/v1/analytics/health`

- **Objetivo:** informar se a base está carregada, sem disparar carga nem mineração (P-069, CA-21).
- **Resposta `200` (`AnalyticsHealthResponse`):**

| Campo `data` | Tipo | Descrição |
| :--- | :--- | :--- |
| `status` | `"UP"` | Processo respondendo |
| `estadoCache` | `"FRIO"` \| `"CARREGANDO"` \| `"QUENTE"` \| `"EXPIRADO"` | `FRIO`: nunca carregou; `CARREGANDO`: uma carga está em andamento (flag lida sem lock); `QUENTE`: snapshot dentro do TTL; `EXPIRADO`: snapshot existe, mas a próxima consulta vai recarregar (Q-7) |
| `cacheCarregado` | boolean | Existe snapshot publicado (`QUENTE` ou `EXPIRADO`, ou `CARREGANDO` com snapshot anterior) |
| `baseSuficiente` | boolean \| null | `false` se a base gera `XSL-003`; `null` sem cache |
| `carregadoEm` | string ISO-8601 \| null | Momento da última carga concluída (o `loadedAt` do Design Plan) |
| `expiraEm` | string ISO-8601 \| null | `carregadoEm + cacheTtlHours` |
| `duracaoUltimaCargaMs` | int \| null | Duração da última carga, para a tela estimar a espera do primeiro acesso |
| `contagens` | objeto \| null | `cestasValidas`, `regrasUteis`, `itensTriviais`, `skusComCesta` (agregados, sem cliente) |
| `parametros` | `CrossSellParameters` | Mesmo objeto de 2.2 |

```json
{
  "data": {
    "status": "UP",
    "estadoCache": "QUENTE",
    "cacheCarregado": true,
    "baseSuficiente": true,
    "carregadoEm": "2026-11-05T14:02:11.418Z",
    "expiraEm": "2026-11-05T20:02:11.418Z",
    "duracaoUltimaCargaMs": 4120,
    "contagens": { "cestasValidas": 61234, "regrasUteis": 4180, "itensTriviais": 3, "skusComCesta": 1712 },
    "parametros": { "minLift": 1.2, "minConfidence": 0.10, "minPairOrders": 10, "trivialItemSupport": 0.15, "dormantDays": 90, "customerProfileDays": 365, "cacheTtlHours": 6 }
  },
  "meta": { "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05" }
}
```

Cache frio: `estadoCache: "FRIO"`, `cacheCarregado: false`, campos de carga `null`, `parametros` preenchido, `meta.dataReferencia: null`. O health nunca dispara carga nem acessa o banco (P-069, CA-21).

---

### 3.2 `POST /api/v1/analytics/cache/reload`

- **Objetivo:** recarga manual (P-068.3). Sem corpo. Bloqueia até a carga terminar; requisições simultâneas aguardam o mesmo lock e reaproveitam o resultado.
- **Resposta `200`:** mesmo schema de `/health`, com o novo snapshot.
- **Erros:** `429 ANL-002` se a última carga terminou há menos de 15 minutos (`MIN_RELOAD_INTERVAL_MINUTES`); `503 ANL-001` se o banco falhar (o snapshot anterior continua valendo, P-068.4).
- Sem botão na tela nesta fase (ADR-002, DA-07).

---

### 3.3 `GET /api/v1/analytics/cross-sell/product/{sku}`

- **Objetivo:** "quem compra A também leva o quê?" (P-061).

**Path / Query Parameters:**

| Parâmetro | Onde | Tipo | Obrigatório? | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `sku` | path | integer | Sim | 1 a 2.147.483.647 | `Codigo` do produto antecedente |
| `limit` / `offset` | query | integer | Não | §2.3 | Paginação |

**Resposta `200` (`ProductCrossSellResponse`):** `data = { produto, recomendacoes }`, `meta = PagedMeta` (sem `motivoVazio`, com `parametros`).

`data.produto` (`ConsultedProduct`, Q-2): `codigo` (int), `descricao` (string), `fornecedor` (string). **Sempre presente** em todo 200, inclusive com `recomendacoes: []` (a tela usa a descrição no título do vazio).

`data.recomendacoes[]` (`ProductRecommendationItem`), **curado por P-094 (1.1.0)**: no máximo 10 itens, sem variantes do produto consultado, um por linha de produto e ordenado por faixa (mesmo fornecedor do produto consultado → similar → demais). Dentro de cada faixa vale a ordem de P-061.1: lift ↓, confiança ↓, `pedidosEmComum` ↓, `codigo` ↑. `meta.totalItems` conta a lista curada:

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `codigo` | int | SKU consequente | P-061.2 |
| `descricao` | string | Descrição do consequente | P-061.2 |
| `fornecedor` | string | Fornecedor do consequente | P-061.2 |
| `suporte` | number | Pedidos com A e B ÷ Cestas Válidas | P-059.2 |
| `confianca` | number | Pedidos com A e B ÷ pedidos com A | P-059.4 |
| `lift` | number | Confiança ÷ frequência de B | P-059.5 |
| `pedidosEmComum` | int | Cestas Válidas com A e B | P-059.3 |
| `estoqueAtual` | number | `Estoque` atual | P-061.2 |
| `semEstoque` | boolean | `Estoque ≤ 0` | P-061.4 |
| `margemNaoPositiva` | boolean | Margem Unitária ≤ 0 | P-061.4 |
| `explicacao` | `Explanation` | Frases de P-065 (ver 3.5) | P-065 |

Consequentes fora do catálogo ativo são excluídos (P-061.3). Nenhum campo de cliente (LGPD-03).

**Exemplo `200` (R1 e R5 do exemplo de P-060):**

```json
{
  "data": {
    "produto": { "codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE" },
    "recomendacoes": [
      {
        "codigo": 2002, "descricao": "CAPSULA DE HIBISCO", "fornecedor": "HERBARIUM",
        "suporte": 0.0170, "confianca": 0.3400, "lift": 4.25, "pedidosEmComum": 170,
        "estoqueAtual": 84.0, "semEstoque": false, "margemNaoPositiva": false,
        "explicacao": {
          "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
          "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
          "evidencia": "Baseado em 170 pedidos.",
          "motivo": null
        }
      },
      {
        "codigo": 3003, "descricao": "OLEO DE COCO 200ML", "fornecedor": "COPRA",
        "suporte": 0.0060, "confianca": 0.1200, "lift": 1.20, "pedidosEmComum": 60,
        "estoqueAtual": 0.0, "semEstoque": true, "margemNaoPositiva": false,
        "explicacao": {
          "frequencia": "Em 12% dos pedidos com CHA VERDE 100G também há OLEO DE COCO 200ML.",
          "intensidade": "OLEO DE COCO 200ML aparece 1,2 vezes mais nesses pedidos do que no geral.",
          "evidencia": "Baseado em 60 pedidos.",
          "motivo": null
        }
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 50, "offset": 0, "totalItems": 2, "totalPages": 1,
    "parametros": { "minLift": 1.2, "minConfidence": 0.10, "minPairOrders": 10, "trivialItemSupport": 0.15, "dormantDays": 90, "customerProfileDays": 365, "cacheTtlHours": 6 }
  }
}
```

**SKU válido sem Regras Úteis (P-061.5, C-02, Q-2):** `200` com o produto consultado identificado:

```json
{
  "data": {
    "produto": { "codigo": 4004, "descricao": "MEL DE ABELHA 500G", "fornecedor": "APIS FLORA" },
    "recomendacoes": []
  },
  "meta": {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 50, "offset": 0, "totalItems": 0, "totalPages": 0,
    "parametros": { "...": "igual a 2.2" }
  }
}
```

**Erros:** `400 XSL-004` (sku/limit/offset inválidos), `404 XSL-001` (fora do catálogo ativo ou sem Cesta Válida), `422 XSL-003` (base insuficiente), `503 ANL-001`.

Ordem de avaliação: validação (400) → carga do snapshot (503) → base suficiente (422) → existência do SKU (404) → lista (200).

---

### 3.4 `GET /api/v1/analytics/cross-sell/customer/{customerCode}`

- **Objetivo:** "o que oferecer a este cliente?" (P-062 a P-064).

**Path / Query Parameters:**

| Parâmetro | Onde | Tipo | Obrigatório? | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customerCode` | path | integer | Sim | 1 a 2.147.483.647 | `Cod Cliente` |
| `limit` / `offset` | query | integer | Não | §2.3 | Paginação |

Nenhum outro dado de cliente na URL ou em headers (LGPD-07).

**Resposta `200` (`CustomerCrossSellResponse`):** `data = { recomendacoes }`, `meta = PagedMeta` com `motivoVazio`. O `customerCode` **não** é ecoado (o cliente já o conhece; minimização).

`data.recomendacoes[]` (`CustomerRecommendationItem`), **curado por P-094 (1.1.0)**: no máximo 10 itens, sem variantes do `antecedentePrincipal` de cada item, um por linha de produto e ordenado por faixa (mesmo fornecedor do `antecedentePrincipal` → similar → demais). Dentro de cada faixa vale a ordem de P-064.2: pontuação ↓, lift ↓, `codigo` ↑. `meta.totalItems` conta a lista curada. Só candidatos com estoque > 0, no catálogo ativo e margem > 0 (P-063):

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `codigo` | int | SKU candidato | P-064.4 |
| `descricao` | string | Descrição | P-064.4 |
| `fornecedor` | string | Fornecedor | P-064.4 |
| `antecedentePrincipal` | `ProductRef` sem `fornecedor`: `{ codigo, descricao }` | SKU do perfil da regra de maior pontuação | P-064.1 |
| `qtdAntecedentesRelacionados` | int | Quantos SKUs do perfil sugerem o candidato | P-064.1 |
| `lift` | number | Da regra principal | P-064.4 |
| `confianca` | number | Da regra principal | P-064.4 |
| `pedidosEmComum` | int | Da regra principal (base da frase de evidência e de "Ver números", Q-4). Métrica **global da regra** (todas as Cestas Válidas), não contagem de pedidos deste cliente | P-065.3 |
| `margemUnitaria` | number | `Pc.Venda − custo` | P-063.3 |
| `custoEstimado` | boolean | Custo pelo fallback de 60% | P-063.3 |
| `pontuacao` | number | `lift × confiança × margemUnitaria` | P-064 |
| `motivo` | `"NUNCA_COMPROU"` \| `"DORMENTE"` | Tipo do candidato | P-062.5 |
| `diasDesdeUltimaCompra` | int \| null | Só quando `DORMENTE` | P-062.5 |
| `explicacao` | `Explanation` | Frases de P-065 com `motivo` preenchido | P-065.4 |

**Exemplo `200` (CA-13: G antes de B):**

```json
{
  "data": {
    "recomendacoes": [
      {
        "codigo": 7007, "descricao": "GENGIBRE EM PO 100G", "fornecedor": "CATARINENSE",
        "antecedentePrincipal": { "codigo": 1001, "descricao": "CHA VERDE 100G" },
        "qtdAntecedentesRelacionados": 2,
        "lift": 1.50, "confianca": 0.2000, "pedidosEmComum": 100,
        "margemUnitaria": 30.00, "custoEstimado": false, "pontuacao": 9.00,
        "motivo": "NUNCA_COMPROU", "diasDesdeUltimaCompra": null,
        "explicacao": {
          "frequencia": "Em 20% dos pedidos com CHA VERDE 100G também há GENGIBRE EM PO 100G.",
          "intensidade": "GENGIBRE EM PO 100G aparece 1,5 vezes mais nesses pedidos do que no geral.",
          "evidencia": "Baseado em 100 pedidos.",
          "motivo": "Sugerido porque o cliente compra CHA VERDE 100G. O cliente nunca comprou GENGIBRE EM PO 100G."
        }
      },
      {
        "codigo": 2002, "descricao": "CAPSULA DE HIBISCO", "fornecedor": "HERBARIUM",
        "antecedentePrincipal": { "codigo": 1001, "descricao": "CHA VERDE 100G" },
        "qtdAntecedentesRelacionados": 1,
        "lift": 4.25, "confianca": 0.3400, "pedidosEmComum": 170,
        "margemUnitaria": 5.00, "custoEstimado": true, "pontuacao": 7.23,
        "motivo": "DORMENTE", "diasDesdeUltimaCompra": 120,
        "explicacao": {
          "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
          "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
          "evidencia": "Baseado em 170 pedidos.",
          "motivo": "Sugerido porque o cliente compra CHA VERDE 100G. O cliente não compra CAPSULA DE HIBISCO há 120 dias."
        }
      }
    ]
  },
  "meta": {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 50, "offset": 0, "totalItems": 2, "totalPages": 1, "motivoVazio": null,
    "parametros": { "...": "igual a 2.2" }
  }
}
```

**Cliente sem compras nos últimos 365 dias (P-062.7, C-07):**

```json
{
  "data": { "recomendacoes": [] },
  "meta": {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 50, "offset": 0, "totalItems": 0, "totalPages": 0, "motivoVazio": "SEM_COMPRAS_RECENTES",
    "parametros": { "...": "igual a 2.2" }
  }
}
```

Perfil não vazio sem candidatos viáveis (C-06): igual, com `motivoVazio: null`.

**Erros:** `400 XSL-004`, `404 XSL-002` (sem nenhum pedido de VENDA no histórico), `422 XSL-003`, `503 ANL-001`. Mesma ordem de avaliação de 3.3.

---

### 3.5 Objeto `Explanation` (P-065)

Frases **separadas e prontas**, montadas no domínio (ADR-002, DA-09; Q-3). O frontend escolhe ordem e destaque (chips, texto `sr-only`) e não recalcula nem concatena números. O mesmo objeto serve aos dois modos; a tela do cliente usa `motivo` e `frequencia` como principais, e a do produto usa `frequencia`, `intensidade` e `evidencia`.

| Campo | Formato | Regra |
| :--- | :--- | :--- |
| `frequencia` | `"Em {X}% dos pedidos com {descrição A} também há {descrição B}."`. X = confiança × 100, inteiro, meio para cima | P-065.1 |
| `intensidade` | `"{descrição B} aparece {L} vezes mais nesses pedidos do que no geral."`. L com 1 casa, meio para cima, vírgula decimal | P-065.2 |
| `evidencia` | `"Baseado em {N} pedidos."`. N com separador de milhar `.` (ex.: `1.234`) | P-065.3 |
| `motivo` | Por cliente: `"Sugerido porque o cliente compra {A}. O cliente nunca comprou {B}."` ou `"Sugerido porque o cliente compra {A}. O cliente não compra {B} há {D} dias."`; por produto: `null` | P-065.4 |

Nenhuma frase contém "lift", "suporte" ou "confiança" (CA-14). As chaves do objeto são identificadores técnicos, não texto exibido.

---

### 3.6 `GET /api/v1/analytics/products/search` — **OPCIONAL, a decidir no checkpoint (DC-5)**

- **Objetivo:** permitir que o comprador encontre o SKU pela descrição (Q-1, D-7 do Design Plan). Se DC-5 for "não", a rota não é criada e a tela busca só por código; nada mais muda no contrato.
- **Fonte:** catálogo ativo (`Externo01.Produto`, `[Pc.Venda] > 0`, mesmas colunas de LGPD-01), em cache próprio e leve (~1.935 linhas, < 2 MB, TTL de 6 h, lock próprio). A busca **não** dispara a carga das cestas: funciona com o cache de cross-sell frio.

**Query Parameters:**

| Parâmetro | Tipo | Obrigatório? | Default | Validação | Descrição |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `q` | string | Sim | — | Após `trim`: 1 a 60 caracteres se só dígitos; 2 a 60 nos demais casos | Código ou trecho da descrição |
| `limit` | integer | Não | `20` | 1 a 20 | Máximo de resultados |
| `offset` | integer | Não | `0` | ≥ 0 | Mantém o padrão de paginação do módulo |

**Regra de busca (domínio puro, `domain/product_search.py`):** normaliza `q` e `descricao` (NFKD sem acentos, minúsculas, espaços colapsados; a descrição normalizada é pré-calculada na carga). Só dígitos: código exato, depois códigos que começam com `q`. Demais: descrição que começa com `q`, depois descrição que contém `q`. Empate por `descricao` ↑ e `codigo` ↑.

**Resposta `200` (`ProductSearchResponse`):** `data = ProductSearchItem[]` (`codigo`, `descricao`, `fornecedor`), `meta = PagedMeta` (sem `parametros`).

```json
{
  "data": [
    { "codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE" },
    { "codigo": 1002, "descricao": "CHA VERDE COM LIMAO 50G", "fornecedor": "CATARINENSE" }
  ],
  "meta": {
    "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0", "dataReferencia": "2026-11-05",
    "page": 1, "limit": 20, "offset": 0, "totalItems": 2, "totalPages": 1
  }
}
```

Nenhum resultado → `200` com `data: []`. **Erros:** `400 XSL-004` (`fields: ["q"]` ou `limit`/`offset`), `503 ANL-001`.

**Custo estimado:** backend cerca de 0,5 dia (cache de catálogo, função de busca pura, rota, testes T-17); frontend cerca de 1 dia (campo vira combobox acessível com *debounce* de 300 ms e mínimo de 2 caracteres, specs T-18). Memória < 2 MB; busca linear em ~1.935 strings pré-normalizadas, menos de 10 ms por requisição. Sem dependência nova (`unicodedata` da biblioteca padrão). Sem dado pessoal (fora do escopo LGPD). Antecipa a rota prevista para a Fase 4, que a reaproveita sem mudança.

---

## 4. Matriz de Erros HTTP Mapeados

Corpo único de erro (`AnalyticsErrorResponse`), sem stacktrace, SQL, mensagem do driver nem valor recebido (LGPD-05):

```json
{
  "error": {
    "code": "XSL-004",
    "message": "Parâmetros inválidos: limit, offset.",
    "fields": ["limit", "offset"]
  },
  "meta": { "timestamp": "2026-11-05T15:10:00.000Z", "version": "1.1.0" }
}
```

| HTTP | `code` | Quando | `message` (fixa) | `fields` | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `400` | `XSL-004` | `sku`/`customerCode` não inteiro positivo; `limit` fora da faixa da rota (1–200; 1–20 na busca); `offset` < 0; qualquer valor não inteiro; `q` fora de 3.6 | `"Parâmetros inválidos: {campos}."` | nomes dos campos inválidos (`sku`, `customerCode`, `limit`, `offset`, `q`), sem duplicatas, na ordem do path/query | P-066.2, P-067 |
| `404` | `XSL-001` | SKU fora do catálogo ativo ou sem Cesta Válida | `"Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item."` | `[]` | P-061.6 |
| `404` | `XSL-002` | Cliente sem pedido de VENDA no histórico | `"Cliente sem histórico de compras."` | `[]` | P-062.7 |
| `422` | `XSL-003` | < 1.000 Cestas Válidas ou zero Regras Úteis | `"Não há pedidos suficientes para gerar recomendações confiáveis."` | `[]` | P-067 |
| `429` | `ANL-002` | Reload antes de 15 min da última carga | `"A base foi recarregada recentemente. Tente novamente mais tarde."` | `[]` | P-068.3 |
| `503` | `ANL-001` | Banco indisponível ou falha na leitura | `"Base de vendas indisponível no momento. Tente novamente em instantes."` | `[]` | P-067 (obs.), P-068.4 |
| `500` | — | Erro não previsto | Corpo padrão do Starlette (`Internal Server Error`), sem stacktrace | — | `security-anti-patterns` |
| `401` | — | Produção sem credencial (middleware global) | Comportamento existente (`WWW-Authenticate: Basic`) | — | P-033, LGPD-10 |

- Validação das rotas do módulo responde **400**, não o 422 padrão do FastAPI; os outros módulos continuam com 422 (ADR-002, DA-08).
- O frontend decide pelo `code`, nunca pelo texto de `message`.
- Exemplo `customerCode = "1 OR 1=1"`: `400`, `fields: ["customerCode"]`, sem eco do valor.
- `fields` está sempre presente (Q-6): lista vazia fora do 400.

### 4.1 Conformidade com LGPD-03 (allowlist de campos)

| Campo novo ou alterado nesta revisão | Natureza | Contém dado de cliente? | Situação |
| :--- | :--- | :--- | :--- |
| `data.produto.{codigo, descricao, fornecedor}` (modo produto) | Catálogo | Não | Já previsto em P-061.2 |
| `explicacao.{frequencia, intensidade, evidencia, motivo}` | Texto montado a partir de catálogo e métricas da regra; `motivo` cita só o SKU antecedente e os dias desde a última compra do candidato | Só o que P-064.4 já permite (`diasDesdeUltimaCompra`, antecedente principal) | Dentro de §3.2 do parecer |
| `pedidosEmComum` (modo cliente) | Métrica global da regra, igual ao modo produto | Não (não é contagem de pedidos do cliente) | **Acréscimo à allowlist do modo cliente**: a confirmar pelo Privacy Officer no checkpoint |
| `meta.parametros` | Constantes do domínio | Não | Sem impacto |
| Health: `estadoCache`, `duracaoUltimaCargaMs` | Estado técnico agregado | Não | Dentro de §3.2 (status do cache) |
| `/products/search` | Catálogo (colunas de LGPD-01) | Não | Sem impacto |

Continuam **fora** de qualquer resposta: `customerCode` (não ecoado), `suporte` no modo cliente, perfil completo, datas absolutas de compra, `Pedido`, valores ou quantidades do cliente, `UF`, nome e documento.

---

## 5. Diretrizes de Integração no Frontend

- **Serviço:** `frontend/src/app/features/analytics/services/analytics.service.ts` (`baseUrl = '/api/v1/analytics'`), métodos `getHealth()`, `getProductCrossSell(sku, page)`, `getCustomerCrossSell(customerCode, page)` e, se DC-5 for aprovado, `searchProducts(q, page)`.
- **Cache frio (Q-7):** a página chama `getHealth()` ao abrir; com `estadoCache` `FRIO`, `EXPIRADO` ou `CARREGANDO`, avisa antes da busca que a primeira consulta pode levar cerca de `duracaoUltimaCargaMs` (ou um texto genérico quando `null`).
- **Textos com parâmetros (Q-5):** a copy interpola `meta.parametros` (por exemplo, `dormantDays`) em vez de fixar números.
- **Estado:** `cross-sell.store.ts` com `signal`s por modo: `idle`, `loading`, `success`, `empty`, `error`. Vazio por `SEM_COMPRAS_RECENTES` tem mensagem própria.
- **Privacidade:** `customerCode` não vai para a URL da SPA, `localStorage`, `sessionStorage`, cookies nem telemetria (LGPD-09). Nada de `console.log` de respostas.
- **Erros:** `toAnalyticsApiError(err: unknown): AnalyticsApiError | null` (type guard) e mapa `code → mensagem de tela`.
- **Tipagem (TypeScript, sem `any`):**

```typescript
/** Contrato analytics-cross-sell 1.1.0 (ADR-002). */
export interface AnalyticsMeta {
  timestamp: string;
  version: string;
  dataReferencia: string | null;
}

export interface PagedMeta extends AnalyticsMeta {
  page: number;
  limit: number;
  offset: number;
  totalItems: number;
  totalPages: number;
}

/** Constantes efetivas do domínio (Q-5), para a copy não fixar números. */
export interface CrossSellParameters {
  minLift: number;
  minConfidence: number;
  minPairOrders: number;
  trivialItemSupport: number;
  dormantDays: number;
  customerProfileDays: number;
  cacheTtlHours: number;
}

export interface CrossSellPagedMeta extends PagedMeta {
  parametros: CrossSellParameters;
}

export type EmptyReason = 'SEM_COMPRAS_RECENTES';

export interface CustomerPagedMeta extends CrossSellPagedMeta {
  motivoVazio: EmptyReason | null;
}

export interface PageRequest {
  limit: number;
  offset: number;
}

export interface ProductRef {
  codigo: number;
  descricao: string;
}

/** Frases prontas de P-065, separadas (Q-3). */
export interface Explanation {
  frequencia: string;
  intensidade: string;
  evidencia: string;
  motivo: string | null;
}

export interface ConsultedProduct extends ProductRef {
  fornecedor: string;
}

export interface ProductRecommendationItem {
  codigo: number;
  descricao: string;
  fornecedor: string;
  suporte: number;
  confianca: number;
  lift: number;
  pedidosEmComum: number;
  estoqueAtual: number;
  semEstoque: boolean;
  margemNaoPositiva: boolean;
  explicacao: Explanation;
}

export interface ProductCrossSellResponse {
  data: { produto: ConsultedProduct; recomendacoes: ProductRecommendationItem[] };
  meta: CrossSellPagedMeta;
}

/** Opcional (DC-5). */
export interface ProductSearchResponse {
  data: ConsultedProduct[];
  meta: PagedMeta;
}

export type CandidateReason = 'NUNCA_COMPROU' | 'DORMENTE';

export interface CustomerRecommendationItem {
  codigo: number;
  descricao: string;
  fornecedor: string;
  antecedentePrincipal: ProductRef;
  qtdAntecedentesRelacionados: number;
  lift: number;
  confianca: number;
  pedidosEmComum: number;
  margemUnitaria: number;
  custoEstimado: boolean;
  pontuacao: number;
  motivo: CandidateReason;
  diasDesdeUltimaCompra: number | null;
  explicacao: Explanation;
}

export interface CustomerCrossSellResponse {
  data: { recomendacoes: CustomerRecommendationItem[] };
  meta: CustomerPagedMeta;
}

export type CacheState = 'FRIO' | 'CARREGANDO' | 'QUENTE' | 'EXPIRADO';

export interface AnalyticsHealthData {
  status: 'UP';
  estadoCache: CacheState;
  cacheCarregado: boolean;
  baseSuficiente: boolean | null;
  carregadoEm: string | null;
  expiraEm: string | null;
  duracaoUltimaCargaMs: number | null;
  contagens: { cestasValidas: number; regrasUteis: number; itensTriviais: number; skusComCesta: number } | null;
  parametros: CrossSellParameters;
}

export interface AnalyticsHealthResponse {
  data: AnalyticsHealthData;
  meta: AnalyticsMeta;
}

export type AnalyticsErrorCode =
  | 'XSL-001' | 'XSL-002' | 'XSL-003' | 'XSL-004'
  | 'ANL-001' | 'ANL-002';

export interface AnalyticsApiError {
  code: AnalyticsErrorCode;
  message: string;
  fields: string[];
}
```

---

## 6. Padrão de documentação no código (obrigatório para o Desenvolvedor)

| Camada | Padrão |
| :--- | :--- |
| Python: topo de arquivo | Docstring do módulo com objetivo e regras implementadas (ex.: `P-062 a P-064`). |
| Python: funções públicas e constantes | Docstring estilo Google (Args, Returns, Raises) com linha `Regra: P-0XX` e o **porquê** quando não óbvio. Constantes com comentário de intenção na mesma linha. |
| Pydantic / OpenAPI | `Field(description=...)` em PT-BR em todos os campos; `Literal[...]` para `motivo`, `motivoVazio`, `status`; `responses={400, 404, 422, 503}` com `model=AnalyticsErrorResponse` no decorator; `summary`/`description` por rota; `json_schema_extra` com os exemplos desta seção. |
| TypeScript | Comentário de topo por arquivo; TSDoc em interfaces, constantes e funções exportadas com a regra (`P-065`); proibido `any` (usar `unknown` + type guard). |

---

## Apêndice A — Variante C para a rota por cliente (adotar só se o checkpoint decidir por DC-1 = C)

Substitui 3.4. Domínio, serviço e resposta são os mesmos.

`POST /api/v1/analytics/cross-sell/customer/query` — `Content-Type: application/json`

| Campo do corpo | Tipo | Obrigatório? | Validação |
| :--- | :--- | :--- | :--- |
| `customerCode` | integer | Sim | 1 a 2.147.483.647 |
| `limit` | integer | Não (50) | 1 a 200 |
| `offset` | integer | Não (0) | ≥ 0 |

`model_config = ConfigDict(extra="forbid")` (campo desconhecido → 400 `XSL-004`). Resposta `200` idêntica a 3.4; erros idênticos. Não há cache HTTP (a rota já é dinâmica). O `customerCode` deixa de aparecer em log de acesso e em `httpRequest.requestUrl`.
