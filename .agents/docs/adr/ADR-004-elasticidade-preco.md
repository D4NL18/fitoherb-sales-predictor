# ADR-004: Modelo Econométrico Log-Log de Elasticidade-Preço, Shrinkage por Cliente e Simulador de Reajuste

> **Status:** Aprovado (Etapa 2)
> **Data:** 2026-11-12
> **Autor:** Arquiteto (`architect`)
> **Localização Mandatória:** `.agents/docs/adr/ADR-004-elasticidade-preco.md`

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | Fase 2 do Analytics Comercial (F5 Elasticidade) — `feature/analytics-elasticidade` |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-elasticidade.md` (P-095 a P-105) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-elasticidade.md` (versão 1.0.0) |
| **Checklist Técnico** | `.agents/docs/tasks/analytics-elasticidade.md` |
| **Parecer de Privacidade** | `.agents/docs/privacy/analytics-elasticidade.md` |

---

## 1. Contexto do Problema

1. **Sensibilidade a Preço em Distribuição B2B:** Em ambiente atacadista farmacêutico/fitoterápico, reajustes de preço impactam diretamente o volume de compra de farmácias e lojistas. No entanto, diferentes produtos e clientes reagem de formas distintas dependendo de poder de barganha e substitutibilidade.
2. **Dados Esparsos por Cliente:** Enquanto o produto agregado possui histórico consolidado ao longo de ~23 meses, a maioria dos clientes compra determinados SKUs com frequência esparsa (menos de 5 pedidos). Ajustar uma regressão log-log isolada por cliente geraria coeficientes ruidosos e instáveis.
3. **Abatimento Obrigatório de Devoluções (D4):** Devoluções devem ser abatidas do faturamento e quantidade do período. Meses com quantidade líquida menor ou igual a zero devem ser expurgados para não gerar valores indefinidos na transformação logarítmica.
4. **Desempenho e Restrição de Memória no Cloud Run:** A estimativa deve ser rápida, sem loops O(N²) e sem carregar vendas brutas no Python. O repositório agrega no banco os `price_points` mensais.

---

## 2. Decisões Arquiteturais (DA)

### DA-01 — Isolamento do Domínio Puro Econométrico (`domain/elasticity.py`)
Toda a matemática econométrica reside em `src/modules/analytics/domain/elasticity.py`, sem dependência de banco de dados (`pyodbc`), HTTP (`fastapi`) ou estado externo:
- Funções puras: recebem dados estruturados (arrays numpy ou DataFrames agregados) e retornam dataclasses imutáveis.
- Parâmetros e limites numéricos extraídos como constantes no topo do módulo.

### DA-02 — Agregado SQL `price_points` com Abatimento de Devoluções
O repositório `sales_repository.py` estende suas consultas agregadas trazendo:
- Volume líquido (`SUM(Qtd Venda)` considerando `VENDA` e `DEVOLU%`).
- Valor líquido (`SUM(Valor Venda)`).
- Agrupamento no grão `Cod Produto x Ano x Mes` e `Cod Produto x Cod Cliente x Ano x Mes`.
- Preço médio calculado como `Valor_Liquido / Qtd_Liquida` para períodos com `Qtd_Liquida > 0`.
- Exclusão do mês corrente (dados parciais).

### DA-03 — Regressão Linear Ponderada Log-Log com Pesos Temporais
A estimação econométrica assume a especificação de elasticidade constante:
$$\ln(Q_t) = \alpha + \beta \ln(P_t) + \epsilon_t$$
- Aplica pesos amostrais com decaimento exponencial $w_t = 2^{-\Delta d_t / 100.0}$, priorizando preços recentes.
- Computação em fórmula fechada do estimador MQOP (Mínimos Quadrados Ordinários Ponderados), obtendo o coeficiente $\beta$, o coeficiente de determinação $R^2$ e o erro padrão $SE(\beta)$.

### DA-04 — Suavização Hierárquica Bayesiana (Shrinkage) para Clientes
Para calcular a elasticidade do par produto-cliente:
$$w = \frac{n_{cliente}}{n_{cliente} + K_{SHRINKAGE}} \quad (K_{SHRINKAGE} = 10.0)$$
$$\beta_{par} = w \cdot \beta_{cliente} + (1 - w) \cdot \beta_{produto}$$
- Se $n_{cliente}$ for pequeno, $\beta_{par}$ aproxima-se com segurança de $\beta_{produto}$.
- Se $n_{cliente}$ for expressivo, o comportamento individual do cliente prevalece.

### DA-05 — Fallback Defensivo e Plausibilidade Econômica
- Se $\beta \ge -0.05$ (anomalia de bem de Giffen / espúria) ou $\beta < -6.0$ ou se a dispersão de preço for nula ($std(\ln(P)) < 1e-4$) ou observações $< 5$:
  - $\beta$ é substituído pelo valor canônico `DEFAULT_ELASTICITY = -1.2`.
  - Classificação de confiança é rebaixada para `BAIXA` (`isReliable = False`).

### DA-06 — Motor de Simulação de Variação de Preço
Endpoint `POST /analytics/elasticity/simulate` calcula de forma determinística:
- $\Delta Volume\% = \beta \cdot \Delta Preço\%$
- Novo volume, nova receita e nova margem monetária absoluta contra o custo unitário mais recente (`Pc.Ultimo Custo`).

### DA-07 — Padronização de Envelope e Tratamento de Erros
- Respostas 2xx encapsuladas no envelope `{ data, meta }` com timestamps e metadados.
- Erros de validação e domínio encapsulados no envelope `{ error, meta }` com prefixo semântico `ELA-XXX`.

---

## 3. Consequências

- **Positivas:**
  - Robustez matemática e garantia de que nenhum resultado positivo ou absurdo será apresentado ao usuário comercial.
  - Baixo consumo computacional (execução em milissegundos sobre séries mensais agregadas).
  - Isolamento estrito de PII em conformidade com a LGPD.
- **Limitações:**
  - Como a base histórica cobre ~23 meses, produtos com menos de 5 meses de vida utilizam o fallback padrão `-1.2` com badge visual indicativo de histórico insuficiente.
