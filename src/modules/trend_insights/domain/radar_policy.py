"""
Validade do radar externo (P-180.3): TTL logico de 30 dias (mes-base corrente e anterior) ou 180 (meses antigos),
depois `stale` ate 120 dias CONTADOS DA GERACAO, depois ausente. Funcao pura (relogio injetado).
"""
from datetime import datetime, timedelta, timezone

from src.modules.trend_insights.domain.constants import (
    BUDGET_TIMEZONE_OFFSET_HOURS,
    RADAR_STALE_MAX_DAYS,
    RADAR_TTL_DAYS,
    RADAR_TTL_PAST_DAYS,
)

STATE_FRESH = "FRESCO"
STATE_STALE = "DESATUALIZADO"
STATE_ABSENT = "AUSENTE"
_LOCAL_TZ = timezone(timedelta(hours=BUDGET_TIMEZONE_OFFSET_HOURS))
_MONTHS_STILL_CURRENT = 1  # mes-base corrente e o anterior usam o TTL curto


def _months_between(base_month: str, now: datetime) -> int:
    year, month = int(base_month[:4]), int(base_month[5:7])
    local = now.astimezone(_LOCAL_TZ)
    return (local.year - year) * 12 + (local.month - month)


def radar_ttl_days(base_month: str, now: datetime) -> int:
    return RADAR_TTL_DAYS if _months_between(base_month, now) <= _MONTHS_STILL_CURRENT else RADAR_TTL_PAST_DAYS


def radar_age_days(generated_at: datetime, now: datetime) -> int:
    """Idade inteira em dias desde a geracao (exibida como `diasDesdeGeracao`)."""
    return max(0, int((now - generated_at) / timedelta(days=1)))


def radar_freshness(generated_at: datetime, base_month: str, now: datetime) -> str:
    age = (now - generated_at) / timedelta(days=1)
    if age <= radar_ttl_days(base_month, now):
        return STATE_FRESH
    return STATE_STALE if age <= RADAR_STALE_MAX_DAYS else STATE_ABSENT
