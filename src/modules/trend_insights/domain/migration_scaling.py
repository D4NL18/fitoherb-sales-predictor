"""
Escala da Janela Anterior por `k` (P-153.2) e agregacao de clientes perdidos (P-164, P-164.1).
Linhas: `(customer_code, sku, pre_qty, pre_rev, cur_qty, cur_rev)`. O codigo do cliente existe so aqui,
em memoria volatil, e nunca sai nas agregacoes (LGPD-TIA-01/02).
"""
from dataclasses import dataclass
from fractions import Fraction
from typing import AbstractSet, Dict, Iterable, Iterator, Mapping, Tuple

Row = Tuple[int, str, float, float, float, float]
_PRE_QTY, _PRE_REV, _CUR_QTY, _CUR_REV = 2, 3, 4, 5


@dataclass(frozen=True)
class LostCustomersAggregate:
    """Perda agregada de um SKU: sem identificador de cliente."""

    count: int
    revenue: float
    quantity: float


def scale_previous(rows: Iterable[Row], k: Fraction) -> Iterator[Row]:
    """Multiplica so as colunas PRE por `k` para comparar grandezas da mesma escala."""
    factor = float(k)
    for customer, sku, pre_qty, pre_rev, cur_qty, cur_rev in rows:
        yield (customer, sku, pre_qty * factor, pre_rev * factor, cur_qty, cur_rev)


def _gained_any_affine(holdings: Mapping[str, Tuple[float, float, float, float]], affines: Iterable[str]) -> bool:
    for affine_sku in affines:
        values = holdings.get(affine_sku)
        if values is not None and values[_CUR_REV - 2] - values[_PRE_REV - 2] > 0:
            return True
    return False


def _collect_lost_holdings(rows: Iterable[Row], lost_codes: AbstractSet[int]) -> Dict[int, Dict[str, tuple]]:
    holdings: Dict[int, Dict[str, tuple]] = {}
    for row in rows:
        if row[0] not in lost_codes:
            continue
        per_sku = holdings.setdefault(row[0], {})
        previous = per_sku.get(row[1], (0.0, 0.0, 0.0, 0.0))
        per_sku[row[1]] = tuple(a + b for a, b in zip(previous, row[2:6]))
    return holdings


def aggregate_lost_customers(
    rows: Iterable[Row],
    lost_codes: AbstractSet[int],
    affinity_map: Mapping[str, Mapping[str, float]],
) -> Dict[str, LostCustomersAggregate]:
    """Soma `max(0, pre*k - cur)` por SKU dos clientes perdidos que NAO ganharam nenhum afim (P-164)."""
    totals: Dict[str, list] = {}
    for per_sku in _collect_lost_holdings(rows, lost_codes).values():
        for sku, (pre_qty, pre_rev, cur_qty, cur_rev) in per_sku.items():
            loss_rev = max(0.0, pre_rev - cur_rev)
            if loss_rev <= 0 or _gained_any_affine(per_sku, affinity_map.get(sku, {})):
                continue
            accumulated = totals.setdefault(sku, [0, 0.0, 0.0])
            accumulated[0] += 1
            accumulated[1] += loss_rev
            accumulated[2] += max(0.0, pre_qty - cur_qty)
    return {sku: LostCustomersAggregate(count=v[0], revenue=v[1], quantity=v[2]) for sku, v in totals.items()}
