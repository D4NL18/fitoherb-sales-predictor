"""
Testes de Integração dos Endpoints REST de Elasticidade-Preço
Fase 2 (F5) - Regras P-095 a P-105 e Contrato de API.
"""
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.api.schemas import (
    CustomerElasticityDetail,
    CustomerElasticityItem,
    ElasticitySimulationResponse,
    ProductElasticityDetail,
    ProductElasticityResponse,
    ProductHeader,
)
from src.modules.analytics.domain.elasticity import (
    CustomerElasticityResult,
    ProductElasticityResult,
    SimulationImpactResult,
)
from src.modules.analytics.domain.exceptions import (
    CustomerWithoutHistoryError,
    InsufficientBaseError,
    ProductNotFoundError,
)

client = TestClient(app)

BASE_URL = "/api/v1/analytics/elasticity"


def _fake_product_response(sku: int = 1001) -> ProductElasticityResponse:
    from src.modules.analytics.api.schemas import ResponseMeta
    return ProductElasticityResponse(
        data=ProductElasticityDetail(
            product=ProductHeader(
                code=sku,
                description="EXTRATO DE PROPOLIS VERDE 30ML",
                supplier="FITOHERB LAB",
                current_price=25.50,
                cost_price=12.00,
                stock=420.0,
            ),
            elasticity=ProductElasticityResult(
                coefficient=-1.45,
                classification="ELASTICO",
                r_squared=0.58,
                standard_error=0.18,
                confidence_interval=(-1.80, -1.10),
                confidence_level="ALTA",
                is_reliable=True,
                observations_count=18,
                fallback_applied=False,
                insight_message="Demanda elástica.",
            ),
            customers=[
                CustomerElasticityItem(
                    customer_code=4501,
                    orders_count=12,
                    total_units=350.0,
                    empirical_elasticity=-1.60,
                    shrinkage_elasticity=-1.52,
                    classification="ELASTICO",
                    shrinkage_weight=0.55,
                )
            ],
        ),
        meta=ResponseMeta(
            timestamp="2026-11-12T12:00:00Z",
            version="1.0.0",
            total_items=1,
            total_pages=1,
            limit=50,
            offset=0,
        ),
    )


def test_get_product_elasticity_success():
    """T-API-01: GET /elasticity/product/{sku} retorna 200 com envelope padronizado."""
    with patch("src.modules.analytics.service.analytics_service.get_product_elasticity") as mock_get:
        mock_get.return_value = _fake_product_response(1001)

        response = client.get(f"{BASE_URL}/product/1001")
        assert response.status_code == 200
        json_data = response.json()
        assert "data" in json_data
        assert "meta" in json_data
        assert json_data["data"]["product"]["code"] == 1001
        assert json_data["data"]["elasticity"]["coefficient"] == -1.45
        assert json_data["data"]["elasticity"]["classification"] == "ELASTICO"
        assert len(json_data["data"]["customers"]) == 1


def test_get_product_elasticity_not_found():
    """T-API-02: GET /elasticity/product/{sku} com SKU inexistente retorna 404 ELA-001."""
    with patch("src.modules.analytics.service.analytics_service.get_product_elasticity") as mock_get:
        mock_get.side_effect = ProductNotFoundError()

        response = client.get(f"{BASE_URL}/product/999999")
        assert response.status_code == 404
        json_data = response.json()
        assert "error" in json_data
        assert json_data["error"]["code"] == "ELA-001"


def test_get_product_elasticity_invalid_sku():
    """T-API-03: GET /elasticity/product/{sku} com SKU inválido retorna 400 ELA-004."""
    response = client.get(f"{BASE_URL}/product/-5")
    assert response.status_code == 400
    json_data = response.json()
    assert json_data["error"]["code"] == "ELA-004"
    assert "sku" in json_data["error"]["fields"]


def test_get_customer_elasticity_success():
    """T-API-04: GET /elasticity/product/{sku}/customer/{customerCode} retorna 200 com shrinkage."""
    from src.modules.analytics.api.schemas import CustomerElasticityResponse, ResponseMeta
    fake_resp = CustomerElasticityResponse(
        data=CustomerElasticityDetail(
            sku=1001,
            customer_code=4501,
            product_elasticity=-1.45,
            customer_empirical_elasticity=-1.60,
            customer_elasticity=-1.52,
            classification="ELASTICO",
            shrinkage_weight=0.55,
            orders_count=12,
            total_units=350.0,
            confidence_level="MEDIA",
            is_reliable=True,
            insight_message="Cliente sensível a variações de preço neste SKU.",
        ),
        meta=ResponseMeta(timestamp="2026-11-12T12:00:00Z", version="1.0.0"),
    )

    with patch("src.modules.analytics.service.analytics_service.get_customer_elasticity") as mock_get:
        mock_get.return_value = fake_resp

        response = client.get(f"{BASE_URL}/product/1001/customer/4501")
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["sku"] == 1001
        assert json_data["data"]["customerCode"] == 4501
        assert json_data["data"]["customerElasticity"] == -1.52


def test_get_customer_elasticity_not_found():
    """T-API-05: GET /elasticity/product/{sku}/customer/{customerCode} sem compras retorna 404 ELA-002."""
    with patch("src.modules.analytics.service.analytics_service.get_customer_elasticity") as mock_get:
        mock_get.side_effect = CustomerWithoutHistoryError()

        response = client.get(f"{BASE_URL}/product/1001/customer/999999")
        assert response.status_code == 404
        json_data = response.json()
        assert json_data["error"]["code"] == "ELA-002"


def test_simulate_price_impact_success():
    """T-API-06: POST /elasticity/simulate calcula variação e retorna 200."""
    from src.modules.analytics.api.schemas import ElasticitySimulationResponse, ResponseMeta
    fake_sim = ElasticitySimulationResponse(
        data=SimulationImpactResult(
            sku=1001,
            customer_code=None,
            applied_elasticity=-1.45,
            price_change_pct=5.0,
            current_price=25.50,
            projected_price=26.78,
            current_volume=350.0,
            projected_volume=324.6,
            volume_change_pct=-7.25,
            current_revenue=8925.0,
            projected_revenue=8692.79,
            revenue_change_pct=-2.60,
            revenue_change_abs=-232.21,
            current_margin=4725.0,
            projected_margin=4797.59,
            margin_change_pct=1.54,
            margin_change_abs=72.59,
            recommendation="Reajuste viável com aumento de margem monetária.",
        ),
        meta=ResponseMeta(timestamp="2026-11-12T12:00:00Z", version="1.0.0"),
    )

    with patch("src.modules.analytics.service.analytics_service.simulate_price_change") as mock_sim:
        mock_sim.return_value = fake_sim

        payload = {"sku": 1001, "priceChangePct": 5.0}
        response = client.post(f"{BASE_URL}/simulate", json=payload)
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["data"]["sku"] == 1001
        assert json_data["data"]["appliedElasticity"] == -1.45
        assert json_data["data"]["marginChangeAbs"] == 72.59


def test_simulate_price_impact_out_of_range():
    """T-API-07: POST /elasticity/simulate com priceChangePct fora de [-50, 100] retorna 400 ELA-004."""
    payload = {"sku": 1001, "priceChangePct": 150.0}
    response = client.post(f"{BASE_URL}/simulate", json=payload)
    assert response.status_code == 400
    json_data = response.json()
    assert json_data["error"]["code"] == "ELA-004"
    assert "priceChangePct" in json_data["error"]["fields"]
