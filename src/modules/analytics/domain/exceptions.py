"""
Exceções de Domínio do módulo Analytics Comercial (P-067, ADR-002 DA-08).

As exceções de domínio herdam de `AnalyticsDomainException`, têm mensagens fixas
e nunca expõem valores recebidos de clientes ou parâmetros (LGPD-05).
Não possuem dependência de HTTP ou FastAPI.
"""
from __future__ import annotations

from typing import Sequence


class AnalyticsDomainException(Exception):
    """Exceção base de domínio para o módulo Analytics Comercial."""

    def __init__(self, code: str, message: str, fields: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = tuple(fields)


class ProductNotFoundError(AnalyticsDomainException):
    """XSL-001: SKU fora do catálogo ativo ou sem histórico em cestas válidas."""

    def __init__(self) -> None:
        super().__init__(
            code="XSL-001",
            message="Produto não encontrado ou sem histórico de vendas em pedidos com mais de um item.",
            fields=(),
        )


class CustomerWithoutHistoryError(AnalyticsDomainException):
    """XSL-002: Cliente sem nenhum histórico de compras na operação VENDA."""

    def __init__(self) -> None:
        super().__init__(
            code="XSL-002",
            message="Cliente sem histórico de compras.",
            fields=(),
        )


class InsufficientBaseError(AnalyticsDomainException):
    """XSL-003: Menos de 1.000 cestas válidas ou zero regras úteis na mineração."""

    def __init__(self) -> None:
        super().__init__(
            code="XSL-003",
            message="Não há pedidos suficientes para gerar recomendações confiáveis.",
            fields=(),
        )


class InvalidParametersError(AnalyticsDomainException):
    """XSL-004: Parâmetros inválidos fornecidos à operação."""

    def __init__(self, fields: Sequence[str] = ()) -> None:
        field_list = tuple(fields)
        msg = f"Parâmetros inválidos: {', '.join(field_list)}." if field_list else "Parâmetros inválidos."
        super().__init__(
            code="XSL-004",
            message=msg,
            fields=field_list,
        )
