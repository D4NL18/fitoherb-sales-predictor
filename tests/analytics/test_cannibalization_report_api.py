"""
Testes de Contrato REST e Repositório SQL (TDD First — v2):
Relatório de Canibalização por Migração de Clientes e Equilíbrio de Preço (Fase F6 v2).

Regras cobertas: P-128 a P-138; ADR-007 (v2); Contrato `analytics-canibalizacao.md` v1.1.0; LGPD-CAN-01..06.

Interface de Serviço / Repositório v2 esperada:
- `src.modules.analytics.service.analytics_service`:
  - `get_cannibalization_report(window_days=90, min_drop_pct=5.0, min_migrated_clients=3, category=None, supplier=None, mechanism=None, search=None)`
  - `get_cannibalization_sku_detail(sku, window_days=90, min_drop_pct=5.0, min_migrated_clients=3)`
- `src.modules.analytics.repository.sales_repository`:
  - `_CUSTOMER_SKU_WINDOW_SALES_SQL` (subquery iniciando com `SELECT`, sem `WITH`, sem `CONCAT`, bind params `?`)
  - `fetch_customer_sku_window_sales(pre_start_date, mid_date, reference_date)` (via `fetchmany`)
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.core.database import is_readonly_query
from src.modules.analytics.domain.exceptions import (
    CannibalizationInsufficientHistoryError,
    CannibalizationInvalidParametersError,
    CannibalizationProcessingError,
    CannibalizationProductNotFoundError,
)
from src.modules.analytics.repository.errors import AnalyticsDataSourceError

client = TestClient(app, raise_server_exceptions=False)

REPORT_URL = "/api/v1/analytics/cannibalization/report"


# ---------------------------------------------------------------------------
# Payloads sintéticos aderentes ao contrato v1.1.0 (camelCase)
# ---------------------------------------------------------------------------


def _fake_report_payload(window_days: int = 90) -> Dict[str, Any]:
    return {
        "data": {
            "kpis": {
                "totalVictims": 1,
                "totalCannibalizedRevenue": 4420.50,
                "avgCannibalizedRevenuePct": 24.02,
                "totalNetMarginImpact": -338.10,
                "marginDestroyingPairsCount": 2,
            },
            "availableCategories": ["CAPSULAS", "CHAS", "EXTRATOS"],
            "availableSuppliers": ["FITOHERB", "HERBARIUM"],
            "victims": [
                {
                    "sku": "100235",
                    "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
                    "category": "EXTRATOS",
                    "supplier": "FITOHERB",
                    "preRevenue": 18400.00,
                    "curRevenue": 12100.00,
                    "revenueDrop": 6300.00,
                    "revenueDropPct": 34.24,
                    "cannibalizedRevenue": 4420.50,
                    "cannibalizedRevenuePct": 24.02,
                    "dropExplainedPct": 70.17,
                    "currentPrice": 30.00,
                    "unitCost": 16.00,
                    "unitMargin": 14.00,
                    "marginPct": 46.67,
                    "costFallbackUsed": False,
                    "currentStock": 185,
                    "cannibalizerCount": 1,
                    "netMarginImpact": -255.39,
                    "topCannibal": {
                        "sku": "100234",
                        "description": "EXTRATO DE PROPOLIS VERDE 30ML",
                        "migratedClients": 11,
                        "migratedRevenue": 3180.50,
                        "shareOfCannibalizationPct": 100.0,
                        "currentPrice": 22.00,
                        "unitMargin": 8.50,
                        "marginPct": 38.64,
                        "costFallbackUsed": False,
                        "priceGapPct": 36.36,
                        "netMarginImpact": -255.39,
                        "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
                        "suggestedVictimPrice": 28.40,
                        "suggestedCannibalPrice": 23.60,
                        "projectedPriceGapPct": 20.34,
                        "actionSummary": (
                            "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador "
                            "para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
                        ),
                    },
                    "cannibalizers": [
                        {
                            "sku": "100234",
                            "description": "EXTRATO DE PROPOLIS VERDE 30ML",
                            "migratedClients": 11,
                            "migratedRevenue": 3180.50,
                            "shareOfCannibalizationPct": 100.0,
                            "currentPrice": 22.00,
                            "unitMargin": 8.50,
                            "marginPct": 38.64,
                            "costFallbackUsed": False,
                            "priceGapPct": 36.36,
                            "netMarginImpact": -255.39,
                            "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
                            "suggestedVictimPrice": 28.40,
                            "suggestedCannibalPrice": 23.60,
                            "projectedPriceGapPct": 20.34,
                            "actionSummary": (
                                "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador "
                                "para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
                            ),
                        }
                    ],
                }
            ],
        },
        "meta": {
            "timestamp": "2026-11-23T19:00:00Z",
            "version": "1.1.0",
            "dataReferencia": "2026-11-23",
            "windowDays": window_days,
            "minDropPct": 5.0,
            "minMigratedClients": 3,
            "prePeriod": {"startDate": "2026-05-27", "endDate": "2026-08-24"},
            "curPeriod": {"startDate": "2026-08-25", "endDate": "2026-11-22"},
            "totalFound": 1,
            "executionTimeMs": 42,
        },
    }


def _fake_detail_payload(sku: str = "100235", is_cannibalized: bool = True) -> Dict[str, Any]:
    cannibalizers = (
        [
            {
                "sku": "100234",
                "description": "EXTRATO DE PROPOLIS VERDE 30ML",
                "category": "EXTRATOS",
                "supplier": "FITOHERB",
                "migratedClients": 11,
                "grossClientsToCannibal": 13,
                "reverseClientsToVictim": 2,
                "migratedRevenue": 3180.50,
                "shareOfCannibalizationPct": 100.0,
                "preRevenue": 9200.00,
                "curRevenue": 14800.00,
                "currentPrice": 22.00,
                "unitCost": 13.50,
                "unitMargin": 8.50,
                "marginPct": 38.64,
                "costFallbackUsed": False,
                "currentStock": 340,
                "priceGapPct": 36.36,
                "netMarginImpact": -255.39,
                "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
                "suggestedVictimPrice": 28.40,
                "suggestedCannibalPrice": 23.60,
                "projectedPriceGapPct": 20.34,
                "victimMarginFloorPrice": 20.00,
                "actionSummary": (
                    "Reduzir vítima para R$ 28,40 (-5,3%) e reajustar canibalizador "
                    "para R$ 23,60 (+7,3%) para fechar o gap de 36,4% para 20,3%."
                ),
            }
        ]
        if is_cannibalized
        else []
    )
    return {
        "data": {
            "isCannibalized": is_cannibalized,
            "victim": {
                "sku": sku,
                "description": "EXTRATO DE PROPOLIS AQUOSO 30ML",
                "category": "EXTRATOS",
                "supplier": "FITOHERB",
                "preRevenue": 18400.00,
                "curRevenue": 12100.00 if is_cannibalized else 19200.00,
                "revenueDrop": 6300.00 if is_cannibalized else 0.0,
                "revenueDropPct": 34.24 if is_cannibalized else 0.0,
                "cannibalizedRevenue": 3180.50 if is_cannibalized else 0.0,
                "cannibalizedRevenuePct": 17.29 if is_cannibalized else 0.0,
                "dropExplainedPct": 50.48 if is_cannibalized else 0.0,
                "currentPrice": 30.00,
                "unitCost": 16.00,
                "unitMargin": 14.00,
                "marginPct": 46.67,
                "costFallbackUsed": False,
                "currentStock": 185,
                "cannibalizerCount": 1 if is_cannibalized else 0,
                "netMarginImpact": -255.39 if is_cannibalized else 0.0,
            },
            "cannibalizers": cannibalizers,
        },
        "meta": {
            "timestamp": "2026-11-23T19:00:00Z",
            "version": "1.1.0",
            "dataReferencia": "2026-11-23",
            "sku": sku,
            "windowDays": 90,
            "prePeriod": {"startDate": "2026-05-27", "endDate": "2026-08-24"},
            "curPeriod": {"startDate": "2026-08-25", "endDate": "2026-11-22"},
            "executionTimeMs": 12,
        },
    }


def _collect_all_keys(obj: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k))
            keys.extend(_collect_all_keys(v))
    elif isinstance(obj, list):
        for item in obj:
            keys.extend(_collect_all_keys(item))
    return keys


# ---------------------------------------------------------------------------
# 1. GET /api/v1/analytics/cannibalization/report
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window_days", [30, 60, 90])
def test_get_report_success_envelope_v1_1_0_and_camel_case(window_days: int):
    """T-CAN-RPT-API-01: Retorna 200 com envelope data/meta v1.1.0 em camelCase para windowDays 30/60/90."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_report",
        create=True,
    ) as mock_svc:
        mock_svc.return_value = _fake_report_payload(window_days=window_days)

        # Act
        response = client.get(REPORT_URL, params={"windowDays": window_days})

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "meta" in body
    assert body["meta"]["version"] == "1.1.0"
    assert body["meta"]["windowDays"] == window_days
    assert "prePeriod" in body["meta"] and "curPeriod" in body["meta"]
    assert "kpis" in body["data"]
    assert "availableCategories" in body["data"]
    assert "availableSuppliers" in body["data"]
    assert len(body["data"]["victims"]) == 1
    assert body["data"]["victims"][0]["topCannibal"]["mechanism"] == "PRECO_MENOR_DESTROI_MARGEM"
    # Rigor camelCase: nenhuma chave com underscore
    all_keys = _collect_all_keys(body)
    assert all("_" not in k for k in all_keys), f"Chaves fora de camelCase: {[k for k in all_keys if '_' in k]}"
    # LGPD-CAN-02: zero Cod Cliente
    raw = json.dumps(body).lower()
    assert "customercode" not in raw and "cod cliente" not in raw


def test_get_report_forwards_all_query_filters():
    """T-CAN-RPT-API-02: Repassa filtros category, supplier, mechanism, search, minDropPct e minMigratedClients."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_report",
        create=True,
    ) as mock_svc:
        mock_svc.return_value = _fake_report_payload(window_days=60)

        # Act
        response = client.get(
            REPORT_URL,
            params={
                "windowDays": 60,
                "minDropPct": 10.0,
                "minMigratedClients": 5,
                "category": "EXTRATOS",
                "supplier": "FITOHERB",
                "mechanism": "PRECO_MENOR_DESTROI_MARGEM",
                "search": "PROPOLIS",
            },
        )

    # Assert
    assert response.status_code == 200
    assert mock_svc.called
    kwargs = mock_svc.call_args.kwargs
    assert kwargs.get("window_days") == 60
    assert kwargs.get("min_drop_pct") == pytest.approx(10.0)
    assert kwargs.get("min_migrated_clients") == 5
    assert kwargs.get("category") == "EXTRATOS"
    assert kwargs.get("supplier") == "FITOHERB"
    assert kwargs.get("mechanism") == "PRECO_MENOR_DESTROI_MARGEM"
    assert kwargs.get("search") == "PROPOLIS"


# ---------------------------------------------------------------------------
# 2. GET /api/v1/analytics/cannibalization/report/{sku}
# ---------------------------------------------------------------------------


def test_get_report_sku_detail_cannibalized_returns_price_equilibrium_block():
    """T-CAN-RPT-API-03: Detalhe /report/{sku} retorna isCannibalized=True, victim e cannibalizers com equilíbrio de preço."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_sku_detail",
        create=True,
    ) as mock_svc:
        mock_svc.return_value = _fake_detail_payload(sku="100235", is_cannibalized=True)

        # Act
        response = client.get(f"{REPORT_URL}/100235", params={"windowDays": 90})

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["version"] == "1.1.0"
    assert body["meta"]["sku"] == "100235"
    assert body["data"]["isCannibalized"] is True
    assert body["data"]["victim"]["sku"] == "100235"
    cann = body["data"]["cannibalizers"][0]
    assert cann["suggestedVictimPrice"] == pytest.approx(28.40)
    assert cann["suggestedCannibalPrice"] == pytest.approx(23.60)
    assert cann["projectedPriceGapPct"] == pytest.approx(20.34)
    assert cann["victimMarginFloorPrice"] == pytest.approx(20.00)
    assert cann["mechanism"] == "PRECO_MENOR_DESTROI_MARGEM"
    assert cann["actionSummary"]
    assert all("_" not in k for k in _collect_all_keys(body))


def test_get_report_sku_detail_not_cannibalized_returns_200_empty_list():
    """T-CAN-RPT-API-04 (C-07): SKU ativo sem canibalização retorna 200 com isCannibalized=False e cannibalizers=[]."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_sku_detail",
        create=True,
    ) as mock_svc:
        mock_svc.return_value = _fake_detail_payload(sku="200100", is_cannibalized=False)

        # Act
        response = client.get(f"{REPORT_URL}/200100")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["isCannibalized"] is False
    assert body["data"]["cannibalizers"] == []
    assert body["data"]["victim"]["cannibalizedRevenue"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. Códigos de Erro Semânticos e LGPD-CAN-06 (CAN-001, 003, 004, 005, ANL-001)
# ---------------------------------------------------------------------------


def test_get_report_sku_not_found_returns_404_can_001():
    """T-CAN-RPT-API-05 (C-06): SKU inexistente retorna 404 CAN-001."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_sku_detail",
        create=True,
    ) as mock_svc:
        mock_svc.side_effect = CannibalizationProductNotFoundError()

        # Act
        response = client.get(f"{REPORT_URL}/999999")

    # Assert
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "CAN-001"
    assert body["meta"]["version"] == "1.1.0"


def test_get_report_insufficient_history_returns_422_can_003():
    """T-CAN-RPT-API-06 (C-08): Histórico insuficiente retorna 422 CAN-003."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_report",
        create=True,
    ) as mock_svc:
        mock_svc.side_effect = CannibalizationInsufficientHistoryError()

        # Act
        response = client.get(REPORT_URL)

    # Assert
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "CAN-003"


@pytest.mark.parametrize(
    "url,params,forbidden_echo,expected_field",
    [
        (REPORT_URL, {"windowDays": 45}, "45", "windowDays"),
        (REPORT_URL, {"minDropPct": 99.5}, "99.5", "minDropPct"),
        (REPORT_URL, {"minMigratedClients": 0}, "0", "minMigratedClients"),
        (REPORT_URL, {"mechanism": "MECANISMO_INVALIDO_XYZ"}, "MECANISMO_INVALIDO_XYZ", "mechanism"),
        (f"{REPORT_URL}/sku_invalido_999", {}, "sku_invalido_999", "sku"),
    ],
)
def test_invalid_parameters_return_400_can_004_without_echoing_input(
    url: str,
    params: Dict[str, Any],
    forbidden_echo: str,
    expected_field: str,
):
    """T-CAN-RPT-API-07 (C-05 / LGPD-CAN-06): Parâmetros inválidos retornam 400 CAN-004 sem ecoar o valor bruto."""
    # Arrange / Act
    response = client.get(url, params=params)

    # Assert
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "CAN-004"
    assert expected_field in body["error"]["fields"]
    assert forbidden_echo not in body["error"]["message"]
    assert forbidden_echo not in json.dumps(body["error"].get("details"))


def test_processing_error_returns_500_can_005_without_stacktrace():
    """T-CAN-RPT-API-08: Erro interno de processamento retorna 500 CAN-005 sem stacktrace."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_report",
        create=True,
    ) as mock_svc:
        mock_svc.side_effect = CannibalizationProcessingError()

        # Act
        response = client.get(REPORT_URL)

    # Assert
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "CAN-005"
    raw = json.dumps(body)
    assert "Traceback" not in raw and "File \"" not in raw


def test_database_unavailable_returns_503_anl_001_without_driver_details():
    """T-CAN-RPT-API-09 (C-09): Indisponibilidade do SQL Server retorna 503 ANL-001 sanitizado."""
    # Arrange
    with patch(
        "src.modules.analytics.service.analytics_service.get_cannibalization_report",
        create=True,
    ) as mock_svc:
        mock_svc.side_effect = AnalyticsDataSourceError()

        # Act
        response = client.get(REPORT_URL)

    # Assert
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "ANL-001"
    raw = json.dumps(body).lower()
    assert "pyodbc" not in raw and "odbc" not in raw


# ---------------------------------------------------------------------------
# 4. Validação da SQL no Repositório (P-137.1, ADR-007 DA-03, LGPD-CAN-01)
# ---------------------------------------------------------------------------


def test_repository_window_sales_sql_starts_with_select_readonly_no_with_no_concat():
    """
    T-CAN-RPT-SQL-01 (P-137.1 / ADR-007 DA-03):
    A SQL de `fetch_customer_sku_window_sales` deve:
    - iniciar com SELECT (proibido WITH CTE);
    - passar por `is_readonly_query(sql) == True`;
    - não usar CONCAT;
    - abater devoluções (`LIKE 'DEVOLU%'`);
    - usar bind parameters `?` para datas.
    """
    # Arrange
    from src.modules.analytics.repository import sales_repository

    sql = sales_repository._CUSTOMER_SKU_WINDOW_SALES_SQL
    sql_stripped = sql.strip()
    sql_upper = sql_stripped.upper()

    # Act
    readonly_ok = is_readonly_query(sql_stripped)

    # Assert
    assert sql_upper.startswith("SELECT"), "SQL deve iniciar com SELECT (proibido WITH CTE)"
    assert readonly_ok is True, "SQL rejeitada por is_readonly_query"
    assert not re.search(r"\bWITH\b", sql_upper), "CTE WITH é proibida"
    assert "CONCAT" not in sql_upper, "Função CONCAT é proibida no SQL Server legado"
    assert "DEVOLU%" in sql_upper, "SQL deve incluir abatimento de devoluções (LIKE 'DEVOLU%')"
    assert sql.count("?") in (3, 4), "SQL deve usar bind parameters '?' para (mid, pre_start, ref)"
    # LGPD-CAN-01: não selecionar nome, CPF ou e-mail de cliente
    for forbidden_col in ("NOME", "CPF", "CNPJ", "EMAIL", "TELEFONE"):
        assert forbidden_col not in sql_upper


def test_repository_fetch_customer_sku_window_sales_uses_fetchmany_streaming():
    """T-CAN-RPT-SQL-02 (DA-03): `fetch_customer_sku_window_sales` lê em blocos via `cursor.fetchmany`."""
    # Arrange
    from src.modules.analytics.repository import sales_repository

    mock_cursor = MagicMock()
    mock_cursor.fetchmany.side_effect = [
        [(101, 100235, 10.0, 300.0, 2.0, 60.0)],
        [],
    ]
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_cursor
    mock_ctx.__exit__.return_value = False

    # Act
    with patch.object(sales_repository, "_execute_readonly", return_value=mock_ctx) as mock_exec:
        rows = sales_repository.fetch_customer_sku_window_sales(
            pre_start_date=date(2026, 5, 27),
            mid_date=date(2026, 8, 25),
            reference_date=date(2026, 11, 23),
        )

    # Assert
    assert mock_exec.called
    assert mock_cursor.fetchmany.called
    assert not mock_cursor.fetchall.called
    assert len(rows) == 1
    assert rows[0]["customer_code"] == 101
    assert rows[0]["sku"] == "100235"
    assert rows[0]["pre_rev"] == pytest.approx(300.0)
    assert rows[0]["cur_rev"] == pytest.approx(60.0)
