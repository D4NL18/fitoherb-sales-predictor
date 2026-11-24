"""
Interface de Integração Desacoplada com Elasticidade-Preço Cruzada (Fase F5).
Regra: P-136; ADR-007 DA-05.

Permite que F6 opere de forma autônoma (`NullCrossElasticityProvider` -> `NAO_INTEGRADO`)
e incorpore a decomposição de choque de preço quando a elasticidade cruzada estiver disponível.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class CrossElasticityProvider(Protocol):
    """Contrato assíncrono para consulta de elasticidade-preço cruzada entre SKUs (P-136)."""

    async def get_cross_elasticity(self, target_sku: str, substitute_sku: str) -> Optional[float]:
        """Retorna epsilon_ji (%ΔQ_j / %ΔP_i) ou None quando indisponível."""
        ...


class NullCrossElasticityProvider:
    """Provedor nulo para degradação graciosa enquanto F5 não expõe elasticidade cruzada (P-136.3)."""

    async def get_cross_elasticity(self, target_sku: str, substitute_sku: str) -> Optional[float]:
        return None


@dataclass(frozen=True)
class CrossElasticityDecomposition:
    """Decomposição do efeito DiD entre choque de preço e efeito residual de visibilidade (P-136.2)."""

    cross_elasticity: float
    price_explained_delta_volume: float
    residual_delta_volume: float
    price_explained_share: float


def decompose_cross_elasticity(
    cross_elasticity: Optional[float],
    candidate_pre_volume: float,
    target_price_change_ratio: float,
    total_delta_volume: float,
) -> Optional[CrossElasticityDecomposition]:
    """
    Decompõe ΔV_j em parcela explicada por elasticidade cruzada de preço e desvio residual.

    Fórmula (P-136.2):
        ΔV_{j,preco} = V_j^{Pre} * (ε_{ji} * (ΔP_i / P_i^{Pre}))
        ΔV_{j,residual} = ΔV_j - ΔV_{j,preco}
    """
    if cross_elasticity is None:
        return None

    price_explained = float(candidate_pre_volume) * (
        float(cross_elasticity) * float(target_price_change_ratio)
    )
    residual = float(total_delta_volume) - price_explained
    if abs(total_delta_volume) > 1e-9:
        share = price_explained / float(total_delta_volume)
    else:
        share = 0.0

    return CrossElasticityDecomposition(
        cross_elasticity=float(cross_elasticity),
        price_explained_delta_volume=price_explained,
        residual_delta_volume=residual,
        price_explained_share=share,
    )
