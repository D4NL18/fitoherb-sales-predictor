"""
Classe de rota customizada TrendAPIRoute para tratamento centralizado de erros do módulo (ADR-003 DA-09).
Captura erros de validação e exceções de domínio/infraestrutura e converte para envelopes semânticos TND-NNN.
Sem registro de handlers globais em FastAPI para prevenir colisões entre módulos.
"""
from datetime import datetime, timezone
from typing import Callable, Coroutine, Sequence
from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from src.modules.sales_trend.domain.exceptions import (
    BaseMonthWithoutSalesError,
    InvalidTrendParametersError,
    SupplierNotFoundError,
    TrendDomainException,
)
from src.modules.sales_trend.repository.errors import (
    TrendDataSourceError,
    TrendInfrastructureException,
)
from src.modules.sales_trend.service.sales_trend_cache import ReloadTooSoonError


def _error_response(code: str, message: str, fields: Sequence[str], status_code: int) -> JSONResponse:
    """Gera resposta JSON de erro no formato padronizado do contrato 1.0.0."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "fields": list(fields),
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            },
        },
    )


class TrendAPIRoute(APIRoute):
    """Classe de rota que intercepta exceções locais do endpoint da Tendência de Vendas."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                # Extrai apenas nomes dos campos inválidos (sem ecoar valores recebidos)
                field_names = []
                for err in exc.errors():
                    loc = err.get("loc", ())
                    if loc:
                        field_names.append(str(loc[-1]))
                return _error_response(
                    code="TND-001",
                    message="Parâmetros de consulta inválidos.",
                    fields=field_names,
                    status_code=400,
                )
            except InvalidTrendParametersError as exc:
                return _error_response(exc.code, exc.message, exc.fields, 400)
            except BaseMonthWithoutSalesError as exc:
                return _error_response(exc.code, exc.message, exc.fields, 422)
            except SupplierNotFoundError as exc:
                return _error_response(exc.code, exc.message, exc.fields, 404)
            except TrendDataSourceError as exc:
                return _error_response(exc.code, exc.message, [], 503)
            except ReloadTooSoonError as exc:
                return _error_response(exc.code, exc.message, [], 429)

        return custom_handler
