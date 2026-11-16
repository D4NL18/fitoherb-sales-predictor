# Parecer de Privacy by Design: Analytics Comercial — F5 Elasticidade-preço por produto e cliente

> **Localização Mandatória:** `.agents/docs/privacy/analytics-elasticidade.md`
> **Responsável:** Encarregado de Dados (`privacy_officer` / `lgpd-privacy-expert`)
> **Etapa:** 2 (Revisão de Privacy by Design)
> **Branch:** `feature/analytics-elasticidade`
> **Status:** APROVADO COM CONDIÇÕES (RIPD não exigido)

---

## 1. Contexto e Classificação dos Dados Tratados

A funcionalidade estima a elasticidade-preço de produtos e analisa o comportamento de compra agregada de clientes sobre determinados SKUs, oferecendo também um simulador de reajustes percentuais.

| Dado | Origem | Classificação LGPD | Observação / Medida de Proteção |
| :--- | :--- | :--- | :--- |
| `customerCode` (`Cod Cliente`) | `Externo01.Vendas` | **Dado pessoal pseudonimizado** (quando cliente for pessoa natural, MEI ou empresário individual) | Tratado como dado pessoal pela regra do pior caso. O código isolado não identifica a pessoa sem o ERP. |
| Frequência e volume por cliente/SKU | Agrupamento de `Externo01.Vendas` | **Dado pessoal pseudonimizado comportamental** | Volumes e contagens de pedidos agregados no grão mensal. |
| Elasticidade individual estimada | Derivado do cálculo econométrico | **Dado analítico inferido** | Estimativa estatística indicativa; mitigada via shrinkage. |
| Dados cadastrais (Razão Social, Nome, CPF, CNPJ, Contato) | ERP | **Dados Pessoais / Cadastrais** | **NÃO SÃO TRATADOS NEM TRAFEGADOS**. Excluídos da consulta SQL e da API. |

---

## 2. Enquadramento Legal (Art. 7º e 10 da LGPD)

### 2.1 Base Legal Aplicável
**Legítimo Interesse do Controlador (Art. 7º, IX c/c Art. 10 da LGPD).**
- **Finalidade Legítima:** Compreender a dinâmica de preços e sensibilidade econômica de mercado para sustentabilidade financeira e comercial da empresa.
- **Necessidade e Proporcionalidade:** O processamento limita-se estritamente aos volumes e preços agregados de pedidos já faturados. Não há coleta de novos dados nem enriquecimento externo com bureaus de crédito.
- **Expectativa Razoável:** Clientes atacadistas e comerciais esperam que o distribuidor analise o histórico agregado de pedidos para planejar preços e estoques.

### 2.2 Decisão Automatizada e Perfilamento (Art. 20 da LGPD)
- **Natureza Consultiva / Assistida:** O sistema **não aplica decisões automatizadas de preço**. A ferramenta é um simulador de apoio à decisão humana para gerentes comerciais e analistas de pricing.
- Não há definição de preços discriminatórios dinâmicos automáticos contra pessoas naturais, nem bloqueio de pedidos ou restrição de acesso a produtos.

### 2.3 Avaliação de Impacto (RIPD / DPIA)
- **Conclusão:** **RIPD NÃO É EXIGIDO** nesta fase, dado que não há tratamento de dados sensíveis (Art. 11), não há tomada de decisão 100% automatizada com efeito jurídico adverso e a base opera prioritariamente no segmento B2B.

---

## 3. Requisitos Obrigatórios de Segurança e Privacidade (LGPD-01 a LGPD-06)

1. **LGPD-01 (Minimização nos Agregados):** O SQL de agregação deve trazer apenas `Cod Cliente`, `Cod Produto`, `Qtd Venda` e `Valor Venda`. Nunca projetar colunas de nome, CPF, endereço ou telefone.
2. **LGPD-02 (Sem PII na Interface):** As telas do frontend devem exibir exclusivamente o identificador numérico `Código do Cliente`. É vedada qualquer interpolação com bases nominais.
3. **LGPD-03 (Sanitização de Logs):** Nenhum payload contendo dados individuais de compra ou listas de clientes deve ser despejado em nível `INFO` ou superior nos logs do servidor.
4. **LGPD-04 (Autenticação e Controle de Acesso):** Os endpoints `/analytics/elasticity/*` permanecem protegidos pelo middleware global de autenticação `HTTPBasicAuthASGIMiddleware`.
5. **LGPD-05 (Prevenção a Injeção de SQL):** Todas as queries agregadas no banco devem utilizar parâmetros vinculados (`?`), sem concatenação de strings de entrada.
6. **LGPD-06 (Direito de Oposição):** Caso um cliente questione a inclusão de seu histórico na análise comercial, o time de operações pode configurar filtros de exclusão no ERP.
