"""
Arredondamento e formatação numérica pt-BR do módulo Analytics (P-064.3, P-065, contrato §2.4).

Por que existe: o `round()` do Python arredonda pelo valor binário (7,225 vira 7,22) e o `locale`
do sistema varia entre a máquina do desenvolvedor e o Cloud Run. Aqui o arredondamento é sempre
"meio para cima" sobre o valor decimal (`Decimal(str(x))`, nunca `Decimal(float)`), e a vírgula
decimal e o ponto de milhar são aplicados sem depender de `locale`.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Casas usadas para descartar o ruído binário antes do arredondamento de exibição
# (ex.: 4,25 x 0,34 x 5 = 7.2250000000000005 e 1,15 = 1.15 exatos no texto decimal).
FLOAT_NOISE_DECIMALS = 9


def round_half_up(value: float, places: int) -> Decimal:
    """
    Arredonda `value` com `places` casas, meio para cima, a partir do texto decimal do número.

    Args:
        value: número de ponto flutuante calculado no domínio.
        places: casas decimais desejadas (0 para inteiro).

    Returns:
        `Decimal` já quantizado.

    Regra: P-064.3, P-065.1, P-065.2.
    """
    denoised = Decimal(str(value)).quantize(Decimal(1).scaleb(-FLOAT_NOISE_DECIMALS), rounding=ROUND_HALF_UP)
    return denoised.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def round_for_display(value: float, places: int) -> float:
    """Valor numérico arredondado meio para cima para os campos estruturados da API (contrato §2.4)."""
    return float(round_half_up(value, places))


PERCENT_FACTOR = Decimal(100)  # razão 0..1 -> percentual


def format_percent_pt_br(ratio: float) -> str:
    """
    Percentual inteiro, meio para cima, a partir de uma razão (0,345 -> '35'; 0,0999...9 -> '10').

    A multiplicação por 100 é feita em `Decimal` para não reintroduzir ruído binário.
    Regra: P-065.1.
    """
    denoised = round_half_up(ratio, FLOAT_NOISE_DECIMALS)
    percent = (denoised * PERCENT_FACTOR).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return format_integer_pt_br(int(percent))


def format_integer_pt_br(value: int) -> str:
    """Inteiro com ponto como separador de milhar (1234 -> '1.234'). Regra: P-065.3."""
    return f"{value:,}".replace(",", ".")


def format_decimal_pt_br(value: float, places: int) -> str:
    """Decimal meio para cima com vírgula decimal e ponto de milhar (1,25 -> '1,3'). Regra: P-065.2."""
    rounded = round_half_up(value, places)
    us_format = f"{rounded:,.{places}f}"
    return us_format.replace(",", "_").replace(".", ",").replace("_", ".")
