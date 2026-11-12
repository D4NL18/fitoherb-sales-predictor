"""
Handlers globais de erro do módulo Analytics (P-067, ADR-002 DA-08, contrato §4, LGPD-05).

- `AnalyticsDomainException` (XSL-001..004) e `AnalyticsInfrastructureException` (ANL-001, ANL-002)
  viram o corpo único `{error: {code, message, fields}, meta: {timestamp, version}}` com HTTP semântico.
- `RequestValidationError` em paths `/api/v1/analytics` vira 400 `XSL-004` com só os nomes dos campos
  (nunca o valor recebido); nos demais paths delega ao handler padrão do FastAPI (422 de pricing e
  inventory intacto).
- Exceções não previstas seguem para o 500 genérico do Starlette, sem stacktrace.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.modules.analytics.api.mappers import to_error_meta
from src.modules.analytics.api.schemas import AnalyticsErrorResponse, ErrorDetail
from src.modules.analytics.domain.exceptions import AnalyticsDomainException, InvalidParametersError
from src.modules.analytics.repository.errors import AnalyticsInfrastructureException

ANALYTICS_PATH_PREFIX = "/api/v1/analytics"
GENERIC_ERROR_STATUS = 500

# Mapa código interno -> HTTP (o domínio não conhece HTTP, DA-08).
ERROR_STATUS_BY_CODE: Dict[str, int] = {
    "XSL-001": 404,
    "XSL-002": 404,
    "XSL-003": 422,
    "XSL-004": 400,
    "ANL-001": 503,
    "ANL-002": 429,
}


def _error_response(code: str, message: str, fields: Sequence[str]) -> JSONResponse:
    """Corpo de erro do contrato §4 com o status do mapa."""
    body = AnalyticsErrorResponse(error=ErrorDetail(code=code, message=message, fields=list(fields)),
                                  meta=to_error_meta())
    status_code = ERROR_STATUS_BY_CODE.get(code, GENERIC_ERROR_STATUS)
    return JSONResponse(status_code=status_code, content=body.model_dump(by_alias=True))


async def _handle_domain_error(request: Request, exc: AnalyticsDomainException) -> JSONResponse:
    """XSL-001..004 -> 404/422/400 com mensagem fixa (P-067)."""
    return _error_response(exc.code, exc.message, exc.fields)


async def _handle_infrastructure_error(request: Request, exc: AnalyticsInfrastructureException) -> JSONResponse:
    """ANL-001 -> 503, ANL-002 -> 429, sem detalhe do driver (LGPD-05)."""
    return _error_response(exc.code, exc.message, ())


def _invalid_field_names(errors: Iterable[dict]) -> List[str]:
    """Nomes dos parâmetros inválidos (`loc[-1]`), sem duplicatas, na ordem do path/query."""
    names = (str(error["loc"][-1]) for error in errors if error.get("loc"))
    return list(dict.fromkeys(names))


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """400 `XSL-004` nas rotas do módulo; demais rotas mantêm o 422 padrão do FastAPI (DA-08)."""
    if not request.url.path.startswith(ANALYTICS_PATH_PREFIX):
        return await request_validation_exception_handler(request, exc)
    error = InvalidParametersError(fields=_invalid_field_names(exc.errors()))
    return _error_response(error.code, error.message, error.fields)


def register_analytics_error_handlers(app: FastAPI) -> None:
    """Registra os handlers globais do módulo no app (chamado em `src/api.py`)."""
    app.add_exception_handler(AnalyticsDomainException, _handle_domain_error)
    app.add_exception_handler(AnalyticsInfrastructureException, _handle_infrastructure_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
