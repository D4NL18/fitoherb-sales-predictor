"""
Motor de Domínio Matemático de Churn de Clientes (P-117 a P-127; ADR-006).

Regra pura sem I/O, sem conexão com banco de dados e sem dependência de frameworks web.
Combina recência temporal individual (gap típico) e faturamento médio mensal líquido de devoluções
em um Score de Prioridade de Retenção unificado (em R$).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import statistics
from typing import Dict, List, Optional, Sequence, Tuple

# Constantes do Domínio (proibição de números mágicos)
SALE_OPERATION = "VENDA"
RETURN_OPERATION_PATTERN = "DEVOLU%"
CHURN_BASE_DAYS = 60
GAP_MULTIPLIER = 1.5
MIN_ORDERS_FOR_CADENCE = 3
FATOR_TEMPO_MAX = 2.0
STATUS_ALERT_THRESHOLD = 0.5
STATUS_RISK_THRESHOLD = 1.0
DIAS_INATIVO_ANTIGO = 180
REVENUE_WINDOW_MONTHS = 12
MIN_ACTIVE_MONTHS = 3
LOST_PRODUCTS_LIMIT = 5
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


@dataclass(frozen=True)
class MonthlyRevenuePoint:
    """Ponto mensal de faturamento líquido de devoluções."""
    year: int
    month: int
    net_revenue: float
    order_count: int = 1


@dataclass(frozen=True)
class CustomerOrderHistory:
    """Histórico de pedidos de VENDA de um cliente."""
    customer_code: int
    order_dates: Tuple[date, ...]


@dataclass(frozen=True)
class ChurnCustomerSummary:
    """Resumo consolidado do status e métricas de churn de um cliente."""
    customer_code: int
    status: str
    dias_sem_comprar: int
    gap_tipico: Optional[float]
    dias_referencia: int
    fator_tempo: float
    faturamento_medio_mensal: float
    score_prioridade: float
    historico_curto: bool
    customer_name: str = ""
    seller_name: str = ""
    city: str = ""
    data_ultimo_pedido: Optional[date] = None
    variacao_trimestral_pct: Optional[float] = None
    historico_mensal: Tuple[MonthlyRevenuePoint, ...] = ()
    produtos_perdidos: Tuple[dict, ...] = ()


@dataclass(frozen=True)
class BacktestResult:
    """Resultado do backtest quantitativo comparativo."""
    revenue_score_priority: float
    revenue_simple_days: float
    is_superior: bool


def calculate_typical_gap(order_dates: Sequence[date]) -> Optional[float]:
    """
    P-119: Calcula a mediana dos intervalos em dias entre pedidos de VENDA consecutivos.
    Exige no mínimo MIN_ORDERS_FOR_CADENCE (3) pedidos.
    """
    if len(order_dates) < MIN_ORDERS_FOR_CADENCE:
        return None
    sorted_dates = sorted(order_dates)
    intervals = [
        (sorted_dates[i] - sorted_dates[i - 1]).days
        for i in range(1, len(sorted_dates))
    ]
    if not intervals:
        return None
    return float(statistics.median(intervals))


def classify_churn_status(fator_tempo: float, dias_sem_comprar: int) -> str:
    """
    P-124, P-125: Classifica o status do cliente com base no fator de urgência e recência.
    """
    if dias_sem_comprar > DIAS_INATIVO_ANTIGO:
        return "INATIVO_RECUPERACAO"
    if fator_tempo >= STATUS_RISK_THRESHOLD:
        return "EM_RISCO"
    if fator_tempo >= STATUS_ALERT_THRESHOLD:
        return "ALERTA"
    return "SAUDAVEL"


def calculate_churn_metrics(
    customer_code: int,
    order_dates: Sequence[date],
    revenue_history: Sequence[MonthlyRevenuePoint],
    reference_date: date,
    customer_name: str = "",
    seller_name: str = "",
    city: str = "",
) -> ChurnCustomerSummary:
    """
    P-117 a P-125: Calcula todas as métricas determinísticas de churn para um cliente.
    """
    sorted_orders = sorted(order_dates)
    if not sorted_orders:
        return ChurnCustomerSummary(
            customer_code=customer_code,
            status="INATIVO_RECUPERACAO",
            dias_sem_comprar=999,
            gap_tipico=None,
            dias_referencia=CHURN_BASE_DAYS,
            fator_tempo=FATOR_TEMPO_MAX,
            faturamento_medio_mensal=0.0,
            score_prioridade=0.0,
            historico_curto=True,
            customer_name=customer_name,
            seller_name=seller_name,
            city=city,
            data_ultimo_pedido=None,
        )

    last_order_date = sorted_orders[-1]
    dias_sem_comprar = max(0, (reference_date - last_order_date).days)

    # P-119: Intervalo típico e dias de referência
    gap_tipico = calculate_typical_gap(sorted_orders)
    if gap_tipico is not None:
        dias_referencia = max(CHURN_BASE_DAYS, int(round(GAP_MULTIPLIER * gap_tipico)))
    else:
        dias_referencia = CHURN_BASE_DAYS

    # P-120: Fator de urgência temporal com saturação
    fator_tempo_raw = dias_sem_comprar / dias_referencia if dias_referencia > 0 else 0.0
    fator_tempo = min(fator_tempo_raw, FATOR_TEMPO_MAX)

    # P-121, P-122: Faturamento médio mensal líquido de devoluções
    historico_curto = len(sorted_orders) < MIN_ORDERS_FOR_CADENCE
    net_revenue_sum = sum(p.net_revenue for p in revenue_history)
    net_revenue_sum = max(0.0, net_revenue_sum)

    # Cálculo dos meses ativos (divisor entre MIN_ACTIVE_MONTHS e REVENUE_WINDOW_MONTHS)
    first_order_date = sorted_orders[0]
    total_active_months = max(1, (reference_date.year - first_order_date.year) * 12 + (reference_date.month - first_order_date.month))
    divisor_meses = max(MIN_ACTIVE_MONTHS, min(total_active_months, REVENUE_WINDOW_MONTHS))

    faturamento_medio_mensal = round(net_revenue_sum / divisor_meses, 2)

    # P-123: Score de Prioridade em R$
    score_prioridade = round(faturamento_medio_mensal * fator_tempo, 2)

    # P-124, P-125: Status operacional
    status = classify_churn_status(fator_tempo, dias_sem_comprar)

    # Variação trimestral recente (P-126.2)
    variacao_trimestral_pct = _calculate_quarterly_variation(revenue_history)

    return ChurnCustomerSummary(
        customer_code=customer_code,
        status=status,
        dias_sem_comprar=dias_sem_comprar,
        gap_tipico=gap_tipico,
        dias_referencia=dias_referencia,
        fator_tempo=round(fator_tempo, 4),
        faturamento_medio_mensal=faturamento_medio_mensal,
        score_prioridade=score_prioridade,
        historico_curto=historico_curto,
        customer_name=customer_name,
        seller_name=seller_name,
        city=city,
        data_ultimo_pedido=last_order_date,
        variacao_trimestral_pct=variacao_trimestral_pct,
        historico_mensal=tuple(revenue_history),
    )


def _calculate_quarterly_variation(revenue_history: Sequence[MonthlyRevenuePoint]) -> Optional[float]:
    """P-126.2: Variação percentual entre os últimos 3 meses e os 3 meses imediatamente anteriores."""
    if len(revenue_history) < 6:
        return None
    sorted_history = sorted(revenue_history, key=lambda p: (p.year, p.month))
    last_3 = sum(p.net_revenue for p in sorted_history[-3:])
    prev_3 = sum(p.net_revenue for p in sorted_history[-6:-3])
    if prev_3 <= 0:
        return None
    return round(((last_3 - prev_3) / prev_3) * 100.0, 1)


def evaluate_lost_products(
    purchased_skus: Sequence[dict],
    reference_date: date,
    cutoff_days: int = 60,
    limit: int = LOST_PRODUCTS_LIMIT,
) -> List[dict]:
    """
    P-126.3: Identifica os principais SKUs adquiridos no passado que deixaram de ser comprados
    nos últimos cutoff_days (padrão 60 dias).
    """
    lost = []
    cutoff_limit = reference_date - timedelta(days=cutoff_days)
    for p in purchased_skus:
        last_date = p.get("last_date")
        if isinstance(last_date, str):
            last_date = date.fromisoformat(last_date)
        if last_date and last_date < cutoff_limit:
            lost.append({
                "sku": p["sku"],
                "descricao": p.get("descricao", ""),
                "fornecedor": p.get("fornecedor", ""),
                "faturamentoHistorico": round(float(p.get("revenue", 0.0)), 2),
                "dataUltimaCompra": last_date.isoformat(),
            })
    lost.sort(key=lambda x: x["faturamentoHistorico"], reverse=True)
    return lost[:limit]


def rank_churn_customers(customers: Sequence[ChurnCustomerSummary]) -> List[ChurnCustomerSummary]:
    """P-123.2: Ordena a lista de clientes por score de prioridade decrescente."""
    return sorted(customers, key=lambda c: c.score_prioridade, reverse=True)


def run_churn_backtest(customers: Sequence[ChurnCustomerSummary], top_n: int = 100) -> BacktestResult:
    """
    P-127: Validação por backtest quantitativo:
    Compara a receita total capturada no topo do ranking por score vs ordenação simples por dias.
    """
    by_score = rank_churn_customers(customers)[:top_n]
    by_days = sorted(customers, key=lambda c: c.dias_sem_comprar, reverse=True)[:top_n]

    rev_score = sum(c.faturamento_medio_mensal for c in by_score)
    rev_days = sum(c.faturamento_medio_mensal for c in by_days)

    return BacktestResult(
        revenue_score_priority=rev_score,
        revenue_simple_days=rev_days,
        is_superior=rev_score >= rev_days,
    )
