"""
Motor Analítico de Estoque e Previsão de Compras pela Política Mín/Máx (Inventory Engine).

Implementa as regras de negócio:
- P-041: Velocidade de vendas (VMD) em precisão integral na janela temporal.
- P-047.1: Filtro opcional por fornecedor com Curva ABC global preservada.
- P-053: Cálculo de Estoque Mínimo e Estoque Máximo por dias de cobertura (sem ROP/ES/z-score).
- P-054: Gatilho de compra e Quantidade Sugerida até o máximo (sem travas físicas ou orçamentárias).
- P-055: Cobertura em dias, precedência de status operacional, Capital Imobilizado, KPIs e ordenação.
- P-056: Revogação integral de ROP, estoque de segurança, estoque ideal, trava P-044.4 e teto P-046.3.
"""
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd

from src.modules.inventory.domain.replenishment_policy import (
    ReplenishmentPolicy,
    StockLevels,
    calculate_stock_levels,
    ceil_units,
)

DEFAULT_HISTORY_WINDOW_DAYS = 60  # P-041 / P-053.1: janela padrão de vendas
MIN_WINDOW_DAYS = 1  # Evita divisão por zero na agregação de velocidade
STD_DEMAND_DECIMALS = 4  # Mantido internamente por compatibilidade com a query SQL (DA-04)
TOTALS_DECIMALS = 2  # Arredondamento de volume e receita agregados na janela

COST_FALLBACK_PRICE_RATIO = 0.60  # P-054.5: custo estimado = 60% do preço de venda quando custo <= 0
MONEY_DECIMALS = 2  # Valores monetários em R$ (custo, preço, investimento, capital imobilizado)
VMD_DISPLAY_DECIMALS = 2  # Seção 1.3 do contrato: VMD arredondada a 2 casas apenas na serialização
STOCK_DISPLAY_DECIMALS = 1  # Seção 1.3 do contrato: estoque físico exibido com 1 casa decimal
COVERAGE_DAYS_DECIMALS = 1  # P-055.1: dias de cobertura arredondados a 1 casa decimal
NO_SALES_COVERAGE_DAYS = 999.0  # P-055.1: sentinela de cobertura infinita ("∞") quando VMD=0 e estoque>0
PERCENT_MULTIPLIER = 100.0  # Conversão de razão para percentual (0-100)
PERCENT_DECIMALS = 1  # Casa decimal do percentual de itens na Curva A

ZERO_FLOAT = 0.0
ZERO_INT = 0
MIN_SAMPLE_DAYS_FOR_VARIANCE = 2

ABC_CLASS_A_MAX_PCT = 80.0  # Curva ABC: classe A até 80% da receita acumulada
ABC_CLASS_B_MAX_PCT = 95.0  # Curva ABC: classe B até 95% da receita acumulada
DEFAULT_ABC_CLASS = "C"  # Curva ABC: restante da receita e SKUs sem venda na janela

DEFAULT_SUPPLIER_NAME = "OUTROS"
DEFAULT_PRODUCT_TYPE = "GERAL"
ALL_SUPPLIERS_TOKENS = frozenset({"TODOS", "ALL", ""})  # P-047.1: valores que desativam o filtro

VELOCITY_COLUMNS = ("vmd", "std_demand", "total_sold_qty", "total_revenue")
CANONICAL_CATALOG_COLUMNS = (
    "codigo",
    "descricao",
    "ean",
    "fornecedor",
    "tipo",
    "estoque",
    "custo_unitario",
    "preco_venda",
)

# Começa pelo nome canônico para garantir que normalize_product_catalog seja idempotente (B-04).
PRODUCT_COLUMN_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "codigo": ("codigo", "Codigo", "Código"),
    "descricao": ("descricao", "Descricao", "Descrição"),
    "ean": ("ean", "EAN"),
    "fornecedor": ("fornecedor", "Fornecedor", "Fornec/Marca", "Marca"),
    "tipo": ("tipo", "Tipo", "Linha"),
    "estoque": ("estoque", "Estoque"),
    "custo_unitario": ("custo_unitario", "Pc.Ultimo Custo", "Custo"),
    "preco_venda": ("preco_venda", "Pc.Venda", "Preço"),
}

SALES_COLUMN_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "sku": ("Cod Produto", "Código", "Codigo"),
    "date": ("Data",),
    "qty": ("Qtd Venda", "Quantidade"),
    "revenue": ("Valor Venda", "Valor"),
}


class InventoryStatus(str, Enum):
    """Códigos de status operacional do SKU segundo a Política Mín/Máx (P-055.2)."""

    CRITICAL_STOCKOUT = "CRITICAL_STOCKOUT"
    REORDER_NEEDED = "REORDER_NEEDED"
    HEALTHY = "HEALTHY"
    OVERSTOCK = "OVERSTOCK"


STATUS_LABELS: Mapping[InventoryStatus, str] = {
    InventoryStatus.CRITICAL_STOCKOUT: "Ruptura Iminente",
    InventoryStatus.REORDER_NEEDED: "Abaixo do Mínimo",
    InventoryStatus.HEALTHY: "Estoque Saudável",
    InventoryStatus.OVERSTOCK: "Acima do Máximo",
}

STATUS_SORT_ORDER: Mapping[InventoryStatus, int] = {
    InventoryStatus.CRITICAL_STOCKOUT: 0,
    InventoryStatus.REORDER_NEEDED: 1,
    InventoryStatus.HEALTHY: 2,
    InventoryStatus.OVERSTOCK: 3,
}

ABC_SORT_ORDER: Mapping[str, int] = {"A": 0, "B": 1, "C": 2}
DEFAULT_SORT_RANK = 99


def _resolve_column(df: pd.DataFrame, aliases: Sequence[str]) -> Optional[str]:
    """Retorna o primeiro nome de coluna existente no DataFrame dentre os aliases informados."""
    for candidate in aliases:
        if candidate in df.columns:
            return candidate
    return None


def _normalize_sales_records(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza colunas de vendas brutas e filtra apenas registros válidos de venda positiva."""
    sku_col = _resolve_column(sales_df, SALES_COLUMN_ALIASES["sku"]) or "Cod Produto"
    date_col = _resolve_column(sales_df, SALES_COLUMN_ALIASES["date"]) or "Data"
    qty_col = _resolve_column(sales_df, SALES_COLUMN_ALIASES["qty"]) or "Qtd Venda"
    val_col = _resolve_column(sales_df, SALES_COLUMN_ALIASES["revenue"]) or "Valor Venda"

    normalized = pd.DataFrame(
        {
            "sku": pd.to_numeric(sales_df[sku_col], errors="coerce").fillna(ZERO_INT).astype(np.int64),
            "date": pd.to_datetime(sales_df[date_col], errors="coerce"),
            "qty": pd.to_numeric(sales_df[qty_col], errors="coerce").fillna(ZERO_FLOAT),
            "revenue": pd.to_numeric(sales_df[val_col], errors="coerce").fillna(ZERO_FLOAT),
        }
    )
    valid_mask = (
        (normalized["sku"] > ZERO_INT)
        & normalized["date"].notna()
        & (normalized["qty"] > ZERO_FLOAT)
    )
    return normalized[valid_mask].copy()


def _filter_sales_window(
    valid_sales_df: pd.DataFrame,
    window_days: int,
    reference_date: Optional[Union[pd.Timestamp, str]],
) -> pd.DataFrame:
    """Recorta os registros de vendas dentro da janela recente [ref_dt - window_days, ref_dt]."""
    ref_dt = (
        valid_sales_df["date"].max()
        if reference_date is None
        else pd.to_datetime(reference_date)
    )
    start_dt = ref_dt - pd.Timedelta(days=window_days)
    return valid_sales_df[valid_sales_df["date"] >= start_dt].copy()


def calculate_sales_velocity(
    sales_df: pd.DataFrame,
    window_days: int = DEFAULT_HISTORY_WINDOW_DAYS,
    reference_date: Optional[Union[pd.Timestamp, str]] = None,
) -> pd.DataFrame:
    """Calcula a VMD em precisão integral, volatilidade, volume e receita por SKU na janela.

    Regra: P-041 e P-053.6 (ADR-001, DA-02) — a coluna `vmd` NÃO é arredondada para evitar
    inflar o Estoque Máximo em SKUs de giro baixo (ex.: 1 un em 60 dias). Arredondar só na exibição.

    Args:
        sales_df: DataFrame de vendas brutas do ERP.
        window_days: Dias da janela de vendas recente (padrão 60).
        reference_date: Data final opcional de referência (usa a maior data do dataset se None).

    Returns:
        DataFrame indexado por `sku` com colunas `vmd`, `std_demand`, `total_sold_qty`, `total_revenue`.
    """
    if sales_df.empty:
        return pd.DataFrame(columns=list(VELOCITY_COLUMNS))

    valid_df = _normalize_sales_records(sales_df)
    if valid_df.empty:
        return pd.DataFrame(columns=list(VELOCITY_COLUMNS))

    recent_df = _filter_sales_window(valid_df, window_days, reference_date)
    if recent_df.empty:
        return pd.DataFrame(columns=list(VELOCITY_COLUMNS))

    recent_df["sale_day"] = recent_df["date"].dt.date
    daily_qty = recent_df.groupby(["sku", "sale_day"])["qty"].sum().reset_index()
    stats = daily_qty.groupby("sku")["qty"].agg(
        sum_qty="sum",
        sum_sq=lambda series: np.sum(series ** 2),
    )

    n_days = float(max(MIN_WINDOW_DAYS, window_days))
    vmd_series = stats["sum_qty"] / n_days
    if n_days >= MIN_SAMPLE_DAYS_FOR_VARIANCE:
        variance = ((stats["sum_sq"] - (n_days * (vmd_series ** 2))) / (n_days - 1)).clip(lower=ZERO_FLOAT)
        std_series = np.sqrt(variance)
    else:
        std_series = pd.Series(ZERO_FLOAT, index=stats.index)

    result_df = pd.DataFrame(
        {
            "vmd": vmd_series,
            "std_demand": std_series.round(STD_DEMAND_DECIMALS),
            "total_sold_qty": recent_df.groupby("sku")["qty"].sum().round(TOTALS_DECIMALS),
            "total_revenue": recent_df.groupby("sku")["revenue"].sum().round(TOTALS_DECIMALS),
        },
        index=stats.index,
    )
    result_df.index.name = "sku"
    return result_df


def _extract_numeric_series(df: pd.DataFrame, column_key: str) -> pd.Series:
    """Extrai uma coluna numérica usando os aliases do catálogo, preenchendo ausentes com 0.0."""
    resolved = _resolve_column(df, PRODUCT_COLUMN_ALIASES[column_key])
    if resolved is None:
        return pd.Series(ZERO_FLOAT, index=df.index, dtype=float)
    return pd.to_numeric(df[resolved], errors="coerce").fillna(ZERO_FLOAT).astype(float)


def _fill_text_column(df: pd.DataFrame, column_key: str, default: str) -> pd.Series:
    """Extrai e higieniza uma coluna textual do catálogo, aplicando valor padrão quando vazia."""
    resolved = _resolve_column(df, PRODUCT_COLUMN_ALIASES[column_key])
    if resolved is None:
        return pd.Series(default, index=df.index, dtype=str)
    cleaned = df[resolved].fillna(default).astype(str).str.strip()
    if default:
        return cleaned.replace("", default)
    return cleaned


def _apply_unit_cost_fallback(raw_cost: pd.Series, sale_price: pd.Series) -> pd.Series:
    """Aplica o fallback de 60% sobre o preço de venda quando o último custo é <= 0 (P-054.5)."""
    fallback_cost = (sale_price * COST_FALLBACK_PRICE_RATIO).round(MONEY_DECIMALS)
    resolved_cost = np.where(raw_cost > ZERO_FLOAT, raw_cost, fallback_cost)
    return pd.Series(resolved_cost, index=sale_price.index, dtype=float)


def normalize_product_catalog(products_df: pd.DataFrame) -> pd.DataFrame:
    """Converte o catálogo de produtos para colunas canônicas de domínio de forma idempotente.

    Regra: P-053.9 (estoque negativo do ERP vira 0) e P-054.5 (custo unitário com fallback de 60%).

    Args:
        products_df: DataFrame do catálogo vindo do ERP ou já normalizado.

    Returns:
        DataFrame com colunas canônicas `codigo`, `descricao`, `ean`, `fornecedor`,
        `tipo`, `estoque`, `custo_unitario`, `preco_venda`.
    """
    if products_df.empty:
        return pd.DataFrame(columns=list(CANONICAL_CATALOG_COLUMNS))

    sale_price = _extract_numeric_series(products_df, "preco_venda")
    raw_cost = _extract_numeric_series(products_df, "custo_unitario")

    return pd.DataFrame(
        {
            "codigo": _extract_numeric_series(products_df, "codigo").astype(np.int64),
            "descricao": _fill_text_column(products_df, "descricao", ""),
            "ean": _fill_text_column(products_df, "ean", ""),
            "fornecedor": _fill_text_column(products_df, "fornecedor", DEFAULT_SUPPLIER_NAME).str.upper(),
            "tipo": _fill_text_column(products_df, "tipo", DEFAULT_PRODUCT_TYPE),
            "estoque": _extract_numeric_series(products_df, "estoque").clip(lower=ZERO_FLOAT),
            "custo_unitario": _apply_unit_cost_fallback(raw_cost, sale_price),
            "preco_venda": sale_price,
        },
        index=products_df.index,
    )


def filter_products_by_supplier(
    catalog_df: pd.DataFrame,
    supplier_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Filtra o catálogo normalizado pelo fornecedor quando informado (P-047.1).

    Regra: P-047.1 — `None`, string vazia, `TODOS` e `ALL` preservam todos os produtos;
    a comparação ignora espaços nas pontas e diferenças de maiúsculas/minúsculas.
    """
    if catalog_df.empty or supplier_filter is None:
        return catalog_df.copy()

    normalized_supplier = supplier_filter.strip().upper()
    if normalized_supplier in ALL_SUPPLIERS_TOKENS:
        return catalog_df.copy()

    return catalog_df[catalog_df["fornecedor"] == normalized_supplier].copy()


def prepare_product_catalog(
    products_df: pd.DataFrame,
    supplier_filter: Optional[str] = None,
) -> pd.DataFrame:
    """Normaliza as colunas do catálogo de produtos e aplica o filtro opcional por fornecedor.

    Regra: P-047.1, P-053.9, P-054.5 (ADR-001, DA-10).
    """
    normalized_df = normalize_product_catalog(products_df)
    return filter_products_by_supplier(normalized_df, supplier_filter)


def classify_abc_curve(revenue_by_sku: Mapping[int, float]) -> Dict[int, str]:
    """Classifica cada SKU na Curva ABC global pela participação acumulada na receita total.

    Regra: Curva ABC global (seção 4 das regras de negócio) — A <= 80%, B <= 95%, C restante.
    Calculada antes de qualquer filtro de fornecedor para que a classe do SKU não mude (CA-10).
    """
    if not revenue_by_sku:
        return {}

    total_revenue = sum(revenue_by_sku.values())
    if total_revenue <= ZERO_FLOAT:
        return {int(sku): DEFAULT_ABC_CLASS for sku in revenue_by_sku}

    sorted_items = sorted(revenue_by_sku.items(), key=lambda item: item[1], reverse=True)
    cumulative_revenue = ZERO_FLOAT
    abc_by_sku: Dict[int, str] = {}

    for sku, revenue in sorted_items:
        cumulative_revenue += revenue
        cumulative_pct = (cumulative_revenue / total_revenue) * PERCENT_MULTIPLIER
        if cumulative_pct <= ABC_CLASS_A_MAX_PCT:
            abc_by_sku[int(sku)] = "A"
        elif cumulative_pct <= ABC_CLASS_B_MAX_PCT:
            abc_by_sku[int(sku)] = "B"
        else:
            abc_by_sku[int(sku)] = DEFAULT_ABC_CLASS

    return abc_by_sku


@dataclass(frozen=True)
class SalesLookup:
    """Consulta encapsulada de VMD e Curva ABC por SKU (Lei de Demeter — DA-10)."""

    vmd_by_sku: Mapping[int, float]
    abc_by_sku: Mapping[int, str]

    def vmd_for(self, sku: int) -> float:
        """Retorna a VMD em precisão integral do SKU, ou 0.0 quando sem vendas."""
        return float(self.vmd_by_sku.get(sku, ZERO_FLOAT))

    def abc_class_for(self, sku: int) -> str:
        """Retorna a classe ABC global do SKU, ou 'C' quando sem vendas na janela."""
        return self.abc_by_sku.get(sku, DEFAULT_ABC_CLASS)


def build_sales_lookup(velocity_df: pd.DataFrame) -> SalesLookup:
    """Constrói o objeto SalesLookup com VMD e Curva ABC global a partir do DataFrame de velocidade."""
    if velocity_df is None or velocity_df.empty:
        return SalesLookup(vmd_by_sku={}, abc_by_sku={})

    vmd_by_sku = {int(sku): float(vmd) for sku, vmd in velocity_df["vmd"].to_dict().items()}
    revenue_by_sku = {
        int(sku): float(rev) for sku, rev in velocity_df["total_revenue"].to_dict().items()
    }
    return SalesLookup(
        vmd_by_sku=vmd_by_sku,
        abc_by_sku=classify_abc_curve(revenue_by_sku),
    )


def calculate_coverage_days(current_stock: float, vmd: float) -> float:
    """Calcula quantos dias o estoque físico atual dura no ritmo atual de vendas (VMD).

    Regra: P-055.1 — `estoque / VMD` arredondado a 1 casa quando VMD > 0;
    999.0 (sentinela de "∞") quando VMD <= 0 e estoque > 0; 0.0 quando ambos são 0.
    """
    if vmd <= ZERO_FLOAT:
        return NO_SALES_COVERAGE_DAYS if current_stock > ZERO_FLOAT else ZERO_FLOAT
    return round(current_stock / vmd, COVERAGE_DAYS_DECIMALS)


@dataclass(frozen=True)
class StockPosition:
    """Posição consolidada de estoque, velocidade, cobertura e níveis Mín/Máx de um SKU."""

    current_stock: float
    vmd: float
    coverage_days: float
    levels: StockLevels


def build_stock_position(
    current_stock: float,
    vmd: float,
    policy: ReplenishmentPolicy,
) -> StockPosition:
    """Monta a posição do SKU frente à política Mín/Máx garantindo estoque não-negativo (P-053.9)."""
    sanitized_stock = max(ZERO_FLOAT, float(current_stock))
    return StockPosition(
        current_stock=sanitized_stock,
        vmd=vmd,
        coverage_days=calculate_coverage_days(sanitized_stock, vmd),
        levels=calculate_stock_levels(vmd, policy),
    )


def is_stockout_imminent(position: StockPosition, lead_time_days: int) -> bool:
    """Indica se o estoque atual do produto com venda acabará antes da chegada do pedido.

    Regra: P-055.2 (ordem 1) e CA-P055-03 — compara `coverage_days` (já arredondado a 1 casa,
    como exibido na tela) estritamente menor que `lead_time_days`.
    """
    return position.vmd > ZERO_FLOAT and position.coverage_days < lead_time_days


def is_purchase_triggered(position: StockPosition, lead_time_days: int) -> bool:
    """Verifica se o gatilho de compra da política Mín/Máx foi acionado para o SKU.

    Regra: P-054.1 e P-054.3 — só há compra para produto com venda (VMD > 0) quando o estoque
    atingiu o Estoque Mínimo (limite inclusivo) ou está em Ruptura Iminente.
    """
    if position.vmd <= ZERO_FLOAT:
        return False
    return (
        position.current_stock <= position.levels.minimum
        or is_stockout_imminent(position, lead_time_days)
    )


def calculate_suggested_purchase(position: StockPosition, lead_time_days: int) -> int:
    """Calcula a quantidade inteira sugerida de compra para recompor o estoque até o máximo.

    Regra: P-054.2, P-054.3, P-054.4 e P-056.1 — sem gatilho retorna 0; com gatilho retorna
    `max(0, ceil_units(Estoque Máximo - estoque atual))`, sem trava física nem teto orçamentário.
    """
    if not is_purchase_triggered(position, lead_time_days):
        return ZERO_INT
    return max(ZERO_INT, ceil_units(position.levels.maximum - position.current_stock))


def classify_stock_status(
    position: StockPosition,
    suggested_qty: int,
    lead_time_days: int,
) -> InventoryStatus:
    """Classifica o status operacional do SKU seguindo a precedência estrita de P-055.2.

    Regra: P-055.2 — 1º Ruptura Iminente; 2º Abaixo do Mínimo (exige suggested_qty > 0 para que
    o caso de borda mínimo == máximo com estoque == mínimo caia em Estoque Saudável, CA-P055-08);
    3º Acima do Máximo (estoque > máximo, incluindo VMD=0 com estoque>0); 4º Estoque Saudável.
    """
    if is_stockout_imminent(position, lead_time_days):
        return InventoryStatus.CRITICAL_STOCKOUT

    if (
        position.vmd > ZERO_FLOAT
        and position.current_stock <= position.levels.minimum
        and suggested_qty > ZERO_INT
    ):
        return InventoryStatus.REORDER_NEEDED

    if position.current_stock > position.levels.maximum:
        return InventoryStatus.OVERSTOCK

    return InventoryStatus.HEALTHY


def calculate_overstock_capital(
    position: StockPosition,
    unit_cost: float,
    status: InventoryStatus,
) -> float:
    """Calcula o capital imobilizado sobre as unidades que excedem o Estoque Máximo.

    Regra: P-055.4 — calculado apenas quando o status é OVERSTOCK; para SKU sem venda
    (Estoque Máximo = 0), todo o estoque físico é contabilizado como excedente.
    """
    if status != InventoryStatus.OVERSTOCK:
        return ZERO_FLOAT
    excess_units = max(ZERO_FLOAT, position.current_stock - position.levels.maximum)
    return excess_units * unit_cost


@dataclass(frozen=True)
class ProductEvaluation:
    """Resultado tipado da avaliação de um SKU pela Política Mín/Máx (DA-10)."""

    codigo: int
    descricao: str
    ean: str
    fornecedor: str
    tipo: str
    estoque_atual: float
    vmd: float
    dias_cobertura: float
    lead_time: int
    estoque_minimo: int
    estoque_maximo: int
    qtd_sugerida_compra: int
    custo_unitario: float
    preco_venda: float
    investimento_total_item: float
    status: InventoryStatus
    status_label: str
    curva_abc: str
    overstock_capital: float

    def to_response_item(self) -> Dict[str, Any]:
        """Serializa o item em camelCase conforme a seção 5.2 do contrato 2.0.0."""
        return {
            "codigo": self.codigo,
            "descricao": self.descricao,
            "ean": self.ean,
            "fornecedor": self.fornecedor,
            "tipo": self.tipo,
            "estoqueAtual": round(self.estoque_atual, STOCK_DISPLAY_DECIMALS),
            "vmd": round(self.vmd, VMD_DISPLAY_DECIMALS),
            "diasCobertura": self.dias_cobertura,
            "leadTime": self.lead_time,
            "estoqueMinimo": self.estoque_minimo,
            "estoqueMaximo": self.estoque_maximo,
            "qtdSugeridaCompra": self.qtd_sugerida_compra,
            "custoUnitario": round(self.custo_unitario, MONEY_DECIMALS),
            "precoVenda": round(self.preco_venda, MONEY_DECIMALS),
            "investimentoTotalItem": self.investimento_total_item,
            "status": self.status.value,
            "statusLabel": self.status_label,
            "curvaAbc": self.curva_abc,
        }


def evaluate_product(
    product_row: Any,
    sales_lookup: SalesLookup,
    policy: ReplenishmentPolicy,
) -> ProductEvaluation:
    """Avalia um único produto do catálogo normalizado contra a política Mín/Máx.

    Regra: P-053, P-054.5, P-055 (ADR-001, DA-10).
    """
    sku = int(product_row.codigo)
    current_stock = float(product_row.estoque)
    unit_cost = float(product_row.custo_unitario)
    sale_price = float(product_row.preco_venda)
    vmd = sales_lookup.vmd_for(sku)

    position = build_stock_position(current_stock, vmd, policy)
    suggested_qty = calculate_suggested_purchase(position, policy.lead_time_days)
    status = classify_stock_status(position, suggested_qty, policy.lead_time_days)
    investment = round(suggested_qty * unit_cost, MONEY_DECIMALS)
    overstock_capital = calculate_overstock_capital(position, unit_cost, status)

    return ProductEvaluation(
        codigo=sku,
        descricao=str(product_row.descricao),
        ean=str(product_row.ean),
        fornecedor=str(product_row.fornecedor),
        tipo=str(product_row.tipo),
        estoque_atual=position.current_stock,
        vmd=vmd,
        dias_cobertura=position.coverage_days,
        lead_time=policy.lead_time_days,
        estoque_minimo=position.levels.minimum,
        estoque_maximo=position.levels.maximum,
        qtd_sugerida_compra=suggested_qty,
        custo_unitario=unit_cost,
        preco_venda=sale_price,
        investimento_total_item=investment,
        status=status,
        status_label=STATUS_LABELS[status],
        curva_abc=sales_lookup.abc_class_for(sku),
        overstock_capital=overstock_capital,
    )


def product_sort_key(evaluation: ProductEvaluation) -> Tuple[int, int, float]:
    """Chave de ordenação padrão: Status (Ruptura -> Acima) -> Curva ABC (A -> C) -> VMD decrescente.

    Regra: P-055.6.
    """
    return (
        STATUS_SORT_ORDER.get(evaluation.status, DEFAULT_SORT_RANK),
        ABC_SORT_ORDER.get(evaluation.curva_abc, DEFAULT_SORT_RANK),
        -evaluation.vmd,
    )


def build_kpis(evaluations: Sequence[ProductEvaluation]) -> Dict[str, Any]:
    """Agrega os indicadores (KPIs) do conjunto de produtos avaliados sem tetos nem travas.

    Regra: P-054.6, P-055.4, P-055.5 e P-056.1.
    """
    status_counts = Counter(evaluation.status for evaluation in evaluations)
    total_skus = len(evaluations)
    total_investment = round(
        sum(evaluation.investimento_total_item for evaluation in evaluations),
        MONEY_DECIMALS,
    )
    total_overstock_capital = round(
        sum(evaluation.overstock_capital for evaluation in evaluations),
        MONEY_DECIMALS,
    )
    class_a_count = sum(1 for evaluation in evaluations if evaluation.curva_abc == "A")
    class_a_pct = round(
        (class_a_count / max(1, total_skus)) * PERCENT_MULTIPLIER,
        PERCENT_DECIMALS,
    )

    return {
        "totalSkusAnalisados": total_skus,
        "skusEmRupturaCritica": status_counts[InventoryStatus.CRITICAL_STOCKOUT],
        "skusNecessitamReposicao": status_counts[InventoryStatus.REORDER_NEEDED],
        "skusEstoqueSaudavel": status_counts[InventoryStatus.HEALTHY],
        "skusEmOverstock": status_counts[InventoryStatus.OVERSTOCK],
        "investimentoTotalSugerido": total_investment,
        "capitalImobilizadoOverstock": total_overstock_capital,
        "curvaADistribuicao": {
            "qtdItens": class_a_count,
            "percentualItens": class_a_pct,
        },
    }


def calculate_inventory_replenishment(
    catalog_df: pd.DataFrame,
    velocity_df: pd.DataFrame,
    policy: Optional[ReplenishmentPolicy] = None,
) -> Dict[str, Any]:
    """Orquestra o cálculo da Política Mín/Máx para o catálogo de produtos e retorna KPIs + itens.

    Regra: P-053 a P-056 (ADR-001, DA-01 e DA-10).
    """
    active_policy = policy or ReplenishmentPolicy()
    normalized_catalog = normalize_product_catalog(catalog_df)
    sales_lookup = build_sales_lookup(velocity_df)
    evaluations = [
        evaluate_product(row, sales_lookup, active_policy)
        for row in normalized_catalog.itertuples(index=False)
    ]
    evaluations.sort(key=product_sort_key)
    return {
        "kpis": build_kpis(evaluations),
        "produtos": [evaluation.to_response_item() for evaluation in evaluations],
    }
