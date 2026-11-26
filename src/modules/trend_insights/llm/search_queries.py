"""
Consultas de busca SUGERIDAS (P-180, LGPD-TIA-12). Duas fontes, ambas por TABELA fixa (nunca texto livre do ERP
ou da galeria): as do radar externo (assunto + mes, sem dado da empresa) e a unica do produto (so sem radar).
O nome comercial do produto nunca e termo e nem "queda"/"alta" entram nas consultas (sem vies de confirmacao).
"""
import re
from typing import List, Optional

from src.modules.trend_insights.domain.constants import RADAR_MAX_SEARCH_QUERIES_SUGGESTED
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.raw_material import RadarSubject, infer_radar_subject

# `{mp}` = termo do assunto, `{mes_ano}` = "outubro de 2026", `{ano}` = "2026". 5 consultas (dimensoes 3+4+5 e 7+8 fundidas).
RADAR_QUERY_TEMPLATES = (
    "ANVISA {mp} {ano} tributo tarifa importação {mes_ano}",
    "safra {mp} clima {mes_ano}",
    "preço oferta demanda importação dólar frete {mp} {mes_ano}",
    "tendência consumo {mp} {mes_ano}",
    "{mp} lançamento preço concorrência {mes_ano}",
)
MONTH_NAMES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
UF_NAMES = {
    "AC": "Acre", "AL": "Alagoas", "AP": "Amapá", "AM": "Amazonas", "BA": "Bahia", "CE": "Ceará",
    "DF": "Distrito Federal", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão", "MT": "Mato Grosso",
    "MS": "Mato Grosso do Sul", "MG": "Minas Gerais", "PA": "Pará", "PB": "Paraíba", "PR": "Paraná",
    "PE": "Pernambuco", "PI": "Piauí", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RS": "Rio Grande do Sul", "RO": "Rondônia", "RR": "Roraima", "SC": "Santa Catarina", "SP": "São Paulo",
    "SE": "Sergipe", "TO": "Tocantins",
}
_COMPANY_SUFFIX = re.compile(r"\b(ltda|eireli|me|epp|s\.?a\.?)\b\.?", re.IGNORECASE)
_SHARE_CLASSES = ("PERDA_DE_PARTICIPACAO", "GANHO_DE_PARTICIPACAO")
_MARKET_CLASSES = ("MERCADO_EM_QUEDA", "MERCADO_EM_ALTA")


def _month_year(base_month: str) -> str:
    return f"{MONTH_NAMES[int(base_month[5:7]) - 1]} de {base_month[:4]}"


def build_radar_queries(subject: RadarSubject, base_month: str) -> List[str]:
    """Ate 5 consultas do radar, so com o termo do assunto e o mes-base."""
    values = {"mp": subject.termo, "mes_ano": _month_year(base_month), "ano": base_month[:4]}
    return [template.format(**values) for template in RADAR_QUERY_TEMPLATES][:RADAR_MAX_SEARCH_QUERIES_SUGGESTED]


def _supplier_name(evidence: EvidencePackage) -> Optional[str]:
    raw = evidence.data["produto"].get("fornecedor")
    if not raw:
        return None
    return re.sub(r"\s+", " ", _COMPANY_SUFFIX.sub("", raw)).strip().lower() or None


def _concentration_uf_name(evidence: EvidencePackage) -> Optional[str]:
    for indicator in evidence.indicators:
        if indicator.get("tipo") == "REGIONAL" and indicator.get("status") == "AVALIADO":
            return UF_NAMES.get((indicator.get("evidencia") or {}).get("ufConcentradora") or "")
    return None


def build_product_query(evidence: EvidencePackage) -> Optional[str]:
    """A unica consulta do produto (P-180.1): participacao -> fornecedor; mercado/REGIONAL -> UF; demais -> lancamento."""
    subject = infer_radar_subject(evidence)
    if subject is None:
        return None
    year, supplier, classification = evidence.base_month[:4], _supplier_name(evidence), evidence.market_classification
    uf_name = _concentration_uf_name(evidence)
    if classification in _SHARE_CLASSES and supplier:
        return f"{supplier} {subject.termo} {year}"
    if uf_name and (classification in _MARKET_CLASSES or classification is None):
        return f"{subject.termo} {uf_name} {_month_year(evidence.base_month)}"
    return f"{subject.termo} {supplier} lançamento {year}" if supplier else f"{subject.termo} lançamento {year}"
