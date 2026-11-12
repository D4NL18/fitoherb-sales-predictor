"""
Motor de Cross-sell — domínio puro: constantes, Cestas Válidas, mineração 1 -> 1, Regra Útil,
Item Trivial, catálogo e Recomendação por Produto.

Regras: P-058.3 (Cesta Válida), P-059 (mineração), P-060 (Regra Útil e Par Trivial),
P-061 (Recomendação por Produto), P-063.3 (custo com fallback), P-067 (XSL-001, XSL-003).
Decisões: ADR-002 DA-04 (revisada: contagem direta de pares em vez de FP-Growth), DA-05 (datas como `order_day`).

Sem I/O: não importa `pyodbc`, `fastapi` nem `src.core.database`. Entradas são DataFrames do
agregado `order_baskets` (colunas `order_idx, sku, customer_code, order_day`, `int32`) e do catálogo.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import sparse

from src.modules.analytics.domain.exceptions import InsufficientBaseError, ProductNotFoundError
from src.modules.pricing.domain.basket_mining import filter_orphan_baskets

# ------------------------------------------------------------------ tabela de constantes (seção 2 das regras)
SALE_OPERATION = "VENDA"            # P-058: única operação que forma Cestas (fonte única; o repositório importa)
MIN_SKUS_PER_BASKET = 2             # P-058.3: Cesta Válida tem ao menos 2 SKUs distintos
MIN_SUPPORT = 0.002                 # P-059.2: suporte mínimo do par (Premissa A-1)
MIN_PAIR_ORDERS = 10                # P-059.3: pedidos em comum mínimos (Premissa A-1)
MIN_LIFT = 1.2                      # P-060: lift mínimo, inclusivo
MIN_CONFIDENCE = 0.10               # P-060: confiança mínima, inclusiva (Premissa A-2)
TRIVIAL_ITEM_SUPPORT = 0.15         # P-060.2: acima disso o SKU é Item Trivial (Premissa A-3)
CUSTOMER_PROFILE_DAYS = 365         # P-062.1: janela do perfil do cliente (Premissa A-4)
DORMANT_DAYS = 90                   # P-062.3: acima disso o SKU é Produto Dormente (Premissa A-5)
COST_FALLBACK_RATIO = 0.60          # P-063.3: custo estimado = 60% do preço (P-054.5)
MIN_VALID_BASKETS = 1000            # P-067: abaixo disso a base é insuficiente (Premissa A-7)
HIT_RATE_K = 5                      # P-071: tamanho do top-K do backtest

ORDER_DAY_EPOCH = date(2000, 1, 1)  # DA-02/DA-05: `order_day` = dias desde esta data (o repositório reexporta)

# Tolerância dos limites inclusivos (P-060.1). O mlxtend calcula 50/500 como 0.09999999999999999 e
# 0,12/0,10 como 1.1999999999999997; sem tolerância essas regras seriam descartadas por erro binário.
# 1e-9 é muito menor que qualquer diferença real de confiança/lift exibida (4 e 2 casas).
FLOAT_TOLERANCE = 1e-9

# Coluna sintética exigida por `filter_orphan_baskets` (DA-04): o agregado já
# vem com `SUM(Qtd Venda) > 0` do SQL, então cada par Pedido x SKU vale 1.
_SYNTHETIC_QUANTITY = 1

# Colunas da tabela de regras de `mine_one_to_one_rules` (mesmo formato do mlxtend), consumida por
# `select_useful_rules`, pelo backtest e pelos testes.
_RULE_COLUMNS = ["antecedents", "consequents", "antecedent support", "consequent support", "support",
                 "confidence", "lift"]


@dataclass(frozen=True)
class UsefulRule:
    """
    Regra Útil 1 -> 1 (P-059, P-060). `pair_orders` = `pedidosEmComum`; `antecedent_orders` =
    `pedidosComAntecedente`. Contagens inteiras exatas, recuperadas de suporte x total de cestas.
    """

    antecedent: int
    consequent: int
    support: float
    confidence: float
    lift: float
    pair_orders: int
    antecedent_orders: int


@dataclass(frozen=True)
class CatalogEntry:
    """Produto do catálogo ativo (`Pc.Venda > 0`) com custo unitário já resolvido (P-063.3)."""

    code: int
    description: str
    supplier: str
    stock: float
    price: float
    unit_cost: float
    is_cost_estimated: bool


@dataclass(frozen=True)
class ProductRecommendation:
    """Item da Recomendação por Produto: regra, consequente e sinalizações de P-061.4."""

    rule: UsefulRule
    entry: CatalogEntry
    is_out_of_stock: bool
    has_non_positive_margin: bool


# ------------------------------------------------------------------ Cestas Válidas (P-058.3)

def build_valid_baskets(order_baskets: pd.DataFrame) -> pd.DataFrame:
    """
    Converte o agregado `order_baskets` no formato de `basket_mining` e descarta cestas de 1 SKU.

    Args:
        order_baskets: agregado com `order_idx` e `sku`.

    Returns:
        DataFrame com `Pedido`, `Cod Produto` e `Qtd Venda` (`int8` = 1), só Cestas Válidas.

    Regra: P-058.3 (reusa `filter_orphan_baskets`, P-005).
    """
    baskets = pd.DataFrame({
        "Pedido": order_baskets["order_idx"].to_numpy(),
        "Cod Produto": order_baskets["sku"].to_numpy(),
        "Qtd Venda": np.full(len(order_baskets), _SYNTHETIC_QUANTITY, dtype=np.int8),
    })
    return filter_orphan_baskets(baskets, min_skus=MIN_SKUS_PER_BASKET)


def count_valid_baskets(valid_baskets: pd.DataFrame) -> int:
    """Número de Cestas Válidas (pedidos distintos). Regra: P-059.2."""
    return int(valid_baskets["Pedido"].nunique())


def list_skus_with_basket(valid_baskets: pd.DataFrame) -> FrozenSet[int]:
    """SKUs presentes em ao menos uma Cesta Válida (base do XSL-001, P-061.6)."""
    return frozenset(valid_baskets["Cod Produto"].unique().tolist())


# ------------------------------------------------------------------ mineração e Regra Útil (P-059, P-060)

def _cooccurrence_counts(valid_baskets: pd.DataFrame) -> Tuple[np.ndarray, sparse.coo_matrix, int]:
    """
    Códigos dos SKUs, matriz SKU x SKU de pedidos em comum (só fora da diagonal) e total de cestas.

    `Xᵀ·X` sobre a matriz esparsa Pedido x SKU conta, de uma vez, em quantos pedidos cada par aparece.
    A diagonal (pedidos de cada SKU) sai à parte em `item_orders` dentro de `mine_one_to_one_rules`.
    """
    pairs = valid_baskets[["Pedido", "Cod Produto"]].drop_duplicates()
    order_codes, order_pos = np.unique(pairs["Pedido"].to_numpy(), return_inverse=True)
    sku_codes, sku_pos = np.unique(pairs["Cod Produto"].to_numpy(), return_inverse=True)
    incidence = sparse.csr_matrix(
        (np.ones(len(pairs), dtype=np.int32), (order_pos, sku_pos)), shape=(len(order_codes), len(sku_codes)),
    )
    cooccurrence = (incidence.T @ incidence).tocoo()
    return sku_codes, cooccurrence, len(order_codes)


def mine_one_to_one_rules(valid_baskets: pd.DataFrame) -> pd.DataFrame:
    """
    Minera regras 1 -> 1 por contagem direta de coocorrência (Xᵀ·X esparso) e devolve o mesmo formato
    do `mine_association_rules` (mlxtend): `antecedents`, `consequents`, `antecedent support`,
    `consequent support`, `support`, `confidence`, `lift`.

    Por que não FP-Growth: com `max_len=2` o resultado é idêntico (todo itemset frequente de 2 itens é
    um par), mas o FP-Growth do mlxtend sobre DataFrame esparso não terminou em 10 min na base real
    (~54 mil cestas) e passou de 4 GB de RAM; a contagem direta leva segundos (ADR-002 DA-04, revisada).

    Os limites usam `FLOAT_TOLERANCE`; o corte definitivo (inclusivo) é de `select_useful_rules`.

    Regra: P-059.1, P-059.2; ADR-002 DA-04.
    """
    if valid_baskets.empty:
        return pd.DataFrame(columns=_RULE_COLUMNS)
    sku_codes, cooccurrence, total_baskets = _cooccurrence_counts(valid_baskets)
    return _rules_from_counts(sku_codes, cooccurrence, total_baskets)


def _rules_from_counts(sku_codes: np.ndarray, cooccurrence: sparse.coo_matrix, total_baskets: int) -> pd.DataFrame:
    """Converte as contagens de pares em linhas de regra 1 -> 1 já pré-filtradas por suporte, confiança e lift."""
    item_orders = np.asarray(cooccurrence.tocsr().diagonal(), dtype=np.float64)
    is_pair = cooccurrence.row != cooccurrence.col
    rows, cols = cooccurrence.row[is_pair], cooccurrence.col[is_pair]
    pair_orders = cooccurrence.data[is_pair].astype(np.float64)
    support = pair_orders / total_baskets
    antecedent_support = item_orders[rows] / total_baskets
    consequent_support = item_orders[cols] / total_baskets
    confidence = pair_orders / item_orders[rows]
    lift = confidence / consequent_support
    keep = ((support >= MIN_SUPPORT - FLOAT_TOLERANCE) & (confidence >= MIN_CONFIDENCE - FLOAT_TOLERANCE)
            & (lift >= MIN_LIFT - FLOAT_TOLERANCE))
    return pd.DataFrame({
        "antecedents": [frozenset((int(code),)) for code in sku_codes[rows[keep]]],
        "consequents": [frozenset((int(code),)) for code in sku_codes[cols[keep]]],
        "antecedent support": antecedent_support[keep], "consequent support": consequent_support[keep],
        "support": support[keep], "confidence": confidence[keep], "lift": lift[keep],
    }, columns=_RULE_COLUMNS)


def _single_item(itemset: frozenset) -> Optional[int]:
    """Item único de um itemset de 1 elemento; `None` para itemsets maiores (P-059.1)."""
    if len(itemset) != 1:
        return None
    return int(next(iter(itemset)))


def _useful_rules_mask(rules: pd.DataFrame) -> pd.Series:
    """
    Máscara das linhas que atendem P-059.3, P-059.6 e P-060 (limites inclusivos, consequente não trivial).
    Espera as colunas auxiliares `antecedent_sku`, `consequent_sku` e `pair_orders`.
    """
    is_one_to_one = rules["antecedent_sku"].notna() & rules["consequent_sku"].notna()
    is_not_self_rule = rules["antecedent_sku"] != rules["consequent_sku"]
    is_not_trivial = rules["consequent support"] <= TRIVIAL_ITEM_SUPPORT + FLOAT_TOLERANCE
    has_confidence = rules["confidence"] >= MIN_CONFIDENCE - FLOAT_TOLERANCE
    has_lift = rules["lift"] >= MIN_LIFT - FLOAT_TOLERANCE
    has_pair_orders = rules["pair_orders"] >= MIN_PAIR_ORDERS
    return is_one_to_one & is_not_self_rule & is_not_trivial & has_confidence & has_lift & has_pair_orders


def select_useful_rules(rules: pd.DataFrame, total_baskets: int) -> Tuple[UsefulRule, ...]:
    """
    Converte a tabela de `mine_one_to_one_rules` em Regras Úteis 1 -> 1.

    Args:
        rules: tabela de `mine_one_to_one_rules` (formato do mlxtend).
        total_baskets: número de Cestas Válidas (N) usado para recuperar as contagens inteiras.

    Returns:
        Tupla de `UsefulRule` (sem ordem garantida; a ordem de P-061.1 vem do índice).

    Regra: P-059.3, P-059.6, P-060 (Par Trivial: consequente com suporte > 15%).
    """
    if rules.empty or total_baskets <= 0:
        return ()
    candidates = rules.assign(
        antecedent_sku=rules["antecedents"].map(_single_item),
        consequent_sku=rules["consequents"].map(_single_item),
        pair_orders=(rules["support"] * total_baskets).round().astype(int),
        antecedent_orders=(rules["antecedent support"] * total_baskets).round().astype(int),
    )
    selected = candidates[_useful_rules_mask(candidates)]
    return tuple(
        UsefulRule(antecedent=int(row.antecedent_sku), consequent=int(row.consequent_sku), support=float(row.support),
                   confidence=float(row.confidence), lift=float(row.lift), pair_orders=int(row.pair_orders),
                   antecedent_orders=int(row.antecedent_orders))
        for row in selected[["antecedent_sku", "consequent_sku", "support", "confidence", "lift", "pair_orders",
                             "antecedent_orders"]].itertuples(index=False)
    )


def find_trivial_skus(valid_baskets: pd.DataFrame) -> FrozenSet[int]:
    """
    Itens Triviais: SKUs em mais de `TRIVIAL_ITEM_SUPPORT` das Cestas Válidas (15% exatos não é trivial).
    Regra: P-060.2, P-060.4.
    """
    total_baskets = count_valid_baskets(valid_baskets)
    if total_baskets == 0:
        return frozenset()
    basket_share = valid_baskets.groupby("Cod Produto")["Pedido"].nunique() / total_baskets
    return frozenset(basket_share[basket_share > TRIVIAL_ITEM_SUPPORT + FLOAT_TOLERANCE].index.tolist())


def _product_mode_order(rule: UsefulRule) -> Tuple[float, float, int, int]:
    """Chave de P-061.1: lift desc, confiança desc, pedidos em comum desc, código asc."""
    return (-rule.lift, -rule.confidence, -rule.pair_orders, rule.consequent)


def index_rules_by_antecedent(useful_rules: Sequence[UsefulRule]) -> Dict[int, Tuple[UsefulRule, ...]]:
    """
    Índice antecedente -> regras já na ordem de P-061.1, montado uma vez por carga (P-059.7).
    """
    grouped: Dict[int, List[UsefulRule]] = {}
    for rule in useful_rules:
        grouped.setdefault(rule.antecedent, []).append(rule)
    return {antecedent: tuple(sorted(rules, key=_product_mode_order)) for antecedent, rules in grouped.items()}


def is_base_sufficient(valid_basket_count: int, useful_rule_count: int) -> bool:
    """Base confiável: ao menos `MIN_VALID_BASKETS` Cestas Válidas e uma Regra Útil. Regra: P-067."""
    return valid_basket_count >= MIN_VALID_BASKETS and useful_rule_count > 0


def assert_base_is_sufficient(valid_basket_count: int, useful_rule_count: int) -> None:
    """
    Raises:
        InsufficientBaseError: `XSL-003` quando `is_base_sufficient` é falso (P-067).
    """
    if not is_base_sufficient(valid_basket_count, useful_rule_count):
        raise InsufficientBaseError()


# ------------------------------------------------------------------ catálogo e margem (P-061.3, P-063.3)

def _numeric_column(catalog_df: pd.DataFrame, column: str) -> pd.Series:
    """Coluna numérica `float` (valores ausentes ou inválidos viram NaN; `Decimal` do pyodbc vira float)."""
    return pd.to_numeric(catalog_df[column], errors="coerce").astype(float)


def _resolve_unit_cost(last_cost: float, price: float) -> Tuple[float, bool]:
    """
    Custo Unitário de P-063.3: `Pc.Ultimo Custo` se positivo; senão `COST_FALLBACK_RATIO x Pc.Venda`.

    Returns:
        (custo unitário, `is_cost_estimated`).
    """
    if math.isnan(last_cost) or last_cost <= 0:
        return price * COST_FALLBACK_RATIO, True
    return last_cost, False


def _text_or_empty(value: object) -> str:
    """Texto do catálogo; ausente (None/NaN) vira string vazia."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


def build_catalog_lookup(catalog_df: pd.DataFrame) -> Dict[int, CatalogEntry]:
    """
    Indexa o catálogo ativo por SKU. Linhas sem preço positivo ficam de fora (catálogo ativo, P-061.3).
    Regra: P-063.3 (fallback de custo de 60%, `is_cost_estimated`).
    """
    prices = _numeric_column(catalog_df, "Pc.Venda").fillna(0.0)
    last_costs = _numeric_column(catalog_df, "Pc.Ultimo Custo")
    stocks = _numeric_column(catalog_df, "Estoque").fillna(0.0)
    lookup: Dict[int, CatalogEntry] = {}
    for position, code in enumerate(catalog_df["Codigo"].tolist()):
        price = float(prices.iat[position])
        if price <= 0:
            continue
        unit_cost, is_cost_estimated = _resolve_unit_cost(float(last_costs.iat[position]), price)
        lookup[int(code)] = CatalogEntry(
            code=int(code), description=_text_or_empty(catalog_df["Descricao"].iat[position]),
            supplier=_text_or_empty(catalog_df["Fornecedor"].iat[position]), stock=float(stocks.iat[position]),
            price=price, unit_cost=unit_cost, is_cost_estimated=is_cost_estimated,
        )
    return lookup


def calculate_unit_margin(entry: CatalogEntry) -> float:
    """Margem Unitária = `Pc.Venda - Custo Unitário` (R$). Regra: P-063.3."""
    return entry.price - entry.unit_cost


def is_out_of_stock(entry: CatalogEntry) -> bool:
    """Sem estoque: `Estoque <= 0` (estoque negativo do ERP também conta). Regra: P-061.4, P-063.1."""
    return entry.stock <= 0


# ------------------------------------------------------------------ Recomendação por Produto (P-061)

def _to_product_recommendation(rule: UsefulRule, entry: CatalogEntry) -> ProductRecommendation:
    """Monta o item com as sinalizações de P-061.4 (sinaliza, não exclui)."""
    return ProductRecommendation(
        rule=rule, entry=entry, is_out_of_stock=is_out_of_stock(entry),
        has_non_positive_margin=calculate_unit_margin(entry) <= 0,
    )


def recommend_for_product(snapshot_view, sku: int) -> List[ProductRecommendation]:
    """
    "Quem compra A também leva o quê?"

    Args:
        snapshot_view: objeto com `rules_by_antecedent`, `catalog` e `skus_with_basket`.
        sku: código do produto antecedente.

    Returns:
        Lista completa (antes da paginação) na ordem de P-061.1; vazia se não há Regra Útil (P-061.5).

    Raises:
        ProductNotFoundError: `XSL-001` se o SKU está fora do catálogo ativo ou sem Cesta Válida (P-061.6).

    Regra: P-061.1 a P-061.6.
    """
    catalog: Mapping[int, CatalogEntry] = snapshot_view.catalog
    if sku not in catalog or sku not in snapshot_view.skus_with_basket:
        raise ProductNotFoundError()
    return [
        _to_product_recommendation(rule, catalog[rule.consequent])
        for rule in snapshot_view.rules_by_antecedent.get(sku, ())
        if rule.consequent in catalog
    ]
