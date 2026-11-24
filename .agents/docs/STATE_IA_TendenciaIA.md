# STATE — AI Specialist · F7 Diagnóstico de Motivos da Tendência com IA

| Campo | Valor |
| :--- | :--- |
| **Agente** | `ai_specialist` |
| **Etapa** | 2 (Arquitetura de IA) — concluída, aguardando Checkpoint |
| **Data** | 2026-11-24 |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **Entrega** | `.agents/docs/architecture/trend-insights-llm.md` |
| **Arquivos NÃO alterados** | `STATE.md`, ADR-009, contrato `trend-insights`, regras P-150..P-187 (divergências viraram pontos CP-1..CP-12) |

## Resumo

1. **Confirmado na doc oficial (aistudio.google.com/docs e docs.cloud.google.com):** IDs `gemini-4-hydrogen` e `gemini-4-neon` (Stable); contexto de 1.048.576 tokens; saída de 65.536; preço Standard US$ 1,50/7,50 (Hydrogen) e US$ 3,00/15,00 (Neon) por 1M tokens de entrada/saída (saída inclui *thinking*); grounding com Google Search com 5.000 consultas grátis/mês compartilhadas entre Gemini 3+ e depois US$ 14/1.000, **cobrado por consulta executada**, sem grounding no Free tier; **saída estruturada + Google Search na mesma chamada suportada em Preview** para Gemini 4; citações `url_citation` (`url`, `title`, índices) via Interactions API (recomendada, GA); `store=false` disponível; Vertex AI tem o Hydrogen com grounding e saída estruturada no endpoint `global` (processamento `us`/`eu`).
2. **Não confirmado:** data de publicação nas citações (não vem), filtro de período na busca, controle das consultas executadas, citações preenchidas junto com saída JSON, temperatura no Gemini 4, preço no Vertex AI, rate limits por modelo (só no painel do AI Studio).
3. **Desenho:** 1 chamada (grounding + JSON Schema) por padrão; modo de 2 chamadas (pesquisa com grounding em texto → estruturação sem busca) por configuração ou automático quando a combinação falhar ou vier sem citações.
4. **`LlmClient`** (porta própria, sem LangChain) com `generate(LlmRequest) -> LlmResponse`, DTOs de uso/citações e 5 erros tipados.
5. **Prompts `tia-v1`** em 7 blocos (S1 regras, S2 guia de fatores, S5 formato, U1 tarefa, U2 evidências, U3 galeria, U4 consultas) + prompt de pesquisa; delimitadores com nonce; números e SKUs só por marcadores (`{{parcela:TIPO}}`, `{{sku:COD}}`).
6. **Pacote de evidências** ≤ 16.000 caracteres com ordem de corte; lista do que nunca entra (`Cod Cliente`, custos, UFs < 3 clientes).
7. **Validação pós-resposta** em 9 etapas; fontes validadas contra a allow-list de citações e a janela de datas; números sempre do motor.
8. **Custo estimado:** Hydrogen ~US$ 0,03 (busca no grátis) a ~US$ 0,07 (busca cobrada); Neon ~US$ 0,13 a ~US$ 0,20. Mistura 80/20 com busca cobrada: ~US$ 0,10 → **~300 diagnósticos/mês em US$ 30**. Pré-checagem: US$ 0,13 (Hydrogen) e US$ 0,30 (Neon) por tentativa.
9. **Avaliação 7.5:** 40 casos rotulados às cegas, metas (top-1 ≥ 70%, mercado × concorrência ≥ 80%, fontes válidas ≥ 60%), red teaming de injeção, SKU, números, datas e links.

## Pontos para o Checkpoint (detalhe na §13 do documento)
- CP-1 Gemini API (chave, `store=false`) na v1; Vertex AI como opção por variável.
- CP-2 Consultas são **sugeridas**, não impostas (ajustar P-180); novas constantes de máximo de consultas.
- CP-3 Grounding não devolve data de publicação (impacta P-182.4).
- CP-4 Termos do grounding: exibir *Search Suggestions* (HTML) e não modificar Grounded Results; conflita com P-184.5 e com a substituição de marcadores → `designer`, `security` e avaliação jurídica/`ai_governance_auditor`.
- CP-5 Prazo total de 110 s para caber na trava de 120 s.
- CP-6 Temperatura: exceção à `ai-llm-integration-rules.md` §3 (não enviar no Gemini 4).
- CP-7 Lista de domínios confiáveis fica para depois da 7.5.
- CP-8 Campo `explicacao` no fator (P-181).
- CP-9 SKU no texto só por marcador (P-182.2).
- CP-10 Custo do grounding por consulta, não por pedido (P-178.1).
- CP-11 Combinação busca + schema é Preview (contingência de 2 chamadas).
- CP-12 Processamento em `us`/`eu` e retenção de 30 dias do grounding → nota do `privacy_officer`.

## Revisão v2 — custo e teto de US$ 2/mês (2026-11-24)

Decisões do usuário: só `gemini-4-hydrogen` (Neon removido), `gemini-3.8-flash` como fallback, Vertex AI, teto de **US$ 2,00/mês** no total, IA só ao apertar o botão, IA não escreve números. Detalhe e cálculos em `architecture/trend-insights-llm.md` §14.

**Confirmado (aistudio.google.com/docs/pricing, /models, /caching):** `gemini-3.8-flash` Stable; preço por 1M: US$ 0,75 entrada / 3,75 saída **até 31/12/2026** e US$ 1,50 / 7,50 **a partir de 01/01/2027**; Hydrogen US$ 1,50 / 7,50 fixo. Grounding: 5.000 consultas grátis/mês (Gemini 3+), depois US$ 14/1.000, por consulta executada. Cache implícito mínimo 4.096 tokens; **cache explícito não suportado no Hydrogen**; storage do explícito no Flash US$ 0,50 (2026) / 1,00 (2027) por 1M tokens·hora. 3.8 Flash: JSON Schema e grounding suportados; thinking `low/medium/high` (`minimal` dá erro). **Não confirmado:** preços no Vertex AI, schema + grounding juntos no 3.8 Flash, escopo da cota grátis, preços de GCS/Scheduler (de memória).

**Custo por geração (Hydrogen):** sem grounding ~US$ 0,014; com grounding na cota grátis ~US$ 0,018; grounding cobrado ~US$ 0,046; Flash fallback ~US$ 0,007 a 0,009 até 31/12/2026 (igual ao Hydrogen depois); cache hit e template US$ 0. **Capacidade com LLM ≤ US$ 1,80: ~104 gerações/mês (~55 se todo grounding fosse cobrado).** Infra F7 (GCS, locks, livro, índice de afinidade, Scheduler) ≈ US$ 0,00 a 0,12: não estoura o teto.

**Decisões:** cache GCS compartilhado com chave por `evidenceHash` (não `dataReferencia`), TTL lógico 30 dias, single-flight; cache de contexto do Gemini **não compensa** (economia ≤ US$ 0,0017/acerto; explícito custaria ~US$ 1/mês de storage); pacote 16 mil → 8 mil caracteres, saída curta, `max_output_tokens` 2.500, `thinking low`; grounding por gate determinístico, ≤ 2 consultas; template sem LLM quando não há o que explicar; livro de gastos no GCS com reserva, teto de LLM US$ 1,80, diário US$ 0,20, alerta 80%, kill-switch, Cloud Billing Budget de US$ 2.

## Impactos nas regras e no contrato (para `analyst` e `architect` aplicarem; o `ai_specialist` não editou `business_rules`, `api_contracts` nem ADR)

### A. Regras `P-1xx` (analyst, `business_rules/analytics-tendencia-ia.md`)

| Regra | Mudança |
| :--- | :--- |
| P-174 | Acrescentar: o botão pode responder com **resumo por template** (sem LLM) quando os gates do §14.7 negarem; isso não é erro |
| P-175 | Chave = `(escopo, id, metric, window, baseMonth, comparisonMode, PROMPT_VERSION, evidenceHash)`; **remover `dataReferencia`** da chave (P-175.4 muda: carga nova com evidência igual reaproveita). Remover P-175.3 (aprofundada). Adicionar TTL lógico `INSIGHT_SOFT_TTL_DAYS=30` e limite de `force` por usuário/dia. `PROMPT_VERSION` passa a `"tia-v2"` |
| P-176 | `GENERATE_RATE_LIMIT_PER_MINUTE` 5 → **2**; novo `GENERATE_MAX_PER_USER_PER_DAY=10`; `FORCE_MAX_PER_USER_PER_DAY=3`. Single-flight mantido (P-176.2) |
| P-177 | **Revogar** (escalonamento Hydrogen → Neon): P-177.1 a P-177.4 removidos. P-177.5 vira "modelo vem de env: `TREND_AI_MODEL_DEFAULT=gemini-4-hydrogen`, `TREND_AI_MODEL_FALLBACK=gemini-3.8-flash`" e define o fallback de modelo (§14.9) |
| P-178 | `TREND_AI_MONTHLY_BUDGET_USD` 30,00 → **1,80** (meta total US$ 2,00 inclui infra); novo `TREND_AI_DAILY_BUDGET_USD=0,20`; P-178.1 custo = tokens + `consultas_executadas × preço` (cota grátis assumida `GROUNDING_FREE_QUERIES_ASSUMED=1500`); P-178.2 vira **reserva + acerto**; P-178.3 livro `ai-budget/AAAA-MM.json` com concorrência otimista; P-178.4 mantém 80% e acrescenta degradação (grounding só com resíduo ≥ 0,50, `force` desabilitado); P-178.5 ao estourar: **resumo por template**, não bloqueio; novo kill-switch `TREND_AI_ENABLED` |
| P-179 | `MAX_EVIDENCE_PAYLOAD_CHARS` 16.000 → **8.000**; afins 25 → 10 no pacote; migração 10 → 5; UFs 5 → 3; só parcelas relevantes (≥ 5% de abs(Δ)) |
| P-180 | Consultas só **sugeridas**; `MAX_SEARCH_QUERIES=2` (1 no `QUALITATIVO`); acrescentar **gate de grounding** (§14.6): mercado em queda/alta, ou resíduo ≥ `GROUNDING_MIN_RESIDUAL_SHARE=0,30`, ou `REGIONAL` + resíduo ≥ 0,15 |
| P-181 | Limites: `MAX_FACTORS` 8 → **5**; `MAX_SOURCES_PER_FACTOR` 5 → **2**; `MAX_SUMMARY_CHARS` 800 → **400**; `explicacao` ≤ 160; hipóteses ≤ 3 (≤ 120); recomendações ≤ 3 (≤ 120) |
| P-183 | `LLM_TRANSIENT_RETRY_LIMIT` 3 → **2**; novo passo: falha de infraestrutura → 1 chamada `gemini-3.8-flash` → senão template; falha de schema repete no mesmo modelo |
| **Nova (ex.: P-188)** | **Gates de não chamada do LLM / narrativa por template:** `|variacaoPct| < MIN_EXPLAINABLE_VARIATION_PCT`, `SEM_BASE`, `|Δ faturamento| < LLM_MIN_ABS_REVENUE_DELTA (R$ 1.000)`, resíduo < `LLM_MIN_RESIDUAL_SHARE (0,20)` sem `REGIONAL` e sem diagnóstico de mercado. Texto do template determinístico, rotulado "Resumo automático (sem IA)" |
| P-185.4 | `GEMINI_API_KEY`/Secret Manager removido: Vertex AI com ADC da conta de serviço; manter proibição de chave em log |
| Constantes a **remover** | `TREND_AI_MODEL_DEEP`, `ESCALATION_MIN_RESIDUAL_SHARE`, `ESCALATION_MIN_ABS_REVENUE_DELTA`, `ESCALATION_TOP_RANK`, `TREND_AI_THINKING_DEEP`, `TREND_AI_MAX_OUTPUT_TOKENS_DEEP`, `MAX_SEARCH_QUERIES_DEEP` |
| Constantes a **alterar/criar** | `TREND_AI_MONTHLY_BUDGET_USD=1.80`; `TREND_AI_DAILY_BUDGET_USD=0.20`; `TREND_AI_ENABLED=true`; `TREND_AI_MODEL_FALLBACK=gemini-3.8-flash`; `TREND_AI_MAX_OUTPUT_TOKENS_DEFAULT=2500`; `MAX_SEARCH_QUERIES=2`; `GROUNDING_MIN_RESIDUAL_SHARE=0.30`; `GROUNDING_FREE_QUERIES_ASSUMED=1500`; `LLM_MIN_RESIDUAL_SHARE=0.20`; `LLM_MIN_ABS_REVENUE_DELTA=1000.00`; `INSIGHT_SOFT_TTL_DAYS=30`; `GENERATE_RATE_LIMIT_PER_MINUTE=2`; `GENERATE_MAX_PER_USER_PER_DAY=10`; `FORCE_MAX_PER_USER_PER_DAY=3`; `MAX_EVIDENCE_PAYLOAD_CHARS=8000`; `MAX_FACTORS=5`; `MAX_SOURCES_PER_FACTOR=2`; `MAX_SUMMARY_CHARS=400`; `LLM_TRANSIENT_RETRY_LIMIT=2`; `PROMPT_VERSION="tia-v2"` |
| `TREND_AI_PRICING_JSON` | Passa a incluir `gemini-4-hydrogen` (1,50/7,50) e `gemini-3.8-flash` (0,75/3,75 até 31/12/2026; 1,50/7,50 depois) e preço por consulta (0,014) |
| Glossário (`GLOSSARY.md`) | "Escalonamento" removido; "Teto de Gasto com IA" passa a US$ 2; criar "Resumo por template" |

### B. Contrato `api_contracts/sales-trend-insights.md` (architect)

| Item atual | Mudança |
| :--- | :--- |
| Body do `POST /generate`: `deep` | **Remover** (e `400 TIA-001` por `deep` não booleano). Manter `force` |
| `meta.tipoAnalise` (`PADRAO`/`APROFUNDADA`) | **Remover** (e do diagnóstico salvo e do tipo TS) |
| `meta.escalonadoAutomaticamente`, aviso `ESCALONAMENTO_NEGADO_POR_ORCAMENTO` | **Remover** |
| `meta.modelo` | Passa a ser `gemini-4-hydrogen` ou `gemini-3.8-flash` (fallback) |
| Botão "Análise aprofundada" | **Remover** da especificação de UI |
| Novo `meta.ia.origem` | `"IA"` \| `"TEMPLATE"` \| `"CACHE"` (para a tela rotular "Resumo automático (sem IA)") |
| Novo `meta.ia.motivoTemplate` (opcional) | `GATE_VARIACAO` \| `GATE_RESIDUO_BAIXO` \| `GATE_VALOR_BAIXO` \| `ORCAMENTO_ESGOTADO` \| `IA_DESLIGADA` \| `IA_INDISPONIVEL` |
| `meta.ia.motivoBloqueio` | Acrescentar `IA_DESLIGADA` (kill-switch) e `LIMITE_DIARIO_USUARIO`; revisar se `ORCAMENTO_ESGOTADO` ainda bloqueia o botão ou apenas devolve template |
| `503 TIA-004` `ORCAMENTO_ESGOTADO` / `IA_INDISPONIVEL` | Decidir: manter 503 ou passar a **200 com resumo por template** (recomendado: 200 + `origem=TEMPLATE`, preserva a UX e o gasto zero). Registrar no ADR-009 |
| `429 TIA-004` `LIMITE_DE_PEDIDOS` | Limite muda para 2/min; novo `motivo` `LIMITE_DIARIO` para 10/dia e `force` 3/dia |
| `meta.reutilizado` | Passa a cobrir também reuso por `evidenceHash` de carga nova; novo `meta.geradoEm` + `meta.vencido` (boolean, TTL lógico de 30 dias) para o botão "Atualizar" |
| Campos do diagnóstico | Limites menores: máx. 5 fatores, 2 fontes por fator, 3 hipóteses, 3 recomendações, `resumo` ≤ 400, `explicacao` ≤ 160 (ajustar `maxItems`/descrições) |
| Chave do cache (descrição) | Substituir `dataReferencia` por `evidenceHash` (interno; não exposto) |
| `GET .../insights/health` | Acrescentar `gastoMesUsd`, `tetoMesUsd`, `gastoDiaUsd`, `consultasBuscaMes`, `iaLigada`; remover o modelo de escalonamento |
| Timeout HTTP 150 s / prazo 110 s | Sem mudança; com 2 tentativas + Flash, verificar se 110 s ainda cabe |
| ADR-009 | `architect` atualiza: remover Neon, Flash fallback, teto US$ 2, Vertex AI como backend padrão, cache por `evidenceHash`, livro de gastos |

### C. Pendências externas
- `devops`: Cloud Billing Budget de US$ 2 (alertas 50/80/100%), contar jobs do Cloud Scheduler na conta (grátis até 3), bucket na mesma região do Cloud Run, conferir SKU/preço do Vertex AI para Hydrogen e 3.8 Flash.
- `privacy_officer`/`security`: sem mudança de dados; o kill-switch e o livro não guardam PII.

## Próximos passos (Etapa 3)
- Spike de 1 h com o SDK `google-genai`: confirmar sintaxe da Interactions API (`system_instruction`, `response_format`, `tools`, `thinking_level`, `store`), presença de citações com saída JSON, campos de `usage` e consumo real de tokens/consultas.
- `tester`: dublê do `LlmClient` e casos C-30..C-35 + red teaming da §12.3.
