"""Checagens puras (sem rede) usadas por 06-verify.sh. Le JSON do `gcloud ... --format=json` em stdin.

Uso: python -I verify_checks.py <bucket|bucket-iam|service|scheduler> [args...]
Saida: uma linha por divergencia; codigo 0 se conforme, 1 se divergente.
"""
import json
import sys

PERMITTED_LOCATION_PREFIXES = ("us-", "europe-")
PERMITTED_LOCATIONS = ("us", "eu", "southamerica-east1")
EXPECTED_LIFECYCLE = {
    ("Delete", "insights/", 90),
    ("Delete", "ai-budget/", 400),
    ("Delete", "locks/", 1),
    ("AbortIncompleteMultipartUpload", "", 1),
}


def check_bucket(data, region):
    errs = []
    if data.get("uniform_bucket_level_access") is not True:
        errs.append("uniform_bucket_level_access nao esta ativo")
    if data.get("public_access_prevention") != "enforced":
        errs.append("public_access_prevention != enforced")
    if data.get("versioning_enabled"):
        errs.append("versionamento ligado (deve ser desligado)")
    if (data.get("location") or "").lower() != region:
        errs.append(f"localizacao != {region}")
    soft = (data.get("soft_delete_policy") or {}).get("retentionDurationSeconds", "0")
    if str(soft) not in ("0", "None"):
        errs.append(f"soft delete ativo ({soft}s); esperado desligado")
    seen = set()
    for rule in (data.get("lifecycle_config") or {}).get("rule", []):
        cond = rule.get("condition", {})
        action = rule.get("action", {}).get("type")
        for prefix in cond.get("matchesPrefix") or [""]:
            seen.add((action, prefix, cond.get("age")))
    for want in sorted(EXPECTED_LIFECYCLE - seen):
        errs.append(f"lifecycle ausente: {want[0]} prefixo='{want[1]}' age={want[2]}")
    return errs


def check_bucket_iam(data, runtime_sa, scheduler_sa):
    errs = []
    text = json.dumps(data)
    if "allUsers" in text or "allAuthenticatedUsers" in text:
        errs.append("bucket com membro publico")
    runtime_roles = {b["role"] for b in data.get("bindings", []) if f"serviceAccount:{runtime_sa}" in b.get("members", [])}
    if runtime_roles != {"roles/storage.objectUser"}:
        errs.append(f"runtime SA no bucket deve ter so objectUser; tem {sorted(runtime_roles)}")
    if scheduler_sa in text:
        errs.append("scheduler SA nao deve ter acesso ao bucket")
    return errs


def check_service(data, bucket, location, runtime_sa, url, scheduler_sa):
    template = data["spec"]["template"]
    annotations = template["metadata"].get("annotations", {})
    container = template["spec"]["containers"][0]
    env = {e["name"]: e.get("value", "") for e in container.get("env", [])}
    errs = []
    if template["spec"].get("serviceAccountName") != runtime_sa:
        errs.append("serviceAccountName != SA de runtime dedicada")
    if annotations.get("autoscaling.knative.dev/minScale", "0") != "0":
        errs.append("min-instances != 0")
    if annotations.get("autoscaling.knative.dev/maxScale") != "3":
        errs.append("max-instances != 3")
    expect = {
        "TREND_INSIGHTS_BUCKET": bucket,
        "AFFINITY_INDEX_GCS_URI": f"gs://{bucket}/affinity/product_affinity_index.json",
        "AFFINITY_SYNC_AUDIENCE": url,
        "AFFINITY_SYNC_INVOKER_SA": scheduler_sa,
        "TREND_AI_LOCATION": location,
    }
    for key, value in expect.items():
        if env.get(key) != value:
            errs.append(f"{key} divergente (esperado '{value}')")
    loc = env.get("TREND_AI_LOCATION", "")
    if not (loc in PERMITTED_LOCATIONS or loc.startswith(PERMITTED_LOCATION_PREFIXES)):
        errs.append("TREND_AI_LOCATION fora de us/eu/southamerica-east1 ('global' proibido, LGPD A-2)")
    for forbidden in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if forbidden in env:
            errs.append(f"{forbidden} nao deve existir (Vertex via ADC, LGPD-TIA-08)")
    pricing = env.get("TREND_AI_PRICING_JSON", "")
    if not pricing or "neon" in pricing.lower():
        errs.append("TREND_AI_PRICING_JSON ausente ou com neon")
    for key in ("TREND_AI_ENABLED", "TREND_AI_MONTHLY_BUDGET_USD", "TREND_AI_DAILY_BUDGET_USD"):
        if key not in env:
            errs.append(f"{key} ausente")
    return errs


def check_scheduler(data, url, scheduler_sa, cron, tz):
    http = data.get("httpTarget", {})
    oidc = http.get("oidcToken", {})
    errs = []
    if http.get("uri") != f"{url}/internal/v1/affinity-index/sync" or http.get("httpMethod") != "POST":
        errs.append("uri/metodo divergentes")
    if oidc.get("serviceAccountEmail") != scheduler_sa or oidc.get("audience") != url:
        errs.append("OIDC: conta ou audience divergentes")
    if data.get("schedule") != cron or data.get("timeZone") != tz:
        errs.append("agenda/fuso divergentes")
    if data.get("attemptDeadline") != "300s":
        errs.append("attempt-deadline != 300s")
    return errs


def main(argv):
    kind, args = argv[1], argv[2:]
    data = json.load(sys.stdin)
    handlers = {
        "bucket": check_bucket,
        "bucket-iam": check_bucket_iam,
        "service": check_service,
        "scheduler": check_scheduler,
    }
    errs = handlers[kind](data, *args)
    for err in errs:
        print(err)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
