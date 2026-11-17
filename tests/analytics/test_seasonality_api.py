"""
Testes de API para as Rotas de Sazonalidade por Produto (contrato 1.0.0; P-106 a P-116).

Testa:
- GET /api/v1/analytics/seasonality/{sku} (200, 404 SEA-001, 400 SEA-002).
- GET /api/v1/analytics/seasonality/ranking?order=most|least (200, 400 SEA-002).
- Envelope de resposta padronizado { data: ..., meta: ... }.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.api.schemas import ANALYTICS_CONTRACT_VERSION
from src.modules.analytics.service import analytics_cache, analytics_service
from tests.analytics.test_seasonality_domain import _build_synthetic_monthly_sales


@pytest.fixture(autouse=True)
def _setup_seasonality_cache(monkeypatch):
    """Configura snapshot simulado no cache para testes de API de sazonalidade."""
    sku_valido = 1042
    df_valido = _build_synthetic_monthly_sales(
        sku=sku_valido,
        start_year=2025,
        start_month=1,
        months_count=22,
        base_qty=100.0,
        peak_month=3,
        peak_factor=1.8,
    )
    df_curto = _build_synthetic_monthly_sales(
        sku=2050,
        start_year=2026,
        start_month=1,
        months_count=8,
        base_qty=50.0,
    )
    combined_sales = pd_concat = __import__("pandas").concat([df_valido, df_curto], ignore_index=True)

    catalog = {
        sku_valido: {
            "Codigo": sku_valido,
            "Descricao": "EXTRATO DE PROPOLIS 30ML",
            "Fornecedor": "APIS FLORA",
            "Estoque": 120,
            "Pc.Ultimo Custo": 15.0,
            "Pc.Venda": 28.50,
        },
        2050: {
            "Codigo": 2050,
            "Descricao": "PRODUTO NOVO 8 MESES",
            "Fornecedor": "HERBARIUM",
            "Estoque": 10,
            "Pc.Ultimo Custo": 10.0,
            "Pc.Venda": 20.0,
        },
    }

    # Injeta os dados mockados no cache ou service
    monkeypatch.setattr(analytics_service, "_get_monthly_sales_df", lambda: combined_sales)
    monkeypatch.setattr(analytics_service, "_get_catalog_dict", lambda: catalog)


def test_get_seasonality_by_sku_success():
    """GET /api/v1/analytics/seasonality/1042 -> 200 OK com envelope e dados de sazonalidade."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/1042")
    assert response.status_code == 200

    payload = response.json()
    assert "data" in payload
    assert "meta" in payload
    assert payload["meta"]["version"] == ANALYTICS_CONTRACT_VERSION

    data = payload["data"]
    assert data["produto"]["codigo"] == 1042
    assert data["produto"]["descricao"] == "EXTRATO DE PROPOLIS 30ML"
    assert data["elegivel"] is True
    assert data["forca"] == "FORTE"
    assert data["pico"]["mesInicio"] == 3
    assert data["pico"]["confianca"] == "ALTA"
    assert len(data["serieMensal"]) == 12


def test_get_seasonality_by_sku_not_found():
    """GET /api/v1/analytics/seasonality/999999 -> 404 Not Found com SEA-001."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/999999")
    assert response.status_code == 404

    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "SEA-001"
    assert "não encontrado" in payload["error"]["message"].lower()


def test_get_seasonality_by_sku_invalid_parameter():
    """GET /api/v1/analytics/seasonality/0 ou negativo -> 400 Bad Request com SEA-002."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/0")
    assert response.status_code == 400

    payload = response.json()
    assert payload["error"]["code"] == "SEA-002"
    assert "sku" in payload["error"]["fields"]


def test_get_seasonality_ranking_most_success():
    """GET /api/v1/analytics/seasonality/ranking?order=most -> 200 OK paginado."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/ranking?order=most&limit=10&offset=0")
    assert response.status_code == 200

    payload = response.json()
    assert "data" in payload
    assert "meta" in payload
    assert payload["meta"]["limit"] == 10
    assert payload["meta"]["page"] == 1
    assert isinstance(payload["data"], list)
    if payload["data"]:
        item = payload["data"][0]
        assert "sku" in item
        assert "forca" in item
        assert "amplitude" in item
        assert "mesPico" in item
        assert "mesVale" in item


def test_get_seasonality_ranking_least_success():
    """GET /api/v1/analytics/seasonality/ranking?order=least -> 200 OK com pouco mensuráveis."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/ranking?order=least&limit=10&offset=0")
    assert response.status_code == 200

    payload = response.json()
    data = payload["data"]
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert item["forca"] == "INSUFICIENTE"
        assert item["motivoInsuficiencia"] in ("HISTORICO_CURTO", "VENDA_ESPORADICA")


def test_get_seasonality_ranking_invalid_order():
    """GET /api/v1/analytics/seasonality/ranking?order=xyz -> 400 Bad Request com SEA-002."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/seasonality/ranking?order=xyz")
    assert response.status_code == 400

    payload = response.json()
    assert payload["error"]["code"] == "SEA-002"
    assert "order" in payload["error"]["fields"]
