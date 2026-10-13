"""
Testes de integração para a API RESTful FastAPI (US-07, P-011, P-012).
"""
import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Testa endpoint de health check."""
    response = client.get("/api/v1/pricing/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "healthy"


def test_get_config(client):
    """Testa obtenção dos valores padrão e limites dos hiperparâmetros."""
    response = client.get("/api/v1/pricing/config")
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert "kRatio" in json_data["data"]
    assert json_data["data"]["kRatio"]["default"] == 0.25
    assert json_data["data"]["topAnchors"]["default"] == 15


def test_predict_endpoint_success(client):
    """Testa execução do pipeline via POST /api/v1/pricing/predict."""
    payload = {
        "kRatio": 0.25,
        "topAnchors": 5,
        "halfLifeDays": 100.0,
        "anchorMinDiscount": -0.15,
        "anchorMaxDiscount": -0.05,
        "compMaxIncrease": 0.06,
        "stressDrop": 0.05
    }
    response = client.post("/api/v1/pricing/predict", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert "summary" in json_data["data"]
    assert "previewProducts" in json_data["data"]
    assert "projectedRevenue" in json_data["data"]["summary"]
    assert "marginProtected" in json_data["data"]["summary"]


def test_predict_validation_error(client):
    """Testa regra P-011: Validação de borda contra parâmetros absurdos."""
    payload = {
        "kRatio": 0.95,  # k_ratio > 0.50 deve falhar na validação Pydantic
        "topAnchors": 15
    }
    response = client.post("/api/v1/pricing/predict", json=payload)
    assert response.status_code == 422


def test_export_csv_endpoint(client):
    """Testa download de CSV via POST /api/v1/pricing/export com UTF-8 BOM e delimitador ';' (P-018)."""
    payload = {
        "kRatio": 0.25,
        "variableKRatio": True,
        "topAnchors": 5,
        "halfLifeDays": 100.0
    }
    response = client.post("/api/v1/pricing/export", json=payload)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment" in response.headers["content-disposition"]
    # Regra P-018: Primeiros 3 bytes devem ser exatamente o BOM UTF-8 (\xef\xbb\xbf)
    assert response.content.startswith(b"\xef\xbb\xbf")
    decoded_text = response.content.decode("utf-8-sig")
    assert "Codigo;Descricao" in decoded_text
    assert "Trava_K_Percentual" in decoded_text
    assert ";" in decoded_text


def test_predict_variable_k_ratio(client):
    """Testa regra P-017: Trava comercial individual por âncora no predict."""
    payload = {
        "kRatio": 0.25,
        "variableKRatio": True,
        "topAnchors": 5
    }
    response = client.post("/api/v1/pricing/predict", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    summary = json_data["data"]["summary"]
    assert summary["variableKRatioApplied"] is True
    assert summary["minKRatio"] is not None
    assert summary["maxKRatio"] is not None
    assert summary["minKRatio"] <= summary["maxKRatio"]
    previews = json_data["data"]["previewProducts"]
    assert len(previews) > 0
    # Verifica se pelo menos um produto âncora possui trava individual preenchida
    anchor_previews = [p for p in previews if "ÂNCORA" in p.get("papelEstrategico", "")]
    if anchor_previews:
        assert anchor_previews[0]["travaKPercentual"] is not None
        assert 0.08 <= anchor_previews[0]["travaKPercentual"] <= 0.45


def test_auto_tune_endpoint(client):
    """Testa endpoint de auto-tuning evolutivo via POST /api/v1/pricing/auto-tune (US-09)."""
    payload = {
        "strategy": "balanced",
        "populationSize": 4,
        "generations": 2
    }
    response = client.post("/api/v1/pricing/auto-tune", json=payload)
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert json_data["data"]["strategy"] == "balanced"
    assert "optimalParams" in json_data["data"]
    assert "kRatio" in json_data["data"]["optimalParams"]
    assert "projectedMetrics" in json_data["data"]


def test_auto_tune_invalid_strategy(client):
    """Testa rejeição de estratégia inválida."""
    payload = {"strategy": "invalid_strat"}
    response = client.post("/api/v1/pricing/auto-tune", json=payload)
    assert response.status_code == 422


def test_db_status_endpoint(client):
    """Testa endpoint de status da conexão ao banco SQL Server (P-022)."""
    response = client.get("/api/v1/pricing/db-status")
    assert response.status_code == 200
    json_data = response.json()
    assert "data" in json_data
    assert "connected" in json_data["data"]
    assert "latencyMs" in json_data["data"]
    assert "activeDataSource" in json_data["data"]

