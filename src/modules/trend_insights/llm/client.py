"""
Porta do provedor de LLM (`LlmClient`) e seus DTOs imutaveis (trend-insights-llm.md secao 4).
Uma chamada, sem estado entre chamadas, sem LangChain. O adaptador concreto fica em `gemini_client.py`.
Nenhuma excecao do SDK atravessa esta fronteira: sao convertidas na hierarquia abaixo (P-183.4).
"""
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional, Protocol, Tuple


@dataclass(frozen=True)
class LlmRequest:
    """Entrada de uma chamada. Sem `temperature`: o controle e por schema, enums e `thinking_level` (CP-6)."""

    model_id: str
    system_prompt: str
    user_prompt: str
    response_schema: Optional[Dict[str, Any]]
    use_search_grounding: bool
    thinking_level: str
    max_output_tokens: int
    timeout_seconds: float
    request_tag: str = ""


@dataclass(frozen=True)
class GroundingCitation:
    url: str
    title: str = ""
    start_index: Optional[int] = None
    end_index: Optional[int] = None


@dataclass(frozen=True)
class LlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cached_input_tokens: int = 0
    tool_tokens: int = 0


@dataclass(frozen=True)
class LlmResponse:
    text: str
    citations: Tuple[GroundingCitation, ...]
    search_result_urls: FrozenSet[str]
    executed_queries_count: int
    search_suggestions_html: Optional[str]
    usage: LlmUsage
    model_id: str
    latency_ms: int
    finish_reason: str


class LlmClient(Protocol):
    def generate(self, request: LlmRequest) -> LlmResponse: ...

    def is_configured(self) -> bool: ...


class LlmError(Exception):
    """Base dos erros do provedor. A mensagem do SDK nunca e guardada nem logada."""

    def __init__(self, *_args: object):
        super().__init__(self.__class__.__name__)


class LlmNotConfiguredError(LlmError):
    """Sem credencial ou cliente nao inicializado."""


class LlmTransientError(LlmError):
    """Timeout, rede, 429, 5xx: vale repetir."""


class LlmRequestRejectedError(LlmError):
    """400/403: repetir no mesmo modelo nao ajuda."""


class LlmBlockedError(LlmError):
    """Resposta vazia ou bloqueada por seguranca."""


class LlmQuotaExhaustedError(LlmError):
    """Cota esgotada (nao transitoria)."""
