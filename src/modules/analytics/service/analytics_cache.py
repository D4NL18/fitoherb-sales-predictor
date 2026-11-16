"""
Cache por snapshot do módulo Analytics Comercial (P-059.7, P-068, P-069; ADR-002 DA-05, DA-06, DA-07).

- `AnalyticsSnapshot` imutável com tudo o que as rotas precisam (regras indexadas, itens triviais, SKUs
  com cesta, histórico do cliente, catálogo, contagens). O agregado e a matriz são descartados após a carga.
- Voo único: `threading.Lock` com double-checked locking; requisições simultâneas com cache vazio ou
  expirado disparam uma única carga (CA-19). TTL de `CACHE_TTL_HOURS` (CA-20).
- Troca atômica: o novo snapshot só é publicado após sucesso; falha mantém o anterior (P-068.4).
- `force_reload` respeita o lock: quem chega durante uma carga reaproveita o resultado; recarga antes
  de `MIN_RELOAD_INTERVAL_MINUTES` levanta `ReloadTooSoonError` (`ANL-002`) sem tocar no banco.
- Base insuficiente vira snapshot com `is_base_sufficient=False` (não recarrega a cada chamada).
- `peek_snapshot()` e `get_cache_status()` não usam o lock (health, P-069).
- Catálogo em cache próprio (`get_catalog()`), usado pela busca de produtos sem carregar as cestas.

Logs só com contagens e duração (P-070.2, LGPD-04).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from typing import Dict, FrozenSet, List, Mapping, NamedTuple, Optional, Tuple

import pandas as pd

from src.modules.analytics.domain.cross_sell import (
    MIN_VALID_BASKETS,
    ORDER_DAY_EPOCH,
    CatalogEntry,
    UsefulRule,
    build_catalog_lookup,
    build_valid_baskets,
    count_valid_baskets,
    find_trivial_skus,
    index_rules_by_antecedent,
    is_base_sufficient,
    list_skus_with_basket,
    mine_one_to_one_rules,
    select_useful_rules,
)
from src.modules.analytics.domain.cross_sell_customer import CustomerHistory, build_customer_history
from src.modules.analytics.domain.product_search import SearchableProduct, build_search_index
from src.modules.analytics.repository import sales_repository
from src.modules.analytics.repository.errors import AnalyticsInfrastructureException

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 6                # P-068.2: validade do snapshot e do catálogo
MIN_RELOAD_INTERVAL_MINUTES = 15   # DA-07: intervalo mínimo entre recargas manuais
BUSINESS_UTC_OFFSET_HOURS = -3     # DA-05: data de referência em UTC-3 (offset fixo, sem tzdata)
CUTOFF_DAYS_AFTER_REFERENCE = 1    # DA-02: corte exclusivo = data de referência + 1 dia
MILLISECONDS_PER_SECOND = 1000

STATE_COLD = "FRIO"
STATE_LOADING = "CARREGANDO"
STATE_HOT = "QUENTE"
STATE_EXPIRED = "EXPIRADO"


class ReloadTooSoonError(AnalyticsInfrastructureException):
    """ANL-002: recarga manual antes de `MIN_RELOAD_INTERVAL_MINUTES` desde a última carga (DA-07)."""

    def __init__(self) -> None:
        super().__init__(code="ANL-002", message="A base foi recarregada recentemente. Tente novamente mais tarde.")


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """Snapshot imutável da base analítica (DA-06). `counts` só tem números agregados (health)."""

    reference_date: date
    loaded_at: datetime
    valid_basket_count: int
    is_base_sufficient: bool
    rules_by_antecedent: Mapping[int, Tuple[UsefulRule, ...]]
    trivial_skus: FrozenSet[int]
    skus_with_basket: FrozenSet[int]
    customer_history: Optional[CustomerHistory]
    catalog: Mapping[int, CatalogEntry]
    counts: Mapping[str, int]

    @property
    def reference_day(self) -> int:
        """Data de referência como `order_day` (dias desde 2000-01-01), base de P-062 (DA-05)."""
        return (self.reference_date - ORDER_DAY_EPOCH).days

    @property
    def expires_at(self) -> datetime:
        """Momento em que o snapshot deixa de valer (`loaded_at + CACHE_TTL_HOURS`)."""
        return self.loaded_at + timedelta(hours=CACHE_TTL_HOURS)


@dataclass(frozen=True)
class CatalogSnapshot:
    """Catálogo ativo indexado por SKU e pré-normalizado para a busca (DA-06, contrato §3.6)."""

    reference_date: date
    loaded_at: datetime
    entries: Mapping[int, CatalogEntry]
    search_index: Tuple[SearchableProduct, ...]


class CacheStatus(NamedTuple):
    """Estado do cache para o `estadoCache` do health (Q-7), lido sem lock."""

    state: str
    load_duration_ms: Optional[int]


_SNAPSHOT: Optional[AnalyticsSnapshot] = None
_LOCK = threading.Lock()
_is_loading = False
_load_duration_ms: Optional[int] = None

_CATALOG: Optional[CatalogSnapshot] = None
_CATALOG_LOCK = threading.Lock()


# ------------------------------------------------------------------ relógio e estado

def _utc_now() -> datetime:
    """Relógio do cache em UTC, substituível em teste (CA-20)."""
    return datetime.now(timezone.utc)


def business_date(moment: datetime) -> date:
    """Data de negócio (UTC-3) de um instante UTC (DA-05)."""
    return (moment + timedelta(hours=BUSINESS_UTC_OFFSET_HOURS)).date()


def reset_cache() -> None:
    """Volta ao estado frio: limpa snapshot, catálogo, flag de carga e duração (apoio a teste)."""
    global _SNAPSHOT, _CATALOG, _CHURN_SNAPSHOT, _MONTHLY_SALES_DF, _MONTHLY_SALES_LOADED_AT, _is_loading, _load_duration_ms
    _CHURN_SNAPSHOT = None
    _SNAPSHOT = None
    _CATALOG = None
    _MONTHLY_SALES_DF = None
    _MONTHLY_SALES_LOADED_AT = None
    _is_loading = False
    _load_duration_ms = None


def peek_snapshot() -> Optional[AnalyticsSnapshot]:
    """Snapshot publicado, sem lock e sem disparar carga (P-069)."""
    return _SNAPSHOT


def _is_fresh(loaded_at: datetime) -> bool:
    """Dentro do TTL: `agora - loaded_at < CACHE_TTL_HOURS` (6 h exatas já expiram, CA-20)."""
    return _utc_now() - loaded_at < timedelta(hours=CACHE_TTL_HOURS)


def get_cache_status() -> CacheStatus:
    """`FRIO` | `CARREGANDO` | `QUENTE` | `EXPIRADO`, derivado sem lock (P-069, contrato §3.1)."""
    snapshot = _SNAPSHOT
    if _is_loading:
        return CacheStatus(STATE_LOADING, _load_duration_ms)
    if snapshot is None:
        return CacheStatus(STATE_COLD, None)
    state = STATE_HOT if _is_fresh(snapshot.loaded_at) else STATE_EXPIRED
    return CacheStatus(state, _load_duration_ms)


# ------------------------------------------------------------------ catálogo (cache próprio)

def _load_catalog() -> CatalogSnapshot:
    """Lê o catálogo do repositório e pré-calcula o índice de busca."""
    loaded_at = _utc_now()
    entries = build_catalog_lookup(sales_repository.fetch_catalog())
    return CatalogSnapshot(business_date(loaded_at), loaded_at, entries, build_search_index(entries.values()))


def get_catalog() -> CatalogSnapshot:
    """
    Catálogo ativo com lock e TTL próprios: a busca de produtos funciona com o cache de cestas frio.
    Regra: contrato §3.6; ADR-002 DA-06.
    """
    global _CATALOG
    catalog = _CATALOG
    if catalog is not None and _is_fresh(catalog.loaded_at):
        return catalog
    with _CATALOG_LOCK:
        if _CATALOG is not None and _is_fresh(_CATALOG.loaded_at):
            return _CATALOG
        _CATALOG = _load_catalog()
        return _CATALOG


# ------------------------------------------------------------------ montagem do snapshot

def _mine_rules(valid_baskets, valid_basket_count: int) -> Tuple[UsefulRule, ...]:
    """Regras Úteis; base abaixo do mínimo nem é minerada (XSL-003 de qualquer forma)."""
    if valid_basket_count < MIN_VALID_BASKETS:
        return ()
    return select_useful_rules(mine_one_to_one_rules(valid_baskets), valid_basket_count)


def _build_snapshot() -> AnalyticsSnapshot:
    """
    Carga completa (chamada sob `_LOCK`): catálogo, agregado com corte exclusivo, cestas, mineração e
    histórico do cliente. Não publica nada; quem publica é `get_snapshot`.
    """
    loaded_at = _utc_now()
    reference_date = business_date(loaded_at)
    catalog = get_catalog()
    order_baskets = sales_repository.fetch_order_baskets(reference_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE))
    valid_baskets = build_valid_baskets(order_baskets)
    valid_basket_count = count_valid_baskets(valid_baskets)
    useful_rules = _mine_rules(valid_baskets, valid_basket_count)
    snapshot = AnalyticsSnapshot(
        reference_date=reference_date, loaded_at=loaded_at, valid_basket_count=valid_basket_count,
        is_base_sufficient=is_base_sufficient(valid_basket_count, len(useful_rules)),
        rules_by_antecedent=index_rules_by_antecedent(useful_rules), trivial_skus=find_trivial_skus(valid_baskets),
        skus_with_basket=list_skus_with_basket(valid_baskets), customer_history=build_customer_history(order_baskets),
        catalog=catalog.entries, counts={},
    )
    return _with_counts(snapshot, len(useful_rules))


def _with_counts(snapshot: AnalyticsSnapshot, useful_rule_count: int) -> AnalyticsSnapshot:
    """Acrescenta as contagens agregadas do health e registra a carga só com números (LGPD-04)."""
    counts: Dict[str, int] = {
        "valid_baskets": snapshot.valid_basket_count, "useful_rules": useful_rule_count,
        "trivial_items": len(snapshot.trivial_skus), "skus_with_basket": len(snapshot.skus_with_basket),
    }
    logger.info("Base do analytics montada: %d cestas validas, %d regras uteis, %d itens triviais, %d SKUs com cesta.",
                counts["valid_baskets"], counts["useful_rules"], counts["trivial_items"], counts["skus_with_basket"])
    return replace(snapshot, counts=counts)


# ------------------------------------------------------------------ obtenção com voo único

def _ensure_reload_allowed(current: Optional[AnalyticsSnapshot]) -> None:
    """
    Raises:
        ReloadTooSoonError: última carga terminou há menos de `MIN_RELOAD_INTERVAL_MINUTES` (DA-07).
    """
    if current is None:
        return
    if _utc_now() - current.loaded_at < timedelta(minutes=MIN_RELOAD_INTERVAL_MINUTES):
        raise ReloadTooSoonError()


def _load_and_publish() -> AnalyticsSnapshot:
    """Carga sob o lock; publica só após sucesso e limpa a flag de carga mesmo em erro (P-068.4)."""
    global _SNAPSHOT, _is_loading, _load_duration_ms
    _is_loading = True
    started = time.perf_counter()
    try:
        snapshot = _build_snapshot()
        _load_duration_ms = int((time.perf_counter() - started) * MILLISECONDS_PER_SECOND)
        _SNAPSHOT = snapshot
    finally:
        _is_loading = False
    logger.info("Carga do analytics concluida em %.1f s.", _load_duration_ms / MILLISECONDS_PER_SECOND)
    return snapshot


def _get_or_reload(seen: Optional[AnalyticsSnapshot]) -> AnalyticsSnapshot:
    """
    `force_reload` sob o lock: se outra carga publicou um snapshot enquanto esperávamos, reaproveita;
    senão aplica o intervalo mínimo e recarrega.
    """
    current = _SNAPSHOT
    if current is not None and current is not seen:
        return current
    _ensure_reload_allowed(current)
    return _load_and_publish()


def get_snapshot(force_reload: bool = False) -> AnalyticsSnapshot:
    """
    Snapshot válido, carregando-o uma única vez sob concorrência.

    Args:
        force_reload: recarga manual (P-068.3), sujeita ao intervalo mínimo.

    Raises:
        ReloadTooSoonError: `ANL-002`.
        AnalyticsDataSourceError: `ANL-001`; o snapshot anterior continua publicado.

    Regra: P-068.1 a P-068.4; CA-19, CA-20.
    """
    seen = _SNAPSHOT
    if not force_reload and seen is not None and _is_fresh(seen.loaded_at):
        return seen
    with _LOCK:
        if force_reload:
            return _get_or_reload(seen)
        current = _SNAPSHOT
        if current is not None and _is_fresh(current.loaded_at):
            return current
        return _load_and_publish()


# ---------------------------------------------------------------------------
# F3: Churn de Clientes — Cache por Snapshot (P-117 a P-127; ADR-006 DA-04)
# ---------------------------------------------------------------------------
from src.modules.analytics.domain.churn import (
    ChurnCustomerSummary,
    MonthlyRevenuePoint,
    calculate_churn_metrics,
    evaluate_lost_products,
    rank_churn_customers,
)

@dataclass(frozen=True)
class ChurnCacheSnapshot:
    reference_date: date
    loaded_at: datetime
    customers_by_code: Mapping[int, ChurnCustomerSummary]
    ranked_active_customers: Tuple[ChurnCustomerSummary, ...]
    ranked_inactive_customers: Tuple[ChurnCustomerSummary, ...]
    summary_kpi: Mapping[str, object]

_CHURN_SNAPSHOT: Optional[ChurnCacheSnapshot] = None
_CHURN_LOCK = threading.Lock()


def _build_churn_snapshot() -> ChurnCacheSnapshot:
    now = _utc_now()
    ref_date = business_date(now)
    cutoff = ref_date + timedelta(days=CUTOFF_DAYS_AFTER_REFERENCE)

    orders_df = sales_repository.fetch_customer_orders(cutoff)
    revenue_df = sales_repository.fetch_customer_monthly_revenue(cutoff)
    top_prod_df = sales_repository.fetch_customer_top_products(cutoff)
    catalog = get_catalog().entries

    # Mapear pedidos por cliente
    orders_by_cust: Dict[int, List[date]] = {}
    for row in orders_df.itertuples(index=False):
        c_code = int(row.customer_code)
        orders_by_cust.setdefault(c_code, []).append(row.order_date)

    # Mapear faturamento mensal por cliente
    rev_by_cust: Dict[int, List[MonthlyRevenuePoint]] = {}
    for row in revenue_df.itertuples(index=False):
        c_code = int(row.customer_code)
        rev_by_cust.setdefault(c_code, []).append(
            MonthlyRevenuePoint(year=int(row.year), month=int(row.month), net_revenue=float(row.net_revenue), order_count=int(row.order_count))
        )

    # Mapear produtos comprados por cliente
    prod_by_cust: Dict[int, List[dict]] = {}
    for row in top_prod_df.itertuples(index=False):
        c_code = int(row.customer_code)
        sku = int(row.sku)
        cat_item = catalog.get(sku)
        desc = cat_item.description if cat_item else ""
        forn = cat_item.supplier if cat_item else ""
        prod_by_cust.setdefault(c_code, []).append({
            "sku": sku,
            "descricao": desc,
            "fornecedor": forn,
            "revenue": float(row.revenue),
            "last_date": row.last_date,
        })

    all_cust_codes = set(orders_by_cust.keys()) | set(rev_by_cust.keys())
    active_summaries: List[ChurnCustomerSummary] = []
    inactive_summaries: List[ChurnCustomerSummary] = []
    summaries_map: Dict[int, ChurnCustomerSummary] = {}

    for c_code in all_cust_codes:
        c_orders = orders_by_cust.get(c_code, [])
        c_rev = rev_by_cust.get(c_code, [])
        summary = calculate_churn_metrics(c_code, c_orders, c_rev, ref_date)

        # Enriquecer com produtos perdidos se tiver compras passadas
        if c_code in prod_by_cust:
            lost = tuple(evaluate_lost_products(prod_by_cust[c_code], ref_date))
            summary = replace(summary, produtos_perdidos=lost)

        summaries_map[c_code] = summary
        if summary.status == "INATIVO_RECUPERACAO":
            inactive_summaries.append(summary)
        else:
            active_summaries.append(summary)

    ranked_active = tuple(rank_churn_customers(active_summaries))
    ranked_inactive = tuple(sorted(inactive_summaries, key=lambda c: c.faturamento_medio_mensal, reverse=True))

    total_risco = sum(1 for c in active_summaries if c.status == "EM_RISCO")
    total_alerta = sum(1 for c in active_summaries if c.status == "ALERTA")
    total_saudavel = sum(1 for c in active_summaries if c.status == "SAUDAVEL")
    receita_risco = sum(c.faturamento_medio_mensal for c in active_summaries if c.status == "EM_RISCO")

    summary_kpi = {
        "totalEmRisco": total_risco,
        "totalAlerta": total_alerta,
        "totalSaudavel": total_saudavel,
        "totalInativos": len(ranked_inactive),
        "receitaMensalEmRisco": round(receita_risco, 2),
    }

    return ChurnCacheSnapshot(
        reference_date=ref_date,
        loaded_at=now,
        customers_by_code=summaries_map,
        ranked_active_customers=ranked_active,
        ranked_inactive_customers=ranked_inactive,
        summary_kpi=summary_kpi,
    )


def get_churn_snapshot(force_reload: bool = False) -> ChurnCacheSnapshot:
    global _CHURN_SNAPSHOT
    seen = _CHURN_SNAPSHOT
    if not force_reload and seen is not None and _is_fresh(seen.loaded_at):
        return seen
    with _CHURN_LOCK:
        if not force_reload and _CHURN_SNAPSHOT is not None and _is_fresh(_CHURN_SNAPSHOT.loaded_at):
            return _CHURN_SNAPSHOT
        snapshot = _build_churn_snapshot()
        _CHURN_SNAPSHOT = snapshot
        return snapshot


def get_churn_customers_list(status: Optional[str] = None) -> List[ChurnCustomerSummary]:
    snap = get_churn_snapshot()
    if status is None or status == "TODOS":
        return list(snap.ranked_active_customers)
    return [c for c in snap.ranked_active_customers if c.status == status]


def get_customer_churn_detail(customer_code: int) -> Optional[ChurnCustomerSummary]:
    snap = get_churn_snapshot()
    return snap.customers_by_code.get(customer_code)


def get_inactive_churn_list() -> List[ChurnCustomerSummary]:
    snap = get_churn_snapshot()
    return list(snap.ranked_inactive_customers)


def get_churn_summary_stats() -> dict:
    snap = get_churn_snapshot()
    return dict(snap.summary_kpi)


# ------------------------------------------------------------------ cache de vendas mensais (P-106, ADR-005 DA-07)

_MONTHLY_SALES_DF: Optional[pd.DataFrame] = None
_MONTHLY_SALES_LOADED_AT: Optional[datetime] = None
_MONTHLY_SALES_LOCK = threading.Lock()


def get_monthly_sales(force_reload: bool = False) -> pd.DataFrame:
    """
    Retorna o agregado mensal líquido por SKU, com cache e TTL de 6h (ADR-005 DA-07).
    """
    global _MONTHLY_SALES_DF, _MONTHLY_SALES_LOADED_AT
    seen = _MONTHLY_SALES_DF
    if not force_reload and seen is not None and _MONTHLY_SALES_LOADED_AT is not None and _is_fresh(_MONTHLY_SALES_LOADED_AT):
        return seen

    with _MONTHLY_SALES_LOCK:
        if not force_reload and _MONTHLY_SALES_DF is not None and _MONTHLY_SALES_LOADED_AT is not None and _is_fresh(_MONTHLY_SALES_LOADED_AT):
            return _MONTHLY_SALES_DF

        now = _utc_now()
        ref_date = business_date(now)
        # Exclui mês corrente: corte no 1º dia do mês corrente
        first_of_month = ref_date.replace(day=1)
        df = sales_repository.fetch_monthly_sales(first_of_month)
        _MONTHLY_SALES_DF = df
        _MONTHLY_SALES_LOADED_AT = now
        logger.info("Carga de vendas mensais concluida: %d registros agregados.", len(df))
        return df
