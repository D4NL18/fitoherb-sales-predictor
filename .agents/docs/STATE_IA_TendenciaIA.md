# STATE — AI Specialist · F7 Diagnóstico de Motivos da Tendência com IA

| Campo | Valor |
| :--- | :--- |
| **Agente** | `ai_specialist` |
| **Etapa** | 2 (Arquitetura de IA) — concluída, aguardando Checkpoint |
| **Data** | 2026-11-24 |
| **Branch** | `claude/ai-sales-trend-analysis-8b0d75` |
| **Entrega** | `.agents/docs/architecture/trend-insights-llm.md` |
| **Arquivos NÃO alterados** | `STATE.md`, ADR-009, contrato `trend-insights`, regras P-150..P-187 (divergências viraram pontos CP-1..CP-12) |

## Resumo

1. **Confirmado na doc oficial (aistudio.google.com/docs e docs.cloud.google.com):** IDs `gemini-4-hydrogen` e `gemini-4-neon` (Stable); contexto de 1.048.576 tokens; saída de 65.536; preço Standard US$ 1,50/7,50 (Hydrogen) e US$ 3,00/15,00 (Neon) por 1M tokens de entrada/saída (saída inclui *thinking*); grounding com Google Search com 5.000 consultas grátis/mês compartilhadas entre Gemini 3+ e depois US$ 14/1.000, **cobrado por consulta executada**, sem grounding no Free tier; **saída estruturada + Google Search na mesma chamada suportada em Preview** para Gemini 4; citações `url_citation` (`url`, `title`, índices) via Interactions API (recomendada, GA); `store=false` disponível; Vertex AI tem o Hydrogen com grounding e saída estruturada no endpoint `global` (processamento `us`/`eu`).
2. **Não confirmado:** data de publicação nas citações (não vem), filtro de período na busca, controle das consultas executadas, citações preenchidas junto com saída JSON, temperatura no Gemini 4, preço no Vertex AI, rate limits por modelo (só no painel do AI Studio).
3. **Desenho:** 1 chamada (grounding + JSON Schema) por padrão; modo de 2 chamadas (pesquisa com grounding em texto → estruturação sem busca) por configuração ou automático quando a combinação falhar ou vier sem citações.
4. **`LlmClient`** (porta própria, sem LangChain) com `generate(LlmRequest) -> LlmResponse`, DTOs de uso/citações e 5 erros tipados.
5. **Prompts `tia-v1`** em 7 blocos (S1 regras, S2 guia de fatores, S5 formato, U1 tarefa, U2 evidências, U3 galeria, U4 consultas) + prompt de pesquisa; delimitadores com nonce; números e SKUs só por marcadores (`{{parcela:TIPO}}`, `{{sku:COD}}`).
6. **Pacote de evidências** ≤ 16.000 caracteres com ordem de corte; lista do que nunca entra (`Cod Cliente`, custos, UFs < 3 clientes).
7. **Validação pós-resposta** em 9 etapas; fontes validadas contra a allow-list de citações e a janela de datas; números sempre do motor.
8. **Custo estimado:** Hydrogen ~US$ 0,03 (busca no grátis) a ~US$ 0,07 (busca cobrada); Neon ~US$ 0,13 a ~US$ 0,20. Mistura 80/20 com busca cobrada: ~US$ 0,10 → **~300 diagnósticos/mês em US$ 30**. Pré-checagem: US$ 0,13 (Hydrogen) e US$ 0,30 (Neon) por tentativa.
9. **Avaliação 7.5:** 40 casos rotulados às cegas, metas (top-1 ≥ 70%, mercado × concorrência ≥ 80%, fontes válidas ≥ 60%), red teaming de injeção, SKU, números, datas e links.

## Pontos para o Checkpoint (detalhe na §13 do documento)
- CP-1 Gemini API (chave, `store=false`) na v1; Vertex AI como opção por variável.
- CP-2 Consultas são **sugeridas**, não impostas (ajustar P-180); novas constantes de máximo de consultas.
- CP-3 Grounding não devolve data de publicação (impacta P-182.4).
- CP-4 Termos do grounding: exibir *Search Suggestions* (HTML) e não modificar Grounded Results; conflita com P-184.5 e com a substituição de marcadores → `designer`, `security` e avaliação jurídica/`ai_governance_auditor`.
- CP-5 Prazo total de 110 s para caber na trava de 120 s.
- CP-6 Temperatura: exceção à `ai-llm-integration-rules.md` §3 (não enviar no Gemini 4).
- CP-7 Lista de domínios confiáveis fica para depois da 7.5.
- CP-8 Campo `explicacao` no fator (P-181).
- CP-9 SKU no texto só por marcador (P-182.2).
- CP-10 Custo do grounding por consulta, não por pedido (P-178.1).
- CP-11 Combinação busca + schema é Preview (contingência de 2 chamadas).
- CP-12 Processamento em `us`/`eu` e retenção de 30 dias do grounding → nota do `privacy_officer`.

## Próximos passos (Etapa 3)
- Spike de 1 h com o SDK `google-genai`: confirmar sintaxe da Interactions API (`system_instruction`, `response_format`, `tools`, `thinking_level`, `store`), presença de citações com saída JSON, campos de `usage` e consumo real de tokens/consultas.
- `tester`: dublê do `LlmClient` e casos C-30..C-35 + red teaming da §12.3.
