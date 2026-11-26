"""
Adaptador `LlmClient` com o SDK `google-genai` em modo Vertex AI (ADC da conta de servico; sem chave de API).
Unico arquivo do pacote `llm` com I/O. Ferramenta unica: busca (P-184.3); sem `temperature`; `thinking_level`
explicito. O SDK e importado so na primeira chamada. Excecoes do SDK viram a hierarquia de `client.py` sem a
mensagem original (ela pode conter o prompt). Os detalhes de campos do SDK devem ser confirmados no spike da
Etapa 3 (trend-insights-llm.md secao 1.2).
"""
import logging
import time
from typing import Any, List, Optional

from src.modules.trend_insights.domain.constants import LOGGER_NAME
from src.modules.trend_insights.llm.client import (
    GroundingCitation,
    LlmBlockedError,
    LlmNotConfiguredError,
    LlmQuotaExhaustedError,
    LlmRequest,
    LlmRequestRejectedError,
    LlmResponse,
    LlmTransientError,
    LlmUsage,
)

logger = logging.getLogger(LOGGER_NAME + ".gemini")
MILLIS_PER_SECOND = 1000
HTTP_QUOTA = 429
HTTP_CLIENT_ERROR_MIN = 400
HTTP_SERVER_ERROR_MIN = 500
HTTP_TIMEOUT_CODES = (408,)


class GeminiVertexClient:
    def __init__(self, project: Optional[str], location: str, sdk_client: Any = None, api_key: Optional[str] = None):
        self._project = project
        self._location = location
        self._sdk_client = sdk_client
        self._api_key = api_key

    def is_configured(self) -> bool:
        """Credencial presente = projeto Vertex ou API key Gemini definida."""
        return bool(self._project or self._api_key) or self._sdk_client is not None

    def _client(self):
        if self._sdk_client is None:
            if not self._project and not self._api_key:
                raise LlmNotConfiguredError()
            from google import genai

            if self._project:
                self._sdk_client = genai.Client(vertexai=True, project=self._project, location=self._location)
            else:
                self._sdk_client = genai.Client(api_key=self._api_key)
        return self._sdk_client

    @classmethod
    def _serving_schema(cls, node: Any) -> Any:
        """Remove `maxItems`/`format`/`pattern` que estouram o limite de estados da API; `validation.py` valida em Python."""
        if isinstance(node, dict):
            return {k: cls._serving_schema(v) for k, v in node.items() if k not in ("maxItems", "format", "pattern")}
        if isinstance(node, list):
            return [cls._serving_schema(item) for item in node]
        return node

    @classmethod
    def _config(cls, request: LlmRequest):
        from google.genai import types

        tools = [types.Tool(google_search=types.GoogleSearch())] if request.use_search_grounding else None
        return types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            response_mime_type="application/json",
            response_json_schema=cls._serving_schema(request.response_schema),
            tools=tools,
            thinking_config=types.ThinkingConfig(thinking_level=request.thinking_level.upper()),
            max_output_tokens=request.max_output_tokens,
            http_options=types.HttpOptions(timeout=int(request.timeout_seconds * MILLIS_PER_SECOND)),
        )

    def generate(self, request: LlmRequest) -> LlmResponse:
        started = time.monotonic()
        try:
            raw = self._client().models.generate_content(
                model=request.model_id, contents=request.user_prompt, config=self._config(request))
        except LlmNotConfiguredError:
            raise
        except Exception as exc:  # o SDK tem hierarquia propria; converte-se tudo, sem guardar a mensagem
            raise self._translate(exc) from None
        return self._to_response(raw, request.model_id, int((time.monotonic() - started) * MILLIS_PER_SECOND))

    @staticmethod
    def _translate(exc: Exception):
        logger.warning("tia.llm.sdk_error type=%s", type(exc).__name__)
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code == HTTP_QUOTA:
            return LlmTransientError()
        if isinstance(code, int) and (code >= HTTP_SERVER_ERROR_MIN or code in HTTP_TIMEOUT_CODES):
            return LlmTransientError()
        if isinstance(code, int) and code >= HTTP_CLIENT_ERROR_MIN:
            return LlmRequestRejectedError()
        return LlmTransientError()  # timeout/rede sem codigo HTTP

    @staticmethod
    def _usage(raw: Any) -> LlmUsage:
        usage = getattr(raw, "usage_metadata", None)
        if usage is None:
            return LlmUsage()
        return LlmUsage(
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            thinking_tokens=int(getattr(usage, "thoughts_token_count", 0) or 0),
            cached_input_tokens=int(getattr(usage, "cached_content_token_count", 0) or 0),
            tool_tokens=int(getattr(usage, "tool_use_prompt_token_count", 0) or 0),
        )

    @staticmethod
    def _grounding(raw: Any):
        candidates = getattr(raw, "candidates", None) or []
        metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
        chunks = getattr(metadata, "grounding_chunks", None) or []
        citations: List[GroundingCitation] = []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if web is not None and getattr(web, "uri", None):
                citations.append(GroundingCitation(url=web.uri, title=getattr(web, "title", "") or ""))
        queries = getattr(metadata, "web_search_queries", None) or []
        rendered = getattr(getattr(metadata, "search_entry_point", None), "rendered_content", None)
        return tuple(citations), len(queries), rendered

    def _to_response(self, raw: Any, model_id: str, latency_ms: int) -> LlmResponse:
        text = getattr(raw, "text", None)
        if not text:
            raise LlmBlockedError()
        citations, queries, suggestions = self._grounding(raw)
        candidates = getattr(raw, "candidates", None) or []
        finish = str(getattr(candidates[0], "finish_reason", "")) if candidates else ""
        return LlmResponse(
            text=text, citations=citations, search_result_urls=frozenset(c.url for c in citations),
            executed_queries_count=queries, search_suggestions_html=suggestions, usage=self._usage(raw),
            model_id=model_id, latency_ms=latency_ms, finish_reason=finish,
        )
