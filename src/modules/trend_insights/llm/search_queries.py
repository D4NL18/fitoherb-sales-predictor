"""
Consultas de busca SUGERIDAS no prompt (P-180, LGPD-TIA-12): so termos de categoria, fornecedor e periodo.
O nome comercial do produto nunca e termo principal e nada de cliente entra.
"""
import re
from typing import List, Optional

from src.modules.trend_insights.domain.constants import (
    MAX_SEARCH_QUERIES,
    MAX_SEARCH_QUERIES_PAID,
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


def search_query_limit(evidence: EvidencePackage, is_paid_search: bool) -> int:
    """
    Consultas sugeridas: 2, ou 1 no modo qualitativo (sinal fraco) e quando a cota gratis do mes acabou
    (cada consulta passa a custar). A API nao impoe o limite; ele e uma sugestao no prompt (CP-2).
    """
    if evidence.mode == MODE_QUALITATIVE:
        return MAX_SEARCH_QUERIES_QUALITATIVE
    return MAX_SEARCH_QUERIES_PAID if is_paid_search else MAX_SEARCH_QUERIES


def build_search_queries(evidence: EvidencePackage, limit: Optional[int] = None) -> List[str]:
    """Ate `limit` consultas (padrao: search_query_limit, cota gratis), em ordem de prioridade."""
    if limit is None:
        limit = search_query_limit(evidence, False)
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
    return list(dict.fromkeys(queries))[:limit]
