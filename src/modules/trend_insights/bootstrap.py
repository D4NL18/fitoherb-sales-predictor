"""
Composition root da F7: unico lugar que liga as camadas (GCS, Vertex AI, Tendencia, Afinidade) ao servico.
Nada aqui acessa rede ou banco ao importar; o servico e montado na primeira requisicao (singleton por processo).
Sem bucket configurado a F7 cai fechada: livro e armazenamento indisponiveis => resumo por template.
"""
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.modules.analytics.service import product_affinity_service
from src.modules.trend_insights.adapters.evidence_adapter import EvidenceBuilder, make_migration_builder
from src.modules.trend_insights.adapters.factor_adapter import FactorSources
from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.llm.gemini_client import GeminiVertexClient
from src.modules.trend_insights.object_storage.gcs_object_store import GcsObjectStore, UnavailableObjectStore
from src.modules.trend_insights.service.evidence_cache import EvidenceCache
from src.modules.trend_insights.service.generation_guard import GenerationGuard
from src.modules.trend_insights.service.insights_service import InsightsService
from src.modules.trend_insights.service.llm_orchestrator import LlmOrchestrator
from src.modules.trend_insights.service.migration_cache import MigrationCache
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.insight_store import InsightStore
from src.modules.trend_insights.store.lease_store import GcsInFlightLease

_SERVICE: Optional[InsightsService] = None
_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _index_status() -> Dict[str, Any]:
    index = product_affinity_service.get_loaded_affinity_index()
    if index is None:
        return {"disponivel": False, "lastSyncAt": None, "totalActiveSkus": 0, "origem": "LOCAL"}
    meta = index.get("meta") or {}
    return {"disponivel": True, "lastSyncAt": meta.get("generatedAt"), "totalActiveSkus": len(index.get("skus") or {}),
            "origem": "LOCAL"}


def _migration_status(cache: MigrationCache) -> List[Dict[str, Any]]:
    """Metadados do cache sem SKU nem cliente (P-187)."""
    result = []
    for entry in cache.status():
        mode, window, base_month, _reference, _generation = entry["key"]
        result.append({
            "modoComparacao": mode, "janela": window, "mesBase": base_month,
            "carregadoEm": entry["loadedAt"].isoformat(), "expiraEm": entry["expiresAt"].isoformat(),
        })
    return result


def _build_service() -> InsightsService:
    settings = TrendInsightsSettings.from_env(os.environ)
    object_store = GcsObjectStore(settings.bucket_name) if settings.bucket_name else UnavailableObjectStore()
    llm = GeminiVertexClient(settings.gcp_project, settings.vertex_location)
    ledger = BudgetLedger(object_store, settings, _utc_now)
    insights = InsightStore(object_store, _utc_now)
    lease = GcsInFlightLease(object_store, _utc_now)
    guard = GenerationGuard(settings, _utc_now)
    orchestrator = LlmOrchestrator(llm, ledger, insights, lease, guard, settings, _utc_now, time.sleep)
    sources = FactorSources(EvidenceCache(_utc_now))
    cache = MigrationCache(make_migration_builder(factor_sources=sources), _utc_now)
    return InsightsService(
        evidence_provider=EvidenceBuilder(cache, sources), orchestrator=orchestrator, insight_store=insights, ledger=ledger,
        lease=lease, settings=settings, clock=_utc_now, index_status_provider=_index_status,
        migration_cache_status_provider=lambda: _migration_status(cache),
    )


def get_default_service() -> InsightsService:
    global _SERVICE
    with _LOCK:
        if _SERVICE is None:
            _SERVICE = _build_service()
        return _SERVICE
