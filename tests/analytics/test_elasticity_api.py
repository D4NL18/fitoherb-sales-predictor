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
    CustomerElasticityResponse,
    ElasticitySimulationResponse,
    ProductElasticityDetail,
    ProductElasticityMetrics,
    ProductElasticityResponse,
    ProductHeader,
    ResponseMeta,
    SimulationImpactData,
)
from src.modules.analytics.domain.exceptions import (
    ElasticityCustomerWithoutHistoryError,
    ElasticityInsufficientBaseError,
    ElasticityProductNotFoundError,
)

client = TestClient(app)

BASE_URL = "/api/v1/analytics/elasticity"


def _fake_product_response(sku: int = 1001) -> ProductElasticityResponse:
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
            elasticity=ProductElasticityMetrics(
                coefficient=-1.45,
                classification="ELASTICO",
                r_squared=0.58,
                standard_error=0.18,
                confidence_interval=[-1.80, -1.10],
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
        mock_get.side_effect = ElasticityProductNotFoundError()

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
        mock_get.side_effect = ElasticityCustomerWithoutHistoryError()

        response = client.get(f"{BASE_URL}/product/1001/customer/999999")
        assert response.status_code == 404
        json_data = response.json()
        assert json_data["error"]["code"] == "ELA-002"


def test_simulate_price_impact_success():
    """T-API-06: POST /elasticity/simulate calcula variação e retorna 200."""
    fake_sim = ElasticitySimulationResponse(
        data=SimulationImpactData(
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


def _real_catalog_snapshot():
    from datetime import datetime, timezone
    from src.modules.analytics.domain.cross_sell import CatalogEntry
    from src.modules.analytics.service.analytics_cache import CatalogSnapshot

    return CatalogSnapshot(
        reference_date=date(2026, 11, 12),
        loaded_at=datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc),
        entries={
            100002: CatalogEntry(
                code=100002,
                description="CHA VERDE SOLUVEL 200G",
                supplier="FITOHERB LAB",
                stock=150.0,
                price=29.90,
                unit_cost=14.00,
                is_cost_estimated=False,
            )
        },
        search_index=(),
    )


def test_real_service_uses_catalog_snapshot_entries_and_decimal_rows():
    """Regressão: serviço real deve consultar `catalog.entries` e tolerar `Decimal` do pyodbc."""
    from decimal import Decimal
    import pandas as pd

    snapshot = _real_catalog_snapshot()
    price_points = pd.DataFrame([
        {"ano": 2026, "mes": m, "operacao": "VENDA", "qtd": Decimal(100 - m * 5), "valor": Decimal((100 - m * 5) * (25 + m))}
        for m in range(1, 7)
    ])
    customers_df = pd.DataFrame([
        {"customer_code": 4501, "orders_count": 8, "total_units": Decimal("120.0"), "total_revenue": Decimal("3588.0")}
    ])

    with (
        patch("src.modules.analytics.service.analytics_cache.get_catalog", return_value=snapshot),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_price_points", return_value=price_points),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_customers", return_value=customers_df),
        patch("src.modules.analytics.repository.sales_repository.fetch_single_customer_points", return_value=price_points),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_recent_volume_60d", return_value=120.0),
    ):
        resp_prod = client.get(f"{BASE_URL}/product/100002")
        assert resp_prod.status_code == 200
        prod_header = resp_prod.json()["data"]["product"]
        assert prod_header["code"] == 100002
        assert prod_header["isCostEstimated"] is False
        assert prod_header["recentVolume60d"] == pytest.approx(120.0)
        assert prod_header["stockTargetDays"] == 60
        assert resp_prod.json()["data"]["customers"][0]["customerCode"] == 4501

        resp_missing = client.get(f"{BASE_URL}/product/999999")
        assert resp_missing.status_code == 404
        assert resp_missing.json()["error"]["code"] == "ELA-001"

        resp_cust = client.get(f"{BASE_URL}/product/100002/customer/4501")
        assert resp_cust.status_code == 200
        assert resp_cust.json()["data"]["customerCode"] == 4501

        resp_sim = client.post(f"{BASE_URL}/simulate", json={"sku": 100002, "priceChangePct": 10.0})
        assert resp_sim.status_code == 200
        sim_data = resp_sim.json()["data"]
        assert sim_data["sku"] == 100002
        assert sim_data["currentVolume"] == pytest.approx(120.0)
        assert sim_data["costPrice"] == pytest.approx(14.00)
        assert sim_data["isCostEstimated"] is False
        assert sim_data["isCostOverride"] is False
        assert sim_data["stock"] == pytest.approx(150.0)
        assert sim_data["stockTargetDays"] == 60
        assert sim_data["currentUnitMargin"] == pytest.approx(15.90, abs=0.01)
        assert sim_data["projectedUnitMargin"] == pytest.approx(18.89, abs=0.01)
        assert sim_data["currentDailyUnits"] == pytest.approx(2.0)
        assert sim_data["currentStockDays"] == pytest.approx(75.0)
        assert sim_data["projectedStockDays"] is not None
        assert sim_data["stockDaysDelta"] is not None


def test_simulate_price_impact_with_manual_cost_price_override():
    """T-API-08: POST /elasticity/simulate com costPrice manual recalcula margens e sinaliza override."""
    from decimal import Decimal
    import pandas as pd

    snapshot = _real_catalog_snapshot()
    price_points = pd.DataFrame([
        {"ano": 2026, "mes": m, "operacao": "VENDA", "qtd": Decimal(100 - m * 5), "valor": Decimal((100 - m * 5) * (25 + m))}
        for m in range(1, 7)
    ])

    with (
        patch("src.modules.analytics.service.analytics_cache.get_catalog", return_value=snapshot),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_price_points", return_value=price_points),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_recent_volume_60d", return_value=120.0),
    ):
        response = client.post(
            f"{BASE_URL}/simulate",
            json={"sku": 100002, "priceChangePct": 10.0, "costPrice": 20.0},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["costPrice"] == pytest.approx(20.0)
    assert data["isCostOverride"] is True
    assert data["isCostEstimated"] is False
    assert data["currentUnitMargin"] == pytest.approx(9.90, abs=0.01)
    assert data["projectedUnitMargin"] == pytest.approx(12.89, abs=0.01)
    assert data["currentUnitMarginPct"] == pytest.approx((9.90 / 29.90) * 100.0, abs=0.1)
    assert data["projectedUnitMarginPct"] == pytest.approx((12.89 / 32.89) * 100.0, abs=0.1)
    assert data["unitMarginPctChangePp"] > 0.0
    assert data["currentMargin"] == pytest.approx(9.90 * 120.0, abs=0.5)


def test_simulate_price_impact_negative_cost_price_returns_ela_004():
    """T-API-09: POST /elasticity/simulate com costPrice negativo retorna 400 ELA-004."""
    payload = {"sku": 1001, "priceChangePct": 5.0, "costPrice": -2.0}
    response = client.post(f"{BASE_URL}/simulate", json=payload)

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["error"]["code"] == "ELA-004"
    assert "costPrice" in json_data["error"]["fields"]


def test_real_service_zero_recent_volume_and_estimated_cost_fallback():
    """T-API-10: Volume 60d zerado não cai em fallback 100.0 e custo ausente usa fallback 60%."""
    from datetime import datetime, timezone
    from decimal import Decimal
    import pandas as pd
    from src.modules.analytics.domain.cross_sell import CatalogEntry
    from src.modules.analytics.service.analytics_cache import CatalogSnapshot

    snapshot = CatalogSnapshot(
        reference_date=date(2026, 11, 12),
        loaded_at=datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc),
        entries={
            100003: CatalogEntry(
                code=100003,
                description="CHA DE CAMOMILA 100G",
                supplier="FITOHERB LAB",
                stock=80.0,
                price=50.0,
                unit_cost=30.0,
                is_cost_estimated=True,
            )
        },
        search_index=(),
    )
    price_points = pd.DataFrame([
        {"ano": 2026, "mes": m, "operacao": "VENDA", "qtd": Decimal(50 - m * 2), "valor": Decimal((50 - m * 2) * (45 + m))}
        for m in range(1, 7)
    ])
    customers_df = pd.DataFrame(columns=["customer_code", "orders_count", "total_units", "total_revenue"])

    with (
        patch("src.modules.analytics.service.analytics_cache.get_catalog", return_value=snapshot),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_price_points", return_value=price_points),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_customers", return_value=customers_df),
        patch("src.modules.analytics.repository.sales_repository.fetch_product_recent_volume_60d", return_value=0.0),
    ):
        resp_prod = client.get(f"{BASE_URL}/product/100003")
        assert resp_prod.status_code == 200
        prod = resp_prod.json()["data"]["product"]
        assert prod["isCostEstimated"] is True
        assert prod["recentVolume60d"] == 0.0
        assert prod["stockTargetDays"] == 60

        resp_sim = client.post(f"{BASE_URL}/simulate", json={"sku": 100003, "priceChangePct": 10.0})
        assert resp_sim.status_code == 200
        sim = resp_sim.json()["data"]
        assert sim["currentVolume"] == 0.0
        assert sim["projectedVolume"] == 0.0
        assert sim["volumeChangeUnits"] == 0.0
        assert sim["currentDailyUnits"] == 0.0
        assert sim["projectedDailyUnits"] == 0.0
        assert sim["currentStockDays"] is None
        assert sim["projectedStockDays"] is None
        assert sim["stockDaysDelta"] is None
        assert sim["isCostEstimated"] is True
        assert sim["isCostOverride"] is False
        assert sim["costPrice"] == pytest.approx(30.0)
        assert sim["currentUnitMargin"] == pytest.approx(20.0)
        assert sim["projectedUnitMargin"] == pytest.approx(25.0)
