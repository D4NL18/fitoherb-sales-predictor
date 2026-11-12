"""
Busca de produto por código ou descrição — domínio puro (contrato §3.6, DC-5 aprovado, B-19).

Normalização: NFKD sem acentos, minúsculas e espaços colapsados ("chá" encontra "CHA").
Prioridade: só dígitos -> código exato, depois códigos que começam com `q`; demais -> descrição que
começa com `q`, depois descrição que contém `q`. Empate por descrição e código crescentes.
A descrição normalizada é calculada uma vez, na carga do catálogo (`build_search_index`).
Só dados de catálogo; nenhum dado de cliente.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from src.modules.analytics.domain.cross_sell import CatalogEntry

MIN_DIGITS_QUERY_LENGTH = 1    # contrato §3.6: código com 1 dígito já é aceito
MIN_TEXT_QUERY_LENGTH = 2      # contrato §3.6: texto exige 2 caracteres após trim
MAX_QUERY_LENGTH = 60          # contrato §3.6
DEFAULT_SEARCH_LIMIT = 20      # contrato §3.6: padrão e máximo da página de busca
MAX_SEARCH_LIMIT = 20

_EXACT_MATCH, _PREFIX_MATCH = 0, 1  # faixas de prioridade (menor vem antes)
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class SearchableProduct:
    """Produto do catálogo com a descrição normalizada pré-calculada."""

    entry: CatalogEntry
    normalized_description: str
    code_text: str


def normalize_text(text: str) -> str:
    """Remove acentos (NFKD), passa a minúsculas, faz trim e colapsa espaços internos."""
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(char)
    )
    return _WHITESPACE.sub(" ", without_accents).strip().lower()


def is_valid_search_query(query: str) -> bool:
    """
    Valida `q` após trim/colapso: 1 a 60 caracteres se só dígitos; 2 a 60 nos demais casos.
    Regra: contrato §3.6 (400 `XSL-004` com `fields: ["q"]` quando falso).
    """
    normalized = normalize_text(query)
    if len(normalized) > MAX_QUERY_LENGTH:
        return False
    minimum = MIN_DIGITS_QUERY_LENGTH if normalized.isdigit() else MIN_TEXT_QUERY_LENGTH
    return len(normalized) >= minimum


def build_search_index(entries: Iterable[CatalogEntry]) -> Tuple[SearchableProduct, ...]:
    """Pré-normaliza as descrições do catálogo (feito uma vez por carga do catálogo, DA-06)."""
    return tuple(SearchableProduct(entry, normalize_text(entry.description), str(entry.code)) for entry in entries)


def _code_priority(product: SearchableProduct, query: str) -> Optional[int]:
    """Faixa de prioridade de uma busca só com dígitos; `None` se o código não casa."""
    if product.code_text == query:
        return _EXACT_MATCH
    if product.code_text.startswith(query):
        return _PREFIX_MATCH
    return None


def _description_priority(product: SearchableProduct, query: str) -> Optional[int]:
    """Faixa de prioridade de uma busca textual; `None` se a descrição não contém `q`."""
    if product.normalized_description.startswith(query):
        return _EXACT_MATCH
    if query in product.normalized_description:
        return _PREFIX_MATCH
    return None


def search_products(index: Sequence[SearchableProduct], query: str) -> List[CatalogEntry]:
    """
    Lista completa (antes da paginação) dos produtos que casam com `query`, na ordem de §3.6.

    Args:
        index: catálogo pré-normalizado (`build_search_index`).
        query: termo já validado por `is_valid_search_query`.
    """
    normalized_query = normalize_text(query)
    priority_of = _code_priority if normalized_query.isdigit() else _description_priority
    ranked = []
    for product in index:
        priority = priority_of(product, normalized_query)
        if priority is not None:
            ranked.append((priority, product.normalized_description, product.entry.code, product.entry))
    return [entry for *_, entry in sorted(ranked, key=lambda match: match[:3])]
