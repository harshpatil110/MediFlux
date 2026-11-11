"""Asynchronous in-process event bus for multi-tier cascade propagation.

Strict constraint: NO Apache Kafka or Redpanda. In-process asyncio.Queue & pub-sub.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.events.models import DomainEvent

logger = logging.getLogger(__name__)


class EventBus:
    """In-process asynchronous event bus supporting typed subscriptions and broadcast."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[DomainEvent], Any]]] = defaultdict(list)
        self._history: list[DomainEvent] = []
        self._max_history = 1000
        self._sse_queues: list[asyncio.Queue[DomainEvent]] = []

    def subscribe(self, event_type: str, callback: Callable[[DomainEvent], Any]) -> None:
        """Register a synchronous or asynchronous callback for a specific event type."""
        self._subscribers[event_type].append(callback)
        logger.info("Subscribed to event type: %s", event_type)

    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event to all subscribers and active SSE channels."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        logger.info(
            "EventBus publish: type=%s tier=%s correlation_id=%s",
            event.event_type,
            event.tier,
            event.correlation_id,
        )

        # Notify direct type subscribers
        callbacks = self._subscribers.get(event.event_type, [])
        # Also wildcards
        callbacks += self._subscribers.get("*", [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as exc:
                logger.error("Error in event subscriber callback: %s", exc)

        # Push to SSE subscriber queues
        dead_queues = []
        for q in self._sse_queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(q)

        for dead in dead_queues:
            self._sse_queues.remove(dead)

    def register_sse_queue(self) -> asyncio.Queue[DomainEvent]:
        """Create and register a new queue for streaming events over SSE."""
        q: asyncio.Queue[DomainEvent] = asyncio.Queue(maxsize=100)
        self._sse_queues.append(q)
        return q

    def unregister_sse_queue(self, q: asyncio.Queue[DomainEvent]) -> None:
        """Unregister an SSE consumer queue."""
        if q in self._sse_queues:
            self._sse_queues.remove(q)

    def get_recent_events(self, limit: int = 50) -> list[DomainEvent]:
        """Fetch recent events from memory history."""
        return self._history[-limit:]


event_bus = EventBus()
