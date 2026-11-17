"""
Testes de integração da API REST de Churn de Clientes (P-117 a P-127).
Envelope data/meta, paginação, filtros e códigos semânticos CHU-001..003.
"""
from __future__ import annotations

from datetime import date
import pytest
from starlette.testclient import TestClient

from src.api import app
from src.modules.analytics.domain.churn import (
    ChurnCustomerSummary,
    MonthlyRevenuePoint,
)
from src.modules.analytics.service import analytics_cache


@pytest.fixture
def mock_churn_cache(monkeypatch):
    """Popula snapshot com dados sintéticos de churn para testes rápidos de API sem banco real."""
    ref_date = date(2026, 6, 1)

    customer_risk = ChurnCustomerSummary(
        customer_code=1042,
        status="EM_RISCO",
        dias_sem_comprar=74,
        gap_tipico=18.5,
        dias_referencia=60,
        fator_tempo=1.23,
        faturamento_medio_mensal=48250.0,
        score_prioridade=59347.5,
        historico_curto=False,
        data_ultimo_pedido=date(2026, 3, 19),
        variacao_trimestral_pct=-38.4,
        historico_mensal=(
            MonthlyRevenuePoint(year=2025, month=12, net_revenue=51200.0, order_count=3),
            MonthlyRevenuePoint(year=2026, month=1, net_revenue=49100.0, order_count=2),
        ),
        produtos_perdidos=(
            {
                "sku": 501,
                "descricao": "EXTRATO DE PROPOLIS VERDE 30ML",
                "fornecedor": "APIS FLORA",
                "faturamentoHistorico": 14200.0,
                "dataUltimaCompra": "2026-01-15",
            },
        ),
    )

    customer_alert = ChurnCustomerSummary(
        customer_code=2050,
        status="ALERTA",
        dias_sem_comprar=45,
        gap_tipico=15.0,
        dias_referencia=60,
        fator_tempo=0.75,
        faturamento_medio_mensal=20000.0,
        score_prioridade=15000.0,
        historico_curto=False,
        data_ultimo_pedido=date(2026, 4, 17),
        variacao_trimestral_pct=0.0,
        historico_mensal=(),
        produtos_perdidos=(),
    )

    customer_inactive = ChurnCustomerSummary(
        customer_code=9999,
        status="INATIVO_RECUPERACAO",
        dias_sem_comprar=210,
        gap_tipico=20.0,
        dias_referencia=60,
        fator_tempo=2.0,
        faturamento_medio_mensal=18000.0,
        score_prioridade=36000.0,
        historico_curto=False,
        data_ultimo_pedido=date(2025, 11, 3),
        variacao_trimestral_pct=0.0,
        historico_mensal=(),
        produtos_perdidos=(),
    )

    all_customers = [customer_risk, customer_alert, customer_inactive]

    monkeypatch.setattr(analytics_cache, "get_churn_customers_list", lambda status=None: [
        c for c in all_customers if status is None or c.status == status or status == "TODOS"
    ])
    monkeypatch.setattr(analytics_cache, "get_customer_churn_detail", lambda code: (
        customer_risk if code == 1042 else None
    ))
    monkeypatch.setattr(analytics_cache, "get_inactive_churn_list", lambda: [customer_inactive])
    monkeypatch.setattr(analytics_cache, "get_churn_summary_stats", lambda: {
        "totalEmRisco": 1,
        "totalAlerta": 1,
        "totalSaudavel": 0,
        "totalInativos": 1,
        "receitaMensalEmRisco": 48250.0,
    })


def test_get_churn_customers_api(mock_churn_cache):
    """GET /analytics/churn/customers: retorna envelope data/meta paginado com resumo."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/churn/customers?status=EM_RISCO&limit=10&offset=0")
    assert response.status_code == 200
    json_data = response.json()

    assert "data" in json_data
    assert "meta" in json_data
    assert json_data["meta"]["limit"] == 10
    assert json_data["meta"]["offset"] == 0
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["customerCode"] == 1042
    assert json_data["data"]["items"][0]["status"] == "EM_RISCO"
    assert json_data["data"]["resumo"]["totalEmRisco"] == 1
    assert json_data["data"]["resumo"]["receitaMensalEmRisco"] == 48250.0


def test_get_customer_churn_detail_api(mock_churn_cache):
    """GET /analytics/churn/customers/{customerCode}: retorna detalhamento explicativo."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/churn/customers/1042")
    assert response.status_code == 200
    json_data = response.json()

    assert json_data["data"]["customerCode"] == 1042
    assert json_data["data"]["diasSemComprar"] == 74
    assert json_data["data"]["variacaoReceitaTrimestralPct"] == -38.4
    assert len(json_data["data"]["produtosPerdidos"]) == 1
    assert json_data["data"]["produtosPerdidos"][0]["sku"] == 501


def test_get_customer_churn_not_found(mock_churn_cache):
    """GET /analytics/churn/customers/{customerCode}: 404 CHU-001 se inexistente."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/churn/customers/8888")
    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error"]["code"] == "CHU-001"


def test_get_churn_inactive_api(mock_churn_cache):
    """GET /analytics/churn/inactive: retorna clientes inativos antigos (>180d)."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/churn/inactive")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["totalInativos"] == 1
    assert json_data["data"]["items"][0]["customerCode"] == 9999
    assert json_data["data"]["items"][0]["diasSemComprar"] == 210


def test_privacy_no_pii_in_churn_responses(mock_churn_cache):
    """Requisito LGPD-CHU-01: Proibição de PII direta nos contratos da API de Churn."""
    client = TestClient(app)
    response = client.get("/api/v1/analytics/churn/customers/1042")
    assert response.status_code == 200
    data_str = response.text.lower()
    for forbidden in ["nome", "razaosocial", "cnpj", "cpf", "email", "telefone"]:
        assert f'"{forbidden}"' not in data_str
