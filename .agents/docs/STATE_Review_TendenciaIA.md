# STATE Review — F7 Diagnóstico de Tendência com IA (Reviewer)

Escopo: `git diff origin/main...HEAD` (branch `claude/ai-sales-trend-analysis-8b0d75`, HEAD 2ab74af). Revisão estática por amostragem dirigida (validação, rotas, auth, logs, helpers de teste, limites de função) mais execução das suítes. Nenhum código foi editado.

## Resultado dos testes
- `python -m pytest tests/trend_insights -q`: 333 passed.
- Suítes `-k "sales_trend or analytics or trend"` (fora de trend_insights, exceto `test_predict_endpoint_success`): 487 passed.
- A suíte completa (`tests` sem `-k`) não foi concluída (estourou 120 s); não é evidência de falha.

## Veredito: APROVADO COM RESSALVAS (nenhum bloqueante confirmado; 1 divergência regra x código a decidir antes do QA)

## Achados

### Importante
1. **FORA_DO_PERIODO: teste x regra x arquitetura divergem** — `src/modules/trend_insights/llm/validation.py:148-150`; `tests/trend_insights/test_validation.py:104`.
   - P-182.4 (`business_rules/analytics-tendencia-ia.md:442`) só rebaixa quando a `dataPublicacao` conhecida está fora de `[início PRE − lookback, dataReferencia]`.
   - `architecture/trend-insights-llm.md:413` diz que, se a data do modelo e a da URL divergem mais de 31 dias, vale a da URL (`origemData = URL`).
   - O código dá prioridade à data do modelo (`_resolve_date`, linha 122) e ainda rejeita se QUALQUER uma (modelo ou URL) estiver fora do período (linha 148-149). O teste usa modelo=2025-01-10 com URL de 2026/10/05 e espera FORA_DO_PERIODO, o que contradiz a regra de preferir a URL.
   - Correção: decidir a fonte da verdade. Opção A (fiel à arquitetura): em `_resolve_date`, se `|modelo − URL| > 31 dias`, usar a URL com `origemData="URL"`; trocar o caso do teste por um com URL também fora do período e acrescentar um teste de divergência. Opção B (manter o rigor atual): atualizar P-182.4 e a seção 413 do doc para "qualquer data conhecida fora do período rejeita". Em ambos os casos, alinhar regra, doc e teste.
2. **try/except por rota em vez de Global Error Handler** — `src/modules/trend_insights/api/route.py:65-91`. A rule `architecture-error-handling-rules.md` §4 pede handler central. O `APIRoute` customizado é isolado por módulo (aceitável, alinhado a ADR-003), mas confirme que isso está registrado no ADR-009; senão registre a exceção. A mensagem é fixa e só o tipo vai ao log, o que é conforme (sem stacktrace e sem PII).
3. **Funções com muitos parâmetros (>3, regra Clean Code §5)** — `service/insights_service.py:79` (`__init__`, 10), `service/llm_orchestrator.py:51` (9), `adapters/evidence_adapter.py:208,242` (7-8), `factor_adapter.py:66`, `migration_adapter.py:41`, `llm/pricing.py:69`, `domain/budget.py:28`. Construtores de composição são toleráveis; `_analysis`, `_base_data` e `compute_cost` devem receber um objeto/dataclass de contexto.
4. **`evidence_adapter.py` com 563 linhas** (maior arquivo do módulo). Há indício de múltiplas responsabilidades (base, análise, grupo afim, indicadores). Sugestão: dividir por fonte de evidência (SRP). Nenhuma função passa de 45 linhas.

### Nit
5. `tests/trend_insights/test_windows_and_modes.py:84`: `<= 0.05 + 1e-9` mascara o arredondamento. Justificado pelo commit a23d27e (float), mas prefira `pytest.approx(..., abs=0.05 + 1e-9)` ou comparar com `Fraction`, e comentar a razão no teste.
6. `tests/trend_insights/test_api_contract.py:225`: troca de `app.routes` por `app.openapi()["paths"]` (justificada por FastAPI lazy). Isso só prova rotas documentadas; rotas com `include_in_schema=False` (a rota interna `/internal/v1/affinity-index/sync`) não seriam vistas. Cobertas por `test_internal_affinity_sync.py`, então apenas ressalva.
7. `tests/trend_insights/helpers.py:85-88` (FakeObjectStore cria o objeto no conflito) e `:283` (aplica `seconds_per_call` ao LlmClient informado): ajustes de dublê coerentes com o GCS real e sem enfraquecer asserções. Aceitos. Os dois ajustes entraram no commit `a23d27e`, separado do commit de testes (`37d1431`), o que é rastreável.
8. `api/route.py:52-58` `_validation_fields`: lógica de deduplicação confusa (insere `None` e filtra depois). Simplificar com um conjunto ordenado.
9. `src/core/auth.py` (isenção Basic para `POST /internal/v1/affinity-index/sync`): exata por método e caminho, e a rota valida OIDC. Conforme. Confirme que o teste cobre o caso de OIDC ausente ou inválido (`SchedulerUnauthorized` -> 401, TIA-006 existe).
10. Commits `fix(analytics)`/`feat(...)` seguem Conventional Commits com `P-XXX` e a atribuição exigida; alguns commits de docs agrupam várias tarefas, mas permanecem atômicos o suficiente.

## Conformidade verificada
- Docs somente em `.agents/docs/` (nenhum `.md` na raiz; só `.env.example` e `requirements.txt` fora dos diretórios, que são configuração).
- Isolamento ADR-003: nenhum import de `trend_insights` para outros módulos de negócio, e `test_import_boundaries.py` existe e passa.
- Logs usam apenas `type(exc).__name__` e marcadores fixos (sem PII, sem objetos inteiros); sem `traceback` em respostas.
- Envelope `data`/`meta` e erro com códigos `TIA-XXX`/`ANL-001` conforme contrato; 429 com `Retry-After`; 409 e 422 usados com semântica correta.
- URLs de fontes validadas (esquema permitido, sem IP literal); fatores externos sem fonte citada viram hipótese (anti-alucinação).

## Pendências para o Developer
Resolver o item 1 (decisão + alinhamento regra/doc/teste) antes do QA. Os itens 2 a 4 podem virar tarefas de refatoração (T7) sem bloquear.
