"""
Orquestrador da geracao com IA (P-174.1): kill-switch -> cache -> gates -> trava local -> limite de pedidos ->
trava entre instancias -> chamadas (Hydrogen, depois uma ao Flash) -> template. IA indisponivel, desligada,
sem orcamento ou reprovada na validacao NUNCA e erro: devolve o resumo por template (custo zero).
Excecoes inesperadas propagam, mas a trava e a reserva sao sempre liberadas.
"""
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.constants import (
    IN_FLIGHT_LOCK_TTL_SECONDS,
    LLM_TOTAL_DEADLINE_SECONDS,
    LOGGER_NAME,
    PROMPT_VERSION,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage, compute_evidence_hash
from src.modules.trend_insights.domain.gates import evaluate_llm_gates, grounding_enabled
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
from src.modules.trend_insights.domain.ports import InFlightLease, ObjectConflict, ObjectStoreUnavailable
from src.modules.trend_insights.domain.template_summary import build_template_summary
from src.modules.trend_insights.llm.client import LlmClient
from src.modules.trend_insights.service.generation_guard import GenerationGuard
from src.modules.trend_insights.service.llm_runner import LlmRunner, RunResult
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.insight_store import InsightKey, InsightStore, StoredInsight

logger = logging.getLogger(LOGGER_NAME + ".orchestrator")
LEASE_POLL_SECONDS = 2.0
SCOPE_PRODUCT = "product"


@dataclass
class GenerationOutcome:
    origem: str
    diagnostico: Optional[dict] = None
    modelo: Optional[str] = None
    gerado_em: Optional[str] = None
    motivo_template: Optional[str] = None
    reutilizado: bool = False
    resumo_automatico: Optional[str] = None
    avisos: List[str] = field(default_factory=list)
    stored: Optional[StoredInsight] = None


class LlmOrchestrator:
    def __init__(
        self,
        llm: LlmClient,
        ledger: BudgetLedger,
        insight_store: InsightStore,
        lease: InFlightLease,
        guard: GenerationGuard,
        settings: TrendInsightsSettings,
        clock: Callable[[], datetime],
        sleep: Callable[[float], None],
    ):
        self._llm = llm
        self._ledger = ledger
        self._insights = insight_store
        self._lease = lease
        self._guard = guard
        self._settings = settings
        self._clock = clock
        self._sleep = sleep
        self._runner = LlmRunner(llm=llm, ledger=ledger, settings=settings, clock=clock, sleep=sleep)
        self._key_locks: Dict[str, threading.Lock] = {}
        self._locks_mutex = threading.Lock()

    # ---------------------------------------------------------------- chaves
    @staticmethod
    def key_for(evidence: EvidencePackage) -> InsightKey:
        return InsightKey(
            escopo=SCOPE_PRODUCT, id=evidence.sku, metric=evidence.metric, window=evidence.window,
            base_month=evidence.base_month, comparison_mode=evidence.comparison_mode,
            prompt_version=PROMPT_VERSION, evidence_hash=compute_evidence_hash(evidence),
        )

    @staticmethod
    def lease_key(key: InsightKey) -> str:
        return hashlib.sha256(key.object_path().encode("utf-8")).hexdigest()[:40]

    def _key_lock(self, key: InsightKey) -> threading.Lock:
        with self._locks_mutex:
            return self._key_locks.setdefault(key.object_path(), threading.Lock())

    # ---------------------------------------------------------------- previsao e atalhos
    def unavailable_reason(self) -> Optional[str]:
        """Passo 1: kill-switch ou credencial ausente."""
        if not self._settings.ai_enabled:
            return "IA_DESLIGADA"
        if not self._llm.is_configured():
            return "IA_INDISPONIVEL"
        return None

    def predict_template_reason(self, evidence: EvidencePackage) -> Optional[str]:
        """Motivo previsto do template se o botao fosse clicado agora (alimenta `meta.ia`)."""
        reason = self.unavailable_reason() or evaluate_llm_gates(evidence)
        if reason:
            return reason
        return "ORCAMENTO_ESGOTADO" if self._ledger.level() == "ESGOTADO" else None

    def _template(self, evidence: EvidencePackage, reason: str, avisos: Optional[List[str]] = None) -> GenerationOutcome:
        return GenerationOutcome(
            origem="template", motivo_template=reason, avisos=list(avisos or []),
            resumo_automatico=build_template_summary(evidence),
        )

    def _cached(self, key: InsightKey) -> Optional[GenerationOutcome]:
        try:
            stored = self._insights.get(key)
        except ObjectStoreUnavailable:
            return None
        except (TypeError, KeyError):
            logger.warning("tia.insight.unreadable")
            return None
        if stored is None:
            return None
        return GenerationOutcome(
            origem="cache", diagnostico=stored.diagnostico, modelo=stored.modelo, gerado_em=stored.gerado_em,
            reutilizado=True, stored=stored,
        )

    # ---------------------------------------------------------------- entrada
    def generate(self, evidence: EvidencePackage, caller_id: str, force: bool = False) -> GenerationOutcome:
        reason = self.unavailable_reason()
        if reason:
            return self._template(evidence, reason)
        key = self.key_for(evidence)
        if not force:
            cached = self._cached(key)
            if cached:
                return cached
        gate = evaluate_llm_gates(evidence)
        if gate:
            return self._template(evidence, gate)
        lock = self._key_lock(key)
        waited = not lock.acquire(blocking=False)
        if waited:
            lock.acquire()
        try:
            if waited or not force:
                cached = self._cached(key)
                if cached:
                    return cached
            return self._generate_exclusive(evidence, key, caller_id, force)
        finally:
            lock.release()

    def _generate_exclusive(self, evidence, key: InsightKey, caller_id: str, force: bool) -> GenerationOutcome:
        level = self._ledger.level()
        if force and level != "NORMAL":
            cached = self._cached(key)
            if cached:
                return cached
            force = False
        self._guard.check(caller_id, force)
        lease_key = self.lease_key(key)
        acquired, cached = self._acquire_lease(lease_key, key, force)
        if cached:
            return cached
        if not acquired:
            return self._template(evidence, "IA_INDISPONIVEL")
        try:
            if not force:
                cached = self._cached(key)
                if cached:
                    return cached
            return self._run_and_store(evidence, key, level, force)
        finally:
            self._lease.release(lease_key)

    def _acquire_lease(self, lease_key: str, key: InsightKey, force: bool):
        """Trava entre instancias; seguidor espera (polling) o resultado do pedido em voo."""
        started = self._clock()
        while not self._lease.try_acquire(lease_key, IN_FLIGHT_LOCK_TTL_SECONDS):
            cached = None if force else self._cached(key)
            if cached:
                return False, cached
            if (self._clock() - started).total_seconds() >= LLM_TOTAL_DEADLINE_SECONDS:
                return False, None
            self._sleep(LEASE_POLL_SECONDS)
        return True, None

    # ---------------------------------------------------------------- geracao e gravacao
    def _run_and_store(self, evidence: EvidencePackage, key: InsightKey, level: str, force: bool) -> GenerationOutcome:
        with_search = grounding_enabled(evidence, level)
        result = self._runner.run(evidence, with_search)
        if result.failure == "ORCAMENTO_ESGOTADO":
            return self._template(evidence, "ORCAMENTO_ESGOTADO")
        if result.failure:
            return self._template(evidence, "IA_INDISPONIVEL", result.avisos)
        return self._finalize(evidence, key, result, force)

    def _finalize(self, evidence: EvidencePackage, key: InsightKey, result: RunResult, force: bool) -> GenerationOutcome:
        origem = "fallback" if result.is_fallback else "llm"
        generated_at = self._clock().isoformat()
        diagnostico = dict(result.validation.diagnostico)
        diagnostico.update(
            direcao=evidence.direction, diagnosticoMercado=evidence.market_classification,
            promptVersion=PROMPT_VERSION, origem=origem, modelo=result.model_id, geradoEm=generated_at,
            sugestoesBuscaHtml=result.response.search_suggestions_html,
        )
        stored = StoredInsight(
            diagnostico=diagnostico, modelo=result.model_id, origem=origem, gerado_em=generated_at,
            prompt_version=PROMPT_VERSION, evidence_hash=key.evidence_hash,
            has_external_factor=any(f["rotulo"] == "POSSIVEL" for f in diagnostico["fatores"]),
            cost_usd=result.cost_usd, input_tokens=result.response.usage.input_tokens,
            output_tokens=result.response.usage.output_tokens, queries=result.queries,
            sugestoes_busca_html=result.response.search_suggestions_html,
        )
        saved = self._save(key, stored, force)
        return GenerationOutcome(
            origem=origem, diagnostico=diagnostico, modelo=result.model_id, gerado_em=generated_at,
            avisos=result.avisos, stored=stored if saved else None,
        )

    def _save(self, key: InsightKey, stored: StoredInsight, overwrite: bool) -> bool:
        try:
            self._insights.put(key, stored, overwrite=overwrite)
            return True
        except ObjectConflict:
            return True
        except ObjectStoreUnavailable:
            logger.warning("tia.insight.save_failed")
            return False
