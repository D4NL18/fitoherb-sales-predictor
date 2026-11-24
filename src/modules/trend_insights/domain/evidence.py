"""
Pacote de evidencias do Motor (P-179, P-175): visao tipada sobre o mapa canonico do diagnostico e o
`evidenceHash` deterministico que identifica o diagnostico salvo. Nenhum dado de cliente entra aqui.
"""
import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

HASH_FLOAT_DECIMALS = 2
HASH_SCORE_DECIMALS = 3
_SCORE_KEYS = ("affinity_score", "residual_share")

INTERNAL_FACTOR_TYPES: Tuple[str, ...] = (
    "SAZONALIDADE", "PRECO", "PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR",
    "CANIBALIZACAO_OUTRO_FORNECEDOR", "PERDA_PARTICIPACAO_SEM_MIGRACAO", "CLIENTES_PERDIDOS",
    "RUPTURA", "PROMOCAO", "REGIONAL",
)


@dataclass(frozen=True)
class RawParcel:
    """Parcela bruta devolvida por uma fonte, antes do corte da cascata (P-169)."""

    tipo: str
    valor: Optional[float]
    confianca: Optional[str] = None
    status: str = "AVALIADO"
    sentido: Optional[str] = None
    itens: Tuple[Any, ...] = ()
    motivo: Optional[str] = None
    detalhe: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class MigrationPair:
    """Par agregado A -> B (ou B -> A em altas) ja ajustado por `k`; sem cliente."""

    sku: int
    same_supplier: bool
    net_rev: float
    net_clients: int
    affinity_score: float = 0.0
    descricao: Optional[str] = None
    fornecedor: Optional[str] = None


@dataclass(frozen=True)
class EvidencePackage:
    """Mapa canonico (snake_case) do diagnostico + data de referencia (fora do hash)."""

    data: Mapping[str, Any]
    data_referencia: date

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any], data_referencia: date) -> "EvidencePackage":
        return cls(data=copy.deepcopy(dict(mapping)), data_referencia=data_referencia)

    # --- acessos de leitura (Lei de Demeter)
    @property
    def sku(self) -> int:
        return int(self.data["produto"]["sku"])

    @property
    def metric(self) -> str:
        return self.data["janela"]["metrica"]

    @property
    def window(self) -> int:
        return int(self.data["janela"]["janela"])

    @property
    def base_month(self) -> str:
        return self.data["janela"]["mes_base"]

    @property
    def comparison_mode(self) -> str:
        return self.data["janela"]["modo_comparacao"]

    @property
    def mode(self) -> str:
        return self.data["modo_diagnostico"]

    @property
    def cell_status(self) -> Optional[str]:
        return self.data.get("cell_status")

    @property
    def direction(self) -> Optional[str]:
        return self.data.get("direcao")

    @property
    def variation_pct(self) -> Optional[float]:
        return self.data.get("variacao_pct")

    @property
    def revenue_delta(self) -> Optional[float]:
        return self.data.get("delta_receita")

    @property
    def residual_share(self) -> Optional[float]:
        return self.data.get("residual_share")

    @property
    def search_term_available(self) -> bool:
        produto = self.data["produto"]
        return bool(produto.get("funcao_primaria") or produto.get("categoria_galeria"))

    @property
    def market_classification(self) -> Optional[str]:
        market = self.data.get("diagnostico_mercado") or {}
        return market.get("classificacao")

    @property
    def indicators(self) -> List[Mapping[str, Any]]:
        return list(self.data.get("indicadores") or [])

    def has_evaluated_indicator(self, tipo: str) -> bool:
        return any(i.get("tipo") == tipo and i.get("status") == "AVALIADO" for i in self.indicators)

    @property
    def package_skus(self) -> FrozenSet[int]:
        skus = {self.sku}
        for afim in self.data.get("afins") or []:
            skus.add(int(afim["sku"]))
        for parcel in self.data.get("cascata") or []:
            for item in parcel.get("itens") or []:
                skus.add(int(item["sku"]))
        return frozenset(skus)

    @property
    def evaluated_types(self) -> FrozenSet[str]:
        types = {p["tipo"] for p in self.data.get("cascata") or [] if p.get("status") == "AVALIADO"}
        types |= {i["tipo"] for i in self.indicators if i.get("status") == "AVALIADO"}
        return frozenset(types)

    @property
    def parcel_values(self) -> Dict[str, float]:
        return {
            p["tipo"]: p["valor"]
            for p in self.data.get("cascata") or []
            if p.get("status") == "AVALIADO" and p.get("valor") is not None
        }


def _round_node(node: Any, key: str = "") -> Any:
    if isinstance(node, bool) or node is None or isinstance(node, (int, str)):
        return node
    if isinstance(node, float):
        decimals = HASH_SCORE_DECIMALS if key in _SCORE_KEYS else HASH_FLOAT_DECIMALS
        return round(node, decimals) + 0.0
    if isinstance(node, Mapping):
        return {str(k): _round_node(v, str(k)) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        rounded = [_round_node(v, key) for v in node]
        return sorted(rounded, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return str(node)


def canonical_evidence_json(evidence: EvidencePackage) -> str:
    """JSON canonico: floats arredondados, listas ordenadas, sem timestamps nem `dataReferencia` (P-175.7)."""
    canonical = _round_node(evidence.data)
    return json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_evidence_hash(evidence: EvidencePackage) -> str:
    """sha256 do pacote canonico: mesmo dado, mesmo hash (P-175)."""
    return hashlib.sha256(canonical_evidence_json(evidence).encode("utf-8")).hexdigest()
