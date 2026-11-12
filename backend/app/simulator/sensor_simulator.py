"""IoT Sensor Telemetry Simulator for Cold-Chain Monitoring (Task 20).

Supports simulated temperature, humidity, and physical shock telemetry across:
- Stockist Hubs (node_id)
- Active Transit Shipments (shipment_id)
With modes: normal, excursion, and shock.
"""

import argparse
import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope, SensorReadingEvent

logger = logging.getLogger("mediflux.simulator.sensor")


class SensorSimulator:
    """Environmental cold-chain sensor simulator for hubs, vehicles, and active shipments."""

    def __init__(
        self,
        vehicle_id: str = "DL-01-RF-1000",
        base_url: str = "http://localhost:8000",
    ) -> None:
        self.vehicle_id = vehicle_id
        self.base_url = base_url.rstrip("/")

    # -------------------------------------------------------------------------
    # Legacy Telemetry Stub (Backwards Compatibility with Task 9)
    # -------------------------------------------------------------------------
    async def emit_telemetry(self, vehicle_id: str | None = None, temp_celsius: float = 4.5) -> None:
        """Publish SensorReadingEvent to coldchain topic (Task 9 stub support)."""
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

    # -------------------------------------------------------------------------
    # Canonical Reading Generation
    # -------------------------------------------------------------------------
    def generate_reading(
        self,
        batch_id: str,
        mode: Literal["normal", "excursion", "shock"] = "normal",
        node_id: str | None = None,
        shipment_id: str | None = None,
        step: int = 0,
        product_id: str | None = None,
        duration_minutes: float = 15.0,
        correlation_id: str | None = None,
    ) -> SensorReadingEvent:
        """Construct a single canonical SensorReadingEvent based on target context and simulation mode."""
        corr_id = correlation_id or str(uuid.uuid4())
        effective_node = node_id or "22222222-2222-2222-2222-222222222222"
        sensor_tag = f"IOT-{effective_node[:8].upper()}-01"

        if mode == "normal":
            temp = round(4.5 + ((step * 0.3) % 1.5), 2)
            hum = round(52.0 + ((step * 1.5) % 8.0), 2)
            shock = round(0.2 + ((step * 0.05) % 0.3), 2)
        elif mode == "excursion":
            # Progressive thermal breach climbing above 8.0 C
            temp = round(11.5 + (step * 2.2), 2)
            hum = round(64.0 + (step % 5), 2)
            shock = round(0.4 + (step * 0.1), 2)
        elif mode == "shock":
            # Normal thermal bounds with severe physical impact breach (>= 8.5g)
            temp = round(4.8 + ((step * 0.1) % 0.5), 2)
            hum = 52.0
            shock = round(8.8 + (step * 0.4), 2)
        else:
            temp = 5.0
            hum = 50.0
            shock = 0.2

        now_iso = datetime.now(UTC).isoformat()

        return SensorReadingEvent(
            event_id=str(uuid.uuid4()),
            batch_id=batch_id,
            product_id=product_id,
            node_id=effective_node,
            shipment_id=shipment_id,
            sensor_id=sensor_tag,
            temperature_c=temp,
            temperature=temp,
            humidity=hum,
            shock_g=shock,
            duration_minutes=duration_minutes,
            mode=mode,
            ts=now_iso,
            correlation_id=corr_id,
        )

    # -------------------------------------------------------------------------
    # Simulation Runner
    # -------------------------------------------------------------------------
    async def run_simulation(
        self,
        batch_id: str,
        mode: Literal["normal", "excursion", "shock"] = "normal",
        steps: int = 3,
        node_id: str | None = None,
        shipment_id: str | None = None,
        product_id: str | None = None,
        duration_minutes: float = 15.0,
        client: httpx.AsyncClient | Any | None = None,
    ) -> list[dict[str, Any]]:
        """Generate and post a series of sensor readings to the sensor event ingestion endpoint."""
        results: list[dict[str, Any]] = []
        corr_id = str(uuid.uuid4())

        for step in range(steps):
            reading = self.generate_reading(
                batch_id=batch_id,
                mode=mode,
                node_id=node_id,
                shipment_id=shipment_id,
                step=step,
                product_id=product_id,
                duration_minutes=duration_minutes,
                correlation_id=corr_id,
            )

            payload = reading.model_dump(mode="json")

            if client is not None:
                resp = await client.post("/api/v1/events/sensor", json=payload)
                if resp.status_code in (200, 201, 202):
                    results.append(resp.json())
                else:
                    logger.warning("Simulation post failed (%d): %s", resp.status_code, resp.text)
            else:
                async with httpx.AsyncClient(base_url=self.base_url) as http_client:
                    resp = await http_client.post("/api/v1/events/sensor", json=payload)
                    if resp.status_code in (200, 201, 202):
                        results.append(resp.json())
                    else:
                        logger.warning("Simulation post failed (%d): %s", resp.status_code, resp.text)

        return results


def main() -> None:
    """Command-line entrypoint for running sensor telemetry simulation."""
    parser = argparse.ArgumentParser(description="MediFlux IoT Sensor Telemetry Simulator")
    parser.add_argument("--batch", type=str, default="BIO-INS-01", help="Batch ID to simulate")
    parser.add_argument("--mode", type=str, choices=["normal", "excursion", "shock"], default="normal", help="Simulation mode")
    parser.add_argument("--steps", type=int, default=3, help="Number of telemetry reading steps")
    parser.add_argument("--node", type=str, default=None, help="Stockist hub or plant node ID")
    parser.add_argument("--shipment", type=str, default=None, help="Transit shipment ID")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Backend base URL")
    args = parser.parse_args()

    sim = SensorSimulator(base_url=args.url)
    res = asyncio.run(
        sim.run_simulation(
            batch_id=args.batch,
            mode=args.mode,
            steps=args.steps,
            node_id=args.node,
            shipment_id=args.shipment,
        )
    )
    print(f"Simulation completed. {len(res)} telemetry reading(s) evaluated.")


if __name__ == "__main__":
    main()
