"""
Execucao das chamadas do DIAGNOSTICO ao LLM (P-183): Hydrogen com ate 2 tentativas por falha de infraestrutura
(backoff), 1 nova tentativa por violacao de schema (mesmo modelo, com os codigos no prompt), uma unica chamada ao
Flash (sem ferramentas, com o MESMO radar) e prazo total de 125 s contado desde o inicio do radar. O radar entra no
prompt como dado (bloco com nonce) e a busca do produto so existe sem radar (1 consulta). Cada tentativa reserva no livro e acerta com o `usage` real; tentativas que
gastaram tokens contam mesmo quando falham na validacao. Nunca loga prompt, pacote, resposta ou mensagem do SDK.
"""
import logging
import secrets
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.constants import (
    EXTERNAL_SOURCE_LOOKBACK_DAYS,
    LLM_BACKOFF_BASE_SECONDS,
    LLM_SCHEMA_RETRY_LIMIT,
    LLM_TIMEOUT_SECONDS,
    LLM_TRANSIENT_RETRY_LIMIT,
    LOGGER_NAME,
    PROMPT_VERSION,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
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
from src.modules.trend_insights.llm.evidence_payload import build_radar_block
from src.modules.trend_insights.llm.output_schema import LLM_OUTPUT_SCHEMA
from src.modules.trend_insights.llm.pricing import compute_cost
from src.modules.trend_insights.llm.prompts import build_prompts
from src.modules.trend_insights.llm.validation import (
    ExternalContext,
    ValidationContext,
    ValidationOutcome,
    date_from_url,
    is_safe_url,
    validate_llm_output,
)
from src.modules.trend_insights.service.radar_service import RadarView
from src.modules.trend_insights.store.budget_ledger import BudgetLedger

logger = logging.getLogger(LOGGER_NAME + ".llm")
THINKING_LEVEL = "low"
NONCE_BYTES = 4
MAX_PRODUCT_SOURCES = 2
MAX_SOURCE_TITLE_CHARS = 200
BACKOFF_FACTOR = 2


@dataclass
class RunResult:
    """Resultado de uma geracao. `failure` in {None, ORCAMENTO_ESGOTADO, IA_FALHOU}."""

    failure: Optional[str] = None
    response: Optional[LlmResponse] = None
    validation: Optional[ValidationOutcome] = None
    model_id: Optional[str] = None
    is_fallback: bool = False
    cost_usd: float = 0.0
    queries: int = 0
    avisos: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiagnosisInputs:
    """Entradas da geracao: pacote, radar utilizavel (ou o motivo de nao haver) e a consulta do produto (ou `None`)."""

    evidence: EvidencePackage
    radar: Optional[RadarView] = None
    radar_missing_reason: Optional[str] = None
    product_query: Optional[str] = None


@dataclass
class _Attempt:
    response: LlmResponse
    validation: ValidationOutcome


class LlmRunner:
    def __init__(
        self,
        llm: LlmClient,
        ledger: BudgetLedger,
        settings: TrendInsightsSettings,
        clock: Callable[[], datetime],
        sleep: Callable[[float], None],
    ):
        self._llm = llm
        self._ledger = ledger
        self._settings = settings
        self._clock = clock
        self._sleep = sleep

    # ---------------------------------------------------------------- contexto de validacao
    @staticmethod
    def _product_sources(response: LlmResponse, with_search: bool) -> Dict[str, Dict[str, object]]:
        """Fontes da busca do produto (`P1..`): so citacoes seguras; a data so vem do caminho da URL."""
        sources: Dict[str, Dict[str, object]] = {}
        for citation in response.citations if with_search else ():
            if not is_safe_url(citation.url) or len(sources) >= MAX_PRODUCT_SOURCES:
                continue
            url, found = citation.url.strip(), date_from_url(citation.url)
            sources[f"P{len(sources) + 1}"] = {
                "id": f"P{len(sources) + 1}", "url": url, "dominio": urlparse(url).hostname,
                "titulo": (citation.title or "")[:MAX_SOURCE_TITLE_CHARS],
                "dataPublicacao": found.isoformat() if found else None, "origemData": "URL" if found else "SEM_DATA",
            }
        return sources

    def _external(self, inputs: DiagnosisInputs, response: LlmResponse, with_search: bool) -> ExternalContext:
        evidence, radar = inputs.evidence, inputs.radar
        window = evidence.data["janela"]
        sources = dict(radar.radar.source_by_id()) if radar else {}
        sources.update(self._product_sources(response, with_search))
        return ExternalContext(
            dimensions=tuple(radar.radar.dimensions) if radar else (), sources=sources,
            variation_pct=evidence.variation_pct, current_start=date.fromisoformat(window["atual"]["inicio"]),
            current_end=date.fromisoformat(window["atual"]["fim"]),
            previous_start=date.fromisoformat(window["anterior"]["inicio"]),
            radar_stale=bool(radar and radar.is_stale),
            radar_missing_reason=None if radar else (inputs.radar_missing_reason or "SEM_RADAR"),
        )

    def _context(self, inputs: DiagnosisInputs, response: LlmResponse, with_search: bool) -> ValidationContext:
        evidence = inputs.evidence
        previous_start = date.fromisoformat(evidence.data["janela"]["anterior"]["inicio"])
        cited = frozenset(c.url for c in response.citations) | frozenset(response.search_result_urls)
        return ValidationContext(
            modo=evidence.mode, package_skus=evidence.package_skus, evaluated_types=evidence.evaluated_types,
            parcel_values=evidence.parcel_values, cited_urls=cited,
            cited_titles={c.url: c.title for c in response.citations if c.title},
            lookback_start=previous_start - timedelta(days=EXTERNAL_SOURCE_LOOKBACK_DAYS),
            reference_date=evidence.data_referencia, external=self._external(inputs, response, with_search),
        )

    # ---------------------------------------------------------------- uma tentativa
    def _build_request(
        self, inputs: DiagnosisInputs, model_id: str, with_search: bool, violations: List[str], remaining: float,
    ) -> LlmRequest:
        nonce = secrets.token_hex(NONCE_BYTES)
        radar_block = build_radar_block(inputs.radar.radar, nonce) if inputs.radar else None
        system_prompt, user_prompt = build_prompts(
            inputs.evidence, nonce, violations, radar_block, inputs.product_query if with_search else None)
        return LlmRequest(
            model_id=model_id, system_prompt=system_prompt, user_prompt=user_prompt,
            response_schema=LLM_OUTPUT_SCHEMA, use_search_grounding=with_search, thinking_level=THINKING_LEVEL,
            max_output_tokens=self._settings.max_output_tokens,
            timeout_seconds=min(LLM_TIMEOUT_SECONDS, max(1.0, remaining)),
        )

    def _attempt(self, spec: "_AttemptSpec") -> _Attempt:
        reservation = self._ledger.reserve(spec.model_id, spec.with_search)
        settled = False
        try:
            response = self._llm.generate(spec.request)
            cost = compute_cost(
                response.model_id or spec.model_id, response.usage, self._settings.pricing, self._clock().date(),
                response.executed_queries_count, reservation.month_queries, self._settings.free_queries,
            )
            self._ledger.settle(reservation, cost, response.executed_queries_count)
            settled = True
        finally:
            if not settled:
                self._release_quietly(reservation)
        spec.totals.add(cost, response.executed_queries_count)
        validation = validate_llm_output(
            response.text, self._context(spec.inputs, response, spec.with_search), spec.drop_offending)
        self._log_call(spec, response, cost, validation)
        return _Attempt(response=response, validation=validation)

    def _release_quietly(self, reservation) -> None:
        try:
            self._ledger.release(reservation)
        except BudgetUnavailable:
            logger.warning("tia.budget.release_failed")

    @staticmethod
    def _log_call(spec: "_AttemptSpec", response: LlmResponse, cost: float, validation: ValidationOutcome) -> None:
        logger.info(
            "tia.llm.call model=%s attempt=%d status=%s inputTokens=%d outputTokens=%d thinkingTokens=%d "
            "searchQueries=%d costUsd=%.5f latencyMs=%d promptChars=%d promptVersion=%s violations=%s",
            spec.model_id, spec.number, "ok" if validation.ok else "schema_violation",
            response.usage.input_tokens, response.usage.output_tokens, response.usage.thinking_tokens,
            response.executed_queries_count, cost, response.latency_ms, len(spec.request.user_prompt),
            PROMPT_VERSION, ",".join(validation.violations),
        )

    # ---------------------------------------------------------------- tempo
    def _remaining(self, started_at: datetime) -> float:
        return self._settings.llm_total_deadline_seconds - (self._clock() - started_at).total_seconds()

    # ---------------------------------------------------------------- Hydrogen
    def _primary(self, inputs, with_search, started_at, totals) -> Tuple[Optional[_Attempt], Optional[str]]:
        """Devolve `(tentativa valida, None)`, `(None, "INFRA")` para ir ao fallback ou `(None, "FALHOU")`."""
        model_id = self._settings.model_default
        transient_failures, schema_retries = 0, 0
        violations: List[str] = []
        number = 0
        while self._remaining(started_at) > 0:
            number += 1
            request = self._build_request(inputs, model_id, with_search, violations, self._remaining(started_at))
            spec = _AttemptSpec(inputs, model_id, with_search, request, schema_retries > 0, number, totals)
            try:
                attempt = self._attempt(spec)
            except (LlmTransientError, LlmQuotaExhaustedError):
                transient_failures += 1
                if transient_failures >= LLM_TRANSIENT_RETRY_LIMIT:
                    return None, "INFRA"
                self._sleep(LLM_BACKOFF_BASE_SECONDS * BACKOFF_FACTOR ** (transient_failures - 1))
                continue
            except LlmRequestRejectedError:
                return None, "INFRA"
            except LlmBlockedError:
                attempt = None
            if attempt is not None and attempt.validation.ok:
                return attempt, None
            if schema_retries >= LLM_SCHEMA_RETRY_LIMIT:
                return None, "FALHOU"
            schema_retries += 1
            violations = list(attempt.validation.violations) if attempt else ["RESPOSTA_BLOQUEADA"]
        return None, "FALHOU"

    # ---------------------------------------------------------------- Flash
    def _fallback(self, inputs, started_at, totals) -> Optional[_Attempt]:
        if self._remaining(started_at) <= 0:
            return None
        model_id = self._settings.model_fallback
        request = self._build_request(inputs, model_id, False, [], self._remaining(started_at))
        spec = _AttemptSpec(inputs, model_id, False, request, True, 1, totals)
        try:
            attempt = self._attempt(spec)
        except LlmError:
            return None
        return attempt if attempt.validation.ok else None

    # ---------------------------------------------------------------- entrada
    def run(self, inputs: DiagnosisInputs, started_at: Optional[datetime] = None) -> RunResult:
        """`started_at` abre o prazo total (125 s): o chamador passa o inicio do radar para somar radar + diagnostico."""
        started_at = started_at or self._clock()
        totals = _Totals()
        with_search = inputs.product_query is not None
        try:
            attempt, reason = self._primary(inputs, with_search, started_at, totals)
            is_fallback = False
            if attempt is None and reason == "INFRA":
                attempt = self._fallback(inputs, started_at, totals)
                is_fallback = attempt is not None
        except (BudgetDenied, BudgetUnavailable):
            return RunResult(failure="ORCAMENTO_ESGOTADO", cost_usd=totals.cost, queries=totals.queries)
        if attempt is None:
            return RunResult(failure="IA_FALHOU", avisos=["IA_FALHOU"], cost_usd=totals.cost, queries=totals.queries)
        avisos = ["SEM_BUSCA_EXTERNA"] if is_fallback and with_search and inputs.radar is None else []
        return RunResult(
            response=attempt.response, validation=attempt.validation, model_id=attempt.response.model_id,
            is_fallback=is_fallback, cost_usd=totals.cost, queries=totals.queries, avisos=avisos,
        )


class _Totals:
    def __init__(self) -> None:
        self.cost = 0.0
        self.queries = 0

    def add(self, cost: float, queries: int) -> None:
        self.cost += cost
        self.queries += queries


@dataclass
class _AttemptSpec:
    inputs: DiagnosisInputs
    model_id: str
    with_search: bool
    request: LlmRequest
    drop_offending: bool
    number: int
    totals: _Totals
