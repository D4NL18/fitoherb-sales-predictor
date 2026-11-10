"""
Testes para utilitários de domínio: paginação, busca, arredondamento e exceções (T-03).
Valida regras P-077, P-081, P-082, CA-17, CA-18, C-20, C-24, C-26.
"""
from fractions import Fraction
import pytest


def test_pagination_standard_and_edge_cases():
    """Valida cálculo de paginação conforme CA-18 e P-081.4."""
    from src.modules.sales_trend.domain.pagination import paginate

    data = list(range(1, 121))  # 120 itens

    # limit=50, offset=100 -> 20 itens, page=3, totalPages=3
    page_res = paginate(data, limit=50, offset=100)
    assert len(page_res.items) == 20
    assert page_res.page == 3
    assert page_res.total_pages == 3
    assert page_res.total_items == 120

    # limit=3, offset=3 -> itens [4, 5, 6], page=2
    p3 = paginate(data, limit=3, offset=3)
    assert p3.items == [4, 5, 6]
    assert p3.page == 2

    # offset >= total -> itens vazio
    p_empty = paginate(data, limit=50, offset=150)
    assert len(p_empty.items) == 0
    assert p_empty.page == 4
    assert p_empty.total_pages == 3

    # lista vazia -> totalPages=0, items=[]
    p_zero = paginate([], limit=50, offset=0)
    assert len(p_zero.items) == 0
    assert p_zero.total_pages == 0
    assert p_zero.total_items == 0


def test_normalize_text():
    """Valida normalização NFKD sem acento, minúsculas e espaços colapsados."""
    from src.modules.sales_trend.domain.search_text import normalize_text

    assert normalize_text("  CHÁ   VERDE  100G ") == "cha verde 100g"
    assert normalize_text("ÓLEO  DE   CÔCO") == "oleo de coco"
    assert normalize_text("LABORATÓRIO   ALFA") == "laboratorio alfa"
    assert normalize_text("") == ""
    assert normalize_text("   ") == ""


def test_is_valid_search_query():
    """Valida regras de tamanho mínimo e máximo de busca (P-081.1)."""
    from src.modules.sales_trend.domain.search_text import is_valid_search_query

    # Dígitos: 1 a 60
    assert is_valid_search_query("1") is True
    assert is_valid_search_query("1001") is True
    assert is_valid_search_query("1" * 60) is True
    assert is_valid_search_query("1" * 61) is False

    # Texto: 2 a 60
    assert is_valid_search_query("a") is False  # 1 letra inválida
    assert is_valid_search_query("ch") is True  # 2 letras válida
    assert is_valid_search_query("cha") is True
    assert is_valid_search_query("a" * 60) is True
    assert is_valid_search_query("a" * 61) is False

    # Vazio / em branco
    assert is_valid_search_query("") is False
    assert is_valid_search_query("   ") is False


def test_search_predicates():
    """Valida predicados de busca de produtos e de fornecedores."""
    from src.modules.sales_trend.domain.search_text import (
        matches_product,
        matches_supplier,
        normalize_text,
    )

    desc_1001 = normalize_text("CHÁ VERDE 100G")
    desc_1004 = normalize_text("CHÁ BRANCO 50G")
    desc_1003 = normalize_text("GUARANÁ EM PÓ")

    # Busca por texto: "cha" casa com 1001 e 1004, não com 1003
    assert matches_product("cha", 1001, desc_1001) is True
    assert matches_product("cha", 1004, desc_1004) is True
    assert matches_product("cha", 1003, desc_1003) is False

    # Busca por código: "100" começa com 1001, 1003 e 1004
    assert matches_product("100", 1001, desc_1001) is True
    assert matches_product("1003", 1003, desc_1003) is True
    assert matches_product("1003", 1001, desc_1001) is False

    # Busca de fornecedor por nome
    supp_alfa = normalize_text("LABORATÓRIO ALFA")
    assert matches_supplier("alfa", supp_alfa) is True
    assert matches_supplier("beta", supp_alfa) is False


def test_rounding_half_up_exact():
    """Valida arredondamento meio para cima exato com Fraction (P-077, P-080)."""
    from src.modules.sales_trend.domain.rounding import round_fraction_half_up

    # 12,25 -> 12,3
    assert round_fraction_half_up(Fraction(1225, 100), 1) == 12.3

    # -12,25 -> -12,3
    assert round_fraction_half_up(Fraction(-1225, 100), 1) == -12.3

    # -0,04 -> 0.0 (sem -0.0)
    res_zero = round_fraction_half_up(Fraction(-4, 100), 1)
    assert res_zero == 0.0
    assert str(res_zero) == "0.0"


def test_domain_exceptions_messages_and_fields():
    """Valida mensagens fixas de exceções de domínio e isolamento de campos (P-082)."""
    from src.modules.sales_trend.domain.exceptions import (
        InvalidTrendParametersError,
        BaseMonthWithoutSalesError,
        SupplierNotFoundError,
    )

    err1 = InvalidTrendParametersError(fields=("baseMonth", "metric"))
    assert err1.code == "TND-001"
    assert err1.message == "Parâmetros de consulta inválidos."
    assert err1.fields == ("baseMonth", "metric")

    err2 = BaseMonthWithoutSalesError(fields=("baseMonth",))
    assert err2.code == "TND-002"
    assert err2.message == "Mês-Base informado não possui dados de vendas suficientes."
    assert err2.fields == ("baseMonth",)

    err3 = SupplierNotFoundError(fields=("supplierKey",))
    assert err3.code == "TND-003"
    assert err3.message == "Fornecedor não encontrado."
    assert err3.fields == ("supplierKey",)
