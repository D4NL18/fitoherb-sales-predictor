"""
T-17 — Busca de produto por código ou descrição (DC-5 aprovado; contrato §3.6; B-19, B-20).

Testado pela rota `GET /api/v1/analytics/products/search`, com o catálogo sintético entregue por
`fetch_catalog` substituído. A busca usa o cache próprio do catálogo (`get_catalog()`, DA-06) e
nunca dispara a carga das cestas (`_build_snapshot` / `fetch_order_baskets`).
"""
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.service import analytics_cache
from tests.analytics.fixtures.synthetic_data import FIXED_NOW_UTC, SyntheticProduct, catalog_frame

URL = "/api/v1/analytics/products/search"

SEARCH_PRODUCTS = [
    SyntheticProduct(1001, "CHA VERDE 100G", "CATARINENSE", 10.0, 5.0, 10.0),
    SyntheticProduct(1002, "CHA VERDE COM LIMAO 50G", "CATARINENSE", 10.0, 5.0, 10.0),
    SyntheticProduct(2100, "CHÁ VERMELHO", "LEAO", 10.0, 5.0, 10.0),
    SyntheticProduct(10010, "CAPSULA DE CHA BRANCO", "HERBARIUM", 10.0, 5.0, 10.0),
    SyntheticProduct(3000, "MISTURA P/ CHÁ", "LEAO", 10.0, 5.0, 10.0),
    SyntheticProduct(100123, "OLEO DE COPAIBA", "COPRA", 10.0, 5.0, 10.0),
    SyntheticProduct(51001, "MEL DE ABELHA", "APIS FLORA", 10.0, 5.0, 10.0),
    SyntheticProduct(7007, "GENGIBRE  EM   PO", "CATARINENSE", 10.0, 5.0, 10.0),
] + [
    SyntheticProduct(80000 + index, f"PRODUTO TESTE {index:02d}", "FORNECEDOR", 10.0, 5.0, 10.0)
    for index in range(30)
]


@pytest.fixture
def search_api(monkeypatch, repository_patcher):
    load_calls = []
    monkeypatch.setattr(analytics_cache, "_utc_now", lambda: FIXED_NOW_UTC)
    monkeypatch.setattr(analytics_cache, "_build_snapshot", lambda: load_calls.append(1))
    calls = repository_patcher(None, catalog_frame(SEARCH_PRODUCTS))
    client = TestClient(app, raise_server_exceptions=False)
    client.load_calls = load_calls
    client.repository_calls = calls
    return client


def codes(response):
    assert response.status_code == 200, response.text
    return [item["codigo"] for item in response.json()["data"]]


# ------------------------------------------------------------------ normalização e prioridade

def test_accent_and_case_insensitive_description_search(search_api):
    """'chá' encontra 'CHA' e 'CHÁ'; descrição que começa com q vem antes da que contém q."""
    assert codes(search_api.get(URL, params={"q": "chá"})) == [1001, 1002, 2100, 10010, 3000]
    assert codes(search_api.get(URL, params={"q": "CHA"})) == [1001, 1002, 2100, 10010, 3000]


def test_spaces_are_trimmed_and_collapsed(search_api):
    assert codes(search_api.get(URL, params={"q": "  cha   verde "})) == [1001, 1002]
    assert codes(search_api.get(URL, params={"q": "gengibre em po"})) == [7007]


def test_digits_search_exact_code_first_then_code_prefix(search_api):
    """Só dígitos: código exato, depois códigos que começam com q (empate por descrição e código)."""
    assert codes(search_api.get(URL, params={"q": "1001"})) == [1001, 10010, 100123]


def test_single_digit_query_is_allowed(search_api):
    assert search_api.get(URL, params={"q": "7"}).status_code == 200


def test_no_match_is_200_with_empty_list(search_api):
    response = search_api.get(URL, params={"q": "xyzw"})

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["meta"]["totalItems"] == 0
    assert body["meta"]["totalPages"] == 0


# ------------------------------------------------------------------ envelope e limite de 20

def test_results_limited_to_20_with_paged_meta(search_api):
    body = search_api.get(URL, params={"q": "produto teste"}).json()

    assert len(body["data"]) == 20
    assert body["data"][0] == {"codigo": 80000, "descricao": "PRODUTO TESTE 00", "fornecedor": "FORNECEDOR"}
    meta = body["meta"]
    assert (meta["page"], meta["limit"], meta["offset"], meta["totalItems"], meta["totalPages"]) == (1, 20, 0, 30, 2)
    assert meta["version"] == "1.1.0"
    assert "parametros" not in meta
    assert all(set(item) == {"codigo", "descricao", "fornecedor"} for item in body["data"])


def test_second_page_with_offset(search_api):
    body = search_api.get(URL, params={"q": "produto teste", "offset": 20}).json()

    assert [item["codigo"] for item in body["data"]] == list(range(80020, 80030))
    assert body["meta"]["page"] == 2


# ------------------------------------------------------------------ validação 400 XSL-004

@pytest.mark.parametrize(
    "params, fields",
    [
        ({"q": "a"}, ["q"]),
        ({"q": ""}, ["q"]),
        ({"q": "   "}, ["q"]),
        ({"q": "x" * 61}, ["q"]),
        ({}, ["q"]),
        ({"q": "cha", "limit": 21}, ["limit"]),
        ({"q": "cha", "limit": 0}, ["limit"]),
        ({"q": "cha", "offset": -1}, ["offset"]),
    ],
)
def test_invalid_query_is_400_xsl004(search_api, params, fields):
    response = search_api.get(URL, params=params)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "XSL-004"
    assert error["fields"] == fields


def test_sixty_characters_is_accepted(search_api):
    assert search_api.get(URL, params={"q": "x" * 60}).status_code == 200


# ------------------------------------------------------------------ não dispara a carga das cestas

def test_search_never_loads_order_baskets(search_api):
    search_api.get(URL, params={"q": "cha"})
    search_api.get(URL, params={"q": "1001"})

    assert search_api.load_calls == []
    assert search_api.repository_calls.order_baskets_cutoffs == []
    assert analytics_cache.get_cache_status().state == "FRIO"


def test_catalog_is_cached_between_searches(search_api):
    for query in ("cha", "mel", "1001"):
        search_api.get(URL, params={"q": query})

    assert search_api.repository_calls.catalog_calls == 1
