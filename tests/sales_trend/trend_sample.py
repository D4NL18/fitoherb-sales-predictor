"""
Massa sintética compartilhada para os testes da feature Tendência de Vendas (P-087.1).
Implementa os dados da Seção 5 das Regras de Negócio e Seção 4.1 (T-01) do Checklist Técnico.
"""
from dataclasses import dataclass
import datetime
from decimal import Decimal
from typing import Dict, List, Mapping, Optional, Set, Tuple

# Constantes globais da massa sintética de teste
REFERENCE_DATE = datetime.date(2026, 11, 9)
LAST_COVERED_DATE = datetime.date(2026, 11, 8)
FIRST_SALE_DATE = datetime.date(2025, 1, 7)


@dataclass(frozen=True)
class RawSalesRow:
    """Representa a linha retornada pela query agregada do SQL Server."""
    sku: int
    year_month: int
    quantity: Decimal
    revenue: Decimal
    first_sale_date: Optional[datetime.date] = None


def get_active_catalog_sample() -> Dict[int, Dict[str, Optional[str]]]:
    """
    Retorna o catálogo ativo sintético (WHERE [Pc.Venda] > 0).
    SKUs 1008 (inativo) e 1009 (sem cadastro) NÃO estão presentes.
    """
    return {
        1001: {"descricao": "CHÁ VERDE 100G", "fornecedor": "LABORATÓRIO ALFA"},
        1002: {"descricao": "CÁPSULA DE HIBISCO", "fornecedor": "LABORATÓRIO GAMA"},
        1003: {"descricao": "GUARANÁ EM PÓ", "fornecedor": "LABORATÓRIO ALFA"},
        1004: {"descricao": "CHÁ BRANCO 50G", "fornecedor": None},
        1005: {"descricao": "MEL SILVESTRE", "fornecedor": "LABORATÓRIO GAMA"},
        1006: {"descricao": "SPIRULINA 60 CÁPS", "fornecedor": "   "},
        1007: {"descricao": "ÓLEO DE COCO", "fornecedor": "LABORATÓRIO BETA"},
        1010: {"descricao": "BARRA DE CEREAL", "fornecedor": "LABORATÓRIO ALFA"},
    }


def get_raw_sales_rows_sample() -> List[RawSalesRow]:
    """
    Retorna as linhas do agregado bruto de vendas (incluindo 1008 inativo e 1009 sem cadastro).
    Valores já líquidos de devoluções conforme P-073.
    Preço padrão R$ 10,00/un, exceto 1001 em 2026-10 (R$ 12,00/un -> R$ 360,00).
    """
    rows: List[RawSalesRow] = []

    # SKU 1001:
    # jan/25 = 8
    rows.append(RawSalesRow(1001, 202501, Decimal("8.0"), Decimal("80.0"), FIRST_SALE_DATE))
    # fev-out/25 = 10 por mês
    for ym in range(202502, 202511):
        rows.append(RawSalesRow(1001, ym, Decimal("10.0"), Decimal("100.0"), FIRST_SALE_DATE))
    # nov/25-ago/26 = 20 por mês
    for ym in [202511, 202512] + list(range(202601, 202609)):
        rows.append(RawSalesRow(1001, ym, Decimal("20.0"), Decimal("200.0"), FIRST_SALE_DATE))
    # set/26 = VENDA 26 + DEVOLU -6 = 20 un / R$ 200,00
    rows.append(RawSalesRow(1001, 202609, Decimal("20.0"), Decimal("200.0"), FIRST_SALE_DATE))
    # out/26 = 30 un a R$ 12,00 = R$ 360,00
    rows.append(RawSalesRow(1001, 202610, Decimal("30.0"), Decimal("360.0"), FIRST_SALE_DATE))
    # nov/26 = 4 un / R$ 40,00 (dias 01 a 08)
    rows.append(RawSalesRow(1001, 202611, Decimal("4.0"), Decimal("40.0"), FIRST_SALE_DATE))

    # SKU 1002: out/26 = 40 un
    rows.append(RawSalesRow(1002, 202610, Decimal("40.0"), Decimal("400.0"), FIRST_SALE_DATE))

    # SKU 1003: set/26 = 50 un
    rows.append(RawSalesRow(1003, 202609, Decimal("50.0"), Decimal("500.0"), FIRST_SALE_DATE))

    # SKU 1004: set/26 = 20 un; out/26 = VENDA 5 + DEVOLU -12 = -7 un / -R$ 70,00
    rows.append(RawSalesRow(1004, 202609, Decimal("20.0"), Decimal("200.0"), FIRST_SALE_DATE))
    rows.append(RawSalesRow(1004, 202610, Decimal("-7.0"), Decimal("-70.0"), FIRST_SALE_DATE))

    # SKU 1005: set/26 = VENDA 2 + DEVOLU -5 = -3 un / -R$ 30,00; out/26 = 10 un / R$ 100,00
    rows.append(RawSalesRow(1005, 202609, Decimal("-3.0"), Decimal("-30.0"), FIRST_SALE_DATE))
    rows.append(RawSalesRow(1005, 202610, Decimal("10.0"), Decimal("100.0"), FIRST_SALE_DATE))

    # SKU 1006: mar/25 = 10 un
    rows.append(RawSalesRow(1006, 202503, Decimal("10.0"), Decimal("100.0"), FIRST_SALE_DATE))

    # SKU 1007: set/26 = 1 un; out/26 = 3 un
    rows.append(RawSalesRow(1007, 202609, Decimal("1.0"), Decimal("10.0"), FIRST_SALE_DATE))
    rows.append(RawSalesRow(1007, 202610, Decimal("3.0"), Decimal("30.0"), FIRST_SALE_DATE))

    # SKU 1008: CHÁ MATE LEGACY (inativo, Pc.Venda = 0): set/26 = 40 un
    rows.append(RawSalesRow(1008, 202609, Decimal("40.0"), Decimal("400.0"), FIRST_SALE_DATE))

    # SKU 1009: PRODUTO SEM CADASTRO: set/26 = 15 un; out/26 = 25 un
    rows.append(RawSalesRow(1009, 202609, Decimal("15.0"), Decimal("150.0"), FIRST_SALE_DATE))
    rows.append(RawSalesRow(1009, 202610, Decimal("25.0"), Decimal("250.0"), FIRST_SALE_DATE))

    # SKU 1010: BARRA DE CEREAL: nov/26 = 4 un
    rows.append(RawSalesRow(1010, 202611, Decimal("4.0"), Decimal("40.0"), FIRST_SALE_DATE))

    return rows


def generate_large_supplier_sample(
    supplier_name: str = "LABORATÓRIO GIGANTE",
    sku_count: int = 120
) -> Tuple[Dict[int, Dict[str, Optional[str]]], List[RawSalesRow]]:
    """
    Gera um catálogo e vendas para teste de paginação de detalhe com 120 SKUs (CA-39).
    """
    catalog: Dict[int, Dict[str, Optional[str]]] = {}
    rows: List[RawSalesRow] = []

    for i in range(1, sku_count + 1):
        sku = 5000 + i
        catalog[sku] = {
            "descricao": f"PRODUTO GIGANTE {i:03d}",
            "fornecedor": supplier_name
        }
        # Vendas variadas em set/26 e out/26 para ter variações ordenáveis
        qty_prev = Decimal(str(10 + (i % 20)))
        qty_curr = Decimal(str(15 + ((i * 3) % 30)))
        rows.append(RawSalesRow(sku, 202609, qty_prev, qty_prev * Decimal("10.0"), FIRST_SALE_DATE))
        rows.append(RawSalesRow(sku, 202610, qty_curr, qty_curr * Decimal("10.0"), FIRST_SALE_DATE))

    return catalog, rows
