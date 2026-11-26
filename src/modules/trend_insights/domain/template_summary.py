"""
Resumo automatico por template (P-188): frases-modelo deterministicas, sem LLM, sem digitos e sem citar
fator externo. Os numeros ficam nos campos numericos da cascata.
"""
from typing import List

from src.modules.trend_insights.domain.evidence import EvidencePackage

TEMPLATE_LABEL = "Resumo automático (sem IA)"

_FACTOR_LABELS = {
    "SAZONALIDADE": "a sazonalidade",
    "PRECO": "a mudança de preço",
    "PRODUTO_NOVO": "o lançamento de produto afim",
    "CANIBALIZACAO_MESMO_FORNECEDOR": "a migração para produto do mesmo fornecedor",
    "CANIBALIZACAO_OUTRO_FORNECEDOR": "a migração para produto de outro fornecedor",
    "CLIENTES_PERDIDOS": "a perda de clientes",
}
_INDICATOR_LABELS = {
    "PROMOCAO": "promoção no período",
    "RUPTURA": "falta de estoque atual",
    "PERDA_PARTICIPACAO_SEM_MIGRACAO": "perda de participação sem migração para afins",
    "REGIONAL": "concentração regional das vendas",
}
_MARKET_SENTENCES = {
    "MERCADO_EM_QUEDA": "O grupo de produtos afins também recuou, o que indica movimento de mercado.",
    "MERCADO_EM_ALTA": "O grupo de produtos afins também avançou, o que indica movimento de mercado.",
    "PERDA_DE_PARTICIPACAO": "O produto perdeu participação dentro do grupo de produtos afins.",
    "GANHO_DE_PARTICIPACAO": "O produto ganhou participação dentro do grupo de produtos afins.",
    "MISTO": "Há efeito de mercado e de participação ao mesmo tempo.",
}
_JOINER = ", "


def _joined(labels: List[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    return _JOINER.join(labels[:-1]) + " e " + labels[-1]


def _factor_sentence(evidence: EvidencePackage) -> str:
    ranked = sorted(
        (p for p in evidence.data.get("cascata") or [] if p.get("status") == "AVALIADO" and p["tipo"] in _FACTOR_LABELS),
        key=lambda p: -abs(p.get("valor") or 0.0),
    )
    labels = [_FACTOR_LABELS[p["tipo"]] for p in ranked[:3]]
    if labels:
        return "Fatores internos que mais contribuíram: " + _joined(labels) + "."
    ind_labels = [
        _INDICATOR_LABELS[i["tipo"]]
        for i in (evidence.data.get("indicadores") or [])
        if i.get("status") == "AVALIADO" and i.get("tipo") in _INDICATOR_LABELS
    ]
    if ind_labels:
        return "Sinais internos observados: " + _joined(ind_labels[:3]) + "."
    return "Os fatores internos medidos não explicam a variação."


def build_template_summary(evidence: EvidencePackage) -> str:
    """Narrativa curta e estavel: mesmo pacote, mesmo texto."""
    verb = "caiu" if evidence.direction == "QUEDA" else "subiu"
    parts = [f"A venda do produto {verb} na janela analisada.", _factor_sentence(evidence)]
    market = _MARKET_SENTENCES.get(evidence.market_classification or "")
    if market:
        parts.append(market)
    return " ".join(parts)
