"""
Testes de contrato e endpoints da API de Tendência de Vendas (T-10).
Valida contrato 1.0.0, envelope data/meta, rotas health, reload, listagem e detalhe.
"""
from datetime import datetime, timezone, date
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from src.api import app
from tests.sales_trend.trend_sample import (
    FIRST_SALE_DATE,
    get_active_catalog_sample,
    get_raw_sales_rows_sample,
)

client = TestClient(app)


def _setup_mock_snapshot():
    from src.modules.sales_trend.domain.sales_trend import (
        TrendCatalogEntry,
        build_monthly_sales,
    )
    from src.modules.sales_trend.domain.search_text import normalize_text
    from src.modules.sales_trend.domain.suppliers import build_supplier_index
    from src.modules.sales_trend.service.sales_trend_cache import SalesTrendSnapshot

    raw_cat = get_active_catalog_sample()
    catalog = {
        k: TrendCatalogEntry(k, v["descricao"], v["fornecedor"], normalize_text(v["descricao"]))
        for k, v in raw_cat.items()
    }
    raw_rows = get_raw_sales_rows_sample()
    ms = build_monthly_sales(
        [(r.sku, r.year_month, r.quantity, r.revenue) for r in raw_rows],
        set(catalog.keys()),
        FIRST_SALE_DATE,
    )
    supp_index = build_supplier_index(catalog)

    ref_date = date(2026, 11, 9)
    return SalesTrendSnapshot(
        reference_date=ref_date,
        last_covered_day=date(2026, 11, 8),
        loaded_at=datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc),
        monthly_sales=ms,
        catalog=catalog,
        supplier_index=supp_index,
        counts={"active_catalog_skus": len(catalog)},
    )


def test_health_check_endpoint():
    """Valida endpoint GET /api/v1/sales-trend/health."""
    response = client.get("/api/v1/sales-trend/health")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "status" in data["data"]


def test_get_trend_products_contract_format():
    """Valida formato da resposta por produto conforme contrato 1.0.0."""
    snap = _setup_mock_snapshot()
    with patch("src.modules.sales_trend.service.sales_trend_service.get_snapshot", return_value=snap):
        response = client.get("/api/v1/sales-trend?baseMonth=2026-10&metric=quantity")
        assert response.status_code == 200
        json_data = response.json()

        assert "data" in json_data
        assert "meta" in json_data
        assert isinstance(json_data["data"], list)

        # Valida campos da primeira linha
        if json_data["data"]:
            item = json_data["data"][0]
            assert "codigo" in item
            assert "descricao" in item
            assert "janelas" in item
            assert isinstance(item["janelas"], list)
            assert len(item["janelas"]) == 4
            assert item["janelas"][0]["meses"] == 1
            assert "ativo" not in item, "Campo 'ativo' não deve existir (P-072.2)"

        # Valida metadados
        meta = json_data["meta"]
        assert meta["version"] == "1.0.0"
        assert meta["mesBase"] == "2026-10"
        assert "janelas" in meta
        assert isinstance(meta["janelas"], list)
        assert len(meta["janelas"]) == 4
        assert meta["janelas"][0]["meses"] == 1
        assert "atual" in meta["janelas"][0]
        assert "anterior" in meta["janelas"][0]
        assert "totaisPorVisao" in meta
        assert "todos" in meta["totaisPorVisao"]
        assert "parametros" in meta
        assert "total" in meta
        assert isinstance(meta["total"]["janelas"], list)


def test_get_trend_suppliers_contract_format():
    """Valida formato da resposta por fornecedor conforme contrato 1.0.0."""
    snap = _setup_mock_snapshot()
    with patch("src.modules.sales_trend.service.sales_trend_service.get_snapshot", return_value=snap):
        response = client.get("/api/v1/sales-trend?baseMonth=2026-10&groupBy=supplier")
        assert response.status_code == 200
        json_data = response.json()

        assert "data" in json_data
        if json_data["data"]:
            item = json_data["data"][0]
            assert "fornecedorChave" in item
            assert "fornecedor" in item
            assert "qtdProdutos" in item
            assert "janelas" in item
            assert isinstance(item["janelas"], list)
            assert len(item["janelas"]) == 4


def test_get_supplier_products_detail_format():
    """Valida detalhe de produtos de fornecedor."""
    snap = _setup_mock_snapshot()
    with patch("src.modules.sales_trend.service.sales_trend_service.get_snapshot", return_value=snap):
        key_alfa = next(k for k in snap.supplier_index.keys() if "alfa" in k)
        response = client.get(f"/api/v1/sales-trend/supplier-products?supplierKey={key_alfa}&baseMonth=2026-10")
        assert response.status_code == 200
        json_data = response.json()

        assert "data" in json_data
        assert "meta" in json_data
        assert isinstance(json_data["meta"]["fornecedor"], dict)
        assert json_data["meta"]["fornecedor"]["fornecedor"] == snap.supplier_index[key_alfa].display_name
        assert json_data["meta"]["fornecedor"]["fornecedorChave"] == key_alfa
        if json_data["data"]:
            item = json_data["data"][0]
            assert "codigo" in item
            assert "janelas" in item
            assert isinstance(item["janelas"], list)
            assert len(item["janelas"]) == 4
            assert "contribuicaoPp" in item["janelas"][0]
