"""
Rota de maquina `POST /internal/v1/affinity-index/sync` (contrato 3.5). Chamada so pelo Cloud Scheduler com token
OIDC; o Basic global e dispensado apenas para este metodo e caminho (`src/core/auth.py`). Controller fino: valida a
identidade, aciona o executor injetado e devolve `{data, meta}`. Todas as falhas de credencial dao a mesma resposta.
"""
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Protocol

from fastapi import APIRouter, Depends, Header, Query

from src.modules.trend_insights.api.route import InsightsAPIRoute
from src.modules.trend_insights.config import SchedulerAuthSettings
from src.modules.trend_insights.domain.constants import CONTRACT_VERSION
from src.modules.trend_insights.domain.exceptions import SchedulerUnauthorized
from src.modules.trend_insights.domain.scheduler_identity import is_authorized_invoker

BEARER_PREFIX = "bearer "


class OidcVerifier(Protocol):
    def verify(self, token: str, audience: str) -> Mapping[str, Any]: ...


def get_oidc_verifier() -> OidcVerifier:
    """Dependencia substituivel nos testes; a implementacao do Google fica fora do pacote `api`."""
    from src.modules.trend_insights.auth.oidc_verifier import GoogleOidcVerifier

    return GoogleOidcVerifier()


def get_affinity_sync_runner() -> Callable[[bool], Dict[str, Any]]:
    """Dependencia substituivel nos testes; a fiacao de producao fica em `bootstrap`."""
    from src.modules.trend_insights.bootstrap import get_affinity_sync_runner as build_runner

    return build_runner()


def require_scheduler_identity(
    authorization: Optional[str] = Header(default=None),
    verifier: OidcVerifier = Depends(get_oidc_verifier),
) -> None:
    settings = SchedulerAuthSettings.from_env(os.environ)
    if not settings.is_configured or not authorization or not authorization.lower().startswith(BEARER_PREFIX):
        raise SchedulerUnauthorized()
    try:
        claims = verifier.verify(authorization[len(BEARER_PREFIX):].strip(), settings.audience)
    except Exception:  # qualquer falha do verificador e credencial invalida; a causa nao e revelada
        raise SchedulerUnauthorized() from None
    if not is_authorized_invoker(claims, settings.audience, settings.invoker_email):
        raise SchedulerUnauthorized()


def _summary_payload(summary: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "lastSyncAt": summary.get("last_sync_at"), "recomputed": bool(summary.get("recomputed")),
        "totalActiveSkus": summary.get("total_active_skus"),
        "galleryProductsFetched": summary.get("gallery_products_fetched"),
        "galleryMatchedSkus": summary.get("gallery_matched_skus"), "addedCount": summary.get("added_count"),
        "updatedCount": summary.get("updated_count"), "removedCount": summary.get("removed_count"),
        "unchangedCount": summary.get("unchanged_count"), "durationMs": summary.get("duration_ms"),
        "geracaoObjeto": summary.get("object_generation"),
    }


internal_router = APIRouter(prefix="/internal/v1", tags=["Interno"], route_class=InsightsAPIRoute)


@internal_router.post("/affinity-index/sync", summary="Sincroniza o índice de afinidade (Cloud Scheduler, OIDC)")
def sync_affinity_index(
    force: bool = Query(False),
    _identity: None = Depends(require_scheduler_identity),
    run_sync: Callable[[bool], Dict[str, Any]] = Depends(get_affinity_sync_runner),
):
    summary = run_sync(force)
    return {
        "data": _summary_payload(summary),
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat(), "version": CONTRACT_VERSION},
    }
