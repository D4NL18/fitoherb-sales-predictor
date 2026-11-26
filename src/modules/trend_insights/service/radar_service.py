"""
Servico do radar externo (P-180.3): `peek` so LE (nunca gera, custo zero: GET, templates e `health`) e
`get_or_create` aplica a politica (`gates.radar_policy`): usa o fresco, gera com single-flight (trava em processo
e trava entre instancias de 90 s) ou cai para o `stale`/ausente. `force` do diagnostico NAO renova o radar.
Falha do radar (infra, schema, orcamento, teto de consultas) nunca e erro: devolve `None` e o diagnostico segue.
"""
import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.constants import (
    LOGGER_NAME,
    RADAR_DEADLINE_SECONDS,
    RADAR_LEASE_TTL_SECONDS,
)
from src.modules.trend_insights.domain.gates import radar_policy
from src.modules.trend_insights.domain.ports import InFlightLease, ObjectConflict, ObjectStoreUnavailable
from src.modules.trend_insights.domain.radar_policy import STATE_ABSENT, STATE_FRESH, radar_age_days, radar_freshness
from src.modules.trend_insights.domain.radar_themes import NO_EVIDENCE_TEXT, RADAR_THEME_TEXTS
from src.modules.trend_insights.domain.raw_material import RadarSubject
from src.modules.trend_insights.llm.client import LlmClient
from src.modules.trend_insights.service.radar_runner import RadarRunner
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.radar_store import RadarStore, StoredRadar

logger = logging.getLogger(LOGGER_NAME + ".radar")
LEASE_POLL_SECONDS = 2.0
ORIGIN_GENERATED, ORIGIN_CACHE = "GERADO_AGORA", "CACHE"
SOURCE_FIELDS = ("id", "url", "dominio", "titulo", "dataPublicacao", "origemData")


@dataclass(frozen=True)
class RadarView:
    """Radar utilizavel com o estado calculado no relogio atual (`FRESCO` ou `DESATUALIZADO`) e a origem na resposta."""

    radar: StoredRadar
    state: str
    age_days: int
    origin: Optional[str] = None

    @property
    def is_stale(self) -> bool:
        return self.state != STATE_FRESH

    def with_origin(self, origin: str) -> "RadarView":
        return RadarView(self.radar, self.state, self.age_days, origin)

    @property
    def response_state(self) -> str:
        """`meta.ia.radar.estado`: `GERADO_AGORA` so no POST que gerou; senao o estado de validade."""
        return ORIGIN_GENERATED if self.origin == ORIGIN_GENERATED else self.state


def _note_for(dimension: Dict[str, Any]) -> Optional[str]:
    """Frase fixa do backend a partir do tema; nunca texto vindo da web (P-184.6)."""
    if dimension["status"] == "SEM_EVIDENCIA":
        return NO_EVIDENCE_TEXT
    return RADAR_THEME_TEXTS.get((dimension["dimensao"], dimension["tema"]))


def _public_sources(radar: StoredRadar, ids: Any) -> list:
    by_id = radar.source_by_id()
    return [{key: by_id[i].get(key) for key in SOURCE_FIELDS} for i in ids if i in by_id]


def public_radar_ref(view: RadarView) -> Dict[str, Any]:
    """`diagnosticoIa.radar` (RadarRef, contrato 3.1.6.2): sem slug, hash, custo ou consultas."""
    radar = view.radar
    return {
        "assunto": {"termo": radar.term, "tipo": radar.kind}, "mesBase": radar.base_month,
        "geradoEm": radar.generated_at.isoformat(), "diasDesdeGeracao": view.age_days,
        "desatualizado": view.is_stale, "origem": view.origin or ORIGIN_CACHE,
    }


def cached_radar_ref(ref: Optional[Dict[str, Any]], now: datetime) -> Optional[Dict[str, Any]]:
    """RadarRef de um diagnostico salvo, com idade e validade recalculadas agora (origem sempre `CACHE`)."""
    if not ref:
        return None
    generated_at = datetime.fromisoformat(ref["geradoEm"])
    return {
        "assunto": {"termo": ref["termo"], "tipo": ref["tipo"]}, "mesBase": ref["mesBase"],
        "geradoEm": ref["geradoEm"], "diasDesdeGeracao": radar_age_days(generated_at, now),
        "desatualizado": radar_freshness(generated_at, ref["mesBase"], now) != STATE_FRESH, "origem": ORIGIN_CACHE,
    }


def public_radar_view(view: RadarView) -> Dict[str, Any]:
    """`data.radarExterno` somente leitura: SEM `direcao`, `relevanciaAoProduto` e `confianca`."""
    radar = view.radar
    dimensions = [
        {
            "dimensao": d["dimensao"], "status": d["status"], "movimento": d["movimento"],
            "intensidade": d["intensidade"], "tema": d["tema"], "notaRadar": _note_for(d),
            "fontes": _public_sources(radar, d["fonteIds"]),
        }
        for d in radar.dimensions
    ]
    ref = public_radar_ref(view)
    return {key: ref[key] for key in ("assunto", "mesBase", "geradoEm", "diasDesdeGeracao", "desatualizado")} | {
        "dimensoes": dimensions}


class RadarService:
    def __init__(self, llm: LlmClient, ledger: BudgetLedger, radar_store: RadarStore, lease: InFlightLease,
                 settings: TrendInsightsSettings, clock: Callable[[], datetime], sleep: Callable[[float], None]):
        self._ledger = ledger
        self._store = radar_store
        self._lease = lease
        self._clock = clock
        self._sleep = sleep
        self._runner = RadarRunner(llm=llm, ledger=ledger, settings=settings, clock=clock, sleep=sleep)
        self._key_locks: Dict[str, threading.Lock] = {}
        self._locks_mutex = threading.Lock()

    # ---------------------------------------------------------------- leitura (custo zero)
    def peek(self, subject: Optional[RadarSubject], base_month: str) -> Optional[RadarView]:
        """Radar fresco ou `stale` (ate 120 d da geracao); `None` se ausente, invalido ou fora da janela."""
        if subject is None:
            return None
        try:
            radar = self._store.get(subject.slug, base_month)
        except ObjectStoreUnavailable:
            return None
        if radar is None:
            return None
        now = self._clock()
        state = radar_freshness(radar.generated_at, radar.base_month, now)
        if state == STATE_ABSENT:
            return None
        return RadarView(radar, state, radar_age_days(radar.generated_at, now))

    def cached_count(self) -> int:
        try:
            return self._store.count()
        except ObjectStoreUnavailable:
            return 0

    def generated_this_month(self) -> int:
        return self._ledger.radars_generated_month()

    # ---------------------------------------------------------------- uso no diagnostico
    def get_or_create(self, subject: Optional[RadarSubject], base_month: str) -> Optional[RadarView]:
        """Radar para o diagnostico: fresco, recem-gerado, `stale` ou `None` (SEM_RADAR)."""
        if subject is None:
            return None
        view = self.peek(subject, base_month)
        limits = self._ledger.radar_limits()
        decision = radar_policy(
            view.state if view else STATE_ABSENT, self._ledger.level(), limits.daily_new, limits.share_spent,
            limits.hard_cap)
        if decision in ("USE_FRESH", "USE_STALE"):
            return view.with_origin(ORIGIN_CACHE)
        if decision == "NONE":
            return None
        return self._generate(subject, base_month, view)

    # ---------------------------------------------------------------- geracao com single-flight
    def _key_lock(self, subject: RadarSubject, base_month: str) -> threading.Lock:
        with self._locks_mutex:
            return self._key_locks.setdefault(f"{subject.slug}/{base_month}", threading.Lock())

    @staticmethod
    def _lease_key(subject: RadarSubject, base_month: str) -> str:
        digest = hashlib.sha256(f"radar/{subject.slug}/{base_month}".encode("utf-8")).hexdigest()
        return f"radar-{digest[:36]}"

    def _fresh_shared(self, subject: RadarSubject, base_month: str) -> Optional[RadarView]:
        view = self.peek(subject, base_month)
        return view.with_origin(ORIGIN_CACHE) if view and view.state == STATE_FRESH else None

    def _generate(self, subject: RadarSubject, base_month: str, stale: Optional[RadarView]) -> Optional[RadarView]:
        lock = self._key_lock(subject, base_month)
        with lock:
            shared = self._fresh_shared(subject, base_month)
            if shared:
                return shared
            return self._generate_with_lease(subject, base_month, stale)

    def _wait_for_other_instance(self, subject: RadarSubject, base_month: str, lease_key: str) -> bool:
        """Seguidor entre instancias: espera o radar compartilhado ate o prazo do radar; `True` se obteve a trava."""
        started = self._clock()
        while not self._lease.try_acquire(lease_key, RADAR_LEASE_TTL_SECONDS):
            if self._fresh_shared(subject, base_month):
                return False
            if (self._clock() - started).total_seconds() >= RADAR_DEADLINE_SECONDS:
                return False
            self._sleep(LEASE_POLL_SECONDS)
        return True

    def _generate_with_lease(self, subject: RadarSubject, base_month: str, stale: Optional[RadarView]
                             ) -> Optional[RadarView]:
        lease_key = self._lease_key(subject, base_month)
        if not self._wait_for_other_instance(subject, base_month, lease_key):
            return self._fresh_shared(subject, base_month) or (stale.with_origin(ORIGIN_CACHE) if stale else None)
        try:
            shared = self._fresh_shared(subject, base_month)
            if shared:
                return shared
            return self._run_and_store(subject, base_month, stale)
        finally:
            self._lease.release(lease_key)

    def _run_and_store(self, subject: RadarSubject, base_month: str, stale: Optional[RadarView]
                       ) -> Optional[RadarView]:
        radar = self._runner.run(subject, base_month)
        if radar is None:
            return stale.with_origin(ORIGIN_CACHE) if stale else None
        try:
            generation = self._store.current_generation(subject.slug, base_month)
            self._store.put(radar, generation)
        except ObjectConflict:
            return self._fresh_shared(subject, base_month) or None  # outro escritor chegou antes: usa o dele
        except ObjectStoreUnavailable:
            logger.warning("tia.radar.save_failed")  # usa em memoria neste pedido; sem gravar nao ha reuso
        now = self._clock()
        return RadarView(radar, STATE_FRESH, radar_age_days(radar.generated_at, now), ORIGIN_GENERATED)
