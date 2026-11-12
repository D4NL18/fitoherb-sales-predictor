# Entidade / Feature: Viabilidade de Produto Novo (`analytics-produto-novo`)

> **Localização Mandatória:** `.agents/docs/tasks/analytics-produto-novo.md`  
> **Status:** Etapa 2 concluída (Planejamento, Arquitetura, Modelagem e Design). Bloqueado para Etapa 3 (aguardando índice sazonal de F1).  
> **Responsáveis:** Analista (`analyst.md`), Arquiteto (`architect.md`), AI Specialist (`ai_specialist.md`), Designer (`designer.md`)  
> **Regras Associadas:** `P-139` a `P-149` (em `.agents/docs/business_rules/analytics-produto-novo.md`)  
> **ADR Associada:** `ADR-008` (em `.agents/docs/adr/ADR-008-produto-novo.md`)  
> **Contrato REST:** `.agents/docs/api_contracts/analytics-produto-novo.md`  
> **Design Plan:** `.agents/docs/design/plans/analytics-produto-novo.md`  
> **Parecer de Privacidade:** `.agents/docs/privacy/analytics-produto-novo.md`

---

## 1. Dúvidas Resolvidas e Decisões de Especificação

- **Dúvida 1 (Decisão D2):** Como avaliar um produto que ainda não existe no catálogo do ERP?
  - **Decisão:** A entrada não utiliza SKU. O usuário informa atributos hipotéticos (`tipo`, `fornecedor`, `descricao`, `precoVendaPrevisto`, `custoUnitario`, `margemMinimaDesejada`, `horizonMonths`). O sistema simula o comportamento ancorado em itens históricos equivalentes.
- **Dúvida 2 (Decisão D4):** Como tratar devoluções de vendas no histórico dos similares?
  - **Decisão:** Devoluções (`[Operação] LIKE 'DEVOLU%'`) são abatidas aritmeticamente de quantidade e faturamento no mês em que ocorreram. Se a quantidade líquida do mês resultar negativa, é truncada em 0.
- **Dúvida 3 (Corte de Lançamento Real):** Como evitar que os 1.421 produtos preexistentes no início da base (2025-T1) distorçam a curva de novos produtos?
  - **Decisão:** Adota-se `LAUNCH_CUTOFF_DATE = '2025-04-01'`. Somente produtos cuja primeira venda foi a partir de abril/2025 e que possuem pelo menos 3 meses completos de histórico são considerados para a curva inicial dos similares. Produtos antigos são usados apenas para o `tetoMaduroP75`.
- **Dúvida 4 (Calibração do Haircut Conservador):** Qual o percentil e fator de desconto ideais para atender à premissa de conservadorismo?
  - **Decisão:** Adota-se o percentil 25 ($P25$) multiplicado pelo fator `NEW_PRODUCT_HAIRCUT = 0.70`. Em backtest temporal leave-one-out, essa formulação garante que mais de 80% dos lançamentos reais vendem acima do projetado, conferindo proteção ao estoque.
- **Dúvida 5 (Integração com Sazonalidade F1):** Como aplicar sazonalidade sem risco de distorção por ruído amostral?
  - **Decisão:** O multiplicador sazonal da categoria é limitado estritamente ao intervalo $[0.90, 1.10]$. Se a confiança for `BAIXA` ou se a Fase F1 não estiver ativa, o fator adotado é $1.00$ (neutro). A previsão nunca pode ultrapassar o $P25$ dos similares no mesmo mês.

---

## 2. Tarefas e Etapas de Desenvolvimento

### Tarefa 1: Modelagem e Contrato de API (Endpoints, DTOs e Exceções)
**Descritivo Detalhado:**
Criar os esquemas Pydantic e as rotas HTTP para consulta de opções do catálogo e execução da simulação de viabilidade, seguindo o padrão de envelope `data`/`meta` em camelCase e os códigos de erro `NEW-XXX`.

**Critérios de Aceite:**
- [ ] `GET /analytics/new-product/options` retorna listas deduplicadas e ordenadas de tipos e fornecedores ativos.
- [ ] `POST /analytics/new-product/forecast` aceita os atributos de `P-140` e retorna projeção mensal, similares e indicadores de margem.
- [ ] Erros de validação e de domínio retornam códigos semânticos `NEW-001` a `NEW-005` sem stacktrace.

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 1.1:** Criar `NewProductOptionsResponse`, `NewProductForecastRequest` e `NewProductForecastResponse` em Pydantic v2 com `to_camel`.
- [ ] **Etapa 1.2:** Implementar exceções de domínio `NewProductDomainException` com atributos `code` e `status_code` herdando de `AnalyticsDomainException`.
- [ ] **Etapa 1.3:** Configurar rotas no APIRouter com tags e documentação OpenAPI.

---

### Tarefa 2: Repositório e Agregados no Banco de Dados
**Descritivo Detalhado:**
Implementar consultas agregadas e seguras no SQL Server via `sales_repository.py`, garantindo leitura em blocos, respeito a `is_readonly_query`, e isolamento dos lançamentos reais a partir de `2025-04-01`.

**Critérios de Aceite:**
- [ ] Consulta de lançamentos reais elegíveis traz apenas produtos com $1^{\text{a}}$ venda $\ge 2025-04-01$ e $\ge 3$ meses de histórico.
- [ ] Devoluções são abatidas nas quantidades mensais agrupadas.
- [ ] Nenhuma linha bruta de vendas é carregada para a memória da aplicação.
- [ ] Teto maduro extrai a distribuição de vendas mensais dos produtos pré-existentes ($1^{\text{a}}$ venda $< 2025-04-01$).

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 2.1:** Implementar query agregada `fetch_new_product_candidates(tipo)` no grão `Cod Produto × mês`.
- [ ] **Etapa 2.2:** Implementar query agregada `fetch_mature_product_distribution(tipo)`.
- [ ] **Etapa 2.3:** Integrar com o cache de memória de 6 horas com mecanismo de lock para concorrência.

---

### Tarefa 3: Motor de Similaridade Híbrido (TF-IDF + Fornecedor + Log-Preço)
**Descritivo Detalhado:**
Desenvolver em Python puro (`src/modules/analytics/domain/new_product.py`) a rotina de pontuação multicritério dos produtos candidatos do mesmo `tipo`, selecionando os TOP-10 similares e garantindo o corte mínimo de 3 similares.

**Critérios de Aceite:**
- [ ] Filtragem obrigatória por `tipo` estrito (sem relaxamento silencioso).
- [ ] Cálculo exato dos scores: Fornecedor (0.25), Log-Preço (0.35) e Cosseno TF-IDF (0.40).
- [ ] Se o número de similares for menor que 3, lançar `NEW-001`.
- [ ] Retornar os similares ordenados por score decrescente com justificativas parciais.

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 3.1:** Implementar pré-processamento textual (normalização, remoção de acentos, stop words pt-BR e termos de embalagem).
- [ ] **Etapa 3.2:** Implementar vetorizador TF-IDF e função de similaridade cosseno em `scikit-learn` ou `numpy`.
- [ ] **Etapa 3.3:** Implementar cálculo de proximidade logarítmica de preço $\exp(-|\Delta \ln|)$.
- [ ] **Etapa 3.4:** Composição do score ponderado e seleção de `TOP_K_SIMILARS = 10`.

---

### Tarefa 4: Curva dos Primeiros Meses, Haircut Conservador e Trava de Segurança
**Descritivo Detalhado:**
Extrair o volume líquido dos primeiros 3 meses de vida de cada similar selecionado, calcular o $P25$ mensal e aplicar o fator conservador de 0.70, assegurando matematicamente que a projeção permaneça $\le P25$.

**Critérios de Aceite:**
- [ ] Quantidades líquidas mensais dos similares apuradas nos meses 1, 2 e 3 de vida comercial.
- [ ] Cálculo de $P10$, $P25$, $P50$ e $P75$ maduro.
- [ ] Aplicação de `NEW_PRODUCT_HAIRCUT = 0.70` sobre o $P25$.
- [ ] Assertiva inegociável de que `previsao_conservadora <= P25`.

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 4.1:** Extrair matriz de quantidades relativas $Q_{\text{liq}}(m)$ para $m \in \{1, 2, 3\}$.
- [ ] **Etapa 4.2:** Implementar rotina estatística de cálculo de percentis sem dependência externa pesada.
- [ ] **Etapa 4.3:** Aplicar haircut de 0.70 e trava `min(P25, Q_haircut)`.
- [ ] **Etapa 4.4:** Calcular o `tetoMaduroP75` a partir do agregado de produtos históricos do tipo.

---

### Tarefa 5: Projeções Financeiras e Interface com Sazonalidade (F1)
**Descritivo Detalhado:**
Calcular faturamento projetado, margem bruta nominal e percentual, verificação booleana de `viavel` e modulação opcional pelo índice sazonal de F1 com travas de $[0.9, 1.1]$.

**Critérios de Aceite:**
- [ ] Receita mensal = Quantidade $\times$ Preço de Venda Previsto.
- [ ] Margem Bruta = Quantidade $\times$ (Preço de Venda Previsto - Custo Unitário).
- [ ] Se `margemMinimaDesejada` informada, definir `viavel: true/false`.
- [ ] Consumo desacoplado do serviço de sazonalidade: fallback seguro para 1.00 se ausente ou confiança `BAIXA`.

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 5.1:** Definir interface desacoplada `SeasonalityProvider` com método `get_category_index(tipo, mes_calendario)`.
- [ ] **Etapa 5.2:** Aplicar filtro de amortecimento $[0.90, 1.10]$ e validação de confiança.
- [ ] **Etapa 5.3:** Implementar cálculos de receita, margem bruta e validação de viabilidade.

---

### Tarefa 6: Interface de Usuário Angular (Design Plan e 8 Estados)
**Descritivo Detalhado:**
Criar o componente de tela de viabilidade de produto novo no Angular seguindo o Design Plan e o Design System Papel & Tinta (sem SKU, formulário limpo, gráfico/tabela de faixas, cartão de viabilidade, selo conservador e tratamento dos 8 estados).

**Critérios de Aceite:**
- [ ] Formulário com selects de tipo e fornecedor (alimentados via API) e inputs monetários/percentuais com formatação pt-BR.
- [ ] Gráfico e tabela de projeção apresentando faixas (P10, Conservador, Mediana e Teto Maduro).
- [ ] Cartão de viabilidade com badge destacado (Viável / Margem Abaixo do Esperado) e dados em Overpass Mono.
- [ ] Selo proeminente de "Estimativa Conservadora: calculada para proteger seu estoque".
- [ ] Cobertura dos 8 estados: Inicial, Preenchido Válido, Preenchido Inválido, Carregando (Skeleton), Sucesso, Base Insuficiente (Aviso), Vazio e Erro de Servidor.

**Checklist Técnico (Arquiteto):**
- [ ] **Etapa 6.1:** Desenvolver `NewProductFormComponent` com Signal Forms e validação em tempo real.
- [ ] **Etapa 6.2:** Desenvolver `NewProductResultsComponent` com tabela de faixas e cartão de viabilidade financeira.
- [ ] **Etapa 6.3:** Desenvolver `NewProductSimilarsDrawerComponent` detalhando os similares e os scores parciais.
- [ ] **Etapa 6.4:** Integrar com `AnalyticsService` tipado e tratar estados de erro semântico.

---

## 3. Matriz de Rastreabilidade e Auditoria de Testes (QA / TDD)

| Teste | Regra | Cenário de Validação |
| :--- | :--- | :--- |
| `test_launch_cutoff_exclusion` | `P-139` | Produtos com $1^{\text{a}}$ venda anterior a 2025-04-01 são excluídos da lista de candidatos a similares. |
| `test_min_launch_months` | `P-139` | Lançamento com apenas 2 meses de histórico é desconsiderado para a curva dos 3 meses. |
| `test_input_validation_price` | `P-140` | `precoVendaPrevisto <= 0` retorna HTTP 400 com erro `NEW-004`. |
| `test_input_validation_cost` | `P-140` | `custoUnitario > precoVendaPrevisto` retorna HTTP 400 com erro `NEW-004`. |
| `test_options_endpoint` | `P-141` | Endpoint de opções retorna tipos e fornecedores ativos ordenados alfabeticamente. |
| `test_similarity_score_weights` | `P-142` | Similar idêntico em fornecedor, preço e descrição atinge score 1.00; variação respeita os pesos (0.25, 0.35, 0.40). |
| `test_min_similars_threshold` | `P-143` | Tipo com menos de 3 similares elegíveis lança `NEW-001` (HTTP 422). |
| `test_returns_deduction` | `P-144` | Devoluções reduzem a quantidade líquida do similar; saldo líquido negativo é truncado em 0. |
| `test_conservative_haircut` | `P-145` | Previsão é igual a $P25 \times 0.70$ e nunca excede $P25$. |
| `test_seasonality_damping` | `P-146` | Índice sazonal externo de 1.40 é amortecido para 1.10; índice com confiança BAIXA é ignorado (fator 1.00). |
| `test_mature_ceiling` | `P-147` | Teto maduro reflete o P75 dos produtos antigos do mesmo tipo e é reportado separadamente. |
| `test_financial_margin_viability` | `P-148` | Margem acima da mínima desejada resulta em `viavel = true`; abaixo resulta em `viavel = false`. |
| `test_backtest_calibration` | `P-145` | Backtest sobre lançamentos históricos comprova taxa de sucesso $\ge 80\%$. |
