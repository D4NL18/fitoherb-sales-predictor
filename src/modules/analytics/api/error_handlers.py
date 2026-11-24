"""
Handlers globais de erro do módulo Analytics (P-067, P-116, ADR-002 DA-08, ADR-005, contrato §4, LGPD-05).

- `AnalyticsDomainException` (XSL-001..004, SEA-001..003) e `AnalyticsInfrastructureException` (ANL-001, ANL-002)
  viram o corpo único `{error: {code, message, fields}, meta: {timestamp, version}}` com HTTP semântico.
- `RequestValidationError` em paths `/api/v1/analytics/seasonality` vira 400 `SEA-002` com os nomes dos campos;
  em outros paths `/api/v1/analytics` vira 400 `XSL-004`; nos demais paths do app delega ao handler padrão do FastAPI.
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
from src.modules.analytics.domain.exceptions import (
    AnalyticsDomainException,
    CannibalizationInvalidParametersError,
    InvalidParametersError,
    SeasonalityInvalidParametersError,
)
from src.modules.analytics.repository.errors import AnalyticsInfrastructureException

ANALYTICS_PATH_PREFIX = "/api/v1/analytics"
SEASONALITY_PATH_PREFIX = "/api/v1/analytics/seasonality"
GENERIC_ERROR_STATUS = 500

# Mapa código interno -> HTTP (o domínio não conhece HTTP, DA-08).
ERROR_STATUS_BY_CODE: Dict[str, int] = {
    "XSL-001": 404,
    "XSL-002": 404,
    "XSL-003": 422,
    "XSL-004": 400,
    "SEA-001": 404,
    "SEA-002": 400,
    "SEA-003": 422,
    "ANL-001": 503,
    "ANL-002": 429,
    "CHU-001": 404,
    "CHU-002": 422,
    "CHU-003": 400,
    "ELA-001": 404,
    "ELA-002": 404,
    "ELA-003": 422,
    "ELA-004": 400,
    "NEW-001": 422,
    "NEW-002": 400,
    "NEW-003": 400,
    "NEW-004": 400,
    "NEW-005": 503,
    "CAN-001": 404,
    "CAN-002": 422,
    "CAN-003": 422,
    "CAN-004": 400,
    "CAN-005": 500,
}


def _error_response(code: str, message: str, fields: Sequence[str]) -> JSONResponse:
    """Corpo de erro do contrato §4 com o status do mapa."""
    body = AnalyticsErrorResponse(error=ErrorDetail(code=code, message=message, fields=list(fields)),
                                  meta=to_error_meta())
    status_code = ERROR_STATUS_BY_CODE.get(code, GENERIC_ERROR_STATUS)
    return JSONResponse(status_code=status_code, content=body.model_dump(by_alias=True))


def _handle_domain_error(request: Request, exc: AnalyticsDomainException) -> JSONResponse:
    """XSL-001..004, SEA-001..003 -> 404/422/400 com mensagem fixa (P-067, P-116)."""
    return _error_response(exc.code, exc.message, exc.fields)


def _handle_infrastructure_error(request: Request, exc: AnalyticsInfrastructureException) -> JSONResponse:
    """ANL-001 -> 503 (ou NEW-005 em /new-product), ANL-002 -> 429, sem detalhe do driver (LGPD-05)."""
    if "/new-product" in request.url.path and exc.code == "ANL-001":
        return _error_response(
            "NEW-005",
            "Serviço de análise de produtos temporariamente indisponível. Tente novamente em instantes.",
            (),
        )
    return _error_response(exc.code, exc.message, ())


def _invalid_field_names(errors: Iterable[dict]) -> List[str]:
    """Nomes dos parâmetros inválidos (`loc[-1]`), sem duplicatas, na ordem do path/query."""
    names = (str(error["loc"][-1]) for error in errors if error.get("loc"))
    return list(dict.fromkeys(names))


async def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """400 `SEA-002` ou `XSL-004` nas rotas do módulo; demais rotas mantêm o 422 padrão do FastAPI (DA-08)."""
    if not request.url.path.startswith(ANALYTICS_PATH_PREFIX):
        return await request_validation_exception_handler(request, exc)
    fields = _invalid_field_names(exc.errors())
    if request.url.path.startswith(SEASONALITY_PATH_PREFIX):
        error = SeasonalityInvalidParametersError(fields=fields)
        return _error_response(error.code, error.message, error.fields)
    if "/elasticity" in request.url.path:
        msg = f"Parâmetros inválidos: {', '.join(fields)}." if fields else "Parâmetros inválidos."
        return _error_response("ELA-004", msg, fields)
    if "/new-product" in request.url.path:
        return _error_response("NEW-004", "Parâmetros comerciais inconsistentes.", fields)
    if "/cannibalization" in request.url.path or "/substitution" in request.url.path:
        error = CannibalizationInvalidParametersError(fields=fields)
        return _error_response(error.code, error.message, error.fields)
    error = InvalidParametersError(fields=fields)
    return _error_response(error.code, error.message, error.fields)


def register_analytics_error_handlers(app: FastAPI) -> None:
    """Registra os handlers globais do módulo no app (chamado em `src/api.py`)."""
    app.add_exception_handler(AnalyticsDomainException, _handle_domain_error)
    app.add_exception_handler(AnalyticsInfrastructureException, _handle_infrastructure_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
