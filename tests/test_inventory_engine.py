"""
Suíte de Testes Unitários: Motor Analítico de Estoque e Reposição (Inventory Engine).
Valida VMD, volatilidade, cobertura, estoque de segurança, ROP, estoque ideal,
sugestão de compra, curva ABC e status de risco (P-041 a P-047).
"""
import numpy as np
import pandas as pd
import pytest

from src.modules.inventory.domain.inventory_engine import (
    calculate_inventory_replenishment,
    calculate_sales_velocity,
    get_z_score,
)


@pytest.fixture
def sample_sales_data():
    """Gera massa de vendas sintética para 3 produtos ao longo de 60 dias."""
    dates = pd.date_range(end="2026-09-30", periods=60, freq="D")
    data = []
    
    # Produto 101: Venda constante de 2 un/dia (120 unidades no período)
    for d in dates:
        data.append({"Data": d, "Cod Produto": 101, "Qtd Venda": 2.0, "Valor Venda": 50.0})
        
    # Produto 102: Vende 10 un a cada 5 dias (12 vendas de 10 un = 120 unidades, maior volatilidade)
    for i, d in enumerate(dates):
        if i % 5 == 0:
            data.append({"Data": d, "Cod Produto": 102, "Qtd Venda": 10.0, "Valor Venda": 200.0})
            
    # Produto 103: Sem vendas nos últimos 60 dias (não entra em sales)
    return pd.DataFrame(data)


@pytest.fixture
def sample_catalog_data():
    """Gera catálogo sintético com 3 produtos com perfis distintos de estoque."""
    return pd.DataFrame([
        {
            "Codigo": 101,
            "Descricao": "EXTRATO PROPOLIS APISFLORA",
            "EAN": "7891234567890",
            "Fornecedor": "APIS FLORA",
            "Tipo": "EXTRATOS",
            "Estoque": 10.0,  # VMD=2.0 -> Cobertura = 5 dias (Lead time 15 -> Ruptura iminente!)
            "Pc.Ultimo Custo": 15.0,
            "Pc.Venda": 25.0
        },
        {
            "Codigo": 102,
            "Descricao": "VITAMINA C HERBARIUM",
            "EAN": "7899876543210",
            "Fornecedor": "HERBARIUM",
            "Tipo": "VITAMINAS",
            "Estoque": 50.0,  # VMD=2.0 -> Cobertura = 25 dias
            "Pc.Ultimo Custo": 10.0,
            "Pc.Venda": 20.0
        },
        {
            "Codigo": 103,
            "Descricao": "CHA VERDE CATARINENSE",
            "EAN": "7891112223334",
            "Fornecedor": "CATARINENSE",
            "Tipo": "CHAS",
            "Estoque": 300.0,  # VMD=0 -> Overstock / Estagnado
            "Pc.Ultimo Custo": 5.0,
            "Pc.Venda": 12.0
        }
    ])


def test_get_z_score():
    assert pytest.approx(get_z_score(0.90), 0.01) == 1.28
    assert pytest.approx(get_z_score(0.95), 0.01) == 1.65
    assert pytest.approx(get_z_score(0.98), 0.01) == 2.05


def test_calculate_sales_velocity(sample_sales_data):
    velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
    
    assert 101 in velocity_df.index
    assert 102 in velocity_df.index
    
    # Produto 101: 120 un / 60 dias = 2.0 VMD
    assert pytest.approx(velocity_df.loc[101, "vmd"], 0.01) == 2.0
    # Desvio padrão de demanda constante (2 todos os dias) deve ser próximo de 0
    assert pytest.approx(velocity_df.loc[101, "std_demand"], 0.01) == 0.0
    
    # Produto 102: 120 un / 60 dias = 2.0 VMD
    assert pytest.approx(velocity_df.loc[102, "vmd"], 0.01) == 2.0
    # Como vendeu 10 em alguns dias e 0 nos outros, desvio padrão deve ser > 0
    assert velocity_df.loc[102, "std_demand"] > 1.0


def test_calculate_inventory_replenishment_metrics(sample_catalog_data, sample_sales_data):
    velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
    result = calculate_inventory_replenishment(
        products_df=sample_catalog_data,
        velocity_df=velocity_df,
        lead_time_days=15,
        target_coverage_days=30,
        service_level=0.95
    )
    
    kpis = result["kpis"]
    produtos = result["produtos"]
    
    assert kpis["totalSkusAnalisados"] == 3
    assert len(produtos) == 3
    
    prod_map = {p["codigo"]: p for p in produtos}
    
    # Produto 101: Ruptura iminente (Estoque 10, VMD 2 -> Cobertura 5 dias < Lead time 15)
    p101 = prod_map[101]
    assert p101["status"] == "CRITICAL_STOCKOUT"
    assert p101["diasCobertura"] == 5.0
    assert p101["qtdSugeridaCompra"] > 0
    assert p101["investimentoTotalItem"] == p101["qtdSugeridaCompra"] * p101["custoUnitario"]
    
    # Produto 103: Overstock (VMD 0, estoque 300)
    p103 = prod_map[103]
    assert p103["status"] == "OVERSTOCK"
    assert p103["qtdSugeridaCompra"] == 0
    
    # Total de investimento sugerido deve bater com a soma dos itens
    expected_invest = sum(p["investimentoTotalItem"] for p in produtos)
    assert pytest.approx(kpis["investimentoTotalSugerido"], 0.01) == expected_invest


def test_supplier_filter(sample_catalog_data, sample_sales_data):
    velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
    result = calculate_inventory_replenishment(
        products_df=sample_catalog_data,
        velocity_df=velocity_df,
        lead_time_days=15,
        target_coverage_days=30,
        service_level=0.95,
        supplier_filter="APIS FLORA"
    )
    
    produtos = result["produtos"]
    assert len(produtos) == 1
    assert produtos[0]["codigo"] == 101
    assert produtos[0]["fornecedor"] == "APIS FLORA"


def test_budget_limit_prioritization(sample_catalog_data, sample_sales_data):
    velocity_df = calculate_sales_velocity(sample_sales_data, window_days=60)
    # Sem limite de orçamento
    res_no_limit = calculate_inventory_replenishment(
        products_df=sample_catalog_data,
        velocity_df=velocity_df,
        lead_time_days=15,
        target_coverage_days=30,
        service_level=0.95
    )
    total_needed = res_no_limit["kpis"]["investimentoTotalSugerido"]
    assert total_needed > 0
    
    # Com limite menor que o total necessário
    budget_limit = total_needed / 2
    res_limited = calculate_inventory_replenishment(
        products_df=sample_catalog_data,
        velocity_df=velocity_df,
        lead_time_days=15,
        target_coverage_days=30,
        service_level=0.95,
        budget_limit=budget_limit
    )
    
    assert res_limited["kpis"]["investimentoTotalSugerido"] <= budget_limit + 1.0
