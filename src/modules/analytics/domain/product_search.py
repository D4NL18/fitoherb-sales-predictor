"""
Busca inteligente e ordenação de produtos do catálogo — domínio puro (contrato §3.6 e §3.7, DC-5, B-19, P-115, P-117).

Normalização: NFKD sem acentos, minúsculas e espaços colapsados ("chá" encontra "CHA"); versão relaxada
separa pontuações comuns (`/`, `-`, `+`, `_`, `.`, `,`, `(`, `)`) por espaço e preserva `%` nos tokens.
Prioridade:
- Só dígitos -> código exato (0), depois códigos que começam com `q` (1).
- Demais -> descrição que começa com `q` (0), descrição que contém `q` (1), tokens em ordem (2),
  tokens em qualquer ordem na descrição (3), tokens na combinação descrição + fornecedor + código (4),
  e match aproximado Damerau-Levenshtein <= 1 para tokens `>= 5` caracteres (5).
Empate por descrição e código crescentes. Só dados de catálogo; nenhum dado de cliente.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from src.modules.analytics.domain.cross_sell import CatalogEntry
from src.modules.analytics.domain.exceptions import InvalidParametersError

MIN_DIGITS_QUERY_LENGTH = 1    # contrato §3.6: código com 1 dígito já é aceito
MIN_TEXT_QUERY_LENGTH = 2      # contrato §3.6: texto exige 2 caracteres após trim
MAX_QUERY_LENGTH = 60          # contrato §3.6 e §3.7
DEFAULT_SEARCH_LIMIT = 20      # contrato §3.6: padrão e máximo da página de busca
MAX_SEARCH_LIMIT = 20
DEFAULT_CATALOG_LIMIT = 5000   # contrato §3.7: catálogo completo (ex.: ~2.200 SKUs ativos) sem truncar
MAX_CATALOG_LIMIT = 5000
MIN_FUZZY_TOKEN_LENGTH = 5     # tolerância de 1 erro apenas para tokens longos (nunca aceita "xyzw")

VALID_STOCK_FILTERS = ("all", "in_stock", "out_of_stock")
VALID_CATALOG_SORT_BY = ("supplier_product", "product", "sku", "stock", "price", "relevance")
VALID_SORT_DIRS = ("asc", "desc")

_PRIORITY_PREFIX = 0
_PRIORITY_SUBSTRING = 1
_PRIORITY_ORDERED_TOKENS = 2
_PRIORITY_UNORDERED_TOKENS = 3
_PRIORITY_COMBINED_TOKENS = 4
_PRIORITY_FUZZY = 5

_WHITESPACE = re.compile(r"\s+")
_RELAXED_SEPARATOR = re.compile(r"[/\-+_.,()]+")


@dataclass(frozen=True)
class SearchableProduct:
    """Produto do catálogo com representações normalizadas pré-calculadas."""

    entry: CatalogEntry
    normalized_description: str
    code_text: str
    normalized_supplier: str = ""
    relaxed_description: str = ""
    relaxed_combined: str = ""
    relaxed_tokens: Tuple[str, ...] = ()
    supplier_tokens: Tuple[str, ...] = ()


def normalize_text(text: str) -> str:
    """Remove acentos (NFKD), passa a minúsculas, faz trim e colapsa espaços internos."""
    without_accents = "".join(
        char for char in unicodedata.normalize("NFKD", text or "") if not unicodedata.combining(char)
    )
    return _WHITESPACE.sub(" ", without_accents).strip().lower()


def normalize_relaxed_text(text: str) -> str:
    """Normaliza separando pontuações (`/`, `-`, `+`, `_`, `.`, `,`, `(`, `)`) por espaço, mantendo `%`."""
    normalized = normalize_text(text)
    if not normalized:
        return ""
    return _WHITESPACE.sub(" ", _RELAXED_SEPARATOR.sub(" ", normalized)).strip()


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
    """Pré-normaliza descrições, fornecedores e tokens do catálogo (uma vez por carga, DA-06)."""
    indexed: List[SearchableProduct] = []
    for entry in entries:
        norm_desc = normalize_text(entry.description)
        norm_supp = normalize_text(entry.supplier)
        code_text = str(entry.code)
        relaxed_desc = normalize_relaxed_text(entry.description)
        relaxed_supp = normalize_relaxed_text(entry.supplier)
        relaxed_combined = _WHITESPACE.sub(" ", f"{relaxed_desc} {relaxed_supp} {code_text}").strip()
        indexed.append(
            SearchableProduct(
                entry=entry,
                normalized_description=norm_desc,
                code_text=code_text,
                normalized_supplier=norm_supp,
                relaxed_description=relaxed_desc,
                relaxed_combined=relaxed_combined,
                relaxed_tokens=tuple(relaxed_desc.split()),
                supplier_tokens=tuple(relaxed_supp.split()),
            )
        )
    return tuple(indexed)


def _code_priority(product: SearchableProduct, query: str) -> Optional[int]:
    """Faixa de prioridade de uma busca só com dígitos; `None` se o código não casa."""
    if product.code_text == query:
        return _PRIORITY_PREFIX
    if product.code_text.startswith(query):
        return _PRIORITY_SUBSTRING
    return None


def _token_matches(query_token: str, target_token: str) -> bool:
    """Casa por exato/prefixo de palavra, ou por substring quando o token tem >= 3 caracteres."""
    if target_token.startswith(query_token):
        return True
    return len(query_token) >= 3 and query_token in target_token


def _tokens_match_in_order(query_tokens: Sequence[str], target_tokens: Sequence[str]) -> bool:
    """Verifica se todos os tokens da consulta aparecem em ordem crescente nos tokens-alvo."""
    cursor = 0
    total = len(target_tokens)
    for query_token in query_tokens:
        matched_index = -1
        for idx in range(cursor, total):
            if _token_matches(query_token, target_tokens[idx]):
                matched_index = idx
                break
        if matched_index < 0:
            return False
        cursor = matched_index + 1
    return True


def _tokens_match_in_text_order(query_tokens: Sequence[str], text: str) -> bool:
    """Fallback em ordem contínua na string normalizada/relaxada para termos sem espaço."""
    cursor = 0
    for query_token in query_tokens:
        pos = text.find(query_token, cursor)
        if pos < 0:
            return False
        cursor = pos + len(query_token)
    return True


def _tokens_match_any_order(query_tokens: Sequence[str], target_tokens: Sequence[str]) -> bool:
    """Verifica se todos os tokens da consulta casam em qualquer posição."""
    return all(any(_token_matches(qt, tt) for tt in target_tokens) for qt in query_tokens)


def _is_damerau_levenshtein_at_most_one(first: str, second: str) -> bool:
    """Retorna True se a distância Damerau-Levenshtein entre `first` e `second` for <= 1."""
    len_a, len_b = len(first), len(second)
    if abs(len_a - len_b) > 1:
        return False
    if first == second:
        return True
    limit = min(len_a, len_b)
    mismatch = 0
    while mismatch < limit and first[mismatch] == second[mismatch]:
        mismatch += 1
    if len_a == len_b:
        if first[mismatch + 1 :] == second[mismatch + 1 :]:
            return True
        return (
            mismatch + 1 < len_a
            and first[mismatch] == second[mismatch + 1]
            and first[mismatch + 1] == second[mismatch]
            and first[mismatch + 2 :] == second[mismatch + 2 :]
        )
    if len_a + 1 == len_b:
        return first[mismatch:] == second[mismatch + 1 :]
    return first[mismatch + 1 :] == second[mismatch:]


def _fuzzy_match_all(query_tokens: Sequence[str], product: SearchableProduct) -> bool:
    """Tolerância de 1 erro apenas para tokens >= 5 chars contra tokens >= 5 da descrição/fornecedor."""
    if not any(len(qt) >= MIN_FUZZY_TOKEN_LENGTH for qt in query_tokens):
        return False
    combined_tokens = product.relaxed_tokens + product.supplier_tokens + (product.code_text,)
    long_candidates = tuple(
        token for token in (product.relaxed_tokens + product.supplier_tokens) if len(token) >= MIN_FUZZY_TOKEN_LENGTH
    )
    if not long_candidates:
        return False
    for query_token in query_tokens:
        if any(_token_matches(query_token, target_token) for target_token in combined_tokens):
            continue
        if len(query_token) >= MIN_FUZZY_TOKEN_LENGTH and any(
            _is_damerau_levenshtein_at_most_one(query_token, candidate) for candidate in long_candidates
        ):
            continue
        return False
    return True


def _description_priority(
    product: SearchableProduct,
    normalized_query: str,
    query_tokens: Sequence[str],
) -> Optional[int]:
    """Faixa de prioridade textual (0..5); `None` se não houver correspondência."""
    if product.normalized_description.startswith(normalized_query):
        return _PRIORITY_PREFIX
    if normalized_query in product.normalized_description:
        return _PRIORITY_SUBSTRING
    if not query_tokens:
        return None
    if _tokens_match_in_order(query_tokens, product.relaxed_tokens):
        return _PRIORITY_ORDERED_TOKENS
    if all(len(qt) >= 2 for qt in query_tokens) and (
        _tokens_match_in_text_order(query_tokens, product.normalized_description)
        or _tokens_match_in_text_order(query_tokens, product.relaxed_description)
    ):
        return _PRIORITY_ORDERED_TOKENS
    if _tokens_match_any_order(query_tokens, product.relaxed_tokens):
        return _PRIORITY_UNORDERED_TOKENS
    combined_tokens = product.relaxed_tokens + product.supplier_tokens + (product.code_text,)
    if _tokens_match_any_order(query_tokens, combined_tokens):
        return _PRIORITY_COMBINED_TOKENS
    if _fuzzy_match_all(query_tokens, product):
        return _PRIORITY_FUZZY
    return None


def _match_priority(
    product: SearchableProduct,
    normalized_query: str,
    query_tokens: Sequence[str],
) -> Optional[int]:
    """Calcula a faixa de relevância de acordo com o tipo de consulta (numérica vs textual)."""
    if normalized_query.isdigit():
        return _code_priority(product, normalized_query)
    return _description_priority(product, normalized_query, query_tokens)


def search_products(index: Sequence[SearchableProduct], query: str) -> List[CatalogEntry]:
    """
    Lista completa (antes da paginação) dos produtos que casam com `query`, na ordem de §3.6.

    Args:
        index: catálogo pré-normalizado (`build_search_index`).
        query: termo já validado por `is_valid_search_query`.
    """
    normalized_query = normalize_text(query)
    relaxed_query = normalize_relaxed_text(normalized_query)
    query_tokens = tuple(relaxed_query.split()) if relaxed_query else ()
    ranked = []
    for product in index:
        priority = _match_priority(product, normalized_query, query_tokens)
        if priority is not None:
            ranked.append((priority, product.normalized_description, product.entry.code, product.entry))
    return [entry for *_, entry in sorted(ranked, key=lambda match: match[:3])]


def catalog_sort_key(
    product: SearchableProduct,
    sort_by: str = "supplier_product",
    priority: int = 0,
) -> Tuple[Any, ...]:
    """Chave pura de ordenação para listagem paginada do catálogo (contrato §3.7, P-117)."""
    if sort_by == "product":
        return (product.normalized_description, product.entry.code)
    if sort_by == "sku":
        return (product.entry.code,)
    if sort_by == "stock":
        return (product.entry.stock, product.normalized_description, product.entry.code)
    if sort_by == "price":
        return (product.entry.price, product.normalized_description, product.entry.code)
    if sort_by == "relevance":
        return (priority, product.normalized_description, product.entry.code)
    return (product.normalized_supplier, product.normalized_description, product.entry.code)


def filter_and_sort_catalog(
    index: Sequence[SearchableProduct],
    query: Optional[str] = None,
    supplier: Optional[str] = None,
    stock_filter: str = "all",
    sort_by: str = "supplier_product",
    sort_dir: str = "asc",
) -> List[CatalogEntry]:
    """
    Filtra e ordena os itens do catálogo ativo em memória (contrato §3.7, P-117).

    Args:
        index: catálogo pré-normalizado (`build_search_index`).
        query: busca textual/código opcional (vazio/espaços não filtra; > 60 chars gera `XSL-004`).
        supplier: filtro opcional por fornecedor (comparação normalizada).
        stock_filter: `all`, `in_stock` (`estoque > 0`) ou `out_of_stock` (`estoque <= 0`).
        sort_by: `supplier_product`, `product`, `sku`, `stock`, `price` ou `relevance`.
        sort_dir: `asc` ou `desc`.
    """
    if stock_filter not in VALID_STOCK_FILTERS:
        raise InvalidParametersError(["stockFilter"])
    if sort_by not in VALID_CATALOG_SORT_BY:
        raise InvalidParametersError(["sortBy"])
    if sort_dir not in VALID_SORT_DIRS:
        raise InvalidParametersError(["sortDir"])

    normalized_query = normalize_text(query) if query is not None else ""
    if len(normalized_query) > MAX_QUERY_LENGTH:
        raise InvalidParametersError(["q"])

    normalized_supplier_filter = normalize_text(supplier) if supplier is not None else ""
    relaxed_query = normalize_relaxed_text(normalized_query) if normalized_query else ""
    query_tokens = tuple(relaxed_query.split()) if relaxed_query else ()

    matches: List[Tuple[int, SearchableProduct]] = []
    for product in index:
        if normalized_supplier_filter and product.normalized_supplier != normalized_supplier_filter:
            continue
        if stock_filter == "in_stock" and product.entry.stock <= 0:
            continue
        if stock_filter == "out_of_stock" and product.entry.stock > 0:
            continue

        priority = 0
        if normalized_query:
            matched_priority = _match_priority(product, normalized_query, query_tokens)
            if matched_priority is None:
                continue
            priority = matched_priority
        matches.append((priority, product))

    effective_sort_by = "supplier_product" if (sort_by == "relevance" and not normalized_query) else sort_by
    ordered = sorted(
        matches,
        key=lambda item: catalog_sort_key(item[1], effective_sort_by, item[0]),
        reverse=(sort_dir == "desc"),
    )
    return [item[1].entry for item in ordered]
