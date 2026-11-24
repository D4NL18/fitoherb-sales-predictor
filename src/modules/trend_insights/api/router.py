"""
Rotas da F7 (`/api/v1/sales-trend/insights`). Controller fino: valida a borda, chama o servico e devolve o
envelope `{data, meta}`. O LLM so e acionado por `POST .../generate` (P-174); `GET` nunca chama o LLM.
"""
import base64
import binascii
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from src.modules.trend_insights.api.route import InsightsAPIRoute
from src.modules.trend_insights.domain.constants import ALLOWED_TREND_WINDOWS, DEFAULT_COMPARISON_MODE
from src.modules.trend_insights.domain.exceptions import InvalidInsightParametersError
from src.modules.trend_insights.service.insights_service import InsightQuery, InsightResult, InsightsService

MAX_SKU = 2_147_483_647
BASE_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
BASIC_PREFIX = "basic "

Metric = Literal["revenue", "quantity"]
Window = Literal[1, 3, 6, 12]
ComparisonMode = Literal["point", "average"]


class GenerateRequest(BaseModel):
    """Corpo do POST. Campos desconhecidos (ex.: campos de clientes antigos) sao ignorados."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    metric: Metric = "revenue"
    window: Window = 3
    base_month: Optional[str] = Field(default=None, alias="baseMonth", pattern=BASE_MONTH_PATTERN)
    comparison_mode: ComparisonMode = Field(default=DEFAULT_COMPARISON_MODE, alias="comparisonMode")
    force: StrictBool = False


def get_insights_service() -> InsightsService:
    """Dependencia substituivel nos testes; a fiacao de producao fica em `bootstrap` (composition root)."""
    from src.modules.trend_insights.bootstrap import get_default_service

    return get_default_service()


def _require_allowed_window(window: int) -> None:
    """Janela fora de 1/3/6/12 e 400 TIA-001 (a coercao de string para Literal nao existe em query)."""
    if window not in ALLOWED_TREND_WINDOWS:
        raise InvalidInsightParametersError(("window",))


def _caller_identifier(request: Request) -> str:
    """Usuario do Basic Auth (credencial compartilhada) ou IP; so o guard o ve, ja pseudonimizado."""
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith(BASIC_PREFIX):
        try:
            return base64.b64decode(authorization[len(BASIC_PREFIX):]).decode("utf-8").split(":", 1)[0]
        except (binascii.Error, UnicodeDecodeError):
            return "invalid-credentials"
    return request.client.host if request.client else "unknown"


def _envelope(result: InsightResult) -> Dict[str, Any]:
    return {"data": result.data, "meta": result.meta}


insights_router = APIRouter(prefix="/sales-trend/insights", tags=["Sales Trend Insights"], route_class=InsightsAPIRoute)


@insights_router.get("/health", summary="Estado operacional da IA, do orçamento e do índice")
def get_health(service: InsightsService = Depends(get_insights_service)):
    return _envelope(service.get_health())


@insights_router.get("/product/{sku}", summary="Cascata e diagnóstico salvo de um produto (sem custo de IA)")
def get_product_insight(
    sku: int = Path(ge=1, le=MAX_SKU),
    metric: Metric = Query("revenue"),
    window: int = Query(3),
    base_month: Optional[str] = Query(None, alias="baseMonth", pattern=BASE_MONTH_PATTERN),
    comparison_mode: ComparisonMode = Query(DEFAULT_COMPARISON_MODE, alias="comparisonMode"),
    service: InsightsService = Depends(get_insights_service),
):
    _require_allowed_window(window)
    query = InsightQuery(sku=sku, metric=metric, window=window, base_month=base_month, comparison_mode=comparison_mode)
    return _envelope(service.get_product_insight(query))


@insights_router.post("/product/{sku}/generate", summary="Gera (ou reutiliza) o diagnóstico com IA")
def generate_product_insight(
    request: Request,
    body: GenerateRequest,
    sku: int = Path(ge=1, le=MAX_SKU),
    service: InsightsService = Depends(get_insights_service),
):
    query = InsightQuery(
        sku=sku, metric=body.metric, window=body.window, base_month=body.base_month,
        comparison_mode=body.comparison_mode, force=body.force,
    )
    return _envelope(service.generate_product_insight(query, _caller_identifier(request)))
