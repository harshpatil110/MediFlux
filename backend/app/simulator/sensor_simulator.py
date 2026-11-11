"""Cold chain IoT temperature and humidity sensor telemetry simulator."""

import logging
import random

from app.events.bus import event_bus
from app.events.models import DomainEvent

logger = logging.getLogger(__name__)


class SensorSimulator:
    """Simulates real-time IoT sensors aboard cold-chain transit vehicles."""

    def __init__(self, shipment_id: str = "SHIP-COLD-9981") -> None:
        self.shipment_id = shipment_id

    async def emit_telemetry(
        self,
        base_temp_celsius: float = 4.5,
        inject_excursion: bool = False,
    ) -> DomainEvent:
        """Emit a sensor reading event."""
        temp = base_temp_celsius + random.uniform(-0.5, 0.5)
        if inject_excursion:
            temp += random.uniform(6.0, 10.0)

        event = DomainEvent(
            event_type="pharma.coldchain.telemetry",
            tier="coldchain",
            payload={
                "shipment_id": self.shipment_id,
                "temperature_celsius": round(temp, 2),
                "target_range": [2.0, 8.0],
                "humidity_rh": round(random.uniform(45.0, 55.0), 1),
                "is_breached": temp < 2.0 or temp > 8.0,
            },
        )

        await event_bus.publish(event)
        logger.info(
            "Cold chain sensor telemetry: %s temp=%.2f C (breached=%s)",
            self.shipment_id,
            temp,
            temp < 2.0 or temp > 8.0,
        )
        return event
