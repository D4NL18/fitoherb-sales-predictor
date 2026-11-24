"""
Casos de uso da F7: `GET` (cascata + diagnostico salvo, sem custo de token), `POST /generate` e `health`.
O servico monta `data` e `meta` do contrato 1.1.0 (camelCase). Custos, tokens, precos, tetos e `evidenceHash`
nunca saem daqui (contrato 4.4): so o `nivel` do orcamento.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Mapping, Optional

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.constants import (
    CONTRACT_VERSION,
    LOGGER_NAME,
    MODE_NO_VARIATION,
    MODE_QUANTITATIVE,
    PROMPT_VERSION,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.exceptions import InvalidInsightParametersError, NoRelevantVariationError
from src.modules.trend_insights.domain.ports import InFlightLease, ObjectStoreUnavailable
from src.modules.trend_insights.domain.privacy import format_small_count
from src.modules.trend_insights.service.llm_orchestrator import GenerationOutcome, LlmOrchestrator
from src.modules.trend_insights.store.budget_ledger import BudgetLedger
from src.modules.trend_insights.store.insight_store import InsightKey, InsightStore, StoredInsight

logger = logging.getLogger(LOGGER_NAME + ".service")
BASE_MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
BUDGET_TZ_HOURS = -3
WARNING_MESSAGES = {
    "TIA-005": "Índice de produtos afins em atualização: canibalização e grupo afim não avaliados.",
    "FORNECEDOR_NAO_INFORMADO": "Fornecedor do produto não informado.",
    "IA_FALHOU": "Não foi possível gerar a análise com IA agora. Exibindo o resumo automático.",
    "SEM_BUSCA_EXTERNA": "Análise feita sem busca externa.",
}
_SNAKE = re.compile(r"_([a-z0-9])")


@dataclass(frozen=True)
class InsightQuery:
    sku: int
    metric: str = "revenue"
    window: int = 3
    base_month: Optional[str] = None
    comparison_mode: str = "point"
    force: bool = False


@dataclass(frozen=True)
class InsightResult:
    data: Dict[str, Any]
    meta: Dict[str, Any]


def _camel_key(name: str) -> str:
    return _SNAKE.sub(lambda m: m.group(1).upper(), name)


def to_camel(node: Any) -> Any:
    """Converte chaves snake_case em camelCase e mascara contagens pequenas de clientes (LGPD-TIA-06)."""
    if isinstance(node, Mapping):
        converted = {}
        for key, value in node.items():
            camel = _camel_key(str(key))
            is_count = camel in ("clientesMigrados", "clientesPerdidosQtd") and isinstance(value, int)
            converted[camel] = format_small_count(value) if is_count else to_camel(value)
        return converted
    if isinstance(node, (list, tuple)):
        return [to_camel(item) for item in node]
    return node


def _rounded(value: Optional[float], decimals: int) -> Optional[float]:
    return None if value is None else round(value, decimals)


class InsightsService:
    def __init__(
        self,
        evidence_provider: Callable[[InsightQuery], EvidencePackage],
        orchestrator: LlmOrchestrator,
        insight_store: InsightStore,
        ledger: BudgetLedger,
        lease: InFlightLease,
        settings: TrendInsightsSettings,
        clock: Callable[[], datetime],
        index_status_provider: Callable[[], Dict[str, Any]],
        migration_cache_status_provider: Callable[[], List[Dict[str, Any]]],
    ):
        self._provider = evidence_provider
        self._orchestrator = orchestrator
        self._insights = insight_store
        self._ledger = ledger
        self._lease = lease
        self._settings = settings
        self._clock = clock
        self._index_status = index_status_provider
        self._migration_status = migration_cache_status_provider

    # ---------------------------------------------------------------- validacao
    def _validate(self, query: InsightQuery) -> None:
        """`baseMonth` futuro e 400 (o formato ja foi validado na borda)."""
        if query.base_month is None:
            return
        match = BASE_MONTH_PATTERN.match(query.base_month)
        if not match:
            raise InvalidInsightParametersError(("baseMonth",))
        now = self._clock() + timedelta(hours=BUDGET_TZ_HOURS)
        if (int(match.group(1)), int(match.group(2))) > (now.year, now.month):
            raise InvalidInsightParametersError(("baseMonth",))

    # ---------------------------------------------------------------- casos de uso
    def get_product_insight(self, query: InsightQuery) -> InsightResult:
        self._validate(query)
        evidence = self._provider(query)
        key = LlmOrchestrator.key_for(evidence)
        stored = self._read_stored(key)
        data = self._build_data(evidence, stored.diagnostico if stored else None, None)
        return InsightResult(data=data, meta=self._build_meta(evidence, key, stored, []))

    def generate_product_insight(self, query: InsightQuery, caller_id: str) -> InsightResult:
        self._validate(query)
        evidence = self._provider(query)
        if evidence.mode == MODE_NO_VARIATION:
            raise NoRelevantVariationError()
        outcome = self._orchestrator.generate(evidence, caller_id, query.force)
        key = LlmOrchestrator.key_for(evidence)
        stored = self._read_stored(key)
        data = self._build_data(evidence, outcome.diagnostico, outcome.resumo_automatico)
        meta = self._build_meta(evidence, key, stored, outcome.avisos)
        meta.update(self._generate_meta(outcome))
        return InsightResult(data=data, meta=meta)

    def get_health(self) -> InsightResult:
        index = self._index_status()
        data = {
            "ia": {
                "ligada": self._settings.ai_enabled,
                "modeloPadrao": self._settings.model_default,
                "modeloFallback": self._settings.model_fallback,
                "promptVersion": PROMPT_VERSION,
            },
            "orcamento": {"mes": self._ledger.month_label(), "nivel": self._ledger.level()},
            "indiceAfinidade": {
                "disponivel": index.get("disponivel", False), "lastSyncAt": index.get("lastSyncAt"),
                "totalActiveSkus": index.get("totalActiveSkus"), "origem": index.get("origem"),
            },
            "cacheMigracao": list(self._migration_status()),
        }
        meta = {"timestamp": self._clock().isoformat(), "version": CONTRACT_VERSION}
        return InsightResult(data=data, meta=meta)

    # ---------------------------------------------------------------- leitura do salvo
    def _read_stored(self, key: InsightKey) -> Optional[StoredInsight]:
        try:
            return self._insights.get(key)
        except ObjectStoreUnavailable:
            return None

    # ---------------------------------------------------------------- meta
    def _warnings(self, evidence: EvidencePackage, extra: List[str]) -> List[Dict[str, str]]:
        codes = list(extra)
        if not self._index_status().get("disponivel", False):
            codes.insert(0, "TIA-005")
        if not evidence.data["produto"].get("fornecedor"):
            codes.append("FORNECEDOR_NAO_INFORMADO")
        return [{"codigo": c, "mensagem": WARNING_MESSAGES[c]} for c in dict.fromkeys(codes) if c in WARNING_MESSAGES]

    def _ia_state(self, evidence: EvidencePackage, key: InsightKey, stored: Optional[StoredInsight]) -> Dict[str, Any]:
        level = self._ledger.level()
        is_blocked = evidence.mode == MODE_NO_VARIATION
        is_running = self._lease.is_held(LlmOrchestrator.lease_key(key))
        predicted = self._orchestrator.predict_template_reason(evidence)
        now = self._clock()
        return {
            "podeGerar": not is_blocked and not is_running,
            "motivoBloqueio": "SEM_VARIACAO" if is_blocked else None,
            "geraComIa": predicted is None,
            "motivoTemplate": predicted,
            "diagnosticoSalvo": stored is not None,
            "diagnosticoSalvoEm": stored.gerado_em if stored else None,
            "diagnosticoVencido": bool(stored and stored.is_expired(now, self._settings.soft_ttl_days)),
            "podeForcar": level == "NORMAL",
            "geracaoEmAndamento": is_running,
            "orcamento": {"nivel": level},
        }

    def _build_meta(
        self, evidence: EvidencePackage, key: InsightKey, stored: Optional[StoredInsight], extra_warnings: List[str],
    ) -> Dict[str, Any]:
        index = self._index_status()
        reference = evidence.data_referencia
        return {
            "timestamp": self._clock().isoformat(),
            "version": CONTRACT_VERSION,
            "dataReferencia": reference.isoformat(),
            "ultimoDiaCoberto": (reference - timedelta(days=1)).isoformat(),
            "mesBase": evidence.base_month,
            "metrica": evidence.metric,
            "janela": evidence.window,
            "modoComparacao": evidence.comparison_mode,
            "promptVersion": PROMPT_VERSION,
            "indiceAfinidade": {"disponivel": index.get("disponivel", False), "lastSyncAt": index.get("lastSyncAt")},
            "avisos": self._warnings(evidence, extra_warnings),
            "ia": self._ia_state(evidence, key, stored),
        }

    @staticmethod
    def _generate_meta(outcome: GenerationOutcome) -> Dict[str, Any]:
        return {
            "origem": outcome.origem,
            "motivoTemplate": outcome.motivo_template,
            "modelo": outcome.modelo,
            "geradoEm": outcome.gerado_em,
            "reutilizado": outcome.reutilizado,
        }

    # ---------------------------------------------------------------- data
    @staticmethod
    def _numeric_summary(evidence: EvidencePackage) -> Optional[Dict[str, Any]]:
        if evidence.mode != MODE_QUANTITATIVE:
            return None
        data = evidence.data
        delta, residual = data.get("delta_observado"), data.get("residuo")
        coverage = None if not delta or residual is None else (1 - abs(residual) / abs(delta)) * 100
        return {
            "baseAjustada": _rounded(data.get("base_ajustada"), 2), "deltaObservado": _rounded(delta, 2),
            "somaParcelas": None if delta is None or residual is None else round(delta - residual, 2),
            "residuo": _rounded(residual, 2), "coberturaExplicacaoPct": _rounded(coverage, 1),
        }

    @staticmethod
    def _public_diagnosis(diagnostico: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Diagnostico exibido: `sugestoesBuscaHtml` fica nulo ate o checkpoint CP-10 (ADR-009)."""
        if diagnostico is None:
            return None
        public = dict(diagnostico)
        public["sugestoesBuscaHtml"] = None
        return public

    def _build_data(
        self, evidence: EvidencePackage, diagnostico: Optional[Dict[str, Any]], summary_text: Optional[str],
    ) -> Dict[str, Any]:
        data = evidence.data
        afins = to_camel(data.get("afins") or [])
        return {
            "produto": to_camel({k: v for k, v in data["produto"].items() if k != "descricao_galeria"}),
            "periodo": {"atual": data["janela"]["atual"], "anterior": data["janela"]["anterior"],
                        **to_camel(data.get("periodo") or {})},
            "celula": to_camel(data.get("celula")),
            "modoDiagnostico": evidence.mode,
            "direcao": evidence.direction,
            "resumoNumerico": self._numeric_summary(evidence),
            "cascata": to_camel(data.get("cascata") or []),
            "indicadores": to_camel(data.get("indicadores") or []),
            "diagnosticoMercado": to_camel(data.get("diagnostico_mercado")),
            "grupoAfim": {"status": "AVALIADO" if afins else "SEM_GRUPO_AFIM", "afins": afins},
            "impactoEmOutrosProdutos": to_camel(data.get("impacto_outros")),
            "diagnosticoIa": self._public_diagnosis(diagnostico),
            "resumoAutomatico": summary_text,
        }
