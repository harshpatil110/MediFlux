"""FastAPI endpoints for zero-LLM ultra-fast event ingestion and atomic inventory decrement."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope, SaleEvent, SensorReadingEvent
from app.events.service import apply_sale
from app.graphs.coldchain import run_coldchain_pipeline

logger = logging.getLogger("mediflux.api.events")

router = APIRouter(prefix="/events", tags=["Events & POS Ingestion"])


@router.post(
    "/sale",
    summary="Ingest Point-of-Sale Dispense Event",
    description="Atomic, zero-LLM retail POS sale ingestion that decrements inventory and broadcasts to pos.sales.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_sale_event(
    event: SaleEvent,
    request: Request,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> JSONResponse:
    """Ingest a single Point-of-Sale event, atomically apply inventory deduction, and publish to the event bus."""
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # 1. Execute atomic sale and idempotency check
    result = await apply_sale(event=event, correlation_id=correlation_id)

    # 2. If new sale applied, broadcast to the event bus
    if result.get("applied", False):
        envelope = EventEnvelope(
            event_id=str(event.event_id),
            type="pos.sales",
            node_id=str(event.pharmacy_id),
            correlation_id=correlation_id,
            timestamp=event.timestamp,
            payload={
                "pharmacy_id": str(event.pharmacy_id),
                "product_id": str(event.product_id),
                "batch_id": str(event.batch_id),
                "quantity": event.quantity,
                "source": event.source,
                "remaining_quantity": result.get("remaining_quantity"),
            },
        )
        await in_process_event_bus.publish("pos.sales", envelope)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "accepted",
                "event_id": str(event.event_id),
                "correlation_id": correlation_id,
            },
        )

    # Duplicate idempotent response
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "duplicate",
            "event_id": str(event.event_id),
            "correlation_id": correlation_id,
            "applied": False,
        },
    )


@router.post(
    "/sale/batch",
    summary="Batch Ingest Point-of-Sale Dispense Events",
    description="Batch ingestion endpoint for simulated bulk POS sales and benchmark load testing.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_sale_batch(
    events: list[SaleEvent],
    request: Request,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> JSONResponse:
    """Ingest a batch of POS sales, applying each atomically and broadcasting to the bus."""
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    processed_ids: list[str] = []

    for event in events:
        res = await apply_sale(event=event, correlation_id=correlation_id)
        if res.get("applied", False):
            envelope = EventEnvelope(
                event_id=str(event.event_id),
                type="pos.sales",
                node_id=str(event.pharmacy_id),
                correlation_id=correlation_id,
                timestamp=event.timestamp,
                payload={
                    "pharmacy_id": str(event.pharmacy_id),
                    "product_id": str(event.product_id),
                    "batch_id": str(event.batch_id),
                    "quantity": event.quantity,
                    "source": event.source,
                },
            )
            await in_process_event_bus.publish("pos.sales", envelope)
            processed_ids.append(str(event.event_id))

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "processed": len(processed_ids),
            "events": processed_ids,
            "correlation_id": correlation_id,
        },
    )


@router.post(
    "/sensor",
    summary="Ingest IoT Sensor Telemetry Reading",
    description="Ingest cold-chain sensor telemetry, record idempotently, evaluate via Cold-Chain Graph, and execute auto-quarantine.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_sensor_event(
    request: Request,
    reading: SensorReadingEvent | list[SensorReadingEvent] | dict[str, Any] | list[dict[str, Any]],
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
) -> JSONResponse:
    """Ingest IoT sensor telemetry reading(s), persist to database, and run cold-chain evaluation."""
    # Normalize single reading vs list
    raw_list: list[Any] = reading if isinstance(reading, list) else [reading]
    normalized_readings: list[dict[str, Any]] = []

    # Extract correlation_id with precedence: Header -> Reading payload -> Request state -> UUID
    first_dict = raw_list[0].model_dump(mode="json") if hasattr(raw_list[0], "model_dump") else dict(raw_list[0]) if raw_list else {}
    correlation_id = (
        x_correlation_id
        or first_dict.get("correlation_id")
        or getattr(request.state, "correlation_id", None)
        or str(uuid.uuid4())
    )

    event_ids: list[str] = []

    for r in raw_list:
        p = r.model_dump(mode="json") if hasattr(r, "model_dump") else dict(r)
        evt_id = str(p.get("event_id") or uuid.uuid4())
        p["event_id"] = evt_id
        p["correlation_id"] = p.get("correlation_id") or correlation_id
        normalized_readings.append(p)
        event_ids.append(evt_id)

        # Idempotent persistence in public.events
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            try:
                client = get_service_db_client()
                if client:
                    client.table("events").upsert({
                        "event_id": evt_id,
                        "type": "sensor.reading",
                        "node_id": p.get("node_id"),
                        "correlation_id": p.get("correlation_id"),
                        "payload": p,
                    }, on_conflict="event_id").execute()

                    client.table("sensor_readings").insert({
                        "id": str(uuid.uuid4()),
                        "event_id": evt_id,
                        "batch_id": p.get("batch_id"),
                        "node_id": p.get("node_id"),
                        "temperature_c": float(p.get("temperature_c") or p.get("temperature") or 5.0),
                        "humidity_pct": float(p.get("humidity") or 50.0),
                        "shock_g": float(p.get("shock_g") or 0.0),
                        "duration_minutes": float(p.get("duration_minutes") or 15.0),
                        "mode": str(p.get("mode") or "normal"),
                        "correlation_id": correlation_id,
                    }).execute()
            except Exception as exc:
                logger.debug("Supabase sensor event ingestion failed: %s", exc)

    # Primary target batch
    primary = normalized_readings[0] if normalized_readings else {}
    batch_id = str(primary.get("batch_id") or "BIO-INS-01")
    node_id = str(primary.get("node_id") or "22222222-2222-2222-2222-222222222222")
    shipment_id = primary.get("shipment_id")
    product_id = primary.get("product_id")

    eval_result = await run_coldchain_pipeline(
        batch_id=batch_id,
        readings=normalized_readings,
        node_id=node_id,
        shipment_id=shipment_id,
        product_id=product_id,
        correlation_id=correlation_id,
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "evaluated",
            "batch_id": batch_id,
            "decision": eval_result.get("decision"),
            "shelf_life_estimate": eval_result.get("shelf_life_estimate"),
            "explanation": eval_result.get("explanation"),
            "quarantined": eval_result.get("quarantined", False),
            "quarantine_action_id": eval_result.get("quarantine_action_id"),
            "rebalance_result": eval_result.get("rebalance_result"),
            "correlation_id": correlation_id,
            "events": event_ids,
        },
    )


