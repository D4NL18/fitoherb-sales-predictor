"""
Correção de Múltiplos Testes via Benjamini-Hochberg (FDR) para Canibalização (Fase F6).
Regra: P-133.2; ADR-007 DA-03.

Isolamento estrito: funções puras sem dependência de I/O ou frameworks web.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class FDRResult:
    """Resultado da correção Benjamini-Hochberg: q-valores ajustados e flags de significância."""

    q_values: List[float]
    significant_flags: List[bool]


def benjamini_hochberg(p_values: Sequence[float], alpha: float = 0.05) -> FDRResult:
    """
    Aplica o procedimento step-up de Benjamini-Hochberg para controle da Taxa de Falsas Descobertas (FDR).

    Args:
        p_values: Sequência de p-valores brutos (entre 0.0 e 1.0).
        alpha: Nível de controle de FDR desejado (padrão 0.05).

    Returns:
        FDRResult contendo `q_values` na ordem original e `significant_flags` (`q <= alpha`).
    """
    m = len(p_values)
    if m == 0:
        return FDRResult(q_values=[], significant_flags=[])

    # Ordena índices pelos p-valores crescentes
    sorted_indices = sorted(range(m), key=lambda idx: p_values[idx])

    raw_q_sorted: List[float] = []
    for rank_zero_based, orig_idx in enumerate(sorted_indices):
        rank = rank_zero_based + 1
        p_clamped = min(1.0, max(0.0, float(p_values[orig_idx])))
        raw_q_sorted.append(min(1.0, (m / rank) * p_clamped))

    # Garante monotonicidade via mínimo cumulativo de trás para frente (step-up)
    q_sorted = list(raw_q_sorted)
    for j in range(m - 2, -1, -1):
        q_sorted[j] = min(q_sorted[j], q_sorted[j + 1])

    q_values = [0.0] * m
    for rank_zero_based, orig_idx in enumerate(sorted_indices):
        q_values[orig_idx] = q_sorted[rank_zero_based]

    significant_flags = [q <= alpha for q in q_values]
    return FDRResult(q_values=q_values, significant_flags=significant_flags)
