"""
Exceções de Infraestrutura / Acesso a Dados do módulo Analytics Comercial (P-067, LGPD-05).
"""
from __future__ import annotations


class AnalyticsInfrastructureException(Exception):
    """Exceção base para falhas de infraestrutura do módulo Analytics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AnalyticsDataSourceError(AnalyticsInfrastructureException):
    """ANL-001: Falha ao conectar ou consultar o banco de dados SQL Server."""

    def __init__(
        self,
        message: str = "Base de vendas indisponível no momento. Tente novamente em instantes.",
    ) -> None:
        super().__init__(code="ANL-001", message=message)
