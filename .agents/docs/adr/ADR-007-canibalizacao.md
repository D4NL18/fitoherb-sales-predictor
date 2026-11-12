# ADR-007: Arquitetura e Modelagem Estatística da Canibalização e Substituição de Produtos (Fase F6)

> **Status:** Proposto (Aguardando Checkpoint da Etapa 2)  
> **Data:** 2026-11-12  
> **Autores:** Arquiteto (`architect.md`) & Especialista em IA (`ai_specialist.md`)  
> **Localização Mandatória:** `.agents/docs/adr/ADR-007-canibalizacao.md`  
> **Módulo:** `src/modules/analytics/` (`domain/cannibalization.py`)  
> **Branch:** `feature/analytics-canibalizacao`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Canibalização e Substituição de Produtos (Fase F6) |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-canibalizacao.md` (Envelope `data`/`meta`, prefixo `CAN-XXX`) |
| **Checklist Técnico** | `.agents/docs/tasks/analytics-canibalizacao.md` |
| **Design Plan** | `.agents/docs/design/plans/analytics-canibalizacao.md` |
| **Parecer de Privacidade** | `.agents/docs/privacy/analytics-canibalizacao.md` (Bypass de RIPD / Minimização) |
| **Integração Externa** | Interface `CrossElasticityProvider` para conexão futura com Fase F5 (Elasticidade) |

---

## 1. Contexto do Problema e Motivação

1. **Problema de Negócio (Promoções Ilusórias vs Ganho Real):**
   Na distribuição de produtos fitoterápicos, suplementos e chás, ações comerciais como descontos agressivos, introdução de novos formatos de embalagem ou lançamentos frequentemente provocam aumento expressivo de vendas no SKU alvo, mas à custa da retração de outros itens de alta margem da mesma categoria. Sem uma ferramenta analítica, a gestão comercial comemora recordes de volume que, na realidade, erodem a rentabilidade líquida da empresa.

2. **Desafios Metodológicos e Limitações da Base:**
   - **Isolamento de Sazonalidade Sem a Fase F1:** A Fase F6 está programada para execução antes da Fase F1 (Sazonalidade). Uma simples comparação "antes vs depois" atribuiria erroneamente variações sazonais de categoria (ex.: aumento geral de chás no inverno ou queda em feriados) à promoção do produto alvo.
   - **Histórico Limitado (~23 meses):** A base cobre de janeiro/2025 a novembro/2026. Modelos econométricos pesados de séries temporais não convergem com robustez nesse horizonte.
   - **Risco de Falsas Descobertas (Múltiplos Testes):** Comparar um produto alvo contra 50 a 100 itens da mesma categoria gera alta probabilidade de falsos positivos pelo acaso se forem usados testes de hipótese ingênuos.
   - **Catálogo ERP Legado:** O ERP não possui taxonomia taxonômica profunda (apenas campo texto `Tipo` e `Fornecedor`).
   - **Orçamento de Recursos no Cloud Run (2Gi):** As operações de mineração e ajuste estatístico não podem carregar bases transacionais brutas no Python nem consumir picos de memória excessivos.

---

## 2. Decisões Arquiteturais e Estatísticas

```
                    ┌──────────────────────────────────────────────┐
                    │          FastAPI Router /analytics/          │
                    │   GET /cannibalization/{sku}                 │
                    │   GET /substitution/{sku}                    │
                    └──────────────────────┬───────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │               AnalyticsService               │
                    │      (Cache em memória, lock, TTL 6h)        │
                    └───────┬──────────────────────────────┬───────┘
                            │                              │
                            ▼                              ▼
      ┌───────────────────────────────────┐  ┌───────────────────────────────────┐
      │   SalesRepository (SQL Server)    │  │   Domain: CannibalizationEngine   │
      │  - monthly_sales (líquido D4)     │  │  - P-128: Jaccard Candidates      │
      │  - promo_calendar (T0 do evento)  │  │  - P-131: Categorial Control Group│
      │  - active_catalog (custo/preço)   │  │  - P-132: Difference-in-Diffs     │
      │  - Somente leitura & sem CONCAT   │  │  - P-133: FDR Benjamini-Hochberg  │
      └───────────────────────────────────┘  │  - P-134: Classification Taxonomy │
                                             │  - P-135: Net Impact Calculator   │
                                             └─────────────────┬─────────────────┘
                                                               │ (Consumo Gracioso)
                                                               ▼
                                             ┌───────────────────────────────────┐
                                             │     CrossElasticityProvider       │
                                             │   (Interface abstrata com F5)     │
                                             │   [Ativa quando F5 for entregue]  │
                                             └───────────────────────────────────┘
```

### DA-01 — Quase-Experimento de Diferença em Diferenças (DiD) com Grupo de Controle Categorial

Para solucionar o isolamento causal sem requerer os índices sazonais de F1, adotamos a abordagem quasi-experimental de **Diferença em Diferenças (DiD)**:
- **Grupo de Tratamento ($i$):** Conjunto de candidatos a substitutos do produto alvo $T$.
- **Grupo de Controle ($C$):** Conjunto de produtos da mesma categoria (`Tipo`) que **não** sofreram alterações de preço ($|\Delta P\%| < 3\%$), **não** participaram de promoções na janela e não possuem correlação comportamental extrema com o alvo.
- **Premissa de Trajetória Paralela:** Na ausência da intervenção no produto alvo, o grupo de candidatos teria seguido a mesma taxa média de variação da categoria:
  $$g_{ctrl} = \frac{\sum_{k \in C} V_k^{Pos}}{\sum_{k \in C} V_k^{Pre}}$$
- **Volume Contrafactual e Efeito Causal Estimado:**
  $$\hat{V}_i^{Pos} = V_i^{Pre} \times g_{ctrl}$$
  $$\Delta V_i = V_i^{Pos} - \hat{V}_i^{Pos}$$
Esta formulação neutraliza instantaneamente qualquer choque de demanda exógeno, inflação, sazonalidade setorial ou variações de dias úteis entre os períodos.

---

### DA-02 — Seleção Híbrida de Substitutos (Semântica de Categoria + Jaccard de Compradores)

Diante da ausência de ontologias de produtos refinadas no ERP, a identificação dos substitutos potenciais opera de forma híbrida e em dois níveis:
1. **Filtro Categorial:** Restringe a busca inicial a produtos com o mesmo atributo `Tipo` (`P-128.1`).
2. **Similaridade Comportamental (Índice de Jaccard):**
   Calcula-se a sobreposição de carteira de clientes nos últimos 365 dias:
   $$J(A, B) = \frac{|Clientes(A) \cap Clientes(B)|}{|Clientes(A) \cup Clientes(B)|}$$
   Candidatos são validados se $J(A, B) \ge 0.15$ ou se compartilham $\ge 5$ clientes compradores habituais (`P-128.3`).
3. **Poda de Complexidade:** Os candidatos são ordenados por Jaccard e limitados aos Top 20 itens mais similares (`MAX_CANDIDATE_SUBSTITUTES = 20`), garantindo que o cômputo estatístico rode em tempo inferior a 150ms.

---

### DA-03 — Modelagem Estatística: Bootstrap / Teste-t e Controle de Descoberta Falsa (FDR Benjamini-Hochberg)

Para evitar que ruído transacional aleatório em dezenas de SKUs seja apresentado como canibalização:
1. **Significância Local:** Calcula-se o erro padrão da diferença em diferenças através da dispersão temporal das vendas semanais no período pré/pós, obtendo-se o valor-p bicaudal ($p_i$) sob a hipótese nula $H_0: \Delta V_i = 0$.
2. **Correção para Testes Múltiplos:** Aplica-se o procedimento de Benjamini-Hochberg com taxa de falso descobrimento fixada em $\alpha = 0.05$:
   - Ordenam-se os $m$ testes: $p_{(1)} \le p_{(2)} \le \dots \le p_{(m)}$.
   - Define-se o corte: $k = \max \left\{ j : p_{(j)} \le \frac{j}{m} \alpha \right\}$.
   - Itens com $p_{(j)} \le p_{(k)}$ são estatisticamente significativos.
3. **Filtro de Relevância Econômica:** Variações com magnitude absoluta inferior a 5 unidades ($|\Delta V_i| < 5$) são reclassificadas automaticamente como `SEM_EFEITO`, mesmo que alcancem significância estatística, protegendo o usuário de alarmismos irrelevantes.

---

### DA-04 — Consolidação Financeira do Efeito Líquido e Diagnóstico Comercial

A feature não se limita a métricas operacionais; ela consolida a saúde financeira da decisão comercial:
- **$\Delta$ Volume Líquido:** $\Delta V_{liq} = \Delta V_{alvo} + \sum_{i} \Delta V_i$
- **$\Delta$ Receita Líquida:** $\Delta R_{liq} = \Delta R_{alvo} + \sum_{i} (\Delta V_i \times \bar{P}_i^{Pos})$
- **$\Delta$ Margem Líquida:** $\Delta M_{liq} = \Delta M_{alvo} + \sum_{i} (\Delta V_i \times M_{u, i})$, onde $M_{u, i} = Pc.Venda_i - Custo_i$. Se o custo for ausente, aplica-se o fallback de 60% de custo ($M_u = 40\%$).
- **Veredito Executivo:**
  - `VALEU_A_PENA`: $\Delta M_{liq} > 0$ (ganho real de rentabilidade).
  - `ILUSAO_DE_VOLUME`: $\Delta V_{liq} > 0$, mas $\Delta M_{liq} \le 0$ (vendeu mais caixas, porém perdeu dinheiro ao canibalizar itens mais nobres).
  - `PREJUIZO_TOTAL`: $\Delta V_{liq} \le 0$ e $\Delta M_{liq} \le 0$ (fracasso da ação comercial).

---

### DA-05 — Design da Interface de Integração Desacoplada com F5 (Elasticidade)

A Fase F6 foi concebida para operar autonomamente, mas preparada para incorporar a elasticidade cruzada assim que a Fase F5 for entregue.
- **Protocolo de Integração em Python:**
  ```python
  class CrossElasticityProvider(Protocol):
      async def get_cross_elasticity(self, target_sku: str, substitute_sku: str) -> Optional[float]:
          ...
  ```
- **Decomposição do Choque:**
  Com $\epsilon_{ji} = \frac{\% \Delta Q_j}{\% \Delta P_i}$:
  $$\Delta V_{j, preco} = V_j^{Pre} \times \left( \epsilon_{ji} \times \frac{\Delta P_i}{P_i^{Pre}} \right)$$
  $$\Delta V_{j, visibilidade} = \Delta V_j - \Delta V_{j, preco}$$
- **Degradação Graciosa:** Enquanto F5 não estiver disponível, o `NullCrossElasticityProvider` injeta `null` nos campos analíticos de elasticidade e atribui `statusElasticidade = "NAO_INTEGRADO"`, sem impactar o cálculo do DiD ou quebrar a resposta.

---

### DA-06 — Agregações no Banco de Dados (SQL Server), Devoluções e Cache

- **Imunidade a OOM:** Nenhuma linha bruta de transação é transmitida da base. O repositório consome o agregado `monthly_sales` e `promo_calendar` (§2.5).
- **Tratamento de Devoluções (D4):** As devoluções são filtradas com `[Operação] LIKE 'DEVOLU%'` e abatidas das vendas.
- **Sem `CONCAT`:** Toda concatenação é feita com operador `+` e `CAST`.
- **Cache Thread-Safe:** Padrão `AnalyticsCache` com bloqueio concorrente (`asyncio.Lock`) e TTL de 6 horas, impedindo múltiplas execuções simultâneas de DiD para o mesmo SKU.

---

### DA-07 — Padronização de Erros Autocontidos (`CAN-XXX`) e Envelope de Resposta

- As exceções herdam de `AnalyticsDomainException` e são tratadas pelo handler centralizado de erros do módulo `analytics`.
- Códigos: `CAN-001` (404), `CAN-002` (422), `CAN-003` (422), `CAN-004` (400), `CAN-005` (500).
- Envelope padrão `{ "data": ..., "meta": ... }` com atributos exclusivamente em `camelCase`.

---

### DA-08 — Formalização dos Bypasses da Etapa 2

- **DBA (Bypass Total):** A feature atua exclusivamente sobre views e tabelas legadas já existentes (`Externo01.Vendas`, `Externo01.Produto`), sem criar tabelas, índices ou migrations.
- **Privacy Officer (Bypass de RIPD / Minimização Estrita):** As consultas de canibalização e substituição operam no nível de SKU. Os códigos de cliente (`Cod Cliente`) são processados apenas como identificadores efêmeros para cálculo de interseção de Jaccard e imediatamente descartados, sem exposição em endpoints ou logs. Formaliza-se parecer de conformidade dispensando RIPD.

---

## 3. Alternativas Consideradas e Descartadas

| Opção | Descrição | Motivo do Descarte |
| :--- | :--- | :--- |
| **A1: Regressão OLS Simples (Sem Controle)** | Regredir vendas dos substitutos contra dummy de evento sem grupo de controle. | **Descartada:** Sofre de viés catastrófico por confundir tendências sazonais e feriados com o efeito da promoção. |
| **A2: Aguardar Conclusão de F1 (Sazonalidade)** | Pausar F6 até que F1 calcule e disponibilize os índices sazonais de todos os produtos. | **Descartada:** Atrasa desnecessariamente o roadmap. O grupo de controle categorial atua como proxy perfeito da sazonalidade compartilhada. |
| **A3: Correlação de Pearson Temporal Simples** | Definir substitutos apenas pela correlação temporal negativa entre séries de vendas. | **Descartada:** Gera dezenas de relações espúrias entre produtos que não têm qualquer relação de consumo. O filtro Jaccard garante fundamentação comportamental de compradores reais. |
| **A4: Correção de Bonferroni para Testes Múltiplos** | Dividir $\alpha$ pelo número total de candidatos ($\alpha / m$). | **Descartada:** Excessivamente conservadora, provocando alto índice de falsos negativos (erro Tipo II) e ocultando casos reais de canibalização moderada. A abordagem Benjamini-Hochberg (FDR) equilibra precisão e sensibilidade. |

---

## 4. Consequências e Trade-offs

### Pontos Positivos:
- **Independência de F1:** A esteira de analytics ganha agilidade sem perder rigor causal.
- **Transparência Gerencial:** O comitê comercial visualiza claramente o efeito em margem de contribuição (R$), evitando prejuízos ocultos.
- **Segurança Operacional:** Processamento leve baseado em agregados SQL, blindando o Cloud Run contra picos de memória e OOM.
- **Design Extensível:** A estrutura modular recebe a Fase F5 sem qualquer ruptura de contrato de API.

### Trade-offs e Mitigações:
- *Categorias Muito Pequenas:* Produtos em categorias com menos de 5 SKUs estáveis não conseguem formar o grupo de controle estrito.
  *Mitigação:* Implementado algoritmo de fallback para produtos do mesmo Fornecedor ou portfólio geral (`P-131.4`), sinalizado via metadados.
- *Janelas de Análise de Lançamentos Recentes:* Novos produtos com menos de 3 meses não podem ser avaliados.
  *Mitigação:* Trava determinística com erro semântico amigável `CAN-003`, orientando o usuário sobre a maturidade do produto.
