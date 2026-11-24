"""
Consultas de busca SUGERIDAS no prompt (P-180, LGPD-TIA-12): so termos de categoria, fornecedor e periodo.
O nome comercial do produto nunca e termo principal e nada de cliente entra.
"""
import re
from typing import List, Optional

from src.modules.trend_insights.domain.constants import (
    MAX_SEARCH_QUERIES,
    MAX_SEARCH_QUERIES_QUALITATIVE,
    MODE_QUALITATIVE,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage

PRIMARY_FUNCTION_SEARCH_TERMS = {
    "creatina": "creatina",
    "pretreino": "pré-treino",
    "colageno_pele": "colágeno hidrolisado",
    "colageno_tipo2": "colágeno tipo 2",
    "cha_infusao": "chás e infusões",
    "whey": "whey protein",
    "omega": "ômega 3 óleo de peixe",
    "termogenico": "termogênico",
    "polivitaminico": "polivitamínico",
}
_COMPANY_SUFFIX = re.compile(r"\b(ltda|eireli|me|epp|s\.?a\.?)\b\.?", re.IGNORECASE)
_MARKET_CLASSES = ("MERCADO_EM_QUEDA", "MERCADO_EM_ALTA")
_SHARE_CLASSES = ("PERDA_DE_PARTICIPACAO", "GANHO_DE_PARTICIPACAO")


def _category_term(evidence: EvidencePackage) -> Optional[str]:
    produto = evidence.data["produto"]
    function = produto.get("funcao_primaria")
    return PRIMARY_FUNCTION_SEARCH_TERMS.get(function) or produto.get("categoria_galeria") or function


def _supplier_name(evidence: EvidencePackage) -> Optional[str]:
    raw = evidence.data["produto"].get("fornecedor")
    if not raw:
        return None
    return re.sub(r"\s+", " ", _COMPANY_SUFFIX.sub("", raw)).strip().lower() or None


def _year(evidence: EvidencePackage) -> str:
    return evidence.base_month[:4]


def build_search_queries(evidence: EvidencePackage) -> List[str]:
    """1 a 2 consultas (1 no modo qualitativo), em ordem de prioridade."""
    term = _category_term(evidence)
    if not term:
        return []
    year = _year(evidence)
    supplier = _supplier_name(evidence)
    classification = evidence.market_classification
    queries: List[str] = []
    if classification in _MARKET_CLASSES or classification is None or classification not in _SHARE_CLASSES:
        queries.append(f"{term} preço matéria-prima {year}")
    if supplier and classification not in _MARKET_CLASSES:
        queries.append(f"{supplier} {term} {year}")
    queries.append(f"{term} mercado {year}")
    limit = MAX_SEARCH_QUERIES_QUALITATIVE if evidence.mode == MODE_QUALITATIVE else MAX_SEARCH_QUERIES
    return list(dict.fromkeys(queries))[:limit]
