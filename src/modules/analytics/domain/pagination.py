"""
Paginação pura do módulo Analytics Comercial (P-066, ADR-002 DA-09).

Implementa corte por limit/offset, cálculo de totalPages (ceil) e page (floor(offset/limit) + 1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generic, Sequence, TypeVar

T = TypeVar("T")

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


@dataclass(frozen=True)
class PageRequest:
    """Parâmetros de paginação solicitados."""

    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0


@dataclass(frozen=True)
class PageResult(Generic[T]):
    """Resultado paginado de itens com metadados."""

    items: Sequence[T]
    total_items: int
    page: int
    total_pages: int


def paginate(items: Sequence[T], page_request: PageRequest) -> PageResult[T]:
    """
    Aplica paginação por corte de lista (P-066).

    - total_items: contagem total de itens disponíveis.
    - total_pages: ceil(total_items / limit); 0 quando não há itens.
    - page: floor(offset / limit) + 1.
    - items: fatia [offset : offset + limit].
    """
    total_items = len(items)
    if total_items == 0:
        total_pages = 0
        page = 1
        sliced: Sequence[T] = []
    else:
        total_pages = math.ceil(total_items / page_request.limit)
        page = (page_request.offset // page_request.limit) + 1
        sliced = items[page_request.offset : page_request.offset + page_request.limit]

    return PageResult(
        items=sliced,
        total_items=total_items,
        page=page,
        total_pages=total_pages,
    )
