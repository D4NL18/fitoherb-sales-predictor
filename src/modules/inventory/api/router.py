"""
Roteador RESTful FastAPI para o Módulo de Estoque e Compras (Inventory & Replenishment AI).
Fitoherb Nordeste Distribuidora.
"""
from datetime import datetime, timezone
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Response

from src.modules.inventory.api.schemas import (
    InventoryConfigResponse,
    InventoryPredictRequest,
    InventoryPredictResponse,
    ResponseMeta,
    SuppliersResponse,
)
from src.modules.inventory.service.inventory_service import (
    execute_inventory_prediction,
    generate_inventory_csv,
    get_inventory_suppliers,
)

logger = logging.getLogger(__name__)

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory Predictor"])


@inventory_router.get("/health")
def inventory_health_check():
    """Health check do serviço de inventário."""
    return {"status": "healthy", "service": "fitoherb-inventory-api"}


@inventory_router.get("/config", response_model=InventoryConfigResponse)
def get_inventory_config():
    """
    Retorna os parâmetros padrão e limites operacionais para calibração de estoque e compras.
    """
    config_data = {
        "historyWindowDays": {"default": 60, "min": 15, "max": 180, "step": 15},
        "leadTimeDays": {"default": 15, "min": 1, "max": 60, "step": 1},
        "targetCoverageDays": {"default": 30, "min": 15, "max": 90, "step": 5},
        "serviceLevel": {
            "default": 0.95,
            "options": [
                {"label": "Conservador (90%)", "value": 0.90, "zScore": 1.28},
                {"label": "Padrão Distribuidora (95%)", "value": 0.95, "zScore": 1.65},
                {"label": "Crítico / Sem Ruptura (98%)", "value": 0.98, "zScore": 2.05},
            ]
        },
        "budgetLimit": {"default": None, "min": 10000.0, "max": 1000000.0, "step": 5000.0}
    }
    return InventoryConfigResponse(
        data=config_data,
        meta=ResponseMeta(
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    )


@inventory_router.get("/suppliers", response_model=SuppliersResponse)
def get_suppliers_list():
    """
    Retorna a lista de fornecedores cadastrados na view Externo01.Produto com contagem de SKUs.
    """
    try:
        suppliers = get_inventory_suppliers()
        return SuppliersResponse(
            data=suppliers,
            meta=ResponseMeta(
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        )
    except Exception as e:
        logger.error(f"Erro ao buscar fornecedores de inventário: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao consultar catálogo de fornecedores: {str(e)}")


@inventory_router.post("/predict", response_model=InventoryPredictResponse)
def predict_inventory(request: InventoryPredictRequest):
    """
    Calcula a velocidade de vendas (VMD), autonomia de estoque, estoque de segurança,
    ROP, estoque ideal e quantidade sugerida de compra para todos os SKUs da Fitoherb.
    """
    try:
        result, elapsed_ms = execute_inventory_prediction(request)
        return InventoryPredictResponse(
            data=result,
            meta=ResponseMeta(
                timestamp=datetime.now(timezone.utc).isoformat(),
                executionTimeMs=elapsed_ms
            )
        )
    except Exception as e:
        logger.error(f"Erro no cálculo de previsão de estoque: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro no cálculo de inventário: {str(e)}")


@inventory_router.post("/export-csv")
def export_inventory_csv(request: InventoryPredictRequest):
    """
    Gera e faz o streaming de arquivo CSV para download do plano de compras sugerido.
    """
    try:
        csv_content = generate_inventory_csv(request)
        fornec_slug = f"_{request.fornecedor.lower().replace(' ', '_')}" if request.fornecedor and request.fornecedor != "TODOS" else ""
        filename = f"fitoherb_plano_compras{fornec_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        logger.error(f"Erro na exportação de CSV de compras: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erro na exportação de CSV: {str(e)}")
