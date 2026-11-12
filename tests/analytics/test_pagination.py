"""
T-01 — Paginação pura do módulo Analytics (P-066, CA-15, C-14).

Interface esperada (B-03, `src/modules/analytics/domain/pagination.py`):
`PageRequest(limit, offset)` frozen dataclass com padrão `limit=DEFAULT_PAGE_LIMIT`, `offset=0`;
`PageResult(items, total_items, page, total_pages)`; `paginate(items, page_request) -> PageResult`.
"""
import dataclasses

import pytest

from src.modules.analytics.domain.pagination import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    PageRequest,
    PageResult,
    paginate,
)

TOTAL_RECOMMENDATIONS = 120


@pytest.fixture
def items():
    return list(range(TOTAL_RECOMMENDATIONS))


def test_page_constants_match_business_rule():
    """P-066.2: padrão 50, máximo 200."""
    assert DEFAULT_PAGE_LIMIT == 50
    assert MAX_PAGE_LIMIT == 200


def test_page_request_is_frozen_with_defaults():
    request = PageRequest()
    assert request.limit == DEFAULT_PAGE_LIMIT
    assert request.offset == 0
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.limit = 10  # type: ignore[misc]


def test_ca15_third_page_of_120_items(items):
    """CA-15: limit=50&offset=100 -> 20 itens, page=3, totalItems=120, totalPages=3."""
    result = paginate(items, PageRequest(limit=50, offset=100))

    assert isinstance(result, PageResult)
    assert list(result.items) == list(range(100, 120))
    assert result.total_items == TOTAL_RECOMMENDATIONS
    assert result.page == 3
    assert result.total_pages == 3


def test_ca15_default_page_returns_first_50(items):
    """CA-15: sem limit, vêm 50 itens."""
    result = paginate(items, PageRequest())

    assert list(result.items) == list(range(50))
    assert result.page == 1
    assert result.total_pages == 3


def test_page_formula_uses_floor_of_offset(items):
    """P-066.3: page = floor(offset / limit) + 1, mesmo com offset fora do múltiplo do limit."""
    result = paginate(items, PageRequest(limit=50, offset=75))

    assert result.page == 2
    assert list(result.items) == list(range(75, 120))


@pytest.mark.parametrize("offset", [120, 121, 500])
def test_c14_offset_beyond_total_returns_empty_with_totals(items, offset):
    """P-066.4 / C-14: offset >= totalItems devolve lista vazia com os totais corretos (não é erro)."""
    result = paginate(items, PageRequest(limit=50, offset=offset))

    assert list(result.items) == []
    assert result.total_items == TOTAL_RECOMMENDATIONS
    assert result.total_pages == 3
    assert result.page == offset // 50 + 1


def test_no_items_means_zero_pages():
    """P-066.3: totalPages = 0 quando não há itens."""
    result = paginate([], PageRequest())

    assert list(result.items) == []
    assert result.total_items == 0
    assert result.total_pages == 0
    assert result.page == 1


def test_exact_multiple_does_not_create_extra_page():
    result = paginate(list(range(100)), PageRequest(limit=50, offset=50))

    assert result.total_pages == 2
    assert len(result.items) == 50


def test_paginate_does_not_mutate_input(items):
    snapshot = list(items)
    paginate(items, PageRequest(limit=10, offset=5))
    assert items == snapshot
