"""
Roteador RESTful FastAPI para o Módulo de Precificação Compensatória (Pricing Predictor).
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
from queue import Queue
from threading import Thread
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from src.core.database import test_db_connection
from src.modules.pricing.api.schemas import (
    AutoTuneRequest,
    PricingRequest,
    PricingSummary,
    ProductPreview,
)
from src.modules.pricing.domain.meta_tuner import run_genetic_algorithm
from src.modules.pricing.service.pricing_service import (
    _DATA_CACHE,
    execute_pricing_computation,
    get_cached_base_data,
    get_shared_prediction,
    save_shared_prediction,
)


logger = logging.getLogger(__name__)

pricing_router = APIRouter(prefix="/pricing", tags=["Pricing Predictor"])


@pricing_router.get("/health")
def health_check():
    return {"status": "healthy", "service": "fitoherb-pricing-api"}


@pricing_router.get("/db-status")
def get_db_status():
    """Retorna o status de conexão com o banco de dados SQL Server da Fitoherb (P-022)."""
    status = test_db_connection()
    cache_source = _DATA_CACHE.get("data_source", "not_initialized")
    loaded_at = _DATA_CACHE.get("loaded_at")
    raw_sales_count = _DATA_CACHE.get("raw_sales_count", 0)
    raw_products_count = _DATA_CACHE.get("raw_products_count", 0)
    return {
        "data": {
            **status,
            "activeDataSource": cache_source,
            "loadedAt": loaded_at,
            "rawSalesCount": raw_sales_count,
            "rawProductsCount": raw_products_count,
        }
    }


@pricing_router.post("/sync-db")
def sync_db():
    """Recarrega os dados analíticos forçando nova extração do SQL Server (P-022)."""
    try:
        get_cached_base_data(force_reload=True)
        return {
            "data": {
                "message": "Dados sincronizados com sucesso a partir do banco SQL Server.",
                "source": _DATA_CACHE.get("data_source"),
                "salesCount": _DATA_CACHE.get("raw_sales_count"),
                "productsCount": _DATA_CACHE.get("raw_products_count"),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar dados do banco: {str(e)}")



@pricing_router.get("/config")
def get_config():
    return {
        "data": {
            "kRatio": {"default": 0.25, "min": 0.15, "max": 0.35, "step": 0.01, "label": "Trava de Parâmetros Base (K%)"},
            "variableKRatio": {"default": True, "label": "Trava Dinâmica por Âncora (Otimizada por SKU)"},
            "topAnchors": {"default": 15, "min": 5, "max": 30, "step": 1, "label": "Qtd Produtos Âncora"},
            "halfLifeDays": {"default": 100, "min": 30, "max": 365, "step": 5, "label": "Meia-Vida Temporal (Dias)"},
            "anchorDiscount": {"default": -0.10, "min": -0.15, "max": -0.05, "step": 0.01, "label": "Desconto no Âncora"},
            "compMaxIncrease": {"default": 0.06, "min": 0.01, "max": 0.08, "step": 0.01, "label": "Teto Compensador"},
            "stressDrop": {"default": 0.05, "min": 0.01, "max": 0.10, "step": 0.01, "label": "Queda no Estresse (%)"}
        },
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    }


@pricing_router.post("/predict")
def predict_pricing(req: PricingRequest):
    try:
        df_consolidated, top_anchors, pricing_recommendations, replay, stress, anchor_locks = execute_pricing_computation(req)
        
        # Ordenação prioritária (P-019): Âncoras primeiro, Compensadores depois, Neutros por último
        df_work = df_consolidated.copy()
        df_work["_prio"] = df_work["Papel_Estrategico"].map(
            lambda p: 1 if "ÂNCORA" in p else (2 if "COMPENSADOR" in p else 3)
        )
        df_sorted = df_work.sort_values(
            by=["_prio", "Impacto_Margem_Projetada", "Codigo"],
            ascending=[True, False, True]
        ).drop(columns=["_prio"])

        all_products = []
        anchor_discounts = []
        comp_increases = []
        stress_drops = []

        for r in df_sorted.itertuples(index=False):
            sku_id = int(r.Codigo)
            info = pricing_recommendations.get(sku_id, {})
            trava_k = float(info["trava_k"]) if "trava_k" in info and info["trava_k"] is not None else None
            elast = float(info["elasticidade"]) if "elasticidade" in info else None
            q_estresse = float(info["queda_volume_estresse_pct"]) if "queda_volume_estresse_pct" in info else None

            var_pct = float(r.Variacao_Percentual)
            if "ÂNCORA" in str(r.Papel_Estrategico):
                anchor_discounts.append(var_pct)
            elif "COMPENSADOR" in str(r.Papel_Estrategico):
                comp_increases.append(var_pct)
                if q_estresse is not None:
                    stress_drops.append(q_estresse)

            all_products.append(
                ProductPreview(
                    codigo=sku_id,
                    descricao=str(r.Descricao),
                    fornecedor=str(r.Fornecedor_Marca),
                    papelEstrategico=str(r.Papel_Estrategico),
                    precoAtual=float(r.Preco_Atual_Tabela),
                    novoPreco=float(r.Novo_Preco_Sugerido),
                    variacaoReais=float(r.Variacao_Reais),
                    variacaoPct=var_pct,
                    regraComercial=str(r.Regra_Comercial_Pedido),
                    travaKPercentual=trava_k,
                    elasticidade=elast,
                    quedaVolumeEstressePct=q_estresse
                )
            )

        k_values = list(anchor_locks.values()) if req.variable_k_ratio and anchor_locks else [req.k_ratio]
        summary = PricingSummary(
            totalSkus=len(df_consolidated),
            totalOrdersAnalyzed=int(replay.get("total_pedidos_com_ancora", 0)),
            anchorsElected=len(top_anchors),
            compensatorsElected=len([s for s, info in pricing_recommendations.items() if info["papel"] == "COMPENSADOR"]),
            projectedRevenue=float(replay.get("faturamento_projetado", 0.0)),
            replay2026EligibilityPct=float(replay.get("pct_elegibilidade", 0.0)),
            stressNetProfit=float(stress.get("lucro_liquido_estresse", 0.0)),
            marginProtected=bool(stress.get("margem_protegida", True)),
            variableKRatioApplied=req.variable_k_ratio,
            minKRatio=float(min(k_values)) if k_values else req.k_ratio,
            maxKRatio=float(max(k_values)) if k_values else req.k_ratio,
            autonomousSkuPricingApplied=req.autonomous_sku_pricing,
            avgAnchorDiscountPct=round(float(sum(anchor_discounts) / len(anchor_discounts)), 4) if anchor_discounts else req.anchor_min_discount,
            minAnchorDiscountPct=round(float(min(anchor_discounts)), 4) if anchor_discounts else req.anchor_min_discount,
            maxAnchorDiscountPct=round(float(max(anchor_discounts)), 4) if anchor_discounts else req.anchor_max_discount,
            avgCompIncreasePct=round(float(sum(comp_increases) / len(comp_increases)), 4) if comp_increases else req.comp_max_increase,
            avgStressDropPct=round(float(sum(stress_drops) / len(stress_drops)), 4) if stress_drops else req.stress_drop
        )

        result_data = {
            "summary": summary.model_dump(),
            "previewProducts": [p.model_dump() for p in all_products],
            "params": req.model_dump(),
            "savedAt": datetime.now(timezone.utc).isoformat()
        }
        save_shared_prediction(result_data)

        return {
            "data": result_data,
            "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar precificação: {str(e)}")


@pricing_router.get("/latest-prediction")
def get_latest_prediction_endpoint():
    """Retorna a última previsão calculada e compartilhada entre todos os usuários."""
    prediction = get_shared_prediction()
    if not prediction:
        return {"data": None, "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}}
    return {
        "data": prediction,
        "meta": {"timestamp": datetime.now(timezone.utc).isoformat()}
    }



@pricing_router.post("/export")
def export_pricing_csv(req: PricingRequest):
    try:
        df_consolidated, _, _, _, _, _ = execute_pricing_computation(req)
        # Regra P-018: Codificação explícita em UTF-8 com BOM (\xef\xbb\xbf) e delimitador ';' para o Microsoft Excel no Windows
        csv_bytes = df_consolidated.to_csv(index=False, sep=";").encode("utf-8-sig")
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"precificacao_fitoherb_{timestamp_str}.csv"

        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8-sig",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar exportação CSV: {str(e)}")


@pricing_router.post("/auto-tune")
def auto_tune_pricing(req: AutoTuneRequest = AutoTuneRequest()):
    """
    Executa o Algoritmo Genético para encontrar os hiperparâmetros ótimos (US-09, P-014 a P-016).
    """
    cache = get_cached_base_data()
    try:
        ga_result = run_genetic_algorithm(
            catalog_df=cache["catalog_df"],
            clean_sales=cache["clean_sales"],
            population_size=req.population_size,
            generations=req.generations,
            strategy=req.strategy,
            random_state=42,
            precomputed_rules=cache["rules_df"],
            precomputed_scores=cache["anchor_scores"],
            precomputed_rules_index=cache.get("rules_index"),
            replay_sales=cache.get("sales_2026")
        )

        bp = ga_result["best_params"]
        sim = ga_result["best_simulation"]

        return {
            "data": {
                "strategy": ga_result["strategy"],
                "generationsRun": ga_result["generations_run"],
                "bestFitness": ga_result["best_fitness"],
                "optimalParams": {
                    "kRatio": bp["k_ratio"],
                    "topAnchors": bp["top_anchors"],
                    "halfLifeDays": bp["half_life_days"],
                    "anchorDiscount": bp["anchor_discount"],
                    "compMaxIncrease": bp["comp_max_increase"],
                    "stressDrop": bp["stress_drop"],
                },
                "projectedMetrics": {
                    "projectedRevenue": sim.get("projected_revenue", 0.0),
                    "replay2026EligibilityPct": sim.get("replay_2026_eligibility_pct", 0.0),
                    "stressNetProfit": sim.get("stress_net_profit", 0.0),
                    "marginProtected": sim.get("margin_protected", False),
                    "anchorsElected": sim.get("anchors_elected", 0),
                    "compensatorsElected": sim.get("compensators_elected", 0),
                },
                "fitnessHistory": ga_result["fitness_history"],
            },
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.2.0"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na execução da meta-otimização: {str(e)}")


@pricing_router.get("/auto-tune-stream")
async def auto_tune_pricing_stream(
    strategy: str = "balanced",
    population_size: int = 12,
    generations: int = 6
):
    """
    Executa o Algoritmo Genético transmitindo o progresso de cada geração via SSE (Server-Sent Events).
    Permite barra de progresso 100% realista no frontend, eliminando travamentos arbitrários.
    """
    cache = get_cached_base_data()
    q = Queue()

    def progress_cb(update_dict: Dict[str, Any]):
        q.put(("progress", update_dict))

    def worker():
        try:
            res = run_genetic_algorithm(
                catalog_df=cache["catalog_df"],
                clean_sales=cache["clean_sales"],
                population_size=population_size,
                generations=generations,
                strategy=strategy,
                random_state=42,
                precomputed_rules=cache["rules_df"],
                precomputed_scores=cache["anchor_scores"],
                progress_callback=progress_cb,
                precomputed_rules_index=cache.get("rules_index"),
                replay_sales=cache.get("sales_2026")
            )
            bp = res["best_params"]
            sim = res["best_simulation"]
            payload = {
                "data": {
                    "strategy": res["strategy"],
                    "generationsRun": res["generations_run"],
                    "bestFitness": res["best_fitness"],
                    "optimalParams": {
                        "kRatio": bp["k_ratio"],
                        "topAnchors": bp["top_anchors"],
                        "halfLifeDays": bp["half_life_days"],
                        "anchorDiscount": bp["anchor_discount"],
                        "compMaxIncrease": bp["comp_max_increase"],
                        "stressDrop": bp["stress_drop"],
                    },
                    "projectedMetrics": {
                        "projectedRevenue": sim.get("projected_revenue", 0.0),
                        "replay2026EligibilityPct": sim.get("replay_2026_eligibility_pct", 0.0),
                        "stressNetProfit": sim.get("stress_net_profit", 0.0),
                        "marginProtected": sim.get("margin_protected", False),
                        "anchorsElected": sim.get("anchors_elected", 0),
                        "compensatorsElected": sim.get("compensators_elected", 0),
                    },
                    "fitnessHistory": res["fitness_history"],
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "totalGenerations": generations
                }
            }
            q.put(("complete", payload))
        except Exception as err:
            q.put(("error", str(err)))

    thread = Thread(target=worker, daemon=True)
    thread.start()

    async def event_generator():
        # Enviar comentário inicial para liberar os cabeçalhos HTTP 200 OK imediatamente
        yield ": ping\n\n"

        while True:
            while q.empty() and thread.is_alive():
                await asyncio.sleep(0.05)

            if not q.empty():
                event_type, event_data = q.get()
                if event_type == "progress":
                    yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"
                elif event_type == "complete":
                    yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                    break
                elif event_type == "error":
                    yield f"event: error\ndata: {json.dumps({'error': event_data})}\n\n"
                    break
            elif not thread.is_alive():
                while not q.empty():
                    event_type, event_data = q.get()
                    if event_type == "progress":
                        yield f"event: progress\ndata: {json.dumps(event_data)}\n\n"
                    elif event_type == "complete":
                        yield f"event: complete\ndata: {json.dumps(event_data)}\n\n"
                    elif event_type == "error":
                        yield f"event: error\ndata: {json.dumps({'error': event_data})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
