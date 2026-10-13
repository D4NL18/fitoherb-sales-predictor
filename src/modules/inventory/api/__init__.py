"""
Camada de API REST do modulo de Estoque e Compras.
"""
from src.modules.inventory.api.router import inventory_router
from src.modules.inventory.api.schemas import (
    InventoryConfigResponse,
    InventoryPredictRequest,
    InventoryPredictResponse,
    SuppliersResponse,
)

__all__ = [
    "inventory_router",
    "InventoryPredictRequest",
    "InventoryPredictResponse",
    "InventoryConfigResponse",
    "SuppliersResponse",
]
