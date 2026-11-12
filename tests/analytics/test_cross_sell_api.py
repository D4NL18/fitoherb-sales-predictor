"""
T-12 — Rotas de cross-sell no contrato 1.1.0 (contrato §2, §3.3, §3.4, §4; P-061 a P-067).

`TestClient` com snapshot real montado a partir das massas sintéticas (repositório substituído,
relógio fixo em 2026-11-05) e publicado no cache. Os números das massas reproduzem os exemplos do
contrato: R1 (lift 4,25, confiança 0,34, 170 pedidos) e R5 (lift 1,2) no modo produto; G antes de B
no modo cliente (CA-13).

Requisitos de interface além dos de `conftest.py`: a carga de produção usa `analytics_cache._utc_now()`
para a data de referência (UTC-3) e chama `fetch_order_baskets(data_referencia + 1 dia)`;
`AnalyticsSnapshot` expõe `reference_day` (campo ou propriedade) para o domínio do cliente.
"""
import re

import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.domain import cross_sell
from src.modules.analytics.repository.errors import AnalyticsDataSourceError
from src.modules.analytics.service import analytics_cache
from tests.analytics.conftest import build_snapshot_from_mass, install_snapshot
from tests.analytics.fixtures.synthetic_data import (
    CUSTOMER_ALREADY_BUYS_ALL,
    CUSTOMER_INACTIVE,
    CUSTOMER_UNKNOWN,
    CUSTOMER_WITH_CANDIDATES,
    EXPECTED_CUTOFF,
    FIXED_NOW_UTC,
    REFERENCE_DAY,
    SKU_CHA_VERDE,
    SKU_GENGIBRE,
    SKU_HIBISCO,
    SKU_INEXISTENTE,
    SKU_MEL,
    SKU_OLEO_COCO_200,
    SKU_SO_PEDIDO_UNITARIO,
    build_customer_contract_mass,
    build_insufficient_mass,
    build_product_contract_mass,
)

BASE = "/api/v1/analytics/cross-sell"
ISO_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

EXPECTED_PARAMETERS = {
    "minLift": cross_sell.MIN_LIFT,
    "minConfidence": cross_sell.MIN_CONFIDENCE,
    "minPairOrders": cross_sell.MIN_PAIR_ORDERS,
    "trivialItemSupport": cross_sell.TRIVIAL_ITEM_SUPPORT,
    "dormantDays": cross_sell.DORMANT_DAYS,
    "customerProfileDays": cross_sell.CUSTOMER_PROFILE_DAYS,
    "cacheTtlHours": analytics_cache.CACHE_TTL_HOURS,
}

EXPECTED_PRODUCT_DATA = {
    "produto": {"codigo": 1001, "descricao": "CHA VERDE 100G", "fornecedor": "CATARINENSE"},
    "recomendacoes": [
        {
            "codigo": 2002, "descricao": "CAPSULA DE HIBISCO", "fornecedor": "HERBARIUM",
            "suporte": 0.017, "confianca": 0.34, "lift": 4.25, "pedidosEmComum": 170,
            "estoqueAtual": 84.0, "semEstoque": False, "margemNaoPositiva": False,
            "explicacao": {
                "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
                "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
                "evidencia": "Baseado em 170 pedidos.",
                "motivo": None,
            },
        },
        {
            "codigo": 3003, "descricao": "OLEO DE COCO 200ML", "fornecedor": "COPRA",
            "suporte": 0.006, "confianca": 0.12, "lift": 1.2, "pedidosEmComum": 60,
            "estoqueAtual": 0.0, "semEstoque": True, "margemNaoPositiva": False,
            "explicacao": {
                "frequencia": "Em 12% dos pedidos com CHA VERDE 100G também há OLEO DE COCO 200ML.",
                "intensidade": "OLEO DE COCO 200ML aparece 1,2 vezes mais nesses pedidos do que no geral.",
                "evidencia": "Baseado em 60 pedidos.",
                "motivo": None,
            },
        },
    ],
}

EXPECTED_CUSTOMER_ITEMS = [
    {
        "codigo": 7007, "descricao": "GENGIBRE EM PO 100G", "fornecedor": "CATARINENSE",
        "antecedentePrincipal": {"codigo": 1001, "descricao": "CHA VERDE 100G"},
        "qtdAntecedentesRelacionados": 2,
        "lift": 2.0, "confianca": 0.2, "pedidosEmComum": 100,
        "margemUnitaria": 30.0, "custoEstimado": False, "pontuacao": 12.0,
        "motivo": "NUNCA_COMPROU", "diasDesdeUltimaCompra": None,
        "explicacao": {
            "frequencia": "Em 20% dos pedidos com CHA VERDE 100G também há GENGIBRE EM PO 100G.",
            "intensidade": "GENGIBRE EM PO 100G aparece 2,0 vezes mais nesses pedidos do que no geral.",
            "evidencia": "Baseado em 100 pedidos.",
            "motivo": "Sugerido porque o cliente compra CHA VERDE 100G. O cliente nunca comprou GENGIBRE EM PO 100G.",
        },
    },
    {
        "codigo": 2002, "descricao": "CAPSULA DE HIBISCO", "fornecedor": "HERBARIUM",
        "antecedentePrincipal": {"codigo": 1001, "descricao": "CHA VERDE 100G"},
        "qtdAntecedentesRelacionados": 1,
        "lift": 4.25, "confianca": 0.34, "pedidosEmComum": 170,
        "margemUnitaria": 5.0, "custoEstimado": True, "pontuacao": 7.23,
        "motivo": "DORMENTE", "diasDesdeUltimaCompra": 120,
        "explicacao": {
            "frequencia": "Em 34% dos pedidos com CHA VERDE 100G também há CAPSULA DE HIBISCO.",
            "intensidade": "CAPSULA DE HIBISCO aparece 4,3 vezes mais nesses pedidos do que no geral.",
            "evidencia": "Baseado em 170 pedidos.",
            "motivo": (
                "Sugerido porque o cliente compra CHA VERDE 100G. "
                "O cliente não compra CAPSULA DE HIBISCO há 120 dias."
            ),
        },
    },
]


@pytest.fixture(scope="module")
def product_build():
    return build_snapshot_from_mass(build_product_contract_mass())


@pytest.fixture(scope="module")
def customer_snapshot():
    return build_snapshot_from_mass(build_customer_contract_mass())[0]


@pytest.fixture(scope="module")
def insufficient_snapshot():
    return build_snapshot_from_mass(build_insufficient_mass())[0]


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def product_api(client, monkeypatch, product_build):
    install_snapshot(monkeypatch, product_build[0])
    return client


@pytest.fixture
def customer_api(client, monkeypatch, customer_snapshot):
    install_snapshot(monkeypatch, customer_snapshot)
    return client


def _assert_paged_meta(meta, *, page, limit, offset, total_items, total_pages):
    assert ISO_TIMESTAMP.match(meta["timestamp"])
    assert meta["version"] == "1.1.0"
    assert meta["dataReferencia"] == "2026-11-05"
    assert (meta["page"], meta["limit"], meta["offset"]) == (page, limit, offset)
    assert (meta["totalItems"], meta["totalPages"]) == (total_items, total_pages)
    assert meta["parametros"] == pytest.approx(EXPECTED_PARAMETERS)
    for key in ("minPairOrders", "dormantDays", "customerProfileDays", "cacheTtlHours"):
        assert isinstance(meta["parametros"][key], int)


def _assert_decimals(value, places):
    assert round(value, places) == value, f"{value} com mais de {places} casas"


# ------------------------------------------------------------------ carga real (DA-02, DA-05)

def test_snapshot_load_uses_exclusive_cutoff_and_reference_day(product_build):
    snapshot, calls = product_build

    assert calls.order_baskets_cutoffs == [EXPECTED_CUTOFF]
    assert str(snapshot.reference_date) == "2026-11-05"
    assert snapshot.reference_day == REFERENCE_DAY
    assert snapshot.is_base_sufficient is True
    assert snapshot.valid_basket_count == 10_000


# ------------------------------------------------------------------ modo produto (§3.3)

def test_product_contract_example(product_api):
    response = product_api.get(f"{BASE}/product/{SKU_CHA_VERDE}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == EXPECTED_PRODUCT_DATA
    assert "motivoVazio" not in body["meta"]
    _assert_paged_meta(body["meta"], page=1, limit=50, offset=0, total_items=2, total_pages=1)


def test_product_numeric_types_and_precision(product_api):
    items = product_api.get(f"{BASE}/product/{SKU_CHA_VERDE}").json()["data"]["recomendacoes"]

    for item in items:
        assert type(item["codigo"]) is int and type(item["pedidosEmComum"]) is int
        assert isinstance(item["estoqueAtual"], float)
        assert isinstance(item["semEstoque"], bool) and isinstance(item["margemNaoPositiva"], bool)
        _assert_decimals(item["suporte"], 4)
        _assert_decimals(item["confianca"], 4)
        _assert_decimals(item["lift"], 2)
        _assert_decimals(item["estoqueAtual"], 1)


def test_c02_product_without_rules_is_200_with_consulted_product(product_api):
    body = product_api.get(f"{BASE}/product/{SKU_MEL}").json()

    assert body["data"] == {
        "produto": {"codigo": 4004, "descricao": "MEL DE ABELHA 500G", "fornecedor": "APIS FLORA"},
        "recomendacoes": [],
    }
    _assert_paged_meta(body["meta"], page=1, limit=50, offset=0, total_items=0, total_pages=0)


@pytest.mark.parametrize("sku", [SKU_INEXISTENTE, SKU_SO_PEDIDO_UNITARIO])
def test_c03_unknown_or_single_item_only_sku_is_404(product_api, sku):
    response = product_api.get(f"{BASE}/product/{sku}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "XSL-001"


def test_product_pagination_second_page(product_api):
    body = product_api.get(f"{BASE}/product/{SKU_CHA_VERDE}?limit=1&offset=1").json()

    assert [item["codigo"] for item in body["data"]["recomendacoes"]] == [SKU_OLEO_COCO_200]
    _assert_paged_meta(body["meta"], page=2, limit=1, offset=1, total_items=2, total_pages=2)


def test_c14_offset_beyond_total_keeps_product_and_totals(product_api):
    response = product_api.get(f"{BASE}/product/{SKU_CHA_VERDE}?offset=5")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["recomendacoes"] == []
    assert body["data"]["produto"]["codigo"] == SKU_CHA_VERDE
    _assert_paged_meta(body["meta"], page=1, limit=50, offset=5, total_items=2, total_pages=1)


# ------------------------------------------------------------------ modo cliente (§3.4)

def test_customer_contract_example(customer_api):
    response = customer_api.get(f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == {"recomendacoes": EXPECTED_CUSTOMER_ITEMS}
    assert "motivoVazio" in body["meta"] and body["meta"]["motivoVazio"] is None
    _assert_paged_meta(body["meta"], page=1, limit=50, offset=0, total_items=2, total_pages=1)


def test_customer_numeric_types_and_precision(customer_api):
    items = customer_api.get(f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}").json()["data"]["recomendacoes"]

    for item in items:
        for key in ("codigo", "pedidosEmComum", "qtdAntecedentesRelacionados"):
            assert type(item[key]) is int, key
        assert item["diasDesdeUltimaCompra"] is None or type(item["diasDesdeUltimaCompra"]) is int
        _assert_decimals(item["confianca"], 4)
        _assert_decimals(item["lift"], 2)
        _assert_decimals(item["margemUnitaria"], 2)
        _assert_decimals(item["pontuacao"], 2)
        assert "suporte" not in item


def test_customer_response_never_echoes_customer_code(customer_api):
    response = customer_api.get(f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}")

    assert "customerCode" not in response.text
    assert str(CUSTOMER_WITH_CANDIDATES) not in response.text


def test_c07_customer_without_recent_purchases(customer_api):
    body = customer_api.get(f"{BASE}/customer/{CUSTOMER_INACTIVE}").json()

    assert body["data"] == {"recomendacoes": []}
    assert body["meta"]["motivoVazio"] == "SEM_COMPRAS_RECENTES"
    _assert_paged_meta(body["meta"], page=1, limit=50, offset=0, total_items=0, total_pages=0)


def test_c06_customer_already_buys_everything(customer_api):
    body = customer_api.get(f"{BASE}/customer/{CUSTOMER_ALREADY_BUYS_ALL}").json()

    assert body["data"] == {"recomendacoes": []}
    assert "motivoVazio" in body["meta"] and body["meta"]["motivoVazio"] is None


def test_c08_unknown_customer_is_404(customer_api):
    response = customer_api.get(f"{BASE}/customer/{CUSTOMER_UNKNOWN}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "XSL-002"
    assert str(CUSTOMER_UNKNOWN) not in response.text


def test_customer_pagination_after_viability_filters(customer_api):
    """P-063.5: totalItems conta só os viáveis (K com margem zero não entra) e a página corta depois."""
    body = customer_api.get(f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}?limit=1&offset=1").json()

    assert [item["codigo"] for item in body["data"]["recomendacoes"]] == [SKU_HIBISCO]
    _assert_paged_meta(body["meta"], page=2, limit=1, offset=1, total_items=2, total_pages=2)
    assert body["meta"]["motivoVazio"] is None


def test_customer_offset_beyond_total(customer_api):
    body = customer_api.get(f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}?offset=50").json()

    assert body["data"]["recomendacoes"] == []
    assert body["meta"]["totalItems"] == 2
    assert body["meta"]["motivoVazio"] is None


def test_product_mode_of_customer_mass_lists_g_and_b(customer_api):
    """
    Sanidade da massa do cliente: A -> B e A -> G são as únicas Regras Úteis com antecedente A.
    G vem antes de B, apesar do lift menor, porque é do mesmo fornecedor de A (P-094.2).
    """
    items = customer_api.get(f"{BASE}/product/{SKU_CHA_VERDE}").json()["data"]["recomendacoes"]
    assert [item["codigo"] for item in items] == [SKU_GENGIBRE, SKU_HIBISCO]


# ------------------------------------------------------------------ ordem de avaliação 400 -> 503 -> 422 -> 404 -> 200

def test_order_400_before_loading(client, repository_patcher, monkeypatch):
    monkeypatch.setattr(analytics_cache, "_utc_now", lambda: FIXED_NOW_UTC)
    calls = repository_patcher(None, None, order_baskets_error=AnalyticsDataSourceError())

    response = client.get(f"{BASE}/product/abc")

    assert response.status_code == 400
    assert calls.order_baskets_cutoffs == []


def test_order_503_when_database_fails(client, repository_patcher, monkeypatch):
    monkeypatch.setattr(analytics_cache, "_utc_now", lambda: FIXED_NOW_UTC)
    repository_patcher(None, build_product_contract_mass()[1], order_baskets_error=AnalyticsDataSourceError())

    for url in (f"{BASE}/product/{SKU_INEXISTENTE}", f"{BASE}/customer/{CUSTOMER_UNKNOWN}"):
        response = client.get(url)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ANL-001"


@pytest.mark.parametrize(
    "url",
    [
        f"{BASE}/product/{SKU_INEXISTENTE}",
        f"{BASE}/product/{SKU_CHA_VERDE}",
        f"{BASE}/customer/{CUSTOMER_UNKNOWN}",
        f"{BASE}/customer/{CUSTOMER_WITH_CANDIDATES}",
    ],
)
def test_order_422_before_404_when_base_is_insufficient(client, monkeypatch, insufficient_snapshot, url):
    install_snapshot(monkeypatch, insufficient_snapshot)

    response = client.get(url)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "XSL-003"


def test_insufficient_snapshot_is_flagged(insufficient_snapshot):
    assert insufficient_snapshot.is_base_sufficient is False


# ------------------------------------------------------------------ cache entre requisições (P-059.7)

def test_rules_are_not_recomputed_per_request(client, repository_patcher, monkeypatch):
    monkeypatch.setattr(analytics_cache, "_utc_now", lambda: FIXED_NOW_UTC)
    order_baskets, catalog = build_insufficient_mass()
    calls = repository_patcher(order_baskets, catalog)

    for _ in range(3):
        client.get(f"{BASE}/product/{SKU_CHA_VERDE}")

    assert len(calls.order_baskets_cutoffs) == 1
