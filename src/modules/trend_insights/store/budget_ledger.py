"""
Livro de gastos no GCS (`ai-budget/AAAA-MM.json`, P-178.2/P-178.3/P-178.8): reserva antes da chamada, acerto com o
`usage` real, escrita otimista (`if_generation_match`) com ate 5 tentativas e FALHA FECHADA (sem livro, sem LLM).
Mes e dia civis em UTC-3. O objeto so tem valores em US$, consultas, contadores de radar e ids opacos de reserva:
nenhum usuario/IP. Radar (v3.1): reserva so de tokens, fatia maxima do teto, radares novos por dia e teto duro de
consultas do mes (nunca se paga busca de proposito).
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.budget import KIND_DIAGNOSIS, KIND_RADAR, budget_level, reservation_amount
from src.modules.trend_insights.domain.constants import (
    BUDGET_TIMEZONE_OFFSET_HOURS,
    LEDGER_MAX_ATTEMPTS,
    LEVEL_CACHE_SECONDS,
    LOGGER_NAME,
    RADAR_BUDGET_SHARE,
    RADAR_MAX_NEW_PER_DAY,
    RADAR_RESERVED_MONTHLY_USD,
)
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
from src.modules.trend_insights.domain.ports import ObjectConflict, ObjectStore, ObjectStoreUnavailable

logger = logging.getLogger(LOGGER_NAME + ".budget")
BUDGET_TZ = timezone(timedelta(hours=BUDGET_TIMEZONE_OFFSET_HOURS))
_EPSILON = 1e-9


@dataclass(frozen=True)
class Reservation:
    """Reserva em aberto; `month_queries` e o contador de consultas lido no momento da reserva."""

    reservation_id: str
    amount_usd: float
    month_queries: int
    path: str
    kind: str = KIND_DIAGNOSIS


@dataclass(frozen=True)
class LedgerSnapshot:
    """Leitura do livro com cache de 60 s: nivel do orcamento, consultas do mes e trava do radar."""

    level: str
    queries: int
    radars_today: int
    radar_spent: float
    radars_month: int = 0


@dataclass(frozen=True)
class RadarLimits:
    """Entrada da politica do radar (`gates.radar_policy`): limite diario, fatia do radar e teto duro de consultas."""

    daily_new: int
    share_spent: bool
    hard_cap: bool


def _empty_document(today: str) -> Dict[str, Any]:
    return {
        "gastoMes": 0.0, "gastoDia": {"data": today, "valor": 0.0}, "reservado": [], "consultasMes": 0,
        "gastoRadarMes": 0.0, "radaresNovosMes": 0, "radaresNovosDia": {"data": today, "valor": 0},
    }


class BudgetLedger:
    def __init__(self, store: ObjectStore, settings: TrendInsightsSettings, clock: Callable[[], datetime]):
        self._store = store
        self._settings = settings
        self._clock = clock
        self._level_cache: Optional[Tuple[datetime, LedgerSnapshot]] = None

    # ---------------------------------------------------------------- tempo
    def _local_now(self) -> datetime:
        return self._clock().astimezone(BUDGET_TZ)

    def _path(self) -> str:
        return f"ai-budget/{self._local_now():%Y-%m}.json"

    def _normalize(self, document: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Completa chaves ausentes, vira o dia e remove reservas vencidas."""
        today = self._local_now().date().isoformat()
        doc = _empty_document(today)
        doc.update(document or {})
        if (doc.get("gastoDia") or {}).get("data") != today:
            doc["gastoDia"] = {"data": today, "valor": 0.0}
        if (doc.get("radaresNovosDia") or {}).get("data") != today:
            doc["radaresNovosDia"] = {"data": today, "valor": 0}
        now = self._clock()
        doc["reservado"] = [r for r in doc.get("reservado") or [] if datetime.fromisoformat(r["expiraEm"]) > now]
        return doc

    # ---------------------------------------------------------------- escrita otimista
    def _read(self, path: str) -> Tuple[Dict[str, Any], int]:
        found = self._store.read_json(path)
        if found is None:
            return self._normalize(None), 0
        content, generation = found
        return self._normalize(content if isinstance(content, dict) else None), generation

    def _mutate(self, mutate: Callable[[Dict[str, Any]], Any]) -> Any:
        """Le, aplica `mutate` e grava com precondicao; conflito repete (ate 5), indisponibilidade falha fechada."""
        path = self._path()
        try:
            for _ in range(LEDGER_MAX_ATTEMPTS):
                document, generation = self._read(path)
                outcome = mutate(document)
                try:
                    self._store.write_json(path, document, if_generation_match=generation)
                    return outcome
                except ObjectConflict:
                    continue
        except ObjectStoreUnavailable:
            raise BudgetUnavailable() from None
        raise BudgetUnavailable()

    # ---------------------------------------------------------------- reserva
    def _check_radar_caps(self, document: Dict[str, Any], amount: float, reserved_radar: float) -> None:
        """Travas do radar (P-178.8, P-180.3): teto duro de consultas, radares por dia e fatia do teto mensal."""
        share_cap = RADAR_BUDGET_SHARE * self._settings.monthly_budget_usd
        is_over_cap = (
            document["consultasMes"] >= self._settings.hard_cap_queries
            or document["radaresNovosDia"]["valor"] >= RADAR_MAX_NEW_PER_DAY
            or document["gastoRadarMes"] + reserved_radar + amount > share_cap + _EPSILON
        )
        if is_over_cap:
            raise BudgetDenied()

    @staticmethod
    def _radar_headroom(document: Dict[str, Any]) -> float:
        """
        Folga protegida para os radares que ainda faltam no mes (arquitetura 15.14.5: ~15 radares = US$ 0,22). So vale
        depois do primeiro radar do mes: assim os diagnosticos nao esgotam o teto antes de os radares restantes serem
        gerados (sem radar o diagnostico sai com `stale` ou `SEM_RADAR`); mes sem radar usa o teto inteiro.
        """
        if document["gastoRadarMes"] <= 0 and document["radaresNovosMes"] <= 0:
            return 0.0
        return max(0.0, RADAR_RESERVED_MONTHLY_USD - document["gastoRadarMes"])

    def reserve(self, model_id: str, with_search: bool, kind: str = KIND_DIAGNOSIS) -> Reservation:
        pricing = self._settings.pricing
        if pricing is None:
            raise BudgetUnavailable()
        state: Dict[str, Any] = {}

        def apply(document: Dict[str, Any]) -> None:
            amount = reservation_amount(
                model_id, pricing, with_search=with_search, month_queries=document["consultasMes"],
                on_date=self._local_now().date(), free_queries=self._settings.free_queries, kind=kind,
            )
            reserved = sum(r["valor"] for r in document["reservado"])
            headroom = 0.0
            if kind == KIND_RADAR:
                reserved_radar = sum(r["valor"] for r in document["reservado"] if r.get("tipo") == KIND_RADAR)
                self._check_radar_caps(document, amount, reserved_radar)
            else:
                headroom = self._radar_headroom(document)
            if (document["gastoMes"] + reserved + amount + headroom > self._settings.monthly_budget_usd + _EPSILON
                    or document["gastoDia"]["valor"] + reserved + amount > self._settings.daily_budget_usd + _EPSILON):
                raise BudgetDenied()
            reservation_id = uuid.uuid4().hex
            expires = self._clock() + timedelta(seconds=self._settings.reservation_ttl_seconds)
            document["reservado"].append(
                {"id": reservation_id, "valor": amount, "expiraEm": expires.isoformat(), "tipo": kind})
            state["reservation"] = Reservation(reservation_id, amount, document["consultasMes"], self._path(), kind)

        self._mutate(apply)
        return state["reservation"]

    def settle(
        self, reservation: Reservation, cost_usd: float, executed_queries: int, new_radar: bool = True,
    ) -> None:
        """
        Troca a reserva pelo custo real (tentativas que gastaram tokens tambem contam, P-178.1). Radar: soma em
        `gastoRadarMes` e, se `new_radar`, nos contadores de radares novos (a nova tentativa do mesmo radar nao conta).
        """
        def apply(document: Dict[str, Any]) -> None:
            document["reservado"] = [r for r in document["reservado"] if r["id"] != reservation.reservation_id]
            document["gastoMes"] += cost_usd
            document["gastoDia"]["valor"] += cost_usd
            document["consultasMes"] += executed_queries
            if reservation.kind != KIND_RADAR:
                return
            document["gastoRadarMes"] += cost_usd
            if new_radar:
                document["radaresNovosMes"] += 1
                document["radaresNovosDia"]["valor"] += 1

        self._mutate(apply)
        self._level_cache = None

    def release(self, reservation: Reservation) -> None:
        """Devolve a reserva sem gasto (chamada que nao consumiu tokens)."""
        def apply(document: Dict[str, Any]) -> None:
            document["reservado"] = [r for r in document["reservado"] if r["id"] != reservation.reservation_id]

        self._mutate(apply)

    # ---------------------------------------------------------------- leitura
    def _snapshot(self) -> LedgerSnapshot:
        """Leitura com cache de 60 s; livro ilegivel = ESGOTADO, cota gratis usada e radar bloqueado (falha fechada)."""
        now = self._clock()
        if self._level_cache and (now - self._level_cache[0]).total_seconds() < LEVEL_CACHE_SECONDS:
            return self._level_cache[1]
        try:
            document, _generation = self._read(self._path())
        except ObjectStoreUnavailable:
            logger.warning("tia.budget.unavailable")
            return LedgerSnapshot("ESGOTADO", self._settings.free_queries, RADAR_MAX_NEW_PER_DAY, float("inf"))
        level = budget_level(
            document["gastoMes"], document["gastoDia"]["valor"],
            self._settings.monthly_budget_usd, self._settings.daily_budget_usd,
        )
        snapshot = LedgerSnapshot(
            level, int(document["consultasMes"]), int(document["radaresNovosDia"]["valor"]),
            float(document["gastoRadarMes"]), int(document["radaresNovosMes"]))
        self._level_cache = (now, snapshot)
        if level == "ALERTA":
            logger.warning("tia.budget.alert")
        return snapshot

    def level(self) -> str:
        """NORMAL/ALERTA/ESGOTADO com cache de 60 s; livro ilegivel conta como ESGOTADO (falha fechada)."""
        return self._snapshot().level

    def month_queries(self) -> int:
        """Consultas de busca executadas no mes (mesmo cache de 60 s do nivel); ilegivel conta como cota gratis usada."""
        return self._snapshot().queries

    def radar_limits(self) -> RadarLimits:
        """Limites do radar para a politica: so leitura (nao reserva nada) e sem expor valores ao cliente."""
        snapshot = self._snapshot()
        share_cap = RADAR_BUDGET_SHARE * self._settings.monthly_budget_usd
        return RadarLimits(
            daily_new=snapshot.radars_today, share_spent=snapshot.radar_spent >= share_cap - _EPSILON,
            hard_cap=snapshot.queries >= self._settings.hard_cap_queries,
        )

    def radars_generated_month(self) -> int:
        """Radares novos do mes (contagem para o `health`; sem valores de custo)."""
        return self._snapshot().radars_month

    def month_label(self) -> str:
        return f"{self._local_now():%Y-%m}"
