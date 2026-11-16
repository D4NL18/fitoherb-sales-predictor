"""
Testes de privacidade e conformidade LGPD da Tendência de Vendas (T-11).
Valida regras P-085, CA-26, CA-40, ADR-003 DA-02.
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from src.api import app
from tests.sales_trend.test_sales_trend_api import _setup_mock_snapshot

client = TestClient(app)


def test_no_customer_data_in_api_response():
    """Valida que nenhuma resposta expõe dados de cliente (Cod Cliente, Cliente, Cidade, UF, Pedido)."""
    snap = _setup_mock_snapshot()
    with patch("src.modules.sales_trend.service.sales_trend_service.get_snapshot", return_value=snap):
        resp = client.get("/api/v1/sales-trend?baseMonth=2026-10")
        assert resp.status_code == 200
        text = resp.text.lower()

        forbidden_keys = [
            "cod_cliente",
            "codcliente",
            "customercode",
            "cliente",
            "pedido",
            "order",
            "cpf",
            "cnpj",
        ]
        for key in forbidden_keys:
            assert f'"{key}"' not in text, f"Chave proibida {key} encontrada na resposta da API"


def test_logs_do_not_contain_payloads_or_customer_pii(caplog):
    """Valida que logs registram apenas contagens e durações, sem payloads de dados."""
    import logging
    snap = _setup_mock_snapshot()

    with caplog.at_level(logging.INFO):
        with patch("src.modules.sales_trend.service.sales_trend_service.get_snapshot", return_value=snap):
            client.get("/api/v1/sales-trend?baseMonth=2026-10")

    log_text = caplog.text.lower()
    assert "cod cliente" not in log_text
    assert "pedido" not in log_text
