# STATE — Privacidade F7 (Diagnóstico de Motivos da Tendência com IA)

| Campo | Valor |
| :--- | :--- |
| **Agente** | `privacy_officer` (revisão leve, Etapa 2) |
| **Data** | 2026-11-24 |
| **Parecer** | **APROVADO COM CONDIÇÕES** — `.agents/docs/privacy/analytics-tendencia-ia.md` |
| **RIPD** | Não exigido (sem dado sensível, sem decisão automatizada sobre titular, LLM sem dado pessoal). Gatilhos de reavaliação no parecer §6 |
| **Base legal** | Legítimo interesse (Art. 7º, IX), mesmo LIA da F6, para a leitura volátil de `Cod Cliente` e status de churn. Envio ao Google fora do escopo da LGPD se cumpridas LGPD-TIA-03..06 |
| **Transferência internacional** | Não há de dado pessoal; o risco é de segredo comercial → Vertex AI (recomendado) ou Gemini API paga; nível gratuito vedado |
| **`MIN_CLIENTS_PER_UF = 3`** | Aprovado, com correção do ataque por diferença em "Outras UFs" |
| **Retenção GCS 90 dias** | Aprovada; lifecycle no bucket, bucket privado, SA com papel restrito |

## Condições para a Etapa 4
LGPD-TIA-01 (colunas mínimas na variante de 4 datas e na query por UF) · 02 (`customer_code` só em escopo local, `del` antes do cache) · 03 (pacote do LLM por lista branca, teste com códigos sintéticos) · 04 (sem custo unitário) · 05 (UF < 3 clientes e "Outras UFs" < 3) · 06 (contagens < 3 em faixa no pacote do LLM) · 07 (logs sem `str(exc)` do SDK) · 08 (Vertex/Gemini pago, segredo no Secret Manager) · 09 (diagnóstico no GCS sem cliente/usuário/IP; lifecycle 90 d) · 10 (bucket privado, SA mínima, travas sem identificador) · 11 (limite por usuário/IP sem persistir IP em claro) · 12 (consultas de busca só com categoria/fornecedor/UF agregada/período) · 13 (erros sem eco) · 14 (rotas autenticadas).

## Pontos para o checkpoint
- PC-01: ADR-009 decide Vertex AI × Gemini API paga e registra retenção/treino (incl. grounding) do Gemini 4.
- PC-02: P-167/P-185.3 precisam da regra de diferença de "Outras UFs".
- PC-03: P-179 deve proibir contagens de clientes < 3 em valor exato no pacote.
- PC-04: P-176.3 precisa definir armazenamento do contador por usuário/IP.
- PC-05: §4 das regras deve condicionar "sem dado pessoal" às LGPD-TIA-03..06.

Arquivos editados: somente este STATE e `privacy/analytics-tendencia-ia.md`.
