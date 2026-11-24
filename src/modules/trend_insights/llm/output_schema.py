"""
Schema JSON de saida enviado ao modelo (raso, `additionalProperties: false`). Os limites de tamanho de
texto sao validados no app (a API ignora `maxLength`); `maxItems` e aplicado pelo decodificador.
"""
from typing import Any, Dict

from src.modules.trend_insights.domain.constants import (
    MAX_FACTORS,
    MAX_HYPOTHESES,
    MAX_RECOMMENDATIONS,
    MAX_SOURCES_PER_FACTOR,
)

INTERNAL_FACTOR_TYPES = (
    "SAZONALIDADE", "PRECO", "PRODUTO_NOVO", "CANIBALIZACAO_MESMO_FORNECEDOR",
    "CANIBALIZACAO_OUTRO_FORNECEDOR", "PERDA_PARTICIPACAO_SEM_MIGRACAO", "CLIENTES_PERDIDOS",
    "RUPTURA", "PROMOCAO", "REGIONAL",
)
EXTERNAL_FACTOR_TYPES = ("CLIMA", "POLITICO_REGULATORIO", "MATERIA_PRIMA", "CONCORRENCIA_MERCADO", "OUTRO")
FACTOR_TYPES = INTERNAL_FACTOR_TYPES + EXTERNAL_FACTOR_TYPES
DIRECTIONS = ("NEGATIVO", "POSITIVO")
CONFIDENCES = ("ALTA", "MEDIA", "BAIXA")
LLM_HYPOTHESIS_REASONS = ("SEM_FONTE", "SEM_EVIDENCIA_INTERNA", "EVIDENCIA_FRACA")

_SOURCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["url", "titulo", "dataPublicacao"],
    "properties": {
        "url": {"type": "string"},
        "titulo": {"type": "string"},
        "dataPublicacao": {"type": ["string", "null"], "format": "date"},
    },
}

_FACTOR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tipo", "sentido", "confianca", "explicacao", "evidenciaInterna", "skusCitados", "fontes"],
    "properties": {
        "tipo": {"type": "string", "enum": list(FACTOR_TYPES)},
        "sentido": {"type": "string", "enum": list(DIRECTIONS)},
        "confianca": {"type": "string", "enum": list(CONFIDENCES)},
        "explicacao": {"type": "string"},
        "evidenciaInterna": {"type": ["string", "null"], "enum": list(INTERNAL_FACTOR_TYPES) + [None]},
        "skusCitados": {"type": "array", "maxItems": 10, "items": {"type": "integer"}},
        "fontes": {"type": "array", "maxItems": MAX_SOURCES_PER_FACTOR, "items": _SOURCE_SCHEMA},
    },
}

_HYPOTHESIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tipo", "descricao", "motivo"],
    "properties": {
        "tipo": {"type": "string", "enum": list(FACTOR_TYPES)},
        "descricao": {"type": "string"},
        "motivo": {"type": "string", "enum": list(LLM_HYPOTHESIS_REASONS)},
    },
}

LLM_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["resumo", "fatores", "hipotesesNaoConfirmadas", "recomendacoes"],
    "properties": {
        "resumo": {"type": "string"},
        "fatores": {"type": "array", "maxItems": MAX_FACTORS, "items": _FACTOR_SCHEMA},
        "hipotesesNaoConfirmadas": {"type": "array", "maxItems": MAX_HYPOTHESES, "items": _HYPOTHESIS_SCHEMA},
        "recomendacoes": {"type": "array", "maxItems": MAX_RECOMMENDATIONS, "items": {"type": "string"}},
    },
}
