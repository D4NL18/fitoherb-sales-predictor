"""
T-17 — Busca de produto por código ou descrição (DC-5 aprovado; contrato §3.6; B-19, B-20).

Testado pela rota `GET /api/v1/analytics/products/search`, com o catálogo sintético entregue por
`fetch_catalog` substituído. A busca usa o cache próprio do catálogo (`get_catalog()`, DA-06) e
nunca dispara a carga das cestas (`_build_snapshot` / `fetch_order_baskets`).
"""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.repository import sales_repository
from src.modules.analytics.service import analytics_cache
from tests.analytics.fixtures.synthetic_data import FIXED_NOW_UTC, SyntheticProduct, catalog_frame
from tests.analytics.test_seasonality_domain import _build_synthetic_monthly_sales

URL = "/api/v1/analytics/products/search"
CATALOG_URL = "/api/v1/analytics/products"

SEARCH_PRODUCTS = [
    SyntheticProduct(1001, "CHA VERDE 100G", "CATARINENSE", 10.0, 5.0, 10.0),
    SyntheticProduct(1002, "CHA VERDE COM LIMAO 50G", "CATARINENSE", 10.0, 5.0, 10.0),
    SyntheticProduct(2100, "CHÁ VERMELHO", "LEAO", 10.0, 5.0, 10.0),
    SyntheticProduct(10010, "CAPSULA DE CHA BRANCO", "HERBARIUM", 10.0, 5.0, 10.0),
    SyntheticProduct(3000, "MISTURA P/ CHÁ", "LEAO", 10.0, 5.0, 10.0),
    SyntheticProduct(100123, "OLEO DE COPAIBA", "COPRA", 10.0, 5.0, 10.0),
    SyntheticProduct(51001, "MEL DE ABELHA", "APIS FLORA", 10.0, 5.0, 10.0),
    SyntheticProduct(7007, "GENGIBRE  EM   PO", "CATARINENSE", 10.0, 5.0, 10.0),
    SyntheticProduct(9001, "WHEY 100% PURE GELATO 900G", "INTEGRALMEDICA", 15.0, 60.0, 129.9),
    SyntheticProduct(9002, "OMEGA-3 CAPSULAS", "VITAFOR", 0.0, 20.0, 49.9),
    SyntheticProduct(9003, "CREATINA MONOHIDRATADA", "INTEGRALMEDICA", -2.0, 35.0, 89.9),
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


# ------------------------------------------------------------------ busca inteligente (§3.6)

def test_smart_search_non_contiguous_tokens_preserving_percent(search_api):
    assert codes(search_api.get(URL, params={"q": "whey 100% gelato"})) == [9001]


def test_smart_search_swapped_token_order(search_api):
    assert codes(search_api.get(URL, params={"q": "gelato whey"})) == [9001]


def test_smart_search_punctuation_separators(search_api):
    assert codes(search_api.get(URL, params={"q": "mistura p cha"})) == [3000]
    assert codes(search_api.get(URL, params={"q": "omega 3"})) == [9002]


def test_smart_search_description_plus_supplier(search_api):
    assert codes(search_api.get(URL, params={"q": "whey integralmedica"})) == [9001]


def test_smart_search_single_typo_tolerance_only_for_long_tokens(search_api):
    assert codes(search_api.get(URL, params={"q": "whey gealto"})) == [9001]
    assert codes(search_api.get(URL, params={"q": "xyzw"})) == []
    assert codes(search_api.get(URL, params={"q": "xyzww"})) == []


def test_smart_search_ranks_higher_relevance_first(search_api):
    """Prefixo/exato vem antes de tokens em ordem, que vem antes de ordem trocada, fornecedor e typo."""
    from src.modules.analytics.domain.cross_sell import CatalogEntry
    from src.modules.analytics.domain.product_search import build_search_index, search_products

    entries = [
        CatalogEntry(5, "GELATO PROTEICO", "OUTRO", 10.0, 50.0, 25.0, False),          # typo/sem whey -> fora
        CatalogEntry(4, "WHEY ISOLADO", "GELATO LABS", 10.0, 50.0, 25.0, False),       # 4: combinado c/ fornecedor
        CatalogEntry(3, "GELATO COM WHEY", "OUTRO", 10.0, 50.0, 25.0, False),          # 3: ordem trocada
        CatalogEntry(2, "WHEY 100% PURE GELATO", "OUTRO", 10.0, 50.0, 25.0, False),    # 2: tokens em ordem
        CatalogEntry(1, "SUPER WHEY GELATO 900G", "OUTRO", 10.0, 50.0, 25.0, False),   # 1: substring exata
        CatalogEntry(0, "WHEY GELATO PRIME", "OUTRO", 10.0, 50.0, 25.0, False),        # 0: prefixo exato
    ]
    index = build_search_index(entries)
    assert [e.code for e in search_products(index, "whey gelato")] == [0, 1, 2, 3, 4]


# ------------------------------------------------------------------ listagem completa do catálogo (§3.7)

CATALOG_BASE_KEYS = {"codigo", "descricao", "fornecedor", "estoque", "precoVenda"}
CATALOG_SEASONALITY_KEYS = {
    "forca",
    "amplitude",
    "mesPico",
    "mesVale",
    "faturamentoTotal",
    "motivoInsuficiencia",
}


def test_catalog_list_default_order_pagination_and_no_pii(search_api, monkeypatch):
    monthly_sales_calls = []
    monkeypatch.setattr(
        sales_repository,
        "fetch_monthly_sales",
        lambda cutoff: monthly_sales_calls.append(cutoff) or pd.DataFrame(),
    )

    response = search_api.get(CATALOG_URL)

    assert response.status_code == 200, response.text
    body = response.json()
    items = body["data"]
    assert len(items) == len(SEARCH_PRODUCTS)
    assert all(set(item.keys()) == (CATALOG_BASE_KEYS | CATALOG_SEASONALITY_KEYS) for item in items)
    assert all(item[key] is None for item in items for key in CATALOG_SEASONALITY_KEYS)

    # Ordem padrão: fornecedor A->Z, depois descrição A->Z, depois código
    expected_order = sorted(
        SEARCH_PRODUCTS,
        key=lambda p: (p.fornecedor.lower(), " ".join(p.descricao.lower().split()), p.codigo),
    )
    assert [item["codigo"] for item in items] == [p.codigo for p in expected_order]

    meta = body["meta"]
    assert (meta["page"], meta["limit"], meta["offset"], meta["totalItems"], meta["totalPages"]) == (
        1, 5000, 0, len(SEARCH_PRODUCTS), 1
    )
    assert meta["version"] == "1.1.0"
    assert "parametros" not in meta

    # Nunca dispara carga das cestas nem de vendas mensais
    assert monthly_sales_calls == []
    assert search_api.load_calls == []
    assert search_api.repository_calls.order_baskets_cutoffs == []
    assert analytics_cache.get_cache_status().state == "FRIO"


def test_catalog_list_filters_q_supplier_and_stock(search_api):
    # Filtro q com busca inteligente e com 1 caractere / vazio
    assert codes(search_api.get(CATALOG_URL, params={"q": "whey gealto"})) == [9001]
    assert len(codes(search_api.get(CATALOG_URL, params={"q": "   "}))) == len(SEARCH_PRODUCTS)
    assert 9001 in codes(search_api.get(CATALOG_URL, params={"q": "w"}))

    # Filtro supplier (case-insensitive)
    leao_codes = codes(search_api.get(CATALOG_URL, params={"supplier": "leao"}))
    assert leao_codes == [2100, 3000]

    # Filtro stockFilter
    out_codes = codes(search_api.get(CATALOG_URL, params={"stockFilter": "out_of_stock"}))
    assert out_codes == [9003, 9002]  # INTEGRALMEDICA (CREATINA) antes de VITAFOR (OMEGA-3)

    in_codes = codes(search_api.get(CATALOG_URL, params={"stockFilter": "in_stock"}))
    assert 9002 not in in_codes
    assert 9003 not in in_codes
    assert len(in_codes) == len(SEARCH_PRODUCTS) - 2

    # Combinação de filtros
    combo = codes(
        search_api.get(
            CATALOG_URL,
            params={"q": "creatina", "supplier": "INTEGRALMEDICA", "stockFilter": "out_of_stock"},
        )
    )
    assert combo == [9003]


def test_catalog_list_sorting_modes(search_api):
    # sortBy=sku desc
    sku_desc = codes(search_api.get(CATALOG_URL, params={"sortBy": "sku", "sortDir": "desc", "limit": 5}))
    assert sku_desc == sorted([p.codigo for p in SEARCH_PRODUCTS], reverse=True)[:5]

    # sortBy=product asc
    prod_asc = codes(search_api.get(CATALOG_URL, params={"sortBy": "product", "sortDir": "asc", "limit": 3}))
    assert prod_asc == [10010, 1001, 1002]

    # sortBy=stock desc (9001 tem estoque 15.0)
    stock_desc = codes(search_api.get(CATALOG_URL, params={"sortBy": "stock", "sortDir": "desc", "limit": 1}))
    assert stock_desc == [9001]

    # sortBy=price desc (9001 tem precoVenda 129.9)
    price_desc = codes(search_api.get(CATALOG_URL, params={"sortBy": "price", "sortDir": "desc", "limit": 2}))
    assert price_desc == [9001, 9003]

    # sortBy=relevance com q
    rel = codes(search_api.get(CATALOG_URL, params={"q": "cha", "sortBy": "relevance", "sortDir": "asc"}))
    assert rel == [1001, 1002, 2100, 10010, 3000]


def test_catalog_list_pagination_limit_and_offset(search_api):
    resp = search_api.get(CATALOG_URL, params={"sortBy": "sku", "sortDir": "asc", "limit": 2, "offset": 2})
    assert resp.status_code == 200
    body = resp.json()
    expected_skus = sorted(p.codigo for p in SEARCH_PRODUCTS)
    assert [item["codigo"] for item in body["data"]] == expected_skus[2:4]
    assert body["meta"]["page"] == 2
    assert body["meta"]["limit"] == 2
    assert body["meta"]["offset"] == 2
    assert body["meta"]["totalItems"] == len(SEARCH_PRODUCTS)

    assert search_api.get(CATALOG_URL, params={"limit": 5000}).status_code == 200


@pytest.mark.parametrize(
    "params, fields",
    [
        ({"limit": 0}, ["limit"]),
        ({"limit": 5001}, ["limit"]),
        ({"offset": -1}, ["offset"]),
        ({"stockFilter": "invalid"}, ["stockFilter"]),
        ({"sortBy": "invalid"}, ["sortBy"]),
        ({"sortDir": "invalid"}, ["sortDir"]),
        ({"q": "x" * 61}, ["q"]),
    ],
)
def test_catalog_list_invalid_params_is_400_xsl004(search_api, params, fields):
    response = search_api.get(CATALOG_URL, params=params)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "XSL-004"
    assert error["fields"] == fields


def test_catalog_list_include_seasonality_false_omits_sales_fetch(search_api, monkeypatch):
    monthly_sales_calls = []
    monkeypatch.setattr(
        sales_repository,
        "fetch_monthly_sales",
        lambda cutoff: monthly_sales_calls.append(cutoff) or pd.DataFrame(),
    )

    response = search_api.get(CATALOG_URL, params={"includeSeasonality": "false"})

    assert response.status_code == 200, response.text
    items = response.json()["data"]
    assert len(items) == len(SEARCH_PRODUCTS)
    assert all(item[key] is None for item in items for key in CATALOG_SEASONALITY_KEYS)
    assert monthly_sales_calls == []
    assert search_api.load_calls == []
    assert search_api.repository_calls.order_baskets_cutoffs == []


def test_catalog_list_include_seasonality_true_returns_summaries_without_baskets_or_pii(search_api, monkeypatch):
    df_forte = _build_synthetic_monthly_sales(
        sku=1001,
        start_year=2025,
        start_month=1,
        months_count=22,
        base_qty=100.0,
        peak_month=3,
        peak_factor=1.8,
        valley_month=9,
        valley_factor=0.5,
    )
    df_fraca = _build_synthetic_monthly_sales(
        sku=1002,
        start_year=2025,
        start_month=1,
        months_count=22,
        base_qty=100.0,
    )
    df_curto = _build_synthetic_monthly_sales(
        sku=2100,
        start_year=2026,
        start_month=1,
        months_count=8,
        base_qty=50.0,
    )
    combined_sales = pd.concat([df_forte, df_fraca, df_curto], ignore_index=True)

    monthly_sales_calls = []

    def fake_fetch_monthly_sales(cutoff):
        monthly_sales_calls.append(cutoff)
        return combined_sales.copy()

    monkeypatch.setattr(sales_repository, "fetch_monthly_sales", fake_fetch_monthly_sales)

    response = search_api.get(CATALOG_URL, params={"includeSeasonality": "true"})

    assert response.status_code == 200, response.text
    assert "customerCode" not in response.text
    assert len(monthly_sales_calls) == 1
    assert search_api.load_calls == []
    assert search_api.repository_calls.order_baskets_cutoffs == []
    assert analytics_cache.get_cache_status().state == "FRIO"

    by_sku = {item["codigo"]: item for item in response.json()["data"]}

    # Elegível forte (1001)
    forte = by_sku[1001]
    assert forte["forca"] == "FORTE"
    assert isinstance(forte["amplitude"], float) and forte["amplitude"] >= 0.40
    assert forte["mesPico"] == "Março"
    assert forte["mesVale"] == "Setembro"
    assert forte["faturamentoTotal"] == round(float(df_forte["net_revenue"].sum()), 2)
    assert forte["motivoInsuficiencia"] is None

    # Elegível fraca (1002) também é incluída
    fraca = by_sku[1002]
    assert fraca["forca"] == "FRACA"
    assert fraca["mesPico"] is not None
    assert fraca["mesVale"] is not None
    assert fraca["faturamentoTotal"] == round(float(df_fraca["net_revenue"].sum()), 2)
    assert fraca["motivoInsuficiencia"] is None

    # Histórico curto (<18 meses) (2100)
    curto = by_sku[2100]
    assert curto["forca"] == "INSUFICIENTE"
    assert curto["mesPico"] is None
    assert curto["mesVale"] is None
    assert curto["motivoInsuficiencia"] == "HISTORICO_CURTO"
    assert curto["faturamentoTotal"] == round(float(df_curto["net_revenue"].sum()), 2)

    # Sem histórico de vendas (9001)
    sem_vendas = by_sku[9001]
    assert sem_vendas["forca"] == "INSUFICIENTE"
    assert sem_vendas["amplitude"] == 0.0
    assert sem_vendas["mesPico"] is None
    assert sem_vendas["mesVale"] is None
    assert sem_vendas["faturamentoTotal"] == 0.0
    assert sem_vendas["motivoInsuficiencia"] == "HISTORICO_CURTO"

    # Segunda chamada reaproveita o cache leve de vendas mensais
    second_resp = search_api.get(CATALOG_URL, params={"includeSeasonality": "true", "q": "1001"})
    assert second_resp.status_code == 200
    assert len(monthly_sales_calls) == 1
