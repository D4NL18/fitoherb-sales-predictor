# Tarefas: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/tasks/analytics-elasticidade.md`
> **Responsável:** Analista (Etapa 1) / Arquiteto (Etapa 2) / Tester & Dev (Etapas 3 e 4)
> **Branch:** `feature/analytics-elasticidade`
> **Regras Associadas:** P-095 a P-105 | **Prefixo de Erros:** `ELA-XXX`

---

## 1. Dúvidas Resolvidas (Especificação)

- **Dúvida 1:** Como lidar com devoluções no cálculo do preço médio praticado?
  - **Decisão (D4 / P-095):** Devoluções são abatidas diretamente das quantidades e faturamentos (`VENDA` + `DEVOLUCAO`). Preço médio é calculado como `Valor_Liquido / Qtd_Liquida`. Meses com quantidade líquida <= 0 são descartados da regressão para evitar logaritmo de zero ou negativo.
- **Dúvida 2:** O que fazer quando um cliente tem pouquíssimas compras de um produto específico?
  - **Decisão (P-097):** Aplicar suavização hierárquica (shrinkage) $w = n / (n + 10)$. Com poucas compras ($n < 3$), a elasticidade converge de forma monótona para a do produto, sem inventar comportamentos espúrios.
- **Dúvida 3:** Como proceder com produtos cujo preço nunca mudou no histórico?
  - **Decisão (P-096, P-098):** Quando a dispersão de log-preço for nula ou menor que `1e-4`, a regressão não tem suporte econométrico; adota-se a elasticidade canônica `-1.2` com status de confiança `BAIXA` / `NAO_CONFIAVEL`.
- **Dúvida 4:** Como garantir a privacidade sob a LGPD ao listar clientes?
  - **Decisão (P-104):** Apenas o identificador numérico `customerCode` é exposto na API, consumido pelo front e aceito em filtros. Nenhuma razão social, nome, CPF ou contato é processado ou logado.

---

## 2. Tarefas e Etapas de Desenvolvimento

### Tarefa 1: Modelagem Econométrica e Domínio Puro de Elasticidade
**Descritivo Detalhado:**
Implementar em `src/modules/analytics/domain/elasticity.py` as funções puras de agregação de preços líquidos, decaimento temporal exponencial, regressão linear ponderada log-log, cálculo de $R^2$, erro padrão, shrinkage bayesiano cliente-produto, validação de limites de plausibilidade econômica e simulação de cenários de preço.

**Critérios de Aceite:**
- [ ] Recuperação precisa de elasticidade sintética controlada (-2.0) dentro da tolerância de ±0.15 (P-096).
- [ ] Shrinkage monótono: conforme $n$ cresce, a elasticidade se aproxima da empírica do cliente; com $n$ baixo, se aproxima da do produto (P-097).
- [ ] Rejeição de valores positivos ou implausíveis com fallback para `-1.2` e marcação de baixa confiança (P-098).
- [ ] Preço constante gera fallback para `-1.2` e confiança `BAIXA` (P-096).
- [ ] Devoluções reduzem a quantidade líquida do mês (P-095).
- [ ] Motor de simulação calcula deltas precisos de volume, receita e margem monetária (P-101).

**Checklist Técnico (Arquiteto/Desenvolvedor):**
- [ ] Definir constantes no topo do módulo `domain/elasticity.py`.
- [ ] Implementar `estimate_product_elasticity` com regressão ponderada por pesos exponenciais de tempo.
- [ ] Implementar `estimate_customer_elasticity` com fórmula de shrinkage $w = n / (n + K)$.
- [ ] Implementar `simulate_price_change` com projeção de volume, faturamento e margem.
- [ ] Implementar testes unitários em `tests/analytics/test_elasticity_domain.py`.

---

### Tarefa 2: Agregados de Vendas no Repositório e Cache
**Descritivo Detalhado:**
Disponibilizar no módulo de repositório (`sales_repository.py`) o agregado `price_points` consolidado no grão SKU x Mês e SKU x Cliente x Mês (líquidos de devolução), e orquestrar snapshot e cache em memória com TTL e lock.

**Critérios de Aceite:**
- [ ] SQL do repositório é estritamente somente leitura e passa por `is_readonly_query`.
- [ ] Agregação agrupa no banco e filtra devoluções via `[Operação] LIKE 'DEVOLU%'`.
- [ ] Mês corrente excluído dos agregados mensais.
- [ ] Tratamento de falhas de banco com código `ANL-001` sem expor dados de conexão.

**Checklist Técnico (Arquiteto/Desenvolvedor):**
- [ ] Adicionar método de leitura agregada de séries de preços/devoluções sem quebrar compatibilidade de `fetch_order_baskets`.
- [ ] Integrar dados de preços no snapshot de cache do analytics.
- [ ] Implementar testes de repositório com cursor mockado em `tests/analytics/test_elasticity_repository.py`.

---

### Tarefa 3: Schemas, Endpoints da API REST e Handler de Erros
**Descritivo Detalhado:**
Criar os contratos REST para `GET /analytics/elasticity/product/{sku}`, `GET /analytics/elasticity/product/{sku}/customer/{customerCode}` e `POST /analytics/elasticity/simulate`, mapeando erros com envelope padrão `data`/`meta` e códigos `ELA-001` a `ELA-004`.

**Critérios de Aceite:**
- [ ] Validações de entrada retornam HTTP 400 com `ELA-004` e lista de campos inválidos.
- [ ] Produto inexistente retorna HTTP 404 `ELA-001`.
- [ ] Cliente sem compra do produto retorna HTTP 404 `ELA-002`.
- [ ] Respostas 2xx encapsuladas no envelope padrão `{ data, meta }`.
- [ ] Endpoint de simulação aceita body `{ sku, customerCode?, priceChangePct }`.
- [ ] Paginação de clientes do produto com limites seguros.

**Checklist Técnico (Arquiteto/Desenvolvedor):**
- [ ] Criar dataclasses/Pydantic schemas em `api/schemas.py` ou arquivo de schema específico da feature.
- [ ] Registrar exceções `ElasticityProductNotFoundError`, `ElasticityCustomerWithoutHistoryError`, `ElasticityInsufficientBaseError`, `ElasticityInvalidParametersError` em `domain/exceptions.py`.
- [ ] Registrar códigos `ELA-001` a `ELA-004` no mapa de status de `error_handlers.py`.
- [ ] Adicionar rotas em `api/router.py`.
- [ ] Implementar testes de integração de API em `tests/analytics/test_elasticity_api.py`.

---

### Tarefa 4: Frontend Angular (Aba Elasticidade)
**Descritivo Detalhado:**
Desenvolver a página de elasticidade em `frontend/src/app/features/analytics/pages/elasticity-page/` e componentes auxiliares, adicionando a aba "Elasticidade" na barra de seções e suportando todos os 8 estados interativos com acessibilidade.

**Critérios de Aceite:**
- [ ] Rota `/analytics/elasticity` acessível via link na casca de Analytics.
- [ ] Busca de produtos com autocomplete reativo.
- [ ] Visualização de elasticidade do produto com selo `ELÁSTICO` / `INELÁSTICO` e badge de confiança.
- [ ] Painel do Simulador de Preço com slider interativo de -50% a +100% e cards de impacto em Volume, Receita e Margem.
- [ ] Tabela paginada de clientes do produto com elasticidade individual e status de shrinkage.
- [ ] Tratamento estrito dos 8 estados: initial, loading (skeleton), success, empty, error, disabled, invalid, partial/low-confidence.
- [ ] Zero dependência de bibliotecas pesadas externas; layout SCSS nativo seguindo o Design System.

**Checklist Técnico (Arquiteto/Desenvolvedor):**
- [ ] Adicionar seção `Elasticidade` em `ANALYTICS_SECTIONS` e rota lazy em `analytics.routes.ts`.
- [ ] Criar interfaces e models TypeScript em `frontend/.../models/elasticity.models.ts`.
- [ ] Adicionar métodos no `analytics.service.ts` chamando os endpoints do backend.
- [ ] Implementar componente de página e componentes filhos (simulator, customer-table).
- [ ] Implementar testes de componente Angular.

---

### Tarefa 5: Quality Gate 360, Auditorias e Auto-Healer
**Descritivo Detalhado:**
Executar suite de testes completa da feature, validar Clean Code, ausência de PII em logs e telas (auditoria LGPD), fidelidade ao Design Plan e ausência de regressões nos módulos compartilhados.
