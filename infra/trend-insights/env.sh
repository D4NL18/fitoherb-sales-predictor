#!/usr/bin/env bash
# Configuracao comum dos scripts da F7 (Tendencia com IA). Somente variaveis NAO secretas.
# Uso: `source infra/trend-insights/env.sh` (os demais scripts ja fazem isso).
# Todas as variaveis podem ser sobrescritas pelo ambiente antes da execucao.

: "${PROJECT_ID:=$(gcloud config get-value project 2>/dev/null)}"
: "${ENV_NAME:=prod}"
: "${REGION:=southamerica-east1}"                       # mesma regiao do Cloud Run (DA-07); evita egress
: "${SERVICE:=fitoherb-sales-predictor}"
: "${BUCKET:=fitoherb-trend-insights-${ENV_NAME}}"
: "${RUNTIME_SA_NAME:=sa-fitoherb-run}"                 # conta de runtime do Cloud Run (menor privilegio)
: "${SCHEDULER_SA_NAME:=sa-affinity-scheduler}"         # so invoca a rota interna
: "${SCHEDULER_JOB:=affinity-index-sync}"
: "${SCHEDULER_CRON:=0 0 * * *}"                        # horario do antigo laco _daily_affinity_cron (00:00)
: "${SCHEDULER_TZ:=America/Sao_Paulo}"
: "${VERTEX_LOCATION:=us-central1}"                     # LGPD A-2: us-*, europe-*, us, eu ou southamerica-east1
: "${BUDGET_DISPLAY_NAME:=trend-insights-ia-mensal}"
: "${BUDGET_AMOUNT:=2}"                                 # na moeda da conta de faturamento (ver docs, secao 5)
: "${FREE_SCHEDULER_JOBS:=3}"                           # cota gratis por conta de faturamento

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERRO: defina PROJECT_ID (export PROJECT_ID=...) ou 'gcloud config set project'." >&2
  return 1 2>/dev/null || exit 1
fi

RUNTIME_SA="${RUNTIME_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="${SCHEDULER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
INFRA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

service_url() {
  gcloud run services describe "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" \
    --format='value(status.url)'
}

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
fail() { printf 'FALHA: %s\n' "$*" >&2; exit 1; }
