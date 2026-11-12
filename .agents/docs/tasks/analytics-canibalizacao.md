# Entidade / Feature: Analytics Comercial — F6 Canibalização e Substituição

Este documento centraliza todo o planejamento técnico, especificações e tarefas de execução da Fase F6 (Canibalização e Substituição de Produtos), atendendo ao plano mestre `.agents/docs/tasks/ia-analytics-vendas.md` (§5) e às regras de negócio `P-128` a `P-138`.

---

## 1. Dúvidas Resolvidas (Especificação & Discovery)

- **Dúvida 1:** Como identificar substitutos sem catálogo de árvore de categorias profunda no ERP legado?
  - **Decisão:** Utilizar o atributo `Tipo` combinado com a similaridade comportamental de compradores عبر Coeficiente de Jaccard ($Jaccard \ge 0.15$ e/ou $\ge 5$ clientes em comum nos últimos 12 meses) conforme `P-128`.
- **Dúvida 2:** Como isolar o efeito da canibalização da sazonalidade natural sem esperar pela entrega da Fase F1 (Sazonalidade)?
  - **Decisão:** Aplicar o método quasi-experimental de **Diferença em Diferenças (DiD)** utilizando como contrafactual um **Grupo de Controle** composto por outros produtos do mesmo `Tipo` que não sofreram alterações de preço nem participaram de promoções no período analisado (`P-131` e `P-132`).
- **Dúvida 3:** Como lidar com dezenas de candidatos a substitutos para não inflar a taxa de falsos positivos?
  - **Decisão:** Aplicar obrigatoriamente a correção estatística de Benjamini-Hochberg (FDR com $\alpha = 0.05$) sobre os p-valores obtidos via Bootstrap/teste-t, além de exigir um corte de relevância prática mínima ($|\Delta V| \ge 5$ unidades) conforme `P-133`.
- **Dúvida 4:** Como classificar lançamentos de novos produtos sem confundir com os produtos que já existiam no início da base?
  - **Decisão:** Seguir o critério de §8.1: somente considerar lançamentos reais com primeira venda a partir de `2025-04-01` (`LAUNCH_CUTOFF_DATE`) e com no mínimo 3 meses completos de vendas (`P-129.3`).
- **Dúvida 5:** Como proceder em relação à dependência com a Fase F5 (Elasticidade)?
  - **Decisão:** A presente fase especifica e desenha os contratos e a arquitetura completa até o Checkpoint da Etapa 2. A implementação (Etapas 3 e 4) aguardará a conclusão da Fase F5 para disponibilizar o cálculo da elasticidade-preço cruzada $\epsilon_{ji}$, operando com degradação graciosa caso F5 esteja temporariamente inativa (`P-136`).

---

## 2. Tarefas e Etapas de Desenvolvimento

---

### Tarefa 1: Identificação de Substitutos e Mineração de Co-compradores (Backend)

**Descritivo Detalhado:**
Desenvolver no domínio (`cannibalization.py`) a lógica de identificação de produtos concorrentes/substitutos a partir de dados históricos do catálogo (`Externo01.Produto`) e de vendas agrupadas por cliente e produto, calculando a matriz de similaridade de Jaccard e aplicando os filtros de poda.

**Critérios de Aceite:**
- [ ] Recuperar produtos do mesmo `Tipo` ativos no catálogo (`P-128.1`).
- [ ] Calcular Coeficiente de Jaccard de clientes dos últimos 365 dias (`P-128.2`).
- [ ] Descartar candidatos com Jaccard $< 0.15$ e menos de 5 compradores em comum (`P-128.3`).
- [ ] Limitar saída aos 20 principais candidatos mais similares (`P-128.4`).
- [ ] Garantir que nenhum `Cod Cliente` seja exposto nos DTOs ou logado (`P-128.5`).

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 1.1:** Criar DTOs de candidatos a substitutos em `schemas.py` (`SubstituteCandidateDTO`, `SubstitutionResponseDTO`).
- [ ] **Etapa 1.2:** Implementar em `cannibalization.py` a função pura `calculate_jaccard_similarity(buyers_target, buyers_candidate)`.
- [ ] **Etapa 1.3:** Implementar algoritmo de ranking e filtro `find_candidate_substitutes(...)`.
- [ ] **Etapa 1.4:** Escrever testes unitários em `tests/analytics/test_substitution_candidates.py` cobrindo casos sintéticos com sobreposição total, parcial e nula.

**Audit (Testes e Validação - QA):**
- [ ] **Cenário 1:** Dois produtos com exatamente a mesma base de 10 compradores devem resultar em Jaccard = 1.0.
- [ ] **Cenário 2:** Produto sem compradores em comum deve retornar Jaccard = 0.0 e ser excluído.
- [ ] **Cenário 3:** Produtos com `Tipo` diferente só entram se tiverem compradores em comum $\ge 5$.

---

### Tarefa 2: Detecção de Eventos e Construção de Séries Temporais Pré/Pós (Backend)

**Descritivo Detalhado:**
Criar a esteira de identificação de eventos comerciais do produto alvo (campanha promocional `promo`, alteração de preço médio $\ge 5\%$ `price`, ou lançamento real `launch`), fatiando as vendas em janelas simétricas pré e pós evento de $W$ semanas (padrão 4 semanas), expurgando o mês corrente incompleto e abatendo devoluções (`[Operação] LIKE 'DEVOLU%'`).

**Critérios de Aceite:**
- [ ] Identificar eventos de promoção a partir do agregado `promo_calendar` (`P-129.1`).
- [ ] Detectar choque de preço $\ge 5\%$ comparando preço médio líquido semanal (`P-129.2`).
- [ ] Validar regra de lançamento real: 1ª venda $\ge 2025-04-01$ e $\ge 3$ meses de histórico (`P-129.3`, `P-129.4`).
- [ ] Construir janelas simétricas $[T_0 - W, T_0 - 1]$ e $[T_0, T_0 + W - 1]$ com preenchimento de zeros para dias sem venda (`P-130`).
- [ ] Abater devoluções algebricamente em quantidade e valor (`P-137.2`).

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 2.1:** Implementar extrator de eventos `detect_product_events(sku, sales_series, promo_calendar)`.
- [ ] **Etapa 2.2:** Implementar gerador de janelas temporais simétricas `build_pre_post_windows(event_date, window_weeks, sales_series)`.
- [ ] **Etapa 2.3:** Integrar com o parser de devoluções no repositório garantindo filtro `LIKE 'DEVOLU%'`.
- [ ] **Etapa 2.4:** Criar testes unitários para detecção de variações de preço e validação da trava de data de lançamento.

**Audit (Testes e Validação - QA):**
- [ ] **Cenário 1:** Produto com primeira venda em fevereiro/2025 submetido com `eventType=launch` deve falhar com erro `CAN-002`.
- [ ] **Cenário 2:** Queda de preço de 10% deve ser detectada como evento `price` (`PRICE_DROP`).
- [ ] **Cenário 3:** Série com devoluções no período deve descontar corretamente o volume líquido.

---

### Tarefa 3: Motor de Diferença em Diferenças (DiD) e Grupo de Controle (Estatística / AI Specialist)

**Descritivo Detalhado:**
Implementar o motor quasi-experimental de Diferença em Diferenças. O motor seleciona produtos do mesmo `Tipo` sem intervenções para formar o grupo de controle categorial, projeta a trajetória contrafactual $\hat{V}_i^{Pos}$ e calcula o efeito causal $\Delta V_i$.

**Critérios de Aceite:**
- [ ] Selecionar grupo de controle com produtos estáveis do mesmo `Tipo` ($N \ge 5$) (`P-131.1`, `P-131.2`).
- [ ] Calcular o fator de expansão/retração macro da categoria $g_{ctrl}$ (`P-131.3`).
- [ ] Calcular contrafactual $\hat{V}_i^{Pos} = V_i^{Pre} \times g_{ctrl}$ e efeito líquido $\Delta V_i = V_i^{Pos} - \hat{V}_i^{Pos}$ (`P-132.1`, `P-132.2`).
- [ ] Prever fallback automático de grupo de controle para a marca/fornecedor se a categoria for pequena (`P-131.4`).

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 3.1:** Implementar selecionador de controle estável `select_control_group(category_products, event_window)`.
- [ ] **Etapa 3.2:** Implementar o algoritmo DiD `estimate_difference_in_differences(target_pre_post, candidates_pre_post, control_group_pre_post)`.
- [ ] **Etapa 3.3:** Criar testes de validação com séries sintéticas onde um choque comum de mercado (+20% em todos os itens) não pode ser classificado como canibalização ou complemento.

**Audit (Testes e Validação - QA):**
- [ ] **Cenário 1:** Cenário neutro (todos os itens sobem 15% pela sazonalidade de Natal) deve acusar $\Delta V_i \approx 0$ (neutralização de sazonalidade bem-sucedida).
- [ ] **Cenário 2:** Substitutos com queda real de 30% em relação ao grupo de controle estável devem acusar efeito DiD negativo com precisão.

---

### Tarefa 4: Rigor Estatístico, Teste de Significância e Correção FDR (Backend / AI Specialist)

**Descritivo Detalhado:**
Adicionar rigor estatístico aos efeitos calculados. Aplicar procedimento de Bootstrap não-paramétrico ou regressão linear com erros robustos para obtenção de p-valores e aplicar a correção de Benjamini-Hochberg para taxa de falsas descobertas (FDR), garantindo que ruído aleatório em centenas de itens não seja rotulado como canibalização.

**Critérios de Aceite:**
- [ ] Estimar variância e p-valores para cada par de comparação (`P-133.1`).
- [ ] Implementar o algoritmo de Benjamini-Hochberg calculando q-valores ($FDR \le 0.05$) (`P-133.2`).
- [ ] Aplicar corte de relevância prática mínima ($|\Delta V_i| \ge 5$ un.) (`P-133.3`).
- [ ] Classificar produtos em `CANIBALIZACAO`, `COMPLEMENTO` e `SEM_EFEITO` (`P-134`).

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 4.1:** Implementar módulo `fdr_correction.py` com o algoritmo de Benjamini-Hochberg.
- [ ] **Etapa 4.2:** Implementar rotina de teste de significância (teste t / bootstrap vetorial).
- [ ] **Etapa 4.3:** Escrever testes de taxa de falsos positivos (FPR) em ruído gaussiano puro (deve respeitar $\alpha \le 0.05$).

**Audit (Testes e Validação - QA):**
- [ ] **Cenário 1:** Testar massa com 50 produtos puramente aleatórios sem canibalização; nenhum produto deve receber classificação significativa após FDR.
- [ ] **Cenário 2:** Produto com $\Delta V = -2$ unidades, mesmo com $p < 0.01$, deve receber `SEM_EFEITO` por corte prático de volume ($< 5$ un.).

---

### Tarefa 5: Efeito Líquido Financeiro e Interface de Elasticidade F5 (Backend)

**Descritivo Detalhado:**
Consolidar os ganhos e perdas em unidades, faturamento líquido e margem de contribuição (R$), avaliando a viabilidade global da ação comercial (`VALEU_A_PENA`, `ILUSAO_DE_VOLUME`, `PREJUIZO_TOTAL`). Desenhar e estruturar a interface para recepção futura da elasticidade cruzada $\epsilon_{ji}$ de F5.

**Critérios de Aceite:**
- [ ] Totalizar $\Delta$ unidades, $\Delta$ receita e $\Delta$ margem em reais (`P-135.1`, `P-135.2`, `P-135.4`).
- [ ] Aplicar margem de custo com fallback de 60% se o custo for ausente (`P-135.3`).
- [ ] Emitir o diagnóstico comercial executivo da ação (`P-135.5`).
- [ ] Projetar a interface abstrata `CrossElasticityProvider` para conexão futura com F5 com tolerância a falha (`P-136`).

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 5.1:** Implementar agregador de impacto financeiro `calculate_net_impact(target_metrics, affected_items, cost_margins)`.
- [ ] **Etapa 5.2:** Definir protocolo e interface de elasticidade `src/modules/analytics/domain/elasticity_interface.py`.
- [ ] **Etapa 5.3:** Mapear envelope de resposta em `schemas.py` com campos de elasticidade opcionais e status de integração.

**Audit (Testes e Validação - QA):**
- [ ] **Cenário 1:** Promoção que vende +500 un. do alvo com margem de R$ 5, mas perde 400 un. de substituto com margem de R$ 10 deve acusar $\Delta M = -R\$ 1.500$ e status `ILUSAO_DE_VOLUME`.
- [ ] **Cenário 2:** Na ausência do serviço de F5, a rota deve responder normalmente com campos de decomposição nulos e status `NAO_INTEGRADO`.

---

### Tarefa 6: Contrato REST, Rotas de API e Tratamento de Exceções CAN-XXX (API Layer)

**Descritivo Detalhado:**
Expor os endpoints `GET /analytics/cannibalization/{sku}` e `GET /analytics/substitution/{sku}` no router de analytics, com envelope `{ "data": ..., "meta": ... }`, validação Pydantic de query parameters e tratamento global mapeando para os códigos `CAN-001` a `CAN-005`.

**Critérios de Aceite:**
- [ ] Registrar rotas com prefixo `/analytics` sob `/api/v1` (`P-138`).
- [ ] Envelope padronizado em `camelCase`.
- [ ] Resposta com códigos semânticos: 404 para produto não encontrado (`CAN-001`), 422 para eventos ou janelas inválidas (`CAN-002`, `CAN-003`), 400 para parâmetros incoerentes (`CAN-004`).
- [ ] Zero vazamento de stacktrace ou queries SQL em respostas de erro.

**Etapas de Execução (Checklist Técnico):**
- [ ] **Etapa 6.1:** Criar schemas de entrada e saída em `api/schemas.py`.
- [ ] **Etapa 6.2:** Declarar exceções de domínio em `domain/exceptions.py` herdando de `AnalyticsDomainException`.
- [ ] **Etapa 6.3:** Conectar rotas em `api/router.py`.
- [ ] **Etapa 6.4:** Escrever testes de integração de API utilizando `TestClient(app)` em `tests/analytics/test_cannibalization_api.py`.

---

### Tarefa 7: Design Plan e Interface do Usuário (Frontend Angular)

**Descritivo Detalhado:**
Especificar o Design Plan completo da feature para o módulo Angular, incluindo:
1. Linha do tempo interativa destacando o evento ($T_0$) e as janelas pré e pós.
2. Tabela de produtos afetados com badges visuais de classificação (`CANIBALIZACAO`, `COMPLEMENTO`, `SEM_EFEITO`), $\Delta$ unidades, $\Delta$ margem e nível de confiança estatística.
3. Card executivo de efeito líquido (Volume líquido, Receita líquida, Margem líquida e Veredito Comercial).
4. Cobertura rigorosa dos 8 estados visuais obrigatórios (Default, Hover/Focus, Loading Shimmer, Empty State, Erro de API, Sem Eventos Elegíveis, Controle Insuficiente e Parâmetro Inválido).

**Critérios de Aceite:**
- [ ] Design Plan formalizado em `.agents/docs/design/plans/analytics-canibalizacao.md`.
- [ ] Aderência estrita aos tokens do `DESIGN_SYSTEM.md` (Papel & Tinta).
- [ ] Zero spinners solitários: especificação de Skeleton Loaders Shimmer.
- [ ] Zero gradientes genéricos ("AI Purple") e copywriting humano direto ao ponto.
