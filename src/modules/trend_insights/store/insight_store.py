"""
Diagnosticos salvos no GCS, um objeto por chave sem usuario (P-175, DA-07), com cache L1 de 5 minutos em
memoria e TTL logico de 30 dias para diagnosticos com fator externo. O JSON nao guarda usuario, IP nem cliente.
"""
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

from src.modules.trend_insights.domain.constants import INSIGHT_L1_CACHE_SECONDS, INSIGHT_SOFT_TTL_DAYS
from src.modules.trend_insights.domain.ports import ObjectConflict, ObjectStore

NEW_OBJECT_GENERATION = 0


@dataclass(frozen=True)
class InsightKey:
    escopo: str
    id: int
    metric: str
    window: int
    base_month: str
    comparison_mode: str
    prompt_version: str
    evidence_hash: str

    def object_path(self) -> str:
        return (
            f"insights/v1/{self.escopo}/{self.id}/{self.metric}/{self.comparison_mode}/"
            f"w{self.window}/{self.base_month}/{self.prompt_version}/{self.evidence_hash}.json"
        )


@dataclass(frozen=True)
class StoredInsight:
    """Diagnostico salvo. Custo, tokens e consultas ficam so aqui; o mapper da API os descarta."""

    diagnostico: Dict[str, Any]
    modelo: str
    origem: str
    gerado_em: str
    prompt_version: str
    evidence_hash: str
    has_external_factor: bool
    cost_usd: float
    input_tokens: int
    output_tokens: int
    queries: int
    sugestoes_busca_html: Optional[str] = None
    radar_ref: Optional[Dict[str, Any]] = None  # radar usado (so referencia): o cache do diagnostico nao depende dele

    def is_expired(self, now: datetime, ttl_days: int = INSIGHT_SOFT_TTL_DAYS) -> bool:
        """Envelhece por tempo todo diagnostico com dimensao externa (P-175.6; na v3, todo diagnostico por LLM)."""
        if not self.has_external_factor:
            return False
        return now - datetime.fromisoformat(self.gerado_em) > timedelta(days=ttl_days)

    def to_json(self) -> Dict[str, Any]:
        document = asdict(self)
        document["radarRef"] = document.pop("radar_ref")
        return document

    @classmethod
    def from_json(cls, payload: Dict[str, Any]) -> "StoredInsight":
        fields = dict(payload)
        fields["radar_ref"] = fields.pop("radarRef", None)
        return cls(**fields)


class InsightStore:
    def __init__(self, store: ObjectStore, clock: Callable[[], datetime]):
        self._store = store
        self._clock = clock
        self._l1: Dict[str, Tuple[datetime, StoredInsight]] = {}
        self._lock = threading.Lock()

    def _l1_get(self, path: str) -> Optional[StoredInsight]:
        with self._lock:
            entry = self._l1.get(path)
        if entry is None:
            return None
        if (self._clock() - entry[0]).total_seconds() > INSIGHT_L1_CACHE_SECONDS:
            return None
        return entry[1]

    def _l1_put(self, path: str, insight: StoredInsight) -> None:
        with self._lock:
            self._l1[path] = (self._clock(), insight)

    def get(self, key: InsightKey) -> Optional[StoredInsight]:
        path = key.object_path()
        cached = self._l1_get(path)
        if cached is not None:
            return cached
        found = self._store.read_json(path)
        if found is None:
            return None
        insight = StoredInsight.from_json(found[0])
        self._l1_put(path, insight)
        return insight

    def put(self, key: InsightKey, insight: StoredInsight, overwrite: bool = False) -> None:
        """Grava apos a validacao. Sem `overwrite`, so cria (conflito = outro ja gravou)."""
        path = key.object_path()
        generation = NEW_OBJECT_GENERATION
        if overwrite:
            current = self._store.read_json(path)
            generation = current[1] if current else NEW_OBJECT_GENERATION
        try:
            self._store.write_json(path, insight.to_json(), if_generation_match=generation)
        except ObjectConflict:
            if not overwrite:
                raise
            self._store.write_json(path, insight.to_json(), if_generation_match=self._current_generation(path))
        self._l1_put(path, insight)

    def _current_generation(self, path: str) -> int:
        current = self._store.read_json(path)
        return current[1] if current else NEW_OBJECT_GENERATION
