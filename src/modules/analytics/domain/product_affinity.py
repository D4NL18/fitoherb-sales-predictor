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
import re
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple
import unicodedata

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.modules.analytics.domain.cannibalization_report import (
    _CANONICAL_SYNONYMS,
    _PRODUCT_TOKEN_STOPWORDS,
    _QUANTITY_UNIT_RE,
    _strip_accents,
    extract_product_family_tokens,
)

# ---------------------------------------------------------------------------
# Constantes Canônicas
# ---------------------------------------------------------------------------

DEFAULT_TOP_K_AFFINITIES: int = 25
MIN_STORED_AFFINITY_SCORE: float = 0.15
DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD: float = 0.25
GALLERY_MATCH_MIN_SCORE: float = 0.35

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
    clean = _strip_accents(str(text or "").lower())
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

    by_supplier_key: Dict[str, List[Tuple[Mapping[str, Any], FrozenSet[str]]]] = {}
    all_indexed: List[Tuple[Mapping[str, Any], str, FrozenSet[str]]] = []

    for item in gallery_items:
        sup_key = _norm_alnum_key(item.get("supplier_name", ""))
        name_tokens = _norm_tokens(item.get("name", ""))
        if not name_tokens:
            continue
        by_supplier_key.setdefault(sup_key, []).append((item, name_tokens))
        all_indexed.append((item, sup_key, name_tokens))

    matched: Dict[str, Dict[str, Any]] = {}
    for sku_str, entry in catalog.items():
        if not entry.get("active", True):
            continue
        erp_sup_key = _norm_alnum_key(entry.get("supplier", ""))
        erp_tokens = _norm_tokens(entry.get("description", ""))
        if not erp_tokens:
            continue

        # Candidatos do mesmo fornecedor (exato ou por prefixo/substring de nome comercial)
        candidates: List[Tuple[Mapping[str, Any], FrozenSet[str]]] = list(
            by_supplier_key.get(erp_sup_key, ())
        )
        if not candidates and erp_sup_key:
            for g_sup_key, items_list in by_supplier_key.items():
                if g_sup_key and (erp_sup_key in g_sup_key or g_sup_key in erp_sup_key):
                    candidates.extend(items_list)

        if not candidates:
            continue

        best_item: Optional[Mapping[str, Any]] = None
        best_score = 0.0
        for g_item, g_tokens in candidates:
            inter = len(erp_tokens & g_tokens)
            if inter == 0:
                continue
            union = len(erp_tokens | g_tokens)
            jaccard = inter / union
            erp_recall = inter / len(erp_tokens)
            score = 0.55 * jaccard + 0.45 * erp_recall
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
    combined = hstack([x_core * 0.60, x_desc_word * 0.30, x_desc_char * 0.10]).tocsr()
    return normalize(combined, norm="l2", axis=1), (core_vec, desc_word_vec, desc_char_vec)


def compute_affinity_matrix(
    sku_documents: Mapping[str, str],
    top_k: int = DEFAULT_TOP_K_AFFINITIES,
    min_score: float = MIN_STORED_AFFINITY_SCORE,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calcula a similaridade de cosseno entre todos os SKUs ativos e retorna, para cada SKU,
    a lista em ordem decrescente de afinidade (`[{"sku": ..., "score": ...}]`).
    """
    valid_items = [(sku, doc) for sku, doc in sorted(sku_documents.items()) if doc.strip()]
    if len(valid_items) < 2:
        return {sku: [] for sku in sku_documents}

    skus = [sku for sku, _ in valid_items]
    docs = [doc for _, doc in valid_items]
    matrix, _ = _vectorize_documents(docs)

    sim_matrix = (matrix @ matrix.T).toarray()
    np.fill_diagonal(sim_matrix, -1.0)

    affinities: Dict[str, List[Dict[str, Any]]] = {sku: [] for sku in sku_documents}
    n = len(skus)
    k = min(top_k, n - 1)

    for i, sku in enumerate(skus):
        row = sim_matrix[i]
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
    q_vec = normalize(hstack([q_core * 0.60, q_word * 0.30, q_char * 0.10]).tocsr(), norm="l2", axis=1)

    scores = (matrix @ q_vec.T).toarray().ravel()
    order = np.argsort(-scores)[:top_k]

    results: List[Dict[str, Any]] = []
    for idx in order:
        score = float(scores[idx])
        if score < min_score:
            break
        results.append({"sku": skus[idx], "score": round(score, 4)})
    return results
