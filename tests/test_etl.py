"""
Testes unitários para o módulo ETL (US-01, P-001 a P-004).
"""
import io
from unittest.mock import patch
import pandas as pd
import pytest

from src.etl import (
    load_catalog,
    load_catalog_from_database,
    normalize_products_dataframe,
    filter_whitelist,
    clean_sales_data,
    deduplicate_orders,
    remove_outliers,
    run_etl_pipeline,
)



@pytest.fixture
def sample_catalog_csv():
    content = (
        "FITOHERB NORDESTE DISTRIBUIDORA LTDA;\n"
        "Lista de preco simplificada/alfabetica;\n"
        "\n"
        "LAURO DE FREITAS,BA - Usuario:IVETE CNPJ:02.125.297/0001-47 Data:28/09/2026 Arquivo:Rel.TXT;\n"
        "Código;Descrição;Fornec/Marca;Und;Preço;Sit;Tipo;\n"
        "500101;COLAGENO 300G;FITONUTRI ;UN;49,90;A;LINHA A;\n"
        "500102;CREATINA 300G;VITA LIFE ;UN;79,90;A;LINHA B;\n"
        "500103;OMEGA 3 120 CAPS;NATURALIS;UN;45,00;B;LINHA C;\n"
    )
    return io.StringIO(content)


@pytest.fixture
def sample_sales_df():
    data = {
        "Data": [
            "2026-01-10 00:00:00.000",
            "2026-01-10 00:00:00.000",
            "2026-01-10 00:00:00.000",
            "2026-01-11 00:00:00.000",
            "2026-01-11 00:00:00.000",
            "2026-01-12 00:00:00.000",
            "2026-01-12 00:00:00.000",
            "2026-01-13 00:00:00.000",
        ],
        "Numero Nota": [1, 1, 1, 2, 2, 3, 3, 4],
        "Pedido": [101, 101, 101, 102, 102, 103, 103, 104],
        "Cod Cliente": [1, 1, 1, 2, 2, 3, 3, 4],
        "Cliente": ["A", "A", "A", "B", "B", "C", "C", "D"],
        "Cidade": ["SALVADOR", "SALVADOR", "SALVADOR", "FEIRA", "FEIRA", "ARACAJU", "ARACAJU", "MACEIO"],
        "UF": ["BA", "BA", "BA", "BA", "BA", "SE", "SE", "AL"],
        "Operação": [
            "VENDA",
            "VENDA",
            "BONIFICACAO",  # deve ser descartado
            "VENDA",
            "VENDA",
            "VENDA",
            "VENDA",
            "VENDA",
        ],
        "Cod Produto": [
            500101,
            500101,  # duplicado no mesmo pedido (deve agregar)
            500102,
            999999,  # fora do catalogo (deve ser expurgado pela whitelist)
            500102,
            500103,
            500103,  # brinde com preco < 0.40 * tabela
            500101,
        ],
        "Produto": ["COLAGENO", "COLAGENO", "CREATINA", "OUTRO", "CREATINA", "OMEGA", "OMEGA", "COLAGENO"],
        "EAN": ["789001", "789001", "789002", "789999", "789002", "789003", "789003", "789001"],
        "Fornecedor": ["FITO", "FITO", "VITA", "OUT", "VITA", "NAT", "NAT", "FITO"],
        "Cod Vendedor": [10, 10, 10, 11, 11, 12, 12, 10],
        "Vendedor": ["CARLOS", "CARLOS", "CARLOS", "ANA", "ANA", "MARCOS", "MARCOS", "CARLOS"],
        "Cod Promocao": [0, 0, 0, 0, 0, 0, 0, 0],
        "Promoção": ["", "", "", "", "", "", "", ""],
        "Valor Venda": [
            49.90,
            49.90,
            0.00,
            79.90,
            79.90,
            45.00,
            1.00,   # preco praticado = 1.00 / 1.0 = 1.00 < 0.40 * 45.00 (18.0) -> descartar
            10000.0,
        ],
        "Qtd Venda": [
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1000.0, # outlier extremo
        ],
    }
    return pd.DataFrame(data)


def test_load_catalog(sample_catalog_csv):
    """Testa regra P-001: Leitura do catálogo, tipos sanitizados e strip."""
    df_cat = load_catalog(sample_catalog_csv)
    assert len(df_cat) == 3
    assert df_cat["Código"].dtype == "int64"
    assert df_cat["Preço"].dtype == "float64"
    assert df_cat.loc[df_cat["Código"] == 500101, "Preço"].iloc[0] == 49.90
    assert df_cat.loc[df_cat["Código"] == 500101, "Fornec/Marca"].iloc[0] == "FITONUTRI"
    assert df_cat.loc[df_cat["Código"] == 500101, "Sit"].iloc[0] == "A"


def test_clean_sales_and_whitelist(sample_catalog_csv, sample_sales_df):
    """Testa regras P-001 a P-003: Whitelist, filtros de operação e remoção de brindes."""
    df_cat = load_catalog(sample_catalog_csv)
    df_clean = clean_sales_data(sample_sales_df, df_cat)

    # Não deve conter BONIFICACAO
    assert (df_clean["Operação"] == "VENDA").all()
    # Não deve conter SKU 999999 fora do catálogo
    assert 999999 not in df_clean["Cod Produto"].values
    # Não deve conter brinde a R$ 1.00
    assert not ((df_clean["Cod Produto"] == 500103) & (df_clean["Valor Venda"] == 1.00)).any()


def test_deduplication(sample_catalog_csv, sample_sales_df):
    """Testa regra P-004: Deduplicação de SKU no mesmo pedido somando quantidade e valor."""
    df_cat = load_catalog(sample_catalog_csv)
    df_clean = clean_sales_data(sample_sales_df, df_cat)
    df_dedup = deduplicate_orders(df_clean)

    # Pedido 101 tinha duas linhas de 500101 com qtd=1 e valor=49.90 cada
    row = df_dedup[(df_dedup["Pedido"] == 101) & (df_dedup["Cod Produto"] == 500101)]
    assert len(row) == 1
    assert row["Qtd Venda"].iloc[0] == 2.0
    assert row["Valor Venda"].iloc[0] == 99.80


def test_remove_outliers():
    """Testa regra P-004: Expurgo de pedidos acima do percentil 99.5."""
    records = []
    # 200 pedidos normais de 2 unidades
    for p in range(1, 201):
        records.append({"Pedido": p, "Cod Produto": 500101, "Qtd Venda": 2.0, "Valor Venda": 100.0})
    # 1 pedido anômalo com 50.000 unidades
    records.append({"Pedido": 999, "Cod Produto": 500101, "Qtd Venda": 50000.0, "Valor Venda": 2500000.0})

    df = pd.DataFrame(records)
    df_no_outliers = remove_outliers(df, percentile=99.5)
    assert 999 not in df_no_outliers["Pedido"].values
    assert len(df_no_outliers["Pedido"].unique()) == 200


def test_pii_discarded_in_projection(sample_catalog_csv, sample_sales_df):
    """Testa minimização LGPD: Dados pessoais descartados na projeção final."""
    df_cat = load_catalog(sample_catalog_csv)
    df_final = run_etl_pipeline(sample_sales_df, df_cat)
    
    assert "Cliente" not in df_final.columns
    assert "Vendedor" not in df_final.columns
    assert "Numero Nota" not in df_final.columns
    assert "EAN" not in df_final.columns
    assert "Cidade" not in df_final.columns
    # Colunas analíticas mantidas
    for col in ["Pedido", "Data", "Cod Produto", "Valor Venda", "Qtd Venda", "Cod Cliente", "UF"]:
        assert col in df_final.columns


@patch("src.core.database.fetch_products_from_database")
def test_load_catalog_from_database_success(mock_fetch):
    """Testa carregamento e normalização de produtos vindos do SQL Server (P-022)."""
    mock_df = pd.DataFrame([
        {
            "Codigo": 500101,
            "Descricao": "COLAGENO 300G",
            "EAN": "789001",
            "Fornecedor": "FITONUTRI",
            "Tipo": "LINHA A",
            "Estoque": 50.0,
            "Pc.Ultimo Custo": 25.0,
            "Pc.Venda": 50.0,
        },
        {
            "Codigo": 500102,
            "Descricao": "CREATINA 300G",
            "EAN": "789002",
            "Fornecedor": "VITA LIFE",
            "Tipo": "LINHA B",
            "Estoque": 20.0,
            "Pc.Ultimo Custo": 0.0,  # Sem custo informado -> deve usar default_cost_ratio (60%)
            "Pc.Venda": 100.0,
        }
    ])
    mock_fetch.return_value = mock_df

    df_cat = load_catalog(source=None)
    assert len(df_cat) == 2
    assert "Código" in df_cat.columns
    assert "Preço" in df_cat.columns
    assert "Custo" in df_cat.columns
    assert "Fornec/Marca" in df_cat.columns
    assert df_cat.loc[df_cat["Código"] == 500101, "Custo"].iloc[0] == 25.0
    assert df_cat.loc[df_cat["Código"] == 500102, "Custo"].iloc[0] == 60.0

