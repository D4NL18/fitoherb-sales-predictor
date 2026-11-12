"""
Curadoria das Sugestões de cross-sell (P-094) — domínio puro, aplicada depois do ranking.

Por quê: na base real a maioria das sugestões era a mesma linha do fornecedor em outro sabor, aroma
ou tamanho (WHEY 100% PURE CHOC para quem compra WHEY 100% PURE BAUN; seis sabores de CRISP BAR), e
as listas passavam de 100 linhas. O usuário pediu só as principais, priorizando produtos do mesmo
fornecedor ou parecidos com o de origem. A curadoria:

1. P-094.1 — descarta a **variante** do produto de origem (mesmo fornecedor + mesmo nome-base):
   outro sabor/tamanho do que o cliente já leva não é venda cruzada;
2. P-094.2 — **prioriza por faixa**: mesmo fornecedor da origem, depois produto similar de outro
   fornecedor (compartilha palavra significativa da descrição), depois o resto. Dentro da faixa vale
   o ranking recebido (P-061.1 / P-064.2);
3. P-094.3 — mantém **uma sugestão por linha de produto** (a primeira após a priorização);
4. P-094.4 — devolve só as `MAX_RECOMMENDATIONS` principais.

Palavras significativas = descrição normalizada sem acento, sem conectivos (DE/E/COM), sem símbolos
(+, &) e sem tamanhos (300G, 1KG, 500MG). Nome-base = a primeira delas. É heurística sobre o
cadastro: o catálogo não tem campo de família/categoria de produto.
"""
from __future__ import annotations

import re
from typing import Callable, FrozenSet, Iterable, List, Mapping, Optional, Set, Tuple, TypeVar

from src.modules.analytics.domain.cross_sell import CatalogEntry, UsefulRule
from src.modules.analytics.domain.product_search import normalize_text

MAX_RECOMMENDATIONS = 10            # P-094.4: só as principais por consulta
LINE_NAME_WORDS = 1                 # P-094.1: palavras do nome-base (ARGILA VERDE ~ ARGILA BRANCA)
MIN_PLURAL_WORD_LENGTH = 3          # palavras curtas (ex.: "MAS") não perdem o S final

# P-094.2: faixas de prioridade (menor = primeiro)
SAME_SUPPLIER_TIER = 0
SIMILAR_PRODUCT_TIER = 1
OTHER_PRODUCT_TIER = 2

# Palavras que não identificam o produto: conectivos e unidades soltas. Palavras com dígito (300G,
# 1KG, 500MG, 12UN, 100%) também saem: tamanho/concentração não muda a linha do produto.
_IGNORED_WORDS = frozenset({"DE", "DA", "DO", "DAS", "DOS", "E", "COM", "C", "SEM", "S", "EM", "PARA",
                            "G", "KG", "MG", "ML", "L", "UN", "UND", "UNID", "CAPS", "CX"})
_WORD_PATTERN = re.compile(r"[A-Z0-9%]+")

Item = TypeVar("Item")
LineKey = Tuple[str, str]


def _singular(word: str) -> str:
    """Plural simples do cadastro (BALAS -> BALA), para BALA GENGIBRE e BALAS GENGIBRE serem a mesma linha."""
    if len(word) > MIN_PLURAL_WORD_LENGTH and word.endswith("S") and not word.endswith("SS"):
        return word[:-1]
    return word


def _significant_words(entry: CatalogEntry) -> List[str]:
    """Palavras que identificam o produto, na ordem da descrição e no singular."""
    words = _WORD_PATTERN.findall(normalize_text(entry.description).upper())
    return [_singular(word) for word in words
            if word not in _IGNORED_WORDS and not any(char.isdigit() for char in word)]


def _supplier(entry: CatalogEntry) -> str:
    """Fornecedor normalizado; `""` quando o cadastro não tem fornecedor (desconhecido)."""
    return normalize_text(entry.supplier).upper().strip()


def _is_same_known_supplier(source: CatalogEntry, candidate: CatalogEntry) -> bool:
    """Mesmo fornecedor, e conhecido: dois produtos sem fornecedor não contam como "mesmo fornecedor"."""
    supplier = _supplier(source)
    return bool(supplier) and supplier == _supplier(candidate)


def product_line_key(entry: CatalogEntry) -> LineKey:
    """(fornecedor, nome-base) que identifica a linha de produto. Regra: P-094.1, P-094.3."""
    return _supplier(entry), " ".join(_significant_words(entry)[:LINE_NAME_WORDS])


def is_variant(source: CatalogEntry, candidate: CatalogEntry) -> bool:
    """
    `True` se o candidato é outro sabor/aroma/tamanho da mesma linha do produto de origem (P-094.1).
    Sem fornecedor conhecido não há como afirmar que é a mesma linha: não é variante.
    """
    return _is_same_known_supplier(source, candidate) and product_line_key(source) == product_line_key(candidate)


def priority_tier(source: Optional[CatalogEntry], candidate: CatalogEntry) -> int:
    """
    Faixa de P-094.2: mesmo fornecedor da origem, similar (palavra significativa em comum) ou outro.
    Sem origem no catálogo não há com o que comparar: vai para a última faixa.
    """
    if source is None:
        return OTHER_PRODUCT_TIER
    if _is_same_known_supplier(source, candidate):
        return SAME_SUPPLIER_TIER
    shared_words: FrozenSet[str] = frozenset(_significant_words(source)) & frozenset(_significant_words(candidate))
    return SIMILAR_PRODUCT_TIER if shared_words else OTHER_PRODUCT_TIER


def _prioritized(items: Iterable[Item], catalog: Mapping[int, CatalogEntry], rule_of: Callable[[Item], UsefulRule]
                 ) -> List[Tuple[Item, CatalogEntry]]:
    """Itens com consequente no catálogo, sem variantes da origem, ordenados por faixa e depois pelo ranking."""
    ranked: List[Tuple[int, int, Item, CatalogEntry]] = []
    for position, item in enumerate(items):
        rule = rule_of(item)
        candidate = catalog.get(rule.consequent)
        source = catalog.get(rule.antecedent)
        if candidate is None or (source is not None and is_variant(source, candidate)):
            continue
        ranked.append((priority_tier(source, candidate), position, item, candidate))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return [(item, candidate) for _, _, item, candidate in ranked]


def curate(items: Iterable[Item], catalog: Mapping[int, CatalogEntry], rule_of: Callable[[Item], UsefulRule]
           ) -> List[Item]:
    """
    Aplica P-094.1 a P-094.4.

    Args:
        items: sugestões já ordenadas pelo ranking do modo (produto ou cliente).
        catalog: catálogo ativo, para descrição e fornecedor.
        rule_of: extrai a regra principal do item (antecedente = origem, consequente = sugestão).

    Returns:
        No máximo `MAX_RECOMMENDATIONS` itens: sem variantes da origem, mesmo fornecedor primeiro,
        depois similares, depois o resto, e um item por linha de produto.
    """
    kept: List[Item] = []
    seen_lines: Set[LineKey] = set()
    for item, candidate in _prioritized(items, catalog, rule_of):
        line = product_line_key(candidate)
        if line in seen_lines:
            continue
        seen_lines.add(line)
        kept.append(item)
        if len(kept) == MAX_RECOMMENDATIONS:
            break
    return kept
