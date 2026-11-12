# Contrato de API — Previsão de Estoque e Compras (`inventory`)

| Campo | Valor |
| :--- | :--- |
| **Recurso** | Previsão de Estoque e Compras (Política Mín/Máx) |
| **Módulo backend** | `src/modules/inventory/` (FastAPI + Pydantic v2) |
| **Consumidor** | `frontend/src/app/features/inventory/` (Angular 18). É o único consumidor. |
| **Base URL** | `/api/v1/inventory` |
| **Versão do contrato** | **2.0.0** (`meta.version`). Substitui a 1.0.0. |
| **Feature / Branch** | P-053 — `feature/P-053-estoque-min-max-30-60` |
| **Regras** | P-041, P-047.1, P-053, P-054, P-055, P-056 (`business_rules/estoque-min-max.md`) |
| **Decisões** | `adr/ADR-001-politica-estoque-min-max.md` (DA-01 a DA-11) |
| **Autenticação** | HTTP Basic aplicada pelo middleware global `HTTPBasicAuthASGIMiddleware`, ativo só em produção (P-033). Nada muda nesta feature. |
| **Case do JSON** | `camelCase` em todos os payloads do módulo |
| **Dados pessoais (LGPD)** | Nenhum. Só catálogo de produtos e vendas agregadas por SKU. O bypass do Privacy Officer está registrado no `STATE.md`. |
| **Autor / Data** | Arquiteto (Etapa 2) — 2026-11-05 |

> Observação de governança: `.agents/docs/api_contracts/TEMPLATE.md` não existe no repositório. Este contrato segue o padrão da skill `api-contract-expert` (envelope `data`/`meta`, semântica HTTP, case único).

---

## ⚠️ BREAKING CHANGE (1.0.0 → 2.0.0)

O contrato muda de forma incompatível em `POST /predict`, `POST /export-csv` e `GET /config`. O prefixo `/api/v1` é mantido porque o único consumidor é o SPA do mesmo repositório, publicado na mesma imagem Docker (ADR-001, DA-07).

| Onde | Antes (1.0.0) | Depois (2.0.0) |
| :--- | :--- | :--- |
| Request `/predict` e `/export-csv` | `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct` | **Removidos.** Se enviados, são **ignorados sem efeito** (P-056.4). |
| Request `/predict` e `/export-csv` | — | **Novos:** `minCoverageDays` (padrão 30) e `maxCoverageDays` (padrão 60) |
| Request `/predict` e `/export-csv` | Sem validação cruzada | **422** se `maxCoverageDays ≤ minCoverageDays` (`INV-001`) ou `leadTimeDays ≥ maxCoverageDays` (`INV-002`) |
| Item `data.produtos[]` | `estoqueSeguranca`, `rop`, `estoqueIdeal`, `estoqueIdealTeorico`, `qtdSugeridaTeorica`, `limitadoPorEspaco`, `tetoCompraFisica`, `desvioPadraoDemanda` | **Removidos** |
| Item `data.produtos[]` | — | **Novos:** `estoqueMinimo` (int) e `estoqueMaximo` (int) |
| Item `statusLabel` | "Reposição Necessária", "Excesso / Overstock" | "Abaixo do Mínimo", "Acima do Máximo" (os códigos de `status` não mudam) |
| `data.kpis` | `skusLimitadosPorEspaco` | **Removido** (os demais nomes são mantidos) |
| `data` | — | **Novo bloco** `politica` (eco dos parâmetros efetivos) |
| `GET /config` | `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct` | **Removidos.** Entram `minCoverageDays` e `maxCoverageDays`. |
| CSV | Colunas "Estoque de Segurança", "Ponto de Reposição (ROP)", "Estoque Ideal", "Demanda Teórica Plena", "Limitado por Espaço Físico", "Teto Físico de Compra" | **Removidas.** Entram "Estoque Mínimo (un)" e "Estoque Máximo (un)". |
| `meta.version` | `"1.0.0"` | `"2.0.0"` |

---

## 1. Convenções

### 1.1 Envelope de sucesso (2xx)

Toda resposta JSON de sucesso segue o formato abaixo:

```json
{
  "data": { },
  "meta": { "timestamp": "2026-11-05T13:00:00.123456+00:00", "version": "2.0.0", "executionTimeMs": null }
}
```

| Campo `meta` | Tipo | Descrição |
| :--- | :--- | :--- |
| `timestamp` | string (ISO-8601, UTC) | Momento da resposta |
| `version` | string | Versão do contrato do módulo (`"2.0.0"`) |
| `executionTimeMs` | number \| null | Tempo do cálculo. Preenchido apenas em `/predict`. |

Exceções já existentes, mantidas: `GET /health` (sonda de infraestrutura, sem envelope) e `POST /export-csv` (arquivo binário/texto).

### 1.2 Erros

| HTTP | Quando | Corpo |
| :--- | :--- | :--- |
| `422` | Payload inválido: tipo, faixa ou regra cruzada | Formato padrão do FastAPI: `{"detail": [ {type, loc, msg, input, ctx?} ]}` |
| `500` | Falha inesperada (banco indisponível, erro interno) | `{"detail": "<mensagem genérica em PT-BR>"}`, sem `str(e)` nem stacktrace (ADR-001, DA-11) |

**Códigos internos** (`detail[].type`) das regras de negócio:

| Código | Parâmetro (`loc`) | Condição | Mensagem (`msg`) | Regra |
| :--- | :--- | :--- | :--- | :--- |
| `INV-001` | `["body", "maxCoverageDays"]` | `maxCoverageDays ≤ minCoverageDays` | `Dias Máximo (maxCoverageDays = {maxCoverageDays}) deve ser maior que Dias Mínimo (minCoverageDays = {minCoverageDays}).` | P-053.3 |
| `INV-002` | `["body", "leadTimeDays"]` | `leadTimeDays ≥ maxCoverageDays` | `Lead Time (leadTimeDays = {leadTimeDays}) deve ser menor que Dias Máximo (maxCoverageDays = {maxCoverageDays}).` | A2 |

Erros de tipo e faixa usam os tipos nativos do Pydantic (`greater_than_equal`, `less_than_equal`, `int_from_float`, `int_parsing`, `string_too_long`, `json_invalid`), com mensagem em inglês (comportamento atual da aplicação). O cliente **decide pelo `type`, nunca pelo texto de `msg`**. Campos extras que o Pydantic adicione (como `url`) devem ser ignorados.

### 1.3 Tipos e precisão numérica

| Grandeza | Tipo | Precisão na resposta |
| :--- | :--- | :--- |
| Unidades de política e compra (`estoqueMinimo`, `estoqueMaximo`, `qtdSugeridaCompra`) | int | Inteiro, arredondado para cima no servidor sem resíduo de ponto flutuante (ADR-001, DA-02) |
| `estoqueAtual` | number | 1 casa |
| `vmd` | number | 2 casas (**só para exibição**) |
| `diasCobertura` | number | 1 casa. `999` é o sentinela de "∞" (VMD 0 e estoque > 0). |
| Valores em R$ (`custoUnitario`, `precoVenda`, `investimentoTotalItem`, KPIs monetários) | number | 2 casas |

> **O cliente NÃO DEVE recalcular `estoqueMinimo`/`estoqueMaximo` a partir da `vmd` exibida.** O servidor usa a VMD em precisão integral (P-053.6). Exemplo: 1 un em 60 dias resulta em `vmd = 0.02` na resposta, mas o máximo correto é 1, enquanto `teto(0,02 × 60) = 2`.

### 1.4 Enumerações

**`status` / `statusLabel`** (P-055.2), em ordem de precedência e de ordenação padrão (P-055.6):

| Ordem | `status` | `statusLabel` |
| :--- | :--- | :--- |
| 1 | `CRITICAL_STOCKOUT` | `Ruptura Iminente` |
| 2 | `REORDER_NEEDED` | `Abaixo do Mínimo` |
| 3 | `HEALTHY` | `Estoque Saudável` |
| 4 | `OVERSTOCK` | `Acima do Máximo` |

A precedência de **classificação** é Ruptura → Abaixo do Mínimo → Acima do Máximo → Saudável. A ordem acima é a de **exibição**.

**`curvaAbc`**: `"A"` \| `"B"` \| `"C"` (global por receita na janela: A ≤ 80%, B ≤ 95%, C restante; SKU sem venda é C).

### 1.5 Paginação

`POST /predict` e `GET /suppliers` devolvem a lista completa, sem `page`/`page_size`. É uma **exceção consciente e pré-existente** à regra de paginação:

1. O resultado é um cálculo sobre o catálogo inteiro (cerca de 2,2 mil SKUs), cujos KPIs e ordenação dependem do conjunto completo.
2. O volume é limitado pelo tamanho do catálogo, não cresce com o histórico.
3. A paginação acontece no cliente.

Alterar isso está fora do escopo. Um ponto de melhoria futura é habilitar `GZipMiddleware`.

---

## 2. Endpoints

| Método | Rota | Descrição | Mudou na 2.0.0? |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/inventory/health` | Sonda de saúde | Não |
| `GET` | `/api/v1/inventory/config` | Padrões e faixas dos parâmetros da tela | **Sim (breaking)** |
| `GET` | `/api/v1/inventory/suppliers` | Fornecedores e contagem de SKUs | Não (só `meta.version`) |
| `POST` | `/api/v1/inventory/predict` | Cálculo da Política Mín/Máx por SKU + KPIs | **Sim (breaking)** |
| `POST` | `/api/v1/inventory/export-csv` | Plano de compras em CSV | **Sim (breaking)** |

---

## 3. `GET /api/v1/inventory/config`

Devolve os padrões e as faixas **da tela** (controles deslizantes do modal "Parâmetros"). As faixas da tela são mais estreitas que as aceitas pela API (seção 5.1), por decisão A1.

### 3.1 Resposta `200` — schema `InventoryConfigResponse`

`data` (`InventoryConfigData`): cada chave é um `RangeParameterConfig { default: int, min: int, max: int, step: int }`.

| Chave | default | min | max | step | Situação |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `historyWindowDays` | 60 | 15 | 180 | 15 | Mantido |
| `leadTimeDays` | 15 | 1 | 60 | 1 | Mantido (A5 fora de escopo) |
| `minCoverageDays` | 30 | 5 | 120 | 5 | **Novo** |
| `maxCoverageDays` | 60 | 10 | 180 | 5 | **Novo** |
| ~~`targetCoverageDays`~~, ~~`serviceLevel`~~, ~~`budgetLimit`~~, ~~`maxPurchaseVariationPct`~~ | — | — | — | — | **Removidos** |

### 3.2 Exemplo

```json
{
  "data": {
    "historyWindowDays": { "default": 60, "min": 15, "max": 180, "step": 15 },
    "leadTimeDays": { "default": 15, "min": 1, "max": 60, "step": 1 },
    "minCoverageDays": { "default": 30, "min": 5, "max": 120, "step": 5 },
    "maxCoverageDays": { "default": 60, "min": 10, "max": 180, "step": 5 }
  },
  "meta": { "timestamp": "2026-11-05T13:00:00.123456+00:00", "version": "2.0.0", "executionTimeMs": null }
}
```

> As regras cruzadas (`max > min`, `leadTime < max`) não são expostas em `/config`. O frontend as aplica a partir de `inventory.constants.ts` e da função de validação da tela (tarefas F-02 e F-04).

---

## 4. `GET /api/v1/inventory/suppliers` (inalterado)

### 4.1 Resposta `200` — schema `SuppliersResponse`

`data`: lista de `SupplierItem { fornecedor: string (maiúsculas), nome: string, totalSkus: int }`. O primeiro item é sempre `TODOS`.

```json
{
  "data": [
    { "fornecedor": "TODOS", "nome": "Todos os Fornecedores", "totalSkus": 2179 },
    { "fornecedor": "APIS FLORA", "nome": "Apis Flora", "totalSkus": 48 },
    { "fornecedor": "HERBARIUM", "nome": "Herbarium", "totalSkus": 112 }
  ],
  "meta": { "timestamp": "2026-11-05T13:00:00.123456+00:00", "version": "2.0.0", "executionTimeMs": null }
}
```

Erro `500`: `{"detail": "Não foi possível consultar o catálogo de fornecedores. Tente novamente em instantes."}`.

---

## 5. `POST /api/v1/inventory/predict`

Calcula, para cada SKU do catálogo (opcionalmente filtrado por fornecedor), VMD, Dias de Cobertura, Estoque Mínimo, Estoque Máximo, Quantidade Sugerida, Investimento e Status, além dos KPIs agregados.

### 5.1 Request — schema `InventoryPredictRequest`

`Content-Type: application/json`. Todos os campos são opcionais (os padrões se aplicam). Os campos **devem ser declarados nesta ordem** no modelo Pydantic, porque a validação cruzada depende dela (ADR-001, DA-05).

| # | Campo | Tipo | Padrão | Faixa aceita pela API | Descrição | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `historyWindowDays` | int | 60 | 15 – 365 | Janela de vendas da VMD, em dias | P-041, P-053.1 (A4 mantido) |
| 2 | `minCoverageDays` | int | 30 | 1 – 180 | Dias Mínimo da política | P-053.2, A1 |
| 3 | `maxCoverageDays` | int | 60 | 2 – 365, e **> `minCoverageDays`** | Dias Máximo da política | P-053.2, P-053.3, A1 |
| 4 | `leadTimeDays` | int | 15 | 1 – 90, e **< `maxCoverageDays`** | Lead time; só sinaliza Ruptura Iminente | P-055.3, A2 (A5 mantido) |
| 5 | `fornecedor` | string \| null | `null` | até 120 caracteres | Filtro por fornecedor. `null`, `""`, `"TODOS"` e `"ALL"` significam sem filtro. A comparação é sem diferença de maiúsculas e sem espaços nas pontas. | P-047.1 |

- `model_config = ConfigDict(extra="ignore")`: campos desconhecidos, inclusive os revogados `serviceLevel`, `targetCoverageDays`, `budgetLimit` e `maxPurchaseVariationPct`, são **descartados sem efeito no resultado** (P-056.4, CA-P056-02).
- Inteiros com parte fracionária (ex.: `30.5`) são rejeitados (`int_from_float`). Inteiros representados como `30.0` ou `"30"` são aceitos pelo modo *lax* do Pydantic, comportamento já existente.

**Exemplo — padrão 30/60:**

```json
{
  "historyWindowDays": 60,
  "minCoverageDays": 30,
  "maxCoverageDays": 60,
  "leadTimeDays": 15,
  "fornecedor": null
}
```

**Exemplo — parâmetros ajustados e filtro (CA-05 / CA-10):**

```json
{
  "historyWindowDays": 90,
  "minCoverageDays": 20,
  "maxCoverageDays": 45,
  "leadTimeDays": 10,
  "fornecedor": "APIS FLORA"
}
```

### 5.2 Resposta `200` — schema `InventoryPredictResponse`

`data` (`InventoryPredictData`) = `{ politica, kpis, produtos }`.

#### `data.politica` — `InventoryPolicyEcho` (**novo**)

Eco dos parâmetros **efetivamente usados** no cálculo, depois da validação e com os padrões aplicados. A tela usa esse bloco para rotular o resultado e para reenviar a mesma política no CSV (P-056.6, ADR-001, DA-08).

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `historyWindowDays` | int | Janela de vendas usada |
| `leadTimeDays` | int | Lead time usado |
| `minCoverageDays` | int | Dias Mínimo usado |
| `maxCoverageDays` | int | Dias Máximo usado |

#### `data.kpis` — `InventoryKPIs`

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `totalSkusAnalisados` | int | SKUs no resultado (depois do filtro de fornecedor) | P-055.5 |
| `skusEmRupturaCritica` | int | Contagem `CRITICAL_STOCKOUT` ("Ruptura Iminente") | P-055.5 |
| `skusNecessitamReposicao` | int | Contagem `REORDER_NEEDED` (**rótulo: "Abaixo do Mínimo"**) | P-055.5 |
| `skusEstoqueSaudavel` | int | Contagem `HEALTHY` | P-055.5 |
| `skusEmOverstock` | int | Contagem `OVERSTOCK` (**rótulo: "Acima do Máximo"**) | P-055.5 |
| `investimentoTotalSugerido` | number (2 casas) | Soma de `investimentoTotalItem`, sem teto | P-054.6 |
| `capitalImobilizadoOverstock` | number (2 casas) | Soma de `(estoque − estoqueMaximo) × custo` dos itens `OVERSTOCK` | P-055.4 |
| `curvaADistribuicao.qtdItens` | int | SKUs Curva A no resultado | Curva ABC |
| `curvaADistribuicao.percentualItens` | number (1 casa) | % de SKUs Curva A no resultado | Curva ABC |
| ~~`skusLimitadosPorEspaco`~~ | — | **Removido** | P-056.1 |

Invariantes: a soma das quatro contagens por status é igual a `totalSkusAnalisados` (CA-P055-09). `investimentoTotalSugerido` é igual à soma dos itens, com tolerância de R$ 0,01 (CA-P054-08).

#### `data.produtos[]` — `InventoryProductItem`

Vem ordenado por status (Ruptura → Abaixo do Mínimo → Saudável → Acima do Máximo), depois Curva ABC (A → C), depois VMD decrescente (P-055.6).

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `codigo` | int | SKU (código do ERP) | — |
| `descricao` | string | Descrição do produto | — |
| `ean` | string | EAN | — |
| `fornecedor` | string | Fornecedor em maiúsculas | P-047.1 |
| `tipo` | string | Tipo/Linha | — |
| `estoqueAtual` | number (1 casa) | Estoque físico. Valor negativo do ERP vira 0. | P-053.9 |
| `vmd` | number (2 casas) | Venda média diária (só exibição; ver 1.3) | P-041 |
| `diasCobertura` | number (1 casa) | `estoque ÷ VMD`. `999` = "∞". `0` se VMD 0 e estoque 0. | P-055.1 |
| `leadTime` | int | Lead time usado (igual a `politica.leadTimeDays`) | P-055.3 |
| **`estoqueMinimo`** | **int** | `teto(VMD × minCoverageDays)`; 0 se VMD 0 | **P-053.4, P-053.6, P-053.8** |
| **`estoqueMaximo`** | **int** | `teto(VMD × maxCoverageDays)`; 0 se VMD 0 | **P-053.5, P-053.6, P-053.8** |
| `qtdSugeridaCompra` | int | `teto(máximo − estoque)` com gatilho; 0 sem gatilho; sem travas | P-054.1 a P-054.4 |
| `custoUnitario` | number (2 casas) | Último custo; se ≤ 0, 60% do preço de venda | P-054.5 |
| `precoVenda` | number (2 casas) | Preço de venda | — |
| `investimentoTotalItem` | number (2 casas) | `qtdSugeridaCompra × custoUnitario` | P-054.5 |
| `status` | enum (1.4) | Status operacional | P-055.2 |
| `statusLabel` | string (1.4) | Rótulo em PT-BR | P-055.2 |
| `curvaAbc` | `"A"` \| `"B"` \| `"C"` | Classe ABC global | Curva ABC |

**Removidos do item:** `estoqueSeguranca`, `rop`, `estoqueIdeal`, `estoqueIdealTeorico`, `qtdSugeridaTeorica`, `limitadoPorEspaco`, `tetoCompraFisica` e `desvioPadraoDemanda`. O desvio-padrão sai porque não participa de nenhuma regra (P-053.7) e não é exibido em lugar nenhum (ADR-001, DA-04).

#### Exemplo de resposta (30/60, lead time 15, janela 60)

Cenário: 101 (VMD 2,0, estoque 10, custo 15) → Ruptura. 102 (VMD 2,0, estoque 50, custo 10) → Abaixo do Mínimo. 104 (VMD 2,0, estoque 90) → Saudável. 103 (sem venda, estoque 300, custo 5) → Acima do Máximo.

```json
{
  "data": {
    "politica": {
      "historyWindowDays": 60,
      "leadTimeDays": 15,
      "minCoverageDays": 30,
      "maxCoverageDays": 60
    },
    "kpis": {
      "totalSkusAnalisados": 4,
      "skusEmRupturaCritica": 1,
      "skusNecessitamReposicao": 1,
      "skusEstoqueSaudavel": 1,
      "skusEmOverstock": 1,
      "investimentoTotalSugerido": 2350.0,
      "capitalImobilizadoOverstock": 1500.0,
      "curvaADistribuicao": { "qtdItens": 1, "percentualItens": 25.0 }
    },
    "produtos": [
      {
        "codigo": 101, "descricao": "EXTRATO PROPOLIS APISFLORA", "ean": "7891234567890",
        "fornecedor": "APIS FLORA", "tipo": "EXTRATOS",
        "estoqueAtual": 10.0, "vmd": 2.0, "diasCobertura": 5.0, "leadTime": 15,
        "estoqueMinimo": 60, "estoqueMaximo": 120, "qtdSugeridaCompra": 110,
        "custoUnitario": 15.0, "precoVenda": 25.0, "investimentoTotalItem": 1650.0,
        "status": "CRITICAL_STOCKOUT", "statusLabel": "Ruptura Iminente", "curvaAbc": "A"
      },
      {
        "codigo": 102, "descricao": "VITAMINA C HERBARIUM", "ean": "7899876543210",
        "fornecedor": "HERBARIUM", "tipo": "VITAMINAS",
        "estoqueAtual": 50.0, "vmd": 2.0, "diasCobertura": 25.0, "leadTime": 15,
        "estoqueMinimo": 60, "estoqueMaximo": 120, "qtdSugeridaCompra": 70,
        "custoUnitario": 10.0, "precoVenda": 20.0, "investimentoTotalItem": 700.0,
        "status": "REORDER_NEEDED", "statusLabel": "Abaixo do Mínimo", "curvaAbc": "B"
      },
      {
        "codigo": 104, "descricao": "OMEGA 3 CATARINENSE", "ean": "7891112223341",
        "fornecedor": "CATARINENSE", "tipo": "SUPLEMENTOS",
        "estoqueAtual": 90.0, "vmd": 2.0, "diasCobertura": 45.0, "leadTime": 15,
        "estoqueMinimo": 60, "estoqueMaximo": 120, "qtdSugeridaCompra": 0,
        "custoUnitario": 12.0, "precoVenda": 22.0, "investimentoTotalItem": 0.0,
        "status": "HEALTHY", "statusLabel": "Estoque Saudável", "curvaAbc": "C"
      },
      {
        "codigo": 103, "descricao": "CHA VERDE CATARINENSE", "ean": "7891112223334",
        "fornecedor": "CATARINENSE", "tipo": "CHAS",
        "estoqueAtual": 300.0, "vmd": 0.0, "diasCobertura": 999.0, "leadTime": 15,
        "estoqueMinimo": 0, "estoqueMaximo": 0, "qtdSugeridaCompra": 0,
        "custoUnitario": 5.0, "precoVenda": 12.0, "investimentoTotalItem": 0.0,
        "status": "OVERSTOCK", "statusLabel": "Acima do Máximo", "curvaAbc": "C"
      }
    ]
  },
  "meta": { "timestamp": "2026-11-05T13:00:01.402311+00:00", "version": "2.0.0", "executionTimeMs": 184.37 }
}
```

### 5.3 Erros

**422 — `INV-001` (Dias Máximo ≤ Dias Mínimo; CA-P053-04)**

Request: `{"minCoverageDays": 60, "maxCoverageDays": 60}`

```json
{
  "detail": [
    {
      "type": "INV-001",
      "loc": ["body", "maxCoverageDays"],
      "msg": "Dias Máximo (maxCoverageDays = 60) deve ser maior que Dias Mínimo (minCoverageDays = 60).",
      "input": 60,
      "ctx": { "minCoverageDays": 60, "maxCoverageDays": 60 }
    }
  ]
}
```

**422 — `INV-002` (Lead Time ≥ Dias Máximo; A2)**

Request: `{"minCoverageDays": 20, "maxCoverageDays": 40, "leadTimeDays": 45}`

```json
{
  "detail": [
    {
      "type": "INV-002",
      "loc": ["body", "leadTimeDays"],
      "msg": "Lead Time (leadTimeDays = 45) deve ser menor que Dias Máximo (maxCoverageDays = 40).",
      "input": 45,
      "ctx": { "leadTimeDays": 45, "maxCoverageDays": 40 }
    }
  ]
}
```

**422 — faixa e tipo (Pydantic nativo)**

Request: `{"minCoverageDays": 0, "maxCoverageDays": 30.5}`

```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": ["body", "minCoverageDays"],
      "msg": "Input should be greater than or equal to 1",
      "input": 0,
      "ctx": { "ge": 1 }
    },
    {
      "type": "int_from_float",
      "loc": ["body", "maxCoverageDays"],
      "msg": "Input should be a valid integer, got a number with a fractional part",
      "input": 30.5
    }
  ]
}
```

Quando o campo de referência já falhou por tipo ou faixa, a regra cruzada que depende dele não é avaliada. Isso evita um erro duplicado: o cliente corrige um campo e reenvia.

**422 — parâmetros revogados NÃO geram erro.** `{"budgetLimit": 1000, "serviceLevel": 0.99}` retorna `200` com o mesmo resultado do cálculo padrão (CA-P056-02).

**500 — falha inesperada**

```json
{ "detail": "Não foi possível calcular a previsão de estoque. Tente novamente em instantes." }
```

O erro completo vai apenas para o log do servidor (`logger.error(..., exc_info=True)`).

---

## 6. `POST /api/v1/inventory/export-csv`

Gera o plano de compras em CSV com **exatamente o mesmo cálculo** de `/predict` para os mesmos parâmetros (P-056.6).

### 6.1 Request

Mesmo schema, mesmos padrões e mesmas regras de validação de `/predict` (seção 5.1). Os erros `422` são idênticos. O frontend **deve enviar a `politica` do resultado exibido**, mais o fornecedor selecionado, e não o rascunho do modal (tarefa F-04).

### 6.2 Resposta `200`

| Item | Valor |
| :--- | :--- |
| `Content-Type` | `text/csv; charset=utf-8` |
| `Content-Disposition` | `attachment; filename="fitoherb_plano_compras[_<slug-fornecedor>]_<AAAAMMDD_HHMMSS>.csv"`. O slug é sanitizado e só contém `[a-z0-9_]` (ADR-001, DA-11). |
| Codificação | UTF-8 com BOM (`﻿`) |
| Separador / decimal | `;` / `,` |
| Linhas | Uma por SKU, na mesma ordem de `data.produtos` |
| Lista vazia | Só o cabeçalho (o DataFrame é criado com colunas explícitas) |

**Colunas, nesta ordem (P-056.5):**

| # | Cabeçalho | Campo de origem |
| :--- | :--- | :--- |
| 1 | `Código` | `codigo` |
| 2 | `Descrição` | `descricao` |
| 3 | `EAN` | `ean` |
| 4 | `Fornecedor` | `fornecedor` |
| 5 | `Tipo/Linha` | `tipo` |
| 6 | `Estoque Físico Atual` | `estoqueAtual` |
| 7 | `Venda Média Diária (VMD)` | `vmd` |
| 8 | `Dias de Cobertura` | `diasCobertura` (`999` = sem venda com estoque; comportamento atual) |
| 9 | `Lead Time (Dias)` | `leadTime` |
| 10 | **`Estoque Mínimo (un)`** | **`estoqueMinimo`** |
| 11 | **`Estoque Máximo (un)`** | **`estoqueMaximo`** |
| 12 | `Qtd Sugerida de Compra` | `qtdSugeridaCompra` |
| 13 | `Último Custo Real (R$)` | `custoUnitario` |
| 14 | `Preço de Venda (R$)` | `precoVenda` |
| 15 | `Investimento Total Sugerido (R$)` | `investimentoTotalItem` |
| 16 | `Status Operacional` | `statusLabel` |
| 17 | `Curva ABC` | `curvaAbc` |

**Removidas:** `Estoque de Segurança`, `Ponto de Reposição (ROP)`, `Estoque Ideal`, `Demanda Teórica Plena`, `Limitado por Espaço Físico` e `Teto Físico de Compra`.

> Os cabeçalhos levam o sufixo "(un)", conforme P-056.5, CA-P056-04 e CA-11 das regras de negócio.

**Exemplo** (os mesmos 4 SKUs da seção 5.2):

```text
Código;Descrição;EAN;Fornecedor;Tipo/Linha;Estoque Físico Atual;Venda Média Diária (VMD);Dias de Cobertura;Lead Time (Dias);Estoque Mínimo (un);Estoque Máximo (un);Qtd Sugerida de Compra;Último Custo Real (R$);Preço de Venda (R$);Investimento Total Sugerido (R$);Status Operacional;Curva ABC
101;EXTRATO PROPOLIS APISFLORA;7891234567890;APIS FLORA;EXTRATOS;10,0;2,0;5,0;15;60;120;110;15,0;25,0;1650,0;Ruptura Iminente;A
102;VITAMINA C HERBARIUM;7899876543210;HERBARIUM;VITAMINAS;50,0;2,0;25,0;15;60;120;70;10,0;20,0;700,0;Abaixo do Mínimo;B
104;OMEGA 3 CATARINENSE;7891112223341;CATARINENSE;SUPLEMENTOS;90,0;2,0;45,0;15;60;120;0;12,0;22,0;0,0;Estoque Saudável;C
103;CHA VERDE CATARINENSE;7891112223334;CATARINENSE;CHAS;300,0;0,0;999,0;15;0;0;0;5,0;12,0;0,0;Acima do Máximo;C
```

### 6.3 Erros

`422`: idêntico a `/predict` (seção 5.3). Como o frontend pede `responseType: 'blob'`, o corpo do erro chega como `Blob`. O cliente mostra uma mensagem genérica de falha na exportação, porque a tela já impede parâmetros inválidos.
`500`: `{"detail": "Não foi possível gerar o arquivo CSV do plano de compras. Tente novamente em instantes."}`.

---

## 7. `GET /api/v1/inventory/health` (inalterado)

`200`: `{"status": "healthy", "service": "fitoherb-inventory-api"}`. Sem envelope: é uma sonda de infraestrutura, exceção pré-existente.

---

## 8. Tipos de referência para o frontend (TypeScript)

Ficam em `frontend/src/app/features/inventory/models/inventory.model.ts` e são a fonte de tipos do cliente (tarefa F-01). Não usar `any`.

```typescript
/** Parâmetros enviados a /predict e /export-csv (contrato 2.0.0). */
export interface InventoryParams {
  historyWindowDays: number;
  minCoverageDays: number;
  maxCoverageDays: number;
  leadTimeDays: number;
  fornecedor?: string | null;
}

/** Eco dos parâmetros efetivamente usados no cálculo (data.politica). */
export interface InventoryPolicy {
  historyWindowDays: number;
  leadTimeDays: number;
  minCoverageDays: number;
  maxCoverageDays: number;
}

export type InventoryStatus = 'CRITICAL_STOCKOUT' | 'REORDER_NEEDED' | 'HEALTHY' | 'OVERSTOCK';
export type CurvaAbc = 'A' | 'B' | 'C';

export interface InventoryKPIs {
  totalSkusAnalisados: number;
  skusEmRupturaCritica: number;
  skusNecessitamReposicao: number;
  skusEstoqueSaudavel: number;
  skusEmOverstock: number;
  investimentoTotalSugerido: number;
  capitalImobilizadoOverstock: number;
  curvaADistribuicao: { qtdItens: number; percentualItens: number };
}

export interface InventoryProductItem {
  codigo: number;
  descricao: string;
  ean: string;
  fornecedor: string;
  tipo: string;
  estoqueAtual: number;
  vmd: number;
  diasCobertura: number;
  leadTime: number;
  estoqueMinimo: number;
  estoqueMaximo: number;
  qtdSugeridaCompra: number;
  custoUnitario: number;
  precoVenda: number;
  investimentoTotalItem: number;
  status: InventoryStatus;
  statusLabel: string;
  curvaAbc: CurvaAbc;
}

export interface InventoryPredictData {
  politica: InventoryPolicy;
  kpis: InventoryKPIs;
  produtos: InventoryProductItem[];
}

export interface InventoryResponseMeta {
  timestamp: string;
  version: string;
  executionTimeMs?: number | null;
}

export interface InventoryPredictResponse {
  data: InventoryPredictData;
  meta: InventoryResponseMeta;
}

export interface RangeParameterConfig {
  default: number;
  min: number;
  max: number;
  step: number;
}

export interface InventoryConfigResponse {
  data: {
    historyWindowDays: RangeParameterConfig;
    leadTimeDays: RangeParameterConfig;
    minCoverageDays: RangeParameterConfig;
    maxCoverageDays: RangeParameterConfig;
  };
  meta: InventoryResponseMeta;
}

/** Item de erro 422 do FastAPI. `type` traz o código interno (INV-001, INV-002) ou o tipo nativo do Pydantic. */
export interface ApiValidationErrorItem {
  type: string;
  loc: Array<string | number>;
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
```

---

## 9. Padrão de documentação no código (obrigatório para o Desenvolvedor)

| Camada | Padrão |
| :--- | :--- |
| Python: topo de arquivo | Docstring do módulo com objetivo e regras implementadas (`P-053 a P-056`). Sem citar ROP/ES/z-score como vigentes. |
| Python: funções públicas e constantes de domínio | Docstring em estilo Google (Args, Returns, Raises), com uma linha `Regra: P-0XX` e o **porquê** quando a lógica não for óbvia (ex.: `ceil_units`). Constantes com comentário de intenção na mesma linha. |
| Pydantic / OpenAPI | `Field(description=...)` em PT-BR em todos os campos de request e response. `json_schema_extra={"examples": [...]}` no request com o exemplo 30/60. `status` e `curvaAbc` como `Literal[...]`. `InventoryConfigResponse.data` tipado (sem `Dict[str, Any]`). |
| Router | `summary` e `description` por rota. `responses={422: ..., 500: ...}` documentados no decorator. Docstrings sem ROP/ES. |
| TypeScript | Comentário de topo por arquivo. TSDoc (`/** */`) em interfaces, constantes e funções exportadas, com referência à regra (`P-053.3`) quando aplicável. Proibido `any` (usar `unknown` + *type guard*). |
