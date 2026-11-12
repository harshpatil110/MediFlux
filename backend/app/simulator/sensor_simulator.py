"""Environmental sensor telemetry simulator stub for cold-chain monitoring (Task 9/Task 20)."""

import logging

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.simulator.sensor")


class SensorSimulator:
    """Interface stub for environmental cold-chain sensor telemetry simulation."""

    def __init__(self, vehicle_id: str = "DL-01-RF-1000") -> None:
        self.vehicle_id = vehicle_id

    async def emit_telemetry(self, vehicle_id: str | None = None, temp_celsius: float = 4.5) -> None:
        """Stub for publishing SensorReadingEvent to coldchain topic."""
        target_vehicle = vehicle_id or self.vehicle_id
        envelope = EventEnvelope(
            type="coldchain.telemetry",
            node_id=target_vehicle,
            payload={
                "vehicle_id": target_vehicle,
                "temperature_celsius": float(temp_celsius),
                "is_breached": temp_celsius < 2.0 or temp_celsius > 8.0,
            },
        )
        await in_process_event_bus.publish("coldchain.telemetry", envelope)
        logger.info("Coldchain telemetry stub emitted: vehicle=%s, temp=%.2f C", target_vehicle, temp_celsius)
