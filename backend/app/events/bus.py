"""Asynchronous in-process event bus for multi-tier cascade propagation.

Strict constraint: NO Apache Kafka or Redpanda in MVP.
In-process asyncio.Queue & pub-sub with database persistence and replay.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from typing import Any

from app.core.config import settings
from app.core.security import get_service_db_client
from app.events.models import EventEnvelope

logger = logging.getLogger("mediflux.events.bus")

STANDARD_TOPICS = {
    "pos.sales",
    "cascade.updates",
    "agent.activity",
    "hitl",
    "coldchain",
    "regulatory",
    "webhooks",
}


class EventBus(ABC):
    """Abstract base class defining the event bus interface."""

    @abstractmethod
    async def publish(self, topic: str, event: EventEnvelope) -> None:
        """Publish an event envelope to a specific topic."""

    @abstractmethod
    async def subscribe(self, topic: str) -> AsyncIterator[EventEnvelope]:
        """Subscribe to a topic and yield an asynchronous stream of event envelopes."""


class InProcessEventBus(EventBus):
    """In-memory asyncio event bus with database persistence and idempotency."""

    def __init__(self, max_history: int = 5000) -> None:
        self._topic_queues: dict[str, list[asyncio.Queue[EventEnvelope]]] = defaultdict(list)
        self._direct_listeners: dict[str, list[Callable[[EventEnvelope], Any]]] = defaultdict(list)
        self._history: list[EventEnvelope] = []
        self._seen_event_ids: set[str] = set()
        self._max_history = max_history
        self._lock = asyncio.Lock()

    async def publish(
        self,
        topic_or_event: str | EventEnvelope,
        event: EventEnvelope | None = None,
    ) -> None:
        """Publish an event envelope to a topic.

        Supports both `publish(topic, event)` and `publish(event)` for backward compatibility.
        """
        if isinstance(topic_or_event, EventEnvelope):
            actual_event = topic_or_event
            actual_topic = actual_event.type
        else:
            actual_topic = topic_or_event
            if event is None:
                raise ValueError("Event must be provided when publishing to a topic")
            actual_event = event

        # 1. Idempotency Check
        async with self._lock:
            if actual_event.event_id in self._seen_event_ids:
                logger.info(
                    "EventBus | Idempotency guard: Event %s already published. Skipping duplicate.",
                    actual_event.event_id,
                )
                return
            self._seen_event_ids.add(actual_event.event_id)

            # Store in memory history
            self._history.append(actual_event)
            if len(self._history) > self._max_history:
                removed = self._history.pop(0)
                # Keep seen_event_ids from growing unboundedly while preserving recent IDs
                if len(self._seen_event_ids) > self._max_history * 2:
                    self._seen_event_ids.discard(removed.event_id)

        # 2. Database Persistence Hook
        await self._persist_to_database(actual_topic, actual_event)

        logger.info(
            "EventBus publish: topic=%s id=%s node=%s correlation_id=%s",
            actual_topic,
            actual_event.event_id,
            actual_event.node_id,
            actual_event.correlation_id,
        )

        # 3. Deliver to topic queues & wildcard queues
        target_queues = list(self._topic_queues.get(actual_topic, []))
        target_queues.extend(self._topic_queues.get("*", []))

        dead_queues = []
        for q in target_queues:
            try:
                q.put_nowait(actual_event)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue is full; dropping subscriber.")
                dead_queues.append(q)

        if dead_queues:
            for q in dead_queues:
                self._remove_queue_from_all_topics(q)

        # 4. Direct callback listeners
        listeners = list(self._direct_listeners.get(actual_topic, []))
        listeners.extend(self._direct_listeners.get("*", []))

        for listener in listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(actual_event))
                else:
                    listener(actual_event)
            except Exception as exc:
                logger.error("Error in direct listener callback for %s: %s", actual_topic, exc)

    async def subscribe(self, topic: str) -> AsyncIterator[EventEnvelope]:
        """Subscribe to a specific topic or wildcard '*' and yield events asynchronously."""
        q: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=1000)
        self._topic_queues[topic].append(q)
        try:
            while True:
                event = await q.get()
                yield event
                q.task_done()
        finally:
            if q in self._topic_queues.get(topic, []):
                self._topic_queues[topic].remove(q)

    def register_listener(
        self,
        topic: str,
        callback: Callable[[EventEnvelope], Any],
    ) -> None:
        """Register a synchronous or asynchronous callback for internal processing."""
        self._direct_listeners[topic].append(callback)

    def _remove_queue_from_all_topics(self, q: asyncio.Queue[EventEnvelope]) -> None:
        """Cleanly remove a dead queue from all subscription lists."""
        for q_list in self._topic_queues.values():
            if q in q_list:
                q_list.remove(q)

    async def _persist_to_database(self, topic: str, event: EventEnvelope) -> None:
        """Persist the event to the Supabase PostgreSQL events table if configured."""
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            return

        try:
            client = get_service_db_client()
            # Idempotent insert with on_conflict
            client.table("events").upsert(
                {
                    "event_id": str(event.event_id),
                    "type": str(event.type),
                    "node_id": str(event.node_id) if event.node_id else None,
                    "payload": event.payload,
                    "correlation_id": str(event.correlation_id),
                },
                on_conflict="event_id",
            ).execute()
        except Exception as exc:
            # Never let database connection blips crash the in-process event bus
            logger.debug("Database event persistence skipped or failed: %s", exc)

    def get_events_after(
        self,
        last_event_id: str | None = None,
        topics: list[str] | None = None,
        visible_nodes: set[str] | None = None,
    ) -> list[EventEnvelope]:
        """Query replay events created after a given event_id matching topics and node visibility."""
        matched: list[EventEnvelope] = []
        found_last = last_event_id is None

        for evt in self._history:
            if not found_last:
                if evt.event_id == last_event_id:
                    found_last = True
                continue

            # Topic filter
            if topics and "*" not in topics and evt.type not in topics:
                continue

            # Node visibility filter (None means global visibility)
            if visible_nodes is not None and str(evt.node_id) not in visible_nodes:
                continue

            matched.append(evt)

        return matched

    def clear(self) -> None:
        """Reset internal in-memory queues and history (useful for test isolation)."""
        self._topic_queues.clear()
        self._direct_listeners.clear()
        self._history.clear()
        self._seen_event_ids.clear()


# Global Singleton Event Bus Instance
in_process_event_bus = InProcessEventBus()
event_bus = in_process_event_bus
