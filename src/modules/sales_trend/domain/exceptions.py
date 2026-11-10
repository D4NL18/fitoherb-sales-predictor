"""
Exceções de domínio puro para Tendência de Vendas (P-082, ADR-003 DA-09).
Mensagens fixas, sem eco de valores recebidos e com nomes de campos afetados.
"""
from typing import Sequence, Tuple


class TrendDomainException(Exception):
    """Exceção base para erros de negócio e validação de domínio da Tendência."""

    def __init__(self, code: str, message: str, fields: Sequence[str] = ()):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = tuple(fields)


class InvalidTrendParametersError(TrendDomainException):
    """TND-001: Parâmetros de consulta inválidos."""

    def __init__(self, fields: Sequence[str] = ()):
        super().__init__(
            code="TND-001",
            message="Parâmetros de consulta inválidos.",
            fields=fields,
        )


class BaseMonthWithoutSalesError(TrendDomainException):
    """TND-002: Mês-Base informado não possui dados de vendas suficientes."""

    def __init__(self, fields: Sequence[str] = ()):
        super().__init__(
            code="TND-002",
            message="Mês-Base informado não possui dados de vendas suficientes.",
            fields=fields,
        )


class SupplierNotFoundError(TrendDomainException):
    """TND-003: Fornecedor não encontrado."""

    def __init__(self, fields: Sequence[str] = ()):
        super().__init__(
            code="TND-003",
            message="Fornecedor não encontrado.",
            fields=fields,
        )
