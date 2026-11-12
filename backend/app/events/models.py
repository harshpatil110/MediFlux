"""Domain event schemas and envelopes for MediFlux supply chain cascade."""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    """Generic envelope wrapping all domain events across the 4-tier supply chain."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., description="Event topic / type, e.g. pos.sales, cascade.updates")
    node_id: str = Field(..., description="Originating node ID (e.g. pharmacy, stockist, plant)")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)

    # Backward compatibility properties for legacy agent references
    @property
    def event_type(self) -> str:
        return self.type

    @property
    def tier(self) -> str:
        return self.payload.get("tier", "unknown")


# Backward compatibility alias
DomainEvent = EventEnvelope


class SaleEvent(BaseModel):
    """Point-of-Sale dispense event for instantaneous single-unit propagation."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pharmacy_id: str = Field(..., description="ID of the dispensing pharmacy node")
    product_id: str = Field(..., description="Master catalog product ID")
    batch_id: str = Field(..., description="Dispensed pharmaceutical batch ID")
    quantity: int = Field(default=1, ge=1, description="Quantity dispensed in units / strips")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(default="pos", description="Event source identifier")


class ReturnEvent(BaseModel):
    """Inventory return event from retail counter or stockist."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pharmacy_id: str = Field(..., description="Originating pharmacy or stockist node")
    product_id: str = Field(..., description="Master catalog product ID")
    batch_id: str = Field(..., description="Returned batch ID")
    quantity: int = Field(..., ge=1, description="Quantity returned")
    reason: str = Field(..., description="Reason for return, e.g. damaged, recall, customer")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExpiryEvent(BaseModel):
    """Pharmaceutical batch expiry notification event."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = Field(..., description="Node where batch expired")
    product_id: str = Field(..., description="Master catalog product ID")
    batch_id: str = Field(..., description="Expired batch ID")
    quantity_expired: int = Field(..., ge=1, description="Expired quantity in stock")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SensorReadingEvent(BaseModel):
    """Cold-chain IoT telemetry event for temperature and humidity tracking."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = Field(..., description="Node or vehicle ID holding the sensor")
    sensor_id: str = Field(..., description="Physical or virtual IoT sensor identifier")
    temperature: float = Field(..., description="Current temperature in Celsius")
    humidity: float = Field(..., description="Relative humidity percentage")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchUpdate(BaseModel):
    """Canonical production/batch update event model for manufacturer ERP dispatches."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: str = Field(..., description="Manufacturing plant or warehouse node ID")
    product_id: str = Field(..., description="Master catalog product ID / SKU")
    batch_number: str = Field(..., description="Batch or lot number")
    quantity: int = Field(..., ge=1, description="Quantity manufactured or dispatched")
    mfg_date: str | None = Field(default=None, description="Manufacturing date in YYYY-MM-DD")
    exp_date: str | None = Field(default=None, description="Expiry date in YYYY-MM-DD")
    status: str = Field(default="released", description="Batch status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispenseEventPayload(BaseModel):
    """Legacy payload emitted when a retail pharmacy counter dispenses a single unit/strip."""

    pharmacy_id: str
    medicine_id: str
    medicine_name: str
    batch_number: str
    quantity_units: int = 1
    unit_price_inr: float = 0.0
    prescription_id: str | None = None
    patient_hash: str | None = None


class ReorderDemandPayload(BaseModel):
    """Legacy demand propagation signal sent to stockist or distributor."""

    source_tier: str
    target_tier: str
    medicine_id: str
    requested_quantity: int
    urgency_level: str = "normal"  # normal, urgent, emergency
    trigger_reason: str = "min_stock_breach"
