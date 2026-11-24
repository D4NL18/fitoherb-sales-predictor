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
