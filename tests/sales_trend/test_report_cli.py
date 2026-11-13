"""
Testes para o CLI de relatório e cálculo de percentis de base baixa (T-12).
"""
from unittest.mock import patch
import pytest

from tests.sales_trend.test_sales_trend_api import _setup_mock_snapshot


def test_calculate_percentiles_helper():
    """Valida cálculo de percentis p10 a p90."""
    from src.modules.sales_trend.diagnostics.run_sales_trend_report import calculate_percentiles

    vals = [float(x) for x in range(1, 101)]  # 1 a 100
    res = calculate_percentiles(vals)
    assert res["p10"] == pytest.approx(10.9, abs=0.2)
    assert res["p50"] == pytest.approx(50.5, abs=0.2)
    assert res["p90"] == pytest.approx(90.1, abs=0.2)


def test_run_report_output_structure():
    """Valida que o relatório contém seções de memória, contagens e percentis sem vazar dados brutos."""
    from src.modules.sales_trend.diagnostics.run_sales_trend_report import run_report

    snap = _setup_mock_snapshot()
    with patch("src.modules.sales_trend.diagnostics.run_sales_trend_report.get_snapshot", return_value=snap):
        out = run_report()

    assert "RELATÓRIO DE TENDÊNCIA DE VENDAS" in out
    assert "Pico de Memória na Carga" in out
    assert "SKUs Ativos Catalogados" in out
    assert "Soma Faturamento Líquido Janela 1m" in out
    assert "p50 (Mediana)" in out
    # Sem dados de clientes
    assert "cod cliente" not in out.lower()
