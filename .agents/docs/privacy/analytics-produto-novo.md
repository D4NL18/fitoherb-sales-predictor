# Parecer de Privacy by Design: Viabilidade de Produto Novo (`analytics-produto-novo`)

> **Localização Mandatória:** `.agents/docs/privacy/analytics-produto-novo.md`  
> **Status:** APROVADO COM BYPASS TOTAL (Isenção Formal LGPD)  
> **Data:** 2026-11-12  
> **Responsável:** Encarregado de Dados / DPO (`privacy_officer.md` / `lgpd-privacy-expert`)  
> **Feature Associada:** FASE F2 — Viabilidade de produto novo (conservadora)  
> **Branch:** `feature/analytics-produto-novo`  
> **Documentos Auditados:** `business_rules/analytics-produto-novo.md` (P-139 a P-149), `adr/ADR-008-produto-novo.md`, `api_contracts/analytics-produto-novo.md`

---

## 1. Contexto e Objeto da Auditoria de Privacidade

A funcionalidade **Viabilidade de Produto Novo** visa permitir a gestores e compradores a simulação do potencial de mercado e viabilidade de introdução de novos itens no catálogo da Fitoherb antes de seu cadastro formal no ERP. 

O objetivo deste parecer é verificar a existência de tratamento de Dados Pessoais (Art. 5º, I da LGPD) ou Dados Pessoais Sensíveis (Art. 5º, II da LGPD), analisar o fluxo de dados na esteira de desenvolvimento e formalizar a dispensa ou exigência de controles de privacidade.

---

## 2. Classificação dos Dados Tratados

| Dado / Atributo | Origem | Natureza | Classificação LGPD | Observações de Governança |
| :--- | :--- | :--- | :--- | :--- |
| `tipo` | Input do Usuário | Comercial | **Não Pessoal** | Categoria genérica de mercadoria (ex.: "Tinturas", "Cápsulas"). |
| `fornecedor` | Input do Usuário / Catálogo | Comercial B2B | **Não Pessoal** | Razão social ou marca comercial de laboratórios fornecedores (PJ). |
| `descricao` | Input do Usuário / Catálogo | Técnica / Comercial | **Não Pessoal** | Texto descritivo de composição, miligramagem e volume. |
| `precoVendaPrevisto` | Input do Usuário | Comercial | **Não Pessoal** | Valor monetário hipotético planejado. |
| `custoUnitario` | Input do Usuário | Comercial | **Não Pessoal** | Valor de aquisição hipotético planejado (sigilo comercial B2B). |
| `margemMinimaDesejada` | Input do Usuário | Estratégico | **Não Pessoal** | Meta de rentabilidade da distribuidora. |
| Quantidade e Faturamento Líquido Mensal dos Similares | `Externo01.Vendas` (Agregado) | Estatístico | **Não Pessoal (Agregado Anônimo)** | Soma aritmética pura agrupada por `Cod Produto × Mês`. |
| `Cod Cliente`, `Nome`, `CPF/CNPJ`, `Endereço`, `UF`, `Pedido` | ERP | Cadastral / Pessoal | **NÃO ACESSADO / PROIBIDO** | O repositório e os serviços da feature NÃO realizam SELECT nessas colunas. |

---

## 3. Avaliação de Conformidade com a LGPD (Lei 13.709/2018)

### 3.1 Inaplicabilidade dos Artigos 7º e 11
Como demonstrado na tabela de dados, a funcionalidade **não realiza operações de tratamento sobre dados de pessoas naturais**. Todas as informações processadas referem-se estritamente a mercadorias, categorias de estoque, métricas de fornecedores industriais (PJ) e agregações estatísticas globais de faturamento. Portanto, a aplicação não exige enquadramento em bases legais do Artigo 7º ou 11 da LGPD para sua operação.

### 3.2 Decisões Automatizadas e Perfilamento (Art. 20)
- **Não há perfilamento de indivíduos:** A previsão é construída exclusivamente sobre séries temporais de produtos e categorias de estoque.
- **Não há impacto sobre titulares:** A simulação apoia a decisão interna de compra da distribuidora (B2B), sem afetar direitos, preços de consumidores finais ou crédito de indivíduos.
- Inaplicabilidade do dever de revisão de decisões automatizadas perante titulares pessoas físicas.

### 3.3 Relatório de Impacto à Proteção de Dados (RIPD / DPIA)
- **DISPENSADO.** Inexiste risco a direitos e liberdades civis de titulares de dados em virtude da ausência de dados pessoais.

---

## 4. Requisitos Mandatórios de Anti-Overfetching para o Desenvolvedor

Para assegurar que o status de isenção de privacidade permaneça inviolável durante a futura Etapa 3 (Implementação):

1. **R-PRIV-01 (Proibição de Projeção de Cliente):** A consulta agregada em `sales_repository.py` DEVE conter unicamente as colunas `[Cod Produto]`, `[Data]`, `[Qtd Venda]`, `[Valor Venda]` e `[Operação]`. É expressamente proibido selecionar `[Cod Cliente]` ou `[Pedido]`.
2. **R-PRIV-02 (Logs Sanitizados):** Os logs estruturados da aplicação nunca devem tentar enriquecer requisições de simulação com dados de vendedores ou clientes autenticados.
3. **R-PRIV-03 (Isolamento de Erros):** Nenhuma informação de banco de dados estrutural ou dados cadastrais poderá ser exposta em respostas de erro `NEW-XXX`.

---

## 5. Parecer Conclusivo

> [!NOTE]
> O **Encarregado de Dados (DPO)** emite parecer de **APROVAÇÃO COM BYPASS TOTAL** para a FASE F2 (`analytics-produto-novo`). A feature está autorizada a prosseguir na esteira sem a necessidade de novos checkpoints de privacidade na Etapa 4, desde que as restrições `R-PRIV-01` a `R-PRIV-03` sejam integralmente observadas pelo Revisor de Código.
