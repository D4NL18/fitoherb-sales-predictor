"""
Saida do radar externo SEM TEXTO LIVRE (P-180.3 v3.1, P-184.6): schema raso enviado ao modelo e validacao estrita
da resposta. Por dimensao so enums, `tema` de lista fechada por dimensao, indice da fonte e data ISO. Qualquer
campo desconhecido, valor fora da lista ou marcador de injecao rejeita a saida INTEIRA (nada e gravado) e gera
o log `tia.radar.injectionSuspect` sem payload. O radar e uma superficie persistente: um envenenamento atingiria
todos os produtos do assunto ate o TTL, por isso o criterio e binario.
"""
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from src.modules.trend_insights.domain.constants import LOGGER_NAME, RADAR_MAX_SOURCES
from src.modules.trend_insights.domain.external_dimensions import EXTERNAL_DIMENSIONS
from src.modules.trend_insights.domain.radar_themes import RADAR_THEMES

logger = logging.getLogger(LOGGER_NAME + ".radar")

STATUSES = ("AVALIADA", "SEM_EVIDENCIA")
MOVEMENTS = ("SUBIU", "CAIU", "ESTAVEL", "MUDOU", "INDEFINIDO")
INTENSITIES = ("FORTE", "MODERADA", "FRACA")
DIMENSION_KEYS = frozenset({"dimensao", "status", "movimento", "intensidade", "tema", "fonteIdx", "dataFonte"})
INJECTION_MARKERS = ("ignore", "instruç", "instruc", "system", "prompt", "http")
_MARKER_PATTERN = re.compile("|".join(INJECTION_MARKERS), re.IGNORECASE)
_ALL_THEMES = sorted({theme for themes in RADAR_THEMES.values() for theme in themes})

_DIMENSION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": sorted(DIMENSION_KEYS),
    "properties": {
        "dimensao": {"type": "string", "enum": list(EXTERNAL_DIMENSIONS)},
        "status": {"type": "string", "enum": list(STATUSES)},
        "movimento": {"type": "string", "enum": list(MOVEMENTS)},
        "intensidade": {"type": ["string", "null"], "enum": list(INTENSITIES) + [None]},
        "tema": {"type": ["string", "null"], "enum": _ALL_THEMES + [None]},
        "fonteIdx": {"type": ["integer", "null"], "minimum": 0, "maximum": RADAR_MAX_SOURCES - 1},
        "dataFonte": {"type": ["string", "null"], "format": "date"},
    },
}

RADAR_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["dimensoes"],
    "properties": {
        "dimensoes": {
            "type": "array", "minItems": len(EXTERNAL_DIMENSIONS), "maxItems": len(EXTERNAL_DIMENSIONS),
            "items": _DIMENSION_SCHEMA,
        },
    },
}


@dataclass(frozen=True)
class RadarParseResult:
    ok: bool
    dimensions: Tuple[Dict[str, Any], ...] = ()
    violations: Tuple[str, ...] = field(default_factory=tuple)


def _fail(*codes: str, suspect: bool = False) -> RadarParseResult:
    if suspect:
        logger.warning("tia.radar.injectionSuspect violations=%s", ",".join(codes))
    return RadarParseResult(ok=False, violations=tuple(codes))


def _has_marker(item: Dict[str, Any]) -> bool:
    return any(isinstance(value, str) and _MARKER_PATTERN.search(value) for value in item.values())


def _valid_date(value: Any) -> bool:
    if value is None:
        return True
    try:
        return isinstance(value, str) and bool(date.fromisoformat(value))
    except ValueError:
        return False


def _item_violation(item: Any, source_count: int) -> Optional[str]:
    """Codigo da primeira violacao do item ou `None`; so lista fechada, nunca texto livre."""
    if not isinstance(item, dict) or set(item) != DIMENSION_KEYS:
        return "CAMPO_FORA_DO_SCHEMA"
    if _has_marker(item):
        return "MARCADOR_DE_INSTRUCAO"
    dimension = item["dimensao"]
    if dimension not in RADAR_THEMES:
        return "DIMENSAO_INVALIDA"
    tema, index = item["tema"], item["fonteIdx"]
    is_closed = (
        item["status"] in STATUSES and item["movimento"] in MOVEMENTS
        and item["intensidade"] in INTENSITIES + (None,)
        and (tema is None or tema in RADAR_THEMES[dimension])
        and (index is None or (isinstance(index, int) and not isinstance(index, bool) and 0 <= index < source_count))
        and _valid_date(item["dataFonte"])
    )
    return None if is_closed else "VALOR_FORA_DA_LISTA"


def parse_radar_output(text: str, source_count: int) -> RadarParseResult:
    """Valida o JSON do radar; `dimensions` sai na ordem fixa das 8 dimensoes."""
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return _fail("JSON_INVALIDO")
    items = body.get("dimensoes") if isinstance(body, dict) and set(body) == {"dimensoes"} else None
    if not isinstance(items, list):
        return _fail("SCHEMA_INVALIDO", suspect=isinstance(body, dict))
    violations: List[str] = []
    for item in items:
        code = _item_violation(item, source_count)
        if code and code not in violations:
            violations.append(code)
    by_dimension = {i["dimensao"]: i for i in items if isinstance(i, dict) and "dimensao" in i}
    is_complete = len(items) == len(EXTERNAL_DIMENSIONS) and set(by_dimension) == set(EXTERNAL_DIMENSIONS)
    if violations or not is_complete:
        return _fail(*(violations or ["DIMENSOES_INCOMPLETAS"]), suspect=True)
    return RadarParseResult(ok=True, dimensions=tuple(dict(by_dimension[d]) for d in EXTERNAL_DIMENSIONS))
