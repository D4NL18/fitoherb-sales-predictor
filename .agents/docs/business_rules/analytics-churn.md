# Regras de Negócio: Analytics Comercial — F3 Churn de Clientes com Score de Prioridade

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-churn.md`  
> **Responsável:** Analista (`business-rules-expert`)  
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`  

| Campo | Valor |
| :--- | :--- |
| **Feature** | Churn de Clientes com Score de Prioridade de Retenção |
| **Módulo** | `analytics` (Contexto delimitado Analytics Comercial) |
| **Branch** | `feature/analytics-churn` |
| **Faixa de Regras** | `P-117` a `P-127` |
| **Códigos de Erro** | `CHU-001`, `CHU-002`, `CHU-003` (além dos comuns `ANL-001`, `ANL-002`) |
| **Origem** | Plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§7) e decisões D1, D3, D4 |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado |

---

## 1. Contexto e Objetivo

- **User Story Relacionada:** US-F3 — *Como gestor comercial / coordenador de televendas da Fitoherb, quero visualizar clientes em risco de churn priorizados por uma métrica unificada de urgência temporal e valor financeiro médio, para atuar proativamente na retenção daqueles cujo impacto na receita da distribuidora é mais crítico.*
- **Objetivo da Feature:** Substituir relatórios brutos ou regras ingênuas de "clientes sem compras há 60 dias" por um sistema inteligente de priorização que:
  1. Identifica a data da última compra de VENDA legítima (D1, D4).
  2. Respeita a cadência natural de compra de cada cliente via mediana histórica de intervalo entre pedidos (evitando falsos alarmes em clientes de compra bimestral/trimestral).
  3. Pondera o tempo sem comprar pelo faturamento médio mensal líquido de devoluções (D4), gerando o **Score de Prioridade de Retenção (em R$)**.
  4. Isola clientes inativos de longa data (> 180 dias) em fila especializada de reativação comercial.
  5. Fornece explicabilidade completa do score e produtos perdidos (produtos de maior relevância histórica que deixaram de ser comprados).
- **Atores Envolvidos:** Gestor Comercial / Time de Vendas (consulta e exportação operacional), Sistema ERP SQL Server (somente leitura de vendas e produtos).
- **Fora do escopo:** Disparo automático de e-mails/WhatsApp a clientes, alteração de dados cadastrais no ERP, deduplicação de filiais/grupos econômicos (D3: 1 cliente = 1 código).

---

## 2. Catálogo de Constantes do Domínio

> [!IMPORTANT]
> Todos os parâmetros numéricos abaixo DEVEM existir como constantes nomeadas estritas no topo de `src/modules/analytics/domain/churn.py` (proibição de números mágicos).

| Constante | Tipo | Valor | Regra | Significado de Negócio |
| :--- | :--- | :--- | :--- | :--- |
| `SALE_OPERATION` | `str` | `'VENDA'` | P-117 | Operação que qualifica compra e renova recência |
| `RETURN_OPERATION_PATTERN` | `str` | `'DEVOLU%'` | P-117, P-121 | Padrão SQL para filtrar devoluções a abater |
| `CHURN_BASE_DAYS` | `int` | `60` | P-118, P-119 | Limiar mínimo de dias sem comprar para risco base (D1) |
| `GAP_MULTIPLIER` | `float` | `1.5` | P-119 | Multiplicador sobre o gap típico de compras |
| `MIN_ORDERS_FOR_CADENCE` | `int` | `3` | P-119, P-122 | Pedidos mínimos para estimar cadência própria |
| `FATOR_TEMPO_MAX` | `float` | `2.0` | P-120 | Teto máximo de saturação da urgência temporal |
| `STATUS_ALERT_THRESHOLD` | `float` | `0.5` | P-124 | Limiar inferior de fatorTempo para status ALERTA |
| `STATUS_RISK_THRESHOLD` | `float` | `1.0` | P-124 | Limiar inferior de fatorTempo para status EM_RISCO |
| `DIAS_INATIVO_ANTIGO` | `int` | `180` | P-125 | Limiar de dias sem comprar para segregar inativos |
| `REVENUE_WINDOW_MONTHS` | `int` | `12` | P-121 | Janela em meses completos para média de faturamento |
| `MIN_ACTIVE_MONTHS` | `int` | `3` | P-121, P-122 | Divisor mínimo de meses para cálculo do faturamento médio |
| `LOST_PRODUCTS_LIMIT` | `int` | `5` | P-126 | Quantidade de SKUs principais exibidos como perdidos |
| `DEFAULT_PAGE_LIMIT` | `int` | `50` | P-123 | Tamanho padrão de página da listagem |
| `MAX_PAGE_LIMIT` | `int` | `200` | P-123 | Tamanho máximo permitido de página |

---

## 3. Catálogo de Regras de Negócio (P-117 a P-127)

### `P-117`: Grão de Dados de Pedidos e Exclusividade de Venda na Recência
- **Declaração Mandatória:** O cálculo da data do último pedido e dos intervalos entre transações DEVE considerar estritamente registros de `Externo01.Vendas` cuja `[Operação] = SALE_OPERATION` (`'VENDA'`).
- **Sub-regras:**
  - **P-117.1 (Abatimento sem renovação de recência - D4):** Linhas de devolução (`[Operação] LIKE 'DEVOLU%'`) NUNCA constituem um pedido de compra e NUNCA atualizam a data do último pedido do cliente.
  - **P-117.2 (Agrupamento no SQL - D3):** Cada cliente é identificado única e exclusivamente pelo seu `[Cod Cliente]`. Não há consolidação por CNPJ raiz, razão social ou filial.
  - **P-117.3 (Agregação em banco):** A agregação dos pedidos ocorre no SQL Server agrupada por `[Cod Cliente]` e `[Data]`, retornando `customer_orders` sem transferir detalhes de itens para a memória do Python.
- **Condições de Ativação:** Carga e processamento da base analítica de churn.
- **Resultado Esperado:** Série temporal ordenada de datas de compra para cada cliente.

---

### `P-118`: Cálculo da Recência (`diasSemComprar`)
- **Declaração Mandatória:** A recência do cliente DEVE ser calculada pela diferença em dias corridos entre a `dataReferencia` analítica e a data do último pedido de `VENDA` realizado pelo cliente:
  $$\text{diasSemComprar} = \text{dataReferencia} - \text{dataUltimoPedido}$$
- **Sub-regras:**
  - **P-118.1 (Data de Referência):** Em ambiente produtivo, `dataReferencia` é a data corrente da execução da carga analítica. Em ambiente de teste/backtest, é a data de corte informada (ex.: 60 dias atrás).
  - **P-118.2 (Invariante Não-Negativo):** `diasSemComprar` DEVE ser sempre $\ge 0$. Caso o cliente tenha realizado pedido na data de referência, `diasSemComprar` é 0.

---

### `P-119`: Intervalo Típico e Referência Individual de Cadência
- **Declaração Mandatória:** O sistema DEVE calcular os `diasReferencia` de cada cliente ajustando a régua de 60 dias (D1) ao padrão natural de recompra do cliente.
- **Fórmulas e Sub-regras:**
  - **P-119.1 (Gap Típico):** Para clientes com número de pedidos $N \ge \text{MIN_ORDERS_FOR_CADENCE}$ (3 pedidos), o `gapTipico` é a **mediana** das diferenças de dias entre pedidos consecutivos de `VENDA`.
  - **P-119.2 (Régua de Referência):**
    $$\text{diasReferencia} = \max(\text{CHURN_BASE_DAYS}, \text{GAP_MULTIPLIER} \times \text{gapTipico})$$
    Com $\text{CHURN_BASE_DAYS} = 60$ e $\text{GAP_MULTIPLIER} = 1.5$.
  - **P-119.3 (Cliente com Poucos Pedidos):** Caso o cliente tenha realizado menos de 3 pedidos no histórico, não há base para estimar cadência; nestes casos, $\text{gapTipico} = \text{None}$ e $\text{diasReferencia} = \text{CHURN_BASE_DAYS}$ ($60$ dias).
  - **P-119.4 (Proteção contra Falsos Positivos em Clientes Periódicos):** Um cliente que habitualmente compra a cada 60 dias ($\text{gapTipico} = 60$) terá $\text{diasReferencia} = \max(60, 1.5 \times 60) = 90$ dias. Aos 70 dias parado, ele NÃO será classificado como `EM_RISCO`.

---

### `P-120`: Fator de Urgência Temporal (`fatorTempo`)
- **Declaração Mandatória:** O componente temporal da priorização DEVE ser normalizado pelo indicador adimensional `fatorTempo`:
  $$\text{fatorTempo} = \min\left( \frac{\text{diasSemComprar}}{\text{diasReferencia}}, \text{FATOR_TEMPO_MAX} \right)$$
- **Sub-regras:**
  - **P-120.1 (Fronteira Crítica 1.0):** No exato momento em que `diasSemComprar == diasReferencia` (60 dias para clientes padrão), `fatorTempo == 1.0`.
  - **P-120.2 (Teto de Saturação - 2.0):** O `fatorTempo` cresce linearmente até $\text{FATOR_TEMPO_MAX} = 2.0$ (aproximadamente 120 dias para cliente padrão). Acima de 2.0, o crescimento é truncado, refletindo que a urgência de contato imediato satura após o dobro do ciclo esperado de recompra.

---

### `P-121`: Faturamento Mensal Líquido e Média de Receita
- **Declaração Mandatória:** O faturamento mensal do cliente DEVE ser calculado com abatimento estrito de devoluções (D4):
  $$\text{faturamentoLiquidoMes} = \sum \text{ValorVenda}_{\text{VENDA}} + \sum \text{ValorVenda}_{\text{DEVOLUCAO}}$$
  *(onde $\text{ValorVenda}_{\text{DEVOLUCAO}} < 0$).*
- **Sub-regras:**
  - **P-121.1 (Exclusão do Mês Corrente Parcial):** A janela de avaliação de faturamento compreende os últimos $\text{REVENUE_WINDOW_MONTHS} = 12$ meses completos de histórico, excluindo o mês corrente em aberto.
  - **P-121.2 (Meses Ativos na Janela):** `mesesAtivos` é o número de meses desde o primeiro pedido de `VENDA` do cliente até o fim da janela de 12 meses, delimitado por:
    $$\text{divisorMeses} = \max(\text{MIN_ACTIVE_MONTHS}, \min(\text{mesesAtivos}, \text{REVENUE_WINDOW_MONTHS}))$$
    onde $\text{MIN_ACTIVE_MONTHS} = 3$ e $\text{REVENUE_WINDOW_MONTHS} = 12$.
  - **P-121.3 (Faturamento Médio Mensal):**
    $$\text{faturamentoMedioMensal} = \frac{\sum_{m \in \text{Janela12m}} \text{faturamentoLiquidoMes}_m}{\text{divisorMeses}}$$
  - **P-121.4 (Piso Não-Negativo):** Se por excesso de devoluções a soma líquida for negativa, $\text{faturamentoMedioMensal}$ é ajustado ao piso de `0.00`.

---

### `P-122`: Tratamento de Histórico Curto
- **Declaração Mandatória:** Clientes recém-cadastrados ou com atividade esparsa (menos de $\text{MIN_ORDERS_FOR_CADENCE} = 3$ pedidos no histórico completo) DEVEM ser identificados com a flag booleana `historicoCurto = True`.
- **Sub-regras:**
  - **P-122.1 (Amortecimento de Pedido Único Alto):** Para clientes com `historicoCurto = True`, o divisor de meses é forçado ao mínimo de 3 meses ($\text{MIN_ACTIVE_MONTHS} = 3$), impedindo que uma única compra pontual de alto valor gere um score irreal de retenção recorrente.
  - **P-122.2 (Selo na UI):** Clientes com `historicoCurto = True` exibem selo visual explicativo no frontend ("Histórico curto: < 3 pedidos").

---

### `P-123`: Score de Prioridade de Retenção
- **Declaração Mandatória:** O sistema DEVE consolidar a priorização comercial em um único indicador monetário:
  $$\text{scorePrioridade} = \text{faturamentoMedioMensal} \times \text{fatorTempo}$$
- **Sub-regras:**
  - **P-123.1 (Unidade de Medida):** O score é expresso em Reais (R$) e representa a "receita média mensal sob risco ponderada pela urgência".
  - **P-123.2 (Ordenação Padrão):** As listagens de clientes em risco e em alerta DEVEM ser ordenadas de forma decrescente por `scorePrioridade` (`scorePrioridade DESC`).
  - **P-123.3 (Prevalência de Valor):** Um cliente de R$ 50.000/mês parado há 70 dias ($\text{fatorTempo} = 1.17$, $\text{score} \approx \text{R\$} 58.500$) terá prioridade estritamente superior a um cliente de R$ 2.000/mês parado há 120 dias ($\text{fatorTempo} = 2.0$, $\text{score} = \text{R\$} 4.000$).

---

### `P-124`: Classificação de Status da Carteira
- **Declaração Mandatória:** Cada cliente ativo na base (com $\text{diasSemComprar} \le \text{DIAS_INATIVO_ANTIGO}$) DEVE receber um dos seguintes três status operacionais:
  1. `SAUDAVEL`: $\text{fatorTempo} < \text{STATUS_ALERT_THRESHOLD}$ ($0.5$). Cliente comprando dentro do ritmo habitual.
  2. `ALERTA`: $\text{STATUS_ALERT_THRESHOLD} \le \text{fatorTempo} < \text{STATUS_RISK_THRESHOLD}$ ($0.5 \le \text{fatorTempo} < 1.0$). Cliente ultrapassou a metade da sua cadência de compra esperada.
  3. `EM_RISCO`: $\text{fatorTempo} \ge \text{STATUS_RISK_THRESHOLD}$ ($1.0$) e $\text{diasSemComprar} \le \text{DIAS_INATIVO_ANTIGO}$ ($180$). Cliente sem compras acima do limiar crítico (D1).

---

### `P-125`: Segregação e Tratamento de Inativos Antigos
- **Declaração Mandatória:** Clientes cuja recência ultrapasse $\text{DIAS_INATIVO_ANTIGO} = 180$ dias DEVEM ser segregados com o status `INATIVO_RECUPERACAO`.
- **Sub-regras:**
  - **P-125.1 (Exclusão da Fila Operacional Ativa):** Clientes inativos antigos NÃO aparecem na listagem padrão de risco `GET /analytics/churn/customers?status=EM_RISCO` para evitar poluição da rotina de televendas ativo com contas frias.
  - **P-125.2 (Fila Especializada de Reativação):** Clientes inativos são disponibilizados na rota dedicada `GET /analytics/churn/inactive`, ordenados decrescentemente por `faturamentoMedioMensal`.
  - **P-125.3 (Cálculo de Faturamento Histórico):** O faturamento médio desses clientes é calculado sobre a janela ativa em que compravam (meses ativos históricos), permitindo priorizar na reativação aqueles que eram grandes compradores.

---

### `P-126`: Explicabilidade de Churn e Identificação de Produtos Perdidos
- **Declaração Mandatória:** A rota de detalhe `GET /analytics/churn/customers/{customerCode}` DEVE devolver diagnósticos explicativos para a perda de tração do cliente:
  - **P-126.1 (Decomposição do Score):** Detalhamento dos fatores: `diasSemComprar`, `gapTipico`, `diasReferencia`, `fatorTempo`, `faturamentoMedioMensal` e `scorePrioridade`.
  - **P-126.2 (Tendência Recente de Faturamento):** Comparação percentual entre a soma líquida dos últimos 3 meses contra os 3 meses anteriores ($\Delta\%$).
  - **P-126.3 (Produtos Perdidos):** Lista dos até $\text{LOST_PRODUCTS_LIMIT} = 5$ SKUs com maior faturamento histórico adquirido por esse cliente nos últimos 12 meses que NÃO foram incluídos em nenhum pedido nos últimos 60 dias.

---

### `P-127`: Critérios de Aceite Quantitativo e Validação por Backtest
- **Declaração Mandatória:** A eficácia do modelo de retenção DEVE ser comprovada por rotina de validação histórica (backtest temporal):
  - **P-127.1 (Backtest em Data de Corte):** Simulação com data de corte 60 dias atrás da base histórica.
  - **P-127.2 (Garantia de Captura de Receita):** A receita total em risco retida nos 100 primeiros clientes ordenados pelo `scorePrioridade` DEVE ser superior à receita obtida pela ordenação puramente por dias parados (`diasSemComprar DESC`).
  - **P-127.3 (Taxa de Acerto de Não-Retorno):** Ao menos 70% dos clientes classificados como `EM_RISCO` na data de corte não devem ter realizado nova compra nos 60 dias subsequentes sem intervenção.

---

## 4. Enquadramento LGPD & Privacidade (Art. 7º e 11)

> [!NOTE]
> A Fitoherb opera primariamente como distribuidora B2B. No entanto, clientes com `Cod Cliente` podem representar pequenos comércios ou empresários individuais (MEI/EI) cujos cadastros tangenciam pessoas físicas.

| Dado / Atributo | Classificação LGPD | Base Legal Aplicada | Medida de Minimização e Proteção |
| :--- | :--- | :--- | :--- |
| `customerCode` (`int`) | Identificador Comercial | Legítimo Interesse (Art. 7º, IX) | Único identificador trafegado. **Zero exposição** de Nome, Razão Social, CNPJ, CPF, E-mail ou Telefone na API. |
| Métricas Financeiras (`scorePrioridade`, `faturamentoMedioMensal`) | Dado Comercial Agregado | Legítimo Interesse (Art. 7º, IX) | Informações estritamente agregadas para gestão comercial interna. |
| Logs de Execução | Governança Técnica | Obrigação Legal (Marco Civil / Art. 7º, II) | **PROIBIDO** registrar arrays de clientes, payloads de requisição ou códigos em logs estruturados (apenas contagens agregadas). |

---

## 5. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP | Código Interno |
| :--- | :--- | :--- | :--- | :--- |
| **C-01** | Cliente regular com 10 pedidos, intervalo médio 15 dias, parado há 70 dias | Classificado como `EM_RISCO`, `fatorTempo = 1.17`, score proporcional | `200 OK` | - |
| **C-02** | Cliente trimestral com gap típico de 60 dias, parado há 70 dias | `diasReferencia = 90`, `fatorTempo = 0.78`, classificado como `ALERTA` (não `EM_RISCO`) | `200 OK` | - |
| **C-03** | Cliente grande (50k/mês) parado há 70d vs Cliente pequeno (2k/mês) parado há 120d | Cliente grande ocupa posição superior no ranking decrescente de score | `200 OK` | - |
| **C-04** | Cliente com 1 pedido isolado de alto valor há 65 dias | Flag `historicoCurto = True`, divisor amortecido para 3 meses | `200 OK` | - |
| **C-05** | Devolução lançada no dia anterior à consulta | Abate faturamento líquido, mas data do último pedido permanece inalterada | `200 OK` | - |
| **C-06** | Cliente com mais de 180 dias sem compras | Aparece em `GET /analytics/churn/inactive`, omitido de `/customers?status=EM_RISCO` | `200 OK` | - |
| **C-07** | Consulta a cliente inexistente no catálogo de vendas | Retorna erro semântico de cliente não encontrado | `404 Not Found` | `CHU-001` |
| **C-08** | Base de vendas vazia ou sem pedidos válidos | Retorna erro semântico de base insuficiente | `422 Unprocessable` | `CHU-002` |
| **C-09** | Parâmetro inválido (`limit=0` ou `status=INVALIDO`) | Rejeição imediata com lista de campos incorretos | `400 Bad Request` | `CHU-003` |

---

## 6. Critérios de Aceitação (Definition of Done)
- [x] Regras P-117 a P-127 formalizadas com fórmulas inequívocas e constantes documentadas.
- [x] Decisões D1 (60 dias), D3 (1 cliente = 1 código) e D4 (devolução abate faturamento sem renovar recência) incorporadas.
- [x] Casos de teste de TDD mapeados diretamente a cada invariante de negócio.
- [x] Diretrizes de minimização LGPD formalizadas.
