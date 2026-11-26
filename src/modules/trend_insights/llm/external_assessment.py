"""
Checklist das 8 dimensoes externas no diagnostico (P-180.4, P-180.5, P-181.3, P-182.5). Funcao pura: recebe as
`avaliacoesExternas` do modelo e o contexto do radar e devolve SEMPRE 8 itens em ordem fixa. O modelo so escolhe
`direcao`, `confianca`, `relevanciaAoProduto`, `fonteIds` e uma `nota` curta sem digitos; `relacaoTemporal`,
`rotulo`, fontes (url, titulo, data), `tema` e texto fixo vem do backend. `SEM_EVIDENCIA` nunca vira `NEUTRA`.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple

from src.modules.trend_insights.domain.constants import (
    MAX_EXTERNAL_FACTORS_IN_FACTORS,
    MAX_EXTERNAL_NOTE_CHARS,
    MAX_SOURCE_IDS_PER_ITEM,
)
from src.modules.trend_insights.domain.external_dimensions import (
    DIMENSION_FACTOR_TYPE,
    EXTERNAL_DIMENSIONS,
    LABEL_POSSIBLE,
    PRESSURE_DOWN,
    PRESSURE_UP,
    directional_coherence,
    temporal_relation,
)
from src.modules.trend_insights.domain.radar_themes import NO_EVIDENCE_TEXT, RADAR_THEME_TEXTS
from src.modules.trend_insights.llm.output_schema import (
    EXTERNAL_DIRECTIONS,
    EXTERNAL_RELEVANCES,
)

ASSESSMENT_KEYS = frozenset({"dimensao", "direcao", "confianca", "relevanciaAoProduto", "fonteIds", "nota"})
REQUIRED_KEYS = ASSESSMENT_KEYS - {"nota"}
RELEVANT = ("ALTA", "MEDIA")
SOURCE_FIELDS = ("id", "url", "dominio", "titulo", "dataPublicacao", "origemData")
_SOURCE_ID = re.compile(r"[FP][0-9]{1,2}")
_RELATION_RANK = {"ANTERIOR": 0, "CONTEMPORANEA": 0, "POSTERIOR": 1, "SEM_DATA": 2, "ANTIGA": 3}
_HYPOTHESIS_MOTIVE = {
    "POSTERIOR": "POSTERIOR_AO_PERIODO", "SEM_DATA": "SEM_DATA", "ANTIGA": "FORA_DO_PERIODO",
}
_GENERIC_TEXT = "Fator externo observado na pesquisa, sem relação causal confirmada."
_MAX_NOTE_CHARS = MAX_EXTERNAL_NOTE_CHARS


@dataclass(frozen=True)
class ExternalContext:
    """Radar utilizavel (ou o motivo de nao haver) e janela do produto para causalidade (calculada pelo backend)."""

    dimensions: Tuple[Mapping[str, Any], ...]
    sources: Mapping[str, Mapping[str, Any]]
    variation_pct: Optional[float]
    current_start: date
    current_end: date
    previous_start: date
    radar_stale: bool = False
    radar_missing_reason: Optional[str] = None


@dataclass
class ExternalAssessment:
    items: List[Dict[str, Any]]
    promoted: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    blocking: List[str] = field(default_factory=list)
    informative: List[str] = field(default_factory=list)


def _item(dimension: str, status: str, **over: Any) -> Dict[str, Any]:
    base = {
        "dimensao": dimension, "status": status, "direcao": "INDETERMINADA", "confianca": "BAIXA",
        "relevanciaAoProduto": "NENHUMA", "relacaoTemporal": None, "rotulo": "SEM_EVIDENCIA",
        "origemEvidencia": "NENHUMA", "motivoNaoAvaliado": None, "tema": None, "notaRadar": None, "nota": None,
        "fontes": [],
    }
    base.update(over)
    return base


def _not_evaluated(dimension: str, reason: str) -> Dict[str, Any]:
    return _item(dimension, "NAO_AVALIADA", motivoNaoAvaliado=reason)


def _no_evidence(dimension: str) -> Dict[str, Any]:
    return _item(dimension, "SEM_EVIDENCIA", notaRadar=NO_EVIDENCE_TEXT)


def _parse_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _note_problems(note: Any) -> List[str]:
    if note is None:
        return []
    if not isinstance(note, str):
        return ["SCHEMA_INVALIDO"]
    problems = []
    if len(note) > _MAX_NOTE_CHARS:
        problems.append("TAMANHO_EXCEDIDO")
    if any(ch.isdigit() for ch in note):
        problems.append("DIGITO_NO_TEXTO")
    return problems


def _is_assessment_shape(raw: Any) -> bool:
    if not isinstance(raw, dict) or not REQUIRED_KEYS <= set(raw) or not set(raw) <= ASSESSMENT_KEYS:
        return False
    ids = raw["fonteIds"]
    return (
        raw["dimensao"] in EXTERNAL_DIMENSIONS and raw["direcao"] in EXTERNAL_DIRECTIONS
        and raw["confianca"] in ("ALTA", "MEDIA", "BAIXA") and raw["relevanciaAoProduto"] in EXTERNAL_RELEVANCES
        and isinstance(ids, list) and len(ids) <= MAX_SOURCE_IDS_PER_ITEM
        and all(isinstance(i, str) and _SOURCE_ID.fullmatch(i) for i in ids)
    )


def _read_assessments(raw: Any, drop: bool, result: ExternalAssessment) -> Dict[str, Dict[str, Any]]:
    """Itens bem formados por dimensao; formato invalido e violacao bloqueante (nova tentativa)."""
    if not isinstance(raw, list):
        result.blocking.append("SCHEMA_INVALIDO")
        return {}
    found: Dict[str, Dict[str, Any]] = {}
    for entry in raw:
        if not _is_assessment_shape(entry):
            result.blocking.append("SCHEMA_INVALIDO")
            continue
        for code in _note_problems(entry.get("nota")):
            (result.informative if drop else result.blocking).append(code)
        found.setdefault(entry["dimensao"], entry)
    return found


def _usable_ids(entry: Mapping[str, Any], radar_dim: Optional[Mapping[str, Any]], context: ExternalContext,
                drop: bool, result: ExternalAssessment) -> List[str]:
    requested = list(dict.fromkeys(entry["fonteIds"]))
    if not requested and radar_dim and radar_dim.get("status") == "AVALIADA":
        requested = list(radar_dim.get("fonteIds") or [])  # o modelo nao citou: vale a fonte do proprio radar
    known = [i for i in requested if i in context.sources]
    if len(known) != len(requested):
        (result.informative if drop else result.blocking).append("FONTE_FORA_DO_RADAR")
    limit = MAX_SOURCE_IDS_PER_ITEM if (radar_dim or {}).get("intensidade") == "FORTE" else 1
    return known[:limit]


def _public_source(source: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: source.get(key) for key in SOURCE_FIELDS}


def _best_relation(sources: List[Dict[str, Any]], context: ExternalContext) -> Tuple[str, str, Dict[str, Any]]:
    """Relacao temporal do melhor candidato a causa: ANTERIOR/CONTEMPORANEA antes de POSTERIOR, SEM_DATA, ANTIGA."""
    ranked = []
    for source in sources:
        relation, label = temporal_relation(
            _parse_date(source.get("dataPublicacao")), current_start=context.current_start,
            current_end=context.current_end, previous_start=context.previous_start)
        ranked.append((_RELATION_RANK[relation], relation, label, source))
    _, relation, label, source = min(ranked, key=lambda r: r[0])
    return relation, label, source


def _confidence(model_value: str, source: Mapping[str, Any], context: ExternalContext) -> str:
    """Nunca ALTA; BAIXA com radar desatualizado ou fonte sem data (P-180.4, P-182.5)."""
    if context.radar_stale or source.get("origemData") in (None, "SEM_DATA") or model_value == "BAIXA":
        return "BAIXA"
    return "MEDIA"


def _hypothesis(dimension: str, motive: str, note_text: str, source: Dict[str, Any]) -> Dict[str, Any]:
    return {"tipo": DIMENSION_FACTOR_TYPE[dimension], "descricao": note_text, "motivo": motive, "fontes": [source]}


def _factor_from(item: Dict[str, Any]) -> Dict[str, Any]:
    explanation = item["nota"] or item["notaRadar"] or _GENERIC_TEXT
    return {
        "tipo": DIMENSION_FACTOR_TYPE[item["dimensao"]],
        "sentido": "NEGATIVO" if item["direcao"] == PRESSURE_DOWN else "POSITIVO",
        "parcelaEstimada": None, "confianca": item["confianca"], "rotulo": LABEL_POSSIBLE, "explicacao": explanation,
        "evidenciaInterna": None, "skusCitados": [], "fontes": list(item["fontes"]), "dimensao": item["dimensao"],
    }


def _evaluated_item(dimension: str, entry: Dict[str, Any], radar_dim: Optional[Mapping[str, Any]],
                    sources: List[Dict[str, Any]], context: ExternalContext) -> Tuple[Dict[str, Any], Optional[str]]:
    """Item AVALIADA e o motivo de hipotese (se a fonte nao pode ser causa)."""
    relation, label, main = _best_relation(sources, context)
    is_relevant = entry["relevanciaAoProduto"] in RELEVANT
    motive = _HYPOTHESIS_MOTIVE.get(relation)
    if label == LABEL_POSSIBLE and is_relevant and not directional_coherence(entry["direcao"], context.variation_pct):
        label = "CONTEXTO"
        is_contrary = entry["direcao"] in (PRESSURE_UP, PRESSURE_DOWN)
        motive = "SEM_COERENCIA_DIRECIONAL" if is_contrary else None
    uses_radar = main["id"].startswith("F") and radar_dim and radar_dim.get("status") == "AVALIADA"
    theme = radar_dim.get("tema") if uses_radar else None
    item = _item(
        dimension, "AVALIADA", direcao=entry["direcao"], confianca=_confidence(entry["confianca"], main, context),
        relevanciaAoProduto=entry["relevanciaAoProduto"], relacaoTemporal=relation, rotulo=label,
        origemEvidencia="BUSCA_PRODUTO" if main["id"].startswith("P") else "RADAR", tema=theme,
        notaRadar=RADAR_THEME_TEXTS.get((dimension, theme)) if theme else None,
        nota=entry.get("nota") if is_relevant else None, fontes=[_public_source(s) for s in sources],
    )
    return item, (motive if is_relevant else None)


def _build_item(dimension: str, entry: Optional[Dict[str, Any]], radar_dim: Optional[Mapping[str, Any]],
                context: ExternalContext, drop: bool, result: ExternalAssessment) -> Dict[str, Any]:
    if entry is None:
        result.informative.append("DIMENSAO_OMITIDA_PELA_IA")
        return _not_evaluated(dimension, "DIMENSAO_OMITIDA_PELA_IA")
    ids = _usable_ids(entry, radar_dim, context, drop, result)
    if not ids:
        return _no_evidence(dimension)
    sources = [dict(context.sources[i]) for i in ids]
    item, motive = _evaluated_item(dimension, entry, radar_dim, sources, context)
    if motive:
        text = item["notaRadar"] or _GENERIC_TEXT
        result.hypotheses.append(_hypothesis(dimension, motive, text, item["fontes"][0]))
    return item


def _promote(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """So AVALIADA + POSSIVEL + relevancia ALTA/MEDIA; ALTA primeiro; ate 3 externos (P-181.3)."""
    candidates = [i for i in items if i["status"] == "AVALIADA" and i["rotulo"] == LABEL_POSSIBLE
                  and i["relevanciaAoProduto"] in RELEVANT]
    candidates.sort(key=lambda i: i["relevanciaAoProduto"] != "ALTA")
    return [_factor_from(i) for i in candidates[:MAX_EXTERNAL_FACTORS_IN_FACTORS]]


def assess_external(raw: Any, context: Optional[ExternalContext], drop: bool = False) -> ExternalAssessment:
    """8 itens em ordem fixa, fatores promovidos e hipoteses; sem radar nem fonte, as 8 saem NAO_AVALIADA."""
    if context is None or (context.radar_missing_reason and not context.sources):
        reason = context.radar_missing_reason if context else "SEM_RADAR"
        return ExternalAssessment(items=[_not_evaluated(d, reason or "SEM_RADAR") for d in EXTERNAL_DIMENSIONS])
    result = ExternalAssessment(items=[])
    entries = _read_assessments(raw if raw is not None else [], drop, result)
    radar_by_dim = {d.get("dimensao"): d for d in context.dimensions}
    for dimension in EXTERNAL_DIMENSIONS:
        result.items.append(_build_item(dimension, entries.get(dimension), radar_by_dim.get(dimension), context, drop, result))
    result.promoted = _promote(result.items)
    return result
