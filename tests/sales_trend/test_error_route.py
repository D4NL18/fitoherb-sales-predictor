"""
Testes para tratamento centralizado de erros via TrendAPIRoute e regressão (T-09).
Valida regras P-082, CA-19, C-07, C-08, C-24..C-26, C-47, C-48, ADR-003 DA-09.
"""
from fastapi.testclient import TestClient
import pytest

from src.api import app

client = TestClient(app)


def test_invalid_query_parameters_returns_tnd001_400():
    """Valida que parâmetros inválidos devolvem 400 com código TND-001 e lista fields sem ecoar valores."""
    # Query inválida: limit=0 e metric=invalida
    response = client.get("/api/v1/sales-trend?limit=0&metric=invalida")
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TND-001"
    assert "limit" in data["error"]["fields"] or "metric" in data["error"]["fields"]
    assert "meta" in data


def test_regression_pricing_retains_default_422():
    """Valida regressão: erro de validação em pricing continua devolvendo 422 padrão sem handlers globais."""
    response = client.post("/api/v1/pricing/predict", json={"kRatio": "invalido"})
    assert response.status_code == 422


def test_supplier_products_missing_key_returns_400():
    """Valida que rota de detalhe sem supplierKey devolve 400 TND-001."""
    response = client.get("/api/v1/sales-trend/supplier-products")
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "TND-001"
    assert "supplierKey" in data["error"]["fields"]
