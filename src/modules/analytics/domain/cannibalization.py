"""
Módulo de Domínio Puro de Canibalização e Substituição de Produtos (Fase F6).
Regras: P-128 a P-137; ADR-007 DA-01 a DA-06.

Isolamento estrito: funções puras em Python/NumPy/Pandas sem dependência de I/O,
banco de dados ou frameworks web. Zero exposição de `Cod Cliente` em retornos ou logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import erfc, sqrt
from typing import AbstractSet, Any, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from src.modules.analytics.domain.exceptions import (
    CannibalizationEventNotFoundError,
    CannibalizationInsufficientHistoryError,
    CannibalizationInvalidParametersError,
    CannibalizationProductNotFoundError,
)

# ---------------------------------------------------------------------------
# Constantes Canônicas do Domínio (P-128 a P-137)
# ---------------------------------------------------------------------------
MIN_JACCARD_SIMILARITY: float = 0.15
MIN_COMMON_BUYERS: int = 5
MAX_CANDIDATE_SUBSTITUTES: int = 20
MIN_PRICE_CHANGE_PCT: float = 0.05
LAUNCH_CUTOFF_DATE: date = date(2025, 4, 1)
MIN_LAUNCH_MONTHS: int = 3
DEFAULT_ANALYSIS_WINDOW_WEEKS: int = 4
MIN_ANALYSIS_WINDOW_WEEKS: int = 2
MAX_ANALYSIS_WINDOW_WEEKS: int = 12
MIN_CONTROL_GROUP_SIZE: int = 5
CONTROL_MAX_PRICE_VARIATION: float = 0.03
FDR_ALPHA: float = 0.05
MIN_EFFECT_VOLUME_UNITS: int = 5
COST_FALLBACK_RATIO: float = 0.60
CACHE_TTL_HOURS: int = 6
RETURN_OPERATION_PATTERN: str = "DEVOLU%"


# ---------------------------------------------------------------------------
# Dataclasses de Domínio
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubstituteCandidate:
    """Produto candidato a substituto com métricas agregadas de similaridade (sem PII)."""

    sku: str
    description: str
    category: str
    jaccard_similarity: float
    common_buyers_count: int
    current_price: float
    current_stock: int


@dataclass(frozen=True)
class DetectedEvent:
    """Evento comercial detectado ou parametrizado para o SKU alvo (P-129)."""

    event_type: str
    event_date: date
    price_direction: str
    avg_price_change_pct: float


@dataclass(frozen=True)
class PrePostWindows:
    """Janelas simétricas pré e pós evento com densidade diária contínua (P-130)."""

    pre_start: date
    pre_end: date
    post_start: date
    post_end: date
    pre_daily: pd.DataFrame
    post_daily: pd.DataFrame
    pre_total_volume: float
    post_total_volume: float
    pre_total_revenue: float
    post_total_revenue: float
    pre_avg_price: float
    post_avg_price: float


@dataclass(frozen=True)
class ControlGroupResult:
    """Grupo de controle categorial/expandido selecionado para o DiD (P-131)."""

    skus: Tuple[str, ...]
    sample_size: int
    control_strategy: str
    is_expanded_control: bool
    pre_volumes: Tuple[float, ...]
    post_volumes: Tuple[float, ...]


@dataclass(frozen=True)
class DiDResult:
    """Resultado da estimação Diferença em Diferenças para um candidato (P-132)."""

    growth_factor: float
    counterfactual_volume: float
    delta_volume: float
    delta_volume_pct: float


@dataclass(frozen=True)
class NetImpactResult:
    """Consolidação financeira global e veredito comercial da ação (P-135)."""

    target_delta_volume: float
    affected_delta_volume: float
    net_delta_volume: float
    target_delta_revenue: float
    affected_delta_revenue: float
    net_delta_revenue: float
    target_delta_margin: float
    affected_delta_margin: float
    net_delta_margin: float
    commercial_verdict: str


# ---------------------------------------------------------------------------
# P-128: Identificação de Substitutos e Similaridade de Jaccard
# ---------------------------------------------------------------------------

def calculate_jaccard_similarity(buyers_target: AbstractSet[Any], buyers_candidate: AbstractSet[Any]) -> float:
    """Calcula o Coeficiente de Jaccard |A ∩ B| / |A ∪ B| com proteção contra conjuntos vazios (P-128.2)."""
    if not buyers_target or not buyers_candidate:
        return 0.0
    union_count = len(buyers_target | buyers_candidate)
    if union_count == 0:
        return 0.0
    return float(len(buyers_target & buyers_candidate) / union_count)


def find_candidate_substitutes(
    target_sku: str,
    catalog: Mapping[str, Mapping[str, Any]],
    buyers_by_sku: Mapping[str, AbstractSet[Any]],
    min_jaccard: float = MIN_JACCARD_SIMILARITY,
    limit: int = MAX_CANDIDATE_SUBSTITUTES,
) -> List[SubstituteCandidate]:
    """
    Identifica produtos candidatos a substitutos do SKU alvo (P-128.1 a P-128.5).

    Critério (P-128.3):
    - Mesmo `category` (`Tipo`): Jaccard >= `min_jaccard` OU compradores em comum >= `MIN_COMMON_BUYERS`.
    - `category` diferente: apenas se compradores em comum >= `MIN_COMMON_BUYERS`.
    """
    target_key = str(target_sku)
    target_entry = catalog.get(target_key)
    if target_entry is None or not target_entry.get("active", True):
        raise CannibalizationProductNotFoundError()

    target_category = str(target_entry.get("category", "") or "")
    target_buyers = buyers_by_sku.get(target_key, set())
    if not target_buyers:
        return []

    candidates: List[SubstituteCandidate] = []
    for sku, entry in catalog.items():
        sku_str = str(sku)
        if sku_str == target_key or not entry.get("active", True):
            continue

        cand_buyers = buyers_by_sku.get(sku_str, set())
        if not cand_buyers:
            continue

        common_count = len(target_buyers & cand_buyers)
        if common_count == 0:
            continue

        jaccard = calculate_jaccard_similarity(target_buyers, cand_buyers)
        cand_category = str(entry.get("category", "") or "")
        same_category = cand_category == target_category

        if same_category:
            eligible = (jaccard >= min_jaccard) or (common_count >= MIN_COMMON_BUYERS)
        else:
            eligible = common_count >= MIN_COMMON_BUYERS

        if not eligible:
            continue

        candidates.append(
            SubstituteCandidate(
                sku=sku_str,
                description=str(entry.get("description", "")),
                category=cand_category,
                jaccard_similarity=jaccard,
                common_buyers_count=common_count,
                current_price=float(entry.get("current_price", 0.0)),
                current_stock=int(entry.get("current_stock", 0)),
            )
        )

    candidates.sort(key=lambda c: (c.jaccard_similarity, c.common_buyers_count), reverse=True)
    return candidates[:limit]


# ---------------------------------------------------------------------------
# P-137.2: Abatimento de Devoluções
# ---------------------------------------------------------------------------

def apply_returns_netting(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Soma algebricamente vendas e devoluções (`[Operação] LIKE 'DEVOLU%'`) por SKU e data (P-137.2).
    Volumes líquidos <= 0 são ajustados para 0.0 na série.
    """
    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=["sku", "date", "qty", "revenue", "price"])

    df = raw_df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0.0)
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0.0)

    if "operation" in df.columns:
        op_upper = df["operation"].astype(str).str.upper()
        is_return = op_upper.str.startswith("DEVOLU")
        # Garante sinal negativo para devoluções caso venham positivas
        df.loc[is_return & (df["qty"] > 0), "qty"] = -df.loc[is_return & (df["qty"] > 0), "qty"]
        df.loc[is_return & (df["revenue"] > 0), "revenue"] = -df.loc[is_return & (df["revenue"] > 0), "revenue"]

    grouped = df.groupby(["sku", "date"], as_index=False).agg(
        qty=("qty", "sum"),
        revenue=("revenue", "sum"),
    )
    grouped["qty"] = grouped["qty"].clip(lower=0.0)
    grouped["revenue"] = grouped["revenue"].clip(lower=0.0)
    grouped["price"] = np.where(grouped["qty"] > 0.0, grouped["revenue"] / grouped["qty"], 0.0)
    return grouped.sort_values(["sku", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# P-129 & P-130: Detecção de Eventos e Janelas Simétricas
# ---------------------------------------------------------------------------

def _to_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def detect_product_events(
    sku: str,
    sales_series: pd.DataFrame,
    promo_calendar: pd.DataFrame,
    event_type: str = "promo",
    event_date: Optional[date] = None,
    window_weeks: int = DEFAULT_ANALYSIS_WINDOW_WEEKS,
    history_start: Optional[date] = None,
    history_end: Optional[date] = None,
) -> DetectedEvent:
    """
    Detecta ou valida o evento comercial (`promo`, `price`, `launch`) do SKU alvo (P-129).
    """
    if event_type not in ("promo", "price", "launch"):
        raise CannibalizationInvalidParametersError(fields=["eventType"])

    sku_str = str(sku)
    df = sales_series.copy() if sales_series is not None else pd.DataFrame()
    if not df.empty and "sku" in df.columns:
        df = df[df["sku"].astype(str) == sku_str].copy()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        if history_end is not None:
            df = df[df["date"] <= history_end].copy()
        df = df.sort_values("date")

    if event_type == "promo":
        return _detect_promo_event(
            sku_str,
            promo_calendar,
            event_date,
            window_weeks=window_weeks,
            history_start=history_start,
            history_end=history_end,
        )

    if event_type == "price":
        return _detect_price_event(
            df,
            event_date,
            min_buffer_days=window_weeks * 7,
            history_start=history_start,
            history_end=history_end,
        )

    return _detect_launch_event(df, event_date)


def _detect_promo_event(
    sku_str: str,
    promo_calendar: Optional[pd.DataFrame],
    event_date: Optional[date],
    window_weeks: int = DEFAULT_ANALYSIS_WINDOW_WEEKS,
    history_start: Optional[date] = None,
    history_end: Optional[date] = None,
) -> DetectedEvent:
    if promo_calendar is None or promo_calendar.empty:
        raise CannibalizationEventNotFoundError()

    cal = promo_calendar.copy()
    if "sku" in cal.columns:
        cal = cal[cal["sku"].astype(str) == sku_str]
    if cal.empty:
        raise CannibalizationEventNotFoundError()

    cal["start_date"] = pd.to_datetime(cal["start_date"]).dt.date
    if event_date is not None:
        matched = cal[cal["start_date"] == event_date]
        selected_date = event_date if not matched.empty else event_date
    else:
        days = window_weeks * 7
        valid_dates = cal["start_date"]
        if history_start is not None:
            valid_dates = valid_dates[valid_dates >= history_start + timedelta(days=days)]
        if history_end is not None:
            valid_dates = valid_dates[valid_dates <= history_end - timedelta(days=days - 1)]
        if valid_dates.empty:
            raise CannibalizationInsufficientHistoryError()
        selected_date = valid_dates.max()

    return DetectedEvent(
        event_type="promo",
        event_date=selected_date,
        price_direction="NONE",
        avg_price_change_pct=0.0,
    )


def _detect_price_event(
    df: pd.DataFrame,
    event_date: Optional[date],
    min_buffer_days: int = 28,
    history_start: Optional[date] = None,
    history_end: Optional[date] = None,
) -> DetectedEvent:
    if df.empty or len(df) < 14:
        raise CannibalizationEventNotFoundError()

    df = df.copy()
    if "price" not in df.columns:
        df["price"] = np.where(df["qty"] > 0, df["revenue"] / df["qty"], 0.0)

    positive = df[df["qty"] > 0].copy()
    if positive.empty:
        raise CannibalizationEventNotFoundError()

    if event_date is not None:
        pre = positive[positive["date"] < event_date]
        post = positive[positive["date"] >= event_date]
        if pre.empty or post.empty:
            raise CannibalizationEventNotFoundError()
        p_pre = float(pre["price"].mean())
        p_post = float(post["price"].mean())
        if p_pre <= 0:
            raise CannibalizationEventNotFoundError()
        change_ratio = (p_post - p_pre) / p_pre
        if abs(change_ratio) < MIN_PRICE_CHANGE_PCT:
            raise CannibalizationEventNotFoundError()
        direction = "PRICE_DROP" if change_ratio < 0 else "PRICE_HIKE"
        return DetectedEvent(
            event_type="price",
            event_date=event_date,
            price_direction=direction,
            avg_price_change_pct=change_ratio * 100.0,
        )

    # Varre pontos semanais / transições no histórico para encontrar a maior mudança >= 5%
    unique_dates = sorted(positive["date"].unique())
    best_date: Optional[date] = None
    best_change: float = 0.0

    # Avalia pontos candidatos respeitando a janela pré/pós completa (fallback 7d se histórico curto)
    bound_start = history_start if history_start is not None else unique_dates[0]
    bound_end = history_end if history_end is not None else unique_dates[-1]
    min_d = bound_start + timedelta(days=min_buffer_days)
    max_d = bound_end - timedelta(days=max(0, min_buffer_days - 1))
    candidates = [d for d in unique_dates if min_d <= d <= max_d]
    if not candidates and history_start is None and history_end is None:
        min_d = unique_dates[0] + timedelta(days=7)
        max_d = unique_dates[-1] - timedelta(days=7)
        candidates = [d for d in unique_dates if min_d <= d <= max_d]
    # Testa em passos semanais ou todos os dias se poucos
    step = max(1, len(candidates) // 30)
    for cand_date in candidates[::step]:
        pre_slice = positive[(positive["date"] >= cand_date - timedelta(days=28)) & (positive["date"] < cand_date)]
        post_slice = positive[(positive["date"] >= cand_date) & (positive["date"] < cand_date + timedelta(days=28))]
        if pre_slice.empty or post_slice.empty:
            continue
        p_pre = float(pre_slice["price"].mean())
        p_post = float(post_slice["price"].mean())
        if p_pre <= 0:
            continue
        ratio = (p_post - p_pre) / p_pre
        if abs(ratio) >= MIN_PRICE_CHANGE_PCT and abs(ratio) > abs(best_change):
            best_change = ratio
            best_date = cand_date

    if best_date is None:
        raise CannibalizationEventNotFoundError()

    direction = "PRICE_DROP" if best_change < 0 else "PRICE_HIKE"
    return DetectedEvent(
        event_type="price",
        event_date=best_date,
        price_direction=direction,
        avg_price_change_pct=best_change * 100.0,
    )


def _detect_launch_event(df: pd.DataFrame, event_date: Optional[date]) -> DetectedEvent:
    if df.empty:
        raise CannibalizationEventNotFoundError()

    positive = df[df["qty"] > 0]
    if positive.empty:
        raise CannibalizationEventNotFoundError()

    first_sale = min(positive["date"])
    last_sale = max(positive["date"])

    # P-129.3: Trava anti-falso lançamento
    if first_sale < LAUNCH_CUTOFF_DATE:
        raise CannibalizationEventNotFoundError()

    # P-129.4: Mínimo de 3 meses completos (~90 dias) de histórico pós-lançamento
    if (last_sale - first_sale).days < MIN_LAUNCH_MONTHS * 30:
        raise CannibalizationInsufficientHistoryError()

    chosen_date = event_date if event_date is not None else first_sale
    return DetectedEvent(
        event_type="launch",
        event_date=chosen_date,
        price_direction="NONE",
        avg_price_change_pct=0.0,
    )


def build_pre_post_windows(
    event_date: date,
    window_weeks: int,
    sales_series: pd.DataFrame,
    history_start: Optional[date] = None,
    history_end: Optional[date] = None,
    allow_empty_pre: bool = False,
) -> PrePostWindows:
    """
    Constrói janelas simétricas [T0 - W*7, T0 - 1] e [T0, T0 + W*7 - 1] com zero-fill (P-130).
    """
    if window_weeks < MIN_ANALYSIS_WINDOW_WEEKS or window_weeks > MAX_ANALYSIS_WINDOW_WEEKS:
        raise CannibalizationInvalidParametersError(fields=["windowWeeks"])

    days = window_weeks * 7
    pre_start = event_date - timedelta(days=days)
    pre_end = event_date - timedelta(days=1)
    post_start = event_date
    post_end = event_date + timedelta(days=days - 1)

    if not allow_empty_pre and history_start is not None and pre_start < history_start:
        raise CannibalizationInsufficientHistoryError()
    if history_end is not None and post_end > history_end:
        raise CannibalizationInsufficientHistoryError()

    df = sales_series.copy() if sales_series is not None else pd.DataFrame(columns=["date", "qty", "revenue"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        daily_agg = df.groupby("date", as_index=False).agg(
            qty=("qty", "sum"),
            revenue=("revenue", "sum"),
        )
    else:
        daily_agg = pd.DataFrame(columns=["date", "qty", "revenue"])

    def _fill_window(start: date, end: date) -> pd.DataFrame:
        date_grid = pd.DataFrame({"date": [start + timedelta(days=i) for i in range((end - start).days + 1)]})
        merged = date_grid.merge(daily_agg, on="date", how="left")
        merged["qty"] = merged["qty"].fillna(0.0).astype(float)
        merged["revenue"] = merged["revenue"].fillna(0.0).astype(float)
        return merged

    pre_daily = _fill_window(pre_start, pre_end)
    post_daily = _fill_window(post_start, post_end)

    pre_vol = float(pre_daily["qty"].sum())
    post_vol = float(post_daily["qty"].sum())
    pre_rev = float(pre_daily["revenue"].sum())
    post_rev = float(post_daily["revenue"].sum())
    pre_price = (pre_rev / pre_vol) if pre_vol > 0 else 0.0
    post_price = (post_rev / post_vol) if post_vol > 0 else 0.0

    return PrePostWindows(
        pre_start=pre_start,
        pre_end=pre_end,
        post_start=post_start,
        post_end=post_end,
        pre_daily=pre_daily,
        post_daily=post_daily,
        pre_total_volume=pre_vol,
        post_total_volume=post_vol,
        pre_total_revenue=pre_rev,
        post_total_revenue=post_rev,
        pre_avg_price=pre_price,
        post_avg_price=post_price,
    )


# ---------------------------------------------------------------------------
# P-131 & P-132: Grupo de Controle e Diferença em Diferenças (DiD)
# ---------------------------------------------------------------------------

def select_control_group(
    target_sku: str,
    target_category: str,
    target_supplier: str,
    substitute_skus: AbstractSet[str],
    category_products: Sequence[Mapping[str, Any]],
) -> ControlGroupResult:
    """
    Seleciona grupo de controle estável com fallback CATEGORIAL -> FORNECEDOR -> GLOBAL (P-131).
    """
    target_key = str(target_sku)
    sub_keys = {str(s) for s in substitute_skus}

    eligible: List[Mapping[str, Any]] = []
    for prod in category_products:
        sku = str(prod["sku"])
        if sku == target_key or sku in sub_keys:
            continue
        if prod.get("in_promo", False):
            continue
        if abs(float(prod.get("price_change_pct", 0.0))) > CONTROL_MAX_PRICE_VARIATION:
            continue
        if float(prod.get("pre_vol", 0.0)) <= 0.0 and float(prod.get("post_vol", 0.0)) <= 0.0:
            continue
        eligible.append(prod)

    cat_group = [p for p in eligible if str(p.get("category", "")) == str(target_category)]
    if len(cat_group) >= MIN_CONTROL_GROUP_SIZE:
        selected = cat_group
        strategy = "CATEGORIAL"
        expanded = False
    else:
        sup_group = [
            p for p in eligible
            if str(p.get("category", "")) == str(target_category)
            or (target_supplier and str(p.get("supplier", "")) == str(target_supplier))
        ]
        if len(sup_group) >= MIN_CONTROL_GROUP_SIZE:
            selected = sup_group
            strategy = "FORNECEDOR"
            expanded = True
        elif len(eligible) >= MIN_CONTROL_GROUP_SIZE:
            selected = eligible
            strategy = "GLOBAL"
            expanded = True
        else:
            raise CannibalizationInsufficientHistoryError()

    return ControlGroupResult(
        skus=tuple(str(p["sku"]) for p in selected),
        sample_size=len(selected),
        control_strategy=strategy,
        is_expanded_control=expanded,
        pre_volumes=tuple(float(p["pre_vol"]) for p in selected),
        post_volumes=tuple(float(p["post_vol"]) for p in selected),
    )


def estimate_difference_in_differences(
    candidate_pre_volume: float,
    candidate_post_volume: float,
    control_pre_volumes: Sequence[float],
    control_post_volumes: Sequence[float],
) -> DiDResult:
    """
    Estima o efeito causal líquido via Diferença em Diferenças (P-132).
    """
    sum_ctrl_pre = float(sum(control_pre_volumes))
    sum_ctrl_post = float(sum(control_post_volumes))

    growth_factor = (sum_ctrl_post / sum_ctrl_pre) if sum_ctrl_pre > 0.0 else 1.0
    counterfactual = float(candidate_pre_volume) * growth_factor
    delta_volume = float(candidate_post_volume) - counterfactual
    delta_pct = ((delta_volume / counterfactual) * 100.0) if counterfactual > 0.0 else 0.0

    return DiDResult(
        growth_factor=growth_factor,
        counterfactual_volume=counterfactual,
        delta_volume=delta_volume,
        delta_volume_pct=delta_pct,
    )


def compute_did_significance_and_ci(
    candidate_pre_daily: Sequence[float],
    candidate_post_daily: Sequence[float],
    growth_factor: float,
) -> Tuple[float, Tuple[float, float]]:
    """
    Calcula o p-valor bicaudal e o intervalo de confiança de 95% para o efeito DiD total (P-133.1, P-133.4).

    Quando há pelo menos 2 semanas completas (`n >= 14` múltiplo de 7), agrega em blocos semanais
    conforme ADR-007 DA-03 para neutralizar variância artificial de fins de semana / dias sem faturamento B2B.
    """
    pre_arr = np.asarray(candidate_pre_daily, dtype=float)
    post_arr = np.asarray(candidate_post_daily, dtype=float)
    n_pre = len(pre_arr)
    n_post = len(post_arr)

    if n_pre >= 14 and n_post >= 14 and n_pre % 7 == 0 and n_post % 7 == 0:
        w_pre = n_pre // 7
        w_post = n_post // 7
        pre_arr = pre_arr.reshape(w_pre, 7).sum(axis=1)
        post_arr = post_arr.reshape(w_post, 7).sum(axis=1)
        n_pre = w_pre
        n_post = w_post

    if n_pre < 2 or n_post < 2:
        delta = float(post_arr.sum() - pre_arr.sum() * growth_factor)
        return 1.0, (delta, delta)

    expected_post_arr = pre_arr * float(growth_factor)
    diff_total = float(post_arr.sum() - expected_post_arr.sum())

    var_pre = float(np.var(expected_post_arr, ddof=1))
    var_post = float(np.var(post_arr, ddof=1))
    se_total = sqrt(max(var_post * n_post + var_pre * n_pre, 1e-12))

    z_stat = abs(diff_total) / se_total
    p_value = float(erfc(z_stat / sqrt(2.0)))
    margin_err = 1.96 * se_total
    return p_value, (diff_total - margin_err, diff_total + margin_err)


# ---------------------------------------------------------------------------
# P-134 & P-135: Classificação, Margem Unitária e Efeito Líquido Global
# ---------------------------------------------------------------------------

def classify_impact(
    target_delta_volume: float,
    candidate_delta_volume: float,
    q_value: float,
) -> str:
    """
    Classifica o impacto no produto candidato conforme P-133.3 e P-134.
    """
    if q_value > FDR_ALPHA or abs(candidate_delta_volume) < MIN_EFFECT_VOLUME_UNITS:
        return "SEM_EFEITO"
    if target_delta_volume < 0.0 and candidate_delta_volume > 0.0:
        return "MIGRACAO_POSITIVA"
    if candidate_delta_volume < 0.0:
        return "CANIBALIZACAO"
    if candidate_delta_volume > 0.0:
        return "COMPLEMENTO"
    return "SEM_EFEITO"


def resolve_unit_margin(
    selling_price: float,
    last_cost: Optional[float],
) -> Tuple[float, bool]:
    """
    Calcula margem unitária aplicando fallback de custo de 60% quando nulo/inválido (P-135.3).
    """
    price = max(0.0, float(selling_price))
    if last_cost is None or float(last_cost) <= 0.0 or float(last_cost) > price:
        estimated_cost = price * COST_FALLBACK_RATIO
        return price - estimated_cost, True
    return price - float(last_cost), False


def calculate_net_impact(
    target_metrics: Mapping[str, float],
    affected_items: Sequence[Mapping[str, Any]],
) -> NetImpactResult:
    """
    Consolida o balanço líquido em volume, receita e margem e emite o veredito comercial (P-135).
    """
    target_dv = float(target_metrics["delta_volume"])
    target_dr = float(target_metrics["delta_revenue"])
    target_dm = float(target_metrics["delta_margin"])

    sig_items = [item for item in affected_items if item.get("is_significant", True)]

    affected_dv = sum(float(item["delta_volume"]) for item in sig_items)
    affected_dr = sum(float(item["delta_volume"]) * float(item["unit_price"]) for item in sig_items)
    affected_dm = sum(float(item["delta_volume"]) * float(item["unit_margin"]) for item in sig_items)

    net_dv = target_dv + affected_dv
    net_dr = target_dr + affected_dr
    net_dm = target_dm + affected_dm

    if net_dm > 0.0:
        verdict = "VALEU_A_PENA"
    elif net_dv > 0.0:
        verdict = "ILUSAO_DE_VOLUME"
    else:
        verdict = "PREJUIZO_TOTAL"

    return NetImpactResult(
        target_delta_volume=target_dv,
        affected_delta_volume=affected_dv,
        net_delta_volume=net_dv,
        target_delta_revenue=target_dr,
        affected_delta_revenue=affected_dr,
        net_delta_revenue=net_dr,
        target_delta_margin=target_dm,
        affected_delta_margin=affected_dm,
        net_delta_margin=net_dm,
        commercial_verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Re-exportação do Motor v2 (Relatório Global de Migração e Equilíbrio de Preço)
# ---------------------------------------------------------------------------
from src.modules.analytics.domain.cannibalization_report import (  # noqa: E402, F401
    ALLOWED_MECHANISMS,
    ALLOWED_WINDOW_DAYS,
    DEFAULT_MIN_DROP_PCT,
    DEFAULT_MIN_MIGRATED_CLIENTS,
    DEFAULT_WINDOW_DAYS,
    GAP_REDUCTION_TARGET,
    MAX_CANNIBALIZERS_PER_VICTIM,
    MAX_CANNIBAL_PRICE_HIKE_PCT,
    MAX_SEARCH_LENGTH,
    MECHANISM_DESTROYS_MARGIN,
    MECHANISM_PRESERVES_MARGIN,
    MECHANISM_VALUE_MIGRATION,
    MIN_CONTRIBUTION_MARGIN_PCT,
    MIN_DROP_PCT_LOWER,
    MIN_DROP_PCT_UPPER,
    MIN_MIGRATED_CLIENTS_LOWER,
    MIN_MIGRATED_CLIENTS_UPPER,
    MIN_PRE_REVENUE,
    PRICE_GAP_THRESHOLD_PCT,
    CannibalizationDetailResult,
    CannibalizationReportResult,
    CannibalizationVictimDetailResult,
    CannibalizerEvaluation,
    DirectedMigrationPair,
    MigrationSnapshot,
    PeriodRange,
    PriceEquilibriumResult,
    ReportKpis,
    SkuPeriodTotals,
    VictimEvaluation,
    WindowBoundaries,
    build_cannibalization_report,
    build_cannibalization_sku_detail,
    build_cannibalization_victim_detail,
    build_migration_snapshot,
    calculate_price_equilibrium,
    classify_mechanism,
    compute_directional_migration,
    compute_price_gap_pct,
    compute_window_boundaries,
    resolve_cost_and_margin,
    resolve_reference_price,
)
