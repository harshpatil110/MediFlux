"""Server-Sent Events (SSE) streaming and replay generator."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.events.sse")


def _format_sse_data(event: EventEnvelope) -> str:
    """Format event into rich normalized JSON string conforming to mobile stream contract."""
    payload = event.payload or {}
    ts_str = event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp)

    agent_name = payload.get("agent_name")
    if not agent_name:
        t = event.type.lower()
        if "sale" in t or "pos" in t:
            agent_name = "Pharmacy Node Agent"
        elif "cascade" in t or "reorder" in t:
            agent_name = "Dynamic Balancing Agent"
        elif "cold" in t or "telemetry" in t or "sensor" in t:
            agent_name = "Cold-Chain Telemetry Agent"
        elif "hitl" in t or "approval" in t:
            agent_name = "HITL Governance Agent"
        elif "reg" in t or "compliance" in t or "quarantine" in t:
            agent_name = "Regulatory Compliance Agent"
        elif "shipment" in t or "fleet" in t:
            agent_name = "Distributor Fleet Agent"
        else:
            agent_name = "Supply Chain Node Agent"

    tier = payload.get("tier")
    if not tier:
        t = event.type.lower()
        if "sale" in t or "pos" in t or "rx" in t:
            tier = "PHARMACY"
        elif "reorder" in t or "stockist" in t:
            tier = "STOCKIST"
        elif "shipment" in t or "fleet" in t or "distributor" in t:
            tier = "DISTRIBUTOR"
        elif "production" in t or "mfg" in t or "plant" in t:
            tier = "MANUFACTURER"
        else:
            tier = "GOVERNANCE"
    else:
        tier = str(tier).upper()

    summary = payload.get("summary")
    if not summary:
        t = event.type.lower()
        if "sale" in t or "pos" in t:
            qty = payload.get("quantity", 1)
            prod = payload.get("product_name") or payload.get("product_id") or "medicine"
            summary = f"Dispensed {qty} unit(s) of {prod}."
        elif "cascade" in t:
            summary = f"Supply demand cascade evaluated at {tier}."
        elif "cold" in t or "telemetry" in t:
            temp = payload.get("current_temp") or payload.get("temperature", 4.2)
            summary = f"Cold storage telemetry reading logged: {temp}°C."
        else:
            summary = f"Supply chain event {event.type} processed."

    data_dict = {
        "id": str(event.event_id),
        "event_id": str(event.event_id),
        "event_type": str(event.type),
        "topic": str(event.type),
        "agent_name": agent_name,
        "tier": tier,
        "summary": summary,
        "correlation_id": str(event.correlation_id),
        "node_id": str(event.node_id) if event.node_id else None,
        "node_name": payload.get("node_name") or "Assigned Node",
        "created_at": ts_str,
        "ts": ts_str,
        "payload": payload,
    }
    return json.dumps(data_dict)


async def sse_event_stream(
    topics: list[str],
    last_event_id: str | None = None,
    visible_nodes: set[str] | None = None,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generate Server-Sent Events from replay history and live event bus subscriptions.

    - Replays events matching requested topics and node visibility created after last_event_id.
    - Yields live broadcasts matching topics and user node visibility.
    - Periodically yields keepalive heartbeats every 15 seconds.
    - Gracefully unsubscribes upon client disconnect.
    """
    # 1. Replay missed events if last_event_id was provided
    if last_event_id:
        replay_events = in_process_event_bus.get_events_after(
            last_event_id=last_event_id,
            topics=topics,
            visible_nodes=visible_nodes,
        )
        for revt in replay_events:
            yield ServerSentEvent(
                id=str(revt.event_id),
                event=str(revt.type),
                data=_format_sse_data(revt),
            )

    # 2. Setup subscription queue for live events
    queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=1000)

    for topic in topics:
        in_process_event_bus._topic_queues[topic].append(queue)

    try:
        # Initial connected signal
        yield ServerSentEvent(
            event="connected",
            data=json.dumps({"status": "connected", "topics": topics}),
        )

        while True:
            try:
                # Wait for next event or 15s heartbeat timeout
                event = await asyncio.wait_for(queue.get(), timeout=15.0)

                # Scoped node visibility check
                if visible_nodes is not None and str(event.node_id) not in visible_nodes:
                    queue.task_done()
                    continue

                yield ServerSentEvent(
                    id=str(event.event_id),
                    event=str(event.type),
                    data=_format_sse_data(event),
                )
                queue.task_done()

            except TimeoutError:
                # Heartbeat keepalive comment every 15s to prevent client timeout
                yield ServerSentEvent(comment="ping")

    finally:
        in_process_event_bus._remove_queue_from_all_topics(queue)
        logger.debug("SSE stream disconnected; queue removed.")
