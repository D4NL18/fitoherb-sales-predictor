#!/usr/bin/env bash
# D-7.2B.10: Cloud Billing Budget da F7 (alertas 50/80/100% reais, 100% previsto e 120%), idempotente por nome.
# O budget e SO ALERTA (nao corta gasto). A trava preventiva e o livro de gastos no GCS + kill-switch (05-kill-switch.sh).
# Requer: BILLING_ACCOUNT (XXXXXX-XXXXXX-XXXXXX) e papel Billing Account Administrator/Costs Manager.
# Opcionais: ALERT_EMAIL (cria canal do Cloud Monitoring), BUDGET_SERVICES="services/ID1,services/ID2".
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
: "${BILLING_ACCOUNT:?defina BILLING_ACCOUNT (gcloud billing accounts list)}"

gcloud services enable billingbudgets.googleapis.com monitoring.googleapis.com --project="${PROJECT_ID}"

CHANNEL_ARGS=()
if [[ -n "${ALERT_EMAIL:-}" ]]; then
  CH=$(gcloud beta monitoring channels list --project="${PROJECT_ID}" \
        --filter="type=email AND labels.email_address=${ALERT_EMAIL}" --format='value(name)' | head -n1)
  if [[ -z "${CH}" ]]; then
    CH=$(gcloud beta monitoring channels create --project="${PROJECT_ID}" --display-name="F7 orcamento IA" \
          --type=email --channel-labels="email_address=${ALERT_EMAIL}" --format='value(name)')
  fi
  CHANNEL_ARGS=(--notifications-rule-monitoring-notification-channels="${CH}")
fi
FILTER_ARGS=(--filter-projects="projects/${PROJECT_ID}")
[[ -n "${BUDGET_SERVICES:-}" ]] && FILTER_ARGS+=(--filter-services="${BUDGET_SERVICES}")

RULES=(--threshold-rule=percent=0.5 --threshold-rule=percent=0.8 --threshold-rule=percent=1.0
       --threshold-rule=percent=1.0,basis=forecasted-spend --threshold-rule=percent=1.2)

EXISTING=$(gcloud billing budgets list --billing-account="${BILLING_ACCOUNT}" \
  --filter="displayName=${BUDGET_DISPLAY_NAME}" --format='value(name)' | head -n1)
if [[ -n "${EXISTING}" ]]; then
  log "Atualizando budget ${BUDGET_DISPLAY_NAME}."
  gcloud billing budgets update "${EXISTING}" --billing-account="${BILLING_ACCOUNT}" \
    --budget-amount="${BUDGET_AMOUNT}" "${FILTER_ARGS[@]}" "${CHANNEL_ARGS[@]}" "${RULES[@]}"
else
  log "Criando budget ${BUDGET_DISPLAY_NAME} (${BUDGET_AMOUNT}/mes)."
  gcloud billing budgets create --billing-account="${BILLING_ACCOUNT}" --display-name="${BUDGET_DISPLAY_NAME}" \
    --budget-amount="${BUDGET_AMOUNT}" --calendar-period=month \
    "${FILTER_ARGS[@]}" "${CHANNEL_ARGS[@]}" "${RULES[@]}"
fi
log "Lembrete: budget so alerta. Para cortar a IA use 05-kill-switch.sh off."
