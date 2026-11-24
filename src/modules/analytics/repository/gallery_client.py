"""
Cliente HTTP somente leitura para a galeria pública de produtos do site fitoherb.com.br.

Consome `GET /products/gallery` paginado para enriquecer o índice de afinidade semântica
de produtos (usado pela Canibalização F6 e pela previsão de Produto Novo).
Nunca loga payloads completos e faz fallback gracioso caso o site esteja indisponível.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_GALLERY_API_URL: str = "https://fitoherb-backend-nkrtrtj5hq-uc.a.run.app/products/gallery"
DEFAULT_GALLERY_PAGE_SIZE: int = 100
DEFAULT_GALLERY_TIMEOUT_SECONDS: float = 30.0
MAX_GALLERY_PAGES: int = 100
MAX_PAGE_RETRIES: int = 2


def _extract_nested_name(obj: Any) -> str:
    if isinstance(obj, dict):
        return str(obj.get("name") or "").strip()
    if isinstance(obj, str):
        return obj.strip()
    return ""


def _normalize_gallery_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    flavours_raw = raw.get("flavours") or []
    presentation_raw = raw.get("presentation") or []
    flavours = [
        _extract_nested_name(x) for x in flavours_raw if _extract_nested_name(x)
    ] if isinstance(flavours_raw, list) else []
    presentation = [
        _extract_nested_name(x) for x in presentation_raw if _extract_nested_name(x)
    ] if isinstance(presentation_raw, list) else []

    return {
        "name": str(raw.get("name") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "category_name": _extract_nested_name(raw.get("category")),
        "supplier_name": _extract_nested_name(raw.get("supplier")),
        "slug": str(raw.get("slug") or "").strip(),
        "flavours": flavours,
        "presentation": presentation,
    }


def fetch_fitoherb_gallery_products(
    base_url: Optional[str] = None,
    page_size: int = DEFAULT_GALLERY_PAGE_SIZE,
    timeout_seconds: float = DEFAULT_GALLERY_TIMEOUT_SECONDS,
) -> List[Dict[str, Any]]:
    """
    Coleta todos os produtos públicos da galeria do fitoherb.com.br via paginação Spring (`page`, `size`).
    Retorna lista vazia em caso de indisponibilidade externa (fallback gracioso).
    """
    url = (base_url or os.getenv("FITOHERB_GALLERY_API_URL") or DEFAULT_GALLERY_API_URL).strip()
    items: List[Dict[str, Any]] = []
    headers = {"User-Agent": "FitoherbAnalyticsAffinityBot/1.0", "Accept": "application/json"}

    try:
        for page in range(MAX_GALLERY_PAGES):
            payload = None
            last_exc: Optional[Exception] = None
            for attempt in range(MAX_PAGE_RETRIES + 1):
                try:
                    with httpx.Client(headers=headers, timeout=timeout_seconds, follow_redirects=True) as client:
                        response = client.get(url, params={"page": page, "size": page_size})
                        response.raise_for_status()
                        payload = response.json()
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < MAX_PAGE_RETRIES:
                        continue
            if payload is None:
                raise last_exc or RuntimeError("Empty gallery payload")

            if isinstance(payload, list):
                content = payload
                is_last = True
            elif isinstance(payload, dict):
                content = payload.get("content") or []
                total_pages = payload.get("totalPages")
                is_last = bool(payload.get("last")) or (
                    isinstance(total_pages, int) and (page + 1) >= total_pages
                )
            else:
                break

            if not content:
                break

            for raw_item in content:
                if isinstance(raw_item, dict):
                    norm = _normalize_gallery_item(raw_item)
                    if norm["name"]:
                        items.append(norm)

            if is_last or len(content) < page_size:
                break
    except Exception as exc:
        logger.warning(
            "Falha ao consultar galeria pública do fitoherb.com.br (%s); usando apenas catálogo ERP.",
            type(exc).__name__,
        )
        return []

    logger.info("Galeria fitoherb.com.br sincronizada: %d produtos públicos lidos.", len(items))
    return items
