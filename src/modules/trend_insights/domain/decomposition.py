"""
Cascata de Atribuicao (P-157..P-171): corte, compensatorias, residuo, parcelas de migracao e
leitura do residuo. Funcoes puras; arredondamento so na saida (P-169.6).
"""
from dataclasses import dataclass, field, replace
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from src.modules.trend_insights.domain.constants import (
    CASCADE_ORDER,
    MAX_PARCEL_TO_BASE_RATIO,
    MIGRATION_HIGH_CONFIDENCE_CLIENTS,
    MIGRATION_MEDIUM_CONFIDENCE_CLIENTS,
    MIN_SHARE_EFFECT_WITHOUT_MIGRATION_RATIO,
    MODE_QUALITATIVE,
)
from src.modules.trend_insights.domain.evidence import MigrationPair, RawParcel

MIGRATION_TYPES = ("PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR", "CANIBALIZACAO_OUTRO_FORNECEDOR")


@dataclass(frozen=True)
class MigrationItem:
    sku: int
    same_supplier: bool
    affinity_score: float
    receita_migrada: float
    clientes_migrados: int
    confianca: str
    descricao: Optional[str] = None
    fornecedor: Optional[str] = None
    lancamento: bool = False


@dataclass(frozen=True)
class Parcel:
    """Parcela final da cascata, ja cortada."""

    tipo: str
    status: str
    valor: Optional[float]
    sentido: Optional[str]
    confianca: Optional[str]
    cortada: bool = False
    explicativa: Optional[bool] = None
    motivo: Optional[str] = None
    itens: Tuple[MigrationItem, ...] = ()
    detalhe: Optional[Mapping[str, object]] = None


@dataclass(frozen=True)
class CascadeResult:
    parcels: Tuple[Parcel, ...]
    residuo: Optional[float]
    cobertura_explicacao_pct: Optional[float]


@dataclass(frozen=True)
class ResidualIndicator:
    valor: float


def _sign(value: float) -> int:
    return (value > 0) - (value < 0)


def _missing_parcel(tipo: str) -> Parcel:
    return Parcel(tipo=tipo, status="NAO_AVALIADO", valor=None, sentido=None, confianca=None, motivo="FONTE_INDISPONIVEL")


def _to_parcel(raw: RawParcel) -> Parcel:
    sentido = raw.sentido or (None if raw.valor is None else ("NEGATIVO" if raw.valor < 0 else "POSITIVO"))
    return Parcel(
        tipo=raw.tipo, status=raw.status, valor=raw.valor, sentido=sentido, confianca=raw.confianca,
        motivo=raw.motivo, itens=tuple(raw.itens), detalhe=raw.detalhe,
    )


def _ordered_parcels(raws: Iterable[RawParcel]) -> List[Parcel]:
    by_type = {raw.tipo: _to_parcel(raw) for raw in raws}
    return [by_type.get(tipo) or _missing_parcel(tipo) for tipo in CASCADE_ORDER]


def _cap_to_base(parcel: Parcel, base_ajustada: float) -> Parcel:
    """P-169.3: nenhuma parcela passa de 100% da Base Ajustada, antes do corte."""
    if parcel.valor is None:
        return parcel
    limit = MAX_PARCEL_TO_BASE_RATIO * abs(base_ajustada)
    if abs(parcel.valor) <= limit:
        return parcel
    return replace(parcel, valor=limit * _sign(parcel.valor))


def _cut_explanatory(parcels: Sequence[Parcel], delta_sign: int, budget: float) -> List[Parcel]:
    """P-169.2: acumula as explicativas na ordem e corta a primeira que ultrapassa o orcamento."""
    accumulated = 0.0
    result: List[Parcel] = []
    for parcel in parcels:
        if parcel.valor is None or _sign(parcel.valor) != delta_sign:
            result.append(parcel)
            continue
        remaining = max(0.0, budget - accumulated)
        magnitude = abs(parcel.valor)
        if magnitude <= remaining:
            accumulated += magnitude
            result.append(replace(parcel, explicativa=True))
            continue
        accumulated += remaining
        result.append(replace(parcel, valor=remaining * delta_sign, cortada=True, explicativa=True))
    return result


def _mark_compensatory(parcels: Sequence[Parcel], delta_sign: int) -> List[Parcel]:
    return [
        replace(p, explicativa=False) if p.valor is not None and _sign(p.valor) == -delta_sign else p
        for p in parcels
    ]


def _qualitative_cascade(parcels: Sequence[Parcel]) -> CascadeResult:
    cleaned = tuple(replace(p, valor=None, cortada=False, explicativa=None) for p in parcels)
    return CascadeResult(parcels=cleaned, residuo=None, cobertura_explicacao_pct=None)


def finalize_cascade(
    delta_observado: Optional[float],
    base_ajustada: Optional[float],
    parcels: Iterable[RawParcel],
    modo: str,
) -> CascadeResult:
    """Ordena, limita, corta e calcula o residuo (P-157, P-168, P-169)."""
    ordered = _ordered_parcels(parcels)
    if modo == MODE_QUALITATIVE or delta_observado is None or base_ajustada is None:
        return _qualitative_cascade(ordered)
    delta_sign = _sign(delta_observado)
    capped = [_cap_to_base(p, base_ajustada) for p in ordered]
    compensatory_total = sum(
        abs(p.valor) for p in capped if p.valor is not None and _sign(p.valor) == -delta_sign
    )
    budget = abs(delta_observado) + compensatory_total
    marked = _mark_compensatory(capped, delta_sign)
    final = _cut_explanatory(marked, delta_sign, budget)
    residual = delta_observado - sum(p.valor or 0.0 for p in final)
    coverage = (1 - abs(residual) / abs(delta_observado)) * 100 if delta_observado else None
    return CascadeResult(parcels=tuple(final), residuo=residual, cobertura_explicacao_pct=coverage)


# ---------------------------------------------------------------- migracao (P-160..P-163, P-171)
def migration_confidence(net_clients: int) -> str:
    if net_clients >= MIGRATION_HIGH_CONFIDENCE_CLIENTS:
        return "ALTA"
    if net_clients >= MIGRATION_MEDIUM_CONFIDENCE_CLIENTS:
        return "MEDIA"
    return "BAIXA"


def _migration_parcel(tipo: str, pairs: Sequence[MigrationPair], sign: int, launch_skus: frozenset) -> RawParcel:
    if not pairs:
        return RawParcel(tipo=tipo, valor=None, status="SEM_EFEITO", motivo="SEM_PARES")
    items = tuple(
        MigrationItem(
            sku=p.sku, same_supplier=p.same_supplier, affinity_score=p.affinity_score,
            receita_migrada=p.net_rev, clientes_migrados=p.net_clients,
            confianca=migration_confidence(p.net_clients), descricao=p.descricao,
            fornecedor=p.fornecedor, lancamento=p.sku in launch_skus,
        )
        for p in sorted(pairs, key=lambda x: (-x.net_rev, x.sku))
    )
    total = sum(p.net_rev for p in pairs) * sign
    return RawParcel(
        tipo=tipo, valor=total, status="AVALIADO",
        confianca=migration_confidence(sum(p.net_clients for p in pairs)), itens=items,
    )


def build_migration_parcels(
    pairs: Sequence[MigrationPair],
    launch_skus: Iterable[int],
    direction: str,
) -> Dict[str, RawParcel]:
    """Cada B entra em uma unica parcela; lancamento tem prioridade sobre canibalizacao (P-169.1)."""
    launches = frozenset(launch_skus)
    is_fall = direction == "QUEDA"
    sign = -1 if is_fall else 1
    launch_pairs = [p for p in pairs if is_fall and p.sku in launches]
    others = [p for p in pairs if p not in launch_pairs]
    result = {
        "PRODUTO_NOVO": _migration_parcel("PRODUTO_NOVO", launch_pairs, sign, launches),
        "CANIBALIZACAO_MESMO_FORNECEDOR": _migration_parcel(
            "CANIBALIZACAO_MESMO_FORNECEDOR", [p for p in others if p.same_supplier], sign, launches),
        "CANIBALIZACAO_OUTRO_FORNECEDOR": _migration_parcel(
            "CANIBALIZACAO_OUTRO_FORNECEDOR", [p for p in others if not p.same_supplier], sign, launches),
    }
    if not is_fall:
        not_applicable = {"status": "SEM_EFEITO", "motivo": "NAO_SE_APLICA_A_ALTA", "valor": None}
        result["PRODUTO_NOVO"] = RawParcel(tipo="PRODUTO_NOVO", **not_applicable)
        result["CLIENTES_PERDIDOS"] = RawParcel(tipo="CLIENTES_PERDIDOS", **not_applicable)
    return result


def convert_revenue_to_quantity(
    revenue: float, rev_pre: float, rev_cur: float, qty_pre: float, qty_cur: float, k: float,
) -> Optional[float]:
    """P-163: converte R$ em unidades pelo preco medio de A nas duas janelas."""
    units = qty_pre * k + qty_cur
    if units <= 0:
        return None
    average_price = (rev_pre * k + rev_cur) / units
    if average_price <= 0:
        return None
    return revenue / average_price


def share_loss_without_migration(
    efeito_participacao: float, migration_total: float, delta_observado: float, residuo: float,
) -> Optional[ResidualIndicator]:
    """P-168.1: leitura do residuo, nao parcela adicional."""
    without_migration = efeito_participacao - migration_total
    if _sign(without_migration) != _sign(efeito_participacao) or without_migration == 0:
        return None
    if abs(without_migration) < MIN_SHARE_EFFECT_WITHOUT_MIGRATION_RATIO * abs(delta_observado):
        return None
    magnitude = min(abs(without_migration), abs(residuo))
    return ResidualIndicator(valor=magnitude * _sign(without_migration))
