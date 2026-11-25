"""
Adaptador da sincronizacao do Indice de Afinidade (contrato 3.5): chama `sync_product_affinity_index`, devolve o
resumo com a geracao do objeto e traduz as falhas do servico de `analytics` em excecoes de dominio da F7.
O log registra so o tipo da excecao (o erro original pode conter dados do ERP).
"""
import logging
from typing import Any, Dict

from src.modules.analytics.service import analytics_service, product_affinity_service
from src.modules.trend_insights.domain.constants import LOGGER_NAME
from src.modules.trend_insights.domain.exceptions import AffinitySyncBusy
from src.modules.trend_insights.domain.ports import TrendSourceUnavailable

logger = logging.getLogger(LOGGER_NAME + ".affinity_sync")


def run_affinity_sync(force: bool) -> Dict[str, Any]:
    try:
        summary = product_affinity_service.sync_product_affinity_index(force=force)
    except (product_affinity_service.AffinitySyncBusyError, product_affinity_service.AffinityIndexConflictError):
        raise AffinitySyncBusy() from None
    except Exception as exc:  # ERP, galeria ou GCS fora do ar: o indice anterior permanece (ANL-001)
        logger.error("tia.affinity_sync.failed type=%s", type(exc).__name__)
        raise TrendSourceUnavailable() from None
    if summary.get("recomputed"):
        analytics_service.reset_cannibalization_report_cache()
    generation = product_affinity_service.get_loaded_generation()
    return {**summary, "object_generation": None if generation is None else str(generation)}
