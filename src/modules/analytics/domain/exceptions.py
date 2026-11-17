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


# ---------------------------------------------------------------------------
# F3: Churn de Clientes (P-127; ADR-006 DA-06)
# ---------------------------------------------------------------------------

class CustomerChurnNotFoundError(AnalyticsDomainException):
    """CHU-001: Cliente não encontrado ou sem pedidos válidos de venda."""

    def __init__(self) -> None:
        super().__init__(
            code="CHU-001",
            message="Cliente não encontrado ou sem histórico de compras válidas.",
            fields=(),
        )


class ChurnBaseInsufficientError(AnalyticsDomainException):
    """CHU-002: Base de clientes/pedidos insuficiente para o cálculo de churn."""

    def __init__(self) -> None:
        super().__init__(
            code="CHU-002",
            message="Base de vendas insuficiente para cálculo de churn de clientes.",
            fields=(),
        )


class ChurnInvalidParametersError(AnalyticsDomainException):
    """CHU-003: Parâmetros inválidos informados para a rota de churn."""

    def __init__(self, fields: Sequence[str] = ()) -> None:
        field_list = tuple(fields)
        msg = f"Parâmetros de churn inválidos: {', '.join(field_list)}." if field_list else "Parâmetros de churn inválidos."
        super().__init__(
            code="CHU-003",
            message=msg,
            fields=field_list,
        )


class SeasonalityProductNotFoundError(AnalyticsDomainException):
    """SEA-001: Produto não encontrado ou sem histórico de vendas para sazonalidade (P-116)."""

    def __init__(self) -> None:
        super().__init__(
            code="SEA-001",
            message="Produto não encontrado ou sem histórico de vendas.",
            fields=(),
        )


class SeasonalityInvalidParametersError(AnalyticsDomainException):
    """SEA-002: Parâmetros inválidos na consulta de sazonalidade (P-116)."""

    def __init__(self, fields: Sequence[str] = ()) -> None:
        field_list = tuple(fields)
        msg = f"Parâmetros inválidos: {', '.join(field_list)}." if field_list else "Parâmetros inválidos."
        super().__init__(
            code="SEA-002",
            message=msg,
            fields=field_list,
        )


class SeasonalityInsufficientBaseError(AnalyticsDomainException):
    """SEA-003: Base de dados agregada insuficiente para análise de sazonalidade (P-116)."""

    def __init__(self) -> None:
        super().__init__(
            code="SEA-003",
            message="Base de vendas insuficiente para calcular sazonalidade dos produtos.",
            fields=(),
        )


class ElasticityProductNotFoundError(AnalyticsDomainException):
    """ELA-001: Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade."""

    def __init__(self) -> None:
        super().__init__(
            code="ELA-001",
            message="Produto não encontrado ou sem histórico de vendas para cálculo de elasticidade.",
            fields=(),
        )


class ElasticityCustomerWithoutHistoryError(AnalyticsDomainException):
    """ELA-002: Cliente sem compras registradas para este produto."""

    def __init__(self) -> None:
        super().__init__(
            code="ELA-002",
            message="Cliente sem compras registradas para este produto.",
            fields=(),
        )


class ElasticityInsufficientBaseError(AnalyticsDomainException):
    """ELA-003: Histórico de vendas insuficiente para estimar elasticidade do produto."""

    def __init__(self) -> None:
        super().__init__(
            code="ELA-003",
            message="Histórico de vendas insuficiente para estimar elasticidade do produto.",
            fields=(),
        )


class ElasticityInvalidParametersError(AnalyticsDomainException):
    """ELA-004: Parâmetros inválidos fornecidos para consulta ou simulação de elasticidade."""

    def __init__(self, fields: Sequence[str] = ()) -> None:
        field_list = tuple(fields)
        msg = f"Parâmetros inválidos: {', '.join(field_list)}." if field_list else "Parâmetros inválidos."
        super().__init__(
            code="ELA-004",
            message=msg,
            fields=field_list,
        )


# ---------------------------------------------------------------------------
# F2: Viabilidade de Produto Novo (P-139 a P-149; ADR-008 DA-09)
# ---------------------------------------------------------------------------

class NewProductDomainException(AnalyticsDomainException):
    """Exceção base de domínio para Viabilidade de Produto Novo (F2, LGPD-05)."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        fields: Sequence[str] = (),
    ) -> None:
        super().__init__(code=code, message=message, fields=fields)
        self.status_code = status_code


class NewProductInsufficientSimilarsError(NewProductDomainException):
    """NEW-001: Quantidade de lançamentos similares elegíveis inferior a MIN_SIMILARS (3)."""

    def __init__(self, count: int = 0) -> None:
        super().__init__(
            code="NEW-001",
            message=(
                "Base de lançamentos similares insuficiente para o tipo selecionado "
                f"(mínimo de 3 lançamentos necessários; encontrados: {int(count)})."
            ),
            status_code=422,
            fields=(),
        )


class NewProductInvalidTypeError(NewProductDomainException):
    """NEW-002: Tipo de produto informado não existe no catálogo ativo."""

    def __init__(self) -> None:
        super().__init__(
            code="NEW-002",
            message="O tipo de produto informado não foi encontrado no catálogo ativo.",
            status_code=400,
            fields=("tipo",),
        )


class NewProductInvalidSupplierError(NewProductDomainException):
    """NEW-003: Fornecedor informado não existe no catálogo ativo."""

    def __init__(self) -> None:
        super().__init__(
            code="NEW-003",
            message="O fornecedor informado não foi encontrado no catálogo ativo.",
            status_code=400,
            fields=("fornecedor",),
        )


class NewProductInvalidParametersError(NewProductDomainException):
    """NEW-004: Parâmetros comerciais ou numéricos inconsistentes (LGPD-05: sem eco de valores)."""

    def __init__(self, message: str = "Parâmetros comerciais inconsistentes.", fields: Sequence[str] = ()) -> None:
        super().__init__(
            code="NEW-004",
            message=message,
            status_code=400,
            fields=fields,
        )


class NewProductDatabaseUnavailableError(NewProductDomainException):
    """NEW-005: Indisponibilidade momentânea da base de dados na análise de produto novo."""

    def __init__(self) -> None:
        super().__init__(
            code="NEW-005",
            message="Serviço de análise de produtos temporariamente indisponível. Tente novamente em instantes.",
            status_code=503,
            fields=(),
        )
