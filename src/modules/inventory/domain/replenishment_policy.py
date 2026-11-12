"""
Objeto de Valor e Invariantes da Política de Estoque Mínimo/Máximo (Replenishment Policy).

Implementa as regras de negócio P-053 (Política Mín/Máx por dias de cobertura), P-055.3 (Lead Time
como sinalizador de ruptura iminente), A2 (invariante lead time < dias máximo) e DA-02/A3 (teto de
unidades imune a resíduo binário de ponto flutuante).
"""
from dataclasses import dataclass
import math
from typing import Mapping, Optional

DEFAULT_MIN_COVERAGE_DAYS = 30  # P-053.2: piso padrão de cobertura (30 dias de venda)
DEFAULT_MAX_COVERAGE_DAYS = 60  # P-053.2: teto padrão de cobertura (60 dias de venda)
DEFAULT_LEAD_TIME_DAYS = 15  # P-055.3: lead time padrão; usado apenas para sinalizar ruptura iminente

ERROR_CODE_MAX_NOT_GREATER_THAN_MIN = "INV-001"  # P-053.3: maxCoverageDays <= minCoverageDays
ERROR_CODE_LEAD_TIME_NOT_BELOW_MAX = "INV-002"  # A2: leadTimeDays >= maxCoverageDays

# Premissa (ADR-001, DA-02): Qtd Venda no ERP tem no máximo 3 casas decimais e janela <= 365 dias.
# Com 6 casas, resíduos binários de float64 (< 1e-9) são absorvidos antes do math.ceil, enquanto
# qualquer fração real de VMD * dias (>= 1 / (1000 * 365) ~= 2.7e-6) é preservada.
UNIT_CEIL_GUARD_DECIMALS = 6
ZERO_UNITS = 0  # P-053.8: nível zero de unidades quando não há venda


@dataclass(frozen=True)
class PolicyViolation:
    """Violação de regra de negócio dos parâmetros da política Mín/Máx (DA-05).

    Retornada como valor puro pelas funções de checagem para que a camada de API
    converta em HTTP 422 (PydanticCustomError) e o domínio lance exceção tipada.
    """

    code: str
    message: str
    context: Mapping[str, int]


class InvalidReplenishmentPolicyError(ValueError):
    """Exceção de domínio lançada quando invariantes da política Mín/Máx são violados.

    Regra: P-053.3, A2 (ADR-001, DA-05).
    """

    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def check_max_coverage_greater_than_min(
    min_days: int,
    max_days: int,
) -> Optional[PolicyViolation]:
    """Verifica se Dias Máximo é estritamente maior que Dias Mínimo.

    Regra: P-053.3 — impede faixa de cobertura degenerada ou invertida.

    Args:
        min_days: Dias de cobertura do Estoque Mínimo.
        max_days: Dias de cobertura do Estoque Máximo.

    Returns:
        None quando válido; PolicyViolation com código INV-001 quando max_days <= min_days.
    """
    if max_days > min_days:
        return None
    return PolicyViolation(
        code=ERROR_CODE_MAX_NOT_GREATER_THAN_MIN,
        message=(
            f"Dias Máximo (maxCoverageDays = {max_days}) deve ser maior que "
            f"Dias Mínimo (minCoverageDays = {min_days})."
        ),
        context={"minCoverageDays": min_days, "maxCoverageDays": max_days},
    )


def check_lead_time_below_max_coverage(
    lead_time_days: int,
    max_days: int,
) -> Optional[PolicyViolation]:
    """Verifica se o Lead Time é estritamente menor que Dias Máximo.

    Regra: A2 (ADR-001, DA-05) — evita classificar como Ruptura Iminente um item cujo
    estoque já está acima do Estoque Máximo (o que geraria status de ruptura com compra 0).

    Args:
        lead_time_days: Prazo de entrega do fornecedor em dias.
        max_days: Dias de cobertura do Estoque Máximo.

    Returns:
        None quando válido; PolicyViolation com código INV-002 quando lead_time_days >= max_days.
    """
    if lead_time_days < max_days:
        return None
    return PolicyViolation(
        code=ERROR_CODE_LEAD_TIME_NOT_BELOW_MAX,
        message=(
            f"Lead Time (leadTimeDays = {lead_time_days}) deve ser menor que "
            f"Dias Máximo (maxCoverageDays = {max_days})."
        ),
        context={"leadTimeDays": lead_time_days, "maxCoverageDays": max_days},
    )


@dataclass(frozen=True)
class ReplenishmentPolicy:
    """Política de reposição Mín/Máx por dias de cobertura e lead time sinalizador.

    Regra: P-053.2, P-053.3, P-055.3, A2 (ADR-001, DA-01 e DA-05).
    """

    min_coverage_days: int = DEFAULT_MIN_COVERAGE_DAYS
    max_coverage_days: int = DEFAULT_MAX_COVERAGE_DAYS
    lead_time_days: int = DEFAULT_LEAD_TIME_DAYS

    def __post_init__(self) -> None:
        min_max_violation = check_max_coverage_greater_than_min(
            self.min_coverage_days,
            self.max_coverage_days,
        )
        if min_max_violation is not None:
            raise InvalidReplenishmentPolicyError(
                min_max_violation.message,
                code=min_max_violation.code,
            )

        lead_time_violation = check_lead_time_below_max_coverage(
            self.lead_time_days,
            self.max_coverage_days,
        )
        if lead_time_violation is not None:
            raise InvalidReplenishmentPolicyError(
                lead_time_violation.message,
                code=lead_time_violation.code,
            )


@dataclass(frozen=True)
class StockLevels:
    """Níveis de Estoque Mínimo e Estoque Máximo em unidades inteiras para um SKU.

    Regra: P-053.4, P-053.5, P-053.8.
    """

    minimum: int
    maximum: int


def ceil_units(value: float) -> int:
    """Arredonda unidades para cima descartando resíduo binário de float64 antes do teto.

    Regra: P-053.6, P-054.2 (ADR-001, DA-02). Sem a guarda de 6 casas, expressões como
    (31 / 15) * 15 produzem 31.000000000000004 em IEEE 754 e math.ceil retornaria 32.

    Args:
        value: Quantidade calculada em ponto flutuante.

    Returns:
        Unidades inteiras arredondadas para cima.
    """
    return math.ceil(round(value, UNIT_CEIL_GUARD_DECIMALS))


def calculate_stock_levels(vmd: float, policy: ReplenishmentPolicy) -> StockLevels:
    """Calcula o Estoque Mínimo e o Estoque Máximo em unidades a partir da VMD e da política.

    Regra: P-053.4, P-053.5, P-053.7, P-053.8 — o cálculo depende exclusivamente da VMD
    em precisão integral e dos dias mínimo/máximo (sem lead time e sem desvio-padrão).

    Args:
        vmd: Venda Média Diária em precisão integral (unidades/dia).
        policy: Política de reposição com min_coverage_days e max_coverage_days.

    Returns:
        StockLevels com minimum e maximum inteiros (0 e 0 quando vmd <= 0).
    """
    if vmd <= ZERO_UNITS:
        return StockLevels(minimum=ZERO_UNITS, maximum=ZERO_UNITS)

    return StockLevels(
        minimum=ceil_units(vmd * policy.min_coverage_days),
        maximum=ceil_units(vmd * policy.max_coverage_days),
    )
