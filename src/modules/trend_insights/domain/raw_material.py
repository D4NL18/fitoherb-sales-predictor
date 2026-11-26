"""
Assunto do radar externo (P-180.3, ADR-009 DA-13): materia-prima inferida de forma DETERMINISTICA, sem LLM, para
a chave de cache do radar ser estavel e compartilhavel. A descricao da galeria e dado nao confiavel: so e
COMPARADA com a lista fechada `RAW_MATERIAL_KEYWORDS` e nunca vira termo de busca nem vai ao prompt.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional

from src.modules.trend_insights.domain.evidence import EvidencePackage

SUBJECT_RAW_MATERIAL = "MATERIA_PRIMA"
SUBJECT_CATEGORY = "CATEGORIA"
MAX_SUBJECT_TERM_CHARS = 60
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NON_TERM_CHARS = re.compile(r"[^\w\s\-]", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Familias fundidas: `colageno_pele` e `colageno_tipo2` compartilham o mesmo radar (reduz ~15 para ~12 radares/mes).
PRIMARY_FUNCTION_RAW_MATERIAL_TERMS: Dict[str, str] = {
    "creatina": "creatina monohidratada",
    "pretreino": "cafeina e beta-alanina",
    "colageno_pele": "colageno hidrolisado",
    "colageno_tipo2": "colageno hidrolisado",
    "cha_infusao": "ervas e plantas medicinais",
    "whey": "soro de leite",
    "omega": "oleo de peixe",
    "termogenico": "cafeina e extratos termogenicos",
    "polivitaminico": "vitaminas e minerais",
}

# Palavras-chave fechadas (sem acento, minusculas) -> termo da materia-prima.
RAW_MATERIAL_KEYWORDS: Dict[str, str] = {
    "propolis": "propolis",
    "curcuma": "curcuma",
    "spirulina": "spirulina",
    "ginseng": "ginseng",
    "guarana": "guarana",
    "maca peruana": "maca peruana",
    "cavalinha": "cavalinha",
    "moringa": "moringa",
    "psyllium": "psyllium",
    "gengibre": "gengibre",
    "camomila": "camomila",
    "hibisco": "hibisco",
    "ashwagandha": "ashwagandha",
    "glutamina": "glutamina",
    "magnesio": "magnesio",
}


@dataclass(frozen=True)
class RadarSubject:
    slug: str
    termo: str
    tipo: str


def _ascii_lower(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def slugify(term: str) -> str:
    """Termo normalizado: minusculas, sem acento, separadores como hifen."""
    return _NON_ALNUM.sub("-", _ascii_lower(term)).strip("-")


def _clean_category(raw: Optional[str]) -> Optional[str]:
    """Categoria vem do ERP/galeria: so letras, digitos, espaco e hifen, tamanho limitado."""
    if not raw:
        return None
    cleaned = _SPACES.sub(" ", _NON_TERM_CHARS.sub(" ", raw)).strip().lower()[:MAX_SUBJECT_TERM_CHARS]
    return cleaned if slugify(cleaned) else None


def _keyword_term(description: Optional[str]) -> Optional[str]:
    haystack = _ascii_lower(description or "")
    for keyword, term in RAW_MATERIAL_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", haystack):
            return term
    return None


def _subject(term: str, kind: str) -> RadarSubject:
    return RadarSubject(slug=slugify(term), termo=term, tipo=kind)


def infer_radar_subject(evidence: EvidencePackage) -> Optional[RadarSubject]:
    """Funcao primaria, depois palavra-chave fechada, depois categoria/Tipo; `None` = SEM_TERMO_BUSCA."""
    produto = evidence.data["produto"]
    by_function = PRIMARY_FUNCTION_RAW_MATERIAL_TERMS.get(produto.get("funcao_primaria") or "")
    if by_function:
        return _subject(by_function, SUBJECT_RAW_MATERIAL)
    by_keyword = _keyword_term(produto.get("descricao_galeria"))
    if by_keyword:
        return _subject(by_keyword, SUBJECT_RAW_MATERIAL)
    category = _clean_category(produto.get("categoria_galeria")) or _clean_category(produto.get("tipo_catalogo"))
    return _subject(category, SUBJECT_CATEGORY) if category else None
