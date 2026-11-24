"""Portas (interfaces) e sinalizadores de indisponibilidade usados pelo dominio e pelos servicos."""
from dataclasses import dataclass
from typing import Any, Optional, Protocol, Tuple


class ObjectConflict(Exception):
    """Precondicao de geracao falhou (outro escritor chegou antes)."""


class ObjectStoreUnavailable(Exception):
    """Armazenamento de objetos inacessivel (rede, permissao, bucket ausente)."""


class TrendSourceUnavailable(Exception):
    """ANL-001: base de vendas indisponivel para a celula da Tendencia (P-173)."""


@dataclass(frozen=True)
class NotEvaluated:
    """Resultado de uma porta que nao pode ser avaliada (P-173): a parcela vira NAO_AVALIADO."""

    reason: str


class ObjectStore(Protocol):
    """Porta de armazenamento de objetos JSON com precondicao de geracao (GCS)."""

    def read_json(self, path: str) -> Optional[Tuple[Any, int]]:
        """Devolve `(conteudo, geracao)` ou `None` se o objeto nao existe."""

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        """Grava com precondicao (0 = so se nao existir). Devolve a nova geracao."""

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        """Remove o objeto (idempotente)."""


class InFlightLease(Protocol):
    """Trava de geracao em voo compartilhada entre instancias."""

    def try_acquire(self, key: str, ttl_seconds: int) -> bool: ...

    def release(self, key: str) -> None: ...

    def is_held(self, key: str) -> bool: ...
