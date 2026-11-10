"""
Exceções de infraestrutura e persistência para Tendência de Vendas (ADR-003 DA-09).
"""

class TrendInfrastructureException(Exception):
    """Exceção base para falhas de infraestrutura / acesso a banco."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class TrendDataSourceError(TrendInfrastructureException):
    """TND-004: Base de dados indisponível no momento (503)."""

    def __init__(self):
        super().__init__(
            code="TND-004",
            message="Base de vendas indisponível no momento. Tente novamente em instantes.",
        )
