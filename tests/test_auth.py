"""
Testes automatizados para Autenticação HTTP Basic em Produção (Regra P-033).
Valida que:
1. No ambiente local (AUTH_REQUIRED=false), nenhuma credencial é solicitada.
2. No ambiente de produção (AUTH_REQUIRED=true / ENVIRONMENT=production), credenciais válidas do .env são exigidas.
3. Tentativas sem autenticação ou com credenciais inválidas recebem HTTP 401 com cabeçalho WWW-Authenticate.
"""
import base64
import os
import pytest
from fastapi.testclient import TestClient

from src.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_auth_bypassed_in_local_environment(client, monkeypatch):
    """Garante que em ambiente de desenvolvimento local não há bloqueio ou pedido de login."""
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("ENVIRONMENT", "development")

    response = client.get("/api/v1/pricing/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_auth_enforced_in_production_unauthorized(client, monkeypatch):
    """Garante que em produção requisição sem cabeçalho Authorization recebe 401 com WWW-Authenticate."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_USERNAME", "testuser")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")

    response = client.get("/api/v1/pricing/health")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert 'Basic realm="Fitoherb Pricing Predictor"' in response.headers["WWW-Authenticate"]


def test_auth_enforced_in_production_wrong_credentials(client, monkeypatch):
    """Garante que em produção credenciais incorretas recebem 401."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_USERNAME", "testuser")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")

    wrong_auth = base64.b64encode(b"wronguser:wrongpass").decode("utf-8")
    response = client.get(
        "/api/v1/pricing/health",
        headers={"Authorization": f"Basic {wrong_auth}"}
    )
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_auth_enforced_in_production_success(client, monkeypatch):
    """Garante que em produção credenciais corretas são aceitas com 200 OK."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_USERNAME", "testuser")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")

    valid_auth = base64.b64encode(b"testuser:testpass").decode("utf-8")
    response = client.get(
        "/api/v1/pricing/health",
        headers={"Authorization": f"Basic {valid_auth}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_auth_options_preflight_always_allowed(client, monkeypatch):
    """Garante que requisições CORS OPTIONS passem sem 401 mesmo em produção."""
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("ENVIRONMENT", "production")

    response = client.options("/api/v1/pricing/predict")
    # OPTIONS não deve ser bloqueado com 401
    assert response.status_code != 401
