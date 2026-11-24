"""
Dubles e fabricas da suite da F7 (`trend_insights`). Nenhum teste chama Google, GCS ou SQL Server reais.

PONTO UNICO DE ADAPTACAO: os nomes de modulos/classes/campos que o `developer` deve seguir estao
documentados em `.agents/docs/STATE_Testes_TendenciaIA.md`. Todo import do codigo produtivo e
PREGUICOSO (`mod()`), para que cada teste falhe individualmente com ModuleNotFoundError (red) e
nao por erro de coleta.
"""
from __future__ import annotations

import importlib
import json
import threading
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

PKG = "src.modules.trend_insights"
BRT = timezone(timedelta(hours=-3))
HYDROGEN = "gemini-4-hydrogen"
FLASH = "gemini-3.8-flash"

PRICING_JSON = json.dumps(
    {
        "search_per_query": 0.014,
        "models": {
            HYDROGEN: [{"from": "2026-01-01", "input_per_million": 1.5, "output_per_million": 7.5}],
            FLASH: [
                {"from": "2026-01-01", "input_per_million": 0.75, "output_per_million": 3.75},
                {"from": "2027-01-01", "input_per_million": 1.5, "output_per_million": 7.5},
            ],
        },
    }
)


def mod(name: str):
    """Importa `src.modules.trend_insights.<name>` so quando o teste roda."""
    return importlib.import_module(f"{PKG}.{name}")


# ---------------------------------------------------------------------------
# Relogio e armazenamento
# ---------------------------------------------------------------------------
class FakeClock:
    """Relogio injetavel (datetime aware em UTC). `sleep` apenas avanca o relogio."""

    def __init__(self, start: Optional[datetime] = None):
        self.now_dt = start or datetime(2026, 11, 24, 15, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now_dt

    def advance(self, seconds: float) -> None:
        self.now_dt += timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        self.advance(seconds)


class FakeObjectStore:
    """Duble do GCS: geracao por objeto, `if_generation_match`, contadores e falha injetavel."""

    def __init__(self):
        self.objects: Dict[str, Any] = {}
        self.generations: Dict[str, int] = {}
        self.reads = 0
        self.writes = 0
        self.fail = False
        self.conflicts_to_inject = 0
        self.write_log: List[str] = []

    def read_json(self, path: str):
        self.reads += 1
        if self.fail:
            raise mod("domain.ports").ObjectStoreUnavailable()
        if path not in self.objects:
            return None
        return json.loads(json.dumps(self.objects[path])), self.generations[path]

    def write_json(self, path: str, payload: Any, *, if_generation_match: int) -> int:
        if self.fail:
            raise mod("domain.ports").ObjectStoreUnavailable()
        if self.conflicts_to_inject > 0:
            self.conflicts_to_inject -= 1
            # Alguem escreveu antes: o objeto passa a existir (se ainda nao existia) com a nova geracao, para que o
            # escritor consiga ler a geracao atual e repetir (no GCS real o objeto criado pelo concorrente existe).
            self.objects.setdefault(path, {})
            self.generations[path] = self.generations.get(path, 0) + 1
            raise mod("domain.ports").ObjectConflict()
        if self.generations.get(path, 0) != if_generation_match:
            raise mod("domain.ports").ObjectConflict()
        self.writes += 1
        self.write_log.append(path)
        self.objects[path] = json.loads(json.dumps(payload, default=str))
        self.generations[path] = self.generations.get(path, 0) + 1
        return self.generations[path]

    def delete(self, path: str, *, if_generation_match: Optional[int] = None) -> None:
        self.objects.pop(path, None)
        self.generations.pop(path, None)

    def paths(self, prefix: str) -> List[str]:
        return sorted(p for p in self.objects if p.startswith(prefix))


class FakeLease:
    """Duble de `InFlightLease`: `preheld` simula outra instancia segurando a trava."""

    def __init__(self):
        self.held: set = set()
        self.preheld: set = set()
        self.hold_all = False  # outra instancia segura qualquer chave
        self.acquired: List[str] = []

    def try_acquire(self, key: str, ttl_seconds: int) -> bool:
        if self.hold_all or key in self.held or key in self.preheld:
            return False
        self.held.add(key)
        self.acquired.append(key)
        return True

    def release(self, key: str) -> None:
        self.held.discard(key)

    def is_held(self, key: str) -> bool:
        return self.hold_all or key in self.held or key in self.preheld


# ---------------------------------------------------------------------------
# Evidencias
# ---------------------------------------------------------------------------
def canonical_evidence(**over) -> Dict[str, Any]:
    """Pacote canonico (dict) padrao: queda quantitativa de R$ 3.000 com sazonalidade e canibalizacao."""
    base: Dict[str, Any] = {
        "produto": {
            "sku": 5102,
            "descricao": "CHA DE HIBISCO 100G",
            "fornecedor": "ERVAS DELTA",
            "categoria_galeria": "Chas e Infusoes",
            "funcao_primaria": "cha_infusao",
            "descricao_galeria": "Cha de hibisco seco, ideal para infusao.",
        },
        "janela": {
            "metrica": "revenue", "janela": 3, "mes_base": "2026-10", "modo_comparacao": "point",
            "atual": {"inicio": "2026-10-01", "fim": "2026-10-31"},
            "anterior": {"inicio": "2026-07-01", "fim": "2026-07-31"},
        },
        "modo_diagnostico": "QUANTITATIVO",
        "cell_status": "VARIACAO",
        "direcao": "QUEDA",
        "variacao_pct": -30.0,
        "delta_observado": -3000.0,
        "delta_receita": -3000.0,
        "base_ajustada": 10000.0,
        "residuo": -1500.0,
        "residual_share": 0.5,
        "cascata": [
            {"tipo": "SAZONALIDADE", "status": "AVALIADO", "valor": -1000.0, "pontos_percentuais": -10.0,
             "sentido": "NEGATIVO", "confianca": "MEDIA", "cortada": False, "itens": []},
            {"tipo": "CANIBALIZACAO_OUTRO_FORNECEDOR", "status": "AVALIADO", "valor": -500.0,
             "pontos_percentuais": -5.0, "sentido": "NEGATIVO", "confianca": "ALTA", "cortada": False,
             "itens": [{"sku": 5140, "descricao": "CHA HIBISCO CANELA 80G", "fornecedor": "NATURAL OMEGA",
                        "same_supplier": False, "affinity_score": 0.712, "receita_migrada": 500.0,
                        "clientes_migrados": 12}]},
        ],
        "indicadores": [],
        "diagnostico_mercado": {"classificacao": "MISTO", "variacao_mercado_pct": -10.0,
                                "efeito_mercado": -1000.0, "efeito_participacao": -2000.0},
        "afins": [{"sku": 5140, "descricao": "CHA HIBISCO CANELA 80G", "fornecedor": "NATURAL OMEGA",
                   "same_supplier": False, "affinity_score": 0.712, "variacao_pct": 20.0,
                   "ganhou_clientes_do_produto": True}],
        "impacto_outros": None,
        "regional": [],
    }
    for key, value in over.items():
        base[key] = value
    return base


def make_evidence(*, data_referencia: date = date(2026, 11, 9), produto: Optional[dict] = None, **over):
    """Monta `EvidencePackage` a partir do dict canonico (`EvidencePackage.from_mapping`)."""
    data = canonical_evidence(**over)
    if produto:
        data["produto"] = {**data["produto"], **produto}
    return mod("domain.evidence").EvidencePackage.from_mapping(data, data_referencia=data_referencia)


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
def valid_llm_text(**over) -> str:
    """JSON de saida valido para a evidencia padrao (sem nenhum digito nos textos)."""
    body = {
        "resumo": "A queda vem principalmente da sazonalidade e da migracao para um produto afim.",
        "fatores": [{
            "tipo": "SAZONALIDADE", "sentido": "NEGATIVO", "confianca": "MEDIA",
            "explicacao": "A epoca do ano costuma reduzir a procura por este cha.",
            "evidenciaInterna": "SAZONALIDADE", "skusCitados": [], "fontes": [],
        }],
        "hipotesesNaoConfirmadas": [],
        "recomendacoes": ["Revisar o estoque do produto afim."],
    }
    body.update(over)
    return json.dumps(body)


def make_llm_response(text: Optional[str] = None, *, model: str = HYDROGEN, input_tokens: int = 4000,
                      output_tokens: int = 800, thinking_tokens: int = 300, queries: int = 0, citations=()):
    client = mod("llm.client")
    return client.LlmResponse(
        text=text if text is not None else valid_llm_text(),
        citations=tuple(citations),
        search_result_urls=frozenset(),
        executed_queries_count=queries,
        search_suggestions_html=None,
        usage=client.LlmUsage(input_tokens=input_tokens, output_tokens=output_tokens,
                              thinking_tokens=thinking_tokens, cached_input_tokens=0, tool_tokens=0),
        model_id=model,
        latency_ms=1200,
        finish_reason="STOP",
    )


class FakeLlm:
    """Duble de `LlmClient`. `script` = lista de respostas/excecoes/callables consumidas em ordem."""

    def __init__(self, script=None, *, configured: bool = True, clock: Optional[FakeClock] = None,
                 seconds_per_call: float = 0.0, on_call: Optional[Callable] = None):
        self.script = list(script or [])
        self.configured = configured
        self.clock = clock
        self.seconds_per_call = seconds_per_call
        self.on_call = on_call
        self.calls: list = []
        self.lock = threading.Lock()

    def is_configured(self) -> bool:
        return self.configured

    @property
    def models(self) -> List[str]:
        return [c.model_id for c in self.calls]

    def generate(self, request):
        with self.lock:
            self.calls.append(request)
            item = self.script.pop(0) if self.script else None
        if self.clock is not None:
            self.clock.advance(self.seconds_per_call)
        if self.on_call:
            self.on_call(request)
        if callable(item) and not isinstance(item, Exception):
            item = item(request)
        if isinstance(item, Exception):
            raise item
        return item if item is not None else make_llm_response(model=request.model_id)


# ---------------------------------------------------------------------------
# Montagem do orquestrador (unico ponto de fiacao dos testes de servico)
# ---------------------------------------------------------------------------
class Rig:
    pass


def make_settings(**env):
    base = {"TREND_AI_PRICING_JSON": PRICING_JSON}
    base.update({k: str(v) for k, v in env.items()})
    return mod("config").TrendInsightsSettings.from_env(base)


def make_rig(*, llm: Optional[FakeLlm] = None, settings_env: Optional[dict] = None,
             seconds_per_call: float = 0.0, objects: Optional[FakeObjectStore] = None,
             sleep: Optional[Callable] = None) -> Rig:
    rig = Rig()
    rig.clock = FakeClock()
    rig.objects = objects or FakeObjectStore()
    rig.lease = FakeLease()
    rig.settings = make_settings(**(settings_env or {}))
    rig.llm = llm or FakeLlm(clock=rig.clock, seconds_per_call=seconds_per_call)
    if llm is not None and llm.clock is None:
        llm.clock = rig.clock
    if llm is not None and seconds_per_call:
        llm.seconds_per_call = seconds_per_call
    rig.ledger = mod("store.budget_ledger").BudgetLedger(store=rig.objects, settings=rig.settings, clock=rig.clock)
    rig.insight_store = mod("store.insight_store").InsightStore(store=rig.objects, clock=rig.clock)
    rig.guard = mod("service.generation_guard").GenerationGuard(settings=rig.settings, clock=rig.clock)
    rig.orch = mod("service.llm_orchestrator").LlmOrchestrator(
        llm=rig.llm, ledger=rig.ledger, insight_store=rig.insight_store, lease=rig.lease,
        guard=rig.guard, settings=rig.settings, clock=rig.clock, sleep=sleep or rig.clock.sleep,
    )
    return rig


def budget_path(clock: FakeClock) -> str:
    local = clock().astimezone(BRT)
    return f"ai-budget/{local:%Y-%m}.json"


def seed_budget(rig: Rig, *, month: float = 0.0, day: float = 0.0, queries: int = 0) -> None:
    local = rig.clock().astimezone(BRT)
    path = budget_path(rig.clock)
    rig.objects.objects[path] = {
        "gastoMes": month, "gastoDia": {"data": local.date().isoformat(), "valor": day},
        "reservado": [], "consultasMes": queries,
    }
    rig.objects.generations[path] = 1


def collect_keys(node: Any) -> List[str]:
    keys: List[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            keys.append(str(k))
            keys.extend(collect_keys(v))
    elif isinstance(node, (list, tuple)):
        for v in node:
            keys.extend(collect_keys(v))
    return keys


FORBIDDEN_COST_KEYS = ("usd", "custo", "token", "consultas", "preco", "teto", "gasto", "saldo", "evidencehash")
