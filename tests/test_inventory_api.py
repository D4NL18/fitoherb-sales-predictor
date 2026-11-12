"""
Suíte TDD (fase vermelha): Contrato REST 2.0.0 da API de Estoque e Compras (/api/v1/inventory).

Regras cobertas: P-053 (mínimo/máximo e validação INV-001), A2 (INV-002), P-054, P-055,
P-056 (revogação de parâmetros/campos antigos e novas colunas CSV), P-047.1 e DA-11 (segurança 500 e slug CSV).
Contrato: .agents/docs/api_contracts/inventory.md (versão 2.0.0).
"""
import re
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import app
import src.modules.inventory.api.router as inv_router
import src.modules.inventory.service.inventory_service as inv_service

EXPECTED_CSV_COLUMNS = [
    "Código",
    "Descrição",
    "EAN",
    "Fornecedor",
    "Tipo/Linha",
    "Estoque Físico Atual",
    "Venda Média Diária (VMD)",
    "Dias de Cobertura",
    "Lead Time (Dias)",
    "Estoque Mínimo (un)",
    "Estoque Máximo (un)",
    "Qtd Sugerida de Compra",
    "Último Custo Real (R$)",
    "Preço de Venda (R$)",
    "Investimento Total Sugerido (R$)",
    "Status Operacional",
    "Curva ABC",
]

REMOVED_CSV_COLUMNS = {
    "Estoque de Segurança",
    "Ponto de Reposição (ROP)",
    "Estoque Ideal",
    "Demanda Teórica Plena",
    "Limitado por Espaço Físico",
    "Teto Físico de Compra",
}

REMOVED_ITEM_KEYS = {
    "estoqueSeguranca",
    "rop",
    "estoqueIdeal",
    "estoqueIdealTeorico",
    "qtdSugeridaTeorica",
    "limitadoPorEspaco",
    "tetoCompraFisica",
    "desvioPadraoDemanda",
}

REMOVED_CONFIG_KEYS = {
    "targetCoverageDays",
    "serviceLevel",
    "budgetLimit",
    "maxPurchaseVariationPct",
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_inventory_data(monkeypatch):
    """Injeta os 4 SKUs do exemplo canônico do contrato 2.0.0 (seções 5.2 e 6.2) em memória."""
    catalog_df = pd.DataFrame([
        {
            "Codigo": 101,
            "Descricao": "EXTRATO PROPOLIS APISFLORA",
            "EAN": "7891234567890",
            "Fornecedor": "APIS FLORA",
            "Tipo": "EXTRATOS",
            "Estoque": 10.0,
            "Pc.Ultimo Custo": 15.0,
            "Pc.Venda": 25.0,
        },
        {
            "Codigo": 102,
            "Descricao": "VITAMINA C HERBARIUM",
            "EAN": "7899876543210",
            "Fornecedor": "HERBARIUM",
            "Tipo": "VITAMINAS",
            "Estoque": 50.0,
            "Pc.Ultimo Custo": 10.0,
            "Pc.Venda": 20.0,
        },
        {
            "Codigo": 104,
            "Descricao": "OMEGA 3 CATARINENSE",
            "EAN": "7891112223341",
            "Fornecedor": "CATARINENSE",
            "Tipo": "SUPLEMENTOS",
            "Estoque": 90.0,
            "Pc.Ultimo Custo": 12.0,
            "Pc.Venda": 22.0,
        },
        {
            "Codigo": 103,
            "Descricao": "CHA VERDE CATARINENSE",
            "EAN": "7891112223334",
            "Fornecedor": "CATARINENSE",
            "Tipo": "CHAS",
            "Estoque": 300.0,
            "Pc.Ultimo Custo": 5.0,
            "Pc.Venda": 12.0,
        },
    ])

    dates = pd.date_range(end="2026-09-30", periods=60, freq="D")
    sales_data = []
    for d in dates:
        # 101: VMD 2.0, receita 3000 (Curva A)
        sales_data.append({"Data": d, "Cod Produto": 101, "Qtd Venda": 2.0, "Valor Venda": 50.0})
        # 102: VMD 2.0, receita 540 (Curva B)
        sales_data.append({"Data": d, "Cod Produto": 102, "Qtd Venda": 2.0, "Valor Venda": 9.0})
        # 104: VMD 2.0, receita 60 (Curva C)
        sales_data.append({"Data": d, "Cod Produto": 104, "Qtd Venda": 2.0, "Valor Venda": 1.0})
    sales_df = pd.DataFrame(sales_data)

    monkeypatch.setattr(inv_service, "get_base_inventory_data", lambda: (catalog_df, sales_df))
    monkeypatch.setattr(inv_service, "get_inventory_catalog", lambda: catalog_df)
    monkeypatch.setattr(
        inv_service,
        "get_inventory_velocity",
        lambda window_days: inv_service.calculate_sales_velocity(sales_df, window_days=window_days),
    )
    inv_service._INVENTORY_CACHE.clear()
    inv_service._VELOCITY_CACHE.clear()


# ---------------------------------------------------------------------------
# GET /health, /config e /suppliers
# ---------------------------------------------------------------------------
def test_inventory_health_check(client):
    response = client.get("/api/v1/inventory/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "fitoherb-inventory-api"}


def test_inventory_config_contract_v2(client):
    """Seção 3.1 do contrato 2.0.0: faixas da tela com minCoverageDays/maxCoverageDays e sem chaves revogadas."""
    response = client.get("/api/v1/inventory/config")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["version"] == "2.0.0"

    data = body["data"]
    assert set(data.keys()) == {"historyWindowDays", "leadTimeDays", "minCoverageDays", "maxCoverageDays"}
    assert not (REMOVED_CONFIG_KEYS & set(data.keys()))
    assert data["historyWindowDays"] == {"default": 60, "min": 15, "max": 180, "step": 15}
    assert data["leadTimeDays"] == {"default": 15, "min": 1, "max": 60, "step": 1}
    assert data["minCoverageDays"] == {"default": 30, "min": 5, "max": 120, "step": 5}
    assert data["maxCoverageDays"] == {"default": 60, "min": 10, "max": 180, "step": 5}


def test_inventory_suppliers(client):
    response = client.get("/api/v1/inventory/suppliers")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["version"] == "2.0.0"
    suppliers = [s["fornecedor"] for s in body["data"]]
    assert suppliers[0] == "TODOS"
    assert {"APIS FLORA", "HERBARIUM", "CATARINENSE"}.issubset(set(suppliers))


# ---------------------------------------------------------------------------
# POST /predict — Caminho feliz, eco da política e contrato 2.0.0
# ---------------------------------------------------------------------------
def test_inventory_predict_default_policy_and_contract_v2(client):
    """Body vazio {} aplica padrão 30/60/15/60, ecoa `politica` e retorna itens sem campos revogados."""
    response = client.post("/api/v1/inventory/predict", json={})
    assert response.status_code == 200
    body = response.json()

    assert body["meta"]["version"] == "2.0.0"
    assert isinstance(body["meta"]["executionTimeMs"], (int, float))

    data = body["data"]
    assert data["politica"] == {
        "historyWindowDays": 60,
        "leadTimeDays": 15,
        "minCoverageDays": 30,
        "maxCoverageDays": 60,
    }

    kpis = data["kpis"]
    assert "skusLimitadosPorEspaco" not in kpis
    assert kpis["totalSkusAnalisados"] == 4
    assert kpis["skusEmRupturaCritica"] == 1
    assert kpis["skusNecessitamReposicao"] == 1
    assert kpis["skusEstoqueSaudavel"] == 1
    assert kpis["skusEmOverstock"] == 1
    assert kpis["investimentoTotalSugerido"] == pytest.approx(2350.0)
    assert kpis["capitalImobilizadoOverstock"] == pytest.approx(1500.0)

    produtos = data["produtos"]
    assert len(produtos) == 4
    for item in produtos:
        assert not (REMOVED_ITEM_KEYS & set(item.keys()))
        assert isinstance(item["estoqueMinimo"], int)
        assert isinstance(item["estoqueMaximo"], int)

    by_sku = {p["codigo"]: p for p in produtos}
    assert by_sku[101]["status"] == "CRITICAL_STOCKOUT"
    assert by_sku[101]["statusLabel"] == "Ruptura Iminente"
    assert (by_sku[101]["estoqueMinimo"], by_sku[101]["estoqueMaximo"], by_sku[101]["qtdSugeridaCompra"]) == (60, 120, 110)

    assert by_sku[102]["status"] == "REORDER_NEEDED"
    assert by_sku[102]["statusLabel"] == "Abaixo do Mínimo"
    assert (by_sku[102]["estoqueMinimo"], by_sku[102]["estoqueMaximo"], by_sku[102]["qtdSugeridaCompra"]) == (60, 120, 70)

    assert by_sku[104]["status"] == "HEALTHY"
    assert by_sku[104]["statusLabel"] == "Estoque Saudável"
    assert by_sku[104]["qtdSugeridaCompra"] == 0

    assert by_sku[103]["status"] == "OVERSTOCK"
    assert by_sku[103]["statusLabel"] == "Acima do Máximo"
    assert (by_sku[103]["estoqueMinimo"], by_sku[103]["estoqueMaximo"], by_sku[103]["qtdSugeridaCompra"]) == (0, 0, 0)


def test_inventory_predict_custom_policy_and_supplier_filter(client):
    """CA-05 e CA-10: Dias 20/45 + filtro de fornecedor APIS FLORA."""
    payload = {
        "historyWindowDays": 60,
        "minCoverageDays": 20,
        "maxCoverageDays": 45,
        "leadTimeDays": 10,
        "fornecedor": "APIS FLORA",
    }
    response = client.post("/api/v1/inventory/predict", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["politica"] == {
        "historyWindowDays": 60,
        "leadTimeDays": 10,
        "minCoverageDays": 20,
        "maxCoverageDays": 45,
    }
    assert len(data["produtos"]) == 1
    p101 = data["produtos"][0]
    assert p101["fornecedor"] == "APIS FLORA"
    assert p101["estoqueMinimo"] == 40
    assert p101["estoqueMaximo"] == 90
    assert p101["qtdSugeridaCompra"] == 80


def test_ca_p056_02_revoked_parameters_are_ignored_without_effect(client):
    """CA-P056-02 / P-056.4: parâmetros revogados enviados por cliente antigo são ignorados (extra='ignore')."""
    baseline = client.post("/api/v1/inventory/predict", json={}).json()["data"]
    legacy_payload = {
        "targetCoverageDays": 15,
        "serviceLevel": 0.99,
        "budgetLimit": 100.0,
        "maxPurchaseVariationPct": 20.0,
    }
    response = client.post("/api/v1/inventory/predict", json=legacy_payload)
    assert response.status_code == 200
    assert response.json()["data"] == baseline


# ---------------------------------------------------------------------------
# POST /predict — Validação 422 (INV-001, INV-002, faixas e tipos)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "min_days,max_days",
    [(60, 60), (50, 45)],
    ids=["CA-P053-04-60/60", "CA-P053-04-50/45"],
)
def test_inventory_predict_rejects_max_not_greater_than_min_with_inv001(client, min_days, max_days):
    response = client.post(
        "/api/v1/inventory/predict",
        json={"minCoverageDays": min_days, "maxCoverageDays": max_days},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert len(detail) == 1
    err = detail[0]
    assert err["type"] == "INV-001"
    assert err["loc"] == ["body", "maxCoverageDays"]
    assert err["msg"] == (
        f"Dias Máximo (maxCoverageDays = {max_days}) deve ser maior que "
        f"Dias Mínimo (minCoverageDays = {min_days})."
    )
    assert err["ctx"] == {"minCoverageDays": min_days, "maxCoverageDays": max_days}


@pytest.mark.parametrize(
    "lead_time,max_days",
    [(45, 40), (40, 40)],
    ids=["A2-lead45-max40", "A2-lead40-max40"],
)
def test_inventory_predict_rejects_lead_time_not_below_max_with_inv002(client, lead_time, max_days):
    response = client.post(
        "/api/v1/inventory/predict",
        json={"minCoverageDays": 20, "maxCoverageDays": max_days, "leadTimeDays": lead_time},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert len(detail) == 1
    err = detail[0]
    assert err["type"] == "INV-002"
    assert err["loc"] == ["body", "leadTimeDays"]
    assert err["msg"] == (
        f"Lead Time (leadTimeDays = {lead_time}) deve ser menor que "
        f"Dias Máximo (maxCoverageDays = {max_days})."
    )
    assert err["ctx"] == {"leadTimeDays": lead_time, "maxCoverageDays": max_days}


@pytest.mark.parametrize(
    "payload,expected_type,expected_loc",
    [
        ({"minCoverageDays": 0}, "greater_than_equal", ["body", "minCoverageDays"]),
        ({"minCoverageDays": 181}, "less_than_equal", ["body", "minCoverageDays"]),
        ({"maxCoverageDays": 1}, "greater_than_equal", ["body", "maxCoverageDays"]),
        ({"maxCoverageDays": 366}, "less_than_equal", ["body", "maxCoverageDays"]),
        ({"minCoverageDays": 30.5}, "int_from_float", ["body", "minCoverageDays"]),
        ({"maxCoverageDays": 60.5}, "int_from_float", ["body", "maxCoverageDays"]),
    ],
    ids=[
        "min-abaixo-1",
        "min-acima-180",
        "max-abaixo-2",
        "max-acima-365",
        "min-float",
        "max-float",
    ],
)
def test_inventory_predict_rejects_out_of_range_and_float_values(client, payload, expected_type, expected_loc):
    response = client.post("/api/v1/inventory/predict", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(err["type"] == expected_type and err["loc"] == expected_loc for err in detail)
    # Quando o campo de referência falha por tipo/faixa, a regra cruzada não deve cascatear
    assert all(not str(err["type"]).startswith("INV-") for err in detail)


# ---------------------------------------------------------------------------
# POST /export-csv — Colunas 2.0.0, paridade com /predict e sanitização do nome
# ---------------------------------------------------------------------------
def test_inventory_export_csv_columns_and_parity_with_predict(client):
    """CA-P056-04 e P-056.6: cabeçalho exato de 17 colunas, sem colunas revogadas e valores iguais a /predict."""
    payload = {"historyWindowDays": 60, "minCoverageDays": 20, "maxCoverageDays": 45, "leadTimeDays": 10}
    predict_res = client.post("/api/v1/inventory/predict", json=payload)
    csv_res = client.post("/api/v1/inventory/export-csv", json=payload)

    assert predict_res.status_code == 200
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]

    raw_text = csv_res.content.decode("utf-8")
    assert raw_text.startswith("\ufeff")
    lines = [line for line in raw_text.lstrip("\ufeff").splitlines() if line.strip()]
    header = lines[0].split(";")
    assert header == EXPECTED_CSV_COLUMNS
    assert not (REMOVED_CSV_COLUMNS & set(header))

    produtos = predict_res.json()["data"]["produtos"]
    assert len(lines) - 1 == len(produtos)
    first_row = dict(zip(header, lines[1].split(";")))
    assert int(first_row["Código"]) == produtos[0]["codigo"]
    assert int(first_row["Estoque Mínimo (un)"]) == produtos[0]["estoqueMinimo"]
    assert int(first_row["Estoque Máximo (un)"]) == produtos[0]["estoqueMaximo"]
    assert int(first_row["Qtd Sugerida de Compra"]) == produtos[0]["qtdSugeridaCompra"]
    assert first_row["Status Operacional"] == produtos[0]["statusLabel"]


def test_inventory_export_csv_filename_sanitization(client):
    """DA-11: slug do fornecedor no Content-Disposition deve conter apenas [a-z0-9_]."""
    res_all = client.post("/api/v1/inventory/export-csv", json={"fornecedor": "TODOS"})
    disp_all = res_all.headers.get("content-disposition", "")
    assert re.match(r'^attachment; filename="fitoherb_plano_compras_\d{8}_\d{6}\.csv"$', disp_all)

    res_sup = client.post("/api/v1/inventory/export-csv", json={"fornecedor": "APIS FLORA / LTDA; rm -rf"})
    disp_sup = res_sup.headers.get("content-disposition", "")
    assert re.match(
        r'^attachment; filename="fitoherb_plano_compras_[a-z0-9_]+_\d{8}_\d{6}\.csv"$',
        disp_sup,
    )


# ---------------------------------------------------------------------------
# DA-11 — Erros 500 não vazam detalhes internos (str(e) / SQL)
# ---------------------------------------------------------------------------
def test_inventory_predict_500_does_not_leak_internal_exception(client, monkeypatch):
    def boom(_request):
        raise RuntimeError("segredo interno sql")

    monkeypatch.setattr(inv_router, "execute_inventory_prediction", boom)
    response = client.post("/api/v1/inventory/predict", json={})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "segredo interno sql" not in detail
    assert detail == "Não foi possível calcular a previsão de estoque. Tente novamente em instantes."


def test_inventory_export_csv_500_does_not_leak_internal_exception(client, monkeypatch):
    def boom(_request):
        raise RuntimeError("segredo interno sql")

    monkeypatch.setattr(inv_router, "generate_inventory_csv", boom)
    response = client.post("/api/v1/inventory/export-csv", json={})
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "segredo interno sql" not in detail
    assert detail == "Não foi possível gerar o arquivo CSV do plano de compras. Tente novamente em instantes."


def test_inventory_suppliers_500_does_not_leak_internal_exception(client, monkeypatch):
    def boom():
        raise RuntimeError("segredo interno sql")

    monkeypatch.setattr(inv_router, "get_inventory_suppliers", boom)
    response = client.get("/api/v1/inventory/suppliers")
    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "segredo interno sql" not in detail
    assert detail == "Não foi possível consultar o catálogo de fornecedores. Tente novamente em instantes."
