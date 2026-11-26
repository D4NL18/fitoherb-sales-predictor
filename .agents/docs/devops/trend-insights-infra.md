# Infraestrutura da F7 (Tendência com IA): runbook DevOps e FinOps

Cobre D-7.0c.9, D-7.2.13, D-7.2B.10, auditoria LGPD A-1/A-2 e LGPD-TIA-08/09/10. Scripts em `infra/trend-insights/` (idempotentes; nada foi executado no GCP por este trabalho). Decisões de origem: ADR-009 DA-06/DA-07/DA-09; custo: `architecture/trend-insights-llm.md` §14.

## 1. Ordem de execução (operador, uma vez por ambiente)

```bash
export PROJECT_ID=<projeto> ENV_NAME=prod BILLING_ACCOUNT=<XXXXXX-XXXXXX-XXXXXX> ALERT_EMAIL=<email>
bash infra/trend-insights/01-bucket.sh        # bucket + UBLA + PAP + lifecycle
bash infra/trend-insights/02-iam.sh           # SAs e papéis mínimos (repetir após o 1o deploy p/ run.invoker)
# definir variáveis de repositório (seção 3) e fazer o deploy pelo workflow
bash infra/trend-insights/03-scheduler.sh --run-now   # job OIDC + carga inicial do índice
bash infra/trend-insights/04-budget.sh        # Billing Budget US$ 2
bash infra/trend-insights/06-verify.sh        # DEVE terminar com "conforme"; senão, não liberar
```

Pré-requisitos do operador: criar contas de serviço, alterar IAM do projeto e `roles/iam.serviceAccountUser` nas duas SAs (actAs); `roles/billing.costsManager`/admin para o budget; o deployer do workflow também precisa de `iam.serviceAccountUser` na SA de runtime. Rodar em Git Bash/WSL/Cloud Shell.

## 2. O que cada script garante

| Script | Garantia | Requisito |
| :--- | :--- | :--- |
| `01-bucket.sh` | `fitoherb-trend-insights-<env>`, `southamerica-east1`, Standard, UBLA, Public Access Prevention `enforced`, sem versionamento, soft delete desligado (evita 7 dias de retenção cobrada e exclusão adiada), lifecycle de `lifecycle.json` | LGPD-TIA-09/10, A-1, D-7.0c.9 |
| `lifecycle.json` | `insights/` 90 d, `ai-budget/` 400 d, `locks/` 1 d, multipart incompleto 1 d (`INSIGHT_RETENTION_DAYS` agora tem consumidor real) | A-1, FinOps |
| `02-iam.sh` | SA de runtime `sa-fitoherb-run`: `roles/storage.objectUser` **só no bucket** + `roles/aiplatform.user`; SA `sa-affinity-scheduler`: **só** `roles/run.invoker` no serviço; nenhuma chave/segredo | LGPD-TIA-08/10, D-7.2.13 |
| `03-scheduler.sh` | Job `affinity-index-sync`, `0 0 * * *` `America/Sao_Paulo` (horário do antigo `_daily_affinity_cron`), `POST /internal/v1/affinity-index/sync`, OIDC (`aud` = URL do serviço), `attempt-deadline=300s`, 2 retentativas; **conta os jobs da conta de faturamento** e recusa criar acima de 3 sem `ACCEPT_SCHEDULER_COST=yes` | D-7.0c.9 |
| `04-budget.sh` | Budget mensal US$ 2: alertas reais 50/80/100/120% e 100% previsto; e-mail via canal do Monitoring (`ALERT_EMAIL`); escopo projeto, opcional `BUDGET_SERVICES` | D-7.2B.10 |
| `05-kill-switch.sh on\|off` | `TREND_AI_ENABLED` no Cloud Run **e** na variável do GitHub | P-178.5 |
| `06-verify.sh` | Somente leitura: PAP, UBLA, lifecycle, IAM (sem membro público, runtime só `objectUser`, scheduler sem acesso ao bucket), região do Vertex us/eu, ausência de `GEMINI_API_KEY`, `min=0`/`max=3`, variáveis, job OIDC. Falha = bloqueia release | "verificável no script de deploy" (A-1) |

## 3. Variáveis de repositório do GitHub (não secretas) e variáveis do Cloud Run

O passo "Configurar variáveis da F7" do `deploy-cloud-run.yml` só roda se `TREND_INSIGHTS_BUCKET` estiver definida; não toca em segredos nem em `AUTH_PASSWORD` (tratada em sessão separada).

| Variável de repositório | Valor | Vira env no Cloud Run |
| :--- | :--- | :--- |
| `TREND_INSIGHTS_BUCKET` | `fitoherb-trend-insights-prod` | `TREND_INSIGHTS_BUCKET`, `AFFINITY_INDEX_GCS_URI=gs://<bucket>/affinity/product_affinity_index.json` |
| `CLOUD_RUN_RUNTIME_SA` | `sa-fitoherb-run@<proj>.iam.gserviceaccount.com` | `--service-account` |
| `AFFINITY_SYNC_INVOKER_SA` | `sa-affinity-scheduler@<proj>.iam.gserviceaccount.com` | `AFFINITY_SYNC_INVOKER_SA` |
| `TREND_AI_ENABLED` | `true`/`false` (padrão `true`) | idem (kill-switch) |
| `TREND_AI_LOCATION` | `us-central1` (padrão) | idem (A-2: `global` é recusado pelo código) |
| `TREND_AI_MONTHLY_BUDGET_USD` / `TREND_AI_DAILY_BUDGET_USD` | `1.80` / `0.20` | idem |
| `TREND_AI_MODEL_RADAR` | `gemini-4-hydrogen` (padrão) | idem (radar externo, ADR-009 DA-13) |
| `TREND_AI_GROUNDING_HARD_CAP_QUERIES` | `1500` (padrão) | idem (teto duro mensal de consultas de busca) |
| `TREND_AI_GROUNDING_FREE_QUERIES` | `1500` (padrão; cota real confirmada: 5.000) | idem (lido por `config.py`) |
| `TREND_AI_LLM_TOTAL_DEADLINE_SECONDS` / `TREND_AI_IN_FLIGHT_LOCK_TTL_SECONDS` | `125` / `150` | idem |
| (calculadas no passo) | URL do serviço, `infra/trend-insights/pricing.json`, `GOOGLE_CLOUD_PROJECT`, modelos | `AFFINITY_SYNC_AUDIENCE`, `TREND_AI_PRICING_JSON`, ... |

Pontos de atenção: (a) o `gcloud run deploy --set-env-vars` existente recria o conjunto de variáveis e o passo seguinte as reaplica: há uma revisão intermediária sem as variáveis da F7 (segundos; a app cai no modo local/IA sem bucket); (b) por isso o kill-switch grava também a variável do GitHub, senão o próximo deploy religaria a IA; (c) `AFFINITY_SYNC_AUDIENCE` é lido do `status.url` do serviço, o mesmo valor usado como `--oidc-token-audience` em `03-scheduler.sh`.

## 4. Região do Vertex (A-2) e consequência de custo

`TREND_AI_LOCATION=us-central1` (código e `.env.example` já recusam `global`). **Achado FinOps:** a página oficial de preços do Vertex cobra endpoints **não-globais 10% acima do global** (Hydrogen US$ 1,65 / 8,25 por 1M tokens, contra 1,50 / 7,50; Flash 3.8: 0,825 / 4,125 até 31/12/2026, 1,65 / 8,25 depois). `pricing.json` e `.env.example` foram atualizados para os preços regionais; sem isso o livro de gastos subestimaria o custo em 10%. Registrar a região escolhida no ADR-009 (pendência do `architect`; A-3 também fica com ele).

## 5. FinOps: preços reconfirmados (páginas oficiais, 2026-11-25)

| Item | Preço oficial | Fonte | Impacto |
| :--- | :--- | :--- | :--- |
| Cloud Scheduler | US$ 0,10 por job/31 dias; **3 jobs grátis por conta de faturamento** (não por projeto) | cloud.google.com/scheduler/pricing | 1 job: US$ 0 se a conta tiver ≤ 2 outros; contar com `03-scheduler.sh` |
| GCS operações (Standard, região única) | Classe A US$ 0,005/1.000; Classe B US$ 0,0004/1.000; armazenamento ~US$ 0,02/GiB-mês (US$ 0,000027397/GiB-h no grupo em que a página lista São Paulo; confira a linha exata no console) | cloud.google.com/storage/pricing | Confirma o "de memória" da §14.11: < US$ 0,01/mês |
| GCS Always Free | 5 GB, 5.000 Classe A, 50.000 Classe B, **só us-west1/us-central1/us-east1** | idem | **Não** vale em `southamerica-east1`; irrelevante pelo volume |
| Vertex Grounding Google Search (reconfirmado 2026-11-26) | 5.000 consultas grátis/mês **por conta de faturamento**, agregadas entre todos os modelos Gemini 3 e 4; depois US$ 14/1.000; tokens da busca não são cobrados | cloud.google.com/vertex-ai/generative-ai/pricing | Resolve a dúvida "projeto ou conta": é a conta. Outro projeto da conta que use grounding consome a mesma cota |
| Vertex Hydrogen / Flash 3.8 | ver seção 4 | idem | +10% no custo por geração |
| Cloud Run (free tier request-based, base us-central1) | 180.000 vCPU-s, 360.000 GiB-s, 2 mi requisições/mês | cloud.google.com/run/pricing | Cobertura do acordar diário do sync |
| Billing Budget | alertas por e-mail sem custo; **só alerta, não corta** gasto | cloud.google.com/billing/docs/how-to/budgets | Trava real = livro + kill-switch |

### Confirmação de preço e cota de *grounding* (2026-11-26, página oficial do Vertex, curl)

Confirmado em cloud.google.com/vertex-ai/generative-ai/pricing: *Grounding with Google Search*: **5.000 consultas grátis/mês por conta de faturamento, agregadas entre todos os modelos Gemini 3 e Gemini 4**; acima disso **US$ 14 por 1.000 consultas**; cobrança **por consulta executada** (não por *prompt*); tokens de entrada vindos da busca **não** são cobrados. O aviso de 13/11/2026 na página trata de requisições com falha por timeout de cliente/servidor, não do preço da busca.

**Incertezas que permanecem (verificar no Billing real):** (a) a página não distingue endpoint regional de global para o preço da busca (assumido US$ 14 sem acréscimo de 10%); (b) combinação busca + JSON Schema no Vertex em `gemini-4-hydrogen`/`gemini-3.8-flash` não é tratada na página de preços; (c) o `usage` pode não refletir todas as consultas internas. Mitigação: `TREND_AI_GROUNDING_HARD_CAP_QUERIES=1500` e livro com `TREND_AI_GROUNDING_FREE_QUERIES=1500` (30% da cota real); a cota é da conta: outro projeto com *grounding* a consome.

### Tabela de custo atualizada (teto US$ 2,00/mês)

| Cenário (Vertex regional) | Custo/geração (US$) | Gerações/mês no teto de 1,80 |
| :--- | :-: | :-: |
| Hydrogen sem grounding (3.800/1.100 tokens) | 0,0154 | |
| Hydrogen com grounding, cota grátis (5.300/1.300) | 0,0195 | |
| Média (50/50, +8% retentativas), cota grátis | ~0,0188 | **~96** (era ~104) |
| Pior caso, grounding todo cobrado (2 × 0,014) | ~0,0340 | **~53** (era ~55) |
| Fallback Flash sem grounding | 0,0077 até 31/12/2026; 0,0154 depois | |
| Infra F7 (GCS, Scheduler, Cloud Run extra, Budget) | ~0,00 a 0,11 (Scheduler 0 se ≤ 3 jobs; senão 0,10) | |

**Radar externo v3.1 (DA-13):** ~15 a 25 radares/mês x 5 consultas = 75 a 125 consultas (1,5% a 2,5% da cota grátis; 5% a 8% do teto duro de 1.500); custo de busca esperado **US$ 0,00**; pior caso impedido pelo teto duro (nunca se paga busca de propósito). Radar no Hydrogen regional ~US$ 0,02 cada; o Flash só difere até 31/12/2026 (0,825/4,125; depois 1,65/8,25). Retenção física do prefixo `radar/`: 210 dias (`lifecycle.json`), custo de armazenamento desprezível (< 1 MB/mês).

Conclusão: continua cabendo em US$ 2 (LLM 1,80 + infra ≤ 0,11 + margem). A margem de ~US$ 0,10 do livro cobre a diferença de 10%; recalibrar `GROUNDING_FREE_QUERIES_ASSUMED` após uma semana (Cenário 3 da 7.2-B). Atualizar `trend-insights-llm.md` §14.1/§14.10 (pendência do `ai_specialist`/`architect`).

Kill-switch e budget: o budget alerta em 50/80/100/120%; ao receber o alerta de 80% (US$ 1,60), avaliar `05-kill-switch.sh off`. O livro já degrada sozinho (80% do teto interno = ALERTA, 100% = template). Automação por Pub/Sub desligando a IA fica fora do escopo (YAGNI; custo e superfície extras).

## 6. Memória da instância (7.1-M) e gate de deploy

Cloud Run está com `--memory=2Gi`, `--concurrency=80` (P-012, inventário). Estimativa do ADR-009 DA-04: pico transitório da carga de migração ~30 MB (`point` X=1) a **~90-130 MB** (`average` X=12), cache de migração ≤ 40 MB, `EvidenceCache` ≤ 6 MB; meta incremental ≤ 200 MB e residente ≤ 50 MB. Os 2 GiB comportam com folga (baseline do cross-sell da F6 ~320 MB de pico), então **não reduzir a memória** antes de medir; reduzir para 1 GiB só como otimização FinOps posterior se o gráfico "Memory utilization" ficar abaixo de ~50%.

**Procedimento que bloqueia o deploy da 7.1 (não executado aqui; depende de D-7.1-M.1, CLI ainda não existe):**
1. Rodar `python -m src.modules.trend_insights.diagnostics.run_migration_memory_report` (somente leitura) contra o SQL Server real, em máquina com o mesmo driver ODBC.
2. Para cada `(point|average) × (1,3,6,12)`, registrar linhas, clientes distintos, pares, SKUs, `query_ms`, `engine_ms`, pico `tracemalloc`, `ru_maxrss` antes/depois.
3. Aprovar somente se: pico incremental ≤ 200 MB, residente ≤ 50 MB, `query_ms` ≤ 20 s no pior caso. Caso contrário abrir tarefa de leitura em dois passes e **não implantar**.
4. Gravar os números no ADR-009 (seção de estimativa) e em `STATE_Arquitetura_TendenciaIA.md`.
5. Pós-deploy (1ª semana): gráfico "Memory utilization" do Cloud Run e logs por carga (`rows`, `pairs`, `query_ms`, `engine_ms`, `rss_delta_mb`). Gatilho: pico > 300 MB ou `query_ms` > 20 s abre a tarefa de dois passes.

## 7. Cenários de auditoria cobertos pelos scripts

7.0c: cenário 1 (instância sem objeto: `indiceAfinidade.disponivel=false`) antes de `03 --run-now`; cenário 2 depois dele; cenário 3 com `gcloud scheduler jobs run` duas vezes seguidas (um 200, um 409; o job tem retentativas, então o 409 é reenviado e inofensivo); cenário 4 com `curl -u` Basic na rota interna → 401. 7.2-B: cenário 1 definindo `TREND_AI_MONTHLY_BUDGET_USD=0.05` via `gcloud run services update --update-env-vars` (e variável do GitHub); cenário 2 com `05-kill-switch.sh off|on`.

## 8. Riscos

1. Budget é só alerta; até o alerta chegar, o teto é o livro de gastos no GCS (falha fechada).
2. Budget no escopo do projeto inteiro alerta também por Cloud Run/Artifact Registry/Cloud Logging; use `BUDGET_SERVICES` (IDs via Catalog API) para isolar Vertex+GCS+Scheduler, ou aceite o alerta como visão do projeto.
3. Moeda: `--budget-amount=2` usa a moeda da conta de faturamento; se for BRL, defina `BUDGET_AMOUNT` com o equivalente.
4. O workflow só envia as variáveis; a SA de runtime dedicada exige `actAs` do deployer, senão o passo falha.
5. `AUTH_PASSWORD` padrão literal no workflow (F-01 do `security`) continua aberta, fora deste escopo.
