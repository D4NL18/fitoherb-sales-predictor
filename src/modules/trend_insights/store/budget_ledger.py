"""
Livro de gastos no GCS (`ai-budget/AAAA-MM.json`, P-178.2/P-178.3): reserva antes da chamada, acerto com o
`usage` real, escrita otimista (`if_generation_match`) com ate 5 tentativas e FALHA FECHADA (sem livro, sem LLM).
Mes e dia civis em UTC-3. O objeto so tem valores em US$, consultas e ids opacos de reserva: nenhum usuario/IP.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.budget import budget_level, reservation_amount
from src.modules.trend_insights.domain.constants import (
    BUDGET_TIMEZONE_OFFSET_HOURS,
    LEDGER_MAX_ATTEMPTS,
    LEVEL_CACHE_SECONDS,
    LOGGER_NAME,
    RESERVATION_TTL_SECONDS,
)
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
from src.modules.trend_insights.domain.ports import ObjectConflict, ObjectStore, ObjectStoreUnavailable

logger = logging.getLogger(LOGGER_NAME + ".budget")
BUDGET_TZ = timezone(timedelta(hours=BUDGET_TIMEZONE_OFFSET_HOURS))


@dataclass(frozen=True)
class Reservation:
    """Reserva em aberto; `month_queries` e o contador de consultas lido no momento da reserva."""

    reservation_id: str
    amount_usd: float
    month_queries: int
    path: str


def _empty_document(today: str) -> Dict[str, Any]:
    return {"gastoMes": 0.0, "gastoDia": {"data": today, "valor": 0.0}, "reservado": [], "consultasMes": 0}


class BudgetLedger:
    def __init__(self, store: ObjectStore, settings: TrendInsightsSettings, clock: Callable[[], datetime]):
        self._store = store
        self._settings = settings
        self._clock = clock
        self._level_cache: Optional[Tuple[datetime, str, int]] = None  # (leitura, nivel, consultas do mes)

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

    # ---------------------------------------------------------------- API
    def reserve(self, model_id: str, with_search: bool) -> Reservation:
        pricing = self._settings.pricing
        if pricing is None:
            raise BudgetUnavailable()
        state: Dict[str, Any] = {}

        def apply(document: Dict[str, Any]) -> None:
            amount = reservation_amount(
                model_id, pricing, with_search=with_search, month_queries=document["consultasMes"],
                on_date=self._local_now().date(), free_queries=self._settings.free_queries,
            )
            reserved = sum(r["valor"] for r in document["reservado"])
            if (document["gastoMes"] + reserved + amount > self._settings.monthly_budget_usd + 1e-9
                    or document["gastoDia"]["valor"] + reserved + amount > self._settings.daily_budget_usd + 1e-9):
                raise BudgetDenied()
            reservation_id = uuid.uuid4().hex
            expires = self._clock() + timedelta(seconds=RESERVATION_TTL_SECONDS)
            document["reservado"].append({"id": reservation_id, "valor": amount, "expiraEm": expires.isoformat()})
            state["reservation"] = Reservation(reservation_id, amount, document["consultasMes"], self._path())

        self._mutate(apply)
        return state["reservation"]

    def settle(self, reservation: Reservation, cost_usd: float, executed_queries: int) -> None:
        """Troca a reserva pelo custo real (tentativas que gastaram tokens tambem contam, P-178.1)."""
        def apply(document: Dict[str, Any]) -> None:
            document["reservado"] = [r for r in document["reservado"] if r["id"] != reservation.reservation_id]
            document["gastoMes"] += cost_usd
            document["gastoDia"]["valor"] += cost_usd
            document["consultasMes"] += executed_queries

        self._mutate(apply)
        self._level_cache = None

    def release(self, reservation: Reservation) -> None:
        """Devolve a reserva sem gasto (chamada que nao consumiu tokens)."""
        def apply(document: Dict[str, Any]) -> None:
            document["reservado"] = [r for r in document["reservado"] if r["id"] != reservation.reservation_id]

        self._mutate(apply)

    def _snapshot(self) -> Tuple[str, int]:
        """`(nivel, consultas do mes)` com cache de 60 s; livro ilegivel = ESGOTADO e cota gratis ja usada (falha fechada)."""
        now = self._clock()
        if self._level_cache and (now - self._level_cache[0]).total_seconds() < LEVEL_CACHE_SECONDS:
            return self._level_cache[1], self._level_cache[2]
        try:
            document, _generation = self._read(self._path())
        except ObjectStoreUnavailable:
            logger.warning("tia.budget.unavailable")
            return "ESGOTADO", self._settings.free_queries
        level = budget_level(
            document["gastoMes"], document["gastoDia"]["valor"],
            self._settings.monthly_budget_usd, self._settings.daily_budget_usd,
        )
        self._level_cache = (now, level, int(document["consultasMes"]))
        if level == "ALERTA":
            logger.warning("tia.budget.alert")
        return level, int(document["consultasMes"])

    def level(self) -> str:
        """NORMAL/ALERTA/ESGOTADO com cache de 60 s; livro ilegivel conta como ESGOTADO (falha fechada)."""
        return self._snapshot()[0]

    def month_queries(self) -> int:
        """Consultas de busca executadas no mes (mesmo cache de 60 s do nivel); ilegivel conta como cota gratis usada."""
        return self._snapshot()[1]

    def month_label(self) -> str:
        return f"{self._local_now():%Y-%m}"
