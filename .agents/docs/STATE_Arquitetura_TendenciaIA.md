# STATE — F7 Diagnóstico de Motivos da Tendência com IA (Arquiteto)

> Estado paralelo ao `STATE.md` (não editado). Responsável: `architect`. Etapa 2 concluída em 2026-11-24 e **revisada (v2) na mesma data** com as decisões de custo do usuário; aguardando o checkpoint. **Revisão v3 (2026-11-26): DA-13, radar externo.** Nada de código de produção nem commit.

| Campo | Valor |
| :--- | :--- |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **ADR** | `ADR-009-diagnostico-tendencia-ia.md` (DA-01..**DA-13**, CP-1..**CP-18**; revisão v3) |
| **Contrato** | `api_contracts/sales-trend-insights.md` (`trend-insights` **1.2.0**; 1.0.0 nunca implantada) |
| **Checklist** | `tasks/analytics-tendencia-ia.md` (7.0c, 7.1, 7.1-M, **7.2-S** ampliado, **7.2-B**, 7.2, **7.2-R radar v3**, 7.3, 7.4, 7.5) |
| **Ajuste em contrato existente** | `api_contracts/analytics-sales-trend.md`: `comparisonMode` e `meta.modoComparacao` documentados (seção 2.6), versão mantida |
| **Insumos incorporados** | `architecture/trend-insights-llm.md` (`ai_specialist`, inclui §14 custo/teto), `privacy/analytics-tendencia-ia.md` (LGPD-TIA-01..14), `design/plans/analytics-tendencia-ia.md` (Q-D1..Q-D9), `STATE_IA_TendenciaIA.md` (impactos A/B/C) |
| **Não tocados nesta revisão** | `business_rules/analytics-tendencia-ia.md` e `GLOSSARY.md` (a cargo do `analyst`, em paralelo) |

## Decisões principais
1. Módulo novo `src/modules/trend_insights/` por portas e adaptadores; só `adapters/` importa `sales_trend`/`analytics`; `sales_trend` continua isolado (ADR-003).
2. Migração: **4 datas sempre** (`fetch_customer_sku_split_window_sales`, SELECT-first, sem CTE/CONCAT, 5 bind params, `fetchmany`, tuplas compactas), em todos os modos e inclusive nas janelas contíguas; a função contígua da F6 nunca é chamada pela F7 (espião no teste). Alimenta `compute_directional_migration` sem cópia; `k` antes; clientes perdidos na mesma etapa volátil; `del` antes do cache (LGPD-TIA-02). Cache por `(modo, janela, mesBase, dataReferencia, geração do índice)`, TTL 6 h, voo único, 1 carga por instância, LRU 8.
3. Índice de afinidade no GCS (concorrência por geração, refresh de 15 min), sem reconstrução no cold start; laço 00:00 removido; Cloud Scheduler com OIDC; sem índice, afins `NAO_AVALIADO` + `TIA-005`. Erros da rota interna **`TIA-006` (401) e `TIA-007` (409) oficiais**.
4. GCS único por ambiente: diagnósticos (90 dias), índice, **livro de gastos `ai-budget/`** (400 dias), leases.
5. **LLM (v2):** `gemini-4-hydrogen` sempre; **Neon removido**; `gemini-3.8-flash` só como fallback de falha de infraestrutura (1 chamada), senão template; **Vertex AI** com ADC (sem `GEMINI_API_KEY`, sem `TREND_AI_BACKEND`); sem `temperature`, `thinking low`; prazo total 110 s.
6. **Custo (v2):** teto **US$ 2,00/mês** total (LLM 1,80 + diário 0,20 + infra); livro de gastos no GCS com **reserva e acerto** e falha fechada; kill-switch `TREND_AI_ENABLED`; Cloud Billing Budget de US$ 2 (medição independente); degradação em `ALERTA` (80%) e `ESGOTADO` → **resumo por template** (`200`, sem LLM); ~104 gerações/mês (~55 no pior caso); rate limit 2/min, 10/dia, `force` 3/dia.
7. **Cache (v2):** chave `(escopo, id, metric, window, baseMonth, comparisonMode, PROMPT_VERSION, evidenceHash)` **sem `dataReferencia`** e sem usuário; TTL lógico 30 dias (`meta.ia.diagnosticoVencido`); cache de contexto do Gemini rejeitado; `PROMPT_VERSION = "tia-v2"` (pacote 8.000 caracteres, 5 fatores, `resumo` ≤ 400).
8. **Gates (v2):** não chamada (P-188: variação ínfima, base insuficiente, delta < R$ 1.000, resíduo < 0,20 sem região/mercado) e de *grounding* (mercado em queda/alta, resíduo ≥ 0,30, `REGIONAL` com resíduo ≥ 0,15; 0,50 em `ALERTA`), `MAX_SEARCH_QUERIES = 2`.
9. **Contrato 1.1.0:** `meta.origem` (`llm`\|`cache`\|`template`\|`fallback`) no `POST`; `meta.ia.{geraComIa, motivoTemplate, podeForcar, diagnosticoVencido, orcamento.nivel}`; `explicacao`; contagens `"<3"`; `SEM_DATA`; sem `deep`, `tipoAnalise`, escalonamento e `desatualizado`; **IA indisponível/sem orçamento não é erro** (200 + template; `TIA-004` só `429`: `LIMITE_DE_PEDIDOS`, `LIMITE_DIARIO`); **nenhum valor de custo exposto** (dólares, percentual, tokens, consultas, preços, tetos, `evidenceHash`; seção 4.4); `health` com `ia.ligada` e `orcamento.nivel`.
10. **IA sem números no texto:** `resumo`, `explicacao`, recomendações e descrições de hipótese sem dígitos; grandezas só nos campos do motor; validação rejeita dígitos; produtos citados por `skusCitados`.

## Revisão v3 — investigação externa (DA-13, 2026-11-26)
11. **Radar externo compartilhado** (GCS `radar/{versão}/{slug}/{AAAA-MM}.json`, sem dado da empresa, single-flight, TTL 30/180 dias, *stale* até 120, `force` não renova), 8 dimensões fixas, saída **sem texto livre** (enums, `tema` fechado, frases fixas do backend), 5 consultas sugeridas. Diagnóstico sem ferramentas recebe o radar como dado; busca do produto só com `SEM_RADAR`. Causalidade (tempo e direção) calculada pelo backend.
12. **Modelo do radar configurável** (`TREND_AI_MODEL_RADAR`, padrão Hydrogen; Flash só após a 7.5 e a validação de busca + schema no Vertex). **Teto duro `GROUNDING_HARD_CAP_QUERIES = 1.500/mês`**: nunca se paga busca. Custo: radar US$ 0,0137, diagnóstico US$ 0,0177, ambos US$ 0,0314; **~83 diagnósticos/mês** no teto de US$ 1,80; teto total de US$ 2 inalterado.
13. **Prazos:** `LLM_TOTAL_DEADLINE_SECONDS` 125 s, trava de voo 150 s, radar 55 s, reserva 180 s, HTTP da tela 150 s (confirmado). **Contrato 1.2.0** aditivo: `fatoresExternos[8]`, `radar`, `radarExterno`, `meta.ia.radar`, avisos `RADAR_DESATUALIZADO`/`SEM_RADAR_EXTERNO`, motivos novos; custo, consultas e teto seguem fora da API.
14. **Divergência registrada:** o `ai_specialist` listou `consultasBuscaMes` no `health`; **não** foi incluído porque o contrato 4.4 proíbe expor consultas (só `radar.radaresEmCache`, `radaresGeradosMes`, `radarVersion`).

## Estimativa de memória (hipótese; medir na 7.1-M)
Pico transitório ~30 MB (`point` X=1) a ~90–130 MB (`average` X=12); residente ≤ 40 MB (8 snapshots) + ≤ 6 MB (evidências). Meta: pico incremental ≤ 200 MB, residente ≤ 50 MB. Medição: CLI `run_migration_memory_report.py` no banco real e gráfico de memória do Cloud Run.

## Pontos para o checkpoint
**Resolvidos na v2:** CP-3 (TIA-006/007), CP-4 (limites), CP-5 (sem histórico, `evidenceHash`), CP-9 (Vertex AI).
**Abertos:** **CP-16 radar compartilhado e injeção persistente (red team do `security`) · CP-17 preço, cota e SKU do grounding no Vertex, busca + schema no Vertex (spike 7.2-S ampliado) · CP-18 regras P-174.1..P-188 para o `analyst`** · CP-1 variante de 4 datas (reafirmada) · CP-6 geração do índice na chave do cache · CP-8 senhas no workflow de deploy (fora do escopo) · **CP-10 Termos do grounding × texto puro (aberto; atenuado pelo texto sem números)** · CP-11..CP-14 ajustes de texto nas regras para o `analyst` (consultas sugeridas, custo por consulta, data das fontes, `<3`, `OUTRAS`, `explicacao`, `LLM_TOTAL_DEADLINE_SECONDS`, texto sem números, P-174/P-175/P-176/P-177/P-178/P-179/P-180/P-181/P-183/P-185.4 e nova P-188) · **CP-15 preço do Vertex, Interactions no Vertex, schema + grounding no Flash e escopo da cota grátis (spike 7.2-S)**.

## Pendências e alertas para outros agentes
- `devops` (v3): ciclo de vida de `radar/` com retenção de **210 dias** (validade de 180 para meses antigos), variáveis novas no deploy (`TREND_AI_MODEL_RADAR`, `GROUNDING_HARD_CAP_QUERIES`, `RADAR_*`, prazos 125/150/180), `pricing.json` com o preço de busca após o spike, `verify_checks.py` e runbook (invalidar radar, acompanhar o teto de 1.500). `04-budget.sh` inalterado. Detalhe: tarefa D-7.2R.17.
- `privacy_officer`: registrar que a chamada com busca do radar não leva dado comercial nem pessoal (D-7.2R.18). `security`: red team do radar (D-7.2R.19). `designer`: painel de 8 fatores externos e `radarExterno` (D-7.2R.20).
- `analyst`: aplicar as revisões da seção A de `STATE_IA_TendenciaIA.md` e o CP-14 (as regras e o glossário seguem em edição paralela).
- `designer`: o Design Plan previa orçamento usado/restante, "Análise aprofundada" e "desatualizado"; o contrato 1.1.0 só entrega `orcamento.nivel`, `geraComIa`/`motivoTemplate`, `diagnosticoVencido` e `podeForcar`. Ajustar os estados do botão e o rótulo "Resumo automático (sem IA)".
- `devops`: Cloud Billing Budget US$ 2 (50/80/100%), contagem de jobs do Scheduler, SKU/preço do Vertex, `roles/aiplatform.user`, sem Secret Manager para IA, lifecycle `ai-budget/`.
- `security`/`privacy_officer`: sem dado novo; o livro e o kill-switch não guardam PII; CP-10 segue aberto.

## Log
- **2026-11-24 — architect:** ADR-009, contrato `trend-insights` 1.0.0, checklist F7 e documentação de `comparisonMode`; incorporados retornos do `designer`, `privacy_officer` e `ai_specialist`.
- **2026-11-24 — architect (revisão v2):** ADR-009 (modelos, DA-09 reescrito, DA-10 Vertex, novo DA-12, CP-3/4/5/9 resolvidos, CP-14/15), contrato 1.1.0 (seção 0 de histórico, 4.4 sem custo), checklist com 7.2-S (spike), 7.2-B (orçamento, livro, kill-switch, gates, template) e 7.2 reescrita, critérios de custo testáveis.
- **2026-11-26 — architect (revisão v3):** ADR-009 DA-13 e CP-16..18 (DA-13 prevalece sobre DA-09/DA-10/DA-12 onde divergir), contrato **1.2.0**, checklist com a tarefa 7.2-R (fases R1..R8, testes C-36..C-45), spike 7.2-S ampliado (grounding/preço no Vertex, calibração do radar) e métricas D-7.5.4. `business_rules` e `GLOSSARY` não tocados (analyst). Sem código nem commit.
