# Release da F7 (Tendência de Vendas com IA): checklist, rollback e PR

## 1. Checklist de pré-deploy (todos os itens bloqueiam)

**Código e qualidade**
- [ ] `pytest tests/trend_insights` verde (262 testes) e `pytest` completo verde; cobertura de `trend_insights` ≥ 80%; `ruff` limpo; build Angular e testes do frontend verdes.
- [ ] Revisão do `security` da isenção Basic da rota OIDC concluída (D-7.0c.7); F-02 (cache de certificados do verificador) avaliado.
- [ ] CI: o workflow atual só roda `tests/test_auth.py` e `tests/test_elasticity_model.py`; incluir `tests/trend_insights` no job (pendência de CI, fora desta entrega).

**Gate de memória (7.1-M)**
- [ ] `run_migration_memory_report` executado contra o banco real; pico incremental ≤ 200 MB, residente ≤ 50 MB, `query_ms` ≤ 20 s; números gravados no ADR-009 e em `STATE_Arquitetura_TendenciaIA.md` (procedimento em `devops/trend-insights-infra.md` §6).

**Spike e pendências de decisão**
- [ ] Spike 7.2-S feito (tokens, schema + grounding no Flash, preço no Vertex); `TREND_AI_PRICING_JSON` conferido (hoje regional, +10%).
- [ ] CP-10 (termos do grounding) decidido; A-3 registrado no ADR-009 (retenção/treino do Vertex) e região `us-central1` registrada (A-2).

**Infraestrutura (`infra/trend-insights/`)**
- [ ] `01-bucket.sh`, `02-iam.sh`, `03-scheduler.sh` (jobs da conta ≤ 3 ou custo aceito), `04-budget.sh` executados.
- [ ] Variáveis de repositório da tabela §3 do runbook definidas; `GEMINI_API_KEY` inexistente.
- [ ] `06-verify.sh` termina com "conforme" **após** o deploy (reauditar A-1/A-2 com o `privacy_officer`).
- [ ] Projeto com faturamento ativo (nível gratuito vedado, LGPD-TIA-08).

**Segurança fora do escopo (decisão do usuário)**
- [ ] F-01 `AUTH_PASSWORD` com padrão literal: tratada em sessão separada; **não liberar produção sem decisão explícita**.

## 2. Verificação pós-deploy (em ordem)

1. `bash infra/trend-insights/06-verify.sh`.
2. `bash infra/trend-insights/03-scheduler.sh --run-now`; `GET /api/v1/sales-trend/insights/health` mostra `indiceAfinidade.disponivel=true` e `ia.ligada=true` (sem valores em dólar).
3. `curl -i -X POST <url>/internal/v1/affinity-index/sync` sem token → 401; com Basic e sem OIDC → 401.
4. Abrir o painel "Por que?" de um SKU; gerar 1 diagnóstico; segunda geração do mesmo dado → `origem=cache`.
5. Primeira semana: Memory utilization, `ai-budget/AAAA-MM.json` × fatura (diferença ≤ 20%).

## 3. Rollback

| Situação | Ação | Tempo |
| :--- | :--- | :--- |
| IA com custo/erro anômalo | `bash infra/trend-insights/05-kill-switch.sh off` (POST vira template; GET e cascata intactos) | ~1 min |
| Regressão geral da aplicação | `gcloud run services update-traffic <svc> --region southamerica-east1 --to-revisions=<revisao-anterior>=100`; as imagens ficam com tag do SHA | ~1 min |
| Índice de afinidade corrompido/ausente | painel mostra `TIA-005`; `gcloud scheduler jobs run affinity-index-sync --location southamerica-east1`; sem reconstrução na partida | ~5 min |
| Job do Scheduler indevido/custo | `gcloud scheduler jobs pause affinity-index-sync --location southamerica-east1` (a rota manual `POST /api/v1/analytics/affinity/sync` continua) | imediato |
| Estouro de orçamento | Livro já devolve template; reduzir `TREND_AI_MONTHLY_BUDGET_USD` (+ variável do GitHub) | ~1 min |

Dados: o bucket só tem agregados (sem dado de cliente) e expira sozinho; apagar `insights/` é seguro (regenera sob demanda, custo de novas gerações). Não há migração de banco nesta feature, logo rollback de código não exige rollback de dados. Não reverter o deploy removendo as variáveis da F7 sem antes desligar a IA.

## 4. Descrição de PR pré-preenchida (não aberta)

**Título:** `feat(trend-insights): diagnostico de motivos da tendencia de vendas com IA (F7)`

```markdown
## Resumo
Painel "Por que?" na Tendência de Vendas: cascata determinística de fatores (sazonal, preço, lançamento/canibalização, migração de clientes, regional) e diagnóstico em texto por IA (Vertex AI, Gemini 4 Hydrogen, fallback Gemini 3.8 Flash), gerado só por botão, com teto de US$ 2/mês, cache por `evidenceHash` e resumo por template quando a IA não pode rodar.
Também move o índice de afinidade para o GCS e troca o cron do processo por Cloud Scheduler (OIDC).

## Tipo / Triagem
Feature full-stack (T1). Regras P-150..P-188, ADR-009, contrato `sales-trend-insights` 1.1.0.

## O que muda
- Backend: `src/modules/trend_insights/` (domínio puro, adaptadores, LLM atrás de `LlmClient`, livro de gastos, rota GET/POST), consultas SQL aditivas em `analytics`, rota interna `POST /internal/v1/affinity-index/sync`.
- Frontend: painel "Por que?", `?abrir={sku}` na Canibalização, refatorações de a11y aprovadas.
- Infra (`infra/trend-insights/`): bucket privado (UBLA, PAP, lifecycle 90/400/1 dias), IAM mínimo, job do Scheduler 00:00 BRT, Billing Budget US$ 2, kill-switch, verificação somente leitura.
- CI/CD: passo extra no deploy repassa variáveis não secretas `TREND_AI_*`/`AFFINITY_*` (só se `TREND_INSIGHTS_BUCKET` existir).

## Privacidade e segurança
Zero `Cod Cliente` em pacote, cache, GCS, logs e respostas (LGPD-TIA-01..14); texto da IA sem números; sem chave de API (ADC); região do Vertex fixa em us-central1 (A-2); nenhum valor de custo na API.

## Custo (FinOps)
~US$ 0,015 a 0,020 por geração (preço regional do Vertex, +10% sobre o global); ~96 gerações/mês no teto de US$ 1,80; infra ≤ US$ 0,11. Cache e template custam US$ 0. Kill-switch `TREND_AI_ENABLED`.

## Antes do merge/deploy (checklist)
Ver `.agents/docs/devops/trend-insights-pr.md` §1: gate de memória 7.1-M, spike 7.2-S, `06-verify.sh`, decisão sobre `AUTH_PASSWORD` (fora deste PR).

## Rollback
Kill-switch `off`; reverter tráfego da revisão; pausar o job. Sem migração de banco.

## Testes
`tests/trend_insights` (262) + suíte existente; frontend (Jasmine/Karma).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Commits devem seguir Conventional Commits com `P-XXX` e `Co-Authored-By` (git-expert); revisar histórico com `git log origin/main..HEAD --oneline` antes de abrir.
