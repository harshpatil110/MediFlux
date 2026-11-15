"""FastAPI endpoints for zero-LLM ultra-fast event ingestion and atomic inventory decrement."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import CurrentUser, get_actor, get_current_user, get_service_db_client, visible_node_ids
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope, SaleEvent, SensorReadingEvent
from app.events.service import apply_sale
from app.graphs.coldchain import run_coldchain_pipeline
from app.services.webhooks import dispatch_webhook_event

logger = logging.getLogger("mediflux.api.events")

router = APIRouter(prefix="/events", tags=["Events & POS Ingestion"])


async def _verify_events_scope(
    authorization: str | None = None,
    x_api_key: str | None = None,
) -> None:
    """Enforce write:events scope if authenticated via X-API-Key."""
    if x_api_key:
        actor = await get_actor(authorization=authorization, x_api_key=x_api_key)
        scopes = actor.scopes
        if "*" not in scopes and "all" not in scopes and "write:events" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient API key scope. Required: 'write:events'",
            )


class NormalizedEvent(BaseModel):
    id: str = Field(..., description="Unique event identifier")
    event_id: str = Field(..., description="Canonical event UUID")
    event_type: str = Field(..., description="Domain event type / topic")
    topic: str = Field(..., description="Event bus topic")
    agent_name: str = Field(..., description="Display name of emitting agent")
    tier: str = Field(..., description="Supply chain tier of event origin")
    summary: str = Field(..., description="One-line operational description")
    correlation_id: str = Field(..., description="Supply cascade correlation ID")
    node_id: str | None = Field(None, description="Originating node ID")
    node_name: str | None = Field(None, description="Originating node display name")
    created_at: str = Field(..., description="Event generation ISO timestamp")
    payload: dict[str, Any] = Field(default_factory=dict, description="Detailed domain event payload")


class RecentEventsResponse(BaseModel):
    events: list[NormalizedEvent] = Field(..., description="List of chronologically ordered recent events")
    count: int = Field(..., description="Number of events returned")
    latest_event_id: str | None = Field(None, description="Latest event ID cursor for subsequent queries")
    server_ts: str = Field(..., description="Server ISO timestamp at query evaluation")


def _format_event_agent_name(event_type: str, payload: dict[str, Any]) -> str:
    if payload.get("agent_name"):
        return str(payload["agent_name"])
    t = event_type.lower()
    if "sale" in t or "pos" in t:
        return "Pharmacy Node Agent"
    if "cascade" in t or "reorder" in t:
        return "Dynamic Balancing Agent"
    if "cold" in t or "telemetry" in t or "sensor" in t:
        return "Cold-Chain Telemetry Agent"
    if "hitl" in t or "approval" in t:
        return "HITL Governance Agent"
    if "reg" in t or "compliance" in t or "quarantine" in t:
        return "Regulatory Compliance Agent"
    if "shipment" in t or "fleet" in t:
        return "Distributor Fleet Agent"
    return "Supply Chain Node Agent"


def _format_event_tier(event_type: str, payload: dict[str, Any]) -> str:
    if payload.get("tier"):
        return str(payload["tier"]).upper()
    t = event_type.lower()
    if "sale" in t or "pos" in t or "rx" in t:
        return "PHARMACY"
    if "reorder" in t or "stockist" in t:
        return "STOCKIST"
    if "shipment" in t or "fleet" in t or "distributor" in t:
        return "DISTRIBUTOR"
    if "production" in t or "mfg" in t or "plant" in t:
        return "MANUFACTURER"
    return "GOVERNANCE"


def _format_event_summary(event_type: str, payload: dict[str, Any]) -> str:
    if payload.get("summary"):
        return str(payload["summary"])
    t = event_type.lower()
    if "sale" in t or "pos" in t:
        qty = payload.get("quantity", 1)
        prod = payload.get("product_name") or payload.get("product_id") or "medicine"
        node = payload.get("node_name") or "Retail Pharmacy"
        return f"Dispensed {qty} unit(s) of {prod} at {node}."
    if "cascade" in t:
        step = payload.get("tier", "Supply Tier")
        return f"Cascade demand signal evaluated at {step}."
    if "cold" in t or "telemetry" in t:
        temp = payload.get("current_temp") or payload.get("temperature", 4.0)
        return f"Cold-chain sensor reading recorded: {temp}°C (Normal)."
    if "hitl" in t:
        return "HITL review requested for order exception."
    return f"Event {event_type} processed successfully."


def _build_normalized_event(
    event_id: str,
    event_type: str,
    node_id: str | None,
    correlation_id: str,
    timestamp: Any,
    payload: dict[str, Any],
) -> NormalizedEvent:
    ts_str = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)
    node_name = payload.get("node_name") or ("Apollo Pharmacy - CP" if node_id and "1111" in str(node_id) else "Assigned Node")
    return NormalizedEvent(
        id=str(event_id),
        event_id=str(event_id),
        event_type=str(event_type),
        topic=str(event_type),
        agent_name=_format_event_agent_name(event_type, payload),
        tier=_format_event_tier(event_type, payload),
        summary=_format_event_summary(event_type, payload),
        correlation_id=str(correlation_id),
        node_id=str(node_id) if node_id else None,
        node_name=node_name,
        created_at=ts_str,
        payload=payload,
    )


@router.get(
    "/recent",
    response_model=RecentEventsResponse,
    summary="Get Recent Normalized Events (Mobile & Polling Fallback)",
    description="Retrieve recent domain events with RLS node scoping, since cursor, topic filters, and rich normalized formatting.",
)
async def get_recent_events(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    since: str | None = Query(default=None, description="Last seen event_id or ISO-8601 timestamp cursor"),
    topics: str | None = Query(default=None, description="Comma-separated topics filter (e.g. pos.sales,cascade.updates)"),
    limit: int = Query(default=50, ge=1, le=100, description="Max number of events to return"),
) -> RecentEventsResponse:
    """Retrieve normalized recent events for mobile activity feed and SSE polling fallback."""
    now_utc = datetime.now(UTC)
    now_iso = now_utc.isoformat()

    # 1. RLS node filtering
    if current_user.role == "admin":
        visible_nodes: set[str] | None = None
    else:
        visible_nodes = set(visible_node_ids(current_user))

    # 2. Topic filtering
    topic_list = [t.strip() for t in topics.split(",") if t.strip()] if topics else None

    # 3. Retrieve matching events
    normalized: list[NormalizedEvent] = []

    # Check in-process event bus history
    history = in_process_event_bus._history
    found_since = since is None

    for evt in history:
        if not found_since:
            if str(evt.event_id) == since or (hasattr(evt, "timestamp") and str(evt.timestamp) == since):
                found_since = True
                continue
            # Also allow timestamp comparison if since is ISO format
            if hasattr(evt, "timestamp") and hasattr(evt.timestamp, "isoformat") and evt.timestamp.isoformat() > since:
                found_since = True

        if not found_since:
            continue

        # Topic filter
        if topic_list and "*" not in topic_list and evt.type not in topic_list:
            continue

        # Node visibility
        if visible_nodes is not None and evt.node_id and str(evt.node_id) not in visible_nodes:
            continue

        normalized.append(
            _build_normalized_event(
                event_id=str(evt.event_id),
                event_type=str(evt.type),
                node_id=str(evt.node_id) if evt.node_id else None,
                correlation_id=str(evt.correlation_id),
                timestamp=evt.timestamp,
                payload=evt.payload or {},
            )
        )

    # If since was not found in history, take the latest limit events
    if since and not found_since and history:
        for evt in history[-limit:]:
            if topic_list and "*" not in topic_list and evt.type not in topic_list:
                continue
            if visible_nodes is not None and evt.node_id and str(evt.node_id) not in visible_nodes:
                continue
            normalized.append(
                _build_normalized_event(
                    event_id=str(evt.event_id),
                    event_type=str(evt.type),
                    node_id=str(evt.node_id) if evt.node_id else None,
                    correlation_id=str(evt.correlation_id),
                    timestamp=evt.timestamp,
                    payload=evt.payload or {},
                )
            )

    # If history is empty or small (e.g. freshly seeded server), provide seeded demo baseline events
    if len(normalized) == 0:
        base_events = [
            {
                "event_id": "seed-evt-001",
                "type": "pos.sales",
                "node_id": "11111111-1111-1111-1111-111111111111",
                "correlation_id": "casc-8f92a1b4c3d2",
                "summary": "Dispensed 1 strip of Azithromycin 500mg at Apollo Pharmacy - CP.",
                "tier": "PHARMACY",
                "agent_name": "Pharmacy POS Agent",
            },
            {
                "event_id": "seed-evt-002",
                "type": "cascade.updates",
                "node_id": "22222222-2222-2222-2222-222222222222",
                "correlation_id": "casc-8f92a1b4c3d2",
                "summary": "Stockist auto-reorder threshold evaluated (0.2s); safety buffer intact.",
                "tier": "STOCKIST",
                "agent_name": "Dynamic Balancing Agent",
            },
            {
                "event_id": "seed-evt-003",
                "type": "coldchain",
                "node_id": "11111111-1111-1111-1111-111111111111",
                "correlation_id": "casc-8f92a1b4c3d2",
                "summary": "Cold storage unit 1 telemetry logged: 4.2°C (Optimal MKT 4.8°C).",
                "tier": "PHARMACY",
                "agent_name": "Cold-Chain Telemetry Agent",
            },
        ]
        for b in base_events:
            if visible_nodes is None or b["node_id"] in visible_nodes:
                normalized.append(
                    _build_normalized_event(
                        event_id=b["event_id"],
                        event_type=b["type"],
                        node_id=b["node_id"],
                        correlation_id=b["correlation_id"],
                        timestamp=now_iso,
                        payload=b,
                    )
                )

    # Slice to limit
    trimmed = normalized[:limit]
    latest_id = trimmed[-1].event_id if trimmed else None

    return RecentEventsResponse(
        events=trimmed,
        count=len(trimmed),
        latest_event_id=latest_id,
        server_ts=now_iso,
    )


@router.get(
    "",
    summary="List Recent Domain Events",
    description="Retrieve recent domain events from the event bus history or database.",
    status_code=status.HTTP_200_OK,
)
async def list_recent_events(
    topic: str | None = Query(default=None, description="Filter by event topic/type"),
    limit: int = Query(default=50, ge=1, le=200, description="Max events to return"),
) -> list[dict[str, Any]]:
    """Retrieve recent events from in-process event bus and database."""
    events: list[dict[str, Any]] = []
    for evt in reversed(in_process_event_bus._history):
        if topic and topic != "*" and evt.type != topic:
            continue
        events.append({
            "event_id": str(evt.event_id),
            "type": evt.type,
            "node_id": str(evt.node_id),
            "correlation_id": str(evt.correlation_id),
            "timestamp": evt.timestamp.isoformat() if hasattr(evt.timestamp, "isoformat") else str(evt.timestamp),
            "payload": evt.payload,
        })
        if len(events) >= limit:
            return events

    if len(events) < limit and settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        try:
            client = get_service_db_client()
            if client:
                q = client.table("events").select("*").order("created_at", desc=True).limit(limit)
                if topic and topic != "*":
                    q = q.eq("type", topic)
                res = q.execute()
                for row in res.data or []:
                    eid = row.get("event_id")
                    if not any(e.get("event_id") == eid for e in events):
                        events.append(row)
                        if len(events) >= limit:
                            break
        except Exception as exc:
            logger.debug("Database event query failed: %s", exc)

    return events


@router.post(
    "",
    summary="Canonical Event Ingestion",
    description="Ingest domain event or POS sale with API key scope enforcement (requires write:events).",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_canonical_event(
    payload: dict[str, Any],
    request: Request,
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> JSONResponse:
    """Ingest either a POS sale event or a generic domain event envelope into the event bus."""
    await _verify_events_scope(authorization=authorization, x_api_key=x_api_key)
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))

    # If it has pharmacy_id and batch_id, treat as SaleEvent
    if "pharmacy_id" in payload and "batch_id" in payload:
        try:
            sale_event = SaleEvent(**payload)
            result = await apply_sale(event=sale_event, correlation_id=correlation_id)
            if result.get("applied", False):
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
                        "remaining_quantity": result.get("remaining_quantity"),
                    },
                )
                await in_process_event_bus.publish("pos.sales", envelope)
                await dispatch_webhook_event(
                    event_type="order.created",
                    data=envelope.payload,
                    node_id=str(sale_event.pharmacy_id),
                    event_id=str(sale_event.event_id),
                )
                return JSONResponse(
                    status_code=status.HTTP_202_ACCEPTED,
                    content={
                        "status": "accepted",
                        "event_id": str(sale_event.event_id),
                        "correlation_id": correlation_id,
                    },
                )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "duplicate",
                    "event_id": str(sale_event.event_id),
                    "correlation_id": correlation_id,
                    "applied": False,
                },
            )
        except Exception as exc:
            logger.warning("Failed parsing SaleEvent in canonical ingestion: %s", exc)

    # Otherwise treat as generic EventEnvelope
    event_id = str(payload.get("event_id") or uuid.uuid4())
    event_type = str(payload.get("type") or "cascade.test")
    node_id = str(payload.get("node_id") or "11111111-1111-1111-1111-111111111111")
    event_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload

    envelope = EventEnvelope(
        event_id=event_id,
        type=event_type,
        node_id=node_id,
        correlation_id=correlation_id,
        payload=event_payload,
    )
    await in_process_event_bus.publish(event_type, envelope)

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "event_id": event_id,
            "correlation_id": correlation_id,
            "type": event_type,
        },
    )


@router.post(
    "/pos",
    summary="Point-of-Sale Event Ingestion Alias",
    status_code=status.HTTP_202_ACCEPTED,
)
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
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> JSONResponse:
    """Ingest a single Point-of-Sale event, atomically apply inventory deduction, and publish to the event bus."""
    await _verify_events_scope(authorization=authorization, x_api_key=x_api_key)
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
        # Dispatch to outbound webhooks
        await dispatch_webhook_event(
            event_type="order.created",
            data=envelope.payload,
            node_id=str(event.pharmacy_id),
            event_id=str(event.event_id),
        )

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
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> JSONResponse:
    """Ingest IoT sensor telemetry reading(s), persist to database, and run cold-chain evaluation."""
    await _verify_events_scope(authorization=authorization, x_api_key=x_api_key)
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

    if eval_result.get("quarantined", False):
        await dispatch_webhook_event(
            event_type="batch.quarantined",
            data={
                "batch_id": batch_id,
                "node_id": node_id,
                "explanation": eval_result.get("explanation"),
                "quarantine_action_id": eval_result.get("quarantine_action_id"),
                "correlation_id": correlation_id,
            },
            node_id=node_id,
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


