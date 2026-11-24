# STATE — F7 Diagnóstico de Motivos da Tendência com IA (Arquiteto)

> Estado paralelo ao `STATE.md` (não editado). Responsável: `architect`. Etapa 2 concluída em 2026-11-24, aguardando o checkpoint do usuário. Nada de código de produção nem commit.

| Campo | Valor |
| :--- | :--- |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **ADR** | `ADR-009-diagnostico-tendencia-ia.md` (DA-01..DA-11, CP-1..CP-13) |
| **Contrato** | `api_contracts/sales-trend-insights.md` (`trend-insights` 1.0.0) |
| **Checklist** | `tasks/analytics-tendencia-ia.md` (7.0c, 7.1, 7.1-M, 7.2, 7.3, 7.4, 7.5) |
| **Ajuste em contrato existente** | `api_contracts/analytics-sales-trend.md`: `comparisonMode` e `meta.modoComparacao` documentados (seção 2.6), versão mantida |
| **Insumos incorporados** | `architecture/trend-insights-llm.md` (`ai_specialist`), `privacy/analytics-tendencia-ia.md` (LGPD-TIA-01..14), `design/plans/analytics-tendencia-ia.md` (Q-D1..Q-D9) |

## Decisões principais
1. Módulo novo `src/modules/trend_insights/` por portas e adaptadores; só `adapters/` importa `sales_trend`/`analytics`; `sales_trend` continua isolado (ADR-003).
2. Migração: uma variante SQL de 4 datas (`fetch_customer_sku_split_window_sales`, SELECT-first, sem CTE/CONCAT, 5 bind params, `fetchmany`, tuplas compactas) usada em todos os modos, alimentando `compute_directional_migration` da F6 sem cópia; `k` aplicado antes; clientes perdidos na mesma etapa volátil; `del` das linhas antes do cache (LGPD-TIA-02). Cache por `(modo, janela, mesBase, dataReferencia, geração do índice)`, TTL 6 h, voo único por chave, 1 carga por instância, LRU 8.
3. Índice de afinidade no GCS (concorrência por geração, refresh a cada 15 min), sem reconstrução no cold start; laço 00:00 removido; Cloud Scheduler chama `POST /internal/v1/affinity-index/sync` com OIDC; sem índice, F7 marca afins `NAO_AVALIADO` + `TIA-005`.
4. GCS único por ambiente: diagnósticos (90 dias no bucket), índice, orçamento mensal (CAS), leases (dedup entre instâncias).
5. LLM: SDK `google-genai`, Interactions API, Gemini API paga com `store=false`, Vertex selecionável por `TREND_AI_BACKEND`; modo de 2 chamadas por configuração ou automático; prazo total 110 s; sem `temperature`; pré-checagem de custo por tentativa (~US$ 0,13 / 0,30); rate limit em memória com chave HMAC.
6. Contrato: `meta.ia` (orçamento, geração em voo, data do salvo), `pontosPercentuais`, `TrendCell` nos afins, contagens `<3`, anonimização de `OUTRAS`, fontes com data anulável e `origemData`, `sugestoesBuscaHtml` opcional.

## Estimativa de memória (hipótese; medir na 7.1-M)
Pico transitório ~30 MB (`point` X=1) a ~90–130 MB (`average` X=12); residente ≤ 40 MB (8 snapshots) + ≤ 6 MB (evidências). Meta: pico incremental ≤ 200 MB, residente ≤ 50 MB. Medição: CLI `run_migration_memory_report.py` (`tracemalloc` + `ru_maxrss`) no banco real e gráfico de memória do Cloud Run.

## Pontos para o checkpoint
CP-1 variante de 4 datas em todos os modos · CP-3 códigos `TIA-006`/`TIA-007` da rota interna · CP-4 rate limit por instância com credencial Basic compartilhada · CP-6 geração do índice na chave do cache · CP-8 senhas no workflow de deploy (fora do escopo) · **CP-9 Gemini API × Vertex AI (decisão do usuário)** · **CP-10 Termos do grounding × texto puro (aberto)** · CP-11..CP-13 ajustes de texto nas regras para o `analyst` (consultas sugeridas, custo por consulta, data das fontes, `<3`, `OUTRAS`, `explicacao`, `LLM_TOTAL_DEADLINE_SECONDS`).

## Log
- **2026-11-24 — architect:** ADR-009, contrato `trend-insights` 1.0.0, checklist F7 e documentação de `comparisonMode`; incorporados retornos do `designer`, `privacy_officer` e `ai_specialist`.
