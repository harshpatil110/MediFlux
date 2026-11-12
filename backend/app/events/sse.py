"""Server-Sent Events (SSE) streaming and replay generator."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.events.sse")


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
                data=revt.model_dump_json(),
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
                    data=event.model_dump_json(),
                )
                queue.task_done()

            except TimeoutError:
                # Heartbeat keepalive comment every 15s to prevent client timeout
                yield ServerSentEvent(comment="ping")

    finally:
        in_process_event_bus._remove_queue_from_all_topics(queue)
        logger.debug("SSE stream disconnected; queue removed.")
