# STATE — F7 Diagnóstico de Motivos da Tendência com IA (Analista)

> Estado paralelo ao `STATE.md` (não editado). Responsável: `analyst`. Etapa 1 concluída em 2026-11-24, sem discovery (escopo já aprovado no plano v2, Q-1..Q-8).

| Campo | Valor |
| :--- | :--- |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` (com `origin/main` mesclado, F6 incluída) |
| **Faixa de regras usada** | `P-150` a `P-187` |
| **Último ID P usado** | `P-187` |
| **Prefixo de erro** | `TIA-001` a `TIA-005` |
| **Próxima etapa** | Etapa 2: `architect` (ADR-009, contrato `trend-insights`), `ai_specialist` (prompts, schema, grounding), `designer` (painel "Por que?"), `privacy_officer` leve |

## Entregas
- `.agents/docs/business_rules/analytics-tendencia-ia.md` — regras P-150..P-187, tabela de constantes, LGPD, matriz C-01..C-36 e DoD.
- `.agents/docs/business_rules/analytics-canibalizacao.md` — P-129.1/P-129.4 e P-130 reescritos para a migração ponderada por afinidade (agnóstica de fornecedor); nova seção do Índice de Afinidade como sub-regras **P-130.3a e P-130.4 a P-130.12** (sem IDs P novos); constantes do índice na tabela.
- `.agents/docs/GLOSSARY.md` — seção 6 (afinidade e F7).

## Achados no código que mudam premissas do plano
1. **Modo de comparação da Tendência:** a API atual usa `comparisonMode` ∈ {`point` (padrão), `average`}; o plano supunha blocos contíguos (`range`). No `point` com X > 1 as janelas não são contíguas e `fetch_customer_sku_window_sales` não serve: precisa de variante com 4 datas (P-153.1). O `comparisonMode` não está documentado em `analytics-sales-trend.md`.
2. **Janela de 12 meses:** nos modos `point`/`average` ela quase sempre tem base; a regra "migração não avaliada" foi generalizada para "Janela Anterior com cobertura < 100%" (P-153.4).
3. **Índice no cold start:** o código não reconstrói o índice na partida; sem o arquivo, fica indisponível até 00:00 ou `POST /affinity/sync`, e a F6 cai no fallback por tokens. A F7 proíbe esse fallback (P-153.3) e reforça a urgência da tarefa 7.0 (c).
4. **Parcela de preço em faturamento:** a fórmula do plano (`anterior × ε × Δp`) só vale para quantidade; P-159 usa `(1+Δp)(1+εΔp) − 1` em R$.
5. A docstring de `_vectorize_documents` cita pesos 60/40; o código usa 80/15/5 (registrado em P-130.7).

## Decisões do Analista para validar no checkpoint
- Limiares propostos: `DOMINANT_EFFECT_RATIO = 0,70`, `MIN_EXPLAINABLE_VARIATION_PCT = 2%`, `MIN_PRICE_CHANGE_PCT = 2%`, `MIGRATION_HIGH_CONFIDENCE_CLIENTS = 10`, `LAUNCH_MIN_DAYS_AFTER_BASE_START = 90`, `REGIONAL_CONCENTRATION_SHARE = 0,60`, `MIN_CLIENTS_PER_UF = 3`, `GENERATE_RATE_LIMIT_PER_MINUTE = 5`, `EXTERNAL_SOURCE_LOOKBACK_DAYS = 90`.
- Teto de gasto modelado como **mensal** (Q-4, US$ 30); o plano §3.7 citava variável diária. Sem teto diário separado.
- Região (UF) fica **fora da soma** da cascata (é onde, não por quê).
- Clientes perdidos só em Mês-Base recente (status de churn é de "hoje").
- Promoção só como indicador (as funções existentes dão presença, não a venda em promoção).
- Limite por minuto devolve `TIA-004` com HTTP 429 (`motivo = LIMITE_DE_PEDIDOS`) para não criar código fora do catálogo do plano; falha do SQL usa o global `ANL-001`.

## Revisão v2 (2026-11-24, custo e checkpoint)
Regras reescritas conforme `STATE_IA_TendenciaIA.md` e ADR-009: último ID P agora `P-188`; erros até `TIA-007`; `PROMPT_VERSION = "tia-v2"`.
- **Alteradas:** P-153.1 (consulta de 4 datas em todos os modos, um caminho só; CP-1), P-167 (+P-167.1 piso de `OUTRAS`, +P-167.2 `"<3"`), P-174 (+P-174.1 template não é erro), P-175 (chave com `evidenceHash`, TTL 30 dias, P-175.3 revogada, +P-175.6/.7), P-176 (2/min, 10/dia, `force` 3/dia, +P-176.4 contador em memória), P-177 (sem Neon; Flash de fallback), P-178 (US$ 1,80/0,20, reserva e acerto, livro GCS, 80%, kill-switch, esgotado = template), P-179 (8.000 caracteres, `"<3"`), P-180 (consultas sugeridas, +gate de grounding), P-181 (limites, +`explicacao`), P-182.2/182.4 (SKU por marcador, `SEM_DATA`), P-183 (Flash, `LLM_TOTAL_DEADLINE_SECONDS=110`), P-184.5 (ressalva CP-10), P-185.4 (Vertex AI/ADC), P-186 (`TIA-004` só 429; novos `TIA-006` 401 e `TIA-007` 409), P-187, §4 (condicionado a LGPD-TIA-03..06).
- **Nova:** P-188 (gates sem LLM e resumo por template). Matriz: C-21a/b, C-25a/b, C-28a..d, C-29a, C-33a/b.
- **Pendente do `architect`:** contrato e ADR ainda refletem a v1 (remover `deep`/`tipoAnalise`; decidir 200 com template em vez de 503 `TIA-004`).

## Revisão v3/v3.1 (2026-11-26, investigação externa e otimização de custo)
Regras aplicadas conforme `STATE_IA_TendenciaIA.md` (impactos v3 e v3.1) e `architecture/trend-insights-llm.md` §15/§15.14. Nenhum ID renumerado.
- **Alteradas:** P-174.1 (ordem de decisão com radar; template + `radarExterno`), P-175/P-175.6 (`tia-v3`, radar fora da chave, TTL vale para todo LLM), P-176.2 (trava 150 s; radar 90 s), P-177.5/.6, P-178.1/.2/.3/.4/.5, P-179 (radar 2.000 caracteres fora do hash), P-180 e P-180.1/.2, P-181, P-182.1/.4/.5, P-183.5, P-184.3, P-186/P-187, P-188 (inalterado, nota). Constantes: teto duro 1.500 consultas, TTL 30/180 e stale 120 d, 5 consultas (reserva 6), `RADAR_BUDGET_SHARE` 0,25, prazos 125/150 s.
- **Novas:** P-178.8, P-180.3 a P-180.6, P-181.3, P-184.6; matriz C-36 a C-45 (C-28, C-28b, C-29a revisados). O antigo C-36 (SQL fora do ar) passou a **C-35a** para liberar a numeração da v3.
- **Glossário:** Radar Externo, Dimensão Externa, Tema (do Radar), Sem Evidência, Relação Temporal.
- **Pendente:** `architect` (contrato 1.2.0 e ADR-009), `devops` (SKU/cota de grounding no Vertex, ciclo de vida `radar/`), `privacy_officer` (RIPD do radar).

## Log
- **2026-11-24 — analyst:** regras F7 P-150..P-187 redigidas; doc da Canibalização alinhada ao código (índice de afinidade); glossário seção 6.
