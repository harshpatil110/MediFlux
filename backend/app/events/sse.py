"""Server-Sent Events (SSE) streaming handler."""

import asyncio
import json
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.events.bus import event_bus


async def sse_event_stream() -> AsyncGenerator[ServerSentEvent, None]:
    """Generate Server-Sent Events from the in-process event bus for clients."""
    queue = event_bus.register_sse_queue()
    try:
        # Initial ping to establish connection
        yield ServerSentEvent(
            event="connected",
            data=json.dumps({"status": "connected", "stream": "mediflux-events"}),
        )
        while True:
            try:
                # Wait for next domain event or timeout ping
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield ServerSentEvent(
                    event=event.event_type,
                    id=event.event_id,
                    data=event.model_dump_json(),
                )
            except TimeoutError:
                # Keep-alive heartbeat
                yield ServerSentEvent(event="ping", data="keepalive")
    finally:
        event_bus.unregister_sse_queue(queue)
