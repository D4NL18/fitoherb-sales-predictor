# Regras de Negócio: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-elasticidade.md`
> **Responsável:** Analista (`business-rules-expert`)
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Elasticidade-preço por produto e cliente, simulação de reajuste de preço e sensibilidade de demanda |
| **Módulo** | `analytics` (contexto delimitado: Analytics Comercial) |
| **Branch** | `feature/analytics-elasticidade` |
| **Faixa de Regras** | P-095 a P-105 |
| **Prefixo de Erros** | `ELA-XXX` |
| **Origem** | Plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§2, §4) e decisões D1–D4 do `STATE.md` |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado |

---

## 1. Contexto e Objetivo

- **User Story Relacionada:** US-F5 — *Como gestor comercial ou de pricing da Fitoherb, quero saber a elasticidade-preço de cada produto e de seus clientes específicos, e simular cenários de reajuste percentual, para tomar decisões de preço que maximizem margem e receita sem perder volume de forma inesperada.*
- **Objetivo da Feature:** responder com rigor estatístico:
  1. **Sensibilidade do Produto:** quanto a demanda do produto varia quando seu preço sofre alteração (`beta` da regressão log-log).
  2. **Sensibilidade do Cliente no Produto:** qual a elasticidade individual do cliente sobre o SKU através de encolhimento bayesiano (*shrinkage*) em direção à média do produto.
  3. **Simulação de Impacto:** projetar instantaneamente a variação esperada em volume (unidades), receita bruta (R$) e margem de contribuição (R$) para um ajuste percentual de preço informado.
- **Atores Envolvidos:** Gestor Comercial, Analista de Pricing, Comprador, Sistema ERP SQL Server (somente leitura).
- **Fora do Escopo:** alteração de preços em lote diretamente no banco do ERP, criação de campanhas automatizadas, previsão de demanda estocástica com fatores climáticos complexos.

---

## 2. Catálogo de Constantes do Domínio

| Constante | Valor | Regra | Significado / Justificativa |
| :--- | :--- | :--- | :--- |
| `DEFAULT_ELASTICITY` | `-1.2` | P-096, P-098 | Elasticidade canônica defensiva B2B quando histórico insuficiente ou anômalo |
| `HALF_LIFE_DAYS` | `100.0` | P-096 | Meia-vida do decaimento temporal exponencial das observações históricas |
| `MIN_OBS_PRODUCT` | `5` | P-096 | Mínimo de pontos mensais válidos do produto para tentar estimação econométrica |
| `MIN_PRICE_DISPERSION_STD` | `1e-4` | P-096 | Desvio padrão mínimo de `ln(Preço)` para garantir que o preço variou historicamente |
| `K_SHRINKAGE` | `10.0` | P-097 | Constante de suavização hierárquica cliente-produto `w = n / (n + K)` |
| `MIN_PLAUSIBLE_BETA` | `-6.0` | P-098 | Limite inferior plausível de elasticidade própria (além disso vira fallback) |
| `MAX_PLAUSIBLE_BETA` | `-0.05` | P-098 | Limite superior plausível (betas >= -0.05 indicam efeito espúrio/Giffen) |
| `MIN_SIMULATION_PRICE_CHANGE` | `-50.0`| P-101 | Limite inferior de simulação percentual (-50%) |
| `MAX_SIMULATION_PRICE_CHANGE` | `100.0`| P-101 | Limite superior de simulação percentual (+100%) |
| `CONFIDENCE_HIGH_R2` | `0.50` | P-099 | R² mínimo para classificação de confiança ALTA |
| `CONFIDENCE_HIGH_MIN_OBS` | `12` | P-099 | Mínimo de observações mensais para confiança ALTA |
| `CONFIDENCE_MEDIUM_R2` | `0.20` | P-099 | R² mínimo para classificação de confiança MEDIA |
| `CONFIDENCE_MEDIUM_MIN_OBS` | `6` | P-099 | Mínimo de observações mensais para confiança MEDIA |
| `INELASTIC_THRESHOLD` | `-1.0` | P-100 | Limiar divisor entre demanda Elástica (< -1.0) e Inelástica (>= -1.0) |

---

## 3. Catálogo de Regras de Negócio (P-095 a P-105)

### `P-095`: Agregado de Preços Líquidos de Devoluções e Expurgos
- **Declaração Mandatória:** O sistema DEVE calcular a série histórica de preços e volumes agregados por produto (e por par produto × cliente) considerando valores **líquidos de devoluções** e expurgando o mês corrente (parcial).
- **Condições de Ativação:** Ao processar os dados para estimativa de elasticidade.
- **Detalhamento:**
  - `Qtd_Liquida = SUM(Qtd_Venda)` onde operação é `VENDA` ou `[Operação] LIKE 'DEVOLU%'` (com devoluções registradas com quantidade negativa).
  - `Valor_Liquido = SUM(Valor_Venda)` líquido correspondente.
  - Se `Qtd_Liquida <= 0`, o mês/período DEVE ser descartado da regressão (para evitar logaritmo de número não-positivo).
  - Preço médio praticado do período: `Preco_Medio = Valor_Liquido / Qtd_Liquida`.
  - Excluir pedidos associados a códigos promocionais declarados (`Cod Promocao > 0`) se informados, para isolar sensibilidade normal a preço de efeito promocional extraordinário.
- **Exceção / Erro:** Se todas as observações resultarem em quantidade líquida <= 0, lançar `ELA-003` (422 - histórico insuficiente).

### `P-096`: Modelo Econométrico Log-Log de Elasticidade do Produto
- **Declaração Mandatória:** O sistema DEVE estimar a elasticidade-preço da demanda pela formulação econométrica Log-Log: `ln(Q) = alpha + beta * ln(P) + epsilon`, onde o coeficiente angular `beta` representa diretamente a elasticidade constante da demanda.
- **Condições de Ativação:** Cálculo de elasticidade de um SKU.
- **Detalhamento:**
  - Aplica pesos amostrais com decaimento exponencial temporal: `peso = 2 ** (-dias_ate_presente / 100.0)`.
  - Exige no mínimo `MIN_OBS_PRODUCT` (5) pontos com preços e quantidades estritamente positivos.
  - Exige dispersão mínima de preços `std(ln(P)) >= 1e-4`. Caso o preço tenha sido constante no histórico, não há variância para regressão; neste caso adota-se `DEFAULT_ELASTICITY` (-1.2) com confiança `BAIXA`.
- **Resultado:** Retorna `beta`, `r2`, erro padrão `se_beta` e `p_value`.

### `P-097`: Suavização Hierárquica Bayesiana (Shrinkage) por Cliente
- **Declaração Mandatória:** A elasticidade de um cliente específico para um determinado produto DEVE ser calculada via suavização hierárquica (shrinkage) que aproxima a elasticidade individual do cliente da elasticidade geral do produto conforme o volume de observações do cliente.
- **Fórmula Mandatória:**
  $$w = \frac{n_{cliente}}{n_{cliente} + K_{SHRINKAGE}}$$
  $$\beta_{cliente\_final} = w \cdot \beta_{cliente\_empirico} + (1 - w) \cdot \beta_{produto}$$
- **Propriedades Mandatórias:**
  - Monotonicidade: à medida que $n_{cliente} \to \infty$, $w \to 1$ e a elasticidade converge para o comportamento individual do cliente.
  - Para clientes com poucas compras ($n_{cliente} < 3$), $\beta_{cliente\_final}$ se aproxima de $\beta_{produto}$.
  - Se o cliente não possuir histórico no produto, o sistema não deve inventar dados e deve reportar erro `ELA-002` (404).

### `P-098`: Limites de Plausibilidade Econômica e Fallback Defensivo
- **Declaração Mandatória:** Elasticidades estimadas fora do intervalo plausível de demanda B2B (`beta >= -0.05` ou `beta < -6.0`) DEVEM ser substituídas pelo valor canônico `DEFAULT_ELASTICITY` (-1.2) e marcadas explicitamente com confiança `BAIXA` / `NAO_CONFIAVEL`.
- **Condições de Ativação:** Toda regressão log-log executada para produto ou cliente.
- **Justificativa Econômica:** Elasticidades próprias positivas (`beta >= 0`) representam anomalias estatísticas espúrias (correlação entre inflação/crescimento de mercado e expansão simultânea de volume), inexistindo Bens de Giffen no portfólio fitoterápico/farmacêutico. Betas menores que -6.0 indicam instabilidade numérica.

### `P-099`: Métricas de Qualidade Estatística e Intervalo de Confiança
- **Declaração Mandatória:** Toda resposta de elasticidade DEVE reportar:
  1. Coeficiente de elasticidade pontual (`elasticity`).
  2. Intervalo de Confiança de 95%: `[elasticity - 1.96 * se, elasticity + 1.96 * se]`.
  3. Coeficiente de determinação $R^2$ (`rSquared`).
  4. Classificação de Confiança (`confidenceLevel`):
     - `ALTA`: $R^2 \ge 0.50$, $n \ge 12$ e beta dentro da faixa plausível sem fallback.
     - `MEDIA`: $0.20 \le R^2 < 0.50$ e $n \ge 6$.
     - `BAIXA`: $R^2 < 0.20$ ou $n < 6$ ou aplicação do fallback defensivo.
  5. Campo booleano `isReliable`: `True` se confiança `ALTA` ou `MEDIA`; `False` se `BAIXA`.

### `P-100`: Classificação Econômica e Diagnóstico Comercial
- **Declaração Mandatória:** O produto e o cliente DEVEM ser classificados economicamente de acordo com sua sensibilidade a preço:
  - `ELASTICO`: se `elasticity < -1.0` (redução de preço tende a gerar aumento proporcionalmente maior em volume; aumento de preço destrói volume agressivamente).
  - `INELASTICO`: se `-1.0 <= elasticity <= 0.0` (demanda pouco sensível; oportunidade para reajuste moderado de preço aumentando faturamento total).
  - Indicação Comercial: para produtos `INELASTICO` com margem unitária positiva e boa confiabilidade, o sistema DEVE emitir recomendação contextual de oportunidade de rentabilização.

### `P-101`: Motor de Simulação de Variação de Preço
- **Declaração Mandatória:** O endpoint `POST /analytics/elasticity/simulate` DEVE calcular o impacto projetado de uma variação percentual de preço informada (`priceChangePct`, entre -50.0% e +100.0%):
  - $\Delta Volume\% \approx \beta \cdot \Delta Preço\%$
  - $Volume_{novo} = Volume_{atual} \cdot (1 + \frac{\Delta Volume\%}{100})$
  - $Preco_{novo} = Preco_{atual} \cdot (1 + \frac{\Delta Preco\%}{100})$
  - $Receita_{nova} = Preco_{novo} \cdot Volume_{novo}$
  - $Margem_{nova} = (Preco_{novo} - Custo_{unitario}) \cdot Volume_{novo}$
  - $\Delta Receita = Receita_{nova} - Receita_{atual}$
  - $\Delta Margem = Margem_{nova} - Margem_{atual}$
- **Validações:** Se `priceChangePct` estiver fora de `[-50.0, 100.0]`, retornar erro `ELA-004` (400) com campo `priceChangePct`.

### `P-102`: Catálogo de Exceções de Domínio `ELA-XXX`
- **Declaração Mandatória:** Os erros do subdomínio de elasticidade DEVEM seguir o padrão de código semântico `ELA-XXX` no envelope padronizado:
  - `ELA-001` (HTTP 404): "Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade."
  - `ELA-002` (HTTP 404): "Cliente sem compras registradas para este produto."
  - `ELA-003` (HTTP 422): "Histórico de vendas insuficiente para estimar elasticidade do produto."
  - `ELA-004` (HTTP 400): "Parâmetros inválidos fornecidos para consulta ou simulação de elasticidade."

### `P-103`: Envelope de Resposta e Paginação de Clientes
- **Declaração Mandatória:** Todas as respostas 2xx DEVEM utilizar o envelope padronizado `{ "data": ..., "meta": { "timestamp", "version", ... } }`.
- **Paginação Mandatória:** A lista de clientes associados ao SKU DEVE ser paginada com parâmetros `limit` (default 50, máx 200) e `offset` (>= 0), retornando `totalItems`, `totalPages`, `limit` e `offset` no meta.

### `P-104`: Conformidade com LGPD e Isolamento de PII
- **Declaração Mandatória:** Clientes são identificados estritamente pelo identificador numérico `customerCode`. Nenhum dado pessoal (nome, CPF, CNPJ, razão social, endereço, telefone ou e-mail) DEVE ser exposto na API, renderizado na tela ou gravado em logs. Logs do sistema registram apenas métricas operacionais e códigos de erro semânticos.

### `P-105`: Interface Reativa Angular e os 8 Estados Interativos
- **Declaração Mandatória:** A tela de Elasticidade (`/analytics/elasticity`) DEVE ser integrada à navegação do módulo Analytics e suportar integralmente os 8 estados:
  1. *Initial / Idle*: Campo de busca de produto ativo com instruções.
  2. *Loading*: Skeleton loader durante consulta e processamento.
  3. *Success*: Cards de elasticidade, badge de confiança, simulador interativo com slider e tabela de clientes.
  4. *Empty*: Aviso quando não houver clientes com compras do produto.
  5. *Error*: Card de erro contextual com botão de retry sem tela quebrada.
  6. *Disabled*: Controles de simulação bloqueados durante processamento.
  7. *Invalid*: Validação visual imediata para valores de slider ou busca fora de escopo.
  8. *Partial / Low-Confidence*: Badge de alerta visual claro quando o resultado for de baixa confiabilidade estatística, explicando a aplicação do fallback defensivo.

---

## 4. Matriz de Cenários e Edge Cases

| ID | Cenário | Entrada | Comportamento Esperado | Código HTTP |
| :--- | :--- | :--- | :--- | :-: |
| E-01 | SKU inexistente | SKU = 999999 | Lança `ProductNotFoundError` com código `ELA-001` | 404 |
| E-02 | Cliente sem compras no SKU | SKU = 1001, Cliente = 999 | Lança `CustomerWithoutHistoryError` com código `ELA-002` | 404 |
| E-03 | Menos de 5 observações | SKU = 1002 (3 meses) | Fallback para `-1.2`, confiança `BAIXA`, `isReliable: false` | 200 |
| E-04 | Preço estritamente constante | SKU = 1003 (preço R$ 10 em 10 meses) | Std = 0, fallback para `-1.2`, confiança `BAIXA` | 200 |
| E-05 | Beta positivo (> 0) em dados reais | Regressão resulta em +0.8 | Rejeição econômica defensiva, substitui por `-1.2`, confiança `BAIXA` | 200 |
| E-06 | Devolução no mês abate volume | Venda = 100, Devolução = 30 | Volume líquido computado como 70 un. | 200 |
| E-07 | Devolução total (líquido zero) | Venda = 50, Devolução = 50 | Mês descartado para não gerar ln(0) | 200 |
| E-08 | Simulação com +10% | `priceChangePct: 10.0` | Projeta delta volume, receita e margem monetária | 200 |
| E-09 | Simulação fora da faixa (+150%) | `priceChangePct: 150.0` | Lança `InvalidParametersError` `ELA-004` com campo `priceChangePct` | 400 |
| E-10 | Paginação de clientes inválida | `limit: 500` | Lança `InvalidParametersError` `ELA-004` | 400 |

---

## 5. Rastreabilidade com Regras do Sistema

- P-095 a P-105 implementam a especificação de F5 descrita no plano mestre `ia-analytics-vendas.md` (§4).
- Respeitam rigorosamente o isolamento de camadas, a governança de documentação e as regras de segurança contra vazamento de PII.
