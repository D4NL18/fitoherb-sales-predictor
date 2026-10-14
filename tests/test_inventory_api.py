"""
Testes de integração para a API de Estoque e Compras (Inventory & Replenishment AI).
Valida endpoints /health, /config, /suppliers, /predict e /export-csv (P-012).
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import app
import src.modules.inventory.service.inventory_service as inv_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_inventory_data(monkeypatch):
    """Injeta dados sintéticos em memória para testes rápidos de API sem depender do banco."""
    catalog_df = pd.DataFrame([
        {
            "Codigo": 101,
            "Descricao": "EXTRATO PROPOLIS APISFLORA",
            "EAN": "7891234567890",
            "Fornecedor": "APIS FLORA",
            "Tipo": "EXTRATOS",
            "Estoque": 5.0,
            "Pc.Ultimo Custo": 15.0,
            "Pc.Venda": 25.0
        },
        {
            "Codigo": 102,
            "Descricao": "VITAMINA C HERBARIUM",
            "EAN": "7899876543210",
            "Fornecedor": "HERBARIUM",
            "Tipo": "VITAMINAS",
            "Estoque": 50.0,
            "Pc.Ultimo Custo": 10.0,
            "Pc.Venda": 20.0
        }
    ])
    
    dates = pd.date_range(end="2026-09-30", periods=60, freq="D")
    sales_data = []
    for d in dates:
        sales_data.append({"Data": d, "Cod Produto": 101, "Qtd Venda": 2.0, "Valor Venda": 50.0})
        sales_data.append({"Data": d, "Cod Produto": 102, "Qtd Venda": 1.0, "Valor Venda": 20.0})
    sales_df = pd.DataFrame(sales_data)

    monkeypatch.setattr(inv_service, "get_base_inventory_data", lambda: (catalog_df, sales_df))
    # Limpa cache de velocidade
    inv_service._VELOCITY_CACHE.clear()


def test_inventory_health_check(client):
    response = client.get("/api/v1/inventory/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_inventory_config(client):
    response = client.get("/api/v1/inventory/config")
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert "historyWindowDays" in json_data["data"]
    assert "leadTimeDays" in json_data["data"]
    assert "targetCoverageDays" in json_data["data"]
    assert "serviceLevel" in json_data["data"]
    assert "meta" in json_data


def test_inventory_suppliers(client):
    response = client.get("/api/v1/inventory/suppliers")
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    suppliers = [s["fornecedor"] for s in json_data["data"]]
    assert "TODOS" in suppliers
    assert "APIS FLORA" in suppliers
    assert "HERBARIUM" in suppliers


def test_inventory_predict_success(client):
    payload = {
        "historyWindowDays": 60,
        "leadTimeDays": 15,
        "targetCoverageDays": 30,
        "serviceLevel": 0.95,
        "fornecedor": None,
        "budgetLimit": None
    }
    response = client.post("/api/v1/inventory/predict", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    data = json_data["data"]
    assert "kpis" in data
    assert "produtos" in data
    assert data["kpis"]["totalSkusAnalisados"] == 2
    assert len(data["produtos"]) == 2
    
    # Produto 101 tem estoque 5 e VMD 2 (cobertura 2.5 dias < 15) -> Ruptura iminente
    p101 = next(p for p in data["produtos"] if p["codigo"] == 101)
    assert p101["status"] == "CRITICAL_STOCKOUT"
    assert p101["qtdSugeridaCompra"] > 0
    assert p101["investimentoTotalItem"] > 0


def test_inventory_predict_supplier_filter(client):
    payload = {
        "historyWindowDays": 60,
        "leadTimeDays": 15,
        "targetCoverageDays": 30,
        "serviceLevel": 0.95,
        "fornecedor": "APIS FLORA"
    }
    response = client.post("/api/v1/inventory/predict", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    produtos = json_data["data"]["produtos"]
    assert len(produtos) == 1
    assert produtos[0]["fornecedor"] == "APIS FLORA"


def test_inventory_export_csv(client):
    payload = {
        "historyWindowDays": 60,
        "leadTimeDays": 15,
        "targetCoverageDays": 30,
        "serviceLevel": 0.95
    }
    response = client.post("/api/v1/inventory/export-csv", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "fitoherb_plano_compras" in response.headers.get("content-disposition", "")
    content = response.text
    assert "Código;" in content or "Código" in content
    assert "EXTRATO PROPOLIS APISFLORA" in content


def test_inventory_predict_with_variation_limit(client):
    payload = {
        "historyWindowDays": 60,
        "leadTimeDays": 15,
        "targetCoverageDays": 30,
        "serviceLevel": 0.95,
        "maxPurchaseVariationPct": 100.0
    }
    response = client.post("/api/v1/inventory/predict", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    data = json_data["data"]
    assert "skusLimitadosPorEspaco" in data["kpis"]
    # Produto 101 tem estoque 5, VMD 2, ideal 90, teórica 85. Com teto 100%, é limitado
    p101 = next(p for p in data["produtos"] if p["codigo"] == 101)
    assert p101["limitadoPorEspaco"] is True
    assert p101["qtdSugeridaCompra"] < p101["qtdSugeridaTeorica"]

