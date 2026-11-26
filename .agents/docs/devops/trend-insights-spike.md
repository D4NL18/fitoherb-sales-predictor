# Spike 7.2-S: script de calibracao (Vertex AI)

Script: `scripts/trend_insights_spike.py`. Prompts `tia-v3` sinteticos (sem dados reais). Nao altera `src/`.

## Uso
```
export GOOGLE_CLOUD_PROJECT=<projeto> TREND_AI_LOCATION=<regiao, nunca global> TREND_AI_PRICING_JSON=<json do .env.example>
gcloud auth application-default login
python scripts/trend_insights_spike.py                    # dry-run: valida env e mostra o teto de custo
python scripts/trend_insights_spike.py --confirm-billing  # 4 chamadas com busca por modelo (8 no total), COM custo
```
Sem variaveis o script sai com codigo 2; sem ADC/SDK, com codigo 3, sempre com mensagem clara.

## O que mede
1. Campos do SDK (`usage_metadata.*`, `grounding_metadata.*`) presentes, em `fields_present`; compare com `llm/gemini_client.py`.
2. Tokens de entrada/saida/thinking/tool e consultas de grounding do radar e do diagnostico.
3. `schema_plus_search` por modelo (`gemini-3.8-flash`, `gemini-4-hydrogen`): `google_search` + JSON Schema + thinking `LOW` na mesma chamada.
4. Custo estimado com `TREND_AI_PRICING_JSON`; aborta acima de US$ 0,10 apos cada chamada (o dry-run mostra o pior caso).

## Seguranca
O relatorio JSON nao contem segredos nem texto de resposta; erros do SDK registram so tipo e codigo.
Resultados alimentam `STATE_IA_TendenciaIA.md` e `trend-insights-llm.md` secoes 14 e 15.
