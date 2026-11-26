#!/usr/bin/env bash
# D-7.0c.9: job do Cloud Scheduler (OIDC) para POST /internal/v1/affinity-index/sync, idempotente.
# Conta os jobs da conta de faturamento ANTES de criar (gratis ate 3; US$ 0,10/job/31 dias acima).
# Opcional: --run-now dispara a carga inicial do indice (gcloud scheduler jobs run).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

RUN_NOW=false; [[ "${1:-}" == "--run-now" ]] && RUN_NOW=true

gcloud services enable cloudscheduler.googleapis.com --project="${PROJECT_ID}"

# --- contagem de jobs: todos os projetos da conta de faturamento, todas as localizacoes ---
count_jobs_in_project() {
  local p="$1" total=0 loc n
  for loc in $(gcloud scheduler locations list --project="${p}" --format='value(locationId)' 2>/dev/null); do
    n=$(gcloud scheduler jobs list --project="${p}" --location="${loc}" --format='value(name)' 2>/dev/null | wc -l)
    total=$((total + n))
  done
  echo "${total}"
}
BILLING_ACCOUNT="${BILLING_ACCOUNT:-$(gcloud billing projects describe "${PROJECT_ID}" --format='value(billingAccountName)' 2>/dev/null | sed 's#billingAccounts/##')}"
TOTAL=0
if [[ -n "${BILLING_ACCOUNT}" ]]; then
  for p in $(gcloud billing projects list --billing-account="${BILLING_ACCOUNT}" --format='value(projectId)'); do
    c=$(count_jobs_in_project "${p}"); log "Projeto ${p}: ${c} job(s) do Scheduler."; TOTAL=$((TOTAL + c))
  done
else
  log "AVISO: conta de faturamento nao identificada; contando so ${PROJECT_ID}."
  TOTAL=$(count_jobs_in_project "${PROJECT_ID}")
fi

EXISTS=false
gcloud scheduler jobs describe "${SCHEDULER_JOB}" --project="${PROJECT_ID}" --location="${REGION}" >/dev/null 2>&1 && EXISTS=true
AFTER=$TOTAL; [[ "${EXISTS}" == false ]] && AFTER=$((TOTAL + 1))
if (( AFTER > FREE_SCHEDULER_JOBS )); then
  log "ATENCAO FINOPS: a conta ficara com ${AFTER} job(s) (> ${FREE_SCHEDULER_JOBS} gratis). Custo extra: US\$ 0,10 por job excedente/31 dias."
  [[ "${ACCEPT_SCHEDULER_COST:-no}" == "yes" ]] || fail "Defina ACCEPT_SCHEDULER_COST=yes para aceitar os US\$ 0,10/mes e repita."
else
  log "Jobs da conta apos esta operacao: ${AFTER} (<= ${FREE_SCHEDULER_JOBS}): US\$ 0,00."
fi

URL="$(service_url)" || fail "Servico ${SERVICE} nao encontrado; faca o 1o deploy antes."
TARGET="${URL}/internal/v1/affinity-index/sync"
# audience = URL do servico, EXATAMENTE o valor de AFFINITY_SYNC_AUDIENCE no Cloud Run
COMMON=(--project="${PROJECT_ID}" --location="${REGION}" --schedule="${SCHEDULER_CRON}" --time-zone="${SCHEDULER_TZ}"
  --uri="${TARGET}" --http-method=POST --attempt-deadline=300s
  --max-retry-attempts=2 --min-backoff=30s --max-backoff=120s
  --oidc-service-account-email="${SCHEDULER_SA}" --oidc-token-audience="${URL}")

if [[ "${EXISTS}" == true ]]; then
  log "Atualizando job ${SCHEDULER_JOB}."
  gcloud scheduler jobs update http "${SCHEDULER_JOB}" "${COMMON[@]}"
else
  log "Criando job ${SCHEDULER_JOB}."
  gcloud scheduler jobs create http "${SCHEDULER_JOB}" "${COMMON[@]}" \
    --description="F7: sync diario do indice de afinidade (00:00 BRT; antigo cron do lifespan)"
fi

if [[ "${RUN_NOW}" == true ]]; then
  log "Disparando carga inicial."
  gcloud scheduler jobs run "${SCHEDULER_JOB}" --project="${PROJECT_ID}" --location="${REGION}"
  log "Confira: GET /api/v1/sales-trend/insights/health -> indiceAfinidade.disponivel = true."
fi
