"""
Roteador RESTful FastAPI para o Módulo de Previsão de Estoque e Compras (Contrato 2.0.0).

Implementa os endpoints `/api/v1/inventory/*` sob a Política de Estoque Mínimo/Máximo
por dias de cobertura (regras P-053 a P-056 e decisões ADR-001 DA-05 a DA-11).
"""
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, HTTPException, Response

from src.modules.inventory.api.schemas import (
    InventoryConfigResponse,
    InventoryPredictRequest,
    InventoryPredictResponse,
    ResponseMeta,
    SuppliersResponse,
)
from src.modules.inventory.service.inventory_service import (
    build_csv_filename,
    execute_inventory_prediction,
    generate_inventory_csv,
    get_inventory_parameter_config,
    get_inventory_suppliers,
)

logger = logging.getLogger(__name__)

CSV_MEDIA_TYPE = "text/csv; charset=utf-8"

# DA-11 / Seções 4.1, 5.3 e 6.3 do contrato 2.0.0: mensagens genéricas sem vazamento de exceções internas.
SUPPLIERS_ERROR_DETAIL = (
    "Não foi possível consultar o catálogo de fornecedores. Tente novamente em instantes."
)
PREDICT_ERROR_DETAIL = (
    "Não foi possível calcular a previsão de estoque. Tente novamente em instantes."
)
EXPORT_CSV_ERROR_DETAIL = (
    "Não foi possível gerar o arquivo CSV do plano de compras. Tente novamente em instantes."
)

VALIDATION_ERROR_RESPONSE_SPEC = {
    "description": "Parâmetros fora de faixa, tipo inválido ou violação das regras INV-001 / INV-002.",
}

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory Predictor"])


@inventory_router.get(
    "/health",
    summary="Sonda de saúde do serviço de estoque",
    description="Verifica a disponibilidade imediata do módulo de previsão de estoque.",
)
def inventory_health_check():
    """Retorna o status operacional da API de estoque (sonda de infraestrutura)."""
    return {"status": "healthy", "service": "fitoherb-inventory-api"}


@inventory_router.get(
    "/config",
    response_model=InventoryConfigResponse,
    summary="Padrões e faixas dos parâmetros da Política Mín/Máx",
    description=(
        "Retorna os valores padrão, mínimos, máximos e passos dos quatro controles deslizantes "
        "do modal de parâmetros da tela (Janela de Vendas, Lead Time, Dias Mínimo e Dias Máximo)."
    ),
)
def get_inventory_config():
    """Retorna a configuração dos parâmetros da tela conforme a seção 3.1 do contrato 2.0.0."""
    return InventoryConfigResponse(
        data=get_inventory_parameter_config(),
        meta=ResponseMeta(
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
    )


@inventory_router.get(
    "/suppliers",
    response_model=SuppliersResponse,
    summary="Lista de fornecedores e contagem de SKUs ativos",
    description="Retorna os fornecedores cadastrados no catálogo de produtos iniciando pela opção TODOS.",
    responses={
        500: {"description": SUPPLIERS_ERROR_DETAIL},
    },
)
def get_suppliers_list():
    """Consulta a lista de fornecedores ativos com contagem de SKUs (seção 4 do contrato 2.0.0)."""
    try:
        suppliers = get_inventory_suppliers()
        return SuppliersResponse(
            data=suppliers,
            meta=ResponseMeta(
                timestamp=datetime.now(timezone.utc).isoformat(),
            ),
        )
    except Exception:
        logger.error("Erro ao consultar o catálogo de fornecedores de inventário.", exc_info=True)
        raise HTTPException(status_code=500, detail=SUPPLIERS_ERROR_DETAIL)


@inventory_router.post(
    "/predict",
    response_model=InventoryPredictResponse,
    summary="Cálculo de previsão de estoque e compras pela Política Mín/Máx",
    description=(
        "Calcula para cada SKU do catálogo a VMD, Dias de Cobertura, Estoque Mínimo, "
        "Estoque Máximo, Quantidade Sugerida de Compra, Investimento e Status Operacional "
        "(P-053 a P-056), além dos KPIs agregados e do eco da política aplicada."
    ),
    responses={
        422: VALIDATION_ERROR_RESPONSE_SPEC,
        500: {"description": PREDICT_ERROR_DETAIL},
    },
)
def predict_inventory(request: InventoryPredictRequest):
    """Executa o cálculo da Política Mín/Máx e devolve o envelope padronizado 2.0.0."""
    try:
        result, elapsed_ms = execute_inventory_prediction(request)
        return InventoryPredictResponse(
            data=result,
            meta=ResponseMeta(
                timestamp=datetime.now(timezone.utc).isoformat(),
                executionTimeMs=elapsed_ms,
            ),
        )
    except Exception:
        logger.error("Erro no cálculo de previsão de estoque pela Política Mín/Máx.", exc_info=True)
        raise HTTPException(status_code=500, detail=PREDICT_ERROR_DETAIL)


@inventory_router.post(
    "/export-csv",
    summary="Exportação do plano de compras em CSV (Política Mín/Máx)",
    description=(
        "Gera o arquivo CSV (UTF-8 com BOM, separador ';' e decimal ',') com as 17 colunas "
        "da Política Mín/Máx e paridade integral com os números de `/predict` (P-056.5, P-056.6)."
    ),
    responses={
        422: VALIDATION_ERROR_RESPONSE_SPEC,
        500: {"description": EXPORT_CSV_ERROR_DETAIL},
    },
)
def export_inventory_csv(request: InventoryPredictRequest):
    """Gera e transmite o CSV do plano de compras com nome de arquivo sanitizado (DA-11)."""
    try:
        csv_content = generate_inventory_csv(request)
        filename = build_csv_filename(request.fornecedor)
        return Response(
            content=csv_content,
            media_type=CSV_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception:
        logger.error("Erro na exportação de CSV do plano de compras.", exc_info=True)
        raise HTTPException(status_code=500, detail=EXPORT_CSV_ERROR_DETAIL)
