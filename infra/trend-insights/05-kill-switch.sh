#!/usr/bin/env bash
# Kill-switch da IA (TREND_AI_ENABLED). `off` => POST /generate devolve resumo por template (IA_DESLIGADA), GET intacto.
# Muda so a variavel (nova revisao do Cloud Run, sem build). Tambem grava a variavel de repositorio do GitHub
# para o proximo deploy (workflow) NAO religar a IA sozinho. Uso: 05-kill-switch.sh on|off
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
case "${1:-}" in on) V=true;; off) V=false;; *) fail "uso: 05-kill-switch.sh on|off";; esac

gcloud run services update "${SERVICE}" --project="${PROJECT_ID}" --region="${REGION}" \
  --update-env-vars="TREND_AI_ENABLED=${V}"
if command -v gh >/dev/null 2>&1; then
  gh variable set TREND_AI_ENABLED --body "${V}" && log "Variavel do GitHub TREND_AI_ENABLED=${V}."
else
  log "AVISO: sem 'gh'. Defina manualmente a variavel de repositorio TREND_AI_ENABLED=${V} (Settings > Variables)."
fi
log "TREND_AI_ENABLED=${V}. Confira: GET /api/v1/sales-trend/insights/health -> ia.ligada."
