"""
Suíte TDD (fase vermelha): Objeto de Política Mín/Máx e teto sem resíduo.

Regras cobertas: P-053.2, P-053.3 (INV-001), A2 (INV-002), P-053.4 a P-053.8, A3 (DA-02).
Contrato: .agents/docs/api_contracts/inventory.md (seção 1.2) e ADR-001 (DA-01, DA-02, DA-05).
"""
import dataclasses

import pytest

from src.modules.inventory.domain.replenishment_policy import (
    DEFAULT_LEAD_TIME_DAYS,
    DEFAULT_MAX_COVERAGE_DAYS,
    DEFAULT_MIN_COVERAGE_DAYS,
    ERROR_CODE_LEAD_TIME_NOT_BELOW_MAX,
    ERROR_CODE_MAX_NOT_GREATER_THAN_MIN,
    InvalidReplenishmentPolicyError,
    PolicyViolation,
    ReplenishmentPolicy,
    StockLevels,
    calculate_stock_levels,
    ceil_units,
    check_lead_time_below_max_coverage,
    check_max_coverage_greater_than_min,
)


# ---------------------------------------------------------------------------
# P-053.2 — Padrões e imutabilidade
# ---------------------------------------------------------------------------
class TestPolicyDefaults:
    def test_p053_2_default_constants(self):
        assert DEFAULT_MIN_COVERAGE_DAYS == 30
        assert DEFAULT_MAX_COVERAGE_DAYS == 60
        assert DEFAULT_LEAD_TIME_DAYS == 15
        assert ERROR_CODE_MAX_NOT_GREATER_THAN_MIN == "INV-001"
        assert ERROR_CODE_LEAD_TIME_NOT_BELOW_MAX == "INV-002"

    def test_p053_2_default_policy_is_30_60_15(self):
        policy = ReplenishmentPolicy()
        assert policy.min_coverage_days == 30
        assert policy.max_coverage_days == 60
        assert policy.lead_time_days == 15

    def test_p053_2_policy_is_immutable(self):
        policy = ReplenishmentPolicy(min_coverage_days=30, max_coverage_days=60, lead_time_days=15)
        with pytest.raises(dataclasses.FrozenInstanceError):
            policy.min_coverage_days = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P-053.3 / A2 — Checagens puras (sem exceção) usadas pela API e pelo domínio
# ---------------------------------------------------------------------------
class TestPolicyChecks:
    def test_p053_3_max_greater_than_min_returns_none(self):
        assert check_max_coverage_greater_than_min(30, 60) is None

    @pytest.mark.parametrize(
        "min_days,max_days",
        [(60, 60), (50, 45)],
        ids=["P-053.3-igual", "P-053.3-menor"],
    )
    def test_p053_3_max_not_greater_than_min_returns_inv001(self, min_days, max_days):
        violation = check_max_coverage_greater_than_min(min_days, max_days)
        assert isinstance(violation, PolicyViolation)
        assert violation.code == "INV-001"
        assert violation.message == (
            f"Dias Máximo (maxCoverageDays = {max_days}) deve ser maior que "
            f"Dias Mínimo (minCoverageDays = {min_days})."
        )
        assert dict(violation.context) == {"minCoverageDays": min_days, "maxCoverageDays": max_days}

    def test_a2_lead_time_below_max_returns_none(self):
        assert check_lead_time_below_max_coverage(15, 60) is None
        assert check_lead_time_below_max_coverage(39, 40) is None

    @pytest.mark.parametrize(
        "lead_time,max_days",
        [(45, 40), (40, 40)],
        ids=["A2-maior", "A2-igual"],
    )
    def test_a2_lead_time_not_below_max_returns_inv002(self, lead_time, max_days):
        violation = check_lead_time_below_max_coverage(lead_time, max_days)
        assert isinstance(violation, PolicyViolation)
        assert violation.code == "INV-002"
        assert violation.message == (
            f"Lead Time (leadTimeDays = {lead_time}) deve ser menor que "
            f"Dias Máximo (maxCoverageDays = {max_days})."
        )
        assert dict(violation.context) == {"leadTimeDays": lead_time, "maxCoverageDays": max_days}


# ---------------------------------------------------------------------------
# DA-05 — Defesa em profundidade: o objeto de política recusa invariantes quebrados
# ---------------------------------------------------------------------------
class TestPolicyInvariants:
    @pytest.mark.parametrize(
        "min_days,max_days,lead_time,expected_code",
        [
            (60, 60, 15, "INV-001"),
            (50, 45, 15, "INV-001"),
            (20, 40, 45, "INV-002"),
            (20, 40, 40, "INV-002"),
        ],
        ids=["CA-P053-04-60/60", "CA-P053-04-50/45", "A2-lead45-max40", "A2-lead40-max40"],
    )
    def test_invalid_policy_raises_with_code(self, min_days, max_days, lead_time, expected_code):
        with pytest.raises(InvalidReplenishmentPolicyError) as exc_info:
            ReplenishmentPolicy(
                min_coverage_days=min_days, max_coverage_days=max_days, lead_time_days=lead_time
            )
        assert exc_info.value.code == expected_code

    def test_invalid_policy_error_is_value_error(self):
        assert issubclass(InvalidReplenishmentPolicyError, ValueError)

    def test_adjusted_valid_policy_is_accepted(self):
        policy = ReplenishmentPolicy(min_coverage_days=20, max_coverage_days=45, lead_time_days=10)
        assert (policy.min_coverage_days, policy.max_coverage_days, policy.lead_time_days) == (20, 45, 10)


# ---------------------------------------------------------------------------
# DA-02 / A3 — ceil_units: teto imune a resíduo binário, mas preserva fração real
# ---------------------------------------------------------------------------
class TestCeilUnits:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (31 / 15 * 15, 31),      # 31.000000000000004 -> 31 (resíduo de float)
            ((1 / 60) * 60, 1),      # E5: 1 un em 60 dias cobre exatamente 60 dias
            (37.5, 38),              # fração real -> teto
            (2.000003, 3),           # 3e-6 fica acima da guarda de 6 casas
            (69.6, 70),              # C8
            (0.0, 0),
            (120.0, 120),
        ],
        ids=["residuo-31/15", "residuo-1/60", "fracao-37.5", "fracao-3e-6", "C8-69.6", "zero", "inteiro"],
    )
    def test_ceil_units(self, value, expected):
        result = ceil_units(value)
        assert result == expected
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# P-053.4 a P-053.8 — Estoque Mínimo / Máximo (exemplos E1–E6)
# ---------------------------------------------------------------------------
class TestStockLevels:
    @pytest.mark.parametrize(
        "sold_in_window,window_days,min_days,max_days,expected_min,expected_max",
        [
            (120, 60, 30, 60, 60, 120),
            (75, 60, 30, 60, 38, 75),
            (30, 60, 30, 60, 15, 30),
            (120, 60, 20, 45, 40, 90),
            (1, 60, 30, 60, 1, 1),
            (0, 60, 30, 60, 0, 0),
        ],
        ids=["P-053-E1", "P-053-E2", "P-053-E3", "P-053-E4", "P-053-E5", "P-053-E6"],
    )
    def test_p053_examples(self, sold_in_window, window_days, min_days, max_days, expected_min, expected_max):
        vmd = sold_in_window / window_days
        policy = ReplenishmentPolicy(min_coverage_days=min_days, max_coverage_days=max_days, lead_time_days=15)
        levels = calculate_stock_levels(vmd, policy)
        assert isinstance(levels, StockLevels)
        assert levels.minimum == expected_min
        assert levels.maximum == expected_max
        assert isinstance(levels.minimum, int) and isinstance(levels.maximum, int)

    def test_p053_7_lead_time_does_not_affect_levels(self):
        short_lead = calculate_stock_levels(2.0, ReplenishmentPolicy(30, 60, 1))
        long_lead = calculate_stock_levels(2.0, ReplenishmentPolicy(30, 60, 59))
        assert short_lead == long_lead == StockLevels(minimum=60, maximum=120)

    def test_p053_8_negative_vmd_is_treated_as_no_sales(self):
        assert calculate_stock_levels(-1.0, ReplenishmentPolicy()) == StockLevels(minimum=0, maximum=0)

    def test_p053_6_rounded_vmd_would_overstate_maximum(self):
        """Documenta o defeito evitado: VMD a 4 casas (0.0167) daria máximo 2; precisão integral dá 1."""
        assert calculate_stock_levels(round(1 / 60, 4), ReplenishmentPolicy()).maximum == 2
        assert calculate_stock_levels(1 / 60, ReplenishmentPolicy()).maximum == 1
