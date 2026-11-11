"""Retail Pharmacy Point-of-Sale (POS) event simulator.

Simulates the dispensing of 1 strip of medicine at a retail pharmacy counter
to trigger the automated 4-tier demand propagation cascade.
"""

import logging
import uuid

from app.events.bus import event_bus
from app.events.models import DispenseEventPayload, DomainEvent

logger = logging.getLogger(__name__)


class POSSimulator:
    """Simulates retail counter checkout dispensing events."""

    def __init__(self, pharmacy_id: str = "PHARM-DELHI-001") -> None:
        self.pharmacy_id = pharmacy_id
        self._running = False

    async def emit_sale(
        self,
        medicine_id: str = "MED-AZI-500",
        medicine_name: str = "Azithromycin 500mg",
        batch_number: str = "BATCH-2026-X01",
        quantity_units: int = 1,
        unit_price_inr: float = 120.0,
    ) -> DomainEvent:
        """Emit a single dispense event on the event bus."""
        payload = DispenseEventPayload(
            pharmacy_id=self.pharmacy_id,
            medicine_id=medicine_id,
            medicine_name=medicine_name,
            batch_number=batch_number,
            quantity_units=quantity_units,
            unit_price_inr=unit_price_inr,
            patient_hash=str(uuid.uuid4())[:8],
        )

        event = DomainEvent(
            event_type="pharma.retail.dispensed",
            tier="pharmacy",
            payload=payload.model_dump(),
        )

        await event_bus.publish(event)
        logger.info(
            "POS simulated dispense: %s x %d strip(s) at %s",
            medicine_name,
            quantity_units,
            self.pharmacy_id,
        )
        return event
