#!/usr/bin/env bash
# D-7.0c.9 / LGPD-TIA-09 e 10: bucket privado da F7, idempotente (pode rodar quantas vezes quiser).
# UBLA + Public Access Prevention + sem versionamento + sem soft delete + lifecycle por prefixo
# (insights/ 90 d, ai-budget/ 400 d, radar/ 210 d [ADR-009 DA-13: > 180 d de validade do passado], locks/ 1 d, multipart abortado em 1 d).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

gcloud services enable storage.googleapis.com --project="${PROJECT_ID}"

if gcloud storage buckets describe "gs://${BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  log "Bucket gs://${BUCKET} ja existe; reaplicando configuracao."
else
  log "Criando gs://${BUCKET} em ${REGION}."
  gcloud storage buckets create "gs://${BUCKET}" --project="${PROJECT_ID}" --location="${REGION}" \
    --default-storage-class=STANDARD --uniform-bucket-level-access --public-access-prevention
fi

# Reaplicar sempre: corrige desvio manual. Soft delete desligado: o dado e agregado, e a retencao
# extra de 7 dias seria cobrada sem necessidade (e adiaria a exclusao real dos 90 dias).
gcloud storage buckets update "gs://${BUCKET}" --project="${PROJECT_ID}" \
  --uniform-bucket-level-access --public-access-prevention --no-versioning --clear-soft-delete \
  --lifecycle-file="${INFRA_DIR}/lifecycle.json"

log "Bucket pronto. Rode 06-verify.sh para conferir."
