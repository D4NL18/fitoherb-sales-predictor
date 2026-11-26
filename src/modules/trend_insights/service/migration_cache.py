"""
Cache do snapshot de migracao por janela (P-153.5, DA-04/DA-05): TTL de 6 h, LRU de 8 chaves, voo unico por
chave e UMA carga por vez (o motor e pesado em memoria). Falha de carga nao e guardada. Guarda so o
snapshot agregado, nunca linhas por cliente.
"""
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Hashable, List, Tuple

from src.modules.trend_insights.domain.constants import MIGRATION_CACHE_MAX_ENTRIES, MIGRATION_CACHE_TTL_HOURS


class MigrationCache:
    def __init__(
        self,
        builder: Callable[[Hashable], Any],
        clock: Callable[[], datetime],
        ttl_hours: int = MIGRATION_CACHE_TTL_HOURS,
        max_entries: int = MIGRATION_CACHE_MAX_ENTRIES,
    ):
        self._builder = builder
        self._clock = clock
        self._ttl = timedelta(hours=ttl_hours)
        self._max_entries = max_entries
        self._entries: "OrderedDict[Hashable, Tuple[datetime, Any, int]]" = OrderedDict()
        self._inflight: Dict[Hashable, threading.Lock] = {}
        self._state_lock = threading.Lock()
        self._build_semaphore = threading.Semaphore(1)

    def _lookup(self, key: Hashable) -> Any:
        entry = self._entries.get(key)
        if entry is None or self._clock() - entry[0] >= self._ttl:
            return None
        self._entries.move_to_end(key)
        return entry

    def _store(self, key: Hashable, value: Any) -> None:
        with self._state_lock:
            self._entries[key] = (self._clock(), value, 0)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def get_or_build(self, key: Hashable) -> Any:
        with self._state_lock:
            hit = self._lookup(key)
            if hit is not None:
                return hit[1]
            key_lock = self._inflight.setdefault(key, threading.Lock())
        with key_lock:
            return self._build_once(key)

    def _build_once(self, key: Hashable) -> Any:
        with self._state_lock:
            hit = self._lookup(key)
        if hit is not None:
            return hit[1]
        with self._build_semaphore:
            value = self._builder(key)
        self._store(key, value)
        return value

    def status(self) -> List[Dict[str, Any]]:
        """Metadados sem SKU nem cliente, para o health."""
        with self._state_lock:
            return [
                {"key": key, "loadedAt": loaded_at, "expiresAt": loaded_at + self._ttl}
                for key, (loaded_at, _value, _n) in self._entries.items()
            ]
