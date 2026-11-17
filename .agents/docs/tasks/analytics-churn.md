# Feature: Churn de Clientes com Score de Prioridade (FASE F3)

Centraliza as especificações, etapas de execução e checklist atômico para a entrega da feature Churn de Clientes.

---

## 1. Dúvidas Resolvidas e Decisões de Negócio
- **D1 (Limiar de Risco):** Cliente sem comprar há $\ge 60$ dias a partir de `VENDA` é considerado em risco.
  - *Decisão:* Priorização unificada combinando tempo sem comprar e faturamento médio mensal.
- **D3 (Identificação do Cliente):** Um cliente = um único `Cod Cliente`.
  - *Decisão:* Sem agrupamento cadastral por filial/matriz.
- **D4 (Devoluções):** Devoluções abatem quantidade e faturamento líquido.
  - *Decisão:* Linhas de devolução NUNCA renovam recência de compra nem criam novas transações.
- **D-CADÊNCIA (Referência Individual):** Clientes com compras regulares espaçadas (ex.: trimestrais).
  - *Decisão:* `diasReferencia = max(60, 1.5 * gapTipico)`. Clientes trimestrais com 70 dias sem comprar não entram em `EM_RISCO`.
- **D-INATIVOS (Clientes Antigos):** Clientes sem compras há mais de 180 dias.
  - *Decisão:* Segregados em fila própria de reativação (`/analytics/churn/inactive`).

---

## 2. Tarefas e Etapas de Desenvolvimento

### Tarefa 1: Motor de Domínio Matemático do Churn (`domain/churn.py`)
**Descritivo Detalhado:**
Implementação da lógica pura de domínio sem I/O para cálculo de recência, mediana de intervalos (gap típico), fator de tempo com saturação (2.0), faturamento médio mensal com abatimento de devoluções, flag de histórico curto, classificação de status e produtos perdidos.

**Critérios de Aceite (TDD):**
- [ ] Recência calculada estritamente sobre pedidos de `VENDA` (P-117, P-118).
- [ ] Gap típico calculado como mediana de intervalos entre compras para clientes com $\ge 3$ pedidos (P-119).
- [ ] `diasReferencia` respeita o mínimo de 60 e o multiplicador 1.5 sobre a mediana (P-119).
- [ ] `fatorTempo` cresce linearmente e satura estritamente em `FATOR_TEMPO_MAX = 2.0` (P-120).
- [ ] Faturamento mensal líquido desconta devoluções e calcula média com divisor entre 3 e 12 meses (P-121).
- [ ] `historicoCurto = True` para clientes com $< 3$ pedidos com divisor mínimo de 3 meses (P-122).
- [ ] `scorePrioridade` calculado em R$ como `faturamentoMedioMensal * fatorTempo` (P-123).
- [ ] Cliente grande (50k/mês) parado 70d tem score superior a cliente pequeno (2k/mês) parado 120d (P-123).
- [ ] Status classificados em `SAUDAVEL`, `ALERTA` e `EM_RISCO` conforme limiares 0.5 e 1.0 (P-124).
- [ ] Clientes $> 180$ dias sem comprar segregados como `INATIVO_RECUPERACAO` (P-125).

---

### Tarefa 2: Agregação SQL Server e Repositório (`sales_repository.py`)
**Descritivo Detalhado:**
Extensão do repositório analítico adicionando consultas somente leitura agregadas no SQL Server para extração dos pedidos dos clientes (`customer_orders`), faturamento líquido mensal (`customer_monthly_revenue`) e produtos mais comprados no passado, respeitando a regra de somente leitura e o abatimento `[Operação] LIKE 'DEVOLU%'`.

**Critérios de Aceite:**
- [ ] Query agregada `customer_orders` agrupa `Cod Cliente` e `Data`, filtrando estritamente `[Operação] = 'VENDA'`.
- [ ] Query agregada `customer_monthly_revenue` calcula a soma de `Valor Venda` agrupada por `Cod Cliente`, ano e mês, incluindo `VENDA` e subtraindo devoluções.
- [ ] Validador `is_readonly_query` protege todas as novas consultas.
- [ ] Todas as chamadas usam parâmetros vinculados para a data de corte.

---

### Tarefa 3: Serviços, Cache e Orquestração (`analytics_service.py` e `analytics_cache.py`)
**Descritivo Detalhado:**
Orquestração da carga em cache dos agregados de clientes, cálculo dos scores e instanciação dos modelos de resposta com paginação e ordenação por score.

**Critérios de Aceite:**
- [ ] Carga cacheada de clientes integrada ao ciclo de vida de snapshot do módulo.
- [ ] Casos de uso: `get_churn_customers`, `get_customer_churn_detail` e `get_inactive_customers`.
- [ ] Lançamento de `CustomerWithoutHistoryError` (`CHU-001`) quando cliente não possui pedidos de venda.
- [ ] Lançamento de `InsufficientBaseError` (`CHU-002`) quando não houver clientes na base.

---

### Tarefa 4: Schemas Pydantic, Router REST e Handlers de Erro (`api/`)
**Descritivo Detalhado:**
Criação dos contratos Pydantic v2 com envelope `data` e `meta`, endpoints REST com parâmetros validados e registro dos códigos de erro `CHU-XXX` no handler global.

**Critérios de Aceite:**
- [ ] `GET /analytics/churn/customers` com filtro `status=EM_RISCO|ALERTA|SAUDAVEL`, `limit` (1 a 200) e `offset`.
- [ ] `GET /analytics/churn/customers/{customerCode}` devolve decomposição do score e top produtos perdidos.
- [ ] `GET /analytics/churn/inactive` lista inativos antigos ordenados por faturamento histórico.
- [ ] Envelope padronizado `{ "data": ..., "meta": { "timestamp", "limit", "offset", "totalItems", ... } }`.
- [ ] Erros `CHU-001` (404), `CHU-002` (422) e `CHU-003` (400) integrados em `error_handlers.py`.

---

### Tarefa 5: Frontend Angular da Aba Churn (`features/analytics/`)
**Descritivo Detalhado:**
Implementação de página e componentes na casca de `/analytics` com rota filha `/churn`: tabela priorizada com ordenação por score, chips visuais de status, badges de histórico curto, drawer/painel de detalhes do cliente com produtos perdidos, exportação de relatório para CSV e suporte integral aos 8 estados interativos.

**Critérios de Aceite:**
- [ ] Nova aba "Churn de Clientes" no cabeçalho de seções do `analytics-shell`.
- [ ] Tabela com colunas: Código do Cliente, Status, Dias sem Comprar, Cadência Típica, Faturamento Médio Mensal e Score de Prioridade.
- [ ] Drawer lateral responsivo exibindo histórico mensal e produtos perdidos ao clicar numa linha.
- [ ] Botão de exportação CSV para prospecção da equipe de vendas.
- [ ] Estados de carregamento (skeleton), vazio, erro e pronto totalmente tratados.

---

### Tarefa 6: Quality Gate 360, Auto-Healer e Backtest
**Descritivo Detalhado:**
Execução rigorosa dos testes automatizados com pytest, validação quantitativa da superioridade do score contra ordenação por dias simples, conferência de Clean Code e auditoria LGPD de código.
