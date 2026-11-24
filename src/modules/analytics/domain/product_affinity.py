"""
Motor de Domínio Puro — Índice de Afinidade Semântica de Produtos (F6 v2.1 + Produto Novo).

Combina o catálogo ativo do ERP com as descrições ricas da galeria pública do fitoherb.com.br
para calcular uma matriz de afinidade semântica (ordem decrescente de score em [0, 1]) com
peso estritamente igual entre fornecedores (nomes de marcas/fornecedores são removidos do
texto vetorizado para eliminar viés de mesma marca).

Reutilizável por:
- Canibalização (F6): define substitutos reais entre qualquer fornecedor e pondera o fluxo.
- Produto Novo (Cold Start): encontra os produtos mais similares do portfólio ativo.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unicodedata

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.modules.analytics.domain.cannibalization_report import (
    _CANONICAL_SYNONYMS,
    _NEGATION_RE,
    _PRODUCT_TOKEN_STOPWORDS,
    _QUANTITY_UNIT_RE,
    _collapse_dotted_acronyms,
    _strip_accents,
    extract_product_family_tokens,
)

# ---------------------------------------------------------------------------
# Constantes Canônicas
# ---------------------------------------------------------------------------

DEFAULT_TOP_K_AFFINITIES: int = 25
MIN_STORED_AFFINITY_SCORE: float = 0.30
DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD: float = 0.50
GALLERY_MATCH_MIN_SCORE: float = 0.50

# Pesos compostos de afinidade (usados igualmente em Canibalização e Produto Novo):
# - 55% nome / função semântica (TF-IDF agnóstico de marca)
# - 25% sabor (mesmo sabor compete diretamente; sabores diferentes ainda competem com peso reduzido)
# - 20% conteúdo / quantidade (peso em g/kg/mg, volume em ml/l, nº de cápsulas ou nº de unidades/doses)
AFFINITY_WEIGHT_SEMANTIC: float = 0.55
AFFINITY_WEIGHT_FLAVOR: float = 0.25
AFFINITY_WEIGHT_SIZE: float = 0.20

# Famílias funcionais primárias mutuamente exclusivas (ordem de precedência explícita):
# - acessórios e barras vêm antes de whey/pretreino para evitar colisões (ex.: coqueteleira, crunch, whey bar);
# - colágeno é dividido entre articular (Tipo II), proteico e pele (Verisol/hidrolisado);
# - polivitamínico vem antes de ômega (ex.: POLI-VIT DE A-Z OMEGA);
# - pré-treino com cafeína vs sem cafeína são separados.
_PRIMARY_FUNCTION_MARKERS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("acessorio", ("coqueteleira", "shaker", "garrafa")),
    (
        "barraproteina",
        (
            "whey bar", "barra whey", "barra de proteina", "protein bar", "barraproteina",
            "crisp bar", "protein crisp", "havanna", "charge bar", "barra bold", "bold ",
            "crunch morango", "crunch cookies", "dark bar",
        ),
    ),
    ("barra_cereal", ("barra de cereais", "barra cereal", "barra de cereal")),
    ("whey_crisp", ("isocrisp",)),
    ("antisseptico_alcool", ("alcool gel", "alcool 70")),
    ("soro_fisiologico", ("soro fisiologico",)),
    ("agua_boricada", ("agua boricada",)),
    ("agua_oxigenada", ("agua oxigenada",)),
    ("antisseptico_iodo", ("farmaiodine",)),
    ("vinagre_maca", ("vinagre de maca", "vinagre maca")),
    ("vinagre_alcool", ("vinagre de alcool", "vinagre alcool")),
    ("vinagre", ("vinagre",)),
    ("oleo_essencial", ("oleo essencial",)),
    ("sabonete", ("sabonete",)),
    ("shampoo", ("shampoo",)),
    ("condicionador", ("condicionador",)),
    ("creme_cosmetico", ("creme ", "creme de ", "pomada")),
    ("oleo_capilar_corporal", ("oleo capilar", "capilar e corporal")),
    (
        "pretreino_sem_cafeina",
        ("pre-workout sem cafeina", "pre workout sem cafeina", "pretreino sem cafeina", "pre treino sem cafeina"),
    ),
    (
        "pretreino",
        (
            "pretreino", "pre treino", "pre-treino", "pre-workout", "pre workout",
            "bope", "horus", "egide", "bone crusher", "evora", "panic", "haze",
            "diabo verde", "venom", "psychotic", "steel pump",
        ),
    ),
    ("creatina_composta", ("dado de creatina", "gummy creatina", "creatina + beta", "creatina frutas", "creatina limao", "creatina maca")),
    ("creatina", ("creatina", "creapure")),
    ("whey", ("whey", "nutriwhey", "iso whey", "proteina do soro", "isofort plant")),
    ("hipercalorico", ("hipercalorico", "creamass", "hiper mass", "sinister mass", "mass 3kg")),
    ("polivitaminico_capilar", ("cabelos e unhas", "gummy hair")),
    ("polivitaminico_bariatrico", ("bariatrico",)),
    ("polivitaminico", ("polivitaminico", "poli-vit", "multivitaminico", "vitabond", "lavitan")),
    ("colageno_tipo2", ("colageno tipo ii", "colageno tipo 2", "colagentek tipo ii", "condro")),
    ("omega_coq10", ("coenzima q10 + omega", "q10 + omega")),
    ("omega_369", ("omega 3/6/9", "omega 3, 6", "omega plus 3,6", "omega 3,6")),
    ("omega", ("omega", "omegafor", "oleo de peixe")),
    ("colageno_protein", ("colagentek protein", "colageno protein")),
    ("colageno_pele", ("verisol", "colageno", "colagentek", "isofort beauty")),
    ("glutamina", ("glutamina", "glutamin")),
    ("bcaa", ("bcaa",)),
    ("pastaamendoim", ("pasta de amendoim", "pasta amendoim", "pastaamendoim")),
    ("termogenico", ("termogenico", "kimera", "thermo", "lipo", "termo plus")),
    ("cha_infusao", ("cha ", "desincha")),
)

_ALNUM_WORD_RE = re.compile(r"[a-z0-9]{2,}")
_ALPHA_WORD_RE = re.compile(r"[a-z]{3,}")
_GALLERY_DESCRIPTION_STOPWORDS: FrozenSet[str] = frozenset(
    {
        "que", "para", "com", "sem", "por", "uma", "uns", "umas", "dos", "das", "nos", "nas",
        "seu", "sua", "seus", "suas", "mais", "menos", "como", "tambem", "entre", "sobre",
        "produto", "produtos", "consumir", "consumo", "recomendacao", "indicacao", "modo",
        "usar", "uso", "diario", "diaria", "contem", "nao", "gluten", "lactose", "acucar",
        "ingredientes", "tabela", "nutricional", "porcao", "embalagem", "conservar", "local",
        "seco", "fresco", "criancas", "gestantes", "adultos", "saudavel", "dieta", "equilibrada",
        "suplemento", "alimentar", "formula", "formulado", "auxilia", "contribui", "ideal",
        "qualidade", "alto", "alta", "melhor", "dia", "apos", "antes", "durante", "agua",
    }
)


@dataclass(frozen=True)
class AffinityMatch:
    """Par de afinidade semântica ordenado por score decrescente."""

    sku: str
    score: float


@dataclass(frozen=True)
class IncrementalDiff:
    """Resumo de alterações do catálogo ativo entre execuções do cron diário."""

    added: FrozenSet[str]
    updated: FrozenSet[str]
    removed: FrozenSet[str]
    unchanged: FrozenSet[str]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)


def _norm_alnum_key(text: str) -> str:
    clean = _strip_accents(str(text or "").lower())
    return re.sub(r"[^a-z0-9]+", "", clean)


_UNIT_NORMALIZE_RE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(grs|gr|g|kg|mg|mcg|ml|capsulas|caps|cap|comp|unid|un)\b")


def _norm_tokens(text: str) -> FrozenSet[str]:
    clean = _collapse_dotted_acronyms(_strip_accents(str(text or "").lower()))
    def _canon_unit(m: re.Match) -> str:
        num = m.group(1).replace(",", ".")
        unit = m.group(2)
        if unit in ("grs", "gr"):
            unit = "g"
        elif unit in ("capsulas", "cap"):
            unit = "caps"
        elif unit == "unid":
            unit = "un"
        return f"{num}{unit}"
    clean = _UNIT_NORMALIZE_RE.sub(_canon_unit, clean)
    return frozenset(_ALNUM_WORD_RE.findall(clean))


def detect_primary_function(name: str, gallery_description: str = "") -> Optional[str]:
    """
    Detecta o objetivo funcional primário do produto a partir do nome comercial
    (e, se o nome for sigla/fantasia como `B.O.P.E.`, da primeira frase da descrição).
    Garante que pré-treinos, barras, acessórios e cosméticos não sejam confundidos.
    """
    norm_name = _collapse_dotted_acronyms(_strip_accents(str(name or "").lower()))
    for func_id, markers in _PRIMARY_FUNCTION_MARKERS:
        if any(m in norm_name for m in markers):
            return func_id
    # Fallback conservador: apenas pré-treino explícito na abertura da descrição
    # e nunca para cápsulas/chás/barras/acessórios.
    if not any(x in norm_name for x in ("caps", "cha ", "barra", "bar ", "crunch", "coqueteleira")):
        norm_desc_head = _collapse_dotted_acronyms(_strip_accents(str(gallery_description or "")[:180].lower()))
        if any(m in norm_desc_head for m in ("pre-treino", "pre treino", "pretreino")):
            return "pretreino"
    return None


_CRITICAL_MODIFIER_FLAGS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("zero", ("zero", "zero acucar", "zero-acucar")),
    ("kids", ("kids", "infantil", "peixinhos")),
    ("kit", ("kit ", "kit-")),
    ("proteica", ("proteica", "protein")),
    ("creapure", ("creapure",)),
    ("dark", ("dark",)),
    ("hair", ("hair",)),
    ("sem_cafeina", ("sem cafeina", "s/ cafeina")),
)

_FORM_BUCKETS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("acessorio", ("coqueteleira", "shaker", "garrafa")),
    ("sabonete", ("sabonete",)),
    ("shampoo", ("shampoo",)),
    ("condicionador", ("condicionador",)),
    ("creme", ("creme", "pomada")),
    ("oleo_essencial", ("oleo essencial",)),
    ("oleo_capilar", ("oleo capilar", "capilar e corporal")),
    ("antisseptico", ("alcool gel", "alcool 70", "agua boricada", "agua oxigenada", "soro fisiologico")),
    ("barra", ("barra", "bar ", "crunch", "whey bar")),
    ("goma", ("goma", "gomas", "gummy")),
    ("bala", ("bala", "balas", "cristais", "dado de")),
    ("spray", ("spray",)),
    ("cha_infusao", ("cha ", "desincha")),
    ("sache", ("sache", "saches")),
    ("caps", ("caps", "capsula", "capsulas", "cap ", "capsgel", "compr", "comp ", "cps", "softgel", "tablete")),
    ("gotas_liq", ("gotas", "xarope", "10ml", "20ml", "30ml", "100ml", "140ml", "200ml", "250ml", "400ml", "500ml", "680ml")),
    ("po", ("pote", "refil", "pouch", "po ", "farinha", "100g", "150g", "200g", "210g", "220g", "240g", "250g", "300g", "350g", "420g", "450g", "500g", "600g", "900g", "1kg", "1,2kg", "3kg")),
)


def _detect_form_bucket(text: str) -> str:
    norm = _collapse_dotted_acronyms(_strip_accents(str(text or "").lower()))
    # Chá em cápsula pertence ao bucket `caps`, não `cha_infusao`
    if any(m in norm for m in ("caps", "capsula", "capsulas", "compr", "cps")):
        return "caps"
    for form_id, markers in _FORM_BUCKETS:
        if any(m in norm for m in markers):
            return form_id
    return "other"


def _detect_modifiers(text: str) -> FrozenSet[str]:
    norm = _collapse_dotted_acronyms(_strip_accents(str(text or "").lower()))
    return frozenset(flag for flag, markers in _CRITICAL_MODIFIER_FLAGS if any(m in norm for m in markers))


def _has_compound_marker(text: str) -> bool:
    norm = _strip_accents(str(text or "").lower())
    # Ignora `c/ ziper` (embalagem) e `c/ almotolia`
    norm = norm.replace("c/ ziper", "").replace("c/ almotolia", "")
    return (" + " in norm) or ("+" in norm) or (" c/ " in norm) or (" com " in norm)


def _extract_negated_terms(text: str) -> FrozenSet[str]:
    norm = _collapse_dotted_acronyms(_strip_accents(str(text or "").lower()))
    return frozenset(m.group(1) for m in _NEGATION_RE.finditer(norm))


def _detect_audience_bucket(text: str) -> str:
    norm = _strip_accents(str(text or "").lower())
    if any(w in norm for w in ("kids", "infantil", "peixinhos")):
        return "kids"
    if "gestante" in norm:
        return "gestante"
    if "senior" in norm:
        return "senior"
    if "mulher" in norm or "femme" in norm:
        return "mulher"
    if "homem" in norm:
        return "homem"
    return "geral"


def _collect_all_supplier_tokens(
    catalog: Mapping[str, Mapping[str, Any]],
    gallery_items: Sequence[Mapping[str, Any]] = (),
) -> FrozenSet[str]:
    tokens: Set[str] = set()
    for entry in catalog.values():
        sup = _strip_accents(str(entry.get("supplier") or "").lower())
        tokens.update(_ALPHA_WORD_RE.findall(sup))
    for item in gallery_items:
        sup = _strip_accents(str(item.get("supplier_name") or "").lower())
        tokens.update(_ALPHA_WORD_RE.findall(sup))
    return frozenset(tokens)


def match_catalog_with_gallery(
    catalog: Mapping[str, Mapping[str, Any]],
    gallery_items: Sequence[Mapping[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Vincula cada SKU ativo do ERP ao produto correspondente na galeria pública
    do fitoherb.com.br usando fornecedor normalizado + sobreposição de tokens do nome.
    """
    if not gallery_items:
        return {}

    by_supplier_key: Dict[str, List[Tuple[Mapping[str, Any], FrozenSet[str], FrozenSet[str], str, FrozenSet[str], bool]]] = {}
    supplier_tokens = _collect_all_supplier_tokens(catalog, gallery_items)

    for item in gallery_items:
        sup_key = _norm_alnum_key(item.get("supplier_name", ""))
        name_raw = str(item.get("name") or "")
        name_tokens = _norm_tokens(name_raw)
        core_name_tokens = extract_product_family_tokens(name_raw, supplier_tokens)
        if not name_tokens or not core_name_tokens:
            continue
        g_form = _detect_form_bucket(name_raw)
        g_mods = _detect_modifiers(name_raw)
        g_comp = _has_compound_marker(name_raw)
        by_supplier_key.setdefault(sup_key, []).append((item, name_tokens, core_name_tokens, g_form, g_mods, g_comp))

    matched: Dict[str, Dict[str, Any]] = {}
    for sku_str, entry in catalog.items():
        if not entry.get("active", True):
            continue
        erp_sup_key = _norm_alnum_key(entry.get("supplier", ""))
        erp_desc = str(entry.get("description") or "")
        erp_tokens = _norm_tokens(erp_desc)
        erp_core = extract_product_family_tokens(erp_desc, supplier_tokens)
        if not erp_tokens or not erp_core:
            continue
        erp_form = _detect_form_bucket(erp_desc)
        erp_mods = _detect_modifiers(erp_desc)
        erp_comp = _has_compound_marker(erp_desc)

        # Candidatos do mesmo fornecedor (exato ou por prefixo/substring de nome comercial)
        candidates = list(by_supplier_key.get(erp_sup_key, ()))
        if not candidates and erp_sup_key:
            for g_sup_key, items_list in by_supplier_key.items():
                if g_sup_key and (erp_sup_key in g_sup_key or g_sup_key in erp_sup_key):
                    candidates.extend(items_list)

        if not candidates:
            continue

        best_item: Optional[Mapping[str, Any]] = None
        best_score = 0.0
        for g_item, g_tokens, g_core, g_form, g_mods, g_comp in candidates:
            core_inter = len(erp_core & g_core)
            if core_inter == 0:
                continue
            # Exige cobertura mínima dos tokens substantivos do produto (evita match só por embalagem/peso)
            core_recall = core_inter / len(erp_core)
            if core_recall < 0.50:
                continue
            # Trava de forma incompatível (ex.: mel sache vs spray, pó 150g vs cápsulas)
            if erp_form != "other" and g_form != "other" and erp_form != g_form:
                if not ({erp_form, g_form} <= {"po", "gotas_liq"}):
                    continue
            # Trava de modificadores críticos (zero, kids, kit, proteica, creapure, dark, hair, sem_cafeina)
            if erp_mods != g_mods:
                continue
            # Trava de composto vs isolado (evita MAGNESIO QUELATO -> CANELA DE VELHO C/ MAGNESIO)
            if erp_comp != g_comp and len(g_core - erp_core) > 0:
                continue

            inter = len(erp_tokens & g_tokens)
            union = len(erp_tokens | g_tokens)
            jaccard = inter / union
            erp_recall = inter / len(erp_tokens)
            score = 0.40 * jaccard + 0.30 * erp_recall + 0.30 * core_recall
            if score > best_score:
                best_score = score
                best_item = g_item

        if best_item is not None and best_score >= GALLERY_MATCH_MIN_SCORE:
            matched[sku_str] = {
                "gallery_slug": str(best_item.get("slug") or ""),
                "gallery_name": str(best_item.get("name") or ""),
                "gallery_description": str(best_item.get("description") or ""),
                "gallery_category": str(best_item.get("category_name") or ""),
                "presentation": list(best_item.get("presentation") or []),
                "match_score": round(best_score, 4),
            }

    return matched


_CORE_DESC_SEP = " ||| "


_CHA_NOISE_TOKENS: FrozenSet[str] = frozenset(
    {"cha", "sache", "saches", "misto", "ervas", "erva", "desincha", "infusao", "natural", "sabor", "especiarias"}
)


def _extract_tea_herb_tokens(name: str, supplier_tokens: FrozenSet[str]) -> FrozenSet[str]:
    norm = _collapse_dotted_acronyms(_strip_accents(str(name or "").lower()))
    for src, dst in _CANONICAL_SYNONYMS:
        if src in norm:
            norm = norm.replace(src, dst)
    norm = _QUANTITY_UNIT_RE.sub(" ", norm)
    return frozenset(
        w for w in _ALPHA_WORD_RE.findall(norm)
        if w not in _CHA_NOISE_TOKENS and w not in supplier_tokens and len(w) >= 3
    )


def build_affinity_document(
    name: str,
    gallery_name: str = "",
    gallery_description: str = "",
    gallery_category: str = "",
    presentation: Sequence[str] = (),
    supplier_tokens: FrozenSet[str] = frozenset(),
) -> str:
    """
    Monta o documento textual canônico de afinidade para um produto em dois canais
    (`<core_tokens> ||| <rich_description_and_category>`), removendo tokens de
    marca/fornecedor, sabores e ruído genérico para garantir peso igual entre fornecedores.
    """
    core_erp = sorted(extract_product_family_tokens(name, supplier_tokens))
    core_gal = sorted(extract_product_family_tokens(gallery_name, supplier_tokens)) if gallery_name else []

    desc_norm = _strip_accents(str(gallery_description or "").lower())
    for src, dst in _CANONICAL_SYNONYMS:
        if src in desc_norm:
            desc_norm = desc_norm.replace(src, dst)
    desc_norm = _QUANTITY_UNIT_RE.sub(" ", desc_norm)
    desc_words = [
        w
        for w in _ALPHA_WORD_RE.findall(desc_norm)
        if w not in _GALLERY_DESCRIPTION_STOPWORDS
        and w not in _PRODUCT_TOKEN_STOPWORDS
        and w not in supplier_tokens
    ]

    cat_norm = _strip_accents(str(gallery_category or "").lower())
    cat_words = [w for w in _ALPHA_WORD_RE.findall(cat_norm) if w not in supplier_tokens]

    pres_words: List[str] = []
    for p in presentation or ():
        p_norm = _strip_accents(str(p or "").lower())
        pres_words.extend(w for w in _ALPHA_WORD_RE.findall(p_norm) if w not in supplier_tokens)

    core_combined = sorted(set(core_erp) | set(core_gal))
    primary_fn = detect_primary_function(name, gallery_description)
    if primary_fn == "cha_infusao":
        herb_tokens = sorted(_extract_tea_herb_tokens(name, supplier_tokens))
        core_part = " ".join(["cha_infusao", *herb_tokens]) if herb_tokens else "cha_infusao"
    elif primary_fn:
        # Quando o produto pertence a uma função primária clara (ex.: creatina, pretreino, whey, omega),
        # usa a função primária como núcleo canônico para que sub-marcas/nomes fantasia (B.O.P.E., Horus,
        # Égide, 7Belo, Turbo) de fornecedores diferentes tenham afinidade alta entre si e zero ruído.
        core_part = primary_fn
    else:
        core_part = " ".join(core_combined)
    rich_parts: List[str] = []
    if desc_words:
        rich_parts.append(" ".join(desc_words[:120]))
    if cat_words:
        rich_parts.append(" ".join(cat_words))
    if pres_words:
        rich_parts.append(" ".join(pres_words[:20]))
    rich_part = " ".join(rich_parts)

    if not core_part and not rich_part:
        return ""
    return f"{core_part}{_CORE_DESC_SEP}{rich_part}"


def _split_doc_channels(documents: Sequence[str]) -> Tuple[List[str], List[str]]:
    cores: List[str] = []
    riches: List[str] = []
    for doc in documents:
        if _CORE_DESC_SEP in doc:
            c, r = doc.split(_CORE_DESC_SEP, 1)
            cores.append(c.strip() or r.strip())
            riches.append(r.strip() or c.strip())
        else:
            cores.append(doc.strip())
            riches.append(doc.strip())
    return cores, riches


def compute_content_hash(doc_text: str) -> str:
    """Hash determinístico SHA-256 do conteúdo canônico do produto (detecta alterações no cron)."""
    return hashlib.sha256(doc_text.encode("utf-8")).hexdigest()[:24]


def compute_incremental_diff(
    previous_hashes: Mapping[str, str],
    current_hashes: Mapping[str, str],
) -> IncrementalDiff:
    """Calcula exatamente quais SKUs foram adicionados, alterados, removidos ou mantidos."""
    prev_keys = set(previous_hashes.keys())
    curr_keys = set(current_hashes.keys())
    added = frozenset(curr_keys - prev_keys)
    removed = frozenset(prev_keys - curr_keys)
    common = curr_keys & prev_keys
    updated = frozenset(s for s in common if previous_hashes[s] != current_hashes[s])
    unchanged = frozenset(common - updated)
    return IncrementalDiff(
        added=added,
        updated=updated,
        removed=removed,
        unchanged=unchanged,
    )


def _vectorize_documents(documents: Sequence[str]):
    """
    Constrói representação vetorial esparsa em dois canais normalizados separadamente:
    - Canal Core (60%): identidade funcional do produto (sem marca/sabor/peso).
    - Canal Descrição Rica (40%): ingredientes, ativos e benefícios do fitoherb.com.br
      (30% word n-grams + 10% char_wb n-grams).
    """
    cores, riches = _split_doc_channels(documents)
    core_vec = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-z]{3,}\b",
    )
    desc_word_vec = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        token_pattern=r"(?u)\b[a-z]{3,}\b",
    )
    desc_char_vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        sublinear_tf=True,
    )
    x_core = normalize(core_vec.fit_transform(cores), norm="l2", axis=1)
    x_desc_word = normalize(desc_word_vec.fit_transform(riches), norm="l2", axis=1)
    x_desc_char = normalize(desc_char_vec.fit_transform(riches), norm="l2", axis=1)
    # Peso estrito: 80% identidade funcional principal + 20% descrição/ativos (evita que ingredientes
    # secundários ou descrições genéricas gerem afinidade artificial alta).
    combined = hstack([x_core * 0.80, x_desc_word * 0.15, x_desc_char * 0.05]).tocsr()
    return normalize(combined, norm="l2", axis=1), (core_vec, desc_word_vec, desc_char_vec)


_STRICT_TOKEN_REQUIRED_FUNCS: FrozenSet[str] = frozenset(
    {
        "cha_infusao",
        "oleo_essencial",
        "oleo_capilar_corporal",
    }
)
_TOPICAL_FORMS: FrozenSet[str] = frozenset({"sabonete", "shampoo", "condicionador", "creme", "oleo_capilar", "antisseptico"})
_EDIBLE_NON_CAPS_FORMS: FrozenSet[str] = frozenset({"barra", "goma", "bala", "cha_infusao", "sache", "spray"})

# Vocabulário canônico de sabores (multi-palavra primeiro para não fragmentar compostos).
_FLAVOR_PHRASES: Tuple[Tuple[str, str], ...] = (
    ("gelato di latte", "gelato"),
    ("chocolate branco", "chocolate_branco"),
    ("dark chocolate", "chocolate_amargo"),
    ("chocolate amargo", "chocolate_amargo"),
    ("chocolate ao leite", "chocolate"),
    ("chocolate belga", "chocolate"),
    ("chocolate suico", "chocolate"),
    ("milk caramel", "caramelo"),
    ("doce de leite", "doce_leite"),
    ("leite condensado", "leite_condensado"),
    ("leite ninho", "leite"),
    ("leite em po", "leite"),
    ("frutas vermelhas", "frutas_vermelhas"),
    ("frutas amarelas", "frutas_amarelas"),
    ("frutas tropicais", "frutas_tropicais"),
    ("torta de limao", "torta_limao"),
    ("cookies & cream", "cookies"),
    ("cookies and cream", "cookies"),
    ("cookies cream", "cookies"),
    ("sem sabor", "sem_sabor"),
    ("s/ sabor", "sem_sabor"),
    ("maca verde", "maca_verde"),
    ("algodao doce", "algodao_doce"),
    ("pao de mel", "pao_mel"),
    ("creme de avela", "avela"),
    ("cafe com leite", "cafe"),
    ("cha verde", "cha_verde"),
)

_FLAVOR_WORDS: Dict[str, str] = {
    "morango": "morango",
    "mor": "morango",
    "chocolate": "chocolate",
    "choco": "chocolate",
    "choc": "chocolate",
    "cacau": "chocolate",
    "baunilha": "baunilha",
    "baun": "baunilha",
    "vanilla": "baunilha",
    "cookies": "cookies",
    "cookie": "cookies",
    "gelato": "gelato",
    "pistache": "pistache",
    "banoffee": "banoffee",
    "caramelo": "caramelo",
    "caramel": "caramelo",
    "coco": "coco",
    "coconut": "coco",
    "limao": "limao",
    "lemon": "limao",
    "laranja": "laranja",
    "orange": "laranja",
    "uva": "uva",
    "grape": "uva",
    "abacaxi": "abacaxi",
    "melancia": "melancia",
    "watermelon": "melancia",
    "acai": "acai",
    "guarana": "guarana",
    "tangerina": "tangerina",
    "maracuja": "maracuja",
    "cafe": "cafe",
    "coffee": "cafe",
    "cappuccino": "cappuccino",
    "pacoca": "pacoca",
    "amendoim": "amendoim",
    "peanut": "amendoim",
    "beijinho": "beijinho",
    "brigadeiro": "brigadeiro",
    "brownie": "brownie",
    "churros": "churros",
    "truffle": "trufa",
    "trufa": "trufa",
    "milkshake": "milkshake",
    "neutro": "sem_sabor",
    "natural": "natural",
    "menta": "menta",
    "hortela": "menta",
    "gengibre": "gengibre",
    "canela": "canela",
    "citrus": "citrus",
    "citrico": "citrus",
    "maca": "maca",
    "pessego": "pessego",
    "manga": "manga",
    "kiwi": "kiwi",
    "framboesa": "framboesa",
    "amora": "amora",
    "cereja": "cereja",
    "banana": "banana",
    "avela": "avela",
    "napolitano": "napolitano",
    "iogurte": "iogurte",
    "yogurt": "iogurte",
    "chocomaltine": "chocomaltine",
    "ovomaltine": "chocomaltine",
    "milho": "milho",
    "pitaya": "pitaya",
    "jabuticaba": "jabuticaba",
    "hibisco": "hibisco",
    "mel": "mel",
    "leite": "leite",
}

_MULTIPACK_RE = re.compile(
    r"\b(\d+)\s*[xX]\s*(\d+(?:[.,]\d+)?)\s*(kg|grs|gr|g|mg|ml|l|lt|capsulas|caps|cap|comp|unid|un)?\b"
)
_SINGLE_SIZE_RE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*(kg|grs|gr|g|mg|ml|l|lt|capsulas|caps|cap|comp|comprimidos|tabletes|tabs|saches|sache|doses|dose|unid|un)\b"
)
_DISPLAY_PACK_MARKERS: Tuple[str, ...] = (
    "display", "sache", "saches", "monodose", "caixa", "cx ", "unidade", "avulso",
)


def _extract_flavor_tokens(description: str) -> FrozenSet[str]:
    """Extrai sabores normalizados presentes no nome comercial do produto."""
    norm = _collapse_dotted_acronyms(_strip_accents(str(description or "").lower()))
    found: Set[str] = set()
    working = norm
    for phrase, canonical in _FLAVOR_PHRASES:
        if phrase in working:
            found.add(canonical)
            working = working.replace(phrase, " ")
    for tok in re.findall(r"[a-z]{3,}", working):
        canonical = _FLAVOR_WORDS.get(tok)
        if canonical:
            found.add(canonical)
    return frozenset(found)


def _normalize_size_unit(amount: float, unit: str) -> Optional[Tuple[str, float]]:
    u = (unit or "").lower()
    if u == "kg":
        return ("mass", amount * 1000.0)
    if u in ("g", "gr", "grs"):
        return ("mass", amount)
    if u == "mg":
        return ("mass", amount / 1000.0)
    if u in ("l", "lt"):
        return ("volume", amount * 1000.0)
    if u == "ml":
        return ("volume", amount)
    if u in ("caps", "capsulas", "cap", "comp", "comprimidos", "tabletes", "tabs", "un", "unid", "sache", "saches", "dose", "doses"):
        return ("count", amount)
    return None


def _extract_size_signature(description: str) -> Tuple[Optional[str], Optional[float], bool]:
    """
    Extrai `(unit_family, total_amount_base, is_display_pack)` do nome comercial:
    - Ex.: `900 GRS` / `900G` -> `('mass', 900.0, False)`
    - Ex.: `1,2KG` -> `('mass', 1200.0, False)`
    - Ex.: `DISPLAY 10X30G` -> `('mass', 300.0, True)`
    - Ex.: `180 CAPS` -> `('count', 180.0, False)`
    """
    norm = _strip_accents(str(description or "").lower())
    is_display = any(marker in norm for marker in _DISPLAY_PACK_MARKERS)

    m_multi = _MULTIPACK_RE.search(norm)
    if m_multi:
        qty = float(m_multi.group(1))
        per_unit = float(m_multi.group(2).replace(",", "."))
        unit = m_multi.group(3) or ""
        norm_unit = _normalize_size_unit(qty * per_unit, unit)
        if norm_unit is not None:
            return (norm_unit[0], norm_unit[1], True)

    best_mass: Optional[float] = None
    best_vol: Optional[float] = None
    best_count: Optional[float] = None
    for m in _SINGLE_SIZE_RE.finditer(norm):
        val = float(m.group(1).replace(",", "."))
        unit = m.group(2)
        parsed = _normalize_size_unit(val, unit)
        if parsed is None or parsed[1] <= 0:
            continue
        fam, amt = parsed
        if fam == "mass":
            best_mass = max(best_mass or 0.0, amt)
        elif fam == "volume":
            best_vol = max(best_vol or 0.0, amt)
        elif fam == "count":
            best_count = max(best_count or 0.0, amt)

    if best_mass is not None:
        return ("mass", best_mass, is_display)
    if best_vol is not None:
        return ("volume", best_vol, is_display)
    if best_count is not None:
        return ("count", best_count, is_display)
    return (None, None, is_display)


def _compute_flavor_similarity(flavors_a: FrozenSet[str], flavors_b: FrozenSet[str]) -> float:
    """
    Similaridade de sabor em `[0, 1]`:
    - Ambos sem sabor (ex.: Creatina pura, Ômega 3): `1.00` (neutro sem penalização).
    - Mesmo sabor / interseção: `0.85..1.00` (Jaccard escalado).
    - Sabores diferentes: `0.20` (competem de forma secundária, abaixo do mesmo sabor).
    - Apenas um informa sabor: `0.55`.
    """
    if not flavors_a and not flavors_b:
        return 1.0
    if not flavors_a or not flavors_b:
        return 0.55
    overlap = flavors_a & flavors_b
    if overlap:
        jaccard = len(overlap) / len(flavors_a | flavors_b)
        return round(0.85 + 0.15 * jaccard, 4)
    return 0.20


def _compute_size_similarity(
    size_a: Tuple[Optional[str], Optional[float], bool],
    size_b: Tuple[Optional[str], Optional[float], bool],
) -> float:
    """
    Similaridade de peso / quantidade / volume em `[0, 1]`:
    - Mesma família de grandeza (`mass` em g/kg/mg, `volume` em ml/l, `count` em cápsulas/unidades/doses):
      `exp(-|ln(qtd_a) - ln(qtd_b)|)`.
      Ex.: 900g vs 900g = 1,00 · 900g vs 1,2kg = 0,75 · 900g vs 300g (10x30g) = 0,33 · 60 caps vs 120 caps = 0,50.
    - Sem medida em ambos: `0,85`; medida em apenas um: `0,65`; grandezas distintas: `0,30`.
    """
    fam_a, amt_a, _ = size_a
    fam_b, amt_b, _ = size_b
    if fam_a is None and fam_b is None:
        base = 0.85
    elif fam_a is None or fam_b is None:
        base = 0.65
    elif fam_a != fam_b:
        base = 0.30
    elif amt_a and amt_b and amt_a > 0 and amt_b > 0:
        base = math.exp(-abs(math.log(amt_a) - math.log(amt_b)))
    else:
        base = 0.65

    return round(max(0.0, min(1.0, base)), 4)


def build_sku_compatibility_profile(
    description: str,
    primary_function: Optional[str],
    supplier_tokens: FrozenSet[str] = frozenset(),
) -> Dict[str, Any]:
    """Extrai perfil estrutural leve para travas de compatibilidade, sabor e tamanho na matriz de afinidade."""
    if primary_function == "cha_infusao":
        core_tokens = _extract_tea_herb_tokens(description, supplier_tokens)
    else:
        core_tokens = extract_product_family_tokens(description, supplier_tokens)
    return {
        "primary_function": primary_function,
        "form": _detect_form_bucket(description),
        "audience": _detect_audience_bucket(description),
        "modifiers": _detect_modifiers(description),
        "is_compound": _has_compound_marker(description),
        "negated": _extract_negated_terms(description),
        "core_tokens": core_tokens,
        "flavors": _extract_flavor_tokens(description),
        "size": _extract_size_signature(description),
    }


def compute_pair_affinity_score(
    base_semantic_score: float,
    prof_a: Mapping[str, Any],
    prof_b: Mapping[str, Any],
) -> float:
    """
    Calcula o score final de afinidade em `[0.0, 1.0]` combinando:
    - Trava estrutural de compatibilidade (`_pair_compatibility_multiplier`);
    - 55% Nome / Função Semântica (`base_semantic_score`);
    - 25% Sabor (`_compute_flavor_similarity`);
    - 20% Tamanho / Embalagem (`_compute_size_similarity`).

    Utilizado de forma idêntica em Canibalização (F6) e Produto Novo (Cold Start).
    """
    mult = _pair_compatibility_multiplier(prof_a, prof_b)
    if mult <= 0.0:
        return 0.0

    sem = max(0.0, min(1.0, float(base_semantic_score)))
    flavors_a = prof_a.get("flavors") or frozenset()
    flavors_b = prof_b.get("flavors") or frozenset()
    size_a = prof_a.get("size") or (None, None, False)
    size_b = prof_b.get("size") or (None, None, False)

    flavor_sim = _compute_flavor_similarity(flavors_a, flavors_b)
    size_sim = _compute_size_similarity(size_a, size_b)

    combined = (
        AFFINITY_WEIGHT_SEMANTIC * sem
        + AFFINITY_WEIGHT_FLAVOR * flavor_sim
        + AFFINITY_WEIGHT_SIZE * size_sim
    ) * mult
    return round(max(0.0, min(1.0, combined)), 4)


def _pair_compatibility_multiplier(prof_a: Mapping[str, Any], prof_b: Mapping[str, Any]) -> float:
    """
    Retorna multiplicador de compatibilidade em `[0.0, 1.0]` entre dois produtos:
    - `0.0`: par estruturalmente incompatível (bloqueado).
    - `0.50`: composto multi-ativo vs mono-ativo (penalização forte).
    - `1.0`: par compatível.
    """
    fn_a = prof_a.get("primary_function")
    fn_b = prof_b.get("primary_function")
    if fn_a is not None and fn_b is not None and fn_a != fn_b:
        return 0.0
    # Se um tem função primária clara de categoria isolada (ex.: acessorio, barra, antisseptico, vinagre,
    # oleo_essencial, sabonete, creme_cosmetico, cha_infusao) e o outro não tem, bloqueia também.
    isolated_funcs = {
        "acessorio", "barraproteina", "barra_cereal", "whey_crisp", "antisseptico_alcool",
        "soro_fisiologico", "agua_boricada", "agua_oxigenada", "antisseptico_iodo",
        "vinagre_maca", "vinagre_alcool", "vinagre", "oleo_essencial", "sabonete",
        "shampoo", "condicionador", "creme_cosmetico", "oleo_capilar_corporal",
        "cha_infusao", "polivitaminico", "polivitaminico_capilar", "polivitaminico_bariatrico",
        "omega_coq10",
    }
    if (fn_a in isolated_funcs or fn_b in isolated_funcs) and fn_a != fn_b:
        return 0.0

    # Negação explícita (ex.: S/ ALCOOL vs ALCOOL, SEM CAFEINA vs CAFEINA)
    neg_a = prof_a.get("negated") or frozenset()
    neg_b = prof_b.get("negated") or frozenset()
    core_a = prof_a.get("core_tokens") or frozenset()
    core_b = prof_b.get("core_tokens") or frozenset()
    if (neg_a & core_b) or (neg_b & core_a):
        return 0.0

    # Público-alvo (Kids nunca casa com adulto; Homem/Mulher/Gestante/Senior isolados)
    aud_a = prof_a.get("audience", "geral")
    aud_b = prof_b.get("audience", "geral")
    if aud_a != aud_b:
        return 0.0

    # Modificador `zero` em barras/alimentos/balas
    mods_a = prof_a.get("modifiers") or frozenset()
    mods_b = prof_b.get("modifiers") or frozenset()
    if ("zero" in mods_a) != ("zero" in mods_b):
        return 0.0
    if ("proteica" in mods_a) != ("proteica" in mods_b):
        return 0.0

    # Forma física incompatível
    form_a = prof_a.get("form", "other")
    form_b = prof_b.get("form", "other")
    if form_a != "other" and form_b != "other" and form_a != form_b:
        if form_a == "acessorio" or form_b == "acessorio":
            return 0.0
        if form_a in _TOPICAL_FORMS or form_b in _TOPICAL_FORMS:
            return 0.0
        if form_a == "oleo_essencial" or form_b == "oleo_essencial":
            return 0.0
        if form_a in _EDIBLE_NON_CAPS_FORMS or form_b in _EDIBLE_NON_CAPS_FORMS:
            return 0.0
        # Cápsulas não competem com pó a granel/pote, óleo líquido ou spray
        if {form_a, form_b} & {"caps"} and {form_a, form_b} & {"po", "gotas_liq", "spray"}:
            return 0.0
        # Pó/farinha sólida não compete com líquido/óleo (ex.: farinha de linhaça vs óleo de linhaça, catuaba pó vs flaconete 10ml)
        if {form_a, form_b} == {"po", "gotas_liq"}:
            return 0.0

    # Exigência de ativo botânico/substantivo compartilhado em chás, óleos essenciais, capilares e produtos sem fn
    if (fn_a in _STRICT_TOKEN_REQUIRED_FUNCS) or (fn_a is None and fn_b is None):
        if core_a and core_b and not (core_a & core_b):
            return 0.0

    # Penalização forte quando um é composto multi-ativo (+ / c/) e o outro é isolado
    comp_a = bool(prof_a.get("is_compound"))
    comp_b = bool(prof_b.get("is_compound"))
    if comp_a != comp_b and core_a and core_b and (core_a != core_b):
        return 0.50

    return 1.0


def compute_affinity_matrix(
    sku_documents: Mapping[str, str],
    top_k: int = DEFAULT_TOP_K_AFFINITIES,
    min_score: float = MIN_STORED_AFFINITY_SCORE,
    sku_primary_functions: Optional[Mapping[str, Optional[str]]] = None,
    sku_profiles: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calcula a similaridade de cosseno entre todos os SKUs ativos e retorna, para cada SKU,
    a lista em ordem decrescente de afinidade (`[{"sku": ..., "score": ...}]`).

    Aplica travas rígidas de compatibilidade (`sku_profiles` / `sku_primary_functions`) para
    impedir falsos positivos entre funções, formas físicas, públicos ou compostos vs isolados.
    """
    valid_items = [(sku, doc) for sku, doc in sorted(sku_documents.items()) if doc.strip()]
    if len(valid_items) < 2:
        return {sku: [] for sku in sku_documents}

    skus = [sku for sku, _ in valid_items]
    docs = [doc for _, doc in valid_items]
    matrix, _ = _vectorize_documents(docs)

    sim_matrix = (matrix @ matrix.T).toarray()
    np.fill_diagonal(sim_matrix, -1.0)

    funcs = [
        (sku_primary_functions.get(sku) if sku_primary_functions else None)
        for sku in skus
    ]
    profiles = [
        (sku_profiles.get(sku) if sku_profiles else None)
        for sku in skus
    ]

    affinities: Dict[str, List[Dict[str, Any]]] = {sku: [] for sku in sku_documents}
    n = len(skus)
    k = min(top_k, n - 1)

    for i, sku in enumerate(skus):
        row = sim_matrix[i].copy()
        prof_i = profiles[i]
        func_i = funcs[i]

        for j in range(n):
            if i == j or row[j] < min_score:
                continue
            if prof_i is not None and profiles[j] is not None:
                scored = compute_pair_affinity_score(float(row[j]), prof_i, profiles[j])
                row[j] = scored if scored > 0.0 else -1.0
            elif func_i is not None and funcs[j] is not None and funcs[j] != func_i:
                row[j] = -1.0

        if k < n - 1:
            top_idx = np.argpartition(row, -k)[-k:]
            top_idx = top_idx[np.argsort(-row[top_idx])]
        else:
            top_idx = np.argsort(-row)[:k]

        neighbors: List[Dict[str, Any]] = []
        for j in top_idx:
            score = float(row[j])
            if score < min_score:
                break
            neighbors.append({"sku": skus[j], "score": round(score, 4)})
        affinities[sku] = neighbors

    return affinities


def find_similar_products_for_new_item(
    name: str,
    description: str,
    category: str,
    indexed_documents: Mapping[str, str],
    supplier_tokens: FrozenSet[str] = frozenset(),
    top_k: int = 10,
    min_score: float = MIN_STORED_AFFINITY_SCORE,
) -> List[Dict[str, Any]]:
    """
    Caso de uso Produto Novo (Cold Start): dado um produto ainda sem histórico de vendas,
    retorna os `top_k` produtos ativos mais afins em ordem decrescente de score.
    """
    query_doc = build_affinity_document(
        name=name,
        gallery_name=name,
        gallery_description=description,
        gallery_category=category,
        supplier_tokens=supplier_tokens,
    )
    if not query_doc:
        return []

    valid_items = [(sku, doc) for sku, doc in sorted(indexed_documents.items()) if doc.strip()]
    if not valid_items:
        return []

    skus = [sku for sku, _ in valid_items]
    docs = [doc for _, doc in valid_items]
    matrix, (core_vec, desc_word_vec, desc_char_vec) = _vectorize_documents(docs)

    q_cores, q_riches = _split_doc_channels([query_doc])
    q_core = normalize(core_vec.transform(q_cores), norm="l2", axis=1)
    q_word = normalize(desc_word_vec.transform(q_riches), norm="l2", axis=1)
    q_char = normalize(desc_char_vec.transform(q_riches), norm="l2", axis=1)
    q_vec = normalize(hstack([q_core * 0.80, q_word * 0.15, q_char * 0.05]).tocsr(), norm="l2", axis=1)

    scores = (matrix @ q_vec.T).toarray().ravel()
    order = np.argsort(-scores)[:top_k]

    results: List[Dict[str, Any]] = []
    for idx in order:
        score = float(scores[idx])
        if score < min_score:
            break
        results.append({"sku": skus[idx], "score": round(score, 4)})
    return results
