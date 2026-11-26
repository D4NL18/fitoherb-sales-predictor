"""
Schema JSON de saida enviado ao modelo (raso, `additionalProperties: false`). Os limites de tamanho de
texto sao validados no app (a API ignora `maxLength`); `maxItems` e aplicado pelo decodificador.
"""
from typing import Any, Dict

from src.modules.trend_insights.domain.constants import (
    MAX_FACTORS,
    MAX_HYPOTHESES,
    MAX_RECOMMENDATIONS,
    MAX_SOURCE_IDS_PER_ITEM,
    MAX_SOURCES_PER_FACTOR,
)
from src.modules.trend_insights.domain.external_dimensions import EXTERNAL_DIMENSIONS

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
# Avaliacao externa (P-180.4): sem `parcelaEstimada`, sem `relacaoTemporal`/`rotulo` (calculados pelo backend),
# confianca nunca ALTA e fontes so por id (`F1..F16` do radar, `P1` da busca do produto).
EXTERNAL_DIRECTIONS = ("PRESSAO_ALTA", "PRESSAO_BAIXA", "NEUTRA", "INDETERMINADA")
EXTERNAL_CONFIDENCES = ("MEDIA", "BAIXA")
EXTERNAL_RELEVANCES = ("ALTA", "MEDIA", "BAIXA", "NENHUMA")
SOURCE_ID_PATTERN = r"^[FP][0-9]{1,2}$"

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

_EXTERNAL_ASSESSMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["dimensao", "direcao", "confianca", "relevanciaAoProduto", "fonteIds", "nota"],
    "properties": {
        "dimensao": {"type": "string", "enum": list(EXTERNAL_DIMENSIONS)},
        "direcao": {"type": "string", "enum": list(EXTERNAL_DIRECTIONS)},
        "confianca": {"type": "string", "enum": list(EXTERNAL_CONFIDENCES)},
        "relevanciaAoProduto": {"type": "string", "enum": list(EXTERNAL_RELEVANCES)},
        "fonteIds": {
            "type": "array", "maxItems": MAX_SOURCE_IDS_PER_ITEM,
            "items": {"type": "string", "pattern": SOURCE_ID_PATTERN},
        },
        "nota": {"type": ["string", "null"]},
    },
}

LLM_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["resumo", "fatores", "hipotesesNaoConfirmadas", "recomendacoes", "avaliacoesExternas"],
    "properties": {
        "resumo": {"type": "string"},
        "avaliacoesExternas": {
            "type": "array", "maxItems": len(EXTERNAL_DIMENSIONS), "items": _EXTERNAL_ASSESSMENT_SCHEMA,
        },
        "fatores": {"type": "array", "maxItems": MAX_FACTORS, "items": _FACTOR_SCHEMA},
        "hipotesesNaoConfirmadas": {"type": "array", "maxItems": MAX_HYPOTHESES, "items": _HYPOTHESIS_SCHEMA},
        "recomendacoes": {"type": "array", "maxItems": MAX_RECOMMENDATIONS, "items": {"type": "string"}},
    },
}
