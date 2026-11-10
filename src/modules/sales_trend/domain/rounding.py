"""
Funções de arredondamento meio para cima exato (P-077, P-080, ADR-003 DA-10).
Utiliza Fraction e Decimal para evitar resíduos de ponto flutuante binário.
"""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def round_fraction_half_up(fraction: Fraction, places: int = 1) -> float:
    """
    Arredonda uma Fraction para 'places' casas decimais usando meio para cima (ROUND_HALF_UP).
    Evita zero negativo (-0.0) convertendo para 0.0.
    """
    if fraction == 0:
        return 0.0

    # Conversão de alta precisão para Decimal
    # Usando string exata de numerador / denominador com precisão suficiente
    dec_val = Decimal(fraction.numerator) / Decimal(fraction.denominator)
    target_exp = Decimal("10") ** (-places)
    rounded = dec_val.quantize(target_exp, rounding=ROUND_HALF_UP)

    res = float(rounded)
    return 0.0 if res == 0.0 else res


def round_scaled_half_up(scaled_value: int, places: int = 2, scale: int = 10_000) -> float:
    """
    Arredonda um inteiro escalado (VALUE_SCALE = 10_000) para 'places' casas decimais.
    """
    if scaled_value == 0:
        return 0.0

    dec_val = Decimal(scaled_value) / Decimal(scale)
    target_exp = Decimal("10") ** (-places)
    rounded = dec_val.quantize(target_exp, rounding=ROUND_HALF_UP)

    res = float(rounded)
    return 0.0 if res == 0.0 else res
