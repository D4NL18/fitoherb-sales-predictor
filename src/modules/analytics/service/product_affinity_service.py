"""
Serviço de Índice Incremental de Afinidade de Produtos (F6 v2.1 + Produto Novo).

Gerencia:
- Carga do índice persistido: em disco (`data/cache/product_affinity_index.json`) ou, com
  `AFFINITY_INDEX_GCS_URI`, no GCS com concorrência otimista (`AffinityIndexStore`, ADR-009 DA-06).
- Sincronização incremental (Cloud Scheduler 00:00 ou sob demanda, com lease no GCS): detecta SKUs novos,
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
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from src.core.object_storage import (
    GcsJsonStorage,
    ObjectPreconditionFailed,
    ObjectStorageUnavailable,
    NEW_OBJECT_GENERATION,
    parse_gcs_uri,
    release_lease,
    try_acquire_lease,
)
from src.modules.analytics.domain.product_affinity import (
    DEFAULT_CANNIBALIZATION_AFFINITY_THRESHOLD,
    DEFAULT_TOP_K_AFFINITIES,
    MIN_STORED_AFFINITY_SCORE,
    _collect_all_supplier_tokens,
    build_affinity_document,
    build_sku_compatibility_profile,
    compute_affinity_matrix,
    compute_content_hash,
    compute_incremental_diff,
    detect_primary_function,
    find_similar_products_for_new_item,
    match_catalog_with_gallery,
)
from src.modules.analytics.repository import gallery_client, sales_repository

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INDEX_PATH: Path = _REPO_ROOT / "data" / "cache" / "product_affinity_index.json"

_AFFINITY_LOCK = threading.Lock()
_LOADED_INDEX: Optional[Dict[str, Any]] = None
_LOADED_GENERATION: Optional[int] = None
_LAST_CHECK_AT: Optional[datetime] = None
_STORE_OVERRIDE: Optional["AffinityIndexStore"] = None
_GCS_STORES: Dict[str, "AffinityIndexStore"] = {}
_INDEX_CLOCK: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
_LISTENERS: List[Callable[[], None]] = []

AFFINITY_INDEX_GCS_URI_ENV = "AFFINITY_INDEX_GCS_URI"
AFFINITY_INDEX_REFRESH_MINUTES = 15
AFFINITY_SYNC_LEASE_PATH = "locks/affinity-sync.lock"
AFFINITY_SYNC_LEASE_TTL_SECONDS = 300


class AffinitySyncBusyError(Exception):
    """Outra sincronização do índice está em andamento (lease GCS ocupado)."""


class AffinityIndexConflictError(Exception):
    """O objeto do índice mudou durante a sincronização (412): nada foi sobrescrito."""


def _is_valid_index(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("affinities"), dict)


class LocalAffinityIndexStore:
    """Índice em arquivo local (comportamento original, sem refresh por geração nem lease)."""

    supports_refresh = False

    def __init__(self, index_path: Path):
        self._path = index_path

    def load(self) -> Optional[Tuple[Dict[str, Any], Optional[int]]]:
        data = _load_index_from_disk(self._path)
        return None if data is None else (data, None)

    def current_generation(self) -> Optional[int]:
        return None

    def save(self, payload: Dict[str, Any], expected_generation: Optional[int]) -> Optional[int]:
        _save_index_atomic(payload, self._path)
        return None

    def try_acquire_sync_lease(self) -> bool:
        return True

    def release_sync_lease(self) -> None:
        return None


class GcsAffinityIndexStore:
    """Índice em um objeto GCS: leitura por geração, escrita com `if_generation_match` e lease de sincronização."""

    supports_refresh = True

    def __init__(self, storage: GcsJsonStorage, path: str, clock: Callable[[], datetime]):
        self._storage = storage
        self.path = path
        self._clock = clock

    def load(self) -> Optional[Tuple[Dict[str, Any], Optional[int]]]:
        found = self._storage.read_json(self.path)
        if found is None or not _is_valid_index(found[0]):
            return None  # ausente ou inválido: nunca reconstrói na partida (P-130.5)
        return found[0], found[1]

    def current_generation(self) -> Optional[int]:
        return self._storage.get_generation(self.path)

    def save(self, payload: Dict[str, Any], expected_generation: Optional[int]) -> Optional[int]:
        match = NEW_OBJECT_GENERATION if expected_generation is None else expected_generation
        try:
            return self._storage.write_json(self.path, payload, if_generation_match=match)
        except ObjectPreconditionFailed:
            logger.warning("[AFFINITY] Conflito de geração (412) ao gravar o índice; nada foi sobrescrito.")
            raise AffinityIndexConflictError() from None

    def try_acquire_sync_lease(self) -> bool:
        return try_acquire_lease(self._storage, AFFINITY_SYNC_LEASE_PATH, AFFINITY_SYNC_LEASE_TTL_SECONDS, self._clock)

    def release_sync_lease(self) -> None:
        try:
            release_lease(self._storage, AFFINITY_SYNC_LEASE_PATH)
        except ObjectStorageUnavailable:
            logger.warning("[AFFINITY] Não foi possível liberar o lease; ele expira sozinho.")


AffinityIndexStore = Any  # contrato estrutural: LocalAffinityIndexStore e GcsAffinityIndexStore


def configure_index_store(store: Optional[AffinityIndexStore], clock: Optional[Callable[[], datetime]] = None) -> None:
    """Injeta um store (testes) ou limpa a injeção; `clock` controla a janela de refresh de 15 min."""
    global _STORE_OVERRIDE, _INDEX_CLOCK
    _STORE_OVERRIDE = store
    _GCS_STORES.clear()
    _INDEX_CLOCK = clock or (lambda: datetime.now(timezone.utc))


def register_index_changed_listener(listener: Callable[[], None]) -> None:
    """Avisado quando a geração do índice muda (ex.: limpar o cache do relatório de canibalização)."""
    if listener not in _LISTENERS:
        _LISTENERS.append(listener)


def clear_index_changed_listeners() -> None:
    _LISTENERS.clear()


def get_index_store(index_path: Path = DEFAULT_INDEX_PATH) -> AffinityIndexStore:
    """GCS quando `AFFINITY_INDEX_GCS_URI` existe e o caminho é o padrão; senão, o arquivo local (P-130.4)."""
    if _STORE_OVERRIDE is not None:
        return _STORE_OVERRIDE
    uri = os.getenv(AFFINITY_INDEX_GCS_URI_ENV, "").strip()
    if not uri or index_path != DEFAULT_INDEX_PATH:
        return LocalAffinityIndexStore(index_path)
    if uri not in _GCS_STORES:
        bucket, path = parse_gcs_uri(uri)
        _GCS_STORES[uri] = GcsAffinityIndexStore(GcsJsonStorage(bucket), path, _INDEX_CLOCK)
    return _GCS_STORES[uri]


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
    global _LOADED_INDEX, _LOADED_GENERATION, _LAST_CHECK_AT
    with _AFFINITY_LOCK:
        _LOADED_INDEX = None
        _LOADED_GENERATION = None
        _LAST_CHECK_AT = None


def _refresh_due() -> bool:
    return _LAST_CHECK_AT is None or _INDEX_CLOCK() - _LAST_CHECK_AT >= timedelta(minutes=AFFINITY_INDEX_REFRESH_MINUTES)


def _load_into_memory(store: AffinityIndexStore) -> None:
    """Carrega o índice do store; falha de armazenamento mantém o que já está em memória."""
    global _LOADED_INDEX, _LOADED_GENERATION, _LAST_CHECK_AT
    _LAST_CHECK_AT = _INDEX_CLOCK()
    try:
        loaded = store.load()
    except ObjectStorageUnavailable:
        logger.warning("[AFFINITY] Armazenamento do índice indisponível; mantendo o estado atual.")
        return
    _LOADED_INDEX, _LOADED_GENERATION = (None, None) if loaded is None else loaded


def _refresh_when_generation_changed(store: AffinityIndexStore) -> bool:
    """Só metadados a cada 15 min; recarrega quando a geração do objeto mudou. Devolve se houve mudança."""
    global _LAST_CHECK_AT
    _LAST_CHECK_AT = _INDEX_CLOCK()
    try:
        generation = store.current_generation()
    except ObjectStorageUnavailable:
        logger.warning("[AFFINITY] Não foi possível verificar a geração do índice; mantendo o atual.")
        return False
    if generation == _LOADED_GENERATION:
        return False
    _load_into_memory(store)
    return True


def get_loaded_generation() -> Optional[int]:
    """Geração do objeto GCS do índice em memória (`None` no armazenamento local ou sem índice)."""
    with _AFFINITY_LOCK:
        return _LOADED_GENERATION


def _notify_index_changed() -> None:
    for listener in list(_LISTENERS):
        listener()


def get_loaded_affinity_index(index_path: Path = DEFAULT_INDEX_PATH) -> Optional[Dict[str, Any]]:
    """Índice em memória: 1ª chamada lê do store; no GCS, relê quando a geração muda (≤ 1 vez a cada 15 min)."""
    changed = False
    with _AFFINITY_LOCK:
        store = get_index_store(index_path)
        if _LOADED_INDEX is None:
            if not store.supports_refresh or _refresh_due():
                _load_into_memory(store)
        elif store.supports_refresh and _refresh_due():
            changed = _refresh_when_generation_changed(store)
        index = _LOADED_INDEX
    if changed:
        _notify_index_changed()
    return index


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


def _previous_index_for_sync(store: AffinityIndexStore) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
    """Índice anterior + geração: no GCS sempre fresco (sob o lease); no local, a memória tem prioridade."""
    if not store.supports_refresh and _LOADED_INDEX is not None:
        return _LOADED_INDEX, _LOADED_GENERATION
    loaded = store.load()
    return (None, None) if loaded is None else loaded


def sync_product_affinity_index(
    force: bool = False,
    index_path: Path = DEFAULT_INDEX_PATH,
    catalog_loader: Optional[Callable[[], Mapping[str, Mapping[str, Any]]]] = None,
    gallery_loader: Optional[Callable[[], Sequence[Mapping[str, Any]]]] = None,
    top_k: int = DEFAULT_TOP_K_AFFINITIES,
) -> Dict[str, Any]:
    """
    Sincroniza o índice sob o lease do store (no GCS só uma instância sincroniza por vez).

    Raises:
        AffinitySyncBusyError: outra sincronização em andamento.
        AffinityIndexConflictError: o objeto mudou durante a sincronização; nada foi sobrescrito.
        ObjectStorageUnavailable: GCS inacessível.
    """
    store = get_index_store(index_path)
    if not store.try_acquire_sync_lease():
        raise AffinitySyncBusyError()
    try:
        return _run_sync(store, force, catalog_loader, gallery_loader, top_k)
    except AffinityIndexConflictError:
        with _AFFINITY_LOCK:
            _load_into_memory(store)
        _notify_index_changed()
        raise
    finally:
        store.release_sync_lease()


def _run_sync(
    store: AffinityIndexStore,
    force: bool = False,
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
    global _LOADED_INDEX, _LOADED_GENERATION
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
        previous_index, previous_generation = _previous_index_for_sync(store)
        prev_skus = (previous_index or {}).get("skus") or {}
        previous_hashes = {
            str(sku): str(meta.get("content_hash") or "")
            for sku, meta in prev_skus.items()
            if isinstance(meta, dict)
        }
        diff = compute_incremental_diff(previous_hashes, current_hashes)

        recomputed = bool(force or previous_index is None or diff.has_changes)
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
                    "provider": "tfidf_word_char_cosine_v1",
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
            _LOADED_GENERATION = store.save(new_index, previous_generation)
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
            _LOADED_GENERATION = previous_generation
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
) -> List[Dict[str, Any]]:
    """
    API de serviço compartilhada para a worktree de Produto Novo (cold start):
    retorna os `top_k` produtos ativos mais afins a um produto candidato novo.
    """
    index = get_loaded_affinity_index(index_path)
    if index is None:
        return []
    skus_meta = index.get("skus") or {}
    indexed_docs = {sku: str(meta.get("doc") or "") for sku, meta in skus_meta.items()}
    supplier_tokens = _collect_all_supplier_tokens(skus_meta)
    matches = find_similar_products_for_new_item(
        name=name,
        description=description,
        category=category,
        indexed_documents=indexed_docs,
        supplier_tokens=supplier_tokens,
        top_k=top_k,
    )
    enriched: List[Dict[str, Any]] = []
    for m in matches:
        meta = skus_meta.get(m["sku"]) or {}
        enriched.append(
            {
                "sku": m["sku"],
                "description": meta.get("description", ""),
                "supplier": meta.get("supplier", ""),
                "category": meta.get("category", ""),
                "currentPrice": float(meta.get("current_price") or 0.0),
                "affinityScore": float(m["score"]),
            }
        )
    return enriched
