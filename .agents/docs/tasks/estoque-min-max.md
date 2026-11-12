# Tarefa — Política de Estoque Mínimo/Máximo 30/60 (Previsão de Estoque)

| Campo | Valor |
| :--- | :--- |
| **ID** | P-053 |
| **Branch** | `feature/P-053-estoque-min-max-30-60` |
| **Módulo** | `inventory` — backend FastAPI (`src/modules/inventory/`) e frontend Angular (`frontend/src/app/features/inventory/`) |
| **Regras de negócio** | `.agents/docs/business_rules/estoque-min-max.md` (P-053 a P-056) |
| **Glossário** | `.agents/docs/GLOSSARY.md` |
| **Etapa** | 1 — Especificação concluída; próxima: Etapa 2 (Arquiteto + Designer) |
| **Data** | 2026-11-05 |

---

## 1. Problema

A Fitoherb repõe estoque mantendo entre 30 e 60 dias de venda: quando um produto chega a 30 dias de estoque, compra-se o suficiente para chegar a 60. A tela "Estoque Ideal & Previsão de Compras" não segue essa política. Ela usa estoque de segurança estatístico, ROP, cobertura alvo única e duas travas (variação física percentual e teto orçamentário) que cortam a sugestão de compra. Com isso, o comprador recebe números que não batem com a prática da empresa e precisa recalcular à mão.

---

## 2. User Story

**Título:** Sugestão de compra pela política Mín/Máx de dias de cobertura

**Descrição:** Como **comprador(a) da Fitoherb Nordeste Distribuidora**, quero ver para cada produto o **Estoque Mínimo** (30 dias de venda) e o **Estoque Máximo** (60 dias de venda), calculados com a venda e o estoque atuais, e a **quantidade a comprar para voltar ao máximo**, para repor no ritmo real da distribuidora sem cortes artificiais de volume ou de orçamento.

**Design:** a definir pelo Designer na Etapa 2 (`.agents/docs/design/plans/estoque-min-max.md`).

### 2.1 Descrição funcional

1. **Parâmetros da tela (modal "Parâmetros"):**
   - Janela de Vendas Recentes: 15 a 180 dias, padrão 60 (mantido).
   - Lead Time de Ressuprimento: padrão 15 dias; serve só para sinalizar Ruptura Iminente (mantido, papel reduzido).
   - **Dias Mínimo** (novo): padrão 30.
   - **Dias Máximo** (novo): padrão 60; precisa ser maior que Dias Mínimo.
   - **Saem:** Autonomia Alvo de Estoque, Nível de Serviço (z-score), Teto Orçamentário Máximo e Margem Máxima de Variação de Compra (trava física).
2. **Cálculo por produto:** VMD, Dias de Cobertura, Estoque Mínimo, Estoque Máximo, Quantidade Sugerida, Investimento e Status, conforme P-053 a P-055.
3. **Tabela de produtos:** as colunas **Est. Mínimo** e **Est. Máximo** substituem **ROP** e **Est. Ideal**. Some o tooltip de "ajustado ao espaço físico / limitado pela capacidade física".
4. **Indicadores (KPIs):**
   - "Ruptura Iminente": mantido.
   - "Reposição Necessária" passa a "**Abaixo do Mínimo**" (texto de apoio deixa de citar ROP).
   - "Estoque Saudável": mantido (texto de apoio passa a remeter à faixa entre mínimo e máximo).
   - "Excesso / Overstock" passa a "**Acima do Máximo**", com o Capital Imobilizado calculado sobre o excedente ao máximo.
   - "Investimento Sugerido": mantido, sem o selo "SKUs c/ trava física".
5. **Filtros de status (pílulas):** os rótulos acompanham os novos nomes de status.
6. **Exportação CSV:** colunas conforme P-056.5, com os mesmos números da tela.

---

## 3. Critérios de aceite (Dado / Quando / Então)

Os critérios detalhados de cálculo estão em `business_rules/estoque-min-max.md` (CA-P053-xx a CA-P056-xx). Os critérios abaixo validam a história de ponta a ponta.

- **CA-01 — Cálculo padrão 30/60**
  - **Dado** um produto que vendeu 120 un nos últimos 60 dias (VMD 2,0), com estoque 50 un e custo R$ 10,00
  - **Quando** o comprador abre a Previsão de Estoque com os parâmetros padrão
  - **Então** a linha do produto mostra Est. Mínimo 60, Est. Máximo 120, Sug. Compra 70, Investimento R$ 700,00 e status "Abaixo do Mínimo".

- **CA-02 — Ruptura iminente**
  - **Dado** um produto com VMD 2,0, estoque 10 un e lead time 15 dias
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é "Ruptura Iminente", a autonomia é 5,0d (destacada como risco) e a Sug. Compra é 110 un.

- **CA-03 — Faixa saudável não gera compra**
  - **Dado** um produto com VMD 2,0 e estoque entre 61 e 120 un
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é "Estoque Saudável" e não há sugestão de compra.

- **CA-04 — Acima do máximo**
  - **Dado** um produto com VMD 2,0, estoque 150 un e custo R$ 15,00
  - **Quando** o cálculo é executado com 30/60
  - **Então** o status é "Acima do Máximo", não há sugestão de compra e o produto soma R$ 450,00 ao KPI de Capital Imobilizado.

- **CA-05 — Ajuste de Dias Mínimo e Dias Máximo**
  - **Dado** que o comprador abre o modal de parâmetros
  - **Quando** define Dias Mínimo 20 e Dias Máximo 45 e aplica
  - **Então** o recálculo mostra, para um produto com VMD 2,0, Est. Mínimo 40 e Est. Máximo 90, e o CSV baixado em seguida traz os mesmos valores.

- **CA-06 — Validação Dias Máximo > Dias Mínimo**
  - **Dado** que o comprador está no modal de parâmetros
  - **Quando** informa Dias Máximo menor ou igual a Dias Mínimo
  - **Então** não consegue aplicar o recálculo, vê uma mensagem em português explicando que o máximo deve ser maior que o mínimo, e a API, se chamada diretamente com esses valores, rejeita a requisição com erro de validação.

- **CA-07 — Fim das travas**
  - **Dado** um conjunto de produtos que antes tinha sugestões cortadas pela trava física ou pelo teto orçamentário
  - **Quando** o cálculo é executado
  - **Então** nenhuma quantidade é limitada, o Investimento Sugerido é a soma integral dos itens e não aparecem indicadores de "trava física" ou "limitado por espaço".

- **CA-08 — Parâmetros antigos removidos**
  - **Dado** que o comprador abre o modal de parâmetros
  - **Quando** o modal é exibido
  - **Então** só aparecem Janela de Vendas, Lead Time, Dias Mínimo e Dias Máximo.

- **CA-09 — Produto sem venda**
  - **Dado** um produto sem venda na janela
  - **Quando** o cálculo é executado
  - **Então** Est. Mínimo e Est. Máximo são 0, não há compra, e o status é "Acima do Máximo" se houver estoque ou "Estoque Saudável" se o estoque for 0.

- **CA-10 — Filtro por fornecedor e Curva ABC preservados**
  - **Dado** que o comprador seleciona um fornecedor específico
  - **Quando** o cálculo é executado com esse fornecedor selecionado
  - **Então** só aparecem produtos desse fornecedor, a Curva ABC de cada produto é a mesma da visão "Todos os Fornecedores" e os KPIs refletem apenas os produtos exibidos.

- **CA-11 — CSV alinhado à nova política**
  - **Dado** um cálculo concluído
  - **Quando** o comprador baixa o CSV
  - **Então** o arquivo traz as colunas Estoque Mínimo (un) e Estoque Máximo (un), não traz Estoque de Segurança, ROP, Estoque Ideal, Demanda Teórica Plena, Limitado por Espaço Físico nem Teto Físico de Compra, e abre corretamente no Excel em português (separador `;`, decimal `,`).

- **CA-12 — Resultado antigo salvo no navegador**
  - **Dado** que o navegador do comprador guarda um resultado calculado pela regra anterior (com ROP e Estoque Ideal)
  - **Quando** ele abre a Previsão de Estoque após a atualização
  - **Então** esse resultado antigo não é exibido e um novo cálculo pela política Mín/Máx é feito.

---

## 4. Fora de escopo

- Arredondamento para **múltiplo de embalagem**, caixa master ou lote mínimo de compra do fornecedor.
- **Estoque em trânsito** e **pedidos de compra em aberto** (a compra considera só o estoque físico atual).
- **Sazonalidade**, tendência ou previsão de demanda por modelo estatístico/ML (a política usa só a VMD atual).
- **Status separado para SKU inativo ou descontinuado** (SKU sem venda com estoque continua "Acima do Máximo").
- Correção da VMD de produtos **recém-lançados** ou que ficaram **sem estoque durante a janela** (demanda subestimada).
- Dias Mínimo/Máximo **por produto, por fornecedor ou por Curva ABC** (os parâmetros valem para todo o cálculo).
- **Lead time por fornecedor**.
- Persistência de parâmetros no servidor, histórico de simulações ou envio automático de pedido ao ERP.
- Reintrodução de qualquer limite de capacidade física ou de orçamento (revogados por P-056).
- Alteração de schema ou da query de agregação de vendas (bypass do DBA registrado no `STATE.md`).

---

## 5. Pontos de atenção para a Etapa 2

1. **Faixas dos novos parâmetros (A1):** o discovery definiu apenas padrão 30/60 e a regra máx. > mín. A faixa de cada controle precisa ser definida no design/contrato. Proposta não vinculante: mínimo 5–120 e máximo 10–180, passo 5.
2. **Lead time > Dias Máximo (A2):** pode gerar "Ruptura Iminente" com compra 0 em item acima do máximo. Avaliar validar `lead time < Dias Máximo`.
3. **Precisão da VMD (A3):** a VMD é arredondada a 4 casas na origem. Para cumprir P-053.6 (ex.: 1 un em 60 dias → máximo 1, não 2), mínimo e máximo devem sair da quantidade vendida e da janela, sem arredondamento intermediário.
4. **Faixas divergentes já existentes (A4, A5):** janela de vendas (regra 15–180, API até 365) e lead time (API 1–90, configuração 1–60, tela 5–60).
5. **Parâmetros revogados enviados por cliente antigo (P-056.4):** decidir entre ignorar e rejeitar. Em qualquer caso eles não podem alterar o resultado.
6. **Contrato de API:** substituir `estoqueSeguranca`, `rop`, `estoqueIdeal`, `estoqueIdealTeorico`, `qtdSugeridaTeorica`, `limitadoPorEspaco`, `tetoCompraFisica` e o KPI `skusLimitadosPorEspaco` por Estoque Mínimo e Estoque Máximo. Decidir também se `desvioPadraoDemanda` permanece. Identificadores sugeridos estão no `GLOSSARY.md`.
7. **Resultado salvo no navegador (CA-12):** o cache local da tela guarda a estrutura antiga, então precisa ser invalidado.
8. **Testes existentes:** os testes de P-044.4 (trava física, piso operacional) e de P-046.3 (teto orçamentário) em `tests/test_inventory_engine.py` passam a contrariar as regras e precisam ser substituídos pelos cenários de P-053 a P-056.

---

## 6. Definition of Done (funcional)

- [x] Todos os critérios CA-01 a CA-12 deste documento atendidos.
- [x] Todos os critérios CA-P053-xx a CA-P056-xx de `business_rules/estoque-min-max.md` cobertos por testes automatizados que referenciam o ID da regra.
- [x] Nenhuma referência funcional a ROP, Estoque de Segurança, Estoque Ideal, Nível de Serviço, Autonomia Alvo, Teto Orçamentário ou Trava Física na tela, nos KPIs, no CSV e na configuração de parâmetros.
- [x] Terminologia de tela, contrato e CSV aderente ao `GLOSSARY.md`.
- [x] Pontos de atenção da seção 5 resolvidos e registrados (ADR ou contrato de API) na Etapa 2.

---

## 7. Checklist técnico (Arquiteto — Etapa 2)

**Referências obrigatórias:** `adr/ADR-001-politica-estoque-min-max.md` (decisões DA-01 a DA-11) e `api_contracts/inventory.md` (contrato 2.0.0). Para a página, também o Design Plan do Designer em `design/plans/estoque-min-max.md`.

### 7.0 Orçamento de Clean Code (vale para todas as tarefas)

| Critério | Limite | Como cumprir |
| :--- | :--- | :--- |
| Tamanho de função | ≤ 40 linhas; orquestradores ≤ 25 | Funções da tabela DA-10 do ADR |
| Parâmetros | ≤ 3, ou um objeto | `ReplenishmentPolicy`, `StockPosition`, `SalesLookup`, `ProductEvaluation` (Python) e `InventoryParams`/`InventoryPolicy` (TS) |
| Aninhamento | ≤ 2 níveis | *Early return* em gatilho, status, cálculo de níveis e leitura de cache |
| Números mágicos | 0 | Constantes nomeadas no topo do módulo (lista em cada tarefa) |
| Booleanos | Prefixo `is_`/`has_`/`should_` (Py) e `is`/`has`/`can` (TS) | `is_stockout_imminent`, `is_purchase_triggered`, `isPolicyValid` |
| Tipos | Sem `any` no TS; `Literal`/`Enum` no Python | `InventoryStatus` (`str`, `Enum`) e `Literal` nos schemas |
| Comentários | Topo de arquivo + o **porquê** das regras | Padrão da seção 9 do contrato |

### 7.1 Backend — Domínio (`src/modules/inventory/domain/`)

> Trilha **[PARALLEL]** com a trilha de frontend (7.4) depois da aprovação do contrato. Dentro da trilha: B-01 → B-02 → (B-04 ∥ B-05 ∥ B-06) → B-07 → B-08 → B-09 → B-10 → B-11. A tarefa B-03 é independente.

- [x] **B-01 — Objeto de política e invariantes.** Criar `domain/replenishment_policy.py` com docstring de topo (P-053, P-055.3). Conteúdo:
  - Constantes `DEFAULT_MIN_COVERAGE_DAYS = 30`, `DEFAULT_MAX_COVERAGE_DAYS = 60`, `DEFAULT_LEAD_TIME_DAYS = 15` e `ERROR_CODE_MAX_NOT_GREATER_THAN_MIN = "INV-001"`, `ERROR_CODE_LEAD_TIME_NOT_BELOW_MAX = "INV-002"`.
  - `PolicyViolation` (`@dataclass(frozen=True)`: `code`, `message`, `context: Mapping[str, int]`).
  - `check_max_coverage_greater_than_min(min_days, max_days) -> Optional[PolicyViolation]` e `check_lead_time_below_max_coverage(lead_time_days, max_days) -> Optional[PolicyViolation]`: funções puras, sem exceção, com o texto exato das mensagens da seção 1.2 do contrato.
  - `InvalidReplenishmentPolicyError(ValueError)` com atributo `code`.
  - `ReplenishmentPolicy` (`@dataclass(frozen=True)`: `min_coverage_days`, `max_coverage_days`, `lead_time_days`). O `__post_init__` chama as duas checagens e lança `InvalidReplenishmentPolicyError` na primeira violação.
  - **Regras:** P-053.2, P-053.3, A2. **Decisão:** DA-01, DA-05.
- [x] **B-02 — Mínimo/Máximo com teto sem resíduo.** Em `replenishment_policy.py`:
  - `UNIT_CEIL_GUARD_DECIMALS = 6`, com comentário da premissa "Qtd Venda ≤ 3 casas" (ADR, DA-02).
  - `ceil_units(value: float) -> int` = `math.ceil(round(value, UNIT_CEIL_GUARD_DECIMALS))`.
  - `StockLevels` (`frozen`: `minimum: int`, `maximum: int`).
  - `calculate_stock_levels(vmd: float, policy: ReplenishmentPolicy) -> StockLevels`, com *early return* `vmd <= 0 → StockLevels(0, 0)`. Lead time **não** entra.
  - **Regras:** P-053.4 a P-053.8, A3.
- [x] **B-03 — VMD em precisão integral (dois caminhos).** **[PARALLEL]**
  - Remover `.round(4)` **apenas** da coluna `vmd` em `calculate_sales_velocity` (`domain/inventory_engine.py`) e em `fetch_sales_velocity_from_database` (`src/core/database.py`). Neste último, mexer só no pós-processamento Python: **a query SQL não muda** (bypass do DBA).
  - `std_demand`, `total_sold_qty` e `total_revenue` ficam como estão. Atualizar as docstrings ("VMD em precisão integral; arredondar só na exibição").
  - **Regras:** P-041 (sem mudança de fórmula), P-053.6, A3. **Decisão:** DA-02, DA-04.
- [x] **B-04 — Preparação do catálogo (extraída da God Function).** Em `inventory_engine.py`:
  - `normalize_product_catalog(products_df) -> pd.DataFrame` produz colunas canônicas `codigo`, `descricao`, `ean`, `fornecedor`, `tipo`, `estoque`, `custo_unitario`, `preco_venda`, com estoque negativo virando 0. É **idempotente**: a lista de aliases começa pelo nome canônico.
  - Dividir em helpers de até 40 linhas: `_resolve_column(df, aliases) -> Optional[str]`, `_fill_text_column(df, column, default)` e `_apply_unit_cost_fallback(df)`, com `COST_FALLBACK_PRICE_RATIO = 0.60` e `MONEY_DECIMALS = 2`. Os aliases ficam em constantes (`PRODUCT_COLUMN_ALIASES`).
  - `filter_products_by_supplier(catalog_df, supplier_filter)` com `ALL_SUPPLIERS_TOKENS = frozenset({"TODOS", "ALL", ""})` e *early return* sem filtro.
  - `prepare_product_catalog(products_df, supplier_filter)` = normalizar + filtrar.
  - **Regras:** P-047.1, P-053.9, P-054.5.
- [x] **B-05 — Curva ABC e consulta de vendas.**
  - `classify_abc_curve(revenue_by_sku: Mapping[int, float]) -> Dict[int, str]`, com `ABC_CLASS_A_MAX_PCT = 80.0`, `ABC_CLASS_B_MAX_PCT = 95.0` e `DEFAULT_ABC_CLASS = "C"`. A lógica atual se mantém.
  - `SalesLookup` (`frozen`: `vmd_by_sku`, `abc_by_sku`) com os métodos `vmd_for(sku) -> float` (padrão 0.0) e `abc_class_for(sku) -> str` (padrão `"C"`), que evitam acoplamento a dicionários (Lei de Demeter).
  - `build_sales_lookup(velocity_df) -> SalesLookup` com *early return* quando o DataFrame está vazio.
  - **Regra:** Curva ABC global (mantida).
- [x] **B-06 — Status, rótulos e cobertura.**
  - `InventoryStatus(str, Enum)` com os 4 códigos e `STATUS_LABELS: Mapping[InventoryStatus, str]` = "Ruptura Iminente", "Abaixo do Mínimo", "Estoque Saudável", "Acima do Máximo".
  - `calculate_coverage_days(current_stock, vmd) -> float`, com `NO_SALES_COVERAGE_DAYS = 999.0` e `COVERAGE_DAYS_DECIMALS = 1`.
  - `StockPosition` (`frozen`: `current_stock`, `vmd`, `coverage_days`, `levels: StockLevels`) e `build_stock_position(current_stock, vmd, policy) -> StockPosition`.
  - `is_stockout_imminent(position, lead_time_days) -> bool` = `vmd > 0` e `coverage_days < lead_time_days`. A comparação usa a cobertura **já arredondada a 1 casa**, como exibida (CA-P055-03).
  - **Regras:** P-055.1, P-055.2 (linha 1), P-055.3.
- [x] **B-07 — Gatilho e quantidade de compra (sem travas).**
  - `is_purchase_triggered(position, lead_time_days) -> bool` = `vmd > 0` e (`estoque ≤ mínimo` ou ruptura iminente).
  - `calculate_suggested_purchase(position, lead_time_days) -> int`: *early return* 0 sem gatilho; senão `max(0, ceil_units(levels.maximum − current_stock))`.
  - **Regras:** P-054.1 a P-054.4, P-056.1.
- [x] **B-08 — Classificação de status e capital imobilizado.**
  - `classify_stock_status(position, suggested_qty, lead_time_days) -> InventoryStatus`: sequência de *early returns* na ordem de P-055.2, incluindo o caso de borda mínimo = máximo, que resulta em `HEALTHY`.
  - `calculate_overstock_capital(position, unit_cost, status) -> float`: `(estoque − máximo) × custo` somente para `OVERSTOCK`, senão 0.0.
  - **Regras:** P-055.2, P-055.4.
- [x] **B-09 — Avaliação por SKU tipada.**
  - `ProductEvaluation` (`frozen`) com os campos do item do contrato (seção 5.2), mais `overstock_capital: float` e `vmd` em precisão integral (usada na ordenação).
  - `to_response_item(self) -> Dict[str, Any]`: devolve camelCase **sem** `overstock_capital`, com `VMD_DISPLAY_DECIMALS = 2`, `STOCK_DISPLAY_DECIMALS = 1` e `MONEY_DECIMALS = 2`.
  - `evaluate_product(product_row, sales_lookup, policy) -> ProductEvaluation` (≤ 40 linhas), com `investimento = round(qtd × custo, MONEY_DECIMALS)`.
  - Preferir `catalog_df.itertuples()` a `iterrows()`, pelo desempenho e porque as colunas canônicas viram atributos.
  - **Regras:** P-053, P-054.5, P-055.
- [x] **B-10 — Ordenação e KPIs.**
  - `product_sort_key(evaluation)` com `STATUS_SORT_ORDER` (Ruptura 0, Abaixo 1, Saudável 2, Acima 3) e `ABC_SORT_ORDER`, seguidos de `-vmd`.
  - `build_kpis(evaluations) -> Dict[str, Any]` usando `collections.Counter` por status, a soma de investimento e capital arredondada a 2 casas e a Curva A com `PERCENT_DECIMALS = 1`. **Sem** `skusLimitadosPorEspaco`.
  - **Regras:** P-055.5, P-055.6, P-054.6, P-055.4.
- [x] **B-11 — Orquestrador e limpeza.**
  - Reescrever `calculate_inventory_replenishment(catalog_df, velocity_df, policy) -> Dict[str, Any]` com ≤ 25 linhas: `build_sales_lookup` → `evaluate_product` para cada linha → `sort` → `{"kpis": build_kpis(...), "produtos": [e.to_response_item() ...]}`.
  - **Remover:** `get_z_score`, estoque de segurança, ROP, estoque ideal (teórico e operacional), trava P-044.4 e orçamento P-046.3.
  - Atualizar `domain/__init__.py`: exportar `ReplenishmentPolicy`, `InvalidReplenishmentPolicyError`, `prepare_product_catalog`, `calculate_stock_levels` e `ceil_units`; remover `get_z_score`. Atualizar a docstring do módulo.
  - **Regras:** P-056.1 a P-056.3. **Decisão:** DA-03, DA-10.

### 7.2 Backend — API e serviço (`src/modules/inventory/api/`, `service/`)

> Depende de B-01 (checagens e política). B-12 e B-13 podem rodar em paralelo entre si.

- [x] **B-12 — Request e validação.** Em `schemas.py`:
  - `InventoryPredictRequest` com `model_config = ConfigDict(extra="ignore")` e campos **nesta ordem**: `historyWindowDays` (15–365, padrão 60), `minCoverageDays` (1–180, padrão 30), `maxCoverageDays` (2–365, padrão 60), `leadTimeDays` (1–90, padrão 15), `fornecedor` (`Optional[str]`, `max_length=120`).
  - Escrever um comentário sobre a dependência de ordem.
  - Faixas como constantes nomeadas: `API_MIN_COVERAGE_DAYS_LOWER/UPPER`, `API_MAX_COVERAGE_DAYS_LOWER/UPPER` etc.
  - `@field_validator("maxCoverageDays")` e `@field_validator("leadTimeDays")` com `ValidationInfo`: *early return* se o campo de referência não estiver em `info.data`; senão delegar à checagem do domínio e lançar `PydanticCustomError(violation.code, violation.message, dict(violation.context))`.
  - Remover os 4 campos revogados.
  - **Regras:** P-053.2, P-053.3, P-056.4, A1, A2. **Decisão:** DA-05, DA-06.
- [x] **B-13 — Schemas de resposta.**
  - `InventoryPolicyEcho` (4 inteiros).
  - `InventoryProductItem`: remover os 8 campos listados no contrato, adicionar `estoqueMinimo: int` e `estoqueMaximo: int`, e tipar `status: Literal[...]` e `curvaAbc: Literal["A", "B", "C"]`.
  - `InventoryKPIs`: remover `skusLimitadosPorEspaco`.
  - `InventoryPredictData.politica`.
  - `RangeParameterConfig`, `InventoryConfigData` e `InventoryConfigResponse.data: InventoryConfigData` (sai `Dict[str, Any]`).
  - `INVENTORY_CONTRACT_VERSION = "2.0.0"` como padrão de `ResponseMeta.version`.
  - `Field(description=...)` em PT-BR em todos os campos.
  - **Regras:** P-053, P-055, P-056.3. **Decisão:** DA-04, DA-07, DA-08.
- [x] **B-14 — Serviço.** Em `inventory_service.py`:
  - `to_replenishment_policy(request) -> ReplenishmentPolicy` (mapper API → domínio).
  - `build_policy_echo(request) -> Dict[str, int]`.
  - `get_inventory_parameter_config() -> InventoryConfigData`: faixas da tela em constantes `UI_*`, conforme a seção 3.1 do contrato.
  - Reescrever `execute_inventory_prediction`: `prepare_product_catalog` → `get_inventory_velocity` → `calculate_inventory_replenishment` → `politica`, com `time.perf_counter()`.
  - Atualizar as docstrings (sem ROP/estoque ideal).
  - **Regras:** P-047.1, P-053 a P-055. **Decisão:** DA-08, DA-10.
- [x] **B-15 — CSV.**
  - `INVENTORY_CSV_COLUMNS` (dicionário ordenado, campo → cabeçalho) exatamente na ordem da seção 6.2 do contrato, com "Estoque Mínimo (un)" e "Estoque Máximo (un)".
  - Criar o DataFrame com `pd.DataFrame(produtos, columns=list(INVENTORY_CSV_COLUMNS))`, para manter o cabeçalho quando a lista vier vazia.
  - Remover a variável morta `writer`.
  - `build_csv_filename(fornecedor, generated_at) -> str` com slug sanitizado `[a-z0-9_]`, via regex em constante.
  - **Regras:** P-056.5, P-056.6. **Decisão:** DA-11.
- [x] **B-16 — Router.**
  - `/config` delega a `get_inventory_parameter_config()`. `/predict` e `/export-csv` só recebem, delegam e devolvem; o nome do arquivo vem de `build_csv_filename`.
  - Respostas 500 com mensagem genérica em PT-BR (textos da seção 5.3/6.3 do contrato, em constantes), **sem `str(e)`**, com `logger.error(..., exc_info=True)`.
  - `summary`/`description` e `responses={422, 500}` nos decorators. Docstrings sem ES/ROP.
  - **Decisão:** DA-11. **Regra de segurança:** sem vazamento de detalhes internos.

### 7.3 Backend — Testes (`tests/`)

> Na Etapa 3 o **Tester escreve estes testes primeiro (TDD, fase vermelha)**. Depois o Desenvolvedor implementa B-01 a B-16 até ficarem verdes. Cada teste referencia o ID da regra no nome ou no `ids=` do `parametrize`.

- [x] **T-01 — `tests/test_replenishment_policy.py` (novo).**
  - `ReplenishmentPolicy` válida (30/60/15); `INV-001` para 60/60 e 50/45; `INV-002` para lead 45 com máximo 40 (via `pytest.raises(InvalidReplenishmentPolicyError)` checando `.code`).
  - `calculate_stock_levels` parametrizado com E1–E6 (`ids="P-053-E1"...`), incluindo E5 (1 un/60 d → 1/1).
  - `ceil_units` com casos de resíduo: `31/15*15 → 31` e `(1/60)*60 → 1`. Fração real preservada: `37.5 → 38` e `2.000003 → 3` (3 × 10⁻⁶ fica acima da guarda de 6 casas).
  - **Regras:** P-053.3 a P-053.8, A2, A3.
- [x] **T-02 — `tests/test_inventory_engine.py` (reescrita).**
  - **Remover:** `test_get_z_score`, `test_budget_limit_prioritization`, `test_max_purchase_variation_limit_caps_unrealistic_orders` e `test_zero_stock_safeguard_operational_floor`.
  - **Manter:** `test_calculate_sales_velocity`. **Adicionar:** um teste de precisão (1 un em 60 dias → `vmd == pytest.approx(1/60, abs=1e-12)`, sem arredondamento).
  - **Cobrir:** C1–C8 (gatilho e quantidade); S1–S9 (status e capital); CA-P053-07 (volatilidade não muda mínimo/máximo); CA-P054-05 (estoque 0, VMD 5 → 300); CA-P054-06 (sem teto em R$); CA-P055-08 (mínimo = máximo = 1 → `HEALTHY`); CA-P054-08 e CA-P055-09 (invariantes de KPI); CA-10 (filtro de fornecedor com Curva ABC idêntica à visão sem filtro).
  - Verificar a ausência das chaves revogadas em itens e KPIs.
  - **Regras:** P-053 a P-056, P-047.1.
- [x] **T-03 — `tests/test_inventory_api.py` (ajuste).**
  - `/config`: chaves novas com os valores da seção 3.1 e as revogadas ausentes.
  - `/predict`: item com `estoqueMinimo`/`estoqueMaximo` e sem os 8 campos removidos; `politica` ecoada com os padrões quando o body é `{}`.
  - 422 `INV-001` (60/60 e 50/45) e `INV-002` (20/40/45), conferindo `type` e `loc`; 422 de faixa (`minCoverageDays: 0`, `maxCoverageDays: 366`) e `int_from_float` (30.5).
  - Parâmetros revogados ignorados: o resultado é idêntico ao do body sem eles (CA-P056-02).
  - CSV: cabeçalho exato e ordenado, ausência das 6 colunas removidas e valores iguais aos de `/predict` para os mesmos parâmetros (CA-P056-04, P-056.6).
  - 500 sem vazamento de mensagem interna (monkeypatch que lança exceção).
  - **Remover** `test_inventory_predict_with_variation_limit`.
- [x] **T-04 — Precisão no caminho SQL.**
  - Teste de `fetch_sales_velocity_from_database` com `monkeypatch` de `pyodbc.connect` e `get_db_connection_string` (cursor falso devolvendo `(sku=1, sum_qty=1, total_revenue=10.0, sum_sq=1.0, days_with_sales=1)` para 60 dias).
  - Afirmar que `vmd` não é arredondada e que o máximo resultante é 1.
  - **Regras:** P-053.6, A3.

### 7.4 Frontend (`frontend/src/app/features/inventory/`)

> Trilha **[PARALLEL]** com o backend, porque o contrato 2.0.0 é a interface. Ordem: F-01 → (F-02 ∥ F-03) → F-04 → F-05 → F-06. F-06 depende do Design Plan aprovado; F-07 acompanha F-02.

- [x] **F-01 — Model.** Em `models/inventory.model.ts`, aplicar os tipos da seção 8 do contrato:
  - Remover `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct`, `skusLimitadosPorEspaco` e os 8 campos de item.
  - Adicionar `InventoryPolicy`, `InventoryPredictData`, `RangeParameterConfig`, `CurvaAbc` e `ApiValidationErrorItem`.
  - Comentário de topo + TSDoc. **Regras:** P-053, P-056.3.
- [x] **F-02 — Constantes e validação pura.**
  - Criar `inventory.constants.ts` com `DEFAULT_HISTORY_WINDOW_DAYS = 60`, `DEFAULT_LEAD_TIME_DAYS = 15`, `DEFAULT_MIN_COVERAGE_DAYS = 30`, `DEFAULT_MAX_COVERAGE_DAYS = 60`, as faixas da tela `MIN_COVERAGE_DAYS_RANGE = { min: 5, max: 120, step: 5 }` e `MAX_COVERAGE_DAYS_RANGE = { min: 10, max: 180, step: 5 }` (espelho de `/config`, com comentário de referência ao contrato), `INVENTORY_CACHE_KEY = 'fitoherb_inventory_cache_v3'` e `LEGACY_INVENTORY_CACHE_KEYS = ['fitoherb_inventory_cache_v2']`.
  - Criar `utils/inventory-policy.validation.ts` com `validateInventoryPolicy(params: Pick<InventoryParams, 'minCoverageDays' | 'maxCoverageDays' | 'leadTimeDays'>): InventoryPolicyIssue | null`, que retorna `{ code: 'INV-001' | 'INV-002', field, message }` com mensagens em PT-BR do Design Plan. A função **não corrige valores** (P-053.3).
  - Criar `isInventoryCachePayload(value: unknown): value is InventoryCachePayload`, um *type guard* que exige `politica` e `estoqueMinimo` no primeiro item.
  - **Regras:** P-053.3, A1, A2, CA-12.
- [x] **F-03 — Service.** Em `services/inventory.service.ts`:
  - Mesmas rotas, com tipos novos.
  - Adicionar `extractInventoryErrorMessage(error: HttpErrorResponse): string`, que trata 3 casos: `detail` como array, usando o `msg` do primeiro item cujo `type` começa com `INV-`, senão mensagem genérica de parâmetros inválidos; `detail` como string; ou `Blob`/desconhecido, com a mensagem genérica.
  - Comentário de topo + TSDoc. O componente não interpreta erro (frontend "burro").
- [x] **F-04 — Estado da página.** Em `inventory-page.component.ts`:
  - Remover os sinais `targetCoverageDays`, `serviceLevel`, `budgetLimit`, `maxPurchaseVariationPct` e `enablePhysicalLimit`. Adicionar `minCoverageDays` e `maxCoverageDays` (padrões das constantes).
  - **Separar rascunho e política aplicada:** `appliedPolicy = signal<InventoryPolicy | null>(null)` passa a ser preenchido por `data.politica`. "Cancelar" restaura o rascunho a partir da política aplicada.
  - `policyIssue = computed(() => validateInventoryPolicy(...))` e `canApplySettings = computed(() => !policyIssue())`. "Aplicar e Recalcular" retorna cedo se `!canApplySettings()`.
  - `buildPredictParams()`, um único montador (DRY). O CSV usa `appliedPolicy()` + fornecedor selecionado (P-056.6). Erros via `extractInventoryErrorMessage`.
  - Trocar o `any` do comparador de ordenação por uma função tipada.
  - **Regras:** P-053.2, P-053.3, P-056.6, CA-05, CA-06.
- [x] **F-05 — Cache local.**
  - Usar a chave `INVENTORY_CACHE_KEY` (v3) e remover as chaves `LEGACY_INVENTORY_CACHE_KEYS` no `ngOnInit`.
  - Payload `{ kpis, produtos, politica, savedAt }`.
  - `loadCachedPrediction(): boolean`: restaura rascunho e `appliedPolicy` a partir de `politica`. Payload inválido pelo *type guard* → remover a chave e devolver `false`.
  - `ngOnInit`: `if (!this.loadCachedPrediction()) this.calculateInventory();`, o que elimina a requisição duplicada atual.
  - Remover `maxPurchaseVariationPct`/`enablePhysicalLimit` do payload.
  - **Regras:** CA-12. **Decisão:** DA-09.
- [x] **F-06 — Template e estilos (segue o Design Plan).** Em `inventory-page.component.html`/`.scss`:
  - Colunas ROP/Est. Ideal → Est. Mínimo/Est. Máximo, com `toggleSort('estoqueMinimo' | 'estoqueMaximo')`. Remover os tooltips de espaço físico.
  - KPIs: "Abaixo do Mínimo" e "Acima do Máximo"; remover o selo "SKUs c/ trava física".
  - Pílulas com os novos rótulos.
  - Modal só com Janela, Lead Time, Dias Mínimo e Dias Máximo, e mensagem de validação acessível (`aria-describedby`, `aria-live="polite"`, botão desabilitado).
  - Textos de apoio com os dias de `appliedPolicy()`.
  - Sem valores mágicos de CSS (tokens do Design System).
  - **Regras:** P-055, P-056.1 a P-056.3, CA-01 a CA-08.
- [x] **F-07 — Testes unitários do frontend (Jasmine/Karma).**
  - `inventory-policy.validation.spec.ts`: 30/60/15 válido; 60/60 e 50/45 → `INV-001`; 20/40/45 → `INV-002`; os valores de entrada não são alterados.
  - Specs de `isInventoryCachePayload` (payload v2 antigo é rejeitado) e de `extractInventoryErrorMessage` (array, string, Blob).
  - **Regras:** P-053.3, CA-06, CA-12.

### 7.5 Fechamento

- [x] **Z-01 — Varredura de termos obsoletos.** `grep` sem ocorrência funcional de `rop`, `estoqueSeguranca`, `estoqueIdeal`, `serviceLevel`, `targetCoverageDays`, `budgetLimit`, `maxPurchaseVariationPct`, `limitadoPorEspaco`, `tetoCompraFisica`, `qtdSugeridaTeorica`, `skusLimitadosPorEspaco`, `desvioPadraoDemanda`, `get_z_score`, "Reposição Necessária" e "Excesso / Overstock" em `src/modules/inventory`, `tests/` e `frontend/src/app/features/inventory` (DoD da seção 6).
- [x] **Z-02 — Suítes verdes.** `pytest tests/test_replenishment_policy.py tests/test_inventory_engine.py tests/test_inventory_api.py` e `ng test` verdes. As outras suítes do backend (`pricing`) seguem verdes sem alteração.
- [x] **Z-03 — Commits atômicos (Conventional Commits).** Executados na branch `feature/P-053-estoque-min-max-30-60`:
  1. `f04251a` — `fix(inventory): [P-053] preserva precisao integral da VMD no calculo de velocidade` (B-03, T-04).
  2. `a6141f7` — `feat(inventory)!: [P-053] adota politica min/max por dias de cobertura no motor e na API` (B-01, B-02, B-04 a B-16, T-01 a T-03), com o rodapé `BREAKING CHANGE: /predict, /export-csv e /config passam ao contrato 2.0.0 (ver .agents/docs/api_contracts/inventory.md)`.
  3. `c1e0eb8` — `feat(inventory)!: [P-053] adapta a tela de previsao de estoque a politica min/max` (F-01 a F-07), com o rodapé `BREAKING CHANGE: cache local migra para fitoherb_inventory_cache_v3`.
