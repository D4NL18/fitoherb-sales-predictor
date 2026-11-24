"""
Grupo Afim: diagnostico de mercado por decomposicao shift-share (P-155, P-156) e identificacao de
Lancamento Afim (P-160). Funcoes puras sobre numeros ja na escala da Janela Atual.
"""
import calendar
import datetime
from dataclasses import dataclass
from typing import Optional

from src.modules.sales_trend.domain.month_windows import index_to_year_month
from src.modules.trend_insights.domain.constants import DOMINANT_EFFECT_RATIO, LAUNCH_MIN_DAYS_AFTER_BASE_START

_EPSILON = 1e-9


@dataclass(frozen=True)
class MarketDiagnosis:
    classificacao: str
    variacao_mercado_pct: Optional[float] = None
    efeito_mercado: Optional[float] = None
    efeito_participacao: Optional[float] = None
    participacao_anterior_pct: Optional[float] = None
    participacao_atual_pct: Optional[float] = None
    variacao_participacao_pp: Optional[float] = None


def _classify(market_effect: float, share_effect: float) -> str:
    """P-156: um efeito e dominante com >= 70% da soma dos modulos."""
    total = abs(market_effect) + abs(share_effect)
    if total <= 0:
        return "MISTO"
    market_weight = abs(market_effect) / total
    if market_weight >= DOMINANT_EFFECT_RATIO - _EPSILON:
        return "MERCADO_EM_QUEDA" if market_effect < 0 else "MERCADO_EM_ALTA"
    if market_weight <= (1 - DOMINANT_EFFECT_RATIO) + _EPSILON:
        return "PERDA_DE_PARTICIPACAO" if share_effect < 0 else "GANHO_DE_PARTICIPACAO"
    return "MISTO"


def compute_market_diagnosis(
    base_adjusted: float,
    a_current: float,
    group_previous_scaled: float,
    group_current: float,
    min_group_base: float,
) -> MarketDiagnosis:
    """Separa a variacao de A em efeito de mercado e de participacao usando os afins sem A (P-155)."""
    if group_previous_scaled < min_group_base or group_previous_scaled <= 0:
        return MarketDiagnosis(classificacao="SEM_GRUPO_AFIM")
    market_variation = (group_current - group_previous_scaled) / group_previous_scaled
    market_effect = base_adjusted * market_variation
    share_effect = (a_current - base_adjusted) - market_effect
    share_before = base_adjusted / (base_adjusted + group_previous_scaled)
    denominator_after = a_current + group_current
    share_after = a_current / denominator_after if denominator_after > 0 else 0.0
    return MarketDiagnosis(
        classificacao=_classify(market_effect, share_effect),
        variacao_mercado_pct=market_variation * 100,
        efeito_mercado=market_effect,
        efeito_participacao=share_effect,
        participacao_anterior_pct=share_before * 100,
        participacao_atual_pct=share_after * 100,
        variacao_participacao_pp=(share_after - share_before) * 100,
    )


def is_launch_affine(
    first_sale_month_index: int,
    pre_last_month_index: int,
    cur_last_month_index: int,
    base_first_date: datetime.date,
) -> bool:
    """1a venda em (fim de PRE, fim de CUR] e >= primeiraData + 90 dias (P-160)."""
    if not pre_last_month_index < first_sale_month_index <= cur_last_month_index:
        return False
    year, month = index_to_year_month(first_sale_month_index)
    last_day_of_first_sale_month = datetime.date(year, month, calendar.monthrange(year, month)[1])
    cutoff = base_first_date + datetime.timedelta(days=LAUNCH_MIN_DAYS_AFTER_BASE_START)
    return last_day_of_first_sale_month >= cutoff
