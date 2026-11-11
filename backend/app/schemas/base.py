"""Core domain data schemas for initial API endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """Authenticated user profile representation."""

    id: str
    user_id: str
    email: str | None = None
    role: str
    node_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NodeResponse(BaseModel):
    """Pharma supply chain node representation."""

    id: str
    tier: str  # pharmacy, stockist, distributor, manufacturer
    name: str
    region: str
    parent_id: str | None = None
    address: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProductResponse(BaseModel):
    """Pharmaceutical product catalog item."""

    id: str
    name: str
    generic_name: str
    schedule_class: str = "GENERAL"
    is_cold_chain: bool = False
    storage_min_c: float | None = None
    storage_max_c: float | None = None
    is_lifesaving: bool = False
    unit: str = "strip"
    price_per_unit: float
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InventoryItemResponse(BaseModel):
    """Inventory item balance with batch and SKU information."""

    id: str
    node_id: str
    product_id: str
    batch_id: str
    quantity: int
    reserved: int = 0
    safety_stock: int = 10
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    product_name: str | None = None
    batch_no: str | None = None
