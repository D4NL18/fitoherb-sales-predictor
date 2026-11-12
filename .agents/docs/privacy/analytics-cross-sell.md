# Parecer de Privacy by Design: Analytics Comercial, Fase 1 (F4 Recomendação de Cross-sell)

| Campo | Valor |
| :--- | :--- |
| **Feature** | F4 Recomendação de cross-sell (por produto e por cliente) e fundação do módulo `analytics` |
| **Branch** | `feature/analytics-cross-sell` |
| **Etapa** | 2: Revisão de Privacy by Design (pré-implementação) |
| **Responsável** | `privacy_officer` (`lgpd-privacy-expert`) |
| **Entradas** | `business_rules/analytics-cross-sell.md` (P-058 a P-071, P-070, premissa A-11), `tasks/ia-analytics-vendas.md` §2.8, `src/core/database.py`, `src/core/auth.py`, `Dockerfile` |
| **Data** | 2026-11-05 |
| **Conclusão** | **APROVADO COM CONDIÇÕES** (requisitos LGPD-01 a LGPD-12). **RIPD não exigido.** |

---

## 1. Classificação dos dados tratados

| Dado | Origem | Classificação LGPD | Observação |
| :--- | :--- | :--- | :--- |
| `Cod Cliente` | `Externo01.Vendas` | **Dado pessoal pseudonimizado** quando o cliente é pessoa natural (MEI, empresário individual, produtor rural PF). **Dado de PJ, fora da LGPD**, nos demais casos | O código não identifica ninguém sozinho, mas é reidentificável por quem tem acesso ao ERP (informação adicional mantida pelo controlador). Pseudonimizado continua sujeito à LGPD (Art. 12, §3º e Art. 13, §4º). Como o sistema não distingue PF de PJ, **todo `Cod Cliente` é tratado como dado pessoal** (regra do pior caso). |
| Histórico de compras por cliente (SKU, data do último pedido, perfil 365 d, produtos dormentes, `diasDesdeUltimaCompra`) | Agregação de `Externo01.Vendas` | **Dado pessoal pseudonimizado** (mesma condição), **comportamental/de consumo**. Não sensível (Art. 5º, II) | Constitui **perfil de consumo** (Art. 12, §2º e Art. 20). |
| Recomendação por cliente (lista de SKUs, pontuação, motivo) | Derivado | **Dado pessoal pseudonimizado inferido** | Ligado ao `customerCode` da requisição. |
| `Pedido` | `Externo01.Vendas` | Pseudonimizado (liga-se ao cliente no ERP) | Uso **apenas interno** para formar cestas; nunca exposto. |
| Regras de associação (suporte, confiança, lift, `pedidosEmComum`), itens triviais | Agregado de toda a base | **Não pessoal (agregado estatístico)** | Mínimo de `MIN_PAIR_ORDERS = 10` pedidos por regra reduz risco de inferência individual (k ≥ 10). |
| Produto (código, descrição, fornecedor, estoque, preço, custo, margem) | `Externo01.Produto` | **Não pessoal** (dado comercial) | Sigilo comercial, não LGPD. |
| `UF`, `Valor Venda`, nome, razão social, CPF/CNPJ, endereço, contatos | ERP | Pessoal (quando PF) | **Não tratados** nesta fase. |

Nenhum dado sensível (Art. 11) é tratado. Não há dados de crianças/adolescentes.

---

## 2. Base legal e necessidade de RIPD

### 2.1 Base legal

**Legítimo interesse do controlador (Art. 7º, IX, c/c Art. 10).** Confirmo a proposta do Analista.

- *Execução de contrato* (Art. 7º, V) foi descartada: a recomendação de novos produtos não é necessária à execução dos pedidos já firmados.
- *Consentimento* foi descartado: desproporcional numa relação B2B existente, cujo titular eventual é um MEI/empresário que já compra da distribuidora.

**Teste de ponderação (LIA) simplificado:**

| Etapa | Avaliação | Resultado |
| :--- | :--- | :--- |
| Finalidade | Apoiar o vendedor a oferecer produtos relevantes a clientes **com relação comercial ativa** (Art. 10, I: "apoio e promoção de atividades do controlador"). Interesse legítimo, concreto e atual. | Atende |
| Necessidade | Usa só código do cliente, SKUs e datas. Sem nome, documento, endereço, UF ou valores. Agregação no SQL Server; dados só em memória, TTL 6 h. Não há meio menos invasivo que produza recomendação **por cliente**. | Atende |
| Balanceamento | Expectativa razoável: um fornecedor B2B usar o histórico de compras do próprio cliente para sugerir produtos é prática comercial esperada. Sem dados sensíveis, sem efeito jurídico, sem restrição de acesso a produtos ou preço diferenciado, sem compartilhamento com terceiros, sem contato automático. O titular é, na maioria, PJ. | Atende |
| Salvaguardas | Requisitos LGPD-01 a LGPD-12; transparência pelo aviso de privacidade comercial (§6, R-05); possibilidade de oposição (Art. 18, §2º) atendida pelo time comercial. | Exigidas |

### 2.2 Decisão automatizada e perfilamento (Art. 20)

- **Há perfilamento de consumo** (P-062: perfil 365 d, dormência). Isso é reconhecido e controlado.
- **Não há decisão exclusivamente automatizada que afete interesses do titular**: a saída é uma **sugestão interna ao vendedor**, que decide se oferece algo. Não define preço, crédito, limite, prioridade de atendimento, bloqueio ou elegibilidade. O cliente não é informado de "pontuação" nem sofre consequência dela.
- Portanto o direito de revisão do Art. 20 não é acionado nesta fase. A explicabilidade (P-065) já cumpre, de forma voluntária, o dever de transparência sobre critérios.

### 2.3 RIPD/DPIA

**Não exigido nesta fase.** Fundamentos: sem dados sensíveis; sem decisão automatizada com efeito sobre o titular; escala limitada (~3,4 mil clientes, maioria PJ); dados pseudonimizados, em memória, sem compartilhamento externo. O LIA acima fica como registro (Art. 10, §3º; Art. 37).

**Gatilhos que tornam o RIPD obrigatório (reavaliar o parecer):**
1. A pontuação passar a definir preço, desconto, crédito, prioridade de atendimento ou campanha enviada automaticamente ao cliente (fora de escopo hoje).
2. Inclusão de nome, CNPJ/CPF, contato, UF ou geolocalização na feature.
3. Exportação/compartilhamento das recomendações por cliente com terceiros (CRM externo, ferramenta de disparo, LLM externo).
4. Fases 3 e 5 (churn/priorização de clientes) se seu resultado limitar o atendimento ao cliente.

---

## 3. Minimização e anti-overfetching

### 3.1 Leitura do banco (repositório)

| Pode selecionar | Não pode selecionar |
| :--- | :--- |
| `Externo01.Vendas`: `[Pedido]`, `[Cod Cliente]`, `[Cod Produto]`, `[Data]` (ou data do pedido), `[Operação]`/`[Qtd Venda]` **somente em `WHERE`/`HAVING`** | `[UF]`, `[Valor Venda]`, `[Cod Promocao]` e qualquer coluna de nome, documento, endereço, contato, vendedor |
| `Externo01.Produto`: `[Codigo]`, `[Descricao]`, `[Fornecedor]`, `[Estoque]`, `[Pc.Ultimo Custo]`, `[Pc.Venda]` | `[EAN]` e `[Tipo]` só se o contrato justificar |

A função genérica `fetch_sales_from_database` **seleciona `UF` e `Valor Venda`** e por isso **não pode** ser reutilizada pelo módulo `analytics` para F4.

### 3.2 Respostas da API

| Endpoint | Pode devolver | Não pode devolver |
| :--- | :--- | :--- |
| Por produto | Campos do P-061.2 e sinalizações (`semEstoque`, `margemNaoPositiva`) | Qualquer `customerCode`, lista de clientes que compraram A/B, números de `Pedido`, contagens por cliente |
| Por cliente | `customerCode` **somente ecoado** em `meta` (ou omitido) e os campos do P-064.4 (SKU, descrição, fornecedor, antecedente principal, `lift`, `confianca`, `margemUnitaria`, `custoEstimado`, `pontuacao`, `motivo`, `diasDesdeUltimaCompra`, `qtdAntecedentesRelacionados`, explicação) | Perfil completo do cliente (lista de todos os SKUs comprados), datas absolutas de cada compra, `Pedido`, valores/quantidades compradas pelo cliente, faturamento do cliente, `UF`, nome, documento |
| `/analytics/health` | Status do cache, `dataReferencia`, contagens agregadas | Qualquer `customerCode`, chaves do cache por cliente, nº de clientes cacheados por código |
| Erros (`XSL-*`, 5xx) | Código interno, mensagem fixa, **nome** do campo inválido | Valor recebido do `customerCode`, SQL, stacktrace, mensagem do driver ODBC, nomes de colunas/servidor |

### 3.3 Logs

| Permitido | Proibido |
| :--- | :--- |
| Contagens agregadas (cestas válidas, cestas descartadas, regras, itens triviais, SKUs), tempos de carga/mineração, status do cache, código `XSL` e HTTP do erro, nome da operação | `customerCode` em logs de domínio, serviço, repositório ou handler de exceção; DataFrames; listas de recomendações; perfis; payloads de request/response; `str(exception)` do pyodbc sem sanitização; SQL com parâmetros interpolados |

---

## 4. Parecer sobre a premissa A-11 (`Cod Cliente` no path)

**Fatos:**
- O Uvicorn (`Dockerfile`, CMD padrão) grava log de acesso com **path e query string**.
- O Cloud Run grava `httpRequest.requestUrl` **completo (path e query string)** no Cloud Logging, independentemente da aplicação.
- Logo, **mover o código para a query string não traz ganho nenhum**: ele aparece nos mesmos logs.
- `POST` com corpo esconderia o código dos logs, mas fere a semântica REST (leitura idempotente), impede cache HTTP, complica paginação e o contrato do módulo. É desproporcional ao risco.

**Avaliação de risco:** o `Cod Cliente` é um identificador interno **pseudonimizado**, sem significado fora do ERP. Quem acessa os logs do projeto GCP (equipe técnica com IAM) não ganha capacidade de reidentificação que não teria no ERP. O log de acesso **não revela o conteúdo da recomendação nem o perfil**, só que "alguém consultou o cliente X em tal horário", que é também um registro de auditoria útil (Art. 37). O risco é **baixo** e aceitável.

**Recomendação (decisão):** **manter `GET /analytics/cross-sell/customer/{customerCode}` com o código no path.** Rejeitar query string (sem benefício) e POST (desproporcional). Condições: LGPD-06 (controles sobre os logs de acesso) e LGPD-07 (nenhuma outra informação de cliente na URL). Atualizar A-11 como **resolvida** e P-070.3 com esta decisão.

---

## 5. Requisitos obrigatórios (MUST)

> Verificáveis em código/configuração. Na Etapa 4, a ausência de qualquer item é **veto**.

| ID | Requisito | Como verificar (Etapa 4) |
| :--- | :--- | :--- |
| **LGPD-01** | **Projeção mínima de colunas no repositório.** As queries do módulo `analytics` selecionam apenas as colunas da coluna "Pode selecionar" de §3.1; sem `SELECT *`; sem `UF`, `Valor Venda`, `Cod Promocao`, `EAN` e colunas de identificação. Não reutilizar `fetch_sales_from_database`. | Leitura das strings SQL do repositório; teste que verifica a lista exata de colunas devolvida pelo repositório (conexão mockada). |
| **LGPD-02** | **Parâmetros vinculados.** `customerCode` e `sku` validados como inteiros positivos por schema (Pydantic/`Path(gt=0)`) e nunca interpolados em SQL (f-string/`format`/concatenação). Filtragem por cliente ocorre preferencialmente em memória sobre a base cacheada. | Grep por f-strings com variáveis de request em SQL; teste do XSL-004 com `customerCode = "1 OR 1=1"` e negativo. |
| **LGPD-03** | **Contrato sem overfetching.** Schemas de resposta (Pydantic `response_model`) listam explicitamente os campos de §3.2; nenhum campo de perfil completo, `Pedido`, valores comprados, datas absolutas de compra, `UF` ou identificação. O modo por produto não contém nenhum `customerCode`. | Teste de contrato que compara o conjunto de chaves da resposta com uma lista permitida (allowlist) e falha em chave extra. |
| **LGPD-04** | **Logs sem dados de cliente.** Nenhuma chamada de `logger` no módulo recebe `customerCode`, DataFrame, lista de recomendações, perfil ou payload. Só contagens e tempos. | Grep em `src/modules/analytics/**` por `logger.` com variáveis não escalares; teste com `caplog` em massa sintética afirmando que o código do cliente de teste e os SKUs recomendados não aparecem em nenhum registro (CA-22). |
| **LGPD-05** | **Erros sanitizados.** Handler global devolve código `XSL`, mensagem fixa e nomes de campos. Não ecoa o valor de `customerCode` (nem no `XSL-002`, nem no `XSL-004`), SQL, stacktrace ou mensagem do driver. Erros 5xx de banco retornam mensagem genérica e o log registra só o tipo da exceção, sem `str(e)` do pyodbc. | Testes de XSL-002/XSL-004 verificando ausência do valor enviado no corpo; teste de falha de conexão verificando corpo genérico. |
| **LGPD-06** | **Controle dos logs de acesso (decisão A-11).** (a) Acesso ao Cloud Logging restrito por IAM a quem já opera o sistema; (b) retenção dos logs de requisição limitada ao padrão de 30 dias do bucket `_Default` (sem sink para BigQuery/GCS de longo prazo contendo essas rotas); (c) nenhum log de aplicação adicional registra a URL da rota de cliente. | Revisão pelo `devops`/`reviewer` da configuração do projeto GCP e do código: sem middleware de log de request que repita a URL. |
| **LGPD-07** | **URL com o mínimo.** A rota por cliente contém apenas `customerCode` no path e `limit`/`offset` na query. Proibido incluir nome, CNPJ/CPF ou qualquer outro identificador na URL ou em headers customizados. | Leitura do router e do service Angular. |
| **LGPD-08** | **Dados só em memória, com limite.** Base, regras e recomendações por cliente ficam só no cache em memória do processo (P-070.4); sem gravação em disco, `/tmp`, pickle, Redis ou serviço externo. Cache por cliente invalidado junto com a base e com tamanho máximo (LRU ou equivalente) para não acumular perfis indefinidamente. | Leitura do serviço de cache; teste de invalidação conjunta (P-068.5). |
| **LGPD-09** | **Frontend sem persistência de cliente.** O Angular não grava `customerCode`, recomendações ou "clientes recentes" em `localStorage`, `sessionStorage`, IndexedDB ou cookies; não envia a URL da tela de cliente a ferramentas de analytics/telemetria de terceiros. | Grep no frontend por `localStorage`/`sessionStorage`/`indexedDB` nos arquivos da feature; revisão de scripts de terceiros. |
| **LGPD-10** | **Autenticação obrigatória nas rotas.** Todas as rotas `/analytics/*` (exceto, se o Arquiteto decidir, `/analytics/health`, que não tem dado de cliente) passam pelo `HTTPBasicAuthASGIMiddleware` em produção. Nenhuma rota do módulo é registrada fora do app protegido. | Teste com `ENVIRONMENT=production` sem credencial em `/analytics/cross-sell/customer/{id}` esperando 401. |
| **LGPD-11** | **Backtest sem dados individuais no PR.** O relatório de P-071 publica só métricas agregadas (hit rate@5, cobertura, tamanhos de amostra, excluídos). Proibido listar `customerCode`, recomendações por cliente ou acertos por cliente no PR, em artefatos versionados ou em logs de CI. Massas de teste versionadas são **sintéticas**, nunca extraídas da produção. | Revisão do PR e de `tests/analytics/fixtures`; grep por códigos de clientes reais. |
| **LGPD-12** | **Uso somente interno.** Sem endpoint de exportação (CSV/Excel) por cliente e sem integração com envio automático de oferta nesta fase. Qualquer inclusão futura reabre este parecer (gatilhos de §2.3). | Leitura do router e do Design Plan. |

---

## 6. Riscos residuais

| # | Risco | Nível | Tratamento |
| :--- | :--- | :--- | :--- |
| R-01 | `Cod Cliente` no log de acesso do Cloud Run/Uvicorn (A-11) | Baixo | Aceito com LGPD-06/LGPD-07. |
| R-02 | **Pré-existente, fora do escopo F4:** `get_db_connection_string` usa `Encrypt=no;TrustServerCertificate=yes`; o tráfego Cloud Run → SQL Server, que carrega `Cod Cliente` e histórico, pode trafegar sem criptografia (Art. 46). | **Médio** | Recomendo abrir dívida técnica para `security`/`devops`: habilitar `Encrypt=yes` com certificado válido, ou garantir túnel privado (VPN/Interconnect). Não bloqueia F4, mas deve ser registrado no `STATE.md`. |
| R-03 | **Pré-existente:** autenticação HTTP Basic com credencial única compartilhada; não há rastreabilidade de **qual** usuário consultou um cliente (Art. 37, responsabilização). | Baixo/Médio | Aceito nesta fase (uso interno restrito). Reavaliar quando houver mais usuários ou as Fases 3 e 5. |
| R-04 | **Pré-existente:** `test_db_connection` devolve `str(e)` do driver na resposta, o que pode expor host/usuário do banco. | Baixo | Não usar no módulo `analytics` (LGPD-05). Dívida técnica para o `security`. |
| R-05 | Transparência: o aviso de privacidade aos clientes pode não mencionar uso do histórico para recomendações comerciais. | Baixo | Ação jurídico-administrativa (fora do código): incluir no aviso de privacidade comercial a finalidade "recomendação de produtos com base no histórico de compras" e canal de oposição. |
| R-06 | Inferência sobre cliente a partir de regras com base pequena (backtest/recortes). | Muito baixo | Mitigado por `MIN_PAIR_ORDERS = 10` e `MIN_VALID_BASKETS`; regras não expõem clientes. |
| R-07 | Ampliação de finalidade nas Fases 2 a 6 (churn, priorização) reutilizando o perfil de F4. | A avaliar | O `privacy_officer` revisa cada fase por cliente (plano §2.8); gatilhos de RIPD em §2.3. |

---

## 7. Encaminhamentos

- **Analista:** marcar A-11 como resolvida (§4) e ajustar P-070.3; atualizar o enquadramento de `Cod Cliente` para "pseudonimizado, tratado como pessoal pelo pior caso".
- **Arquiteto:** refletir LGPD-01, 02, 03, 05, 07, 10 e 12 no contrato `api_contracts/` e no checklist de `tasks/analytics-cross-sell.md`.
- **Designer:** refletir LGPD-09 e LGPD-12 no Design Plan (sem "clientes recentes" persistidos, sem exportação).
- **Tester:** incluir os testes indicados na coluna de verificação (allowlist de campos, `caplog`, erros sem eco, 401 em produção).
- **Orquestrador:** registrar R-02, R-03 e R-04 como dívida técnica no `STATE.md`.
- **Etapa 4:** `privacy_officer` audita LGPD-01 a LGPD-12 com poder de veto.
