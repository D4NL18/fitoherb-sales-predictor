"""
Configuracao da F7 a partir de variaveis de ambiente (P-177.5, P-178). Modelos so da lista permitida;
a tabela de precos so pode conter esses modelos. Falha de configuracao e `ValueError` (SettingsError).
"""
from dataclasses import dataclass
from typing import Mapping, Optional

from src.modules.trend_insights.domain import constants
from src.modules.trend_insights.domain.exceptions import SettingsError
from src.modules.trend_insights.llm.pricing import PricingTable, parse_pricing

PRIMARY_MODEL = "gemini-4-hydrogen"
FALLBACK_MODEL = "gemini-3.8-flash"
ALLOWED_MODELS = (PRIMARY_MODEL, FALLBACK_MODEL)
DEFAULT_MONTHLY_BUDGET_USD = 1.80
DEFAULT_DAILY_BUDGET_USD = 0.20
DEFAULT_MAX_OUTPUT_TOKENS = 2500
# Processamento so em regiao controlada (parecer LGPD A-2): o endpoint `global` nao fixa onde o dado e processado.
DEFAULT_VERTEX_LOCATION = "us-central1"
PERMITTED_LOCATION_PREFIXES = ("us-", "europe-", "southamerica-east1")
PERMITTED_MULTI_REGIONS = ("us", "eu")
_FALSE_VALUES = ("false", "0", "no", "off")


def _read_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in _FALSE_VALUES


def _read_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise SettingsError("Valor numerico invalido.", field=name) from None


def _read_non_negative_int(env: Mapping[str, str], name: str, default: int) -> int:
    value = _read_float(env, name, float(default))
    if value < 0 or value != int(value):
        raise SettingsError("Valor inteiro nao negativo esperado.", field=name)
    return int(value)


def _read_model(env: Mapping[str, str], name: str, default: str) -> str:
    value = (env.get(name) or default).strip()
    if value not in ALLOWED_MODELS:
        raise SettingsError("Modelo fora da lista permitida.", field=name)
    return value


def _read_first_set(env: Mapping[str, str], names: tuple) -> Optional[str]:
    """Primeiro nome definido: aceita o nome com prefixo `TREND_AI_` (.env.example) e o nome curto (infra)."""
    for name in names:
        raw = env.get(name)
        if raw is not None and raw.strip() != "":
            return raw
    return None


def _read_int_from_names(env: Mapping[str, str], names: tuple, default: int) -> int:
    raw = _read_first_set(env, names)
    if raw is None:
        return default
    return _read_non_negative_int({names[0]: raw}, names[0], default)


def _read_positive_int(env: Mapping[str, str], names: tuple, default: int) -> int:
    value = _read_int_from_names(env, names, default)
    if value <= 0:
        raise SettingsError("Valor inteiro positivo esperado.", field=names[0])
    return value


def _read_pricing(env: Mapping[str, str]) -> Optional[PricingTable]:
    raw = env.get("TREND_AI_PRICING_JSON")
    if not raw or not raw.strip():
        return None
    table = parse_pricing(raw)
    if not set(table.model_ids()) <= set(ALLOWED_MODELS):
        raise SettingsError("Tabela de precos com modelo nao permitido.", field="TREND_AI_PRICING_JSON")
    return table


def _read_location(env: Mapping[str, str]) -> str:
    value = (env.get("TREND_AI_LOCATION") or "").strip() or DEFAULT_VERTEX_LOCATION
    if value in PERMITTED_MULTI_REGIONS or value.startswith(PERMITTED_LOCATION_PREFIXES):
        return value
    raise SettingsError("Regiao do Vertex fora das regioes permitidas (us, eu ou southamerica-east1).",
                        field="TREND_AI_LOCATION")


@dataclass(frozen=True)
class TrendInsightsSettings:
    ai_enabled: bool
    monthly_budget_usd: float
    daily_budget_usd: float
    model_default: str
    model_fallback: str
    pricing: Optional[PricingTable]
    max_output_tokens: int
    bucket_name: Optional[str]
    gcp_project: Optional[str]
    vertex_location: str
    generate_rate_limit_per_minute: int = constants.GENERATE_RATE_LIMIT_PER_MINUTE
    generate_max_per_day: int = constants.GENERATE_MAX_PER_USER_PER_DAY
    force_max_per_day: int = constants.FORCE_MAX_PER_USER_PER_DAY
    soft_ttl_days: int = constants.INSIGHT_SOFT_TTL_DAYS
    free_queries: int = constants.GROUNDING_FREE_QUERIES_ASSUMED
    # Radar externo v3.1 (P-180.3, P-178.8) e prazos de DA-13 (P-183.5).
    model_radar: str = PRIMARY_MODEL
    hard_cap_queries: int = constants.GROUNDING_HARD_CAP_QUERIES
    llm_total_deadline_seconds: int = constants.LLM_TOTAL_DEADLINE_SECONDS
    in_flight_lock_ttl_seconds: int = constants.IN_FLIGHT_LOCK_TTL_SECONDS
    reservation_ttl_seconds: int = constants.RESERVATION_TTL_SECONDS

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "TrendInsightsSettings":
        return cls(
            ai_enabled=_read_bool(env, "TREND_AI_ENABLED", True),
            monthly_budget_usd=_read_float(env, "TREND_AI_MONTHLY_BUDGET_USD", DEFAULT_MONTHLY_BUDGET_USD),
            daily_budget_usd=_read_float(env, "TREND_AI_DAILY_BUDGET_USD", DEFAULT_DAILY_BUDGET_USD),
            model_default=_read_model(env, "TREND_AI_MODEL_DEFAULT", PRIMARY_MODEL),
            model_fallback=_read_model(env, "TREND_AI_MODEL_FALLBACK", FALLBACK_MODEL),
            pricing=_read_pricing(env),
            max_output_tokens=int(_read_float(env, "TREND_AI_MAX_OUTPUT_TOKENS_DEFAULT", DEFAULT_MAX_OUTPUT_TOKENS)),
            bucket_name=env.get("TREND_INSIGHTS_BUCKET") or None,
            gcp_project=env.get("GOOGLE_CLOUD_PROJECT") or None,
            vertex_location=_read_location(env),
            # Cota gratis de busca ASSUMIDA pelo livro. No Vertex ela nao esta confirmada: com 0 toda consulta e
            # contada como paga (livro correto) e a busca sugere 1 consulta so. Ajuste sem deploy de codigo.
            free_queries=_read_non_negative_int(
                env, "TREND_AI_GROUNDING_FREE_QUERIES", constants.GROUNDING_FREE_QUERIES_ASSUMED),
            model_radar=_read_model(env, "TREND_AI_MODEL_RADAR", PRIMARY_MODEL),
            # Teto duro de consultas do mes (P-178.8); 0 desliga toda busca nova.
            hard_cap_queries=_read_int_from_names(
                env, ("TREND_AI_GROUNDING_HARD_CAP_QUERIES", "GROUNDING_HARD_CAP_QUERIES"),
                constants.GROUNDING_HARD_CAP_QUERIES),
            llm_total_deadline_seconds=_read_positive_int(
                env, ("TREND_AI_LLM_TOTAL_DEADLINE_SECONDS", "LLM_TOTAL_DEADLINE_SECONDS"),
                constants.LLM_TOTAL_DEADLINE_SECONDS),
            in_flight_lock_ttl_seconds=_read_positive_int(
                env, ("TREND_AI_IN_FLIGHT_LOCK_TTL_SECONDS", "IN_FLIGHT_LOCK_TTL_SECONDS"),
                constants.IN_FLIGHT_LOCK_TTL_SECONDS),
            reservation_ttl_seconds=_read_positive_int(
                env, ("TREND_AI_RESERVATION_TTL_SECONDS", "RESERVATION_TTL_SECONDS"),
                constants.RESERVATION_TTL_SECONDS),
        )


@dataclass(frozen=True)
class SchedulerAuthSettings:
    """Audiencia e conta de servico do Cloud Scheduler aceitas pela rota interna (DA-06). Sem elas a rota fica fechada."""

    audience: str
    invoker_email: str

    @property
    def is_configured(self) -> bool:
        return bool(self.audience and self.invoker_email)

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "SchedulerAuthSettings":
        return cls(
            audience=(env.get("AFFINITY_SYNC_AUDIENCE") or "").strip(),
            invoker_email=(env.get("AFFINITY_SYNC_INVOKER_SA") or "").strip(),
        )
