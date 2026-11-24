"""
Testes Unitários: Identificação de Substitutos e Mineração de Co-compradores (TDD First)
Fase F6 — Tarefa 1 — Regras P-128 (P-128.1 a P-128.5).

Cenários cobertos:
1. Jaccard = 1.0 para bases de compradores idênticas.
2. Jaccard = 0.0 para bases disjuntas e exclusão do candidato.
3. Jaccard parcial exato e proteção contra conjuntos vazios (sem divisão por zero).
4. Filtro híbrido: mesmo `Tipo` + Jaccard >= 0.15 OU compradores em comum >= 5.
5. Produto de `Tipo` diferente só entra se tiver >= 5 compradores em comum.
6. Exclusão do próprio SKU alvo e de produtos inativos no catálogo.
7. Ranqueamento decrescente por Jaccard e poda em `MAX_CANDIDATE_SUBSTITUTES` (20).
8. Isolamento de PII: nenhum `Cod Cliente` exposto nos DTOs ou payload serializado.
"""
from __future__ import annotations

import json

import pytest

from src.modules.analytics.api.schemas import (
    ResponseMeta,
    SubstituteCandidateDTO,
    SubstitutionDataDTO,
    SubstitutionResponse,
)
from src.modules.analytics.domain.cannibalization import (
    MAX_CANDIDATE_SUBSTITUTES,
    MIN_COMMON_BUYERS,
    MIN_JACCARD_SIMILARITY,
    calculate_jaccard_similarity,
    find_candidate_substitutes,
)


def _catalog_entry(
    sku: str,
    tipo: str = "EXTRATOS",
    ativo: bool = True,
    descricao: str = "",
    preco: float = 25.0,
    estoque: int = 100,
) -> dict:
    return {
        "sku": sku,
        "description": descricao or f"PRODUTO {sku}",
        "category": tipo,
        "active": ativo,
        "current_price": preco,
        "current_stock": estoque,
    }


def test_jaccard_identical_buyers_returns_one():
    """Cenário 1: Dois produtos com exatamente os mesmos 10 compradores resultam em Jaccard = 1.0."""
    # Arrange
    buyers_target = {f"C{i}" for i in range(1, 11)}
    buyers_candidate = {f"C{i}" for i in range(1, 11)}

    # Act
    score = calculate_jaccard_similarity(buyers_target, buyers_candidate)

    # Assert
    assert score == pytest.approx(1.0)


def test_jaccard_disjoint_buyers_returns_zero():
    """Cenário 2: Produtos sem nenhum comprador em comum resultam em Jaccard = 0.0."""
    # Arrange
    buyers_target = {1, 2, 3, 4, 5}
    buyers_candidate = {6, 7, 8, 9, 10}

    # Act
    score = calculate_jaccard_similarity(buyers_target, buyers_candidate)

    # Assert
    assert score == pytest.approx(0.0)


@pytest.mark.parametrize(
    "buyers_a,buyers_b,expected",
    [
        ({1, 2, 3, 4}, {3, 4, 5, 6}, 2 / 6),
        (set(), {1, 2}, 0.0),
        ({1, 2}, set(), 0.0),
        (set(), set(), 0.0),
    ],
)
def test_jaccard_partial_and_empty_sets(buyers_a, buyers_b, expected):
    """Edge case: cálculo exato de interseção/união e proteção contra conjuntos vazios."""
    # Arrange & Act
    score = calculate_jaccard_similarity(buyers_a, buyers_b)

    # Assert
    assert score == pytest.approx(expected)


def test_find_candidates_same_tipo_vs_different_tipo_min_common_buyers():
    """
    Cenário 3 (P-128.3):
    - Mesmo `Tipo` + Jaccard >= 0.15 entra.
    - `Tipo` diferente só entra se `common_buyers >= 5` (mesmo se Jaccard >= 0.15 com < 5).
    - Sem sobreposição (Jaccard = 0.0) é excluído.
    """
    # Arrange
    target_sku = "1001"
    target_buyers = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
    catalog = {
        "1001": _catalog_entry("1001", tipo="EXTRATOS"),
        "1002": _catalog_entry("1002", tipo="EXTRATOS"),   # mesmo Tipo, 3 em comum, Jaccard = 3/12 = 0.25 >= 0.15 -> ENTRA
        "1003": _catalog_entry("1003", tipo="EXTRATOS"),   # mesmo Tipo, 1 em comum, Jaccard = 1/19 = 0.052 < 0.15 -> FORA
        "1004": _catalog_entry("1004", tipo="CAPSULAS"),   # Tipo diferente, 3 em comum (< 5), Jaccard = 3/10 = 0.30 -> FORA
        "1005": _catalog_entry("1005", tipo="CAPSULAS"),   # Tipo diferente, 5 em comum (>= 5) -> ENTRA
        "1006": _catalog_entry("1006", tipo="EXTRATOS"),   # 0 em comum -> FORA
    }
    buyers_by_sku = {
        "1001": target_buyers,
        "1002": {1, 2, 3, 11, 12},
        "1003": {1, 20, 21, 22, 23, 24, 25, 26, 27, 28},
        "1004": {1, 2, 3},
        "1005": {1, 2, 3, 4, 5, 30, 31, 32, 33, 34},
        "1006": {90, 91, 92},
    }

    # Act
    candidates = find_candidate_substitutes(
        target_sku=target_sku,
        catalog=catalog,
        buyers_by_sku=buyers_by_sku,
    )

    # Assert
    assert MIN_JACCARD_SIMILARITY == pytest.approx(0.15)
    assert MIN_COMMON_BUYERS == 5
    returned_skus = [c.sku for c in candidates]
    assert "1002" in returned_skus
    assert "1005" in returned_skus
    assert "1001" not in returned_skus
    assert "1003" not in returned_skus
    assert "1004" not in returned_skus
    assert "1006" not in returned_skus


def test_find_candidates_excludes_inactive_products():
    """P-128.1: Produtos inativos no catálogo não podem aparecer como substitutos."""
    # Arrange
    catalog = {
        "1001": _catalog_entry("1001", tipo="CHAS", ativo=True),
        "1002": _catalog_entry("1002", tipo="CHAS", ativo=False),
    }
    buyers_by_sku = {
        "1001": {1, 2, 3, 4, 5},
        "1002": {1, 2, 3, 4, 5},
    }

    # Act
    candidates = find_candidate_substitutes(
        target_sku="1001",
        catalog=catalog,
        buyers_by_sku=buyers_by_sku,
    )

    # Assert
    assert candidates == []


def test_find_candidates_sorts_descending_and_caps_at_20():
    """P-128.4: Ordenação decrescente por Jaccard e limite máximo de 20 candidatos."""
    # Arrange
    target_buyers = set(range(1, 31))  # 30 compradores
    catalog = {"1000": _catalog_entry("1000", tipo="EXTRATOS")}
    buyers_by_sku = {"1000": target_buyers}

    for idx in range(1, 31):
        sku = str(1000 + idx)
        catalog[sku] = _catalog_entry(sku, tipo="EXTRATOS")
        # Interseção cresce com idx: de 5 a 30 compradores em comum
        overlap = min(30, 4 + idx)
        buyers_by_sku[sku] = set(range(1, overlap + 1)) | {100 + idx}

    # Act
    candidates = find_candidate_substitutes(
        target_sku="1000",
        catalog=catalog,
        buyers_by_sku=buyers_by_sku,
    )

    # Assert
    assert MAX_CANDIDATE_SUBSTITUTES == 20
    assert len(candidates) == 20
    jaccards = [c.jaccard_similarity for c in candidates]
    assert jaccards == sorted(jaccards, reverse=True)


def test_substitution_dtos_do_not_expose_customer_pii():
    """P-128.5: Nenhum `Cod Cliente` ou identificador de comprador pode existir nos DTOs."""
    # Arrange
    candidate = SubstituteCandidateDTO(
        sku="100235",
        description="EXTRATO DE PROPOLIS AQUOSO 30ML",
        category="EXTRATOS",
        jaccard_similarity=0.42,
        common_buyers_count=38,
        current_price=22.00,
        current_stock=185,
    )
    response = SubstitutionResponse(
        data=SubstitutionDataDTO(
            target_sku="100234",
            target_description="EXTRATO DE PROPOLIS VERDE 30ML",
            target_category="EXTRATOS",
            target_current_price=24.50,
            target_stock=340,
            substitutes=[candidate],
        ),
        meta=ResponseMeta(
            timestamp="2026-11-12T14:30:00Z",
            version="1.0.0",
            data_referencia="2026-11-12",
        ),
    )

    # Act
    dumped = response.model_dump(by_alias=True)

    def _collect_keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k.lower()
                yield from _collect_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _collect_keys(item)

    all_keys = set(_collect_keys(dumped))

    # Assert
    for forbidden_key in ("codcliente", "cod_cliente", "customercode", "customer_code", "buyers", "clientes"):
        assert forbidden_key not in all_keys
