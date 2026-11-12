# Parecer de Privacy by Design: Analytics Comercial, Fase F3 (Churn de Clientes)

> **Localização Mandatória:** `.agents/docs/privacy/analytics-churn.md`  
> **Responsável:** Encarregado de Proteção de Dados (`privacy_officer` / DPO)  
> **Status:** APROVADO COM CONDIÇÕES  
> **Data:** 2026-11-12  

| Campo | Valor |
| :--- | :--- |
| **Feature** | Detecção e Priorização de Churn de Clientes com Score de Retenção |
| **Branch** | `feature/analytics-churn` |
| **Regras** | P-117 a P-127 (`business_rules/analytics-churn.md`) |
| **Contrato** | `api_contracts/analytics-churn.md` (v1.0.0) |
| **Arquitetura** | `adr/ADR-006-churn-clientes.md` |

---

## 1. Classificação dos Dados Tratados

| Atributo | Origem | Natureza Jurídica (LGPD) | Medida Protetiva / Minimização |
| :--- | :--- | :--- | :--- |
| `Cod Cliente` (`customerCode`) | `Externo01.Vendas` | **Dado Pessoal Pseudonimizado** (regra do pior caso: trata MEI/EI como titular individual) | Código numérico desprovido de metadados identificáveis. Reidentificação possível apenas com acesso restrito direto ao ERP. |
| Recência e Histórico de Compras | `Externo01.Vendas` | Dado Comportamental Comercial | Agregado analítico em memória (`diasSemComprar`, `gapTipico`, `diasReferencia`). |
| Faturamento Médio e Score | Agregação | Métrica Comercial Derivada | Calculada em memória com base em faturamento líquido; usada unicamente para ordenação de atendimento. |
| Dados Cadastrais (Razão Social, Nome, CPF/CNPJ, E-mail, Telefone) | ERP | Dado Pessoal / PII | **TOTALMENTE EXCLUÍDOS**. A API não projeta nem recebe nenhum destes atributos. |

*Nenhum dado sensível (Art. 11 da LGPD) ou dado de menores é processado nesta feature.*

---

## 2. Enquadramento Legal e Teste de Ponderação (LIA)

### 2.1 Base Legal
**Legítimo Interesse do Controlador (Art. 7º, IX c/c Art. 10 da Lei 13.709/2018).**

### 2.2 Teste de Ponderação (Legitimate Interests Assessment - LIA)
1. **Finalidade:** Otimizar e direcionar o contato comercial da equipe de vendas da distribuidora Fitoherb para clientes que reduziram a frequência de compra habitual ("apoio e promoção de atividades do controlador", Art. 10, I).
2. **Necessidade:** O algoritmo utiliza a menor quantidade possível de dados (apenas `customerCode`, datas de pedidos de venda e valores faturados líquidos). Não há mecanismo alternativo menos invasivo para detectar retenção de carteira.
3. **Balanceamento e Expectativa Legítima:** No contexto B2B de distribuição farmacêutica e fitoterápica, é razoável e esperado que a distribuidora monitore a constância de pedidos de seus compradores habituais para oferecer suporte comercial e reposição de estoque. Não há qualquer impacto depreciativo ou restritivo de direitos para o cliente.
4. **Salvaguardas:** Implementação das travas de segurança e privacidade detalhadas a seguir.

---

## 3. Decisões Automatizadas e Perfilamento (Art. 20)
- **Não há decisão exclusivamente automatizada que produza efeitos jurídicos ou afete negativamente o titular:** O algoritmo gera apenas uma fila de prioridade para guiar o televendas interno. A decisão de ligar, oferecer promoções ou negociar condições continua sob julgamento estritamente humano do vendedor/gestor.
- **Transparência e Explicabilidade:** O endpoint `/customers/{customerCode}` expõe os fatores matemáticos que compõem o score (fator tempo, cadência e média de faturamento), assegurando auditabilidade total das razões de contato.

---

## 4. Requisitos Obrigatórios de Segurança e Privacidade (LGPD-CHU-01 a 06)

1. **LGPD-CHU-01 (Minimização nos Contratos de API):** Nenhuma resposta da API de churn pode conter nome, documento, razão social ou telefone. O único identificador de cliente permitido é `customerCode` (inteiro).
2. **LGPD-CHU-02 (Proibição de PII em Logs):** É terminantemente proibido registrar códigos de cliente individuais ou payloads de requisição/resposta nos logs da aplicação (`console.log` / `logger.info`). Os logs devem registrar exclusivamente estatísticas operacionais agregadas (ex.: "Cálculo de churn finalizado: N clientes processados").
3. **LGPD-CHU-03 (Consultas Somente Leitura e Prevenção de SQLi):** Todas as queries executadas contra a base do ERP devem passar pelo validador `is_readonly_query` e utilizar parametrização com bind parameters (`?`), eliminando qualquer risco de injeção de comandos.
4. **LGPD-CHU-04 (Isolamento em Memória e TTL):** Os agregados de clientes não são persistidos em tabelas intermediárias no banco de dados. Ficam retidos temporariamente na memória RAM do processo protegidos por TTL de 6 horas.
5. **LGPD-CHU-05 (Exportação CSV Controlada):** A exportação de arquivos CSV no frontend deve ser protegida por autenticação e restrita aos usuários autenticados da área comercial. O arquivo gerado contém apenas os dados exibidos na tela (`customerCode`, status, recência, score).
6. **LGPD-CHU-06 (Canal de Oposição):** Caso algum cliente solicite não receber contatos proativos de televendas, sua exclusão da esteira de contato é operacionalizada pela equipe de atendimento no ERP.

---

## 5. Conclusão do DPO
A feature **F3 — Churn de Clientes com Score de Prioridade** está **APROVADA** para desenvolvimento e homologação, sujeita à verificação estrita dos requisitos `LGPD-CHU-01` a `LGPD-CHU-06` na Etapa 4 (Quality Gate 360).
