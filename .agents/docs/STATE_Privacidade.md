# STATE_Privacidade: Analytics Comercial, Fase 1 (F4 Cross-sell)

> Estado isolado do `privacy_officer` (execução paralela na Etapa 2). Mesclar no `STATE.md` pelo Orquestrador.

| Campo | Valor |
| :--- | :--- |
| **Etapa** | 2: Privacy by Design |
| **Status** | Concluído: APROVADO COM CONDIÇÕES |
| **Parecer** | `.agents/docs/privacy/analytics-cross-sell.md` |
| **Data** | 2026-11-05 |

## Decisões
- `Cod Cliente` e histórico de compras: dado pessoal **pseudonimizado** (pior caso: MEI/empresário individual); não sensível.
- Base legal: **legítimo interesse** (Art. 7º, IX; Art. 10), com LIA simplificado no parecer.
- Perfilamento de consumo existe, mas sem decisão exclusivamente automatizada com efeito sobre o titular: **RIPD não exigido** (gatilhos de reabertura no §2.3 do parecer).
- **A-11 resolvida:** manter `customerCode` no path do GET. Query string não traz ganho (Cloud Run registra a URL completa); POST é desproporcional. Condições LGPD-06 e LGPD-07.
- Requisitos obrigatórios LGPD-01 a LGPD-12 para a implementação e a auditoria da Etapa 4.

## Dívidas técnicas a registrar no STATE.md (pré-existentes, não bloqueiam F4)
- R-02: `Encrypt=no` na conexão ODBC com o SQL Server (Art. 46).
- R-03: HTTP Basic com credencial única, sem rastreabilidade por usuário.
- R-04: `test_db_connection` devolve `str(e)` do driver.

## Pendências para outros agentes
- Analista: atualizar A-11 e P-070.3.
- Arquiteto/Designer/Tester: incorporar LGPD-xx (ver §7 do parecer).

---

## Auditoria Etapa 4 (Auditoria de Código LGPD)

| Campo | Valor |
| :--- | :--- |
| **Etapa** | 4: Quality Gate 360, Auditoria de Código LGPD |
| **Data** | 2026-11-10 |
| **Escopo auditado** | `src/modules/analytics/**` (repositório, domínio, serviço/cache, schemas, mappers, router, error handlers, CLI do backtest), registro em `src/api.py`, `src/core/auth.py`, `frontend/src/app/features/analytics/**`, `tests/analytics/test_analytics_privacy.py` e massa `tests/analytics/fixtures/synthetic_data.py` |
| **Veredito** | **APROVADO COM CONDIÇÕES** (nenhum achado bloqueante no código de produção; condições C-1 a C-3 abaixo) |

### Verificação LGPD-01 a LGPD-12

| ID | Resultado | Evidência |
| :--- | :--- | :--- |
| LGPD-01 | Conforme | `sales_repository._ORDER_BASKETS_SQL` projeta só `Pedido` (como `DENSE_RANK`, sem o número real), `Cod Produto`, `MIN([Cod Cliente])`, `DATEDIFF` da data; `[Operação]` e `[Qtd Venda]` só em `WHERE`/`HAVING`. `_CATALOG_SQL` só com as 6 colunas permitidas. Sem `SELECT *`, sem `UF`, `Valor Venda`, `Cod Promocao`, `EAN`, nome, documento ou endereço. `fetch_sales_from_database` não é reutilizada. |
| LGPD-02 | Conforme | Única entrada externa no SQL (data de corte) vai como `?`. A f-string interpola só constantes do módulo (`ORDER_DAY_EPOCH`, `SALE_OPERATION`). `customerCode` e `sku` validados por `Path(gt=0, le=MAX_INT32)` e filtrados em memória (`searchsorted` sobre o snapshot). `is_readonly_query` antes de executar. |
| LGPD-03 | Conforme | `response_model` explícito em todas as rotas; `CustomerCrossSellData` só tem `recomendacoes`; sem eco de `customerCode`; sem `Pedido`, datas absolutas, valores ou perfil completo. `pedidosEmComum` é métrica global da regra (k >= 10), já aceita. `parametros.customerProfileDays` é **nome de constante de configuração** (365), não dado de cliente. |
| LGPD-04 | Conforme | Só 3 chamadas de log no módulo: tipo da exceção (repositório), contagens agregadas e duração em segundos (cache). Nenhum `customerCode`, DataFrame, lista, perfil ou payload. Serviço e router sem log. |
| LGPD-05 | Conforme | Exceções de domínio com mensagens fixas (XSL-002 sem o código). Handler de validação devolve só nomes de campos (`loc[-1]`). Erro de driver vira `ANL-001` com `from None` e log só de `type(exc).__name__`. Sem stacktrace no corpo. |
| LGPD-06 | **Pendente fora do código (condição C-2)** | Nenhum middleware de log de request no app. IAM e retenção de 30 dias do Cloud Logging dependem da configuração do projeto GCP: verificação do `devops` na Etapa 5. |
| LGPD-07 | Conforme | Rota com `customerCode` só no path e `limit`/`offset` na query; `AnalyticsService.getCustomerCrossSell` não usa header nem query para o código. |
| LGPD-08 | Conforme | Histórico do cliente dentro do snapshot imutável (vetores `int32`), invalidado junto com a base pelo TTL; não há cache por cliente (logo, sem acúmulo). Nenhum `to_csv`, `pickle`, `open`, `/tmp`, Redis ou chamada HTTP externa no módulo. |
| LGPD-09 | Conforme (melhor que o mínimo) | Código do cliente **não** vai para a URL da SPA: `CrossSellPageComponent.syncUrl` grava só `?modo=cliente` (Design Plan D-6). Sem `localStorage`/`sessionStorage`/IndexedDB/cookies na feature; sem script de terceiros em `index.html`. Observação: a premissa "`?modo=cliente&cliente=`" citada na convocação **não** corresponde ao Design Plan nem ao código, e não deve ser adotada. |
| LGPD-10 | Conforme | Router incluído no `app` com `HTTPBasicAuthASGIMiddleware` global (sem exceção de path); teste de 401 em produção existe em `test_analytics_api_foundation.py`. |
| LGPD-11 | Conforme no código (condição C-3 para o artefato real) | `render_markdown` só imprime taxas, contagens de avaliados e de excluídos por motivo e medições; nada gravado em arquivo. Massa de teste sintética. |
| LGPD-12 | Conforme | Sem endpoint de exportação nem integração de disparo; `POST /cache/reload` não expõe dado de cliente. |

### Achados bloqueantes
- Nenhum no código de produção.

### Achados não bloqueantes (recomendações)
- **NB-01:** acrescentar `Cache-Control: no-store` na resposta de `GET /cross-sell/customer/{customerCode}`, para o navegador não guardar em disco a recomendação ligada ao código (Art. 46, defesa em profundidade). Pode entrar como melhoria pós-merge.
- **NB-02:** exceção não prevista cai no 500 genérico do Starlette, que registra o traceback no logger `uvicorn.error`. Tracebacks não incluem variáveis locais e os pontos de `KeyError` possíveis (`catalog[...]`) carregam SKU, não cliente. Risco muito baixo; manter a regra de não interpolar `customer_code` em mensagens de exceção.
- **NB-03 (pré-existente, fora do módulo):** o 422 padrão do FastAPI nas rotas de pricing/inventory ecoa o valor recebido em `input`. Não envolve dado de cliente hoje; registrar para o `security`.
- **NB-04:** dívidas R-02 (`Encrypt=no`), R-03 (credencial única) e R-04 (`str(e)` em `test_db_connection`) continuam abertas e não bloqueiam F4.

### Condições para avançar
- **C-1:** o `tester` aplica a decisão sobre os 3 testes abaixo, sem outras mudanças, e a suíte `tests/analytics/test_analytics_privacy.py` passa inteira.
- **C-2:** `devops` confirma na Etapa 5 que o Cloud Logging do projeto tem acesso restrito por IAM e não há sink de longo prazo com as rotas `/api/v1/analytics/cross-sell/customer/*` (LGPD-06).
- **C-3:** a saída real do backtest (B-18) é colada no PR só como a tabela agregada do CLI; nenhum código de cliente em PR, log de CI ou arquivo versionado.

### Decisão sobre os testes contestados
Os três testes estão **errados**; o código está correto. As correções abaixo não enfraquecem a proteção: cada exceção é a mais estreita possível e vem com uma asserção nova que a compensa.

1. **`test_customer_route_logs_nothing_about_the_customer`: teste errado.** O registro vem do logger `httpx` do `TestClient` (lado do cliente HTTP do teste), equivalente ao log de acesso cuja exposição foi aceita no parecer (§4, R-01, LGPD-06). Correção em `_assert_logs_are_clean`: ignorar **apenas** registros cujo `record.name` seja `httpx` ou `httpcore` ou comece com `httpx.`/`httpcore.` (constante `TEST_CLIENT_LOGGERS = ("httpx", "httpcore")`). **Não** trocar por uma allowlist de `src.*`: o filtro tem de continuar pegando logs da raiz, `uvicorn`, `fastapi` e `starlette`. Manter `caplog.set_level(logging.DEBUG)` e todas as demais asserções.
2. **`test_product_response_has_only_allowlisted_keys_and_no_customer_data`: teste errado.** `customerProfileDays` é nome de parâmetro exigido pelo contrato, não dado de cliente. Correção: (a) acrescentar `assert set(body["meta"]["parametros"]) == PARAMETER_KEYS` (as 7 chaves do contrato) e que todo valor de `parametros` é `int` ou `float` e não `bool`; (b) no laço de `_all_keys`, isentar **somente** o par exato `(path, key) == (".meta.parametros", "customerProfileDays")`. Nenhuma outra chave ou caminho isento.
3. **`test_health_exposes_no_customer_data`: teste errado (mesmo motivo).** Correção: (a) manter a checagem dos códigos de cliente em `response.text`; (b) acrescentar `assert set(body["data"]["parametros"]) == PARAMETER_KEYS` com valores numéricos escalares; (c) acrescentar allowlist de `body["data"]` (`status, estadoCache, cacheCarregado, baseSuficiente, carregadoEm, expiraEm, duracaoUltimaCargaMs, contagens, parametros`) e de `body["meta"]` (`timestamp, version, dataReferencia`); (d) trocar `assert "customer" not in response.text.lower()` por: copiar o corpo (`copy.deepcopy`), remover só `data.parametros.customerProfileDays` e afirmar que `"customer"` e `"cliente"` não aparecem em `json.dumps(copia).lower()`.
