"""FastAPI endpoints for zero-LLM ultra-fast event ingestion and atomic inventory decrement."""

import logging
import uuid

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import JSONResponse

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope, SaleEvent
from app.events.service import apply_sale

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

