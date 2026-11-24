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

## Log
- **2026-11-24 — analyst:** regras F7 P-150..P-187 redigidas; doc da Canibalização alinhada ao código (índice de afinidade); glossário seção 6.
