"""
Adaptadores das fontes dos fatores internos (D-7.1.16): sazonalidade, elasticidade, clientes perdidos (churn),
estoque atual e promocoes. Unica ponte da F7 com essas funcoes de `analytics` (ADR-003). Qualquer falha da
fonte vira `NotEvaluated("FONTE_INDISPONIVEL")` (P-173) e nunca derruba o diagnostico; o log registra so o
tipo da excecao. O churn devolve um `frozenset` de codigos usado apenas dentro da construcao do snapshot
de migracao (P-164.3, P-185): ele nunca e guardado em cache.
"""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, FrozenSet, Optional, Union

from src.modules.analytics.domain.elasticity import estimate_product_elasticity, prepare_price_points
from src.modules.analytics.domain.exceptions import AnalyticsDomainException, ElasticityProductNotFoundError
from src.modules.analytics.repository import sales_repository
from src.modules.analytics.repository.errors import AnalyticsInfrastructureException
from src.modules.analytics.service import analytics_cache, analytics_service
from src.modules.sales_trend.repository.errors import TrendInfrastructureException
from src.modules.trend_insights.domain.constants import LOGGER_NAME, LOST_CUSTOMER_STATUSES
from src.modules.trend_insights.domain.factor_parcels import SeasonalityEvidence
from src.modules.trend_insights.domain.ports import NotEvaluated
from src.modules.trend_insights.service.evidence_cache import EvidenceCache

logger = logging.getLogger(LOGGER_NAME + ".factors")
UNAVAILABLE_SOURCE = "FONTE_INDISPONIVEL"
SOURCE_ERRORS = (AnalyticsInfrastructureException, AnalyticsDomainException, TrendInfrastructureException)
CHURN_SCOPE_ALL = "TODOS_GERAL"
STOCK_FIELD = "current_stock"


@dataclass(frozen=True)
class ElasticityEvidence:
    """Coeficiente de elasticidade-preco do SKU e a sua confiabilidade (P-159.2)."""

    elasticity: float
    is_reliable: bool
    is_fallback: bool
    confidence_level: str


# ----------------------------------------------------------------------------- leitores padrao (I/O)
def _read_seasonality_response(sku: int) -> Any:
    return analytics_service.get_product_seasonality(sku)


def _read_elasticity_result(sku: int) -> Any:
    catalog = analytics_cache.get_catalog()
    if sku not in catalog.entries:
        raise ElasticityProductNotFoundError()
    cutoff = catalog.reference_date + timedelta(days=analytics_cache.CUTOFF_DAYS_AFTER_REFERENCE)
    points = prepare_price_points(sales_repository.fetch_product_price_points(sku, cutoff))
    return estimate_product_elasticity(points)


def _read_churn_customers() -> Any:
    return analytics_cache.get_churn_customers_list(CHURN_SCOPE_ALL)


def _read_promotion_skus(start: date, end_inclusive: date) -> Any:
    return sales_repository.fetch_promo_skus_in_window(start, end_inclusive)


class FactorSources:
    """Fontes dos fatores com cache de 200 chaves / 6 h; os leitores sao injetaveis (dubles nos testes)."""

    def __init__(
        self,
        cache: EvidenceCache,
        seasonality_reader: Callable[[int], Any] = _read_seasonality_response,
        elasticity_reader: Callable[[int], Any] = _read_elasticity_result,
        churn_reader: Callable[[], Any] = _read_churn_customers,
        stock_reader: Callable[[], Any] = analytics_service.get_cannibalization_catalog,
        promotion_reader: Callable[[date, date], Any] = _read_promotion_skus,
    ):
        self._cache = cache
        self._seasonality_reader = seasonality_reader
        self._elasticity_reader = elasticity_reader
        self._churn_reader = churn_reader
        self._stock_reader = stock_reader
        self._promotion_reader = promotion_reader

    @staticmethod
    def _unavailable(source: str, exc: Exception) -> NotEvaluated:
        logger.warning("tia.factor.unavailable source=%s type=%s", source, type(exc).__name__)
        return NotEvaluated(UNAVAILABLE_SOURCE)

    def seasonality(self, sku: int) -> Union[SeasonalityEvidence, NotEvaluated]:
        try:
            response = self._cache.get_or_build(("seasonality", sku), lambda: self._seasonality_reader(sku))
        except SOURCE_ERRORS as exc:
            return self._unavailable("seasonality", exc)
        data = response.data
        monthly = {int(p.mes): (float(p.indice), str(p.confianca)) for p in data.serie_mensal}
        return SeasonalityEvidence(
            eligible=bool(data.elegivel), strength=str(data.forca), reason=data.motivo_insuficiencia, monthly=monthly)

    def elasticity(self, sku: int) -> Union[ElasticityEvidence, NotEvaluated]:
        try:
            result = self._cache.get_or_build(("elasticity", sku), lambda: self._elasticity_reader(sku))
        except SOURCE_ERRORS as exc:
            return self._unavailable("elasticity", exc)
        return ElasticityEvidence(
            elasticity=float(result.coefficient), is_reliable=bool(result.is_reliable),
            is_fallback=bool(result.fallback_applied), confidence_level=str(result.confidence_level))

    def lost_customer_codes(self) -> Union[FrozenSet[int], NotEvaluated]:
        """Codigos de clientes em risco/inativos. Volatil: o chamador nao pode guardar nem expor (P-164.3)."""
        try:
            customers = self._churn_reader()
        except SOURCE_ERRORS as exc:
            return self._unavailable("churn", exc)
        return frozenset(int(c.customer_code) for c in customers if c.status in LOST_CUSTOMER_STATUSES)

    def current_stock(self, sku: int) -> Union[float, NotEvaluated]:
        try:
            catalog = self._stock_reader()
        except SOURCE_ERRORS as exc:
            return self._unavailable("stock", exc)
        entry: Optional[Any] = catalog.get(str(sku))
        if entry is None or entry.get(STOCK_FIELD) is None:
            return NotEvaluated(UNAVAILABLE_SOURCE)
        return float(entry[STOCK_FIELD])

    def promotion_skus(self, start: date, end_exclusive: date) -> Union[FrozenSet[int], NotEvaluated]:
        """SKUs com promocao na janela `[start, end_exclusive)` (a consulta usa fim inclusivo)."""
        end_inclusive = end_exclusive - timedelta(days=1)
        try:
            skus = self._cache.get_or_build(
                ("promotion", start, end_inclusive), lambda: self._promotion_reader(start, end_inclusive))
        except SOURCE_ERRORS as exc:
            return self._unavailable("promotion", exc)
        return frozenset(int(s) for s in skus)
