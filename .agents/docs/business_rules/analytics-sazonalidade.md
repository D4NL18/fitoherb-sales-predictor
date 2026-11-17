# Regras de Negócio: Analytics Comercial — F1 Detecção de Sazonalidade por Produto

> **Localização Mandatória:** `.agents/docs/business_rules/analytics-sazonalidade.md`  
> **Responsável:** Analista (`business-rules-expert`)  
> **Referências de Regras:** `.agents/rules/architecture-business-logic-isolation-rules.md`, `backend-api-contract-rules.md`, `architecture-error-handling-rules.md`, `backend-db-performance-rules.md`, `security-anti-patterns.md`

| Campo | Valor |
| :--- | :--- |
| **Feature** | Detecção de Sazonalidade por Produto (Fase 4 do Plano Mestre / F1) |
| **Módulo** | `analytics` (subdomínio: Sazonalidade de Vendas) |
| **Branch** | `feature/analytics-sazonalidade` |
| **Faixa de Regras** | P-106 a P-117 |
| **Prefixo de Erros** | `SEA-XXX` |
| **Origem** | Plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§2, §6) e decisões D1-D4 |
| **Autor** | Analista (Etapa 1) |
| **Status** | Especificado — pronto para Etapa 2 |

---

## 1. Contexto e Objetivo

- **User Story:** US-F1 — *Como comprador ou gestor comercial da Fitoherb, quero consultar a sazonalidade histórica de qualquer produto e visualizar rankings de sazonalidade, identificando com clareza os meses de pico e vale de demanda, a força do padrão e o nível de confiança estatística de cada mês, para planejar compras, produção e estoques sem ser induzido a erro por dados escassos.*
- **Objetivo da Feature:**
  1. Fornecer busca rápida com autocomplete por código ou descrição de produto.
  2. Apresentar a curva de sazonalidade de 12 meses (janeiro a dezembro) com índice normalizado (média 1.0).
  3. Indicar claramente o(s) mês(es) de pico e vale, agrupando períodos adjacentes de alta ou baixa.
  4. Classificar a força da sazonalidade (`FORTE`, `MODERADA`, `FRACA`, `INSUFICIENTE`).
  5. Declarar a confiança de cada mês (`ALTA`, `MEDIA`, `BAIXA`), prevenindo falsas conclusões sobre meses com apenas 1 ciclo observado (como novembro e dezembro na base de ~23 meses).
  6. Disponibilizar rankings paginados dos produtos **mais sazonais** e dos **menos mensuráveis** (com motivo estruturado).
  7. Expor a função pública de domínio `get_seasonality_index(...)` para consumo desacoplado pelas fases posteriores F6 (Canibalização) e F2 (Viabilidade de Novo Produto).

---

## 2. Catálogo de Constantes e Parâmetros Numéricos

> [!IMPORTANT]
> Todos os parâmetros abaixo DEVEM ser definidos como constantes em caixa-alta no topo de `src/modules/analytics/domain/seasonality.py`. É proibido o uso de números mágicos na lógica.

| Constante | Valor | Finalidade / Regra |
| :--- | :---: | :--- |
| `MIN_MONTHS_FOR_SEASONALITY` | `18` | Mínimo de meses corridos desde a 1ª venda para elegibilidade (P-107). |
| `MIN_ACTIVE_MONTHS_RATIO` | `0.50` | Proporção mínima de meses com vendas líquidas > 0 no período ativo (P-107). |
| `MIN_YOY_CORRELATION` | `0.60` | Correlação linear mínima entre anos para classificar força como `FORTE` (P-110, P-111). |
| `MODERATE_YOY_CORRELATION` | `0.35` | Correlação mínima para considerar padrão `MODERADA` (P-111). |
| `STRONG_SEASONALITY_AMPLITUDE` | `0.40` | Amplitude mínima (pico - vale) do índice para força `FORTE` (P-111). |
| `MODERATE_SEASONALITY_AMPLITUDE` | `0.20` | Amplitude mínima do índice para força `MODERADA` (P-111). |
| `MAX_DIVERGENCE_RATIO` | `0.35` | Divergência relativa máxima entre dois anos para confiança `ALTA` do mês (P-112). |
| `PEAK_VALLEY_THRESHOLD_RATIO` | `0.90` | Limiar para agrupar meses adjacentes ao pico (>= 90% do pico) (P-113). |
| `MIN_REVENUE_SHARE` | `0.0005` | Participação mínima no faturamento total (0,05%) para entrar no ranking de mais sazonais (P-114). |
| `DEFAULT_PAGE_LIMIT` | `50` | Limite padrão de paginação de rankings (P-114). |
| `MAX_PAGE_LIMIT` | `200` | Limite máximo de paginação de rankings (P-114). |
| `AUTOCOMPLETE_LIMIT` | `20` | Máximo de sugestões devolvidas na busca rápida (P-115). |

---

## 3. Catálogo de Regras de Negócio (P-106 a P-116)

### `P-106`: Série Temporal Mensal Líquida por Produto
- **Declaração Mandatória:** A série histórica de vendas de cada produto DEVE ser agregada mensalmente a partir da base `Externo01.Vendas`, somando a quantidade e o valor das operações `VENDA` e abatendo as devoluções (`[Operação] LIKE 'DEVOLU%'`).
- **Condições de Ativação:** Consulta da sazonalidade de um produto ou geração de rankings.
- **Resultado Esperado:** 
  - O mês corrente (parcial) DEVE ser categoricamente excluído da série histórica.
  - Meses calendários compreendidos entre a primeira venda do produto e o último mês completo disponível que não tiveram vendas DEVEM ser preenchidos com quantidade 0 e valor 0.
  - Quantidade líquida ou valor líquido mensal negativo (ex: devoluções superiores a vendas no mês) DEVE ser truncado em zero para efeito de cálculo do índice sazonal.
- **Exceção / Erro:** Caso o produto não tenha nenhuma venda registrada na base, lançar erro `SEA-001`.

### `P-107`: Critério de Elegibilidade e Diagnóstico de Mensurabilidade
- **Declaração Mandatória:** O sistema DEVE avaliar a elegibilidade da série do produto antes do cálculo do índice sazonal.
- **Critérios de Elegibilidade:**
  1. O produto deve ter no mínimo `MIN_MONTHS_FOR_SEASONALITY` (18) meses decorridos entre o primeiro mês com venda e o último mês completo avaliado.
  2. O produto deve ter vendas em pelo menos `MIN_ACTIVE_MONTHS_RATIO` (50%) dos meses do seu período ativo.
- **Resultado Esperado:**
  - Se aprovado em ambos os critérios: prossegue para o cálculo de sazonalidade e força.
  - Se meses < 18: status de força recebe `INSUFICIENTE` com motivo de insuficiência `HISTORICO_CURTO`.
  - Se meses >= 18 mas taxa de atividade < 0.50: status de força recebe `INSUFICIENTE` com motivo `VENDA_ESPORADICA`.
- **Exibição:** Produtos classificados como `INSUFICIENTE` ainda exibem sua série histórica mensal e os índices aparentes, mas com banner explicativo e inclusão na lista de "Pouco Mensuráveis".

### `P-108`: Remoção de Tendência Linear (Detrending)
- **Declaração Mandatória:** Antes de computar a razão ano a ano, o sistema DEVE remover a tendência linear de longo prazo da série temporal mensal de vendas.
- **Procedimento:**
  - Ajusta-se uma regressão linear simples (mínimos quadrados) onde a variável independente $t$ é o índice sequencial do mês ($t = 1, 2, \dots, N$) e a dependente é a quantidade líquida $y_t$.
  - Calcula-se o valor de tendência $\hat{y}_t = \alpha + \beta t$.
  - A série destendenciada multiplicativa é calculada como $z_t = y_t / \max(\hat{y}_t, \epsilon)$ (onde $\epsilon$ é um piso positivo para evitar divisão por zero). Se a tendência estimada for nula ou não significativa (ex: inclinação negativa severa que levaria a valores espúrios), utiliza-se a normalização pela média global.
- **Objetivo:** Evitar que o crescimento orgânico da distribuidora ao longo de 2025/2026 infle artificialmente os meses do segundo semestre de 2026 como falsos picos sazonais.

### `P-109`: Cálculo do Índice Sazonal Mensal por Razão Ano a Ano
- **Declaração Mandatória:** O índice de cada mês do calendário (1 a 12) DEVE ser calculado pela média das razões relativas disponíveis para aquele mês nos ciclos anuais observados.
- **Procedimento:**
  - Para cada ano de calendário completo ou parcial disponível (ex: 2025 e 2026), calcula-se a média mensal do produto naquele ano específico.
  - Para cada mês $m \in \{1, \dots, 12\}$ com dado presente no ano $a$, define-se a razão $R_{a, m} = z_{a, m} / \bar{z}_a$.
  - O índice sazonal bruto do mês $m$ é a média aritmética das razões $R_{a, m}$ disponíveis (1 ou 2 observações).
  - Normaliza-se o conjunto final dos 12 índices multiplicando por um fator de calibração tal que $\frac{1}{12} \sum_{m=1}^{12} I_m = 1.00$.
- **Interpretação:** $I_m = 1.00$ representa volume normal; $I_m = 1.45$ representa 45% acima da média; $I_m = 0.70$ representa 30% abaixo.

### `P-110`: Consistência Ano a Ano (Correlação YoY)
- **Declaração Mandatória:** O sistema DEVE calcular o coeficiente de correlação de Pearson ($r_{YoY}$) entre as razões mensais dos anos que possuem meses coincidentes (meses 1 a 10 entre 2025 e 2026).
- **Procedimento:**
  - Sejam $u_m = R_{2025, m}$ e $v_m = R_{2026, m}$ para $m \in \{1, \dots, 10\}$.
  - $r_{YoY} = \mathrm{corr}(u, v)$. Se o desvio padrão de $u$ ou $v$ for nulo (série plana), $r_{YoY} = 0.0$.
- **Resultado:** O valor de $r_{YoY}$ fundamenta o diagnóstico de estabilidade do padrão sazonal.

### `P-111`: Classificação da Força da Sazonalidade
- **Declaração Mandatória:** O produto DEVE ser classificado em um de 4 níveis de força:
  1. `FORTE`: $r_{YoY} \ge 0.60$ E amplitude $(I_{\max} - I_{\min}) \ge 0.40$.
  2. `MODERADA`: ($r_{YoY} \ge 0.35$ E amplitude $\ge 0.20$) OU (amplitude $\ge 0.40$ E $r_{YoY} \ge 0.25$).
  3. `FRACA`: Elegível, mas amplitude $< 0.20$ OU $r_{YoY} < 0.25$ (série plana ou sem repetição entre os anos).
  4. `INSUFICIENTE`: Inelegível conforme P-107.

### `P-112`: Nível de Confiança por Mês do Calendário
- **Declaração Mandatória:** Cada um dos 12 meses do calendário DEVE receber uma classificação de confiança transparente:
  - `ALTA`: Mês possui 2 observações com divergência relativa $|R_{2025, m} - R_{2026, m}| / \max(R_{2025, m}, R_{2026, m}) \le 0.35$.
  - `MEDIA`: Mês possui 2 observações, mas divergência relativa $> 0.35$.
  - `BAIXA`: Mês possui apenas 1 observação histórica (típico para novembro e dezembro na base atual de 23 meses).
- **Sinalização Mandatória:** Na interface visual, caso o mês de pico ou vale ocorra em mês com confiança `BAIXA`, um selo de aviso obrigatório DEVE ser exibido alertando que a evidência decorre de um único ano.

### `P-113`: Identificação de Picos e Vales com Agrupamento de Meses Adjacentes
- **Declaração Mandatória:** O sistema DEVE identificar o período de maior venda (pico) e o período de menor venda (vale).
- **Procedimento:**
  - O mês de pico é $m^* = \arg\max I_m$.
  - Meses adjacentes (incluindo a transição circular dez $\leftrightarrow$ jan) que apresentem $I_m \ge 0.90 \times I_{m^*}$ DEVEM ser agrupados no mesmo período de pico (ex: "nov–jan").
  - O mês de vale é $m_* = \arg\min I_m$.
  - Meses adjacentes com índice dentro de $10\%$ da distância entre vale e neutro ($I_m \le I_{m_*} + 0.10 \times (1.0 - I_{m_*})$) DEVEM ser agrupados no período de vale.

### `P-114`: Rankings de Sazonalidade Paginados
- **Declaração Mandatória:** O endpoint de ranking DEVE aceitar o parâmetro `order=most` (mais sazonais) e `order=least` (pouco mensuráveis).
- **Regras de Ordenação:**
  - `order=most`: Produtos elegíveis com força `FORTE` ou `MODERADA`, cuja participação de faturamento seja $\ge MIN\_REVENUE\_SHARE$ (0,05% do total da empresa), ordenados decrescentemente por amplitude de índice sazonal.
  - `order=least`: Produtos ativos com classificação `INSUFICIENTE`, ordenados decrescentemente por faturamento total do produto, informando o motivo estruturado (`HISTORICO_CURTO` ou `VENDA_ESPORADICA`).
- **Paginação:** Suporta `limit` (padrão 50, máx 200) e `offset` (>= 0), retornando metadados `totalItems`, `totalPages`, `page` e `limit`.
- **Nota de Integração no Catálogo:** Além da rota dedicada `/seasonality/ranking` (preservada integralmente), o resumo de sazonalidade de todos os SKUs (`FORTE`, `MODERADA`, `FRACA` e `INSUFICIENTE`) pode ser embutido diretamente na listagem de catálogo (`P-117`) via `includeSeasonality=true`.

### `P-115`: Busca Inteligente de Produtos com Autocomplete
- **Declaração Mandatória:** O sistema DEVE oferecer busca inteligente por código, descrição ou combinação de palavras (incluindo fornecedor) sem exigir recarga de base nem consulta lenta de transações, retornando até `AUTOCOMPLETE_LIMIT` (20) itens ativos na rota de autocomplete.
- **Validação e Normalização:** Em `/products/search`, `q` exige após trim 1 a 60 caracteres se só dígitos e 2 a 60 nos demais casos (`XSL-004`). A busca é insensível a maiúsculas e acentos, trata separadores (`/`, `-`, `+`, `_`, `.`, `,`, `(`, `)`) como espaço mantendo `%`, suporta tokens em ordem ou fora de ordem, combinação descrição + fornecedor e tolerância leve a erro de digitação (Damerau-Levenshtein ≤ 1) apenas para tokens com `len >= 5`.

### `P-116`: Tratamento de Erros e Códigos Internos `SEA-XXX`
- **Declaração Mandatória:** Erros de negócio da feature de sazonalidade DEVEM ser mapeados para códigos estruturados `SEA-XXX`:
  - `SEA-001` (HTTP 404): Produto não encontrado no catálogo ativo ou sem registros de vendas na base.
  - `SEA-002` (HTTP 400): Parâmetros de consulta inválidos (ex: SKU $\le 0$, `order` diferente de `most` ou `least`, `limit` fora do intervalo $[1, 200]$ ou query `q` inválida).
  - `SEA-003` (HTTP 422): Base de dados agregada insuficiente para cálculo de sazonalidade (ex: total de produtos ativos no sistema com histórico $< 20$).

### `P-117`: Listagem Paginada do Catálogo Ativo (`GET /api/v1/analytics/products`)
- **Declaração Mandatória:** O sistema DEVE expor listagem paginada de todo o catálogo ativo em cache (`analytics_cache.get_catalog()`), sem disparar carga das cestas (`_build_snapshot`).
- **Ordenação Padrão e Suportadas:**
  - Padrão (`sortBy=supplier_product`, `sortDir=asc`): `fornecedor` A→Z, depois `descricao` A→Z, desempate por `codigo` ↑.
  - Modos suportados (`sortBy`): `supplier_product`, `product`, `sku`, `stock`, `price`, `relevance` (combinados com `sortDir=asc|desc`).
- **Filtros:**
  - `q` (opcional, até 60 caracteres): aplica a busca inteligente (`P-115`); quando nulo ou vazio após trim, não aplica filtro textual; quando não vazio após trim, aceita inclusive 1 caractere.
  - `supplier` (opcional, até 120 caracteres): filtra pelo fornecedor normalizado.
  - `stockFilter` (`all` | `in_stock` | `out_of_stock`, padrão `all`): filtra todos, com `estoque > 0` ou `estoque <= 0`.
- **Integração Opcional de Sazonalidade (`includeSeasonality`):** Quando `includeSeasonality=false` (padrão), não consulta vendas mensais e os campos sazonais (`forca`, `amplitude`, `mesPico`, `mesVale`, `faturamentoTotal`, `motivoInsuficiencia`) permanecem `null`. Quando `includeSeasonality=true`, utiliza o agregado mensal em cache (`get_monthly_sales()`) para preencher o resumo sazonal de cada SKU do catálogo (inclusive `FRACA` e `INSUFICIENTE`, onde SKUs sem histórico retornam `forca="INSUFICIENTE"`, `motivoInsuficiencia="HISTORICO_CURTO"` e `faturamentoTotal=0.0`).
- **Paginação e Dados:** `limit` padrão `2000` (faixa `1..5000`), `offset` >= `0`. Retorna exclusivamente dados de catálogo e agregados por SKU (`codigo`, `descricao`, `fornecedor`, `estoque`, `precoVenda` e resumo sazonal opcional) no envelope `data` / `meta` (`PagedMeta`), sem dados de cliente (PII).

---

## 4. Enquadramento LGPD & Privacidade

> [!NOTE]
> A feature de Detecção de Sazonalidade por Produto opera exclusivamente sobre dados de produtos (`Externo01.Produto`) e transações agregadas por SKU e Mês (`Externo01.Vendas`).
> **Não há manipulação, projeção nem exposição de nenhum dado pessoal (nem mesmo `Cod Cliente`).**
> Enquadramento: **Bypass de auditoria LGPD dedicada**, com confirmação de ausência de PII pelo revisor de código.

---

## 5. Matriz de Cenários e Edge Cases

| ID | Cenário / Entrada | Comportamento Esperado | Código HTTP |
| :---: | :--- | :--- | :---: |
| **C-01** | SKU com 23 meses e pico evidente e coincidente em março nos dois anos. | Força `FORTE`, pico em março com confiança `ALTA`, amplitude > 0.40. | 200 OK |
| **C-02** | SKU com vendas constantes/planas em todos os meses. | Amplitude ~0, força `FRACA`, sem períodos anômalos. | 200 OK |
| **C-03** | SKU lançado recentemente (10 meses de histórico). | Força `INSUFICIENTE`, motivo `HISTORICO_CURTO`, elegível = falso. | 200 OK |
| **C-04** | SKU antigo (23 meses), mas vendeu em apenas 4 meses espaçados. | Força `INSUFICIENTE`, motivo `VENDA_ESPORADICA` (taxa de atividade < 0.50). | 200 OK |
| **C-05** | SKU com pico aparente em dezembro (apenas 2025 observado). | Pico em dez/jan detectado, porém com selo de confiança `BAIXA`. | 200 OK |
| **C-06** | Mês com 100 vendas e 20 devoluções registradas. | Vendas líquidas computadas como 80 un. (devoluções abatidas). | 200 OK |
| **C-07** | Mês com 10 vendas e 15 devoluções (saldo negativo). | Saldo truncado em 0 un., sem quebra de log ou divisão por zero. | 200 OK |
| **C-08** | SKU inexistente na base ou inativo (`Pc.Venda <= 0`). | Erro `SEA-001` no envelope padronizado. | 404 Not Found |
| **C-09** | Parâmetro `order=invalido` no ranking. | Erro `SEA-002` no envelope padronizado. | 400 Bad Request |
| **C-10** | Ranking `most` filtra produtos irrelevantes (share < 0,05%). | Apenas produtos de relevância comercial figuram no topo. | 200 OK |
