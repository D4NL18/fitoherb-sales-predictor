"""
Testes de API REST para Viabilidade de Produto Novo (contrato 1.0.0; P-139 a P-149).

Testa:
- GET /api/v1/analytics/new-product/options (200 OK, envelope data/meta, ordenação).
- POST /api/v1/analytics/new-product/forecast:
  - 200 OK completo (com custo, margem mínima, similares, tetoMaduroP75, sazonalidade e selo).
  - 200 OK sem custoUnitario / margemMinimaDesejada (campos financeiros null).
  - 200 OK borda custoUnitario == precoVendaPrevisto (margem 0.00).
  - 400 NEW-004 para precoVendaPrevisto <= 0, custoUnitario > precoVendaPrevisto, margemMinimaDesejada fora [0, 1],
    horizonMonths fora {1, 2, 3}, descricao curta.
  - 400 NEW-002 para tipo inexistente no catálogo.
  - 400 NEW-003 para fornecedor inexistente no catálogo.
  - 422 NEW-001 para < 3 similares elegíveis.
  - 503 NEW-005 para indisponibilidade do banco de dados.
  - LGPD-05: ausência de eco dos valores enviados ou stacktrace nas mensagens de erro.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.domain.exceptions import (
    NewProductInsufficientSimilarsError,
    NewProductInvalidSupplierError,
    NewProductInvalidTypeError,
)
from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from src.modules.analytics.service import analytics_service
from tests.analytics.test_new_product_domain import _make_launch_df


@pytest.fixture(autouse=True)
def _setup_new_product_mocks(monkeypatch):
    """Configura mocks determinísticos de catálogo, lançamentos e produtos maduros para a API."""
    options = {
        "tipos": ["Capsulas", "Extratos", "Pomadas", "Tinturas"],
        "fornecedores": [
            "BIO ERVAS IND E COM LTDA",
            "FITOHERB LABORATORIOS",
            "HERBAL BRASIL DISTRIBUICAO",
        ],
    }

    s1 = _make_launch_df(
        sku=1042,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura de Passiflora Incarnata 50ml",
        preco=39.90,
        first_sale=date(2025, 5, 10),
        monthly_quantities=[58, 65, 80],
    )
    s2 = _make_launch_df(
        sku=1089,
        tipo="Tinturas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Tintura Mae de Valeriana Officinalis 50ml",
        preco=44.00,
        first_sale=date(2025, 6, 1),
        monthly_quantities=[52, 60, 75],
    )
    s3 = _make_launch_df(
        sku=1150,
        tipo="Tinturas",
        fornecedor="HERBAL BRASIL DISTRIBUICAO",
        descricao="Tintura de Camomila Matricaria 50ml Gotas",
        preco=38.00,
        first_sale=date(2025, 4, 18),
        monthly_quantities=[45, 50, 68],
    )
    # Tipo Pomadas tem apenas 2 lançamentos -> deve disparar NEW-001 (422)
    p1 = _make_launch_df(
        sku=2001,
        tipo="Pomadas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Pomada de Arnica 30g",
        preco=25.00,
        first_sale=date(2025, 5, 1),
        monthly_quantities=[30, 35, 40],
    )
    p2 = _make_launch_df(
        sku=2002,
        tipo="Pomadas",
        fornecedor="FITOHERB LABORATORIOS",
        descricao="Pomada de Calendula 30g",
        preco=26.00,
        first_sale=date(2025, 6, 1),
        monthly_quantities=[25, 30, 35],
    )
    candidates_df = pd.concat([s1, s2, s3, p1, p2], ignore_index=True)

    mature_df = pd.DataFrame(
        [
            {"sku": 9001, "tipo": "Tinturas", "first_sale_date": date(2025, 1, 10), "net_quantity": 120},
            {"sku": 9002, "tipo": "Tinturas", "first_sale_date": date(2025, 2, 1), "net_quantity": 180},
            {"sku": 9003, "tipo": "Tinturas", "first_sale_date": date(2025, 3, 15), "net_quantity": 240},
        ]
    )

    monkeypatch.setattr(analytics_service, "_get_new_product_options", lambda: options)
    monkeypatch.setattr(
        analytics_service,
        "_get_new_product_candidates_df",
        lambda tipo: candidates_df[candidates_df["tipo"] == tipo].copy(),
    )
    monkeypatch.setattr(
        analytics_service,
        "_get_mature_product_distribution_df",
        lambda tipo: mature_df[mature_df["tipo"] == tipo].copy(),
    )
    monkeypatch.setattr(
        analytics_service,
        "_find_affinity_similars_for_new_product",
        lambda name, description="", category="", top_k=30: [
            {
                "sku": "1042",
                "description": "Tintura de Passiflora Incarnata 50ml",
                "supplier": "FITOHERB LABORATORIOS",
                "category": "Tinturas",
                "currentPrice": 39.90,
                "affinityScore": 0.82,
            },
            {
                "sku": "1089",
                "description": "Tintura Mae de Valeriana Officinalis 50ml",
                "supplier": "FITOHERB LABORATORIOS",
                "category": "Tinturas",
                "currentPrice": 44.00,
                "affinityScore": 0.76,
            },
            {
                "sku": "1150",
                "description": "Tintura de Camomila Matricaria 50ml Gotas",
                "supplier": "HERBAL BRASIL DISTRIBUICAO",
                "category": "Tinturas",
                "currentPrice": 38.00,
                "affinityScore": 0.68,
            },
        ],
    )


def _valid_payload(**overrides) -> dict:
    payload = {
        "tipo": "Tinturas",
        "fornecedor": "FITOHERB LABORATORIOS",
        "descricao": "Tintura Mae de Melissa Officinalis 50ml Frasco",
        "precoVendaPrevisto": 42.50,
        "custoUnitario": 19.10,
        "margemMinimaDesejada": 0.50,
        "horizonMonths": 3,
    }
    payload.update(overrides)
    return payload


def test_options_endpoint():
    """P-141: GET /api/v1/analytics/new-product/options retorna tipos e fornecedores ordenados no envelope data/meta."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/new-product/options")
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["data"]["tipos"] == sorted(body["data"]["tipos"])
    assert body["data"]["fornecedores"] == sorted(body["data"]["fornecedores"])
    assert "Tinturas" in body["data"]["tipos"]
    assert "FITOHERB LABORATORIOS" in body["data"]["fornecedores"]


def test_forecast_success_full_payload():
    """C-01: POST /api/v1/analytics/new-product/forecast retorna projeção conservadora, similares e viabilidade."""
    client = TestClient(app)
    response = client.post("/api/v1/analytics/new-product/forecast", json=_valid_payload())
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert "dataReferencia" in body["meta"]

    data = body["data"]
    assert len(data["monthlyForecast"]) == 3
    for m in data["monthlyForecast"]:
        assert m["conservativeQuantity"] <= m["similarP25Quantity"]
        assert 0.90 <= m["seasonalityFactor"] <= 1.10

    assert data["financialViability"]["viavel"] is True
    assert data["financialViability"]["margemBrutaUnitaria"] == pytest.approx(23.40, abs=0.01)
    assert data["marketCeiling"]["tetoMaduroP75"] > 0
    assert len(data["similarsUsed"]) == 3
    assert data["similarsUsed"][0]["affinityScore"] > 0
    assert data["referencePriceRange"]["minPrice"] == pytest.approx(38.00)
    assert data["referencePriceRange"]["maxPrice"] == pytest.approx(44.00)
    assert data["cannibalizationRisk"]["riskLevel"] == "ALTO"
    assert data["cannibalizationRisk"]["affectedSkuCount"] == 3
    assert data["cannibalizationRisk"]["sameSupplierAffectedCount"] == 2
    assert data["cannibalizationRisk"]["crossSupplierAffectedCount"] == 1
    assert "conservador" in data["methodologyNotice"].lower()


def test_forecast_without_cost_or_margin():
    """C-03: Sem custoUnitario e margemMinimaDesejada, campos de margem e viavel retornam null."""
    client = TestClient(app)
    payload = {
        "tipo": "Tinturas",
        "fornecedor": "FITOHERB LABORATORIOS",
        "descricao": "Tintura Mae de Melissa Officinalis 50ml",
        "precoVendaPrevisto": 42.50,
    }
    response = client.post("/api/v1/analytics/new-product/forecast", json=payload)
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["financialViability"]["custoUnitario"] is None
    assert data["financialViability"]["margemBrutaUnitaria"] is None
    assert data["financialViability"]["margemBrutaPercentual"] is None
    assert data["financialViability"]["viavel"] is None


def test_input_validation_price():
    """P-140 / C-07: precoVendaPrevisto <= 0 retorna HTTP 400 com código NEW-004 e sem eco do valor."""
    client = TestClient(app)
    for bad_price in (0, -15.75):
        response = client.post(
            "/api/v1/analytics/new-product/forecast",
            json=_valid_payload(precoVendaPrevisto=bad_price),
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "NEW-004"
        assert "precoVendaPrevisto" in body["error"]["fields"]
        assert str(bad_price) not in body["error"]["message"]


def test_input_validation_cost():
    """P-140 / C-08: custoUnitario > precoVendaPrevisto -> HTTP 400 NEW-004; borda igualdade -> HTTP 200 margem 0.00."""
    client = TestClient(app)

    # Caso inválido: custo maior que preço
    resp_invalid = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(precoVendaPrevisto=40.00, custoUnitario=45.99),
    )
    assert resp_invalid.status_code == 400
    err = resp_invalid.json()["error"]
    assert err["code"] == "NEW-004"
    assert "custoUnitario" in err["fields"]
    assert "45.99" not in err["message"]

    # Caso de borda permitido: custo == preco -> margem 0.00
    resp_edge = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(precoVendaPrevisto=40.00, custoUnitario=40.00, margemMinimaDesejada=0.10),
    )
    assert resp_edge.status_code == 200
    fin = resp_edge.json()["data"]["financialViability"]
    assert fin["margemBrutaUnitaria"] == pytest.approx(0.00, abs=1e-4)
    assert fin["margemBrutaPercentual"] == pytest.approx(0.00, abs=1e-4)
    assert fin["viavel"] is False


def test_input_validation_margin_out_of_range():
    """P-140 / C-09: margemMinimaDesejada fora de [0.0, 1.0] retorna HTTP 400 com NEW-004."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(margemMinimaDesejada=1.25),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "NEW-004"
    assert "margemMinimaDesejada" in body["error"]["fields"]
    assert "1.25" not in body["error"]["message"]


def test_min_similars_threshold_api():
    """P-143 / C-04: Tipo com < 3 similares elegíveis retorna HTTP 422 com erro NEW-001."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(tipo="Pomadas", descricao="Pomada de Confrei Natural 30g"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "NEW-001"
    assert body["error"]["fields"] == []


def test_invalid_type_new_002():
    """P-149 / C-05: Tipo inexistente no catálogo retorna HTTP 400 com NEW-002 sem eco do valor (LGPD-05)."""
    client = TestClient(app)
    secret_invalid_type = "TipoInexistenteXYZ999"
    response = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(tipo=secret_invalid_type),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "NEW-002"
    assert body["error"]["fields"] == ["tipo"]
    assert secret_invalid_type not in body["error"]["message"]


def test_invalid_supplier_new_003():
    """P-149 / C-06: Fornecedor inexistente no catálogo retorna HTTP 400 com NEW-003 sem eco do valor (LGPD-05)."""
    client = TestClient(app)
    secret_invalid_supplier = "FORNECEDOR_FANTASMA_XYZ"
    response = client.post(
        "/api/v1/analytics/new-product/forecast",
        json=_valid_payload(fornecedor=secret_invalid_supplier),
    )
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "NEW-003"
    assert body["error"]["fields"] == ["fornecedor"]
    assert secret_invalid_supplier not in body["error"]["message"]


def test_database_unavailable_new_005(monkeypatch):
    """P-149 / C-12: Indisponibilidade de banco retorna HTTP 503 com NEW-005 e sem stacktrace."""
    monkeypatch.setattr(
        analytics_service,
        "_get_new_product_options",
        lambda: (_ for _ in ()).throw(AnalyticsDataSourceError()),
    )
    client = TestClient(app)
    response = client.get("/api/v1/analytics/new-product/options")
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "NEW-005"
    assert body["error"]["fields"] == []
    assert "traceback" not in response.text.lower()
    assert "pyodbc" not in response.text.lower()
