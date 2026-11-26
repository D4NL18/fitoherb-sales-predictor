# Auditoria de Código LGPD (Etapa 4): F7 Tendência de Vendas com IA

| Campo | Valor |
| :--- | :--- |
| Feature | `analytics-tendencia-ia` (F7), `src/modules/trend_insights/`, `analytics/repository/sales_repository.py`, frontend `sales-trend/insights` |
| Referência | `privacy/analytics-tendencia-ia.md` (LGPD-TIA-01..14) e tabela LGPD-TIA em `tasks/analytics-tendencia-ia.md` |
| Data | 2026-11-25 |
| **Veredito** | **APROVADO COM RESSALVAS** (nenhum veto de código; pendências de infraestrutura/ADR bloqueiam o release, não o merge) |

## 1. Resultado por condição

| ID | Status | Evidência |
| :--- | :--- | :--- |
| TIA-01 | OK | `sales_repository.py:590-600` (4 datas) seleciona só `[Cod Cliente]`, `[Cod Produto]`, `[Data]`, `[Operação]`, qtd e valor; `:607-622` (UF) devolve `COUNT(DISTINCT [Cod Cliente])` e nunca o código; parâmetros vinculados `?`. Teste `test_split_window_repository.py` |
| TIA-02 | OK | `customer_code` só em `migration_scaling.py`, `migration_adapter.py:45-59` (`del rows`, `del scaled`) e `factor_adapter.py:112` (frozenset volátil de clientes perdidos, sem nome). Grep por cpf/cnpj/nome/e-mail no módulo: zero ocorrências. Teste `test_migration.py` |
| TIA-03/04 | OK | `llm/evidence_payload.py:160-185` monta por lista branca; sem custo, sem `netClients`, sem `clientesPerdidosQtd`. Teste com `987654321` em `test_evidence_payload.py` |
| TIA-05 | OK | `domain/privacy.py:52-74`: UF < 3 vai a `OUTRAS`; `OUTRAS` < 3 absorve a menor UF exibida; impossível, `NAO_AVALIADO/ANONIMIZACAO`. `evidence_adapter.py:478-487` só emite grupos; `OUTRAS` nunca é nomeada (`privacy.py:83`) |
| TIA-06 | OK | `evidence_payload.py:81` usa `format_small_count` (`"<3"`); a API também mascara (`insight-view.ts:43`) |
| TIA-07 | OK | Todos os logs do módulo registram só `type(exc).__name__` ou campos de P-185.2 (`gemini_client.py:80`, `route.py:90`, `gcs_object_store.py:40,56,67`, `llm_runner.py:137-144`). `from None` descarta a mensagem do SDK (`gemini_client.py:75`). Teste caplog em `test_llm_orchestrator.py:266` |
| TIA-08 | OK no código, pendente em deploy | Único cliente é Vertex via ADC, `vertexai=True` (`gemini_client.py:49`); não há `api_key`/Gemini API no `src`. Configuração de faturamento e papel `aiplatform.user` ainda em D-7.2.13 (aberto) |
| TIA-09 | Parcial | `InsightKey.object_path` (`insight_store.py:27-31`) e `StoredInsight` não têm usuário/IP/cliente. **Regra de lifecycle de 90 dias não existe no repositório**: `INSIGHT_RETENTION_DAYS` (`constants.py:75`) é só constante e nenhum script/IaC a aplica |
| TIA-10 | Pendente | Nenhum IaC/script de bucket (Uniform access, Public Access Prevention, papel restrito) no repositório; D-7.0c.9 aberto. Leases/budget sem identificador (testes T-7.2.7, T-7.2B.1) |
| TIA-11 | OK | `generation_guard.py:3,33` usa HMAC com sal de processo; estado em memória; IP não logado |
| TIA-12 | OK | `llm/search_queries.py:48-63`: só função primária, categoria, fornecedor e ano; sem UF nem texto livre |
| TIA-13 | OK | `api/route.py:28-38,89-91`: mensagens fixas, sem eco de parâmetros nem stacktrace |
| TIA-14 | OK | Testes T-7.0c.3 e `test_api_contract.py`; rota atrás do middleware |

## 2. Frontend e transparência (R-04)
- Aviso fixo em `insight-copy.ts:117`: "Diagnóstico gerado por IA a partir de dados internos e notícias públicas; confira as fontes." Selos "Gerada por IA" e "Resumo automático (sem IA)" (`insight-copy.ts:110-113`). Atende R-04.
- Sem `localStorage`/`sessionStorage` (`trend-insights.store.ts:5`). Contagens de clientes exibidas só como número agregado ou "menos de 3 clientes". Sem checkbox pré-marcado; a feature não coleta consentimento.

## 3. Achados e ressalvas

| # | Gravidade | Achado | Ação exigida |
| :-: | :--- | :--- | :--- |
| A-1 | Alta (bloqueia release) | Lifecycle de 90 dias e bloqueio de acesso público do bucket não estão implementados nem verificáveis (`constants.py:75` sem consumidor; sem IaC). LGPD-TIA-09/10 exigem a verificação no script de deploy | `devops` (D-7.0c.9, D-7.2.13): criar a regra no prefixo `insights/` com 90 dias, `ai-budget/` com 400 dias, PAP ativo, Uniform access e papel restrito ao bucket. Reauditar antes do deploy |
| A-2 | Média | `DEFAULT_VERTEX_LOCATION = "global"` (`config.py:18`): processamento sem região definida. O parecer pede região controlada (R-01) e a exigência desta auditoria é processamento us/eu. Sem dado pessoal, não há Art. 33, mas há segredo comercial | Fixar `TREND_AI_LOCATION` em região us/eu (ou `southamerica-east1`, se o grounding permitir) no deploy e registrar no ADR-009 |
| A-3 | Média | PC-01 não está comprovado no ADR-009: não há registro de retenção do Google, ausência de treino e condições do grounding (só a decisão por Vertex, ADR-009:382) | `architect`/`devops`: registrar os termos oficiais do Vertex/Gemini 4 no ADR-009 |
| A-4 | Baixa | O aviso da UI não nomeia o Google como operador de IA (R-03, ROPA) | Atualizar ROPA e aviso interno de privacidade |
| A-5 | Baixa | `_regional` usa a coluna `[UF]` da linha de venda; `generation_guard` usa `request.client.host` (`router.py:59`) apenas em HMAC volátil. Nada a corrigir, só conferir atrás do proxy do Cloud Run | Informativo |
| A-6 | Informativa | Não executei a suíte de testes nesta auditoria (análise estática) | Reviewer/tester confirmam execução verde |

## 4. Conclusão
Código aprovado quanto a vazamento de dado de cliente no prompt, cache, GCS, logs, respostas e UI. Os pontos A-1 a A-3 devem ser fechados no `devops` (Etapa 5) e no ADR-009 antes de o recurso ser ativado em produção. Sem alteração de código requerida ao `developer`.
