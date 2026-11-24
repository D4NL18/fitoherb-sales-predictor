"""Modo do diagnostico derivado do estado da celula da Tendencia (P-152), sem recalcular o estado."""
from typing import Optional

from src.modules.trend_insights.domain.constants import (
    MIN_EXPLAINABLE_VARIATION_PCT,
    MODE_NO_VARIATION,
    MODE_QUALITATIVE,
    MODE_QUANTITATIVE,
)

_QUALITATIVE_STATUSES = ("SEM_BASE", "NOVO")


def diagnosis_mode(status: str, variacao_pct: Optional[float], base_baixa: bool) -> str:
    """Variacao pequena ou celula parada nao tem o que explicar; base fraca so permite sinais."""
    if status in _QUALITATIVE_STATUSES:
        return MODE_QUALITATIVE
    if status != "VARIACAO" or variacao_pct is None:
        return MODE_NO_VARIATION
    if abs(variacao_pct) < MIN_EXPLAINABLE_VARIATION_PCT:
        return MODE_NO_VARIATION
    return MODE_QUALITATIVE if base_baixa else MODE_QUANTITATIVE
