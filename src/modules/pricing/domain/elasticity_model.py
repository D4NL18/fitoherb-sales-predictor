"""
Módulo de Modelagem Preditiva de Demanda e Elasticidade-Preço (US-04, P-007).
Implementa decaimento temporal exponencial e estimação econométrica Log-Log.
"""
import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


def calculate_temporal_decay_weights(
    dates: pd.Series,
    half_life_days: float = 100.0,
    reference_date: Optional[Union[pd.Timestamp, str]] = None
) -> np.ndarray:
    """
    Regra P-007: Calcula os pesos amostrais com decaimento temporal exponencial:
    sample_weight = 2 ** (-dias_ate_presente / meia_vida).
    Vendas recentes têm peso próximo de 1.0; vendas antigas recebem peso residual.
    """
    if pd.api.types.is_datetime64_any_dtype(dates):
        date_series = dates
    else:
        date_series = pd.to_datetime(dates, errors="coerce")

    if reference_date is None:
        ref_dt = date_series.max()
    else:
        ref_dt = pd.to_datetime(reference_date)

    diff_days = (ref_dt - date_series).dt.total_seconds() / 86400.0
    # Evitar dias negativos caso haja datas futuras/inconsistentes
    diff_days = np.maximum(diff_days.values, 0.0)

    weights = 2.0 ** (-diff_days / half_life_days)
    return weights


def estimate_log_log_elasticity(
    df_product: pd.DataFrame,
    default_elasticity: float = -1.2,
    min_obs: int = 5
) -> float:
    """
    Estima a elasticidade-preço da demanda pela especificação econométrica Log-Log:
    ln(Q) = alpha + beta * ln(P) + erro.
    O coeficiente beta representa diretamente a elasticidade constante.
    """
    if len(df_product) < min_obs:
        return default_elasticity

    # Determinar colunas de preço e quantidade
    price_col = "preco_praticado" if "preco_praticado" in df_product.columns else "Preco Praticado"
    qty_col = "Qtd Venda" if "Qtd Venda" in df_product.columns else "qtd"

    if price_col not in df_product.columns or qty_col not in df_product.columns:
        return default_elasticity

    prices = pd.to_numeric(df_product[price_col], errors="coerce").fillna(0.0)
    quantities = pd.to_numeric(df_product[qty_col], errors="coerce").fillna(0.0)

    valid_mask = (prices > 0) & (quantities > 0)
    if valid_mask.sum() < min_obs:
        return default_elasticity

    log_p = np.log(prices[valid_mask].values).reshape(-1, 1)
    log_q = np.log(quantities[valid_mask].values)

    # Verificar se há dispersão/variação suficiente de preço histórico
    if np.std(log_p) < 1e-4:
        return default_elasticity

    # Ponderação amostral
    if "sample_weight" in df_product.columns:
        weights = df_product.loc[valid_mask, "sample_weight"].values
    else:
        weights = np.ones(len(log_q))

    # Regressão linear ponderada
    reg = LinearRegression(fit_intercept=True)
    reg.fit(log_p, log_q, sample_weight=weights)

    estimated_beta = float(reg.coef_[0])

    # Validação econômica defensiva: Elasticidade própria de demanda deve ser negativa.
    # Se beta >= 0 (efeito Giffen espúrio por inflação/demanda agregada), calibrar para baseline B2B.
    if estimated_beta >= -0.05 or estimated_beta < -5.0:
        logger.debug(f"Elasticidade estimada anômala ({estimated_beta:.2f}); aplicando valor canônico ({default_elasticity:.2f}).")
        return default_elasticity

    return estimated_beta


def build_elasticity_matrix(
    skus: List[int],
    sales_df: pd.DataFrame,
    catalog_prices: Dict[int, float],
    half_life_days: float = 100.0,
    reference_date: Optional[pd.Timestamp] = None
) -> Dict[Tuple[int, int], float]:
    """
    Constrói o dicionário de elasticidades próprias e cruzadas para o conjunto de SKUs da cesta.
    Otimizado para filtrar apenas as vendas dos SKUs alvo antes de computar pesos temporais,
    evitando a cópia e varredura de 685.000 linhas da base completa.
    """
    elasticities: Dict[Tuple[int, int], float] = {}

    target_sales = sales_df[sales_df["Cod Produto"].isin(skus)].copy()
    if target_sales.empty:
        return {(s, s): -1.2 for s in skus}

    # Preparar pesos temporais apenas sobre os registros dos SKUs avaliados
    if "Data" in target_sales.columns and not target_sales["Data"].isna().all():
        target_sales["sample_weight"] = calculate_temporal_decay_weights(
            target_sales["Data"], half_life_days=half_life_days, reference_date=reference_date
        )
    else:
        target_sales["sample_weight"] = 1.0

    # Agrupar por Cod Produto para evitar dezenas de varreduras lineares repetidas
    sales_by_sku = dict(tuple(target_sales.groupby("Cod Produto")))

    for sku in skus:
        sku_sales = sales_by_sku.get(sku)
        if sku_sales is not None and not sku_sales.empty:
            beta_ii = estimate_log_log_elasticity(sku_sales)
        else:
            beta_ii = -1.2
        elasticities[(sku, sku)] = beta_ii

    # Elasticidades cruzadas entre âncora e compensador:
    # Em bens complementares, uma redução de preço no âncora eleva a demanda do compensador.
    for i in skus:
        for j in skus:
            if i != j and (i, j) not in elasticities:
                own_i = elasticities.get((i, i), -1.2)
                elasticities[(i, j)] = float(np.clip(own_i * 0.15, -0.6, -0.05))

    return elasticities
