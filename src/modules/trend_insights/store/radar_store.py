"""
Radar externo no GCS (`radar/{versao}/{slug}/{AAAA-MM}.json`, P-180.3, DA-13): um objeto por (assunto, mes-base),
SEM usuario, SKU, cliente ou variacao na chave nem no conteudo, compartilhado entre produtos e usuarios. A leitura
e ESTRITA: objeto com campo livre, tema fora da lista ou formato inesperado (ex.: plantado no bucket) e ignorado
e logado como `tia.radar.injectionSuspect` sem payload. Escrita com precondicao de geracao (concorrencia segura).
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.modules.trend_insights.domain.constants import LOGGER_NAME, RADAR_PROMPT_VERSION
from src.modules.trend_insights.domain.external_dimensions import EXTERNAL_DIMENSIONS
from src.modules.trend_insights.domain.ports import ObjectStore
from src.modules.trend_insights.domain.radar_themes import RADAR_THEMES
from src.modules.trend_insights.llm.radar_schema import INTENSITIES, MOVEMENTS, STATUSES

logger = logging.getLogger(LOGGER_NAME + ".radar")
NEW_OBJECT_GENERATION = 0
_SOURCE_ID = re.compile(r"F[0-9]{1,2}")
_DOC_KEYS = frozenset({
    "geradoEm", "modelo", "assunto", "mesBase", "dimensoes", "fontes", "consultasExecutadas",
    "searchSuggestionsHtml", "radarHash",
})
_SUBJECT_KEYS = frozenset({"slug", "termo", "tipo"})
_DIMENSION_KEYS = frozenset({"dimensao", "status", "movimento", "intensidade", "tema", "fonteIds"})
_SOURCE_KEYS = frozenset({"id", "url", "dominio", "titulo", "dataPublicacao", "origemData"})
MAX_IDS_PER_DIMENSION = 2


class RadarObjectInvalid(ValueError):
    """Objeto do radar fora do formato fechado (nunca ecoa o conteudo)."""


def radar_path(version: str, slug: str, base_month: str) -> str:
    return f"radar/{version}/{slug}/{base_month}.json"


def _check(condition: bool) -> None:
    if not condition:
        raise RadarObjectInvalid()


def _check_dimension(item: Any, expected: str) -> None:
    _check(isinstance(item, dict) and set(item) == _DIMENSION_KEYS and item["dimensao"] == expected)
    ids = item["fonteIds"]
    _check(item["status"] in STATUSES and item["movimento"] in MOVEMENTS)
    _check(item["intensidade"] in INTENSITIES + (None,))
    _check(item["tema"] is None or item["tema"] in RADAR_THEMES[expected])
    _check(isinstance(ids, list) and len(ids) <= MAX_IDS_PER_DIMENSION)
    _check(all(isinstance(i, str) and _SOURCE_ID.fullmatch(i) for i in ids))


def _check_source(item: Any) -> None:
    _check(isinstance(item, dict) and set(item) == _SOURCE_KEYS and _SOURCE_ID.fullmatch(str(item["id"])) is not None)
    _check(all(isinstance(item[key], str) for key in ("url", "dominio", "titulo")))


@dataclass(frozen=True)
class StoredRadar:
    generated_at: datetime
    model: str
    slug: str
    term: str
    kind: str
    base_month: str
    dimensions: Tuple[Dict[str, Any], ...]
    sources: Tuple[Dict[str, Any], ...]
    queries_executed: int
    search_suggestions_html: Optional[str]
    radar_hash: str
    generation: int = NEW_OBJECT_GENERATION  # geracao GCS lida (precondicao da proxima escrita)

    @classmethod
    def from_json(cls, doc: Any, generation: int = NEW_OBJECT_GENERATION) -> "StoredRadar":
        """Leitura estrita; qualquer desvio do formato fechado levanta `RadarObjectInvalid`."""
        _check(isinstance(doc, dict) and set(doc) == _DOC_KEYS)
        subject, dimensions, sources = doc["assunto"], doc["dimensoes"], doc["fontes"]
        _check(isinstance(subject, dict) and set(subject) == _SUBJECT_KEYS)
        _check(isinstance(dimensions, list) and len(dimensions) == len(EXTERNAL_DIMENSIONS))
        _check(isinstance(sources, list) and isinstance(doc["mesBase"], str))
        for item, expected in zip(dimensions, EXTERNAL_DIMENSIONS):
            _check_dimension(item, expected)
        for source in sources:
            _check_source(source)
        try:
            generated_at = datetime.fromisoformat(doc["geradoEm"])
        except (TypeError, ValueError):
            raise RadarObjectInvalid() from None
        return cls(
            generated_at=generated_at, model=str(doc["modelo"]), slug=subject["slug"], term=subject["termo"],
            kind=subject["tipo"], base_month=doc["mesBase"], dimensions=tuple(dimensions), sources=tuple(sources),
            queries_executed=int(doc["consultasExecutadas"] or 0), search_suggestions_html=doc["searchSuggestionsHtml"],
            radar_hash=str(doc["radarHash"]), generation=generation,
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "geradoEm": self.generated_at.isoformat(), "modelo": self.model,
            "assunto": {"slug": self.slug, "termo": self.term, "tipo": self.kind}, "mesBase": self.base_month,
            "dimensoes": [dict(d) for d in self.dimensions], "fontes": [dict(s) for s in self.sources],
            "consultasExecutadas": self.queries_executed, "searchSuggestionsHtml": self.search_suggestions_html,
            "radarHash": self.radar_hash,
        }

    def source_by_id(self) -> Dict[str, Dict[str, Any]]:
        return {source["id"]: source for source in self.sources}


def compute_radar_hash(dimensions: List[Dict[str, Any]], sources: List[Dict[str, Any]]) -> str:
    """Impressao digital do conteudo (rastreabilidade de radar suspeito); nunca exposta pela API."""
    canonical = json.dumps({"dimensoes": dimensions, "fontes": sources}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RadarStore:
    def __init__(self, store: ObjectStore, clock: Callable[[], datetime], version: str = RADAR_PROMPT_VERSION):
        self._store = store
        self._clock = clock
        self._version = version

    def path_for(self, slug: str, base_month: str) -> str:
        return radar_path(self._version, slug, base_month)

    def get(self, slug: str, base_month: str) -> Optional[StoredRadar]:
        """Radar salvo ou `None` (ausente ou objeto invalido, que e ignorado e logado sem payload)."""
        found = self._store.read_json(self.path_for(slug, base_month))
        if found is None:
            return None
        try:
            return StoredRadar.from_json(found[0], generation=found[1])
        except (RadarObjectInvalid, KeyError, TypeError):
            logger.warning("tia.radar.injectionSuspect violations=OBJETO_INVALIDO")
            return None

    def current_generation(self, slug: str, base_month: str) -> int:
        """Geracao atual do objeto no GCS (mesmo invalido): base da precondicao de escrita."""
        found = self._store.read_json(self.path_for(slug, base_month))
        return found[1] if found else NEW_OBJECT_GENERATION

    def put(self, radar: StoredRadar, expected_generation: int) -> int:
        """Grava com `if_generation_match`; `ObjectConflict` sobe (outro escritor chegou antes)."""
        return self._store.write_json(
            self.path_for(radar.slug, radar.base_month), radar.to_json(), if_generation_match=expected_generation)

    def count(self) -> int:
        """Radares em cache sob o prefixo da versao atual (so contagem, para o `health`)."""
        return len(self._store.paths(f"radar/{self._version}/"))
