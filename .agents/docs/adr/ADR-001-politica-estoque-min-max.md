# ADR-001 — Política de Estoque Mínimo/Máximo por Dias de Cobertura

| Campo | Valor |
| :--- | :--- |
| **ID** | ADR-001 |
| **Título** | Substituir ROP + estoque de segurança + travas pela Política Mín/Máx por dias de cobertura |
| **Status** | Proposto (aguarda checkpoint do usuário na Etapa 2) |
| **Data** | 2026-11-05 |
| **Feature** | P-053 — `feature/P-053-estoque-min-max-30-60` |
| **Autor** | Arquiteto (Etapa 2) |
| **Regras de negócio** | `.agents/docs/business_rules/estoque-min-max.md` (P-053 a P-056) |
| **Contrato de API** | `.agents/docs/api_contracts/inventory.md` (versão 2.0.0) |
| **Tarefas** | `.agents/docs/tasks/estoque-min-max.md` (seção 7) |
| **Decisões de origem** | `STATE.md`: D1–D4 (usuário) e A1–A5 (Orquestrador) |

> Observação de governança: `.agents/docs/adr/TEMPLATE.md` não existe no repositório. Este ADR segue a estrutura clássica (Contexto → Decisão → Alternativas → Consequências) até que o template seja criado.

---

## 1. Contexto

O módulo `inventory` calcula, por SKU, a sugestão de compra exibida na tela "Estoque Ideal & Previsão de Compras". Hoje o motor (`src/modules/inventory/domain/inventory_engine.py`) aplica um modelo estatístico:

- Estoque de segurança `z × σ × √LT` (z-score obtido via `scipy.stats.norm.ppf`, com tabela de fallback).
- ROP `VMD × LT + ES` e estoque ideal `VMD × (LT + cobertura alvo) + ES`.
- Trava percentual de variação física da compra (P-044.4), com teto e piso operacional.
- Teto orçamentário em R$ com priorização e corte de quantidades (P-046.3).

A distribuidora pratica outra política: manter entre 30 e 60 dias de venda; ao chegar em 30 dias, comprar até 60. As travas cortam a sugestão e o resultado diverge da prática (D1, D2).

Problemas técnicos adicionais identificados:

1. **God Function.** `calculate_inventory_replenishment` tem cerca de 250 linhas, 8 parâmetros e mistura normalização de catálogo, Curva ABC, cálculo por item, trava física, orçamento, ordenação e KPIs.
2. **Precisão da VMD (A3).** A VMD é arredondada a 4 casas nos dois caminhos de cálculo (`calculate_sales_velocity` em memória e `fetch_sales_velocity_from_database` no SQL Server). Com a nova fórmula `teto(VMD × dias)`, isso gera unidades a mais em itens de giro baixo (exemplo E5: 1 un em 60 dias resulta em máximo 2, e não 1).
3. **Resíduo de ponto flutuante.** Mesmo sem o arredondamento, `teto(q / w × d)` em `float64` erra quando o produto exato é inteiro mas o binário fica um pouco acima. Exemplo: 31 / 15 × 15 = `31.000000000000004`, cujo teto é 32.
4. **Único consumidor.** A API é consumida apenas pelo SPA Angular do mesmo repositório. O `Dockerfile` compila o frontend e o copia para a mesma imagem servida pelo FastAPI, então o deploy é atômico.

---

## 2. Decisão

### DA-01 — Motor Mín/Máx determinístico com objeto de política

Adotar a Política Mín/Máx por dias de cobertura (P-053 a P-055) como único modelo de reposição do módulo:

- `Estoque Mínimo = ceil_units(VMD × minCoverageDays)` e `Estoque Máximo = ceil_units(VMD × maxCoverageDays)`. Com `VMD = 0`, ambos são 0.
- Gatilho de compra: `VMD > 0` e (`estoque ≤ mínimo` ou ruptura iminente). Quantidade: `ceil_units(máximo − estoque)`, sem cortes.
- O lead time participa apenas da classificação `CRITICAL_STOCKOUT` (`diasCobertura < leadTime`, com a cobertura já arredondada a 1 casa, como exibida).
- Os parâmetros do cálculo trafegam em um objeto de valor imutável do domínio:

```python
@dataclass(frozen=True)
class ReplenishmentPolicy:
    """Política Mín/Máx (P-053.2) + lead time sinalizador de ruptura (P-055.3)."""
    min_coverage_days: int = DEFAULT_MIN_COVERAGE_DAYS   # 30
    max_coverage_days: int = DEFAULT_MAX_COVERAGE_DAYS   # 60
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS         # 15

    def __post_init__(self) -> None:
        # Defesa em profundidade: as mesmas checagens usadas pela API (DA-05).
        ...
```

São removidos do motor: `get_z_score`, estoque de segurança, ROP, estoque ideal (teórico e operacional), trava física (P-044.4) e teto orçamentário com priorização (P-046.3).

### DA-02 — Precisão da VMD e teto imune a resíduo (decisão técnica para A3)

**Escolha: as duas medidas, combinadas.**

1. **Não arredondar a coluna `vmd`** no DataFrame de velocidade, nos dois caminhos: `calculate_sales_velocity` (em memória) e `fetch_sales_velocity_from_database` (pós-processamento Python; a query SQL não muda, então o bypass do DBA continua válido). O arredondamento passa a existir só na serialização do item (`vmd` com 2 casas, para exibição).
2. **Aplicar o teto sobre o valor arredondado a 6 casas**, por meio de uma única função de domínio:

```python
UNIT_CEIL_GUARD_DECIMALS = 6  # descarta resíduo binário de float64 antes do teto (P-053.6)

def ceil_units(value: float) -> int:
    """Arredonda unidades para cima sem ser acionado por resíduo de ponto flutuante."""
    return math.ceil(round(value, UNIT_CEIL_GUARD_DECIMALS))
```

`ceil_units` é usada no mínimo, no máximo e na quantidade sugerida (P-054.2).

**Justificativa e evidência.** A verificação numérica comparou cada estratégia com o teto exato `ceil(Fraction(q × d, w))`. O teste cobriu janelas de 15 a 365 dias, quantidades de 0 a 99.999 un e 12 valores de dias de cobertura entre 1 e 365, num total de 1.705.860 combinações:

| Estratégia | Divergências do valor exato |
| :--- | :--- |
| VMD com 4 casas (comportamento atual) + teto sobre 6 casas | 13.544 (inclui E5: 1 un/60 d → máximo 2) |
| VMD em precisão integral + teto direto | 1.706 (ex.: 31/15 × 15 → 32) |
| **VMD em precisão integral + teto sobre 6 casas (escolhida)** | **0** |
| Idem, quantidades fracionárias com 3 casas (68.592 casos) | **0** |

**Por que 6 casas é seguro.** Com quantidades de até 3 casas decimais e janela de até 365 dias, a parte fracionária real de `VMD × dias` é 0 ou pelo menos `1 / (1000 × 365) ≈ 2,7 × 10⁻⁶`. Arredondar a 6 casas só absorve valores abaixo de `5 × 10⁻⁷`. Já o erro de `float64` fica abaixo de `10⁻⁹` para valores até 10⁶ un. As duas faixas não se sobrepõem.

**Premissa registrada.** `Qtd Venda` no ERP tem no máximo 3 casas decimais. Se um dia houver 4 ou mais casas, reavaliar esta constante.

### DA-03 — `get_z_score` removido; `scipy` permanece no projeto

- `get_z_score` e sua exportação em `domain/__init__.py` são removidos, junto com `test_get_z_score`. O módulo `inventory` deixa de depender de `scipy`.
- `scipy` **permanece** em `requirements.txt`, porque o módulo `pricing` usa `scipy.optimize.linprog` (`price_optimizer.py`) e `scipy.sparse.csr_matrix` (`basket_mining.py`).

### DA-04 — `desvioPadraoDemanda` sai do contrato; `std_demand` fica interno

- **Sai da resposta.** O desvio-padrão não participa de nenhuma regra (P-053.7) e está listado como obsoleto no `GLOSSARY.md`. Ele não é exibido na tela nem exportado no CSV (`grep` no template confirma). Mantê-lo como "informativo" sugeriria ao comprador que a volatilidade influencia a compra (CA-P053-07 afirma o contrário) e contraria a minimização do contrato.
- **Fica interno.** A coluna `std_demand` do DataFrame de velocidade é mantida para não alterar a query SQL (que calcula `sum_sq`) nem o teste de velocidade existente. O motor deixa de lê-la. Isso fica registrado como dívida técnica de baixo custo, a remover numa revisão futura da query com o DBA.

### DA-05 — Validação cruzada: regra no domínio, 422 no formato padrão do FastAPI

- A regra (P-053.3 e A2) mora no domínio, em duas funções puras que **retornam** a violação em vez de lançar exceção:
  - `check_max_coverage_greater_than_min(min_days, max_days) -> Optional[PolicyViolation]` → código `INV-001`.
  - `check_lead_time_below_max_coverage(lead_time_days, max_days) -> Optional[PolicyViolation]` → código `INV-002`.
- **API.** `InventoryPredictRequest` usa `field_validator` em `maxCoverageDays` e em `leadTimeDays`. Os validadores delegam a essas funções e convertem a violação em `PydanticCustomError(code, message, context)`. O FastAPI devolve **HTTP 422** no formato padrão, com `type = "INV-00X"` e `loc = ["body", "<parâmetro>"]`, o que identifica o parâmetro sem que o cliente precise interpretar texto.
- **Ordem de declaração obrigatória** dos campos do request: `historyWindowDays`, `minCoverageDays`, `maxCoverageDays`, `leadTimeDays`, `fornecedor`. O Pydantic v2 valida na ordem de declaração, e `info.data` só contém os campos anteriores ao que está sendo validado. Se o campo de referência falhou (por exemplo, por faixa), o validador cruzado retorna cedo, sem erro duplicado.
- **Domínio.** `ReplenishmentPolicy.__post_init__` aplica as mesmas checagens e lança `InvalidReplenishmentPolicyError` (com `.code`). Isso protege chamadas diretas ao motor, como testes e scripts. Pela API esse erro não ocorre, porque o Pydantic barra antes.
- Não é criado um handler global de 422. Isso mudaria o contrato de erro do módulo `pricing` e está fora do escopo.

### DA-06 — Parâmetros revogados são ignorados (P-056.4)

`InventoryPredictRequest` declara explicitamente `model_config = ConfigDict(extra="ignore")`. Assim, `serviceLevel`, `targetCoverageDays`, `budgetLimit` e `maxPurchaseVariationPct` enviados por um cliente antigo são descartados antes do domínio e não alteram o resultado (CA-P056-02). A alternativa `extra="forbid"` foi descartada: uma aba com o SPA antigo aberto receberia 422 em vez de um resultado.

### DA-07 — Breaking change sem novo prefixo de URL

- O contrato de `/predict`, `/export-csv` e `/config` muda de forma incompatível: campos removidos e renomeados, rótulos alterados e colunas do CSV trocadas.
- **Mantém-se `/api/v1`.** O único consumidor é o SPA do mesmo repositório, empacotado na mesma imagem Docker (deploy atômico). Uma rota `/api/v2` paralela duplicaria código sem consumidor externo.
- `meta.version` das respostas do módulo passa de `"1.0.0"` para `"2.0.0"` (constante `INVENTORY_CONTRACT_VERSION`) como marcador explícito de versão do contrato.
- Os commits seguem `feat(inventory)!:` com rodapé `BREAKING CHANGE:` que descreve a migração (regra de commits do projeto).

### DA-08 — Bloco `politica` ecoado na resposta de `/predict`

`data.politica = { historyWindowDays, leadTimeDays, minCoverageDays, maxCoverageDays }` é montado pelo serviço a partir do request já validado, com os padrões aplicados. Ele serve para três coisas:

1. A tela rotula colunas, KPIs e textos com os dias **efetivamente usados** no resultado exibido, e não com o rascunho do modal.
2. O cache local restaura os parâmetros junto com o resultado.
3. A exportação CSV reenvia exatamente a política do resultado exibido (P-056.6).

A mudança é aditiva e de baixo custo (4 inteiros).

### DA-09 — Cache `localStorage` da tela troca de chave e passa a validar o formato

- A chave `fitoherb_inventory_cache_v2` é substituída por `fitoherb_inventory_cache_v3`. A chave `v2` é removida na inicialização da página (CA-12).
- O payload passa a ser `{ kpis, produtos, politica, savedAt }`. Um *type guard* (`isInventoryCachePayload(value: unknown)`) descarta qualquer conteúdo fora do formato, por exemplo sem `politica` ou sem `estoqueMinimo` no item. Nesse caso a chave é removida e o cálculo é refeito (defesa em profundidade além da troca de chave).
- Dados armazenados: só catálogo e agregados de venda por SKU, sem token nem dado pessoal. Isso está em conformidade com a regra de segurança, que proíbe apenas credenciais em `localStorage`, e com o bypass do Privacy Officer registrado no `STATE.md`.

### DA-10 — Decomposição do motor (fim da God Function)

O motor passa a ter funções puras de no máximo cerca de 40 linhas, no máximo 3 parâmetros (ou um objeto), *early return* e constantes nomeadas. A preparação do catálogo, que inclui o filtro de fornecedor P-047.1, sai do cálculo. Assim o orquestrador fica com 3 parâmetros, e a Curva ABC continua global porque é derivada do DataFrame de velocidade, que não é filtrado.

| Arquivo | Função / tipo | Responsabilidade | Regra |
| :--- | :--- | :--- | :--- |
| `domain/replenishment_policy.py` (novo) | `ReplenishmentPolicy`, `PolicyViolation`, `InvalidReplenishmentPolicyError` | Objeto de política e invariantes | P-053.2, P-053.3, A2 |
| idem | `check_max_coverage_greater_than_min`, `check_lead_time_below_max_coverage` | Checagens puras (`INV-001`, `INV-002`) | P-053.3, A2 |
| idem | `ceil_units(value)` | Teto sem resíduo (DA-02) | P-053.6, P-054.2 |
| idem | `StockLevels`, `calculate_stock_levels(vmd, policy)` | Mínimo e máximo; `VMD ≤ 0` → (0, 0) | P-053.4, P-053.5, P-053.8 |
| `domain/inventory_engine.py` | `calculate_sales_velocity` (inalterada, exceto o arredondamento da `vmd`) | VMD em memória | P-041, DA-02 |
| idem | `normalize_product_catalog(products_df)` + helpers `_resolve_column`, `_apply_unit_cost_fallback`, `_fill_text_column` | Colunas canônicas, estoque negativo → 0, custo com fallback | P-053.9, P-054.5 |
| idem | `filter_products_by_supplier(catalog_df, supplier_filter)` | Filtro opcional | P-047.1 |
| idem | `prepare_product_catalog(products_df, supplier_filter)` | Normaliza e filtra | P-047.1 |
| idem | `classify_abc_curve(revenue_by_sku)`, `SalesLookup`, `build_sales_lookup(velocity_df)` | Curva ABC global e consulta de VMD | Curva ABC |
| idem | `InventoryStatus` (`str`, `Enum`), `STATUS_LABELS` | Códigos e rótulos novos | P-055.2 |
| idem | `calculate_coverage_days(current_stock, vmd)` | Dias de cobertura (999 / 0) | P-055.1 |
| idem | `StockPosition`, `build_stock_position(current_stock, vmd, policy)` | Posição do SKU frente à política | P-053, P-055.1 |
| idem | `is_stockout_imminent(position, lead_time_days)` | Ruptura iminente | P-055.2 (1) |
| idem | `is_purchase_triggered(position, lead_time_days)` | Gatilho de compra | P-054.1 |
| idem | `calculate_suggested_purchase(position, lead_time_days)` | Compra até o máximo, sem travas | P-054.2 a P-054.4 |
| idem | `classify_stock_status(position, suggested_qty, lead_time_days)` | Precedência de status com *early return* | P-055.2 |
| idem | `calculate_overstock_capital(position, unit_cost, status)` | Capital imobilizado do item | P-055.4 |
| idem | `ProductEvaluation` (+ `to_response_item()`), `evaluate_product(product_row, sales_lookup, policy)` | Resultado tipado por SKU e serialização camelCase | P-054.5 |
| idem | `product_sort_key(evaluation)` | Ordenação padrão | P-055.6 |
| idem | `build_kpis(evaluations)` | KPIs por status, investimento e capital | P-055.5, P-054.6 |
| idem | `calculate_inventory_replenishment(catalog_df, velocity_df, policy)` | Orquestrador (≤ 25 linhas) | P-053 a P-056 |

O fluxo no serviço passa a ser:

```python
policy = to_replenishment_policy(request)                                    # mapper API → domínio
velocity_df = get_inventory_velocity(request.historyWindowDays)
catalog_df = prepare_product_catalog(get_inventory_catalog(), request.fornecedor)
result = calculate_inventory_replenishment(catalog_df, velocity_df, policy)
result["politica"] = build_policy_echo(request)                              # DA-08
```

### DA-11 — Endurecimento nos arquivos já tocados

Estes três ajustes cabem no escopo porque os arquivos já mudam, e a revisão de segurança da Etapa 4 os vetaria:

1. **Respostas 500 genéricas.** O router deixa de devolver `str(e)` no `detail`. O erro completo vai apenas para o log, com `exc_info=True`.
2. **Nome do arquivo CSV.** O slug do fornecedor no `Content-Disposition` passa a ser sanitizado (`[a-z0-9_]`) e a montagem sai do router para o serviço (`build_csv_filename`), porque controller não decide.
3. **`fornecedor` limitado** a `max_length=120`.

---

## 3. Alternativas consideradas e descartadas

| # | Alternativa | Motivo do descarte |
| :--- | :--- | :--- |
| ALT-1 | Manter estoque de segurança/ROP e trocar só a cobertura alvo por 30/60 | Contraria D2 (30/60 puro, sem z-score). Mantém complexidade estatística que o negócio não usa. |
| ALT-2 | Mínimo híbrido `VMD × 30 + ES` | Contraria D2 e CA-P053-07: a volatilidade não pode alterar o mínimo. |
| ALT-3 | Manter trava física e teto orçamentário como opcionais, desligados por padrão | Contraria D1 (revogação). Mantém cerca de 80 linhas de código e dois parâmetros sem uso, com risco de reativação acidental. |
| ALT-4 | Cálculo exato com inteiros/`Fraction` a partir de `total_sold_qty` e da janela | Exato, mas exige levar a quantidade vendida e a janela até o motor e mudar a interface do DataFrame de velocidade. O ganho é nulo frente a DA-02 (0 divergências em 1,7 milhão de casos). |
| ALT-5 | Só remover o arredondamento de 4 casas | 1.706 divergências por resíduo binário (ex.: 31/15 × 15 → 32). |
| ALT-6 | Só aplicar a guarda de 6 casas, mantendo a VMD com 4 casas | 13.544 divergências. Não resolve E5. |
| ALT-7 | `Decimal` em toda a cadeia de cálculo | Custo de desempenho e de interoperabilidade com pandas/numpy sem benefício sobre DA-02. |
| ALT-8 | `extra="forbid"` (rejeitar parâmetros revogados com 422) | Uma aba com o SPA antigo aberto quebraria com erro. O Orquestrador decidiu ignorar (P-056.4). |
| ALT-9 | Rota `/api/v2/inventory` paralela | Sem consumidor externo e com deploy atômico. Duplicaria router, schemas e testes. |
| ALT-10 | `model_validator(mode="after")` para a validação cruzada | O erro sairia com `loc = ["body"]`, sem identificar o parâmetro (P-053.3 exige identificar). |
| ALT-11 | Handler global de 422 com envelope `{error, code}` para toda a aplicação | Mudaria o contrato de erro do módulo `pricing`. Fica fora do escopo e pode virar um ADR próprio. |
| ALT-12 | Manter `desvioPadraoDemanda` como campo informativo | Ver DA-04: induz leitura errada da regra e é payload sem uso. |

---

## 4. Consequências

### Positivas

- O resultado bate com a prática da distribuidora (30/60). O cálculo é determinístico, auditável à mão e explicável ao comprador.
- O código encolhe: saem z-score, ES, ROP, trava física e orçamento. O motor passa a ter funções pequenas e testáveis isoladamente.
- A precisão de `teto(VMD × dias)` fica provada contra o valor exato (DA-02).
- Os erros de parâmetros identificam o campo (`loc`) e trazem código estável (`INV-001`, `INV-002`).

### Negativas e custos

- **Breaking change** em `/predict`, `/export-csv` e `/config` (DA-07). Os testes de P-044.4, P-046.3 e z-score são removidos e substituídos.
- **Investimento sugerido maior.** Sem travas, o total pode crescer bastante (CA-P054-06). O risco de negócio foi aceito pelo usuário (D1).
- **Aba com bundle antigo aberta durante o deploy.** Os parâmetros antigos são ignorados (cálculo 30/60 padrão) e as colunas ROP/Est. Ideal aparecem vazias até o recarregamento da página. A situação é transitória.
- `std_demand` continua sendo calculado sem consumidor (dívida técnica, DA-04).
- `vmd` em precisão integral no DataFrame. A exibição continua com 2 casas, então o cliente **não deve** recalcular mínimo/máximo a partir da `vmd` exibida (registrado no contrato).

### Riscos e mitigação

| Risco | Mitigação |
| :--- | :--- |
| Alguém reordenar os campos de `InventoryPredictRequest` e desligar silenciosamente a validação cruzada | Comentário no schema explicando a dependência de ordem, mais testes de API para `INV-001` e `INV-002` (tarefas T-03). |
| Desalinhamento entre as faixas de `/config` e as constantes do frontend (a tela não consome `/config`) | Constantes centralizadas em `inventory.constants.ts`, com comentário de referência ao contrato. Teste de `/config` que verifica os valores. |
| CSV diferente da tela porque o modal altera os sinais antes de "Aplicar" | Rascunho e política aplicada separados no estado da página. O CSV usa `politica` do último resultado (F-04). |
| `index.html` do SPA em cache do navegador após o deploy | Os bundles do Angular têm hash. O type guard do cache (DA-09) evita renderizar formato antigo. |
| Quantidades com 4 ou mais casas decimais no ERP invalidarem a premissa de DA-02 | Premissa documentada na constante `UNIT_CEIL_GUARD_DECIMALS`. Teste de regressão com 3 casas. |

### Rollback

Reverter o merge da feature. Como o deploy é atômico, backend e frontend voltam juntos. A chave `fitoherb_inventory_cache_v3` fica órfã nos navegadores e a versão antiga, que lê a `v2` (já removida), refaz o cálculo. Não há migração de dados nem alteração de schema.

---

## 5. Referências

- `.agents/docs/business_rules/estoque-min-max.md` — P-053 a P-056, exemplos E1–E6, C1–C8, S1–S9.
- `.agents/docs/api_contracts/inventory.md` — contrato v2.0.0.
- `.agents/docs/tasks/estoque-min-max.md` — checklist técnico (seção 7).
- `.agents/docs/GLOSSARY.md` — identificadores confirmados.
- Pydantic v2: ordem de validação de campos e `ValidationInfo.data`; `pydantic_core.PydanticCustomError`.
