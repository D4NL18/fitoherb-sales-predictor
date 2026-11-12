# Contrato de API: Tendência de Vendas por Item (módulo `sales_trend`)

> **Localização Mandatória:** `.agents/docs/api_contracts/analytics-sales-trend.md` (o slug `analytics-sales-trend` é **histórico**; o módulo de código é `sales_trend`, ver ADR-003)
> **Responsável:** Arquiteto (`api-contract-expert`)
> **Referências de Regras:** `.agents/rules/backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Módulo backend** | `src/modules/sales_trend/` (FastAPI + Pydantic v2), independente do módulo `analytics` (cross-sell) |
| **Consumidor** | `frontend/src/app/features/sales-trend/` (Angular 18), único consumidor; página `/tendencia-vendas` |
| **Versão do contrato** | **1.0.0** (`meta.version`, constante `SALES_TREND_CONTRACT_VERSION`). Nada foi implementado, então as revisões de 2026-11-09 e 2026-11-10 não mudam a versão |
| **Regras** | P-072 a P-093 (`business_rules/analytics-sales-trend.md`) |
| **Decisões** | `adr/ADR-003-tendencia-vendas.md` (DA-01 a DA-16) |
| **Design Plan** | `design/plans/analytics-sales-trend.md` (dúvidas Q-1 a Q-17 respondidas na seção 6) |
| **Autenticação** | HTTP Basic do middleware global `HTTPBasicAuthASGIMiddleware` (`src/core/auth.py`), ativo em produção (P-033). Vale para todas as rotas abaixo. Sem 401 específico do módulo |
| **Privacidade** | Sem dado pessoal em qualquer campo (P-085): nenhum `Cod Cliente`, pedido, nome, documento, endereço ou contato. O `fornecedor` é nome de fabricante/marca (catálogo) |
| **Universo** | **Somente produtos ativos do catálogo atual (`Pc.Venda > 0`)** com movimento no período. Produto com venda histórica e fora do catálogo ativo **não aparece em nenhuma lista, soma de fornecedor nem total** (ADR-003 DA-16). Não há filtro `activeOnly`, campo `ativo` nem selo "Inativo" |
| **Autor / Data** | Arquiteto (Etapa 2) — 2026-11-09, revisado em 2026-11-10 |

---

## 1. Visão Geral

- **Prefixo Base:** `/api/v1/sales-trend`
- **Protocolo:** HTTP/REST, `application/json; charset=utf-8`
- **Convenção de Nomenclatura:** `camelCase` em todos os payloads (atributos Python em `snake_case` com `alias_generator=to_camel`). **Parâmetros de query** também em `camelCase` (`baseMonth`, `sortWindow`, `minVolume`, `supplierKey`). Os valores de enum de entrada ficam em inglês minúsculo (`quantity`, `revenue`, `product`, `supplier`, `asc`, `desc`, `all`, `rising`, `falling`, `new`, `contribution`, `variation`) e os de estado de célula em maiúsculas (`VARIACAO`, `NOVO`, `SEM_MOVIMENTO`, `SEM_BASE`), como em P-078 e P-084.
- **Idioma dos campos de negócio:** os nomes de domínio seguem o Glossário (seção 4): `fornecedor`, `atual`, `anterior`, `variacaoPct`, `mesBase`. Os de infraestrutura são `timestamp`, `version`, `page`, `limit`, `offset`, `totalItems`, `totalPages`, `dataReferencia`.
- **Erros:** códigos `TND-001` a `TND-005`, todos definidos neste contrato (seção 5).

| Método | Rota | Descrição | Regras |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/sales-trend` | Lista paginada da tendência, por produto (padrão) ou por fornecedor (`groupBy`). O `meta` traz tudo que o seletor de Mês-Base precisa | P-072 a P-091, P-084 |
| `GET` | `/api/v1/sales-trend/supplier-products` | Produtos de um fornecedor (detalhe sob demanda), paginado, com variação própria e contribuição | P-090, P-092 |
| `GET` | `/api/v1/sales-trend/health` | Estado do snapshot (frio, carregando, quente, expirado), **sem** disparar carga nem acessar o banco; serve ao aviso de cache frio (Q-14) | P-083.6 |
| `POST` | `/api/v1/sales-trend/reload` | Recarga manual do snapshot (respeita o lock e o intervalo mínimo de 15 min). **Não é chamada pela tela** | P-083.2 |

> Não existe rota separada para o seletor de Mês-Base: a primeira chamada da lista (sem `baseMonth`) já devolve `mesBasePadrao`, `mesBaseMinimo`, `mesBaseMaximo` e `ultimoDiaCoberto` em `meta` (P-084.3, ADR-003 DA-08).

### 1.1 Cálculo no servidor, nada de SQL por requisição

Todas as respostas saem de um **snapshot em memória** (TTL de 6 h, voo único). Trocar `metric`, `baseMonth`, `groupBy`, `view`, `sortWindow`, `sortDir`, `q`, `minVolume`, página, ou expandir um fornecedor **não consulta o banco** (P-073.5, P-083.5, P-093.3). Só a primeira chamada após o TTL (ou após `reload`) espera a carga (alguns segundos).

### 1.2 Ordem de avaliação (P-082.1)

1. Formato e domínio dos parâmetros → `400 TND-001` (inclusive `q`, `limit`, `offset`, `supplierKey` ausente).
2. Obtenção do snapshot → `503 TND-004`.
3. Mês-Base vs snapshot: futuro → `400 TND-001` (campo `baseMonth`); anterior à primeira venda, mês corrente sem dia fechado ou base vazia → `422 TND-002`.
4. Só no detalhe: `supplierKey` inexistente no universo → `404 TND-003`.

---

## 2. Padrão de Envelope de Resposta

### 2.1 `meta` comum (`TrendMeta`), presente em toda resposta 2xx de lista e de detalhe

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `timestamp` | string ISO-8601 UTC | Momento da resposta (`...Z`, milissegundos) | P-066 |
| `version` | string | `"1.0.0"` | — |
| `dataReferencia` | string `AAAA-MM-DD` | **Data de referência do snapshot** (data de negócio em UTC-3 no instante da carga). Nunca é o relógio da requisição | P-083.3 |
| `ultimoDiaCoberto` | string `AAAA-MM-DD` | `dataReferencia` menos 1 dia: último dia fechado. A tela mostra "Dados até DD/MM/AAAA" com este campo | P-076.1 |
| `mesBase` | string `AAAA-MM` | Mês-Base efetivamente usado (o pedido ou `mesBasePadrao`) | P-074.6 |
| `mesBasePadrao` | string `AAAA-MM` | Mês anterior ao da `dataReferencia` | P-074.1 |
| `mesBaseMinimo` | string `AAAA-MM` | Mês da primeira venda da base (hoje `2025-01`), lido do banco (considera todos os produtos, não só os ativos) | P-074.2 |
| `mesBaseMaximo` | string `AAAA-MM` | Mês da `dataReferencia` (mês corrente, parcial) | P-074.2 |
| `mesBaseParcial` | boolean | `true` quando `mesBase == mesBaseMaximo` (a janela atual cobre só os dias fechados do mês corrente) | P-074.3 |
| `metrica` | `"quantity"` \| `"revenue"` | Métrica efetiva | P-073 |
| `janelas` | `TrendWindowMeta[4]` | Descrição das 4 janelas, na ordem `1, 3, 6, 12` (2.2) | P-084.3 |
| `parametros` | `TrendParameters` | Constantes efetivas do domínio, para a tela não fixar números na copy (Q-9). Ver tabela abaixo | A-7, A-2 |
| `page`, `limit`, `offset`, `totalItems`, `totalPages` | int | Paginação: `page = floor(offset / limit) + 1`; `totalPages = ceil(totalItems / limit)` (0 sem itens) | P-066, P-081.4 |

**`meta.parametros` (`TrendParameters`, Q-9).** Eco das constantes do domínio em vigor. Valores globais, sem dado pessoal. A tela interpola estes valores (ex.: "menos de {limiteBaseBaixaQuantidade} un na janela anterior") e **nunca** fixa "10 un / R$ 500,00" ou "50%" (os limiares de base baixa são calibráveis, A-7).

| Campo | Tipo | Constante | Valor atual |
| :--- | :--- | :--- | :--- |
| `limiteBaseBaixaQuantidade` | number | `LOW_BASE_MIN_QUANTITY` | `10.0` |
| `limiteBaseBaixaFaturamento` | number | `LOW_BASE_MIN_REVENUE` | `500.0` |
| `coberturaMinimaAnterior` | number (razão 0..1) | `MIN_PREVIOUS_COVERAGE_RATIO` | `0.5` |
| `buscaMinCaracteres` | int | `MIN_TEXT_QUERY_LENGTH` | `2` |
| `buscaMinCaracteresNumerica` | int | `MIN_DIGITS_QUERY_LENGTH` | `1` |
| `buscaMaxCaracteres` | int | `MAX_QUERY_LENGTH` | `60` |
| `ttlCacheHoras` | int | `CACHE_TTL_HOURS` | `6` |

> `mesBaseMaximo` é o mês da `dataReferencia` mesmo no dia 1, quando ainda não há dia fechado nele; escolhê-lo devolve `422 TND-002` (P-074.5). A tela pode desabilitar essa opção quando `ultimoDiaCoberto` for anterior ao primeiro dia de `mesBaseMaximo`.

**`meta` da lista** (`TrendListMeta`, estende `TrendMeta`) acrescenta:

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `agrupamento` | `"product"` \| `"supplier"` | Eco de `groupBy`; discrimina o tipo de `data[]` (produto ou fornecedor) |
| `visao` | `"all"` \| `"rising"` \| `"falling"` \| `"new"` | Eco de `view` |
| `ordenacao` | `{ janela: 1\|3\|6\|12, sentido: "asc"\|"desc" }` | Ordenação **efetiva** (o `sentido` já resolve o padrão da visão: `falling` → `asc`, demais → `desc`) |
| `totaisPorVisao` | `{ todos, maioresAltas, maioresQuedas, novos }` (ints) | Quantidade de linhas de cada visão **com os demais filtros aplicados** (`q`, `minVolume`) e relativa à `ordenacao.janela`; **não** depende de `view`. Permite rotular o controle segmentado ("Maiores quedas (3)") e desabilitar visões vazias. `totalItems` é igual ao total da visão ativa |
| `total` | `TrendTotalRow` | **Linha "Todos os produtos" (Q-4):** `{ qtdProdutos, janelas[4] }`, com a mesma forma de célula, calculada sobre a **soma líquida de todos os produtos ativos com movimento** do universo, tratada como um único grupo (mesmas regras de P-089: soma bruta, cobertura, piso zero, `NOVO`/`SEM_BASE`, `baseBaixa`). **Ignora** `q`, `view` e `minVolume`. É o ponto de referência ("a empresa subiu X%; este fornecedor caiu Y%"). Presente nas duas visões. A tela pode ocultar a linha, mas o campo está sempre presente |

**`meta` do detalhe** (`TrendDetailMeta`, estende `TrendMeta`) acrescenta:

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `ordenacao` | `{ por: "contribution"\|"variation", janela: 1\|3\|6\|12, sentido: "asc"\|"desc" }` | Ordenação efetiva do detalhe |
| `fornecedor` | `TrendSupplierRow` | A **mesma** linha de fornecedor que a lista devolve (soma completa, não afetada por `q`), para a tela conferir e exibir o total acima dos filhos (P-092.6) |

### 2.2 `TrendWindowMeta` (item de `meta.janelas[]`)

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `meses` | `1` \| `3` \| `6` \| `12` | Tamanho da janela |
| `atual` / `anterior` | `TrendWindowSpan` | Janela Atual (termina no Mês-Base) e Janela Anterior (os X meses imediatamente anteriores) |
| `semBase` | boolean | `true` quando a Janela Anterior tem cobertura < 50% (toda a coluna é `SEM_BASE`, P-076.6, P-078.7) |
| `baseParcial` | boolean | `true` quando a comparação usa média diária (alguma das janelas com cobertura < 100%) e `semBase = false` (P-076.4) |

`TrendWindowSpan`:

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `inicio` | string `AAAA-MM-DD` | Primeiro dia do primeiro mês da janela |
| `fim` | string `AAAA-MM-DD` | Último dia do último mês da janela |
| `diasJanela` | int | Dias corridos da janela (P-075.3) |
| `diasCobertos` | int | Dias da janela dentro de `[primeira venda, ultimoDiaCoberto]` (P-076.2) |

A tela monta o cabeçalho da coluna ("ago–out/26 vs mai–jul/26") a partir de `inicio` e `fim` (`utils/trend-format.ts`). Os rótulos de selo e os tooltips **não** vêm da API (seção 6).

### 2.3 Paginação (query params das rotas de lista e detalhe)

| Parâmetro | Tipo | Obrigatório? | Default | Faixa | Erro fora da faixa |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `limit` | integer | Não | `50` | 1 a 200 | `400 TND-001` (sem truncamento silencioso) |
| `offset` | integer | Não | `0` | ≥ 0 | `400 TND-001` |

O **detalhe do fornecedor** (3.2) tem `limit` padrão **20** (Q-5; a lista fica em 50); o máximo continua 200. `offset >= totalItems` → `200` com `data: []` e totais corretos (P-081.4). O projeto usa `limit`/`offset` (decisão do plano §2.7 e P-066) em vez de `page`/`page_size` do template; `page` é devolvido no `meta`.

### 2.4 Precisão numérica e tipos

| Campo | Tipo JSON | Precisão | Observação |
| :--- | :--- | :--- | :--- |
| `variacaoPct`, `contribuicaoPp` | number \| `null` | 1 casa, **meio para cima** sobre a magnitude (12,25 → 12,3; −12,25 → −12,3) | Calculados de forma exata (razão de inteiros) e arredondados só na saída (ADR-003 DA-06) |
| `atual`, `anterior` (`metrica = revenue`) | number | 2 casas | **Total líquido bruto** (pode ser negativo), mesmo quando a variação usou média diária |
| `atual`, `anterior` (`metrica = quantity`) | number | até 3 casas | Idem; inteiros aparecem como `30.0` |
| `atualPorDia`, `anteriorPorDia` | number \| `null` | 4 casas | Só quando `baseParcial = true`; piso zero aplicado |
| `contribuicaoValor` | number \| `null` | 2 casas (revenue) / 3 (quantity); 4 casas quando `baseParcial` (valor por dia) | `atual − anterior` do SKU, bruto |
| `codigo`, `qtdProdutos`, `meses`, `diasJanela`, `diasCobertos`, `page`, `limit`, `offset`, `totalItems`, `totalPages` | int | — | — |

### 2.5 Enums

| Enum | Valores | Onde |
| :--- | :--- | :--- |
| `status` (célula) | `VARIACAO`, `NOVO`, `SEM_MOVIMENTO`, `SEM_BASE` | `janelas[].status`; precedência de avaliação: `SEM_BASE` → `VARIACAO` → `NOVO` → `SEM_MOVIMENTO` (P-078) |
| `metric` / `metrica` | `quantity`, `revenue` | query / `meta` |
| `groupBy` / `agrupamento` | `product`, `supplier` | query / `meta` |
| `view` / `visao` | `all`, `rising`, `falling`, `new` | query / `meta` |
| `sortDir` / `sentido` | `asc`, `desc` | query / `meta` |
| `sortBy` / `ordenacao.por` | `contribution`, `variation` | query do detalhe / `meta` |
| `sortWindow` / `janela` / `meses` | `1`, `3`, `6`, `12` | query (inteiro) / `meta` |

---

## 3. Endpoints

### 3.1 `GET /api/v1/sales-trend`

- **Objetivo:** tabela de todos os produtos ativos (ou fornecedores) com a variação % de vendas nas janelas de 1, 3, 6 e 12 meses (P-072 a P-091).
- **Cache:** snapshot em memória; ver 1.1.

**Query Parameters (todos opcionais):**

| Parâmetro | Tipo | Default | Validação | Descrição | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `baseMonth` | string | `mesBasePadrao` | Regex `^\d{4}-(0[1-9]\|1[0-2])$` (mês 01 a 12), senão `400`. Depois da leitura do snapshot: `> mesBaseMaximo` → `400 TND-001`; `< mesBaseMinimo` ou mês corrente sem dia fechado → `422 TND-002` | Mês-Base (`AAAA-MM`) | P-074 |
| `metric` | string | `revenue` | `quantity` \| `revenue` | Métrica líquida de devoluções | P-073 |
| `groupBy` | string | `product` | `product` \| `supplier` | Visão por produto ou por fornecedor | P-088 |
| `sortWindow` | integer | `3` | `1`, `3`, `6` ou `12` | Coluna de ordenação | P-080.1 |
| `sortDir` | string | `desc`; `asc` se `view=falling` | `asc` \| `desc`. Se informado, prevalece sobre o padrão da visão | Sentido da ordenação por %. Com `view=new` não tem efeito (ordem de P-080.2) | P-080.1, P-080.4 |
| `view` | string | `all` | `all` \| `rising` \| `falling` \| `new` | Atalho relativo a `sortWindow` | P-080.4 |
| `q` | string | sem filtro | Após `trim` e colapso de espaços: 1 a 60 caracteres se só dígitos, 2 a 60 nos demais; em branco = sem filtro; fora disso `400` | Por produto: código (igual ou que começa com) ou descrição (contém). Por fornecedor: nome (contém). Sem acento e sem diferenciar maiúsculas | P-081.1, P-091.2 |
| `minVolume` | number | `0` | `>= 0`, finito (sem `NaN`/`inf`), máximo `1000000000` | Na unidade da métrica (un ou R$): remove só linhas `VARIACAO` cuja Janela Anterior (total líquido) na `sortWindow` é menor que o valor | P-079.3 |
| `limit` / `offset` | integer | `50` / `0` | 2.3 | Paginação | P-081.4 |

Parâmetros desconhecidos (inclusive o antigo `activeOnly`) são **ignorados**. Qualquer valor inválido responde `400 TND-001` com **todos** os campos inválidos em `fields`, sem eco do valor.

**Resposta `200`:** `ProductTrendResponse` (`groupBy=product`) ou `SupplierTrendResponse` (`groupBy=supplier`), distinguidas por `meta.agrupamento`.

#### 3.1.1 Linha de produto (`TrendProductRow`)

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `codigo` | int | Código do SKU (`Cod Produto`) | P-084.2 |
| `descricao` | string | Descrição do catálogo ativo. **Sempre preenchida** (produto sem cadastro ativo não entra no universo) | P-084.2 |
| `fornecedor` | string \| `null` | Fornecedor do catálogo atual, aparado e com espaços colapsados; `null` se nulo ou em branco (o produto pertence ao grupo "Sem fornecedor") | P-089.2 |
| `janelas` | `TrendCell[4]` | As quatro janelas, na ordem `1, 3, 6, 12`, **sempre as quatro**, qualquer que seja a coluna de ordenação | P-072.5 |

#### 3.1.2 Linha de fornecedor (`TrendSupplierRow`)

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `fornecedor` | string | Nome exibido (menor grafia ordinal entre as variantes); `"Sem fornecedor"` no grupo reservado | P-089.1, P-089.2 |
| `fornecedorChave` | string | Chave **opaca** do grupo: `"f:" + nome normalizado` ou `"sem-fornecedor"`. Vai de volta em `supplierKey` no detalhe. A tela não interpreta o conteúdo | P-092.1 |
| `semFornecedor` | boolean | `true` só no grupo reservado (a tela rotula "Sem fornecedor" sem tratamento de erro) | P-089.2 |
| `qtdProdutos` | int | Produtos **ativos** do fornecedor com movimento no período | P-089.8 |
| `janelas` | `TrendCell[4]` | Cálculo sobre a **soma líquida** dos produtos ativos do fornecedor (nunca média das %) | P-089.3 |

A lista de fornecedores **não** traz os produtos filhos (P-092).

#### 3.1.3 Exemplo `200` por produto

`GET /api/v1/sales-trend?baseMonth=2026-10&metric=quantity&sortWindow=1&limit=2` (massa sintética da seção 5 das regras, **só produtos ativos**: o SKU 1008, descontinuado, não está no catálogo ativo e não conta; `dataReferencia = 2026-11-09`):

```json
{
  "data": [
    {
      "codigo": 1007,
      "descricao": "ÓLEO DE COCO",
      "fornecedor": "LABORATÓRIO BETA",
      "janelas": [
        { "meses": 1, "atual": 3.0, "anterior": 1.0, "variacaoPct": 200.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": true, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.011, "anteriorPorDia": 0.0 }
      ]
    },
    {
      "codigo": 1001,
      "descricao": "CHÁ VERDE 100G",
      "fornecedor": "LABORATÓRIO ALFA",
      "janelas": [
        { "meses": 1, "atual": 30.0, "anterior": 20.0, "variacaoPct": 50.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 70.0, "anterior": 60.0, "variacaoPct": 16.7, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 130.0, "anterior": 120.0, "variacaoPct": 8.3, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 250.0, "anterior": 98.0, "variacaoPct": 108.3, "status": "VARIACAO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.6849, "anteriorPorDia": 0.3289 }
      ]
    }
  ],
  "meta": {
    "timestamp": "2026-11-09T15:10:00.000Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-09",
    "ultimoDiaCoberto": "2026-11-08",
    "mesBase": "2026-10",
    "mesBasePadrao": "2026-10",
    "mesBaseMinimo": "2025-01",
    "mesBaseMaximo": "2026-11",
    "mesBaseParcial": false,
    "metrica": "quantity",
    "agrupamento": "product",
    "visao": "all",
    "ordenacao": { "janela": 1, "sentido": "desc" },
    "totaisPorVisao": { "todos": 7, "maioresAltas": 2, "maioresQuedas": 2, "novos": 2 },
    "total": {
      "qtdProdutos": 7,
      "janelas": [
        { "meses": 1, "atual": 76.0, "anterior": 88.0, "variacaoPct": -13.6, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 184.0, "anterior": 60.0, "variacaoPct": 206.7, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 244.0, "anterior": 120.0, "variacaoPct": 103.3, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 364.0, "anterior": 108.0, "variacaoPct": 175.2, "status": "VARIACAO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.9973, "anteriorPorDia": 0.3624 }
      ]
    },
    "parametros": {
      "limiteBaseBaixaQuantidade": 10.0, "limiteBaseBaixaFaturamento": 500.0, "coberturaMinimaAnterior": 0.5,
      "buscaMinCaracteres": 2, "buscaMinCaracteresNumerica": 1, "buscaMaxCaracteres": 60, "ttlCacheHoras": 6
    },
    "janelas": [
      { "meses": 1,
        "atual":    { "inicio": "2026-10-01", "fim": "2026-10-31", "diasJanela": 31, "diasCobertos": 31 },
        "anterior": { "inicio": "2026-09-01", "fim": "2026-09-30", "diasJanela": 30, "diasCobertos": 30 },
        "semBase": false, "baseParcial": false },
      { "meses": 3,
        "atual":    { "inicio": "2026-08-01", "fim": "2026-10-31", "diasJanela": 92, "diasCobertos": 92 },
        "anterior": { "inicio": "2026-05-01", "fim": "2026-07-31", "diasJanela": 92, "diasCobertos": 92 },
        "semBase": false, "baseParcial": false },
      { "meses": 6,
        "atual":    { "inicio": "2026-05-01", "fim": "2026-10-31", "diasJanela": 184, "diasCobertos": 184 },
        "anterior": { "inicio": "2025-11-01", "fim": "2026-04-30", "diasJanela": 181, "diasCobertos": 181 },
        "semBase": false, "baseParcial": false },
      { "meses": 12,
        "atual":    { "inicio": "2025-11-01", "fim": "2026-10-31", "diasJanela": 365, "diasCobertos": 365 },
        "anterior": { "inicio": "2024-11-01", "fim": "2025-10-31", "diasJanela": 365, "diasCobertos": 298 },
        "semBase": false, "baseParcial": true }
    ],
    "page": 1, "limit": 2, "offset": 0, "totalItems": 7, "totalPages": 4
  }
}
```

Leitura do exemplo: o SKU 1007 é o primeiro porque +200,0% é a maior variação em 1 mês (CA-11, CA-15); nas janelas de 3, 6 e 12 meses ele é `NOVO` (sem venda líquida na anterior); a de 12 meses herda `baseParcial` porque a Janela Anterior cobre 298 de 365 dias. O SKU 1001 reproduz CA-02 e CA-03. `total` é a soma dos 7 produtos ativos com movimento (1001 a 1007); o descontinuado 1008 e o 1010 (venda só em nov/26, depois do Mês-Base) ficam de fora.

> Se a massa sintética do Analista mudar (por exemplo, o SKU 1008 passar a ser ativo), os exemplos desta seção devem ser recalculados; o teste T-09 compara a resposta com eles.

#### 3.1.4 Exemplo `200` por fornecedor

`GET /api/v1/sales-trend?groupBy=supplier&baseMonth=2026-10&metric=quantity&sortWindow=1&limit=2` (CA-29, CA-30, CA-32 revisados para só produtos ativos). `meta` igual ao anterior, exceto os campos abaixo (`total` é o mesmo: não depende de `groupBy`).

```json
{
  "data": [
    {
      "fornecedor": "LABORATÓRIO BETA",
      "fornecedorChave": "f:laboratorio beta",
      "semFornecedor": false,
      "qtdProdutos": 1,
      "janelas": [
        { "meses": 1, "atual": 3.0, "anterior": 1.0, "variacaoPct": 200.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": true, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 4.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.011, "anteriorPorDia": 0.0 }
      ]
    },
    {
      "fornecedor": "LABORATÓRIO ALFA",
      "fornecedorChave": "f:laboratorio alfa",
      "semFornecedor": false,
      "qtdProdutos": 2,
      "janelas": [
        { "meses": 1, "atual": 30.0, "anterior": 70.0, "variacaoPct": -57.1, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 120.0, "anterior": 60.0, "variacaoPct": 100.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 180.0, "anterior": 120.0, "variacaoPct": 50.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 300.0, "anterior": 98.0, "variacaoPct": 149.9, "status": "VARIACAO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.8219, "anteriorPorDia": 0.3289 }
      ]
    }
  ],
  "meta": {
    "agrupamento": "supplier",
    "totaisPorVisao": { "todos": 4, "maioresAltas": 1, "maioresQuedas": 2, "novos": 1 },
    "page": 1, "limit": 2, "offset": 0, "totalItems": 4, "totalPages": 2
  }
}
```

(O `meta` real traz todos os campos de 2.1; aqui só os que mudam.) Ordem `desc` por `sortWindow = 1`: Beta (+200,0%), Alfa (−57,1%), **Sem fornecedor** (−100,0%), Gama (`NOVO`). O grupo reservado tem este formato:

```json
{
  "fornecedor": "Sem fornecedor",
  "fornecedorChave": "sem-fornecedor",
  "semFornecedor": true,
  "qtdProdutos": 2,
  "janelas": [
    { "meses": 1, "atual": -7.0, "anterior": 20.0, "variacaoPct": -100.0, "status": "VARIACAO",
      "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": true, "atualPorDia": null, "anteriorPorDia": null }
  ]
}
```

(Janelas de 3, 6 e 12 omitidas por brevidade.) Note que `atual = -7.0` é o **líquido bruto**; o piso zero só entra no cálculo (−100,0%) e no selo `devolucaoLiquida`.

**Exemplo vazio legítimo** (`view=rising` com nenhum item, ou `offset` além do fim): `200` com `"data": []`, `totalItems` coerente com a visão e `totalPages` correspondente (0 sem itens). `meta.janelas` continua presente.

---

### 3.2 `GET /api/v1/sales-trend/supplier-products`

- **Objetivo:** listar, sob demanda (quando o usuário expande a linha), os produtos ativos de **um** fornecedor com a variação própria e a contribuição de cada um para a variação do fornecedor (P-090, P-092). Não é chamada pela lista.

**Query Parameters:**

| Parâmetro | Tipo | Obrigatório? | Default | Validação | Descrição | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `supplierKey` | string | **Sim** | — | 1 a 200 caracteres; ausente ou vazio → `400 TND-001`. Inexistente no universo → `404 TND-003` | `fornecedorChave` devolvida pela lista (valor opaco). Vai na **query string**: o nome pode ter barra, acento e espaço | P-092.1 |
| `baseMonth` | string | Não | `mesBasePadrao` | Igual a 3.1 | **Deve ser o mesmo da lista** para fechar a conta | P-092.2 |
| `metric` | string | Não | `revenue` | Igual a 3.1 | Idem | P-092.2 |
| `sortBy` | string | Não | `contribution` | `contribution` \| `variation` | `contribution`: por `contribuicaoValor` da `sortWindow`; `variation`: por % própria (regras de P-080) | P-092.4 |
| `sortWindow` | integer | Não | `3` | `1`, `3`, `6` ou `12` | Janela de ordenação | P-092.2 |
| `sortDir` | string | Não | `desc` | `asc` \| `desc` | Com `contribution`: `desc` = quem mais puxou a alta, `asc` = quem mais puxou a queda | P-092.4 |
| `q` | string | Não | sem filtro | Igual a 3.1 | Busca de **produto** (código ou descrição), não de fornecedor | P-081.1 |
| `limit` / `offset` | integer | Não | **`20`** / `0` | 2.3 (1 a 200) | Paginação dos filhos. Padrão 20 (Q-5, paginador do Design Plan D-9) | P-092.5 |

`view` e `minVolume`, se enviados, são **ignorados** (não se aplicam ao detalhe, P-091.3, P-092.2). `totalItems` = número de filhos após `q`; com `q`, os filhos exibidos podem não somar a linha do fornecedor, mas `meta.fornecedor` continua com a soma completa (P-092.5).

**Linha filha (`TrendDetailRow`):** `TrendProductRow` com `janelas` do tipo `TrendDetailCell` (`TrendCell` mais `contribuicaoPp` e `contribuicaoValor`). Filhos = produtos **ativos** do fornecedor com movimento no período (P-092.3). A linha filha é a **mesma** linha da visão por produto (mesmos números) mais a contribuição (P-088.3).

**Regras de `contribuicaoPp` e `contribuicaoValor` (por janela):**

| Situação | `contribuicaoPp` | `contribuicaoValor` |
| :--- | :--- | :--- |
| Normal | `(atual − anterior) ÷ anteriorF × 100` do SKU (bruto) sobre a soma do fornecedor; 1 casa | `atual − anterior` do SKU (bruto), na unidade da métrica |
| `baseParcial = true` | mesma fórmula sobre médias diárias | **por dia** (4 casas); a tela rotula "por dia" |
| `status = SEM_BASE` | `null` | `null` |
| Fornecedor com `anteriorF ≤ 0` (`NOVO` ou `SEM_MOVIMENTO`) | `null` (divisão por zero) | calculado normalmente |

**Resposta `200` (`SupplierDetailResponse`):** `data = TrendDetailRow[]`, `meta = TrendDetailMeta`.

`GET /api/v1/sales-trend/supplier-products?supplierKey=f%3Alaboratorio%20alfa&baseMonth=2026-10&metric=quantity&sortWindow=1`:

```json
{
  "data": [
    {
      "codigo": 1001,
      "descricao": "CHÁ VERDE 100G",
      "fornecedor": "LABORATÓRIO ALFA",
      "janelas": [
        { "meses": 1, "atual": 30.0, "anterior": 20.0, "variacaoPct": 50.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": 14.3, "contribuicaoValor": 10.0 },
        { "meses": 3, "atual": 70.0, "anterior": 60.0, "variacaoPct": 16.7, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": 16.7, "contribuicaoValor": 10.0 },
        { "meses": 6, "atual": 130.0, "anterior": 120.0, "variacaoPct": 8.3, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": 8.3, "contribuicaoValor": 10.0 },
        { "meses": 12, "atual": 250.0, "anterior": 98.0, "variacaoPct": 108.3, "status": "VARIACAO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.6849, "anteriorPorDia": 0.3289,
          "contribuicaoPp": 108.3, "contribuicaoValor": 0.3561 }
      ]
    },
    {
      "codigo": 1003,
      "descricao": "GUARANÁ EM PÓ",
      "fornecedor": "LABORATÓRIO ALFA",
      "janelas": [
        { "meses": 1, "atual": 0.0, "anterior": 50.0, "variacaoPct": -100.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": -71.4, "contribuicaoValor": -50.0 },
        { "meses": 3, "atual": 50.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": 83.3, "contribuicaoValor": 50.0 },
        { "meses": 6, "atual": 50.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null,
          "contribuicaoPp": 41.7, "contribuicaoValor": 50.0 },
        { "meses": 12, "atual": 50.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.137, "anteriorPorDia": 0.0,
          "contribuicaoPp": 41.7, "contribuicaoValor": 0.137 }
      ]
    }
  ],
  "meta": {
    "timestamp": "2026-11-09T15:10:05.000Z",
    "version": "1.0.0",
    "dataReferencia": "2026-11-09",
    "ultimoDiaCoberto": "2026-11-08",
    "mesBase": "2026-10",
    "mesBasePadrao": "2026-10",
    "mesBaseMinimo": "2025-01",
    "mesBaseMaximo": "2026-11",
    "mesBaseParcial": false,
    "metrica": "quantity",
    "ordenacao": { "por": "contribution", "janela": 1, "sentido": "desc" },
    "parametros": { "...": "igual a 2.1 / 3.1.3" },
    "fornecedor": {
      "fornecedor": "LABORATÓRIO ALFA",
      "fornecedorChave": "f:laboratorio alfa",
      "semFornecedor": false,
      "qtdProdutos": 2,
      "janelas": [
        { "meses": 1, "atual": 30.0, "anterior": 70.0, "variacaoPct": -57.1, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 3, "atual": 120.0, "anterior": 60.0, "variacaoPct": 100.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 6, "atual": 180.0, "anterior": 120.0, "variacaoPct": 50.0, "status": "VARIACAO",
          "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null },
        { "meses": 12, "atual": 300.0, "anterior": 98.0, "variacaoPct": 149.9, "status": "VARIACAO",
          "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.8219, "anteriorPorDia": 0.3289 }
      ]
    },
    "janelas": [ "... igual a 3.1.3 ..." ],
    "page": 1, "limit": 20, "offset": 0, "totalItems": 2, "totalPages": 1
  }
}
```

Cada linha filha traz, **por janela**, tudo que a sub-tabela "Valores por janela" (Design Plan D-8) precisa: `atual` e `anterior` (totais), `atualPorDia`/`anteriorPorDia` (quando `baseParcial`), `contribuicaoValor` e `contribuicaoPp`; os períodos e os dias cobertos vêm de `meta.janelas`. O mesmo vale para as linhas da lista (produto e fornecedor) e para `meta.fornecedor`.

**Invariante do "por dia" (Q-3):** `contribuicaoValor` é **por dia** se e somente se a célula tem `baseParcial = true`; não há campo `porDia` separado (ver Q-3 na seção 6).

Fecho da conta, verificável no exemplo (1m): `10 + (−50) = −40 = 30 − 70` (valor) e `14,3 + (−71,4) = −57,1` (p.p.). Em 12 meses, `108,3 + 41,7 = 150,0` difere de `149,9` por arredondamento de exibição (até 0,1 p.p., P-090.4). O `meta.janelas` do exemplo é o mesmo de 3.1.3 (abreviado).

**Erros:** `400 TND-001` (`supplierKey` ausente/vazio/maior que 200, demais parâmetros inválidos, `baseMonth` futuro), `404 TND-003` (chave inexistente no universo de produtos ativos, inclusive por troca de Mês-Base ou porque o fornecedor deixou de ter produto ativo com movimento), `422 TND-002`, `503 TND-004`. `TND-005` não ocorre aqui (Q-16).

**Coerência lista × detalhe (P-092.7):** se `meta.dataReferencia` do detalhe for diferente da `dataReferencia` da lista exibida (recarga do snapshot entre as chamadas), a tela recarrega a lista.

---

### 3.3 `GET /api/v1/sales-trend/health`

- **Objetivo (Q-14):** informar o estado do snapshot para a tela avisar sobre a carga fria **antes** da primeira consulta, sem disparar carga nem acessar o banco (P-083.6). Sem parâmetros.
- **Resposta `200` (`SalesTrendCacheResponse`, o mesmo `data` de 3.4):**

| Campo `data` | Tipo | Descrição |
| :--- | :--- | :--- |
| `estadoCache` | `"FRIO"` \| `"CARREGANDO"` \| `"QUENTE"` \| `"EXPIRADO"` | `FRIO` = nunca carregou; `CARREGANDO` = carga em andamento; `QUENTE` = dentro do TTL; `EXPIRADO` = a próxima consulta recarrega |
| `carregadoEm` / `expiraEm` | string ISO-8601 \| `null` | `expiraEm = carregadoEm + 6 h`; `null` com cache frio |
| `duracaoUltimaCargaMs` | int \| `null` | Duração da última carga, para estimar a espera do primeiro acesso |
| `contagens` | `{ skus, meses, linhasAgregado, fornecedores }` (ints) \| `null` | Só agregados; nenhum nome, SKU ou fornecedor. `skus` = produtos ativos retidos. `null` com cache frio |

```json
{
  "data": { "estadoCache": "FRIO", "carregadoEm": null, "expiraEm": null, "duracaoUltimaCargaMs": null, "contagens": null },
  "meta": { "timestamp": "2026-11-09T15:10:00.000Z", "version": "1.0.0", "dataReferencia": null }
}
```

`meta.dataReferencia` é `null` só com o cache frio. **Erros:** nenhum específico (a rota não acessa o banco). Se o frontend preferir não chamar o health, o aviso por tempo (> 4 s na primeira consulta) continua funcionando sozinho.

---

### 3.4 `POST /api/v1/sales-trend/reload`

- **Objetivo:** recarga manual do snapshot (P-083.2). Sem corpo. Bloqueia até a carga terminar; requisições simultâneas aguardam o mesmo lock e reaproveitam o resultado. **A tela não chama esta rota**; uso operacional via `curl`.
- **Resposta `200` (`SalesTrendCacheResponse`):** mesmo `data` de 3.3, com o novo snapshot (`estadoCache = QUENTE`).

```json
{
  "data": {
    "estadoCache": "QUENTE",
    "carregadoEm": "2026-11-09T15:20:11.418Z",
    "expiraEm": "2026-11-09T21:20:11.418Z",
    "duracaoUltimaCargaMs": 2310,
    "contagens": { "skus": 1398, "meses": 23, "linhasAgregado": 31240, "fornecedores": 121 }
  },
  "meta": { "timestamp": "2026-11-09T15:20:12.000Z", "version": "1.0.0", "dataReferencia": "2026-11-09" }
}
```

(Números ilustrativos.) **Erros:** `429 TND-005` (última carga há menos de 15 minutos; não toca o banco), `503 TND-004` (o snapshot anterior continua valendo, P-083.2).

---

## 4. O objeto `TrendCell` (uma janela de um SKU ou fornecedor)

### 4.1 Campos

| Campo | Tipo | Descrição | Regra |
| :--- | :--- | :--- | :--- |
| `meses` | `1\|3\|6\|12` | Tamanho da janela; a posição no array é sempre `1, 3, 6, 12` | P-075 |
| `atual` | number | **Total líquido bruto** da Janela Atual na métrica escolhida (pode ser negativo) | P-084.2 |
| `anterior` | number | **Total líquido bruto** da Janela Anterior (pode ser negativo) | P-084.2 |
| `variacaoPct` | number \| `null` | `(atual − anterior) ÷ anterior × 100` após piso zero, 1 casa; `null` em `NOVO`, `SEM_MOVIMENTO` e `SEM_BASE`. Mínimo exato `-100.0`; sem teto | P-077 |
| `status` | enum | `VARIACAO` \| `NOVO` \| `SEM_MOVIMENTO` \| `SEM_BASE` (4.2) | P-078 |
| `baseParcial` | boolean | A comparação usou média diária (alguma janela com cobertura < 100%). Sempre `false` em `SEM_BASE` | P-076.4 |
| `baseBaixa` | boolean | Só em `VARIACAO` com Janela Anterior (total líquido) abaixo de `LOW_BASE_MIN_QUANTITY` (10 un) ou `LOW_BASE_MIN_REVENUE` (R$ 500,00). Informativo; não altera cálculo nem ordenação | P-079.1, P-089.6 |
| `devolucaoLiquida` | boolean | Alguma das janelas teve líquido negativo e o piso zero foi aplicado ("Devoluções superam vendas"). Sempre `false` em `SEM_BASE` | P-077.1 |
| `atualPorDia` / `anteriorPorDia` | number \| `null` | Média diária (total líquido após piso zero ÷ dias cobertos), 4 casas. **Só** quando `baseParcial = true`; senão `null`. Alimenta o tooltip "média por dia" | P-086.2 |
| `contribuicaoPp` / `contribuicaoValor` | number \| `null` | **Só no detalhe do fornecedor** (3.2) | P-090 |

`atual` e `anterior` são sempre os **totais** brutos, mesmo quando a variação foi calculada por média diária: o tooltip mostra os totais, as médias por dia e os dias cobertos (de `meta.janelas`).

### 4.2 Estados da célula e exemplos completos

Ordem de avaliação (P-078): `SEM_BASE` → `VARIACAO` → `NOVO` → `SEM_MOVIMENTO`. Nenhum estado gera erro HTTP. Os exemplos usam a massa sintética (1m, Mês-Base `2026-10`, `quantity`, salvo indicação).

**`VARIACAO`**, caso comum (SKU 1001, CA-02):

```json
{ "meses": 1, "atual": 30.0, "anterior": 20.0, "variacaoPct": 50.0, "status": "VARIACAO",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

**`VARIACAO` com `baseParcial`** (SKU 1001, 12m, CA-03): totais 250 × 98; variação por média diária.

```json
{ "meses": 12, "atual": 250.0, "anterior": 98.0, "variacaoPct": 108.3, "status": "VARIACAO",
  "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.6849, "anteriorPorDia": 0.3289 }
```

**`VARIACAO` com Mês-Base parcial** (`baseMonth=2026-11`, SKU 1001, 1m, CA-04; `meta.mesBaseParcial = true`, `meta.janelas[0].atual.diasCobertos = 8` de `30`):

```json
{ "meses": 1, "atual": 4.0, "anterior": 30.0, "variacaoPct": -48.3, "status": "VARIACAO",
  "baseParcial": true, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": 0.5, "anteriorPorDia": 0.9677 }
```

**`VARIACAO` com `baseBaixa`** (SKU 1007, CA-11): anterior de 1 un (< 10).

```json
{ "meses": 1, "atual": 3.0, "anterior": 1.0, "variacaoPct": 200.0, "status": "VARIACAO",
  "baseParcial": false, "baseBaixa": true, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

Com `metric=revenue` o limiar é R$ 500,00: o SKU 1001 em out/26 (R$ 360,00 vs R$ 200,00) é `+80.0` com `"baseBaixa": true`:

```json
{ "meses": 1, "atual": 360.0, "anterior": 200.0, "variacaoPct": 80.0, "status": "VARIACAO",
  "baseParcial": false, "baseBaixa": true, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

**`VARIACAO` −100,0% com `devolucaoLiquida`** (SKU 1004, CA-10): atual bruto −7 (venda 5 menos devolução 12).

```json
{ "meses": 1, "atual": -7.0, "anterior": 20.0, "variacaoPct": -100.0, "status": "VARIACAO",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": true, "atualPorDia": null, "anteriorPorDia": null }
```

**`VARIACAO` "parou de vender"** (SKU 1003, CA-08): `atual = 0`, `variacaoPct = -100.0`, sem selo.

**`NOVO`** (SKU 1002, CA-07): sem venda líquida na anterior e com venda na atual. `variacaoPct = null`.

```json
{ "meses": 1, "atual": 40.0, "anterior": 0.0, "variacaoPct": null, "status": "NOVO",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

**`NOVO` com `devolucaoLiquida`** (SKU 1005, CA-10): anterior bruto −3 (piso zero).

```json
{ "meses": 1, "atual": 10.0, "anterior": -3.0, "variacaoPct": null, "status": "NOVO",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": true, "atualPorDia": null, "anteriorPorDia": null }
```

**`SEM_MOVIMENTO`** (SKU 1006, CA-09): líquido 0 nas duas janelas; continua listado. `variacaoPct = null`.

```json
{ "meses": 1, "atual": 0.0, "anterior": 0.0, "variacaoPct": null, "status": "SEM_MOVIMENTO",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

**`SEM_BASE`** (`baseMonth=2025-07`, SKU 1001, 6m, CA-06): a Janela Anterior (ago/24–jan/25) tem 25 de 184 dias cobertos (13,6% < 50%). `variacaoPct = null`, todos os selos `false`; `atual` fica exposto para o tooltip e `anterior` é o total da janela parcialmente coberta, **não comparável** (a tela não o apresenta como base de comparação). `meta.janelas[2].semBase = true`.

```json
{ "meses": 6, "atual": 60.0, "anterior": 8.0, "variacaoPct": null, "status": "SEM_BASE",
  "baseParcial": false, "baseBaixa": false, "devolucaoLiquida": false, "atualPorDia": null, "anteriorPorDia": null }
```

Se as quatro janelas forem `SEM_BASE` (ex.: `baseMonth=2025-01`), a resposta é `200` com todas as colunas "—" e `meta.janelas[].semBase = true` nas quatro (P-078.7). A tela explica "histórico anterior insuficiente".

### 4.3 Regras de seleção de campos (resumo para o Tester)

| `status` | `variacaoPct` | `baseParcial` | `baseBaixa` | `devolucaoLiquida` | `atualPorDia`/`anteriorPorDia` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SEM_BASE` | `null` | `false` | `false` | `false` | `null` |
| `VARIACAO` | número | por janela | por limiar (4.1) | se algum líquido negativo | preenchidos se `baseParcial` |
| `NOVO` | `null` | por janela | `false` | se `anterior` ou `atual` brutos < 0 | preenchidos se `baseParcial` |
| `SEM_MOVIMENTO` | `null` | por janela | `false` | se `anterior` ou `atual` brutos < 0 | preenchidos se `baseParcial` |

Premissas de arquitetura que esclarecem lacunas das regras (a validar no checkpoint, ver ADR-003 DC-8): **AR-1** o desempate de ordenação usa os valores após o piso zero; **AR-2** em `SEM_BASE` todos os selos são `false` (não houve comparação); **AR-3** `baseParcial` é por janela e vale para `VARIACAO`, `NOVO` e `SEM_MOVIMENTO` (não só para `VARIACAO`); **AR-9** com `view=new` a ordem é a de P-080.2 (`atual` desc, código asc) e `sortDir` não tem efeito.

---

## 5. Matriz de Erros HTTP Mapeados

### 5.1 Corpo único de erro (`TrendErrorResponse`), definido neste contrato

Vale para **todo** erro das rotas de `/api/v1/sales-trend`, sem stacktrace, SQL, mensagem de driver nem valor recebido (P-082.4):

```json
{
  "error": {
    "code": "TND-001",
    "message": "Parâmetros inválidos: baseMonth, limit.",
    "fields": ["baseMonth", "limit"]
  },
  "meta": { "timestamp": "2026-11-09T15:10:00.000Z", "version": "1.0.0" }
}
```

| Campo | Tipo | Descrição |
| :--- | :--- | :--- |
| `error.code` | string `TND-NNN` | Código interno (`TND-001` a `TND-005`). O frontend decide **sempre por este campo**, nunca pelo texto |
| `error.message` | string | Mensagem fixa em português, sem valor recebido |
| `error.fields` | string[] | Nomes dos parâmetros inválidos (`TND-001`, e `["baseMonth"]` em `TND-002` quando o mês foi informado). Sempre presente; lista vazia nos demais |
| `meta.timestamp` / `meta.version` | string | Momento (ISO-8601 UTC) e versão do contrato |

### 5.2 Códigos

| HTTP | `code` | Quando | `message` (fixa) | `fields` | Regra |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `400` | `TND-001` | `baseMonth` fora de `AAAA-MM` (mês 01 a 12) ou posterior ao mês da `dataReferencia`; `metric` fora de `quantity\|revenue`; `groupBy` fora de `product\|supplier`; `sortWindow` fora de `{1,3,6,12}`; `sortDir` fora de `asc\|desc`; `view` fora de `all\|rising\|falling\|new`; `q` curto demais (< 2 caracteres não numéricos) ou > 60; `minVolume` negativo, não numérico ou não finito; `limit` fora de 1 a 200; `offset` < 0 ou não inteiro; no detalhe: `supplierKey` ausente/vazio/> 200 e `sortBy` fora de `contribution\|variation` | `"Parâmetros inválidos: {campos}."` | nomes dos campos (`baseMonth`, `metric`, `groupBy`, `sortWindow`, `sortDir`, `view`, `q`, `minVolume`, `limit`, `offset`, `supplierKey`, `sortBy`), sem duplicatas, na ordem da query | P-082, P-074.4, P-079.4, P-088.1 |
| `404` | `TND-003` | Detalhe com `supplierKey` que não corresponde a nenhum fornecedor do universo de produtos ativos no Mês-Base informado | `"Fornecedor não encontrado no período analisado."` | `[]` | P-092.1 |
| `422` | `TND-002` | Mês-Base **informado** anterior ao mês da primeira venda, ou mês corrente sem nenhum dia fechado (dia 1) → `fields: ["baseMonth"]`. Base de vendas vazia, ou Mês-Base padrão (não informado) sem dias cobertos → `fields: []` (Q-7) | `"O mês-base escolhido não possui dias com vendas registradas na base."` | `["baseMonth"]` ou `[]` | P-074.5 |
| `429` | `TND-005` | **Só** `POST /reload` antes de 15 min da última carga | `"A base foi recarregada recentemente. Tente novamente mais tarde."` | `[]` | P-083.2 |
| `503` | `TND-004` | Base de vendas indisponível (conexão, driver, configuração) em qualquer rota que precise do snapshot | `"Base de vendas indisponível no momento. Tente novamente em instantes."` | `[]` | P-082 |
| `500` | — | Erro não previsto | Corpo padrão do Starlette (`Internal Server Error`), sem stacktrace | — | `security-anti-patterns` |
| `401` | — | Produção sem credencial (middleware global) | Comportamento existente (`WWW-Authenticate: Basic`) | — | P-033 |

Corpo exato de `TND-004` (Q-16):

```json
{
  "error": { "code": "TND-004", "message": "Base de vendas indisponível no momento. Tente novamente em instantes.", "fields": [] },
  "meta": { "timestamp": "2026-11-09T15:10:00.000Z", "version": "1.0.0" }
}
```

- **`TND-005` nunca ocorre na UI (Q-16):** só `POST /reload` usa `force_reload`; `GET /`, `GET /supplier-products` e `GET /health` jamais devolvem 429, e a tela não tem botão de recarga.
- **Tratamento no módulo:** a validação do FastAPI (tipos, faixas, `Literal`, `AfterValidator` de `q`) é convertida em `400 TND-001` pela classe de rota do próprio módulo; as demais rotas da aplicação (`pricing`, `inventory` e qualquer outro módulo) **não** são afetadas e mantêm seus formatos (ADR-003 DA-09).
- O frontend decide pelo `code`, nunca pelo texto de `message`.
- Exemplo `baseMonth = "2026-13"`: `400`, `fields: ["baseMonth"]`, sem eco do valor. Exemplo `baseMonth = "2024-12"`: `422 TND-002` com `fields: ["baseMonth"]` (a tela oferece "Voltar para {mesBasePadrao}"); base vazia: `422 TND-002` com `fields: []` (a tela oferece "Tentar de novo"). Exemplo `baseMonth = "2026-12"` (futuro): `400 TND-001` com `fields: ["baseMonth"]`.
- `q` e `baseMonth` nunca aparecem na mensagem nem nos logs (LGPD-05, P-085.2).

### 5.3 Conformidade com privacidade (P-085)

| Campo | Natureza | Dado pessoal? |
| :--- | :--- | :--- |
| `codigo`, `descricao`, `fornecedor` | Catálogo | Não |
| `atual`, `anterior`, `variacaoPct`, `contribuicao*`, `*PorDia` | Agregado comercial por SKU/fornecedor e mês | Não |
| `fornecedorChave`, `qtdProdutos`, `semFornecedor` | Derivados do catálogo | Não |
| `meta.*` | Datas de negócio, contagens e configuração | Não |

Continuam **fora** de qualquer resposta: `Cod Cliente`, `Pedido`, nome, documento, endereço, contato, `UF`, custo, estoque e preço. Se algum `Fornecedor` do catálogo for pessoa natural, o `reviewer` reavalia (regras §3).

---

## 6. Respostas às dúvidas do Design Plan (§11, Q-1 a Q-17) e pontos que a UI pode precisar

### 6.1 Q-n do Designer

Legenda: **Aceito** = adotado como recomendado; **Ajustado** = adotado com mudança; **Recusado** = não adotado, com justificativa.

| Q | Resposta | Decisão e onde está no contrato |
| :-: | :--- | :--- |
| Q-1 | **Aceito** | `meta.janelas[].baseParcial` e `semBase` explícitos (2.2). Invariante garantida e testada (T-09): para todo item e toda janela, `cell.baseParcial == meta.janelas[i].baseParcial`, inclusive em `SEM_BASE` (ambos `false`; ali vale `semBase = true`). O cabeçalho da coluna mostra o selo (D-7) |
| Q-2 | **Aceito** | `inicio`/`fim` em `AAAA-MM-DD` (primeiro e último dia da janela); `mesBase*` em `AAAA-MM`; `ultimoDiaCoberto` e `dataReferencia` em `AAAA-MM-DD` (2.1, 2.2) |
| Q-3 | **Aceito em parte** | `atualPorDia`/`anteriorPorDia` por célula, `null` fora da base parcial (4.1). **Recusado** o boolean `porDia` na janela do filho: `contribuicaoValor` é por dia **se e somente se** `baseParcial = true` (já presente na célula e em `meta.janelas[]`); um segundo campo poderia divergir do primeiro. Invariante documentada em 3.2 e testada |
| Q-4 | **Aceito** | `meta.total` na lista, `{ qtdProdutos, janelas[4] }`, soma líquida do universo de produtos ativos, ignorando `q`, `view` e `minVolume`, nas duas visões (2.1, exemplo 3.1.3). Cálculo novo (não está nas regras do Analista): premissa **AR-10**, reutiliza as fórmulas de P-089 sobre um único grupo |
| Q-5 | **Aceito** | Detalhe com `limit` padrão **20** (lista continua 50), `sortBy=contribution` como padrão, `sortWindow`/`sortDir` enviados pela tela (herdados da lista; defaults `3`/`desc`). `meta.fornecedor` traz `atual`, `anterior`, `atualPorDia`, `anteriorPorDia` e `variacaoPct` de cada janela (3.2). Desvio de P-092.5 (que herdava o padrão 50): premissa **AR-11** |
| Q-6 | **Aceito** | Corpo `{ error: { code, message, fields[] }, meta: { timestamp, version } }` para `TND-001` a `TND-005`, definido em 5.1; `fields` lista só nomes de campo, nunca o valor; a tela decide sempre por `code`/`fields` |
| Q-7 | **Aceito** | `TND-002` com `fields:["baseMonth"]` quando o mês foi **informado** e é inválido (antes da base ou mês corrente sem dia fechado); `fields:[]` para base vazia ou mês padrão (5.2) |
| Q-8 | **Aceito** | Grupo reservado vem com `fornecedor: "Sem fornecedor"` e `semFornecedor: true`; `descricao` é **sempre** uma string preenchida (só produtos ativos do catálogo entram; não existe "Sem cadastro"); `fornecedorChave` opaco, enviado como `supplierKey` (`HttpParams` codifica; `encodeURIComponent` se a URL for montada à mão) (3.1.1, 3.1.2) |
| Q-9 | **Aceito** | `meta.parametros` com `limiteBaseBaixaQuantidade/Faturamento`, `coberturaMinimaAnterior`, `buscaMinCaracteres`, `buscaMinCaracteresNumerica`, `buscaMaxCaracteres`, `ttlCacheHoras` em lista e detalhe (2.1) |
| Q-10 | **Aceito** | Só dados estruturados (booleans, números, datas, enums). Textos de selo, tooltip e período montados em `utils/trend-view.ts` / `trend-format.ts` (P-084.5 resolvido: frontend; ADR-003 DA-11) |
| Q-11 | **Aceito** | Nomes e valores exatamente como em 3.1 e 3.2, **sem** `activeOnly`; a tela omite parâmetros iguais ao padrão. Exceção única de padrão: `limit` do detalhe é 20 (Q-5) |
| Q-12 | **Aceito** | `meta` do detalhe repete `mesBase`, `metrica`, `janelas[]`, `parametros` e `dataReferencia`, e acrescenta `fornecedor` (3.2) |
| Q-13 | **Aceito (substituída)** | O universo é "produtos ativos do catálogo atual". Um produto que deixa de ser ativo some da lista, das somas e do detalhe na próxima carga; um fornecedor cujo único produto saiu devolve `404 TND-003` no detalhe. Não há `activeOnly` nem `ativo`. Reforço: a tela envia `baseMonth = meta.mesBase` da lista no detalhe (não omite), para que uma recarga entre as chamadas não troque o Mês-Base padrão; a divergência de `dataReferencia` continua sendo detectada (P-092.7) |
| Q-14 | **Aceito** | `GET /api/v1/sales-trend/health` (3.3): estado do snapshot sem carga e sem banco |
| Q-15 | **Aceito** | A ordenação é uma ordem **total** determinística (desempate final por código ascendente; contribuições `null` ao fim por `atual` desc e código asc), logo estável entre páginas enquanto o snapshot é o mesmo. Se o snapshot for recarregado entre duas páginas, `meta.dataReferencia` muda e a tela recarrega a partir da página 1 |
| Q-16 | **Aceito** | **`TND-005` não ocorre na UI**: só `POST /reload` usa `force_reload`; nenhuma rota chamada pela tela devolve 429 (5.2). A copy do Designer existe só por defesa. Corpo de `TND-004` (503) fixado em 5.2, no formato `{ error: { code, message, fields[] }, meta }`, com `fields: []` |
| Q-17 | **Confirmado, sem tarefa** | Verificado em `main`: `frontend/proxy.conf.json` tem uma única entrada `"/api"` → `http://127.0.0.1:8000` (referenciada em `angular.json`, `serve.options.proxyConfig`), que **já cobre** `/api/v1/sales-trend`. `SalesTrendService` fixa `baseUrl = '/api/v1/sales-trend'` como `InventoryService`. Em produção a API serve o Angular compilado na mesma origem. **Nenhuma edição** em `proxy.conf.json` e nenhuma tarefa F-xx para isso |

Premissas novas de arquitetura geradas por estas respostas: **AR-10** (`meta.total`) e **AR-11** (`limit` padrão 20 no detalhe). Ambas são aditivas e não alteram os números das regras P-072 a P-093.

### 6.2 Pontos adicionais que a UI pode precisar

| # | Necessidade provável | Resposta no contrato |
| :-: | :--- | :--- |
| UI-1 | Rótulos prontos dos selos ("Base parcial", "Base baixa", "Sem base", "Devoluções superam vendas", "Novo") | **Não vêm da API.** São copy fixa por `status`/selo booleano, mantida em um único mapa no frontend (`utils/trend-view.ts`). O texto do tooltip é composto com campos estruturados |
| UI-2 | Texto de explicação da variação ("sem venda líquida na janela anterior", "janela anterior com X de Y dias", "mês-base parcial: X de Y dias") | Montado no frontend com `status`, `baseParcial`, `meta.janelas[].atual/anterior.diasCobertos/diasJanela` e `meta.mesBaseParcial`. "Média por dia" vem pronta em `atualPorDia`/`anteriorPorDia` |
| UI-3 | Total de itens por visão ("Todos / Maiores altas / Maiores quedas / Novos") | `meta.totaisPorVisao` (2.1), com os demais filtros aplicados e relativo à `sortWindow`. `totalItems` é o total da visão ativa |
| UI-4 | Cabeçalho de coluna "ago–out/26 vs mai–jul/26" | `meta.janelas[].atual.inicio/fim` e `anterior.inicio/fim` (formatação em `trend-format.ts`) |
| UI-5 | Seletor de Mês-Base | `meta.mesBaseMinimo`, `mesBaseMaximo`, `mesBasePadrao`, `mesBaseParcial`, `ultimoDiaCoberto`; o frontend enumera os meses de mínimo a máximo e rotula o corrente "parcial até DD/MM" com `ultimoDiaCoberto`. Desabilitar o máximo se `ultimoDiaCoberto` < 1º dia de `mesBaseMaximo` (dia 1 do mês) |
| UI-6 | "Dados até DD/MM/AAAA" | `meta.ultimoDiaCoberto` (e `dataReferencia` para detectar divergência lista × detalhe) |
| UI-7 | Estado "histórico anterior insuficiente" | Todas as `meta.janelas[].semBase = true` (P-078.7) |
| UI-8 | Unidade do volume mínimo e da contribuição | Derivada de `meta.metrica` (`quantity` → "un"; `revenue` → "R$"); contribuição por dia quando `baseParcial` |
| UI-9 | Sentido de ordenação efetivo e visão ativa | `meta.ordenacao` e `meta.visao` (a tela não precisa reimplementar o padrão `falling → asc`) |
| UI-10 | Fornecedor sem nome | `semFornecedor = true` e `fornecedor = "Sem fornecedor"`; em produto, `fornecedor = null` |
| UI-11 | Variação com sinal e direção | A API devolve o número com sinal (`-57.1`, `0.0`); sinal `+`/`−`, seta ▲/▼ e texto de direção são do frontend (`trend-format.ts`); `0.0` não tem sinal |
| UI-12 | Posição na lista | `offset + índice + 1` (a lista tem ordem estável e determinística) |
| UI-13 | Estado da consulta na URL (Design Plan D-12) | Fora do contrato, mas **compatível**: os nomes dos query params da SPA podem ser os mesmos da API (`baseMonth`, `metric`, `groupBy`, `sortWindow`, `sortDir`, `view`, `q`, `minVolume`) mais a página; nada de dado pessoal |
| UI-14 | Contribuição em valor e por dia nos filhos | `contribuicaoValor` na unidade da métrica; por dia se `baseParcial` (Q-3) |
| UI-15 | Linha de referência "Todos os produtos" | `meta.total` (Q-4) |
| UI-16 | Escopo "apenas produtos ativos" na copy | Constante de produto: toda a resposta já é restrita ao catálogo ativo; a tela só precisa dizê-lo (Design Plan D-21). Não há campo a ler |

Se o Designer precisar de um campo novo, a inclusão é **aditiva** e sobe a versão menor do contrato (`1.1.0`) sem quebrar o consumidor.

---

## 7. Diretrizes de Integração no Frontend

- **Serviço:** `frontend/src/app/features/sales-trend/services/sales-trend.service.ts` (`baseUrl = '/api/v1/sales-trend'`), métodos `getTrend(query)` (com *overloads* por `groupBy`: `'product'` → `ProductTrendResponse`, `'supplier'` → `SupplierTrendResponse`, mesma URL), `getSupplierProducts(query)` e `getHealth()` (aviso de cache frio, Q-14). `HttpParams` **omite valores padrão** (`metric=revenue`, `groupBy=product`, `sortWindow=3`, `view=all`, `minVolume=0`, `q` vazio) para manter URLs curtas e idempotentes; `supplierKey` é codificado por `HttpParams`. Sem `console.log`, sem storage. O dev server já faz proxy de `/api` (Q-17).
- **Estado:** `SalesTrendStore` com `signal`s: `idle`, `loading`, `success`, `empty`, `error`; um estado por expansão de fornecedor (carregando, sucesso, vazio, erro). Regras de transição no store (ADR-003 DA-12): trocar `groupBy` preserva Mês-Base, métrica, `sortWindow` e `sortDir` e zera `view`, `minVolume`, `q`; trocar métrica zera `minVolume`; qualquer mudança volta `offset` a 0 e recolhe as expansões; `TND-003` recolhe a linha com aviso; `dataReferencia` divergente recarrega a lista.
- **Erros:** `utils/trend-error.ts` com o type guard `toTrendApiError(err: unknown): TrendApiError | null` (só corpos `{error:{code,message,fields}}` com código `TND-001..005`) e o mapa `TREND_ERROR_MESSAGES: Record<TrendErrorCode, string>` (mensagens de tela definidas no Design Plan §6.4). 500, rede e corpo malformado → falha genérica.
- **Formatação:** `utils/pt-br-format.ts` (própria da feature: `roundHalfUp`, `formatDecimal`, `formatCurrency`, `formatIsoDate`) e `utils/trend-format.ts`: variação com sinal (`+50,0%`, `−100,0%` com U+2212, `0,0%` sem sinal), faixa de meses (`ago–out/26`), valor por métrica (`R$ 1.234,56` / `1.234 un`) e p.p. (`+14,3 p.p.`).
- **Tipagem (TypeScript, sem `any`):**

```typescript
/** Contrato analytics-sales-trend 1.0.0 (ADR-003). */
export type TrendMetric = 'quantity' | 'revenue';
export type TrendGroupBy = 'product' | 'supplier';
export type TrendView = 'all' | 'rising' | 'falling' | 'new';
export type TrendSortDir = 'asc' | 'desc';
export type TrendWindowSize = 1 | 3 | 6 | 12;
export type TrendDetailSortBy = 'contribution' | 'variation';
export type TrendStatus = 'VARIACAO' | 'NOVO' | 'SEM_MOVIMENTO' | 'SEM_BASE';

export const TREND_WINDOWS: readonly TrendWindowSize[] = [1, 3, 6, 12] as const;

export interface TrendWindowSpan {
  inicio: string;        // AAAA-MM-DD
  fim: string;           // AAAA-MM-DD
  diasJanela: number;
  diasCobertos: number;
}

export interface TrendWindowMeta {
  meses: TrendWindowSize;
  atual: TrendWindowSpan;
  anterior: TrendWindowSpan;
  semBase: boolean;
  baseParcial: boolean;
}

/** Constantes efetivas do domínio (Q-9); a copy interpola, não fixa números. */
export interface TrendParameters {
  limiteBaseBaixaQuantidade: number;
  limiteBaseBaixaFaturamento: number;
  coberturaMinimaAnterior: number;
  buscaMinCaracteres: number;
  buscaMinCaracteresNumerica: number;
  buscaMaxCaracteres: number;
  ttlCacheHoras: number;
}

export interface TrendMeta {
  parametros: TrendParameters;
  timestamp: string;
  version: string;
  dataReferencia: string;       // AAAA-MM-DD
  ultimoDiaCoberto: string;     // AAAA-MM-DD
  mesBase: string;              // AAAA-MM
  mesBasePadrao: string;
  mesBaseMinimo: string;
  mesBaseMaximo: string;
  mesBaseParcial: boolean;
  metrica: TrendMetric;
  janelas: TrendWindowMeta[];   // sempre 4, na ordem 1, 3, 6, 12
  page: number;
  limit: number;
  offset: number;
  totalItems: number;
  totalPages: number;
}

export interface TrendViewTotals {
  todos: number;
  maioresAltas: number;
  maioresQuedas: number;
  novos: number;
}

export interface TrendCell {
  meses: TrendWindowSize;
  atual: number;
  anterior: number;
  variacaoPct: number | null;
  status: TrendStatus;
  baseParcial: boolean;
  baseBaixa: boolean;
  devolucaoLiquida: boolean;
  atualPorDia: number | null;
  anteriorPorDia: number | null;
}

export interface TrendDetailCell extends TrendCell {
  contribuicaoPp: number | null;
  contribuicaoValor: number | null;
}

/** Linha "Todos os produtos" (Q-4): soma líquida do universo de produtos ativos. */
export interface TrendTotalRow {
  qtdProdutos: number;
  janelas: TrendCell[];
}

export interface TrendListMeta extends TrendMeta {
  agrupamento: TrendGroupBy;
  visao: TrendView;
  ordenacao: { janela: TrendWindowSize; sentido: TrendSortDir };
  totaisPorVisao: TrendViewTotals;
  total: TrendTotalRow;
}

export interface TrendProductRow {
  codigo: number;
  descricao: string;
  fornecedor: string | null;
  janelas: TrendCell[];
}

export interface TrendSupplierRow {
  fornecedor: string;
  fornecedorChave: string;
  semFornecedor: boolean;
  qtdProdutos: number;
  janelas: TrendCell[];
}

export interface TrendDetailRow extends Omit<TrendProductRow, 'janelas'> {
  janelas: TrendDetailCell[];
}

export interface ProductTrendResponse {
  data: TrendProductRow[];
  meta: TrendListMeta & { agrupamento: 'product' };
}

export interface SupplierTrendResponse {
  data: TrendSupplierRow[];
  meta: TrendListMeta & { agrupamento: 'supplier' };
}

export type SalesTrendResponse = ProductTrendResponse | SupplierTrendResponse;

export interface SupplierDetailMeta extends TrendMeta {
  ordenacao: { por: TrendDetailSortBy; janela: TrendWindowSize; sentido: TrendSortDir };
  fornecedor: TrendSupplierRow;
}

export interface SupplierDetailResponse {
  data: TrendDetailRow[];
  meta: SupplierDetailMeta;
}

/** `data` de `GET /health` e `POST /reload` (Q-14). */
export interface SalesTrendCacheData {
  estadoCache: 'FRIO' | 'CARREGANDO' | 'QUENTE' | 'EXPIRADO';
  carregadoEm: string | null;
  expiraEm: string | null;
  duracaoUltimaCargaMs: number | null;
  contagens: { skus: number; meses: number; linhasAgregado: number; fornecedores: number } | null;
}

/** Consulta da lista; o que não for informado assume o padrão do contrato (3.1). */
export interface SalesTrendQuery {
  baseMonth?: string;
  metric: TrendMetric;
  groupBy: TrendGroupBy;
  sortWindow: TrendWindowSize;
  sortDir?: TrendSortDir;
  view: TrendView;
  q: string;
  minVolume: number;
  limit: number;
  offset: number;
}

/** Códigos de erro do módulo (5.2). */
export const TREND_ERROR_CODES = ['TND-001', 'TND-002', 'TND-003', 'TND-004', 'TND-005'] as const;
export type TrendErrorCode = (typeof TREND_ERROR_CODES)[number];

/** Erro do contrato já validado; `null` nos consumidores significa falha técnica genérica. */
export interface TrendApiError {
  code: TrendErrorCode;
  message: string;
  fields: string[];
}

/** Type guard de discriminação da resposta da lista por `meta.agrupamento`. */
export function isSupplierTrend(response: SalesTrendResponse): response is SupplierTrendResponse {
  return response.meta.agrupamento === 'supplier';
}
```

---

## 8. Padrão de documentação no código (obrigatório para o Desenvolvedor)

| Camada | Padrão |
| :--- | :--- |
| Python: topo de arquivo | Docstring do módulo com objetivo e regras (`P-072 a P-078`, etc.) |
| Python: constantes | Tabela de constantes no topo de `domain/sales_trend.py` (`WINDOW_SIZES_MONTHS`, `TREND_SPAN_MONTHS`, `DEFAULT_METRIC`, `DEFAULT_SORT_WINDOW`, `MIN_PREVIOUS_COVERAGE_RATIO`, `PERCENT_DECIMALS`, `LOW_BASE_MIN_QUANTITY`, `LOW_BASE_MIN_REVENUE`, `DEFAULT_MIN_VOLUME`, `DEFAULT_GROUP_BY`, `NO_SUPPLIER_LABEL`, `NO_SUPPLIER_KEY`, `VALUE_SCALE`), cada uma com comentário de intenção e a regra |
| Python: funções públicas | Docstring Google (Args/Returns/Raises) com `Regra: P-0XX` e o porquê quando não óbvio (ex.: por que o desempate usa o valor pós-piso) |
| Pydantic / OpenAPI | `Field(description=...)` em PT-BR em todos os campos; `Literal[...]` para `status`, `agrupamento`, `visao`, `metrica`; `responses={400, 404, 422, 429, 503}` com `model=TrendErrorResponse`; `json_schema_extra` com os exemplos 3.1.3, 3.1.4 e 3.2; `SALES_TREND_CONTRACT_VERSION = "1.0.0"` |
| TypeScript | Comentário de topo por arquivo; TSDoc nas exportações com a regra (`P-078`); proibido `any` (usar `unknown` + type guard) |
