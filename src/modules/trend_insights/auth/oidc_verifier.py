"""
Verificador de token OIDC do Google (unico ponto com `google.oauth2`): confere assinatura, expiracao e audiencia.
Importacao tardia: nada acessa rede nem exige o SDK ao importar o modulo. Qualquer falha vira `ValueError` sem
o texto do token ou da excecao original.
Defesa contra trafego de saida por requisicao anonima (a rota e publica pelo bypass do Basic): token que nao tem
3 segmentos ou passa do tamanho maximo e recusado antes de qualquer rede, e a resposta dos certificados do Google
fica em cache com TTL curto (so respostas 200).
"""
import functools
import threading
import time
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

CERTS_TTL_SECONDS = 300.0
MAX_TOKEN_CHARS = 4096
_JWT_SEGMENTS = 3


def _looks_like_jwt(token: Any) -> bool:
    return isinstance(token, str) and len(token) <= MAX_TOKEN_CHARS and token.count(".") == _JWT_SEGMENTS - 1 \
        and all(token.split("."))


class _CachedCertsRequest:
    """Transporte que reaproveita respostas GET bem-sucedidas (certificados publicos) ate o TTL."""

    def __init__(self, inner: Callable[..., Any], ttl_seconds: float, clock: Callable[[], float]):
        self._inner = inner
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: Dict[str, Tuple[float, Any]] = {}

    def __call__(self, url: str, method: str = "GET", body: Any = None, headers: Any = None,
                 timeout: Any = None, **kwargs: Any) -> Any:
        if method.upper() != "GET":
            return self._inner(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
        now = self._clock()
        with self._lock:
            cached = self._entries.get(url)
            if cached and now < cached[0]:
                return cached[1]
        response = self._inner(url, method=method, body=body, headers=headers, timeout=timeout, **kwargs)
        if getattr(response, "status", None) == 200:
            with self._lock:
                self._entries[url] = (now + self._ttl, response)
        return response


class GoogleOidcVerifier:
    def __init__(
        self,
        request: Optional[Callable[..., Any]] = None,
        verify_fn: Optional[Callable[..., Mapping[str, Any]]] = None,
        clock: Callable[[], float] = time.monotonic,
        certs_ttl_seconds: float = CERTS_TTL_SECONDS,
    ):
        self._request_override = request
        self._verify_fn = verify_fn
        self._clock = clock
        self._ttl = certs_ttl_seconds
        self._request: Optional[_CachedCertsRequest] = None
        self._lock = threading.Lock()

    def _transport(self) -> _CachedCertsRequest:
        with self._lock:
            if self._request is None:
                inner = self._request_override
                if inner is None:
                    from google.auth.transport import requests as google_requests

                    inner = google_requests.Request()
                self._request = _CachedCertsRequest(inner, self._ttl, self._clock)
            return self._request

    def verify(self, token: str, audience: str) -> Mapping[str, Any]:
        if not _looks_like_jwt(token):
            raise ValueError("token OIDC invalido")
        try:
            verify_fn = self._verify_fn
            if verify_fn is None:
                from google.oauth2 import id_token

                verify_fn = id_token.verify_oauth2_token
            return verify_fn(token, self._transport(), audience)
        except Exception:  # a biblioteca levanta tipos variados: todos significam token invalido
            raise ValueError("token OIDC invalido") from None


@functools.lru_cache(maxsize=1)
def shared_verifier() -> GoogleOidcVerifier:
    """Instancia unica por processo: o cache de certificados so vale se sobreviver entre requisicoes."""
    return GoogleOidcVerifier()
