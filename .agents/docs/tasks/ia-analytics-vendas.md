# Plano de Implementação — Módulo "Analytics Comercial com IA"

| Campo | Valor |
| :--- | :--- |
| **Status** | Proposta com decisões do usuário incorporadas (2026-11-05), aguardando início da Fase 1 |
| **Data** | 2026-11-05 |
| **Módulo novo** | `src/modules/analytics/` (backend) e `frontend/src/app/features/analytics/` (frontend) |
| **Reaproveita** | `modules/pricing/domain/basket_mining.py`, `modules/pricing/domain/elasticity_model.py`, `core/database.py`, padrão de cache de `pricing_service.py` |
| **Regras de negócio** | `.agents/docs/business_rules/analytics-<feature>.md` (IDs P-0XX definidos pelo `analyst` em cada fase) |
| **Contratos de API** | `.agents/docs/api_contracts/analytics-<feature>.md` (envelope `data`/`meta`) |

## 1. Visão geral e ordem das fases

Cada fase é **uma feature completa** (backend + frontend), com branch, testes, Quality Gate e PR próprios. Nenhuma fase depende de uma fase posterior para ser entregue.

| Fase | Feature | Branch sugerida | Depende de |
| :-: | :--- | :--- | :--- |
| 1 | **F4** Recomendação de cross-sell (inclui a fundação do módulo) | `feature/analytics-cross-sell` | nada |
| 2 | **F5** Elasticidade-preço por produto e cliente | `feature/analytics-elasticidade` | Fase 1 (fundação) |
| 3 | **F6** Canibalização e substituição | `feature/analytics-canibalizacao` | Fase 2 (elasticidade); usa Fase 1 como evidência complementar |
| 4 | **F1** Detecção de sazonalidade por produto | `feature/analytics-sazonalidade` | Fase 1 (fundação) |
| 5 | **F3** Churn de clientes (score tempo × faturamento) | `feature/analytics-churn` | Fase 1 (fundação); usa Fase 4 opcionalmente |
| 6 | **F2** Viabilidade de produto novo (conservadora) | `feature/analytics-produto-novo` | Fase 4 (índice sazonal) |

### 1.1 Pontos de atenção da ordem escolhida
- **F6 antes de F1:** a canibalização precisa descontar sazonalidade. Na Fase 3 isso é feito pelo **grupo de controle** (produtos do mesmo `Tipo` não afetados pelo evento, que sofrem a mesma sazonalidade). Quando a Fase 4 existir, o índice sazonal entra só como refinamento opcional, sem mudar o contrato da API.
- **A fundação mora na Fase 1** (repositório, cache, erros, rota e aba do Angular), pois não há fase separada de infraestrutura.

### 1.2 Rota da esteira (AGENTS.md) por fase
Cada fase é uma Categoria A, tipo **T1 (feature full-stack)**, com as exceções abaixo.

| Etapa | Fases 1 a 6 |
| :--- | :--- |
| 1. Descoberta | `analyst` escreve as regras P-XXX da fase (sem `product_owner`, pois o escopo já foi fatiado aqui) |
| 2. Arquitetura | `architect` (contrato da fase) + `designer` (Design Plan da fase) |
| 2. `dba` | **Bypass:** só leitura em views existentes, sem migrations |
| 2. `ai_specialist` | Só onde há modelo estatístico novo (F2, F6); nas demais o motor é determinístico |
| 2/4. `privacy_officer` | **Obrigatório** em F4, F5 e F3 (operam por `Cod Cliente`); bypass em F1, F2, F6 se não expuserem cliente |
| 3. TDD | `tester` escreve os testes antes; `developer` implementa |
| 4. Quality Gate | `reviewer` + `ux_reviewer` (todas, há frontend); `security` só se surgir superfície nova |
| 5. Release | `devops` abre o PR; medir o pico de memória do Cloud Run |

---

## 2. Decisões e fatos que valem para todas as fases

### 2.1 Decisões do usuário (2026-11-05)
| # | Decisão |
| :-: | :--- |
| D1 | **Churn:** cliente sem comprar há **60 dias** é considerado em risco. A priorização combina **tempo sem comprar** e **faturamento médio mensal** numa única métrica (Fase 5). |
| D2 | **Produto novo não está cadastrado.** A feature responde "vale a pena incluir este produto?". A entrada são atributos hipotéticos, não um SKU (Fase 6). |
| D3 | **Um cliente = um único `Cod Cliente`.** Sem tratamento de filiais. |
| D4 | **Devoluções são abatidas** de quantidade e valor (§2.3). |

### 2.2 Diagnóstico da base (consulta somente leitura em 2026-11-05)
| Fato | Valor | Consequência |
| :--- | :--- | :--- |
| Período das vendas | 2025-01-07 a 2026-11-05, **~23 meses** | Menos de 2 ciclos anuais completos: afeta F1 e F2 |
| Volume | 824.638 linhas de venda, 3.361 clientes, 1.935 produtos | Agregar no SQL (§2.4) |
| Meses por ano | 2025: 12 meses; 2026: 11 meses (novembro **incompleto**) | Excluir o mês corrente das séries mensais |
| Devoluções | 2.955 linhas, R$ 380 mil negativos (~0,4% de R$ 95 mi), todas com quantidade negativa | Efeito pequeno, mas obrigatório pela D4 |
| Devoluções com pedido original | 2.857 de 2.955 (97%) | Dá para atribuir a devolução ao cliente e ao produto corretos |
| Lançamentos por trimestre | 1.421 produtos com 1ª venda em 2025-T1; depois ~100 por trimestre | A "1ª venda" dos 1.421 é só o início da base, não um lançamento (§8.1) |
| Clientes por nº de pedidos | 610 com 1-2; 540 com 3-5; 674 com 6-11; 1.537 com 12+ | Clientes com poucos pedidos não têm ritmo próprio medível |
| Clientes sem comprar há > 60 dias | **1.402 de 3.361 (42%)** | Uma regra fixa de 60 dias marcaria quase metade da carteira, então o score de priorização (Fase 5) é indispensável |

### 2.3 Regra de devolução (D4)
- Em `Externo01.Vendas`, devolução é a operação `DEVOLUÇÃO DE VENDA (R)`, com `Qtd Venda` e `Valor Venda` **negativos**. Filtrar por `[Operação] LIKE 'DEVOLU%'` (o acento aparece corrompido no driver ODBC atual, então não comparar a string completa).
- **Quantidade e faturamento líquidos** = soma de `VENDA` + devoluções. Valem para F1, F2, F5, F6 e para o faturamento do cliente em F3.
- **Cestas (F4) e recência (F3) usam só `VENDA`:** uma devolução não é uma compra, não co-ocorre com outro item e não "renova" o cliente.
- Quantidade líquida mensal ≤ 0 num produto vira 0 na série e é sinalizada, para não gerar logaritmo inválido em F5.
- O código existente de `pricing` e `inventory` filtra só `VENDA`. Alterá-lo está **fora do escopo** deste plano; registrar como dívida técnica no `STATE.md`.
- Constante única `RETURN_OPERATION_PATTERN = 'DEVOLU%'` no repositório, coberta por teste com devolução na série.

### 2.4 Estrutura do módulo (mesmo padrão de `pricing` e `inventory`)
```
src/modules/analytics/
├── api/         router.py, schemas.py          # só recebe, chama service, devolve
├── service/     analytics_service.py           # orquestra cache + domínio
├── domain/      cross_sell.py, elasticity.py, cannibalization.py,
│                seasonality.py, churn.py, new_product.py   # regra pura, sem I/O
└── repository/  sales_repository.py            # única camada que fala com o banco
```
O domínio não importa `pyodbc` nem `core.database`. O router é registrado em `src/api.py` com `prefix="/api/v1"`; cada feature usa `/analytics/<feature>`. Cada fase só cria os arquivos de sua feature.

### 2.5 Agregar no SQL Server, não no Python
O Cloud Run já estourou 2Gi com vendas brutas (commits `#5` e `#6`). O repositório nunca traz linhas por item; cada query agregada passa por `is_readonly_query`. Nenhuma query de agregado usa `CONCAT` (a versão do servidor não o reconhece): usar `CAST` e `+`. Cada fase adiciona só o seu agregado:

| Agregado | Grão | Fase |
| :--- | :--- | :-: |
| `order_baskets` (já existe em `basket_mining`, só `VENDA`) | `Pedido` × `Cod Produto` | 1 |
| `price_points` (líquido de devoluções) | `Cod Produto` × `Cod Cliente` × mês: preço médio, qtd | 2 |
| `promo_calendar` | `Cod Produto` × `Cod Promocao` × mês | 2, 3 |
| `monthly_sales` (líquido) | `Cod Produto` × mês | 3, 4, 6 |
| `customer_orders` | `Cod Cliente` × data do pedido (só `VENDA`) | 5 |
| `customer_monthly_revenue` (líquido) | `Cod Cliente` × mês | 5 |

Séries mensais **excluem o mês corrente** (parcial) e sempre preenchem meses sem venda com 0 dentro do intervalo do produto.

### 2.6 Cache e concorrência
Reaproveitar o padrão de `get_cached_base_data` do `pricing_service`: cache em memória com lock (requisições simultâneas não recarregam a base em paralelo), TTL de 6 h e `force_reload` manual. Cálculos pesados (FP-Growth, decomposição, ajuste por cliente) rodam **sob demanda** e são cacheados por chave.

### 2.7 Contrato de API
- Todo 2xx no envelope `{ "data": ..., "meta": { "timestamp", "page", "total" } }`, em `camelCase`.
- Listas sempre paginadas (`limit` padrão 50, máximo 200, e `offset`), com `totalItems` e `totalPages`.
- Erros de domínio com código interno `TRES_LETRAS-NUMERO` (prefixos: `XSL` cross-sell, `ELA`, `CAN`, `SEA`, `CHU`, `NEW`) e HTTP semântico (`404` inexistente, `422` histórico insuficiente, `400` validação). Exceções herdam de `AnalyticsDomainException` e são traduzidas pelo handler global, sem `try/catch` por rota.

### 2.8 Privacidade (LGPD)
`Cod Cliente` identifica empresas, mas pode apontar sócios de pequenos comércios. Nenhuma tela mostra nome, documento ou endereço; não logar DataFrames nem payloads de cliente (só contagens); o `privacy-officer` revisa as fases que operam por cliente.

### 2.9 Convenções de código
Early return, funções de até ~30 linhas, no máximo 3 parâmetros (senão DTO), sem números mágicos (constantes no topo de cada módulo de domínio), docstring de topo em todo arquivo e comentários explicando o *porquê*. No Angular, sem `any`; componentes só desenham e a lógica fica nos services.

### 2.10 Estratégia de testes (TDD, vale para todas as fases)
O `tester` escreve os testes antes do código, em `tests/analytics/`. O domínio é testado com DataFrames sintéticos (sem banco); o repositório com conexão mockada. Cada fase tem um **critério de aceite quantitativo** (backtest ou dado sintético com resposta conhecida). Todo teste de série inclui uma devolução, para garantir o abatimento. Frontend: testes de componente com serviço mockado, cobrindo carregando, vazio e erro.

---

## 3. Fase 1 — F4: Recomendação de cross-sell (e fundação do módulo)

**Objetivo:** dizer "quem compra A leva B" por produto e "o que oferecer" por cliente. É a fase de maior retorno por esforço, pois o `basket_mining` já existe.

### 3.1 Tarefas de fundação (comuns ao módulo)
1. Criar a estrutura de §2.4 e registrar o router em `src/api.py`.
2. `sales_repository.py` com a primeira query agregada, a regra de somente leitura e a constante `RETURN_OPERATION_PATTERN`.
3. Cache com lock e TTL (§2.6).
4. `AnalyticsDomainException`, códigos internos e mapeamento no handler global.
5. Schemas base `ResponseMeta` e `PagedMeta`.
6. Frontend: rota `/analytics` (lazy) com abas, item na navbar e `analytics.service.ts` tipado.

### 3.2 Comportamento da feature
Dois modos: **por produto** e **por cliente**. Cestas usam só `VENDA` (§2.3).

### 3.3 Algoritmo
1. **Reuso:** `build_basket_matrix` e `mine_association_rules` (FP-Growth sobre matriz esparsa) já geram suporte, confiança e lift. Cachear as regras junto da base.
2. **Regras úteis:** `lift ≥ 1.2` e `confidence ≥ MIN_CONFIDENCE`; excluir pares triviais (itens que quase todo pedido leva).
3. **Por cliente:** pegar os produtos que o cliente compra, aplicar as regras e propor os consequentes que ele **não compra** (ou não compra há `DORMANT_DAYS`). Pontuar por `lift × confiança × margem unitária` (`Pc.Venda` e `Pc.Ultimo Custo`).
4. **Viabilidade:** não recomendar produto com `Estoque ≤ 0` nem margem negativa.
5. **Aceite:** *hit rate@5* em backtest temporal (aprender até o mês N−1 e ver se o cliente comprou o recomendado no mês N).

### 3.4 API
`GET /analytics/cross-sell/product/{sku}` e `GET /analytics/cross-sell/customer/{customerCode}?limit=`.

### 3.5 Frontend
Duas abas: busca de produto ("em 34% dos pedidos com A também há B", com lift e confiança em linguagem simples) e busca de cliente (lista priorizada, com o motivo de cada sugestão).

### 3.6 Testes
Associação plantada (A→B) é recuperada; pares triviais filtrados; produto sem estoque não é sugerido; devolução não cria co-ocorrência; paginação; envelope e códigos de erro da fundação; cache sob concorrência (uma única carga).

### 3.7 Pronto quando
`hit rate@5` do backtest medido e reportado; aba "Cross-sell" funcional; `GET /analytics/health` responde no envelope; revisão de privacidade aprovada.

---

## 4. Fase 2 — F5: Elasticidade-preço por produto e por cliente

**Objetivo:** mostrar quanto o volume cai quando o preço sobe, por produto e por par produto × cliente, e simular um reajuste.

### 4.1 Algoritmo
1. **Reuso:** `estimate_log_log_elasticity` e `calculate_temporal_decay_weights` de `elasticity_model.py` (regressão log-log, meia-vida de 100 dias).
2. **Dados:** `price_points` com quantidade e valor **líquidos de devolução** (preço médio = valor líquido ÷ quantidade líquida; descartar linhas com quantidade líquida ≤ 0). **Separar o efeito de promoção** (`Cod Promocao`) para não confundir desconto promocional com sensibilidade de preço.
3. **Hierarquia (shrinkage):** a elasticidade do par é uma média ponderada entre a do cliente-no-produto e a do produto, com peso `n / (n + K_SHRINKAGE)`. Poucos dados ficam perto da elasticidade do produto; sem dado nenhum do produto, usa o padrão `-1.2` já existente.
4. **Qualidade:** exigir variação mínima de preço e `MIN_OBS`; reportar **intervalo de confiança** e **R²**. Valor positivo ou implausível (> 0 ou < −6) é marcado `NAO_CONFIAVEL` e substituído pelo padrão.
5. **Simulador:** `Δvolume% ≈ elasticidade × Δpreço%`, com `Δreceita` e `Δmargem` usando `Pc.Ultimo Custo`.
6. **Classes:** `ELASTICO` (< −1) e `INELASTICO` (−1 a 0); destacar os inelásticos de alta margem como candidatos a reajuste.

### 4.2 API
`GET /analytics/elasticity/product/{sku}`, `GET /analytics/elasticity/product/{sku}/customer/{customerCode}` e `POST /analytics/elasticity/simulate` com `{ "sku", "customerCode?", "priceChangePct" }`.

### 4.3 Frontend
Ficha do produto (elasticidade, intervalo, confiança), tabela dos principais clientes do produto com a elasticidade de cada um e simulador com controle deslizante de variação de preço (volume, receita e margem). Selo "baixa confiança" quando aplicável.

### 4.4 Testes
Elasticidade sintética conhecida (−2.0) recuperada dentro da tolerância; preço constante cai no padrão; shrinkage aproxima do valor do produto com poucas observações (propriedade monotônica); valor positivo é rejeitado; devolução reduz a quantidade líquida do mês.

### 4.5 Riscos
Preço de distribuidora muda em degraus e por tabela de cliente, então a variação natural pode ser pequena. Com ~23 meses, há no máximo 22 pontos mensais por produto. A transparência da confiança faz parte da entrega.

### 4.6 Pronto quando
Teste sintético passa, a tela mostra confiança em todo resultado e o `privacy-officer` aprova a visão por cliente.

---

## 5. Fase 3 — F6: Canibalização e substituição

**Objetivo:** dado um produto em promoção, com preço alterado ou recém-lançado, mostrar quais outros perderam ou ganharam volume e se o **efeito líquido** compensa.

### 5.1 Algoritmo
1. **Candidatos a substitutos:** produtos do mesmo `Tipo` e/ou com compradores em comum acima de um limiar (Jaccard entre conjuntos de clientes).
2. **Eventos:** início de promoção (`promo_calendar`), mudança de preço ≥ `MIN_PRICE_CHANGE_PCT` ou lançamento real de produto (definição de §8.1).
3. **Efeito (diferença em diferenças):** compara a venda líquida do candidato antes e depois do evento contra um **grupo de controle** (produtos do mesmo `Tipo` não afetados). O controle já neutraliza a sazonalidade, o que torna a Fase 4 desnecessária aqui. `canibalização = esperado − observado`.
4. **Classificação:** `CANIBALIZACAO` (candidato cai e o evento sobe), `COMPLEMENTO` (ambos sobem; reaproveita as regras da Fase 1) e `SEM_EFEITO`.
5. **Efeito líquido:** `Δ do alvo + Σ Δ dos afetados`, em quantidade e em margem; responde "a promoção valeu a pena?".
6. **Reaproveitamento da Fase 2:** usar a elasticidade para separar quanto da queda do substituto é efeito de preço do alvo.
7. **Rigor estatístico:** bootstrap ou teste t com correção para múltiplas comparações; só reportar efeitos acima de `MIN_EFFECT_SIGNIFICANCE`, evitando falsas descobertas com centenas de candidatos.
8. **Evolução futura (após a Fase 4):** subtrair o índice sazonal de F1 do "esperado" como refinamento opcional.

### 5.2 API
`GET /analytics/cannibalization/{sku}?eventType=promo|price|launch` e `GET /analytics/substitution/{sku}`.

### 5.3 Frontend
Linha do tempo com o evento marcado, tabela de produtos afetados (tipo de efeito, Δ em unidades e margem) e cartão de efeito líquido (por exemplo, "+1.200 un., mas −900 em Y e Z: ganho líquido de 300 un. e −R$ 2.100 de margem").

### 5.4 Testes
Canibalização plantada (−40% em B quando A entra em promoção) é detectada; complemento plantado classifica como `COMPLEMENTO`; ruído puro não gera falsos positivos acima do esperado; produto sem eventos devolve lista vazia, não erro.

### 5.5 Pronto quando
Cenários sintéticos passam, o efeito líquido é calculado em quantidade e margem e a taxa de falso positivo em ruído puro está medida.

---

## 6. Fase 4 — F1: Detecção de sazonalidade por produto

**Objetivo:** buscar um produto por código ou nome e mostrar o gráfico mensal, o período de maior e menor venda e os rankings de mais sazonais e menos mensuráveis.

### 6.1 Limite real da base
Há ~23 meses, então cada mês do calendário aparece **no máximo duas vezes** (janeiro a outubro em 2025 e 2026; novembro só com 2025 completo; dezembro só com 2025). A decomposição clássica com média móvel de 12 meses perderia 6 meses em cada ponta e deixaria ~11 pontos úteis, o que é insuficiente. O método abaixo é desenhado para 2 observações por mês e **declara a confiança** em vez de fingir precisão.

### 6.2 Comportamento
- **Busca** por código ou `Descricao` (contém, sem acento e sem maiúsculas), com autocomplete de até 20 resultados.
- **Produto escolhido:** gráfico de vendas líquidas por mês (quantidade e faturamento), mês de maior e de menor venda, **índice sazonal** por mês, **força** e **confiança**.
- **Rankings:** produtos mais sazonais e, em lista à parte, os **menos mensuráveis** (histórico curto, esparso ou ruidoso), com o motivo.

### 6.3 Algoritmo
1. Série mensal líquida por produto (sem o mês corrente), com meses sem venda preenchidos com 0.
2. **Elegibilidade:** `MIN_MONTHS_FOR_SEASONALITY = 18` meses completos desde a primeira venda e `MIN_ACTIVE_MONTHS_RATIO = 0.5`. Quem não passa vai para "pouco mensurável" com motivo (`HISTORICO_CURTO` ou `VENDA_ESPORADICA`).
3. **Índice sazonal por razão ano a ano:** para cada ano, `razão_mês = venda do mês ÷ média mensal daquele ano`; o índice do mês do calendário é a média das razões disponíveis (1 ou 2). `1.0` é normal e `1.4` é 40% acima. Como o ano de 2025 pode ter tendência de crescimento, remover antes uma tendência linear da série.
4. **Consistência entre anos:** para os meses com 2 observações, medir a concordância das razões de 2025 e 2026 (correlação dos índices dos 10 meses em comum). É o que sustenta a **força**: `FORTE` exige correlação ≥ `MIN_YOY_CORRELATION` (0.6) **e** amplitude do índice relevante.
5. **Confiança por mês:** `ALTA` (2 observações concordantes), `MEDIA` (2 observações divergentes) e `BAIXA` (1 observação: novembro e dezembro). O pico ou o vale em mês de confiança `BAIXA` é exibido com selo.
6. **Pico e vale:** meses de maior e menor índice, agrupando meses adjacentes com índice ≥ 90% do pico (por exemplo, "nov–jan").
7. **Classes:** `FORTE`, `MODERADA`, `FRACA` e `INSUFICIENTE`. Limites em constantes, calibrados com os dados reais antes do release. A base de 2 anos será ampliada automaticamente conforme novos meses entrarem; a lógica já usa "todas as observações disponíveis" do mês.
8. **Ranking:** ordenar por força, mas só incluir produtos acima de `MIN_REVENUE_SHARE` do faturamento, para o topo não ser dominado por itens irrelevantes.

### 6.4 API
| Método | Rota | Retorno |
| :-- | :-- | :-- |
| GET | `/analytics/products/search?q=` | Lista curta (código, descrição) |
| GET | `/analytics/seasonality/{sku}` | Série mensal, índices, pico/vale, força, confiança por mês |
| GET | `/analytics/seasonality/ranking?order=most\|least&limit=&offset=` | Ranking paginado, com motivo nos "pouco mensuráveis" |

### 6.5 Frontend
Autocomplete; gráfico mensal com pico e vale destacados e linha do índice 1.0; cartões "maior venda / menor venda / força"; selo de confiança nos meses com 1 observação; duas tabelas (mais sazonais e menos mensuráveis) que, ao clicar, abrem o produto no gráfico. Estados: skeleton, vazio, erro e "histórico insuficiente" com explicação.

### 6.6 Testes
Série sintética de 23 meses com pico plantado em março (2 observações concordantes); série plana (força ≈ 0); série com 10 meses cai em `INSUFICIENTE`; pico só em dezembro recebe confiança `BAIXA`; produto sem venda; busca com acento; devolução abatida no mês.

### 6.7 Integrações ao concluir
Expor o índice sazonal como função de domínio reutilizável (consumida pela Fase 6, e opcionalmente por F6 e F3).

### 6.8 Pronto quando
Para um produto de sazonalidade conhecida pelo comprador, o mês de pico bate com a expectativa, e meses com pouca evidência estão claramente sinalizados.

---

## 7. Fase 5 — F3: Churn de clientes com score de prioridade

**Objetivo:** listar clientes parados, ordenados por uma **métrica única que combina há quanto tempo não compram e quanto faturam em média**, para atacar primeiro quem mais vale.

### 7.1 Regras de negócio (D1 e D3)
- **Em risco de churn:** `diasSemComprar ≥ 60`, contados a partir do último pedido de `VENDA` (devolução não conta como compra).
- **Referência individual:** `diasReferencia = max(60, GAP_MULTIPLIER × gapTipico)`, onde `gapTipico` é a mediana do intervalo entre pedidos do cliente (exige ≥ 3 pedidos; senão `diasReferencia = 60`) e `GAP_MULTIPLIER = 1.5`. Isso evita marcar como perdido quem compra de forma legítima a cada 2 ou 3 meses; para a maioria, vale a regra simples dos 60 dias.
- **Um cliente = um código** (D3), então não há agrupamento de filiais.
- **Faturamento líquido de devoluções** (D4).

### 7.2 A métrica: Score de Prioridade de Retenção
```
fatorTempo      = min( diasSemComprar / diasReferencia , FATOR_TEMPO_MAX )     # FATOR_TEMPO_MAX = 2.0
faturamentoMedioMensal = faturamento líquido dos últimos 12 meses completos ÷ meses ativos
                         (meses desde o 1º pedido, no mínimo 3 e no máximo 12)
scorePrioridade = faturamentoMedioMensal × fatorTempo                          # em R$
```
- `fatorTempo` vale 1.0 exatamente na fronteira (60 dias, para a maioria) e cresce até 2.0 (cerca de 120 dias), quando a urgência para de aumentar, porque cliente parado há muito tempo é mais difícil de recuperar.
- O score é um **valor em R$**: "receita mensal ponderada pela urgência". Um cliente de R$ 50 mil/mês parado há 70 dias (`50.000 × 1,17 ≈ 58 mil`) fica muito acima de um de R$ 2 mil/mês parado há 120 dias (`2.000 × 2,0 = 4 mil`).
- **Status** pelo `fatorTempo`: `SAUDAVEL` (< 0,5), `ALERTA` (0,5 a < 1), `EM_RISCO` (≥ 1). Clientes com `diasSemComprar > DIAS_INATIVO_ANTIGO` (180) saem do ranking principal e vão para a lista "inativos antigos (recuperação)", ordenada pelo mesmo faturamento médio.
- **Clientes com menos de 3 pedidos:** entram, mas com selo "histórico curto" e `faturamentoMedioMensal` calculado no mínimo de 3 meses, para um pedido grande isolado não inflar o score.
- Os parâmetros (`60`, `1.5`, `2.0`, `180`) ficam em constantes e são ajustáveis sem mudar a lógica.

### 7.3 Explicabilidade
Cada linha mostra os componentes do score: dias sem comprar, dias de referência, faturamento médio mensal, e os motivos ("intervalo habitual 12 dias, parado há 41", "faturamento dos últimos 3 meses caiu 38% contra os 3 anteriores", "deixou de comprar as linhas X e Y").

### 7.4 Aceite (backtest)
Cortar a base 60 dias atrás, calcular o score e verificar quem comprou nos 60 dias seguintes. Métricas: (a) **precisão** dos clientes `EM_RISCO` que de fato não voltaram; (b) **receita capturada** nos 100 primeiros do ranking comparada a uma ordenação só por dias parados; (c) fatia de faturamento dos clientes A coberta. O score deve capturar mais receita em risco que a ordenação simples; esse é o critério.

### 7.5 API
`GET /analytics/churn/customers?status=EM_RISCO&limit=&offset=` (ordenado por `scorePrioridade`), `GET /analytics/churn/customers/{customerCode}` (histórico mensal e produtos perdidos) e `GET /analytics/churn/inactive` (inativos antigos).

### 7.6 Frontend
Tabela por score com colunas de dias sem comprar, faturamento médio mensal e score, chips de status, filtros, painel lateral do cliente (faturamento mensal e produtos perdidos) e exportação CSV para vendas (sem envio automático). Cartão de topo: "N clientes em risco somam R$ X de faturamento mensal médio".

### 7.7 Testes
Cliente grande parado há 70 dias fica acima de cliente pequeno parado há 120; cliente trimestral com 70 dias sem comprar não é `EM_RISCO` (referência individual); `fatorTempo` respeita o teto; cliente com 1 pedido recebe selo de histórico curto; devolução não renova a recência e reduz o faturamento; > 180 dias vai para a lista de inativos.

### 7.8 Riscos
Cliente sazonal parece churn fora de temporada: usar o índice da Fase 4 quando disponível, senão marcar "possível sazonal". Com 42% da carteira parada há mais de 60 dias, validar com o time de vendas se esse volume é plausível ou se há clientes de compra muito eventual (610 têm só 1 ou 2 pedidos).

### 7.9 Pronto quando
Backtest reportado superando a ordenação simples, regra de 60 dias e score validados com vendas e o `privacy-officer` aprova.

---

## 8. Fase 6 — F2: Viabilidade de produto novo (conservadora)

**Objetivo:** responder "vale a pena incluir este produto?". O usuário descreve um produto **que não existe no catálogo** (D2) e recebe uma previsão conservadora de vendas, receita e margem nos primeiros meses, ancorada em lançamentos reais parecidos.

### 8.1 O que é um "lançamento real" na base
A primeira venda de 1.421 produtos cai em 2025-T1 porque a base começa em janeiro de 2025; esses produtos já existiam e **não** servem como exemplo de lançamento. Definição:
- **Lançamento real** = produto cuja primeira venda é **a partir de 2025-04-01** (`LAUNCH_CUTOFF_DATE`, três meses depois do início da base), o que dá ~500 produtos.
- **Elegível para a curva** = lançamento real com pelo menos `MIN_LAUNCH_MONTHS = 3` meses completos desde a primeira venda (~450 produtos).
- Produtos antigos servem só como **teto de referência** (venda de produto maduro do mesmo `Tipo`), nunca como base da previsão.

### 8.2 Entrada (sem SKU)
```json
{
  "tipo": "…", "fornecedor": "…", "descricao": "…",
  "precoVendaPrevisto": 0.0, "custoUnitario": 0.0,
  "margemMinimaDesejada": 0.0,
  "horizonMonths": 3
}
```
`tipo` e `fornecedor` vêm de listas existentes no catálogo (`GET /analytics/new-product/options`); `descricao` é texto livre; `custoUnitario` e `margemMinimaDesejada` são opcionais, e sem eles a resposta traz só volume e receita.

### 8.3 Algoritmo
1. **Similares:** entre os lançamentos elegíveis, filtrar pelo mesmo `Tipo` e pontuar por (a) mesmo `Fornecedor`, (b) proximidade de `precoVendaPrevisto` ao `Pc.Venda` do lançamento (escala log) e (c) similaridade TF-IDF entre a `descricao` informada e a do lançamento. Usar os `TOP_K_SIMILARS = 10`, com mínimo `MIN_SIMILARS = 3`; abaixo disso responder `422` (`NEW-001`) em vez de chutar. Se o `Tipo` tiver poucos lançamentos, avisar e não relaxar o filtro em silêncio.
2. **Volume dos primeiros meses:** para cada similar, a quantidade líquida (devolução abatida) nos meses 1 a 3 desde a primeira venda. Usa-se volume absoluto, pois o produto novo não tem histórico próprio, e só 3 meses são exigidos, o que a base comporta.
3. **Nível conservador:** previsão do mês *n* = **percentil 25** dos similares naquele mês *n*, vezes o fator de desconto `NEW_PRODUCT_HAIRCUT = 0.7`. Garantia no código: a previsão nunca excede o P25 dos similares no mesmo mês, logo o novo **começa abaixo dos similares por construção**.
4. **Sazonalidade:** multiplicar pelo índice da Fase 4 do `Tipo`, limitado a `[0.9, 1.1]` (faixa estreita, porque o índice tem apenas 2 anos de evidência) e ignorado quando a confiança do mês é `BAIXA`.
5. **Resultado financeiro (opcional):** receita = quantidade × `precoVendaPrevisto`; margem bruta = quantidade × (`precoVendaPrevisto` − `custoUnitario`). Se `margemMinimaDesejada` for informada, devolver `viavel: true|false` no cenário conservador e o volume mínimo mensal para atingir o ponto de equilíbrio da margem desejada.
6. **Faixa e teto:** devolver `p10`, previsão conservadora e mediana dos similares, mais o **teto de referência** do `Tipo` (P75 de produtos maduros). O comprador vê o que seria o melhor caso sem tratá-lo como meta.
7. **Calibração do fator (backtest):** usar os lançamentos já elegíveis, esconder os 3 primeiros meses de cada um, prever com os demais similares e comparar. Ajustar `NEW_PRODUCT_HAIRCUT` até que **≥ 80% dos lançamentos vendam acima da previsão**. Esse é o critério objetivo de "conservador".

### 8.4 API
`GET /analytics/new-product/options` (tipos e fornecedores do catálogo) e `POST /analytics/new-product/forecast` (corpo de §8.2). A resposta traz a previsão mensal, o resultado financeiro, os similares usados (com pontuação) e o aviso de conservadorismo.

### 8.5 Frontend
Formulário (tipo, fornecedor, descrição, preço, custo e margem mínima opcionais), gráfico e tabela da previsão com a faixa, lista de similares explicando o "porquê", cartão de viabilidade e o selo "estimativa conservadora: na maioria dos casos espera-se vender mais que isto".

### 8.6 Testes
Propriedade "previsão ≤ P25 dos similares"; menos de 3 similares devolve `NEW-001`; produto antigo (1ª venda em 2025-T1) nunca entra como similar; devolução abatida na quantidade do similar; margem e `viavel` calculados corretamente; backtest automatizado com limiar de 80%.

### 8.7 Riscos
Só `Tipo` e `Fornecedor` classificam o catálogo; se `Tipo` for grosso demais, os similares ficam fracos. Mitigação: peso do preço e da descrição e transparência da lista. Poucos lançamentos em certos `Tipo` resultam em `NEW-001`, que é o comportamento desejado.

### 8.8 Pronto quando
Backtest atinge ≥ 80% dos lançamentos acima da previsão e a tela explica os similares usados e a viabilidade.

---

## 9. Desempenho e custo (Cloud Run)

- Agregação sempre no SQL; nenhuma tabela bruta no Python.
- Cálculos pesados sob demanda e cacheados por chave; nada em lote na subida do servidor.
- Limitar o número de produtos/clientes por request e paginar tudo.
- Medir o pico de memória em cada fase, dentro do limite atual de 2Gi. Esta versão do plano **não adiciona** `statsmodels` nem `lifetimes` (sazonalidade e churn usam cálculos diretos em `pandas`/`numpy`), então não pesa na imagem.

## 10. Riscos transversais

| Risco | Efeito | Mitigação |
| :--- | :--- | :--- |
| Só ~23 meses de histórico | Sazonalidade com 2 observações por mês | Método ano a ano com confiança declarada (§6) |
| 1.421 produtos "nascem" no início da base | Falso lançamento distorceria F2 | `LAUNCH_CUTOFF_DATE` (§8.1) |
| 42% da carteira parada há mais de 60 dias | Lista de churn enorme | Score de prioridade e referência individual (§7) |
| Preço com pouca variação | Elasticidade fraca | Shrinkage, selo de confiança e padrão conservador |
| Devoluções fora do código legado | Inconsistência entre módulos | Dívida técnica registrada; módulo novo já abate |
| Acento corrompido no driver ODBC | Filtro de devolução falharia | `LIKE 'DEVOLU%'` e teste dedicado |

## 11. Premissas assumidas (a confirmar na Etapa 1 de cada fase)

1. **Churn:** a referência individual `max(60, 1,5 × intervalo típico)` e o teto de `fatorTempo` em 2,0 foram escolhidos por mim para equilibrar a regra de 60 dias com clientes de compra mais espaçada. Podem ser simplificados para 60 dias fixos se preferir.
2. **Faturamento médio por mês** é calculado nos últimos 12 meses completos (mínimo 3). Se "faturamento médio" significar outra janela, é só trocar a constante.
3. **Margem mínima** na Fase 6 é opcional e informada pelo usuário; não existe benchmark de margem no banco.
4. **Lançamento real** é a partir de abril de 2025 (§8.1); ajustável.

## 12. Definição de pronto (por fase)

- [ ] Regras P-0XX em `.agents/docs/business_rules/analytics-<feature>.md` e contrato em `.agents/docs/api_contracts/analytics-<feature>.md`
- [ ] Design Plan em `.agents/docs/design/plans/analytics-<feature>.md`
- [ ] Testes escritos antes do código, todos passando, e critério de aceite quantitativo atingido
- [ ] Devolução abatida onde a regra de §2.3 manda, com teste
- [ ] Sem lógica de negócio em controllers, sem `any`, sem números mágicos, funções curtas
- [ ] Envelope `data`/`meta`, listas paginadas, erros com código interno
- [ ] Revisão de privacidade (Fases 1, 2 e 5) e Quality Gate 360 aprovados
- [ ] Pico de memória no Cloud Run medido, abaixo do limite
- [ ] Commits atômicos em Conventional Commits e PR próprio da fase
- [ ] `STATE.md` atualizado com as decisões e bypasses da fase
