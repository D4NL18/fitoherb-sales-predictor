"""
Formulas puras das parcelas e indicadores que dependem de fontes externas a Tendencia (P-158, P-159, P-164,
P-165, P-166): sazonalidade, preco, clientes perdidos, ruptura (so estoque atual) e promocao.
Sem I/O: os adaptadores trazem os dados das fontes e este modulo so calcula. Fonte ausente nunca chega aqui
(P-173: o adaptador devolve `NotEvaluated`).
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from src.modules.trend_insights.domain.constants import MIN_PRICE_CHANGE_PCT
from src.modules.trend_insights.domain.evidence import RawParcel
from src.modules.trend_insights.domain.migration_scaling import LostCustomersAggregate

SEASONAL_ELIGIBLE_STRENGTHS = ("FORTE", "MODERADA")
CONFIDENCE_RANK = {"BAIXA": 0, "MEDIA": 1, "ALTA": 2}
LOW_CONFIDENCE = "BAIXA"
MEDIUM_CONFIDENCE = "MEDIA"
MIN_PRICE_VARIATION = -0.50  # P-159: truncamento de delta-p em [-50%, +100%]
MAX_PRICE_VARIATION = 1.00
PERCENT = 100.0
PCT_DECIMALS = 1
INDEX_DECIMALS = 3
LOST_CUSTOMERS_MEDIUM_CLIENTS = 3  # P-164.4
PROMOTION_OBSERVATION = "PRECO_INFLUENCIADO_POR_PROMOCAO"
RUPTURE_OBSERVATION = "Migracao pode ter sido forcada por falta de estoque."


@dataclass(frozen=True)
class SeasonalityEvidence:
    """Resumo do indice sazonal do SKU: `monthly[mes_do_ano] = (indice, confianca)`."""

    eligible: bool
    strength: str
    reason: Optional[str]
    monthly: Mapping[int, Tuple[float, str]]


@dataclass(frozen=True)
class PriceEvidence:
    """Totais efetivos (piso zero) das duas janelas, `k` e a elasticidade do SKU."""

    metric: str
    qty_pre: float
    rev_pre: float
    qty_cur: float
    rev_cur: float
    scale_k: float
    elasticity: float
    is_reliable: bool
    is_fallback: bool
    confidence_level: str
    is_promotion_involved: bool = False


def month_day_weights(start: date, end_exclusive: date) -> Dict[int, int]:
    """Dias da janela `[start, end)` por mes-do-ano: pesos da media do indice sazonal (P-158)."""
    weights: Dict[int, int] = {}
    day = start
    while day < end_exclusive:
        weights[day.month] = weights.get(day.month, 0) + 1
        day += timedelta(days=1)
    return weights


def _weighted_index(weights: Mapping[int, int], monthly: Mapping[int, Tuple[float, str]]) -> Optional[float]:
    total_days = sum(weights.values())
    if not total_days or any(month not in monthly for month in weights):
        return None
    return sum(monthly[month][0] * days for month, days in weights.items()) / total_days


def _lowest_confidence(weights_a: Mapping[int, int], weights_b: Mapping[int, int], monthly) -> str:
    months = set(weights_a) | set(weights_b)
    return min((monthly[m][1] for m in months), key=lambda c: CONFIDENCE_RANK.get(c, 0))


def _no_effect(tipo: str, reason: str) -> RawParcel:
    return RawParcel(tipo=tipo, valor=None, status="SEM_EFEITO", motivo=reason)


def _not_evaluated(tipo: str, reason: str) -> RawParcel:
    return RawParcel(tipo=tipo, valor=None, status="NAO_AVALIADO", motivo=reason)


def build_seasonal_parcel(
    seasonality: SeasonalityEvidence,
    base_adjusted: float,
    cur_weights: Mapping[int, int],
    pre_weights: Mapping[int, int],
) -> RawParcel:
    """`E_saz = baseAjustada x (I(CUR) / I(PRE) - 1)` com elegibilidade, neutralidade e confianca (P-158.1..3)."""
    if not seasonality.eligible or seasonality.strength not in SEASONAL_ELIGIBLE_STRENGTHS:
        return _no_effect("SAZONALIDADE", seasonality.reason or seasonality.strength or "FRACA")
    if set(cur_weights) == set(pre_weights):
        return _no_effect("SAZONALIDADE", "MESMOS_MESES")
    index_cur = _weighted_index(cur_weights, seasonality.monthly)
    index_pre = _weighted_index(pre_weights, seasonality.monthly)
    if index_cur is None or index_pre is None or index_pre <= 0:
        return _not_evaluated("SAZONALIDADE", "FONTE_INDISPONIVEL")
    confidence = _lowest_confidence(cur_weights, pre_weights, seasonality.monthly)
    if confidence == LOW_CONFIDENCE:
        return _not_evaluated("SAZONALIDADE", "CONFIANCA_BAIXA_SAZONAL")
    detail = {"indice_atual": round(index_cur, INDEX_DECIMALS), "indice_anterior": round(index_pre, INDEX_DECIMALS),
              "forca": seasonality.strength}
    return RawParcel(tipo="SAZONALIDADE", valor=base_adjusted * (index_cur / index_pre - 1.0), confianca=confidence,
                     detalhe=detail)


def _price_confidence(price: PriceEvidence) -> str:
    if not price.is_reliable or price.is_fallback:
        return LOW_CONFIDENCE
    return price.confidence_level if price.confidence_level in CONFIDENCE_RANK else MEDIUM_CONFIDENCE


def _price_effect(price: PriceEvidence, variation: float) -> float:
    volume_factor = max(0.0, 1.0 + price.elasticity * variation)
    if price.metric == "quantity":
        return price.qty_pre * price.scale_k * (volume_factor - 1.0)
    return price.rev_pre * price.scale_k * ((1.0 + variation) * volume_factor - 1.0)


def build_price_parcel(price: PriceEvidence) -> RawParcel:
    """Efeito do preco medio praticado com a elasticidade do SKU (P-159); `|dp|` pequeno e `SEM_EFEITO`."""
    if min(price.qty_pre, price.rev_pre, price.qty_cur, price.rev_cur) <= 0:
        return _not_evaluated("PRECO", "SEM_PRECO_MEDIO")
    price_pre, price_cur = price.rev_pre / price.qty_pre, price.rev_cur / price.qty_cur
    raw_variation = (price_cur - price_pre) / price_pre
    if abs(raw_variation) * PERCENT < MIN_PRICE_CHANGE_PCT:
        return _no_effect("PRECO", "VARIACAO_PRECO_PEQUENA")
    variation = min(MAX_PRICE_VARIATION, max(MIN_PRICE_VARIATION, raw_variation))
    detail = {
        "valor_medio_anterior": round(price_pre, 2), "valor_medio_atual": round(price_cur, 2),
        "variacao_valor_pct": round(raw_variation * PERCENT, PCT_DECIMALS), "elasticidade": round(price.elasticity, 2),
        "observacoes": [PROMOTION_OBSERVATION] if price.is_promotion_involved else [],
    }
    return RawParcel(tipo="PRECO", valor=_price_effect(price, variation), confianca=_price_confidence(price),
                     detalhe=detail)


def build_lost_customers_parcel(aggregate: Optional[LostCustomersAggregate], metric: str) -> RawParcel:
    """`E_perdidos = -soma(max(0, pre*k - cur))` dos clientes perdidos sem ganho em afins (P-164)."""
    if aggregate is None or aggregate.count <= 0:
        return _no_effect("CLIENTES_PERDIDOS", "SEM_CLIENTES_PERDIDOS")
    amount = aggregate.quantity if metric == "quantity" else aggregate.revenue
    confidence = MEDIUM_CONFIDENCE if aggregate.count >= LOST_CUSTOMERS_MEDIUM_CLIENTS else LOW_CONFIDENCE
    return RawParcel(tipo="CLIENTES_PERDIDOS", valor=-amount, confianca=confidence,
                     detalhe={"clientes_perdidos_qtd": aggregate.count})


def _indicator(tipo: str, status: str, **fields: Any) -> Dict[str, Any]:
    base = {"tipo": tipo, "status": status, "valor": None, "evidencia": None}
    base.update(fields)
    return base


def not_evaluated_indicator(tipo: str, reason: str) -> Dict[str, Any]:
    return _indicator(tipo, "NAO_AVALIADO", motivo_nao_avaliado=reason)


def build_stockout_indicator(current_stock: float, has_value_migration: bool) -> Dict[str, Any]:
    """`RUPTURA` so com o estoque atual <= 0 (P-165); sem valor e com confianca `BAIXA`."""
    if current_stock > 0:
        return _indicator("RUPTURA", "SEM_EFEITO", motivo_sem_efeito="SEM_RUPTURA")
    evidence = {"estoque_atual": current_stock, "status_estoque": "SEM_ESTOQUE",
                "observacao": RUPTURE_OBSERVATION if has_value_migration else None}
    return _indicator("RUPTURA", "AVALIADO", sentido="NEGATIVO", confianca=LOW_CONFIDENCE, evidencia=evidence)


def build_promotion_indicator(
    own_pre: bool, own_cur: bool, affines_pre: FrozenSet[int], affines_cur: FrozenSet[int],
) -> Dict[str, Any]:
    """Fim/inicio de promocao do proprio SKU e afins em promocao so na Janela Atual (P-166)."""
    affines_only_current = sorted(affines_cur - affines_pre)
    evidence = {"produto_em_promocao_anterior": own_pre, "produto_em_promocao_atual": own_cur,
                "afins_em_promocao_so_na_atual": affines_only_current}
    if own_pre != own_cur:
        direction = "POSITIVO" if own_cur else "NEGATIVO"
        return _indicator("PROMOCAO", "AVALIADO", sentido=direction, confianca=LOW_CONFIDENCE, evidencia=evidence)
    if affines_only_current:
        return _indicator("PROMOCAO", "AVALIADO", sentido="NEGATIVO", confianca=LOW_CONFIDENCE, evidencia=evidence)
    return _indicator("PROMOCAO", "SEM_EFEITO", motivo_sem_efeito="SEM_PROMOCAO")


def is_recent_base_month(base_month_index: int, reference_month_index: int, max_months_before: int) -> bool:
    """Fatores que so existem 'hoje' (churn, estoque) valem no mes da referencia ou ate N meses antes (P-164.2)."""
    return 0 <= reference_month_index - base_month_index <= max_months_before
