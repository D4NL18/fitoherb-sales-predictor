"""
Validacao antialucinacao da saida do LLM (P-181, P-182, P-184.4). Funcoes puras.
Texto da IA sem NENHUM digito (os numeros ficam nos campos do motor); SKU so do pacote; fator interno so com
evidencia avaliada; fator externo so com fonte citada pela busca, com data valida no periodo.
`violations` lista todos os codigos achados; `ok` so e falso para violacoes bloqueantes (nova tentativa).
"""
import json
import re
import ipaddress
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from src.modules.trend_insights.domain.constants import (
    EXTERNAL_SOURCE_LOOKBACK_DAYS,
    MAX_EXPLANATION_CHARS,
    MAX_FACTORS,
    MAX_HYPOTHESES,
    MAX_HYPOTHESIS_CHARS,
    MAX_RECOMMENDATION_CHARS,
    MAX_RECOMMENDATIONS,
    MAX_SOURCES_PER_FACTOR,
    MAX_SUMMARY_CHARS,
    MODE_QUALITATIVE,
)
from src.modules.trend_insights.llm.output_schema import (
    CONFIDENCES,
    DIRECTIONS,
    EXTERNAL_FACTOR_TYPES,
    FACTOR_TYPES,
    INTERNAL_FACTOR_TYPES,
    LLM_HYPOTHESIS_REASONS,
)

TOP_LEVEL_KEYS = frozenset({"resumo", "fatores", "hipotesesNaoConfirmadas", "recomendacoes"})
MAX_SKUS_PER_FACTOR = 10
MAX_SOURCE_TITLE_CHARS = 200
_URL_DATE = re.compile(r"/(20\d{2})[/-](0[1-9]|1[0-2])(?:[/-](0[1-9]|[12]\d|3[01]))?(?:/|$|-)")
_ALLOWED_SCHEME = "https"
_INTERNAL_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".intranet")
_NUMERIC_HOST = re.compile(r"^(0x[0-9a-f]+|\d+)(\.(0x[0-9a-f]+|\d+))*$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidationContext:
    modo: str
    package_skus: FrozenSet[int]
    evaluated_types: FrozenSet[str]
    parcel_values: Mapping[str, float]
    cited_urls: FrozenSet[str]
    lookback_start: date
    reference_date: date
    cited_titles: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationOutcome:
    ok: bool
    violations: Tuple[str, ...]
    diagnostico: Optional[Dict[str, Any]]


class _Collector:
    """Acumula codigos de violacao (bloqueantes ou nao) sem repeti-los."""

    def __init__(self) -> None:
        self.blocking: List[str] = []
        self.informative: List[str] = []

    def block(self, code: str) -> None:
        if code not in self.blocking:
            self.blocking.append(code)

    def note(self, code: str) -> None:
        if code not in self.informative:
            self.informative.append(code)

    def all_codes(self) -> Tuple[str, ...]:
        return tuple(self.blocking + [c for c in self.informative if c not in self.blocking])


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _text_problems(text: Any, limit: int, context: ValidationContext) -> List[str]:
    if not isinstance(text, str):
        return ["SCHEMA_INVALIDO"]
    problems = []
    if len(text) > limit:
        problems.append("TAMANHO_EXCEDIDO")
    if _has_digit(text):
        problems.append("DIGITO_NO_TEXTO")
    if "{{" in text or "}}" in text:
        problems.append("MARCADOR_EM_MODO_QUALITATIVO" if context.modo == MODE_QUALITATIVE else "MARCADOR_NAO_SUPORTADO")
    return problems


# ------------------------------------------------------------------ fontes externas
def _parse_iso_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _date_from_url(url: str) -> Optional[date]:
    match = _URL_DATE.search(urlparse(url).path + "/")
    if not match:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3) or 1))


def _is_safe_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError:  # IPv6 malformado ou porta invalida
        return False
    if parsed.scheme != _ALLOWED_SCHEME or not host or parsed.username or parsed.password:
        return False
    if port not in (None, 443) or ":" in host or _NUMERIC_HOST.match(host):  # IPv6 e IPv4 (inclusive hex/inteiro)
        return False
    if "." not in host or host == "localhost" or host.endswith(_INTERNAL_HOST_SUFFIXES):
        return False
    return not _is_non_public_ip(host)


def _is_non_public_ip(host: str) -> bool:
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _resolve_date(model_date: Optional[date], url_date: Optional[date]) -> Tuple[Optional[date], Optional[str]]:
    """Data exibida: a lida pelo modelo; sem ela, a do caminho da URL."""
    if model_date:
        return model_date, "MODELO"
    if url_date:
        return url_date, "URL"
    return None, None


def _check_source(raw: Any, context: ValidationContext) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Devolve (fonte normalizada, None) se aceita ou (fonte para exibir, motivo) se rejeitada."""
    if not isinstance(raw, dict) or not _is_safe_url(raw.get("url")):
        return None, "FONTE_NAO_CITADA"
    url = raw["url"].strip()
    resolved, origin = _resolve_date(_parse_iso_date(raw.get("dataPublicacao")), _date_from_url(url))
    source = {
        "url": url,
        "dominio": urlparse(url).hostname,
        # o titulo vem da citacao do grounding; so sem ela cai no texto do modelo (que nao decide o rotulo do link)
        "titulo": str(context.cited_titles.get(url) or raw.get("titulo") or "")[:MAX_SOURCE_TITLE_CHARS],
        "dataPublicacao": resolved.isoformat() if resolved else None,
        "origemData": origin,
    }
    if url not in context.cited_urls:
        return source, "FONTE_NAO_CITADA"
    if resolved is None:
        return source, "SEM_DATA"
    known_dates = [d for d in (resolved, _date_from_url(url)) if d is not None]
    if any(not context.lookback_start <= d <= context.reference_date for d in known_dates):
        return source, "FORA_DO_PERIODO"
    return source, None


def _split_sources(raw_sources: Any, context: ValidationContext) -> Tuple[List[dict], List[dict], Optional[str]]:
    accepted: List[dict] = []
    rejected: List[dict] = []
    first_reason: Optional[str] = None
    for raw in (raw_sources or [])[:MAX_SOURCES_PER_FACTOR]:
        source, reason = _check_source(raw, context)
        if reason is None:
            accepted.append(source)
            continue
        first_reason = first_reason or reason
        if source is not None:
            rejected.append(source)
    return accepted, rejected, first_reason


# ------------------------------------------------------------------ fatores
def _validate_factor_schema(factor: Any) -> bool:
    if not isinstance(factor, dict):
        return False
    enums_ok = (
        factor.get("tipo") in FACTOR_TYPES
        and factor.get("sentido") in DIRECTIONS
        and factor.get("confianca") in CONFIDENCES
    )
    internal_ok = factor.get("evidenciaInterna") in (None,) + INTERNAL_FACTOR_TYPES
    lists_ok = isinstance(factor.get("skusCitados", []), list) and isinstance(factor.get("fontes", []), list)
    return bool(enums_ok and internal_ok and lists_ok)


def _normalize_skus(raw_skus: Any) -> Optional[List[int]]:
    try:
        return [int(sku) for sku in (raw_skus or [])][:MAX_SKUS_PER_FACTOR]
    except (TypeError, ValueError):
        return None


def _hypothesis(tipo: str, text: str, reason: str, sources: List[dict]) -> Dict[str, Any]:
    return {"tipo": tipo, "descricao": text[:MAX_HYPOTHESIS_CHARS], "motivo": reason, "fontes": sources}


def _build_internal_factor(factor: dict, skus: List[int], context: ValidationContext) -> Dict[str, Any]:
    evidence_type = factor.get("evidenciaInterna") or factor["tipo"]
    is_quantitative = context.modo != MODE_QUALITATIVE
    return {
        "tipo": factor["tipo"], "sentido": factor["sentido"],
        "parcelaEstimada": context.parcel_values.get(evidence_type) if is_quantitative else None,
        "confianca": factor["confianca"], "rotulo": "EVIDENCIA", "explicacao": factor["explicacao"],
        "evidenciaInterna": factor.get("evidenciaInterna"), "skusCitados": skus, "fontes": [],
    }


def _build_external_factor(factor: dict, skus: List[int], sources: List[dict]) -> Dict[str, Any]:
    confidence = "MEDIA" if factor["confianca"] == "ALTA" else factor["confianca"]
    return {
        "tipo": factor["tipo"], "sentido": factor["sentido"], "parcelaEstimada": None, "confianca": confidence,
        "rotulo": "POSSIVEL", "explicacao": factor["explicacao"], "evidenciaInterna": None,
        "skusCitados": skus, "fontes": sources,
    }


def _process_factor(
    factor: dict, context: ValidationContext, found: _Collector, hypotheses: List[dict],
) -> Optional[Dict[str, Any]]:
    skus = _normalize_skus(factor.get("skusCitados"))
    if skus is None or any(sku not in context.package_skus for sku in skus):
        found.note("SKU_FORA_DO_PACOTE")
        return None
    if factor["tipo"] in INTERNAL_FACTOR_TYPES:
        evidence_type = factor.get("evidenciaInterna") or factor["tipo"]
        if factor["tipo"] not in context.evaluated_types or evidence_type not in context.evaluated_types:
            found.note("FATOR_INTERNO_SEM_EVIDENCIA")
            return None
        return _build_internal_factor(factor, skus, context)
    accepted, rejected, reason = _split_sources(factor.get("fontes"), context)
    if accepted:
        return _build_external_factor(factor, skus, accepted)
    hypotheses.append(_hypothesis(factor["tipo"], factor["explicacao"], reason or "SEM_FONTE", rejected))
    return None


def _merge_duplicates(factors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for factor in factors:
        existing = merged.get(factor["tipo"])
        if existing is None:
            merged[factor["tipo"]] = factor
            continue
        known = {s["url"] for s in existing["fontes"]}
        existing["fontes"] += [s for s in factor["fontes"] if s["url"] not in known]
        existing["fontes"] = existing["fontes"][:MAX_SOURCES_PER_FACTOR]
    return list(merged.values())


# ------------------------------------------------------------------ textos
def _check_factor_texts(factor: dict, context: ValidationContext, found: _Collector, drop: bool) -> bool:
    """True se o fator pode seguir. Em modo `drop`, texto ruim descarta so o fator."""
    problems = _text_problems(factor.get("explicacao"), MAX_EXPLANATION_CHARS, context)
    for code in problems:
        found.note(code) if drop else found.block(code)
    return not problems or not drop


def _clean_recommendations(raw: Any, context: ValidationContext, found: _Collector, drop: bool) -> List[str]:
    if not isinstance(raw, list):
        found.block("SCHEMA_INVALIDO")
        return []
    kept: List[str] = []
    for text in raw:
        problems = _text_problems(text, MAX_RECOMMENDATION_CHARS, context)
        for code in problems:
            found.note(code) if drop else found.block(code)
        if not problems:
            kept.append(text)
    return kept[:MAX_RECOMMENDATIONS]


def _clean_hypotheses(raw: Any, context: ValidationContext, found: _Collector, drop: bool) -> List[dict]:
    if not isinstance(raw, list):
        found.block("SCHEMA_INVALIDO")
        return []
    kept: List[dict] = []
    for item in raw:
        valid = (isinstance(item, dict) and item.get("tipo") in FACTOR_TYPES
                 and item.get("motivo") in LLM_HYPOTHESIS_REASONS)
        if not valid:
            found.block("SCHEMA_INVALIDO")
            continue
        problems = _text_problems(item.get("descricao"), MAX_HYPOTHESIS_CHARS, context)
        for code in problems:
            found.note(code) if drop else found.block(code)
        if not problems:
            kept.append(_hypothesis(item["tipo"], item["descricao"], item["motivo"], []))
    return kept


def _parse_body(text: str, found: _Collector) -> Optional[dict]:
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        found.block("JSON_INVALIDO")
        return None
    if not isinstance(body, dict) or set(body) != TOP_LEVEL_KEYS or not isinstance(body.get("fatores"), list):
        found.block("SCHEMA_INVALIDO")
        return None
    return body


def validate_llm_output(text: str, context: ValidationContext, drop_offending: bool = False) -> ValidationOutcome:
    """Valida e normaliza a saida; `drop_offending` descarta trechos com digito em vez de reprovar a resposta."""
    found = _Collector()
    body = _parse_body(text, found)
    if body is None:
        return ValidationOutcome(ok=False, violations=found.all_codes(), diagnostico=None)
    for code in _text_problems(body.get("resumo"), MAX_SUMMARY_CHARS, context):
        found.block(code)
    hypotheses: List[dict] = []
    factors: List[Dict[str, Any]] = []
    for factor in body["fatores"]:
        if not _validate_factor_schema(factor):
            found.block("SCHEMA_INVALIDO")
            continue
        if not _check_factor_texts(factor, context, found, drop_offending):
            continue
        built = _process_factor(factor, context, found, hypotheses)
        if built:
            factors.append(built)
    hypotheses += _clean_hypotheses(body.get("hipotesesNaoConfirmadas"), context, found, drop_offending)
    diagnostico = {
        "resumo": body.get("resumo"),
        "fatores": _merge_duplicates(factors)[:MAX_FACTORS],
        "hipotesesNaoConfirmadas": hypotheses[:MAX_HYPOTHESES],
        "recomendacoes": _clean_recommendations(body.get("recomendacoes"), context, found, drop_offending),
    }
    return ValidationOutcome(ok=not found.blocking, violations=found.all_codes(), diagnostico=diagnostico)
