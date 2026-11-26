"""
Limite de pedidos que CHAMAM o LLM (P-176.3, P-176.4, LGPD-TIA-11): contadores so em memoria do processo,
indexados por identificador pseudonimizado (HMAC com sal de processo, truncado). O usuario/IP em claro
nunca e guardado, logado ou devolvido.
"""
import hashlib
import hmac
import os
import threading
from collections import deque
from datetime import datetime
from typing import Callable, Deque, Dict

from src.modules.trend_insights.config import TrendInsightsSettings
from src.modules.trend_insights.domain.exceptions import GenerationRefused

SECONDS_PER_MINUTE = 60
SECONDS_PER_DAY = 86_400
PSEUDONYM_HEX_CHARS = 16
SALT_BYTES = 16


class GenerationGuard:
    def __init__(self, settings: TrendInsightsSettings, clock: Callable[[], datetime]):
        self._settings = settings
        self._clock = clock
        self._salt = os.urandom(SALT_BYTES)
        self._requests: Dict[str, Deque[float]] = {}
        self._forced: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _pseudonym(self, caller_id: str) -> str:
        digest = hmac.new(self._salt, caller_id.encode("utf-8"), hashlib.sha256).hexdigest()
        return digest[:PSEUDONYM_HEX_CHARS]

    @staticmethod
    def _prune(events: Deque[float], now: float) -> None:
        while events and now - events[0] >= SECONDS_PER_DAY:
            events.popleft()

    @staticmethod
    def _retry_after(events: Deque[float], now: float, window_seconds: int, limit: int) -> int:
        """Segundos ate o evento mais antigo da janela sair dela, liberando uma vaga."""
        in_window = [t for t in events if now - t < window_seconds]
        if len(in_window) < limit:
            return 1
        return int(window_seconds - (now - in_window[-limit])) + 1

    def check(self, caller_id: str, force: bool = False) -> None:
        """Registra o pedido ou levanta `GenerationRefused` (nada e registrado quando recusa)."""
        now = self._clock().timestamp()
        key = self._pseudonym(caller_id)
        with self._lock:
            requests = self._requests.setdefault(key, deque())
            forced = self._forced.setdefault(key, deque())
            self._prune(requests, now)
            self._prune(forced, now)
            self._enforce(requests, forced, now, force)
            requests.append(now)
            if force:
                forced.append(now)

    def _enforce(self, requests: Deque[float], forced: Deque[float], now: float, force: bool) -> None:
        settings = self._settings
        if force and len(forced) >= settings.force_max_per_day:
            raise GenerationRefused("LIMITE_DIARIO", self._retry_after(forced, now, SECONDS_PER_DAY, settings.force_max_per_day))
        if len(requests) >= settings.generate_max_per_day:
            raise GenerationRefused("LIMITE_DIARIO", self._retry_after(requests, now, SECONDS_PER_DAY, settings.generate_max_per_day))
        per_minute = settings.generate_rate_limit_per_minute
        recent = [t for t in requests if now - t < SECONDS_PER_MINUTE]
        if len(recent) >= per_minute:
            raise GenerationRefused("LIMITE_DE_PEDIDOS", self._retry_after(requests, now, SECONDS_PER_MINUTE, per_minute))
