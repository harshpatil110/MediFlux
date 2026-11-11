"""Domain event schemas for MediFlux supply chain cascade."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """Base domain event envelope representing state changes and supply chain signals."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    tier: str  # pharmacy, stockist, distributor, manufacturer, compliance, coldchain
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DispenseEventPayload(BaseModel):
    """Payload emitted when a retail pharmacy counter dispenses a single unit/strip."""

    pharmacy_id: str
    medicine_id: str
    medicine_name: str
    batch_number: str
    quantity_units: int = 1
    unit_price_inr: float
    prescription_id: str | None = None
    patient_hash: str | None = None


class ReorderDemandPayload(BaseModel):
    """Demand propagation signal sent to stockist or distributor."""

    source_tier: str
    target_tier: str
    medicine_id: str
    requested_quantity: int
    urgency_level: str = "normal"  # normal, urgent, emergency
    trigger_reason: str = "min_stock_breach"
