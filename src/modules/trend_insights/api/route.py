"""
`InsightsAPIRoute`: traduz excecoes do modulo em envelopes de erro `TIA-NNN` (ADR-009 DA-11), sem handler global.
Mensagens fixas (nunca ecoam sku, baseMonth ou qualquer valor recebido) e sem stacktrace.
"""
import logging
from datetime import datetime, timezone
from typing import Callable, Coroutine, Optional, Sequence

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from src.modules.trend_insights.domain.constants import CONTRACT_VERSION, LOGGER_NAME
from src.modules.trend_insights.domain.exceptions import (
    GenerationRefused,
    InsufficientBaseError,
    InvalidInsightParametersError,
    NoRelevantVariationError,
    ProductNotFoundError,
)
from src.modules.trend_insights.domain.ports import TrendSourceUnavailable

logger = logging.getLogger(LOGGER_NAME + ".api")

MESSAGES = {
    "TIA-001": "Parâmetros inválidos para o diagnóstico.",
    "TIA-002": "Produto ou fornecedor não encontrado no catálogo ativo.",
    "TIA-003": "Não há base de vendas suficiente para diagnosticar esta janela.",
    "TIA-003-VARIACAO": "Não há variação relevante para analisar.",
    "TIA-004": "Limite de análises com IA atingido. A parte numérica continua disponível.",
    "ANL-001": "Base de vendas indisponível no momento. Tente novamente em instantes.",
    "INTERNAL": "Erro interno. Tente novamente em instantes.",
}


def error_response(
    code: str, message: str, status_code: int, fields: Sequence[str] = (), motivo: Optional[str] = None,
    headers: Optional[dict] = None,
) -> JSONResponse:
    body = {
        "error": {"code": code, "message": message, "fields": list(fields), "motivo": motivo},
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat(), "version": CONTRACT_VERSION},
    }
    return JSONResponse(status_code=status_code, content=body, headers=headers)


def _validation_fields(exc: RequestValidationError) -> list:
    fields = []
    for error in exc.errors():
        location = error.get("loc", ())
        name = str(location[-1]) if location else "body"
        fields.append(name if name not in fields else None)
    return [name for name in fields if name]


class InsightsAPIRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[None, None, Response]]:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                return error_response("TIA-001", MESSAGES["TIA-001"], 400, _validation_fields(exc))
            except InvalidInsightParametersError as exc:
                return error_response("TIA-001", MESSAGES["TIA-001"], 400, exc.fields)
            except ProductNotFoundError:
                return error_response("TIA-002", MESSAGES["TIA-002"], 404)
            except InsufficientBaseError:
                return error_response("TIA-003", MESSAGES["TIA-003"], 422)
            except NoRelevantVariationError:
                return error_response("TIA-003", MESSAGES["TIA-003-VARIACAO"], 422)
            except GenerationRefused as exc:
                return error_response(
                    "TIA-004", MESSAGES["TIA-004"], 429, motivo=exc.motivo,
                    headers={"Retry-After": str(exc.retry_after_seconds)},
                )
            except TrendSourceUnavailable:
                return error_response("ANL-001", MESSAGES["ANL-001"], 503)
            except Exception as exc:  # ultima barreira: corpo generico, so o tipo vai ao log
                logger.error("tia.api.unexpected_error type=%s", type(exc).__name__)
                return error_response("INTERNAL_ERROR", MESSAGES["INTERNAL"], 500)

        return custom_handler
