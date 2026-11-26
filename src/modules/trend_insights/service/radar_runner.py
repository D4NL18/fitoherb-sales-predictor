"""
Execucao da chamada do radar externo (P-180.3, P-183.5): UMA chamada com busca (modelo `TREND_AI_MODEL_RADAR`),
sem dado da empresa, prazo proprio de 55 s, 1 nova tentativa por violacao de schema, ate 2 tentativas por falha
de infraestrutura e depois UMA ao Flash (fallback permitido). Cada tentativa reserva e acerta no livro (tokens
gastos contam mesmo quando a saida e rejeitada). Radar que falha NAO e gravado e nunca derruba o diagnostico.
Nenhuma string da web entra no radar alem de URL, dominio, titulo e data validados das fontes.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.budget import KIND_RADAR
from src.modules.trend_insights.domain.constants import (
    LLM_BACKOFF_BASE_SECONDS,
    LLM_SCHEMA_RETRY_LIMIT,
    LLM_TIMEOUT_SECONDS,
    LLM_TRANSIENT_RETRY_LIMIT,
    LOGGER_NAME,
    RADAR_DEADLINE_SECONDS,
    RADAR_MAX_OUTPUT_TOKENS,
    RADAR_MAX_SOURCES,
    RADAR_SOURCE_LOOKBACK_DAYS,
)
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
from src.modules.trend_insights.domain.raw_material import RadarSubject
from src.modules.trend_insights.llm.client import (
    LlmBlockedError,
    LlmClient,
    LlmError,
    LlmQuotaExhaustedError,
    LlmRequest,
    LlmRequestRejectedError,
    LlmResponse,
    LlmTransientError,
)
from src.modules.trend_insights.llm.pricing import compute_cost
from src.modules.trend_insights.llm.prompts import build_radar_prompts
from src.modules.trend_insights.llm.radar_schema import RADAR_OUTPUT_SCHEMA, parse_radar_output
from src.modules.trend_insights.llm.search_queries import build_radar_queries
from src.modules.trend_insights.llm.validation import date_from_url, is_safe_url, parse_iso_date
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.radar_store import StoredRadar, compute_radar_hash

logger = logging.getLogger(LOGGER_NAME + ".radar")
THINKING_LEVEL = "low"
BACKOFF_FACTOR = 2
MAX_TITLE_CHARS = 200
EMPTY_DIMENSION = {"status": "SEM_EVIDENCIA", "movimento": "INDEFINIDO", "intensidade": None, "tema": None}


@dataclass
class _Call:
    model_id: str
    subject: RadarSubject
    base_month: str
    remaining: float


class RadarRunner:
    def __init__(self, llm: LlmClient, ledger: BudgetLedger, settings: TrendInsightsSettings,
                 clock: Callable[[], datetime], sleep: Callable[[float], None]):
        self._llm = llm
        self._ledger = ledger
        self._settings = settings
        self._clock = clock
        self._sleep = sleep

    # ---------------------------------------------------------------- fontes e dimensoes
    @staticmethod
    def _period_limit(base_month: str) -> date:
        """Fonte mais antiga que 270 dias do fim do mes-base e ANTIGA e descartada (P-180.3)."""
        year, month = int(base_month[:4]), int(base_month[5:7])
        first_next = date(year + month // 12, month % 12 + 1, 1)
        return first_next - timedelta(days=1 + RADAR_SOURCE_LOOKBACK_DAYS)

    @staticmethod
    def _build_source(citation: Any, data_fonte: Optional[str], limit: date) -> Optional[Dict[str, Any]]:
        """Fonte validada (https publico, data dentro do limite) ou `None`; titulo e dado da web (so exibicao)."""
        if not is_safe_url(citation.url):
            return None
        url = citation.url.strip()
        model_date, url_date = parse_iso_date(data_fonte), date_from_url(url)
        resolved = model_date or url_date
        if resolved and resolved < limit:
            return None
        origin = "MODELO" if model_date else ("URL" if url_date else "SEM_DATA")
        return {"url": url, "dominio": urlparse(url).hostname, "titulo": (citation.title or "")[:MAX_TITLE_CHARS],
                "dataPublicacao": resolved.isoformat() if resolved else None, "origemData": origin}

    def _assemble(self, parsed: Tuple[Dict[str, Any], ...], response: LlmResponse, base_month: str
                  ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Dimensoes normalizadas e fontes `F1..F16`; AVALIADA sem fonte valida vira SEM_EVIDENCIA."""
        limit = self._period_limit(base_month)
        ids_by_url: Dict[str, str] = {}
        sources: List[Dict[str, Any]] = []
        dimensions: List[Dict[str, Any]] = []
        for item in parsed:
            source = None
            has_index = item["status"] == "AVALIADA" and item["fonteIdx"] is not None
            if has_index and len(sources) < RADAR_MAX_SOURCES:
                source = self._build_source(response.citations[item["fonteIdx"]], item["dataFonte"], limit)
            if source is None:
                dimensions.append({"dimensao": item["dimensao"], **EMPTY_DIMENSION, "fonteIds": []})
                continue
            source_id = ids_by_url.get(source["url"])
            if source_id is None:
                source_id = f"F{len(sources) + 1}"
                ids_by_url[source["url"]] = source_id
                sources.append({"id": source_id, **source})
            dimensions.append({
                "dimensao": item["dimensao"], "status": "AVALIADA", "movimento": item["movimento"],
                "intensidade": item["intensidade"], "tema": item["tema"] or "OUTRO", "fonteIds": [source_id],
            })
        return dimensions, sources

    def _to_stored(self, parsed: Tuple[Dict[str, Any], ...], response: LlmResponse, subject: RadarSubject,
                   base_month: str, queries: int) -> StoredRadar:
        dimensions, sources = self._assemble(parsed, response, base_month)
        return StoredRadar(
            generated_at=self._clock(), model=response.model_id, slug=subject.slug, term=subject.termo,
            kind=subject.tipo, base_month=base_month, dimensions=tuple(dimensions), sources=tuple(sources),
            queries_executed=queries, search_suggestions_html=None,  # HTML cru de terceiros nunca e persistido (S-4)
            radar_hash=compute_radar_hash(dimensions, sources),
        )

    # ---------------------------------------------------------------- uma tentativa
    def _request(self, call: _Call) -> LlmRequest:
        system_prompt, user_prompt = build_radar_prompts(
            call.subject, call.base_month, build_radar_queries(call.subject, call.base_month))
        return LlmRequest(
            model_id=call.model_id, system_prompt=system_prompt, user_prompt=user_prompt,
            response_schema=RADAR_OUTPUT_SCHEMA, use_search_grounding=True, thinking_level=THINKING_LEVEL,
            max_output_tokens=RADAR_MAX_OUTPUT_TOKENS,
            timeout_seconds=min(LLM_TIMEOUT_SECONDS, max(1.0, call.remaining)), request_tag="radar",
        )

    def _call(self, call: _Call, state: "_State") -> LlmResponse:
        """Reserva, chama e acerta com o `usage` real; sem acerto, a reserva e devolvida."""
        reservation = self._ledger.reserve(call.model_id, True, kind=KIND_RADAR)
        settled = False
        try:
            response = self._llm.generate(self._request(call))
            cost = compute_cost(
                response.model_id or call.model_id, response.usage, self._settings.pricing, self._clock().date(),
                response.executed_queries_count, reservation.month_queries, self._settings.free_queries,
            )
            self._ledger.settle(reservation, cost, response.executed_queries_count, new_radar=not state.has_settled)
            settled = state.has_settled = True
        finally:
            if not settled:
                self._release_quietly(reservation)
        logger.info("tia.radar.call model=%s status=%s searchQueries=%d costUsd=%.5f latencyMs=%d",
                    call.model_id, "settled", response.executed_queries_count, cost, response.latency_ms)
        return response

    def _release_quietly(self, reservation) -> None:
        try:
            self._ledger.release(reservation)
        except BudgetUnavailable:
            logger.warning("tia.budget.release_failed")

    def _parse(self, response: LlmResponse):
        return parse_radar_output(response.text, source_count=len(response.citations))

    # ---------------------------------------------------------------- ciclo da geracao
    def _primary(self, subject: RadarSubject, base_month: str, started_at: datetime, state: "_State"
                 ) -> Tuple[Optional[StoredRadar], bool]:
        """`(radar, vai_ao_flash)`: infra esgotada vai ao fallback; schema esgotado nao troca de modelo."""
        model_id = self._settings.model_radar
        transient_failures = schema_retries = 0
        while self._remaining(started_at) > 0:
            call = _Call(model_id, subject, base_month, self._remaining(started_at))
            try:
                response = self._call(call, state)
            except (LlmTransientError, LlmQuotaExhaustedError):
                transient_failures += 1
                if transient_failures >= LLM_TRANSIENT_RETRY_LIMIT:
                    return None, True
                self._sleep(LLM_BACKOFF_BASE_SECONDS * BACKOFF_FACTOR ** (transient_failures - 1))
                continue
            except LlmRequestRejectedError:
                return None, True
            except LlmBlockedError:
                response = None
            radar = self._radar_from(response, subject, base_month)
            if radar is not None:
                return radar, False
            if schema_retries >= LLM_SCHEMA_RETRY_LIMIT:
                return None, False
            schema_retries += 1
        return None, False

    def _radar_from(self, response: Optional[LlmResponse], subject: RadarSubject, base_month: str
                    ) -> Optional[StoredRadar]:
        if response is None:
            return None
        parsed = self._parse(response)
        if not parsed.ok:
            return None
        return self._to_stored(parsed.dimensions, response, subject, base_month, response.executed_queries_count)

    def _fallback(self, subject: RadarSubject, base_month: str, started_at: datetime, state: "_State"
                  ) -> Optional[StoredRadar]:
        if self._remaining(started_at) <= 0 or self._settings.model_fallback == self._settings.model_radar:
            return None
        call = _Call(self._settings.model_fallback, subject, base_month, self._remaining(started_at))
        try:
            response = self._call(call, state)
        except LlmError:
            return None
        return self._radar_from(response, subject, base_month)

    def _remaining(self, started_at: datetime) -> float:
        return RADAR_DEADLINE_SECONDS - (self._clock() - started_at).total_seconds()

    def run(self, subject: RadarSubject, base_month: str) -> Optional[StoredRadar]:
        """Radar valido (ainda nao gravado) ou `None` (orcamento, falha ou saida rejeitada)."""
        started_at, state = self._clock(), _State()
        try:
            radar, goes_to_fallback = self._primary(subject, base_month, started_at, state)
            if radar is None and goes_to_fallback:
                radar = self._fallback(subject, base_month, started_at, state)
        except (BudgetDenied, BudgetUnavailable):
            return None
        return radar


class _State:
    """Estado de uma geracao: so a primeira tentativa acertada conta como radar novo no livro."""

    def __init__(self) -> None:
        self.has_settled = False
