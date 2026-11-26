# STATE - Testes F7 (tester, Etapa 3, fase RED) - 2026-11-24

Suite: `tests/trend_insights/` (262 testes; 258 falham por ausencia de implementacao, 4 passam: regressao de import sales_trend/analytics e varredura sem Neon, esta guardada por `test_package_exists_for_static_scan`).
Comando: `python -m pytest tests/trend_insights -q`
Todo import do codigo produtivo e preguicoso (`helpers.mod`). Ponto unico de adaptacao de fabricas: `tests/trend_insights/helpers.py` (`make_rig`, `make_evidence`, fakes).

## Premissas de nomes (pacote `src/modules/trend_insights`)
- `config.TrendInsightsSettings.from_env(mapping)`: `ai_enabled`, `monthly_budget_usd`, `daily_budget_usd`, `model_default`, `model_fallback`; ValueError para modelo fora da lista ou `TREND_AI_PRICING_JSON` com modelo extra. Formato do pricing JSON: ver `helpers.PRICING_JSON`.
- `domain.constants`: constantes de P-150..P-188 s.2 + `RESERVATION_TTL_SECONDS=150`.
- `domain.windows.build_window_spec(base_month_index, window, comparison_mode, first_sale_date, last_covered_day)` -> pre_start, pre_end_exclusive, cur_start, cur_end_exclusive, scale_k (Fraction), is_contiguous, is_previous_fully_covered.
- `domain.cell_mode.diagnosis_mode(status, variacao_pct, base_baixa)`.
- `domain.affinity_group`: `compute_market_diagnosis(...)`, `is_launch_affine(...)`.
- `domain.decomposition`: `finalize_cascade`, `build_migration_parcels`, `migration_confidence`, `convert_revenue_to_quantity`, `share_loss_without_migration`.
- `domain.migration_scaling`: `scale_previous`, `aggregate_lost_customers`; `domain.privacy`: `RegionRow`, `group_regions`, `detect_regional`, `format_small_count`.
- `domain.evidence`: `EvidencePackage.from_mapping(dict, data_referencia)`, `RawParcel`, `MigrationPair`, `compute_evidence_hash`. Dict canonico: `helpers.canonical_evidence`.
- `domain.gates`: `evaluate_llm_gates(ev)`, `grounding_enabled(ev, budget_level)`; `domain.template_summary`: `build_template_summary`, `TEMPLATE_LABEL`; `domain.budget`: `budget_level`, `reservation_amount`.
- `domain.ports`: `ObjectStore` (read_json/write_json/delete), `ObjectConflict`, `ObjectStoreUnavailable`, `NotEvaluated(reason)`, `TrendSourceUnavailable`. `domain.exceptions`: `BudgetDenied`, `BudgetUnavailable`, `GenerationRefused(motivo, retry_after_seconds)`, `ProductNotFoundError`, `InsufficientBaseError`.
- `llm.client` (DTOs do trend-insights-llm.md s.4), `llm.pricing` (`parse_pricing`, `compute_cost`), `llm.validation` (`ValidationContext`, `validate_llm_output`), `llm.evidence_payload.build_llm_payload`, `llm.search_queries.build_search_queries`.
- `store.budget_ledger.BudgetLedger(store, settings, clock)`: `reserve/settle/release/level`; `store.insight_store`: `InsightStore`, `InsightKey`, `StoredInsight`; `store.lease_store.GcsInFlightLease`.
- `service.llm_orchestrator.LlmOrchestrator(llm, ledger, insight_store, lease, guard, settings, clock, sleep).generate(evidence, caller_id, force)` -> `origem`, `motivo_template`, `modelo`, `avisos`, `diagnostico`, `reutilizado`, `resumo_automatico`; `service.generation_guard.GenerationGuard.check(caller_id, force=False)`; `service.migration_cache.MigrationCache`; `service.insights_service.InsightsService`; `adapters.migration_adapter.build_migration_snapshot`.
- `api.router`: `insights_router`, `get_insights_service`. `analytics.repository.sales_repository`: `_CUSTOMER_SKU_SPLIT_WINDOW_SALES_SQL`, `fetch_customer_sku_split_window_sales`, `_SKU_REGION_WINDOW_SALES_SQL`, `fetch_sku_region_window_sales`.

## Fora desta fase (cobertura pendente)
Rotas internas OIDC 7.0c, object_storage, demais adaptadores (T-7.1.14), health detalhado do indice, visao por fornecedor (7.4), frontend (7.3).

## Radar externo v3.1 (tarefa 7.2-R, fase RED) - 2026-11-26
Comando: `python -m pytest tests/trend_insights -q` (antes do radar: 371 passam, 1 falha previa `test_search_queries_limits_and_terms`). Agora: 198 novos vermelhos + 4 revisados vermelhos; 1 novo ja verde (`lifecycle.json` ja tem `radar/` 210 d, feito pelo devops).
Arquivos novos: `radar_helpers.py` (RoutedLlm por `request_tag=="radar"`, TtlLease, `make_radar_rig`, `plant_radar`, `seed_ledger`), `test_radar_subject`, `test_external_dimensions`, `test_radar_injection`, `test_radar_store_policy`, `test_budget_radar`, `test_external_validation`, `test_radar_orchestrator`, `test_api_contract_radar`.
Existentes revisados (regra v3.1): `tia-v2`->`tia-v3` e contrato `1.1.0`->`1.2.0` (test_llm_orchestrator, test_api_contract); `RESERVATION_TTL` 150->180 e expiracao 151->181 s (test_budget).
A SUPERAR pelo developer junto da implementacao (hoje verdes, conflitam com v3): `test_budget.py::test_reservation_estimate_values` (so se mudar reserva), testes `grounding_enabled`/`test_grounding_*` e `test_search_queries_*` em test_gates_template.py (substituidos por `product_search_enabled`/`build_product_query`), buscas sugeridas (2 consultas/cota gratis) e `test_total_deadline_110s` em test_llm_orchestrator.py (C-28b/C-29a/110 s revisados em `test_radar_orchestrator.py`).
Divergencia nos docs: TTL de meses antigos = 180 d (regras, DA-13, tarefa) e nao 90 (arquitetura 15.4 antiga); stale = 120 d contados desde a geracao.
### Premissas de nomes (radar)
- `domain.raw_material`: `infer_radar_subject(evidence)->RadarSubject(slug,termo,tipo)|None` (None = SEM_TERMO_BUSCA), `PRIMARY_FUNCTION_RAW_MATERIAL_TERMS`, `RAW_MATERIAL_KEYWORDS`; categoria usa `produto.categoria_galeria` e `produto.tipo_catalogo`.
- `domain.external_dimensions`: `EXTERNAL_DIMENSIONS`, `DIMENSION_FACTOR_TYPE`, `temporal_relation(d,*,current_start,current_end,previous_start)->(relacao,rotulo)`, `directional_coherence(direcao,variation_pct)`. `domain.radar_themes`: `RADAR_THEMES`, `RADAR_THEME_TEXTS[(dim,tema)]`, `NO_EVIDENCE_TEXT`.
- `domain.radar_policy.radar_freshness(generated_at,base_month,now)->FRESCO|DESATUALIZADO|AUSENTE`; `domain.gates.radar_policy(radar_state,budget_level,daily_new,share_spent,hard_cap)->USE_FRESH|GENERATE|USE_STALE|NONE`; `product_search_enabled(ev,budget_level,radar_state,hard_cap)`; `grounding_enabled` removido.
- `llm.radar_schema.parse_radar_output(text,source_count)->.ok/.dimensions/.violations` (JSON `{dimensoes:[{dimensao,status,movimento,intensidade,tema,fonteIdx,dataFonte}]}`, `fonteIdx` 0-based nas citacoes); log `tia.radar.injectionSuspect`.
- `store.radar_store`: `radar_path(version,slug,mes)`, `RadarStore(store,clock).get(slug,mes)/put`, `StoredRadar.from_json`; objeto: geradoEm, modelo, assunto{slug,termo,tipo}, mesBase, dimensoes[8]{dimensao,status,movimento,intensidade,tema,fonteIds}, fontes[], consultasExecutadas, searchSuggestionsHtml, radarHash. Objeto plantado com campo livre/tema invalido e ignorado.
- `service.radar_service.RadarService(llm,ledger,radar_store,lease,settings,clock,sleep)`: `peek(subject,mes)` (so leitura), `get_or_create`. `LlmOrchestrator(..., radar_service=)`; `GenerationOutcome.radar` (RadarRef) e `.radar_externo`. `InsightsService(..., radar_service=)`. Radar request: `request_tag=="radar"`, grounding, `settings.model_radar`, 1500 tokens, timeout<=55.
- `BudgetLedger.reserve(model,with_search,kind="DIAGNOSTICO"|"RADAR")`, `Reservation.kind`; livro: `gastoRadarMes`, `radaresNovosMes`, `radaresNovosDia={"data","valor"}`; `domain.budget.reservation_amount(...,kind="RADAR")`. Settings: `model_radar` (`TREND_AI_MODEL_RADAR`), `hard_cap_queries` (`GROUNDING_HARD_CAP_QUERIES`). Constantes `RADAR_*` conforme regras.
- `llm.validation.ExternalContext(dimensions,sources,variation_pct,current_start,current_end,previous_start,radar_stale,radar_missing_reason)` em `ValidationContext(external=...)`; violacao `FONTE_FORA_DO_RADAR`; saida `fatoresExternos[8]`, `fatores[].dimensao`. `llm.evidence_payload.build_radar_block(StoredRadar,nonce)`; `nota` <= 100 chars.
