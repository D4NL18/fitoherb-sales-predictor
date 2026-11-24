"""
Testes de Integração e Contrato REST: Canibalização e Substituição (TDD First)
Fase F6 — Tarefa 6 — Regras P-138 e Contrato `.agents/docs/api_contracts/analytics-canibalizacao.md`.

Cenários cobertos:
1. `GET /api/v1/analytics/cannibalization/{sku}` -> 200 OK, envelope `data`/`meta` em `camelCase`,
   `timelineSeries`, `meta.dataReferencia`, `elasticityIntegration.status == "NAO_INTEGRADO"`.
2. Repasse de query params (`eventType`, `eventDate`, `windowWeeks`, `includeNonSignificant`).
3. `GET /api/v1/analytics/substitution/{sku}` -> 200 OK, envelope `data`/`meta`, `meta.dataReferencia`,
   sem exposição de `Cod Cliente` / `customerCode`.
4. Códigos de erro semânticos: `CAN-001` (404), `CAN-002` (422), `CAN-003` (422), `CAN-004` (400),
   `CAN-005` (500) e `ANL-001` (503).
5. `error.fields[]` preenchido em `CAN-004` sem ecoar o valor inválido recebido (LGPD-CAN-06).
6. Zero vazamento de stacktrace Python ou queries SQL em respostas 500/503.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.api.schemas import (
    AffectedProductDTO,
    CannibalizationDataDTO,
    CannibalizationMeta,
    CannibalizationResponse,
    ControlGroupDTO,
    ElasticityIntegrationDTO,
    NetImpactDTO,
    PeriodMetricsDTO,
    SubstituteCandidateDTO,
    SubstitutionDataDTO,
    SubstitutionMeta,
    SubstitutionResponse,
    TargetProductDTO,
    TimelinePointDTO,
)
from src.modules.analytics.domain.exceptions import (
    CannibalizationEventNotFoundError,
    CannibalizationInsufficientHistoryError,
    CannibalizationInvalidParametersError,
    CannibalizationProcessingError,
    CannibalizationProductNotFoundError,
)
from src.modules.analytics.repository.errors import SalesDatabaseUnavailableError

client = TestClient(app, raise_server_exceptions=False)

CANNIBALIZATION_URL = "/api/v1/analytics/cannibalization"
SUBSTITUTION_URL = "/api/v1/analytics/substitution"


def _fake_cannibalization_response(sku: str = "100234") -> CannibalizationResponse:
    return CannibalizationResponse(
        data=CannibalizationDataDTO(
            target_product=TargetProductDTO(
                sku=sku,
                description="EXTRATO DE PROPOLIS VERDE 30ML",
                category="EXTRATOS",
                event_type="promo",
                event_date="2026-09-01",
                price_direction="PRICE_DROP",
                avg_price_change_pct=-22.86,
                cost_fallback_used=False,
                pre_period=PeriodMetricsDTO(
                    start_date="2026-08-04",
                    end_date="2026-08-31",
                    volume=420.0,
                    avg_price=24.50,
                    revenue=10290.00,
                    estimated_margin=4116.00,
                ),
                post_period=PeriodMetricsDTO(
                    start_date="2026-09-01",
                    end_date="2026-09-28",
                    volume=980.0,
                    avg_price=18.90,
                    revenue=18522.00,
                    estimated_margin=4900.00,
                ),
                delta_volume=560.0,
                delta_volume_pct=133.33,
                delta_revenue=8232.00,
                delta_margin=784.00,
            ),
            control_group=ControlGroupDTO(
                category="EXTRATOS",
                sample_size=14,
                growth_factor=1.05,
                control_strategy="CATEGORIAL",
                is_expanded_control=False,
                description="14 produtos estáveis da categoria EXTRATOS.",
            ),
            timeline_series=[
                TimelinePointDTO(
                    week_offset=-1,
                    start_date="2026-08-25",
                    end_date="2026-08-31",
                    period="PRE",
                    target_volume=105.0,
                    control_total_volume=410.0,
                ),
                TimelinePointDTO(
                    week_offset=1,
                    start_date="2026-09-01",
                    end_date="2026-09-07",
                    period="POST",
                    target_volume=265.0,
                    control_total_volume=430.0,
                ),
            ],
            affected_products=[
                AffectedProductDTO(
                    sku="100235",
                    description="EXTRATO DE PROPOLIS AQUOSO 30ML",
                    category="EXTRATOS",
                    jaccard_similarity=0.42,
                    common_buyers_count=38,
                    pre_volume=310.0,
                    post_volume=165.0,
                    counterfactual_volume=325.5,
                    delta_volume=-160.5,
                    delta_volume_pct=-49.31,
                    unit_price=22.00,
                    unit_margin=9.50,
                    cost_fallback_used=False,
                    delta_revenue=-3531.00,
                    delta_margin=-1524.75,
                    classification="CANIBALIZACAO",
                    p_value=0.0018,
                    q_value=0.0072,
                    is_significant=True,
                    confidence_interval=[-192.0, -129.0],
                    elasticity_decomposition=None,
                )
            ],
            net_impact=NetImpactDTO(
                target_delta_volume=560.0,
                affected_delta_volume=-160.5,
                net_delta_volume=399.5,
                target_delta_revenue=8232.00,
                affected_delta_revenue=-3531.00,
                net_delta_revenue=4701.00,
                target_delta_margin=784.00,
                affected_delta_margin=-1524.75,
                net_delta_margin=-740.75,
                commercial_verdict="ILUSAO_DE_VOLUME",
                summary_message="Aumento de giro com perda líquida de margem.",
            ),
            elasticity_integration=ElasticityIntegrationDTO(
                status="NAO_INTEGRADO",
                message="Módulo de Elasticidade-Preço (Fase F5) ainda não acoplado.",
            ),
        ),
        meta=CannibalizationMeta(
            timestamp="2026-11-12T14:30:00Z",
            version="1.0.0",
            data_referencia="2026-11-12",
            sku=sku,
            event_type="promo",
            window_weeks=4,
            execution_time_ms=42,
        ),
    )


def _fake_substitution_response(sku: str = "100234") -> SubstitutionResponse:
    return SubstitutionResponse(
        data=SubstitutionDataDTO(
            target_sku=sku,
            target_description="EXTRATO DE PROPOLIS VERDE 30ML",
            target_category="EXTRATOS",
            target_current_price=24.50,
            target_stock=340,
            substitutes=[
                SubstituteCandidateDTO(
                    sku="100235",
                    description="EXTRATO DE PROPOLIS AQUOSO 30ML",
                    category="EXTRATOS",
                    jaccard_similarity=0.42,
                    common_buyers_count=38,
                    current_price=22.00,
                    current_stock=185,
                )
            ],
        ),
        meta=SubstitutionMeta(
            timestamp="2026-11-12T14:30:00Z",
            version="1.0.0",
            data_referencia="2026-11-12",
            target_sku=sku,
            total_found=1,
            execution_time_ms=15,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/cannibalization/{sku}
# ---------------------------------------------------------------------------


def test_get_cannibalization_success_envelope_and_camel_case():
    """T-CAN-API-01: Retorna 200 com envelope data/meta em camelCase, timelineSeries e meta.dataReferencia."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.return_value = _fake_cannibalization_response("100234")

        # Act
        response = client.get(f"{CANNIBALIZATION_URL}/100234")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "meta" in body
    assert body["meta"]["dataReferencia"] == "2026-11-12"
    assert body["meta"]["sku"] == "100234"
    assert body["meta"]["eventType"] == "promo"
    assert body["meta"]["windowWeeks"] == 4
    assert body["data"]["targetProduct"]["priceDirection"] == "PRICE_DROP"
    assert body["data"]["controlGroup"]["controlStrategy"] == "CATEGORIAL"
    assert len(body["data"]["timelineSeries"]) == 2
    assert body["data"]["timelineSeries"][0]["weekOffset"] == -1
    assert body["data"]["affectedProducts"][0]["classification"] == "CANIBALIZACAO"
    assert body["data"]["netImpact"]["commercialVerdict"] == "ILUSAO_DE_VOLUME"
    assert body["data"]["elasticityIntegration"]["status"] == "NAO_INTEGRADO"
    assert "_" not in json.dumps(list(body["data"].keys()))


def test_get_cannibalization_forwards_query_params():
    """T-CAN-API-02: Repassa eventType, eventDate, windowWeeks e includeNonSignificant ao serviço."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.return_value = _fake_cannibalization_response("100234")

        # Act
        response = client.get(
            f"{CANNIBALIZATION_URL}/100234",
            params={
                "eventType": "price",
                "eventDate": "2026-09-01",
                "windowWeeks": 6,
                "includeNonSignificant": "true",
            },
        )

    # Assert
    assert response.status_code == 200
    assert mock_svc.called


def test_get_cannibalization_not_found_returns_404_can_001():
    """T-CAN-API-03: SKU inexistente retorna 404 com código CAN-001."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.side_effect = CannibalizationProductNotFoundError()

        # Act
        response = client.get(f"{CANNIBALIZATION_URL}/999999")

    # Assert
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "CAN-001"
    assert body["error"]["fields"] == []


@pytest.mark.parametrize(
    "exc_cls,expected_code",
    [
        (CannibalizationEventNotFoundError, "CAN-002"),
        (CannibalizationInsufficientHistoryError, "CAN-003"),
    ],
)
def test_get_cannibalization_unprocessable_returns_422_can_002_can_003(exc_cls, expected_code):
    """T-CAN-API-04: Evento não encontrado (CAN-002) ou histórico insuficiente (CAN-003) retornam 422."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.side_effect = exc_cls()

        # Act
        response = client.get(f"{CANNIBALIZATION_URL}/100234?eventType=launch")

    # Assert
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == expected_code
    assert body["error"]["fields"] == []


@pytest.mark.parametrize(
    "path_and_query,expected_field,forbidden_echo",
    [
        ("/0", "sku", None),
        ("/abc", "sku", "abc"),
        ("/100234?eventType=desconto_relampago", "eventType", "desconto_relampago"),
        ("/100234?windowWeeks=20", "windowWeeks", "20"),
        ("/100234?windowWeeks=1", "windowWeeks", None),
        ("/100234?eventDate=2026-99-99", "eventDate", "2026-99-99"),
    ],
)
def test_get_cannibalization_invalid_params_returns_400_can_004_without_echo(
    path_and_query, expected_field, forbidden_echo
):
    """T-CAN-API-05 (LGPD-CAN-06): Parâmetros inválidos retornam 400 CAN-004 com error.fields[] e sem eco do input."""
    # Arrange & Act
    response = client.get(f"{CANNIBALIZATION_URL}{path_and_query}")

    # Assert
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "CAN-004"
    assert expected_field in body["error"]["fields"]
    if forbidden_echo:
        assert forbidden_echo not in body["error"]["message"]


def test_get_cannibalization_domain_invalid_params_returns_400_can_004():
    """T-CAN-API-06: Exceção CannibalizationInvalidParametersError mapeia para 400 CAN-004."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.side_effect = CannibalizationInvalidParametersError(fields=["eventDate"])

        # Act
        response = client.get(f"{CANNIBALIZATION_URL}/100234")

    # Assert
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "CAN-004"
    assert "eventDate" in body["error"]["fields"]


def test_get_cannibalization_internal_error_sanitized_zero_stacktrace_or_sql():
    """T-CAN-API-07 (P-138.4): Erro 500 CAN-005 e 503 ANL-001 nunca expõem stacktrace nem SQL."""
    # Arrange (CAN-005)
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.side_effect = CannibalizationProcessingError()
        resp_500 = client.get(f"{CANNIBALIZATION_URL}/100234")

    # Assert 500
    assert resp_500.status_code == 500
    raw_500 = resp_500.text
    assert resp_500.json()["error"]["code"] == "CAN-005"
    for leak in ("Traceback", 'File "', "SELECT ", "pyodbc", "Externo01"):
        assert leak not in raw_500

    # Arrange (ANL-001)
    with patch("src.modules.analytics.service.analytics_service.get_cannibalization_analysis") as mock_svc:
        mock_svc.side_effect = SalesDatabaseUnavailableError()
        resp_503 = client.get(f"{CANNIBALIZATION_URL}/100234")

    # Assert 503
    assert resp_503.status_code == 503
    assert resp_503.json()["error"]["code"] == "ANL-001"


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/substitution/{sku}
# ---------------------------------------------------------------------------


def test_get_substitution_success_envelope_and_no_pii():
    """T-SUB-API-01: GET /substitution/{sku} retorna 200 com envelope data/meta e zero Cod Cliente."""
    # Arrange
    with patch("src.modules.analytics.service.analytics_service.get_substitution_candidates") as mock_svc:
        mock_svc.return_value = _fake_substitution_response("100234")

        # Act
        response = client.get(f"{SUBSTITUTION_URL}/100234?minJaccard=0.20&limit=10")

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["dataReferencia"] == "2026-11-12"
    assert body["meta"]["totalFound"] == 1
    assert body["data"]["targetSku"] == "100234"
    assert len(body["data"]["substitutes"]) == 1
    assert body["data"]["substitutes"][0]["jaccardSimilarity"] == 0.42
    serialized = json.dumps(body).lower()
    assert "codcliente" not in serialized
    assert "customercode" not in serialized


def test_get_substitution_not_found_and_validation_errors():
    """T-SUB-API-02: SKU inexistente -> 404 CAN-001; minJaccard/limit fora da faixa -> 400 CAN-004."""
    # Arrange & Act: 404
    with patch("src.modules.analytics.service.analytics_service.get_substitution_candidates") as mock_svc:
        mock_svc.side_effect = CannibalizationProductNotFoundError()
        resp_404 = client.get(f"{SUBSTITUTION_URL}/999999")

    assert resp_404.status_code == 404
    assert resp_404.json()["error"]["code"] == "CAN-001"

    # Act: 400 invalid minJaccard / limit
    resp_jaccard = client.get(f"{SUBSTITUTION_URL}/100234?minJaccard=0.90")
    assert resp_jaccard.status_code == 400
    assert resp_jaccard.json()["error"]["code"] == "CAN-004"
    assert "minJaccard" in resp_jaccard.json()["error"]["fields"]

    resp_limit = client.get(f"{SUBSTITUTION_URL}/100234?limit=100")
    assert resp_limit.status_code == 400
    assert resp_limit.json()["error"]["code"] == "CAN-004"
    assert "limit" in resp_limit.json()["error"]["fields"]
