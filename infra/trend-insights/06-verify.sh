#!/usr/bin/env bash
# Verificacao SOMENTE LEITURA exigida por LGPD-TIA-09/10 e D-7.0c.9 / D-7.2.13. Sai com codigo != 0 se algo divergir.
# Rodar antes de liberar o release e apos qualquer mudanca de infra. Nao altera nada no GCP.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
PY=$(command -v python3 || command -v python) || fail "python nao encontrado"
CHECKS=("${PY}" -I "${INFRA_DIR}/verify_checks.py")
FAILS=0

run_check() {  # titulo, comando-gcloud (string) , args do verify_checks...
  local title="$1" cmd="$2"; shift 2
  local out
  if ! out=$(eval "${cmd}" 2>/dev/null); then printf '  FALHA %s: recurso inexistente ou sem permissao\n' "${title}"; FAILS=$((FAILS + 1)); return; fi
  local res
  if res=$(printf '%s' "${out}" | "${CHECKS[@]}" "$@"); then
    printf '  OK    %s\n' "${title}"
  else
    while IFS= read -r line; do printf '  FALHA %s: %s\n' "${title}" "${line}"; done <<< "${res}"
    FAILS=$((FAILS + 1))
  fi
}

URL="$(service_url 2>/dev/null || true)"

echo "== Bucket gs://${BUCKET} (LGPD-TIA-09/10)"
run_check "configuracao do bucket" "gcloud storage buckets describe gs://${BUCKET} --project=${PROJECT_ID} --format=json" bucket "${REGION}"
run_check "IAM do bucket" "gcloud storage buckets get-iam-policy gs://${BUCKET} --format=json" bucket-iam "${RUNTIME_SA}" "${SCHEDULER_SA}"

echo "== IAM de projeto (menor privilegio)"
RT=$(gcloud projects get-iam-policy "${PROJECT_ID}" --flatten=bindings --filter="bindings.members:serviceAccount:${RUNTIME_SA}" --format='value(bindings.role)' 2>/dev/null | sort | tr '\n' ' ')
[[ "${RT}" == "roles/aiplatform.user " ]] && echo "  OK    runtime SA: so roles/aiplatform.user no projeto" || { echo "  FALHA runtime SA no projeto: '${RT}'"; FAILS=$((FAILS + 1)); }
SC=$(gcloud projects get-iam-policy "${PROJECT_ID}" --flatten=bindings --filter="bindings.members:serviceAccount:${SCHEDULER_SA}" --format='value(bindings.role)' 2>/dev/null | tr '\n' ' ')
[[ -z "${SC// /}" ]] && echo "  OK    scheduler SA: nenhum papel de projeto" || { echo "  FALHA scheduler SA com papeis de projeto: '${SC}'"; FAILS=$((FAILS + 1)); }
INV=$(gcloud run services get-iam-policy "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" --flatten=bindings --filter="bindings.members:serviceAccount:${SCHEDULER_SA}" --format='value(bindings.role)' 2>/dev/null)
[[ "${INV}" == "roles/run.invoker" ]] && echo "  OK    scheduler SA: so roles/run.invoker no servico" || { echo "  FALHA scheduler SA no servico: '${INV}'"; FAILS=$((FAILS + 1)); }

echo "== Cloud Run (D-7.2.13, FinOps)"
run_check "servico: SA, escala, variaveis TREND_AI_*/AFFINITY_*" "gcloud run services describe ${SERVICE} --project=${PROJECT_ID} --region=${REGION} --format=json" \
  service "${BUCKET}" "${VERTEX_LOCATION}" "${RUNTIME_SA}" "${URL}" "${SCHEDULER_SA}"

echo "== Cloud Scheduler (D-7.0c.9)"
run_check "job OIDC ${SCHEDULER_CRON} ${SCHEDULER_TZ}" "gcloud scheduler jobs describe ${SCHEDULER_JOB} --project=${PROJECT_ID} --location=${REGION} --format=json" \
  scheduler "${URL}" "${SCHEDULER_SA}" "${SCHEDULER_CRON}" "${SCHEDULER_TZ}"

echo
if (( FAILS > 0 )); then echo "RESULTADO: ${FAILS} grupo(s) com falha. NAO liberar o release."; exit 1; fi
echo "RESULTADO: infraestrutura da F7 conforme (LGPD-TIA-09/10, D-7.0c.9, D-7.2.13)."
