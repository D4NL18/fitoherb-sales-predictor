#!/usr/bin/env bash
# D-7.0c.9 / D-7.2.13: IAM minimo, idempotente.
#  - runtime SA: roles/storage.objectUser SO no bucket + roles/aiplatform.user (Vertex; so existe no projeto).
#  - scheduler SA: SO roles/run.invoker no servico (nenhum papel de projeto, nenhum acesso ao bucket).
# Pre-requisito do OPERADOR: criar contas de servico, alterar IAM do projeto e roles/iam.serviceAccountUser
# nas duas contas (actAs) para criar o job e implantar com --service-account.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

gcloud services enable aiplatform.googleapis.com iam.googleapis.com --project="${PROJECT_ID}"

ensure_sa() {  # nome, descricao
  if gcloud iam service-accounts describe "$1@${PROJECT_ID}.iam.gserviceaccount.com" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    log "SA $1 ja existe."
  else
    gcloud iam service-accounts create "$1" --project="${PROJECT_ID}" --display-name="$2"
  fi
}
ensure_sa "${RUNTIME_SA_NAME}" "Runtime Cloud Run - fitoherb-sales-predictor"
ensure_sa "${SCHEDULER_SA_NAME}" "Cloud Scheduler - sync do indice de afinidade (so invoker)"

# add-iam-policy-binding e idempotente (repetir nao duplica).
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" --project="${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/storage.objectUser" >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SA}" --role="roles/aiplatform.user" --condition=None >/dev/null

if gcloud run services describe "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" >/dev/null 2>&1; then
  gcloud run services add-iam-policy-binding "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" \
    --member="serviceAccount:${SCHEDULER_SA}" --role="roles/run.invoker" >/dev/null
else
  log "AVISO: servico ${SERVICE} ainda nao existe; rode este script de novo apos o 1o deploy (run.invoker do Scheduler)."
fi
log "IAM aplicado. Nenhum segredo/chave foi criado (Vertex usa ADC; OIDC nao usa chave)."
