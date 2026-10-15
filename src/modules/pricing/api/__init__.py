"""
Pricing API Layer: Router and Schemas.
"""
from src.modules.pricing.api.schemas import (
    AutoTuneData,
    AutoTuneRequest,
    AutoTuneResponse,
    OptimalParams,
    PricingRequest,
    PricingSummary,
    ProductPreview,
)
def __getattr__(name: str):
    if name == "pricing_router":
        from src.modules.pricing.api.router import pricing_router
        return pricing_router
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "pricing_router",
    "PricingRequest",
    "ProductPreview",
    "PricingSummary",
    "AutoTuneRequest",
    "OptimalParams",
    "AutoTuneData",
    "AutoTuneResponse",
]

