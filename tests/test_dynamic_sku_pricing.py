"""
Testes unitários para Precificação Autônoma e Dinâmica por SKU (Épico 7, P-013).
Valida P-048, P-049, P-050 e P-051.
"""
import pytest
from src.modules.pricing.api.schemas import PricingRequest
from src.modules.pricing.service.pricing_service import execute_pricing_computation


def test_autonomous_sku_pricing_computation():
    """Valida se execute_pricing_computation com autonomous_sku_pricing=True produz variações individuais."""
    req_autonomous = PricingRequest(
        kRatio=0.25,
        variableKRatio=True,
        topAnchors=15,
        halfLifeDays=100.0,
        anchorMinDiscount=-0.15,
        anchorMaxDiscount=-0.05,
        compMaxIncrease=0.06,
        stressDrop=0.05,
        autonomousSkuPricing=True
    )

    df_consolidated, top_anchors, pricing_results, replay, stress, anchor_locks = execute_pricing_computation(req_autonomous)

    assert len(top_anchors) >= 5, "Deve eleger quantidade saudável de âncoras dinâmicos"
    assert len(pricing_results) > len(top_anchors), "Deve haver produtos compensadores mapeados"

    # Verificar se os âncoras possuem descontos e elasticidades atribuídas
    anchor_discounts = []
    for anchor in top_anchors:
        info = pricing_results[anchor]
        assert info["papel"] == "PRODUTO ÂNCORA"
        assert "elasticidade" in info
        assert "trava_k" in info
        anchor_discounts.append(info["novo_preco"])

    assert len(anchor_discounts) == len(top_anchors)

    # Verificar se compensadores possuem queda de estresse preditiva
    comp_skus = [s for s, info in pricing_results.items() if info["papel"] == "COMPENSADOR"]
    assert len(comp_skus) > 0
    sample_comp = pricing_results[comp_skus[0]]
    assert "queda_volume_estresse_pct" in sample_comp
    assert sample_comp["queda_volume_estresse_pct"] > 0.0

    # Verificar métricas de estresse
    assert "lucro_liquido_estresse" in stress
    assert stress["lucro_liquido_estresse"] is not None


def test_uniform_pricing_when_autonomous_disabled():
    """Valida se com autonomous_sku_pricing=False o sistema respeita os parâmetros escalares do usuário."""
    req_uniform = PricingRequest(
        kRatio=0.20,
        variableKRatio=False,
        topAnchors=10,
        halfLifeDays=100.0,
        anchorMinDiscount=-0.10,
        anchorMaxDiscount=-0.05,
        compMaxIncrease=0.05,
        stressDrop=0.04,
        autonomousSkuPricing=False
    )

    df_consolidated, top_anchors, pricing_results, replay, stress, anchor_locks = execute_pricing_computation(req_uniform)

    assert len(top_anchors) == 10, "Com modo autônomo desligado, deve usar exatamente 10 âncoras"
    assert stress["queda_volume_compensadores_pct"] == 4.0
