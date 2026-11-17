"""
Utilitário de paginação para listas de tendência de vendas (P-081.4, ADR-003 DA-10).
"""
import math
from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

DEFAULT_PAGE_LIMIT: int = 50
MAX_PAGE_LIMIT: int = 200

T = TypeVar("T")


@dataclass(frozen=True)
class PageRequest:
    """Parâmetros de requisição de página."""
    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """Resultado paginado imutável."""
    items: Sequence[T]
    total_items: int
    page: int
    total_pages: int
    limit: int
    offset: int


def paginate(items: Sequence[T], limit: int = DEFAULT_PAGE_LIMIT, offset: int = 0) -> PageResult[T]:
    """
    Pagina uma sequência em memória devolvendo fatiamento e metadados.
    Se total_items == 0, total_pages é 0 e items é vazio.
    """
    total = len(items)
    if total == 0:
        return PageResult(
            items=[],
            total_items=0,
            page=1,
            total_pages=0,
            limit=limit,
            offset=offset,
        )

    safe_limit = max(1, limit)
    total_pages = math.ceil(total / safe_limit)
    page = (offset // safe_limit) + 1
    slice_items = items[offset : offset + safe_limit]

    return PageResult(
        items=slice_items,
        total_items=total,
        page=page,
        total_pages=total_pages,
        limit=safe_limit,
        offset=offset,
    )
