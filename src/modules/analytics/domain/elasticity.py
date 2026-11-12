"""
Módulo de Domínio Puro de Elasticidade-Preço e Simulação Comercial (Fase F5).
Regras: P-095 a P-101; ADR-004 DA-01, DA-03 a DA-06.

Isolamento estrito: funções puras em Python/NumPy/Pandas sem dependência de I/O,
banco de dados ou frameworks web. Todos os parâmetros numéricos são constantes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Constantes do Domínio (ADR-004 e P-095..P-101)
DEFAULT_ELASTICITY: float = -1.2
HALF_LIFE_DAYS: float = 100.0
MIN_OBS_PRODUCT: int = 5
MIN_PRICE_DISPERSION_STD: float = 1e-4
K_SHRINKAGE: float = 10.0
MIN_PLAUSIBLE_BETA: float = -6.0
MAX_PLAUSIBLE_BETA: float = -0.05
CONFIDENCE_HIGH_R2: float = 0.50
CONFIDENCE_HIGH_MIN_OBS: int = 12
CONFIDENCE_MEDIUM_R2: float = 0.20
CONFIDENCE_MEDIUM_MIN_OBS: int = 6
INELASTIC_THRESHOLD: float = -1.0
MIN_SIMULATION_PRICE_CHANGE: float = -50.0
MAX_SIMULATION_PRICE_CHANGE: float = 100.0


@dataclass(frozen=True)
class ProductElasticityResult:
    """Resultado da estimação econométrica da elasticidade do produto (P-096, P-099)."""
    coefficient: float
    classification: str
    r_squared: float
    standard_error: float
    confidence_interval: Tuple[float, float]
    confidence_level: str
    is_reliable: bool
    observations_count: int
    fallback_applied: bool
    insight_message: str


@dataclass(frozen=True)
class CustomerElasticityResult:
    """Resultado da suavização hierárquica (shrinkage) de elasticidade do cliente (P-097)."""
    customer_code: int
    orders_count: int
    total_units: float
    empirical_elasticity: float
    shrinkage_elasticity: float
    classification: str
    shrinkage_weight: float


@dataclass(frozen=True)
class SimulationImpactResult:
    """Resultado do simulador de variação de preço em volume, receita e margem (P-101)."""
    sku: int
    customer_code: Optional[int]
    applied_elasticity: float
    price_change_pct: float
    current_price: float
    projected_price: float
    current_volume: float
    projected_volume: float
    volume_change_pct: float
    current_revenue: float
    projected_revenue: float
    revenue_change_pct: float
    revenue_change_abs: float
    current_margin: float
    projected_margin: float
    margin_change_pct: float
    margin_change_abs: float
    recommendation: str


def calculate_decay_weights(
    dates: Sequence[Union[date, datetime, pd.Timestamp]],
    half_life_days: float = HALF_LIFE_DAYS,
    reference_date: Optional[Union[date, datetime, pd.Timestamp]] = None,
) -> np.ndarray:
    """Calcula pesos amostrais com decaimento exponencial temporal (ADR-004 DA-03)."""
    date_series = pd.to_datetime(pd.Series(dates))
    if date_series.empty:
        return np.array([], dtype=float)

    ref_dt = pd.to_datetime(reference_date) if reference_date else date_series.max()
    diff_days = (ref_dt - date_series).dt.total_seconds() / 86400.0
    diff_days = np.maximum(diff_days.values, 0.0)

    return 2.0 ** (-diff_days / half_life_days)


def prepare_price_points(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega vendas e abate devoluções por ano e mês (P-095).
    Descarta meses com quantidade líquida <= 0 para viabilizar ln(Q).
    """
    if df_raw.empty:
        return pd.DataFrame(columns=["ano", "mes", "preco_medio", "qtd_liquida", "valor_liquido"])

    df = df_raw.copy()
    # Normalizar nomes de colunas
    col_map = {
        "Ano": "ano", "Mes": "mes", "Operacao": "operacao", "Operação": "operacao",
        "Qtd Venda": "qtd", "Valor Venda": "valor",
    }
    df = df.rename(columns=col_map)

    # Identificar devoluções e garantir sinal correto
    is_return = df["operacao"].astype(str).str.upper().str.startswith("DEVOLU")
    # Na base ERP, devoluções já vêm negativas; se porventura vierem positivas, invertemos o sinal
    df["qtd_adj"] = np.where(is_return, -df["qtd"].abs(), df["qtd"].abs())
    df["valor_adj"] = np.where(is_return, -df["valor"].abs(), df["valor"].abs())

    # Agrupar por ano e mês
    group_cols = ["ano", "mes"]
    if "data" in df.columns:
        group_cols.append("data")

    grouped = df.groupby(["ano", "mes"], as_index=False).agg(
        qtd_liquida=("qtd_adj", "sum"),
        valor_liquido=("valor_adj", "sum"),
    )

    # Filtrar apenas períodos com quantidade líquida positiva (P-095)
    valid = grouped[grouped["qtd_liquida"] > 0].copy()
    valid["preco_medio"] = valid["valor_liquido"] / valid["qtd_liquida"]

    # Criar coluna de data média representativa se não existir
    if "data" not in valid.columns:
        valid["data"] = pd.to_datetime(
            valid["ano"].astype(str) + "-" + valid["mes"].astype(str) + "-15"
        )

    return valid.sort_values(by=["ano", "mes"]).reset_index(drop=True)


def estimate_product_elasticity(
    df_points: pd.DataFrame,
    default_elasticity: float = DEFAULT_ELASTICITY,
    min_obs: int = MIN_OBS_PRODUCT,
) -> ProductElasticityResult:
    """
    Estima a elasticidade-preço do produto via regressão log-log ponderada (P-096, P-098, P-099).
    """
    n_obs = len(df_points)

    def _fallback(reason: str, obs: int = n_obs) -> ProductElasticityResult:
        cls = "INELASTICO" if default_elasticity >= INELASTIC_THRESHOLD else "ELASTICO"
        ci = (default_elasticity - 0.5, default_elasticity + 0.5)
        return ProductElasticityResult(
            coefficient=default_elasticity,
            classification=cls,
            r_squared=0.0,
            standard_error=0.0,
            confidence_interval=ci,
            confidence_level="BAIXA",
            is_reliable=False,
            observations_count=obs,
            fallback_applied=True,
            insight_message=f"Estimador padrão aplicado ({default_elasticity:.1f}): {reason}.",
        )

    if n_obs < min_obs:
        return _fallback(f"histórico de vendas insuficiente ({n_obs} meses, mínimo {min_obs})")

    # Extrair colunas
    price_col = "preco_medio" if "preco_medio" in df_points.columns else "preco"
    qty_col = "qtd_liquida" if "qtd_liquida" in df_points.columns else "qtd"

    prices = pd.to_numeric(df_points[price_col], errors="coerce").fillna(0.0).values
    quantities = pd.to_numeric(df_points[qty_col], errors="coerce").fillna(0.0).values

    valid_mask = (prices > 0) & (quantities > 0)
    valid_count = int(np.sum(valid_mask))
    if valid_count < min_obs:
        return _fallback(f"poucos períodos com volume líquido positivo ({valid_count})", valid_count)

    valid_prices = prices[valid_mask]
    valid_qtys = quantities[valid_mask]

    log_p = np.log(valid_prices)
    log_q = np.log(valid_qtys)

    # Dispersão mínima de preços (P-096)
    if float(np.std(log_p)) < MIN_PRICE_DISPERSION_STD:
        return _fallback("preço praticado constante ao longo do histórico (sem dispersão para regressão)", valid_count)

    # Pesos temporais
    if "data" in df_points.columns:
        dates = df_points.loc[valid_mask, "data"]
        weights = calculate_decay_weights(dates)
    else:
        weights = np.ones(valid_count, dtype=float)

    # Regressão linear ponderada: ln(Q) = alpha + beta * ln(P)
    reg = LinearRegression(fit_intercept=True)
    reg.fit(log_p.reshape(-1, 1), log_q, sample_weight=weights)

    estimated_beta = float(reg.coef_[0])

    # Rejeição de betas anômalos (P-098)
    if estimated_beta >= MAX_PLAUSIBLE_BETA or estimated_beta < MIN_PLAUSIBLE_BETA:
        return _fallback(
            f"elasticidade estimada fora do intervalo plausível ({estimated_beta:.2f})",
            valid_count,
        )

    # Cálculo do R² ponderado e Erro Padrão de Beta (P-099)
    y_pred = reg.predict(log_p.reshape(-1, 1))
    residuals = log_q - y_pred
    weighted_rss = float(np.sum(weights * (residuals ** 2)))

    w_mean_y = float(np.average(log_q, weights=weights))
    weighted_tss = float(np.sum(weights * ((log_q - w_mean_y) ** 2)))
    r_squared = max(0.0, min(1.0, 1.0 - (weighted_rss / weighted_tss))) if weighted_tss > 0 else 0.0

    w_mean_x = float(np.average(log_p, weights=weights))
    sum_w_diff_x2 = float(np.sum(weights * ((log_p - w_mean_x) ** 2)))
    dof = max(1, valid_count - 2)
    s2 = weighted_rss / dof
    standard_error = math.sqrt(s2 / sum_w_diff_x2) if sum_w_diff_x2 > 0 else 0.0

    margin_ci = 1.96 * standard_error
    confidence_interval = (
        round(estimated_beta - margin_ci, 2),
        round(estimated_beta + margin_ci, 2),
    )

    # Nível de confiança estatística (P-099)
    if r_squared >= CONFIDENCE_HIGH_R2 and valid_count >= CONFIDENCE_HIGH_MIN_OBS:
        confidence_level = "ALTA"
        is_reliable = True
    elif r_squared >= CONFIDENCE_MEDIUM_R2 and valid_count >= CONFIDENCE_MEDIUM_MIN_OBS:
        confidence_level = "MEDIA"
        is_reliable = True
    else:
        confidence_level = "BAIXA"
        is_reliable = False

    classification = "INELASTICO" if estimated_beta >= INELASTIC_THRESHOLD else "ELASTICO"

    if classification == "INELASTICO":
        insight = "Demanda inelástica: sensibilidade baixa a preço; potencial para ganho de margem com reajuste moderado."
    else:
        insight = "Demanda elástica: sensibilidade alta a preço; elevações tendem a reduzir o volume comercializado."

    return ProductElasticityResult(
        coefficient=round(estimated_beta, 2),
        classification=classification,
        r_squared=round(r_squared, 4),
        standard_error=round(standard_error, 4),
        confidence_interval=confidence_interval,
        confidence_level=confidence_level,
        is_reliable=is_reliable,
        observations_count=valid_count,
        fallback_applied=False,
        insight_message=insight,
    )


def estimate_customer_elasticity(
    product_elasticity: float,
    customer_empirical: float,
    orders_count: int,
    k_shrinkage: float = K_SHRINKAGE,
    customer_code: int = 0,
    total_units: float = 0.0,
) -> CustomerElasticityResult:
    """
    Aplica suavização hierárquica (shrinkage bayesiano) para o par produto x cliente (P-097).
    w = orders_count / (orders_count + k_shrinkage).
    """
    count = max(0, orders_count)
    weight = count / (count + k_shrinkage)

    # Se a elasticidade empírica do cliente for anômala, substitui pela do produto antes do shrinkage
    clean_empirical = customer_empirical
    if clean_empirical >= MAX_PLAUSIBLE_BETA or clean_empirical < MIN_PLAUSIBLE_BETA:
        clean_empirical = product_elasticity

    shrinkage_beta = (weight * clean_empirical) + ((1.0 - weight) * product_elasticity)
    classification = "INELASTICO" if shrinkage_beta >= INELASTIC_THRESHOLD else "ELASTICO"

    return CustomerElasticityResult(
        customer_code=customer_code,
        orders_count=count,
        total_units=round(total_units, 1),
        empirical_elasticity=round(clean_empirical, 2),
        shrinkage_elasticity=round(shrinkage_beta, 2),
        classification=classification,
        shrinkage_weight=round(weight, 4),
    )


def simulate_price_impact(
    elasticity: float,
    current_price: float,
    cost_price: float,
    current_volume: float,
    price_change_pct: float,
    sku: int = 0,
    customer_code: Optional[int] = None,
) -> SimulationImpactResult:
    """
    Calcula o impacto projetado de uma variação percentual de preço em volume, receita e margem (P-101).
    """
    # Validação do intervalo permitido [-50.0%, +100.0%]
    if price_change_pct < MIN_SIMULATION_PRICE_CHANGE or price_change_pct > MAX_SIMULATION_PRICE_CHANGE:
        raise ValueError(f"priceChangePct fora da faixa [{MIN_SIMULATION_PRICE_CHANGE}, {MAX_SIMULATION_PRICE_CHANGE}]")

    price_factor = 1.0 + (price_change_pct / 100.0)
    projected_price = round(current_price * price_factor, 2)

    # Variação projetada de volume: delta_volume% = beta * delta_preco%
    volume_change_pct = round(elasticity * price_change_pct, 2)
    volume_factor = max(0.0, 1.0 + (volume_change_pct / 100.0))
    projected_volume = round(current_volume * volume_factor, 2)

    current_revenue = round(current_price * current_volume, 2)
    projected_revenue = round(projected_price * projected_volume, 2)
    revenue_change_abs = round(projected_revenue - current_revenue, 2)
    revenue_change_pct = (
        round((revenue_change_abs / current_revenue) * 100.0, 2)
        if current_revenue > 0
        else 0.0
    )

    current_unit_margin = current_price - cost_price
    projected_unit_margin = projected_price - cost_price

    current_margin = round(current_unit_margin * current_volume, 2)
    projected_margin = round(projected_unit_margin * projected_volume, 2)
    margin_change_abs = round(projected_margin - current_margin, 2)
    margin_change_pct = (
        round((margin_change_abs / current_margin) * 100.0, 2)
        if abs(current_margin) > 0
        else 0.0
    )

    if margin_change_abs > 0:
        recommendation = "Reajuste viável com expansão de margem financeira líquida."
    elif margin_change_abs == 0:
        recommendation = "Cenário neutro com estabilidade de margem financeira."
    else:
        recommendation = "Atenção: queda de volume estimada supera o ganho de preço, reduzindo a margem total."

    return SimulationImpactResult(
        sku=sku,
        customer_code=customer_code,
        applied_elasticity=round(elasticity, 2),
        price_change_pct=round(price_change_pct, 2),
        current_price=round(current_price, 2),
        projected_price=projected_price,
        current_volume=round(current_volume, 2),
        projected_volume=projected_volume,
        volume_change_pct=volume_change_pct,
        current_revenue=current_revenue,
        projected_revenue=projected_revenue,
        revenue_change_pct=revenue_change_pct,
        revenue_change_abs=revenue_change_abs,
        current_margin=current_margin,
        projected_margin=projected_margin,
        margin_change_pct=margin_change_pct,
        margin_change_abs=margin_change_abs,
        recommendation=recommendation,
    )
