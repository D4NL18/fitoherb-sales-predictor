# Parecer de Privacy by Design: Diagnóstico de Motivos da Tendência de Vendas com IA (F7)

| Campo | Valor |
| :--- | :--- |
| **Feature** | F7 — Diagnóstico de Motivos da Tendência de Vendas com IA (`analytics-tendencia-ia`) |
| **Módulo** | `src/modules/trend_insights/` (novo; consome `sales_trend` e `analytics` por portas) |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **Etapa** | 2 — Revisão leve de Privacy by Design (triagem do Orquestrador) |
| **Responsável** | Encarregado de Dados / DPO (`privacy_officer` / `lgpd-privacy-expert`) |
| **Entradas** | `tasks/ia-tendencia-vendas-motivos.md` (§3.2, §3.5, §3.6, §3.7), `business_rules/analytics-tendencia-ia.md` (P-150..P-187, em especial P-153, P-164, P-167, P-176, P-179, P-185), precedente `privacy/analytics-canibalizacao.md` (LGPD-CAN-01..08), código `cannibalization_report.compute_directional_migration`, `sales_repository.fetch_customer_sku_window_sales`, `analytics_service` (padrão `del raw_rows`), `churn.evaluate_lost_products` |
| **Data** | 2026-11-24 |
| **Conclusão** | **APROVADO COM CONDIÇÕES** (LGPD-TIA-01 a LGPD-TIA-14). RIPD **não exigido**. |

---

## 1. Objeto e escopo da revisão

A F7 explica a variação de vendas **por produto e por fornecedor**. Ela lê `Cod Cliente` só dentro de duas etapas voláteis já existentes ou derivadas (migração da F6 e clientes perdidos), gera agregados por SKU, monta um pacote de evidências e, **somente quando o usuário aperta o botão**, envia esse pacote ao Google Gemini 4 com *grounding* no Google Search. O diagnóstico é salvo em GCS por 90 dias.

A revisão é leve porque o grão da saída é o produto, não a pessoa. O foco é garantir que nenhum dado de cliente atravesse as fronteiras do processo (LLM, busca, GCS, logs, API) e que agregados pequenos não permitam reidentificação.

---

## 2. Mapa do fluxo de dados

| # | Fluxo | Dados | Classificação | Avaliação |
| :-: | :--- | :--- | :--- | :--- |
| F1 | SQL Server → memória (migração) | `Cod Cliente`, `Cod Produto`, qtd e R$ por janela (`fetch_customer_sku_window_sales` + variante de 4 datas, P-153.1) | Pseudonimizado; pessoal quando o cliente é PF/MEI/produtor rural | Igual à F6: colunas mínimas (LGPD-CAN-01), `by_cli` apagado no motor (`del by_cli`, linha 753) e `raw_rows` apagado no serviço (`del raw_rows`). **Atenção:** a função devolve `customer_code` em cada dict; o ajuste por `k` (P-153.2) não pode criar cópia persistente nem guardar `raw_rows` fora do escopo local (LGPD-TIA-02) |
| F2 | Snapshot de churn → memória (clientes perdidos, P-164) | Status de churn por cliente (snapshot F3 já em memória, com nome) | Pessoal derivado de comportamento | Cruzamento volátil; saem só `clientesPerdidosQtd` e soma. `evaluate_lost_products` (lista de SKUs por cliente) **não** deve ser usado na F7, pois trabalha no grão cliente; P-164 define fórmula própria |
| F3 | SQL Server → memória (UF) | `[UF]`, R$/qtd e contagem de clientes distintos por UF | Agregado; reidentificável com poucos clientes | `MIN_CLIENTS_PER_UF = 3` (k-anonimato 3) aceito, com a correção de diferença em LGPD-TIA-05 |
| F4 | Processo → `MigrationSnapshot` em cache (6 h) | Pares A→B com `netRev`, `netClients`, totais por SKU | Agregado sem identificador | Conforme (estrutura imutável já sem `Cod Cliente`) |
| F5 | Processo → **Google Gemini API / Vertex AI** (`POST /generate`) | Pacote P-179: SKU, descrição, fornecedor, categoria, função primária, janelas, cascata, grupo afim, pares agregados, indicadores, UF agregada, trecho da descrição pública da galeria | Sem dado pessoal; **segredo comercial** da Fitoherb | Conforme, com LGPD-TIA-03/04/06 (contagens pequenas em faixa) e LGPD-TIA-08 (modalidade contratual do Google) |
| F6 | Gemini → Google Search (*grounding*) | Consultas montadas pelo backend: função primária, categoria, fornecedor, UF, período | Não pessoal | Conforme (P-180). Proibido incluir nome de cliente ou qualquer texto livre do usuário na consulta |
| F7 | Processo → GCS (diagnósticos, trava em voo, orçamento) | Diagnóstico JSON (mesmo conteúdo agregado + texto do LLM + fontes), chave `(escopo, id, metric, window, baseMonth, comparisonMode, dataReferencia, PROMPT_VERSION)` | Não pessoal, se cumpridas as condições | Conforme com LGPD-TIA-09/10. Chaves de objeto e de trava sem usuário/IP |
| F8 | Processo → API/tela | Cascata, grupo afim, `impactoEmOutrosProdutos` (`clientesMigrados` = contagem) | Agregado | Conforme; rota autenticada (LGPD-CAN-07). Contagens exatas podem aparecer na tela interna (usuários autenticados já veem a Carteira de Churn nominal) |
| F9 | Processo → Cloud Logging | Etapa, latência, modelo, tokens, custo, status, tamanho do pacote, `PROMPT_VERSION` (P-185.2) | Não pessoal | Conforme, com LGPD-TIA-07 (exceções do SDK sanitizadas) e LGPD-TIA-11 (limite por usuário/IP) |

**Constatação:** nenhum dado pessoal sensível (Art. 11) é tratado. Os clientes da Fitoherb são predominantemente comércios que compram para revenda; o fato de um comércio (mesmo de titular PF) comprar fitoterápicos ou suplementos para revenda não revela dado de saúde de pessoa natural. Não há dado de criança ou adolescente.

---

## 3. Reidentificação e o limiar `MIN_CLIENTS_PER_UF`

1. **Valor 3 aprovado.** Para um terceiro (Google) sem acesso à base de clientes, uma contagem agregada por UF sem identificador não reidentifica ninguém. O risco real é interno ou por cruzamento (ex.: "a única farmácia de Roraima que compra o SKU X parou"). k = 3 é o mesmo piso usado na F6 (`DEFAULT_MIN_MIGRATED_CLIENTS`) e é proporcional para um dado comercial não sensível.
2. **Ataque por diferença (lacuna em P-167).** O total de `A` é conhecido. Se só **uma** UF pequena for para "Outras UFs", então `Outras UFs = total − Σ UFs exibidas` revela exatamente aquela UF. Condição LGPD-TIA-05: o grupo "Outras UFs" também precisa somar ≥ 3 clientes; senão, a menor UF exibida é absorvida no grupo até atingir o piso, ou a quebra regional inteira é suprimida (`REGIONAL` = `NAO_AVALIADO`, motivo `ANONIMIZACAO`).
3. **Dominância.** Uma UF com 3 clientes em que um deles responde por quase todo o faturamento ainda expõe aquele cliente de forma aproximada. Como o dado é comercial e não sensível, não exijo regra de dominância agora; fica como recomendação (R-02) para reavaliar se a quebra por UF passar a ser exibida em valores absolutos fora do painel.
4. **Contagens pequenas no pacote do LLM.** `netClients`, `clientesMigrados` e `clientesPerdidosQtd` iguais a 1 ou 2, junto com SKU, fornecedor e UF, são minimização insuficiente para um envio externo e não ajudam o LLM (a confiança `BAIXA` já carrega a informação). Condição LGPD-TIA-06: no pacote do LLM, contagens abaixo de 3 vão como faixa `"<3"` (ou só a confiança); a API e o GCS interno podem manter o número exato.

---

## 4. Operador, transferência internacional e confidencialidade

- **Papel do Google:** operador (Art. 5º, VII) do processamento do LLM e da busca. Como o pacote não contém dado pessoal (após LGPD-TIA-03..06), o envio **não configura transferência internacional de dados pessoais** (Art. 33) e não exige cláusulas-padrão da ANPD para esse fluxo. O GCS, se em região fora do Brasil, armazenaria só agregados; mesmo assim recomenda-se `southamerica-east1` (R-01).
- **O que de fato está em jogo é segredo comercial** (faturamento por SKU, margens em percentual, portfólio). Por isso a modalidade de contratação importa:
  - **Gemini API em nível gratuito:** os termos do Google permitem uso dos dados enviados para melhoria de produtos e revisão humana. **Vedado** (LGPD-TIA-08).
  - **Gemini API paga (projeto com faturamento):** os termos declaram que prompts e respostas não são usados para treinar modelos; há retenção limitada para detecção de abuso, e o *grounding* com Google Search tem retenção própria. Aceitável.
  - **Vertex AI:** termos de serviço do Google Cloud (Cloud Data Processing Addendum), sem uso para treino, controle de região e opções de retenção zero para parte dos recursos. **Recomendado**, por alinhar com a conta GCP onde já ficam Cloud Run, GCS e Secret Manager.
  - Os prazos exatos de retenção e as condições do *grounding* para os modelos Gemini 4 (lançados em 11/2026) DEVEM ser confirmados na documentação oficial antes da Etapa 3 e registrados no ADR-009 (ponto para o checkpoint PC-01).
- **Galeria do fitoherb.com.br:** texto público; sem impacto de privacidade (o risco é de *prompt injection*, tratado em P-184 pelo `security`).

---

## 5. Base legal e LIA

| Tratamento | Base legal | Observação |
| :--- | :--- | :--- |
| Leitura volátil de `Cod Cliente` (migração e clientes perdidos) | Legítimo interesse (Art. 7º, IX c/c Art. 10) | Mesmo LIA de `privacy/analytics-canibalizacao.md` §3.2, que se estende à F7: finalidade (gestão de portfólio, preço e compra), necessidade (migração só é medível no grão cliente; não há meio menos invasivo), balanceamento (nenhuma decisão sobre o cliente, nenhum contato ou preço individual derivado) |
| Status de churn reutilizado | Legítimo interesse | Já tratado e aprovado na F3 (`privacy/analytics-churn.md`); a F7 só consome contagem e soma |
| Envio ao Gemini, busca, GCS | Fora do escopo da LGPD se cumpridas LGPD-TIA-03..06 (sem dado pessoal) | Governado por confidencialidade comercial e contrato com o Google |
| Dados do usuário interno (usuário/IP para limite por minuto, P-176.3) | Legítimo interesse (segurança e controle de custo) | Minimização em LGPD-TIA-11 |

**Transparência (R-03):** o Registro das Operações de Tratamento (ROPA) e o aviso interno de privacidade devem citar o Google como operador de IA da ferramenta de análise. Não há coleta nova de titulares nem consentimento a pedir; não há checkbox ou opt-in na UI (Privacy by Default não se aplica a elementos de tela desta feature).

---

## 6. RIPD/DPIA: não exigido

1. **Sem dado sensível** (Art. 11) — ver §2.
2. **Sem decisão automatizada sobre titular** (Art. 20): a IA explica a venda de produtos e apoia decisões de preço, mix e compra. Nenhum cliente recebe pontuação, preço, oferta ou restrição a partir do diagnóstico.
3. **Sem tratamento novo em larga escala de dado individual:** a F7 reaproveita leituras já aprovadas (F3, F6) e só adiciona a contagem por UF, anonimizada.
4. **O LLM externo não recebe dado pessoal.**

**Gatilhos de reavaliação (exigiriam RIPD):** pacote do LLM passar a conter qualquer dado no grão cliente; investigação agêntica em que o LLM consulte dados internos sozinho (gatilho de LangGraph do plano §3.10) com acesso a portas que leiam cliente; diagnóstico por cliente ou por vendedor; uso do diagnóstico para ação automática sobre clientes.

---

## 7. Retenção e acesso ao GCS

- **90 dias (`INSIGHT_RETENTION_DAYS`) aprovado.** O conteúdo é agregado e não pessoal; o prazo é proporcional à utilidade (Mês-Base recente) e está abaixo de qualquer exigência. A regra de ciclo de vida DEVE ser configurada no bucket (prefixo de diagnósticos), não apenas no código (LGPD-TIA-09).
- **Objetos do mesmo bucket com outra natureza:** a trava em voo (P-176.2) e o acumulado de orçamento (P-178.3) não podem conter usuário, IP ou e-mail; o índice de afinidade (tarefa 7.0 c) é dado de catálogo. Prefixos separados e ciclo de vida próprio para as travas.
- **Acesso:** bucket privado, *Uniform bucket-level access*, *Public Access Prevention* ativo, sem URLs assinadas para a tela (a API lê e devolve), conta de serviço do Cloud Run com o menor papel necessário (`roles/storage.objectUser` restrito ao bucket, não ao projeto), criptografia padrão do Google em repouso (CMEK opcional) e TLS em trânsito.
- **Pessoa física como cliente (pequenos comércios, MEI, produtor rural):** coberta pelo tratamento conservador da F6 (todo `Cod Cliente` tratado como dado pessoal). Como nada no grão cliente sai do processo e as contagens externas pequenas vão em faixa (LGPD-TIA-06), não há caminho para que o titular PF seja identificado pelo Google ou por quem leia o GCS. Direitos do titular (Art. 18) seguem atendidos na origem (ERP); a F7 não cria base nova de cliente a ser apagada.

---

## 8. Condições obrigatórias para a Etapa 4 (`LGPD-TIA-XX`)

Cada condição tem um teste automatizado ou verificação objetiva. O `reviewer` e o `privacy_officer` vetam a entrega se alguma falhar.

| ID | Condição | Verificação |
| :--- | :--- | :--- |
| **LGPD-TIA-01** | A variante de 4 datas do repositório (P-153.1) e a nova query por UF (P-167) selecionam só as colunas necessárias: `[Cod Cliente]`, `[Cod Produto]`, `[Quantidade]`, `[Valor Venda]`, `[Data]`, `[UF]`; nada de nome, CPF/CNPJ, e-mail, telefone ou endereço. A query por UF devolve `COUNT(DISTINCT [Cod Cliente])` por UF, nunca a lista de códigos. Mesma blindagem SQL (parâmetros vinculados) | Teste de repositório que inspeciona o SQL (lista de colunas) e o formato do retorno da query por UF (sem `customer_code`) |
| **LGPD-TIA-02** | Linhas com `customer_code` e o cruzamento cliente × status de churn existem só no escopo local da construção do snapshot; o ajuste por `k` (P-153.2) é feito sem guardar a lista em atributo, cache ou disco, e a lista é apagada (`del`) antes de gravar o cache, seguindo o padrão de `analytics_service` (linha 1341) | Teste que inspeciona o `MigrationSnapshot` da F7 e todo objeto do cache da F7 (serialização recursiva) e falha se encontrar a chave `customer_code` ou atributo `customer`/`cliente` |
| **LGPD-TIA-03** | O pacote do LLM (P-179) é montado por uma função pura com **lista branca** de campos (DTO imutável); nunca por serialização de objetos de domínio inteiros | Teste com base sintética em que os códigos de cliente são valores únicos (ex.: `987654321`); o JSON enviado ao dublê do `LlmClient` não pode conter esses valores nem as chaves `customer`, `cliente`, `codCliente`, `nome`, `cpf`, `cnpj`, `email` |
| **LGPD-TIA-04** | O pacote do LLM não leva `Pc.Ultimo Custo` nem custo unitário; margens só em percentual e mecanismo (P-179) | Mesmo teste de LGPD-TIA-03, checando ausência de campos de custo |
| **LGPD-TIA-05** | UF com menos de `MIN_CLIENTS_PER_UF` (3) clientes vai para "Outras UFs", **e** "Outras UFs" também precisa ter ≥ 3 clientes; senão absorve a menor UF exibida até atingir o piso ou a quebra regional é suprimida (`NAO_AVALIADO`, motivo `ANONIMIZACAO`). Vale para pacote do LLM, API, GCS e consultas de busca | Testes: UF com 2 clientes (C-21); uma única UF pequena isolada (diferença); todas as UFs pequenas (supressão) |
| **LGPD-TIA-06** | No pacote do LLM, `netClients`, `clientesMigrados` e `clientesPerdidosQtd` menores que 3 vão como faixa `"<3"` (ou omitidos, ficando só a `confianca`) | Teste de pacote com par `netClients = 1` |
| **LGPD-TIA-07** | Logs da camada de IA só com os campos de P-185.2. Exceções do SDK `google-genai`, do GCS e do SQL são registradas com tipo, código HTTP/status e etapa; **nunca** `str(exc)`/`repr(exc)` cru do SDK, que pode ecoar o prompt | Teste com `caplog`: dublê do LLM lança erro cuja mensagem contém o pacote; o log capturado não pode conter trechos do pacote nem os códigos de cliente sintéticos |
| **LGPD-TIA-08** | LLM só por **Vertex AI** ou **Gemini API em projeto pago**; proibido o nível gratuito. Chave/credencial no Secret Manager (P-185.4), nunca em log, resposta, `health` ou repositório | Verificação de configuração no `devops` (Etapa 5) e registro da modalidade no ADR-009; teste de `/health` mostrando só booleano da credencial |
| **LGPD-TIA-09** | Diagnóstico salvo no GCS segue lista branca: sem `Cod Cliente`, sem usuário/e-mail/IP de quem gerou. Ciclo de vida de 90 dias configurado no bucket (prefixo dos diagnósticos) | Teste que serializa o objeto gravado pelo dublê do `insight_store` e aplica a mesma varredura de LGPD-TIA-03; verificação da regra de lifecycle no IaC/script de deploy |
| **LGPD-TIA-10** | Bucket privado (Uniform bucket-level access, Public Access Prevention), conta de serviço com papel restrito ao bucket, sem URL assinada exposta à tela. Travas (P-176.2) e acumulado de orçamento (P-178.3) sem identificador de pessoa | Revisão de IaC/deploy pelo `devops` e `security`; teste do formato do nome/conteúdo do objeto de trava |
| **LGPD-TIA-11** | Limite por usuário/IP (P-176.3) mantido em memória ou com identificador em hash com sal e TTL ≤ 1 minuto se precisar ser compartilhado; IP e usuário não entram em log nem no GCS | Teste do limitador (estado não persistido em claro) e do log no caso 429 |
| **LGPD-TIA-12** | Consultas de busca (*grounding*) montadas pelo backend só com função primária, categoria da galeria, fornecedor, UF agregada (LGPD-TIA-05) e período; sem texto livre do usuário e sem dado de cliente | Teste unitário do montador de consultas |
| **LGPD-TIA-13** | Respostas de erro (`TIA-001..005`, `ANL-001`, 500) não ecoam parâmetros, conteúdo do pacote nem resposta do LLM (P-150, P-183.4) | Testes de contrato de erro |
| **LGPD-TIA-14** | Rotas `trend-insights` atrás do middleware de autenticação (como LGPD-CAN-07) | Teste de rota sem credencial → 401 |

---

## 9. Recomendações (não bloqueantes)

- **R-01:** bucket e, se Vertex AI, endpoint do modelo em `southamerica-east1` quando o *grounding* permitir; se não permitir, registrar no ADR-009.
- **R-02:** reavaliar regra de dominância por UF se a quebra regional passar a ser exibida em valores absolutos fora do painel.
- **R-03:** incluir no ROPA e no aviso interno de privacidade o Google como operador de IA da ferramenta.
- **R-04:** o aviso fixo da tela ("Diagnóstico gerado por IA… confira as fontes") atende à transparência; mantê-lo.

---

## 10. Pontos para o checkpoint (divergências com outros artefatos)

- **PC-01 (ADR-009 / `architect` + `devops`):** decidir Vertex AI × Gemini API paga e registrar prazos de retenção e uso para treino, incluindo o *grounding*, conforme documentação oficial do Gemini 4. Nível gratuito vedado.
- **PC-02 (`business_rules` P-167 / P-185.3, `analyst`):** acrescentar a regra de diferença de "Outras UFs" (LGPD-TIA-05). Hoje P-167 só agrega a UF pequena, o que permite deduzi-la quando é a única.
- **PC-03 (`business_rules` P-179, `analyst` / `ai_specialist`):** acrescentar ao "Proibido no pacote" as contagens de clientes abaixo de 3 em valor exato (LGPD-TIA-06).
- **PC-04 (`business_rules` P-176.3 / contrato, `architect`):** definir onde vive o contador por usuário/IP sem persistir IP em claro (LGPD-TIA-11).
- **PC-05 (`business_rules` §4, `analyst`):** a linha "Pacote enviado ao Gemini" pode citar este parecer e a modalidade contratual (PC-01); a classificação "sem dado pessoal" só vale com LGPD-TIA-03..06 cumpridas.
