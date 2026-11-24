"""
Diagnostico de motivos da Tendencia de Vendas com IA (F7, ADR-009).

Camadas: `domain` (puro), `adapters` (unica ponte com `sales_trend` e `analytics`), `service`,
`store` (GCS), `llm` (porta e regras de saida), `object_storage` (SDK do GCS) e `api` (FastAPI).
"""
