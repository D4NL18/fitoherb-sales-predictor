"""
T-04 — Fundação da API do módulo Analytics (P-066.2, P-067, P-069, CA-16, CA-17, CA-21, LGPD-05, LGPD-10).

`TestClient` sobre `src.api.app`; o serviço é substituído por funções que levantam as exceções.
Requisito de interface: o router chama o serviço pelo módulo
(`from src.modules.analytics.service import analytics_service` + `analytics_service.<função>(...)`),
para que `monkeypatch.setattr(analytics_service, ...)` tenha efeito. Funções esperadas:
`get_health()`, `reload_cache()`, `get_product_cross_sell(sku, page_request)`,
`get_customer_cross_sell(customer_code, page_request)`, `search_products(q, page_request)`.
"""
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.domain.exceptions import (
    AnalyticsDomainException,
    CustomerWithoutHistoryError,
    InsufficientBaseError,
    InvalidParametersError,
    ProductNotFoundError,
)
from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from src.modules.analytics.service import analytics_cache, analytics_service
from src.modules.analytics.service.analytics_cache import ReloadTooSoonError

BASE = "/api/v1/analytics"
PRODUCT_URL = f"{BASE}/cross-sell/product/1001"
CUSTOMER_URL = f"{BASE}/cross-sell/customer/48213"

MESSAGES = {
    "XSL-001": "Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item.",
    "XSL-002": "Cliente sem histórico de compras.",
    "XSL-003": "Não há pedidos suficientes para gerar recomendações confiáveis.",
    "ANL-001": "Base de vendas indisponível no momento. Tente novamente em instantes.",
    "ANL-002": "A base foi recarregada recentemente. Tente novamente mais tarde.",
}

PARAMETER_KEYS = {
    "minLift", "minConfidence", "minPairOrders", "trivialItemSupport", "dormantDays", "customerProfileDays",
    "cacheTtlHours",
}

LEAK_MARKERS = ("Traceback", "File \"", "pyodbc", "SELECT", "Externo01", "detail", "input")


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def service_must_not_be_called(monkeypatch):
    """Validação deve responder 400 antes de tocar no serviço (ordem 400 -> 503 -> 422 -> 404)."""
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("o serviço não deveria ser chamado em erro de validação")

    for name in ("get_product_cross_sell", "get_customer_cross_sell", "search_products", "reload_cache"):
        monkeypatch.setattr(analytics_service, name, forbidden)
    return calls


def _raise(exc):
    def _fail(*args, **kwargs):
        raise exc

    return _fail


def _assert_error_body(response, status, code, fields=()):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error", "meta"}
    assert set(body["error"]) == {"code", "message", "fields"}
    assert body["error"]["code"] == code
    assert body["error"]["fields"] == list(fields)
    assert set(body["meta"]) == {"timestamp", "version"}
    assert body["meta"]["version"] == "1.1.0"
    for marker in LEAK_MARKERS:
        assert marker not in response.text, marker
    return body


# ------------------------------------------------------------------ exceções de domínio (B-02)

def test_domain_exceptions_have_codes_and_fixed_messages():
    cases = [
        (ProductNotFoundError(), "XSL-001"),
        (CustomerWithoutHistoryError(), "XSL-002"),
        (InsufficientBaseError(), "XSL-003"),
    ]
    for exc, code in cases:
        assert isinstance(exc, AnalyticsDomainException)
        assert exc.code == code
        assert exc.message == MESSAGES[code]
        assert tuple(exc.fields) == ()


def test_invalid_parameters_error_lists_fields_without_values():
    exc = InvalidParametersError(fields=("limit", "offset"))
    assert exc.code == "XSL-004"
    assert exc.message == "Parâmetros inválidos: limit, offset."
    assert tuple(exc.fields) == ("limit", "offset")


# ------------------------------------------------------------------ health (P-069, CA-21)

def test_ca21_health_with_cold_cache_does_not_load(client, monkeypatch, repository_patcher):
    load_calls = []
    monkeypatch.setattr(analytics_cache, "_build_snapshot", lambda: load_calls.append(1))
    calls = repository_patcher(None, None)

    response = client.get(f"{BASE}/health")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data", "meta"}
    data = body["data"]
    assert data["status"] == "UP"
    assert data["estadoCache"] == "FRIO"
    assert data["cacheCarregado"] is False
    assert data["baseSuficiente"] is None
    assert data["carregadoEm"] is None
    assert data["expiraEm"] is None
    assert data["duracaoUltimaCargaMs"] is None
    assert data["contagens"] is None
    assert set(data["parametros"]) == PARAMETER_KEYS
    assert body["meta"]["dataReferencia"] is None
    assert body["meta"]["version"] == "1.1.0"
    assert body["meta"]["timestamp"]
    assert load_calls == []
    assert calls.order_baskets_cutoffs == [] and calls.catalog_calls == 0


# ------------------------------------------------------------------ códigos de erro (P-067, CA-17, LGPD-05)

@pytest.mark.parametrize(
    "exc, status, code",
    [
        (ProductNotFoundError(), 404, "XSL-001"),
        (InsufficientBaseError(), 422, "XSL-003"),
        (AnalyticsDataSourceError(), 503, "ANL-001"),
    ],
)
def test_ca17_product_route_errors(client, monkeypatch, exc, status, code):
    monkeypatch.setattr(analytics_service, "get_product_cross_sell", _raise(exc))

    body = _assert_error_body(client.get(PRODUCT_URL), status, code)
    assert body["error"]["message"] == MESSAGES[code]


def test_ca17_customer_without_history_does_not_echo_code(client, monkeypatch):
    monkeypatch.setattr(analytics_service, "get_customer_cross_sell", _raise(CustomerWithoutHistoryError()))

    response = client.get(CUSTOMER_URL)

    body = _assert_error_body(response, 404, "XSL-002")
    assert body["error"]["message"] == MESSAGES["XSL-002"]
    assert "48213" not in response.text


def test_domain_invalid_parameters_maps_to_400(client, monkeypatch):
    monkeypatch.setattr(analytics_service, "get_product_cross_sell", _raise(InvalidParametersError(fields=("sku",))))

    body = _assert_error_body(client.get(PRODUCT_URL), 400, "XSL-004", ["sku"])
    assert body["error"]["message"] == "Parâmetros inválidos: sku."


def test_reload_too_soon_is_429(client, monkeypatch):
    monkeypatch.setattr(analytics_service, "reload_cache", _raise(ReloadTooSoonError()))

    body = _assert_error_body(client.post(f"{BASE}/cache/reload"), 429, "ANL-002")
    assert body["error"]["message"] == MESSAGES["ANL-002"]


def test_reload_with_database_down_is_503(client, monkeypatch):
    monkeypatch.setattr(analytics_service, "reload_cache", _raise(AnalyticsDataSourceError()))

    _assert_error_body(client.post(f"{BASE}/cache/reload"), 503, "ANL-001")


def test_unexpected_error_returns_generic_500_without_stacktrace(client, monkeypatch):
    monkeypatch.setattr(analytics_service, "get_product_cross_sell", _raise(RuntimeError("segredo interno xyz")))

    response = client.get(PRODUCT_URL)

    assert response.status_code == 500
    assert "segredo interno xyz" not in response.text
    assert "Traceback" not in response.text


# ------------------------------------------------------------------ validação 400 XSL-004 (CA-16, C-04, C-13)

@pytest.mark.parametrize(
    "url, fields",
    [
        (f"{PRODUCT_URL}?limit=0", ["limit"]),
        (f"{PRODUCT_URL}?limit=201", ["limit"]),
        (f"{PRODUCT_URL}?offset=-1", ["offset"]),
        (f"{PRODUCT_URL}?limit=1.5", ["limit"]),
        (f"{PRODUCT_URL}?limit=0&offset=-1", ["limit", "offset"]),
        (f"{BASE}/cross-sell/product/abc", ["sku"]),
        (f"{BASE}/cross-sell/product/-5", ["sku"]),
        (f"{BASE}/cross-sell/product/0", ["sku"]),
        (f"{BASE}/cross-sell/product/2147483648", ["sku"]),
        (f"{BASE}/cross-sell/customer/-5", ["customerCode"]),
        (f"{BASE}/cross-sell/customer/1%20OR%201%3D1", ["customerCode"]),
        (f"{CUSTOMER_URL}?limit=201", ["limit"]),
    ],
)
def test_ca16_validation_errors_are_400_xsl004(client, service_must_not_be_called, url, fields):
    response = client.get(url)

    body = _assert_error_body(response, 400, "XSL-004", fields)
    assert body["error"]["message"] == f"Parâmetros inválidos: {', '.join(fields)}."
    assert "OR 1=1" not in response.text
    assert "-5" not in response.text
    assert service_must_not_be_called == []


def test_limit_at_bounds_is_accepted(client, monkeypatch):
    """Faixa inclusiva: limit=1 e limit=200 passam pela validação (P-066.2)."""
    received = []

    def fake_product(sku, page_request):
        received.append((sku, page_request.limit, page_request.offset))
        raise ProductNotFoundError()

    monkeypatch.setattr(analytics_service, "get_product_cross_sell", fake_product)

    assert client.get(f"{PRODUCT_URL}?limit=1").status_code == 404
    assert client.get(f"{PRODUCT_URL}?limit=200&offset=0").status_code == 404
    assert client.get(PRODUCT_URL).status_code == 404
    assert received == [(1001, 1, 0), (1001, 200, 0), (1001, 50, 0)]


# ------------------------------------------------------------------ regressão (DA-08)

def test_other_modules_keep_fastapi_422(client):
    """O handler 400 é escopado ao prefixo /api/v1/analytics: inventory continua com o 422 padrão."""
    response = client.post("/api/v1/inventory/predict", json={"historyWindowDays": 5})

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], list)
    assert "error" not in body


# ------------------------------------------------------------------ autenticação (LGPD-10)

def test_customer_route_requires_auth_in_production(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_USERNAME", "testuser")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")
    monkeypatch.setattr(analytics_service, "get_customer_cross_sell", _raise(AssertionError("não autenticado")))

    response = client.get(CUSTOMER_URL)

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
