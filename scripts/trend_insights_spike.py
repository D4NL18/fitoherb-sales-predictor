"""
Spike 7.2-S do Radar de Tendencias (Vertex AI). Uso e custos: .agents/docs/devops/trend-insights-spike.md.
Autonomo (stdlib + google-genai); nao importa src/. Sem `--confirm-billing` nao ha rede nem custo.
Prompts 100% sinteticos; nenhum segredo ou texto de resposta e gravado no relatorio.
"""
import argparse
import json
import os
import sys
import time
from datetime import date
from typing import Any, Dict, List, Optional

MODELS = ("gemini-3.8-flash", "gemini-4-hydrogen")
COST_LIMIT_USD = 0.10
MAX_OUTPUT = 1500
SDK_USAGE_FIELDS = ("prompt_token_count", "candidates_token_count", "thoughts_token_count",
                    "cached_content_token_count", "tool_use_prompt_token_count")
SDK_GROUNDING_FIELDS = ("grounding_chunks", "web_search_queries", "search_entry_point")
SCHEMA = {"type": "object", "properties": {"resumo": {"type": "string"}, "fatores": {
    "type": "array", "items": {"type": "string"}}}, "required": ["resumo", "fatores"]}
SYSTEM = "tia-v3 (sintetico): responda em JSON conciso, em portugues, sem digitos."
PROMPTS = {
    "radar": "Radar sintetico: liste fatores externos recentes que afetam a categoria ficticia 'chas'.",
    "diagnostico": "Diagnostico sintetico: categoria ficticia 'chas' caiu no periodo; explique causas "
                   "provaveis usando o contexto de radar ficticio 'clima frio e feriados'.",
}


class SpikeError(Exception):
    pass


def check_environment(env: Dict[str, str]) -> Dict[str, Any]:
    missing = [k for k in ("GOOGLE_CLOUD_PROJECT", "TREND_AI_LOCATION", "TREND_AI_PRICING_JSON") if not env.get(k)]
    if missing:
        raise SpikeError("Variaveis ausentes: " + ", ".join(missing))
    if env["TREND_AI_LOCATION"].strip().lower() == "global":
        raise SpikeError("TREND_AI_LOCATION=global e proibido.")
    try:
        pricing = json.loads(env["TREND_AI_PRICING_JSON"])
        float(pricing["search_per_query"])
        pricing["models"].items()
    except (ValueError, KeyError, TypeError, AttributeError):
        raise SpikeError("TREND_AI_PRICING_JSON invalido.") from None
    return {"project": env["GOOGLE_CLOUD_PROJECT"], "location": env["TREND_AI_LOCATION"], "pricing": pricing}


def _price(pricing: Dict[str, Any], model: str, on: date) -> Optional[Dict[str, Any]]:
    tiers = sorted(pricing["models"].get(model) or [], key=lambda t: t["from"])
    eligible = [t for t in tiers if t["from"] <= on.isoformat()]
    return (eligible[-1] if eligible else tiers[0]) if tiers else None


def estimate_cost(pricing: Dict[str, Any], model: str, usage: Dict[str, int], queries: int, on: date) -> float:
    price = _price(pricing, model, on)
    if price is None:
        raise SpikeError(f"Modelo sem preco em TREND_AI_PRICING_JSON: {model}")
    tokens_in = usage["input"] + usage["tool"]
    tokens_out = usage["output"] + usage["thinking"]
    return (tokens_in * float(price["input_per_million"]) + tokens_out * float(price["output_per_million"])) / 1e6 \
        + queries * float(pricing["search_per_query"])


def worst_case_cost(pricing: Dict[str, Any], on: date) -> float:
    """Teto pre-voo: 2 modelos x 2 prompts, tokens e consultas maximos por chamada."""
    worst = {"input": 6000, "tool": 3000, "output": MAX_OUTPUT, "thinking": 2000}
    return sum(2 * estimate_cost(pricing, m, worst, 5, on) for m in MODELS)


def extract(raw: Any) -> Dict[str, Any]:
    u = getattr(raw, "usage_metadata", None)
    cands = getattr(raw, "candidates", None) or []
    meta = getattr(cands[0], "grounding_metadata", None) if cands else None

    def g(obj, name):
        return getattr(obj, name, None) if obj is not None else None

    return {
        "usage": {"input": int(g(u, "prompt_token_count") or 0), "output": int(g(u, "candidates_token_count") or 0),
                  "thinking": int(g(u, "thoughts_token_count") or 0),
                  "tool": int(g(u, "tool_use_prompt_token_count") or 0)},
        "queries": len(g(meta, "web_search_queries") or []),
        "citations": len(g(meta, "grounding_chunks") or []),
        "has_text": bool(getattr(raw, "text", None)),
        "fields_present": {
            "usage_metadata": u is not None, "grounding_metadata": meta is not None,
            **{f: g(u, f) is not None for f in SDK_USAGE_FIELDS},
            **{f: g(meta, f) is not None for f in SDK_GROUNDING_FIELDS}},
    }


def _config(types: Any):
    return types.GenerateContentConfig(
        system_instruction=SYSTEM, response_mime_type="application/json", response_json_schema=SCHEMA,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        thinking_config=types.ThinkingConfig(thinking_level="LOW"), max_output_tokens=MAX_OUTPUT)


def run_spike(sdk_client: Any, types: Any, pricing: Dict[str, Any], today: date, limit: float = COST_LIMIT_USD,
              clock=time.monotonic) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    total = 0.0
    for model in MODELS:
        for name, prompt in PROMPTS.items():
            entry: Dict[str, Any] = {"model": model, "prompt": name, "grounding": True}
            t0 = clock()
            try:
                raw = sdk_client.models.generate_content(model=model, contents=prompt, config=_config(types))
                info = extract(raw)
                cost = estimate_cost(pricing, model, info["usage"], info["queries"], today)
                total += cost
                entry.update(ok=True, schema_plus_search_accepted=info["has_text"], cost_usd=round(cost, 6), **info)
            except SpikeError:
                raise
            except Exception as exc:  # so tipo/codigo: a mensagem pode ecoar o prompt
                entry.update(ok=False, schema_plus_search_accepted=False, error_type=type(exc).__name__,
                             error_code=getattr(exc, "code", None))
            entry["latency_ms"] = int((clock() - t0) * 1000)
            calls.append(entry)
            if total > limit:
                raise SpikeError(f"Custo estimado US$ {total:.4f} acima do limite US$ {limit:.2f}; abortado.")
    return {"calls": calls, "estimated_total_usd": round(total, 6), "limit_usd": limit,
            "schema_plus_search": {m: any(c["schema_plus_search_accepted"] for c in calls if c["model"] == m)
                                   for m in MODELS}}


def main(argv: Optional[List[str]] = None, env: Optional[Dict[str, str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-billing", action="store_true", help="autoriza chamadas reais (geram custo)")
    args = parser.parse_args(argv)
    try:
        cfg = check_environment(dict(os.environ if env is None else env))
        if not args.confirm_billing:
            print(json.dumps({"dry_run": True, "worst_case_usd": round(worst_case_cost(cfg["pricing"], date.today()), 4),
                              "hint": "use --confirm-billing para executar"}))
            return 0
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=cfg["project"], location=cfg["location"])
        report = run_spike(client, types, cfg["pricing"], date.today())
    except SpikeError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERRO: falha de credenciais/ADC ou SDK ({type(exc).__name__}). "
              "Rode `gcloud auth application-default login`.", file=sys.stderr)
        return 3
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
