"""
Serviço de Índice Incremental de Afinidade de Produtos (F6 v2.1 + Produto Novo).

Gerencia:
- Carga do índice persistido em disco (`data/cache/product_affinity_index.json`).
- Sincronização incremental diária às 00:00 (ou sob demanda): detecta SKUs novos,
  alterados e desativados via `content_hash`, recalcula apenas o necessário e remove
  produtos inativos.
- Consulta em O(1) da lista decrescente de afinidades por SKU para Canibalização e
  busca semântica para Produto Novo (cold start).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from src.modules.analytics.domain.product_affinity import (
    DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD,
    DEFAULT_TOP_K_AFFINITIES,
    MIN_STORED_AFFINITY_SCORE,
    _collect_all_supplier_tokens,
    _pair_compatibility_multiplier,
    _split_doc_channels,
    _vectorize_documents,
    build_affinity_document,
    build_sku_compatibility_profile,
    compute_affinity_matrix,
    compute_content_hash,
    compute_incremental_diff,
    compute_pair_affinity_score,
    detect_primary_function,
    find_similar_products_for_new_item,
    match_catalog_with_gallery,
)
from scipy.sparse import hstack
from sklearn.preprocessing import normalize
import numpy as np
from src.modules.analytics.repository import gallery_client, sales_repository

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INDEX_PATH: Path = _REPO_ROOT / "data" / "cache" / "product_affinity_index.json"

_AFFINITY_LOCK = threading.Lock()
_LOADED_INDEX: Optional[Dict[str, Any]] = None
_QUERY_VECTOR_CACHE: Optional[Dict[str, Any]] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def seconds_until_next_midnight(now: Optional[datetime] = None) -> float:
    """Retorna quantos segundos faltam até a próxima meia-noite (00:00:00) no horário local."""
    current = now or datetime.now()
    next_midnight = (current + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(1.0, (next_midnight - current).total_seconds())


def _load_index_from_disk(index_path: Path = DEFAULT_INDEX_PATH) -> Optional[Dict[str, Any]]:
    if not index_path.exists():
        return None
    try:
        with index_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("affinities"), dict):
            return data
    except Exception as exc:
        logger.warning("Índice de afinidade em disco inválido (%s); será reconstruído.", type(exc).__name__)
    return None


def _save_index_atomic(payload: Dict[str, Any], index_path: Path = DEFAULT_INDEX_PATH) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = index_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp_path, index_path)


def reset_product_affinity_memory_cache() -> None:
    """Limpa o cache em memória (apoio a testes)."""
    global _LOADED_INDEX, _QUERY_VECTOR_CACHE
    with _AFFINITY_LOCK:
        _LOADED_INDEX = None
        _QUERY_VECTOR_CACHE = None


def _get_or_build_query_vector_cache(index: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Cacheia em memória a matriz TF-IDF vetorizada e os tokens de fornecedor do índice carregado,
    evitando refazer `fit_transform` em ~2.000 produtos a cada simulação de Produto Novo (< 30ms/req).
    """
    global _QUERY_VECTOR_CACHE
    index_key = (id(index), str((index.get("meta") or {}).get("last_sync_at") or ""), len(index.get("skus") or {}))
    cached = _QUERY_VECTOR_CACHE
    if cached is not None and cached.get("key") == index_key:
        return cached

    skus_meta = index.get("skus") or {}
    valid_items = [
        (str(sku), str(meta.get("doc") or ""))
        for sku, meta in sorted(skus_meta.items())
        if isinstance(meta, dict) and str(meta.get("doc") or "").strip()
    ]
    if not valid_items:
        return None

    skus = [sku for sku, _ in valid_items]
    docs = [doc for _, doc in valid_items]
    matrix, vectorizers = _vectorize_documents(docs)
    core_vec = vectorizers[0]
    doc_cores, _ = _split_doc_channels(docs)
    core_matrix = normalize(core_vec.transform(doc_cores), norm="l2", axis=1)
    supplier_tokens = _collect_all_supplier_tokens(skus_meta)
    built = {
        "key": index_key,
        "skus": skus,
        "matrix": matrix,
        "core_matrix": core_matrix,
        "vectorizers": vectorizers,
        "supplier_tokens": supplier_tokens,
    }
    _QUERY_VECTOR_CACHE = built
    return built


def get_loaded_affinity_index(index_path: Path = DEFAULT_INDEX_PATH) -> Optional[Dict[str, Any]]:
    """Retorna o índice de afinidade carregado em memória (lendo do disco na 1ª chamada)."""
    global _LOADED_INDEX
    with _AFFINITY_LOCK:
        if _LOADED_INDEX is None:
            _LOADED_INDEX = _load_index_from_disk(index_path)
        return _LOADED_INDEX


def get_affinity_lookup_map(
    min_score: float = DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Retorna mapa `{sku_a: {sku_b: score}}` pronto para consulta O(1) em
    `compute_directional_migration`, ou `None` se o índice ainda não foi construído.
    """
    index = get_loaded_affinity_index(index_path)
    if index is None:
        return None
    raw_affinities = index.get("affinities") or {}
    lookup: Dict[str, Dict[str, float]] = {}
    for sku_a, neighbors in raw_affinities.items():
        filtered = {
            str(item["sku"]): float(item["score"])
            for item in neighbors
            if float(item.get("score", 0.0)) >= min_score
        }
        if filtered:
            lookup[str(sku_a)] = filtered
    return lookup


def sync_product_affinity_index(
    force: bool = False,
    index_path: Path = DEFAULT_INDEX_PATH,
    catalog_loader: Optional[Callable[[], Mapping[str, Mapping[str, Any]]]] = None,
    gallery_loader: Optional[Callable[[], Sequence[Mapping[str, Any]]]] = None,
    top_k: int = DEFAULT_TOP_K_AFFINITIES,
) -> Dict[str, Any]:
    """
    Executa a sincronização incremental do índice de afinidade de produtos:
    - Carrega índice anterior (se existir).
    - Lê catálogo ativo do ERP + galeria pública do fitoherb.com.br.
    - Detecta SKUs novos, alterados (por `content_hash`) e desativados.
    - Remove desativados, atualiza apenas novos/alterados e recalcula a matriz
      de afinidade somente quando houver alteração (ou `force=True`).
    """
    global _LOADED_INDEX
    started = time.perf_counter()

    fetch_catalog = catalog_loader or sales_repository.fetch_cannibalization_catalog
    fetch_gallery = gallery_loader or gallery_client.fetch_fitoherb_gallery_products

    catalog = fetch_catalog()
    gallery_items = fetch_gallery()
    gallery_matches = match_catalog_with_gallery(catalog, gallery_items)
    supplier_tokens = _collect_all_supplier_tokens(catalog, gallery_items)

    current_docs: Dict[str, str] = {}
    current_hashes: Dict[str, str] = {}
    current_skus_meta: Dict[str, Dict[str, Any]] = {}

    for sku_str, entry in catalog.items():
        if not entry.get("active", True):
            continue
        g_info = gallery_matches.get(sku_str) or {}
        doc_text = build_affinity_document(
            name=str(entry.get("description") or ""),
            gallery_name=str(g_info.get("gallery_name") or ""),
            gallery_description=str(g_info.get("gallery_description") or ""),
            gallery_category=str(g_info.get("gallery_category") or ""),
            presentation=g_info.get("presentation") or (),
            supplier_tokens=supplier_tokens,
        )
        content_hash = compute_content_hash(doc_text)
        current_docs[sku_str] = doc_text
        current_hashes[sku_str] = content_hash
        primary_fn = detect_primary_function(
            str(entry.get("description") or ""),
            str(g_info.get("gallery_description") or ""),
        )
        current_skus_meta[sku_str] = {
            "content_hash": content_hash,
            "doc": doc_text,
            "primary_function": primary_fn or "",
            "description": str(entry.get("description") or "").strip(),
            "supplier": str(entry.get("supplier") or "").strip(),
            "category": str(entry.get("category") or "").strip(),
            "current_price": float(entry.get("current_price") or 0.0),
            "gallery_matched": bool(g_info),
            "gallery_slug": str(g_info.get("gallery_slug") or ""),
            "gallery_category": str(g_info.get("gallery_category") or ""),
        }

    with _AFFINITY_LOCK:
        previous_index = _LOADED_INDEX if _LOADED_INDEX is not None else _load_index_from_disk(index_path)
        prev_skus = (previous_index or {}).get("skus") or {}
        previous_hashes = {
            str(sku): str(meta.get("content_hash") or "")
            for sku, meta in prev_skus.items()
            if isinstance(meta, dict)
        }
        diff = compute_incremental_diff(previous_hashes, current_hashes)

        prev_provider = str(((previous_index or {}).get("meta") or {}).get("provider") or "")
        recomputed = bool(
            force
            or previous_index is None
            or diff.has_changes
            or prev_provider != "tfidf_word_char_flavor_size_v2"
        )
        now_iso = _utc_now_iso()

        if recomputed:
            # Preserva metadados/doc de inalterados e atualiza apenas novos/alterados (desativados já foram excluídos)
            merged_skus: Dict[str, Dict[str, Any]] = {}
            for sku_str in current_hashes:
                if sku_str in diff.unchanged and sku_str in prev_skus and not force:
                    prev_meta = dict(prev_skus[sku_str])
                    # Atualiza preço/descrição de exibição se necessário, preservando `doc` e `content_hash`
                    prev_meta["current_price"] = current_skus_meta[sku_str]["current_price"]
                    merged_skus[sku_str] = prev_meta
                else:
                    meta_new = dict(current_skus_meta[sku_str])
                    meta_new["updated_at"] = now_iso
                    merged_skus[sku_str] = meta_new

            docs_for_matrix = {sku: str(meta.get("doc") or "") for sku, meta in merged_skus.items()}
            funcs_for_matrix = {
                sku: (str(meta.get("primary_function") or "") or None)
                for sku, meta in merged_skus.items()
            }
            profiles_for_matrix = {
                sku: build_sku_compatibility_profile(
                    description=str(meta.get("description") or ""),
                    primary_function=funcs_for_matrix[sku],
                    supplier_tokens=supplier_tokens,
                )
                for sku, meta in merged_skus.items()
            }
            affinities = compute_affinity_matrix(
                sku_documents=docs_for_matrix,
                top_k=top_k,
                min_score=MIN_STORED_AFFINITY_SCORE,
                sku_primary_functions=funcs_for_matrix,
                sku_profiles=profiles_for_matrix,
            )

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            new_index: Dict[str, Any] = {
                "meta": {
                    "last_sync_at": now_iso,
                    "provider": "tfidf_word_char_flavor_size_v2",
                    "total_active_skus": len(merged_skus),
                    "gallery_products_fetched": len(gallery_items),
                    "gallery_matched_skus": sum(1 for m in merged_skus.values() if m.get("gallery_matched")),
                    "added_count": len(diff.added),
                    "updated_count": len(diff.updated),
                    "removed_count": len(diff.removed),
                    "unchanged_count": len(diff.unchanged),
                    "recomputed": True,
                    "duration_ms": elapsed_ms,
                },
                "skus": merged_skus,
                "affinities": affinities,
            }
            _save_index_atomic(new_index, index_path)
            _LOADED_INDEX = new_index
            summary = dict(new_index["meta"])
        else:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            assert previous_index is not None
            prev_meta_block = dict(previous_index.get("meta") or {})
            prev_meta_block.update(
                {
                    "last_check_at": now_iso,
                    "added_count": 0,
                    "updated_count": 0,
                    "removed_count": 0,
                    "unchanged_count": len(diff.unchanged),
                    "recomputed": False,
                    "duration_ms": elapsed_ms,
                }
            )
            previous_index["meta"] = prev_meta_block
            _LOADED_INDEX = previous_index
            summary = prev_meta_block

    logger.info(
        "[AFFINITY-CRON] Sync concluído: ativos=%d gallery=%d matched=%d (+%d ~%d -%d) recomputed=%s (%dms)",
        int(summary.get("total_active_skus") or 0),
        int(summary.get("gallery_products_fetched") or 0),
        int(summary.get("gallery_matched_skus") or 0),
        int(summary.get("added_count") or 0),
        int(summary.get("updated_count") or 0),
        int(summary.get("removed_count") or 0),
        bool(summary.get("recomputed", False)),
        int(summary.get("duration_ms") or 0),
    )
    return summary


def get_product_affinities(
    sku: str,
    top_k: int = 20,
    index_path: Path = DEFAULT_INDEX_PATH,
) -> Optional[Dict[str, Any]]:
    """
    Retorna a lista em ordem decrescente dos produtos com maior afinidade com `sku`,
    enriquecida com nome, fornecedor, categoria e preço.
    """
    index = get_loaded_affinity_index(index_path)
    if index is None:
        return None

    sku_str = str(sku).strip()
    skus_meta = index.get("skus") or {}
    target = skus_meta.get(sku_str)
    if target is None:
        return None

    target_supplier = str(target.get("supplier") or "").strip().upper()
    raw_neighbors = (index.get("affinities") or {}).get(sku_str) or []
    items: List[Dict[str, Any]] = []
    for n in raw_neighbors[: max(1, int(top_k))]:
        n_sku = str(n["sku"])
        n_meta = skus_meta.get(n_sku)
        if not n_meta:
            continue
        n_sup = str(n_meta.get("supplier") or "").strip()
        items.append(
            {
                "sku": n_sku,
                "description": n_meta.get("description", ""),
                "supplier": n_sup,
                "category": n_meta.get("category", ""),
                "galleryCategory": n_meta.get("gallery_category", ""),
                "currentPrice": float(n_meta.get("current_price") or 0.0),
                "affinityScore": float(n["score"]),
                "sameSupplier": bool(target_supplier and n_sup.upper() == target_supplier),
            }
        )

    return {
        "sku": sku_str,
        "description": target.get("description", ""),
        "supplier": target.get("supplier", ""),
        "category": target.get("category", ""),
        "galleryMatched": bool(target.get("gallery_matched", False)),
        "affinities": items,
        "meta": index.get("meta") or {},
    }


def find_similar_for_new_product(
    name: str,
    description: str = "",
    category: str = "",
    top_k: int = 10,
    index_path: Path = DEFAULT_INDEX_PATH,
    auto_sync: bool = False,
    min_score: float = MIN_STORED_AFFINITY_SCORE,
) -> List[Dict[str, Any]]:
    """
    API de serviço compartilhada para Produto Novo (cold start):
    retorna os `top_k` produtos ativos mais afins a um produto candidato novo,
    aplicando as mesmas travas estruturais de compatibilidade (`build_sku_compatibility_profile`
    + `_pair_compatibility_multiplier`) usadas na matriz de canibalização.
    """
    index = get_loaded_affinity_index(index_path)
    if index is None and auto_sync:
        try:
            sync_product_affinity_index(index_path=index_path)
            index = get_loaded_affinity_index(index_path)
        except Exception as exc:
            logger.warning(
                "Fallback gracioso no cold start: falha ao sincronizar índice de afinidade (%s).",
                type(exc).__name__,
            )
            return []
    if index is None:
        return []

    skus_meta = index.get("skus") or {}
    vec_cache = _get_or_build_query_vector_cache(index)
    if vec_cache is None:
        return []

    supplier_tokens = vec_cache["supplier_tokens"]
    query_doc = build_affinity_document(
        name=name,
        gallery_name=name,
        gallery_description=description,
        gallery_category=category,
        supplier_tokens=supplier_tokens,
    )
    if not query_doc:
        return []

    core_vec, desc_word_vec, desc_char_vec = vec_cache["vectorizers"]
    q_cores, q_riches = _split_doc_channels([query_doc])
    q_core = normalize(core_vec.transform(q_cores), norm="l2", axis=1)
    q_word = normalize(desc_word_vec.transform(q_riches), norm="l2", axis=1)
    q_char = normalize(desc_char_vec.transform(q_riches), norm="l2", axis=1)
    q_vec = normalize(hstack([q_core * 0.80, q_word * 0.15, q_char * 0.05]).tocsr(), norm="l2", axis=1)

    # Usa max(core_cosine, full_cosine) no cold start para não penalizar produtos
    # que possuem descrição rica da galeria do site frente a produtos sem descrição.
    full_scores = (vec_cache["matrix"] @ q_vec.T).toarray().ravel()
    core_scores = (vec_cache["core_matrix"] @ q_core.T).toarray().ravel()
    scores = np.maximum(full_scores, core_scores)
    pool_k = min(len(scores), max(int(top_k) * 5, 50))
    if pool_k < len(scores):
        top_idx = np.argpartition(scores, -pool_k)[-pool_k:]
        order = top_idx[np.argsort(-scores[top_idx])]
    else:
        order = np.argsort(-scores)

    skus = vec_cache["skus"]
    raw_matches = [
        {"sku": skus[int(idx)], "score": round(float(scores[int(idx)]), 4)}
        for idx in order
        if float(scores[int(idx)]) >= min_score
    ]
    if not raw_matches:
        return []

    candidate_fn = detect_primary_function(name, description)
    candidate_profile = build_sku_compatibility_profile(
        description=name,
        primary_function=candidate_fn,
        supplier_tokens=supplier_tokens,
    )

    enriched: List[Dict[str, Any]] = []
    for m in raw_matches:
        sku_str = str(m["sku"])
        meta = skus_meta.get(sku_str) or {}
        cand_desc = str(meta.get("description") or "")
        cand_fn = str(meta.get("primary_function") or "") or detect_primary_function(cand_desc)
        cand_profile = build_sku_compatibility_profile(
            description=cand_desc,
            primary_function=cand_fn,
            supplier_tokens=supplier_tokens,
        )
        adjusted_score = compute_pair_affinity_score(
            base_semantic_score=float(m["score"]),
            prof_a=candidate_profile,
            prof_b=cand_profile,
        )
        if adjusted_score < min_score:
            continue
        enriched.append(
            {
                "sku": sku_str,
                "description": cand_desc,
                "supplier": str(meta.get("supplier") or ""),
                "category": str(meta.get("category") or ""),
                "currentPrice": float(meta.get("current_price") or 0.0),
                "affinityScore": adjusted_score,
            }
        )

    enriched.sort(key=lambda item: (-float(item["affinityScore"]), str(item["sku"])))
    return enriched[: max(1, int(top_k))]
