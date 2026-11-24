# Parecer de Privacy by Design: Analytics Comercial — Canibalização e Substituição (Fase F6)

| Campo | Valor |
| :--- | :--- |
| **Feature** | Canibalização e Substituição de Produtos (`analytics-canibalizacao`) |
| **Módulo** | `analytics` (`src/modules/analytics/domain/cannibalization.py`) |
| **Branch** | `feature/analytics-canibalizacao` |
| **Etapa** | 2: Revisão de Privacy by Design e Parecer Formal de LGPD |
| **Responsável** | Encarregado de Dados / DPO (`privacy_officer.md` / `lgpd-privacy-expert`) |
| **Entradas** | `business_rules/analytics-canibalizacao.md` (`P-128` a `P-138`), `ADR-007-canibalizacao.md`, `api_contracts/analytics-canibalizacao.md` |
| **Data** | 2026-11-12 |
| **Conclusão** | **APROVADO FORMALMENTE COM BYPASS DE RIPD COMPLETO** (Salvaguardas Mandatórias LGPD-CAN-01 a LGPD-CAN-08). |

---

## 1. Contexto e Objeto da Avaliação

A funcionalidade F6 destina-se a analisar o impacto de intervenções comerciais (promoções, alterações de preço e lançamentos) em produtos fitoterápicos, calculando a transferência de vendas entre itens substitutos da mesma categoria via Diferença em Diferenças (DiD).

A avaliação de privacidade tem como foco verificar se o uso de dados transacionais para o cálculo do Coeficiente de Similaridade de Jaccard e para a projeção de séries temporais viola preceitos da Lei Geral de Proteção de Dados (Lei Federal nº 13.709/2018 - LGPD), garantindo os princípios de finalidade, necessidade, transparência e segurança.

---

## 2. Inventário e Classificação dos Dados Tratados

| Dado / Atributo | Origem | Classificação LGPD | Observações de Privacidade |
| :--- | :--- | :--- | :--- |
| `Cod Cliente` | `Externo01.Vendas` | **Dado Pessoal Pseudonimizado** (quando o cliente for pessoa natural, MEI ou produtor rural) | Tratado na pior hipótese como dado pessoal (Art. 13, §4º). É lido **exclusivamente em memória volátil** para contagem de compradores em comum no cálculo de Jaccard ($J = \frac{|C_A \cap C_B|}{|C_A \cup C_B|}$) e imediatamente descartado. **NUNCA exposto na API, NUNCA persistido em cache e NUNCA registrado em logs**. |
| Quantidade de Venda e Preço Líquido | `Externo01.Vendas` | **Dado Transacional Comercial Agregado** | Agrupado por SKU e período de tempo (semanal/mensal). Não permite reidentificação de pessoas físicas. |
| Códigos e Atributos de Produto (`Codigo`, `Descricao`, `Tipo`, `Fornecedor`, `Preco`, `Custo`) | `Externo01.Produto` | **Dado Comercial Não Pessoal** | Informações de catálogo e inteligência de negócios da Fitoherb (fora do escopo da LGPD). |
| Indicadores de Efeito DiD e Margem Líquida | Motor Estatístico do Domínio | **Dado Estatístico Sintético / Agregado** | Resultados derivados anônimos por produto. |

> **Constatação Relevante:** Nenhum dado pessoal sensível (Art. 11), dados de crianças ou adolescentes (Art. 14), dados cadastrais nominais (nomes, CPFs, e-mails, telefones ou endereços) é lido, trafegado ou persistido nesta funcionalidade.

---

## 3. Base Legal e Teste de Ponderação (LIA)

### 3.1 Base Legal Aplicada
**Legítimo Interesse do Controlador (Art. 7º, IX da LGPD c/c Art. 10).**

A distribuidora possui legítimo interesse em compreender a dinâmica concorrencial interna de seu portfólio de produtos para otimizar estoques, planejar compras e assegurar sustentabilidade econômica.

### 3.2 Teste de Ponderação de Legítimo Interesse (LIA)

| Dimensão do Teste | Análise do Encarregado | Parecer |
| :--- | :--- | :--- |
| **1. Finalidade (Legitimidade)** | O tratamento visa quantificar perdas e ganhos comerciais de produtos em virtude de campanhas, atividade essencial de gestão de negócios (Art. 10, I). | **Atende** |
| **2. Necessidade (Proporcionalidade)** | A similaridade entre produtos exige saber se eles atendem à mesma base de clientes. O uso do `Cod Cliente` limita-se estritamente à operação matemática de interseção de conjuntos de inteiros, sem cruzar com hábitos individuais ou gerar relatórios individualizados. | **Atende** |
| **3. Balanceamento (Expectativa do Titular)** | O processamento não gera decisões que afetem direitos do comprador, não altera seus preços individuais e não resulta em contato direcionado ou telemarketing. Os clientes não sofrem impacto adverso. | **Atende** |
| **4. Salvaguardas** | Aplicação rigorosa das regras LGPD-CAN-01 a LGPD-CAN-08 (anti-overfetching, proibição de log, descarte de identificadores). | **Atende** |

---

## 4. Parecer Formal Quanto à Exigência de RIPD/DPIA

### Decisão: **BYPASS DE RIPD COMPLETO HOMOLOGADO**

**Fundamentação Técnica e Jurídica:**
1. A funcionalidade opera no grão de **SKU (Produto)**, e não no grão de cliente.
2. Não há tomada de decisão exclusivamente automatizada que produza efeitos jurídicos ou afete significativamente os interesses do titular (Art. 20).
3. Não há tratamento de dados sensíveis ou em larga escala de dados comportamentais individualizados.
4. Os dados retornados nas APIs e expostos na interface são estritamente estatísticos e agregados.
5. Em conformidade com o Guia Orientativo da ANPD para Agentes de Tratamento de Pequeno Porte e com o Art. 38 da LGPD, a elaboração de RIPD/DPIA é **inexigível** para esta entrega.

---

## 5. Salvaguardas Mandatórias de Privacy by Design (DoD de Privacidade)

O Desenvolvedor, o Tester e o Revisor de Código DEVEM assegurar o cumprimento inegociável das seguintes salvaguardas:

- **LGPD-CAN-01 (Anti-Overfetching no Repositório):** A consulta ao banco de dados para similaridade de compradores DEVE selecionar estritamente `[Cod Produto]` e `[Cod Cliente]`, sem incluir colunas de nome, CPF/CNPJ, e-mail, telefone ou endereço.
- **LGPD-CAN-02 (Zero Identificadores em Endpoints):** Nenhuma resposta da API de canibalização (`/analytics/cannibalization/{sku}`) ou de substituição (`/analytics/substitution/{sku}`) conterá arrays, contagens nominais ou propriedades referenciando códigos de clientes.
- **LGPD-CAN-03 (Proibição Terminante de Log de Clientes):** É expressamente proibido registrar `Cod Cliente`, instâncias de clientes ou DataFrames contendo clientes em logs de console, arquivos de log ou Cloud Logging.
- **LGPD-CAN-04 (Volatilidade dos Conjuntos de Jaccard):** Os conjuntos `Set[int]` utilizados para calcular a similaridade de Jaccard devem existir apenas durante a execução da função de agregação e serem liberados para coleta de lixo (garbage collector), nunca sendo gravados em arquivos temporários ou em disco.
- **LGPD-CAN-05 (Isolamento de Cache):** O cache do serviço (`AnalyticsCache`) deve indexar apenas o resultado final do produto (similaridade numérica e métricas agregadas), sem armazenar a lista de clientes associados ao SKU.
- **LGPD-CAN-06 (Sanitização de Mensagens de Erro):** Em nenhuma hipótese respostas de erro HTTP (ex: 400, 404, 422, 500) devem ecoar códigos de clientes ou detalhes de registros de clientes.
- **LGPD-CAN-07 (Controle de Acesso):** As rotas de canibalização devem permanecer protegidas pelo middleware de autenticação da aplicação (`HTTPBasicAuthASGIMiddleware`), sendo acessíveis unicamente por operadores autenticados.
- **LGPD-CAN-08 (Veto no Code Review):** Qualquer commit que introduza exposição de dados pessoais na camada de apresentação ou de API acarretará veto imediato da entrega pelo `reviewer` e pelo `security`.
