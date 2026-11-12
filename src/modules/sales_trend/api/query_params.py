"""
Validação e tipagem de query parameters para os endpoints de Tendência de Vendas (P-081, ADR-003 DA-13).
"""
from typing import Any, Literal, Optional
from fastapi import Query
from pydantic import BaseModel, Field, field_validator


class TrendListQuery(BaseModel):
    """Parâmetros de consulta para o endpoint principal /sales-trend."""
    base_month: Optional[str] = Field(default=None, alias="baseMonth")
    metric: Literal["revenue", "quantity"] = Field(default="revenue")
    group_by: Literal["product", "supplier"] = Field(default="product", alias="groupBy")
    sort_window: int = Field(default=3, alias="sortWindow")
    sort_dir: Literal["asc", "desc"] = Field(default="desc", alias="sortDir")
    view: Literal["all", "rising", "falling", "new"] = Field(default="all")
    q: Optional[str] = Field(default=None)
    min_volume: float = Field(default=0.0, ge=0.0, le=1_000_000_000.0, alias="minVolume")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    active_only: Optional[str] = Field(default=None, alias="activeOnly")

    @field_validator("sort_window", mode="before")
    @classmethod
    def validate_sort_window(cls, v: Any) -> int:
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError("sortWindow deve ser 1, 3, 6 ou 12")
        if val not in (1, 3, 6, 12):
            raise ValueError("sortWindow deve ser 1, 3, 6 ou 12")
        return val

    @field_validator("q")
    @classmethod
    def validate_q(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        if len(trimmed) > 60:
            raise ValueError("q excede 60 caracteres")
        if not trimmed.isdigit() and len(trimmed) < 2:
            raise ValueError("q textual deve possuir no mínimo 2 caracteres")
        return trimmed


class TrendDetailQuery(BaseModel):
    """Parâmetros de consulta para o endpoint de detalhe /supplier-products."""
    supplier_key: str = Field(min_length=1, max_length=200, alias="supplierKey")
    base_month: Optional[str] = Field(default=None, alias="baseMonth")
    metric: Literal["revenue", "quantity"] = Field(default="revenue")
    sort_by: Literal["contribution", "variation"] = Field(default="contribution", alias="sortBy")
    sort_dir: Literal["asc", "desc"] = Field(default="desc", alias="sortDir")
    sort_window: int = Field(default=3, alias="sortWindow")
    q: Optional[str] = Field(default=None)
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @field_validator("sort_window", mode="before")
    @classmethod
    def validate_sort_window(cls, v: Any) -> int:
        try:
            val = int(v)
        except (ValueError, TypeError):
            raise ValueError("sortWindow deve ser 1, 3, 6 ou 12")
        if val not in (1, 3, 6, 12):
            raise ValueError("sortWindow deve ser 1, 3, 6 ou 12")
        return val

    @field_validator("q")
    @classmethod
    def validate_q(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        trimmed = v.strip()
        if not trimmed:
            return None
        if len(trimmed) > 60:
            raise ValueError("q excede 60 caracteres")
        if not trimmed.isdigit() and len(trimmed) < 2:
            raise ValueError("q textual deve possuir no mínimo 2 caracteres")
        return trimmed
