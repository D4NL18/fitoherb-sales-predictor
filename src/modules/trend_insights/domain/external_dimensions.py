"""
Checklist fixo de 8 dimensoes externas (P-180.4) e regras de causalidade CALCULADAS PELO BACKEND (P-180.5):
relacao temporal da fonte com a Janela Atual e coerencia direcional com a variacao do produto. Funcoes puras;
o modelo nunca decide `relacaoTemporal` nem `rotulo`.
"""
from datetime import date, timedelta
from typing import Optional, Tuple

from src.modules.trend_insights.domain.constants import EXTERNAL_SOURCE_LOOKBACK_DAYS

EXTERNAL_DIMENSIONS: Tuple[str, ...] = (
    "POLITICA_REGULATORIO", "CLIMA_SAFRA", "CUSTO_MATERIA_PRIMA", "OFERTA_DEMANDA_MATERIA_PRIMA",
    "CAMBIO_LOGISTICA_IMPORTACAO", "CONSUMO_MIDIA_SAUDE", "CONCORRENCIA", "EVENTOS_MERCADO",
)

# Dimensao -> `fatores[].tipo` (P-181.3).
DIMENSION_FACTOR_TYPE = {
    "POLITICA_REGULATORIO": "POLITICO_REGULATORIO",
    "CLIMA_SAFRA": "CLIMA",
    "CUSTO_MATERIA_PRIMA": "MATERIA_PRIMA",
    "OFERTA_DEMANDA_MATERIA_PRIMA": "MATERIA_PRIMA",
    "CAMBIO_LOGISTICA_IMPORTACAO": "MATERIA_PRIMA",
    "CONSUMO_MIDIA_SAUDE": "OUTRO",
    "CONCORRENCIA": "CONCORRENCIA_MERCADO",
    "EVENTOS_MERCADO": "OUTRO",
}

RELATION_PREVIOUS, RELATION_CONTEMPORARY, RELATION_LATER = "ANTERIOR", "CONTEMPORANEA", "POSTERIOR"
RELATION_NO_DATE, RELATION_OLD = "SEM_DATA", "ANTIGA"
LABEL_POSSIBLE, LABEL_CONTEXT, LABEL_NO_DATE, LABEL_DISCARDED = "POSSIVEL", "CONTEXTO", "SEM_DATA", "DESCARTADA"
PRESSURE_UP, PRESSURE_DOWN = "PRESSAO_ALTA", "PRESSAO_BAIXA"


def temporal_relation(
    source_date: Optional[date], *, current_start: date, current_end: date, previous_start: date,
) -> Tuple[str, str]:
    """`(relacaoTemporal, rotulo)` da fonte contra a Janela Atual; so `POSSIVEL` pode ser causa."""
    if source_date is None:
        return RELATION_NO_DATE, LABEL_NO_DATE
    if source_date < previous_start - timedelta(days=EXTERNAL_SOURCE_LOOKBACK_DAYS):
        return RELATION_OLD, LABEL_DISCARDED
    if source_date < current_start:
        return RELATION_PREVIOUS, LABEL_POSSIBLE
    if source_date <= current_end:
        return RELATION_CONTEMPORARY, LABEL_POSSIBLE
    return RELATION_LATER, LABEL_CONTEXT


def directional_coherence(direction: str, variation_pct: Optional[float]) -> bool:
    """Pressao de baixa so explica queda; de alta, so alta. `NEUTRA` e `INDETERMINADA` nao explicam variacao."""
    if variation_pct is None:
        return False
    if direction == PRESSURE_DOWN:
        return variation_pct < 0
    if direction == PRESSURE_UP:
        return variation_pct > 0
    return False
