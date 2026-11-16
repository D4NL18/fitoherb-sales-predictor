# ADR-005: Detecção de Sazonalidade por Produto com Agregação SQL Enxuta, Detrending Linear e Declaração Transparente de Confiança

> **Status:** Aprovado para Implementação  
> **Data:** 2026-11-12  
> **Autor:** Arquiteto (`architect`)  
> **Localização Mandatória:** `.agents/docs/adr/ADR-005-sazonalidade-produto.md`  

| Campo | Valor |
| :--- | :--- |
| **Feature / Branch** | FASE F1 — Detecção de Sazonalidade por Produto (`feature/analytics-sazonalidade`) |
| **Regras de Negócio** | `.agents/docs/business_rules/analytics-sazonalidade.md` (P-106 a P-116) |
| **Contrato de API** | `.agents/docs/api_contracts/analytics-sazonalidade.md` (versão 1.0.0) |
| **Checklist Técnico** | `.agents/docs/tasks/analytics-sazonalidade.md` (T-xx, B-xx, F-xx, Q-xx) |
| **Plano Mestre** | `.agents/docs/tasks/ia-analytics-vendas.md` §2 e §6 |
| **Enquadramento LGPD** | Bypass justificado (dados agregados por SKU/Produto; zero dados pessoais ou de cliente) |

---

## 1. Contexto do Problema

1. **Janela Real da Base de Dados (~23 meses):**
   A base de vendas da distribuidora cobre de janeiro de 2025 até o presente (~23 meses decorridos). Cada mês do calendário possui no máximo duas ocorrências (janeiro a outubro de 2025 e 2026), e apenas uma ocorrência para novembro e dezembro (referentes a 2025 completo). A decomposição sazonal estatística clássica (médias móveis de 12 meses como STL ou X-13ARIMA) descartaria 6 meses em cada extremidade da série, deixando apenas ~11 pontos úteis, o que tornaria o cálculo inviável ou artificial.
2. **Restrição Severa de Memória no Cloud Run (2Gi):**
   O ambiente Cloud Run possui teto de 2Gi. Trazer transações linha a linha no grão de pedido para calcular séries mensais em Python causaria picos de alocação e risco de OOM (Out Of Memory). A agregação de quantidade e faturamento líquidos DEVE ser realizada diretamente no motor SQL Server, trafegando apenas o grão `Cod Produto × Ano × Mês`.
3. **Tratamento de Devoluções e Mês Corrente (Decisão D4):**
   Devoluções (`[Operação] LIKE 'DEVOLU%'`) possuem quantidades e valores negativos que precisam abater as vendas do respectivo mês. O mês corrente deve ser excluído por ser incompleto e distorcer médias anuais.
4. **Reutilização Intermódulos (F6 e F2):**
   As fases futuras F6 (Canibalização de Produtos) e F2 (Viabilidade de Novo Produto) necessitam do índice sazonal por produto. O domínio deve expor uma função limpa e determinística, desacoplada do framework web FastAPI e do banco.

---

## 2. Decisões Arquiteturais (DA-01 a DA-07)

### DA-01 — Estrutura de Camadas e Isolamento no Módulo `analytics`

A feature estende a estrutura estabelecida no ADR-002, sem criar módulos paralelos nem acoplamentos indevidos:

```
src/modules/analytics/
├── api/
│   ├── router.py             # Adiciona rotas GET /seasonality/{sku} e GET /seasonality/ranking
│   ├── schemas.py            # Schemas Pydantic camelCase da feature
│   └── error_handlers.py     # Mapeamento dos erros SEA-XXX
├── domain/
│   ├── seasonality.py        # Motor determinístico, detrending, cálculo YoY, pico/vale, rankings
│   └── exceptions.py         # SeasonalityProductNotFoundError (SEA-001), etc.
├── repository/
│   └── sales_repository.py   # Nova query agregada fetch_monthly_sales (somente leitura)
└── service/
    ├── analytics_cache.py    # Integração de monthly_sales no snapshot compartilhado
    └── analytics_service.py  # Orquestração do caso de uso de sazonalidade
```

### DA-02 — Agregação SQL Enxuta no Grão `Cod Produto × Ano × Mês`

O repositório `sales_repository.py` adiciona a função `fetch_monthly_sales(cutoff: date) -> pd.DataFrame` com a seguinte query executada via cursor seguro `_execute_readonly`:

```sql
SELECT
    [Cod Produto]                                     AS sku,
    YEAR([Data])                                      AS sale_year,
    MONTH([Data])                                     AS sale_month,
    SUM([Qtd Venda])                                  AS net_quantity,
    SUM([Valor Venda])                                AS net_revenue
FROM Externo01.Vendas
WHERE ([Operação] = 'VENDA' OR [Operação] LIKE 'DEVOLU%')
  AND [Data] < ?
GROUP BY [Cod Produto], YEAR([Data]), MONTH([Data])
```

- **Impacto de Memória:** Com ~1.935 produtos ativos e ~23 meses, essa agregação resulta em no máximo ~45.000 linhas na base completa, ocupando menos de **2,5 MB** em memória no Pandas. O impacto no Cloud Run é praticamente nulo (< 0,2% do limite).

### DA-03 — Algoritmo Determinístico de Razão Ano a Ano com Detrending Linear

Para evitar dependências pesadas como `statsmodels`, `prophet` ou `scipy`, o cálculo é implementado com NumPy e matemática matricial pura em `src/modules/analytics/domain/seasonality.py`:
1. **Série Temporal Completa:** O intervalo do produto compreende do seu primeiro mês ativo até o último mês completo disponível. Meses sem vendas recebem 0. Saldos líquidos mensais negativos são truncados em 0.
2. **Remoção de Tendência Linear:** Ajusta-se $\hat{y}_t = \alpha + \beta t$ por regressão linear de mínimos quadrados ($N$ meses). A série destendenciada multiplicativa é $z_t = y_t / \max(\hat{y}_t, \epsilon)$.
3. **Razão Anual:** Para cada ano $a$, $R_{a, m} = z_{a, m} / \bar{z}_a$.
4. **Índice Final Normalizado:** Média das razões disponíveis por mês de calendário com calibração final para $\sum_{m=1}^{12} I_m / 12 = 1.00$.
5. **Correlação YoY ($r_{YoY}$):** Correlação linear de Pearson calculada sobre os meses com ocorrência em 2025 e 2026 ($m \in [1, 10]$).

### DA-04 — Declaração Explícita de Confiança e Classificação de Força

Em vez de induzir o usuário a uma falsa precisão estatística:
- **Confiança por Mês:**
  - `ALTA`: 2 observações com divergência relativa $\le 35\%$.
  - `MEDIA`: 2 observações com divergência $> 35\%$.
  - `BAIXA`: 1 única observação (novembro e dezembro de 2025).
- **Força do Produto:**
  - `FORTE`: $r_{YoY} \ge 0.60$ e amplitude $(I_{\max} - I_{\min}) \ge 0.40$.
  - `MODERADA`: ($r_{YoY} \ge 0.35$ e amplitude $\ge 0.20$) ou amplitude $\ge 0.40$ com correlação aceitável.
  - `FRACA`: Amplitude $< 0.20$ ou correlação fraca (ausência de padrão repetível).
  - `INSUFICIENTE`: Menos de 18 meses de histórico ou atividade $< 50\%$.

### DA-05 — Função de Domínio Exportada (`get_seasonality_index`)

O domínio de `seasonality.py` expõe explicitamente:
```python
def get_seasonality_index(
    sku: int,
    monthly_sales_df: pd.DataFrame,
    catalog_dict: Dict[int, CatalogItem]
) -> SeasonalityResult:
    ...
```
Esta assinatura não depende do FastAPI, de rotas ou de banco de dados, permitindo que as fases F6 (Canibalização) e F2 (Viabilidade de Novo Produto) importem diretamente a função e obtenham os 12 índices mensais de qualquer produto.

### DA-06 — Contratos REST com Envelope Padronizado e Paginação

As rotas seguem rigorosamente o padrão do módulo `analytics`:
- Envelope: `{ "data": ..., "meta": { "timestamp", "version", "page", "totalItems", ... } }`.
- Nomes dos atributos em JSON gerados em `camelCase`.
- Erros traduzidos pelo handler global (`api/error_handlers.py`), mapeando `SEA-001` (404), `SEA-002` (400) e `SEA-003` (422).

### DA-07 — Reuso da Infraestrutura de Cache Existente

O `monthly_sales` é carregado e incorporado no `AnalyticsSnapshot` de `analytics_cache.py`. O double-checked locking e o TTL de 6 horas já existentes no módulo garantem que a base mensal seja lida uma única vez de forma atômica e compartilhada entre todas as consultas e rankings.

---

## 3. Consequências

- **Positivas:**
  - Zero dependências de bibliotecas externas complexas (cálculo determinístico em Python puro + NumPy).
  - Memória residente incremental inferior a 3 MB no Cloud Run.
  - Total transparência para o usuário de negócios sobre a confiança de cada mês.
  - Desacoplamento completo do domínio para reuso futuro em F6 e F2.
- **Limitações:**
  - Meses com apenas 1 observação (novembro e dezembro) não possuem validação cruzada entre anos; a interface resolve isso com o selo visual de confiança `BAIXA`.
