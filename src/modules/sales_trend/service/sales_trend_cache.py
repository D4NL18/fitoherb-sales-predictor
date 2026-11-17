"""
Gerenciamento de cache em memória por snapshot com voo único e TTL (P-083, ADR-003 DA-04).
Garante que requisições concorrentes aguardem a carga em andamento sem duplicar o consumo de memória.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
import threading
from typing import Dict, Mapping, Optional

from src.modules.sales_trend.domain.sales_trend import (
    CACHE_TTL_HOURS,
    MIN_RELOAD_INTERVAL_MINUTES,
    MonthlySales,
    TrendCatalogEntry,
)
from src.modules.sales_trend.domain.suppliers import SupplierGroup, build_supplier_index
from src.modules.sales_trend.repository.errors import (
    TrendDataSourceError,
    TrendInfrastructureException,
)
from src.modules.sales_trend.repository.sales_trend_repository import (
    fetch_active_catalog,
    fetch_monthly_net_sales,
)

logger = logging.getLogger(__name__)

BUSINESS_UTC_OFFSET_HOURS: int = -3


class ReloadTooSoonError(TrendInfrastructureException):
    """TND-005: Recarga solicitada em intervalo inferior ao mínimo permitido (429)."""

    def __init__(self):
        super().__init__(
            code="TND-005",
            message="Recarga solicitada recentemente. Aguarde 15 minutos entre recargas.",
        )


@dataclass(frozen=True)
class SalesTrendSnapshot:
    """Snapshot imutável e autocontido em memória da Tendência de Vendas."""
    reference_date: date
    last_covered_day: date
    loaded_at: datetime
    monthly_sales: MonthlySales
    catalog: Mapping[int, TrendCatalogEntry]
    supplier_index: Mapping[str, SupplierGroup]
    counts: Dict[str, int]


# Estado global do cache
_SNAPSHOT: Optional[SalesTrendSnapshot] = None
_LAST_LOADED_AT: Optional[datetime] = None
_CACHE_LOCK = threading.Lock()
_IS_LOADING: bool = False
_LOAD_DURATION_MS: int = 0


def _utc_now() -> datetime:
    """Retorna o timestamp UTC atual (ponto de injeção para testes)."""
    return datetime.now(timezone.utc)


def business_date(moment: datetime) -> date:
    """Converte momento UTC para a data comercial da Fitoherb (UTC-3)."""
    local_moment = moment + timedelta(hours=BUSINESS_UTC_OFFSET_HOURS)
    return local_moment.date()


def reset_cache() -> None:
    """Reseta o snapshot em memória (usado para isolamento em testes)."""
    global _SNAPSHOT, _LAST_LOADED_AT, _IS_LOADING, _LOAD_DURATION_MS
    with _CACHE_LOCK:
        _SNAPSHOT = None
        _LAST_LOADED_AT = None
        _IS_LOADING = False
        _LOAD_DURATION_MS = 0


def peek_snapshot() -> Optional[SalesTrendSnapshot]:
    """Retorna o snapshot atual sem disparar lock nem carga (leitura não bloqueante para health)."""
    return _SNAPSHOT


def get_cache_status() -> str:
    """Retorna o status do cache: FRIO, CARREGANDO, QUENTE, EXPIRADO."""
    if _IS_LOADING:
        return "CARREGANDO"
    if _SNAPSHOT is None:
        return "FRIO"
    now = _utc_now()
    if now - _SNAPSHOT.loaded_at >= timedelta(hours=CACHE_TTL_HOURS):
        return "EXPIRADO"
    return "QUENTE"


def _build_snapshot() -> SalesTrendSnapshot:
    """Executa a carga do catálogo ativo e do agregado no SQL Server."""
    start_time = _utc_now()
    ref_date = business_date(start_time)
    last_covered = ref_date - timedelta(days=1)

    # 1. Carrega catálogo ativo
    catalog = fetch_active_catalog()
    active_skus = set(catalog.keys())

    # 2. Carrega agregado mensal filtrando pelos ativos
    monthly_sales = fetch_monthly_net_sales(
        cutoff_date=ref_date,
        active_skus=active_skus,
    )

    # 3. Monta índice de fornecedores
    supplier_index = build_supplier_index(catalog)

    duration_ms = int((_utc_now() - start_time).total_seconds() * 1000)

    counts = {
        "active_catalog_skus": len(catalog),
        "retained_sales_skus": len(monthly_sales.series),
        "suppliers_count": len(supplier_index),
        "month_count": monthly_sales.month_count,
        "load_duration_ms": duration_ms,
    }

    logger.info(
        "[SALES_TREND_CACHE] Snapshot criado em %d ms: %d SKUs ativos, %d fornecedores",
        duration_ms,
        len(catalog),
        len(supplier_index),
    )

    return SalesTrendSnapshot(
        reference_date=ref_date,
        last_covered_day=last_covered,
        loaded_at=start_time,
        monthly_sales=monthly_sales,
        catalog=catalog,
        supplier_index=supplier_index,
        counts=counts,
    )


def get_snapshot(force_reload: bool = False) -> SalesTrendSnapshot:
    """
    Retorna o snapshot do cache em memória.
    Utiliza double-checked locking para garantir voo único seguro entre threads concorrentes.
    """
    global _SNAPSHOT, _LAST_LOADED_AT, _IS_LOADING, _LOAD_DURATION_MS

    now = _utc_now()

    # Fast-path: se o cache estiver quente e não for recarga forçada, retorna imediatamente
    if not force_reload and _SNAPSHOT is not None:
        if now - _SNAPSHOT.loaded_at < timedelta(hours=CACHE_TTL_HOURS):
            return _SNAPSHOT

    with _CACHE_LOCK:
        now = _utc_now()

        # Verifica rate-limit de 15 minutos em recargas forçadas
        if force_reload and _LAST_LOADED_AT is not None:
            if now - _LAST_LOADED_AT < timedelta(minutes=MIN_RELOAD_INTERVAL_MINUTES):
                raise ReloadTooSoonError()

        # Double-check após adquirir o lock
        if not force_reload and _SNAPSHOT is not None:
            if now - _SNAPSHOT.loaded_at < timedelta(hours=CACHE_TTL_HOURS):
                return _SNAPSHOT

        _IS_LOADING = True
        try:
            new_snapshot = _build_snapshot()
            _SNAPSHOT = new_snapshot
            _LAST_LOADED_AT = now
            _LOAD_DURATION_MS = new_snapshot.counts["load_duration_ms"]
            return _SNAPSHOT
        finally:
            _IS_LOADING = False
