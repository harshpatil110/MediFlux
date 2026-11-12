"""Background worker subscribing to POS retail sales and triggering cascade orchestration."""

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any

from app.core.config import settings
from app.events.bus import in_process_event_bus
from app.events.models import EventEnvelope
from app.graphs.cascade import CascadeState, cascade_graph

logger = logging.getLogger("mediflux.workers.cascade")


class CascadeWorker:
    """Asynchronous worker managing POS sale consumption and multi-tier cascade propagation."""

    def __init__(self) -> None:
        self._running = False
        self._listener_task: asyncio.Task[Any] | None = None
        self._batch_flush_task: asyncio.Task[Any] | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._micro_batch_queue: list[EventEnvelope] = []
        self._queue_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Start background consumer task."""
        if self._running:
            return

        self._running = True
        self._semaphore = asyncio.Semaphore(settings.CASCADE_MAX_CONCURRENCY)
        self._listener_task = asyncio.create_task(self._consume_pos_sales())

        if settings.CASCADE_MODE == "micro_batch":
            self._batch_flush_task = asyncio.create_task(self._micro_batch_loop())

        # Yield control so event bus subscriber queue is attached
        await asyncio.sleep(0.02)

        logger.info(
            "CascadeWorker started in [%s] mode with max_concurrency=%d",
            settings.CASCADE_MODE,
            settings.CASCADE_MAX_CONCURRENCY,
        )

    async def stop(self) -> None:
        """Gracefully stop background tasks."""
        if not self._running:
            return

        self._running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._batch_flush_task and not self._batch_flush_task.done():
            self._batch_flush_task.cancel()
            try:
                await self._batch_flush_task
            except asyncio.CancelledError:
                pass

        logger.info("CascadeWorker stopped.")

    async def _consume_pos_sales(self) -> None:
        """Event stream consumer listening to pos.sales topic."""
        try:
            async for envelope in in_process_event_bus.subscribe("pos.sales"):
                if not self._running:
                    break

                if settings.CASCADE_MODE == "micro_batch":
                    async with self._queue_lock:
                        self._micro_batch_queue.append(envelope)
                else:
                    # per_event mode: dispatch immediately
                    asyncio.create_task(self._process_single_sale(envelope))
        except asyncio.CancelledError:
            logger.debug("CascadeWorker listener cancelled.")
        except Exception as exc:
            logger.error("CascadeWorker consumer encountered unexpected error: %s", exc)

    async def _process_single_sale(self, envelope: EventEnvelope) -> None:
        """Execute cascade graph for an individual sale event under concurrency semaphore."""
        sem = self._semaphore or asyncio.Semaphore(settings.CASCADE_MAX_CONCURRENCY)
        async with sem:
            payload = envelope.payload
            corr_id = envelope.correlation_id or str(uuid.uuid4())

            initial_state: CascadeState = {
                "event": payload,
                "correlation_id": corr_id,
                "pharmacy_id": str(payload.get("pharmacy_id", "")),
                "product_id": str(payload.get("product_id", "")),
                "batch_id": str(payload.get("batch_id", "")),
                "quantity": int(payload.get("quantity", 1)),
                "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
                "pharmacy_result": None,
                "stockist_result": None,
                "distributor_result": None,
                "manufacturer_result": None,
                "hitl_status": None,
                "trace": [],
                "errors": [],
                "status": "pending",
            }

            try:
                logger.info("Invoking cascade graph for correlation_id=%s", corr_id)
                await cascade_graph.ainvoke(
                    initial_state,
                    config={"configurable": {"thread_id": corr_id}},
                )
            except Exception as exc:
                logger.error("Cascade graph failed for correlation_id=%s: %s", corr_id, exc)

    async def _micro_batch_loop(self) -> None:
        """Periodically flush and aggregate accumulated events in micro_batch mode."""
        window = max(1, settings.CASCADE_MICRO_BATCH_WINDOW_SECONDS)
        while self._running:
            try:
                await asyncio.sleep(window)
                await self._flush_micro_batch()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in micro-batch flush loop: %s", exc)

    async def _flush_micro_batch(self) -> None:
        """Group accumulated events by (pharmacy_id, product_id) and invoke cascade."""
        async with self._queue_lock:
            if not self._micro_batch_queue:
                return
            batch = list(self._micro_batch_queue)
            self._micro_batch_queue.clear()

        # Group by (pharmacy_id, product_id)
        grouped: dict[tuple[str, str], list[EventEnvelope]] = defaultdict(list)
        for env in batch:
            pharm = str(env.payload.get("pharmacy_id", ""))
            prod = str(env.payload.get("product_id", ""))
            grouped[(pharm, prod)].append(env)

        for (pharm_id, prod_id), events in grouped.items():
            total_qty = sum(int(e.payload.get("quantity", 1)) for e in events)
            latest_batch = str(events[-1].payload.get("batch_id", ""))
            corr_id = f"batch-{uuid.uuid4()}"

            initial_state: CascadeState = {
                "event": {
                    "pharmacy_id": pharm_id,
                    "product_id": prod_id,
                    "batch_id": latest_batch,
                    "quantity": total_qty,
                    "batched_event_ids": [e.event_id for e in events],
                },
                "correlation_id": corr_id,
                "pharmacy_id": pharm_id,
                "product_id": prod_id,
                "batch_id": latest_batch,
                "quantity": total_qty,
                "active_tiers": ["pharmacy", "stockist", "distributor", "manufacturer"],
                "pharmacy_result": None,
                "stockist_result": None,
                "distributor_result": None,
                "manufacturer_result": None,
                "hitl_status": None,
                "trace": [],
                "errors": [],
                "status": "pending",
            }

            sem = self._semaphore or asyncio.Semaphore(settings.CASCADE_MAX_CONCURRENCY)
            async with sem:
                try:
                    logger.info("Invoking micro-batch cascade (%d events) for corr_id=%s", len(events), corr_id)
                    await cascade_graph.ainvoke(
                        initial_state,
                        config={"configurable": {"thread_id": corr_id}},
                    )
                except Exception as exc:
                    logger.error("Micro-batch cascade failed for corr_id=%s: %s", corr_id, exc)


cascade_worker = CascadeWorker()
