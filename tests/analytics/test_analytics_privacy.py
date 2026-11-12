"""
T-05 — Privacidade do módulo Analytics (P-070, CA-22, LGPD-03, LGPD-04).

Massa sintética (LGPD-11). Verifica, com `caplog` em nível DEBUG, que nem a carga nem as rotas
registram `customerCode`, SKUs recomendados, DataFrames, listas ou payloads, e que as respostas
só têm as chaves da allowlist do contrato (§3.3, §3.4, §4.1).
"""
import copy
import json
import logging

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import app
from src.modules.analytics.service import analytics_cache
from tests.analytics.conftest import build_snapshot_from_mass, install_snapshot
from tests.analytics.fixtures.synthetic_data import (
    CUSTOMER_ALREADY_BUYS_ALL,
    CUSTOMER_INACTIVE,
    CUSTOMER_WITH_CANDIDATES,
    EXPECTED_CUTOFF,
    FIXED_NOW_UTC,
    SKU_CHA_VERDE,
    SKU_GENGIBRE,
    SKU_HIBISCO,
    build_customer_contract_mass,
    build_product_contract_mass,
)

CUSTOMER_CODES = [CUSTOMER_WITH_CANDIDATES, CUSTOMER_INACTIVE, CUSTOMER_ALREADY_BUYS_ALL]
RECOMMENDED_SKUS = [SKU_GENGIBRE, SKU_HIBISCO]
FORBIDDEN_LOG_FRAGMENTS = (
    "order_idx", "customer_code", "customerCode", "dtype", "recomendacoes", "Sugerido porque",
    "GENGIBRE", "HIBISCO", "frozenset", "UsefulRule", "CatalogEntry",
)

TOP_KEYS = {"data", "meta"}
PAGED_META_KEYS = {"timestamp", "version", "dataReferencia", "page", "limit", "offset", "totalItems", "totalPages",
                   "parametros"}
EXPLANATION_KEYS = {"frequencia", "intensidade", "evidencia", "motivo"}
PRODUCT_ITEM_KEYS = {"codigo", "descricao", "fornecedor", "suporte", "confianca", "lift", "pedidosEmComum",
                     "estoqueAtual", "semEstoque", "margemNaoPositiva", "explicacao"}
CUSTOMER_ITEM_KEYS = {"codigo", "descricao", "fornecedor", "antecedentePrincipal", "qtdAntecedentesRelacionados",
                      "lift", "confianca", "pedidosEmComum", "margemUnitaria", "custoEstimado", "pontuacao", "motivo",
                      "diasDesdeUltimaCompra", "explicacao"}
FORBIDDEN_RESPONSE_KEY_FRAGMENTS = ("cliente", "customer", "pedido", "nome", "cnpj", "cpf", "uf", "data")

# As 7 chaves de `parametros` do contrato (§3.3, §4.1). `customerProfileDays` é nome de parâmetro de
# configuração (janela de 365 dias), não dado de cliente: é a única chave com "customer" admitida.
PARAMETER_KEYS = {
    "minLift", "minConfidence", "minPairOrders", "trivialItemSupport", "dormantDays", "customerProfileDays",
    "cacheTtlHours",
}
ALLOWED_PARAMETER_KEY = (".meta.parametros", "customerProfileDays")
HEALTH_DATA_KEYS = {"status", "estadoCache", "cacheCarregado", "baseSuficiente", "carregadoEm", "expiraEm",
                    "duracaoUltimaCargaMs", "contagens", "parametros"}
HEALTH_META_KEYS = {"timestamp", "version", "dataReferencia"}

# Loggers do próprio TestClient (httpx/httpcore registram a URL da requisição, que contém o código do
# cliente por contrato, DC-1). Só eles são ignorados: raiz, uvicorn, fastapi, starlette e src.* seguem vigiados.
TEST_CLIENT_LOGGERS = ("httpx", "httpcore")


@pytest.fixture(scope="module")
def customer_snapshot():
    return build_snapshot_from_mass(build_customer_contract_mass())[0]


@pytest.fixture(scope="module")
def product_snapshot():
    return build_snapshot_from_mass(build_product_contract_mass())[0]


@pytest.fixture
def client():
    return TestClient(app)


def _is_test_client_record(record) -> bool:
    return any(record.name == name or record.name.startswith(f"{name}.") for name in TEST_CLIENT_LOGGERS)


def _assert_parameters_are_scalar_numbers(parameters):
    """`parametros` tem exatamente as 7 chaves do contrato e só valores numéricos (nenhum dado de cliente)."""
    assert set(parameters) == PARAMETER_KEYS
    for key, value in parameters.items():
        assert isinstance(value, (int, float)) and not isinstance(value, bool), f"parametros.{key} = {value!r}"


def _assert_logs_are_clean(caplog):
    for record in caplog.records:
        if _is_test_client_record(record):
            continue
        message = record.getMessage()
        for code in CUSTOMER_CODES:
            assert str(code) not in message, f"customerCode no log: {message}"
        for sku in RECOMMENDED_SKUS:
            assert str(sku) not in message, f"SKU recomendado no log: {message}"
        for fragment in FORBIDDEN_LOG_FRAGMENTS:
            assert fragment not in message, f"payload/DataFrame no log: {message}"
        args = record.args if isinstance(record.args, tuple) else (record.args,)
        for arg in args:
            assert not isinstance(arg, (pd.DataFrame, pd.Series, list, dict, set, frozenset)), (
                f"objeto não escalar no log: {type(arg).__name__}"
            )


def _all_keys(value, path=""):
    """Gera (caminho, chave) para todas as chaves de objetos aninhados."""
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key
            yield from _all_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            yield from _all_keys(child, f"{path}[]")


# ------------------------------------------------------------------ logs (LGPD-04, CA-22)

def test_load_logs_only_aggregate_counts(caplog, monkeypatch, repository_patcher):
    monkeypatch.setattr(analytics_cache, "_utc_now", lambda: FIXED_NOW_UTC)
    order_baskets, catalog = build_customer_contract_mass()
    calls = repository_patcher(order_baskets, catalog)
    caplog.set_level(logging.DEBUG)

    analytics_cache.get_snapshot()

    assert calls.order_baskets_cutoffs == [EXPECTED_CUTOFF]
    assert caplog.records, "a carga deve registrar ao menos contagens e duração (DA-03)"
    _assert_logs_are_clean(caplog)


def test_customer_route_logs_nothing_about_the_customer(caplog, client, monkeypatch, customer_snapshot):
    install_snapshot(monkeypatch, customer_snapshot)
    caplog.set_level(logging.DEBUG)

    for code in CUSTOMER_CODES:
        assert client.get(f"/api/v1/analytics/cross-sell/customer/{code}").status_code == 200
    assert client.get("/api/v1/analytics/cross-sell/customer/88888").status_code == 404

    _assert_logs_are_clean(caplog)


def test_product_route_logs_nothing_about_recommendations(caplog, client, monkeypatch, customer_snapshot):
    install_snapshot(monkeypatch, customer_snapshot)
    caplog.set_level(logging.DEBUG)

    assert client.get(f"/api/v1/analytics/cross-sell/product/{SKU_CHA_VERDE}").status_code == 200

    _assert_logs_are_clean(caplog)


# ------------------------------------------------------------------ allowlist de campos (LGPD-03)

def test_customer_response_has_only_allowlisted_keys(client, monkeypatch, customer_snapshot):
    install_snapshot(monkeypatch, customer_snapshot)

    response = client.get(f"/api/v1/analytics/cross-sell/customer/{CUSTOMER_WITH_CANDIDATES}")
    body = response.json()

    assert set(body) == TOP_KEYS
    assert set(body["data"]) == {"recomendacoes"}
    assert set(body["meta"]) == PAGED_META_KEYS | {"motivoVazio"}
    assert body["data"]["recomendacoes"], "a massa tem candidatos para este cliente"
    for item in body["data"]["recomendacoes"]:
        assert set(item) == CUSTOMER_ITEM_KEYS
        assert set(item["antecedentePrincipal"]) == {"codigo", "descricao"}
        assert set(item["explicacao"]) == EXPLANATION_KEYS
    assert str(CUSTOMER_WITH_CANDIDATES) not in response.text
    assert "customerCode" not in response.text


def test_product_response_has_only_allowlisted_keys_and_no_customer_data(client, monkeypatch, product_snapshot):
    install_snapshot(monkeypatch, product_snapshot)

    body = client.get(f"/api/v1/analytics/cross-sell/product/{SKU_CHA_VERDE}").json()

    assert set(body) == TOP_KEYS
    assert set(body["data"]) == {"produto", "recomendacoes"}
    assert set(body["data"]["produto"]) == {"codigo", "descricao", "fornecedor"}
    assert set(body["meta"]) == PAGED_META_KEYS
    _assert_parameters_are_scalar_numbers(body["meta"]["parametros"])
    for item in body["data"]["recomendacoes"]:
        assert set(item) == PRODUCT_ITEM_KEYS
        assert set(item["explicacao"]) == EXPLANATION_KEYS
    for path, key in _all_keys(body):
        lowered = key.lower()
        if key in {"dataReferencia"}:
            continue
        if (path, key) == ALLOWED_PARAMETER_KEY:
            continue
        for fragment in FORBIDDEN_RESPONSE_KEY_FRAGMENTS:
            if fragment == "pedido" and key == "pedidosEmComum":
                continue
            if fragment == "data" and path == "":
                continue
            assert fragment not in lowered, f"chave proibida {path}.{key}"


def test_health_exposes_no_customer_data(client, monkeypatch, customer_snapshot):
    install_snapshot(monkeypatch, customer_snapshot)

    response = client.get("/api/v1/analytics/health")
    body = response.json()

    assert set(body["data"]) == HEALTH_DATA_KEYS
    assert set(body["meta"]) == HEALTH_META_KEYS
    assert set(body["data"]["contagens"]) == {"cestasValidas", "regrasUteis", "itensTriviais", "skusComCesta"}
    _assert_parameters_are_scalar_numbers(body["data"]["parametros"])
    for code in CUSTOMER_CODES:
        assert str(code) not in response.text
    without_profile_parameter = copy.deepcopy(body)
    del without_profile_parameter["data"]["parametros"]["customerProfileDays"]
    serialized = json.dumps(without_profile_parameter).lower()
    assert "customer" not in serialized
    assert "cliente" not in serialized
