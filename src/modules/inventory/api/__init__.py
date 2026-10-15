"""
Camada de API REST do modulo de Estoque e Compras.
"""
from src.modules.inventory.api.schemas import (
    InventoryConfigResponse,
    InventoryPredictRequest,
    InventoryPredictResponse,
    SuppliersResponse,
)


def __getattr__(name: str):
    if name == "inventory_router":
        from src.modules.inventory.api.router import inventory_router
        return inventory_router
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "inventory_router",
    "InventoryPredictRequest",
    "InventoryPredictResponse",
    "InventoryConfigResponse",
    "SuppliersResponse",
]

