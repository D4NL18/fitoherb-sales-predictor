"""Excecoes de dominio e de orcamento da F7. Mensagens fixas: nunca ecoam valores recebidos."""
from typing import Optional


class TrendInsightsError(Exception):
    """Base das excecoes da F7."""


class ProductNotFoundError(TrendInsightsError):
    """TIA-002: SKU fora do Catalogo Ativo."""


class InsufficientBaseError(TrendInsightsError):
    """TIA-003: Mes-Base sem base de vendas suficiente."""


class NoRelevantVariationError(TrendInsightsError):
    """TIA-003: `POST /generate` em modo SEM_VARIACAO."""


class InvalidInsightParametersError(TrendInsightsError):
    """TIA-001: parametro invalido (so os nomes dos campos, nunca os valores)."""

    def __init__(self, fields: tuple = ()):
        super().__init__("Parametros invalidos para o diagnostico.")
        self.fields = tuple(fields)


class SchedulerUnauthorized(TrendInsightsError):
    """TIA-006: token OIDC ausente, invalido, expirado, audiencia ou chamador diferente (sem dizer qual)."""


class AffinitySyncBusy(TrendInsightsError):
    """TIA-007: outra sincronizacao do indice de afinidade em andamento (lease ocupado)."""


class BudgetDenied(TrendInsightsError):
    """Reserva negada: o teto mensal ou diario nao comporta a chamada."""


class BudgetUnavailable(TrendInsightsError):
    """Livro de gastos ilegivel ou com conflito persistente: falha fechada (sem chamada ao LLM)."""


class GenerationRefused(TrendInsightsError):
    """TIA-004: limite de pedidos por usuario. `motivo` in {LIMITE_DE_PEDIDOS, LIMITE_DIARIO}."""

    def __init__(self, motivo: str, retry_after_seconds: int):
        super().__init__("Limite de analises com IA atingido.")
        self.motivo = motivo
        self.retry_after_seconds = max(1, int(retry_after_seconds))


class SettingsError(ValueError):
    """Configuracao invalida (modelo fora da lista, tabela de precos inconsistente)."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field
