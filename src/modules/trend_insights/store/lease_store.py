"""
Trava de geracao em voo entre instancias (P-176.2, DA-08): objeto GCS criado com precondicao de inexistencia.
O corpo tem so `expiresAt` (LGPD-TIA-10); lease vencido e removido por quem tenta adquirir.
"""
from datetime import datetime, timedelta
from typing import Callable

from src.modules.trend_insights.domain.ports import ObjectConflict, ObjectStore, ObjectStoreUnavailable

NEW_OBJECT_GENERATION = 0


class GcsInFlightLease:
    def __init__(self, store: ObjectStore, clock: Callable[[], datetime]):
        self._store = store
        self._clock = clock

    @staticmethod
    def _path(key: str) -> str:
        return f"locks/insights/{key}.lock"

    def _is_expired(self, body: dict) -> bool:
        return datetime.fromisoformat(body["expiresAt"]) <= self._clock()

    def _create(self, key: str, ttl_seconds: int) -> bool:
        body = {"expiresAt": (self._clock() + timedelta(seconds=ttl_seconds)).isoformat()}
        try:
            self._store.write_json(self._path(key), body, if_generation_match=NEW_OBJECT_GENERATION)
            return True
        except ObjectConflict:
            return False

    def try_acquire(self, key: str, ttl_seconds: int) -> bool:
        """Sem acesso ao armazenamento nao ha como coordenar: segue com a trava local (o livro limita o gasto)."""
        try:
            if self._create(key, ttl_seconds):
                return True
            existing = self._store.read_json(self._path(key))
            if existing is not None and not self._is_expired(existing[0]):
                return False
            self._store.delete(self._path(key), if_generation_match=existing[1] if existing else None)
            return self._create(key, ttl_seconds)
        except ObjectStoreUnavailable:
            return True

    def release(self, key: str) -> None:
        try:
            self._store.delete(self._path(key))
        except ObjectStoreUnavailable:
            return

    def is_held(self, key: str) -> bool:
        try:
            existing = self._store.read_json(self._path(key))
        except ObjectStoreUnavailable:
            return False
        return existing is not None and not self._is_expired(existing[0])
