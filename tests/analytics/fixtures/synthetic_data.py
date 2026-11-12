"""
Massas sintéticas do módulo Analytics Comercial (Fase 1, F4 Cross-sell).

Todas as massas são fabricadas aqui, com números escolhidos para que as métricas esperadas
(suporte, confiança, lift, pedidos em comum, pontuação, hit rate@5) sejam conhecidas de antemão.
Nada é extraído da produção (LGPD-11). Os códigos de cliente são inventados.

Convenções:
- O agregado `order_baskets` segue o contrato do repositório (ADR-002, DA-02): colunas
  `order_idx, sku, customer_code, order_day`, todas `int32`; `order_day` = dias desde 2000-01-01.
- O catálogo segue a projeção mínima de LGPD-01: `Codigo, Descricao, Fornecedor, Estoque,
  Pc.Ultimo Custo, Pc.Venda`.
- "Cesta de enchimento" (filler) = pedido com um SKU do sorteio determinístico de um pool grande,
  para que os pares com filler nunca atinjam o suporte mínimo nem `MIN_PAIR_ORDERS`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

ORDER_BASKET_COLUMNS = ["order_idx", "sku", "customer_code", "order_day"]
CATALOG_COLUMNS = ["Codigo", "Descricao", "Fornecedor", "Estoque", "Pc.Ultimo Custo", "Pc.Venda"]

EPOCH_DATE = date(2000, 1, 1)

# Relógio fixo dos testes: 2026-11-05 15:00 UTC = 12:00 em UTC-3 -> data de referência 2026-11-05.
FIXED_NOW_UTC = datetime(2026, 11, 5, 15, 0, 0, tzinfo=timezone.utc)
REFERENCE_DATE = date(2026, 11, 5)
EXPECTED_CUTOFF = REFERENCE_DATE + timedelta(days=1)  # corte exclusivo (DA-02, DA-05)

FILLER_POOL_START = 900_000
FILLER_POOL_SIZE = 300
MINING_CUSTOMER = 1  # dono de todas as cestas de mineração (pedidos antigos, sem perfil recente)


def to_order_day(day: date) -> int:
    """Converte uma data em `order_day` (dias desde 2000-01-01), como o DATEDIFF do repositório."""
    return (day - EPOCH_DATE).days


REFERENCE_DAY = to_order_day(REFERENCE_DATE)
MINING_DAY = REFERENCE_DAY - 500  # cestas de mineração bem antigas: fora do perfil de 365 dias


class BasketBuilder:
    """Monta o agregado `order_baskets` pedido a pedido, com enchimento determinístico."""

    def __init__(self, seed: int = 42, filler_pool_size: int = FILLER_POOL_SIZE):
        self._rows: List[Tuple[int, int, int, int]] = []
        self._next_order = 0
        self._rng = np.random.RandomState(seed)
        self.filler_pool = list(range(FILLER_POOL_START, FILLER_POOL_START + filler_pool_size))

    def add_order(self, skus: Sequence[int], customer_code: int = MINING_CUSTOMER, order_day: int = MINING_DAY) -> int:
        """Acrescenta um pedido com os SKUs distintos informados e devolve o `order_idx`."""
        order_idx = self._next_order
        self._next_order += 1
        for sku in dict.fromkeys(skus):
            self._rows.append((order_idx, int(sku), int(customer_code), int(order_day)))
        return order_idx

    def add_orders(self, count: int, skus: Sequence[int], customer_code: int = MINING_CUSTOMER,
                   order_day: int = MINING_DAY) -> None:
        for _ in range(count):
            self.add_order(skus, customer_code, order_day)

    def add_with_filler(self, count: int, skus: Sequence[int], customer_code: int = MINING_CUSTOMER,
                        order_day: int = MINING_DAY) -> None:
        """`count` pedidos com os SKUs informados mais um SKU de enchimento sorteado."""
        for _ in range(count):
            filler = int(self.filler_pool[self._rng.randint(len(self.filler_pool))])
            self.add_order(list(skus) + [filler], customer_code, order_day)

    def add_filler_only(self, count: int, customer_code: int = MINING_CUSTOMER, order_day: int = MINING_DAY) -> None:
        """`count` pedidos com dois SKUs de enchimento distintos."""
        for _ in range(count):
            first, second = self._rng.choice(len(self.filler_pool), size=2, replace=False)
            self.add_order([self.filler_pool[first], self.filler_pool[second]], customer_code, order_day)

    def to_frame(self) -> pd.DataFrame:
        frame = pd.DataFrame(self._rows, columns=ORDER_BASKET_COLUMNS)
        return frame.astype({column: np.int32 for column in ORDER_BASKET_COLUMNS})


@dataclass(frozen=True)
class SyntheticProduct:
    codigo: int
    descricao: str
    fornecedor: str
    estoque: float
    ultimo_custo: float
    preco_venda: float


def catalog_frame(products: Iterable[SyntheticProduct], filler_skus: Iterable[int] = ()) -> pd.DataFrame:
    """Catálogo ativo sintético; SKUs de enchimento entram com estoque, preço e margem positivos."""
    rows = [
        {"Codigo": p.codigo, "Descricao": p.descricao, "Fornecedor": p.fornecedor, "Estoque": p.estoque,
         "Pc.Ultimo Custo": p.ultimo_custo, "Pc.Venda": p.preco_venda}
        for p in products
    ]
    rows += [
        {"Codigo": sku, "Descricao": f"PRODUTO SINTETICO {sku}", "Fornecedor": "FORNECEDOR SINTETICO",
         "Estoque": 10.0, "Pc.Ultimo Custo": 5.0, "Pc.Venda": 10.0}
        for sku in filler_skus
    ]
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS)


# ---------------------------------------------------------------------------------------------
# Massa do contrato, modo produto (contrato §3.3: R1 e R5 de P-060, 10.000 Cestas Válidas)
# ---------------------------------------------------------------------------------------------
SKU_CHA_VERDE = 1001          # antecedente A (500 cestas)
SKU_HIBISCO = 2002            # B: 800 cestas, 170 com A -> confiança 0,34, lift 4,25
SKU_OLEO_COCO_200 = 3003      # F: 1.000 cestas, 60 com A -> confiança 0,12, lift 1,2 (limite inclusivo); estoque 0
SKU_FORA_CATALOGO = 6006      # X: 300 cestas, 50 com A -> regra útil, mas fora do catálogo (P-061.3)
SKU_MEL = 4004                # no catálogo, com cestas, sem nenhuma Regra Útil (C-02)
SKU_SO_PEDIDO_UNITARIO = 5005  # no catálogo, só em pedidos de 1 item (C-03, XSL-001)
SKU_INEXISTENTE = 999_999     # fora do catálogo e da base (XSL-001)

PRODUCT_MASS_PRODUCTS = [
    SyntheticProduct(SKU_CHA_VERDE, "CHA VERDE 100G", "CATARINENSE", 50.0, 8.0, 15.0),
    SyntheticProduct(SKU_HIBISCO, "CAPSULA DE HIBISCO", "HERBARIUM", 84.0, 10.0, 20.0),
    SyntheticProduct(SKU_OLEO_COCO_200, "OLEO DE COCO 200ML", "COPRA", 0.0, 9.0, 15.0),
    SyntheticProduct(SKU_MEL, "MEL DE ABELHA 500G", "APIS FLORA", 12.0, 20.0, 32.0),
    SyntheticProduct(SKU_SO_PEDIDO_UNITARIO, "PROPOLIS VERDE 30ML", "APIS FLORA", 5.0, 10.0, 18.0),
]


def build_product_contract_mass() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Agregado e catálogo que reproduzem o exemplo 200 do contrato §3.3 (A -> B e A -> F)."""
    builder = BasketBuilder(seed=7)
    builder.add_orders(170, [SKU_CHA_VERDE, SKU_HIBISCO])
    builder.add_orders(60, [SKU_CHA_VERDE, SKU_OLEO_COCO_200])
    builder.add_orders(50, [SKU_CHA_VERDE, SKU_FORA_CATALOGO])
    builder.add_with_filler(220, [SKU_CHA_VERDE])
    builder.add_with_filler(630, [SKU_HIBISCO])
    builder.add_with_filler(940, [SKU_OLEO_COCO_200])
    builder.add_with_filler(250, [SKU_FORA_CATALOGO])
    builder.add_with_filler(30, [SKU_MEL])
    builder.add_filler_only(10_000 - (500 + 630 + 940 + 250 + 30))
    builder.add_orders(3, [SKU_SO_PEDIDO_UNITARIO])  # pedidos de 1 item: não viram Cesta Válida
    return builder.to_frame(), catalog_frame(PRODUCT_MASS_PRODUCTS, builder.filler_pool)


# ---------------------------------------------------------------------------------------------
# Massa do contrato, modo cliente (contrato §3.4 e CA-13: G antes de B)
# ---------------------------------------------------------------------------------------------
SKU_GENGIBRE = 7007   # G: 1.000 cestas; 100 com A (conf. 0,20, lift 2,0) e 60 com H (conf. 0,15, lift 1,5)
SKU_CHA_MATE = 8008   # H: 400 cestas
SKU_OLEO_COCO_500 = 9009  # K: 500 cestas; 120 com H (lift 6,0), mas margem zero (P-063.4)

CUSTOMER_WITH_CANDIDATES = 48_213      # comprou A (5 d) e H (10 d); B há 120 d (DORMENTE); nunca G
CUSTOMER_INACTIVE = 51_977             # só comprou há 400 dias -> SEM_COMPRAS_RECENTES (C-07)
CUSTOMER_ALREADY_BUYS_ALL = 63_421     # comprou A, B e G nos últimos 90 dias -> vazio sem motivo (C-06)
CUSTOMER_UNKNOWN = 88_888              # nunca comprou -> XSL-002 (C-08)

CUSTOMER_MASS_PRODUCTS = [
    SyntheticProduct(SKU_CHA_VERDE, "CHA VERDE 100G", "CATARINENSE", 50.0, 8.0, 15.0),
    SyntheticProduct(SKU_HIBISCO, "CAPSULA DE HIBISCO", "HERBARIUM", 84.0, 0.0, 12.5),  # custo 0 -> 7,50 (fallback)
    SyntheticProduct(SKU_GENGIBRE, "GENGIBRE EM PO 100G", "CATARINENSE", 30.0, 20.0, 50.0),
    SyntheticProduct(SKU_CHA_MATE, "CHA MATE 250G", "LEAO", 20.0, 5.0, 9.0),
    SyntheticProduct(SKU_OLEO_COCO_500, "OLEO DE COCO 500ML", "COPRA", 40.0, 10.0, 10.0),
]


def build_customer_contract_mass() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Agregado e catálogo do exemplo do contrato §3.4; pedidos dos clientes são de 1 item (P-062.1)."""
    builder = BasketBuilder(seed=11)
    builder.add_orders(170, [SKU_CHA_VERDE, SKU_HIBISCO])
    builder.add_orders(100, [SKU_CHA_VERDE, SKU_GENGIBRE])
    builder.add_with_filler(230, [SKU_CHA_VERDE])
    builder.add_orders(60, [SKU_CHA_MATE, SKU_GENGIBRE])
    builder.add_orders(120, [SKU_CHA_MATE, SKU_OLEO_COCO_500])
    builder.add_with_filler(220, [SKU_CHA_MATE])
    builder.add_with_filler(630, [SKU_HIBISCO])
    builder.add_with_filler(840, [SKU_GENGIBRE])
    builder.add_with_filler(380, [SKU_OLEO_COCO_500])
    builder.add_filler_only(10_000 - (500 + 400 + 630 + 840 + 380))

    builder.add_order([SKU_CHA_VERDE], CUSTOMER_WITH_CANDIDATES, REFERENCE_DAY - 5)
    builder.add_order([SKU_CHA_MATE], CUSTOMER_WITH_CANDIDATES, REFERENCE_DAY - 10)
    builder.add_order([SKU_HIBISCO], CUSTOMER_WITH_CANDIDATES, REFERENCE_DAY - 120)

    builder.add_order([SKU_CHA_VERDE], CUSTOMER_INACTIVE, REFERENCE_DAY - 400)

    builder.add_order([SKU_CHA_VERDE], CUSTOMER_ALREADY_BUYS_ALL, REFERENCE_DAY - 3)
    builder.add_order([SKU_HIBISCO], CUSTOMER_ALREADY_BUYS_ALL, REFERENCE_DAY - 4)
    builder.add_order([SKU_GENGIBRE], CUSTOMER_ALREADY_BUYS_ALL, REFERENCE_DAY - 6)
    return builder.to_frame(), catalog_frame(CUSTOMER_MASS_PRODUCTS, builder.filler_pool)


def build_insufficient_mass() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Base com 50 Cestas Válidas (< MIN_VALID_BASKETS): todo cross-sell vira XSL-003."""
    builder = BasketBuilder(seed=3)
    builder.add_orders(50, [SKU_CHA_VERDE, SKU_HIBISCO])
    builder.add_order([SKU_CHA_VERDE], CUSTOMER_WITH_CANDIDATES, REFERENCE_DAY - 5)
    return builder.to_frame(), catalog_frame(PRODUCT_MASS_PRODUCTS)


# ---------------------------------------------------------------------------------------------
# Massa do backtest (P-071) com resposta conhecida: N = 2026-10
# ---------------------------------------------------------------------------------------------
BACKTEST_MONTH = "2026-10"
BACKTEST_CUTOFF = date(2026, 10, 1)              # 1º dia de N: treino = order_day < este dia
BACKTEST_CUT_DAY = to_order_day(BACKTEST_CUTOFF)
BACKTEST_NEXT_MONTH_DAY = to_order_day(date(2026, 11, 1))

SKU_POPULAR_FORA_CATALOGO = 6100  # P: 900 cestas, não está no catálogo -> fora da popularidade
SKU_MARGEM_ZERO = 6200            # H': 400 cestas, custo = preço -> fora da popularidade
SKU_POP_K = 6300                  # 300 cestas
SKU_POP_M = 6400                  # 250 cestas
SKU_POP_N = 6500                  # 200 cestas
SKU_SEM_REGRA = 6600              # só em pedidos de 1 item: perfil sem regra -> sem recomendação
SKU_LEAK_A = 6700                 # par inédito que só aparece no mês N (CA-23)
SKU_LEAK_B = 6800

BACKTEST_CUSTOMER_HIT_1 = 900_101      # perfil A; compra B em N (modelo acerta, popularidade acerta)
BACKTEST_CUSTOMER_HIT_2 = 900_102      # idem
BACKTEST_CUSTOMER_POP_ONLY = 900_103   # perfil A; compra G em N (modelo erra, popularidade acerta)
BACKTEST_CUSTOMER_NO_BUY = 900_104     # perfil A; só compra em novembro (fora de N)
BACKTEST_CUSTOMER_NO_PROFILE = 900_105  # última compra há 400 dias; compra B em N
BACKTEST_CUSTOMER_NO_RULE = 900_106    # perfil só com SKU sem regra; compra B em N
BACKTEST_CUSTOMER_RECENT_G = 900_107   # perfil A e G (G há 50 dias); compra G em N: popularidade não pode sugerir G

BACKTEST_CUSTOMERS = [
    BACKTEST_CUSTOMER_HIT_1, BACKTEST_CUSTOMER_HIT_2, BACKTEST_CUSTOMER_POP_ONLY, BACKTEST_CUSTOMER_NO_BUY,
    BACKTEST_CUSTOMER_NO_PROFILE, BACKTEST_CUSTOMER_NO_RULE, BACKTEST_CUSTOMER_RECENT_G,
]

BACKTEST_PRODUCTS = [
    SyntheticProduct(SKU_CHA_VERDE, "CHA VERDE 100G", "CATARINENSE", 50.0, 8.0, 15.0),
    SyntheticProduct(SKU_HIBISCO, "CAPSULA DE HIBISCO", "HERBARIUM", 0.0, 10.0, 20.0),  # sem estoque: P-071.5
    SyntheticProduct(SKU_GENGIBRE, "GENGIBRE EM PO 100G", "CATARINENSE", 30.0, 20.0, 50.0),
    SyntheticProduct(SKU_MARGEM_ZERO, "CHA DE BOLDO", "LEAO", 30.0, 12.0, 12.0),
    SyntheticProduct(SKU_POP_K, "CHA DE CAMOMILA", "LEAO", 30.0, 5.0, 9.0),
    SyntheticProduct(SKU_POP_M, "CHA DE HORTELA", "LEAO", 30.0, 5.0, 9.0),
    SyntheticProduct(SKU_POP_N, "CHA DE ERVA DOCE", "LEAO", 30.0, 5.0, 9.0),
    SyntheticProduct(SKU_SEM_REGRA, "OLEO DE COPAIBA", "COPRA", 30.0, 5.0, 9.0),
]


def build_backtest_mass(with_leak_pair: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Treino (10.000 Cestas Válidas antes de 2026-10-01): só A -> B é Regra Útil para os clientes.
    Popularidade no treino: G 1.000 > P 900 (fora do catálogo) > B 800 > A 500 > H' 400 (margem 0)
    > K 300 > M 250 > N 200 > enchimento (~55).

    Resposta conhecida para N = 2026-10:
    - avaliados: HIT_1, HIT_2, POP_ONLY, RECENT_G (4)
    - modelo (top 5 = [B]): acertos HIT_1, HIT_2 -> 2/4 = 0,50
    - popularidade: HIT_1, HIT_2, POP_ONLY acertam; RECENT_G não (G comprado há 50 dias é excluído) -> 3/4 = 0,75
    - excluídos: SEM_PERFIL = 2 (MINING_CUSTOMER e NO_PROFILE), SEM_COMPRA_NO_MES = 1 (NO_BUY),
      SEM_RECOMENDACAO = 1 (NO_RULE)
    """
    builder = BasketBuilder(seed=23)
    train_day = BACKTEST_CUT_DAY - 450
    builder.add_orders(170, [SKU_CHA_VERDE, SKU_HIBISCO], order_day=train_day)
    builder.add_with_filler(330, [SKU_CHA_VERDE], order_day=train_day)
    builder.add_with_filler(630, [SKU_HIBISCO], order_day=train_day)
    builder.add_with_filler(1000, [SKU_GENGIBRE], order_day=train_day)
    builder.add_with_filler(900, [SKU_POPULAR_FORA_CATALOGO], order_day=train_day)
    builder.add_with_filler(400, [SKU_MARGEM_ZERO], order_day=train_day)
    builder.add_with_filler(300, [SKU_POP_K], order_day=train_day)
    builder.add_with_filler(250, [SKU_POP_M], order_day=train_day)
    builder.add_with_filler(200, [SKU_POP_N], order_day=train_day)
    builder.add_filler_only(10_000 - 4180, order_day=train_day)

    cut = BACKTEST_CUT_DAY
    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_HIT_1, cut - 30)
    builder.add_order([SKU_HIBISCO], BACKTEST_CUSTOMER_HIT_1, cut + 5)

    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_HIT_2, cut - 60)
    builder.add_order([SKU_HIBISCO], BACKTEST_CUSTOMER_HIT_2, cut + 6)

    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_POP_ONLY, cut - 10)
    builder.add_order([SKU_GENGIBRE], BACKTEST_CUSTOMER_POP_ONLY, cut + 7)

    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_NO_BUY, cut - 20)
    builder.add_order([SKU_HIBISCO], BACKTEST_CUSTOMER_NO_BUY, BACKTEST_NEXT_MONTH_DAY + 2)  # novembro: fora de N

    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_NO_PROFILE, cut - 400)
    builder.add_order([SKU_HIBISCO], BACKTEST_CUSTOMER_NO_PROFILE, cut + 8)

    builder.add_order([SKU_SEM_REGRA], BACKTEST_CUSTOMER_NO_RULE, cut - 15)
    builder.add_order([SKU_HIBISCO], BACKTEST_CUSTOMER_NO_RULE, cut + 9)

    builder.add_order([SKU_CHA_VERDE], BACKTEST_CUSTOMER_RECENT_G, cut - 25)
    builder.add_order([SKU_GENGIBRE], BACKTEST_CUSTOMER_RECENT_G, cut - 50)
    builder.add_order([SKU_GENGIBRE], BACKTEST_CUSTOMER_RECENT_G, cut + 10)

    if with_leak_pair:
        # Par inédito A'-B' com 40 pedidos, todos dentro do mês N (CA-23).
        builder.add_orders(40, [SKU_LEAK_A, SKU_LEAK_B], customer_code=2, order_day=cut + 3)

    return builder.to_frame(), catalog_frame(BACKTEST_PRODUCTS, builder.filler_pool)


def rules_frame(rows: Iterable[Dict[str, object]]) -> pd.DataFrame:
    """Tabela de regras no formato de `mine_association_rules` (mlxtend), para testes de filtro puro."""
    columns = ["antecedents", "consequents", "antecedent support", "consequent support", "support", "confidence",
               "lift"]
    return pd.DataFrame(list(rows), columns=columns)
