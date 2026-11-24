"""
Pacote de evidencias enviado ao LLM, montado por LISTA BRANCA (P-179, LGPD-TIA-03..06).
Nada de cliente, custo unitario ou contagem pequena exata entra; o pacote tem no maximo 8.000 caracteres.
A descricao da galeria NAO vai neste JSON: segue em bloco proprio, delimitado e sanitizado (P-184).
"""
import json
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional

from src.modules.trend_insights.domain.constants import (
    EXTERNAL_SOURCE_LOOKBACK_DAYS,
    MAX_AFFINES_IN_PAYLOAD,
    MAX_EVIDENCE_PAYLOAD_CHARS,
    MAX_GALLERY_DESCRIPTION_CHARS,
    MAX_MIGRATION_PAIRS_IN_PAYLOAD,
    MAX_UFS_IN_PAYLOAD,
    MIN_GALLERY_DESCRIPTION_CHARS,
    MIN_PARCEL_SHARE_IN_PAYLOAD,
)
from src.modules.trend_insights.domain.evidence import EvidencePackage
from src.modules.trend_insights.domain.privacy import format_small_count

PRODUCT_DESCRIPTION_CHARS = 80
AFFINE_DESCRIPTION_CHARS = 30
MIN_DESCRIPTION_CHARS_AFTER_TRIM = 12
_HTML_TAG = re.compile(r"<[^>]*>")
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL = re.compile(r"\S+@\S+")
_BLOCKED_CHARS = re.compile(r"[<>{}`]")
_PUNCT_RUN = re.compile(r"([^\w\s])\1{2,}")
_SPACES = re.compile(r"\s+")
_DELIMITER_FRAGMENT = re.compile(r"descricao_galeria\w*", re.IGNORECASE)


def sanitize_gallery_description(text: Optional[str]) -> Optional[str]:
    """P-184.2: sem HTML, URL, e-mail, delimitadores ou crases; ate 500 caracteres; descarta se sobrar pouco."""
    if not text:
        return None
    cleaned = _HTML_TAG.sub(" ", text)
    cleaned = _URL.sub(" ", _EMAIL.sub(" ", cleaned))
    cleaned = _DELIMITER_FRAGMENT.sub(" ", cleaned)
    cleaned = _BLOCKED_CHARS.sub(" ", cleaned)
    cleaned = _PUNCT_RUN.sub(r"\1", cleaned)
    cleaned = _SPACES.sub(" ", cleaned).strip()
    if len(cleaned) > MAX_GALLERY_DESCRIPTION_CHARS:
        cleaned = cleaned[:MAX_GALLERY_DESCRIPTION_CHARS].rsplit(" ", 1)[0]
    return cleaned if len(cleaned) >= MIN_GALLERY_DESCRIPTION_CHARS else None


def _clean_text(text: Optional[str], limit: int) -> Optional[str]:
    if not text:
        return None
    return _BLOCKED_CHARS.sub("", str(text))[:limit].strip() or None


def _compact(node: Any) -> Any:
    """Omite None, vazios e zeros (P-179): menos tokens, mesmo significado."""
    if isinstance(node, dict):
        cleaned = {k: _compact(v) for k, v in node.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, [], {}, 0, 0.0, "")}
    if isinstance(node, list):
        return [_compact(v) for v in node]
    return node


def _round_money(value: Optional[float]) -> Optional[int]:
    return None if value is None else int(round(value))


def _round_pct(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 1)


def _pair_payload(item: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "sku": item["sku"],
        "descricao": _clean_text(item.get("descricao"), AFFINE_DESCRIPTION_CHARS),
        "mesmoFornecedor": bool(item.get("same_supplier")),
        "receitaMigrada": _round_money(item.get("receita_migrada")),
        "clientesMigrados": format_small_count(int(item.get("clientes_migrados") or 0)),
        "confianca": item.get("confianca"),
    }


def _parcel_payload(parcel: Mapping[str, Any]) -> Dict[str, Any]:
    pairs = sorted(parcel.get("itens") or [], key=lambda i: -(i.get("receita_migrada") or 0.0))
    return {
        "tipo": parcel["tipo"],
        "valor": _round_money(parcel.get("valor")),
        "sentido": parcel.get("sentido"),
        "confianca": parcel.get("confianca"),
        "cortada": bool(parcel.get("cortada")),
        "pares": [_pair_payload(i) for i in pairs[:MAX_MIGRATION_PAIRS_IN_PAYLOAD]],
    }


def _split_parcels(evidence: EvidencePackage) -> Dict[str, Any]:
    delta = abs(evidence.data.get("delta_observado") or 0.0)
    relevant: List[Dict[str, Any]] = []
    others: List[str] = []
    for parcel in evidence.data.get("cascata") or []:
        value = parcel.get("valor")
        is_relevant = parcel.get("status") == "AVALIADO" and (
            value is None or abs(value) >= MIN_PARCEL_SHARE_IN_PAYLOAD * delta
        )
        if is_relevant:
            relevant.append(_parcel_payload(parcel))
        else:
            others.append(parcel["tipo"])
    return {"cascata": relevant, "naoRelevantes": sorted(others)}


def _afins_payload(evidence: EvidencePackage) -> List[Dict[str, Any]]:
    afins = sorted(evidence.data.get("afins") or [], key=lambda a: (-(a.get("affinity_score") or 0.0), a["sku"]))
    return [
        {
            "sku": a["sku"],
            "descricao": _clean_text(a.get("descricao"), AFFINE_DESCRIPTION_CHARS),
            "fornecedor": _clean_text(a.get("fornecedor"), 30),
            "score": round(a.get("affinity_score") or 0.0, 2),
            "mesmoFornecedor": bool(a.get("same_supplier")),
            "variacaoPct": _round_pct(a.get("variacao_pct")),
            "ganhouClientesDeA": bool(a.get("ganhou_clientes_do_produto")),
        }
        for a in afins[:MAX_AFFINES_IN_PAYLOAD]
    ]


def _market_payload(evidence: EvidencePackage) -> Dict[str, Any]:
    market = evidence.data.get("diagnostico_mercado") or {}
    return {
        "classe": market.get("classificacao"),
        "vMercadoPct": _round_pct(market.get("variacao_mercado_pct")),
        "efeitoMercado": _round_money(market.get("efeito_mercado")),
        "efeitoParticipacao": _round_money(market.get("efeito_participacao")),
        "deltaParticipacaoPp": _round_pct(market.get("variacao_participacao_pp")),
    }


def _indicators_payload(evidence: EvidencePackage) -> List[Dict[str, Any]]:
    return [
        {"tipo": i["tipo"], "sentido": i.get("sentido"), "uf": (i.get("evidencia") or {}).get("ufConcentradora")}
        for i in evidence.indicators
        if i.get("status") == "AVALIADO"
    ]


def _regions_payload(evidence: EvidencePackage) -> List[Dict[str, Any]]:
    regions = sorted(evidence.data.get("regional") or [], key=lambda r: -abs(r.get("delta") or 0.0))
    return [{"uf": r["uf"], "delta": _round_money(r.get("delta"))} for r in regions[:MAX_UFS_IN_PAYLOAD + 1]]


def _source_period(evidence: EvidencePackage) -> Dict[str, str]:
    previous_start = date.fromisoformat(evidence.data["janela"]["anterior"]["inicio"])
    start = previous_start - timedelta(days=EXTERNAL_SOURCE_LOOKBACK_DAYS)
    return {"inicio": start.isoformat(), "fim": evidence.data_referencia.isoformat()}


def _build_dict(evidence: EvidencePackage) -> Dict[str, Any]:
    produto = evidence.data["produto"]
    janela = evidence.data["janela"]
    payload = {
        "produto": {
            "sku": produto["sku"],
            "descricao": _clean_text(produto.get("descricao"), PRODUCT_DESCRIPTION_CHARS),
            "fornecedor": _clean_text(produto.get("fornecedor"), 40),
            "categoriaGaleria": _clean_text(produto.get("categoria_galeria"), 40),
            "funcaoPrimaria": produto.get("funcao_primaria"),
        },
        "janela": {"meses": janela["janela"], "modo": janela["modo_comparacao"], "mesBase": janela["mes_base"],
                   "atual": janela["atual"], "anterior": janela["anterior"], "fontes": _source_period(evidence)},
        "metrica": evidence.metric,
        "modo": evidence.mode,
        "direcao": evidence.direction,
        "variacaoPct": _round_pct(evidence.variation_pct),
        "residuo": {"valor": _round_money(evidence.data.get("residuo")),
                    "fracao": round(evidence.residual_share or 0.0, 2)},
        "diagnosticoMercado": _market_payload(evidence),
        "indicadores": _indicators_payload(evidence),
        "regioes": _regions_payload(evidence),
        "afins": _afins_payload(evidence),
    }
    payload.update(_split_parcels(evidence))
    return payload


def _dump(payload: Mapping[str, Any]) -> str:
    return json.dumps(_compact(payload), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _shrink_once(payload: Dict[str, Any]) -> bool:
    """Ordem de corte: afins de menor score, depois pares de migracao, depois descricoes (registrado pelo chamador)."""
    if len(payload["afins"]) > 1:
        payload["afins"].pop()
        return True
    for parcel in payload["cascata"]:
        if len(parcel.get("pares", [])) > 1:
            parcel["pares"].pop()
            return True
    for item in payload["afins"] + [payload["produto"]]:
        description = item.get("descricao") or ""
        if len(description) > MIN_DESCRIPTION_CHARS_AFTER_TRIM:
            item["descricao"] = description[:MIN_DESCRIPTION_CHARS_AFTER_TRIM]
            return True
    return False


def build_llm_payload(evidence: EvidencePackage) -> str:
    """JSON compacto, deterministico (chaves ordenadas) e dentro do limite de caracteres."""
    payload = _build_dict(evidence)
    text = _dump(payload)
    while len(text) > MAX_EVIDENCE_PAYLOAD_CHARS and _shrink_once(payload):
        text = _dump(payload)
    return text
