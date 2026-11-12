# ADR-006: Detecção e Priorização de Churn de Clientes com Score Multidimensional (Tempo × Faturamento)

> **Status:** Aprovado para Implementação  
> **Data:** 2026-11-12  
> **Autor:** Arquiteto de Software (`architect`)  
> **Localização Mandatória:** `.agents/docs/adr/ADR-006-churn-clientes.md`  

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | Fase F3 — Churn de Clientes com Score de Prioridade (`feature/analytics-churn`) |
| **Módulo** | `analytics` (Backend FastAPI + Frontend Angular) |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-churn.md` (P-117 a P-127) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-churn.md` (v1.0.0) |
| **Tarefas e DoD** | `.agents/docs/tasks/analytics-churn.md` |
| **Plano Mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` (§7) |
| **Parecer de Privacidade**| `.agents/docs/privacy/analytics-churn.md` |

---

## 1. Contexto do Problema e Forças

1. **Volume de Clientes em Risco:** A consulta analítica preliminar revelou que cerca de 42% da carteira histórica de clientes (1.402 de 3.361) possui mais de 60 dias sem efetuar compras. Uma listagem simples e não-priorizada sobrecarregaria a equipe de vendas e inviabilizaria ações assertivas.
2. **Heterogeneidade de Clientes e Cadências:** A distribuidora atende farmácias e comércios com perfis de compra distintos (desde compras semanais até compras bimestrais/trimestrais programadas). Uma régua fixa e rígida de 60 dias geraria falsos positivos severos para clientes periódicos.
3. **Ponderação de Valor Financeiro:** Perder um cliente com faturamento de R$ 50.000/mês que está sem comprar há 70 dias representa uma perda de receita exponencialmente mais grave do que um cliente esporádico de R$ 500/mês parado há 120 dias. A métrica de ordenação deve combinar valor e urgência de forma contínua e compreensível.
4. **Restrições de Memória do Cloud Run (2Gi):** Não podemos carregar vendas brutas linha a linha no Python. O repositório deve realizar agregações no SQL Server e transferir apenas agregados consolidados por cliente.
5. **Simplicidade de Dependências e FinOps:** Evitar bibliotecas pesadas de machine learning probabilístico (como `lifetimes` ou `scipy.optimize` complexo). O cálculo é totalmente determinístico, expressivo e executável em milissegundos com NumPy/Pandas.
6. **Privacidade (LGPD):** O código do cliente (`Cod Cliente`) é o único elo de ligação com o ERP. Nenhuma informação de identificação direta (Razão Social, Nome, CNPJ/CPF, Telefone) deve transitar na API ou constar em logs.

---

## 2. Decisões Arquiteturais

### DA-01 — Estrutura e Isolamento de Camadas (Clean Architecture)
A implementação do Churn de Clientes adere estritamente à estrutura modular existente de `src/modules/analytics/`:
```
src/modules/analytics/
├── domain/
│   ├── churn.py              # Regra pura: P-117 a P-127, sem I/O, sem HTTP, sem SQL
│   └── exceptions.py         # CustomerWithoutHistoryError (CHU-001), InsufficientBaseError (CHU-002)
├── repository/
│   └── sales_repository.py  # Agregados customer_orders e customer_monthly_revenue (somente leitura)
├── service/
│   ├── analytics_service.py # Casos de uso de churn orquestrando cache e domínio
│   └── analytics_cache.py   # Snapshot enriquecido com agregados de churn
└── api/
    ├── router.py             # Rotas /analytics/churn/...
    ├── schemas.py            # Schemas Pydantic v2 com envelope camelCase
    ├── mappers.py            # Mapeamento domínio -> DTO
    └── error_handlers.py     # Mapeamento CHU-001..003 -> HTTP 404/422/400
```

### DA-02 — Agregação em SQL Server no Grão Adequado
Para evitar estouro de memória (OOM), o repositório executa duas queries analíticas agregadas via `_execute_readonly`:
1. `_CUSTOMER_ORDERS_SQL`: Grão `Cod Cliente × Data`, com `[Operação] = 'VENDA'` e `[Data] < ?`. Retorna datas de pedidos de venda para cálculo de recência e gap típico.
2. `_CUSTOMER_MONTHLY_REVENUE_SQL`: Grão `Cod Cliente × Ano × Mês`. Calcula a soma líquida de `Valor Venda` considerando `VENDA` e subtraindo devoluções (`[Operação] LIKE 'DEVOLU%'`), filtrando `[Data] < ?`.

### DA-03 — Algoritmo Determinístico de Retenção (`domain/churn.py`)
- **Gap Típico:** Mediana dos intervalos entre pedidos consecutivos para clientes com $\ge 3$ pedidos.
- **Régua Adaptativa:** $\text{diasReferencia} = \max(60, 1.5 \times \text{gapTipico})$. Clientes com $< 3$ pedidos utilizam a régua base de 60 dias.
- **Fator Tempo com Saturação:** $\text{fatorTempo} = \min(\text{diasSemComprar} / \text{diasReferencia}, 2.0)$.
- **Faturamento Médio Mensal:** Soma líquida dos últimos 12 meses completos dividida pelos meses ativos (delimitado entre 3 e 12). Clientes com histórico curto ($< 3$ pedidos) recebem divisor mínimo forçado de 3 meses.
- **Score:** $\text{scorePrioridade} = \text{faturamentoMedioMensal} \times \text{fatorTempo}$ (expresso em R$).
- **Segregação de Inativos Antigos:** Clientes com $\text{diasSemComprar} > 180$ são segregados para `GET /analytics/churn/inactive`.

### DA-04 — Cache por Snapshot Compartilhado
Os agregados de churn são calculados durante o ciclo de snapshot em memória de `analytics_cache.py`, aproveitando o mesmo lock e TTL de 6 horas já estabelecido. O snapshot armazena dicionários pré-calculados de clientes em risco e clientes inativos para servir consultas paginadas instantâneas (< 15ms).

### DA-05 — Contrato REST com Envelope Padronizado e Paginação
Todas as rotas expostas respondem no envelope corporativo da plataforma:
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2026-11-12T12:00:00Z",
    "version": "1.0.0",
    "limit": 50,
    "offset": 0,
    "totalItems": 420,
    "totalPages": 9
  }
}
```
Rotas expostas:
- `GET /api/v1/analytics/churn/customers?status=EM_RISCO&limit=50&offset=0`
- `GET /api/v1/analytics/churn/customers/{customerCode}`
- `GET /api/v1/analytics/churn/inactive?limit=50&offset=0`

### DA-06 — Tratamento Semântico de Erros (CHU-XXX)
- `CHU-001` (`404 Not Found`): Cliente não encontrado ou sem pedidos válidos de venda.
- `CHU-002` (`422 Unprocessable Entity`): Base analítica vazia ou insuficiente para apuração de churn.
- `CHU-003` (`400 Bad Request`): Parâmetros de consulta inválidos (ex.: `status` inválido, paginação fora de limites).

### DA-07 — Governança LGPD e Minimização
- Nenhuma rota de churn recebe ou devolve PII (nomes, e-mails, telefones ou documentos).
- Operação baseada exclusivamente em `customerCode` (inteiro).
- Logs estruturados registram apenas métricas agregadas (ex.: "Cálculo de churn concluído: 350 clientes em risco").

### DA-08 — Frontend Angular Reativo com Signals
- Implementação de página standalone `ChurnPageComponent` roteada como filha lazy em `/analytics/churn`.
- Tabela de dados priorizada com chips semânticos (`EM_RISCO`, `ALERTA`, `SAUDAVEL`), badge de `Histórico Curto` e formatação monetária padrão PT-BR.
- Painel lateral (drawer) de detalhes com abertura sob demanda, exibindo gráfico de barras dos últimos meses e lista dos 5 produtos perdidos.
- Suporte a download imediato de arquivo CSV estruturado para uso direto pela equipe comercial.

---

## 3. Consequências

- **Positivas:**
  - Redução drástica da sobrecarga operacional da equipe comercial, focando nos clientes cujo retorno financeiro é prioritário.
  - Baixíssimo consumo adicional de RAM (< 10 MB residentes para o snapshot de churn).
  - Isolamento estrito de regras de negócio na camada de domínio, garantindo facilidade de teste unitário via TDD.
- **Neutras / Trade-offs:**
  - Clientes que compram produtos altamente sazonais (fora de época) podem ser pontuados como em risco até a entrada da Fase F1 (Sazonalidade). A sinalização explicativa no drawer mitiga dúvidas do usuário.
