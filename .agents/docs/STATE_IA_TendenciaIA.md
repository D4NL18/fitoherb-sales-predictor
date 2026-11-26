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

## Revisão v3 — Investigação externa (radar externo + checklist de 8 dimensões) — 2026-11-25

Diretriz do usuário: a pesquisa no Google não pode ser só em casos específicos; política, clima, custo e demanda de matéria-prima e outros fatores externos entram **sempre que o LLM for chamado**. Desenho completo em `architecture/trend-insights-llm.md` **§15** (§14.6 e P-180.1 marcados como superados). Nenhum arquivo de `business_rules`, `api_contracts`, ADR ou código foi alterado.

**Decisões:** (1) radar externo por `(matéria-prima ou categoria, mês-base)`, 1 chamada Hydrogen com busca, **sem dado da empresa**, cache GCS compartilhado, TTL 30 dias (90 para meses antigos), `force` não o renova; (2) diagnóstico do produto **sem ferramentas** recebe o radar como dado e devolve 8 `avaliacoesExternas` (nunca omite dimensão; `SEM_EVIDENCIA` explícito); (3) 0 ou 1 consulta específica do produto, pelas antigas condições de P-180.1; (4) tempo e direção calculados pelo backend (`POSTERIOR`/`SEM_DATA` nunca são causa); (5) orçamento esgotado: template + radar existente só leitura, sem nova busca; (6) Flash faz fallback do diagnóstico com o mesmo radar, sem busca.

**Custo (Vertex regional 1,65/8,25):** radar US$ 0,029 (cota grátis) / 0,113 (busca cobrada); diagnóstico com radar em cache US$ 0,020; com 1 consulta do produto 0,023; radar novo + diagnóstico 0,049; Flash 0,010 (até 31/12) / 0,020; cache e template 0. **Capacidade com LLM ≤ US$ 1,80: ~60 diagnósticos/mês** (46 a 69 com 25 a 8 radares/mês) contra ~96 da v2; ~110 consultas de busca/mês (2,2% das 5.000 grátis).

## Otimização v3.1 de custo (2026-11-26) — prevalece sobre os valores da v3 abaixo

Detalhe em `architecture/trend-insights-llm.md` **§15.14**. **Capacidade com LLM ≤ US$ 1,80: ~83 diagnósticos/mês** (75 a 88 conforme 25 a 8 radares/mês; era ~60 na v3 inicial e ~96 na v2 com busca em só ~50%). Custo: radar US$ 0,0137 (5 consultas, cota grátis; Flash US$ 0,0068 até 31/12/2026), diagnóstico com radar em cache US$ 0,0177, radar novo + diagnóstico US$ 0,0314, fallback Flash 0,0089 até 31/12, cache e template 0. Busca: ~75 consultas/mês (1,5% das 5.000 grátis) com teto duro `GROUNDING_HARD_CAP_QUERIES = 1.500` (acima dele, sem radar novo nem busca: nunca se paga busca de propósito).

**Adotado:** radar sem texto livre (`tema` fechado + frase fixa do backend, saída ~1.000 tokens, injeção persistente quase eliminada); 5 consultas (funde custo, oferta/demanda e câmbio/logística); prompt do radar comprimido; 1 fonte por dimensão; diagnóstico sem busca própria (só com `SEM_RADAR`); contexto do radar ~450 tokens; fusão de famílias de matéria-prima; `TREND_AI_MODEL_RADAR` configurável (padrão Hydrogen; Flash só até 31/12 ou se a 7.5 aprovar); fallback Flash do radar permitido; reordenar prompt (system, radar, evidências) para cache implícito, sem orçar. **Rejeitado com números:** radar em lote (~US$ 0,03/mês de ganho, mais risco), radar por categoria (perde o insumo), TTL por dimensão com refresh incremental (~US$ 0,016/mês).

**Confirmações (26/11/2026):** grounding no Vertex é cobrado por consulta executada (Gemini 3; Gemini 4 não confirmado); preço e cota grátis no Vertex **não confirmados** (página truncada; versões indicam 5.000 grátis e US$ 14/1.000, outra US$ 35/1.000 prompts; aviso de mudança em 13/11/2026); `gemini-3.8-flash` combina busca + JSON Schema em Preview segundo a doc do AI Studio (Vertex a validar no spike).

**Ajustes sobre a seção A/B/C/D abaixo:** constantes `RADAR_MAX_SEARCH_QUERIES_SUGGESTED` 5, `RADAR_RESERVATION_QUERIES` 6, `RADAR_MAX_OUTPUT_TOKENS` 1.500, `RADAR_TTL_PAST_DAYS` 180, `RADAR_BUDGET_SHARE` 0,25, `MAX_RADAR_CONTEXT_CHARS` 2.000; novas `GROUNDING_HARD_CAP_QUERIES`, `TREND_AI_MODEL_RADAR`, `RADAR_THEMES`, `RADAR_THEME_TEXTS`. **P-180.1** passa a "busca do produto só com `SEM_RADAR`"; **P-180.3** inclui teto duro de consultas e fallback Flash do radar; **P-178.2** reserva do radar de ~US$ 0,02 (6 consultas dentro da cota). Contrato: `radar.dimensoes[].tema` (enum) com `nota` gerada pelo backend, `fontes` ≤ 1 por padrão. Código: `domain/radar_themes.py` (novo, temas e frases), `radar_schema.py` com `tema` e sem texto livre, `radar_policy` considera o teto duro, `RadarRunner` com modelo configurável e fallback Flash. Testes novos: radar sem texto livre (nenhuma string da web chega ao radar armazenado), teto duro de 1.500 consultas, busca do produto só com `SEM_RADAR`, fusão de famílias gera o mesmo slug, ordem do prompt (radar antes das evidências), custo do radar dentro de US$ 0,02 na reserva.

## Impactos nas regras, no contrato e no código (v3)

### A. Regras e constantes (`business_rules/analytics-tendencia-ia.md`, para o `analyst`)

| Regra / constante | Mudança exata |
| :--- | :--- |
| **P-180** | Reescrever título e declaração: "Investigação externa v3". Pesquisa externa **sempre** considerada em diagnóstico por LLM via radar (P-180.3) e checklist de 8 dimensões (P-180.4). Consultas do radar vêm de tabela fixa; consulta do produto sugerida (máx. 1) |
| **P-180.1** | **Revogar** o gate de grounding. Reaproveitar o ID como "Busca específica do produto": liga só com termo de busca, modo ≠ `QUALITATIVO`, orçamento `NORMAL` e (mercado em queda/alta com `REGIONAL`, ou resíduo ≥ 0,30, ou `REGIONAL` e resíduo ≥ 0,15, ou participação com fornecedor) |
| **P-180.2** | Contingência de 2 chamadas passa a valer só para o **radar** |
| **P-180.3 (nova)** | Radar: chave `(RADAR_PROMPT_VERSION, slug do assunto, AAAA-MM)`, conteúdo, TTL 30/90 dias, stale até 120, compartilhado, sem dado da empresa, single-flight, sem Flash, `force` não renova, tetos `RADAR_BUDGET_SHARE` e `RADAR_MAX_NEW_PER_DAY` |
| **P-180.4 (nova)** | Checklist fixo das 8 dimensões, uma linha cada, nunca omitida; assunto inferido de forma determinística (função primária → matéria-prima; palavra-chave; categoria) |
| **P-180.5 (nova)** | Causalidade: `relacaoTemporal` e `rotulo` calculados pelo backend; `POSTERIOR`, `SEM_DATA` e `ANTIGA` nunca são causa; coerência direcional; `SEM_EVIDENCIA` ≠ "não houve" |
| **P-181** | `fatoresExternos[]` (8 itens fixos) e `fatores[].dimensao`; no máx. 3 externos entre os 5 fatores; externo sem `parcelaEstimada` e confiança ≤ `MEDIA` |
| **P-182.1** | Estender "sem dígitos" à `nota` das dimensões; `fonteIds` com gramática `^[FP][0-9]{1,2}$` |
| **P-182.4 / P-182.5** | Fonte do fator externo vem do radar (id) ou da busca do produto; data validada no radar; `relacaoTemporal` do P-180.5 substitui a decisão por data isolada |
| **P-174.1** | Template pode trazer o bloco `radarExterno` (somente leitura, sem `direcao`), sem citar fator externo no texto do resumo |
| **P-175 / P-175.6** | `PROMPT_VERSION = "tia-v3"`; chave de cache do diagnóstico **inalterada** (radar não entra na chave); guardar `radarRef`; TTL lógico de 30 dias vale para todo diagnóstico por LLM |
| **P-176.2** | `IN_FLIGHT_LOCK_TTL_SECONDS` 120 → 150; trava própria do radar (90 s) |
| **P-178.1** | Custo inclui radar (tokens + consultas executadas); `GROUNDING_FREE_QUERIES_ASSUMED` (1.500) inalterado |
| **P-178.2** | Reserva do radar (6.000 entrada, 3.000 saída, 8 consultas: ≈ US$ 0,035; ≈ US$ 0,15 acima da cota assumida) e do diagnóstico (7.000/2.500, 1 consulta) |
| **P-178.3** | Livro `ai-budget/AAAA-MM.json` ganha `gastoRadarMes`, `radaresNovosMes`, `radaresNovosDia` |
| **P-178.4** | A 80%: sem busca do produto; radar novo só se não houver nenhum (fresco ou stale); remove "resíduo ≥ 0,50" |
| **P-178.5** | Ao esgotar: template + radar existente (sem nova busca) |
| **P-183** | Radar: 1 nova tentativa por schema, sem Flash; diagnóstico Flash sem ferramentas e com radar; `LLM_TOTAL_DEADLINE_SECONDS` 110 → 125 |
| **P-184** | Radar como superfície persistente de injeção: sanitização das notas, `<radar_externo_{nonce}>`, referência só por id, invalidação por versão |
| **P-179** | Novo limite `MAX_RADAR_CONTEXT_CHARS = 3.000`; `MAX_EVIDENCE_PAYLOAD_CHARS` (8.000) inalterado |
| **P-188** | Sem mudança nos gates; não cria radar novo (só exibe o existente) |
| Constantes | §15.12 do documento de arquitetura (remover `GROUNDING_MIN_RESIDUAL_SHARE_ALERT` e `MAX_SEARCH_QUERIES_QUALITATIVE`; renomear `GROUNDING_*` e `MAX_SEARCH_QUERIES` para `PRODUCT_SEARCH_*`; criar as `RADAR_*`) |
| Casos de teste (C-xx) | Revisar **C-28b** (resíduo 25%: agora chama o LLM com radar e sem busca do produto) e **C-29a** (a 80% a busca do produto desliga, não "resíduo ≥ 0,50"); novos C-36 a C-45 (seção D) |

### B. Contrato `api_contracts/sales-trend-insights.md` (para o `architect`; versão 1.2.0)

| Campo / item | Mudança |
| :--- | :--- |
| `diagnosticoIa.fatoresExternos[8]` | **Novo.** `{dimensao, status, direcao, confianca, relevanciaAoProduto, relacaoTemporal, rotulo, origemEvidencia, motivoNaoAvaliado?, nota ≤ 160, fontes[≤2]}`; sempre 8 itens em ordem fixa; enums da §15.6 |
| `fonte` | Acrescentar `id` (`F1..F16`/`P1`); `origemData` aceita `SEM_DATA`; `dataPublicacao` continua anulável |
| `fatores[]` | Acrescentar `dimensao` (anulável nos internos); `tipo` externo mantém os 5 valores atuais |
| `hipotesesNaoConfirmadas[].motivo` | Acrescentar `POSTERIOR_AO_PERIODO`, `SEM_COERENCIA_DIRECIONAL` |
| `diagnosticoIa.radar` | **Novo.** `{assunto: {termo, tipo}, mesBase, geradoEm, diasDesdeGeracao, desatualizado, origem: GERADO_AGORA \| CACHE}` ou `null` |
| `meta.ia.radar` | **Novo.** `{estado: FRESCO \| DESATUALIZADO \| AUSENTE \| GERADO_AGORA, geradoEm}` |
| Resposta `TEMPLATE` | `radarExterno` **novo**, somente leitura (dimensão, `movimento`, `nota`, fontes; sem `direcao`) |
| `meta.avisos` | Acrescentar `RADAR_DESATUALIZADO`, `SEM_RADAR_EXTERNO`; `SEM_BUSCA_EXTERNA` passa a significar "sem radar e sem busca do produto" |
| `sugestoesBuscaHtml` | Pode vir do radar e do diagnóstico (lista); mesma exceção de `iframe sandbox` |
| `promptVersion` | `"tia-v3"` |
| `GET .../insights/health` | Acrescentar `radaresEmCache`, `radaresGeradosMes`, `radarVersion`; mantém `consultasBuscaMes` |
| Limites | `fatores[]` ≤ 5 (≤ 3 externos); `avaliacoesExternas` é interno ao LLM e não é exposto |
| Timeout | Confirmar 125 s de prazo de LLM dentro do HTTP de 150 s |
| ADR-009 | Registrar o radar como decisão (alternativas: busca por produto, radar por produto) |

### C. Código (`src/modules/trend_insights/`)

| Módulo | Mudança |
| :--- | :--- |
| `domain/constants.py` | Constantes da §15.12 |
| `domain/gates.py` | `grounding_enabled(evidence, budget_level)` → `product_search_enabled(evidence, budget_level)` (remove ramo `ALERT`; desliga fora de `NORMAL` e no `QUALITATIVO`; acrescenta condição (d)); nova `radar_policy(radar_state, budget_level, daily_new, share_spent)` pura → `USE_FRESH \| GENERATE \| USE_STALE \| NONE`. `evaluate_llm_gates` **inalterado** |
| `domain/external_dimensions.py` (novo) | `EXTERNAL_DIMENSIONS`, mapeamento para `fatores[].tipo`, `temporal_relation(date, window)`, `directional_coherence(direcao, variacao)` |
| `domain/raw_material.py` (novo) | `infer_radar_subject(evidence) -> RadarSubject` e tabelas de termos |
| `domain/budget.py` | `reservation_amount` com variante radar; checagem de `RADAR_BUDGET_SHARE` |
| `domain/template_summary.py` | Anexar bloco `radarExterno` somente leitura (texto do resumo inalterado) |
| `llm/search_queries.py` | `build_search_queries` → `build_product_query` (0 ou 1); nova `build_radar_queries(subject, base_month)` com `RADAR_QUERY_TEMPLATES` |
| `llm/radar_schema.py` (novo) | `RadarOutput`, `RadarDimension`, `RadarSource` (schema raso) |
| `llm/prompts.py` | Diretório `tia_v3`: S1 regra 4 revista, S2 como checklist, U5 `<radar_externo_{nonce}>`, prompt do radar `radar_v1`; `build_prompts(..., radar)` |
| `llm/output_schema.py` | `LlmDiagnosisOutput.avaliacoesExternas` (8 itens, `fonteIds`), limites novos |
| `llm/validation.py` | Validar 8 dimensões, `fonteIds ⊆ radar ∪ busca`, dígitos em `nota`, `temporal_relation`, coerência direcional, promoção a `fatores[]`, sanitização e marcadores de injeção das notas do radar; completar dimensões omitidas |
| `llm/evidence_payload.py` | Montar o bloco compacto do radar (≤ 3.000 caracteres) fora do `evidenceHash` |
| `llm/gemini_client.py` | Sem mudança de interface; diagnóstico com `tools=[]` por padrão e radar com busca |
| `store/radar_store.py` (novo) | GCS `radar/{versão}/{slug}/{AAAA-MM}.json`, L1 de 5 min, TTL 30/90, stale 120, escrita `if_generation_match` |
| `store/budget_ledger.py` | `reserve`/`settle` por tipo (`RADAR`/`DIAGNOSTICO`) e consultas assumidas; campos de radar no documento; `level()` expõe a parcela de radar |
| `store/insight_store.py` | `StoredInsight.radarRef`; `is_expired` aplica a todo diagnóstico por LLM |
| `service/radar_service.py` (novo) | `get_or_create(subject, base_month)` com lease próprio; retorna `(radar, estado)`; stale e `NONE` |
| `service/llm_runner.py` | `run(evidence, radar, with_product_search)`; novo `RadarRunner` (1 retry de schema, sem Flash, `two_step` opcional); Flash sem ferramentas |
| `service/llm_orchestrator.py` | Passos 6 a 8 da §15.8; template com radar existente; `radarRef` no `StoredInsight` |
| `service/insights_service.py`, `api/router.py` | Campos novos de resposta, `meta.ia.radar`, avisos |
| `config.py` | Variáveis de ambiente novas (TTL, share, tetos); `TREND_AI_PRICING_JSON` inalterado |
| Infra (`devops`) | Ciclo de vida do prefixo `radar/` (120 dias); `deploy` repassa as variáveis novas; conferir SKU de grounding no Vertex |

### D. Testes novos (`tests/trend_insights/`)

| Arquivo | Casos |
| :--- | :--- |
| `test_gates_template.py` (ampliar) | `product_search_enabled`: cada condição (a) a (d), `QUALITATIVO`, níveis de orçamento; `evaluate_llm_gates` não muda; **LLM chamado sempre leva radar** (C-36) |
| `test_radar_subject.py` (novo) | Função primária → matéria-prima; palavra-chave da galeria só por lista fechada; fallback categoria; sem termo → `SEM_TERMO_BUSCA`; slug estável |
| `test_radar_store_policy.py` (novo) | TTL 30/90, stale 120, chave sem SKU/usuário, `force` não renova, single-flight, 2 usuários compartilham (C-37) |
| `test_external_validation.py` (novo) | 8 dimensões sempre (omitida vira `NAO_AVALIADA`); `SEM_EVIDENCIA` ≠ `NEUTRA`; `POSTERIOR`/`SEM_DATA`/`ANTIGA` nunca em `fatores[]`; coerência direcional; confiança nunca `ALTA`; no máx. 3 externos; `fonteIds` fora do radar rejeitado; dígito em `nota` bloqueia (C-38 a C-41) |
| `test_radar_injection.py` (novo) | Nota com instrução, URL ou `<>{}` rejeitada; radar envenenado não altera o schema nem cria número; `injectionSuspect` no log sem payload (C-42) |
| `test_budget.py` (ampliar) | Reserva do radar; `RADAR_BUDGET_SHARE`; `RADAR_MAX_NEW_PER_DAY`; 80% sem busca do produto e radar só se ausente; esgotado → template com radar stale sem nova chamada; busca cobrada acima de 1.500 (C-43, C-44) |
| `test_llm_orchestrator.py` (ampliar) | Ordem de decisão da §15.8; radar falha → diagnóstico segue com `SEM_RADAR`; Flash usa o mesmo radar sem ferramentas; cache do diagnóstico não depende do radar (C-45) |
| `test_evidence_payload.py` (ampliar) | Radar fora do `evidenceHash`; bloco do radar ≤ 3.000 e sem dado de cliente |
| `test_api_contract.py` (ampliar) | `fatoresExternos` (8 itens), `radar`, `meta.ia.radar`, avisos e `promptVersion = "tia-v3"` |
| Avaliação 7.5 | Métricas da §15.13 e red team da §15.11 |

### E. Pendências
- `devops`: ciclo de vida do prefixo `radar/`, variáveis no deploy, SKU e cota de grounding no Vertex (não confirmados).
- `privacy_officer`: registrar no RIPD que a chamada com busca do radar não contém dado comercial nem pessoal.
- Spike da Etapa 3 calibra tokens e consultas reais do radar; se passar de US$ 0,05, reduzir para 4 consultas.
