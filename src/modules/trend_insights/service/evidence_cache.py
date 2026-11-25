"""
Cache de fontes de evidencia (D-7.1.16, DA-05): LRU de 200 chaves e TTL de 6 h para elasticidade, sazonalidade
e promocoes por janela. Guarda so agregados por SKU/janela; falha de carga nunca e guardada.
"""
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Callable, Hashable, List, Tuple

EVIDENCE_CACHE_MAX_ENTRIES = 200
EVIDENCE_CACHE_TTL_HOURS = 6


class EvidenceCache:
    def __init__(
        self,
        clock: Callable[[], datetime],
        ttl_hours: int = EVIDENCE_CACHE_TTL_HOURS,
        max_entries: int = EVIDENCE_CACHE_MAX_ENTRIES,
    ):
        self._clock = clock
        self.ttl_hours = ttl_hours
        self.max_entries = max_entries
        self._entries: "OrderedDict[Hashable, Tuple[datetime, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def _lookup(self, key: Hashable) -> Tuple[bool, Any]:
        entry = self._entries.get(key)
        if entry is None or self._clock() - entry[0] >= timedelta(hours=self.ttl_hours):
            return False, None
        self._entries.move_to_end(key)
        return True, entry[1]

    def get_or_build(self, key: Hashable, builder: Callable[[], Any]) -> Any:
        """Devolve o valor guardado ou constroi (fora do lock, para nao travar outras chaves)."""
        with self._lock:
            hit, value = self._lookup(key)
        if hit:
            return value
        value = builder()
        with self._lock:
            self._entries[key] = (self._clock(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return value

    def keys(self) -> List[Hashable]:
        with self._lock:
            return list(self._entries)
