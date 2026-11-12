# STATE_Backend — Fase 1 Analytics Comercial (F4 Cross-sell) — Etapa 3 (Developer Backend)

| Campo | Valor |
| :--- | :--- |
| Agente | `developer` (frente Backend, em paralelo com o Frontend) |
| Data | 2026-11-09 |
| Branch | `feature/analytics-cross-sell` (sem commit; commits na Etapa 5) |
| Escopo | B-01 a B-17, B-19, B-20 (B-18 fica para a Etapa 5) |
| Status | Concluído; 3 testes considerados incorretos (ver abaixo) |

## Arquivos
- Alterados: `src/modules/pricing/domain/basket_mining.py` (B-09: `*, max_len=None`), `src/api.py` (router + handlers).
- Criados em `src/modules/analytics/`: `api/{schemas,mappers,error_handlers,router}.py`,
  `service/{analytics_cache,analytics_service}.py`,
  `domain/{exceptions,pagination,number_format,cross_sell,cross_sell_customer,cross_sell_explanation,cross_sell_backtest,product_search}.py`,
  `repository/{errors,sales_repository}.py`, `backtest/run_cross_sell_backtest.py`, `__init__.py` de cada pacote.
- Uma execução anterior, interrompida por limite de uso, havia deixado rascunhos destes arquivos. Eles foram revisados e reescritos para cumprir as regras (funções ≤ 30 linhas, sem `except: pass`, sem `except Exception` amplo, constantes com fonte única).

## Decisões e desvios do checklist
1. **`ORDER_DAY_EPOCH` definido no domínio** (`cross_sell.py`) e reexportado pelo repositório (`repo.ORDER_DAY_EPOCH`). O backtest (domínio puro) precisa da época e não pode importar o repositório. `SALE_OPERATION` segue a mesma regra (DA-02).
2. **Limites inclusivos (P-060.1):** `FLOAT_TOLERANCE = 1e-9` nas comparações de confiança/lift/trivial e nos limites passados ao mlxtend. Não foi possível recalcular só pelas contagens inteiras: `test_just_below_limits_is_rejected` injeta `confidence=0.0999` com contagens que dão 0,10, então o filtro tem de usar a coluna do mlxtend.
3. **Arredondamento** (`domain/number_format.py`): `Decimal(str(x))`, depois remoção de ruído binário em 9 casas, depois `ROUND_HALF_UP`. Assim 4,25 × 0,34 × 5 = 7.2250000000000005 vira `7,23`, e o percentual é multiplicado por 100 em `Decimal`.
4. **Empate de pontuação (P-064.1):** em empate exato, a regra principal fica com o menor código de antecedente (bate com o exemplo do contrato §3.4, que mostra A).
5. **`force_reload` concorrente:** reaproveita a carga por identidade do snapshot (o que foi lido antes do lock é comparado com o publicado), e não por horário. Dessa forma, um reload que chega durante outra carga não recebe `ANL-002`.
6. **Catálogo** em cache próprio (`get_catalog()`, TTL de 6 h e lock próprio), com o índice de busca pré-normalizado. A carga do snapshot reaproveita esse catálogo (DA-06).
7. **`CustomerHistory`** guarda três vetores `int32` ordenados por cliente e consulta por `searchsorted` (DA-03), sem um dicionário por cliente.
8. **Log da carga** só com contagens e a duração em segundos com 1 casa. A duração em ms poderia, por acaso, conter um código de SKU ou cliente da massa de teste.
9. **DC-4 / A-13:** não rodei a consulta de diagnóstico, pois a instrução era não acessar o banco. O Orquestrador já a havia executado em 2026-11-05 (`STATE.md`): 0 pedidos com mais de um `Cod Cliente`.
10. Rota por cliente com `Path(alias="customerCode")` (DC-1 = GET). A busca valida `q` com `AfterValidator` sobre a regra pura `is_valid_search_query`, então os campos inválidos saem juntos no 400.

## Testes considerados incorretos (não alterados)
- `test_analytics_privacy.py::test_customer_route_logs_nothing_about_the_customer`: o registro com o código vem do logger `httpx` do próprio `TestClient` (`HTTP Request: GET .../customer/48213`), e não da aplicação. Os loggers da aplicação não emitem nada nessa rota (verificado). Sugestão ao Tester: filtrar `caplog` pelos loggers `src.*` ou subir `httpx` para WARNING.
- `test_analytics_privacy.py::test_product_response_has_only_allowlisted_keys_and_no_customer_data` e `::test_health_exposes_no_customer_data`: proíbem a substring "customer" em chaves e no texto. Porém o contrato (§2.2, §3.1) exige `parametros.customerProfileDays`, e outros testes do próprio Tester a exigem (`PARAMETER_KEYS`, `EXPECTED_PARAMETERS`). Sugestão: ignorar `parametros` nessas checagens.

## Pendências
- B-18 (Etapa 5): `python -m src.modules.analytics.backtest.run_cross_sell_backtest --months 2026-08 2026-09 2026-10` na base real. O CLI foi testado com o repositório substituído pela massa sintética (corte de 2026-11-01, tabela só com agregados).
