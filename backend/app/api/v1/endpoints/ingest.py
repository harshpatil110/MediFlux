"""Live legacy system ingestion endpoint with Restricted Execution Guard translation (Task 17)."""

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.security import get_actor
from app.events.bus import in_process_event_bus
from app.events.models import BatchUpdate, EventEnvelope, SaleEvent
from app.events.service import apply_sale
from app.graphs.forge import get_adapter
from app.modules_runtime.guard import (
    GuardViolationError,
    ModuleExecutionError,
    ModuleTimeoutError,
    SubprocessRunner,
)

logger = logging.getLogger("mediflux.api.v1.ingest")

router = APIRouter(prefix="/ingest", tags=["Live Legacy Ingestion"])


@router.post(
    "/{adapter_id}",
    summary="Ingest Legacy Format Payload via Active Adapter",
    description="Translates legacy payloads (CSV, XML, JSON) via active sandboxed adapter and forwards canonical event to supply chain pipeline.",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_legacy_payload(
    adapter_id: str,
    request: Request,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> JSONResponse:
    """Ingest raw legacy payload, translate via adapter, validate against canonical schema, and route to event bus."""
    if x_api_key:
        actor = await get_actor(x_api_key=x_api_key)
        scopes = actor.scopes
        if (
            "*" not in scopes
            and "all" not in scopes
            and "manage:adapters" not in scopes
            and "write:events" not in scopes
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope. Required: 'manage:adapters'",
            )

    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # 1. Lookup active adapter
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adapter '{adapter_id}' not found.",
        )

    if adapter.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Adapter '{adapter_id}' is inactive or has status '{adapter.get('status')}'.",
        )

    # 2. Extract raw payload from request
    content_type = request.headers.get("content-type", "").lower()
    raw_body = await request.body()
    decoded_text = raw_body.decode("utf-8") if raw_body else ""

    raw_input: Any = decoded_text
    if "application/json" in content_type:
        try:
            parsed_json = json.loads(decoded_text)
            if isinstance(parsed_json, dict) and "payload" in parsed_json and len(parsed_json) == 1:
                raw_input = parsed_json["payload"]
            else:
                raw_input = parsed_json
        except Exception:
            raw_input = decoded_text

    # 3. Execute adapter inside Task 8 Restricted Execution Guard
    source_code = adapter.get("source_code") or adapter.get("generated_parser_code") or ""
    try:
        translated_dict, duration_ms = SubprocessRunner.execute_module(
            source_code=source_code,
            input_data=raw_input,
            timeout=3.0,
        )
    except GuardViolationError as exc:
        logger.error("Adapter guard violation during live ingestion: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Adapter execution blocked by security guard: {exc}",
        ) from exc
    except (ModuleTimeoutError, ModuleExecutionError, Exception) as exc:
        logger.error("Adapter execution runtime error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Adapter execution error: {exc}",
        ) from exc

    target_schema = adapter.get("target_schema", "SaleEvent")

    # 4. Handle BatchUpdate (Manufacturer / Production tier)
    if target_schema == "BatchUpdate" or "batch_number" in translated_dict:
        try:
            batch_event = BatchUpdate.model_validate(translated_dict)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Translated output failed canonical BatchUpdate validation: {exc}",
            ) from exc

        envelope = EventEnvelope(
            event_id=str(batch_event.event_id),
            type="batch.update",
            node_id=str(batch_event.node_id),
            correlation_id=correlation_id,
            timestamp=batch_event.timestamp,
            payload=batch_event.model_dump(mode="json"),
        )
        await in_process_event_bus.publish("batch.update", envelope)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "accepted",
                "event_type": "batch.update",
                "canonical_event": batch_event.model_dump(mode="json"),
                "correlation_id": correlation_id,
                "execution_duration_ms": duration_ms,
            },
        )

    # 5. Handle SaleEvent (Pharmacy / Retail POS tier)
    try:
        sale_event = SaleEvent.model_validate(translated_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Translated output failed canonical SaleEvent validation: {exc}",
        ) from exc

    # Execute atomic inventory decrement and duplicate check
    apply_result = await apply_sale(event=sale_event, correlation_id=correlation_id)

    # Broadcast to pos.sales on EventBus
    if apply_result.get("applied", False):
        envelope = EventEnvelope(
            event_id=str(sale_event.event_id),
            type="pos.sales",
            node_id=str(sale_event.pharmacy_id),
            correlation_id=correlation_id,
            timestamp=sale_event.timestamp,
            payload={
                "pharmacy_id": str(sale_event.pharmacy_id),
                "product_id": str(sale_event.product_id),
                "batch_id": str(sale_event.batch_id),
                "quantity": sale_event.quantity,
                "source": sale_event.source,
                "remaining_quantity": apply_result.get("remaining_quantity"),
            },
        )
        await in_process_event_bus.publish("pos.sales", envelope)

    is_applied = apply_result.get("applied", False)
    status_code = status.HTTP_202_ACCEPTED if is_applied else status.HTTP_200_OK
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "accepted" if is_applied else "duplicate",
            "event_type": "pos.sales",
            "canonical_event": sale_event.model_dump(mode="json"),
            "correlation_id": correlation_id,
            "inventory_decrement": apply_result,
            "execution_duration_ms": duration_ms,
        },
    )
