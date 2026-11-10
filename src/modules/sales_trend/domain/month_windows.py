"""
Aritmética de meses, janelas e cobertura de datas (P-074, P-075, P-076, ADR-003 DA-05).
Trabalha com índice inteiro de mês (ano * 12 + mês - 1) para prevenir erros de virada de ano.
"""
import calendar
import datetime
from functools import lru_cache
import re
from typing import List, Optional, Sequence, Tuple

from src.modules.sales_trend.domain.exceptions import (
    BaseMonthWithoutSalesError,
    InvalidTrendParametersError,
)

_BASE_MONTH_REGEX = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def month_index(year: int, month: int) -> int:
    """Converte (ano, mês) em índice escalar contínuo."""
    return year * 12 + month - 1


def index_to_year_month(index: int) -> Tuple[int, int]:
    """Converte índice escalar de volta para (ano, mês)."""
    year = index // 12
    month = (index % 12) + 1
    return year, month


def parse_base_month(val: Optional[str]) -> Optional[int]:
    """
    Converte string 'AAAA-MM' para índice escalar.
    Retorna None se o formato for inválido ou se o ano for <= 0 sem levantar ValueError.
    """
    if not val:
        return None
    match = _BASE_MONTH_REGEX.match(val.strip())
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2))
    if year <= 0:
        return None
    return month_index(year, month)


def format_year_month(index: int) -> str:
    """Formata índice escalar de mês para 'AAAA-MM'."""
    year, month = index_to_year_month(index)
    return f"{year:04d}-{month:02d}"


def previous_month(base_month_index: int) -> int:
    """Retorna o índice do mês imediatamente anterior."""
    return base_month_index - 1


def window_pair(base_month_index: int, size: int) -> Tuple[List[int], List[int]]:
    """
    Calcula as janelas atual e anterior de tamanho 'size' a partir de base_month_index.
    Janela atual: termina em base_month_index, abrangendo 'size' meses.
    Janela anterior: termina em (base_month_index - size), abrangendo 'size' meses.
    """
    curr = list(range(base_month_index - size + 1, base_month_index + 1))
    prev = list(range(base_month_index - 2 * size + 1, base_month_index - size + 1))
    return curr, prev


@lru_cache(maxsize=128)
def days_in_month(month_idx: int) -> int:
    """Retorna a quantidade de dias no mês (respeitando anos bissextos)."""
    year, month = index_to_year_month(month_idx)
    return calendar.monthrange(year, month)[1]


def days_in_span(span: Sequence[int]) -> int:
    """Soma a quantidade total de dias de calendário em uma sequência de meses."""
    return _days_in_span_cached(tuple(span))


@lru_cache(maxsize=128)
def _days_in_span_cached(span_tuple: Tuple[int, ...]) -> int:
    return sum(days_in_month(m) for m in span_tuple)


def covered_days(
    span: Sequence[int],
    first_sale_date: datetime.date,
    last_covered_day: datetime.date,
) -> int:
    """
    Calcula a quantidade de dias cobertos na janela delimitada por [first_sale_date, last_covered_day].
    """
    return _covered_days_cached(tuple(span), first_sale_date, last_covered_day)


@lru_cache(maxsize=128)
def _covered_days_cached(
    span_tuple: Tuple[int, ...],
    first_sale_date: datetime.date,
    last_covered_day: datetime.date,
) -> int:
    total_covered = 0
    for m in span_tuple:
        year, month = index_to_year_month(m)
        m_start = datetime.date(year, month, 1)
        m_end = datetime.date(year, month, days_in_month(m))

        eff_start = max(m_start, first_sale_date)
        eff_end = min(m_end, last_covered_day)

        if eff_start <= eff_end:
            total_covered += (eff_end - eff_start).days + 1

    return total_covered


def is_coverage_sufficient(covered: int, total: int, min_ratio: float = 0.5) -> bool:
    """
    Verifica se a cobertura de dias da janela é suficiente (>= 50%, P-076.6).
    Exatos 50% de cobertura NÃO é SEM_BASE (retorna True).
    """
    if total <= 0:
        return False
    return (covered / total) >= min_ratio


def validate_base_month(
    base_month_index: int,
    min_month_index: int,
    max_month_index: int,
    last_covered_day: datetime.date,
) -> None:
    """
    Valida limites de negócio do Mês-Base (P-074, CA-20).
    - baseMonth futuro (> max_month_index) -> TND-001 (400)
    - baseMonth anterior ao início da base (< min_month_index) -> TND-002 (422)
    - baseMonth igual a max_month_index sem nenhum dia coberto -> TND-002 (422)
    """
    if base_month_index > max_month_index:
        raise InvalidTrendParametersError(fields=("baseMonth",))

    if base_month_index < min_month_index:
        raise BaseMonthWithoutSalesError(fields=("baseMonth",))

    # Verifica se o mês corrente tem ao menos 1 dia coberto
    year, month = index_to_year_month(base_month_index)
    month_start = datetime.date(year, month, 1)
    if last_covered_day < month_start:
        raise BaseMonthWithoutSalesError(fields=("baseMonth",))
