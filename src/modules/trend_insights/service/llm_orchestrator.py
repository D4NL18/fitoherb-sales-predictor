"""
Orquestrador da geracao com IA (P-174.1, ordem da arquitetura 15.8): kill-switch -> cache -> gates -> orcamento
-> trava local -> limite de pedidos -> trava entre instancias -> RADAR (fresco, gerado com single-flight, `stale` ou
`SEM_RADAR`) -> diagnostico (Hydrogen, depois uma chamada ao Flash sem ferramentas e com o mesmo radar) -> template.
IA indisponivel, desligada, sem orcamento ou reprovada na validacao NUNCA e erro: devolve o resumo por template
(custo zero), e o template traz o radar existente SOMENTE LEITURA. A chave do cache do diagnostico NAO inclui o radar.
Excecoes inesperadas propagam, mas a trava e a reserva sao sempre liberadas.
"""
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.constants import LOGGER_NAME, PROMPT_VERSION
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.exceptions import BudgetDenied, BudgetUnavailable
from src.modules.trend_insights.domain.gates import evaluate_llm_gates, product_search_enabled
from src.modules.trend_insights.domain.ports import InFlightLease, ObjectConflict, ObjectStoreUnavailable
from src.modules.trend_insights.domain.radar_policy import STATE_ABSENT, STATE_FRESH, radar_age_days, radar_freshness
from src.modules.trend_insights.domain.raw_material import infer_radar_subject
from src.modules.trend_insights.domain.template_summary import build_template_summary
from src.modules.trend_insights.llm.client import LlmClient
from src.modules.trend_insights.llm.evidence_payload import compute_evidence_hash
from src.modules.trend_insights.llm.search_queries import build_product_query
from src.modules.trend_insights.service.generation_guard import GenerationGuard
from src.modules.trend_insights.service.llm_runner import DiagnosisInputs, LlmRunner, RunResult
from src.modules.trend_insights.service.radar_service import (
    RadarService,
    RadarView,
    public_radar_ref,
    public_radar_view,
)
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.insight_store import InsightKey, InsightStore, StoredInsight

logger = logging.getLogger(LOGGER_NAME + ".orchestrator")
LEASE_POLL_SECONDS = 2.0
SCOPE_PRODUCT = "product"
WARNING_NO_RADAR = "SEM_RADAR_EXTERNO"
WARNING_STALE_RADAR = "RADAR_DESATUALIZADO"
MISSING_NO_RADAR, MISSING_NO_TERM = "SEM_RADAR", "SEM_TERMO_BUSCA"


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
    radar: Optional[Dict[str, Any]] = None  # RadarRef publico (origem GERADO_AGORA ou CACHE)
    radar_externo: Optional[Dict[str, Any]] = None  # bloco somente leitura nos templates
    radar_estado: Optional[str] = None  # `meta.ia.radar.estado`


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
        radar_service: Optional[RadarService] = None,
    ):
        self._llm = llm
        self._ledger = ledger
        self._insights = insight_store
        self._lease = lease
        self._guard = guard
        self._settings = settings
        self._clock = clock
        self._sleep = sleep
        self._radar = radar_service
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

    def _peek_radar(self, evidence: EvidencePackage) -> Optional[RadarView]:
        """Leitura do radar existente (fresco ou `stale`): nunca gera, nunca chama o LLM, custo zero."""
        if self._radar is None:
            return None
        return self._radar.peek(infer_radar_subject(evidence), evidence.base_month)

    def _template(self, evidence: EvidencePackage, reason: str, avisos: Optional[List[str]] = None) -> GenerationOutcome:
        """Resumo por template + radar existente em leitura (sem `direcao`); o texto do resumo nao cita fator externo."""
        view = self._peek_radar(evidence)
        warnings = list(avisos or [])
        if view is not None and view.is_stale:
            warnings.append(WARNING_STALE_RADAR)
        return GenerationOutcome(
            origem="template", motivo_template=reason, avisos=warnings,
            resumo_automatico=build_template_summary(evidence),
            radar_externo=public_radar_view(view) if view else None,
        )

    def _cached_radar_ref(self, stored: StoredInsight) -> Optional[Dict[str, Any]]:
        """RadarRef do diagnostico salvo com idade e validade recalculadas agora (origem sempre `CACHE`)."""
        ref = stored.radar_ref
        if not ref:
            return None
        generated_at, now = datetime.fromisoformat(ref["geradoEm"]), self._clock()
        state = radar_freshness(generated_at, ref["mesBase"], now)
        return {
            "assunto": {"termo": ref["termo"], "tipo": ref["tipo"]}, "mesBase": ref["mesBase"],
            "geradoEm": ref["geradoEm"], "diasDesdeGeracao": radar_age_days(generated_at, now),
            "desatualizado": state != STATE_FRESH, "origem": "CACHE",
        }

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
            reutilizado=True, stored=stored, radar=self._cached_radar_ref(stored),
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
        if level == "ESGOTADO":
            return self._template(evidence, "ORCAMENTO_ESGOTADO")
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
        ttl = self._settings.in_flight_lock_ttl_seconds
        while not self._lease.try_acquire(lease_key, ttl):
            cached = None if force else self._cached(key)
            if cached:
                return False, cached
            if (self._clock() - started).total_seconds() >= self._settings.llm_total_deadline_seconds:
                return False, None
            self._sleep(LEASE_POLL_SECONDS)
        return True, None

    # ---------------------------------------------------------------- radar e geracao
    def _resolve_radar(self, evidence: EvidencePackage) -> tuple:
        """`(radar utilizavel ou None, motivo de nao haver)`; falha do radar nunca e erro do diagnostico."""
        subject = infer_radar_subject(evidence)
        if subject is None:
            return None, MISSING_NO_TERM
        if self._radar is None:
            return None, MISSING_NO_RADAR
        try:
            return self._radar.get_or_create(subject, evidence.base_month), MISSING_NO_RADAR
        except (BudgetDenied, BudgetUnavailable, ObjectStoreUnavailable):
            logger.warning("tia.radar.unavailable")
            return None, MISSING_NO_RADAR

    def _run_and_store(self, evidence: EvidencePackage, key: InsightKey, level: str, force: bool) -> GenerationOutcome:
        started_at = self._clock()
        view, missing_reason = self._resolve_radar(evidence)
        hard_cap = self._ledger.radar_limits().hard_cap
        radar_state = view.state if view else STATE_ABSENT
        query = build_product_query(evidence) if product_search_enabled(evidence, level, radar_state, hard_cap) else None
        result = self._runner.run(DiagnosisInputs(evidence, view, missing_reason, query), started_at)
        if result.failure == "ORCAMENTO_ESGOTADO":
            return self._template(evidence, "ORCAMENTO_ESGOTADO")
        if result.failure:
            return self._template(evidence, "IA_INDISPONIVEL", result.avisos)
        return self._finalize(evidence, key, result, view, force)

    @staticmethod
    def _radar_warnings(view: Optional[RadarView]) -> List[str]:
        if view is None:
            return [WARNING_NO_RADAR]
        return [WARNING_STALE_RADAR] if view.is_stale else []

    def _finalize(self, evidence: EvidencePackage, key: InsightKey, result: RunResult, view: Optional[RadarView],
                  force: bool) -> GenerationOutcome:
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
            has_external_factor=True,  # v3: todo diagnostico por LLM tem as 8 dimensoes externas (TTL logico de 30 d)
            cost_usd=result.cost_usd, input_tokens=result.response.usage.input_tokens,
            output_tokens=result.response.usage.output_tokens, queries=result.queries,
            sugestoes_busca_html=result.response.search_suggestions_html, radar_ref=self._radar_ref(view),
        )
        saved = self._save(key, stored, force)
        return GenerationOutcome(
            origem=origem, diagnostico=diagnostico, modelo=result.model_id, gerado_em=generated_at,
            avisos=result.avisos + self._radar_warnings(view), stored=stored if saved else None,
            radar=public_radar_ref(view) if view else None, radar_estado=view.response_state if view else None,
        )

    @staticmethod
    def _radar_ref(view: Optional[RadarView]) -> Optional[Dict[str, Any]]:
        """So referencia ao radar usado (o diagnostico salvo nao depende dele); sem hash, custo ou consultas."""
        if view is None:
            return None
        radar = view.radar
        return {"slug": radar.slug, "termo": radar.term, "tipo": radar.kind, "mesBase": radar.base_month,
                "geradoEm": radar.generated_at.isoformat()}

    def _save(self, key: InsightKey, stored: StoredInsight, overwrite: bool) -> bool:
        try:
            self._insights.put(key, stored, overwrite=overwrite)
            return True
        except ObjectConflict:
            return True
        except ObjectStoreUnavailable:
            logger.warning("tia.insight.save_failed")
            return False
